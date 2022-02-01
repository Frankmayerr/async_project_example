import asyncio
import datetime
import logging
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import settings
from app.bus_service import listener
from app.bus_service import sender
from app.huntflow_api import huntflow_client
from app.sync import sync_applicant_vacancy_statuses

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

loop = asyncio.get_event_loop()


async def listen_bus_events() -> None:
    def stop_loop() -> None:
        loop.create_task(listener.stop())
        loop.create_task(sender.close())
        loop.create_task(huntflow_client.session.close())

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(sig, stop_loop)
    await sender.connect()
    await listener.listen()

if __name__ == '__main__':
    scheduler.start()
    scheduler.add_job(
        sync_applicant_vacancy_statuses,
        'interval',
        minutes=settings.APP_SCHEDULER_INTERVAL_MINUTES,
        next_run_time=datetime.datetime.now(),
        max_instances=1,
    )
    loop.create_task(listen_bus_events())
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
