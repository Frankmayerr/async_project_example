import logging

import pydantic

import settings
from app.database import get_all_applicants
from app.database import update_applicant
from app.event_handlers import send_applicant_rejected_event
from app.event_handlers import send_applicant_reserved_event
from app.event_handlers import send_applicant_security_check_prepared_event
from app.huntflow_api import huntflow_client

logger = logging.getLogger(__name__)

STATUS_EVENT_HANDLERS = [
    (settings.HUNTFLOW_SECURITY_CHECK_STATUS, send_applicant_security_check_prepared_event),
    (settings.HUNTFLOW_REJECTED_STATUS, send_applicant_rejected_event),
    (settings.HUNTFLOW_RESERVE_STATUS, send_applicant_reserved_event)
]


class ApplicantStatus(pydantic.BaseModel):
    id: int
    status_id: int


async def sync_applicant_vacancy_statuses() -> None:
    applicants = await get_all_applicants()
    applicants_by_hf_id = {
        a['applicant_id']: ApplicantStatus(
            id=a['id'],
            status_id=a['status_id'],
        )
        for a in applicants
    }

    for status, applicant_status_sender in STATUS_EVENT_HANDLERS:
        logger.info('Sync applicants with status %s', status)
        checked_applicants = await huntflow_client.get_vacancy_status_applicants(
            settings.HUNTFLOW_REFERRAL_VACANCY,
            status
        )
        async for applicant in checked_applicants:
            applicant_id = applicant['id']
            if applicant_id not in applicants_by_hf_id:
                continue
            try:
                applicant_status: ApplicantStatus = applicants_by_hf_id[applicant['id']]
                if applicant_status.status_id != status:
                    await applicant_status_sender(applicant_status.id, applicant_id)
                    await update_applicant(applicant_status.id, status_id=status)
            except Exception as e:
                logger.exception(str(e))
