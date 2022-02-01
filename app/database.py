import typing as t
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from databases import Database

import settings
from app.models import SyncError
from app.models import applicants_table


@asynccontextmanager
async def connect_database() -> AsyncGenerator[Database, None]:
    async with Database(settings.DB_DSN) as db:
        yield db


async def create_applicant(
    id_: int, applicant_id: t.Optional[int] = None, status_id: t.Optional[int] = None
) -> None:
    query = applicants_table.insert()
    values = {
        'id': id_,
        'applicant_id': applicant_id,
        'status_id': status_id
    }
    async with connect_database() as db:
        await db.execute(query=query, values=values)


async def update_applicant(
    id_: int,
    applicant_id: t.Optional[int] = None,
    status_id: t.Optional[int] = None,
    files_ids: t.Optional[t.List[int]] = None,
    last_sync_error: t.Optional[SyncError] = None,
) -> None:
    values: t.Dict[str, t.Any] = {}
    if applicant_id is not None:
        values['applicant_id'] = applicant_id
    if status_id is not None:
        values['status_id'] = status_id
    if files_ids is not None:
        values['files_ids'] = files_ids
    if last_sync_error is not None:
        values['last_sync_error'] = last_sync_error

    query = (
        applicants_table.update()
        .where(applicants_table.c.id == id_)
        .values(**values)
    )
    async with connect_database() as db:
        await db.execute(query=query)


async def get_applicant_by_id(id_: int) -> t.Any:
    query = applicants_table.select().where(
        applicants_table.c.id == id_
    )
    async with connect_database() as db:
        return await db.fetch_one(query=query)


async def get_all_applicants() -> t.Any:
    async with connect_database() as db:
        return await db.fetch_all(query=applicants_table.select())
