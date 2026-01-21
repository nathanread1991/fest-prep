"""Add OAuth and privacy fields to user model

Revision ID: oauth_privacy_fields
Revises: ca2bb95d843e
Create Date: 2026-01-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'oauth_privacy_fields'
down_revision = 'ca2bb95d843e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add OAuth and privacy fields to users table
    op.add_column('users', sa.Column('oauth_provider', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('oauth_provider_id', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('display_name', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('profile_picture_url', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('marketing_opt_in', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('known_songs', postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column('users', sa.Column('last_login', sa.DateTime(), nullable=True))
    
    # Add indexes for OAuth fields
    op.create_index(op.f('ix_users_oauth_provider'), 'users', ['oauth_provider'], unique=False)
    op.create_index(op.f('ix_users_oauth_provider_id'), 'users', ['oauth_provider_id'], unique=False)


def downgrade() -> None:
    # Remove indexes
    op.drop_index(op.f('ix_users_oauth_provider_id'), table_name='users')
    op.drop_index(op.f('ix_users_oauth_provider'), table_name='users')
    
    # Remove columns
    op.drop_column('users', 'last_login')
    op.drop_column('users', 'known_songs')
    op.drop_column('users', 'marketing_opt_in')
    op.drop_column('users', 'profile_picture_url')
    op.drop_column('users', 'display_name')
    op.drop_column('users', 'oauth_provider_id')
    op.drop_column('users', 'oauth_provider')