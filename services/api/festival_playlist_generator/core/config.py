"""Application configuration settings."""

import os
from typing import Any, Callable, List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # Database settings
    DATABASE_URL: str = (
        "postgresql://festival_user:festival_pass@localhost:5432/festival_db"
    )

    # Redis settings
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery settings
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # API settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALLOWED_HOSTS: List[str] = ["*"]

    # Admin settings
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # External API settings
    CLASHFINDER_USERNAME: str = ""
    CLASHFINDER_PRIVATE_KEY: str = ""
    SETLIST_FM_API_KEY: str = ""
    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""
    YOUTUBE_API_KEY: str = ""

    # AI API Keys for Festival Scraping
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # OAuth Provider Settings
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    APPLE_CLIENT_ID: str = ""
    APPLE_CLIENT_SECRET: str = ""
    APPLE_PRIVATE_KEY: str = ""  # Apple requires private key for JWT
    APPLE_KEY_ID: str = ""
    APPLE_TEAM_ID: str = ""
    YOUTUBE_OAUTH_CLIENT_ID: str = ""  # Separate from YouTube API key
    YOUTUBE_OAUTH_CLIENT_SECRET: str = ""
    X_CLIENT_ID: str = ""  # Twitter/X OAuth
    X_CLIENT_SECRET: str = ""

    # OAuth Configuration
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    SESSION_SECRET_KEY: str = ""  # For session encryption
    SESSION_EXPIRE_HOURS: int = 24

    # Push notification settings (VAPID)
    VAPID_PRIVATE_KEY: str = ""
    VAPID_PUBLIC_KEY: str = ""
    VAPID_EMAIL: str = "admin@festivalplaylists.com"

    # SSL/HTTPS Configuration
    DOMAIN_NAME: str = ""  # e.g., "example.com" - leave empty for localhost
    USE_HTTPS: bool = False  # Auto-enabled if DOMAIN_NAME is set or SSL certs exist
    SSL_CERT_PATH: str = "ssl/localhost.crt"
    SSL_KEY_PATH: str = "ssl/localhost.key"
    SSL_AUTO_GENERATE: bool = True  # Auto-generate self-signed certs for localhost
    CERTBOT_EMAIL: str = ""  # Email for Let's Encrypt notifications

    # Image Cache Configuration
    IMAGE_CACHE_ENABLED: bool = True
    IMAGE_PROXY_URL: str = "http://localhost:80"
    WARM_CACHE_ON_STARTUP: bool = False  # Set to True to pre-populate cache on startup

    # Application settings
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"


settings = Settings()
