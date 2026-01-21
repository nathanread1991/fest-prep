"""Data export and deletion service for user privacy compliance."""

import csv
import io
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.models.audit_log import AuditLog
from festival_playlist_generator.models.playlist import Playlist
from festival_playlist_generator.models.user import User, UserSongPreference
from festival_playlist_generator.schemas.user import User as UserSchema

logger = logging.getLogger(__name__)


class DataExportService:
    """Service for handling user data export and deletion requests."""

    DATA_RETENTION_DAYS = 2555  # 7 years for audit logs

    async def export_user_data(
        self,
        db: AsyncSession,
        user_id: UUID,
        format: str = "json",
        requester_ip: str = None,
    ) -> Dict[str, Any]:
        """Export all user data in the specified format."""
        try:
            # Log the data export request
            await self._log_audit_event(
                db,
                user_id,
                "DATA_EXPORT_REQUESTED",
                details={"format": format, "ip_address": requester_ip},
            )

            # Get user data
            user_data = await self._get_user_data(db, user_id)
            if not user_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )

            # Get related data
            playlists_data = await self._get_user_playlists(db, user_id)
            preferences_data = await self._get_user_song_preferences(db, user_id)
            audit_data = await self._get_user_audit_logs(db, user_id)

            # Compile complete export
            export_data = {
                "export_metadata": {
                    "user_id": str(user_id),
                    "export_date": datetime.utcnow().isoformat(),
                    "format": format,
                    "data_types": ["profile", "playlists", "preferences", "audit_logs"],
                },
                "user_profile": user_data,
                "playlists": playlists_data,
                "song_preferences": preferences_data,
                "audit_logs": audit_data,
            }

            # Log successful export
            await self._log_audit_event(
                db,
                user_id,
                "DATA_EXPORT_COMPLETED",
                details={
                    "format": format,
                    "record_count": len(playlists_data) + len(preferences_data),
                },
            )

            if format.lower() == "csv":
                return self._convert_to_csv_format(export_data)
            elif format.lower() == "xml":
                return self._convert_to_xml_format(export_data)
            else:
                return export_data

        except Exception as e:
            await self._log_audit_event(
                db,
                user_id,
                "DATA_EXPORT_FAILED",
                details={"error": str(e), "format": format},
            )
            logger.error(f"Data export failed for user {user_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Data export failed",
            )

    async def delete_user_account(
        self, db: AsyncSession, user_id: UUID, requester_ip: str = None
    ) -> Dict[str, Any]:
        """Completely delete user account and all associated data."""
        try:
            # Log the deletion request
            await self._log_audit_event(
                db,
                user_id,
                "ACCOUNT_DELETION_REQUESTED",
                details={"ip_address": requester_ip},
            )

            # Verify user exists
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )

            deletion_summary = {
                "user_id": str(user_id),
                "deletion_date": datetime.utcnow().isoformat(),
                "deleted_records": {},
            }

            # Delete user song preferences
            preferences_result = await db.execute(
                delete(UserSongPreference).where(UserSongPreference.user_id == user_id)
            )
            deletion_summary["deleted_records"][
                "song_preferences"
            ] = preferences_result.rowcount

            # Delete user playlists
            playlists_result = await db.execute(
                delete(Playlist).where(Playlist.user_id == user_id)
            )
            deletion_summary["deleted_records"]["playlists"] = playlists_result.rowcount

            # Delete the user record
            user_result = await db.execute(delete(User).where(User.id == user_id))
            deletion_summary["deleted_records"]["user_profile"] = user_result.rowcount

            # Log successful deletion (before committing to ensure it's recorded)
            await self._log_audit_event(
                db, user_id, "ACCOUNT_DELETION_COMPLETED", details=deletion_summary
            )

            # Commit all deletions
            await db.commit()

            logger.info(f"User account {user_id} successfully deleted")
            return deletion_summary

        except Exception as e:
            await db.rollback()
            await self._log_audit_event(
                db, user_id, "ACCOUNT_DELETION_FAILED", details={"error": str(e)}
            )
            logger.error(f"Account deletion failed for user {user_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Account deletion failed",
            )

    async def cleanup_old_audit_logs(self, db: AsyncSession) -> Dict[str, int]:
        """Clean up audit logs older than retention period."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.DATA_RETENTION_DAYS)

            # Delete old audit logs
            result = await db.execute(
                delete(AuditLog).where(AuditLog.created_at < cutoff_date)
            )

            deleted_count = result.rowcount
            await db.commit()

            # Log the cleanup operation
            await self._log_audit_event(
                db,
                None,
                "AUDIT_LOG_CLEANUP",
                details={
                    "deleted_count": deleted_count,
                    "cutoff_date": cutoff_date.isoformat(),
                },
            )

            logger.info(f"Cleaned up {deleted_count} old audit log entries")
            return {"deleted_audit_logs": deleted_count}

        except Exception as e:
            await db.rollback()
            logger.error(f"Audit log cleanup failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Audit log cleanup failed",
            )

    async def _get_user_data(
        self, db: AsyncSession, user_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get user profile data."""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return None

        return {
            "id": str(user.id),
            "email": user.email,
            "oauth_provider": user.oauth_provider,
            "oauth_provider_id": user.oauth_provider_id,
            "display_name": user.display_name,
            "profile_picture_url": user.profile_picture_url,
            "marketing_opt_in": user.marketing_opt_in,
            "preferences": user.preferences,
            "connected_platforms": user.connected_platforms,
            "festival_history": [str(fid) for fid in (user.festival_history or [])],
            "known_songs": user.known_songs,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }

    async def _get_user_playlists(
        self, db: AsyncSession, user_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get user's playlists."""
        result = await db.execute(select(Playlist).where(Playlist.user_id == user_id))
        playlists = result.scalars().all()

        return [
            {
                "id": str(playlist.id),
                "name": playlist.name,
                "description": playlist.description,
                "festival_id": (
                    str(playlist.festival_id) if playlist.festival_id else None
                ),
                "artist_id": str(playlist.artist_id) if playlist.artist_id else None,
                "platform": playlist.platform.value if playlist.platform else None,
                "external_id": playlist.external_id,
                "created_at": (
                    playlist.created_at.isoformat() if playlist.created_at else None
                ),
                "updated_at": (
                    playlist.updated_at.isoformat() if playlist.updated_at else None
                ),
            }
            for playlist in playlists
        ]

    async def _get_user_song_preferences(
        self, db: AsyncSession, user_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get user's song preferences."""
        result = await db.execute(
            select(UserSongPreference).where(UserSongPreference.user_id == user_id)
        )
        preferences = result.scalars().all()

        return [
            {
                "id": str(pref.id),
                "song_id": str(pref.song_id),
                "is_known": pref.is_known,
                "created_at": pref.created_at.isoformat() if pref.created_at else None,
            }
            for pref in preferences
        ]

    async def _get_user_audit_logs(
        self, db: AsyncSession, user_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get user's audit logs."""
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
        )
        logs = result.scalars().all()

        return [
            {
                "id": str(log.id),
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]

    async def _log_audit_event(
        self,
        db: AsyncSession,
        user_id: Optional[UUID],
        action: str,
        resource_type: str = None,
        resource_id: str = None,
        details: Dict[str, Any] = None,
    ):
        """Log an audit event."""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            created_at=datetime.utcnow(),
        )

        db.add(audit_log)
        await db.commit()

    def _convert_to_csv_format(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Convert JSON data to CSV format."""
        csv_files = {}

        # User profile CSV
        if data.get("user_profile"):
            profile_output = io.StringIO()
            profile_writer = csv.DictWriter(
                profile_output, fieldnames=data["user_profile"].keys()
            )
            profile_writer.writeheader()
            profile_writer.writerow(data["user_profile"])
            csv_files["user_profile.csv"] = profile_output.getvalue()

        # Playlists CSV
        playlists_output = io.StringIO()
        if data.get("playlists") and len(data["playlists"]) > 0:
            playlists_writer = csv.DictWriter(
                playlists_output, fieldnames=data["playlists"][0].keys()
            )
            playlists_writer.writeheader()
            playlists_writer.writerows(data["playlists"])
        else:
            # Create empty CSV with headers
            playlists_writer = csv.DictWriter(
                playlists_output,
                fieldnames=[
                    "id",
                    "name",
                    "description",
                    "festival_id",
                    "artist_id",
                    "platform",
                    "external_id",
                    "created_at",
                    "updated_at",
                ],
            )
            playlists_writer.writeheader()
        csv_files["playlists.csv"] = playlists_output.getvalue()

        # Song preferences CSV
        prefs_output = io.StringIO()
        if data.get("song_preferences") and len(data["song_preferences"]) > 0:
            prefs_writer = csv.DictWriter(
                prefs_output, fieldnames=data["song_preferences"][0].keys()
            )
            prefs_writer.writeheader()
            prefs_writer.writerows(data["song_preferences"])
        else:
            # Create empty CSV with headers
            prefs_writer = csv.DictWriter(
                prefs_output, fieldnames=["id", "song_id", "is_known", "created_at"]
            )
            prefs_writer.writeheader()
        csv_files["song_preferences.csv"] = prefs_output.getvalue()

        # Audit logs CSV
        audit_output = io.StringIO()
        if data.get("audit_logs") and len(data["audit_logs"]) > 0:
            audit_writer = csv.DictWriter(
                audit_output, fieldnames=data["audit_logs"][0].keys()
            )
            audit_writer.writeheader()
            audit_writer.writerows(data["audit_logs"])
        else:
            # Create empty CSV with headers
            audit_writer = csv.DictWriter(
                audit_output,
                fieldnames=[
                    "id",
                    "action",
                    "resource_type",
                    "resource_id",
                    "ip_address",
                    "user_agent",
                    "details",
                    "created_at",
                ],
            )
            audit_writer.writeheader()
        csv_files["audit_logs.csv"] = audit_output.getvalue()

        return csv_files

    def _convert_to_xml_format(self, data: Dict[str, Any]) -> str:
        """Convert JSON data to XML format."""

        def dict_to_xml(d, root_name="root"):
            xml_str = f"<{root_name}>\n"
            for key, value in d.items():
                if isinstance(value, dict):
                    xml_str += f"  <{key}>\n"
                    for sub_key, sub_value in value.items():
                        xml_str += f"    <{sub_key}>{sub_value}</{sub_key}>\n"
                    xml_str += f"  </{key}>\n"
                elif isinstance(value, list):
                    xml_str += f"  <{key}>\n"
                    for item in value:
                        if isinstance(item, dict):
                            xml_str += "    <item>\n"
                            for sub_key, sub_value in item.items():
                                xml_str += f"      <{sub_key}>{sub_value}</{sub_key}>\n"
                            xml_str += "    </item>\n"
                        else:
                            xml_str += f"    <item>{item}</item>\n"
                    xml_str += f"  </{key}>\n"
                else:
                    xml_str += f"  <{key}>{value}</{key}>\n"
            xml_str += f"</{root_name}>\n"
            return xml_str

        return dict_to_xml(data, "user_data_export")


# Global service instance
data_export_service = DataExportService()
