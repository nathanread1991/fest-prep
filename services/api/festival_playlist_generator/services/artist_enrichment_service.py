"""Artist Enrichment Service - Automatically populate artist data from Spotify."""

import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.models.artist import Artist as ArtistModel
from festival_playlist_generator.services.spotify_artist_service import (
    spotify_artist_service,
)

logger = logging.getLogger(__name__)


class ArtistEnrichmentService:
    """Service for enriching artist records with Spotify data."""

    async def enrich_artists(self, artist_ids: List[str], db: AsyncSession) -> dict:
        """
        Enrich multiple artists with Spotify data.

        Args:
            artist_ids: List of artist UUIDs to enrich
            db: Database session

        Returns:
            Dictionary with enrichment statistics
        """
        enriched_count = 0
        skipped_count = 0
        failed_count = 0

        for artist_id in artist_ids:
            try:
                # Get artist from database
                result = await db.execute(
                    select(ArtistModel).filter(ArtistModel.id == artist_id)
                )
                artist = result.scalar_one_or_none()

                if not artist:
                    logger.warning(f"Artist {artist_id} not found")
                    failed_count += 1
                    continue

                # Skip if already enriched
                if artist.spotify_id:
                    logger.info(
                        f"Artist {artist.name} already has Spotify data, skipping"
                    )
                    skipped_count += 1
                    continue

                # Fetch Spotify data
                spotify_info = spotify_artist_service.search_artist(artist.name)

                if spotify_info:
                    # Check if this Spotify ID is already used by another artist
                    existing_spotify_result = await db.execute(
                        select(ArtistModel).filter(
                            ArtistModel.spotify_id == spotify_info.id
                        )
                    )
                    existing_spotify_artist = (
                        existing_spotify_result.scalar_one_or_none()
                    )

                    if (
                        existing_spotify_artist
                        and existing_spotify_artist.id != artist.id
                    ):
                        # This Spotify ID is already used by another artist
                        logger.warning(
                            f"Spotify ID {spotify_info.id} for '{artist.name}' is already used by '{existing_spotify_artist.name}'. "
                            f"These may be the same artist with different names. Skipping enrichment."
                        )
                        skipped_count += 1
                    else:
                        # Update artist with Spotify data
                        artist.spotify_id = spotify_info.id
                        artist.spotify_image_url = spotify_info.image_url
                        artist.spotify_popularity = float(spotify_info.popularity)
                        artist.spotify_followers = float(spotify_info.followers)
                        artist.genres = spotify_info.genres

                        enriched_count += 1
                        logger.info(f"Enriched artist {artist.name} with Spotify data")
                else:
                    logger.warning(f"No Spotify data found for artist {artist.name}")
                    failed_count += 1

            except Exception as e:
                logger.error(f"Error enriching artist {artist_id}: {e}")
                failed_count += 1
                continue

        # Commit all changes at once
        try:
            await db.commit()
            logger.info(
                f"Artist enrichment complete: {enriched_count} enriched, {skipped_count} skipped, {failed_count} failed"
            )
        except Exception as e:
            logger.error(f"Error committing artist enrichment: {e}")
            await db.rollback()
            raise

        return {
            "enriched": enriched_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "total": len(artist_ids),
        }

    async def enrich_artist_by_name(
        self, artist_name: str, db: AsyncSession
    ) -> Optional[ArtistModel]:
        """
        Enrich a single artist by name with Spotify data.

        Args:
            artist_name: Name of the artist
            db: Database session

        Returns:
            Updated artist model or None if not found
        """
        try:
            # Get artist from database
            result = await db.execute(
                select(ArtistModel).filter(ArtistModel.name == artist_name)
            )
            artist = result.scalar_one_or_none()

            if not artist:
                logger.warning(f"Artist {artist_name} not found in database")
                return None

            # Skip if already enriched
            if artist.spotify_id:
                logger.info(f"Artist {artist.name} already has Spotify data")
                return artist

            # Fetch Spotify data
            spotify_info = spotify_artist_service.search_artist(artist.name)

            if spotify_info:
                # Check if this Spotify ID is already used by another artist
                existing_spotify_result = await db.execute(
                    select(ArtistModel).filter(
                        ArtistModel.spotify_id == spotify_info.id
                    )
                )
                existing_spotify_artist = existing_spotify_result.scalar_one_or_none()

                if existing_spotify_artist and existing_spotify_artist.id != artist.id:
                    # This Spotify ID is already used by another artist
                    logger.warning(
                        f"Spotify ID {spotify_info.id} for '{artist.name}' is already used by '{existing_spotify_artist.name}'. "
                        f"These may be the same artist with different names."
                    )
                    return artist

                # Update artist with Spotify data
                artist.spotify_id = spotify_info.id
                artist.spotify_image_url = spotify_info.image_url
                artist.spotify_popularity = float(spotify_info.popularity)
                artist.spotify_followers = float(spotify_info.followers)
                artist.genres = spotify_info.genres

                await db.commit()
                logger.info(f"Enriched artist {artist.name} with Spotify data")
                return artist
            else:
                logger.warning(f"No Spotify data found for artist {artist.name}")
                return artist

        except Exception as e:
            logger.error(f"Error enriching artist {artist_name}: {e}")
            await db.rollback()
            return None


# Global instance
artist_enrichment_service = ArtistEnrichmentService()
