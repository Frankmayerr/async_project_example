import datetime as dt
from typing import List
from typing import Optional

from bus import Event
from bus import Listener
from bus import Sender
from pydantic import BaseModel

import settings

listener: Listener = Listener(
    dsn=settings.SERVICE_BUS_DSN,
    service_name=settings.SERVICE_NAME,
)

sender = Sender(
    dsn=settings.SERVICE_BUS_DSN,
    service_name=settings.SERVICE_NAME,
)


class ApplicantSecurityCheckPrepared(Event, sender=settings.SERVICE_NAME):
    id: int


class ApplicantRejected(Event, sender=settings.SERVICE_NAME):
    id: int


class ApplicantSelfRejected(Event, sender=settings.SERVICE_NAME):
    id: int


class ApplicantAlreadyRecommended(Event, sender=settings.SERVICE_NAME):
    id: int


class ApplicantSBRejected(Event, sender=settings.SERVICE_NAME):
    id: int


class ApplicantSecurityCheckFilled(Event, sender='hr-one'):
    id: int


class ApplicantSecurityCheckFailed(Event, sender='hr-one'):
    id: int
    arms_id: str
    candidate_url: str


class ApplicantSecurityCheckFinished(Event, sender='hr-one'):
    id: int
    arms_id: str
    status: str


class ApplicantSecurityCheckCreated(Event, sender='hr-one'):
    id: int
    arms_id: str
    arms_url: str
    arms_created_at: dt.datetime


class Inviter(BaseModel):
    first_name: str
    last_name: str
    username: str


class VacancyRecommendationSubmitted(Event, sender='hr-one'):
    id: int
    inviter: Inviter
    first_name: str
    last_name: str
    phone: str
    city: str
    about: Optional[str]
    circle: Optional[str]
    specialization: Optional[str]
    is_notified: bool
    files: Optional[List[str]]
