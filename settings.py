import logging
import sys

import sentry_sdk
from environs import Env
from sentry_sdk.integrations.logging import LoggingIntegration

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

env = Env()
env.read_env(override=True)

DB_DSN = env.str('APP_DB_DSN')

SERVICE_NAME = 'huntflow-candidates'
SERVICE_BUS_DSN = env.str('APP_SERVICE_BUS_DSN')
SENTRY_DSN = env.str('SENTRY_DSN', None)
SENTRY_ENVIRONMENT = env.str('SENTRY_ENVIRONMENT', None)

IE_INTRANET_AD_API = env.str('IE_INTRANET_AD_API')

TOKEN = env.str('APP_TOKEN', 'SECRET')

HUNTFLOW_API = env.str('APP_HUNTFLOW_API')
HUNTFLOW_ACCOUNT = env.int('APP_HUNTFLOW_ACCOUNT', 111)
HUNTFLOW_TOKEN = env.str('APP_HUNTFLOW_TOKEN', None)
HUNTFLOW_REFERRAL_VACANCY = env.int('APP_HUNTFLOW_REFERRAL_VACANCY', 222)
HUNTFLOW_CANDIDATE_INIT_STATUS = env.int('APP_HUNTFLOW_CANDIDATE_INIT_STATUS', None)
HUNTFLOW_SECURITY_CHECK_STATUS = env.int('APP_HUNTFLOW_SECURITY_CHECK_STATUS', 333)
HUNTFLOW_REJECTED_STATUS = env.int('APP_HUNTFLOW_REJECTED_STATUS', 444)
HUNTFLOW_RESERVE_STATUS = env.int('APP_HUNTFLOW_RESERVE_STATUS', 555)
HUNTFLOW_RECOMMENDATION_ACCOUNT_SOURCE = env.str('APP_HUNTFLOW_RECOMMENDATION_ACCOUNT_SOURCE', None)

APP_SCHEDULER_INTERVAL_MINUTES = env.int('APP_SCHEDULER_INTERVAL_MINUTES', 5)

if SENTRY_DSN:
    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR
    )
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        integrations=[sentry_logging]
    )
