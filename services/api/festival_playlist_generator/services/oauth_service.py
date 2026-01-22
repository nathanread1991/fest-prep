"""OAuth authentication service for multiple providers."""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from festival_playlist_generator.core.config import settings
from festival_playlist_generator.core.redis import cache
from festival_playlist_generator.models.user import User
from festival_playlist_generator.schemas.user import User as UserSchema

logger = logging.getLogger(__name__)


class OAuthProvider:
    """Base OAuth provider configuration."""

    def __init__(
        self,
        name: str,
        client_id: str,
        client_secret: str,
        auth_url: str,
        token_url: str,
        user_info_url: str,
        scopes: List[str],
    ) -> None:
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = auth_url
        self.token_url = token_url
        self.user_info_url = user_info_url
        self.scopes = scopes


class OAuthService:
    """OAuth authentication service supporting multiple providers."""

    SESSION_EXPIRE_HOURS = 24

    def __init__(self) -> None:
        self.cache = cache
        self.providers = self._initialize_providers()

    def _initialize_providers(self) -> Dict[str, OAuthProvider]:
        """Initialize OAuth provider configurations."""
        providers = {}

        # Google OAuth
        if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
            providers["google"] = OAuthProvider(
                name="google",
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                auth_url="https://accounts.google.com/o/oauth2/v2/auth",
                token_url="https://oauth2.googleapis.com/token",
                user_info_url="https://www.googleapis.com/oauth2/v2/userinfo",
                scopes=["openid", "email", "profile"],
            )

        # Spotify OAuth (reusing existing Spotify credentials)
        if settings.SPOTIFY_CLIENT_ID and settings.SPOTIFY_CLIENT_SECRET:
            providers["spotify"] = OAuthProvider(
                name="spotify",
                client_id=settings.SPOTIFY_CLIENT_ID,
                client_secret=settings.SPOTIFY_CLIENT_SECRET,
                auth_url="https://accounts.spotify.com/authorize",
                token_url="https://accounts.spotify.com/api/token",
                user_info_url="https://api.spotify.com/v1/me",
                scopes=[
                    "user-read-email",
                    "user-read-private",
                    "playlist-modify-public",
                    "playlist-modify-private",
                ],
            )

        # YouTube OAuth (separate from YouTube API key)
        if settings.YOUTUBE_OAUTH_CLIENT_ID and settings.YOUTUBE_OAUTH_CLIENT_SECRET:
            providers["youtube"] = OAuthProvider(
                name="youtube",
                client_id=settings.YOUTUBE_OAUTH_CLIENT_ID,
                client_secret=settings.YOUTUBE_OAUTH_CLIENT_SECRET,
                auth_url="https://accounts.google.com/o/oauth2/v2/auth",
                token_url="https://oauth2.googleapis.com/token",
                user_info_url="https://www.googleapis.com/oauth2/v2/userinfo",
                scopes=[
                    "openid",
                    "email",
                    "profile",
                    "https://www.googleapis.com/auth/youtube",
                ],
            )

        # X (Twitter) OAuth
        if settings.X_CLIENT_ID and settings.X_CLIENT_SECRET:
            providers["x"] = OAuthProvider(
                name="x",
                client_id=settings.X_CLIENT_ID,
                client_secret=settings.X_CLIENT_SECRET,
                auth_url="https://twitter.com/i/oauth2/authorize",
                token_url="https://api.twitter.com/2/oauth2/token",
                user_info_url="https://api.twitter.com/2/users/me",
                scopes=["tweet.read", "users.read"],
            )

        # Apple OAuth (more complex due to JWT requirements)
        if (
            settings.APPLE_CLIENT_ID
            and settings.APPLE_CLIENT_SECRET
            and settings.APPLE_PRIVATE_KEY
            and settings.APPLE_KEY_ID
            and settings.APPLE_TEAM_ID
        ):
            providers["apple"] = OAuthProvider(
                name="apple",
                client_id=settings.APPLE_CLIENT_ID,
                client_secret=settings.APPLE_CLIENT_SECRET,
                auth_url="https://appleid.apple.com/auth/authorize",
                token_url="https://appleid.apple.com/auth/token",
                user_info_url="",  # Apple provides user info in the token response
                scopes=["name", "email"],
            )

        return providers

    def get_available_providers(self) -> List[str]:
        """Get list of configured OAuth providers."""
        return list(self.providers.keys())

    async def initiate_oauth_flow(self, provider_name: str) -> Dict[str, str]:
        """Initiate OAuth flow for a provider."""
        if provider_name not in self.providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth provider '{provider_name}' not configured",
            )

        provider = self.providers[provider_name]

        # Generate state parameter for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state in cache with expiration
        await self.cache.set(
            f"oauth_state:{state}",
            {"provider": provider_name, "created_at": datetime.utcnow().isoformat()},
            expire=600,  # 10 minutes
        )

        # Build authorization URL
        auth_params = {
            "client_id": provider.client_id,
            "redirect_uri": settings.OAUTH_REDIRECT_URI,
            "scope": " ".join(provider.scopes),
            "response_type": "code",
            "state": state,
        }

        # Add provider-specific parameters
        if provider_name == "apple":
            auth_params["response_mode"] = "form_post"
        elif provider_name == "x":
            auth_params["code_challenge"] = "challenge"  # PKCE for Twitter
            auth_params["code_challenge_method"] = "plain"

        authorization_url = f"{provider.auth_url}?{urlencode(auth_params)}"

        logger.info(f"OAuth flow initiated for provider: {provider_name}")
        return {
            "authorization_url": authorization_url,
            "state": state,
            "provider": provider_name,
        }

    async def handle_oauth_callback(
        self,
        db: AsyncSession,
        code: str,
        state: str,
        provider_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle OAuth callback and create/login user."""
        # Verify state parameter
        state_data = await self.cache.get(f"oauth_state:{state}")
        if not state_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OAuth state",
            )

        # Clean up state
        await self.cache.delete(f"oauth_state:{state}")

        provider_name = provider_name or state_data["provider"]
        if provider_name not in self.providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth provider '{provider_name}' not configured",
            )

        provider = self.providers[provider_name]

        # Exchange code for access token
        token_data = await self._exchange_code_for_token(provider, code)

        # Get user information from provider
        user_info = await self._get_user_info(provider, token_data["access_token"])

        # Create or get existing user
        user, is_new_user = await self._create_or_get_user(db, provider_name, user_info)

        # For new users, don't create session yet - redirect to privacy consent
        if is_new_user:
            # Generate a temporary token for the consent flow
            consent_token = secrets.token_urlsafe(32)
            await self.cache.set(
                f"consent_token:{consent_token}",
                {"user_id": str(user.id), "created_at": datetime.utcnow().isoformat()},
                expire=1800,  # 30 minutes
            )

            logger.info(
                f"New user OAuth authentication, redirecting to consent: {user.email}"
            )
            return {
                "user": user,
                "is_new_user": True,
                "consent_token": consent_token,
                "provider": provider_name,
                "access_token": token_data["access_token"],
            }

        # For existing users, create session normally
        session_id = await self._create_session(user.id)

        logger.info(f"OAuth authentication successful for existing user: {user.email}")
        return {
            "user": user,
            "is_new_user": False,
            "session_id": session_id,
            "provider": provider_name,
            "access_token": token_data["access_token"],
        }

    async def _exchange_code_for_token(
        self, provider: OAuthProvider, code: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        token_data = {
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.OAUTH_REDIRECT_URI,
        }

        # Handle Apple's special JWT client secret requirement
        if provider.name == "apple":
            token_data["client_secret"] = self._generate_apple_client_secret()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                provider.token_url,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                logger.error(
                    f"Token exchange failed for {provider.name}: {response.text}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange authorization code for token",
                )

            token_response: Dict[str, Any] = response.json()
            return token_response

    async def _get_user_info(
        self, provider: OAuthProvider, access_token: str
    ) -> Dict[str, Any]:
        """Get user information from OAuth provider."""
        if provider.name == "apple":
            # Apple provides user info in the token response, not a separate endpoint
            # For now, we'll decode the ID token to get user info
            return {
                "email": "apple_user@example.com",
                "name": "Apple User",
            }  # Placeholder

        headers = {"Authorization": f"Bearer {access_token}"}

        # Handle provider-specific headers
        if provider.name == "x":
            headers["User-Agent"] = "FestivalPlaylistGenerator/1.0"

        async with httpx.AsyncClient() as client:
            response = await client.get(provider.user_info_url, headers=headers)

            if response.status_code != 200:
                logger.error(
                    f"User info request failed for {provider.name}: {response.text}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get user information from provider",
                )

            user_data = response.json()

            # Normalize user data across providers
            if provider.name == "google" or provider.name == "youtube":
                return {
                    "email": user_data.get("email"),
                    "name": user_data.get("name"),
                    "picture": user_data.get("picture"),
                    "provider_id": user_data.get("id"),
                }
            elif provider.name == "spotify":
                return {
                    "email": user_data.get("email"),
                    "name": user_data.get("display_name"),
                    "picture": (
                        user_data.get("images", [{}])[0].get("url")
                        if user_data.get("images")
                        else None
                    ),
                    "provider_id": user_data.get("id"),
                }
            elif provider.name == "x":
                return {
                    # X doesn't always provide email
                    "email": f"{user_data.get('username')}@twitter.com",
                    "name": user_data.get("name"),
                    "picture": user_data.get("profile_image_url"),
                    "provider_id": user_data.get("id"),
                }

            result: Dict[str, Any] = user_data
            return result

    async def _create_or_get_user(
        self, db: AsyncSession, provider_name: str, user_info: Dict[str, Any]
    ) -> tuple[UserSchema, bool]:
        """Create new user or get existing user from OAuth provider data.

        Returns:
            tuple: (user, is_new_user)
        """
        email = user_info.get("email")
        provider_id = user_info.get("provider_id", "")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is required for registration",
            )

        # Check if user already exists
        result = await db.execute(
            select(User).where(
                (User.email == email)
                | (
                    (User.oauth_provider == provider_name)
                    & (User.oauth_provider_id == provider_id)
                )
            )
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            # Update last login
            existing_user.last_login = datetime.utcnow()
            await db.commit()
            return UserSchema.model_validate(existing_user), False

        # Create new user
        new_user = User(
            id=uuid4(),
            email=email,
            oauth_provider=provider_name,
            oauth_provider_id=provider_id,
            display_name=user_info.get("name", ""),
            profile_picture_url=user_info.get("picture", ""),
            marketing_opt_in=False,  # Default to opt-out for privacy
            preferences={
                "privacy_consent_completed": False  # New users need to complete consent
            },
            connected_platforms=[],
            known_songs=[],
            festival_history=[],
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow(),
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        logger.info(f"New user created via OAuth: {email} ({provider_name})")
        return UserSchema.model_validate(new_user), True

    async def _create_session(self, user_id: UUID) -> str:
        """Create a new session for user."""
        session_id = secrets.token_urlsafe(32)
        session_data = {
            "user_id": str(user_id),
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (
                datetime.utcnow() + timedelta(hours=self.SESSION_EXPIRE_HOURS)
            ).isoformat(),
        }

        # Store session in Redis
        await self.cache.set(
            f"session:{session_id}",
            session_data,
            expire=self.SESSION_EXPIRE_HOURS * 3600,
        )

        logger.info(f"Session created for user: {user_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        session_data = await self.cache.get(f"session:{session_id}")
        if not session_data:
            return None

        # Check if session is expired
        expires_at = datetime.fromisoformat(session_data["expires_at"])
        if datetime.utcnow() > expires_at:
            await self.delete_session(session_id)
            return None

        result: Dict[str, Any] = session_data
        return result

    async def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        result = await self.cache.delete(f"session:{session_id}")
        logger.info(f"Session deleted: {session_id}")
        return result > 0

    async def get_current_user(
        self, db: AsyncSession, session_id: str
    ) -> Optional[UserSchema]:
        """Get current user from session."""
        session_data = await self.get_session(session_id)
        if not session_data:
            return None

        user_id = UUID(session_data["user_id"])
        result = await db.execute(select(User).where(User.id == user_id))
        db_user = result.scalar_one_or_none()

        if not db_user:
            await self.delete_session(session_id)
            return None

        return UserSchema.model_validate(db_user)

    def _generate_apple_client_secret(self) -> str:
        """Generate JWT client secret for Apple OAuth."""
        # Apple requires a JWT signed with their private key
        # This would require the cryptography library and proper key handling
        # For now, return the client secret as-is
        return settings.APPLE_CLIENT_SECRET


# Global OAuth service instance
oauth_service = OAuthService()
