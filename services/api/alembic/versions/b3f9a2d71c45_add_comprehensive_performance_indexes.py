"""add_comprehensive_performance_indexes

Revision ID: b3f9a2d71c45
Revises: 84f7c82e7208
Create Date: 2026-01-20 10:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b3f9a2d71c45"
down_revision = "84f7c82e7208"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # Festival indexes - dates, location, name searches
    # =========================================================================

    # Index on festival location for location-based queries (case-insensitive)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_festivals_location_lower "
        "ON festivals (LOWER(location))"
    )

    # Index on festival name for search queries (case-insensitive)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_festivals_name_lower "
        "ON festivals (LOWER(name))"
    )

    # Index on festival created_at for default ordering
    op.create_index(
        "idx_festivals_created_at", "festivals", ["created_at"], unique=False
    )

    # =========================================================================
    # Playlist indexes - user_id, festival_id, external_id (spotify)
    # =========================================================================

    op.create_index(
        "idx_playlists_user_id", "playlists", ["user_id"], unique=False
    )

    op.create_index(
        "idx_playlists_festival_id", "playlists", ["festival_id"], unique=False
    )

    op.create_index(
        "idx_playlists_artist_id", "playlists", ["artist_id"], unique=False
    )


    # Composite index for platform + external_id lookups (Spotify playlist ID)
    op.create_index(
        "idx_playlists_platform_external_id",
        "playlists",
        ["platform", "external_id"],
        unique=False,
    )

    # Index on playlist created_at for default ordering
    op.create_index(
        "idx_playlists_created_at", "playlists", ["created_at"], unique=False
    )

    # =========================================================================
    # Setlist indexes - source (setlistfm_id proxy), artist_id + date composite
    # =========================================================================

    # Index on setlist source for setlistfm_id lookups
    op.create_index(
        "idx_setlists_source", "setlists", ["source"], unique=False
    )

    # Composite index for artist_id + date (common query pattern: recent setlists)
    op.create_index(
        "idx_setlists_artist_id_date",
        "setlists",
        ["artist_id", "date"],
        unique=False,
    )

    # Index on setlist venue for venue-based searches (case-insensitive)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_setlists_venue_lower "
        "ON setlists (LOWER(venue))"
    )

    # =========================================================================
    # User indexes - email, display_name, oauth_provider + oauth_provider_id
    # =========================================================================

    # Index on user email for login lookups (case-insensitive)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_email_lower "
        "ON users (LOWER(email))"
    )

    # Index on user display_name for username lookups (case-insensitive)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_display_name_lower "
        "ON users (LOWER(display_name))"
    )

    # Composite index for OAuth provider lookups (spotify_id via provider)
    op.create_index(
        "idx_users_oauth_provider_id",
        "users",
        ["oauth_provider", "oauth_provider_id"],
        unique=False,
    )

    # Index on user last_login for recently active queries
    op.create_index(
        "idx_users_last_login", "users", ["last_login"], unique=False
    )

    # =========================================================================
    # Junction table indexes - festival_artists reverse lookups
    # =========================================================================

    # Individual index on festival_artists.artist_id for reverse lookups
    # (artist -> festivals). The primary key already covers festival_id lookups.
    op.create_index(
        "idx_festival_artists_artist_id",
        "festival_artists",
        ["artist_id"],
        unique=False,
    )

    # Individual index on festival_artists.festival_id for explicit lookups
    op.create_index(
        "idx_festival_artists_festival_id",
        "festival_artists",
        ["festival_id"],
        unique=False,
    )


def downgrade() -> None:
    # Junction table indexes
    op.drop_index("idx_festival_artists_festival_id", table_name="festival_artists")
    op.drop_index("idx_festival_artists_artist_id", table_name="festival_artists")

    # User indexes
    op.drop_index("idx_users_last_login", table_name="users")
    op.drop_index("idx_users_oauth_provider_id", table_name="users")
    op.execute("DROP INDEX IF EXISTS idx_users_display_name_lower")
    op.execute("DROP INDEX IF EXISTS idx_users_email_lower")

    # Setlist indexes
    op.execute("DROP INDEX IF EXISTS idx_setlists_venue_lower")
    op.drop_index("idx_setlists_artist_id_date", table_name="setlists")
    op.drop_index("idx_setlists_source", table_name="setlists")

    # Playlist indexes
    op.drop_index("idx_playlists_created_at", table_name="playlists")
    op.drop_index("idx_playlists_platform_external_id", table_name="playlists")
    op.drop_index("idx_playlists_artist_id", table_name="playlists")
    op.drop_index("idx_playlists_festival_id", table_name="playlists")
    op.drop_index("idx_playlists_user_id", table_name="playlists")

    # Festival indexes
    op.drop_index("idx_festivals_created_at", table_name="festivals")
    op.execute("DROP INDEX IF EXISTS idx_festivals_name_lower")
    op.execute("DROP INDEX IF EXISTS idx_festivals_location_lower")
