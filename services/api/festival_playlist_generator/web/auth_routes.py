"""OAuth authentication routes."""

import logging
import os
from datetime import datetime
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.schemas.user import User as UserSchema
from festival_playlist_generator.services.oauth_service import oauth_service
from festival_playlist_generator.web.utils import get_asset_url, get_css_url, get_js_url

logger = logging.getLogger(__name__)

# Create router
auth_router = APIRouter(prefix="/auth", tags=["authentication"])

# Set up templates
templates = Jinja2Templates(directory="festival_playlist_generator/web/templates")
templates.env.globals.update(
    {"asset_url": get_asset_url, "css_url": get_css_url, "js_url": get_js_url}
)


@auth_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    """Login page with OAuth provider selection."""
    available_providers = oauth_service.get_available_providers()
    return_url = request.query_params.get("return_url", "/")

    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "providers": available_providers,
            "return_url": return_url,
        },
    )


@auth_router.post("/login/{provider}")
async def initiate_oauth(provider: str) -> Response:
    """Initiate OAuth flow for specified provider."""
    try:
        oauth_data = await oauth_service.initiate_oauth_flow(provider)
        return RedirectResponse(url=oauth_data["authorization_url"], status_code=302)
    except HTTPException as e:
        logger.error(f"OAuth initiation failed for {provider}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error initiating OAuth for {provider}: {e}")
        raise HTTPException(status_code=500, detail="Authentication service error")


@auth_router.get("/callback")
async def oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Handle OAuth callback from providers."""
    if error:
        logger.warning(f"OAuth callback error: {error}")
        return RedirectResponse(url="/auth/login?error=oauth_denied", status_code=302)

    if not code or not state:
        logger.warning("OAuth callback missing code or state parameter")
        return RedirectResponse(
            url="/auth/login?error=invalid_callback", status_code=302
        )

    try:
        # Handle OAuth callback
        auth_result = await oauth_service.handle_oauth_callback(db, code, state)

        # Check if this is a new user who needs to complete privacy consent
        if auth_result.get("is_new_user", False):
            consent_token = auth_result["consent_token"]
            user_id = auth_result["user"].id

            return RedirectResponse(
                url=f"/auth/privacy-consent?user_id={user_id}&session_token={consent_token}",
                status_code=302,
            )

        # For existing users, create response with session cookie
        return_url = request.query_params.get("return_url", "/")
        response = RedirectResponse(url=return_url, status_code=302)

        # Use secure cookies only in production (HTTPS)
        is_production = os.getenv("ENVIRONMENT", "development") == "production"

        response.set_cookie(
            key="session_id",
            value=auth_result["session_id"],
            httponly=True,
            secure=is_production,  # Only use secure flag in production with HTTPS
            samesite="lax",
            max_age=24 * 3600,  # 24 hours
        )

        logger.info(
            f"OAuth authentication successful for user: {auth_result['user'].email}"
        )
        return response

    except HTTPException as e:
        logger.error(f"OAuth callback failed: {e.detail}")
        return RedirectResponse(url=f"/auth/login?error=auth_failed", status_code=302)
    except Exception as e:
        logger.error(f"Unexpected error in OAuth callback: {e}")
        return RedirectResponse(url="/auth/login?error=server_error", status_code=302)


@auth_router.post("/callback")
async def oauth_callback_post(
    request: Request,
    code: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    error: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Handle OAuth callback via POST (for Apple Sign In)."""
    return await oauth_callback(request, code, state, error, db)


@auth_router.post("/logout")
async def logout(request: Request) -> Response:
    """Logout user and clear session."""
    session_id = request.cookies.get("session_id")

    if session_id:
        await oauth_service.delete_session(session_id)
        logger.info(f"Session deleted: {session_id}")

    # Check if this is a JSON request (from fetch) or form submission
    content_type = request.headers.get("content-type", "")
    is_json_request = "application/json" in content_type

    # Delete cookie with same parameters as when it was set
    is_production = os.getenv("ENVIRONMENT", "development") == "production"

    if is_json_request:
        # For JSON requests (fetch), return JSON response with cookie deletion
        from fastapi.responses import JSONResponse

        json_response = JSONResponse(
            {"success": True, "message": "Logged out successfully"}
        )
        json_response.delete_cookie(
            key="session_id",
            path="/",
            domain=None,
            secure=is_production,
            httponly=True,
            samesite="lax",
        )
        logger.info("User logged out (JSON)")
        return json_response
    else:
        # For form submissions, redirect to home
        redirect_response = RedirectResponse(url="/", status_code=302)
        redirect_response.delete_cookie(
            key="session_id",
            path="/",
            domain=None,
            secure=is_production,
            httponly=True,
            samesite="lax",
        )
        logger.info("User logged out (redirect)")
        return redirect_response


@auth_router.get("/logout")
async def logout_get(request: Request) -> Response:
    """Logout user via GET request (for manual clearing)."""
    session_id = request.cookies.get("session_id")

    if session_id:
        await oauth_service.delete_session(session_id)

    response = RedirectResponse(url="/", status_code=302)

    # Delete cookie with same parameters as when it was set
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.delete_cookie(
        key="session_id",
        path="/",
        domain=None,
        secure=is_production,
        httponly=True,
        samesite="lax",
    )

    logger.info("User logged out via GET")
    return response


@auth_router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    """User profile page (requires authentication)."""
    session_id = request.cookies.get("session_id")

    if not session_id:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = await oauth_service.get_current_user(db, session_id)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    return templates.TemplateResponse(
        "auth/profile.html", {"request": request, "user": user}
    )


@auth_router.get("/settings", response_class=HTMLResponse)
async def account_settings_page(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    """Account settings page (requires authentication)."""
    session_id = request.cookies.get("session_id")

    if not session_id:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = await oauth_service.get_current_user(db, session_id)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    return templates.TemplateResponse(
        "auth/account_settings.html", {"request": request, "user": user}
    )


@auth_router.post("/profile")
async def update_profile(
    request: Request, display_name: str = Form(...), db: AsyncSession = Depends(get_db)
) -> Response:
    """Update user profile information."""
    session_id = request.cookies.get("session_id")

    if not session_id:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = await oauth_service.get_current_user(db, session_id)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    # Update user display name in database
    from sqlalchemy import update

    from festival_playlist_generator.models.user import User

    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(display_name=display_name.strip() if display_name else None)
    )
    await db.commit()

    logger.info(f"Profile updated for user: {user.email}")
    return RedirectResponse(url="/auth/profile?updated=profile", status_code=302)


@auth_router.get("/privacy-consent", response_class=HTMLResponse)
async def privacy_consent_page(
    request: Request, user_id: Optional[str] = None, session_token: Optional[str] = None
) -> Response:
    """Privacy consent page for new users."""
    if not user_id or not session_token:
        return RedirectResponse(url="/auth/login", status_code=302)

    # Verify session token (basic validation)
    # In production, this should be more secure
    return templates.TemplateResponse(
        "auth/privacy_consent.html",
        {"request": request, "user_id": user_id, "session_token": session_token},
    )


@auth_router.post("/privacy-consent")
async def handle_privacy_consent(
    request: Request,
    user_id: str = Form(...),
    session_token: str = Form(...),
    marketing_opt_in: bool = Form(False),
    analytics_opt_in: bool = Form(True),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Handle privacy consent form submission."""
    try:
        from uuid import UUID

        from sqlalchemy import select, update

        from festival_playlist_generator.models.user import User

        # Get user from database
        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user preferences
        await db.execute(
            update(User)
            .where(User.id == UUID(user_id))
            .values(
                marketing_opt_in=marketing_opt_in,
                preferences={
                    **(user.preferences or {}),
                    "analytics_opt_in": analytics_opt_in,
                    "privacy_consent_completed": True,
                    "privacy_consent_date": datetime.utcnow().isoformat(),
                },
            )
        )
        await db.commit()

        # Create session for the user
        session_id = await oauth_service._create_session(user.id)

        # Use secure cookies only in production (HTTPS)
        is_production = os.getenv("ENVIRONMENT", "development") == "production"

        # Create response with session cookie
        response = RedirectResponse(url="/?welcome=true", status_code=302)
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=is_production,  # Only use secure flag in production with HTTPS
            samesite="lax",
            max_age=24 * 3600,  # 24 hours
        )

        logger.info(f"Privacy consent completed for user: {user.email}")
        return response

    except Exception as e:
        logger.error(f"Privacy consent handling failed: {e}")
        return RedirectResponse(url="/auth/login?error=consent_failed", status_code=302)


@auth_router.get("/privacy-preferences", response_class=HTMLResponse)
async def privacy_preferences_page(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    """Privacy preferences management page."""
    session_id = request.cookies.get("session_id")

    if not session_id:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = await oauth_service.get_current_user(db, session_id)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    return templates.TemplateResponse(
        "auth/privacy_preferences.html", {"request": request, "user": user}
    )


@auth_router.post("/privacy-preferences")
async def update_privacy_preferences(
    request: Request,
    marketing_opt_in: bool = Form(False),
    analytics_opt_in: bool = Form(True),
    festival_notifications: bool = Form(True),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Update user privacy preferences."""
    session_id = request.cookies.get("session_id")

    if not session_id:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = await oauth_service.get_current_user(db, session_id)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    # Update user preferences in database
    from sqlalchemy import select, update

    from festival_playlist_generator.models.user import User

    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            marketing_opt_in=marketing_opt_in,
            preferences={
                **user.preferences,
                "analytics_opt_in": analytics_opt_in,
                "festival_notifications": festival_notifications,
            },
        )
    )
    await db.commit()

    logger.info(f"Privacy preferences updated for user: {user.email}")
    return RedirectResponse(url="/auth/profile?updated=privacy", status_code=302)


# Dependency to get current authenticated user
async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Optional[UserSchema]:
    """Dependency to get current authenticated user."""
    session_id = request.cookies.get("session_id")

    if not session_id:
        return None

    return await oauth_service.get_current_user(db, session_id)


# Dependency that requires authentication
async def require_auth(
    request: Request, db: AsyncSession = Depends(get_db)
) -> UserSchema:
    """Dependency that requires user to be authenticated."""
    user = await get_current_user(request, db)

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    return user


@auth_router.get("/export-data")
async def export_user_data_page(
    request: Request, user: UserSchema = Depends(require_auth)
) -> Response:
    """Display data export page."""
    return templates.TemplateResponse(
        "auth/export_data.html",
        {"request": request, "user": user, "title": "Export My Data"},
    )


@auth_router.post("/export-data")
async def export_user_data_request(
    request: Request,
    format: str = Form("json"),
    db: AsyncSession = Depends(get_db),
    user: UserSchema = Depends(require_auth),
) -> Response:
    """Handle data export request."""
    import io
    import json
    import zipfile

    from fastapi.responses import Response

    from festival_playlist_generator.services.data_export_service import (
        data_export_service,
    )

    try:
        # Get client IP for audit logging
        client_ip = request.client.host if request.client else None

        # Export user data
        export_data = await data_export_service.export_user_data(
            db, user.id, format, client_ip
        )

        if format.lower() == "json":
            return Response(
                content=json.dumps(export_data, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=user_data_export_{user.id}.json"
                },
            )
        elif format.lower() == "csv":
            # Create ZIP file with multiple CSV files
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                if isinstance(export_data, dict):
                    for filename, csv_content in export_data.items():
                        zip_file.writestr(filename, csv_content)

            zip_buffer.seek(0)
            return Response(
                content=zip_buffer.getvalue(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename=user_data_export_{user.id}.zip"
                },
            )
        elif format.lower() == "xml":
            return Response(
                content=export_data,
                media_type="application/xml",
                headers={
                    "Content-Disposition": f"attachment; filename=user_data_export_{user.id}.xml"
                },
            )
        else:
            # Default to JSON for unknown formats
            return Response(
                content=json.dumps(export_data, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=user_data_export_{user.id}.json"
                },
            )

    except Exception as e:
        logger.error(f"Data export failed for user {user.id}: {str(e)}")
        return templates.TemplateResponse(
            "auth/export_data.html",
            {
                "request": request,
                "user": user,
                "title": "Export My Data",
                "error": "Data export failed. Please try again later.",
            },
        )


@auth_router.get("/delete-account")
async def delete_account_page(
    request: Request, user: UserSchema = Depends(require_auth)
) -> Response:
    """Display account deletion confirmation page."""
    return templates.TemplateResponse(
        "auth/delete_account.html",
        {"request": request, "user": user, "title": "Delete My Account"},
    )


@auth_router.post("/delete-account")
async def delete_account_request(
    request: Request,
    confirm_deletion: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: UserSchema = Depends(require_auth),
) -> Response:
    """Handle account deletion request."""
    from festival_playlist_generator.services.data_export_service import (
        data_export_service,
    )

    if confirm_deletion.lower() != "delete my account":
        return templates.TemplateResponse(
            "auth/delete_account.html",
            {
                "request": request,
                "user": user,
                "title": "Delete My Account",
                "error": "Please type 'DELETE MY ACCOUNT' to confirm deletion.",
            },
        )

    try:
        # Get client IP for audit logging
        client_ip = request.client.host if request.client else None

        # Delete user account
        deletion_summary = await data_export_service.delete_user_account(
            db, user.id, client_ip
        )

        # Clear session cookie and redirect to home
        response = RedirectResponse(url="/?deleted=true", status_code=302)
        response.delete_cookie("session_id")

        return response

    except Exception as e:
        logger.error(f"Account deletion failed for user {user.id}: {str(e)}")
        return templates.TemplateResponse(
            "auth/delete_account.html",
            {
                "request": request,
                "user": user,
                "title": "Delete My Account",
                "error": "Account deletion failed. Please try again later.",
            },
        )
