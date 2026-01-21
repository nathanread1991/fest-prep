# Services

This directory contains all application services for the Festival Playlist Generator.

## Current Services

### API Service (`/api`)
FastAPI application providing REST API endpoints for festival and playlist management.

**Tech Stack:**
- FastAPI (Python web framework)
- PostgreSQL (database)
- Redis (caching)
- Celery (background tasks)

**Deployment:** AWS ECS Fargate

## Future Services

### Worker Service
Celery worker service for background job processing (playlist generation, data scraping, etc.)

**Deployment:** AWS ECS Fargate Spot

## Service Architecture

Each service follows clean architecture principles:
- **Controllers** - HTTP request/response handling
- **Services** - Business logic
- **Repositories** - Data access
- **Models** - Domain entities

## Development

Each service has its own:
- `Dockerfile` for containerization
- `requirements.txt` for dependencies
- `tests/` directory for testing
- `README.md` for service-specific documentation

## Deployment

All services are deployed via infrastructure defined in `/infrastructure/terraform`.
