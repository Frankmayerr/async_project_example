"""add file ids column

Revision ID: e48a3c57d043
Revises: 4c25a9f23a36
Create Date: 2021-06-16 10:37:57.186435

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'e48a3c57d043'
down_revision = '4c25a9f23a36'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('applicants', sa.Column('files_ids', sa.ARRAY(sa.Integer), nullable=True))


def downgrade():
    op.drop_column('applicants', 'files_ids')
