# Festival Playlist Generator - API Service

This directory contains the FastAPI application for the Festival Playlist Generator.

## Structure

```
services/api/
├── festival_playlist_generator/  # Main application code
│   ├── api/                      # API endpoints
│   ├── core/                     # Core configuration
│   ├── models/                   # Database models
│   ├── repositories/             # Data access layer
│   ├── schemas/                  # Pydantic schemas
│   ├── services/                 # Business logic
│   ├── tasks/                    # Celery tasks
│   └── web/                      # Web UI
├── tests/                        # Test suite
├── alembic/                      # Database migrations
├── nginx/                        # Nginx configuration
├── Dockerfile                    # Container image
├── docker-compose.yml            # Local development
├── requirements.txt              # Python dependencies
├── setup.py                      # Package setup
└── alembic.ini                   # Alembic configuration
```

## Local Development

See the main [README.md](../../README.md) in the project root for setup instructions.

## Deployment

This service is deployed to AWS ECS Fargate. See [infrastructure/terraform](../../infrastructure/terraform) for IaC configuration.
