# Project Structure

This document describes the monorepo structure of the Festival Playlist Generator project.

## Overview

The project follows a monorepo pattern with clear separation between application services and infrastructure code. This structure supports:

- **Scalability**: Easy to add new services (worker, admin, etc.)
- **Maintainability**: Clear boundaries between concerns
- **Team collaboration**: Backend devs work in `/services`, DevOps in `/infrastructure`
- **CI/CD**: Independent deployment of services

## Directory Structure

```
festival-playlist-generator/
│
├── services/                      # Application Services
│   ├── api/                      # FastAPI Application
│   │   ├── festival_playlist_generator/
│   │   │   ├── api/             # API endpoints
│   │   │   ├── core/            # Core configuration
│   │   │   ├── models/          # Database models
│   │   │   ├── repositories/    # Data access layer
│   │   │   ├── schemas/         # Pydantic schemas
│   │   │   ├── services/        # Business logic
│   │   │   ├── tasks/           # Celery tasks
│   │   │   ├── web/             # Web UI
│   │   │   └── main.py          # Application entry point
│   │   ├── tests/               # Test suite
│   │   ├── alembic/             # Database migrations
│   │   ├── nginx/               # Nginx configuration
│   │   ├── Dockerfile           # Container image
│   │   ├── docker-compose.yml   # Local development
│   │   ├── requirements.txt     # Python dependencies
│   │   └── README.md            # Service documentation
│   │
│   └── README.md                # Services overview
│
├── infrastructure/               # Infrastructure as Code
│   ├── terraform/               # Terraform configurations
│   │   ├── modules/            # Reusable Terraform modules
│   │   │   ├── billing/        # AWS Budgets, Cost Anomaly Detection
│   │   │   ├── networking/     # VPC, subnets, security groups
│   │   │   ├── database/       # Aurora Serverless v2
│   │   │   ├── cache/          # ElastiCache Redis
│   │   │   ├── compute/        # ECS Fargate, ALB
│   │   │   ├── storage/        # S3, ECR
│   │   │   ├── cdn/            # CloudFront
│   │   │   ├── monitoring/     # CloudWatch, X-Ray
│   │   │   └── security/       # Secrets Manager, ACM, WAF
│   │   ├── scripts/            # Utility scripts
│   │   ├── main.tf             # Root module
│   │   ├── variables.tf        # Input variables
│   │   ├── outputs.tf          # Output values
│   │   ├── backend.tf          # Remote state configuration
│   │   └── README.md           # Terraform documentation
│   │
│   └── README.md               # Infrastructure overview
│
├── docs/                        # Documentation
│   ├── aws-account-setup.md    # AWS setup guide
│   ├── PROJECT-STRUCTURE.md    # This file
│   └── ...
│
├── scripts/                     # Utility scripts
│   ├── festival.sh             # Festival management script
│   └── ...
│
├── .kiro/                       # Kiro specs
│   └── specs/
│       └── aws-enterprise-migration/
│
├── logs/                        # Application logs (local dev)
├── ssl/                         # SSL certificates (local dev)
├── test-results/                # Test results (local dev)
├── playwright-report/           # Playwright test reports
│
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore rules
├── README.md                    # Project overview
└── SETUP.md                     # Setup instructions
```

## Key Directories

### `/services`
Contains all application services. Currently includes:
- **api**: FastAPI application with REST API and web UI

Future services:
- **worker**: Celery worker service for background jobs

### `/infrastructure`
Contains all Infrastructure as Code (IaC):
- **terraform**: AWS infrastructure definitions using Terraform

### `/docs`
Project documentation including:
- AWS setup guides
- Architecture diagrams
- API documentation
- Runbooks

### `/scripts`
Utility scripts for development and operations:
- Local development helpers
- Deployment scripts
- Maintenance tools

### `/.kiro`
Kiro AI assistant specifications:
- Feature specs
- Migration plans
- Requirements and design documents

## Service Architecture

Each service follows clean architecture principles:

```
Controller Layer (HTTP)
    ↓
Service Layer (Business Logic)
    ↓
Repository Layer (Data Access)
    ↓
Model Layer (Domain Entities)
```

## Infrastructure Architecture

Infrastructure is organized by AWS service category:

- **Networking**: VPC, subnets, security groups, VPC endpoints
- **Compute**: ECS Fargate clusters, task definitions, ALB
- **Database**: Aurora Serverless v2 PostgreSQL
- **Cache**: ElastiCache Redis
- **Storage**: S3 buckets, ECR repositories
- **CDN**: CloudFront distributions
- **Monitoring**: CloudWatch logs, metrics, alarms, X-Ray
- **Security**: Secrets Manager, ACM certificates, WAF

## Development Workflow

### Local Development
1. Work in `/services/api` for application code
2. Use Docker Compose for local services
3. Run tests in `/services/api/tests`

### Infrastructure Changes
1. Work in `/infrastructure/terraform`
2. Test changes with `terraform plan`
3. Apply with `terraform apply`

### Deployment
1. Application: Build Docker image, push to ECR, update ECS
2. Infrastructure: Apply Terraform changes

## Benefits of This Structure

### Separation of Concerns
- Application code is isolated from infrastructure code
- Each service can be developed independently
- Clear ownership boundaries

### Scalability
- Easy to add new services
- Services can scale independently
- Infrastructure modules are reusable

### Maintainability
- Clear directory structure
- Consistent patterns across services
- Well-documented components

### CI/CD Friendly
- Services can be deployed independently
- Infrastructure changes are isolated
- Clear testing boundaries

## Migration Notes

This structure was established during the AWS migration (Week 1, Task 2). Previous structure had all code at the root level, making the project overwhelming to navigate.

The reorganization provides:
- ✅ Clear separation between app and infrastructure
- ✅ Scalable structure for future services
- ✅ Industry-standard monorepo pattern
- ✅ Better developer experience
