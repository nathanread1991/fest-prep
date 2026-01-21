"""merge_migration_heads

Revision ID: eb8aaef96516
Revises: 1d2bc2efe8e7, audit_log_table
Create Date: 2026-01-13 23:12:07.360704

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb8aaef96516'
down_revision = ('1d2bc2efe8e7', 'audit_log_table')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass