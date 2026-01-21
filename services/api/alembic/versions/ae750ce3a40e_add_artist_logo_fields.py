"""add_artist_logo_fields

Revision ID: ae750ce3a40e
Revises: 2ff62d8daa39
Create Date: 2026-01-14 19:57:15.274969

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ae750ce3a40e'
down_revision = '2ff62d8daa39'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add logo fields to artists table
    op.add_column('artists', sa.Column('logo_url', sa.Text(), nullable=True))
    op.add_column('artists', sa.Column('logo_source', sa.String(length=50), nullable=True))


def downgrade() -> None:
    # Remove logo fields from artists table
    op.drop_column('artists', 'logo_source')
    op.drop_column('artists', 'logo_url')