"""Web interface routes for the Festival Playlist Generator."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.models.festival import Festival
from festival_playlist_generator.models.playlist import Playlist
from festival_playlist_generator.web.utils import get_asset_url, get_css_url, get_js_url

logger = logging.getLogger(__name__)

# Create router
web_router = APIRouter()

# Set up templates
templates = Jinja2Templates(directory="festival_playlist_generator/web/templates")

# Add asset management functions to template globals
templates.env.globals.update(
    {"asset_url": get_asset_url, "css_url": get_css_url, "js_url": get_js_url}
)


def add_no_cache_headers(response: Any) -> Any:
    """Add no-cache headers to prevent stale data."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@web_router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> Response:
    """Home page with festival search and features."""
    # Check for welcome parameter for new users
    welcome = request.query_params.get("welcome") == "true"

    response = templates.TemplateResponse(
        request, "index.html", {"request": request, "welcome_new_user": welcome}
    )

    # Add no-cache headers if refresh parameter is present
    if request.query_params.get("_refresh"):
        response = add_no_cache_headers(response)

    return response


@web_router.get("/debug-auth", response_class=HTMLResponse)
async def debug_auth(request: Request) -> Response:
    """Debug page for authentication issues."""
    return templates.TemplateResponse(request, "debug_auth.html", {"request": request})


@web_router.get("/artists", response_class=HTMLResponse)
async def artists_page(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    """Artists listing page."""
    from sqlalchemy import func, select

    from festival_playlist_generator.models.artist import Artist as ArtistModel
    from festival_playlist_generator.models.setlist import Setlist as SetlistModel
    from festival_playlist_generator.services.image_url_helper import (
        convert_to_proxy_url,
    )

    # Get all artists with setlist counts
    query = (
        select(ArtistModel, func.count(SetlistModel.id).label("setlist_count"))
        .outerjoin(SetlistModel)
        .group_by(ArtistModel.id)
        .order_by(ArtistModel.name)
    )

    result = await db.execute(query)
    artists_with_counts = result.all()

    # Convert artist images to use proxy cache
    # We'll add cached URLs as temporary attributes to the artist objects
    for artist, setlist_count in artists_with_counts:
        artist._cached_spotify_image = convert_to_proxy_url(artist.spotify_image_url)
        artist._cached_logo = convert_to_proxy_url(artist.logo_url)

    response = templates.TemplateResponse(
        request, "artists.html", {"request": request, "artists": artists_with_counts}
    )

    # Add no-cache headers if refresh parameter is present
    if request.query_params.get("_refresh"):
        response = add_no_cache_headers(response)

    return response


@web_router.get("/festivals", response_class=HTMLResponse)
async def festivals_page(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    """Festivals listing page."""
    from sqlalchemy import select

    from festival_playlist_generator.models.festival import Festival as FestivalModel
    from festival_playlist_generator.services.image_url_helper import (
        convert_to_proxy_url,
    )

    # Get all festivals
    result = await db.execute(select(FestivalModel).order_by(FestivalModel.name))
    festivals = result.scalars().all()

    # Convert festival logo URLs to use proxy cache
    # Create a list of festivals with cached logo URLs
    festivals_with_cached_logos = []
    for festival in festivals:
        # Create a dict-like object with cached logo
        festival_data = {
            "festival": festival,
            "cached_logo": convert_to_proxy_url(festival.logo_url),
        }
        festivals_with_cached_logos.append(festival_data)

    response = templates.TemplateResponse(
        request,
        "festivals.html",
        {"request": request, "festivals": festivals_with_cached_logos},
    )

    # Add no-cache headers if refresh parameter is present
    if request.query_params.get("_refresh"):
        response = add_no_cache_headers(response)

    return response


@web_router.get("/festivals/{festival_id}", response_class=HTMLResponse)
async def festival_detail(
    request: Request, festival_id: str, db: AsyncSession = Depends(get_db)
) -> Response:
    """Individual festival detail page with branding and tiered artist grouping."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from festival_playlist_generator.core.caching import HTTPCacheManager, cache_manager
    from festival_playlist_generator.services.image_url_helper import (
        convert_to_proxy_url,
    )

    # Check if we should bypass cache (for refresh or admin updates)
    bypass_cache = request.query_params.get("_refresh") or request.query_params.get(
        "_nocache"
    )

    # Try to get cached response
    cache_key = f"poster:{festival_id}"
    if not bypass_cache:
        cached_html = await cache_manager.get(cache_key, namespace="posters")
        if cached_html:
            logger.debug(f"Cache hit for festival poster: {festival_id}")
            # Return cached HTML with appropriate headers
            from fastapi.responses import HTMLResponse

            response = HTMLResponse(content=cached_html)

            # Add cache headers
            cache_headers = HTTPCacheManager.get_cache_headers(
                max_age=3600, public=True, must_revalidate=True  # 1 hour
            )
            for header, value in cache_headers.items():
                response.headers[header] = value

            return response

    # Get festival from database with artists eagerly loaded
    result = await db.execute(
        select(Festival)
        .options(selectinload(Festival.artists))
        .filter(Festival.id == festival_id)
    )
    festival = result.scalar_one_or_none()

    if not festival:
        raise HTTPException(status_code=404, detail="Festival not found")

    # Sort artists by Spotify followers (descending) for poster-style display
    # Artists with no Spotify data go to the end
    sorted_artists = sorted(
        festival.artists, key=lambda a: (a.spotify_followers or 0), reverse=True
    )

    # Group artists by tier based on follower counts
    # Tier thresholds (can be adjusted based on festival size)
    headliners = []
    sub_headliners = []
    mid_tier = []
    lower_tier = []
    small_tier = []

    for artist in sorted_artists:
        followers = artist.spotify_followers or 0

        # Create artist dict with cached image URLs
        artist_dict = {
            "id": artist.id,
            "name": artist.name,
            "spotify_image_url": convert_to_proxy_url(artist.spotify_image_url),
            "logo_url": convert_to_proxy_url(artist.logo_url),
            "spotify_followers": artist.spotify_followers,
            "spotify_popularity": artist.spotify_popularity,
            "genres": artist.genres,
        }

        if followers >= 1_000_000:  # 1M+ followers
            headliners.append(artist_dict)
        elif followers >= 500_000:  # 500K-1M followers
            sub_headliners.append(artist_dict)
        elif followers >= 100_000:  # 100K-500K followers
            mid_tier.append(artist_dict)
        elif followers >= 10_000:  # 10K-100K followers
            lower_tier.append(artist_dict)
        else:  # <10K followers
            small_tier.append(artist_dict)

    # Prepare color scheme for template
    color_scheme = {
        "primary": festival.primary_color or "#667eea",
        "secondary": festival.secondary_color or "#764ba2",
        "accent": festival.accent_colors[0] if festival.accent_colors else "#ffffff",
    }

    # Convert festival logo URL to use proxy cache
    festival_logo = convert_to_proxy_url(festival.logo_url)

    # Render template
    response = templates.TemplateResponse(
        request,
        "festival_detail.html",
        {
            "request": request,
            "festival": festival,
            "festival_logo": festival_logo,
            "sorted_artists": sorted_artists,
            "headliners": headliners,
            "sub_headliners": sub_headliners,
            "mid_tier": mid_tier,
            "lower_tier": lower_tier,
            "small_tier": small_tier,
            "color_scheme": color_scheme,
        },
    )

    # Cache the rendered HTML
    # Extract the body content from the response
    try:
        # Get the response body
        response_body = (
            response.body.decode("utf-8")
            if isinstance(response.body, bytes)
            else str(response.body)
        )

        # Cache for 1 hour
        await cache_manager.set(cache_key, response_body, ttl=3600, namespace="posters")
        logger.debug(f"Cached festival poster: {festival_id}")
    except Exception as e:
        logger.error(f"Error caching poster for festival {festival_id}: {e}")

    # Add cache headers
    cache_headers = HTTPCacheManager.get_cache_headers(
        max_age=3600, public=True, must_revalidate=True  # 1 hour
    )
    for header, value in cache_headers.items():
        response.headers[header] = value

    return response


@web_router.get("/playlists", response_class=HTMLResponse)
async def playlists_page(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    """User playlists page (requires authentication)."""
    # Check authentication
    from festival_playlist_generator.services.oauth_service import oauth_service

    session_id = request.cookies.get("session_id")
    if not session_id:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = await oauth_service.get_current_user(db, session_id)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    # Get user's playlists
    from sqlalchemy import select

    from festival_playlist_generator.models.playlist import Playlist as PlaylistModel

    result = await db.execute(
        select(PlaylistModel)
        .where(PlaylistModel.user_id == user.id)
        .order_by(PlaylistModel.created_at.desc())
    )
    playlists = result.scalars().all()

    response = templates.TemplateResponse(
        request,
        "playlists.html",
        {"request": request, "playlists": playlists, "user": user},
    )

    # Add no-cache headers if refresh parameter is present
    if request.query_params.get("_refresh"):
        response = add_no_cache_headers(response)

    return response


@web_router.get("/playlists/{playlist_id}", response_class=HTMLResponse)
async def playlist_detail(
    request: Request, playlist_id: str, db: AsyncSession = Depends(get_db)
) -> Response:
    """Individual playlist detail page."""
    # Get playlist from database
    from sqlalchemy import select

    result = await db.execute(select(Playlist).filter(Playlist.id == playlist_id))
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    return templates.TemplateResponse(
        request, "playlist.html", {"request": request, "playlist": playlist}
    )


@web_router.get("/artists/{artist_id}", response_class=HTMLResponse)
async def artist_detail(
    request: Request, artist_id: str, db: AsyncSession = Depends(get_db)
) -> Response:
    """Individual artist detail page with setlists and song frequency analysis."""
    from collections import Counter
    from uuid import UUID

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from festival_playlist_generator.models.artist import Artist as ArtistModel
    from festival_playlist_generator.models.setlist import Setlist as SetlistModel
    from festival_playlist_generator.services.image_url_helper import (
        convert_to_proxy_url,
        convert_track_images,
    )
    from festival_playlist_generator.services.spotify_artist_service import (
        spotify_artist_service,
    )

    try:
        # Get artist with setlists and festivals
        result = await db.execute(
            select(ArtistModel)
            .options(
                selectinload(ArtistModel.setlists), selectinload(ArtistModel.festivals)
            )
            .filter(ArtistModel.id == UUID(artist_id))
        )
        artist = result.scalar_one_or_none()

        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found")

        # Force load relationships to avoid lazy loading issues later
        _ = list(artist.festivals)
        _ = list(artist.setlists)

        # Fetch Spotify information if not already cached
        spotify_info = None
        if not artist.spotify_id or not artist.spotify_image_url:
            spotify_info = spotify_artist_service.search_artist(artist.name)
            if spotify_info:
                try:
                    # Update artist with Spotify information
                    artist.spotify_id = spotify_info.id
                    artist.spotify_image_url = spotify_info.medium_image_url
                    artist.spotify_popularity = spotify_info.popularity
                    artist.spotify_followers = spotify_info.followers
                    if spotify_info.genres and not artist.genres:
                        artist.genres = spotify_info.genres

                    await db.commit()
                    # Refresh the artist to reload relationships after commit
                    await db.refresh(artist, ["festivals", "setlists"])
                except Exception as e:
                    # Handle duplicate Spotify ID or other database errors
                    await db.rollback()
                    logger.warning(f"Could not update Spotify info: {e}")
                    # Re-query the artist to get a fresh object after rollback
                    result = await db.execute(
                        select(ArtistModel)
                        .options(
                            selectinload(ArtistModel.setlists),
                            selectinload(ArtistModel.festivals),
                        )
                        .filter(ArtistModel.id == UUID(artist_id))
                    )
                    artist = result.scalar_one_or_none()
                    if not artist:
                        raise HTTPException(status_code=404, detail="Artist not found")
                    # Continue without Spotify info update

        # Get recent setlists (last 10)
        recent_setlists_query = (
            select(SetlistModel)
            .filter(SetlistModel.artist_id == UUID(artist_id))
            .order_by(SetlistModel.date.desc())
            .limit(10)
        )

        result = await db.execute(recent_setlists_query)
        recent_setlists = result.scalars().all()

        # If no setlists, try to fetch from external API
        if not recent_setlists:
            try:
                from festival_playlist_generator.core.config import settings
                from festival_playlist_generator.services.artist_analyzer import (
                    ArtistAnalyzerService,
                )

                if settings.SETLIST_FM_API_KEY:
                    analyzer = ArtistAnalyzerService(settings.SETLIST_FM_API_KEY)
                    await analyzer.get_artist_setlists(artist.name, limit=10)

                    # Refresh the query to get newly stored setlists
                    result = await db.execute(recent_setlists_query)
                    recent_setlists = result.scalars().all()
            except Exception as e:
                logger.error(f"Error fetching external setlists for {artist.name}: {e}")

        # Analyze song frequency across all setlists
        all_songs = []
        for setlist in recent_setlists:
            if setlist.songs:  # type: ignore[attr-defined]
                all_songs.extend(setlist.songs)  # type: ignore[attr-defined]

        # Count song occurrences and get top songs
        song_counter = Counter(all_songs)
        top_songs = song_counter.most_common(20)  # Top 20 most played songs

        # If no setlist data, fetch top tracks from Spotify
        spotify_top_tracks = None
        if not top_songs and artist.spotify_id:
            try:
                raw_tracks = spotify_artist_service.get_artist_top_tracks(
                    artist.spotify_id
                )
                if raw_tracks:
                    # Format tracks for template
                    spotify_top_tracks = []
                    for track in raw_tracks[:10]:  # Limit to top 10
                        spotify_top_tracks.append(
                            {
                                "name": track.get("name"),
                                "album_name": track.get("album", {}).get("name"),
                                "album_image": (
                                    track.get("album", {})
                                    .get("images", [{}])[0]
                                    .get("url")
                                    if track.get("album", {}).get("images")
                                    else None
                                ),
                                "popularity": track.get("popularity"),
                                "preview_url": track.get("preview_url"),
                                "spotify_url": track.get("external_urls", {}).get(
                                    "spotify"
                                ),
                            }
                        )

                    # Convert track album images to use proxy cache
                    spotify_top_tracks = convert_track_images(spotify_top_tracks)
            except Exception as e:
                logger.error(
                    f"Error fetching Spotify top tracks for {artist.name}: {e}"
                )

        # Convert artist images to use proxy cache
        artist_spotify_image = convert_to_proxy_url(artist.spotify_image_url)
        artist_logo = convert_to_proxy_url(artist.logo_url)

        # Convert festival logo URLs
        # Force load festivals collection before accessing to avoid lazy loading issues
        artist_festivals = list(artist.festivals)
        festivals_with_cached_images = []
        for festival in artist_festivals:
            festivals_with_cached_images.append(
                {
                    "id": festival.id,
                    "name": festival.name,
                    "location": festival.location,
                    "start_date": festival.start_date,
                    "end_date": festival.end_date,
                    "logo_url": convert_to_proxy_url(festival.logo_url),
                }
            )

        return templates.TemplateResponse(
            request,
            "artist_detail.html",
            {
                "request": request,
                "artist": artist,
                "artist_spotify_image": artist_spotify_image,
                "artist_logo": artist_logo,
                "recent_setlists": recent_setlists,
                "top_songs": top_songs,
                "spotify_top_tracks": spotify_top_tracks,
                "total_songs": len(set(all_songs)),
                "total_performances": len(recent_setlists),
                "spotify_info": spotify_info,
                "festivals": festivals_with_cached_images,
            },
        )

    except ValueError:
        raise HTTPException(status_code=404, detail="Invalid artist ID")
    except HTTPException:
        # Re-raise HTTPException (404, etc.) without converting to 500
        raise
    except Exception as e:
        import traceback

        logger.error(f"Error in artist detail: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@web_router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request, q: Optional[str] = None, type: Optional[str] = None
) -> Response:
    """Search results page."""
    return templates.TemplateResponse(
        request, "search.html", {"request": request, "query": q, "search_type": type}
    )


@web_router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request) -> Response:
    """About page."""
    return templates.TemplateResponse(request, "about.html", {"request": request})


@web_router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request) -> Response:
    """Privacy policy page."""
    return templates.TemplateResponse(request, "privacy.html", {"request": request})


@web_router.get("/streaming", response_class=HTMLResponse)
async def streaming_page(request: Request) -> Response:
    """Streaming services management page."""
    return templates.TemplateResponse(request, "streaming.html", {"request": request})


@web_router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request) -> Response:
    """Terms of service page."""
    return templates.TemplateResponse(request, "terms.html", {"request": request})


@web_router.get("/offline", response_class=HTMLResponse)
async def offline_page(request: Request) -> Response:
    """Offline page for PWA functionality."""
    return templates.TemplateResponse(request, "offline.html", {"request": request})
