import logging
import typing as t

from chassis.clients.ie_intranet_ad import Client as IntranetADClient

import settings
from app import database
from app.bus_service import ApplicantAlreadyRecommended
from app.bus_service import ApplicantRejected
from app.bus_service import ApplicantSBRejected
from app.bus_service import ApplicantSecurityCheckCreated
from app.bus_service import ApplicantSecurityCheckFailed
from app.bus_service import ApplicantSecurityCheckFilled
from app.bus_service import ApplicantSecurityCheckFinished
from app.bus_service import ApplicantSecurityCheckPrepared
from app.bus_service import ApplicantSelfRejected
from app.bus_service import VacancyRecommendationSubmitted
from app.bus_service import listener
from app.bus_service import sender
from app.huntflow_api import huntflow_client
from app.models import SyncError
from app.utlis import files as files_utils
from app.utlis import huntflow as huntflow_utils

logger = logging.getLogger(__name__)


def render_resume(candidate: VacancyRecommendationSubmitted, email: t.Optional[str]) -> str:
    return (
        f'Рекомендатель: {candidate.inviter.first_name} {candidate.inviter.last_name}\n'
        f'Логин рекомендателя: {candidate.inviter.username}\n'
        f'Почта рекомендателя: {email}\n\n'
        f'Город кандидата: {candidate.city}\n'
        f'Круг: {candidate.circle or "нет информации о круге"}\n'
        f'Уведомлён и ждет ответа: {"да" if candidate.is_notified else "нет"}\n'
        f'Комментарий: {candidate.about or "без комментария"}'
    )


ad_client: IntranetADClient = IntranetADClient(
    url=settings.IE_INTRANET_AD_API, token=settings.TOKEN
)


@listener.on(VacancyRecommendationSubmitted)
async def push_candidate_to_huntflow(event: VacancyRecommendationSubmitted) -> None:
    users = ad_client.get_users(event.inviter.username)
    email = users[0].mail if len(users) == 1 else ''
    resume_str = render_resume(event, email)
    applicant = await database.get_applicant_by_id(event.id)

    if applicant is None:
        await database.create_applicant(event.id)
        applicant = {'id': event.id}

    await _push_candidate(applicant, event, resume_str)
    await _push_candidate_to_vacancy(applicant, event)


async def _push_candidate_to_vacancy(
    applicant: t.Dict[str, t.Any],
    event: VacancyRecommendationSubmitted
) -> None:
    if applicant.get('status_id') is None:
        applicant_vacancy_status = await huntflow_client.push_candidate_to_vacancy(
            applicant['applicant_id'], files_ids=applicant.get('files_ids')
        )
        await database.update_applicant(
            event.id, status_id=applicant_vacancy_status
        )


async def _push_candidate(
    applicant: t.Dict[str, t.Any],
    event: VacancyRecommendationSubmitted,
    resume_str: str
) -> None:
    if applicant.get('applicant_id') is not None:
        return
    candidate: t.Dict[str, t.Any] = {
        'first_name': event.first_name,
        'last_name': event.last_name,
        'phone': event.phone,
        'specialization': event.specialization or '',
        'body': resume_str,
    }

    if event.files and len(event.files) > 0:
        files = await huntflow_client.account_upload_files(
            await files_utils.download_files(event.files)
        )
        candidate['files_ids'] = applicant['files_ids'] = huntflow_utils.get_files_ids(files)
        logger.info('uploaded files %s', str(candidate['files_ids']))

    applicant_id = await huntflow_client.push_candidate(**candidate)
    await database.update_applicant(event.id, applicant_id, files_ids=candidate.get('files_ids'))
    applicant['applicant_id'] = applicant_id


@listener.on(ApplicantSecurityCheckCreated)
async def push_arms_url_to_huntflow(event: ApplicantSecurityCheckCreated) -> None:
    applicant = await database.get_applicant_by_id(event.id)
    await huntflow_client.push_candidate_to_vacancy(
        applicant['applicant_id'],
        status_id=settings.HUNTFLOW_SECURITY_CHECK_STATUS,
        comment=f'Создана ссылка на проверку в СБ: {event.arms_url}'
    )


@listener.on(ApplicantSecurityCheckFilled)
async def push_arms_filled(event: ApplicantSecurityCheckFilled) -> None:
    applicant = await database.get_applicant_by_id(event.id)
    await huntflow_client.push_candidate_to_vacancy(
        applicant['applicant_id'],
        status_id=settings.HUNTFLOW_SECURITY_CHECK_STATUS,
        comment='Анкета СБ заполнена'
    )


@listener.on(ApplicantSecurityCheckFailed)
async def push_arms_failed(event: ApplicantSecurityCheckFailed) -> None:
    applicant = await database.get_applicant_by_id(event.id)
    await huntflow_client.push_candidate_to_vacancy(
        applicant['applicant_id'],
        status_id=settings.HUNTFLOW_SECURITY_CHECK_STATUS,
        comment='Анкета СБ была заполнена некорректно.'
    )


@listener.on(ApplicantSecurityCheckFinished)
async def push_arms_finished(event: ApplicantSecurityCheckFinished) -> None:
    applicant = await database.get_applicant_by_id(event.id)
    status_description = {
        'done': 'Проверка завершена.',
        'refuse': 'Отказ от проверки.'
    }
    await huntflow_client.push_candidate_to_vacancy(
        applicant['applicant_id'],
        status_id=settings.HUNTFLOW_SECURITY_CHECK_STATUS,
        comment=f'Проверка СБ завершена со статусом: {status_description.get(event.status, event.status)}'
    )


async def send_applicant_security_check_prepared_event(id_: int, hf_id: int) -> None:
    await sender.send(ApplicantSecurityCheckPrepared(id=id_))


class RejectedCandidateStatusError(Exception):
    pass


async def send_applicant_rejected_event(id_: int, hf_id: int) -> None:
    logs = await huntflow_client.get_applicant_log(hf_id)
    async for log in logs:
        if log.get('status') != settings.HUNTFLOW_REJECTED_STATUS or not log.get('rejection_reason'):
            continue

        comment = (await huntflow_client.get_rejection_reason(log['rejection_reason'])).lower()
        if 'сам:' in comment:
            await sender.send(ApplicantSelfRejected(id=id_))
        elif 'не прошел сб' in comment:
            await sender.send(ApplicantSBRejected(id=id_))
        else:
            await sender.send(ApplicantRejected(id=id_))
        return
    applicant = await database.get_applicant_by_id(id_)
    last_sync_error = applicant.get('last_sync_error')
    await database.update_applicant(id_=id_, last_sync_error=SyncError.no_rejection_reason)

    if not last_sync_error or last_sync_error is not SyncError.no_rejection_reason:
        raise RejectedCandidateStatusError('Invalid rejected status for applicant %s', hf_id)


async def send_applicant_reserved_event(id_: int, hf_id: int) -> None:
    await sender.send(ApplicantAlreadyRecommended(id=id_))
