"""Authentication and session management service."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from festival_playlist_generator.core.redis import cache
from festival_playlist_generator.models.user import User
from festival_playlist_generator.schemas.user import User as UserSchema
from festival_playlist_generator.schemas.user import UserCreate

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and session management service."""

    SESSION_EXPIRE_HOURS = 24 * 7  # 7 days

    def __init__(self):
        self.cache = cache

    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256 with salt."""
        salt = secrets.token_hex(32)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{password_hash}"

    def _verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        try:
            salt, password_hash = hashed_password.split(":")
            return (
                hashlib.sha256((password + salt).encode()).hexdigest() == password_hash
            )
        except ValueError:
            return False

    async def register_user(
        self, db: Session, user_data: UserCreate, password: str
    ) -> UserSchema:
        """Register a new user."""
        # Check if user already exists
        result = await db.execute(select(User).where(User.email == user_data.email))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        # Create new user
        hashed_password = self._hash_password(password)
        db_user = User(
            email=user_data.email,
            preferences=user_data.preferences,
            connected_platforms=user_data.connected_platforms,
            festival_history=[],
        )

        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

        # Store password hash in cache (in production, use proper user table with password field)
        # Use a very long TTL instead of 0 (Redis doesn't accept 0)
        await self.cache.set(
            f"user_password:{db_user.id}", hashed_password, expire=31536000
        )  # 1 year

        logger.info(f"User registered: {db_user.email}")
        return UserSchema.model_validate(db_user)

    async def authenticate_user(
        self, db: Session, email: str, password: str
    ) -> Optional[UserSchema]:
        """Authenticate user with email and password."""
        # Get user from database
        result = await db.execute(select(User).where(User.email == email))
        db_user = result.scalar_one_or_none()

        if not db_user:
            return None

        # Get password hash from cache
        hashed_password = await self.cache.get(f"user_password:{db_user.id}")
        if not hashed_password or not self._verify_password(password, hashed_password):
            return None

        logger.info(f"User authenticated: {email}")
        return UserSchema.model_validate(db_user)

    async def create_session(self, user_id: UUID) -> str:
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

        return session_data

    async def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        result = await self.cache.delete(f"session:{session_id}")
        logger.info(f"Session deleted: {session_id}")
        return result

    async def get_current_user(
        self, db: Session, session_id: str
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


# Global auth service instance
auth_service = AuthService()
