"""Add last_sync_error column

Revision ID: eeaf0e41447a
Revises: e48a3c57d043
Create Date: 2021-07-28 19:29:28.104435

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'eeaf0e41447a'
down_revision = 'e48a3c57d043'
branch_labels = None
depends_on = None


def upgrade():
    sync_error = postgresql.ENUM('no_rejection_reason', name='sync_error')
    sync_error.create(op.get_bind())
    op.add_column(
        'applicants',
        sa.Column('last_sync_error', sa.Enum('no_rejection_reason', name='sync_error'), nullable=True)
    )


def downgrade():
    op.drop_column('applicants', 'last_sync_error')
    sync_error = postgresql.ENUM('no_rejection_reason', name='sync_error')
    sync_error.drop(op.get_bind())
