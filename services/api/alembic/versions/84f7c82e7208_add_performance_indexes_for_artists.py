"""add_performance_indexes_for_artists

Revision ID: 84f7c82e7208
Revises: 79855e329c76
Create Date: 2026-01-15 20:12:18.995034

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '84f7c82e7208'
down_revision = '79855e329c76'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add indexes for performance optimization
    
    # Index on artist name for search queries (case-insensitive)
    op.execute('CREATE INDEX IF NOT EXISTS idx_artists_name_lower ON artists (LOWER(name))')
    
    # Index on spotify_id for orphaned artist detection
    op.create_index('idx_artists_spotify_id', 'artists', ['spotify_id'], unique=False)
    
    # Index on created_at for sorting
    op.create_index('idx_artists_created_at', 'artists', ['created_at'], unique=False)
    
    # Index on setlists.artist_id for orphaned artist detection
    op.create_index('idx_setlists_artist_id', 'setlists', ['artist_id'], unique=False)
    
    # Composite index for genres array search (PostgreSQL GIN index)
    op.execute('CREATE INDEX IF NOT EXISTS idx_artists_genres_gin ON artists USING gin(genres)')


def downgrade() -> None:
    # Remove indexes
    op.execute('DROP INDEX IF EXISTS idx_artists_name_lower')
    op.drop_index('idx_artists_spotify_id', table_name='artists')
    op.drop_index('idx_artists_created_at', table_name='artists')
    op.drop_index('idx_setlists_artist_id', table_name='setlists')
    op.execute('DROP INDEX IF EXISTS idx_artists_genres_gin')
