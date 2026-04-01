"""Centralized cache configuration with TTL values and key prefixes.

Provides a single source of truth for all cache TTL values and key prefix
patterns used across the application. Tuning cache behavior is as simple
as adjusting the constants in CacheTTL.

Requirements: US-7.4
"""


class CacheTTL:
    """Cache TTL values in seconds, organized by data domain.

    Artist data is relatively static, so it uses longer TTLs.
    Festival data is semi-static with moderate TTLs.
    Playlist data is user-specific and uses shorter TTLs.
    Setlist data rarely changes once created, so it uses the longest TTL.
    """

    # Artist TTLs
    ARTIST_BY_ID: int = 3600  # 1 hour
    ARTIST_BY_NAME: int = 3600  # 1 hour
    ARTIST_BY_SPOTIFY_ID: int = 3600  # 1 hour
    ARTIST_SEARCH: int = 300  # 5 minutes
    ARTIST_COUNT: int = 300  # 5 minutes

    # Festival TTLs
    FESTIVAL_BY_ID: int = 1800  # 30 minutes
    FESTIVAL_BY_NAME: int = 1800  # 30 minutes
    FESTIVAL_UPCOMING: int = 300  # 5 minutes
    FESTIVAL_SEARCH: int = 300  # 5 minutes
    FESTIVAL_COUNT: int = 300  # 5 minutes

    # Playlist TTLs
    PLAYLIST_BY_ID: int = 900  # 15 minutes
    PLAYLIST_BY_SPOTIFY_ID: int = 900  # 15 minutes
    PLAYLIST_USER: int = 300  # 5 minutes
    PLAYLIST_FESTIVAL: int = 300  # 5 minutes

    # Setlist TTLs
    SETLIST_DATA: int = 86400  # 24 hours

    # Default
    DEFAULT: int = 3600  # 1 hour


class CachePrefix:
    """Cache key prefix constants for organized namespacing.

    Using consistent prefixes enables efficient pattern-based invalidation
    via ``delete_pattern``.
    """

    ARTIST: str = "artist:"
    ARTISTS: str = "artists:"
    FESTIVAL: str = "festival:"
    FESTIVALS: str = "festivals:"
    PLAYLIST: str = "playlist:"
    PLAYLISTS: str = "playlists:"
    SETLIST: str = "setlist:"
    SETLISTS: str = "setlists:"
    STATS: str = "cache:stats:"
