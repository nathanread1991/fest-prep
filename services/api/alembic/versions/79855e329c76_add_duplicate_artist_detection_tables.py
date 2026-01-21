"""add_duplicate_artist_detection_tables

Revision ID: 79855e329c76
Revises: 2d60b1c8955d
Create Date: 2026-01-15 13:21:18.516558

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY


# revision identifiers, used by Alembic.
revision = '79855e329c76'
down_revision = '2d60b1c8955d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create not_duplicate_pairs table
    op.create_table(
        'not_duplicate_pairs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('artist_id_1', UUID(as_uuid=True), sa.ForeignKey('artists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('artist_id_2', UUID(as_uuid=True), sa.ForeignKey('artists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('marked_by', sa.String(255), nullable=False),
        sa.Column('marked_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.UniqueConstraint('artist_id_1', 'artist_id_2', name='unique_pair'),
        sa.CheckConstraint('artist_id_1 < artist_id_2', name='ordered_pair')
    )
    
    # Create indexes for not_duplicate_pairs
    op.create_index('idx_not_duplicate_pairs_artist1', 'not_duplicate_pairs', ['artist_id_1'])
    op.create_index('idx_not_duplicate_pairs_artist2', 'not_duplicate_pairs', ['artist_id_2'])
    
    # Create merge_audit_log table
    op.create_table(
        'merge_audit_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('primary_artist_id', UUID(as_uuid=True), sa.ForeignKey('artists.id', ondelete='SET NULL'), nullable=True),
        sa.Column('primary_artist_name', sa.String(255), nullable=False),
        sa.Column('merged_artist_ids', ARRAY(UUID(as_uuid=True)), nullable=False),
        sa.Column('merged_artist_names', ARRAY(sa.Text()), nullable=False),
        sa.Column('festivals_transferred', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('setlists_transferred', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('spotify_data_source', sa.String(255), nullable=True),
        sa.Column('performed_by', sa.String(255), nullable=False),
        sa.Column('performed_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True)
    )
    
    # Create indexes for merge_audit_log
    op.create_index('idx_merge_audit_primary', 'merge_audit_log', ['primary_artist_id'])
    op.create_index('idx_merge_audit_performed_at', 'merge_audit_log', ['performed_at'])
    op.create_index('idx_merge_audit_performed_by', 'merge_audit_log', ['performed_by'])
    
    # Note: Unique constraint on artists.name will be added in a later migration
    # after existing duplicates are cleaned up


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_merge_audit_performed_by', 'merge_audit_log')
    op.drop_index('idx_merge_audit_performed_at', 'merge_audit_log')
    op.drop_index('idx_merge_audit_primary', 'merge_audit_log')
    op.drop_index('idx_not_duplicate_pairs_artist2', 'not_duplicate_pairs')
    op.drop_index('idx_not_duplicate_pairs_artist1', 'not_duplicate_pairs')
    
    # Drop tables
    op.drop_table('merge_audit_log')
    op.drop_table('not_duplicate_pairs')