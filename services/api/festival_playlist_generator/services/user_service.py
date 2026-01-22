"""User service for business logic with authentication."""

import logging
from typing import Any, Callable, Optional
from uuid import UUID

from festival_playlist_generator.models.user import User
from festival_playlist_generator.repositories.user_repository import UserRepository
from festival_playlist_generator.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class UserService:
    """
    Service layer for user business logic.

    Handles user operations with:
    - Caching strategy
    - Authentication support
    - JWT token management

    Requirements: US-4.2, US-4.6
    """

    def __init__(self, user_repository: UserRepository, cache_service: CacheService) -> None:
        """
        Initialize user service.

        Args:
            user_repository: Repository for user data access
            cache_service: Service for caching operations
        """
        self.user_repo = user_repository
        self.cache = cache_service

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Get user by ID with caching.

        Args:
            user_id: User UUID

        Returns:
            User or None if not found
        """
        # Generate cache key
        cache_key = f"user:{user_id}"

        # Check cache first
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for user {user_id}")
            return User(**cached) if isinstance(cached, dict) else cached

        # Fetch from database
        user = await self.user_repo.get_by_id(user_id)

        # Cache result (1 hour TTL)
        if user:
            await self.cache.set(cache_key, user, ttl=3600)
            logger.debug(f"Cached user {user_id}")

        return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: User email address

        Returns:
            User or None if not found
        """
        # Check cache
        cache_key = f"user:email:{email}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for user email {email}")
            return User(**cached) if isinstance(cached, dict) else cached

        # Fetch from database
        user = await self.user_repo.get_by_email(email)

        # Cache result (1 hour TTL)
        if user:
            await self.cache.set(cache_key, user, ttl=3600)

        return user

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            username: Username

        Returns:
            User or None if not found
        """
        # Check cache
        cache_key = f"user:username:{username}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for username {username}")
            return User(**cached) if isinstance(cached, dict) else cached

        # Fetch from database
        user = await self.user_repo.get_by_username(username)

        # Cache result (1 hour TTL)
        if user:
            await self.cache.set(cache_key, user, ttl=3600)

        return user

    async def get_user_by_spotify_id(self, spotify_id: str) -> Optional[User]:
        """
        Get user by Spotify ID.

        Args:
            spotify_id: Spotify user ID

        Returns:
            User or None if not found
        """
        # Check cache
        cache_key = f"user:spotify:{spotify_id}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for Spotify ID {spotify_id}")
            return User(**cached) if isinstance(cached, dict) else cached

        # Fetch from database
        user = await self.user_repo.get_by_spotify_id(spotify_id)

        # Cache result (1 hour TTL)
        if user:
            await self.cache.set(cache_key, user, ttl=3600)

        return user

    async def create_user(self, user: User) -> User:
        """
        Create a new user.

        Args:
            user: User instance to create

        Returns:
            Created user with generated ID
        """
        # Create in database
        created_user = await self.user_repo.create(user)

        logger.info(f"Created user {created_user.id}: {created_user.email}")
        return created_user

    async def update_user(self, user: User) -> User:
        """
        Update an existing user.

        Args:
            user: User instance to update

        Returns:
            Updated user
        """
        # Update in database
        updated_user = await self.user_repo.update(user)

        # Invalidate caches for this user
        await self._invalidate_user_caches(user.id)

        logger.info(f"Updated user {user.id}: {user.email}")
        return updated_user

    async def delete_user(self, user_id: UUID) -> bool:
        """
        Delete a user.

        Args:
            user_id: User UUID to delete

        Returns:
            True if deleted, False if not found
        """
        # Get user for cache invalidation
        user = await self.user_repo.get_by_id(user_id)

        # Delete from database
        deleted = await self.user_repo.delete(user_id)

        if deleted and user:
            # Invalidate caches for this user
            await self._invalidate_user_caches(user_id)

            logger.info(f"Deleted user {user_id}")

        return deleted

    async def verify_password(self, user: User, password: str) -> bool:
        """
        Verify user password.

        Args:
            user: User instance
            password: Plain text password to verify

        Returns:
            True if password is correct, False otherwise
        """
        # Import auth service to avoid circular dependency
        from festival_playlist_generator.services.auth import auth_service
        
        # Use auth service method for password verification
        authenticated_user = await auth_service.authenticate_user(
            self.user_repo.db, user.email, password
        )
        return authenticated_user is not None

    async def update_password(self, user: User, new_password: str) -> User:
        """
        Update user password.

        Args:
            user: User instance
            new_password: New plain text password

        Returns:
            Updated user
        """
        # Import auth service to avoid circular dependency
        from festival_playlist_generator.services.auth import auth_service
        
        # Hash the new password
        hashed_password = auth_service._hash_password(new_password)
        
        # Store hashed password in cache
        await self.cache.set(f"user_password:{user.id}", hashed_password)
        
        # Invalidate caches
        await self._invalidate_user_caches(user.id)

        logger.info(f"Updated password for user {user.id}")
        return user

    async def _invalidate_user_caches(self, user_id: UUID) -> None:
        """
        Invalidate all caches related to a specific user.

        Args:
            user_id: User UUID
        """
        # Get user to invalidate email and username caches
        user = await self.user_repo.get_by_id(user_id)

        # Delete specific user caches
        await self.cache.delete(f"user:{user_id}")

        if user:
            if user.email:
                await self.cache.delete(f"user:email:{user.email}")
            # Note: User model doesn't have username or spotify_id attributes
            # It uses oauth_provider_id instead
            if user.oauth_provider_id:
                await self.cache.delete(f"user:spotify:{user.oauth_provider_id}")

        logger.debug(f"Invalidated caches for user {user_id}")
