"""Pydantic schemas for data validation and serialization."""

from .festival import Festival, FestivalCreate, FestivalUpdate
from .artist import Artist, ArtistCreate, ArtistUpdate
from .setlist import Setlist, SetlistCreate, SetlistUpdate
from .song import Song, SongCreate, SongUpdate
from .playlist import Playlist, PlaylistCreate, PlaylistUpdate, StreamingPlatform
from .user import User, UserCreate, UserUpdate, UserSongPreference, UserSongPreferenceCreate, UserSongPreferenceUpdate

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