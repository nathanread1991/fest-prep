# Festival Playlist Generator - Setup Guide

This guide will help you set up the Festival Playlist Generator application from scratch.

## Quick Start

### Option 1: Interactive Setup Script (Recommended)

The easiest way to set up the application is using our interactive setup script:

**Linux/macOS:**
```bash
./setup.sh
```

**Windows:**
```cmd
setup.bat
```

**Direct Python execution:**
```bash
python3 setup.py
```

The setup script will guide you through:
- Database configuration (PostgreSQL)
- Redis configuration (for caching and task queues)
- Application settings (secret key, debug mode, logging)
- External API keys (Clashfinder, Setlist.fm, Spotify, YouTube)
- CORS settings

### Option 2: Manual Setup

If you prefer to configure manually, copy the example environment file:

```bash
cp .env.example .env
```

Then edit `.env` with your preferred text editor and fill in the required values.

## Prerequisites

Before running the setup, ensure you have:

### Required Software
- **Python 3.8+** - [Download here](https://www.python.org/downloads/)
- **PostgreSQL 12+** - [Download here](https://www.postgresql.org/download/)
- **Redis 6+** - [Download here](https://redis.io/download)

### API Keys (Optional but Recommended)

The application integrates with several external services. While not required for basic functionality, these API keys enable full features:

1. **Clashfinder API Key** (Recommended for festival lineup data)
   - Visit: https://clashfinder.com/api
   - Sign up for an API account
   - Get your API key from the developer dashboard
   - Used for: Fetching structured festival lineup data (primary source)

2. **Setlist.fm API Key** (Required for setlist data)
   - Visit: https://api.setlist.fm/docs/1.0/index.html
   - Sign up and request an API key
   - Used for: Fetching artist setlist data

3. **Spotify API Credentials** (Required for Spotify integration)
   - Visit: https://developer.spotify.com/dashboard
   - Create a new app
   - Get your Client ID and Client Secret
   - Used for: Creating playlists on Spotify

4. **YouTube Data API Key** (Required for YouTube Music integration)
   - Visit: https://console.developers.google.com/
   - Create a project and enable YouTube Data API v3
   - Create credentials (API key)
   - Used for: YouTube Music playlist integration

## Configuration Details

### Database Configuration

The application uses PostgreSQL as its primary database. You'll need:

- **Host**: Usually `localhost` for local development
- **Port**: Default is `5432`
- **Database Name**: Suggested `festival_db`
- **Username**: Suggested `festival_user`
- **Password**: Choose a secure password

**Example PostgreSQL setup:**
```sql
-- Connect to PostgreSQL as superuser
CREATE USER festival_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE festival_db OWNER festival_user;
GRANT ALL PRIVILEGES ON DATABASE festival_db TO festival_user;
```

### Redis Configuration

Redis is used for:
- Caching frequently accessed data
- Task queue management (Celery)
- Session storage

**Default Redis setup:**
- **Host**: `localhost`
- **Port**: `6379`
- **Password**: Usually none for local development

### Application Settings

- **Secret Key**: Automatically generated secure key for session encryption
- **Debug Mode**: Enable for development, disable for production
- **Log Level**: Choose from DEBUG, INFO, WARNING, ERROR

### CORS Settings

- **Development**: Use `["*"]` to allow all origins
- **Production**: Specify your exact domains, e.g., `["myapp.com", "www.myapp.com"]`

## Post-Setup Steps

After running the setup script, follow these steps:

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Database

Run database migrations to create the required tables:

```bash
alembic upgrade head
```

### 3. Start Redis

**Linux/macOS:**
```bash
redis-server
```

**Windows:**
```cmd
redis-server.exe
```

### 4. Start the Application

**Development mode:**
```bash
python -m uvicorn festival_playlist_generator.main:app --reload
```

**Or use the development script:**
```bash
./scripts/dev.sh  # Linux/macOS
scripts\dev.bat   # Windows
```

### 5. Verify Installation

Open your browser and navigate to:
- **Application**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Testing

### Run Unit Tests
```bash
pytest
```

### Run UI Tests
```bash
# Install browser dependencies first
npm install
npx playwright install

# Run the tests
npm run test:e2e
```

## Troubleshooting

### Common Issues

**"ModuleNotFoundError" when starting the application:**
- Make sure you've installed dependencies: `pip install -r requirements.txt`
- Ensure you're in the correct directory

**Database connection errors:**
- Verify PostgreSQL is running
- Check your database credentials in `.env`
- Ensure the database and user exist

**Redis connection errors:**
- Verify Redis is running: `redis-cli ping` should return "PONG"
- Check Redis configuration in `.env`

**API key errors:**
- Verify your API keys are correct
- Check that you've enabled the required APIs in the respective dashboards
- Some APIs have usage limits - check your quotas

### Getting Help

If you encounter issues:

1. Check the application logs for detailed error messages
2. Verify all prerequisites are installed and running
3. Ensure your `.env` file has all required values
4. Check the [GitHub Issues](https://github.com/your-repo/festival-playlist-generator/issues) for known problems

## Security Notes

### For Production Deployment

- **Never commit your `.env` file** - it contains sensitive credentials
- **Use strong passwords** for database and Redis
- **Set `DEBUG=False`** in production
- **Use HTTPS** for all external communications
- **Regularly rotate API keys** and passwords
- **Restrict CORS origins** to your specific domains
- **Use environment-specific configurations** for different deployment stages

### API Key Security

- Store API keys securely and never commit them to version control
- Use environment variables or secure key management systems
- Regularly monitor API usage for unusual activity
- Rotate keys periodically as a security best practice

## Next Steps

Once setup is complete, you can:

1. **Explore the API**: Visit http://localhost:8000/docs for interactive API documentation
2. **Import festival data**: Use the admin interface or API to add festivals
3. **Connect streaming services**: Configure your Spotify/YouTube credentials
4. **Create playlists**: Start generating playlists from festival lineups
5. **Customize the UI**: Modify templates and styles to match your preferences

Happy playlist generating! 🎵