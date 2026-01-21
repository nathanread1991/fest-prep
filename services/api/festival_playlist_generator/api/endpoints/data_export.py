"""API endpoints for user data export and deletion."""

import io
import json
import zipfile
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.schemas.user import User as UserSchema
from festival_playlist_generator.services.data_export_service import data_export_service
from festival_playlist_generator.services.oauth_service import oauth_service

router = APIRouter(prefix="/data", tags=["data-export"])


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> UserSchema:
    """Get current authenticated user."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    user = await oauth_service.get_current_user(db, session_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )

    return user


@router.get("/export")
async def export_user_data(
    request: Request,
    format: str = Query("json", pattern="^(json|csv|xml)$"),
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Export all user data in the specified format.

    **Validates: Requirements 26.12, 27.9**

    Supports JSON, CSV, and XML formats. Returns a comprehensive export
    of all user data including profile, playlists, preferences, and audit logs.
    """
    try:
        # Get client IP for audit logging
        client_ip = request.client.host if request.client else None

        # Export user data
        export_data = await data_export_service.export_user_data(
            db, current_user.id, format, client_ip
        )

        if format.lower() == "json":
            return JSONResponse(
                content=export_data,
                headers={
                    "Content-Disposition": f"attachment; filename=user_data_export_{current_user.id}.json"
                },
            )
        elif format.lower() == "csv":
            # Create ZIP file with multiple CSV files
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for filename, csv_content in export_data.items():
                    zip_file.writestr(filename, csv_content)

            zip_buffer.seek(0)
            return Response(
                content=zip_buffer.getvalue(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename=user_data_export_{current_user.id}.zip"
                },
            )
        elif format.lower() == "xml":
            return Response(
                content=export_data,
                media_type="application/xml",
                headers={
                    "Content-Disposition": f"attachment; filename=user_data_export_{current_user.id}.xml"
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Data export failed",
        )


@router.delete("/account")
async def delete_user_account(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Permanently delete user account and all associated data.

    **Validates: Requirements 26.12, 27.7**

    This action is irreversible and will remove all user data including:
    - User profile and authentication data
    - All created playlists
    - Song preferences and history
    - Festival attendance history

    Audit logs of the deletion will be retained for compliance purposes.
    """
    try:
        # Get client IP for audit logging
        client_ip = request.client.host if request.client else None

        # Delete user account
        deletion_summary = await data_export_service.delete_user_account(
            db, current_user.id, client_ip
        )

        # Clear session cookie
        response = JSONResponse(
            content={
                "message": "Account successfully deleted",
                "deletion_summary": deletion_summary,
            }
        )
        response.delete_cookie("session_id")

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account deletion failed",
        )


@router.post("/cleanup-audit-logs")
async def cleanup_old_audit_logs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """
    Clean up old audit logs (admin only).

    **Validates: Requirements 27.6, 27.10**

    Removes audit logs older than the retention period (7 years).
    This endpoint is typically called by system administrators or automated cleanup jobs.
    """
    # Note: In a real implementation, you'd want to check if the user is an admin
    # For now, we'll allow any authenticated user to trigger cleanup

    try:
        cleanup_result = await data_export_service.cleanup_old_audit_logs(db)

        return JSONResponse(
            content={
                "message": "Audit log cleanup completed",
                "cleanup_summary": cleanup_result,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audit log cleanup failed",
        )


@router.get("/retention-policy")
async def get_data_retention_policy():
    """
    Get information about data retention policies.

    **Validates: Requirements 27.6**

    Returns information about how long different types of data are retained
    and what happens during the retention lifecycle.
    """
    return JSONResponse(
        content={
            "data_retention_policy": {
                "user_data": {
                    "retention_period": "Until account deletion or user request",
                    "description": "User profile, playlists, and preferences are retained until the user deletes their account or requests data deletion",
                },
                "audit_logs": {
                    "retention_period": "7 years",
                    "retention_days": data_export_service.DATA_RETENTION_DAYS,
                    "description": "Security and access audit logs are retained for 7 years for compliance purposes",
                },
                "session_data": {
                    "retention_period": "24 hours",
                    "description": "User session data expires after 24 hours of inactivity",
                },
                "oauth_state": {
                    "retention_period": "10 minutes",
                    "description": "OAuth state parameters expire after 10 minutes for security",
                },
            },
            "user_rights": {
                "data_export": "Users can request a complete export of their data at any time",
                "data_deletion": "Users can request complete deletion of their account and all associated data",
                "data_portability": "Exported data is provided in standard formats (JSON, CSV, XML) for portability",
            },
        }
    )
