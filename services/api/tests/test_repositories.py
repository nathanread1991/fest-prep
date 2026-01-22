"""Unit tests for all repository classes."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from festival_playlist_generator.models.artist import Artist
from festival_playlist_generator.models.festival import Festival
from festival_playlist_generator.models.playlist import Playlist, StreamingPlatform
from festival_playlist_generator.models.setlist import Setlist
from festival_playlist_generator.models.user import User


class TestBaseRepository:
    """Test BaseRepository generic CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, artist_repository, sample_artist):
        """Test getting an entity by ID when it exists."""
        result = await artist_repository.get_by_id(sample_artist.id)
        assert result is not None
        assert result.id == sample_artist.id
        assert result.name == sample_artist.name

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, artist_repository):
        """Test getting an entity by ID when it doesn't exist."""
        result = await artist_repository.get_by_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_empty(self, festival_repository):
        """Test getting all entities when none exist."""
        result = await festival_repository.get_all()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_with_data(self, festival_repository, async_session):
        """Test getting all entities with pagination."""
        # Create multiple festivals
        festivals = []
        for i in range(5):
            festival = Festival(
                name=f"Festival {i}",
                dates=[datetime.utcnow() + timedelta(days=i)],
                location=f"City {i}",
            )
            async_session.add(festival)
            festivals.append(festival)
        await async_session.flush()

        # Get all with default pagination
        result = await festival_repository.get_all(limit=3)
        assert len(result) == 3

        # Get with skip
        result = await festival_repository.get_all(skip=2, limit=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_create(self, artist_repository, async_session):
        """Test creating a new entity."""
        artist = Artist(name="New Artist", spotify_id="new_spotify_id", genres=["jazz"])

        result = await artist_repository.create(artist)
        await async_session.flush()

        assert result.id is not None
        assert result.name == "New Artist"
        assert result.created_at is not None

    @pytest.mark.asyncio
    async def test_update(self, artist_repository, sample_artist, async_session):
        """Test updating an existing entity."""
        sample_artist.name = "Updated Artist"
        sample_artist.popularity_score = 90.0

        result = await artist_repository.update(sample_artist)
        await async_session.flush()

        assert result.name == "Updated Artist"
        assert result.popularity_score == 90.0

    @pytest.mark.asyncio
    async def test_delete_existing(
        self, artist_repository, sample_artist, async_session
    ):
        """Test deleting an existing entity."""
        artist_id = sample_artist.id

        result = await artist_repository.delete(artist_id)
        await async_session.flush()

        assert result is True

        # Verify deletion
        deleted = await artist_repository.get_by_id(artist_id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_delete_non_existing(self, artist_repository):
        """Test deleting a non-existing entity."""
        result = await artist_repository.delete(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_bulk_delete(self, artist_repository, async_session):
        """Test bulk deleting multiple entities."""
        # Create multiple artists
        artist_ids = []
        for i in range(3):
            artist = Artist(name=f"Artist {i}")
            async_session.add(artist)
            await async_session.flush()
            artist_ids.append(artist.id)

        # Bulk delete
        count = await artist_repository.bulk_delete(artist_ids)
        await async_session.flush()

        assert count == 3

        # Verify all deleted
        for artist_id in artist_ids:
            result = await artist_repository.get_by_id(artist_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_exists_true(self, artist_repository, sample_artist):
        """Test exists returns True for existing entity."""
        result = await artist_repository.exists_by_name(sample_artist.name)
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, artist_repository):
        """Test exists returns False for non-existing entity."""
        result = await artist_repository.exists_by_name("Non-existing Artist")
        assert result is False

    @pytest.mark.asyncio
    async def test_count(self, artist_repository, async_session):
        """Test counting total entities."""
        # Create multiple artists
        for i in range(5):
            artist = Artist(name=f"Artist {i}")
            async_session.add(artist)
        await async_session.flush()

        count = await artist_repository.count_total()
        assert count >= 5

    @pytest.mark.asyncio
    async def test_get_all_with_ordering(self, festival_repository, async_session):
        """Test getting all entities with custom ordering."""
        # Create festivals with different names
        for i in range(3):
            festival = Festival(
                name=f"Festival {chr(65 + i)}",  # A, B, C
                dates=[datetime.utcnow() + timedelta(days=i)],
                location=f"City {i}",
            )
            async_session.add(festival)
        await async_session.flush()

        # Test ascending order by name
        results = await festival_repository.get_all(order_by="name", order_desc=False)
        assert len(results) >= 3

    @pytest.mark.asyncio
    async def test_get_all_ids(self, artist_repository, async_session):
        """Test getting all entity IDs."""
        # Create artists
        created_ids = []
        for i in range(3):
            artist = Artist(
                name=f"ID Test Artist {i}", spotify_id=f"id_test_{i}", genres=["pop"]
            )
            async_session.add(artist)
            await async_session.flush()
            created_ids.append(artist.id)

        all_ids = await artist_repository.get_all_ids()
        assert len(all_ids) >= 3
        # Check that our created IDs are in the result
        for created_id in created_ids:
            assert created_id in all_ids


class TestArtistRepository:
    """Test ArtistRepository specific methods."""

    @pytest.mark.asyncio
    async def test_get_by_name(self, artist_repository, sample_artist):
        """Test getting artist by exact name."""
        result = await artist_repository.get_by_name(sample_artist.name)
        assert result is not None
        assert result.id == sample_artist.id

    @pytest.mark.asyncio
    async def test_get_by_spotify_id(self, artist_repository, sample_artist):
        """Test getting artist by Spotify ID."""
        result = await artist_repository.get_by_spotify_id(sample_artist.spotify_id)
        assert result is not None
        assert result.id == sample_artist.id

    @pytest.mark.asyncio
    async def test_search_paginated_by_name(self, artist_repository, async_session):
        """Test searching artists by name."""
        # Create artists with different names
        for name in ["Rock Band", "Jazz Ensemble", "Rock Star"]:
            artist = Artist(name=name)
            async_session.add(artist)
        await async_session.flush()

        # Search for "rock"
        results, total = await artist_repository.search_paginated(search="rock")
        assert total == 2
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_paginated_by_genre(self, artist_repository, async_session):
        """Test searching artists by genre."""
        # Create artists with different genres
        artist1 = Artist(name="Artist 1", genres=["rock", "indie"])
        artist2 = Artist(name="Artist 2", genres=["jazz", "blues"])
        async_session.add_all([artist1, artist2])
        await async_session.flush()

        # Search for "rock"
        results, total = await artist_repository.search_paginated(search="rock")
        assert total == 1
        assert results[0].name == "Artist 1"

    @pytest.mark.asyncio
    async def test_search_paginated_pagination(self, artist_repository, async_session):
        """Test pagination in search."""
        # Create 10 artists
        for i in range(10):
            artist = Artist(name=f"Artist {i}")
            async_session.add(artist)
        await async_session.flush()

        # Get first page
        results, total = await artist_repository.search_paginated(page=1, per_page=3)
        assert total == 10
        assert len(results) == 3

        # Get second page
        results, total = await artist_repository.search_paginated(page=2, per_page=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_exists_by_spotify_id(self, artist_repository, sample_artist):
        """Test checking if artist exists by Spotify ID."""
        result = await artist_repository.exists_by_spotify_id(sample_artist.spotify_id)
        assert result is True

        result = await artist_repository.exists_by_spotify_id("non_existing_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_all_ids(self, artist_repository, async_session):
        """Test getting all artist IDs."""
        # Create multiple artists
        artist_ids = []
        for i in range(3):
            artist = Artist(name=f"Artist {i}")
            async_session.add(artist)
            await async_session.flush()
            artist_ids.append(artist.id)
        await async_session.flush()

        result = await artist_repository.get_all_ids()
        assert len(result) == 3
        assert all(aid in result for aid in artist_ids)

    @pytest.mark.asyncio
    async def test_count_orphaned(self, artist_repository, async_session):
        """Test counting orphaned artists."""
        # Create orphaned artist (no spotify_id, no setlists)
        orphaned = Artist(name="Orphaned Artist", spotify_id=None)
        async_session.add(orphaned)

        # Create non-orphaned artist (has spotify_id)
        non_orphaned = Artist(name="Non-Orphaned Artist", spotify_id="spotify_123")
        async_session.add(non_orphaned)

        await async_session.flush()

        count = await artist_repository.count_orphaned()
        assert count >= 1


class TestFestivalRepository:
    """Test FestivalRepository specific methods."""

    @pytest.mark.asyncio
    async def test_get_by_name(self, festival_repository, sample_festival):
        """Test getting festival by name."""
        result = await festival_repository.get_by_name(sample_festival.name)
        assert result is not None
        assert result.id == sample_festival.id

    @pytest.mark.asyncio
    async def test_get_upcoming_festivals(self, festival_repository, async_session):
        """Test getting upcoming festivals."""
        # Create past festival
        past_festival = Festival(
            name="Past Festival",
            dates=[datetime.utcnow() - timedelta(days=30)],
            location="Past City",
        )
        async_session.add(past_festival)

        # Create future festivals
        for i in range(3):
            festival = Festival(
                name=f"Future Festival {i}",
                dates=[datetime.utcnow() + timedelta(days=i + 1)],
                location=f"Future City {i}",
            )
            async_session.add(festival)
        await async_session.flush()

        # Get upcoming festivals
        results = await festival_repository.get_upcoming_festivals(limit=10)
        assert len(results) >= 3
        # All should be in the future
        for festival in results:
            assert festival.start_date >= datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

    @pytest.mark.asyncio
    async def test_search_festivals(self, festival_repository, async_session):
        """Test searching festivals."""
        # Create festivals with different names
        for name in ["Rock Festival", "Jazz Fest", "Rock Concert"]:
            festival = Festival(
                name=name, dates=[datetime.utcnow()], location="Test City"
            )
            async_session.add(festival)
        await async_session.flush()

        # Search for "rock"
        results = await festival_repository.search_festivals("rock")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_by_location(self, festival_repository, async_session):
        """Test getting festivals by location."""
        # Create festivals in different locations
        for i in range(3):
            festival = Festival(
                name=f"Festival {i}",
                dates=[datetime.utcnow()],
                location="London" if i < 2 else "Manchester",
            )
            async_session.add(festival)
        await async_session.flush()

        results = await festival_repository.get_by_location("London")
        assert len(results) == 2


class TestPlaylistRepository:
    """Test PlaylistRepository specific methods."""

    @pytest.mark.asyncio
    async def test_get_by_user(self, playlist_repository, sample_user, async_session):
        """Test getting playlists by user."""
        # Create multiple playlists for user
        for i in range(3):
            playlist = Playlist(name=f"Playlist {i}", user_id=sample_user.id)
            async_session.add(playlist)
        await async_session.flush()

        results = await playlist_repository.get_by_user(sample_user.id)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_by_festival(
        self, playlist_repository, sample_festival, sample_user, async_session
    ):
        """Test getting playlists by festival."""
        # Create playlists for festival
        for i in range(2):
            playlist = Playlist(
                name=f"Playlist {i}",
                user_id=sample_user.id,
                festival_id=sample_festival.id,
            )
            async_session.add(playlist)
        await async_session.flush()

        results = await playlist_repository.get_by_festival(sample_festival.id)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_by_artist(
        self, playlist_repository, sample_artist, sample_user, async_session
    ):
        """Test getting playlists by artist."""
        # Create playlists for artist
        for i in range(2):
            playlist = Playlist(
                name=f"Playlist {i}", user_id=sample_user.id, artist_id=sample_artist.id
            )
            async_session.add(playlist)
        await async_session.flush()

        results = await playlist_repository.get_by_artist(sample_artist.id)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_by_spotify_id(self, playlist_repository, sample_playlist):
        """Test getting playlist by Spotify ID."""
        result = await playlist_repository.get_by_spotify_id(
            sample_playlist.external_id
        )
        assert result is not None
        assert result.id == sample_playlist.id

    @pytest.mark.asyncio
    async def test_get_by_external_id(self, playlist_repository, sample_playlist):
        """Test getting playlist by platform and external ID."""
        result = await playlist_repository.get_by_external_id(
            StreamingPlatform.SPOTIFY, sample_playlist.external_id
        )
        assert result is not None
        assert result.id == sample_playlist.id

    @pytest.mark.asyncio
    async def test_get_user_festival_playlist(
        self, playlist_repository, sample_user, sample_festival, async_session
    ):
        """Test getting user's playlist for specific festival."""
        # Create playlist for user and festival
        playlist = Playlist(
            name="User Festival Playlist",
            user_id=sample_user.id,
            festival_id=sample_festival.id,
        )
        async_session.add(playlist)
        await async_session.flush()

        result = await playlist_repository.get_user_festival_playlist(
            sample_user.id, sample_festival.id
        )
        assert result is not None
        assert result.user_id == sample_user.id
        assert result.festival_id == sample_festival.id

    @pytest.mark.asyncio
    async def test_count_by_user(self, playlist_repository, sample_user, async_session):
        """Test counting playlists by user."""
        # Create playlists
        for i in range(5):
            playlist = Playlist(name=f"Playlist {i}", user_id=sample_user.id)
            async_session.add(playlist)
        await async_session.flush()

        count = await playlist_repository.count_by_user(sample_user.id)
        assert count == 5

    @pytest.mark.asyncio
    async def test_count_by_platform(
        self, playlist_repository, sample_user, async_session
    ):
        """Test counting playlists by platform."""
        # Create playlists on different platforms
        for i in range(3):
            playlist = Playlist(
                name=f"Playlist {i}",
                user_id=sample_user.id,
                platform=StreamingPlatform.SPOTIFY,
            )
            async_session.add(playlist)

        playlist = Playlist(
            name="YouTube Playlist",
            user_id=sample_user.id,
            platform=StreamingPlatform.YOUTUBE,
        )
        async_session.add(playlist)
        await async_session.flush()

        spotify_count = await playlist_repository.count_by_platform(
            StreamingPlatform.SPOTIFY
        )
        assert spotify_count == 3

        youtube_count = await playlist_repository.count_by_platform(
            StreamingPlatform.YOUTUBE
        )
        assert youtube_count == 1

    @pytest.mark.asyncio
    async def test_exists_by_external_id(self, playlist_repository, sample_playlist):
        """Test checking if playlist exists by external ID."""
        result = await playlist_repository.exists_by_external_id(
            StreamingPlatform.SPOTIFY, sample_playlist.external_id
        )
        assert result is True

        result = await playlist_repository.exists_by_external_id(
            StreamingPlatform.SPOTIFY, "non_existing_id"
        )
        assert result is False


class TestSetlistRepository:
    """Test SetlistRepository specific methods."""

    @pytest.mark.asyncio
    async def test_get_by_artist(
        self, setlist_repository, sample_artist, async_session
    ):
        """Test getting setlists by artist."""
        # Create multiple setlists for artist
        for i in range(3):
            setlist = Setlist(
                artist_id=sample_artist.id,
                venue=f"Venue {i}",
                date=datetime.utcnow() - timedelta(days=i),
                songs=[f"Song {i}"],
            )
            async_session.add(setlist)
        await async_session.flush()

        results = await setlist_repository.get_by_artist(sample_artist.id)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_recent_setlists(
        self, setlist_repository, sample_artist, async_session
    ):
        """Test getting recent setlists."""
        # Create setlists with different dates
        for i in range(5):
            setlist = Setlist(
                artist_id=sample_artist.id,
                venue=f"Venue {i}",
                date=datetime.utcnow() - timedelta(days=i * 10),
                songs=[f"Song {i}"],
            )
            async_session.add(setlist)
        await async_session.flush()

        # Get recent setlists (last 30 days)
        from_date = datetime.utcnow() - timedelta(days=30)
        results = await setlist_repository.get_recent_setlists(
            sample_artist.id, from_date=from_date
        )
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_by_venue(self, setlist_repository, sample_artist, async_session):
        """Test getting setlists by venue."""
        # Create setlists at different venues
        for i in range(3):
            setlist = Setlist(
                artist_id=sample_artist.id,
                venue="Madison Square Garden" if i < 2 else "Other Venue",
                date=datetime.utcnow(),
                songs=[f"Song {i}"],
            )
            async_session.add(setlist)
        await async_session.flush()

        results = await setlist_repository.get_by_venue("Madison Square Garden")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_count_by_artist(
        self, setlist_repository, sample_artist, async_session
    ):
        """Test counting setlists by artist."""
        # Create setlists
        for i in range(4):
            setlist = Setlist(
                artist_id=sample_artist.id,
                venue=f"Venue {i}",
                date=datetime.utcnow(),
                songs=[f"Song {i}"],
            )
            async_session.add(setlist)
        await async_session.flush()

        count = await setlist_repository.count_by_artist(sample_artist.id)
        assert count == 4


class TestUserRepository:
    """Test UserRepository specific methods."""

    @pytest.mark.asyncio
    async def test_get_by_email(self, user_repository, sample_user):
        """Test getting user by email."""
        result = await user_repository.get_by_email(sample_user.email)
        assert result is not None
        assert result.id == sample_user.id

    @pytest.mark.asyncio
    async def test_get_by_oauth_provider(self, user_repository, sample_user):
        """Test getting user by OAuth provider."""
        result = await user_repository.get_by_oauth_provider(
            sample_user.oauth_provider, sample_user.oauth_provider_id
        )
        assert result is not None
        assert result.id == sample_user.id

    @pytest.mark.asyncio
    async def test_exists_by_email(self, user_repository, sample_user):
        """Test checking if user exists by email."""
        result = await user_repository.exists_by_email(sample_user.email)
        assert result is True

        result = await user_repository.exists_by_email("nonexistent@example.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_last_login(self, user_repository, sample_user, async_session):
        """Test updating user's last login timestamp."""
        original_login = sample_user.last_login

        await user_repository.update_last_login(sample_user.id)
        await async_session.flush()

        updated_user = await user_repository.get_by_id(sample_user.id)
        assert updated_user.last_login is not None
        assert updated_user.last_login != original_login

    @pytest.mark.asyncio
    async def test_get_users_with_marketing_opt_in(
        self, user_repository, async_session
    ):
        """Test getting users who opted in for marketing."""
        # Create users with different opt-in status
        for i in range(5):
            user = User(email=f"user{i}@example.com", marketing_opt_in=(i % 2 == 0))
            async_session.add(user)
        await async_session.flush()

        results = await user_repository.get_users_with_marketing_opt_in()
        # Should have at least 3 users with opt-in (0, 2, 4)
        assert len(results) >= 3
        assert all(user.marketing_opt_in for user in results)

    @pytest.mark.asyncio
    async def test_update_preferences(
        self, user_repository, sample_user, async_session
    ):
        """Test updating user preferences."""
        new_prefs = {"theme": "dark", "notifications": True}
        result = await user_repository.update_preferences(sample_user.id, new_prefs)
        await async_session.flush()

        assert result is True
        updated_user = await user_repository.get_by_id(sample_user.id)
        assert updated_user.preferences == new_prefs

    @pytest.mark.asyncio
    async def test_add_connected_platform(
        self, user_repository, sample_user, async_session
    ):
        """Test adding a connected platform."""
        result = await user_repository.add_connected_platform(sample_user.id, "youtube")
        await async_session.flush()

        assert result is True
        updated_user = await user_repository.get_by_id(sample_user.id)
        assert "youtube" in updated_user.connected_platforms

    @pytest.mark.asyncio
    async def test_remove_connected_platform(
        self, user_repository, sample_user, async_session
    ):
        """Test removing a connected platform."""
        # First add a platform
        await user_repository.add_connected_platform(sample_user.id, "youtube")
        await async_session.flush()

        # Then remove it
        result = await user_repository.remove_connected_platform(
            sample_user.id, "youtube"
        )
        await async_session.flush()

        assert result is True
        updated_user = await user_repository.get_by_id(sample_user.id)
        assert "youtube" not in (updated_user.connected_platforms or [])

    @pytest.mark.asyncio
    async def test_add_festival_to_history(
        self, user_repository, sample_user, sample_festival, async_session
    ):
        """Test adding a festival to user history."""
        result = await user_repository.add_festival_to_history(
            sample_user.id, sample_festival.id
        )
        await async_session.flush()

        assert result is True
        updated_user = await user_repository.get_by_id(sample_user.id)
        assert sample_festival.id in updated_user.festival_history

    @pytest.mark.asyncio
    async def test_get_by_spotify_id(self, user_repository, sample_user):
        """Test getting user by Spotify ID."""
        result = await user_repository.get_by_spotify_id(sample_user.oauth_provider_id)
        assert result is not None
        assert result.id == sample_user.id

    @pytest.mark.asyncio
    async def test_exists_by_oauth_provider(self, user_repository, sample_user):
        """Test checking if user exists by OAuth provider."""
        result = await user_repository.exists_by_oauth_provider(
            sample_user.oauth_provider, sample_user.oauth_provider_id
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_count_by_oauth_provider(self, user_repository, sample_user):
        """Test counting users by OAuth provider."""
        count = await user_repository.count_by_oauth_provider("spotify")
        assert count >= 1

    @pytest.mark.asyncio
    async def test_count_with_marketing_opt_in(self, user_repository, async_session):
        """Test counting users with marketing opt-in."""
        # Create a user with marketing opt-in
        user = User(
            email="marketing_count@example.com",
            display_name="Marketing Count User",
            oauth_provider="spotify",
            oauth_provider_id="marketing_count_oauth",
            marketing_opt_in=True,
        )
        async_session.add(user)
        await async_session.flush()

        count = await user_repository.count_with_marketing_opt_in()
        assert count >= 1


class TestSetlistRepositoryExtended:
    """Extended tests for SetlistRepository to improve coverage."""

    @pytest.mark.asyncio
    async def test_get_by_id_with_relationships(
        self, setlist_repository, sample_artist, async_session
    ):
        """Test getting setlist by ID with relationships loaded."""
        setlist = Setlist(
            artist_id=sample_artist.id,
            venue="Test Venue",
            date=datetime.utcnow(),
            songs=["Song 1", "Song 2"],
        )
        async_session.add(setlist)
        await async_session.flush()

        result = await setlist_repository.get_by_id(setlist.id, load_relationships=True)
        assert result is not None
        assert result.id == setlist.id

    @pytest.mark.asyncio
    async def test_get_by_tour(self, setlist_repository, sample_artist, async_session):
        """Test getting setlists by tour name."""
        for i in range(3):
            setlist = Setlist(
                artist_id=sample_artist.id,
                venue=f"Venue {i}",
                tour_name="World Tour 2024" if i < 2 else "Other Tour",
                date=datetime.utcnow(),
                songs=[f"Song {i}"],
            )
            async_session.add(setlist)
        await async_session.flush()

        results = await setlist_repository.get_by_tour("World Tour 2024")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_by_festival_name(
        self, setlist_repository, sample_artist, async_session
    ):
        """Test getting setlists by festival name."""
        for i in range(3):
            setlist = Setlist(
                artist_id=sample_artist.id,
                venue=f"Venue {i}",
                festival_name="Coachella" if i < 2 else "Lollapalooza",
                date=datetime.utcnow(),
                songs=[f"Song {i}"],
            )
            async_session.add(setlist)
        await async_session.flush()

        results = await setlist_repository.get_by_festival_name("Coachella")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_by_date_range(
        self, setlist_repository, sample_artist, async_session
    ):
        """Test getting setlists by date range."""
        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow() + timedelta(days=30)

        for i in range(3):
            setlist = Setlist(
                artist_id=sample_artist.id,
                venue=f"Venue {i}",
                date=datetime.utcnow() - timedelta(days=i * 10),
                songs=[f"Song {i}"],
            )
            async_session.add(setlist)
        await async_session.flush()

        results = await setlist_repository.get_by_date_range(
            start_date, end_date, artist_id=sample_artist.id
        )
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_count_by_venue(
        self, setlist_repository, sample_artist, async_session
    ):
        """Test counting setlists by venue."""
        for i in range(3):
            setlist = Setlist(
                artist_id=sample_artist.id,
                venue="Madison Square Garden",
                date=datetime.utcnow() - timedelta(days=i),
                songs=[f"Song {i}"],
            )
            async_session.add(setlist)
        await async_session.flush()

        count = await setlist_repository.count_by_venue("Madison Square Garden")
        assert count == 3


class TestFestivalRepositoryExtended:
    """Extended tests for FestivalRepository to improve coverage."""

    @pytest.mark.asyncio
    async def test_get_by_id_with_relationships(
        self, festival_repository, sample_festival
    ):
        """Test getting festival by ID with relationships loaded."""
        result = await festival_repository.get_by_id(
            sample_festival.id, load_relationships=True
        )
        assert result is not None
        assert result.id == sample_festival.id

    @pytest.mark.asyncio
    async def test_count_by_location(self, festival_repository, async_session):
        """Test counting festivals by location."""
        for i in range(3):
            festival = Festival(
                name=f"Festival {i}",
                dates=[datetime.utcnow() + timedelta(days=i)],
                location="Los Angeles",
            )
            async_session.add(festival)
        await async_session.flush()

        count = await festival_repository.count_by_location("Los Angeles")
        assert count == 3

    @pytest.mark.asyncio
    async def test_exists_by_name(self, festival_repository, sample_festival):
        """Test checking if festival exists by name."""
        result = await festival_repository.exists_by_name(sample_festival.name)
        assert result is True

        result = await festival_repository.exists_by_name("Nonexistent Festival")
        assert result is False


class TestPlaylistRepositoryExtended:
    """Extended tests for PlaylistRepository to improve coverage."""

    @pytest.mark.asyncio
    async def test_get_by_id_with_relationships(
        self, playlist_repository, sample_playlist
    ):
        """Test getting playlist by ID with relationships loaded."""
        result = await playlist_repository.get_by_id(
            sample_playlist.id, load_relationships=True
        )
        assert result is not None
        assert result.id == sample_playlist.id

    @pytest.mark.asyncio
    async def test_search_paginated(self, festival_repository, async_session):
        """Test paginated festival search with filters."""
        # Create test festivals
        for i in range(5):
            festival = Festival(
                name=f"Test Festival {i}",
                dates=[datetime.utcnow() + timedelta(days=i * 10)],
                location="Los Angeles" if i < 3 else "New York",
                venue=f"Venue {i}",
            )
            async_session.add(festival)
        await async_session.flush()

        # Test search with location filter
        results, total = await festival_repository.search_paginated(
            location="Los Angeles", page=1, per_page=10
        )
        assert len(results) == 3
        assert total == 3

        # Test search with name filter
        results, total = await festival_repository.search_paginated(
            search="Test", page=1, per_page=10
        )
        assert len(results) >= 5

    @pytest.mark.asyncio
    async def test_base_count_method(self, festival_repository, async_session):
        """Test BaseRepository count method directly."""
        # Create festivals
        for i in range(3):
            festival = Festival(
                name=f"Count Test {i}", dates=[datetime.utcnow()], location="Test City"
            )
            async_session.add(festival)
        await async_session.flush()

        # FestivalRepository doesn't override count(), so this tests
        # BaseRepository.count()
        count = await festival_repository.count()
        assert count >= 3

    @pytest.mark.asyncio
    async def test_base_get_all_ids_method(self, festival_repository, async_session):
        """Test BaseRepository get_all_ids method directly."""
        # Create festivals
        created_ids = []
        for i in range(3):
            festival = Festival(
                name=f"IDs Test {i}", dates=[datetime.utcnow()], location="Test City"
            )
            async_session.add(festival)
            await async_session.flush()
            created_ids.append(festival.id)

        # FestivalRepository doesn't override get_all_ids(), so this tests
        # BaseRepository.get_all_ids()
        all_ids = await festival_repository.get_all_ids()
        assert len(all_ids) >= 3
        for created_id in created_ids:
            assert created_id in all_ids
