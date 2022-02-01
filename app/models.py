import enum

import sqlalchemy

metadata = sqlalchemy.MetaData()


class SyncError(enum.Enum):
    no_rejection_reason = 1


applicants_table = sqlalchemy.Table(
    'applicants',
    metadata,
    sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True, autoincrement=False),
    sqlalchemy.Column('applicant_id', sqlalchemy.Integer, unique=True),
    sqlalchemy.Column('status_id', sqlalchemy.Integer),
    sqlalchemy.Column('files_ids', sqlalchemy.ARRAY(sqlalchemy.Integer)),
    sqlalchemy.Column('last_sync_error', sqlalchemy.Enum(SyncError), nullable=True),
)
