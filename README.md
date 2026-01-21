# Festival Playlist Generator

A mobile-first web application that helps music fans prepare for festivals and gigs by automatically generating playlists based on artists' recent setlists.

## 🚀 AWS Migration Status

**Current Phase**: Week 1 - Foundation & Architecture

This project is being migrated from local Docker deployment to AWS infrastructure. See [AWS Migration Spec](.kiro/specs/aws-enterprise-migration/) for details.

## ✅ CI Pipeline Test

Testing GitHub Actions workflow integration - verifying all 7 jobs execute correctly.

### Completed Tasks
- ✅ Task 1: AWS account setup and billing alerts configured
- ✅ Task 2: Terraform project structure initialized

### Cost Monitoring
- **Target Cost**: $10-15/month with daily teardown strategy
- **Current Setup**: AWS Budgets with $10, $20, $30 thresholds
- **Monitoring**: Cost Anomaly Detection enabled

For AWS setup details, see [docs/aws-account-setup.md](docs/aws-account-setup.md)

## Project Structure

This project follows a monorepo structure with clear separation between application code and infrastructure:

```
festival-playlist-generator/
├── services/              # Application services
│   └── api/              # FastAPI application
│       ├── festival_playlist_generator/  # Main app code
│       ├── tests/        # Test suite
│       ├── alembic/      # Database migrations
│       ├── Dockerfile    # Container image
│       └── ...
├── infrastructure/        # Infrastructure as Code
│   └── terraform/        # Terraform configurations
│       ├── modules/      # Reusable modules
│       └── ...
├── docs/                 # Documentation
├── scripts/              # Utility scripts
└── .kiro/               # Kiro specs
```

## Features

- Automatic festival data collection from multiple sources including Clashfinder API
- Artist setlist analysis using Setlist.fm API
- Intelligent playlist generation based on performance frequency
- Integration with popular streaming platforms (Spotify, YouTube Music, Apple Music)
- Mobile-first responsive web interface
- Background task processing with Celery
- RESTful API for external integrations

## Technology Stack

### Application
- **Backend**: FastAPI with Python 3.11+
- **Database**: PostgreSQL with Redis for caching
- **Task Queue**: Celery with Redis broker
- **Frontend**: Mobile-first responsive web application

### Infrastructure (AWS)
- **Compute**: ECS Fargate (API + Worker services)
- **Database**: Aurora Serverless v2 PostgreSQL
- **Cache**: ElastiCache Redis
- **Storage**: S3, ECR
- **CDN**: CloudFront
- **Monitoring**: CloudWatch, X-Ray
- **IaC**: Terraform with native S3 state locking

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd festival-playlist-generator
   ```

2. **Copy environment configuration**
   ```bash
   cp .env.example .env
   ```

3. **Start services with Docker Compose**
   ```bash
   cd services/api
   docker-compose up -d
   ```

4. **Run database migrations**
   ```bash
   docker-compose exec app alembic upgrade head
   ```

5. **Access the application**
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

For detailed development setup, see [services/api/README.md](services/api/README.md)

### AWS Deployment

1. **Initialize Terraform backend**
   ```bash
   cd infrastructure/terraform
   ./scripts/init-backend.sh
   ```

2. **Configure variables**
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your values
   ```

3. **Deploy infrastructure**
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

For detailed infrastructure setup, see [infrastructure/README.md](infrastructure/README.md)

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure the following:

- **Database**: PostgreSQL connection settings
- **Redis**: Cache and message broker settings
- **API Keys**: External service credentials (Clashfinder, Setlist.fm, Spotify, etc.)
- **Security**: Secret keys and CORS settings

### External API Setup

1. **Clashfinder API**: Register at https://clashfinder.com/api (Primary source for festival lineup data)
2. **Setlist.fm API**: Register at https://api.setlist.fm/
3. **Spotify API**: Create app at https://developer.spotify.com/
4. **YouTube API**: Get key from Google Cloud Console

## Development

### Running Tests

```bash
cd services/api
pytest
```

### Database Migrations

```bash
cd services/api

# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Code Formatting

```bash
cd services/api

# Format code
black festival_playlist_generator/
isort festival_playlist_generator/

# Lint code
flake8 festival_playlist_generator/
mypy festival_playlist_generator/
```

## Documentation

- [API Service](services/api/README.md) - Application code and local development
- [Infrastructure](infrastructure/README.md) - AWS infrastructure and Terraform
- [AWS Migration Spec](.kiro/specs/aws-enterprise-migration/) - Migration plan and requirements
- [AWS Setup Guide](docs/aws-account-setup.md) - AWS account configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
