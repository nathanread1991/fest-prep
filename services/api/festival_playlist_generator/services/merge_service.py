"""Merge Service - Consolidate duplicate artists into a single record."""

import uuid
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from festival_playlist_generator.models.artist import Artist


@dataclass
class MergeResult:
    """Result of a merge operation."""

    success: bool
    primary_artist_id: str
    primary_artist_name: str
    merged_artist_ids: List[str]
    merged_artist_names: List[str]
    festivals_transferred: int
    setlists_transferred: int
    spotify_data_source: Optional[str]
    error: Optional[str] = None


@dataclass
class MergePreview:
    """Preview of what will happen during a merge."""

    primary_artist_id: str
    primary_artist_name: str
    secondary_artist_ids: List[str]
    secondary_artist_names: List[str]
    total_festivals: int
    total_setlists: int
    spotify_data_available: bool
    spotify_data_source: Optional[str]
    warnings: List[str]


class MergeService:
    """Service for merging duplicate artists."""

    def __init__(self, db: Session) -> None:
        """
        Initialize the merge service.

        Args:
            db: Database session
        """
        self.db = db

    def preview_merge(self, primary_id: str, secondary_ids: List[str]) -> MergePreview:
        """
        Preview what will happen during a merge.

        Args:
            primary_id: ID of the artist to keep (string UUID)
            secondary_ids: IDs of artists to merge into primary (string UUIDs)

        Returns:
            MergePreview with details about the merge

        Raises:
            ValueError: If artists not found or invalid IDs
        """
        # Convert string IDs to UUID objects
        primary_uuid = uuid.UUID(primary_id)
        secondary_uuids = [uuid.UUID(sid) for sid in secondary_ids]

        # Load primary artist
        primary = self.db.query(Artist).filter(Artist.id == primary_uuid).first()
        if not primary:
            raise ValueError(f"Primary artist not found: {primary_id}")

        # Load secondary artists
        secondaries = []
        for sid_uuid in secondary_uuids:
            artist = self.db.query(Artist).filter(Artist.id == sid_uuid).first()
            if not artist:
                raise ValueError(f"Secondary artist not found: {sid_uuid}")
            secondaries.append(artist)

        # Calculate totals
        total_festivals = len(primary.festivals) if primary.festivals else 0
        total_setlists = len(primary.setlists) if primary.setlists else 0

        for secondary in secondaries:
            # Count unique festivals (avoid double-counting)
            if secondary.festivals:
                for festival in secondary.festivals:
                    if festival not in (primary.festivals or []):
                        total_festivals += 1

            # Count all setlists (they'll be transferred)
            if secondary.setlists:
                total_setlists += len(secondary.setlists)

        # Determine Spotify data source
        spotify_data_available = False
        spotify_data_source = None

        if primary.spotify_id:
            spotify_data_available = True
            spotify_data_source = primary.name
        else:
            for secondary in secondaries:
                if secondary.spotify_id:
                    spotify_data_available = True
                    spotify_data_source = secondary.name
                    break

        # Generate warnings
        warnings = []

        if not spotify_data_available:
            warnings.append("No Spotify data available in any artist")

        if total_festivals == 0:
            warnings.append("No festivals associated with any artist")

        if total_setlists == 0:
            warnings.append("No setlists associated with any artist")

        # Check for name conflicts
        all_names = [primary.name] + [s.name for s in secondaries]
        if len(set(all_names)) > 1:
            warnings.append(
                f"Artists have different names: {', '.join(set(all_names))}"
            )

        return MergePreview(
            primary_artist_id=str(primary.id),
            primary_artist_name=primary.name,
            secondary_artist_ids=[str(s.id) for s in secondaries],
            secondary_artist_names=[s.name for s in secondaries],
            total_festivals=total_festivals,
            total_setlists=total_setlists,
            spotify_data_available=spotify_data_available,
            spotify_data_source=spotify_data_source,
            warnings=warnings,
        )

    def merge_artists(
        self, primary_id: str, secondary_ids: List[str], performed_by: str = "system"
    ) -> MergeResult:
        """
        Merge multiple artists into primary artist.

        This operation:
        1. Transfers all festivals from secondary artists to primary
        2. Transfers all setlists from secondary artists to primary
        3. Preserves Spotify data (uses best available)
        4. Deletes secondary artists
        5. Logs the merge operation

        Args:
            primary_id: ID of the artist to keep (string UUID)
            secondary_ids: IDs of artists to merge into primary (string UUIDs)
            performed_by: Username/identifier of who performed the merge

        Returns:
            MergeResult with details about the merge

        Raises:
            ValueError: If artists not found or invalid IDs
            Exception: If merge fails (transaction will be rolled back)
        """
        try:
            # Convert string IDs to UUID objects
            primary_uuid = uuid.UUID(primary_id)
            secondary_uuids = [uuid.UUID(sid) for sid in secondary_ids]

            # Load primary artist
            primary = self.db.query(Artist).filter(Artist.id == primary_uuid).first()
            if not primary:
                raise ValueError(f"Primary artist not found: {primary_id}")

            # Load secondary artists
            secondaries = []
            for sid_uuid in secondary_uuids:
                artist = self.db.query(Artist).filter(Artist.id == sid_uuid).first()
                if not artist:
                    raise ValueError(f"Secondary artist not found: {sid_uuid}")
                secondaries.append(artist)

            # Flush to ensure all objects are in session
            self.db.flush()

            # Track statistics
            festivals_transferred = 0
            setlists_transferred = 0
            spotify_data_source = None

            # Store primary UUID for setlist updates
            primary_artist_uuid = primary.id

            # Merge each secondary artist
            for secondary in secondaries:
                # Transfer festivals (avoid duplicates)
                if secondary.festivals:
                    for festival in secondary.festivals:
                        if festival not in (primary.festivals or []):
                            primary.festivals.append(festival)
                            festivals_transferred += 1

                # Count setlists before transferring
                setlist_count = len(secondary.setlists) if secondary.setlists else 0

                # Transfer setlists using direct SQL UPDATE to avoid ORM issues
                if setlist_count > 0:
                    # Use raw SQL to update setlists - must cast UUIDs explicitly
                    update_query = text(
                        """
                        UPDATE setlists
                        SET artist_id = CAST(:primary_id AS uuid), updated_at = NOW()
                        WHERE artist_id = CAST(:secondary_id AS uuid)
                    """
                    )
                    self.db.execute(
                        update_query,
                        {
                            "primary_id": str(primary_artist_uuid),
                            "secondary_id": str(secondary.id),
                        },
                    )
                    setlists_transferred += setlist_count

                # Preserve Spotify data if primary doesn't have it
                if not primary.spotify_id and secondary.spotify_id:
                    primary.spotify_id = secondary.spotify_id
                    primary.spotify_image_url = secondary.spotify_image_url
                    primary.spotify_popularity = secondary.spotify_popularity
                    primary.spotify_followers = secondary.spotify_followers
                    primary.genres = secondary.genres
                    primary.logo_url = secondary.logo_url
                    primary.logo_source = secondary.logo_source
                    spotify_data_source = secondary.name

            # If primary already had Spotify data, note that
            if primary.spotify_id and not spotify_data_source:
                spotify_data_source = primary.name

            # Flush changes to ensure data is synced
            self.db.flush()

            # Log the merge operation
            self._log_merge(
                primary_id=primary.id,
                primary_name=primary.name,
                secondary_ids=[s.id for s in secondaries],
                secondary_names=[s.name for s in secondaries],
                festivals_transferred=festivals_transferred,
                setlists_transferred=setlists_transferred,
                spotify_data_source=spotify_data_source,
                performed_by=performed_by,
            )

            # Delete secondary artists using raw SQL to avoid ORM relationship issues
            for secondary in secondaries:
                # Use raw SQL DELETE to bypass ORM relationship management
                delete_query = text(
                    """
                    DELETE FROM artists WHERE id = CAST(:artist_id AS uuid)
                """
                )
                self.db.execute(delete_query, {"artist_id": str(secondary.id)})

                # Expunge from session to prevent ORM from trying to manage it
                self.db.expunge(secondary)

            # Commit transaction
            self.db.commit()

            return MergeResult(
                success=True,
                primary_artist_id=str(primary.id),
                primary_artist_name=primary.name,
                merged_artist_ids=[str(s.id) for s in secondaries],
                merged_artist_names=[s.name for s in secondaries],
                festivals_transferred=festivals_transferred,
                setlists_transferred=setlists_transferred,
                spotify_data_source=spotify_data_source,
            )

        except Exception as e:
            # Rollback on error
            self.db.rollback()

            return MergeResult(
                success=False,
                primary_artist_id=primary_id,
                primary_artist_name="",
                merged_artist_ids=secondary_ids,
                merged_artist_names=[],
                festivals_transferred=0,
                setlists_transferred=0,
                spotify_data_source=None,
                error=str(e),
            )

    def _log_merge(
        self,
        primary_id: uuid.UUID,
        primary_name: str,
        secondary_ids: List[uuid.UUID],
        secondary_names: List[str],
        festivals_transferred: int,
        setlists_transferred: int,
        spotify_data_source: Optional[str],
        performed_by: str,
    ) -> None:
        """
        Log merge operation to merge_audit_log table.

        Args:
            primary_id: ID of primary artist
            primary_name: Name of primary artist
            secondary_ids: IDs of merged artists
            secondary_names: Names of merged artists
            festivals_transferred: Number of festivals transferred
            setlists_transferred: Number of setlists transferred
            spotify_data_source: Source of Spotify data
            performed_by: Who performed the merge
        """
        # Insert into merge_audit_log using raw SQL
        # (We don't have a model for this table yet)
        query = text(
            """
            INSERT INTO merge_audit_log (
                primary_artist_id,
                primary_artist_name,
                merged_artist_ids,
                merged_artist_names,
                festivals_transferred,
                setlists_transferred,
                spotify_data_source,
                performed_by
            ) VALUES (
                CAST(:primary_id AS uuid),
                :primary_name,
                CAST(:merged_ids AS uuid[]),
                CAST(:merged_names AS text[]),
                :festivals,
                :setlists,
                :spotify_source,
                :performed_by
            )
        """
        )

        # Convert UUID objects to strings for the array cast
        merged_ids_str = "{" + ",".join([str(sid) for sid in secondary_ids]) + "}"
        merged_names_str = (
            "{"
            + ",".join(
                ['"' + name.replace('"', '\\"') + '"' for name in secondary_names]
            )
            + "}"
        )

        self.db.execute(
            query,
            {
                "primary_id": str(primary_id),
                "primary_name": primary_name,
                "merged_ids": merged_ids_str,
                "merged_names": merged_names_str,
                "festivals": festivals_transferred,
                "setlists": setlists_transferred,
                "spotify_source": spotify_data_source,
                "performed_by": performed_by,
            },
        )


# Factory function for creating service instances
def create_merge_service(db: Session) -> MergeService:
    """
    Create a merge service instance.

    Args:
        db: Database session

    Returns:
        MergeService instance
    """
    return MergeService(db)
