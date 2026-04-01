"""Application configuration settings.

Supports both local Docker and AWS ECS deployments.
In AWS, secrets are injected as environment variables by the ECS task
definition from Secrets Manager. The env var names from ECS are mapped
to the application's expected field names via Pydantic validators.

ECS-injected env vars:
- DATABASE_URL: From database credentials secret
- REDIS_URL: From Redis URL secret
- SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET: From Spotify secret
- SETLISTFM_API_KEY: From Setlist.fm secret (mapped to SETLIST_FM_API_KEY)
- JWT_SECRET_KEY: From JWT secret (mapped to SECRET_KEY)
- CELERY_BROKER_URL / CELERY_RESULT_BACKEND: From Redis URL secret
"""

import os
from typing import List, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # AWS environment settings
    ENVIRONMENT: str = "local"
    AWS_REGION: str = "eu-west-2"

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

    # CloudWatch Metrics settings
    METRICS_ENABLED: bool = False  # Enable in AWS environments
    METRICS_NAMESPACE: str = "FestivalApp"
    METRICS_FLUSH_INTERVAL: int = 60  # Seconds between batch flushes

    # X-Ray tracing settings
    XRAY_ENABLED: bool = False  # Enable in AWS environments
    XRAY_SERVICE_NAME: str = "festival-playlist-api"
    XRAY_DAEMON_ADDRESS: str = "127.0.0.1:2000"
    XRAY_SAMPLING_RATE: float = 0.1  # 10% default sampling

    # Application settings
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    @model_validator(mode="before")
    @classmethod
    def map_aws_env_vars(cls, values: dict) -> dict:  # type: ignore[type-arg]
        """Map AWS ECS-injected env var names to application field names.

        ECS task definitions inject secrets with specific env var names
        that may differ from the application's expected field names.
        This validator handles the mapping at startup.
        """
        # JWT_SECRET_KEY (from ECS) -> SECRET_KEY (app field)
        jwt_key: Optional[str] = os.environ.get("JWT_SECRET_KEY")
        if jwt_key and not values.get("SECRET_KEY"):
            values["SECRET_KEY"] = jwt_key

        # SETLISTFM_API_KEY (from ECS) -> SETLIST_FM_API_KEY (app field)
        setlistfm_key: Optional[str] = os.environ.get("SETLISTFM_API_KEY")
        if setlistfm_key and not values.get("SETLIST_FM_API_KEY"):
            values["SETLIST_FM_API_KEY"] = setlistfm_key

        return values


settings = Settings()
