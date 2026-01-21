#!/usr/bin/env python3
"""
Festival Playlist Generator - Interactive Setup Script

This script will guide you through setting up the Festival Playlist Generator
by prompting for all necessary configuration values and creating the .env file.
"""

import getpass
import os
import secrets
import sys
from pathlib import Path


def print_banner():
    """Print the setup banner."""
    print("=" * 60)
    print("🎵 Festival Playlist Generator - Setup Script 🎵")
    print("=" * 60)
    print()
    print("This script will help you configure the application by")
    print("prompting for database credentials, API keys, and other")
    print("necessary configuration values.")
    print()


def print_section(title):
    """Print a section header."""
    print(f"\n{'─' * 50}")
    print(f"📋 {title}")
    print("─" * 50)


def get_input(prompt, default=None, required=True, password=False):
    """Get user input with optional default and validation."""
    if default:
        display_prompt = f"{prompt} [{default}]: "
    else:
        display_prompt = f"{prompt}: "

    if password:
        value = getpass.getpass(display_prompt)
    else:
        value = input(display_prompt).strip()

    if not value and default:
        return default

    if required and not value:
        print("❌ This field is required. Please enter a value.")
        return get_input(prompt, default, required, password)

    return value


def get_yes_no(prompt, default=True):
    """Get yes/no input from user."""
    default_str = "Y/n" if default else "y/N"
    response = input(f"{prompt} [{default_str}]: ").strip().lower()

    if not response:
        return default

    return response in ["y", "yes", "true", "1"]


def generate_secret_key():
    """Generate a secure secret key."""
    return secrets.token_urlsafe(32)


def validate_database_url(url):
    """Basic validation for database URL format."""
    if not url.startswith("postgresql://"):
        print("⚠️  Warning: Database URL should start with 'postgresql://'")
        return False
    return True


def validate_redis_url(url):
    """Basic validation for Redis URL format."""
    if not url.startswith("redis://"):
        print("⚠️  Warning: Redis URL should start with 'redis://'")
        return False
    return True


def setup_database_config():
    """Configure database settings."""
    print_section("Database Configuration")
    print("Configure your PostgreSQL database connection.")
    print("If you haven't set up PostgreSQL yet, you can use the default")
    print("values and set up the database later.")
    print()

    # Database host
    db_host = get_input("Database host", "localhost", required=False)

    # Database port
    db_port = get_input("Database port", "5432", required=False)

    # Database name
    db_name = get_input("Database name", "festival_db", required=False)

    # Database user
    db_user = get_input("Database username", "festival_user", required=False)

    # Database password
    print("\n🔐 Database password (will be hidden as you type):")
    db_password = get_input(
        "Database password", "festival_pass", required=False, password=True
    )

    # Construct database URL
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    print(f"\n✅ Database URL: {database_url}")

    return database_url


def setup_redis_config():
    """Configure Redis settings."""
    print_section("Redis Configuration")
    print("Configure your Redis connection for caching and task queues.")
    print("If you haven't set up Redis yet, you can use the default")
    print("values and set up Redis later.")
    print()

    # Redis host
    redis_host = get_input("Redis host", "localhost", required=False)

    # Redis port
    redis_port = get_input("Redis port", "6379", required=False)

    # Redis password (optional)
    has_password = get_yes_no("Does your Redis instance require a password?", False)
    redis_password = ""
    if has_password:
        print("\n🔐 Redis password (will be hidden as you type):")
        redis_password = get_input("Redis password", required=True, password=True)
        redis_auth = f":{redis_password}@"
    else:
        redis_auth = ""

    # Construct Redis URLs
    redis_url = f"redis://{redis_auth}{redis_host}:{redis_port}/0"
    celery_broker_url = f"redis://{redis_auth}{redis_host}:{redis_port}/1"
    celery_result_backend = f"redis://{redis_auth}{redis_host}:{redis_port}/2"

    print(f"\n✅ Redis URL: {redis_url}")
    print(f"✅ Celery Broker URL: {celery_broker_url}")
    print(f"✅ Celery Result Backend: {celery_result_backend}")

    return redis_url, celery_broker_url, celery_result_backend


def setup_application_config():
    """Configure application settings."""
    print_section("Application Configuration")

    # Secret key
    print("Generating a secure secret key for your application...")
    secret_key = generate_secret_key()
    print(f"✅ Generated secret key: {secret_key[:16]}... (truncated for security)")

    # Debug mode
    debug_mode = get_yes_no("Enable debug mode? (recommended for development)", True)

    # Log level
    print("\nSelect log level:")
    print("1. DEBUG (most verbose)")
    print("2. INFO (recommended)")
    print("3. WARNING")
    print("4. ERROR")

    log_choice = get_input("Log level choice", "2", required=False)
    log_levels = {"1": "DEBUG", "2": "INFO", "3": "WARNING", "4": "ERROR"}
    log_level = log_levels.get(log_choice, "INFO")

    return secret_key, debug_mode, log_level


def setup_api_keys():
    """Configure external API keys."""
    print_section("External API Keys")
    print("The Festival Playlist Generator integrates with several external")
    print("services. You'll need to obtain API keys from these services:")
    print()

    api_keys = {}

    # Clashfinder API Credentials
    print("🎪 Clashfinder API Credentials (Required)")
    print("   Get your credentials from: https://clashfinder.com/api")
    print("   This is required for fetching structured festival lineup data.")
    print("   Clashfinder provides the primary source for artist lineup information.")
    api_keys["CLASHFINDER_USERNAME"] = get_input("Clashfinder username", required=False)
    if api_keys["CLASHFINDER_USERNAME"]:
        print("🔐 Clashfinder Private Key (will be hidden as you type):")
        api_keys["CLASHFINDER_PRIVATE_KEY"] = get_input(
            "Clashfinder private key", required=False, password=True
        )
    else:
        api_keys["CLASHFINDER_PRIVATE_KEY"] = ""

    # Setlist.fm API Key
    print("\n🎤 Setlist.fm API Key (Required)")
    print("   Get your API key from: https://api.setlist.fm/docs/1.0/index.html")
    print("   This is required for fetching artist setlist data.")
    api_keys["SETLIST_FM_API_KEY"] = get_input("Setlist.fm API key", required=False)

    # Spotify API
    print("\n🎵 Spotify API Credentials (Required)")
    print("   Create an app at: https://developer.spotify.com/dashboard")
    print("   This is required for Spotify playlist integration and OAuth.")
    api_keys["SPOTIFY_CLIENT_ID"] = get_input("Spotify Client ID", required=False)
    print("🔐 Spotify Client Secret (will be hidden as you type):")
    api_keys["SPOTIFY_CLIENT_SECRET"] = get_input(
        "Spotify Client Secret", required=False, password=True
    )

    # YouTube API
    print("\n📺 YouTube Data API Key (Required)")
    print("   Get your API key from: https://console.developers.google.com/")
    print("   Enable the YouTube Data API v3 for your project.")
    print("   This is required for YouTube Music integration.")
    api_keys["YOUTUBE_API_KEY"] = get_input("YouTube API key", required=False)

    return api_keys


def setup_oauth_providers():
    """Configure OAuth provider credentials."""
    print_section("OAuth Provider Configuration")
    print("Configure OAuth providers for user authentication.")
    print("Users can sign in with these providers. You can skip any")
    print("providers you don't want to support.")
    print()

    oauth_config = {}

    # Google OAuth
    print("🔍 Google OAuth (Recommended)")
    print("   1. Go to: https://console.cloud.google.com/")
    print("   2. Create/select a project")
    print("   3. Enable Google+ API or Google Identity API")
    print("   4. Create OAuth 2.0 Client ID credentials")
    print("   5. Set redirect URI: http://localhost:8000/auth/callback")
    oauth_config["GOOGLE_CLIENT_ID"] = get_input(
        "Google OAuth Client ID", required=False
    )
    if oauth_config["GOOGLE_CLIENT_ID"]:
        print("🔐 Google OAuth Client Secret (will be hidden as you type):")
        oauth_config["GOOGLE_CLIENT_SECRET"] = get_input(
            "Google OAuth Client Secret", required=False, password=True
        )
    else:
        oauth_config["GOOGLE_CLIENT_SECRET"] = ""

    # Apple OAuth
    print("\n🍎 Apple OAuth (Advanced)")
    print("   1. Go to: https://developer.apple.com/")
    print("   2. Create App ID and Services ID")
    print("   3. Configure Sign in with Apple")
    print("   4. Generate private key and note Key ID and Team ID")
    oauth_config["APPLE_CLIENT_ID"] = get_input(
        "Apple Client ID (Services ID)", required=False
    )
    if oauth_config["APPLE_CLIENT_ID"]:
        print("🔐 Apple Client Secret (will be hidden as you type):")
        oauth_config["APPLE_CLIENT_SECRET"] = get_input(
            "Apple Client Secret", required=False, password=True
        )
        print("🔐 Apple Private Key (will be hidden as you type):")
        oauth_config["APPLE_PRIVATE_KEY"] = get_input(
            "Apple Private Key (full content)", required=False, password=True
        )
        oauth_config["APPLE_KEY_ID"] = get_input("Apple Key ID", required=False)
        oauth_config["APPLE_TEAM_ID"] = get_input("Apple Team ID", required=False)
    else:
        oauth_config["APPLE_CLIENT_SECRET"] = ""
        oauth_config["APPLE_PRIVATE_KEY"] = ""
        oauth_config["APPLE_KEY_ID"] = ""
        oauth_config["APPLE_TEAM_ID"] = ""

    # YouTube OAuth (separate from YouTube API)
    print("\n📺 YouTube OAuth (Optional)")
    print("   Same as Google OAuth but for YouTube-specific permissions")
    print("   You can use the same Google credentials or create separate ones")
    use_same_google = False
    if oauth_config["GOOGLE_CLIENT_ID"]:
        use_same_google = get_yes_no("Use same credentials as Google OAuth?", True)

    if use_same_google:
        oauth_config["YOUTUBE_OAUTH_CLIENT_ID"] = oauth_config["GOOGLE_CLIENT_ID"]
        oauth_config["YOUTUBE_OAUTH_CLIENT_SECRET"] = oauth_config[
            "GOOGLE_CLIENT_SECRET"
        ]
    else:
        oauth_config["YOUTUBE_OAUTH_CLIENT_ID"] = get_input(
            "YouTube OAuth Client ID", required=False
        )
        if oauth_config["YOUTUBE_OAUTH_CLIENT_ID"]:
            print("🔐 YouTube OAuth Client Secret (will be hidden as you type):")
            oauth_config["YOUTUBE_OAUTH_CLIENT_SECRET"] = get_input(
                "YouTube OAuth Client Secret", required=False, password=True
            )
        else:
            oauth_config["YOUTUBE_OAUTH_CLIENT_SECRET"] = ""

    # X (Twitter) OAuth
    print("\n🐦 X (Twitter) OAuth (Optional)")
    print("   1. Go to: https://developer.twitter.com/")
    print("   2. Create an app")
    print("   3. Enable OAuth 2.0")
    print("   4. Set callback URL: http://localhost:8000/auth/callback")
    oauth_config["X_CLIENT_ID"] = get_input("X (Twitter) Client ID", required=False)
    if oauth_config["X_CLIENT_ID"]:
        print("🔐 X (Twitter) Client Secret (will be hidden as you type):")
        oauth_config["X_CLIENT_SECRET"] = get_input(
            "X (Twitter) Client Secret", required=False, password=True
        )
    else:
        oauth_config["X_CLIENT_SECRET"] = ""

    return oauth_config


def setup_additional_config():
    """Configure additional application settings."""
    print_section("Additional Configuration")

    config = {}

    # OAuth redirect URI
    print("🔗 OAuth Configuration")
    is_production = get_yes_no("Is this a production deployment?", False)
    if is_production:
        domain = get_input("Your domain (e.g., myapp.com)", required=True)
        config["OAUTH_REDIRECT_URI"] = f"https://{domain}/auth/callback"
    else:
        config["OAUTH_REDIRECT_URI"] = "http://localhost:8000/auth/callback"

    # Session configuration
    config["SESSION_SECRET_KEY"] = generate_secret_key()
    config["SESSION_EXPIRE_HOURS"] = get_input(
        "Session expiry hours", "24", required=False
    )

    # Push notifications (VAPID keys)
    print("\n🔔 Push Notifications (Optional)")
    print("   Generate VAPID keys for web push notifications")
    setup_vapid = get_yes_no("Set up push notifications?", False)
    if setup_vapid:
        print("   You can generate VAPID keys at: https://vapidkeys.com/")
        print("   Or use: npx web-push generate-vapid-keys")
        config["VAPID_PUBLIC_KEY"] = get_input("VAPID Public Key", required=False)
        if config["VAPID_PUBLIC_KEY"]:
            print("🔐 VAPID Private Key (will be hidden as you type):")
            config["VAPID_PRIVATE_KEY"] = get_input(
                "VAPID Private Key", required=False, password=True
            )
            config["VAPID_EMAIL"] = get_input(
                "VAPID Email (contact email)", required=False
            )
        else:
            config["VAPID_PRIVATE_KEY"] = ""
            config["VAPID_EMAIL"] = ""
    else:
        config["VAPID_PUBLIC_KEY"] = ""
        config["VAPID_PRIVATE_KEY"] = ""
        config["VAPID_EMAIL"] = ""

    return config


def setup_admin_config():
    """Configure admin credentials."""
    print_section("Admin Configuration")
    print("Configure the admin interface credentials.")
    print("These credentials will be used to access the admin panel")
    print("for managing festivals and artists.")
    print()

    # Admin username
    admin_username = get_input("Admin username", "admin", required=False)

    # Admin password
    print("\n🔐 Admin password (will be hidden as you type):")
    print("   Choose a strong password for the admin interface.")
    admin_password = get_input(
        "Admin password", "admin123", required=False, password=True
    )

    # Confirm password
    print("🔐 Confirm admin password:")
    confirm_password = get_input("Confirm admin password", required=True, password=True)

    if admin_password != confirm_password:
        print("❌ Passwords do not match. Please try again.")
        return setup_admin_config()

    print(f"\n✅ Admin username: {admin_username}")
    print("✅ Admin password: [HIDDEN]")

    return admin_username, admin_password


def setup_cors_config():
    """Configure CORS settings."""
    print_section("CORS Configuration")
    print("Configure Cross-Origin Resource Sharing (CORS) settings.")
    print("For development, you can allow all hosts. For production,")
    print("specify your domain(s).")
    print()

    is_production = get_yes_no("Is this a production deployment?", False)

    if is_production:
        print("Enter your allowed hosts (domains), separated by commas:")
        print("Example: myapp.com,www.myapp.com,api.myapp.com")
        hosts_input = get_input("Allowed hosts", required=True)
        hosts = [host.strip() for host in hosts_input.split(",")]
        allowed_hosts = str(hosts)
    else:
        allowed_hosts = '["*"]'
        print("✅ Using wildcard (*) for development - allows all hosts")

    return allowed_hosts


def create_env_file(config):
    """Create the .env file with the provided configuration."""
    print_section("Creating Configuration File")

    env_content = f"""# Festival Playlist Generator Configuration
# Generated by setup script on {os.popen('date').read().strip()}

# Database Configuration
DATABASE_URL={config['database_url']}

# Redis Configuration
REDIS_URL={config['redis_url']}

# Celery Configuration
CELERY_BROKER_URL={config['celery_broker_url']}
CELERY_RESULT_BACKEND={config['celery_result_backend']}

# Application Configuration
SECRET_KEY={config['secret_key']}
DEBUG={config['debug']}
LOG_LEVEL={config['log_level']}

# Admin Configuration
ADMIN_USERNAME={config['admin_username']}
ADMIN_PASSWORD={config['admin_password']}

# External API Keys
CLASHFINDER_USERNAME={config['api_keys']['CLASHFINDER_USERNAME']}
CLASHFINDER_PRIVATE_KEY={config['api_keys']['CLASHFINDER_PRIVATE_KEY']}
SETLIST_FM_API_KEY={config['api_keys']['SETLIST_FM_API_KEY']}
SPOTIFY_CLIENT_ID={config['api_keys']['SPOTIFY_CLIENT_ID']}
SPOTIFY_CLIENT_SECRET={config['api_keys']['SPOTIFY_CLIENT_SECRET']}
YOUTUBE_API_KEY={config['api_keys']['YOUTUBE_API_KEY']}

# OAuth Provider Configuration
GOOGLE_CLIENT_ID={config['oauth_config']['GOOGLE_CLIENT_ID']}
GOOGLE_CLIENT_SECRET={config['oauth_config']['GOOGLE_CLIENT_SECRET']}
APPLE_CLIENT_ID={config['oauth_config']['APPLE_CLIENT_ID']}
APPLE_CLIENT_SECRET={config['oauth_config']['APPLE_CLIENT_SECRET']}
APPLE_PRIVATE_KEY={config['oauth_config']['APPLE_PRIVATE_KEY']}
APPLE_KEY_ID={config['oauth_config']['APPLE_KEY_ID']}
APPLE_TEAM_ID={config['oauth_config']['APPLE_TEAM_ID']}
YOUTUBE_OAUTH_CLIENT_ID={config['oauth_config']['YOUTUBE_OAUTH_CLIENT_ID']}
YOUTUBE_OAUTH_CLIENT_SECRET={config['oauth_config']['YOUTUBE_OAUTH_CLIENT_SECRET']}
X_CLIENT_ID={config['oauth_config']['X_CLIENT_ID']}
X_CLIENT_SECRET={config['oauth_config']['X_CLIENT_SECRET']}

# OAuth Configuration
OAUTH_REDIRECT_URI={config['additional_config']['OAUTH_REDIRECT_URI']}
SESSION_SECRET_KEY={config['additional_config']['SESSION_SECRET_KEY']}
SESSION_EXPIRE_HOURS={config['additional_config']['SESSION_EXPIRE_HOURS']}

# Push Notifications (VAPID)
VAPID_PRIVATE_KEY={config['additional_config']['VAPID_PRIVATE_KEY']}
VAPID_PUBLIC_KEY={config['additional_config']['VAPID_PUBLIC_KEY']}
VAPID_EMAIL={config['additional_config']['VAPID_EMAIL']}

# CORS Configuration
ALLOWED_HOSTS={config['allowed_hosts']}
"""

    # Check if .env already exists
    env_path = Path(".env")
    if env_path.exists():
        backup_existing = get_yes_no(
            "⚠️  .env file already exists. Create backup?", True
        )
        if backup_existing:
            backup_path = Path(".env.backup")
            counter = 1
            while backup_path.exists():
                backup_path = Path(f".env.backup.{counter}")
                counter += 1

            env_path.rename(backup_path)
            print(f"✅ Existing .env backed up to {backup_path}")

    # Write the new .env file
    with open(".env", "w") as f:
        f.write(env_content)

    print("✅ Configuration saved to .env file")


def print_next_steps():
    """Print next steps for the user."""
    print_section("Next Steps")
    print("🎉 Setup complete! Here's what to do next:")
    print()
    print("1. 📦 Install dependencies:")
    print("   pip install -r requirements.txt")
    print("   npm install  # For frontend dependencies")
    print()
    print("2. 🗄️  Set up your database:")
    print("   - Install PostgreSQL if you haven't already")
    print("   - Create the database and user specified in your config")
    print("   - Run database migrations: alembic upgrade head")
    print()
    print("3. 🔴 Set up Redis:")
    print("   - Install Redis if you haven't already")
    print("   - Start Redis server: redis-server")
    print()
    print("4. 🔑 Configure OAuth providers (if not done during setup):")
    print("   - Google: https://console.cloud.google.com/")
    print("   - Apple: https://developer.apple.com/")
    print("   - X (Twitter): https://developer.twitter.com/")
    print("   - Update the .env file with your actual OAuth credentials")
    print()
    print("5. 🔑 Configure remaining API keys (if not done during setup):")
    print("   - Clashfinder: https://clashfinder.com/api")
    print("   - Setlist.fm: https://api.setlist.fm/docs/1.0/index.html")
    print("   - Spotify: https://developer.spotify.com/dashboard")
    print("   - YouTube: https://console.developers.google.com/")
    print("   - Update the .env file with your actual API keys")
    print()
    print("6. 🚀 Start the application:")
    print("   - Using the launcher script: ./festival.sh start")
    print(
        "   - Or manually: python -m uvicorn festival_playlist_generator.main:app --reload"
    )
    print()
    print("7. 🧪 Run tests:")
    print("   - Unit tests: pytest")
    print("   - Property-based tests: pytest tests/test_oauth_authentication.py")
    print("   - UI tests: npm run test:e2e")
    print()
    print("8. 🌐 Access the application:")
    print("   - Web interface: http://localhost:8000")
    print("   - API documentation: http://localhost:8000/docs")
    print("   - Admin panel: http://localhost:8000/admin")
    print()
    print("💡 Useful Commands:")
    print("   - Change admin password: ./setup.sh --change-admin-password")
    print("   - View logs: ./festival.sh logs")
    print("   - Stop services: ./festival.sh stop")
    print("   - Restart services: ./festival.sh restart")
    print()
    print("🔐 OAuth Testing:")
    print("   - Test OAuth flows at: http://localhost:8000/auth/login")
    print("   - Each configured provider will appear as a sign-in option")
    print(
        "   - Make sure redirect URIs are set to: http://localhost:8000/auth/callback"
    )
    print()
    print("📖 For more detailed instructions, check:")
    print("   - README.md - General setup and usage")
    print("   - SETUP.md - Detailed setup instructions")
    print("   - OAUTH_SETUP_NOTES.md - OAuth configuration guide")
    print()
    print("🎵 Happy playlist generating! 🎵")


def main():
    """Main setup function."""
    try:
        print_banner()

        # Collect all configuration
        config = {}

        # Database configuration
        config["database_url"] = setup_database_config()

        # Redis configuration
        redis_url, celery_broker_url, celery_result_backend = setup_redis_config()
        config["redis_url"] = redis_url
        config["celery_broker_url"] = celery_broker_url
        config["celery_result_backend"] = celery_result_backend

        # Application configuration
        secret_key, debug_mode, log_level = setup_application_config()
        config["secret_key"] = secret_key
        config["debug"] = str(debug_mode)
        config["log_level"] = log_level

        # API keys
        config["api_keys"] = setup_api_keys()

        # OAuth providers
        config["oauth_config"] = setup_oauth_providers()

        # Additional configuration
        config["additional_config"] = setup_additional_config()

        # Admin configuration
        admin_username, admin_password = setup_admin_config()
        config["admin_username"] = admin_username
        config["admin_password"] = admin_password

        # CORS configuration
        config["allowed_hosts"] = setup_cors_config()

        # Create .env file
        create_env_file(config)

        # Print next steps
        print_next_steps()

    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ An error occurred during setup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
