"""Pydantic schemas for data validation and serialization."""

from .artist import Artist, ArtistCreate, ArtistUpdate
from .festival import Festival, FestivalCreate, FestivalUpdate
from .playlist import Playlist, PlaylistCreate, PlaylistUpdate, StreamingPlatform
from .setlist import Setlist, SetlistCreate, SetlistUpdate
from .song import Song, SongCreate, SongUpdate
from .user import (
    User,
    UserCreate,
    UserSongPreference,
    UserSongPreferenceCreate,
    UserSongPreferenceUpdate,
    UserUpdate,
)

__all__ = [
    # Festival schemas
    "Festival",
    "FestivalCreate",
    "FestivalUpdate",
    # Artist schemas
    "Artist",
    "ArtistCreate",
    "ArtistUpdate",
    # Setlist schemas
    "Setlist",
    "SetlistCreate",
    "SetlistUpdate",
    # Song schemas
    "Song",
    "SongCreate",
    "SongUpdate",
    # Playlist schemas
    "Playlist",
    "PlaylistCreate",
    "PlaylistUpdate",
    "StreamingPlatform",
    # User schemas
    "User",
    "UserCreate",
    "UserUpdate",
    "UserSongPreference",
    "UserSongPreferenceCreate",
    "UserSongPreferenceUpdate",
]
