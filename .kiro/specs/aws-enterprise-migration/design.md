# AWS Enterprise Migration - Design Document

## Overview

This design document details the architecture and implementation strategy for migrating the Festival Playlist Generator from a local Docker-based deployment to a production-ready AWS infrastructure. The design prioritizes cost optimization through daily teardown/rebuild capability, clean architecture patterns, and Infrastructure as Code principles.

### Design Goals

1. **Cost-Optimized Infrastructure**: Target $10-15/month with daily teardown capability
2. **Fast Teardown/Rebuild**: < 15 min provision, < 10 min destroy with automated data persistence
3. **Clean Architecture**: Repository → Service → Controller pattern with 80%+ test coverage
4. **Infrastructure as Code**: 100% Terraform-managed with no manual AWS console changes
5. **Zero-Trust Security**: Tight security groups with ECS tasks in public subnets (no NAT Gateway)
6. **Automated CI/CD**: GitHub Actions for testing and deployment
7. **Enterprise Observability**: CloudWatch Logs, Metrics, Alarms, and X-Ray tracing
8. **Solo Developer Friendly**: Manageable by one person with clear documentation

### AWS Region Configuration

**Primary Region**: `eu-west-2` (London)

**Rationale**:
- Geographic proximity to UK-based developer and users
- Lower latency for UK/European users
- Compliance with UK data residency preferences
- Competitive pricing similar to us-east-1

**Multi-Region Considerations**:
- Phase 1 (MVP): Single region deployment (eu-west-2)
- Future: CloudFront provides global CDN regardless of origin region
- Future: Multi-region can be added later if needed

**Region-Specific Notes**:
- All Terraform configurations use `eu-west-2` as default
- CloudWatch billing metrics still require `us-east-1` (AWS limitation)
- ACM certificates for CloudFront must be in `us-east-1` (AWS requirement)
- All other resources deploy to `eu-west-2`

### Key Architectural Decisions

**Decision 1: ECS Fargate over Lambda**
- Rationale: Existing containerized application, long-running Celery workers, more predictable costs
- Trade-off: Slightly higher cost than Lambda for low traffic, but simpler migration

**Decision 2: Aurora Serverless v2 over RDS**
- Rationale: Per-second billing, auto-scaling (0.5-4 ACU), auto-pause in dev saves costs
- Trade-off: Slightly more expensive than t4g.micro at constant load, but better for variable workloads

**Decision 3: No NAT Gateway/Instance**
- Rationale: Saves $32-96/month, ECS tasks in public subnets with tight security groups equally secure
- Trade-off: Requires careful security group configuration, but well worth the cost savings

**Decision 4: Single Environment with Daily Teardown**
- Rationale: Reduces costs by ~50% ($10-15/month vs $30/month running 24/7)
- Trade-off: Requires automated snapshot/restore, but provision time < 15 min is acceptable

**Decision 5: Terraform over CloudFormation**
- Rationale: Better module ecosystem, cleaner syntax, multi-cloud capability
- Trade-off: Learning curve, but more marketable skill


## Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Internet Users                                  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ HTTPS
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AWS CloudFront (CDN)                                 │
│  - Global edge locations                                                     │
│  - Static asset caching                                                      │
│  - SSL/TLS termination                                                       │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Application Load Balancer (ALB)                           │
│  - SSL termination                                                           │
│  - Path-based routing                                                        │
│  - Health checks                                                             │
│  - Protected by AWS WAF                                                      │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ Port 8000
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VPC (10.0.0.0/16)                                    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              Public Subnets (10.0.1.0/24, 10.0.2.0/24)              │   │
│  │                                                                       │   │
│  │  ┌──────────────────────────────────────────────────────────────┐  │   │
│  │  │           ECS Fargate Cluster                                 │  │   │
│  │  │                                                               │  │   │
│  │  │  ┌─────────────────┐      ┌─────────────────┐              │  │   │
│  │  │  │  API Service    │      │  Worker Service │              │  │   │
│  │  │  │  (FastAPI)      │      │  (Celery)       │              │  │   │
│  │  │  │  1-4 tasks      │      │  0-2 tasks      │              │  │   │
│  │  │  │  On-Demand      │      │  Spot (70% off) │              │  │   │
│  │  │  └────────┬────────┘      └────────┬────────┘              │  │   │
│  │  │           │                         │                        │  │   │
│  │  └───────────┼─────────────────────────┼────────────────────────┘  │   │
│  │              │                         │                            │   │
│  └──────────────┼─────────────────────────┼────────────────────────────┘   │
│                 │                         │                                 │
│                 │ Port 5432               │ Port 6379                       │
│                 ▼                         ▼                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │            Private Subnets (10.0.10.0/24, 10.0.11.0/24)             │   │
│  │                                                                       │   │
│  │  ┌──────────────────────┐         ┌──────────────────────┐          │   │
│  │  │  Aurora Serverless   │         │  ElastiCache Redis   │          │   │
│  │  │  v2 (PostgreSQL)     │         │  (cache.t4g.micro)   │          │   │
│  │  │  0.5-4 ACU           │         │  Single node (dev)   │          │   │
│  │  │  Auto-pause (dev)    │         │  Multi-AZ (prod)     │          │   │
│  │  └──────────────────────┘         └──────────────────────┘          │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        VPC Endpoints (PrivateLink)                     │  │
│  │  - S3, ECR, CloudWatch Logs, Secrets Manager                          │  │
│  │  - No internet/NAT needed for AWS API calls                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         External AWS Services                                │
│                                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │      S3      │  │     ECR      │  │   Secrets    │  │  CloudWatch  │   │
│  │   Buckets    │  │  Container   │  │   Manager    │  │  Logs/Metrics│   │
│  │              │  │   Registry   │  │              │  │   X-Ray      │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Network Architecture

**VPC Design:**
- CIDR: 10.0.0.0/16 (65,536 IPs)
- Region: us-east-1 (2 Availability Zones)

**Subnets:**
- Public Subnet 1: 10.0.1.0/24 (AZ us-east-1a) - 256 IPs
- Public Subnet 2: 10.0.2.0/24 (AZ us-east-1b) - 256 IPs
- Private Subnet 1: 10.0.10.0/24 (AZ us-east-1a) - 256 IPs
- Private Subnet 2: 10.0.11.0/24 (AZ us-east-1b) - 256 IPs

**Routing:**
- Public subnets: Route to Internet Gateway (0.0.0.0/0 → IGW)
- Private subnets: No internet access (databases don't need it)
- VPC Endpoints: S3, ECR, CloudWatch Logs, Secrets Manager (PrivateLink)

**Why No NAT Gateway/Instance:**
- Cost savings: $32-96/month eliminated
- ECS tasks in public subnets with direct internet access
- Security maintained through tight security groups
- VPC Endpoints for AWS service access (no internet needed)
- Databases in private subnets (no internet access)


### Security Group Architecture (Zero-Trust Model)

**Critical Design Principle**: Least privilege access with explicit allow rules. All security groups use references to other security groups (not CIDR blocks) where possible.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Security Group Flow                                  │
│                                                                               │
│  Internet (0.0.0.0/0)                                                        │
│       │                                                                       │
│       │ Port 443 (HTTPS)                                                     │
│       │ Port 80 (HTTP → redirect to 443)                                     │
│       ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  ALB Security Group (sg-alb)                                     │        │
│  │  Inbound:  0.0.0.0/0:443, 0.0.0.0/0:80                          │        │
│  │  Outbound: sg-ecs:8000                                          │        │
│  └────────────────────────┬────────────────────────────────────────┘        │
│                           │                                                  │
│                           │ Port 8000                                        │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  ECS Tasks Security Group (sg-ecs)                              │        │
│  │  Inbound:  sg-alb:8000 ONLY                                     │        │
│  │  Outbound: 0.0.0.0/0:443 (external APIs)                        │        │
│  │            sg-rds:5432                                           │        │
│  │            sg-redis:6379                                         │        │
│  │            10.0.0.0/16:443 (VPC Endpoints)                      │        │
│  └────────┬──────────────────────┬─────────────────────────────────┘        │
│           │                      │                                           │
│           │ Port 5432            │ Port 6379                                │
│           ▼                      ▼                                           │
│  ┌──────────────────┐   ┌──────────────────┐                               │
│  │  RDS SG (sg-rds) │   │ Redis SG         │                               │
│  │  Inbound:        │   │ (sg-redis)       │                               │
│  │  sg-ecs:5432     │   │ Inbound:         │                               │
│  │  Outbound: None  │   │ sg-ecs:6379      │                               │
│  └──────────────────┘   │ Outbound: None   │                               │
│                         └──────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Security Group Specifications:**

**1. ALB Security Group (`sg-alb`)**
```hcl
# Inbound Rules
- Port 443 from 0.0.0.0/0 (HTTPS from internet)
- Port 80 from 0.0.0.0/0 (HTTP redirect to HTTPS)

# Outbound Rules
- Port 8000 to sg-ecs (forward to ECS tasks)

# Purpose: Accept public traffic, forward only to ECS tasks
```

**2. ECS Tasks Security Group (`sg-ecs`)**
```hcl
# Inbound Rules
- Port 8000 from sg-alb ONLY (no direct public access!)

# Outbound Rules
- Port 443 to 0.0.0.0/0 (external APIs: Spotify, Setlist.fm, GitHub)
- Port 5432 to sg-rds (database access)
- Port 6379 to sg-redis (cache access)
- Port 443 to 10.0.0.0/16 (VPC Endpoints: S3, ECR, CloudWatch, Secrets Manager)

# Purpose: Accept traffic only from ALB, access databases and external APIs
```

**3. RDS Security Group (`sg-rds`)**
```hcl
# Inbound Rules
- Port 5432 from sg-ecs ONLY (no public access!)

# Outbound Rules
- None (database doesn't initiate connections)

# Purpose: Accept connections only from ECS tasks
```

**4. ElastiCache Redis Security Group (`sg-redis`)**
```hcl
# Inbound Rules
- Port 6379 from sg-ecs ONLY (no public access!)

# Outbound Rules
- None (cache doesn't initiate connections)

# Purpose: Accept connections only from ECS tasks
```

**5. VPC Endpoints Security Group (`sg-vpc-endpoints`)**
```hcl
# Inbound Rules
- Port 443 from sg-ecs (ECS tasks accessing AWS services)

# Outbound Rules
- None (endpoints don't initiate connections)

# Purpose: Allow ECS tasks to access AWS services via PrivateLink
```

**Security Group Validation Rules:**
1. No security group allows 0.0.0.0/0 inbound except ALB (ports 80/443)
2. All database security groups only allow traffic from application security groups
3. All security group rules use SG references (not CIDR) where possible
4. All security group changes require Terraform (no manual console changes)
5. Security group changes trigger CloudWatch alarms for review
6. VPC Flow Logs enabled to monitor all traffic patterns


## Components and Interfaces

### Application Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Clean Architecture Layers                            │
│                                                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      Controllers (HTTP Layer)                          │  │
│  │  - api/v1/controllers/artist_controller.py                            │  │
│  │  - api/v1/controllers/festival_controller.py                          │  │
│  │  - api/v1/controllers/playlist_controller.py                          │  │
│  │  - api/v1/controllers/setlist_controller.py                           │  │
│  │  - api/v1/controllers/user_controller.py                              │  │
│  │                                                                         │  │
│  │  Responsibilities:                                                     │  │
│  │  - HTTP request/response handling                                     │  │
│  │  - Request validation (Pydantic models)                               │  │
│  │  - Response serialization                                             │  │
│  │  - Error handling and HTTP status codes                               │  │
│  │  - Authentication/authorization checks                                │  │
│  │  - NO business logic                                                  │  │
│  │  - NO database access                                                 │  │
│  └─────────────────────────────┬─────────────────────────────────────────┘  │
│                                │ depends on                                 │
│                                ▼                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      Services (Business Logic Layer)                   │  │
│  │  - services/artist_service.py                                         │  │
│  │  - services/festival_service.py                                       │  │
│  │  - services/playlist_service.py                                       │  │
│  │  - services/setlist_service.py                                        │  │
│  │  - services/user_service.py                                           │  │
│  │  - services/spotify_service.py (external API)                         │  │
│  │  - services/setlistfm_service.py (external API)                       │  │
│  │                                                                         │  │
│  │  Responsibilities:                                                     │  │
│  │  - Business logic and orchestration                                   │  │
│  │  - Data transformation and validation                                 │  │
│  │  - Caching strategy (Redis)                                           │  │
│  │  - External API integration                                           │  │
│  │  - Transaction management                                             │  │
│  │  - Framework-agnostic (can swap FastAPI for Flask)                   │  │
│  │  - NO HTTP concerns                                                   │  │
│  │  - NO direct database access                                          │  │
│  └─────────────────────────────┬─────────────────────────────────────────┘  │
│                                │ depends on                                 │
│                                ▼                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                   Repositories (Data Access Layer)                     │  │
│  │  - repositories/artist_repository.py (EXISTS)                         │  │
│  │  - repositories/festival_repository.py                                │  │
│  │  - repositories/playlist_repository.py                                │  │
│  │  - repositories/setlist_repository.py                                 │  │
│  │  - repositories/user_repository.py                                    │  │
│  │  - repositories/base_repository.py (abstract base)                    │  │
│  │                                                                         │  │
│  │  Responsibilities:                                                     │  │
│  │  - ALL database operations (CRUD)                                     │  │
│  │  - Query construction and optimization                                │  │
│  │  - Database transaction handling                                      │  │
│  │  - ORM mapping (SQLAlchemy)                                           │  │
│  │  - NO business logic                                                  │  │
│  │  - NO caching (handled by service layer)                              │  │
│  └─────────────────────────────┬─────────────────────────────────────────┘  │
│                                │ depends on                                 │
│                                ▼                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        Models (Domain Layer)                           │  │
│  │  - models/artist.py                                                   │  │
│  │  - models/festival.py                                                 │  │
│  │  - models/playlist.py                                                 │  │
│  │  - models/setlist.py                                                  │  │
│  │  - models/user.py                                                     │  │
│  │                                                                         │  │
│  │  Responsibilities:                                                     │  │
│  │  - SQLAlchemy ORM models                                              │  │
│  │  - Database schema definition                                         │  │
│  │  - Relationships and constraints                                      │  │
│  │  - NO business logic                                                  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Dependency Injection Pattern

**Service Container (`core/container.py`):**
```python
from dependency_injector import containers, providers
from repositories.artist_repository import ArtistRepository
from repositories.festival_repository import FestivalRepository
from services.artist_service import ArtistService
from services.festival_service import FestivalService

class Container(containers.DeclarativeContainer):
    """Dependency injection container for all services and repositories."""
    
    # Configuration
    config = providers.Configuration()
    
    # Database session
    db_session = providers.Singleton(
        get_db_session,
        database_url=config.database_url
    )
    
    # Repositories
    artist_repository = providers.Factory(
        ArtistRepository,
        session=db_session
    )
    
    festival_repository = providers.Factory(
        FestivalRepository,
        session=db_session
    )
    
    # Services
    artist_service = providers.Factory(
        ArtistService,
        artist_repository=artist_repository,
        cache_client=providers.Singleton(get_redis_client)
    )
    
    festival_service = providers.Factory(
        FestivalService,
        festival_repository=festival_repository,
        artist_service=artist_service,
        cache_client=providers.Singleton(get_redis_client)
    )
```

**Controller Usage:**
```python
from fastapi import APIRouter, Depends
from core.container import Container

router = APIRouter()
container = Container()

@router.get("/artists/{artist_id}")
async def get_artist(
    artist_id: int,
    artist_service: ArtistService = Depends(container.artist_service)
):
    """Get artist by ID - controller only handles HTTP concerns."""
    artist = await artist_service.get_artist_by_id(artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    return artist
```

### Repository Interface Pattern

**Base Repository (`repositories/base_repository.py`):**
```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar('T')

class BaseRepository(ABC, Generic[T]):
    """Abstract base repository with common CRUD operations."""
    
    def __init__(self, session: AsyncSession, model_class: type[T]):
        self.session = session
        self.model_class = model_class
    
    async def get_by_id(self, id: int) -> Optional[T]:
        """Get entity by ID."""
        result = await self.session.execute(
            select(self.model_class).where(self.model_class.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all entities with pagination."""
        result = await self.session.execute(
            select(self.model_class).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    async def create(self, entity: T) -> T:
        """Create new entity."""
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity
    
    async def update(self, entity: T) -> T:
        """Update existing entity."""
        await self.session.commit()
        await self.session.refresh(entity)
        return entity
    
    async def delete(self, id: int) -> bool:
        """Delete entity by ID."""
        entity = await self.get_by_id(id)
        if entity:
            await self.session.delete(entity)
            await self.session.commit()
            return True
        return False
```

**Concrete Repository Example (`repositories/festival_repository.py`):**
```python
from typing import List, Optional
from sqlalchemy import select
from models.festival import Festival
from repositories.base_repository import BaseRepository

class FestivalRepository(BaseRepository[Festival]):
    """Repository for Festival entity with custom queries."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Festival)
    
    async def get_by_name(self, name: str) -> Optional[Festival]:
        """Get festival by name."""
        result = await self.session.execute(
            select(Festival).where(Festival.name == name)
        )
        return result.scalar_one_or_none()
    
    async def get_upcoming_festivals(self, limit: int = 10) -> List[Festival]:
        """Get upcoming festivals ordered by date."""
        result = await self.session.execute(
            select(Festival)
            .where(Festival.date >= datetime.now())
            .order_by(Festival.date.asc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def search_festivals(
        self, 
        query: str, 
        skip: int = 0, 
        limit: int = 20
    ) -> List[Festival]:
        """Full-text search for festivals."""
        result = await self.session.execute(
            select(Festival)
            .where(Festival.name.ilike(f"%{query}%"))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
```

### Service Layer Pattern

**Service Interface (`services/festival_service.py`):**
```python
from typing import List, Optional
from datetime import datetime
from repositories.festival_repository import FestivalRepository
from repositories.artist_repository import ArtistRepository
from services.cache_service import CacheService
from models.festival import Festival

class FestivalService:
    """Business logic for festival operations."""
    
    def __init__(
        self,
        festival_repository: FestivalRepository,
        artist_repository: ArtistRepository,
        cache_service: CacheService
    ):
        self.festival_repo = festival_repository
        self.artist_repo = artist_repository
        self.cache = cache_service
    
    async def get_festival_by_id(self, festival_id: int) -> Optional[Festival]:
        """Get festival by ID with caching."""
        # Check cache first
        cache_key = f"festival:{festival_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached
        
        # Fetch from database
        festival = await self.festival_repo.get_by_id(festival_id)
        
        # Cache result
        if festival:
            await self.cache.set(cache_key, festival, ttl=3600)
        
        return festival
    
    async def create_festival(
        self, 
        name: str, 
        date: datetime, 
        location: str,
        artist_ids: List[int]
    ) -> Festival:
        """Create new festival with artists."""
        # Validate artists exist
        artists = await self.artist_repo.get_by_ids(artist_ids)
        if len(artists) != len(artist_ids):
            raise ValueError("One or more artists not found")
        
        # Create festival
        festival = Festival(name=name, date=date, location=location)
        festival.artists = artists
        
        # Save to database
        festival = await self.festival_repo.create(festival)
        
        # Invalidate related caches
        await self.cache.delete_pattern("festivals:*")
        
        return festival
    
    async def search_festivals(
        self, 
        query: str, 
        skip: int = 0, 
        limit: int = 20
    ) -> List[Festival]:
        """Search festivals with caching."""
        cache_key = f"festivals:search:{query}:{skip}:{limit}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached
        
        results = await self.festival_repo.search_festivals(query, skip, limit)
        await self.cache.set(cache_key, results, ttl=300)
        
        return results
```


### AWS Service Specifications

#### 1. Amazon ECS Fargate (Compute)

**API Service Configuration:**
```hcl
resource "aws_ecs_task_definition" "api" {
  family                   = "festival-api"
  requires_compatibilities = ["FARGATE"]
  network_mode            = "awsvpc"
  cpu                     = "256"  # 0.25 vCPU
  memory                  = "512"  # 0.5 GB
  execution_role_arn      = aws_iam_role.ecs_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn
  
  container_definitions = jsonencode([{
    name  = "api"
    image = "${aws_ecr_repository.app.repository_url}:latest"
    
    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]
    
    environment = [
      { name = "ENVIRONMENT", value = var.environment },
      { name = "AWS_REGION", value = var.aws_region }
    ]
    
    secrets = [
      {
        name      = "DATABASE_URL"
        valueFrom = "${aws_secretsmanager_secret.db_credentials.arn}:url::"
      },
      {
        name      = "REDIS_URL"
        valueFrom = "${aws_secretsmanager_secret.redis_url.arn}:url::"
      },
      {
        name      = "SPOTIFY_CLIENT_ID"
        valueFrom = "${aws_secretsmanager_secret.spotify.arn}:client_id::"
      },
      {
        name      = "SPOTIFY_CLIENT_SECRET"
        valueFrom = "${aws_secretsmanager_secret.spotify.arn}:client_secret::"
      }
    ]
    
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/festival-api"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }
    
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "festival-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true  # Required for internet access (no NAT)
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }
  
  # Auto-scaling configuration
  lifecycle {
    ignore_changes = [desired_count]
  }
  
  depends_on = [aws_lb_listener.https]
}

# Auto-scaling for API service
resource "aws_appautoscaling_target" "api" {
  max_capacity       = 4
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "api-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace
  
  target_tracking_scaling_policy_configuration {
    target_value       = 70.0
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
```

**Worker Service Configuration (Celery with Spot):**
```hcl
resource "aws_ecs_task_definition" "worker" {
  family                   = "festival-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode            = "awsvpc"
  cpu                     = "256"
  memory                  = "512"
  execution_role_arn      = aws_iam_role.ecs_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn
  
  container_definitions = jsonencode([{
    name    = "worker"
    image   = "${aws_ecr_repository.app.repository_url}:latest"
    command = ["celery", "-A", "app.celery_app", "worker", "--loglevel=info"]
    
    environment = [
      { name = "ENVIRONMENT", value = var.environment }
    ]
    
    secrets = [
      {
        name      = "DATABASE_URL"
        valueFrom = "${aws_secretsmanager_secret.db_credentials.arn}:url::"
      },
      {
        name      = "REDIS_URL"
        valueFrom = "${aws_secretsmanager_secret.redis_url.arn}:url::"
      }
    ]
    
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/festival-worker"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "worker"
      }
    }
  }])
}

resource "aws_ecs_service" "worker" {
  name            = "festival-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  
  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"  # 70% cost savings!
    weight            = 100
    base              = 0
  }
  
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }
  
  lifecycle {
    ignore_changes = [desired_count]
  }
}
```

#### 2. Amazon Aurora Serverless v2 (Database)

**Aurora Cluster Configuration:**
```hcl
resource "aws_rds_cluster" "main" {
  cluster_identifier      = "festival-db-${var.environment}"
  engine                  = "aurora-postgresql"
  engine_mode             = "provisioned"
  engine_version          = "15.3"
  database_name           = "festival"
  master_username         = "festival_admin"
  master_password         = random_password.db_password.result
  
  # Serverless v2 scaling
  serverlessv2_scaling_configuration {
    min_capacity = 0.5  # Minimum ACU (cheapest)
    max_capacity = 4.0  # Maximum ACU (can increase if needed)
  }
  
  # Network configuration
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  
  # Backup configuration
  backup_retention_period      = 7
  preferred_backup_window      = "03:00-04:00"
  preferred_maintenance_window = "mon:04:00-mon:05:00"
  
  # Snapshot configuration for daily teardown
  skip_final_snapshot       = false
  final_snapshot_identifier = "festival-db-final-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  snapshot_identifier       = var.restore_from_snapshot ? data.aws_db_cluster_snapshot.latest[0].id : null
  
  # Encryption
  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn
  
  # Enable auto-pause for dev environment (saves costs)
  dynamic "scaling_configuration" {
    for_each = var.environment == "dev" ? [1] : []
    content {
      auto_pause               = true
      seconds_until_auto_pause = 300  # 5 minutes
    }
  }
  
  # CloudWatch logging
  enabled_cloudwatch_logs_exports = ["postgresql"]
  
  tags = {
    Name        = "festival-db-${var.environment}"
    Environment = var.environment
    Terraform   = "true"
  }
}

resource "aws_rds_cluster_instance" "main" {
  count              = var.environment == "prod" ? 2 : 1  # Multi-AZ for prod
  identifier         = "festival-db-${var.environment}-${count.index}"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version
  
  performance_insights_enabled = true
  
  tags = {
    Name        = "festival-db-instance-${count.index}"
    Environment = var.environment
  }
}

# Data source to get latest snapshot for restore
data "aws_db_cluster_snapshot" "latest" {
  count                  = var.restore_from_snapshot ? 1 : 0
  db_cluster_identifier  = "festival-db-${var.environment}"
  most_recent            = true
  snapshot_type          = "manual"
}
```

**Database Subnet Group:**
```hcl
resource "aws_db_subnet_group" "main" {
  name       = "festival-db-subnet-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
  
  tags = {
    Name = "Festival DB subnet group"
  }
}
```

#### 3. Amazon ElastiCache Redis (Cache)

**Redis Cluster Configuration:**
```hcl
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "festival-redis-${var.environment}"
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = "cache.t4g.micro"  # Graviton2, cheapest option
  num_cache_nodes      = 1
  parameter_group_name = aws_elasticache_parameter_group.redis.name
  port                 = 6379
  
  # Network configuration
  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]
  
  # Snapshot configuration (optional, cache is ephemeral)
  snapshot_retention_limit = 0  # No snapshots needed for cache
  
  # Maintenance
  maintenance_window = "mon:05:00-mon:06:00"
  
  tags = {
    Name        = "festival-redis-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_elasticache_parameter_group" "redis" {
  name   = "festival-redis-params-${var.environment}"
  family = "redis7"
  
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"  # Evict least recently used keys
  }
  
  parameter {
    name  = "timeout"
    value = "300"
  }
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "festival-redis-subnet-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
  
  tags = {
    Name = "Festival Redis subnet group"
  }
}
```

#### 4. Application Load Balancer

**ALB Configuration:**
```hcl
resource "aws_lb" "main" {
  name               = "festival-alb-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  
  enable_deletion_protection = var.environment == "prod"
  enable_http2              = true
  enable_cross_zone_load_balancing = true
  
  tags = {
    Name        = "festival-alb-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_lb_target_group" "api" {
  name        = "festival-api-tg-${var.environment}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }
  
  deregistration_delay = 30
  
  tags = {
    Name = "festival-api-target-group"
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate.main.arn
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}
```


#### 5. Amazon S3 (Storage)

**S3 Buckets Configuration:**
```hcl
# Application data bucket
resource "aws_s3_bucket" "app_data" {
  bucket = "festival-app-data-${var.environment}-${data.aws_caller_identity.current.account_id}"
  
  lifecycle {
    prevent_destroy = true  # Never destroy this bucket
  }
  
  tags = {
    Name        = "festival-app-data"
    Environment = var.environment
    Persistent  = "true"  # Survives teardown
  }
}

resource "aws_s3_bucket_versioning" "app_data" {
  bucket = aws_s3_bucket.app_data.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_intelligent_tiering_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id
  name   = "EntireBucket"
  
  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90
  }
  
  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "app_data" {
  bucket = aws_s3_bucket.app_data.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Terraform state bucket
resource "aws_s3_bucket" "terraform_state" {
  bucket = "festival-terraform-state-${data.aws_caller_identity.current.account_id}"
  
  lifecycle {
    prevent_destroy = true  # Never destroy this bucket
  }
  
  tags = {
    Name       = "terraform-state"
    Persistent = "true"
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# CloudFront logs bucket
resource "aws_s3_bucket" "cloudfront_logs" {
  bucket = "festival-cloudfront-logs-${var.environment}-${data.aws_caller_identity.current.account_id}"
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = {
    Name        = "cloudfront-logs"
    Environment = var.environment
    Persistent  = "true"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id
  
  rule {
    id     = "delete-old-logs"
    status = "Enabled"
    
    expiration {
      days = 30
    }
  }
}
```

#### 6. Amazon CloudFront (CDN)

**CloudFront Distribution:**
```hcl
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Festival Playlist Generator CDN"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"  # US, Canada, Europe (cheapest)
  
  # Origin: ALB for API
  origin {
    domain_name = aws_lb.main.dns_name
    origin_id   = "alb"
    
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }
  
  # Origin: S3 for static assets
  origin {
    domain_name = aws_s3_bucket.app_data.bucket_regional_domain_name
    origin_id   = "s3"
    
    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.main.cloudfront_access_identity_path
    }
  }
  
  # Default cache behavior (API)
  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    target_origin_id       = "alb"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    
    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Host"]
      
      cookies {
        forward = "all"
      }
    }
    
    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }
  
  # Cache behavior for static assets
  ordered_cache_behavior {
    path_pattern           = "/static/*"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    target_origin_id       = "s3"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    
    forwarded_values {
      query_string = false
      
      cookies {
        forward = "none"
      }
    }
    
    min_ttl     = 0
    default_ttl = 86400   # 1 day
    max_ttl     = 31536000 # 1 year
  }
  
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  
  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.main.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
  
  logging_config {
    bucket = aws_s3_bucket.cloudfront_logs.bucket_domain_name
    prefix = "cloudfront/"
  }
  
  tags = {
    Name        = "festival-cdn"
    Environment = var.environment
  }
}

resource "aws_cloudfront_origin_access_identity" "main" {
  comment = "Festival app S3 access"
}
```

#### 7. AWS Secrets Manager

**Secrets Configuration:**
```hcl
# Database credentials
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "festival/db-credentials-${var.environment}"
  description             = "Database credentials for Festival app"
  recovery_window_in_days = 0  # Immediate deletion on destroy
  
  lifecycle {
    prevent_destroy = true  # Survives teardown
  }
  
  tags = {
    Name        = "db-credentials"
    Environment = var.environment
    Persistent  = "true"
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = aws_rds_cluster.main.master_username
    password = aws_rds_cluster.main.master_password
    host     = aws_rds_cluster.main.endpoint
    port     = aws_rds_cluster.main.port
    database = aws_rds_cluster.main.database_name
    url      = "postgresql://${aws_rds_cluster.main.master_username}:${aws_rds_cluster.main.master_password}@${aws_rds_cluster.main.endpoint}:${aws_rds_cluster.main.port}/${aws_rds_cluster.main.database_name}"
  })
}

# Redis URL
resource "aws_secretsmanager_secret" "redis_url" {
  name                    = "festival/redis-url-${var.environment}"
  description             = "Redis connection URL"
  recovery_window_in_days = 0
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = {
    Name        = "redis-url"
    Environment = var.environment
    Persistent  = "true"
  }
}

resource "aws_secretsmanager_secret_version" "redis_url" {
  secret_id = aws_secretsmanager_secret.redis_url.id
  secret_string = jsonencode({
    url = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.cache_nodes[0].port}"
  })
}

# Spotify API credentials (manually populated)
resource "aws_secretsmanager_secret" "spotify" {
  name                    = "festival/spotify-credentials-${var.environment}"
  description             = "Spotify API credentials"
  recovery_window_in_days = 0
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = {
    Name        = "spotify-credentials"
    Environment = var.environment
    Persistent  = "true"
  }
}

# Setlist.fm API credentials (manually populated)
resource "aws_secretsmanager_secret" "setlistfm" {
  name                    = "festival/setlistfm-credentials-${var.environment}"
  description             = "Setlist.fm API credentials"
  recovery_window_in_days = 0
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = {
    Name        = "setlistfm-credentials"
    Environment = var.environment
    Persistent  = "true"
  }
}

# JWT secret
resource "aws_secretsmanager_secret" "jwt_secret" {
  name                    = "festival/jwt-secret-${var.environment}"
  description             = "JWT signing secret"
  recovery_window_in_days = 0
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = {
    Name        = "jwt-secret"
    Environment = var.environment
    Persistent  = "true"
  }
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id = aws_secretsmanager_secret.jwt_secret.id
  secret_string = jsonencode({
    secret = random_password.jwt_secret.result
  })
}
```


## Data Models

### Database Schema

The existing database schema will be maintained with minimal changes. Key models include:

**Artist Model:**
```python
from sqlalchemy import Column, Integer, String, Text, DateTime, Table, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

# Association table for many-to-many relationship
festival_artists = Table(
    'festival_artists',
    Base.metadata,
    Column('festival_id', Integer, ForeignKey('festivals.id'), primary_key=True),
    Column('artist_id', Integer, ForeignKey('artists.id'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)
)

class Artist(Base):
    __tablename__ = 'artists'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    spotify_id = Column(String(255), unique=True, index=True)
    spotify_uri = Column(String(255))
    genres = Column(Text)  # JSON array stored as text
    popularity = Column(Integer)
    image_url = Column(String(512))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    festivals = relationship('Festival', secondary=festival_artists, back_populates='artists')
    setlists = relationship('Setlist', back_populates='artist')
    
    def __repr__(self):
        return f"<Artist(id={self.id}, name='{self.name}')>"
```

**Festival Model:**
```python
from sqlalchemy import Column, Integer, String, Text, Date, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class Festival(Base):
    __tablename__ = 'festivals'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    location = Column(String(255))
    date = Column(Date, index=True)
    description = Column(Text)
    website_url = Column(String(512))
    image_url = Column(String(512))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    artists = relationship('Artist', secondary=festival_artists, back_populates='festivals')
    playlists = relationship('Playlist', back_populates='festival')
    
    def __repr__(self):
        return f"<Festival(id={self.id}, name='{self.name}', date={self.date})>"
```

**Playlist Model:**
```python
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class Playlist(Base):
    __tablename__ = 'playlists'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    spotify_id = Column(String(255), unique=True, index=True)
    spotify_uri = Column(String(255))
    spotify_url = Column(String(512))
    is_public = Column(Boolean, default=True)
    
    # Foreign keys
    festival_id = Column(Integer, ForeignKey('festivals.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    festival = relationship('Festival', back_populates='playlists')
    user = relationship('User', back_populates='playlists')
    tracks = relationship('PlaylistTrack', back_populates='playlist', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Playlist(id={self.id}, name='{self.name}', festival_id={self.festival_id})>"
```

**User Model:**
```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    # Spotify integration
    spotify_user_id = Column(String(255), unique=True, index=True)
    spotify_access_token = Column(Text)
    spotify_refresh_token = Column(Text)
    spotify_token_expires_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime)
    
    # Relationships
    playlists = relationship('Playlist', back_populates='user')
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"
```

**Setlist Model:**
```python
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class Setlist(Base):
    __tablename__ = 'setlists'
    
    id = Column(Integer, primary_key=True, index=True)
    setlistfm_id = Column(String(255), unique=True, index=True)
    event_date = Column(Date, index=True)
    venue_name = Column(String(255))
    city = Column(String(255))
    country = Column(String(255))
    
    # Foreign keys
    artist_id = Column(Integer, ForeignKey('artists.id'), nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    artist = relationship('Artist', back_populates='setlists')
    songs = relationship('SetlistSong', back_populates='setlist', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Setlist(id={self.id}, artist_id={self.artist_id}, date={self.event_date})>"
```

### Database Indexes

**Performance-Critical Indexes:**
```sql
-- Artists
CREATE INDEX idx_artists_name ON artists(name);
CREATE INDEX idx_artists_spotify_id ON artists(spotify_id);
CREATE INDEX idx_artists_created_at ON artists(created_at);

-- Festivals
CREATE INDEX idx_festivals_name ON festivals(name);
CREATE INDEX idx_festivals_date ON festivals(date);
CREATE INDEX idx_festivals_location ON festivals(location);

-- Playlists
CREATE INDEX idx_playlists_festival_id ON playlists(festival_id);
CREATE INDEX idx_playlists_user_id ON playlists(user_id);
CREATE INDEX idx_playlists_spotify_id ON playlists(spotify_id);

-- Users
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_spotify_user_id ON users(spotify_user_id);

-- Setlists
CREATE INDEX idx_setlists_artist_id ON setlists(artist_id);
CREATE INDEX idx_setlists_event_date ON setlists(event_date);
CREATE INDEX idx_setlists_setlistfm_id ON setlists(setlistfm_id);

-- Full-text search indexes (PostgreSQL)
CREATE INDEX idx_artists_name_trgm ON artists USING gin(name gin_trgm_ops);
CREATE INDEX idx_festivals_name_trgm ON festivals USING gin(name gin_trgm_ops);
```

### Caching Strategy

**Redis Cache Keys:**
```python
# Cache key patterns
CACHE_KEYS = {
    'artist': 'artist:{artist_id}',
    'artist_by_spotify': 'artist:spotify:{spotify_id}',
    'festival': 'festival:{festival_id}',
    'festival_artists': 'festival:{festival_id}:artists',
    'playlist': 'playlist:{playlist_id}',
    'user': 'user:{user_id}',
    'user_playlists': 'user:{user_id}:playlists',
    'search_artists': 'search:artists:{query}:{skip}:{limit}',
    'search_festivals': 'search:festivals:{query}:{skip}:{limit}',
    'spotify_token': 'spotify:token:{user_id}',
}

# Cache TTLs (seconds)
CACHE_TTLS = {
    'artist': 3600,           # 1 hour
    'festival': 3600,         # 1 hour
    'playlist': 1800,         # 30 minutes
    'user': 1800,             # 30 minutes
    'search': 300,            # 5 minutes
    'spotify_token': 3000,    # 50 minutes (tokens expire in 60)
}
```

**Cache Service Implementation:**
```python
import json
import redis.asyncio as redis
from typing import Any, Optional
from datetime import timedelta

class CacheService:
    """Redis cache service for application data."""
    
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL."""
        serialized = json.dumps(value, default=str)
        return await self.redis.setex(key, ttl, serialized)
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        return await self.redis.delete(key) > 0
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        keys = await self.redis.keys(pattern)
        if keys:
            return await self.redis.delete(*keys)
        return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return await self.redis.exists(key) > 0
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter."""
        return await self.redis.incrby(key, amount)
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on existing key."""
        return await self.redis.expire(key, ttl)
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Clean Architecture Properties

**Property 1: Repository Layer Isolation**
*For any* controller or service class in the codebase, it should not contain direct SQLAlchemy session operations (session.query, session.add, session.commit, session.delete) - all database operations must go through repository classes.
**Validates: Requirements US-4.1, US-4.3**

**Property 2: Service Layer Framework Independence**
*For any* service class in the services/ directory, it should not import or depend on FastAPI, Starlette, or any other web framework-specific code - services must be framework-agnostic.
**Validates: Requirements US-4.6**

**Property 3: Controller Delegation**
*For any* controller endpoint function, it should delegate business logic to service layer methods and only handle HTTP concerns (request validation, response serialization, status codes, authentication).
**Validates: Requirements US-4.4**

### Infrastructure Security Properties

**Property 4: Security Group Zero-Trust**
*For any* security group defined in Terraform, the following rules must hold:
- ECS security group only accepts inbound traffic from ALB security group on port 8000
- RDS security group only accepts inbound traffic from ECS security group on port 5432
- Redis security group only accepts inbound traffic from ECS security group on port 6379
- ALB security group only accepts inbound traffic from 0.0.0.0/0 on ports 80 and 443
- No other security groups allow 0.0.0.0/0 inbound access
**Validates: Requirements US-6.1**

**Property 5: No Hardcoded Secrets**
*For any* Python file in the codebase, it should not contain hardcoded credentials, API keys, passwords, or tokens - all secrets must be loaded from environment variables or AWS Secrets Manager.
**Validates: Requirements US-6.2**

**Property 6: S3 Bucket Privacy**
*For any* S3 bucket defined in Terraform, it must have public access blocked (block_public_acls, block_public_policy, ignore_public_acls, restrict_public_buckets all set to true).
**Validates: Requirements US-6.9**

### Observability Properties

**Property 7: Structured Logging with Request Tracking**
*For any* log entry emitted by the application, it should be valid JSON and contain required fields: timestamp, level, message, request_id, service_name.
**Validates: Requirements US-5.1, US-5.7**

### Resilience Properties

**Property 8: External API Error Handling**
*For any* external API call (Spotify, Setlist.fm), if the API returns an error or times out, the system should handle it gracefully with circuit breaker pattern, return a meaningful error to the user, and not crash the application.
**Validates: Requirements US-7.6**

### Infrastructure Idempotence Properties

**Property 9: Terraform Idempotence**
*For any* Terraform configuration, running `terraform apply` multiple times without changes should result in "No changes" output and not modify any infrastructure.
**Validates: Requirements US-1.8**

### Cost Management Properties

**Property 10: Cost Allocation Tags**
*For any* AWS resource created by Terraform, it must have the required cost allocation tags: Environment, Application, Component, Tier, Project, ManagedBy.
**Validates: Requirements US-3.5**

**Property 11: Budget Configuration**
*For any* environment, AWS Budgets must be configured with at least three alert thresholds (80%, 100% actual, 100% forecasted) and Cost Anomaly Detection must be enabled with immediate alerts.
**Validates: Requirements US-3.6**

### Domain and Certificate Properties

**Property 12: SSL Certificate Validity**
*For any* public-facing endpoint (CloudFront, ALB), it must use a valid SSL/TLS certificate from AWS Certificate Manager with automatic renewal enabled and minimum TLS version 1.2.
**Validates: Requirements US-7.1, US-7.2**

**Property 13: Custom Domain Configuration**
*For any* environment, the custom domain (gig-prep.co.uk) must be configured with Route 53 DNS records pointing to CloudFront for the root domain and ALB for the API subdomain, with SSL certificates properly validated.
**Validates: Requirements US-7.3**


## Error Handling

### Application Error Handling Strategy

**Error Categories:**

1. **Client Errors (4xx)**
   - Invalid input data
   - Authentication failures
   - Authorization failures
   - Resource not found
   - Rate limiting

2. **Server Errors (5xx)**
   - Database connection failures
   - External API failures
   - Unexpected exceptions
   - Service unavailable

3. **External API Errors**
   - Spotify API failures
   - Setlist.fm API failures
   - Timeout errors
   - Rate limiting

**Error Response Format:**
```python
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class ErrorResponse(BaseModel):
    """Standardized error response format."""
    error: str
    message: str
    status_code: int
    request_id: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid festival date format",
                "status_code": 400,
                "request_id": "req_abc123",
                "timestamp": "2024-01-15T10:30:00Z",
                "details": {
                    "field": "date",
                    "expected": "YYYY-MM-DD"
                }
            }
        }
```

**Global Exception Handler:**
```python
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

def setup_exception_handlers(app: FastAPI):
    """Configure global exception handlers."""
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors."""
        request_id = request.state.request_id
        logger.error(
            "Validation error",
            extra={
                "request_id": request_id,
                "errors": exc.errors(),
                "body": exc.body
            }
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "ValidationError",
                "message": "Invalid request data",
                "status_code": 422,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "details": exc.errors()
            }
        )
    
    @app.exception_handler(SQLAlchemyError)
    async def database_exception_handler(request: Request, exc: SQLAlchemyError):
        """Handle database errors."""
        request_id = request.state.request_id
        logger.error(
            "Database error",
            extra={
                "request_id": request_id,
                "error": str(exc)
            },
            exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "DatabaseError",
                "message": "Database operation failed",
                "status_code": 503,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions."""
        request_id = request.state.request_id
        logger.error(
            "Unhandled exception",
            extra={
                "request_id": request_id,
                "error": str(exc),
                "type": type(exc).__name__
            },
            exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
                "status_code": 500,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
```

### Circuit Breaker Pattern for External APIs

**Circuit Breaker Implementation:**
```python
from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, Any
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreaker:
    """Circuit breaker for external API calls."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        recovery_timeout: int = 30
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass
```

**Usage in External API Service:**
```python
from services.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
import httpx
import logging

logger = logging.getLogger(__name__)

class SpotifyService:
    """Service for Spotify API integration with circuit breaker."""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60,
            recovery_timeout=30
        )
    
    async def search_artist(self, query: str) -> Optional[Dict]:
        """Search for artist with circuit breaker protection."""
        try:
            return await self.circuit_breaker.call(
                self._search_artist_internal,
                query
            )
        except CircuitBreakerOpenError:
            logger.warning(
                "Spotify API circuit breaker is open",
                extra={"query": query}
            )
            return None
        except Exception as e:
            logger.error(
                "Spotify API error",
                extra={"query": query, "error": str(e)},
                exc_info=True
            )
            return None
    
    async def _search_artist_internal(self, query: str) -> Dict:
        """Internal method for actual API call."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.spotify.com/v1/search",
                params={"q": query, "type": "artist"},
                headers={"Authorization": f"Bearer {await self.get_access_token()}"},
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
```

### Retry Strategy

**Exponential Backoff with Jitter:**
```python
import asyncio
import random
from typing import Callable, Any, Type
from functools import wraps

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """Decorator for retrying functions with exponential backoff."""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        raise
                    
                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = random.uniform(0, delay * 0.1)
                    total_delay = delay + jitter
                    
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{max_retries} after {total_delay:.2f}s",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "error": str(e)
                        }
                    )
                    
                    await asyncio.sleep(total_delay)
        
        return wrapper
    return decorator

# Usage example
@retry_with_backoff(max_retries=3, base_delay=1.0, exceptions=(httpx.HTTPError,))
async def fetch_setlist(setlist_id: str) -> Dict:
    """Fetch setlist from Setlist.fm API with retry."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.setlist.fm/rest/1.0/setlist/{setlist_id}",
            headers={"x-api-key": SETLISTFM_API_KEY},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()
```

### Database Transaction Management

**Transaction Context Manager:**
```python
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def transaction_context(session: AsyncSession):
    """Context manager for database transactions with automatic rollback."""
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(
            "Transaction rolled back",
            extra={"error": str(e)},
            exc_info=True
        )
        raise
    finally:
        await session.close()

# Usage example
async def create_festival_with_artists(
    festival_data: Dict,
    artist_ids: List[int],
    session: AsyncSession
) -> Festival:
    """Create festival with artists in a transaction."""
    async with transaction_context(session):
        # Create festival
        festival = Festival(**festival_data)
        session.add(festival)
        await session.flush()
        
        # Add artists
        artists = await session.execute(
            select(Artist).where(Artist.id.in_(artist_ids))
        )
        festival.artists = artists.scalars().all()
        
        return festival
```


## Testing Strategy

### Testing Pyramid

```
                    ┌─────────────┐
                    │   E2E Tests │  (10%)
                    │  Playwright │
                    └─────────────┘
                  ┌───────────────────┐
                  │ Integration Tests │  (30%)
                  │  API + Database   │
                  └───────────────────┘
              ┌─────────────────────────────┐
              │      Unit Tests             │  (60%)
              │  Repositories + Services    │
              └─────────────────────────────┘
```

### Unit Testing

**Test Framework:** pytest with pytest-asyncio

**Coverage Targets:**
- Repositories: 90%+
- Services: 85%+
- Controllers: 80%+
- Overall: 80%+

**Repository Tests Example:**
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from repositories.festival_repository import FestivalRepository
from models.festival import Festival
from datetime import date

@pytest.fixture
async def db_session():
    """Create test database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()

@pytest.fixture
def festival_repository(db_session):
    """Create festival repository instance."""
    return FestivalRepository(db_session)

@pytest.mark.asyncio
async def test_create_festival(festival_repository):
    """Test creating a festival."""
    festival = Festival(
        name="Coachella 2024",
        location="Indio, CA",
        date=date(2024, 4, 12)
    )
    
    created = await festival_repository.create(festival)
    
    assert created.id is not None
    assert created.name == "Coachella 2024"
    assert created.location == "Indio, CA"

@pytest.mark.asyncio
async def test_get_upcoming_festivals(festival_repository):
    """Test getting upcoming festivals."""
    # Create past festival
    past = Festival(name="Past Fest", date=date(2020, 1, 1))
    await festival_repository.create(past)
    
    # Create future festivals
    future1 = Festival(name="Future Fest 1", date=date(2025, 6, 1))
    future2 = Festival(name="Future Fest 2", date=date(2025, 7, 1))
    await festival_repository.create(future1)
    await festival_repository.create(future2)
    
    # Get upcoming
    upcoming = await festival_repository.get_upcoming_festivals(limit=10)
    
    assert len(upcoming) == 2
    assert upcoming[0].name == "Future Fest 1"
    assert upcoming[1].name == "Future Fest 2"
```

**Service Tests Example:**
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.festival_service import FestivalService
from repositories.festival_repository import FestivalRepository
from services.cache_service import CacheService

@pytest.fixture
def mock_festival_repo():
    """Create mock festival repository."""
    return AsyncMock(spec=FestivalRepository)

@pytest.fixture
def mock_cache():
    """Create mock cache service."""
    return AsyncMock(spec=CacheService)

@pytest.fixture
def festival_service(mock_festival_repo, mock_cache):
    """Create festival service with mocks."""
    return FestivalService(
        festival_repository=mock_festival_repo,
        cache_service=mock_cache
    )

@pytest.mark.asyncio
async def test_get_festival_by_id_cached(festival_service, mock_cache, mock_festival_repo):
    """Test getting festival from cache."""
    festival_id = 1
    cached_festival = Festival(id=festival_id, name="Cached Fest")
    
    mock_cache.get.return_value = cached_festival
    
    result = await festival_service.get_festival_by_id(festival_id)
    
    assert result == cached_festival
    mock_cache.get.assert_called_once_with(f"festival:{festival_id}")
    mock_festival_repo.get_by_id.assert_not_called()

@pytest.mark.asyncio
async def test_get_festival_by_id_not_cached(festival_service, mock_cache, mock_festival_repo):
    """Test getting festival from database when not cached."""
    festival_id = 1
    db_festival = Festival(id=festival_id, name="DB Fest")
    
    mock_cache.get.return_value = None
    mock_festival_repo.get_by_id.return_value = db_festival
    
    result = await festival_service.get_festival_by_id(festival_id)
    
    assert result == db_festival
    mock_cache.get.assert_called_once()
    mock_festival_repo.get_by_id.assert_called_once_with(festival_id)
    mock_cache.set.assert_called_once()
```

### Integration Testing

**Test Framework:** pytest with testcontainers

**Integration Test Setup:**
```python
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient
from main import app

@pytest.fixture(scope="session")
def postgres_container():
    """Start PostgreSQL container for tests."""
    with PostgresContainer("postgres:15") as postgres:
        yield postgres

@pytest.fixture(scope="session")
def redis_container():
    """Start Redis container for tests."""
    with RedisContainer("redis:7") as redis:
        yield redis

@pytest.fixture
async def test_db(postgres_container):
    """Create test database."""
    engine = create_async_engine(postgres_container.get_connection_url())
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield async_session
    
    await engine.dispose()

@pytest.fixture
async def test_client(test_db, redis_container):
    """Create test API client."""
    app.dependency_overrides[get_db] = lambda: test_db()
    app.dependency_overrides[get_redis] = lambda: redis_container.get_connection_url()
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_create_festival_endpoint(test_client):
    """Test creating festival via API."""
    response = await test_client.post(
        "/api/v1/festivals",
        json={
            "name": "Test Festival",
            "location": "Test City",
            "date": "2024-06-15"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Festival"
    assert data["id"] is not None

@pytest.mark.asyncio
async def test_search_festivals_endpoint(test_client):
    """Test searching festivals via API."""
    # Create test festivals
    await test_client.post("/api/v1/festivals", json={"name": "Rock Fest", "date": "2024-07-01"})
    await test_client.post("/api/v1/festivals", json={"name": "Jazz Fest", "date": "2024-08-01"})
    
    # Search
    response = await test_client.get("/api/v1/festivals/search?q=Rock")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Rock Fest"
```

### Property-Based Testing

**Test Framework:** hypothesis

**Property Test Configuration:**
- Minimum 100 iterations per test
- Each test references design document property
- Tag format: `# Feature: aws-enterprise-migration, Property N: [property text]`

**Property Test Examples:**
```python
import pytest
from hypothesis import given, strategies as st
from hypothesis import settings
from services.festival_service import FestivalService

# Feature: aws-enterprise-migration, Property 1: Repository Layer Isolation
@given(st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_no_direct_db_access_in_controllers(controller_code: str):
    """Property: Controllers should not contain direct database operations."""
    forbidden_patterns = [
        "session.query",
        "session.add",
        "session.commit",
        "session.delete",
        "session.execute"
    ]
    
    for pattern in forbidden_patterns:
        assert pattern not in controller_code, \
            f"Controller contains direct database access: {pattern}"

# Feature: aws-enterprise-migration, Property 2: Service Layer Framework Independence
@given(st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_services_framework_agnostic(service_code: str):
    """Property: Services should not import web framework code."""
    forbidden_imports = [
        "from fastapi",
        "import fastapi",
        "from starlette",
        "import starlette"
    ]
    
    for import_stmt in forbidden_imports:
        assert import_stmt not in service_code, \
            f"Service imports web framework: {import_stmt}"

# Feature: aws-enterprise-migration, Property 7: Structured Logging with Request Tracking
@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(st.text(), st.integers(), st.floats())
    )
)
@settings(max_examples=100)
def test_log_entries_are_valid_json(log_data: dict):
    """Property: All log entries should be valid JSON with required fields."""
    import json
    from core.logging import format_log_entry
    
    log_entry = format_log_entry(
        level="INFO",
        message="Test message",
        request_id="test_req_123",
        **log_data
    )
    
    # Should be valid JSON
    parsed = json.loads(log_entry)
    
    # Should contain required fields
    assert "timestamp" in parsed
    assert "level" in parsed
    assert "message" in parsed
    assert "request_id" in parsed
    assert "service_name" in parsed
```

### E2E Testing

**Test Framework:** Playwright

**E2E Test Example:**
```python
import pytest
from playwright.async_api import async_playwright

@pytest.mark.asyncio
async def test_create_festival_playlist_flow():
    """E2E test: User creates a festival playlist."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Navigate to app
        await page.goto("https://festival-app.example.com")
        
        # Login
        await page.click("text=Login")
        await page.fill("input[name=email]", "test@example.com")
        await page.fill("input[name=password]", "testpass123")
        await page.click("button[type=submit]")
        
        # Search for festival
        await page.fill("input[placeholder='Search festivals']", "Coachella")
        await page.click("button:has-text('Search')")
        
        # Select festival
        await page.click("text=Coachella 2024")
        
        # Create playlist
        await page.click("button:has-text('Create Playlist')")
        await page.wait_for_selector("text=Playlist created successfully")
        
        # Verify playlist exists
        await page.click("text=My Playlists")
        await page.wait_for_selector("text=Coachella 2024 Playlist")
        
        await browser.close()
```

### Load Testing

**Test Framework:** Locust

**Load Test Configuration:**
```python
from locust import HttpUser, task, between

class FestivalUser(HttpUser):
    """Simulated user for load testing."""
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login before starting tasks."""
        response = self.client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123"
        })
        self.token = response.json()["access_token"]
        self.client.headers["Authorization"] = f"Bearer {self.token}"
    
    @task(3)
    def search_festivals(self):
        """Search for festivals."""
        self.client.get("/api/v1/festivals/search?q=rock")
    
    @task(2)
    def get_festival(self):
        """Get festival details."""
        self.client.get("/api/v1/festivals/1")
    
    @task(1)
    def create_playlist(self):
        """Create a playlist."""
        self.client.post("/api/v1/playlists", json={
            "festival_id": 1,
            "name": "Test Playlist"
        })

# Run: locust -f load_test.py --host=https://api.example.com
# Target: 1,000 concurrent users
```

### Test Execution in CI/CD

**GitHub Actions Test Workflow:**
```yaml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run unit tests
        run: pytest tests/unit -v --cov=. --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
  
  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run integration tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test
          REDIS_URL: redis://localhost:6379
        run: pytest tests/integration -v
  
  property-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install hypothesis
      
      - name: Run property-based tests
        run: pytest tests/property -v --hypothesis-show-statistics
```


## CI/CD Pipeline Design

### Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CI/CD Pipeline Flow                                  │
│                                                                               │
│  Pull Request                                                                │
│       │                                                                       │
│       ├─> Lint & Format (black, isort, flake8)                              │
│       ├─> Type Check (mypy)                                                  │
│       ├─> Security Scan (bandit, safety)                                     │
│       ├─> Unit Tests (pytest)                                                │
│       ├─> Integration Tests (pytest + testcontainers)                        │
│       ├─> Property Tests (hypothesis)                                        │
│       ├─> Build Docker Image                                                 │
│       ├─> Terraform Validate                                                 │
│       ├─> Terraform Plan (comment on PR)                                     │
│       └─> Cost Estimate (Infracost comment)                                  │
│                                                                               │
│  Merge to Main                                                               │
│       │                                                                       │
│       ├─> Run All Tests                                                      │
│       ├─> Build & Push Docker Image to ECR                                   │
│       ├─> Terraform Apply (dev environment)                                  │
│       ├─> Run Smoke Tests                                                    │
│       └─> Notify (Slack/Discord)                                             │
│                                                                               │
│  Manual Trigger (Production)                                                 │
│       │                                                                       │
│       ├─> Manual Approval Required                                           │
│       ├─> Run All Tests                                                      │
│       ├─> Build & Push Docker Image                                          │
│       ├─> Terraform Plan (review required)                                   │
│       ├─> Blue-Green Deployment (ECS)                                        │
│       ├─> Run Smoke Tests                                                    │
│       ├─> Rollback on Failure                                                │
│       └─> Notify                                                             │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### GitHub Actions Workflows

**1. Pull Request Workflow (`.github/workflows/pr.yml`):**
```yaml
name: Pull Request Checks

on:
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: '3.11'

jobs:
  lint:
    name: Lint and Format
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          pip install black isort flake8 mypy
      
      - name: Run black
        run: black --check .
      
      - name: Run isort
        run: isort --check-only .
      
      - name: Run flake8
        run: flake8 . --max-line-length=100
      
      - name: Run mypy
        run: mypy . --ignore-missing-imports

  security:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          pip install bandit safety
      
      - name: Run bandit
        run: bandit -r . -f json -o bandit-report.json
      
      - name: Run safety
        run: safety check --json
      
      - name: Upload security reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: bandit-report.json

  test:
    name: Run Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Cache dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run unit tests
        run: pytest tests/unit -v --cov=. --cov-report=xml --cov-report=html
      
      - name: Run integration tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test
          REDIS_URL: redis://localhost:6379
        run: pytest tests/integration -v
      
      - name: Run property tests
        run: pytest tests/property -v --hypothesis-show-statistics
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: true

  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Build image
        uses: docker/build-push-action@v4
        with:
          context: .
          push: false
          tags: festival-app:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  terraform:
    name: Terraform Validate and Plan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.5.0
      
      - name: Terraform Format Check
        run: terraform fmt -check -recursive
        working-directory: terraform
      
      - name: Terraform Init
        run: terraform init
        working-directory: terraform
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
      
      - name: Terraform Validate
        run: terraform validate
        working-directory: terraform
      
      - name: Terraform Plan
        id: plan
        run: terraform plan -no-color -out=tfplan
        working-directory: terraform
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
      
      - name: Comment PR with Plan
        uses: actions/github-script@v6
        with:
          script: |
            const output = `#### Terraform Plan 📖
            \`\`\`
            ${{ steps.plan.outputs.stdout }}
            \`\`\`
            `;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            })

  cost-estimate:
    name: Cost Estimation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Infracost
        uses: infracost/actions/setup@v2
        with:
          api-key: ${{ secrets.INFRACOST_API_KEY }}
      
      - name: Generate cost estimate
        run: |
          infracost breakdown --path=terraform \
            --format=json \
            --out-file=/tmp/infracost.json
      
      - name: Post cost comment
        run: |
          infracost comment github --path=/tmp/infracost.json \
            --repo=$GITHUB_REPOSITORY \
            --github-token=${{ secrets.GITHUB_TOKEN }} \
            --pull-request=${{ github.event.pull_request.number }} \
            --behavior=update
```

**2. Deploy to Dev Workflow (`.github/workflows/deploy-dev.yml`):**
```yaml
name: Deploy to Dev

on:
  push:
    branches: [main]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: festival-app
  ENVIRONMENT: dev

jobs:
  test:
    name: Run All Tests
    runs-on: ubuntu-latest
    # ... (same as PR workflow test job)

  build-and-push:
    name: Build and Push to ECR
    needs: test
    runs-on: ubuntu-latest
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}
          tags: |
            type=sha,prefix=,format=short
            type=raw,value=latest
      
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    name: Deploy to Dev Environment
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.5.0
      
      - name: Terraform Init
        run: terraform init
        working-directory: terraform
      
      - name: Terraform Apply
        run: terraform apply -auto-approve -var="image_tag=${{ needs.build-and-push.outputs.image-tag }}"
        working-directory: terraform
      
      - name: Get ECS service name
        id: ecs
        run: |
          SERVICE_NAME=$(terraform output -raw ecs_service_name)
          CLUSTER_NAME=$(terraform output -raw ecs_cluster_name)
          echo "service_name=$SERVICE_NAME" >> $GITHUB_OUTPUT
          echo "cluster_name=$CLUSTER_NAME" >> $GITHUB_OUTPUT
        working-directory: terraform
      
      - name: Wait for ECS deployment
        run: |
          aws ecs wait services-stable \
            --cluster ${{ steps.ecs.outputs.cluster_name }} \
            --services ${{ steps.ecs.outputs.service_name }}
      
      - name: Run smoke tests
        run: |
          API_URL=$(terraform output -raw api_url)
          curl -f $API_URL/health || exit 1
        working-directory: terraform
      
      - name: Notify deployment
        if: always()
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Dev deployment ${{ job.status }}'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

**3. Deploy to Production Workflow (`.github/workflows/deploy-prod.yml`):**
```yaml
name: Deploy to Production

on:
  workflow_dispatch:
    inputs:
      image_tag:
        description: 'Docker image tag to deploy'
        required: true
        default: 'latest'

env:
  AWS_REGION: us-east-1
  ENVIRONMENT: prod

jobs:
  approval:
    name: Manual Approval
    runs-on: ubuntu-latest
    steps:
      - name: Wait for approval
        uses: trstringer/manual-approval@v1
        with:
          secret: ${{ github.TOKEN }}
          approvers: your-github-username
          minimum-approvals: 1
          issue-title: "Deploy to Production"
          issue-body: "Please approve deployment of ${{ github.event.inputs.image_tag }} to production"

  deploy:
    name: Deploy to Production
    needs: approval
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.5.0
      
      - name: Terraform Init
        run: terraform init
        working-directory: terraform
      
      - name: Terraform Plan
        id: plan
        run: terraform plan -var="image_tag=${{ github.event.inputs.image_tag }}" -out=tfplan
        working-directory: terraform
      
      - name: Terraform Apply
        run: terraform apply tfplan
        working-directory: terraform
      
      - name: Blue-Green Deployment
        run: |
          # ECS automatically handles blue-green with new task definition
          aws ecs update-service \
            --cluster $(terraform output -raw ecs_cluster_name) \
            --service $(terraform output -raw ecs_service_name) \
            --force-new-deployment
        working-directory: terraform
      
      - name: Wait for deployment
        run: |
          aws ecs wait services-stable \
            --cluster $(terraform output -raw ecs_cluster_name) \
            --services $(terraform output -raw ecs_service_name)
        working-directory: terraform
      
      - name: Run smoke tests
        id: smoke
        run: |
          API_URL=$(terraform output -raw api_url)
          curl -f $API_URL/health || exit 1
          curl -f $API_URL/api/v1/festivals || exit 1
        working-directory: terraform
      
      - name: Rollback on failure
        if: failure() && steps.smoke.outcome == 'failure'
        run: |
          echo "Smoke tests failed, rolling back..."
          # Get previous task definition
          PREVIOUS_TASK_DEF=$(aws ecs describe-services \
            --cluster $(terraform output -raw ecs_cluster_name) \
            --services $(terraform output -raw ecs_service_name) \
            --query 'services[0].deployments[1].taskDefinition' \
            --output text)
          
          # Update service to previous task definition
          aws ecs update-service \
            --cluster $(terraform output -raw ecs_cluster_name) \
            --service $(terraform output -raw ecs_service_name) \
            --task-definition $PREVIOUS_TASK_DEF
        working-directory: terraform
      
      - name: Notify deployment
        if: always()
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Production deployment ${{ job.status }}'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```


## Teardown/Rebuild Workflow

### Daily Teardown/Rebuild Strategy

**Goal:** Minimize costs by destroying infrastructure when not in use, while maintaining data persistence and fast rebuild capability.

### Teardown Script (`scripts/teardown.sh`)

```bash
#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

echo "========================================="
echo "Festival App Infrastructure Teardown"
echo "Environment: $ENVIRONMENT"
echo "Timestamp: $TIMESTAMP"
echo "========================================="

# Step 1: Create database snapshot
echo "Step 1/4: Creating database snapshot..."
cd terraform

# Get RDS cluster identifier
CLUSTER_ID=$(terraform output -raw rds_cluster_id)

if [ -n "$CLUSTER_ID" ]; then
    echo "Creating snapshot for cluster: $CLUSTER_ID"
    
    aws rds create-db-cluster-snapshot \
        --db-cluster-identifier "$CLUSTER_ID" \
        --db-cluster-snapshot-identifier "festival-${ENVIRONMENT}-snapshot-${TIMESTAMP}" \
        --tags Key=Environment,Value=$ENVIRONMENT Key=AutomatedSnapshot,Value=true
    
    echo "Waiting for snapshot to complete..."
    aws rds wait db-cluster-snapshot-available \
        --db-cluster-snapshot-identifier "festival-${ENVIRONMENT}-snapshot-${TIMESTAMP}"
    
    echo "✓ Snapshot created successfully"
else
    echo "⚠ No RDS cluster found, skipping snapshot"
fi

# Step 2: Terraform destroy (excludes persistent resources)
echo ""
echo "Step 2/4: Destroying infrastructure with Terraform..."
echo "Note: S3 buckets, Secrets Manager, and ECR will be preserved"

terraform destroy \
    -auto-approve \
    -var="environment=$ENVIRONMENT" \
    -target=aws_ecs_service.api \
    -target=aws_ecs_service.worker \
    -target=aws_ecs_task_definition.api \
    -target=aws_ecs_task_definition.worker \
    -target=aws_lb.main \
    -target=aws_lb_target_group.api \
    -target=aws_lb_listener.https \
    -target=aws_lb_listener.http \
    -target=aws_rds_cluster.main \
    -target=aws_rds_cluster_instance.main \
    -target=aws_elasticache_cluster.redis \
    -target=aws_cloudfront_distribution.main

echo "✓ Infrastructure destroyed"

# Step 3: Verify destruction
echo ""
echo "Step 3/4: Verifying destruction..."

# Check ECS services
ECS_SERVICES=$(aws ecs list-services --cluster festival-$ENVIRONMENT --query 'serviceArns' --output text)
if [ -z "$ECS_SERVICES" ]; then
    echo "✓ ECS services destroyed"
else
    echo "⚠ Warning: Some ECS services still exist"
fi

# Check RDS clusters
RDS_CLUSTERS=$(aws rds describe-db-clusters --query "DBClusters[?DBClusterIdentifier=='$CLUSTER_ID'].DBClusterIdentifier" --output text)
if [ -z "$RDS_CLUSTERS" ]; then
    echo "✓ RDS cluster destroyed"
else
    echo "⚠ Warning: RDS cluster still exists"
fi

# Step 4: Calculate cost savings
echo ""
echo "Step 4/4: Cost summary..."
echo "========================================="
echo "Resources Destroyed:"
echo "  - ECS Fargate tasks (API + Worker)"
echo "  - Application Load Balancer"
echo "  - Aurora Serverless v2 cluster"
echo "  - ElastiCache Redis cluster"
echo "  - CloudFront distribution"
echo ""
echo "Resources Preserved:"
echo "  - S3 buckets (app data, logs, Terraform state)"
echo "  - Secrets Manager secrets"
echo "  - ECR container images"
echo "  - RDS snapshots (latest: festival-${ENVIRONMENT}-snapshot-${TIMESTAMP})"
echo ""
echo "Estimated monthly savings: \$8-10/month"
echo "Estimated cost while torn down: \$2-5/month"
echo "========================================="

# Step 5: Cleanup old snapshots (keep last 7 days)
echo ""
echo "Cleaning up old snapshots (keeping last 7 days)..."
SEVEN_DAYS_AGO=$(date -d '7 days ago' +%Y%m%d)

aws rds describe-db-cluster-snapshots \
    --query "DBClusterSnapshots[?starts_with(DBClusterSnapshotIdentifier, 'festival-${ENVIRONMENT}-snapshot-')].DBClusterSnapshotIdentifier" \
    --output text | tr '\t' '\n' | while read snapshot; do
    
    SNAPSHOT_DATE=$(echo $snapshot | grep -oP '\d{8}' | head -1)
    
    if [ "$SNAPSHOT_DATE" -lt "$SEVEN_DAYS_AGO" ]; then
        echo "Deleting old snapshot: $snapshot"
        aws rds delete-db-cluster-snapshot --db-cluster-snapshot-identifier "$snapshot" || true
    fi
done

echo ""
echo "✓ Teardown complete!"
echo "Teardown time: $(date)"
echo ""
echo "To rebuild: ./scripts/provision.sh $ENVIRONMENT"
```

### Provision Script (`scripts/provision.sh`)

```bash
#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}
START_TIME=$(date +%s)

echo "========================================="
echo "Festival App Infrastructure Provision"
echo "Environment: $ENVIRONMENT"
echo "Start time: $(date)"
echo "========================================="

cd terraform

# Step 1: Find latest snapshot
echo "Step 1/5: Finding latest database snapshot..."

LATEST_SNAPSHOT=$(aws rds describe-db-cluster-snapshots \
    --query "reverse(sort_by(DBClusterSnapshots[?starts_with(DBClusterSnapshotIdentifier, 'festival-${ENVIRONMENT}-snapshot-')], &SnapshotCreateTime))[0].DBClusterSnapshotIdentifier" \
    --output text)

if [ "$LATEST_SNAPSHOT" != "None" ] && [ -n "$LATEST_SNAPSHOT" ]; then
    echo "✓ Found snapshot: $LATEST_SNAPSHOT"
    RESTORE_FROM_SNAPSHOT=true
else
    echo "⚠ No snapshot found, will create fresh database"
    RESTORE_FROM_SNAPSHOT=false
fi

# Step 2: Terraform init
echo ""
echo "Step 2/5: Initializing Terraform..."
terraform init

# Step 3: Terraform plan
echo ""
echo "Step 3/5: Planning infrastructure..."
if [ "$RESTORE_FROM_SNAPSHOT" = true ]; then
    terraform plan \
        -var="environment=$ENVIRONMENT" \
        -var="restore_from_snapshot=true" \
        -var="snapshot_identifier=$LATEST_SNAPSHOT" \
        -out=tfplan
else
    terraform plan \
        -var="environment=$ENVIRONMENT" \
        -var="restore_from_snapshot=false" \
        -out=tfplan
fi

# Step 4: Terraform apply
echo ""
echo "Step 4/5: Applying infrastructure..."
terraform apply tfplan

echo "✓ Infrastructure provisioned"

# Step 5: Wait for services to be healthy
echo ""
echo "Step 5/5: Waiting for services to be healthy..."

# Get outputs
ECS_CLUSTER=$(terraform output -raw ecs_cluster_name)
ECS_SERVICE=$(terraform output -raw ecs_service_name)
API_URL=$(terraform output -raw api_url)

echo "Waiting for ECS service to stabilize..."
aws ecs wait services-stable \
    --cluster "$ECS_CLUSTER" \
    --services "$ECS_SERVICE"

echo "✓ ECS service is stable"

# Health check
echo ""
echo "Running health checks..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f -s "$API_URL/health" > /dev/null; then
        echo "✓ API health check passed"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Health check attempt $RETRY_COUNT/$MAX_RETRIES..."
    sleep 10
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "✗ Health check failed after $MAX_RETRIES attempts"
    exit 1
fi

# Calculate provision time
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo ""
echo "========================================="
echo "✓ Provision complete!"
echo "Environment: $ENVIRONMENT"
echo "Provision time: ${MINUTES}m ${SECONDS}s"
echo ""
echo "API URL: $API_URL"
echo "CloudWatch Logs: /ecs/festival-api"
echo ""
echo "Next steps:"
echo "  1. Verify application: curl $API_URL/health"
echo "  2. View logs: aws logs tail /ecs/festival-api --follow"
echo "  3. Monitor costs: aws ce get-cost-and-usage --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d)"
echo "========================================="
```

### Automated Teardown/Provision with GitHub Actions

**Scheduled Teardown Workflow (`.github/workflows/scheduled-teardown.yml`):**
```yaml
name: Scheduled Teardown

on:
  schedule:
    # Run at 6 PM EST (11 PM UTC) on weekdays
    - cron: '0 23 * * 1-5'
  workflow_dispatch:  # Allow manual trigger

jobs:
  teardown:
    name: Teardown Dev Environment
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.5.0
      
      - name: Run teardown script
        run: ./scripts/teardown.sh dev
      
      - name: Notify completion
        if: always()
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Dev environment teardown ${{ job.status }}'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

**Scheduled Provision Workflow (`.github/workflows/scheduled-provision.yml`):**
```yaml
name: Scheduled Provision

on:
  schedule:
    # Run at 9 AM EST (2 PM UTC) on weekdays
    - cron: '0 14 * * 1-5'
  workflow_dispatch:  # Allow manual trigger

jobs:
  provision:
    name: Provision Dev Environment
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.5.0
      
      - name: Run provision script
        run: ./scripts/provision.sh dev
      
      - name: Notify completion
        if: always()
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Dev environment provision ${{ job.status }} - API: ${{ steps.provision.outputs.api_url }}'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### Cost Tracking Script (`scripts/cost-report.sh`)

```bash
#!/bin/bash

ENVIRONMENT=${1:-dev}
START_DATE=$(date -d '1 month ago' +%Y-%m-%d)
END_DATE=$(date +%Y-%m-%d)

echo "========================================="
echo "AWS Cost Report"
echo "Environment: $ENVIRONMENT"
echo "Period: $START_DATE to $END_DATE"
echo "========================================="

# Get cost by service
aws ce get-cost-and-usage \
    --time-period Start=$START_DATE,End=$END_DATE \
    --granularity MONTHLY \
    --metrics "UnblendedCost" \
    --group-by Type=DIMENSION,Key=SERVICE \
    --filter file://<(cat <<EOF
{
  "Tags": {
    "Key": "Environment",
    "Values": ["$ENVIRONMENT"]
  }
}
EOF
) \
    --query 'ResultsByTime[0].Groups[*].[Keys[0], Metrics.UnblendedCost.Amount]' \
    --output table

echo ""
echo "Total cost:"
aws ce get-cost-and-usage \
    --time-period Start=$START_DATE,End=$END_DATE \
    --granularity MONTHLY \
    --metrics "UnblendedCost" \
    --filter file://<(cat <<EOF
{
  "Tags": {
    "Key": "Environment",
    "Values": ["$ENVIRONMENT"]
  }
}
EOF
) \
    --query 'ResultsByTime[0].Total.UnblendedCost.Amount' \
    --output text

echo ""
echo "Cost breakdown by day:"
aws ce get-cost-and-usage \
    --time-period Start=$START_DATE,End=$END_DATE \
    --granularity DAILY \
    --metrics "UnblendedCost" \
    --filter file://<(cat <<EOF
{
  "Tags": {
    "Key": "Environment",
    "Values": ["$ENVIRONMENT"]
  }
}
EOF
) \
    --query 'ResultsByTime[*].[TimePeriod.Start, Total.UnblendedCost.Amount]' \
    --output table
```


## Monitoring and Observability

### CloudWatch Logging Architecture

**Log Groups:**
```
/ecs/festival-api          - API service logs
/ecs/festival-worker       - Worker service logs
/aws/rds/cluster/festival  - Database logs
/aws/elasticache/redis     - Redis logs
/aws/lambda/migrations     - Database migration logs
/aws/codedeploy            - Deployment logs
```

**Structured Logging Configuration:**
```python
import logging
import json
from datetime import datetime
from typing import Any, Dict
import traceback
from contextvars import ContextVar

# Context variable for request ID
request_id_var: ContextVar[str] = ContextVar('request_id', default='')

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'service_name': self.service_name,
            'message': record.getMessage(),
            'request_id': request_id_var.get(),
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add extra fields
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data)

def setup_logging(service_name: str, log_level: str = 'INFO'):
    """Configure structured logging."""
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add JSON handler
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter(service_name))
    logger.addHandler(handler)
    
    return logger

# FastAPI middleware for request ID
from fastapi import Request
import uuid

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all logs."""
    request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    request_id_var.set(request_id)
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    
    return response
```

### CloudWatch Metrics

**Custom Metrics Configuration:**
```python
import boto3
from datetime import datetime
from typing import Dict, List

class MetricsClient:
    """Client for publishing custom CloudWatch metrics."""
    
    def __init__(self, namespace: str = 'FestivalApp'):
        self.cloudwatch = boto3.client('cloudwatch')
        self.namespace = namespace
    
    def put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = 'Count',
        dimensions: Dict[str, str] = None
    ):
        """Publish a single metric."""
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Timestamp': datetime.utcnow()
        }
        
        if dimensions:
            metric_data['Dimensions'] = [
                {'Name': k, 'Value': v} for k, v in dimensions.items()
            ]
        
        self.cloudwatch.put_metric_data(
            Namespace=self.namespace,
            MetricData=[metric_data]
        )
    
    def put_metrics_batch(self, metrics: List[Dict]):
        """Publish multiple metrics in a batch."""
        self.cloudwatch.put_metric_data(
            Namespace=self.namespace,
            MetricData=metrics
        )

# Usage in application
metrics = MetricsClient()

# Track API requests
@app.middleware("http")
async def track_requests(request: Request, call_next):
    """Track request metrics."""
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    
    # Publish metrics
    metrics.put_metric(
        'APIRequest',
        1,
        unit='Count',
        dimensions={
            'Endpoint': request.url.path,
            'Method': request.method,
            'StatusCode': str(response.status_code)
        }
    )
    
    metrics.put_metric(
        'APILatency',
        duration * 1000,  # Convert to milliseconds
        unit='Milliseconds',
        dimensions={
            'Endpoint': request.url.path,
            'Method': request.method
        }
    )
    
    return response
```

**Key Metrics to Track:**
```
Application Metrics:
- APIRequest (Count) - Total API requests
- APILatency (Milliseconds) - API response time
- APIError (Count) - API errors by status code
- DatabaseQuery (Count) - Database queries executed
- DatabaseLatency (Milliseconds) - Database query time
- CacheHit (Count) - Cache hits
- CacheMiss (Count) - Cache misses
- ExternalAPICall (Count) - External API calls
- ExternalAPILatency (Milliseconds) - External API response time
- ExternalAPIError (Count) - External API errors

Business Metrics:
- FestivalCreated (Count) - Festivals created
- PlaylistCreated (Count) - Playlists created
- UserRegistered (Count) - New user registrations
- SpotifySync (Count) - Spotify syncs performed
- SetlistFetch (Count) - Setlists fetched

Infrastructure Metrics (AWS-provided):
- ECS CPU/Memory utilization
- RDS CPU/Memory/Connections
- Redis CPU/Memory/Connections
- ALB Request count/Latency/Errors
- CloudFront Requests/Bytes transferred
```

### CloudWatch Alarms

**Terraform Alarm Configuration:**
```hcl
# API Error Rate Alarm
resource "aws_cloudwatch_metric_alarm" "api_error_rate" {
  alarm_name          = "festival-api-error-rate-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "5XXError"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "API error rate is too high"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  
  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }
}

# API Latency Alarm
resource "aws_cloudwatch_metric_alarm" "api_latency" {
  alarm_name          = "festival-api-latency-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Average"
  threshold           = "0.5"  # 500ms
  alarm_description   = "API latency is too high"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  
  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }
}

# Database CPU Alarm
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "festival-rds-cpu-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "RDS CPU utilization is too high"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  
  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  }
}

# Database Connections Alarm
resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  alarm_name          = "festival-rds-connections-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "RDS connection count is too high"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  
  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  }
}

# ECS CPU Alarm
resource "aws_cloudwatch_metric_alarm" "ecs_cpu" {
  alarm_name          = "festival-ecs-cpu-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "ECS CPU utilization is too high"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  
  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.api.name
  }
}

# Cost Alarm
resource "aws_cloudwatch_metric_alarm" "cost_alarm" {
  alarm_name          = "festival-cost-alert-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "21600"  # 6 hours
  statistic           = "Maximum"
  threshold           = var.environment == "dev" ? "15" : "50"
  alarm_description   = "AWS costs are approaching budget limit"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  
  dimensions = {
    Currency = "USD"
  }
}

# SNS Topic for Alerts
resource "aws_sns_topic" "alerts" {
  name = "festival-alerts-${var.environment}"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
```

### AWS X-Ray Tracing

**X-Ray Configuration:**
```python
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.ext.flask.middleware import XRayMiddleware
from aws_xray_sdk.core import patch_all

# Configure X-Ray
xray_recorder.configure(
    service='festival-api',
    sampling=True,
    context_missing='LOG_ERROR'
)

# Patch libraries for automatic tracing
patch_all()

# Add X-Ray middleware to FastAPI
from fastapi import FastAPI
from aws_xray_sdk.ext.aiohttp.middleware import XRayMiddleware as AsyncXRayMiddleware

app = FastAPI()
app.add_middleware(AsyncXRayMiddleware, recorder=xray_recorder)

# Manual subsegment creation
from aws_xray_sdk.core import xray_recorder

@xray_recorder.capture('fetch_spotify_artist')
async def fetch_spotify_artist(artist_id: str):
    """Fetch artist from Spotify with X-Ray tracing."""
    # Add metadata
    xray_recorder.current_subsegment().put_metadata('artist_id', artist_id)
    
    try:
        # Make API call
        result = await spotify_client.get_artist(artist_id)
        
        # Add annotation for filtering
        xray_recorder.current_subsegment().put_annotation('spotify_success', True)
        
        return result
    except Exception as e:
        xray_recorder.current_subsegment().put_annotation('spotify_success', False)
        xray_recorder.current_subsegment().put_metadata('error', str(e))
        raise
```

### CloudWatch Dashboards

**Dashboard Configuration (Terraform):**
```hcl
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "festival-app-${var.environment}"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", { stat = "Sum", label = "Requests" }],
            [".", "TargetResponseTime", { stat = "Average", label = "Latency (avg)" }],
            [".", "HTTPCode_Target_5XX_Count", { stat = "Sum", label = "5XX Errors" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "API Performance"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", { stat = "Average", label = "CPU %" }],
            [".", "DatabaseConnections", { stat = "Average", label = "Connections" }],
            [".", "ReadLatency", { stat = "Average", label = "Read Latency" }],
            [".", "WriteLatency", { stat = "Average", label = "Write Latency" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Database Performance"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", { stat = "Average", label = "CPU %" }],
            [".", "MemoryUtilization", { stat = "Average", label = "Memory %" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "ECS Performance"
        }
      },
      {
        type = "log"
        properties = {
          query   = "SOURCE '/ecs/festival-api' | fields @timestamp, level, message, request_id | filter level = 'ERROR' | sort @timestamp desc | limit 20"
          region  = var.aws_region
          title   = "Recent Errors"
        }
      }
    ]
  })
}
```

### Log Insights Queries

**Useful CloudWatch Insights Queries:**

```
# Top 10 slowest API endpoints
fields @timestamp, request_id, endpoint, latency
| filter level = "INFO" and endpoint != ""
| sort latency desc
| limit 10

# Error rate by endpoint
fields endpoint, level
| filter level = "ERROR"
| stats count() as error_count by endpoint
| sort error_count desc

# Request volume by hour
fields @timestamp
| stats count() as request_count by bin(1h)

# Database query performance
fields @timestamp, query, duration
| filter query != ""
| stats avg(duration) as avg_duration, max(duration) as max_duration, count() as query_count by query
| sort avg_duration desc

# External API failures
fields @timestamp, service, error
| filter service in ["spotify", "setlistfm"] and level = "ERROR"
| stats count() as failure_count by service

# Cache hit rate
fields @timestamp, cache_key, cache_hit
| stats sum(cache_hit) as hits, count() as total
| extend hit_rate = hits / total * 100
```


## Terraform Module Structure

### Module Organization

```
terraform/
├── main.tf                      # Root module
├── variables.tf                 # Input variables
├── outputs.tf                   # Output values
├── backend.tf                   # S3 backend configuration
├── terraform.tfvars             # Variable values
├── versions.tf                  # Provider versions
│
├── modules/
│   ├── networking/              # VPC, subnets, security groups
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md
│   │
│   ├── database/                # Aurora Serverless v2
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md
│   │
│   ├── cache/                   # ElastiCache Redis
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md
│   │
│   ├── compute/                 # ECS Fargate
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md
│   │
│   ├── storage/                 # S3 buckets
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md
│   │
│   ├── cdn/                     # CloudFront
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md
│   │
│   ├── monitoring/              # CloudWatch, X-Ray
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md
│   │
│   └── security/                # WAF, Secrets Manager
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── README.md
│
└── scripts/
    ├── init-backend.sh          # Initialize S3 + DynamoDB
    ├── teardown.sh              # Snapshot DB + terraform destroy
    ├── provision.sh             # Terraform apply + restore
    └── cost-report.sh           # AWS cost analysis
```

### Root Module Example (`terraform/main.tf`)

```hcl
terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
  
  backend "s3" {
    bucket         = "festival-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "festival-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "Festival Playlist Generator"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

# Networking module
module "networking" {
  source = "./modules/networking"
  
  environment         = var.environment
  vpc_cidr            = var.vpc_cidr
  availability_zones  = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnet_cidrs = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
}

# Database module
module "database" {
  source = "./modules/database"
  
  environment             = var.environment
  vpc_id                  = module.networking.vpc_id
  private_subnet_ids      = module.networking.private_subnet_ids
  database_security_group_id = module.networking.database_security_group_id
  restore_from_snapshot   = var.restore_from_snapshot
  snapshot_identifier     = var.snapshot_identifier
}

# Cache module
module "cache" {
  source = "./modules/cache"
  
  environment            = var.environment
  vpc_id                 = module.networking.vpc_id
  private_subnet_ids     = module.networking.private_subnet_ids
  cache_security_group_id = module.networking.cache_security_group_id
}

# Compute module
module "compute" {
  source = "./modules/compute"
  
  environment              = var.environment
  vpc_id                   = module.networking.vpc_id
  public_subnet_ids        = module.networking.public_subnet_ids
  ecs_security_group_id    = module.networking.ecs_security_group_id
  alb_target_group_arn     = module.networking.alb_target_group_arn
  database_url             = module.database.connection_url
  redis_url                = module.cache.connection_url
  image_tag                = var.image_tag
}

# Storage module
module "storage" {
  source = "./modules/storage"
  
  environment = var.environment
}

# CDN module
module "cdn" {
  source = "./modules/cdn"
  
  environment        = var.environment
  alb_dns_name       = module.networking.alb_dns_name
  s3_bucket_id       = module.storage.app_data_bucket_id
  s3_bucket_domain   = module.storage.app_data_bucket_domain
  logs_bucket_domain = module.storage.logs_bucket_domain
}

# Monitoring module
module "monitoring" {
  source = "./modules/monitoring"
  
  environment       = var.environment
  alb_arn_suffix    = module.networking.alb_arn_suffix
  ecs_cluster_name  = module.compute.ecs_cluster_name
  ecs_service_name  = module.compute.ecs_service_name
  rds_cluster_id    = module.database.cluster_id
  alert_email       = var.alert_email
}

# Security module
module "security" {
  source = "./modules/security"
  
  environment         = var.environment
  alb_arn             = module.networking.alb_arn
  database_credentials = module.database.master_credentials
  redis_url           = module.cache.connection_url
}
```

### Variables Configuration (`terraform/variables.tf`)

```hcl
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod"
  }
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "Private subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "restore_from_snapshot" {
  description = "Whether to restore database from snapshot"
  type        = bool
  default     = false
}

variable "snapshot_identifier" {
  description = "RDS snapshot identifier to restore from"
  type        = string
  default     = null
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "alert_email" {
  description = "Email address for CloudWatch alarms"
  type        = string
}
```

### Outputs Configuration (`terraform/outputs.tf`)

```hcl
output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = module.networking.alb_dns_name
}

output "api_url" {
  description = "API URL"
  value       = "https://${module.networking.alb_dns_name}"
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain"
  value       = module.cdn.cloudfront_domain
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.compute.ecs_cluster_name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = module.compute.ecs_service_name
}

output "rds_cluster_id" {
  description = "RDS cluster identifier"
  value       = module.database.cluster_id
}

output "rds_endpoint" {
  description = "RDS cluster endpoint"
  value       = module.database.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = module.cache.endpoint
  sensitive   = true
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = module.compute.ecr_repository_url
}
```

## Migration Execution Plan

### Week 1: Foundation & Architecture (Days 1-7)

**Day 1-2: AWS Account Setup & Terraform Foundation**
- Create AWS account with billing alerts
- Set up IAM users and roles
- Initialize Terraform project structure
- Create S3 bucket and DynamoDB table for Terraform state
- Set up GitHub repository with branch protection

**Day 3-4: Repository Layer Implementation**
- Create BaseRepository abstract class
- Implement FestivalRepository
- Implement PlaylistRepository
- Implement SetlistRepository
- Implement UserRepository
- Write unit tests for all repositories (target: 90% coverage)

**Day 5-6: Service Layer Implementation**
- Create service interfaces with dependency injection
- Implement ArtistService
- Implement FestivalService
- Implement PlaylistService
- Implement CacheService
- Write unit tests for all services (target: 85% coverage)

**Day 7: CI/CD Pipeline Setup**
- Create GitHub Actions workflows (PR checks, tests)
- Set up code quality tools (black, isort, flake8, mypy)
- Configure security scanning (bandit, safety)
- Verify all tests pass in CI

**Deliverables:**
- ✅ AWS account configured with billing alerts
- ✅ Terraform project initialized with S3 backend
- ✅ All repository classes implemented and tested
- ✅ All service classes implemented and tested
- ✅ CI pipeline running successfully
- ✅ 80%+ test coverage achieved

### Week 2: Infrastructure Provisioning (Days 8-14)

**Day 8-9: Networking Infrastructure**
- Create VPC module (VPC, subnets, IGW, route tables)
- Create security groups module (ALB, ECS, RDS, Redis)
- Create VPC endpoints (S3, ECR, CloudWatch, Secrets Manager)
- Test networking module in isolation

**Day 10-11: Database & Cache Infrastructure**
- Create Aurora Serverless v2 module
- Create ElastiCache Redis module
- Configure automated backups
- Test database connectivity
- Test snapshot/restore functionality

**Day 12-13: Compute & Load Balancer Infrastructure**
- Create ECS cluster and task definitions
- Create ALB with target groups and listeners
- Create ECR repository
- Configure auto-scaling policies
- Test ECS task deployment

**Day 14: Storage & Monitoring Infrastructure**
- Create S3 buckets (app data, logs, Terraform state)
- Create CloudWatch log groups and alarms
- Create CloudWatch dashboards
- Configure X-Ray tracing
- Test complete infrastructure provisioning

**Deliverables:**
- ✅ All Terraform modules complete and documented
- ✅ Dev environment fully provisioned
- ✅ Infrastructure tested and validated
- ✅ Teardown/rebuild scripts working
- ✅ Cost tracking dashboard created

### Week 3: Application Migration (Days 15-21)

**Day 15-16: Controller Refactoring**
- Refactor artist endpoints to use ArtistService
- Refactor festival endpoints to use FestivalService
- Refactor playlist endpoints to use PlaylistService
- Remove all direct database access from controllers
- Update integration tests

**Day 17-18: AWS Configuration & Deployment**
- Update application configuration for AWS services
- Configure structured JSON logging
- Add X-Ray tracing to application
- Add CloudWatch metrics publishing
- Build and push Docker image to ECR

**Day 19-20: Deploy & Test in AWS**
- Deploy application to dev environment
- Run integration tests against AWS environment
- Test external API integrations (Spotify, Setlist.fm)
- Test caching with ElastiCache Redis
- Performance testing and optimization

**Day 21: Data Migration & Validation**
- Export data from local database
- Import data to Aurora Serverless v2
- Validate data integrity
- Test application with production data
- Document migration process

**Deliverables:**
- ✅ All controllers refactored to use service layer
- ✅ Application running on ECS Fargate
- ✅ ALB routing traffic correctly
- ✅ CloudFront serving static assets
- ✅ All tests passing in AWS environment
- ✅ Data successfully migrated

### Week 4: CI/CD & Production (Days 22-28)

**Day 22-23: CI/CD Automation**
- Create deployment workflows (dev, staging, prod)
- Configure blue-green deployment
- Set up automated rollback
- Test deployment pipeline end-to-end
- Configure deployment notifications

**Day 24-25: Staging Environment**
- Provision staging environment
- Deploy application to staging
- Run full test suite in staging
- Load testing (target: 1,000 concurrent users)
- Security testing and validation

**Day 26-27: Production Deployment**
- Provision production environment
- Deploy application to production
- Configure production monitoring and alerts
- Validate all production services
- Test teardown/rebuild workflow

**Day 28: Documentation & Handoff**
- Complete README with setup instructions
- Document all Terraform modules
- Create architecture diagrams
- Write runbooks for common operations
- Create troubleshooting guide
- Document cost optimization strategies

**Deliverables:**
- ✅ Automated CI/CD pipeline working
- ✅ Staging environment live and tested
- ✅ Production environment live
- ✅ All monitoring and alerts configured
- ✅ Complete documentation
- ✅ Migration successfully completed

## Success Criteria

The migration is considered successful when:

1. **Infrastructure:**
   - ✅ 100% of AWS resources defined in Terraform
   - ✅ Can destroy environment with single command (< 10 min)
   - ✅ Can provision environment with single command (< 15 min)
   - ✅ Automated database snapshot/restore working
   - ✅ Daily teardown/rebuild tested and documented

2. **Application:**
   - ✅ All controllers use service layer (no direct DB access)
   - ✅ All repositories implemented
   - ✅ 80%+ test coverage achieved
   - ✅ All tests passing in CI/CD

3. **Deployment:**
   - ✅ GitHub Actions CI/CD pipeline working
   - ✅ Automated deployment to dev on merge
   - ✅ Blue-green deployment working
   - ✅ Rollback capability tested

4. **Observability:**
   - ✅ Structured JSON logging to CloudWatch
   - ✅ CloudWatch metrics tracking KPIs
   - ✅ CloudWatch alarms configured
   - ✅ X-Ray tracing working
   - ✅ Cost monitoring dashboard created

5. **Security:**
   - ✅ All secrets in AWS Secrets Manager
   - ✅ Security groups configured with zero-trust model
   - ✅ ECS tasks only accessible via ALB
   - ✅ Databases in private subnets
   - ✅ AWS WAF protecting API
   - ✅ Security scanning passing in CI/CD

6. **Performance:**
   - ✅ API response time < 200ms (p95)
   - ✅ Auto-scaling working correctly
   - ✅ Load testing passed (1,000 concurrent users)

7. **Cost:**
   - ✅ Environment with daily teardown costs $10-15/month
   - ✅ Cost alerts configured and tested
   - ✅ Teardown/rebuild scripts working

8. **Documentation:**
   - ✅ README with setup instructions
   - ✅ Terraform modules documented
   - ✅ Architecture diagrams created
   - ✅ Runbooks for common operations
   - ✅ Troubleshooting guide

## Conclusion

This design provides a comprehensive blueprint for migrating the Festival Playlist Generator to AWS with a focus on cost optimization, clean architecture, and operational simplicity. The daily teardown/rebuild capability reduces costs by ~50% while maintaining fast provision times (< 15 minutes). The clean architecture pattern (Repository → Service → Controller) ensures maintainability and testability. Infrastructure as Code with Terraform enables version control and reproducibility. Automated CI/CD with GitHub Actions streamlines deployments. Comprehensive observability with CloudWatch and X-Ray provides visibility into system health and performance.

The design is practical for a solo developer to implement and maintain, using managed AWS services to minimize operational overhead while following enterprise best practices for security, monitoring, and deployment automation.


## Cost Management and Budgets

### AWS Budgets Configuration

**Budget Setup (Terraform):**
```hcl
# Monthly budget with multiple alert thresholds
resource "aws_budgets_budget" "monthly" {
  name              = "festival-monthly-budget-${var.environment}"
  budget_type       = "COST"
  limit_amount      = var.environment == "dev" ? "15" : "50"
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2024-01-01_00:00"
  
  cost_filter {
    name = "TagKeyValue"
    values = [
      "user:Environment$${var.environment}"
    ]
  }
  
  # Alert at 80% of budget
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
  
  # Alert at 100% of budget
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
  
  # Forecasted alert at 100%
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
}

# Daily budget for fine-grained tracking
resource "aws_budgets_budget" "daily" {
  name              = "festival-daily-budget-${var.environment}"
  budget_type       = "COST"
  limit_amount      = var.environment == "dev" ? "0.50" : "2.00"
  limit_unit        = "USD"
  time_unit         = "DAILY"
  time_period_start = "2024-01-01_00:00"
  
  cost_filter {
    name = "TagKeyValue"
    values = [
      "user:Environment$${var.environment}"
    ]
  }
  
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
}

# Budget for specific services
resource "aws_budgets_budget" "rds" {
  name              = "festival-rds-budget-${var.environment}"
  budget_type       = "COST"
  limit_amount      = var.environment == "dev" ? "5" : "20"
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2024-01-01_00:00"
  
  cost_filter {
    name = "Service"
    values = ["Amazon Relational Database Service"]
  }
  
  cost_filter {
    name = "TagKeyValue"
    values = [
      "user:Environment$${var.environment}"
    ]
  }
  
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
}

# SNS topic for budget alerts
resource "aws_sns_topic" "budget_alerts" {
  name = "festival-budget-alerts-${var.environment}"
  
  tags = {
    Name        = "Budget Alerts"
    Environment = var.environment
  }
}

resource "aws_sns_topic_subscription" "budget_alerts_email" {
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Budget action to automatically notify when threshold exceeded
resource "aws_budgets_budget_action" "notify_on_exceed" {
  budget_name        = aws_budgets_budget.monthly.name
  action_type        = "APPLY_IAM_POLICY"
  approval_model     = "AUTOMATIC"
  notification_type  = "ACTUAL"
  execution_role_arn = aws_iam_role.budget_action.arn
  
  action_threshold {
    action_threshold_type  = "PERCENTAGE"
    action_threshold_value = 100
  }
  
  definition {
    iam_action_definition {
      policy_arn = aws_iam_policy.budget_exceeded.arn
      roles      = [aws_iam_role.ecs_task_role.name]
    }
  }
  
  subscriber {
    address           = var.alert_email
    subscription_type = "EMAIL"
  }
}
```

### AWS Cost Anomaly Detection

**Cost Anomaly Monitor Configuration:**
```hcl
# Cost anomaly monitor for the entire account
resource "aws_ce_anomaly_monitor" "account" {
  name              = "festival-account-monitor-${var.environment}"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
  
  tags = {
    Name        = "Account Cost Anomaly Monitor"
    Environment = var.environment
  }
}

# Cost anomaly monitor for specific environment
resource "aws_ce_anomaly_monitor" "environment" {
  name         = "festival-environment-monitor-${var.environment}"
  monitor_type = "CUSTOM"
  
  monitor_specification = jsonencode({
    Tags = {
      Key    = "Environment"
      Values = [var.environment]
    }
  })
  
  tags = {
    Name        = "Environment Cost Anomaly Monitor"
    Environment = var.environment
  }
}

# Anomaly subscription for immediate alerts
resource "aws_ce_anomaly_subscription" "immediate" {
  name      = "festival-anomaly-alerts-${var.environment}"
  frequency = "IMMEDIATE"
  
  monitor_arn_list = [
    aws_ce_anomaly_monitor.account.arn,
    aws_ce_anomaly_monitor.environment.arn
  ]
  
  subscriber {
    type    = "EMAIL"
    address = var.alert_email
  }
  
  subscriber {
    type    = "SNS"
    address = aws_sns_topic.cost_anomaly_alerts.arn
  }
  
  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      values        = ["5"]  # Alert on anomalies > $5
      match_options = ["GREATER_THAN_OR_EQUAL"]
    }
  }
  
  tags = {
    Name        = "Cost Anomaly Subscription"
    Environment = var.environment
  }
}

# Daily summary subscription
resource "aws_ce_anomaly_subscription" "daily" {
  name      = "festival-anomaly-daily-${var.environment}"
  frequency = "DAILY"
  
  monitor_arn_list = [
    aws_ce_anomaly_monitor.account.arn,
    aws_ce_anomaly_monitor.environment.arn
  ]
  
  subscriber {
    type    = "EMAIL"
    address = var.alert_email
  }
  
  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      values        = ["1"]  # Include anomalies > $1 in daily summary
      match_options = ["GREATER_THAN_OR_EQUAL"]
    }
  }
  
  tags = {
    Name        = "Daily Cost Anomaly Summary"
    Environment = var.environment
  }
}

# SNS topic for cost anomaly alerts
resource "aws_sns_topic" "cost_anomaly_alerts" {
  name = "festival-cost-anomaly-alerts-${var.environment}"
  
  tags = {
    Name        = "Cost Anomaly Alerts"
    Environment = var.environment
  }
}

resource "aws_sns_topic_subscription" "cost_anomaly_email" {
  topic_arn = aws_sns_topic.cost_anomaly_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
```

### Cost Allocation Tags

**Tagging Strategy:**
```hcl
# Default tags applied to all resources
locals {
  common_tags = {
    Project     = "Festival Playlist Generator"
    Environment = var.environment
    ManagedBy   = "Terraform"
    CostCenter  = "Engineering"
    Owner       = var.owner_email
  }
  
  # Additional tags for cost allocation
  cost_tags = {
    Application = "festival-app"
    Component   = var.component_name  # e.g., "api", "worker", "database"
    Tier        = var.tier            # e.g., "compute", "storage", "network"
  }
}

# Apply tags to all resources
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = merge(local.common_tags, local.cost_tags)
  }
}

# Activate cost allocation tags
resource "aws_ce_cost_allocation_tag" "environment" {
  tag_key = "Environment"
  status  = "Active"
}

resource "aws_ce_cost_allocation_tag" "application" {
  tag_key = "Application"
  status  = "Active"
}

resource "aws_ce_cost_allocation_tag" "component" {
  tag_key = "Component"
  status  = "Active"
}

resource "aws_ce_cost_allocation_tag" "tier" {
  tag_key = "Tier"
  status  = "Active"
}
```

### Cost Reporting Dashboard

**Enhanced CloudWatch Dashboard with Cost Metrics:**
```hcl
resource "aws_cloudwatch_dashboard" "cost_monitoring" {
  dashboard_name = "festival-cost-monitoring-${var.environment}"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Billing", "EstimatedCharges", { stat = "Maximum", label = "Estimated Charges" }]
          ]
          period = 21600  # 6 hours
          stat   = "Maximum"
          region = "us-east-1"  # Billing metrics only in us-east-1
          title  = "Estimated Monthly Charges"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/RDS", "ACUUtilization", { stat = "Average", label = "Aurora ACU Usage" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Aurora Serverless ACU Utilization"
          annotations = {
            horizontal = [
              {
                value = 0.5
                label = "Min ACU"
                color = "#2ca02c"
              },
              {
                value = 4.0
                label = "Max ACU"
                color = "#d62728"
              }
            ]
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", { stat = "Average", label = "ECS CPU" }],
            [".", "MemoryUtilization", { stat = "Average", label = "ECS Memory" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "ECS Resource Utilization (Cost Driver)"
        }
      },
      {
        type = "log"
        properties = {
          query   = <<-EOT
            SOURCE '/aws/cost/anomalies'
            | fields @timestamp, anomalyScore, impact, service
            | filter anomalyScore > 0.5
            | sort @timestamp desc
            | limit 20
          EOT
          region  = var.aws_region
          title   = "Recent Cost Anomalies"
        }
      }
    ]
  })
}
```

### Cost Optimization Script

**Enhanced Cost Report Script (`scripts/cost-report.sh`):**
```bash
#!/bin/bash

ENVIRONMENT=${1:-dev}
START_DATE=$(date -d '1 month ago' +%Y-%m-%d)
END_DATE=$(date +%Y-%m-%d)

echo "========================================="
echo "AWS Cost Report with Anomaly Detection"
echo "Environment: $ENVIRONMENT"
echo "Period: $START_DATE to $END_DATE"
echo "========================================="

# Get cost by service
echo ""
echo "Cost by Service:"
aws ce get-cost-and-usage \
    --time-period Start=$START_DATE,End=$END_DATE \
    --granularity MONTHLY \
    --metrics "UnblendedCost" \
    --group-by Type=DIMENSION,Key=SERVICE \
    --filter file://<(cat <<EOF
{
  "Tags": {
    "Key": "Environment",
    "Values": ["$ENVIRONMENT"]
  }
}
EOF
) \
    --query 'ResultsByTime[0].Groups[*].[Keys[0], Metrics.UnblendedCost.Amount]' \
    --output table

# Get total cost
echo ""
echo "Total Monthly Cost:"
TOTAL_COST=$(aws ce get-cost-and-usage \
    --time-period Start=$START_DATE,End=$END_DATE \
    --granularity MONTHLY \
    --metrics "UnblendedCost" \
    --filter file://<(cat <<EOF
{
  "Tags": {
    "Key": "Environment",
    "Values": ["$ENVIRONMENT"]
  }
}
EOF
) \
    --query 'ResultsByTime[0].Total.UnblendedCost.Amount' \
    --output text)

echo "\$$TOTAL_COST"

# Check budget status
echo ""
echo "Budget Status:"
aws budgets describe-budgets \
    --account-id $(aws sts get-caller-identity --query Account --output text) \
    --query "Budgets[?BudgetName=='festival-monthly-budget-$ENVIRONMENT'].[BudgetName, BudgetLimit.Amount, CalculatedSpend.ActualSpend.Amount]" \
    --output table

# Get cost anomalies
echo ""
echo "Recent Cost Anomalies:"
aws ce get-anomalies \
    --date-interval Start=$START_DATE,End=$END_DATE \
    --max-results 10 \
    --query 'Anomalies[*].[AnomalyStartDate, AnomalyScore.CurrentScore, Impact.TotalImpact, RootCauses[0].Service]' \
    --output table

# Cost forecast
echo ""
echo "Cost Forecast (Next 7 Days):"
FORECAST_START=$(date +%Y-%m-%d)
FORECAST_END=$(date -d '+7 days' +%Y-%m-%d)

aws ce get-cost-forecast \
    --time-period Start=$FORECAST_START,End=$FORECAST_END \
    --metric UNBLENDED_COST \
    --granularity DAILY \
    --filter file://<(cat <<EOF
{
  "Tags": {
    "Key": "Environment",
    "Values": ["$ENVIRONMENT"]
  }
}
EOF
) \
    --query 'Total.Amount' \
    --output text

# Cost optimization recommendations
echo ""
echo "Cost Optimization Recommendations:"
echo "1. Current teardown status: $(terraform output -raw environment_status 2>/dev/null || echo 'Unknown')"
echo "2. Estimated savings with daily teardown: \$5-9/month"
echo "3. Aurora ACU usage: Check if min ACU can be reduced"
echo "4. ECS task count: Verify auto-scaling is working correctly"
echo "5. CloudWatch log retention: Currently 7 days (optimal)"

# Alert if over budget
BUDGET_LIMIT=$([ "$ENVIRONMENT" = "dev" ] && echo "15" || echo "50")
if (( $(echo "$TOTAL_COST > $BUDGET_LIMIT" | bc -l) )); then
    echo ""
    echo "⚠️  WARNING: Cost ($TOTAL_COST) exceeds budget ($BUDGET_LIMIT)!"
    echo "Consider running teardown script: ./scripts/teardown.sh $ENVIRONMENT"
fi
```

### Cost Monitoring Best Practices

**Daily Cost Checks:**
1. Review AWS Budgets dashboard daily
2. Check Cost Anomaly Detection alerts
3. Monitor CloudWatch cost dashboard
4. Run cost report script weekly
5. Review cost allocation by tags monthly

**Cost Optimization Actions:**
1. Tear down dev environment when not in use (saves $8-10/month)
2. Review Aurora ACU usage and adjust min/max if needed
3. Optimize CloudWatch log retention (currently 7 days)
4. Use S3 Intelligent-Tiering for automatic cost optimization
5. Review and remove unused snapshots older than 7 days
6. Monitor ECS task count and adjust auto-scaling policies
7. Use Spot instances for worker tasks (70% savings)

**Alert Response Procedures:**
1. **Budget Alert (80%)**: Review current spending, identify high-cost services
2. **Budget Alert (100%)**: Immediate review, consider teardown if dev environment
3. **Cost Anomaly Alert**: Investigate root cause, check for misconfiguration
4. **Forecasted Budget Exceed**: Plan cost reduction actions proactively


## Domain and SSL Certificate Management

### Domain Configuration

**Domain:** gig-prep.co.uk

**DNS Management Options:**

**Option 1: Register domain with Route 53 (Recommended)**
- Simplest integration with AWS services
- Automatic DNS management
- Cost: ~$12/year for .co.uk domain

**Option 2: External registrar with Route 53 DNS**
- Register domain with external registrar (e.g., Namecheap, GoDaddy)
- Use Route 53 for DNS management
- Update nameservers at registrar to point to Route 53
- Cost: Domain registration fee + $0.50/month for hosted zone

### Route 53 Configuration

**Terraform Configuration for Route 53:**
```hcl
# Route 53 hosted zone
resource "aws_route53_zone" "main" {
  name = "gig-prep.co.uk"
  
  tags = {
    Name        = "gig-prep.co.uk"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# A record for root domain pointing to CloudFront
resource "aws_route53_record" "root" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "gig-prep.co.uk"
  type    = "A"
  
  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

# A record for www subdomain pointing to CloudFront
resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "www.gig-prep.co.uk"
  type    = "A"
  
  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

# A record for API subdomain pointing to ALB
resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "api.gig-prep.co.uk"
  type    = "A"
  
  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# CNAME record for dev environment
resource "aws_route53_record" "dev" {
  count   = var.environment == "dev" ? 1 : 0
  zone_id = aws_route53_zone.main.zone_id
  name    = "dev.gig-prep.co.uk"
  type    = "A"
  
  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

# Output nameservers for domain configuration
output "route53_nameservers" {
  description = "Route 53 nameservers for domain configuration"
  value       = aws_route53_zone.main.name_servers
}
```

### SSL/TLS Certificate Configuration

**AWS Certificate Manager (ACM) Setup:**
```hcl
# SSL certificate for CloudFront (must be in us-east-1)
resource "aws_acm_certificate" "cloudfront" {
  provider          = aws.us_east_1  # CloudFront requires cert in us-east-1
  domain_name       = "gig-prep.co.uk"
  validation_method = "DNS"
  
  subject_alternative_names = [
    "*.gig-prep.co.uk",  # Wildcard for all subdomains
    "www.gig-prep.co.uk"
  ]
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Name        = "gig-prep.co.uk-cloudfront"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# SSL certificate for ALB (in application region)
resource "aws_acm_certificate" "alb" {
  domain_name       = "api.gig-prep.co.uk"
  validation_method = "DNS"
  
  subject_alternative_names = [
    "*.api.gig-prep.co.uk"
  ]
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Name        = "api.gig-prep.co.uk"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# DNS validation records for CloudFront certificate
resource "aws_route53_record" "cert_validation_cloudfront" {
  for_each = {
    for dvo in aws_acm_certificate.cloudfront.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }
  
  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.main.zone_id
}

# DNS validation records for ALB certificate
resource "aws_route53_record" "cert_validation_alb" {
  for_each = {
    for dvo in aws_acm_certificate.alb.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }
  
  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.main.zone_id
}

# Wait for CloudFront certificate validation
resource "aws_acm_certificate_validation" "cloudfront" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.cloudfront.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation_cloudfront : record.fqdn]
}

# Wait for ALB certificate validation
resource "aws_acm_certificate_validation" "alb" {
  certificate_arn         = aws_acm_certificate.alb.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation_alb : record.fqdn]
}

# Additional provider for us-east-1 (required for CloudFront certificates)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
  
  default_tags {
    tags = local.common_tags
  }
}
```

### Updated CloudFront Configuration with Custom Domain

```hcl
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Festival Playlist Generator CDN"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  
  # Custom domain configuration
  aliases = [
    "gig-prep.co.uk",
    "www.gig-prep.co.uk",
    var.environment == "dev" ? "dev.gig-prep.co.uk" : null
  ]
  
  # Origin: ALB for API
  origin {
    domain_name = aws_lb.main.dns_name
    origin_id   = "alb"
    
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
    
    custom_header {
      name  = "X-Custom-Header"
      value = random_password.cloudfront_secret.result
    }
  }
  
  # Origin: S3 for static assets
  origin {
    domain_name = aws_s3_bucket.app_data.bucket_regional_domain_name
    origin_id   = "s3"
    
    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.main.cloudfront_access_identity_path
    }
  }
  
  # Default cache behavior (API)
  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    target_origin_id       = "alb"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    
    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Host", "Origin"]
      
      cookies {
        forward = "all"
      }
    }
    
    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }
  
  # Cache behavior for static assets
  ordered_cache_behavior {
    path_pattern           = "/static/*"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    target_origin_id       = "s3"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    
    forwarded_values {
      query_string = false
      
      cookies {
        forward = "none"
      }
    }
    
    min_ttl     = 0
    default_ttl = 86400
    max_ttl     = 31536000
  }
  
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  
  # SSL certificate configuration
  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.cloudfront.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
  
  logging_config {
    bucket = aws_s3_bucket.cloudfront_logs.bucket_domain_name
    prefix = "cloudfront/"
  }
  
  depends_on = [aws_acm_certificate_validation.cloudfront]
  
  tags = {
    Name        = "festival-cdn"
    Environment = var.environment
  }
}
```

### Updated ALB Configuration with Custom Domain

```hcl
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate.alb.arn
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  
  depends_on = [aws_acm_certificate_validation.alb]
}

# Additional listener certificate for multiple domains if needed
resource "aws_lb_listener_certificate" "additional" {
  count           = var.environment == "dev" ? 1 : 0
  listener_arn    = aws_lb_listener.https.arn
  certificate_arn = aws_acm_certificate.alb.arn
}
```

### Domain Setup Instructions

**Step 1: Register Domain (if not already registered)**
```bash
# Option A: Register with Route 53
aws route53domains register-domain \
    --domain-name gig-prep.co.uk \
    --duration-in-years 1 \
    --admin-contact file://contact.json \
    --registrant-contact file://contact.json \
    --tech-contact file://contact.json \
    --auto-renew

# Option B: Register with external registrar
# Then update nameservers to Route 53 nameservers
```

**Step 2: Apply Terraform Configuration**
```bash
cd terraform
terraform init
terraform plan -var="domain_name=gig-prep.co.uk"
terraform apply -var="domain_name=gig-prep.co.uk"
```

**Step 3: Verify DNS Propagation**
```bash
# Check nameservers
dig NS gig-prep.co.uk

# Check A records
dig A gig-prep.co.uk
dig A www.gig-prep.co.uk
dig A api.gig-prep.co.uk

# Check SSL certificate
curl -vI https://gig-prep.co.uk
curl -vI https://api.gig-prep.co.uk
```

**Step 4: Update Application Configuration**
```bash
# Update environment variables
export API_URL=https://api.gig-prep.co.uk
export FRONTEND_URL=https://gig-prep.co.uk

# Update CORS configuration in API
ALLOWED_ORIGINS=["https://gig-prep.co.uk", "https://www.gig-prep.co.uk"]
```

### Certificate Renewal

**Automatic Renewal:**
- ACM automatically renews certificates before expiration
- DNS validation records must remain in Route 53
- CloudWatch alarm for certificate expiration (60 days before)

**Certificate Expiration Alarm:**
```hcl
resource "aws_cloudwatch_metric_alarm" "cert_expiration" {
  alarm_name          = "festival-cert-expiration-${var.environment}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "DaysToExpiry"
  namespace           = "AWS/CertificateManager"
  period              = "86400"  # 1 day
  statistic           = "Minimum"
  threshold           = "30"  # Alert 30 days before expiration
  alarm_description   = "SSL certificate expiring soon"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  
  dimensions = {
    CertificateArn = aws_acm_certificate.cloudfront.arn
  }
}
```

### Domain Cost Breakdown

**Annual Costs:**
- Domain registration (.co.uk): ~$12/year
- Route 53 hosted zone: $0.50/month = $6/year
- Route 53 queries: $0.40/million queries (negligible for hobby project)
- SSL certificates (ACM): Free
- **Total: ~$18/year (~$1.50/month)**

### Security Considerations

**Domain Security:**
- Enable domain transfer lock
- Enable DNSSEC for Route 53 hosted zone
- Use strong registrar account password
- Enable 2FA on registrar account
- Monitor for unauthorized DNS changes

**SSL/TLS Security:**
- Use TLS 1.2 or higher only
- Enable HSTS (HTTP Strict Transport Security)
- Configure secure cipher suites
- Monitor certificate expiration
- Use SNI (Server Name Indication) for multiple domains

**HSTS Configuration:**
```hcl
# Add HSTS header to CloudFront responses
resource "aws_cloudfront_response_headers_policy" "security_headers" {
  name = "festival-security-headers-${var.environment}"
  
  security_headers_config {
    strict_transport_security {
      access_control_max_age_sec = 31536000  # 1 year
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
    
    content_type_options {
      override = true
    }
    
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    
    xss_protection {
      mode_block = true
      protection = true
      override   = true
    }
    
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
  }
}

# Attach to CloudFront distribution
resource "aws_cloudfront_distribution" "main" {
  # ... other configuration ...
  
  default_cache_behavior {
    # ... other configuration ...
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security_headers.id
  }
}
```

