"""add_festival_branding_fields

Revision ID: 2ff62d8daa39
Revises: eb8aaef96516
Create Date: 2026-01-14 19:56:40.742353

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


# revision identifiers, used by Alembic.
revision = '2ff62d8daa39'
down_revision = 'eb8aaef96516'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add visual branding fields to festivals table
    op.add_column('festivals', sa.Column('logo_url', sa.Text(), nullable=True))
    op.add_column('festivals', sa.Column('primary_color', sa.String(length=7), nullable=True))
    op.add_column('festivals', sa.Column('secondary_color', sa.String(length=7), nullable=True))
    op.add_column('festivals', sa.Column('accent_colors', ARRAY(sa.String()), nullable=True))
    op.add_column('festivals', sa.Column('branding_extracted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove visual branding fields from festivals table
    op.drop_column('festivals', 'branding_extracted_at')
    op.drop_column('festivals', 'accent_colors')
    op.drop_column('festivals', 'secondary_color')
    op.drop_column('festivals', 'primary_color')
    op.drop_column('festivals', 'logo_url')