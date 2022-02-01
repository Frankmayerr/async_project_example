import datetime
from unittest.mock import Mock
import logging
import time

import pytest
from mock import patch

import app.database as database
import settings
from app.bus_service import ApplicantAlreadyRecommended
from app.bus_service import ApplicantRejected
from app.bus_service import ApplicantSBRejected
from app.bus_service import ApplicantSecurityCheckCreated
from app.bus_service import ApplicantSecurityCheckFailed
from app.bus_service import ApplicantSecurityCheckFilled
from app.bus_service import ApplicantSecurityCheckFinished
from app.bus_service import ApplicantSecurityCheckPrepared
from app.bus_service import ApplicantSelfRejected
from app.bus_service import Inviter
from app.bus_service import VacancyRecommendationSubmitted
from app.event_handlers import push_arms_failed
from app.event_handlers import push_arms_filled
from app.event_handlers import push_arms_finished
from app.event_handlers import push_arms_url_to_huntflow
from app.event_handlers import push_candidate_to_huntflow
from app.event_handlers import render_resume
from app.huntflow_api import AsyncClient
from app.sync import sync_applicant_vacancy_statuses
from app.models import SyncError

client = AsyncClient('http://localhost', 'TOKEN')

pytestmark = pytest.mark.asyncio

candidate = {
    'id': 123,
    'inviter': Inviter(first_name='Василий', last_name='Петров', username='petrovasiliy'),
    'first_name': 'first_name',
    'last_name': 'last_name',
    'phone': '+799999999',
    'city': 'Ekat',
    'about': 'about',
    'circle': 'circle',
    'specialization': 'spec',
    'is_notified': True,
    'files': ['url1', 'url2']
}

expected_resume_str = (
        'Рекомендатель: Василий Петров\n'
        'Логин рекомендателя: petrovasiliy\n'
        'Почта рекомендателя: user1@tochka.com\n\n'
        'Город кандидата: Ekat\n'
        'Круг: circle\n'
        'Уведомлён и ждет ответа: да\n'
        'Комментарий: about'
    )


@pytest.fixture()
def check_no_errors(caplog):
    def _assert_no_errors():
        assert not [r.message for r in caplog.records if r.levelno >= logging.ERROR]
    return _assert_no_errors


@pytest.fixture()
def assert_log_errors(caplog):
    def _assert_log_warnings(*errors):
        time.sleep(0.1)  # по какой-то причине не всегда успевает захватить логи
        assert [r.message for r in caplog.records if r.levelno >= logging.ERROR] == list(errors)
        caplog.clear()
    return _assert_log_warnings


@patch('app.huntflow_api.AsyncClient.request_post')
async def test_recommendation_push_to_hf(request_mock):
    request_mock.return_value = {'id': 1}
    candidate_id = await client.push_candidate(
        candidate['first_name'], candidate['last_name'],
        candidate['phone'], candidate['specialization'],
        render_resume(VacancyRecommendationSubmitted(**candidate), 'user1@tochka.com'),
        files_ids=[123, 456]
    )
    assert candidate_id == 1

    request_mock.assert_called_once_with(
        f'/account/{settings.HUNTFLOW_ACCOUNT}/applicants',
        {
            'first_name': candidate['first_name'],
            'last_name': candidate['last_name'],
            'phone': candidate['phone'],
            'position': candidate['specialization'],
            'externals': [
                {
                    'data': {
                        'body': expected_resume_str
                    },
                    'files': [
                        {'id': 123},
                        {'id': 456}
                    ],
                    'auth_type': 'NATIVE',
                    'account_source': settings.HUNTFLOW_RECOMMENDATION_ACCOUNT_SOURCE
                },
            ]
        }
    )


@patch('app.huntflow_api.AsyncClient.request_post')
async def test_recommendation_push_to_vacancy(request_mock):
    await client.push_candidate_to_vacancy(1)

    request_mock.assert_called_once_with(
        f'/account/{settings.HUNTFLOW_ACCOUNT}/applicants/1/vacancy',
        {
            'vacancy': settings.HUNTFLOW_REFERRAL_VACANCY,
            'status': settings.HUNTFLOW_CANDIDATE_INIT_STATUS,
            'comment': '',
            'files': [],
            'rejection_reason': None
        }
    )


@patch('app.huntflow_api.AsyncClient.account_upload_files')
@patch('app.utlis.files.download_files')
@patch('app.huntflow_api.AsyncClient.push_candidate')
@patch('app.huntflow_api.AsyncClient.push_candidate_to_vacancy')
@patch('chassis.clients.ie_intranet_ad.Client.get_users')
async def test_push_candidate(
    get_users_mock, push_to_vacancy_mock, push_candidate_mock, download_files_mock, upload_files_mock
):
    download_files_mock.return_value = [b'1', b'2']
    get_users_mock.return_value = [Mock(mail='user1@tochka.com')]
    upload_files_mock.return_value = [{'id': 1}, {'id': 2}]
    push_candidate_mock.return_value = 456
    push_to_vacancy_mock.return_value = 789
    await push_candidate_to_huntflow(VacancyRecommendationSubmitted(**candidate))
    applicant = await database.get_applicant_by_id(123)
    assert dict(applicant) == {
        'id': 123,
        'applicant_id': 456,
        'status_id': 789,
        'files_ids': [1, 2],
        'last_sync_error': None
    }

    download_files_mock.assert_called_once_with(['url1', 'url2'])

    push_candidate_mock.assert_called_once_with(**{
        'first_name': candidate['first_name'],
        'last_name': candidate['last_name'],
        'phone': candidate['phone'],
        'specialization': candidate['specialization'],
        'body': expected_resume_str,
        'files_ids': [1, 2]
    })
    push_to_vacancy_mock.assert_called_once_with(456, files_ids=[1, 2])


async def test_db_queries():
    await database.create_applicant(123)
    applicant = await database.get_applicant_by_id(123)
    assert dict(applicant) == {
        'id': 123,
        'applicant_id': None,
        'status_id': None,
        'files_ids': None,
        'last_sync_error': None,
    }

    await database.update_applicant(123, 456)
    applicant = await database.get_applicant_by_id(123)
    assert dict(applicant) == {
        'id': 123,
        'applicant_id': 456,
        'status_id': None,
        'files_ids': None,
        'last_sync_error': None,
    }

    await database.update_applicant(123, status_id=789)
    applicant = await database.get_applicant_by_id(123)
    assert dict(applicant) == {
        'id': 123,
        'applicant_id': 456,
        'status_id': 789,
        'files_ids': None,
        'last_sync_error': None,
    }

    await database.create_applicant(1, 2, 3)
    applicant = await database.get_applicant_by_id(1)
    assert dict(applicant) == {
        'id': 1,
        'applicant_id': 2,
        'status_id': 3,
        'files_ids': None,
        'last_sync_error': None,
    }


@patch('bus.sender.Sender.send')
@patch('app.huntflow_api.AsyncClient.request_get')
async def test_sync_secure_check_applicants_statuses(request_mock, send_mock):
    request_mock.side_effect = lambda path, params: (
        {'items': ([{'id': 789}] if params.get('status') == settings.HUNTFLOW_SECURITY_CHECK_STATUS else [])}
    )
    await database.create_applicant(123, 789, 456)
    await database.create_applicant(111, 121, 111)
    await sync_applicant_vacancy_statuses()

    applicant = await database.get_applicant_by_id(123)
    assert applicant['status_id'] == settings.HUNTFLOW_SECURITY_CHECK_STATUS

    applicant = await database.get_applicant_by_id(111)
    assert applicant['status_id'] == 111

    send_mock.assert_called_with(ApplicantSecurityCheckPrepared(id=123))


@pytest.mark.parametrize(
    ('event_cls', 'reason'), [
        (ApplicantRejected, 'Отказ. МЫ: нехороший человек'),
        (ApplicantSelfRejected, 'Отказ. САМ: не хочет работать'),
        (ApplicantSBRejected, 'Отказ. МЫ: Не прошел СБ'),
    ],
)
@patch('app.huntflow_api.AsyncClient.get_rejection_reason')
@patch('bus.sender.Sender.send')
@patch('app.huntflow_api.AsyncClient.request_get')
@patch('app.huntflow_api.AsyncClient.get_applicant_log')
async def test_sync_rejected_applicants_statuses(
    log_mock, request_mock, send_mock, get_reason_mock, event_cls, reason
):
    get_reason_mock.return_value = reason
    request_mock.side_effect = lambda path, params: (
        {'items': ([{'id': 789}] if params.get('status') == settings.HUNTFLOW_REJECTED_STATUS else [])}
    )

    async def get_log_items(hf_id):
        yield {'id': 789, 'status': settings.HUNTFLOW_REJECTED_STATUS, 'rejection_reason': 123}

    log_mock.side_effect = get_log_items
    await database.create_applicant(123, 789, 456)
    await sync_applicant_vacancy_statuses()
    applicant = await database.get_applicant_by_id(123)
    assert applicant['status_id'] == settings.HUNTFLOW_REJECTED_STATUS
    send_mock.assert_called_once_with(event_cls(id=123))


@patch('app.huntflow_api.AsyncClient.get_rejection_reason')
@patch('bus.sender.Sender.send')
@patch('app.huntflow_api.AsyncClient.request_get')
@patch('app.huntflow_api.AsyncClient.get_applicant_log')
async def test_sync_rejected_applicatns_no_rejection_reason(
    log_mock, request_mock, get_reason_mock, reason, assert_log_errors, caplog, check_no_errors
):
    get_reason_mock.return_value = reason
    request_mock.side_effect = lambda path, params: (
        {'items': ([{'id': 789}] if params.get('status') == settings.HUNTFLOW_REJECTED_STATUS else [])}
    )

    async def get_log_items(hf_id):
        yield {'id': 789, 'status': settings.HUNTFLOW_REJECTED_STATUS, 'rejection_reason': None}

    log_mock.side_effect = get_log_items
    await database.create_applicant(123, 789, 456)

    applicant = await database.get_applicant_by_id(123)
    assert applicant['last_sync_error'] is None
    await sync_applicant_vacancy_statuses()
    assert_log_errors("('Invalid rejected status for applicant %s', 789)")

    applicant = await database.get_applicant_by_id(123)
    assert applicant['last_sync_error'] == SyncError.no_rejection_reason
    await sync_applicant_vacancy_statuses()
    check_no_errors()


@patch('bus.sender.Sender.send')
@patch('app.huntflow_api.AsyncClient.request_get')
async def test_sync_self_reserved_applicants_statuses(request_mock, send_mock):
    request_mock.side_effect = lambda path, params: (
        {'items': ([{'id': 789}] if params.get('status') == settings.HUNTFLOW_RESERVE_STATUS else [])}
    )
    await database.create_applicant(123, 789, 456)
    await sync_applicant_vacancy_statuses()
    applicant = await database.get_applicant_by_id(123)
    assert applicant['status_id'] == settings.HUNTFLOW_RESERVE_STATUS
    send_mock.assert_called_once_with(ApplicantAlreadyRecommended(id=123))


@patch('app.huntflow_api.AsyncClient.request_post')
async def test_push_arms_url_to_huntflow(request_mock):
    await database.create_applicant(123, 456, 789)
    await push_arms_url_to_huntflow(ApplicantSecurityCheckCreated(
        id=123, arms_url='test_url', arms_id='1', arms_created_at=datetime.datetime.now()
    ))

    request_mock.assert_called_once_with(
        f'/account/{settings.HUNTFLOW_ACCOUNT}/applicants/456/vacancy',
        {
            'vacancy': settings.HUNTFLOW_REFERRAL_VACANCY,
            'status': settings.HUNTFLOW_SECURITY_CHECK_STATUS,
            'comment': 'Создана ссылка на проверку в СБ: test_url',
            'files': [],
            'rejection_reason': None
        }
    )


@patch('app.huntflow_api.AsyncClient.request_post')
async def test_push_arms_filled_to_huntflow(request_mock):
    await database.create_applicant(123, 456, 789)
    await push_arms_filled(ApplicantSecurityCheckFilled(id=123))

    request_mock.assert_called_once_with(
        f'/account/{settings.HUNTFLOW_ACCOUNT}/applicants/456/vacancy',
        {
            'vacancy': settings.HUNTFLOW_REFERRAL_VACANCY,
            'status': settings.HUNTFLOW_SECURITY_CHECK_STATUS,
            'comment': 'Анкета СБ заполнена',
            'files': [],
            'rejection_reason': None
        }
    )


@patch('app.huntflow_api.AsyncClient.request_post')
async def test_push_arms_failed_event_to_huntflow(request_mock):
    await database.create_applicant(123, 456, 789)
    await push_arms_failed(ApplicantSecurityCheckFailed(id=123, arms_id='1', candidate_url='url'))

    request_mock.assert_called_once_with(
        f'/account/{settings.HUNTFLOW_ACCOUNT}/applicants/456/vacancy',
        {
            'vacancy': settings.HUNTFLOW_REFERRAL_VACANCY,
            'status': settings.HUNTFLOW_SECURITY_CHECK_STATUS,
            'comment': 'Анкета СБ была заполнена некорректно.',
            'files': [],
            'rejection_reason': None
        }
    )


@patch('app.huntflow_api.AsyncClient.request_post')
async def test_push_arms_finished_event_to_huntflow(request_mock):
    await database.create_applicant(123, 456, 789)
    await push_arms_finished(ApplicantSecurityCheckFinished(id=123, arms_id='1', status='done'))

    request_mock.assert_called_once_with(
        f'/account/{settings.HUNTFLOW_ACCOUNT}/applicants/456/vacancy',
        {
            'vacancy': settings.HUNTFLOW_REFERRAL_VACANCY,
            'status': settings.HUNTFLOW_SECURITY_CHECK_STATUS,
            'comment': 'Проверка СБ завершена со статусом: Проверка завершена.',
            'files': [],
            'rejection_reason': None
        }
    )
