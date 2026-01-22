"""Admin interface routes and authentication."""

import hashlib
import logging
import os
import secrets
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from festival_playlist_generator.core.config import settings
from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.models.festival import Festival as FestivalModel
from festival_playlist_generator.models.user import User as UserModel
from festival_playlist_generator.web.utils import get_asset_url, get_css_url, get_js_url

logger = logging.getLogger(__name__)

# Create router
admin_router = APIRouter()

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


# Admin credentials from settings (which loads from .env)
ADMIN_USERNAME = settings.ADMIN_USERNAME
ADMIN_PASSWORD = settings.ADMIN_PASSWORD

security = HTTPBasic()


def verify_admin_credentials(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """Verify admin credentials."""
    is_correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    is_correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)

    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@admin_router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Admin dashboard with overview."""
    try:
        # Get counts
        festivals_result = await db.execute(select(FestivalModel))
        festivals_count = len(festivals_result.scalars().all())

        artists_result = await db.execute(select(ArtistModel))
        artists_count = len(artists_result.scalars().all())

        users_result = await db.execute(select(UserModel))
        users_count = len(users_result.scalars().all())

        response = templates.TemplateResponse(
            "admin/dashboard.html",
            {
                "request": request,
                "admin_user": admin_user,
                "festivals_count": festivals_count,
                "artists_count": artists_count,
                "users_count": users_count,
            },
        )

        # Add no-cache headers if refresh parameter is present
        if request.query_params.get("_refresh"):
            response = add_no_cache_headers(response)

        return response

    except Exception as e:
        response = templates.TemplateResponse(
            "admin/dashboard.html",
            {
                "request": request,
                "admin_user": admin_user,
                "festivals_count": 0,
                "artists_count": 0,
                "users_count": 0,
                "error": str(e),
            },
        )

        # Add no-cache headers if refresh parameter is present
        if request.query_params.get("_refresh"):
            response = add_no_cache_headers(response)

        return response


@admin_router.get("/festivals", response_class=HTMLResponse)
async def admin_festivals(
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Admin festivals management page."""
    try:
        from sqlalchemy.orm import selectinload

        # Get all festivals with artists
        result = await db.execute(
            select(FestivalModel).options(selectinload(FestivalModel.artists))
        )
        festivals = result.scalars().all()

        response = templates.TemplateResponse(
            "admin/festivals.html",
            {"request": request, "admin_user": admin_user, "festivals": festivals},
        )

        # Add no-cache headers if refresh parameter is present
        if request.query_params.get("_refresh"):
            response = add_no_cache_headers(response)

        return response

    except Exception as e:
        response = templates.TemplateResponse(
            "admin/festivals.html",
            {
                "request": request,
                "admin_user": admin_user,
                "festivals": [],
                "error": str(e),
            },
        )

        # Add no-cache headers if refresh parameter is present
        if request.query_params.get("_refresh"):
            response = add_no_cache_headers(response)

        return response


@admin_router.get("/festivals/new", response_class=HTMLResponse)
async def admin_new_festival(
    request: Request, admin_user: str = Depends(verify_admin_credentials)
) -> Response:
    """New festival form."""
    return templates.TemplateResponse(
        "admin/festival_form.html",
        {
            "request": request,
            "admin_user": admin_user,
            "festival": None,
            "action": "Create",
        },
    )


@admin_router.get("/festivals/{festival_id}/edit", response_class=HTMLResponse)
async def admin_edit_festival(
    request: Request,
    festival_id: str,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Edit festival form."""
    try:
        from uuid import UUID

        from sqlalchemy.orm import selectinload

        festival_uuid = UUID(festival_id)

        # Get festival with artists
        result = await db.execute(
            select(FestivalModel)
            .options(selectinload(FestivalModel.artists))
            .filter(FestivalModel.id == festival_uuid)
        )
        festival = result.scalar_one_or_none()

        if not festival:
            return templates.TemplateResponse(
                "admin/festivals.html",
                {
                    "request": request,
                    "admin_user": admin_user,
                    "festivals": [],
                    "error": "Festival not found",
                },
            )

        # Format data for form
        dates_str = (
            ", ".join([d.strftime("%Y-%m-%d") for d in festival.dates])
            if festival.dates
            else ""
        )
        genres_str = ", ".join(festival.genres) if festival.genres else ""
        artists_str = (
            ", ".join([a.name for a in festival.artists]) if festival.artists else ""
        )
        accent_colors_str = (
            ", ".join(festival.accent_colors) if festival.accent_colors else ""
        )

        return templates.TemplateResponse(
            "admin/festival_form.html",
            {
                "request": request,
                "admin_user": admin_user,
                "festival": festival,
                "action": "Update",
                "form_data": {
                    "name": festival.name,
                    "location": festival.location,
                    "venue": festival.venue,
                    "dates": dates_str,
                    "genres": genres_str,
                    "artists": artists_str,
                    "ticket_url": festival.ticket_url,
                    "logo_url": festival.logo_url,
                    "primary_color": festival.primary_color,
                    "secondary_color": festival.secondary_color,
                    "accent_colors": accent_colors_str,
                },
            },
        )

    except ValueError:
        return templates.TemplateResponse(
            "admin/festivals.html",
            {
                "request": request,
                "admin_user": admin_user,
                "festivals": [],
                "error": "Invalid festival ID",
            },
        )
    except Exception as e:
        logger.error(f"Error loading festival for edit: {e}")
        return templates.TemplateResponse(
            "admin/festivals.html",
            {
                "request": request,
                "admin_user": admin_user,
                "festivals": [],
                "error": "Error loading festival",
            },
        )


@admin_router.post("/festivals/new")
async def admin_create_festival(
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
    name: str = Form(...),
    location: str = Form(...),
    venue: Optional[str] = Form(None),
    dates: str = Form(...),  # Comma-separated dates
    genres: Optional[str] = Form(None),  # Comma-separated genres
    artists: Optional[str] = Form(None),  # Comma-separated artists
    ticket_url: Optional[str] = Form(None),
    logo_url: Optional[str] = Form(None),
    primary_color: Optional[str] = Form(None),
    secondary_color: Optional[str] = Form(None),
    text_color: Optional[str] = Form(None),
    accent_colors: Optional[str] = Form(None),
) -> Response:
    """Create a new festival."""
    try:
        from datetime import datetime

        # Parse dates
        date_strings = [d.strip() for d in dates.split(",") if d.strip()]
        parsed_dates = []
        for date_str in date_strings:
            try:
                parsed_dates.append(
                    datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                )
            except:
                # Try common date formats
                try:
                    parsed_dates.append(datetime.strptime(date_str, "%Y-%m-%d"))
                except:
                    continue

        if not parsed_dates:
            raise ValueError("No valid dates provided")

        # Parse genres
        genre_list = (
            [g.strip() for g in genres.split(",") if g.strip()] if genres else []
        )

        # Parse accent colors
        accent_color_list = []
        if accent_colors:
            accent_color_list = [
                c.strip() for c in accent_colors.split(",") if c.strip()
            ]

        # Create festival
        festival = FestivalModel(
            name=name,
            location=location,
            venue=venue,
            dates=parsed_dates,
            genres=genre_list,
            ticket_url=ticket_url,
            logo_url=logo_url if logo_url else None,
            primary_color=primary_color if primary_color else None,
            secondary_color=secondary_color if secondary_color else None,
            text_color=text_color if text_color else None,
            accent_colors=accent_color_list if accent_color_list else None,
        )

        # Add artists
        new_artist_ids = []
        if artists:
            artist_names = [a.strip() for a in artists.split(",") if a.strip()]
            for artist_name in artist_names:
                # Find or create artist
                result = await db.execute(
                    select(ArtistModel).filter(ArtistModel.name == artist_name)
                )
                artist = result.scalar_one_or_none()
                if not artist:
                    artist = ArtistModel(name=artist_name)
                    db.add(artist)
                    await db.flush()  # Flush to get the artist ID
                    new_artist_ids.append(str(artist.id))
                festival.artists.append(artist)

        db.add(festival)
        await db.commit()

        # Invalidate poster cache for this festival (in case it's being recreated)
        from festival_playlist_generator.core.caching import (
            invalidate_festival_poster_cache,
        )

        await invalidate_festival_poster_cache(str(festival.id))

        # Enrich new artists with Spotify data in the background
        if new_artist_ids:
            try:
                from festival_playlist_generator.services.artist_enrichment_service import (
                    artist_enrichment_service,
                )

                logger.info(
                    f"Enriching {len(new_artist_ids)} new artists with Spotify data..."
                )
                enrichment_result = await artist_enrichment_service.enrich_artists(
                    new_artist_ids, db
                )
                logger.info(f"Artist enrichment complete: {enrichment_result}")
            except Exception as e:
                logger.error(f"Error enriching artists: {e}")
                # Don't fail the festival creation if enrichment fails

        # Enrich new artists with setlist data in the background
        if new_artist_ids:
            try:
                from festival_playlist_generator.services.setlist_enrichment_service import (
                    setlist_enrichment_service,
                )

                logger.info(
                    f"Enriching {len(new_artist_ids)} new artists with setlist data..."
                )
                setlist_enrichment_result = (
                    await setlist_enrichment_service.enrich_artists(new_artist_ids, db)
                )
                logger.info(f"Setlist enrichment complete: {setlist_enrichment_result}")
            except Exception as e:
                logger.error(f"Error enriching artists with setlist data: {e}")
                # Don't fail the festival creation if enrichment fails

        return RedirectResponse(url="/admin/festivals", status_code=303)

    except ValueError as ve:
        # Handle validation errors with user-friendly messages
        error_msg = str(ve)
        if "No valid dates provided" in error_msg:
            error_msg = "Please provide at least one valid date in YYYY-MM-DD format (e.g., 2024-07-15)."

        return templates.TemplateResponse(
            "admin/festival_form.html",
            {
                "request": request,
                "admin_user": admin_user,
                "festival": None,
                "action": "Create",
                "error": error_msg,
                "form_data": {
                    "name": name,
                    "location": location,
                    "venue": venue,
                    "dates": dates,
                    "genres": genres,
                    "artists": artists,
                    "ticket_url": ticket_url,
                    "logo_url": logo_url,
                    "primary_color": primary_color,
                    "secondary_color": secondary_color,
                    "accent_colors": accent_colors,
                },
            },
        )

    except Exception as e:
        # Handle database and other errors gracefully
        error_msg = "An error occurred while creating the festival."

        # Check for specific database constraint violations
        error_str = str(e).lower()
        if "unique constraint" in error_str or "uniqueviolationerror" in error_str:
            if "name" in error_str:
                error_msg = "A festival with this name already exists. Please use a different name or update the existing festival."
            else:
                error_msg = "This festival information conflicts with an existing festival. Please check for duplicates."

        logger.error(f"Error creating festival '{name}': {e}")

        return templates.TemplateResponse(
            "admin/festival_form.html",
            {
                "request": request,
                "admin_user": admin_user,
                "festival": None,
                "action": "Create",
                "error": error_msg,
                "form_data": {
                    "name": name,
                    "location": location,
                    "venue": venue,
                    "dates": dates,
                    "genres": genres,
                    "artists": artists,
                    "ticket_url": ticket_url,
                    "logo_url": logo_url,
                    "primary_color": primary_color,
                    "secondary_color": secondary_color,
                    "accent_colors": accent_colors,
                },
            },
        )


@admin_router.get("/artists", response_class=HTMLResponse)
async def admin_artists(
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    per_page: int = 100,
    search: Optional[str] = None,
    filter_orphaned: bool = False,
    filter_with_festivals: bool = False,
) -> Response:
    """
    Admin artists management page with server-side search, filtering, and pagination.

    Uses Repository pattern for database operations following enterprise best practices.
    """
    try:
        from festival_playlist_generator.repositories import ArtistRepository

        # Validate pagination parameters
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 1000:
            per_page = 100

        # Initialize repository
        repo = ArtistRepository(db)

        # Get paginated artists with filters
        artists, total_count = await repo.search_paginated(
            search=search,
            filter_orphaned=filter_orphaned,
            filter_with_festivals=filter_with_festivals,
            page=page,
            per_page=per_page,
            order_by="created_at",
            order_desc=True,
        )

        # Calculate pagination info
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        has_prev = page > 1
        has_next = page < total_pages

        response = templates.TemplateResponse(
            "admin/artists.html",
            {
                "request": request,
                "admin_user": admin_user,
                "artists": artists,
                "page": page,
                "per_page": per_page,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_prev": has_prev,
                "has_next": has_next,
                "search": search or "",
                "filter_orphaned": filter_orphaned,
                "filter_with_festivals": filter_with_festivals,
            },
        )

        # Add no-cache headers if refresh parameter is present
        if request.query_params.get("_refresh"):
            response = add_no_cache_headers(response)

        return response

    except Exception as e:
        logger.error(f"Error loading artists page: {e}", exc_info=True)
        response = templates.TemplateResponse(
            "admin/artists.html",
            {
                "request": request,
                "admin_user": admin_user,
                "artists": [],
                "page": 1,
                "per_page": per_page,
                "total_count": 0,
                "total_pages": 1,
                "has_prev": False,
                "has_next": False,
                "search": search or "",
                "filter_orphaned": filter_orphaned,
                "filter_with_festivals": filter_with_festivals,
                "error": str(e),
            },
        )

        # Add no-cache headers if refresh parameter is present
        if request.query_params.get("_refresh"):
            response = add_no_cache_headers(response)

        return response


@admin_router.get("/artists/new", response_class=HTMLResponse)
async def admin_new_artist(
    request: Request, admin_user: str = Depends(verify_admin_credentials)
) -> Response:
    """New artist form."""
    return templates.TemplateResponse(
        "admin/artist_form.html",
        {
            "request": request,
            "admin_user": admin_user,
            "artist": None,
            "action": "Create",
        },
    )


@admin_router.post("/api/spotify/search")
async def admin_spotify_search(
    request: Request, admin_user: str = Depends(verify_admin_credentials)
) -> Dict[str, Any]:
    """Search for artist on Spotify (admin API) - returns top 5 results."""
    try:
        body = await request.json()
        artist_name = body.get("artist_name", "").strip()

        if not artist_name:
            return {"success": False, "message": "Artist name is required"}

        from festival_playlist_generator.services.spotify_artist_service import (
            spotify_artist_service,
        )

        artists = spotify_artist_service.search_artists_multiple(artist_name, limit=5)

        if artists:
            return {
                "success": True,
                "results": [
                    {
                        "id": artist.id,
                        "name": artist.name,
                        "genres": artist.genres,
                        "popularity": artist.popularity,
                        "followers": artist.followers,
                        "image_url": artist.medium_image_url,
                        "spotify_url": artist.spotify_url,
                    }
                    for artist in artists
                ],
            }
        else:
            return {
                "success": False,
                "message": f"No Spotify results found for '{artist_name}'",
            }

    except Exception as e:
        logger.error(f"Error in Spotify search: {e}")
        return {"success": False, "message": "Internal server error"}


@admin_router.post("/artists/new")
async def admin_create_artist(
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
    name: str = Form(...),
    genres: Optional[str] = Form(None),  # Comma-separated genres
    musicbrainz_id: Optional[str] = Form(None),
    popularity_score: Optional[float] = Form(None),
    spotify_id: Optional[str] = Form(None),
    spotify_image_url: Optional[str] = Form(None),
    spotify_popularity: Optional[float] = Form(None),
    spotify_followers: Optional[float] = Form(None),
    logo_url: Optional[str] = Form(None),
) -> Response:
    """Create a new artist."""
    try:
        # Parse genres
        genre_list = (
            [g.strip() for g in genres.split(",") if g.strip()] if genres else []
        )

        # Check if artist with same name already exists
        existing_artist_query = select(ArtistModel).filter(ArtistModel.name == name)
        existing_artist_result = await db.execute(existing_artist_query)
        existing_artist = existing_artist_result.scalar_one_or_none()

        if existing_artist:
            error_msg = f"An artist named '{name}' already exists in the database."
            if existing_artist.spotify_id:
                error_msg += " You may want to update the existing artist instead of creating a duplicate."

            return templates.TemplateResponse(
                "admin/artist_form.html",
                {
                    "request": request,
                    "admin_user": admin_user,
                    "artist": None,
                    "action": "Create",
                    "error": error_msg,
                    "form_data": {
                        "name": name,
                        "genres": genres,
                        "musicbrainz_id": musicbrainz_id,
                        "popularity_score": popularity_score,
                        "spotify_id": spotify_id,
                        "spotify_image_url": spotify_image_url,
                        "spotify_popularity": spotify_popularity,
                        "spotify_followers": spotify_followers,
                        "logo_url": logo_url,
                    },
                },
            )

        # Check if Spotify ID already exists (if provided)
        if spotify_id:
            existing_spotify_query = select(ArtistModel).filter(
                ArtistModel.spotify_id == spotify_id
            )
            existing_spotify_result = await db.execute(existing_spotify_query)
            existing_spotify_artist = existing_spotify_result.scalar_one_or_none()

            if existing_spotify_artist:
                error_msg = f"An artist with this Spotify ID already exists: '{existing_spotify_artist.name}'. "
                error_msg += "Each artist can only have one unique Spotify ID. "
                error_msg += "You may want to update the existing artist or use a different artist."

                return templates.TemplateResponse(
                    "admin/artist_form.html",
                    {
                        "request": request,
                        "admin_user": admin_user,
                        "artist": None,
                        "action": "Create",
                        "error": error_msg,
                        "form_data": {
                            "name": name,
                            "genres": genres,
                            "musicbrainz_id": musicbrainz_id,
                            "popularity_score": popularity_score,
                            "spotify_id": spotify_id,
                            "spotify_image_url": spotify_image_url,
                            "spotify_popularity": spotify_popularity,
                            "spotify_followers": spotify_followers,
                            "logo_url": logo_url,
                        },
                    },
                )

        # Check if MusicBrainz ID already exists (if provided)
        if musicbrainz_id:
            existing_mb_query = select(ArtistModel).filter(
                ArtistModel.musicbrainz_id == musicbrainz_id
            )
            existing_mb_result = await db.execute(existing_mb_query)
            existing_mb_artist = existing_mb_result.scalar_one_or_none()

            if existing_mb_artist:
                error_msg = f"An artist with this MusicBrainz ID already exists: '{existing_mb_artist.name}'. "
                error_msg += "Each artist can only have one unique MusicBrainz ID."

                return templates.TemplateResponse(
                    "admin/artist_form.html",
                    {
                        "request": request,
                        "admin_user": admin_user,
                        "artist": None,
                        "action": "Create",
                        "error": error_msg,
                        "form_data": {
                            "name": name,
                            "genres": genres,
                            "musicbrainz_id": musicbrainz_id,
                            "popularity_score": popularity_score,
                            "spotify_id": spotify_id,
                            "spotify_image_url": spotify_image_url,
                            "spotify_popularity": spotify_popularity,
                            "spotify_followers": spotify_followers,
                            "logo_url": logo_url,
                        },
                    },
                )

        # Create artist
        artist = ArtistModel(
            name=name,
            genres=genre_list,
            musicbrainz_id=musicbrainz_id if musicbrainz_id else None,
            popularity_score=popularity_score,
            spotify_id=spotify_id if spotify_id else None,
            spotify_image_url=spotify_image_url if spotify_image_url else None,
            spotify_popularity=spotify_popularity,
            spotify_followers=spotify_followers,
            logo_url=logo_url if logo_url else None,
            logo_source="manual" if logo_url else None,
        )

        db.add(artist)
        await db.commit()

        # Trigger stats update for dashboard (if open in another tab)
        # This will be handled by the redirect, but we can add a note for future enhancement

        return RedirectResponse(url="/admin/artists", status_code=303)

    except Exception as e:
        # Handle any remaining database errors gracefully
        error_msg = "An error occurred while creating the artist."

        # Check for specific database constraint violations
        error_str = str(e).lower()
        if "unique constraint" in error_str or "uniqueviolationerror" in error_str:
            if "spotify_id" in error_str:
                error_msg = "This Spotify ID is already associated with another artist. Please check if the artist already exists or use a different Spotify account."
            elif "musicbrainz_id" in error_str:
                error_msg = "This MusicBrainz ID is already associated with another artist. Please check if the artist already exists or use a different MusicBrainz ID."
            elif "name" in error_str:
                error_msg = "An artist with this name already exists. Please use a different name or update the existing artist."
            else:
                error_msg = "This artist information conflicts with an existing artist. Please check for duplicates."

        logger.error(f"Error creating artist '{name}': {e}")

        return templates.TemplateResponse(
            "admin/artist_form.html",
            {
                "request": request,
                "admin_user": admin_user,
                "artist": None,
                "action": "Create",
                "error": error_msg,
                "form_data": {
                    "name": name,
                    "genres": genres,
                    "musicbrainz_id": musicbrainz_id,
                    "popularity_score": popularity_score,
                    "spotify_id": spotify_id,
                    "spotify_image_url": spotify_image_url,
                    "spotify_popularity": spotify_popularity,
                    "spotify_followers": spotify_followers,
                    "logo_url": logo_url,
                },
            },
        )


@admin_router.post("/festivals/{festival_id}/delete")
async def admin_delete_festival(
    festival_id: str,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a festival."""
    logger.info(f"Attempting to delete festival {festival_id}")
    try:
        from uuid import UUID

        from sqlalchemy import delete

        from festival_playlist_generator.core.caching import (
            invalidate_festival_poster_cache,
        )
        from festival_playlist_generator.models.festival import festival_artists

        festival_uuid = UUID(festival_id)

        # Invalidate poster cache before deleting
        await invalidate_festival_poster_cache(festival_id)
        logger.info(f"Invalidated poster cache for festival {festival_id}")

        # First, delete relationships in festival_artists table
        delete_relationships = delete(festival_artists).where(
            festival_artists.c.festival_id == festival_uuid
        )
        await db.execute(delete_relationships)
        logger.info(
            f"Deleted festival_artists relationships for festival {festival_id}"
        )

        # Then delete the festival
        delete_stmt = delete(FestivalModel).where(FestivalModel.id == festival_uuid)
        result = await db.execute(delete_stmt)
        await db.commit()

        logger.info(
            f"Successfully deleted festival {festival_id}, rows affected: {result.rowcount}"  # type: ignore[attr-defined]
        )
        return RedirectResponse(url="/admin/festivals?deleted=success", status_code=303)
    except Exception as e:
        logger.error(f"Error deleting festival {festival_id}: {e}", exc_info=True)
        await db.rollback()
        return RedirectResponse(
            url="/admin/festivals?error=delete_failed", status_code=303
        )


@admin_router.post("/festivals/{festival_id}/update")
async def admin_update_festival(
    request: Request,
    festival_id: str,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
    name: str = Form(...),
    location: str = Form(...),
    venue: Optional[str] = Form(None),
    dates: str = Form(...),
    genres: Optional[str] = Form(None),
    artists: Optional[str] = Form(None),
    ticket_url: Optional[str] = Form(None),
    logo_url: Optional[str] = Form(None),
    primary_color: Optional[str] = Form(None),
    secondary_color: Optional[str] = Form(None),
    text_color: Optional[str] = Form(None),
    accent_colors: Optional[str] = Form(None),
) -> Response:
    """Update an existing festival."""
    try:
        from datetime import datetime
        from uuid import UUID

        from sqlalchemy.orm import selectinload

        from festival_playlist_generator.core.caching import (
            invalidate_festival_poster_cache,
        )

        festival_uuid = UUID(festival_id)

        # Get festival
        result = await db.execute(
            select(FestivalModel)
            .options(selectinload(FestivalModel.artists))
            .filter(FestivalModel.id == festival_uuid)
        )
        festival = result.scalar_one_or_none()

        if not festival:
            raise ValueError("Festival not found")

        # Parse dates
        date_strings = [d.strip() for d in dates.split(",") if d.strip()]
        parsed_dates = []
        for date_str in date_strings:
            try:
                parsed_dates.append(
                    datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                )
            except:
                try:
                    parsed_dates.append(datetime.strptime(date_str, "%Y-%m-%d"))
                except:
                    continue

        if not parsed_dates:
            raise ValueError("No valid dates provided")

        # Parse genres
        genre_list = (
            [g.strip() for g in genres.split(",") if g.strip()] if genres else []
        )

        # Parse accent colors
        accent_color_list = (
            [c.strip() for c in accent_colors.split(",") if c.strip()]
            if accent_colors
            else []
        )

        # Update festival fields
        festival.name = name
        festival.location = location
        festival.venue = venue
        festival.dates = parsed_dates
        festival.genres = genre_list
        festival.ticket_url = ticket_url
        festival.logo_url = logo_url if logo_url else None
        festival.primary_color = primary_color if primary_color else None
        festival.secondary_color = secondary_color if secondary_color else None
        festival.text_color = text_color if text_color else None
        festival.accent_colors = accent_color_list if accent_color_list else None

        # Update artists
        festival.artists.clear()
        new_artist_ids = []
        if artists:
            artist_names = [a.strip() for a in artists.split(",") if a.strip()]
            for artist_name in artist_names:
                result = await db.execute(
                    select(ArtistModel).filter(ArtistModel.name == artist_name)
                )
                artist = result.scalar_one_or_none()
                if not artist:
                    artist = ArtistModel(name=artist_name)  # type: ignore[assignment]
                    db.add(artist)
                    await db.flush()
                    new_artist_ids.append(str(artist.id))  # type: ignore[union-attr]
                festival.artists.append(artist)

        await db.commit()

        # Invalidate poster cache after update
        await invalidate_festival_poster_cache(festival_id)
        logger.info(f"Invalidated poster cache for updated festival {festival_id}")

        # Enrich new artists if any were created
        if new_artist_ids:
            try:
                from festival_playlist_generator.services.artist_enrichment_service import (
                    artist_enrichment_service,
                )

                logger.info(
                    f"Enriching {len(new_artist_ids)} new artists with Spotify data..."
                )
                await artist_enrichment_service.enrich_artists(new_artist_ids, db)
            except Exception as e:
                logger.error(f"Error enriching artists: {e}")

        return RedirectResponse(url="/admin/festivals?updated=success", status_code=303)

    except ValueError as ve:
        error_msg = str(ve)
        if "No valid dates provided" in error_msg:
            error_msg = "Please provide at least one valid date in YYYY-MM-DD format."

        # Get festival data for form
        try:
            result = await db.execute(
                select(FestivalModel)
                .options(selectinload(FestivalModel.artists))
                .filter(FestivalModel.id == UUID(festival_id))
            )
            festival = result.scalar_one_or_none()
        except:
            festival = None

        return templates.TemplateResponse(
            "admin/festival_form.html",
            {
                "request": request,
                "admin_user": admin_user,
                "festival": festival,
                "action": "Update",
                "error": error_msg,
                "form_data": {
                    "name": name,
                    "location": location,
                    "venue": venue,
                    "dates": dates,
                    "genres": genres,
                    "artists": artists,
                    "ticket_url": ticket_url,
                    "logo_url": logo_url,
                    "primary_color": primary_color,
                    "secondary_color": secondary_color,
                    "accent_colors": accent_colors,
                },
            },
        )

    except Exception as e:
        logger.error(f"Error updating festival {festival_id}: {e}")
        await db.rollback()

        # Get festival data for form
        try:
            result = await db.execute(
                select(FestivalModel)
                .options(selectinload(FestivalModel.artists))
                .filter(FestivalModel.id == UUID(festival_id))
            )
            festival = result.scalar_one_or_none()
        except:
            festival = None

        return templates.TemplateResponse(
            "admin/festival_form.html",
            {
                "request": request,
                "admin_user": admin_user,
                "festival": festival,
                "action": "Update",
                "error": "An error occurred while updating the festival.",
                "form_data": {
                    "name": name,
                    "location": location,
                    "venue": venue,
                    "dates": dates,
                    "genres": genres,
                    "artists": artists,
                    "ticket_url": ticket_url,
                    "logo_url": logo_url,
                    "primary_color": primary_color,
                    "secondary_color": secondary_color,
                    "accent_colors": accent_colors,
                },
            },
        )


@admin_router.post("/festivals/bulk-delete")
async def admin_bulk_delete_festivals(
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Bulk delete festivals."""
    try:
        from uuid import UUID

        from sqlalchemy import delete

        from festival_playlist_generator.models.festival import festival_artists

        # Parse request body
        body = await request.json()
        festival_ids = body.get("festival_ids", [])

        if not festival_ids:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No festival IDs provided"},
            )

        logger.info(f"Attempting to bulk delete {len(festival_ids)} festivals")

        # Convert to UUIDs
        festival_uuids = [UUID(fid) for fid in festival_ids]

        # First, delete all relationships in festival_artists table
        delete_relationships = delete(festival_artists).where(
            festival_artists.c.festival_id.in_(festival_uuids)
        )
        await db.execute(delete_relationships)
        logger.info(
            f"Deleted festival_artists relationships for {len(festival_ids)} festivals"
        )

        # Then delete the festivals
        delete_stmt = delete(FestivalModel).where(FestivalModel.id.in_(festival_uuids))
        result = await db.execute(delete_stmt)
        await db.commit()

        logger.info(f"Successfully bulk deleted {result.rowcount} festivals")  # type: ignore[attr-defined]

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Successfully deleted {result.rowcount} festival(s)",  # type: ignore[attr-defined]
                "deleted_count": result.rowcount,  # type: ignore[attr-defined]
            },
        )

    except Exception as e:
        logger.error(f"Error bulk deleting festivals: {e}", exc_info=True)
        await db.rollback()
        return JSONResponse(
            status_code=500, content={"success": False, "message": str(e)}
        )


@admin_router.get("/artists/{artist_id}/edit", response_class=HTMLResponse)
async def admin_edit_artist(
    request: Request,
    artist_id: str,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Edit artist form."""
    try:
        from uuid import UUID

        from sqlalchemy.orm import selectinload

        artist_uuid = UUID(artist_id)

        # Get artist with relationships
        result = await db.execute(
            select(ArtistModel)
            .options(
                selectinload(ArtistModel.festivals), selectinload(ArtistModel.setlists)
            )
            .filter(ArtistModel.id == artist_uuid)
        )
        artist = result.scalar_one_or_none()

        if not artist:
            return templates.TemplateResponse(
                "admin/artists.html",
                {
                    "request": request,
                    "admin_user": admin_user,
                    "artists": [],
                    "error": "Artist not found",
                },
            )

        # Format data for form
        genres_str = ", ".join(artist.genres) if artist.genres else ""

        return templates.TemplateResponse(
            "admin/artist_edit_form.html",
            {
                "request": request,
                "admin_user": admin_user,
                "artist": artist,
                "action": "Update",
                "form_data": {
                    "name": artist.name,
                    "genres": genres_str,
                    "musicbrainz_id": artist.musicbrainz_id,
                    "popularity_score": artist.popularity_score,
                    "spotify_id": artist.spotify_id,
                    "spotify_image_url": artist.spotify_image_url,
                    "spotify_popularity": artist.spotify_popularity,
                    "spotify_followers": artist.spotify_followers,
                    "logo_url": artist.logo_url,
                },
            },
        )

    except ValueError:
        return templates.TemplateResponse(
            "admin/artists.html",
            {
                "request": request,
                "admin_user": admin_user,
                "artists": [],
                "error": "Invalid artist ID",
            },
        )
    except Exception as e:
        logger.error(f"Error loading artist for edit: {e}")
        return templates.TemplateResponse(
            "admin/artists.html",
            {
                "request": request,
                "admin_user": admin_user,
                "artists": [],
                "error": "Error loading artist",
            },
        )


@admin_router.get("/api/artists/search")
async def admin_search_artists(
    request: Request,
    q: str,
    source: str = "database",  # "database" or "spotify"
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Search for artists by name.

    Args:
        q: Search query
        source: "database" for local DB search, "spotify" for Spotify API search
    """
    try:
        search_term = q.strip()

        if not search_term:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Search term is required"},
            )

        if source == "spotify":
            # Search Spotify API for artist suggestions
            from festival_playlist_generator.services.spotify_artist_service import (
                spotify_artist_service,
            )

            try:
                spotify_artists = spotify_artist_service.search_artists_multiple(
                    search_term, limit=10
                )

                if not spotify_artists:
                    return JSONResponse(
                        status_code=200,
                        content={
                            "success": True,
                            "artists": [],
                            "message": f"No artists found on Spotify matching '{search_term}'",
                        },
                    )

                # Format Spotify results
                results = []
                for artist in spotify_artists:
                    results.append(
                        {
                            "id": artist.id,
                            "name": artist.name,
                            "spotify_id": artist.id,
                            "genres": artist.genres if artist.genres else [],
                            "popularity": artist.popularity,
                            "followers": artist.followers,
                            "image_url": artist.medium_image_url,
                            "spotify_url": artist.spotify_url,
                            "match_score": 100,  # Spotify's own relevance
                            "match_type": "spotify_search",
                            "source": "spotify",
                        }
                    )

                return JSONResponse(
                    status_code=200, content={"success": True, "artists": results}
                )

            except Exception as e:
                logger.error(f"Error searching Spotify: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": f"Spotify search error: {str(e)}",
                    },
                )

        else:
            # Search local database using advanced fuzzy matching
            from festival_playlist_generator.services.advanced_fuzzy_matcher import (
                advanced_fuzzy_search,
            )

            results = await advanced_fuzzy_search(
                db, search_term, limit=10, min_score=40, use_semantic=True
            )

            if not results:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "artists": [],
                        "message": f"No artists found matching '{search_term}'",
                    },
                )

            return JSONResponse(
                status_code=200, content={"success": True, "artists": results}
            )

    except Exception as e:
        logger.error(f"Error searching artists: {e}")
        return JSONResponse(
            status_code=500, content={"success": False, "message": str(e)}
        )


@admin_router.post("/api/setlistfm/search")
async def admin_setlistfm_search(
    request: Request, admin_user: str = Depends(verify_admin_credentials)
) -> Dict[str, Any]:
    """Search for artist on Setlist.fm (admin API) - returns top 5 artist matches."""
    try:
        body = await request.json()
        artist_name = body.get("artist_name", "").strip()

        if not artist_name:
            return {"success": False, "message": "Artist name is required"}

        import httpx

        from festival_playlist_generator.core.config import settings

        if not settings.SETLIST_FM_API_KEY:
            return {"success": False, "message": "Setlist.fm API key not configured"}

        # Search for artists on Setlist.fm
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.setlist.fm/rest/1.0/search/artists",
                params={"artistName": artist_name, "p": 1, "sort": "relevance"},
                headers={
                    "x-api-key": settings.SETLIST_FM_API_KEY,
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "message": f"Setlist.fm API error: {response.status_code}",
                }

            data = response.json()
            artists = data.get("artist", [])[:5]  # Top 5 results

            if artists:
                results = []
                for artist in artists:
                    # Get setlist count for this artist
                    setlist_response = await client.get(
                        f"https://api.setlist.fm/rest/1.0/artist/{artist['mbid']}/setlists",
                        params={"p": 1},
                        headers={
                            "x-api-key": settings.SETLIST_FM_API_KEY,
                            "Accept": "application/json",
                        },
                    )

                    setlist_count = 0
                    if setlist_response.status_code == 200:
                        setlist_data = setlist_response.json()
                        setlist_count = setlist_data.get("total", 0)

                    results.append(
                        {
                            "mbid": artist.get("mbid"),
                            "name": artist.get("name"),
                            "disambiguation": artist.get("disambiguation", ""),
                            "url": artist.get("url", ""),
                            "setlist_count": setlist_count,
                        }
                    )

                return {"success": True, "results": results}
            else:
                return {
                    "success": False,
                    "message": f"No Setlist.fm results found for '{artist_name}'",
                }

    except Exception as e:
        logger.error(f"Error in Setlist.fm search: {e}")
        return {"success": False, "message": f"Internal server error: {str(e)}"}


@admin_router.post("/api/artists/{artist_id}/apply-spotify")
async def admin_apply_spotify_data(
    artist_id: str,
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Apply selected Spotify artist data to the artist."""
    try:
        from uuid import UUID

        from festival_playlist_generator.services.spotify_artist_service import (
            spotify_artist_service,
        )

        body = await request.json()
        spotify_id = body.get("spotify_id")
        force_override = body.get("force_override", False)

        if not spotify_id:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Spotify ID is required"},
            )

        artist_uuid = UUID(artist_id)

        # Get artist
        result = await db.execute(
            select(ArtistModel).filter(ArtistModel.id == artist_uuid)
        )
        artist = result.scalar_one_or_none()

        if not artist:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Artist not found"},
            )

        # Check if this Spotify ID is already used by another artist
        existing_result = await db.execute(
            select(ArtistModel).filter(ArtistModel.spotify_id == spotify_id)
        )
        existing_artist = existing_result.scalar_one_or_none()

        if existing_artist and existing_artist.id != artist_uuid:
            if not force_override:
                # Offer to clear the Spotify ID from the other artist
                return JSONResponse(
                    status_code=409,
                    content={
                        "success": False,
                        "conflict": True,
                        "message": f"This Spotify ID is already linked to: '{existing_artist.name}'",
                        "duplicate_artist": {
                            "id": str(existing_artist.id),
                            "name": existing_artist.name,
                        },
                        "options": {
                            "can_override": True,
                            "override_message": f"Would you like to unlink this Spotify profile from '{existing_artist.name}' and link it to this artist instead?",
                        },
                    },
                )
            else:
                # Clear the Spotify ID from the other artist
                logger.info(
                    f"Unlinking Spotify ID {spotify_id} from artist '{existing_artist.name}' (ID: {existing_artist.id})"
                )
                existing_artist.spotify_id = None
                existing_artist.spotify_image_url = None
                existing_artist.spotify_popularity = None
                existing_artist.spotify_followers = None
                # Keep genres and logo as they might be useful
                await db.flush()

        # Get full Spotify data
        spotify_info = spotify_artist_service.get_artist_by_id(spotify_id)

        if not spotify_info:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Spotify artist not found"},
            )

        # Update artist with Spotify data
        artist.spotify_id = spotify_info.id
        artist.spotify_image_url = spotify_info.medium_image_url
        artist.spotify_popularity = float(spotify_info.popularity)
        artist.spotify_followers = float(spotify_info.followers)
        artist.genres = spotify_info.genres
        if spotify_info.image_url:
            artist.logo_url = spotify_info.image_url
            artist.logo_source = "spotify"

        await db.commit()
        await db.refresh(artist)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Spotify data applied successfully"
                + (
                    " (unlinked from other artist)"
                    if force_override and existing_artist
                    else ""
                ),
                "artist": {
                    "id": str(artist.id),
                    "name": artist.name,
                    "spotify_id": artist.spotify_id,
                    "spotify_image_url": artist.spotify_image_url,
                    "spotify_popularity": artist.spotify_popularity,
                    "spotify_followers": artist.spotify_followers,
                    "genres": artist.genres,
                    "logo_url": artist.logo_url,
                },
            },
        )

    except Exception as e:
        logger.error(f"Error applying Spotify data: {e}")
        await db.rollback()
        return JSONResponse(
            status_code=500, content={"success": False, "message": str(e)}
        )


@admin_router.post("/api/artists/{artist_id}/apply-setlistfm")
async def admin_apply_setlistfm_data(
    artist_id: str,
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Apply selected Setlist.fm artist data and fetch setlists."""
    try:
        from uuid import UUID

        from festival_playlist_generator.services.setlist_enrichment_service import (
            setlist_enrichment_service,
        )

        body = await request.json()
        mbid = body.get("mbid")

        if not mbid:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "MusicBrainz ID is required"},
            )

        artist_uuid = UUID(artist_id)

        # Get artist
        result = await db.execute(
            select(ArtistModel).filter(ArtistModel.id == artist_uuid)
        )
        artist = result.scalar_one_or_none()

        if not artist:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Artist not found"},
            )

        # Update MusicBrainz ID
        artist.musicbrainz_id = mbid
        await db.commit()

        # Fetch setlists
        setlist_result = await setlist_enrichment_service.enrich_artists(
            [str(artist_uuid)], db, limit=10
        )

        await db.refresh(artist)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Setlist.fm data applied successfully. Fetched {setlist_result.get('enriched', 0)} setlists.",
                "setlists_added": setlist_result.get("enriched", 0),
                "artist": {
                    "id": str(artist.id),
                    "name": artist.name,
                    "musicbrainz_id": artist.musicbrainz_id,
                },
            },
        )

    except Exception as e:
        logger.error(f"Error applying Setlist.fm data: {e}")
        return JSONResponse(
            status_code=500, content={"success": False, "message": str(e)}
        )


@admin_router.post("/api/artists/{artist_id}/enrich")
async def admin_enrich_artist(
    artist_id: str,
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Enrich artist with Spotify and Setlist.fm data."""
    try:
        from uuid import UUID

        from festival_playlist_generator.services.artist_enrichment_service import (
            artist_enrichment_service,
        )
        from festival_playlist_generator.services.setlist_enrichment_service import (
            setlist_enrichment_service,
        )

        artist_uuid = UUID(artist_id)

        # Get artist
        result = await db.execute(
            select(ArtistModel).filter(ArtistModel.id == artist_uuid)
        )
        artist = result.scalar_one_or_none()

        if not artist:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Artist not found"},
            )

        enrichment_results: Dict[str, Dict[str, Any]] = {
            "spotify": {"success": False, "message": ""},
            "setlistfm": {"success": False, "message": ""},
        }

        # Enrich with Spotify data
        try:
            spotify_result = await artist_enrichment_service.enrich_artists(
                [str(artist_uuid)], db
            )
            if spotify_result["enriched"] > 0:
                enrichment_results["spotify"] = {
                    "success": True,
                    "message": "Spotify data added successfully",
                }
            elif spotify_result["skipped"] > 0:
                enrichment_results["spotify"] = {
                    "success": True,
                    "message": "Artist already has Spotify data",
                }
            else:
                enrichment_results["spotify"] = {
                    "success": False,
                    "message": "No Spotify data found",
                }
        except Exception as e:
            logger.error(f"Error enriching with Spotify: {e}")
            enrichment_results["spotify"] = {"success": False, "message": str(e)}

        # Enrich with Setlist.fm data
        try:
            setlist_result = await setlist_enrichment_service.enrich_artists(
                [str(artist_uuid)], db
            )
            if setlist_result["enriched"] > 0:
                enrichment_results["setlistfm"] = {
                    "success": True,
                    "message": f"Added {setlist_result['enriched']} setlists",
                }
            elif setlist_result["skipped"] > 0:
                enrichment_results["setlistfm"] = {
                    "success": True,
                    "message": "Artist already has setlist data",
                }
            else:
                enrichment_results["setlistfm"] = {
                    "success": False,
                    "message": "No setlist data found",
                }
        except Exception as e:
            logger.error(f"Error enriching with Setlist.fm: {e}")
            enrichment_results["setlistfm"] = {"success": False, "message": str(e)}

        # Refresh artist data
        await db.refresh(artist)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Enrichment complete",
                "results": enrichment_results,
                "artist": {
                    "id": str(artist.id),
                    "name": artist.name,
                    "spotify_id": artist.spotify_id,
                    "spotify_image_url": artist.spotify_image_url,
                    "spotify_popularity": artist.spotify_popularity,
                    "spotify_followers": artist.spotify_followers,
                    "genres": artist.genres,
                    "logo_url": artist.logo_url,
                },
            },
        )

    except Exception as e:
        logger.error(f"Error enriching artist: {e}")
        return JSONResponse(
            status_code=500, content={"success": False, "message": str(e)}
        )


@admin_router.post("/artists/{artist_id}/update")
async def admin_update_artist(
    request: Request,
    artist_id: str,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
    name: str = Form(...),
    genres: Optional[str] = Form(None),
    musicbrainz_id: Optional[str] = Form(None),
    popularity_score: Optional[float] = Form(None),
    spotify_id: Optional[str] = Form(None),
    spotify_image_url: Optional[str] = Form(None),
    spotify_popularity: Optional[float] = Form(None),
    spotify_followers: Optional[float] = Form(None),
    logo_url: Optional[str] = Form(None),
) -> Response:
    """Update an existing artist."""
    try:
        from uuid import UUID

        from sqlalchemy.orm import selectinload

        artist_uuid = UUID(artist_id)

        # Get artist
        result = await db.execute(
            select(ArtistModel)
            .options(
                selectinload(ArtistModel.festivals), selectinload(ArtistModel.setlists)
            )
            .filter(ArtistModel.id == artist_uuid)
        )
        artist = result.scalar_one_or_none()

        if not artist:
            raise ValueError("Artist not found")

        # Parse genres
        genre_list = (
            [g.strip() for g in genres.split(",") if g.strip()] if genres else []
        )

        # Update artist fields
        artist.name = name
        artist.genres = genre_list
        artist.musicbrainz_id = musicbrainz_id if musicbrainz_id else None
        artist.popularity_score = popularity_score
        artist.spotify_id = spotify_id if spotify_id else None
        artist.spotify_image_url = spotify_image_url if spotify_image_url else None
        artist.spotify_popularity = spotify_popularity
        artist.spotify_followers = spotify_followers
        artist.logo_url = logo_url if logo_url else None
        if logo_url:
            artist.logo_source = "manual"

        await db.commit()

        return RedirectResponse(url="/admin/artists?updated=success", status_code=303)

    except ValueError as ve:
        error_msg = str(ve)

        # Get artist data for form
        try:
            result = await db.execute(
                select(ArtistModel)
                .options(
                    selectinload(ArtistModel.festivals),
                    selectinload(ArtistModel.setlists),
                )
                .filter(ArtistModel.id == UUID(artist_id))
            )
            artist = result.scalar_one_or_none()
        except:
            artist = None

        return templates.TemplateResponse(
            "admin/artist_edit_form.html",
            {
                "request": request,
                "admin_user": admin_user,
                "artist": artist,
                "action": "Update",
                "error": error_msg,
                "form_data": {
                    "name": name,
                    "genres": genres,
                    "musicbrainz_id": musicbrainz_id,
                    "popularity_score": popularity_score,
                    "spotify_id": spotify_id,
                    "spotify_image_url": spotify_image_url,
                    "spotify_popularity": spotify_popularity,
                    "spotify_followers": spotify_followers,
                    "logo_url": logo_url,
                },
            },
        )

    except Exception as e:
        logger.error(f"Error updating artist {artist_id}: {e}")
        await db.rollback()

        # Get artist data for form
        try:
            result = await db.execute(
                select(ArtistModel)
                .options(
                    selectinload(ArtistModel.festivals),
                    selectinload(ArtistModel.setlists),
                )
                .filter(ArtistModel.id == UUID(artist_id))
            )
            artist = result.scalar_one_or_none()
        except:
            artist = None

        return templates.TemplateResponse(
            "admin/artist_edit_form.html",
            {
                "request": request,
                "admin_user": admin_user,
                "artist": artist,
                "action": "Update",
                "error": "An error occurred while updating the artist.",
                "form_data": {
                    "name": name,
                    "genres": genres,
                    "musicbrainz_id": musicbrainz_id,
                    "popularity_score": popularity_score,
                    "spotify_id": spotify_id,
                    "spotify_image_url": spotify_image_url,
                    "spotify_popularity": spotify_popularity,
                    "spotify_followers": spotify_followers,
                    "logo_url": logo_url,
                },
            },
        )


@admin_router.post("/artists/{artist_id}/delete")
async def admin_delete_artist(
    artist_id: str,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete an artist and all related data."""
    try:
        from uuid import UUID

        from sqlalchemy import delete
        from sqlalchemy.orm import selectinload

        logger.info(f"Admin {admin_user} attempting to delete artist {artist_id}")

        artist_uuid = UUID(artist_id)

        # Check if artist is associated with any festivals
        result = await db.execute(
            select(ArtistModel)
            .options(selectinload(ArtistModel.festivals))
            .filter(ArtistModel.id == artist_uuid)
        )
        artist = result.scalar_one_or_none()

        if not artist:
            logger.warning(f"Artist {artist_id} not found")
            return RedirectResponse(
                url="/admin/artists?error=not_found", status_code=303
            )

        if artist.festivals:
            # Artist is still associated with festivals, prevent deletion
            festival_names = ", ".join([f.name for f in artist.festivals[:3]])
            if len(artist.festivals) > 3:
                festival_names += f" and {len(artist.festivals) - 3} more"
            logger.warning(
                f"Cannot delete artist {artist.name} - still associated with festivals: {festival_names}"
            )
            return RedirectResponse(
                url=f"/admin/artists?error=has_festivals&artist={artist.name}&festivals={len(artist.festivals)}",
                status_code=303,
            )

        logger.info(
            f"Deleting artist {artist.name} (ID: {artist_id}) - Orphaned: {not artist.spotify_id and len(artist.setlists) == 0}"
        )

        # First, delete relationships in festival_artists table (should be empty at this point)
        from festival_playlist_generator.models.festival import festival_artists

        delete_relationships = delete(festival_artists).where(
            festival_artists.c.artist_id == artist_uuid
        )
        await db.execute(delete_relationships)

        # Delete any setlists for this artist
        from festival_playlist_generator.models.setlist import Setlist

        delete_setlists = delete(Setlist).where(Setlist.artist_id == artist_uuid)
        await db.execute(delete_setlists)

        # Delete any playlists for this artist
        from festival_playlist_generator.models.playlist import Playlist

        delete_playlists = delete(Playlist).where(Playlist.artist_id == artist_uuid)
        await db.execute(delete_playlists)

        # Finally, delete the artist
        delete_artist = delete(ArtistModel).where(ArtistModel.id == artist_uuid)
        await db.execute(delete_artist)

        await db.commit()

        logger.info(f"Successfully deleted artist {artist.name} (ID: {artist_id})")
        return RedirectResponse(url="/admin/artists?deleted=success", status_code=303)
    except Exception as e:
        logger.error(f"Error deleting artist {artist_id}: {e}", exc_info=True)
        await db.rollback()
        return RedirectResponse(
            url="/admin/artists?error=delete_failed", status_code=303
        )


@admin_router.get("/api/stats")
async def admin_get_stats(
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get current admin dashboard statistics."""
    try:
        # Get counts
        festivals_result = await db.execute(select(FestivalModel))
        festivals_count = len(festivals_result.scalars().all())

        artists_result = await db.execute(select(ArtistModel))
        artists_count = len(artists_result.scalars().all())

        users_result = await db.execute(select(UserModel))
        users_count = len(users_result.scalars().all())

        return {
            "success": True,
            "data": {
                "festivals_count": festivals_count,
                "artists_count": artists_count,
                "users_count": users_count,
            },
        }
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        return {"success": False, "message": "Error retrieving statistics"}


@admin_router.post("/api/cache/warm")
async def admin_warm_cache(
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Warm the nginx image cache by pre-fetching all images."""
    try:
        from festival_playlist_generator.services.cache_warmer import cache_warmer

        logger.info(f"Admin {admin_user} initiated cache warming")

        # Warm the cache
        stats = await cache_warmer.warm_cache(db)

        return {
            "success": True,
            "message": f"Cache warming complete: {stats['successful']} images cached",
            "data": stats,
        }
    except Exception as e:
        logger.error(f"Error warming cache: {e}")
        return {"success": False, "message": f"Error warming cache: {str(e)}"}


@admin_router.post("/artists/bulk-delete")
async def admin_bulk_delete_artists(
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Bulk delete multiple artists and all their related data."""
    try:
        from uuid import UUID

        from sqlalchemy import delete

        # Get the JSON body
        body = await request.json()
        artist_ids = body.get("artist_ids", [])

        if not artist_ids:
            return {"success": False, "message": "No artist IDs provided"}

        # Convert string IDs to UUIDs
        artist_uuids = []
        for artist_id in artist_ids:
            try:
                artist_uuids.append(UUID(artist_id))
            except ValueError:
                return {
                    "success": False,
                    "message": f"Invalid artist ID format: {artist_id}",
                }

        # Check if any artists are associated with festivals
        result = await db.execute(
            select(ArtistModel)
            .options(selectinload(ArtistModel.festivals))
            .filter(ArtistModel.id.in_(artist_uuids))
        )
        artists = result.scalars().all()

        artists_with_festivals = [a for a in artists if a.festivals]
        if artists_with_festivals:
            artist_names_list = [a.name for a in artists_with_festivals[:3]]
            artist_names = ", ".join(artist_names_list)
            if len(artists_with_festivals) > 3:
                artist_names += f" and {len(artists_with_festivals) - 3} more"
            return {
                "success": False,
                "message": f"Cannot delete {len(artists_with_festivals)} artist(s) still associated with festivals: {artist_names}. Remove them from festivals first.",
            }

        # Get artist names for logging
        artist_names_for_logging = [a.name for a in artists]

        # Delete in the correct order to avoid foreign key constraint violations

        # 1. Delete relationships in festival_artists table (should be empty at this point)
        from festival_playlist_generator.models.festival import festival_artists

        delete_relationships = delete(festival_artists).where(
            festival_artists.c.artist_id.in_(artist_uuids)
        )
        await db.execute(delete_relationships)

        # 2. Delete any setlists for these artists
        from festival_playlist_generator.models.setlist import Setlist

        delete_setlists = delete(Setlist).where(Setlist.artist_id.in_(artist_uuids))
        await db.execute(delete_setlists)

        # 3. Delete any playlists for these artists
        from festival_playlist_generator.models.playlist import Playlist

        delete_playlists = delete(Playlist).where(Playlist.artist_id.in_(artist_uuids))
        await db.execute(delete_playlists)

        # 4. Finally, delete the artists
        delete_artists = delete(ArtistModel).where(ArtistModel.id.in_(artist_uuids))
        result = await db.execute(delete_artists)

        await db.commit()

        deleted_count = result.rowcount  # type: ignore[attr-defined]
        logger.info(f"Bulk deleted {deleted_count} artists: {', '.join(artist_names_for_logging)}")

        return {
            "success": True,
            "message": f"Successfully deleted {deleted_count} artist(s)",
            "deleted_count": deleted_count,
        }

    except Exception as e:
        logger.error(f"Error bulk deleting artists: {e}")
        await db.rollback()
        return {"success": False, "message": f"Error deleting artists: {str(e)}"}


@admin_router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Admin users management page."""
    try:
        # Get all users
        result = await db.execute(
            select(UserModel).order_by(UserModel.created_at.desc())
        )
        users = result.scalars().all()

        response = templates.TemplateResponse(
            "admin/users.html",
            {"request": request, "admin_user": admin_user, "users": users},
        )

        # Add no-cache headers if refresh parameter is present
        if request.query_params.get("_refresh"):
            response = add_no_cache_headers(response)

        return response

    except Exception as e:
        response = templates.TemplateResponse(
            "admin/users.html",
            {
                "request": request,
                "admin_user": admin_user,
                "users": [],
                "error": str(e),
            },
        )

        # Add no-cache headers if refresh parameter is present
        if request.query_params.get("_refresh"):
            response = add_no_cache_headers(response)

        return response


@admin_router.post("/artists/enrich-all")
async def admin_enrich_all_artists(
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Enrich all artists that don't have Spotify data yet."""
    try:
        from festival_playlist_generator.services.artist_enrichment_service import (
            artist_enrichment_service,
        )

        # Get all artists without Spotify data
        result = await db.execute(
            select(ArtistModel).filter(ArtistModel.spotify_id == None)
        )
        artists_to_enrich = result.scalars().all()

        if not artists_to_enrich:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "All artists already have Spotify data",
                    "enriched": 0,
                    "skipped": 0,
                    "failed": 0,
                    "total": 0,
                },
            )

        artist_ids = [str(artist.id) for artist in artists_to_enrich]
        logger.info(f"Starting bulk enrichment for {len(artist_ids)} artists")

        # Enrich artists
        enrichment_result = await artist_enrichment_service.enrich_artists(
            artist_ids, db
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Enriched {enrichment_result['enriched']} artists with Spotify data",
                **enrichment_result,
            },
        )

    except Exception as e:
        logger.error(f"Error in bulk artist enrichment: {e}")
        return JSONResponse(
            status_code=500, content={"success": False, "message": str(e)}
        )


@admin_router.post("/users/{user_id}/delete")
async def admin_delete_user(
    user_id: str,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a user and all related data (un-onboard)."""
    try:
        from uuid import UUID

        from sqlalchemy import delete

        from festival_playlist_generator.core.redis import cache

        user_uuid = UUID(user_id)

        # Get user info for logging
        user_result = await db.execute(
            select(UserModel).where(UserModel.id == user_uuid)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            logger.warning(f"Attempted to delete non-existent user: {user_id}")
            return RedirectResponse(url="/admin/users?_refresh=1", status_code=303)

        user_email = user.email

        # Delete in the correct order to avoid foreign key constraint violations

        # 1. Delete user song preferences
        from festival_playlist_generator.models.user import UserSongPreference

        delete_preferences = delete(UserSongPreference).where(
            UserSongPreference.user_id == user_uuid
        )
        await db.execute(delete_preferences)

        # 2. Delete user playlists
        from festival_playlist_generator.models.playlist import Playlist

        delete_playlists = delete(Playlist).where(Playlist.user_id == user_uuid)
        await db.execute(delete_playlists)

        # 3. Delete audit logs for this user
        from festival_playlist_generator.models.audit_log import AuditLog

        delete_audit_logs = delete(AuditLog).where(AuditLog.user_id == user_uuid)
        await db.execute(delete_audit_logs)

        # 4. Invalidate all active sessions for this user
        # Since we don't have a user_id index on sessions, we need to scan for them
        # This is a limitation of the current session storage design
        # For now, we'll log this and the session will expire naturally
        logger.info(
            f"User {user_email} deleted - active sessions will expire naturally within {24} hours"
        )

        # 5. Finally, delete the user
        delete_user = delete(UserModel).where(UserModel.id == user_uuid)
        await db.execute(delete_user)

        await db.commit()

        logger.info(f"Successfully deleted user: {user_email} (ID: {user_id})")

        # Redirect with refresh parameter to force cache bypass
        return RedirectResponse(url="/admin/users?_refresh=1", status_code=303)

    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        await db.rollback()
        return RedirectResponse(
            url="/admin/users?error=delete_failed&_refresh=1", status_code=303
        )


@admin_router.post("/api/festivals/{festival_id}/refresh-branding")
async def admin_refresh_festival_branding(
    festival_id: str,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Refresh festival branding by re-scraping from the website."""
    try:
        from uuid import UUID

        import httpx

        from festival_playlist_generator.services.brand_extractor import BrandExtractor
        from festival_playlist_generator.services.festival_scraper import (
            FestivalScraper,
        )

        festival_uuid = UUID(festival_id)

        # Get the festival
        result = await db.execute(
            select(FestivalModel).where(FestivalModel.id == festival_uuid)
        )
        festival = result.scalar_one_or_none()

        if not festival:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Festival not found"},
            )

        # Try to get the festival URL from ticket_url or search for it
        festival_url = festival.ticket_url

        if not festival_url:
            # Try to find the festival website using the scraper
            logger.info(
                f"No URL found for festival {festival.name}, attempting to search..."
            )
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "No festival URL available. Please add a ticket URL or website URL to the festival.",
                },
            )

        # Fetch the HTML content
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(festival_url, follow_redirects=True)
                response.raise_for_status()
                html_content = response.text
            except Exception as e:
                logger.error(f"Error fetching festival URL {festival_url}: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": f"Failed to fetch festival website: {str(e)}",
                    },
                )

        # Extract branding
        brand_extractor = BrandExtractor()
        try:
            branding = await brand_extractor.extract_festival_branding(
                html_content, festival_url
            )

            # Store the extracted branding but mark that it came from a refresh
            # This allows the admin to review before saving
            # We return the branding data but don't automatically save it
            # The JavaScript will populate the form fields, and the admin can review/modify before saving

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Branding extracted successfully. Review the values and save the form to apply changes.",
                    "branding": {
                        "logo_url": branding.logo_url,
                        "primary_color": branding.primary_color,
                        "secondary_color": branding.secondary_color,
                        "accent_colors": branding.accent_colors,
                    },
                },
            )

        except Exception as e:
            logger.error(f"Error extracting branding for festival {festival.name}: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": f"Failed to extract branding: {str(e)}",
                },
            )

    except Exception as e:
        logger.error(f"Error refreshing festival branding: {e}")
        return JSONResponse(
            status_code=500, content={"success": False, "message": str(e)}
        )


@admin_router.get("/duplicates", response_class=HTMLResponse)
async def admin_duplicates(
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Admin duplicate artists detection page."""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from festival_playlist_generator.services.duplicate_detection_service import (
            DuplicateDetectionService,
        )

        # Create synchronous session for duplicate detection service
        # (The service uses sync SQLAlchemy)
        db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        sync_session = Session()

        try:
            # Find all duplicate groups
            detection_service = DuplicateDetectionService(sync_session)
            groups = detection_service.find_all_duplicates()

            response = templates.TemplateResponse(
                "admin/duplicates.html",
                {
                    "request": request,
                    "admin_user": admin_user,
                    "duplicate_groups": groups,
                    "total_groups": len(groups),
                },
            )

            # Add no-cache headers if refresh parameter is present
            if request.query_params.get("_refresh"):
                response = add_no_cache_headers(response)

            return response

        finally:
            sync_session.close()

    except Exception as e:
        logger.error(f"Error finding duplicates: {e}")
        response = templates.TemplateResponse(
            "admin/duplicates.html",
            {
                "request": request,
                "admin_user": admin_user,
                "duplicate_groups": [],
                "total_groups": 0,
                "error": str(e),
            },
        )

        # Add no-cache headers if refresh parameter is present
        if request.query_params.get("_refresh"):
            response = add_no_cache_headers(response)

        return response


@admin_router.post("/api/duplicates/preview")
async def admin_preview_merge(
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Preview a merge operation."""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from festival_playlist_generator.services.merge_service import MergeService

        # Parse request body
        body = await request.json()
        primary_id = body.get("primary_id")
        secondary_ids = body.get("secondary_ids", [])

        if not primary_id or not secondary_ids:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Missing primary_id or secondary_ids",
                },
            )

        # Create synchronous session for merge service
        db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        sync_session = Session()

        try:
            # Preview the merge
            merge_service = MergeService(sync_session)
            preview = merge_service.preview_merge(primary_id, secondary_ids)

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "preview": {
                        "primary_artist_id": preview.primary_artist_id,
                        "primary_artist_name": preview.primary_artist_name,
                        "secondary_artist_ids": preview.secondary_artist_ids,
                        "secondary_artist_names": preview.secondary_artist_names,
                        "total_festivals": preview.total_festivals,
                        "total_setlists": preview.total_setlists,
                        "spotify_data_available": preview.spotify_data_available,
                        "spotify_data_source": preview.spotify_data_source,
                        "warnings": preview.warnings,
                    },
                },
            )

        finally:
            sync_session.close()

    except ValueError as ve:
        return JSONResponse(
            status_code=400, content={"success": False, "message": str(ve)}
        )
    except Exception as e:
        logger.error(f"Error previewing merge: {e}")
        return JSONResponse(
            status_code=500, content={"success": False, "message": str(e)}
        )


@admin_router.post("/api/duplicates/merge")
async def admin_merge_artists(
    request: Request,
    admin_user: str = Depends(verify_admin_credentials),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Merge duplicate artists."""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from festival_playlist_generator.services.merge_service import MergeService

        # Parse request body
        body = await request.json()
        primary_id = body.get("primary_id")
        secondary_ids = body.get("secondary_ids", [])

        if not primary_id or not secondary_ids:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Missing primary_id or secondary_ids",
                },
            )

        logger.info(
            f"Admin {admin_user} merging artists: primary={primary_id}, secondaries={secondary_ids}"
        )

        # Create synchronous session for merge service
        db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        sync_session = Session()

        try:
            # Perform the merge
            merge_service = MergeService(sync_session)
            result = merge_service.merge_artists(
                primary_id=primary_id,
                secondary_ids=secondary_ids,
                performed_by=admin_user,
            )

            if result.success:
                logger.info(
                    f"Successfully merged artists: {result.merged_artist_names} into {result.primary_artist_name}"
                )
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": f"Successfully merged {len(result.merged_artist_ids)} artist(s) into {result.primary_artist_name}",
                        "result": {
                            "primary_artist_id": result.primary_artist_id,
                            "primary_artist_name": result.primary_artist_name,
                            "merged_artist_ids": result.merged_artist_ids,
                            "merged_artist_names": result.merged_artist_names,
                            "festivals_transferred": result.festivals_transferred,
                            "setlists_transferred": result.setlists_transferred,
                            "spotify_data_source": result.spotify_data_source,
                        },
                    },
                )
            else:
                logger.error(f"Merge failed: {result.error}")
                return JSONResponse(
                    status_code=500, content={"success": False, "message": result.error}
                )

        finally:
            sync_session.close()

    except ValueError as ve:
        return JSONResponse(
            status_code=400, content={"success": False, "message": str(ve)}
        )
    except Exception as e:
        logger.error(f"Error merging artists: {e}")
        return JSONResponse(
            status_code=500, content={"success": False, "message": str(e)}
        )
