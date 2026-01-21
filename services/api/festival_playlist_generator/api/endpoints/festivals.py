"""Festival API endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.core.container import get_festival_service
from festival_playlist_generator.models.festival import Festival as FestivalModel
from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.schemas.festival import Festival, FestivalCreate, FestivalUpdate
from festival_playlist_generator.api.response_formatter import APIVersionManager
from festival_playlist_generator.api.versioning import get_request_version, version_compatible_response
from festival_playlist_generator.services.festival_enrichment import festival_enrichment_service
from festival_playlist_generator.services.festival_service import FestivalService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/enrich/{clashfinder_id}")
async def enrich_festival_data(clashfinder_id: str):
    """
    Fetch and enrich festival data from Clashfinder.
    
    Args:
        clashfinder_id: The Clashfinder event ID (e.g., 'coachella2024', 'glastonbury2025')
    
    Returns:
        Enriched festival data including name, location, dates, artists, etc.
    """
    try:
        enriched_data = await festival_enrichment_service.fetch_from_clashfinder(clashfinder_id)
        
        if not enriched_data:
            return JSONResponse(content={
                "success": False,
                "error": "Festival not found",
                "message": f"Could not find festival data for Clashfinder ID: {clashfinder_id}",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            }, status_code=404)
        
        if "error" in enriched_data:
            return JSONResponse(content={
                "success": False,
                "error": enriched_data["error"],
                "message": "Failed to fetch festival data from Clashfinder",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            }, status_code=400)
        
        return JSONResponse(content={
            "success": True,
            "data": enriched_data,
            "message": "Festival data enriched successfully",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        })
        
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "error": "Internal server error",
            "message": str(e),
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        }, status_code=500)


@router.get("/scrape")
async def scrape_festival_by_name(
    name: str = Query(..., description="Festival name to search for"),
    year: Optional[str] = Query(None, description="Optional year (e.g., 2024)"),
    url: Optional[str] = Query(None, description="Optional direct URL to scrape"),
    db: AsyncSession = Depends(get_db)
):
    """
    Search for a festival by name and use AI to extract its data from the web.
    This intelligently finds the festival's official website and uses AI to extract lineup information.
    
    Args:
        name: Festival name (e.g., "Download Festival", "Coachella")
        year: Optional year (e.g., "2024", "2026")
        url: Optional direct URL to scrape (bypasses search)
    
    Returns:
        Festival data including artists, dates, location, etc.
    """
    try:
        from festival_playlist_generator.services.festival_scraper import festival_scraper
        
        if url:
            # Direct URL scraping with AI
            logger.info(f"Scraping URL with AI: {url}")
            festival_data = await festival_scraper.scrape_url_with_ai(url, name)
        else:
            # Search and scrape with AI
            logger.info(f"Searching and scraping festival: {name} {year or ''}")
            festival_data = await festival_scraper.search_and_scrape_festival(name, year)
        
        if not festival_data:
            return JSONResponse(content={
                "success": False,
                "error": "Festival not found",
                "message": f"Could not find or extract festival data for: {name}. Make sure you have OPENAI_API_KEY or ANTHROPIC_API_KEY configured in your .env file.",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            }, status_code=404)
        
        return JSONResponse(content={
            "success": True,
            "data": festival_data,
            "message": f"Successfully extracted festival data with {len(festival_data.get('artists', []))} artists using AI",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        })
        
    except Exception as e:
        logger.error(f"Error scraping festival: {e}")
        return JSONResponse(content={
            "success": False,
            "error": "Scraping failed",
            "message": str(e),
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        }, status_code=500)


@router.post("/scrape/import")
async def scrape_and_import_festivals(db: AsyncSession = Depends(get_db)):
    """
    Scrape festivals from web sources and import them into the database.
    This will create new festivals and update existing ones.
    
    Returns:
        Summary of imported festivals
    """
    try:
        from festival_playlist_generator.services.festival_scraper import festival_scraper
        from sqlalchemy.orm import selectinload
        
        logger.info("Starting festival scraping and import...")
        scraped_festivals = await festival_scraper.scrape_all_sources()
        
        imported_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        
        for festival_data in scraped_festivals:
            try:
                # Check if festival already exists
                result = await db.execute(
                    select(FestivalModel)
                    .filter(FestivalModel.name.ilike(f"%{festival_data['name']}%"))
                    .options(selectinload(FestivalModel.artists))
                )
                existing_festival = result.scalar_one_or_none()
                
                if existing_festival:
                    # Update existing festival if we have more data
                    if festival_data['artists'] and len(festival_data['artists']) > len(existing_festival.artists):
                        # Add new artists
                        for artist_name in festival_data['artists']:
                            artist_result = await db.execute(select(ArtistModel).filter(ArtistModel.name == artist_name))
                            artist = artist_result.scalar_one_or_none()
                            if not artist:
                                artist = ArtistModel(name=artist_name)
                                db.add(artist)
                            if artist not in existing_festival.artists:
                                existing_festival.artists.append(artist)
                        updated_count += 1
                    else:
                        skipped_count += 1
                else:
                    # Create new festival
                    if not festival_data['dates']:
                        # Skip festivals without dates
                        skipped_count += 1
                        continue
                    
                    # Parse dates
                    dates = [datetime.strptime(d, '%Y-%m-%d') for d in festival_data['dates']]
                    
                    new_festival = FestivalModel(
                        name=festival_data['name'],
                        location=festival_data['location'],
                        venue=festival_data.get('venue', ''),
                        dates=dates,
                        genres=festival_data.get('genres', []),
                        ticket_url=festival_data.get('source_url', '')
                    )
                    
                    # Add artists
                    for artist_name in festival_data.get('artists', [])[:50]:  # Limit to 50 artists
                        artist_result = await db.execute(select(ArtistModel).filter(ArtistModel.name == artist_name))
                        artist = artist_result.scalar_one_or_none()
                        if not artist:
                            artist = ArtistModel(name=artist_name)
                            db.add(artist)
                        new_festival.artists.append(artist)
                    
                    db.add(new_festival)
                    imported_count += 1
                    
            except Exception as e:
                logger.error(f"Error importing festival {festival_data.get('name', 'unknown')}: {e}")
                errors.append(f"{festival_data.get('name', 'unknown')}: {str(e)}")
                continue
        
        await db.commit()
        
        return JSONResponse(content={
            "success": True,
            "data": {
                "scraped": len(scraped_festivals),
                "imported": imported_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "errors": errors[:10]  # Limit error list
            },
            "message": f"Imported {imported_count} new festivals, updated {updated_count}, skipped {skipped_count}",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        })
        
    except Exception as e:
        logger.error(f"Error in scrape and import: {e}")
        return JSONResponse(content={
            "success": False,
            "error": "Import failed",
            "message": str(e),
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        }, status_code=500)


@router.post("/", status_code=201)
async def create_festival(
    festival: FestivalCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new festival."""
    try:
        from sqlalchemy.orm import selectinload
        
        # Create festival instance
        db_festival = FestivalModel(
            name=festival.name,
            dates=festival.dates,
            location=festival.location,
            venue=festival.venue,
            genres=festival.genres,
            ticket_url=festival.ticket_url,
            # Visual branding fields
            logo_url=festival.logo_url,
            primary_color=festival.primary_color,
            secondary_color=festival.secondary_color,
            accent_colors=festival.accent_colors,
            branding_extracted_at=festival.branding_extracted_at
        )
        
        # Add artists if provided
        new_artist_ids = []
        artist_images = festival.artist_images or {}
        
        if festival.artists:
            for artist_name in festival.artists:
                # Find or create artist
                result = await db.execute(select(ArtistModel).filter(ArtistModel.name == artist_name))
                artist = result.scalar_one_or_none()
                if not artist:
                    artist = ArtistModel(name=artist_name)
                    db.add(artist)
                    await db.flush()  # Flush to get the artist ID
                    new_artist_ids.append(str(artist.id))
                
                # Update artist logo if we have image data for this artist
                if artist_name in artist_images:
                    image_data = artist_images[artist_name]
                    artist.logo_url = image_data.get('logo_url')
                    artist.logo_source = image_data.get('logo_source', 'festival')
                    logger.info(f"Set logo for artist {artist_name}: {artist.logo_url}")
                
                db_festival.artists.append(artist)
        
        db.add(db_festival)
        await db.commit()
        await db.refresh(db_festival)
        
        # Enrich new artists with Spotify data
        if new_artist_ids:
            try:
                from festival_playlist_generator.services.artist_enrichment_service import artist_enrichment_service
                logger.info(f"Enriching {len(new_artist_ids)} new artists with Spotify data...")
                enrichment_result = await artist_enrichment_service.enrich_artists(new_artist_ids, db)
                logger.info(f"Artist enrichment complete: {enrichment_result}")
            except Exception as e:
                logger.error(f"Error enriching artists: {e}")
                # Don't fail the festival creation if enrichment fails
        
        # Enrich new artists with setlist data
        if new_artist_ids:
            try:
                from festival_playlist_generator.services.setlist_enrichment_service import setlist_enrichment_service
                logger.info(f"Enriching {len(new_artist_ids)} new artists with setlist data...")
                setlist_enrichment_result = await setlist_enrichment_service.enrich_artists(new_artist_ids, db)
                logger.info(f"Setlist enrichment complete: {setlist_enrichment_result}")
            except Exception as e:
                logger.error(f"Error enriching artists with setlist data: {e}")
                # Don't fail the festival creation if enrichment fails
        
        # Load artists relationship
        await db.execute(select(FestivalModel).options(selectinload(FestivalModel.artists)).filter(FestivalModel.id == db_festival.id))
        
        # Convert to response format
        return JSONResponse(content={
            "success": True,
            "data": {
                "id": str(db_festival.id),
                "name": db_festival.name,
                "dates": [date.isoformat() for date in db_festival.dates],
                "location": db_festival.location,
                "venue": db_festival.venue,
                "genres": db_festival.genres or [],
                "ticket_url": db_festival.ticket_url,
                "artists": [artist.name for artist in db_festival.artists],
                "created_at": db_festival.created_at.isoformat(),
                "updated_at": db_festival.updated_at.isoformat(),
                # Visual branding fields
                "logo_url": db_festival.logo_url,
                "primary_color": db_festival.primary_color,
                "secondary_color": db_festival.secondary_color,
                "accent_colors": db_festival.accent_colors,
                "branding_extracted_at": db_festival.branding_extracted_at.isoformat() if db_festival.branding_extracted_at else None
            },
            "message": "Festival created successfully",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        }, status_code=201)
        
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "error": "Internal server error",
            "message": str(e),
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        }, status_code=500)


@router.get("/test")
async def test_festivals_endpoint():
    """Simple test endpoint to check if basic functionality works."""
    return {"message": "Festivals endpoint is working", "timestamp": "2026-01-13"}


@router.get("/")
async def list_festivals(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of festivals to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of festivals to return"),
    location: Optional[str] = Query(None, description="Filter by location"),
    genre: Optional[str] = Query(None, description="Filter by genre"),
    artist: Optional[str] = Query(None, description="Filter by artist name"),
    db: AsyncSession = Depends(get_db),
    festival_service: FestivalService = Depends(get_festival_service)
):
    """List festivals with optional filtering."""
    try:
        # Calculate page from skip/limit
        page = (skip // limit) + 1
        per_page = limit
        
        # Build search query
        search = location if location else (artist if artist else None)
        
        # Get festivals via service
        festivals, total = await festival_service.search_festivals(
            search=search,
            page=page,
            per_page=per_page,
            order_by="dates",
            order_desc=False
        )
        
        # Filter by genre if provided (service doesn't support genre filter yet)
        if genre:
            festivals = [f for f in festivals if genre in (f.genres or [])]
            total = len(festivals)
        
        # Convert to response format
        from sqlalchemy import inspect
        festival_data = []
        for festival in festivals:
            # Only access artists if the relationship is already loaded (avoid lazy load)
            artists_list = []
            insp = inspect(festival)
            if 'artists' in insp.unloaded:
                # Relationship not loaded, skip it
                artists_list = []
            else:
                # Relationship is loaded, safe to access
                try:
                    artists_list = [artist.name for artist in festival.artists]
                except:
                    artists_list = []
            
            festival_data.append({
                "id": str(festival.id),
                "name": festival.name,
                "dates": [date.isoformat() for date in festival.dates] if festival.dates else [],
                "location": festival.location,
                "venue": festival.venue,
                "genres": festival.genres or [],
                "ticket_url": festival.ticket_url,
                "artists": artists_list,
                "created_at": festival.created_at.isoformat(),
                "updated_at": festival.updated_at.isoformat(),
                # Visual branding fields
                "logo_url": festival.logo_url,
                "primary_color": festival.primary_color,
                "secondary_color": festival.secondary_color,
                "accent_colors": festival.accent_colors,
                "branding_extracted_at": festival.branding_extracted_at.isoformat() if festival.branding_extracted_at else None
            })
        
        return JSONResponse(content={
            "success": True,
            "data": {"festivals": festival_data},
            "message": "Festivals retrieved successfully",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        })
        
    except Exception as e:
        logger.error(f"Error listing festivals: {e}")
        return JSONResponse(content={
            "success": False,
            "error": "Internal server error",
            "message": str(e),
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        }, status_code=500)


@router.get("/{festival_id}", response_model=Festival)
async def get_festival(
    festival_id: UUID,
    db: AsyncSession = Depends(get_db),
    festival_service: FestivalService = Depends(get_festival_service)
):
    """Get a specific festival by ID."""
    # Get festival via service
    festival = await festival_service.get_festival_by_id(festival_id, load_relationships=True)
    
    if not festival:
        raise HTTPException(status_code=404, detail="Festival not found")
    
    return Festival(
        id=festival.id,
        name=festival.name,
        dates=festival.dates,
        location=festival.location,
        venue=festival.venue,
        genres=festival.genres or [],
        ticket_url=festival.ticket_url,
        artists=[artist.name for artist in festival.artists] if hasattr(festival, 'artists') else [],
        created_at=festival.created_at,
        updated_at=festival.updated_at,
        # Visual branding fields
        logo_url=festival.logo_url,
        primary_color=festival.primary_color,
        secondary_color=festival.secondary_color,
        accent_colors=festival.accent_colors,
        branding_extracted_at=festival.branding_extracted_at
    )


@router.put("/{festival_id}", response_model=Festival)
async def update_festival(
    festival_id: UUID,
    festival_update: FestivalUpdate,
    db: AsyncSession = Depends(get_db),
    festival_service: FestivalService = Depends(get_festival_service)
):
    """Update a festival."""
    from festival_playlist_generator.core.caching import invalidate_festival_poster_cache
    from sqlalchemy import inspect
    
    # Get existing festival
    festival = await festival_service.get_festival_by_id(festival_id, load_relationships=True)
    
    if not festival:
        raise HTTPException(status_code=404, detail="Festival not found")
    
    # Update fields if provided
    update_data = festival_update.model_dump(exclude_unset=True)
    
    # Handle artists separately
    artist_ids = None
    if "artists" in update_data:
        artist_names = update_data.pop("artists")
        # Convert artist names to IDs
        artist_ids = []
        for artist_name in artist_names:
            result = await db.execute(select(ArtistModel).where(ArtistModel.name == artist_name))
            artist = result.scalar_one_or_none()
            if not artist:
                artist = ArtistModel(name=artist_name)
                db.add(artist)
                await db.flush()
            artist_ids.append(artist.id)
    
    # Update other fields
    for field, value in update_data.items():
        setattr(festival, field, value)
    
    # Update via service
    updated_festival = await festival_service.update_festival(festival, artist_ids=artist_ids)
    
    # Invalidate poster cache after update
    await invalidate_festival_poster_cache(str(festival_id))
    
    # Only access artists if the relationship is already loaded
    artists_list = []
    insp = inspect(updated_festival)
    if 'artists' not in insp.unloaded:
        try:
            artists_list = [artist.name for artist in updated_festival.artists]
        except:
            artists_list = []
    
    return Festival(
        id=updated_festival.id,
        name=updated_festival.name,
        dates=updated_festival.dates,
        location=updated_festival.location,
        venue=updated_festival.venue,
        genres=updated_festival.genres or [],
        ticket_url=updated_festival.ticket_url,
        artists=artists_list,
        created_at=updated_festival.created_at,
        updated_at=updated_festival.updated_at,
        # Visual branding fields
        logo_url=updated_festival.logo_url,
        primary_color=updated_festival.primary_color,
        secondary_color=updated_festival.secondary_color,
        accent_colors=updated_festival.accent_colors,
        branding_extracted_at=updated_festival.branding_extracted_at
    )


@router.delete("/{festival_id}", status_code=204)
async def delete_festival(
    festival_id: UUID,
    db: AsyncSession = Depends(get_db),
    festival_service: FestivalService = Depends(get_festival_service)
):
    """Delete a festival."""
    # Delete via service
    deleted = await festival_service.delete_festival(festival_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Festival not found")


@router.get("/search/", response_model=List[Festival])
async def search_festivals(
    q: str = Query(..., min_length=1, description="Search query"),
    skip: int = Query(0, ge=0, description="Number of festivals to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of festivals to return"),
    db: AsyncSession = Depends(get_db),
    festival_service: FestivalService = Depends(get_festival_service)
):
    """Search festivals by name, location, or artist."""
    from sqlalchemy import inspect
    
    # Calculate page from skip/limit
    page = (skip // limit) + 1
    per_page = limit
    
    # Search via service
    festivals, total = await festival_service.search_festivals(
        search=q,
        page=page,
        per_page=per_page,
        order_by="dates",
        order_desc=False
    )
    
    result = []
    for festival in festivals:
        # Only access artists if the relationship is already loaded
        artists_list = []
        insp = inspect(festival)
        if 'artists' not in insp.unloaded:
            try:
                artists_list = [artist.name for artist in festival.artists]
            except:
                artists_list = []
        
        result.append(Festival(
            id=festival.id,
            name=festival.name,
            dates=festival.dates,
            location=festival.location,
            venue=festival.venue,
            genres=festival.genres or [],
            ticket_url=festival.ticket_url,
            artists=artists_list,
            created_at=festival.created_at,
            updated_at=festival.updated_at
        ))
    
    return result