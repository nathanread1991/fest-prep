"""add_text_color_to_festivals

Revision ID: 2d60b1c8955d
Revises: ae750ce3a40e
Create Date: 2026-01-14 21:31:33.355338

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2d60b1c8955d'
down_revision = 'ae750ce3a40e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add text_color column to festivals table
    op.add_column('festivals', sa.Column('text_color', sa.String(7), nullable=True))


def downgrade() -> None:
    # Remove text_color column from festivals table
    op.drop_column('festivals', 'text_color')