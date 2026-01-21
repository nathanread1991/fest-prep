# AWS Enterprise Migration - Requirements

## Overview

Transform the Festival Playlist Generator from a local Docker-based hobby project into a production-ready, enterprise-grade system deployed on AWS. The solution must be cost-conscious ($30/month during development), leverage Infrastructure as Code (Terraform), automated CI/CD (GitHub Actions), and use serverless/spot instances where appropriate. The architecture must support easy infrastructure teardown to minimize costs while maintaining professional quality and AWS migration best practices.

## Problem Statement

**Current State:**
- Local Docker Compose deployment only
- Direct database access in API endpoints (no service layer)
- No production infrastructure or deployment automation
- Missing enterprise observability and monitoring
- No infrastructure as code or version control for infrastructure
- Limited scalability and no auto-scaling
- No proper environment separation (dev/staging/prod)
- Manual deployment process
- Single developer maintaining everything

**Business Context:**
- Hobby project funded personally
- Need to minimize AWS costs during development ($30/month target)
- Must be maintainable by one person
- Should be production-ready for future growth
- 4-week migration timeline

## Goals

1. **AWS-Native Serverless Architecture**: Migrate to AWS using serverless and managed services
2. **Infrastructure as Code**: All infrastructure in Terraform with ability to tear down/rebuild
3. **Cost Optimization**: $30/month during development, scale costs with usage
4. **CI/CD Automation**: GitHub Actions for automated testing and deployment
5. **Clean Architecture**: Implement Repository → Service → Controller pattern
6. **Enterprise Observability**: CloudWatch logging, metrics, alarms, and X-Ray tracing
7. **Security Best Practices**: AWS security standards without compromising on protection
8. **Maintainability**: Simple enough for solo developer to manage

## User Stories

### US-1: As a Solo Developer
I want all infrastructure defined as Terraform code so that I can tear down and rebuild my environment daily to minimize costs.

**Acceptance Criteria:**
- All AWS resources defined in Terraform modules
- Terraform state in S3 with DynamoDB locking
- **Single command to destroy entire environment: `terraform destroy`**
- **Single command to provision entire environment: `terraform apply`**
- **Provision time: < 15 minutes (fast enough for daily use)**
- **Destroy time: < 10 minutes**
- **Data persistence strategy for daily teardown:**
  - Database snapshots before destroy (automated)
  - Restore from latest snapshot on provision (automated)
  - S3 data persists (not destroyed)
  - Secrets Manager persists (not destroyed)
- **Idempotent**: Can run multiple times safely
- Cost estimation before applying changes
- Documentation for teardown/rebuild workflow
- **GitHub Actions workflow for scheduled teardown (optional)**

### US-2: As a Solo Developer
I want automated CI/CD pipelines using GitHub Actions so that code changes are tested and deployed automatically without manual intervention.

**Acceptance Criteria:**
- GitHub Actions workflows for CI/CD (free tier)
- Automated unit, integration, and e2e tests on every PR
- Automated deployment to dev environment on merge to main
- Manual approval gate for production deployments
- Automated rollback capability
- Container images stored in Amazon ECR
- Deployment notifications
- Build and deployment time < 10 minutes

### US-3: As a Project Owner
I want to minimize AWS costs by tearing down infrastructure daily when not in use while maintaining the ability to quickly rebuild.

**Acceptance Criteria:**
- **Daily teardown capability**: Destroy environment at end of workday
- **Daily rebuild capability**: Provision environment in < 15 minutes
- **Automated database backup before teardown**
- **Automated database restore on rebuild**
- Environment costs when active (8 hours/day, 5 days/week): ~$8-10/month
  - Aurora Serverless v2 (auto-pause + partial month): $2-3
  - ECS Fargate API (partial month): $2-3
  - ECS Fargate Worker (Spot, partial month): $1
  - ALB (partial month): $2
  - ElastiCache Redis (partial month): $1
  - VPC Endpoints: Free
- Environment costs when torn down: $2-3/month
  - S3 storage for backups and Terraform state
  - Secrets Manager
  - RDS snapshots (free for 7 days)
- **Total monthly cost with daily teardown: ~$10-13/month** (vs $15-19 running 24/7)
- **AWS Budgets configured with alerts at $10, $20, $30**
- **AWS Cost Anomaly Detection enabled with automatic alerts**
- **Budget actions configured to send SNS notifications**
- **Cost allocation tags applied to all resources**
- Monthly cost dashboard in CloudWatch
- S3 Intelligent-Tiering for storage
- CloudWatch log retention: 7 days

### US-4: As a Backend Developer
I want proper architectural layers (Repository/Service/Controller) so that business logic is decoupled, testable, and maintainable.

**Acceptance Criteria:**
- Repository layer for ALL database operations (no direct DB access elsewhere)
- Service layer for business logic with dependency injection
- Controller layer only handles HTTP/request concerns
- All existing endpoints refactored to use service layer
- 80%+ code coverage with unit and integration tests
- Service layer is framework-agnostic (can swap FastAPI for Flask)
- Clear separation of concerns documented

### US-5: As a DevOps Engineer
I want comprehensive observability built-in so that I can monitor, debug, and optimize the system in production without additional tools.

**Acceptance Criteria:**
- Structured JSON logging to CloudWatch Logs
- CloudWatch Metrics for all key performance indicators
- CloudWatch Alarms for critical issues (errors, latency, costs)
- AWS X-Ray distributed tracing across all services
- CloudWatch Dashboards for application and infrastructure metrics
- Log aggregation with query capabilities
- Request ID tracking across all services
- Performance monitoring (p50, p95, p99 latencies)


### US-6: As a Security Engineer
I want AWS security best practices implemented with defense-in-depth, especially tight security groups since ECS tasks are in public subnets.

**Acceptance Criteria:**
- **Security Groups**: Zero-trust model with least privilege
  - ECS tasks ONLY accept traffic from ALB (no direct public access)
  - RDS ONLY accepts traffic from ECS tasks
  - Redis ONLY accepts traffic from ECS tasks
  - Security group rules use SG references (not CIDR blocks)
  - All rules documented and audited
- All secrets in AWS Secrets Manager (no hardcoded credentials)
- IAM roles with least privilege principle
- VPC with public/private subnets (databases in private)
- AWS WAF protecting ALB with rate limiting
- Encryption at rest (RDS, S3, EBS)
- Encryption in transit (TLS everywhere)
- Automated security scanning in CI/CD pipeline
- Regular dependency vulnerability scanning
- No public S3 buckets
- CloudTrail enabled for audit logging
- VPC Flow Logs for network monitoring
- Security group change alerts

### US-7: As an End User
I want fast, reliable access to the application with minimal downtime so I can create festival playlists without frustration.

**Acceptance Criteria:**
- **Custom domain configured: gig-prep.co.uk**
- **SSL/TLS certificate from AWS Certificate Manager**
- **Domain registered via Route 53 (or external registrar with Route 53 DNS)**
- **CloudFront distribution using custom domain**
- **ALB using custom domain with SSL certificate**
- **Automatic certificate renewal configured**
- API response time < 200ms (p95) with caching
- Page load time < 3 seconds (p95)
- 99.5% uptime SLA (acceptable for hobby project)
- CloudFront CDN for static assets (global distribution)
- Auto-scaling based on demand
- Graceful degradation when external APIs fail
- Health checks and automatic recovery
- Zero-downtime deployments

### US-8: As a Solo Developer
I want the system to be simple enough to maintain alone while following enterprise patterns so I don't get overwhelmed with operational complexity.

**Acceptance Criteria:**
- Use managed AWS services (minimize operational overhead)
- Clear documentation for all infrastructure and code
- Automated backups and recovery procedures
- Self-healing infrastructure where possible
- Monitoring alerts only for actionable issues
- Runbooks for common operational tasks
- Infrastructure changes via Terraform only (no manual AWS console changes)
- Single command deployment process

## Non-Functional Requirements

### Performance
- **API Endpoints**: < 200ms response time (p95) with Redis caching
- **Database Queries**: < 100ms (p95) with proper indexing
- **Search Operations**: < 300ms (p95) with full-text search
- **Page Load**: < 3 seconds (p95) with CloudFront CDN
- **Concurrent Users**: Support 1,000 initially, design for 10K+
- **Background Jobs**: Process within 5 minutes

### Cost Targets (US-East-1)

**Single Environment (Daily Teardown Strategy):**

*Active (8 hours/day, 5 days/week = ~40 hours/week = ~173 hours/month):*
- Aurora Serverless v2 (0.5 ACU, partial month): $2-3
- ECS Fargate API (1 task, partial month): $2-3
- ECS Fargate Worker (Spot, partial month): $1
- ALB (partial month): $2
- ElastiCache Redis (partial month): $1
- VPC Endpoints: Free
- **Subtotal: $8-10/month**

*Torn Down (remaining ~557 hours/month):*
- S3 storage (backups, Terraform state): $1-2
- Secrets Manager: $1-2
- RDS snapshots (free for 7 days, then $0.095/GB/month): $0-1
- **Subtotal: $2-5/month**

**Total Monthly Cost: $10-15/month**
**Savings vs 24/7: ~$5-9/month!**

---

**If Running 24/7 (for comparison):**
- Aurora Serverless v2 (0.5-1 ACU): $15-25
- ECS Fargate API (1-2 tasks): $8-20
- ECS Fargate Worker (Spot): $2-5
- ALB: $16
- ElastiCache Redis (t4g.micro): $3
- Other: $5-10
- **Total: $49-79/month**


### Scalability
- **Horizontal Scaling**: ECS Fargate auto-scaling (CPU/memory based)
- **Database**: Aurora Serverless v2 auto-scaling (0.5-4 ACUs)
- **Cache**: ElastiCache Redis with read replicas if needed
- **Storage**: S3 (unlimited, pay per use)
- **CDN**: CloudFront (global edge locations)
- **Design Target**: Handle 10K+ concurrent users without architecture changes

### Reliability
- **Uptime SLA**: 99.5% (acceptable for hobby project, ~3.6 hours downtime/month)
- **Multi-AZ**: Production database and cache
- **Automated Backups**: Daily snapshots, 7-day retention
- **Health Checks**: ECS task health checks with auto-restart
- **Circuit Breakers**: For external API calls (Spotify, Setlist.fm)
- **Retry Logic**: Exponential backoff for transient failures
- **Graceful Degradation**: Core features work even if external APIs fail

### Security
- **Authentication**: JWT tokens with refresh mechanism
- **Authorization**: Role-based access control (RBAC)
- **Secrets Management**: AWS Secrets Manager for all credentials
- **Network Security**: VPC with private subnets, security groups
- **API Protection**: AWS WAF with rate limiting
- **Data Encryption**: At rest (RDS, S3) and in transit (TLS 1.2+)
- **Vulnerability Scanning**: Automated in CI/CD pipeline
- **Audit Logging**: CloudTrail for all AWS API calls
- **Compliance**: Follow AWS Well-Architected Framework

### Maintainability
- **Infrastructure as Code**: 100% Terraform (no manual changes)
- **Code Coverage**: > 80% with unit and integration tests
- **Documentation**: Inline code docs, README files, architecture diagrams
- **Versioning**: Semantic versioning for releases
- **Change Management**: All changes via pull requests with reviews
- **Monitoring**: Automated alerts for issues
- **Deployment**: Automated via GitHub Actions

## AWS Services Architecture (Cost-Optimized)

### Compute Layer
**Primary: Amazon ECS Fargate**
- **API Service**: 
  - 0.25 vCPU, 0.5 GB RAM per task
  - Auto-scaling: 1-4 tasks based on CPU/memory
  - On-demand instances (need reliability)
  - ~$10-40/month depending on scale
  
- **Worker Service** (Celery):
  - 0.25 vCPU, 0.5 GB RAM per task
  - Fargate Spot instances (70% cost savings)
  - Auto-scaling: 0-2 tasks based on queue depth
  - ~$2-8/month
  
**Why ECS Fargate over Lambda:**
- Existing containerized application
- Long-running background jobs (Celery workers)
- More predictable costs for steady traffic
- Easier to migrate from Docker Compose

**Why Spot for Workers:**
- Background jobs can tolerate interruptions
- 70% cost savings
- Celery handles retries automatically


### Database Layer
**Amazon RDS Aurora Serverless v2 (PostgreSQL)**
- **Capacity**: 0.5 ACU minimum, 2-4 ACU maximum
- **Auto-Pause**: After 5 minutes of inactivity (dev environment)
- **Multi-AZ**: Production only
- **Backups**: Automated daily, 7-day retention
- **Cost**: ~$8-12/month (dev with auto-pause), ~$15-40/month (prod)

**Why Aurora Serverless v2:**
- Pay only for capacity used (per second billing)
- Auto-scales with load (0.5-4 ACUs)
- Auto-pause in dev saves costs
- PostgreSQL compatible (no code changes)
- Automated backups included
- Better than RDS for variable workloads

**Why Not DynamoDB:**
- Existing relational data model
- Complex queries and joins needed
- PostgreSQL-specific features used (arrays, JSON)
- Migration effort too high

### Caching Layer
**Amazon ElastiCache for Redis**
- **Instance Type**: cache.t4g.micro (dev), cache.t4g.small (prod)
- **Deployment**: Single node (dev), Multi-AZ (prod)
- **Cost**: ~$3/month (dev), ~$6/month (prod)

**Why ElastiCache:**
- Managed Redis (no operational overhead)
- Existing Redis code works as-is
- Used for caching, sessions, and Celery broker
- Graviton2 instances (t4g) are cheapest

### Storage Layer
**Amazon S3**
- **Storage Class**: S3 Intelligent-Tiering
- **Use Cases**: Static assets, user uploads, backups, logs
- **Lifecycle Policies**: Move to Glacier after 90 days
- **Cost**: ~$1-5/month for typical usage

**Amazon CloudFront (CDN)**
- **Use Cases**: Static assets, API caching
- **Free Tier**: 1 TB data transfer/month
- **Cost**: Free tier covers most hobby project needs

### Networking Layer
**Amazon VPC**
- **CIDR**: 10.0.0.0/16
- **Subnets**: 
  - Public: 10.0.1.0/24, 10.0.2.0/24 (2 AZs) - For ECS tasks and ALB
  - Private: 10.0.10.0/24, 10.0.11.0/24 (2 AZs) - For RDS and ElastiCache
- **No NAT Gateway/Instance**: ECS tasks in public subnets with direct internet access
  - **Cost**: $0 (saves $3-32/month!)
  - **Security**: Tight security groups (see Security Groups section below)
  - **Rationale**: Simpler, cheaper, equally secure with proper SG rules
- **VPC Endpoints**: S3, ECR, CloudWatch Logs, Secrets Manager (PrivateLink)
  - Free for most services
  - No internet/NAT needed for AWS API calls
  - More secure (traffic stays in AWS network)

**Security Groups (CRITICAL - Zero Trust Model)**

*ALB Security Group:*
- **Inbound**: 
  - Port 443 (HTTPS) from 0.0.0.0/0 (CloudFront or public)
  - Port 80 (HTTP) from 0.0.0.0/0 (redirect to HTTPS)
- **Outbound**: 
  - Port 8000 to ECS Security Group ONLY

*ECS Tasks Security Group:*
- **Inbound**: 
  - Port 8000 from ALB Security Group ONLY (no public access!)
- **Outbound**: 
  - Port 443 to 0.0.0.0/0 (external APIs: Spotify, Setlist.fm)
  - Port 5432 to RDS Security Group ONLY
  - Port 6379 to Redis Security Group ONLY
  - Port 443 to VPC CIDR (VPC Endpoints)

*RDS Security Group:*
- **Inbound**: 
  - Port 5432 from ECS Security Group ONLY (no public access!)
- **Outbound**: 
  - None (database doesn't initiate connections)

*ElastiCache Redis Security Group:*
- **Inbound**: 
  - Port 6379 from ECS Security Group ONLY (no public access!)
- **Outbound**: 
  - None (cache doesn't initiate connections)

**Key Security Principles:**
- ✅ Least privilege (only allow what's needed)
- ✅ No direct public access to ECS tasks (only via ALB)
- ✅ Databases in private subnets (no internet access)
- ✅ Security group references (not CIDR blocks where possible)
- ✅ Explicit deny by default (AWS default)
- ✅ Regular security group audits in Terraform

**Application Load Balancer**
- **Type**: ALB (Layer 7)
- **Features**: Path-based routing, health checks, SSL termination
- **Cost**: ~$16/month + data transfer

**Why ALB over API Gateway:**
- Better for containerized apps
- WebSocket support needed
- More cost-effective for steady traffic
- Simpler integration with ECS

### Security Layer
**AWS Secrets Manager**
- **Secrets**: Database credentials, API keys, JWT secrets
- **Rotation**: Automated for RDS
- **Cost**: $0.40/secret/month (~$5/month total)

**AWS WAF**
- **Rules**: Rate limiting, SQL injection, XSS protection
- **Cost**: $5/month + $1/rule (~$8/month)

**AWS Certificate Manager**
- **SSL Certificates**: Free
- **Auto-Renewal**: Yes


### Monitoring & Observability
**Amazon CloudWatch**
- **Logs**: All application and infrastructure logs
- **Metrics**: Custom application metrics + AWS service metrics
- **Alarms**: Critical alerts (errors, latency, costs)
- **Dashboards**: Application and infrastructure views
- **Log Retention**: 7 days (dev), 30 days (prod)
- **Cost**: Free tier covers most needs (~$5/month if exceeded)

**AWS X-Ray**
- **Tracing**: Distributed tracing across all services
- **Free Tier**: 100K traces/month
- **Cost**: Free tier sufficient for hobby project

### CI/CD Layer
**GitHub Actions**
- **Cost**: Free for public repositories
- **Workflows**: Build, test, deploy
- **Runners**: GitHub-hosted (free)

**Amazon ECR**
- **Container Registry**: Store Docker images
- **Cost**: $0.10/GB/month (~$2-5/month)

**AWS CodeDeploy**
- **Deployment**: Blue-green deployments for ECS
- **Cost**: Free (pay for compute only)

## Clean Architecture Implementation

### Current Problems
1. **Direct Database Access**: API endpoints query database directly
2. **No Service Layer**: Business logic mixed with HTTP handling
3. **Tight Coupling**: Hard to test, hard to change
4. **No Dependency Injection**: Services instantiated inline

### Target Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Controllers                          │
│  (HTTP handling, request/response, validation)          │
│  - api/v1/controllers/artist_controller.py              │
│  - api/v1/controllers/festival_controller.py            │
└────────────────────┬────────────────────────────────────┘
                     │ depends on
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   Service Layer                          │
│  (Business logic, orchestration, caching)                │
│  - services/artist_service.py                            │
│  - services/festival_service.py                          │
│  - services/playlist_service.py                          │
└────────────────────┬────────────────────────────────────┘
                     │ depends on
                     ▼
┌─────────────────────────────────────────────────────────┐
│                 Repository Layer                         │
│  (Database operations, queries, transactions)            │
│  - repositories/artist_repository.py (EXISTS)            │
│  - repositories/festival_repository.py                   │
│  - repositories/playlist_repository.py                   │
└────────────────────┬────────────────────────────────────┘
                     │ depends on
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   Models Layer                           │
│  (SQLAlchemy models, database schema)                    │
│  - models/artist.py                                      │
│  - models/festival.py                                    │
└─────────────────────────────────────────────────────────┘
```

### Refactoring Requirements

**Phase 1: Repository Layer**
- ✅ ArtistRepository exists and follows pattern
- ❌ Create FestivalRepository
- ❌ Create PlaylistRepository
- ❌ Create SetlistRepository
- ❌ Create UserRepository

**Phase 2: Service Layer**
- ❌ Create ArtistService (uses ArtistRepository)
- ❌ Create FestivalService (uses FestivalRepository)
- ❌ Create PlaylistService (uses PlaylistRepository)
- ❌ Refactor existing services to use repositories
- ❌ Add caching at service layer

**Phase 3: Controller Layer**
- ❌ Refactor api/endpoints/artists.py to use ArtistService
- ❌ Refactor api/endpoints/festivals.py to use FestivalService
- ❌ Refactor api/endpoints/playlists.py to use PlaylistService
- ❌ Remove all direct database access from controllers
- ❌ Controllers only handle HTTP concerns


## Infrastructure as Code (Terraform)

### Daily Teardown/Rebuild Requirements

**Critical Design Principle**: All infrastructure must support daily destroy/provision cycles without data loss or manual intervention.

**Data Persistence Strategy:**

1. **Database (Aurora Serverless v2)**
   - Automated snapshot before `terraform destroy`
   - Terraform creates from latest snapshot on `terraform apply`
   - Snapshot retention: 7 days (free)
   - Restore time: ~5-10 minutes

2. **Cache (ElastiCache Redis)**
   - No persistence needed (cache data is ephemeral)
   - Rebuilds empty on provision

3. **Object Storage (S3)**
   - Never destroyed (excluded from teardown)
   - Persists across teardown/rebuild cycles
   - Stores: backups, logs, user uploads, Terraform state

4. **Secrets (Secrets Manager)**
   - Never destroyed (excluded from teardown)
   - Persists across teardown/rebuild cycles

5. **Container Images (ECR)**
   - Never destroyed (excluded from teardown)
   - Images persist for deployment

**Terraform Lifecycle Management:**

```hcl
# Example: Prevent accidental deletion of persistent resources
resource "aws_s3_bucket" "persistent" {
  lifecycle {
    prevent_destroy = true
  }
}

# Example: Create DB from latest snapshot
resource "aws_db_instance" "main" {
  snapshot_identifier = data.aws_db_snapshot.latest.id
  # ... other config
}
```

**Teardown/Rebuild Scripts:**

```bash
# scripts/teardown.sh
#!/bin/bash
# 1. Create database snapshot
# 2. Wait for snapshot completion
# 3. terraform destroy (excludes S3, Secrets Manager, ECR)
# 4. Verify destruction
# Time: ~10 minutes

# scripts/provision.sh
#!/bin/bash
# 1. terraform apply (restores from latest snapshot)
# 2. Wait for health checks
# 3. Run smoke tests
# 4. Notify completion
# Time: ~15 minutes
```

### Project Structure
```
terraform/
├── main.tf                # Main configuration
├── variables.tf           # Input variables
├── outputs.tf             # Output values
├── backend.tf             # S3 backend configuration
├── terraform.tfvars       # Variable values
├── modules/
│   ├── networking/        # VPC, subnets, security groups
│   ├── database/          # Aurora Serverless v2
│   ├── cache/             # ElastiCache Redis
│   ├── compute/           # ECS Fargate
│   ├── storage/           # S3 buckets
│   ├── cdn/               # CloudFront
│   ├── monitoring/        # CloudWatch, X-Ray
│   └── security/          # WAF, Secrets Manager
├── scripts/
│   ├── init-backend.sh    # Initialize S3 + DynamoDB for state
│   ├── teardown.sh        # Snapshot DB + terraform destroy
│   ├── provision.sh       # Terraform apply + restore from snapshot
│   └── cost-estimate.sh   # Infracost estimation
└── README.md
```

### Terraform Requirements
- **Version**: >= 1.5
- **State Backend**: S3 with DynamoDB locking
- **State Encryption**: Yes (S3 server-side encryption)
- **Workspaces**: One per environment (dev, staging, prod)
- **Modules**: Reusable, well-documented
- **Variables**: Environment-specific tfvars files
- **Outputs**: All important resource IDs and endpoints
- **Cost Estimation**: Integrated with Infracost

### Key Features
1. **Tear Down Capability**: `terraform destroy` removes all resources
2. **Cost Estimation**: See costs before applying changes
3. **Idempotent**: Can run multiple times safely
4. **Modular**: Reusable modules for each AWS service
5. **Documented**: README for each module
6. **Validated**: Terraform validate + tflint in CI

## CI/CD Pipeline (GitHub Actions)

### Workflows

**1. Pull Request Workflow** (`.github/workflows/pr.yml`)
```yaml
Triggers: Pull request to main
Jobs:
  - Lint code (black, isort, flake8)
  - Type check (mypy)
  - Security scan (bandit, safety)
  - Unit tests (pytest)
  - Integration tests (pytest with test database)
  - Build Docker image
  - Terraform validate
  - Terraform plan (comment on PR)
  - Cost estimation (Infracost comment on PR)
```

**2. Deploy to Dev** (`.github/workflows/deploy-dev.yml`)
```yaml
Triggers: Push to main branch
Jobs:
  - Run all PR checks
  - Build and push Docker image to ECR
  - Terraform apply to dev environment
  - Run smoke tests
  - Notify on Slack/Discord
```

**3. Deploy to Production** (`.github/workflows/deploy-prod.yml`)
```yaml
Triggers: Manual workflow dispatch or tag push
Jobs:
  - Manual approval required
  - Run all tests
  - Build and push Docker image to ECR
  - Terraform plan (review required)
  - Blue-green deployment to ECS
  - Run smoke tests
  - Rollback on failure
  - Notify on Slack/Discord
```

**4. Destroy Environment** (`.github/workflows/destroy.yml`)
```yaml
Triggers: Manual workflow dispatch
Jobs:
  - Manual approval required
  - Backup database
  - Terraform destroy
  - Confirm destruction
```

### GitHub Actions Secrets
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `ECR_REPOSITORY`
- `TERRAFORM_CLOUD_TOKEN` (optional)


## Testing Strategy

### Test Coverage Requirements
- **Unit Tests**: 80%+ coverage
- **Integration Tests**: All API endpoints
- **E2E Tests**: Critical user flows
- **Load Tests**: Performance validation

### Test Types

**1. Unit Tests**
- Repository layer: 90% coverage
- Service layer: 85% coverage
- Controller layer: 80% coverage
- Test frameworks: pytest, pytest-asyncio
- Mocking: pytest-mock
- Property-based: hypothesis

**2. Integration Tests**
- API endpoint tests with test database
- Database transaction tests
- Cache integration tests
- External API mocking (Spotify, Setlist.fm)
- Test containers for PostgreSQL and Redis

**3. E2E Tests**
- Critical user flows (create playlist, search artists)
- Playwright for web UI testing
- API workflow testing
- Run in staging environment

**4. Load Tests**
- Locust or k6 for load testing
- Target: 1,000 concurrent users
- Run before production deployment
- Identify bottlenecks

## Migration Strategy (4 Weeks)

### Week 1: Foundation & Architecture
**Goals**: Set up AWS account, Terraform, clean architecture

**Tasks**:
1. AWS account setup with billing alerts
2. Terraform project structure
3. S3 + DynamoDB for Terraform state
4. Implement Repository layer (Festival, Playlist, Setlist, User)
5. Implement Service layer (Artist, Festival, Playlist)
6. Write unit tests for repositories and services
7. GitHub Actions CI workflow

**Deliverables**:
- AWS account configured
- Terraform project initialized
- Repository layer complete
- Service layer complete
- 80%+ test coverage
- CI pipeline running

### Week 2: Infrastructure Provisioning
**Goals**: Provision AWS infrastructure via Terraform

**Tasks**:
1. VPC, subnets, security groups (networking module)
2. Aurora Serverless v2 (database module)
3. ElastiCache Redis (cache module)
4. S3 buckets (storage module)
5. ECR repository (compute module)
6. Secrets Manager (security module)
7. CloudWatch Logs and Alarms (monitoring module)
8. Test infrastructure with sample application

**Deliverables**:
- All Terraform modules complete
- Dev environment provisioned
- Infrastructure tested and validated
- Cost tracking dashboard

### Week 3: Application Migration
**Goals**: Containerize and deploy application to AWS

**Tasks**:
1. Refactor controllers to use service layer
2. Update configuration for AWS services
3. ECS task definitions and services
4. Application Load Balancer configuration
5. CloudFront CDN setup
6. Deploy application to dev environment
7. Integration testing in AWS
8. Performance testing and optimization

**Deliverables**:
- Controllers refactored
- Application running on ECS Fargate
- ALB routing traffic
- CloudFront serving static assets
- All tests passing in AWS environment

### Week 4: CI/CD & Production
**Goals**: Automate deployments and go live

**Tasks**:
1. GitHub Actions deployment workflows
2. Blue-green deployment setup
3. Staging environment provisioning
4. Data migration scripts and testing
5. Production environment provisioning
6. Production deployment
7. Monitoring and alerting validation
8. Documentation and runbooks

**Deliverables**:
- Automated CI/CD pipeline
- Staging environment live
- Production environment live
- Data migrated successfully
- Monitoring and alerts configured
- Complete documentation


## Success Metrics

### Technical Metrics
- **Infrastructure as Code**: 100% of AWS resources in Terraform
- **Automated Deployments**: 100% via GitHub Actions
- **Test Coverage**: > 80% across all layers
- **API Response Time**: < 200ms (p95)
- **Deployment Time**: < 10 minutes
- **Zero-Downtime Deployments**: Yes
- **Failed Deployment Rate**: < 5%

### Cost Metrics
- **Environment (active 8hrs/day)**: $8-10/month
- **Environment (torn down)**: $2-5/month
- **Total Cost with Daily Teardown**: $10-15/month
- **Cost per User**: < $0.10/month
- **No Surprise Charges**: Alerts at 80% of budget
- **Teardown Savings**: ~$5-9/month vs running 24/7

### Operational Metrics
- **Deployment Frequency**: Multiple per week
- **Mean Time to Recovery**: < 30 minutes
- **Manual Interventions**: Minimal (< 1 per week)
- **Uptime**: 99.5%+
- **Time to Provision Environment**: < 15 minutes

### Quality Metrics
- **Code Review**: 100% of changes reviewed
- **Security Scans**: Pass on every deployment
- **Documentation**: Complete for all modules
- **Rollback Success Rate**: 100%

## Out of Scope (Phase 1)

The following are explicitly out of scope for the initial 4-week migration:

1. **Multi-Region Deployment**: Single region (us-east-1) only
2. **Kubernetes/EKS**: Too expensive and complex for hobby project
3. **Elasticsearch**: Use PostgreSQL full-text search instead
4. **SQS/SNS**: Use Redis for queuing initially
5. **Custom Domain**: Use ALB DNS initially (can add later)
6. **CloudFormation**: Using Terraform instead
7. **Lambda Functions**: Using ECS Fargate for consistency
8. **DynamoDB**: Keeping PostgreSQL
9. **API Gateway**: Using ALB instead
10. **Advanced Monitoring**: Basic CloudWatch sufficient initially
11. **Disaster Recovery**: Basic backups only (no multi-region DR)
12. **Blue-Green at DNS Level**: Blue-green at ECS level only

## Constraints

### Budget Constraints
- **Hard Limit**: $30/month (daily teardown achieves this easily!)
- **Target**: $10-15/month with daily teardown
- **Cost Alerts**: Must be configured before any resources created
- **Daily Teardown Required**: Must destroy environment when not in use
- **Fast Rebuild Required**: Provision time < 15 minutes

### Time Constraints
- **Timeline**: 4 weeks total
- **Solo Developer**: All work done by one person
- **Learning Curve**: Time for learning GitHub Actions and Terraform
- **Testing Time**: Adequate time for testing in each phase

### Technical Constraints
- **AWS Region**: us-east-1 (cheapest, most services)
- **Database**: Must remain PostgreSQL (no migration to DynamoDB)
- **Existing Code**: Minimize code changes where possible
- **Python Version**: 3.11+ (current version)
- **Container-Based**: Must use containers (existing Docker setup)

### Operational Constraints
- **Solo Maintenance**: Must be manageable by one person
- **Availability**: 99.5% acceptable (not 99.99%)
- **Support**: No 24/7 on-call (hobby project)
- **Complexity**: Keep it simple (managed services preferred)


## Dependencies

### Required Tools
- **AWS Account**: With billing alerts configured
- **Terraform**: >= 1.5 installed locally
- **AWS CLI**: >= 2.0 configured with credentials
- **Docker**: For local development and testing
- **Python**: 3.11+ with virtual environment
- **Git**: For version control
- **GitHub Account**: For Actions (can be free tier)

### Required Knowledge
- **AWS Basics**: VPC, EC2, RDS, S3 concepts
- **Terraform**: Basic syntax and workflow
- **Docker**: Container concepts and Dockerfile
- **CI/CD**: Basic GitHub Actions understanding
- **Python**: FastAPI, SQLAlchemy, async/await

### External Dependencies
- **GitHub**: Repository hosting and Actions
- **AWS**: Cloud infrastructure provider
- **External APIs**: Spotify, Setlist.fm (existing)

## Risks & Mitigations

### Risk 1: Cost Overruns
**Impact**: High (project sustainability)  
**Probability**: Medium  
**Mitigation**:
- Set up billing alerts at $25, $50, $75 BEFORE creating resources
- Use AWS Budgets with automatic notifications
- Weekly cost reviews in first month
- Conservative auto-scaling limits (max 4 tasks)
- Spot instances for workers (70% savings)
- Auto-pause Aurora in dev (saves ~$200/month)
- Document teardown procedure and use regularly
- Infracost in CI/CD to preview costs

### Risk 2: Learning Curve (Terraform + GitHub Actions)
**Impact**: Medium (timeline delay)  
**Probability**: High  
**Mitigation**:
- Start with simple Terraform modules
- Use official AWS Terraform provider examples
- GitHub Actions has excellent documentation
- Allocate extra time in Week 1 for learning
- Use Terraform Cloud free tier for state management (optional)
- Community support (Terraform Discord, GitHub Discussions)

### Risk 3: Data Migration Issues
**Impact**: High (data loss)  
**Probability**: Low  
**Mitigation**:
- Comprehensive database backup before migration
- Test migration in dev environment first
- Test migration in staging environment second
- Use pg_dump/pg_restore (standard PostgreSQL tools)
- Parallel run period (keep old system running)
- Rollback plan documented
- Data validation scripts

### Risk 4: Complexity Overwhelm (Solo Developer)
**Impact**: High (burnout, project abandonment)  
**Probability**: Medium  
**Mitigation**:
- Use managed services (minimize operational overhead)
- Start simple, add complexity only when needed
- Comprehensive documentation for future self
- Automated monitoring and alerts
- Self-healing infrastructure where possible
- Clear runbooks for common tasks
- Take breaks, don't rush

### Risk 5: GitHub Actions Costs (if private repo)
**Impact**: Low (can switch to public)  
**Probability**: Low  
**Mitigation**:
- Use public repository (free Actions)
- If private: 2,000 minutes/month free
- Optimize workflow efficiency
- Cache dependencies to speed up builds
- Alternative: Self-hosted runner on cheap VPS

### Risk 6: Aurora Serverless v2 Costs Higher Than Expected
**Impact**: Medium (budget exceeded)  
**Probability**: Medium  
**Mitigation**:
- Start with 0.5 ACU minimum (lowest possible)
- Enable auto-pause in dev (5 minutes)
- Monitor ACU usage closely
- Set maximum ACU limit (2 ACU initially)
- Fallback: Switch to RDS t4g.micro if needed
- Optimize queries to reduce database load

### Risk 7: Security Group Misconfiguration
**Impact**: Critical (potential data breach)  
**Probability**: Medium  
**Mitigation**:
- Security groups defined in Terraform (version controlled)
- Automated security group auditing in CI/CD
- Use security group references instead of CIDR blocks
- Principle of least privilege enforced
- Regular security reviews
- CloudWatch alarms for security group changes
- VPC Flow Logs to monitor traffic patterns
- Penetration testing before production
- Security group rules documented inline in Terraform
- Peer review required for all security group changes


## Assumptions

### Technical Assumptions
- Current codebase is in working state
- Existing Docker setup is functional
- Database schema is stable (no major migrations needed)
- External APIs (Spotify, Setlist.fm) will remain available
- Python 3.11 is sufficient (no need to upgrade)
- Current data volume is small (< 10GB)

### Business Assumptions
- Traffic will remain low initially (< 1,000 users)
- Hobby project status (not mission-critical)
- Solo developer has time to dedicate (10-20 hours/week)
- Can tolerate some downtime during migration
- No strict compliance requirements (HIPAA, PCI-DSS, etc.)

### AWS Assumptions
- AWS Free Tier benefits available (new account or within limits)
- us-east-1 region is acceptable (no geographic requirements)
- AWS services will remain available and pricing stable
- GitHub Actions will remain free for public repos
- Terraform AWS provider will remain stable

### Cost Assumptions
- Traffic patterns are predictable
- Database queries are optimized
- External API calls are reasonable
- No sudden viral growth
- Can tear down dev environment when not in use

## Acceptance Criteria (Overall)

The migration is considered successful when ALL of the following are met:

### Infrastructure
- [ ] 100% of AWS resources defined in Terraform
- [ ] **Can destroy entire environment with single command**
- [ ] **Can provision entire environment with single command**
- [ ] **Provision time < 15 minutes**
- [ ] **Destroy time < 10 minutes**
- [ ] **Automated database snapshot before destroy**
- [ ] **Automated database restore from snapshot on provision**
- [ ] **S3, Secrets Manager, ECR persist across teardown/rebuild**
- [ ] Terraform state in S3 with DynamoDB locking
- [ ] **Daily teardown/rebuild tested and documented**

### Application
- [ ] All controllers refactored to use service layer
- [ ] No direct database access in controllers
- [ ] All repositories implemented (Artist, Festival, Playlist, Setlist, User)
- [ ] All services implemented with dependency injection
- [ ] 80%+ test coverage achieved
- [ ] All tests passing in CI/CD

### Deployment
- [ ] GitHub Actions CI/CD pipeline working
- [ ] Automated deployment to dev on merge to main
- [ ] Manual approval for production deployments
- [ ] Blue-green deployment working
- [ ] Rollback capability tested and working
- [ ] Deployment time < 10 minutes

### Observability
- [ ] CloudWatch Logs collecting all application logs
- [ ] CloudWatch Metrics tracking key performance indicators
- [ ] CloudWatch Alarms configured for critical issues
- [ ] X-Ray tracing working across all services
- [ ] Cost monitoring dashboard created
- [ ] Alerts configured and tested

### Security
- [ ] All secrets in AWS Secrets Manager
- [ ] IAM roles with least privilege
- [ ] VPC with private subnets for databases
- [ ] **Security groups configured with zero-trust model**
- [ ] **ECS tasks ONLY accessible via ALB (no direct public access)**
- [ ] **RDS/Redis ONLY accessible from ECS tasks**
- [ ] **Security group rules use SG references (not CIDR)**
- [ ] AWS WAF protecting API
- [ ] SSL/TLS everywhere
- [ ] Security scanning in CI/CD passing
- [ ] VPC Flow Logs enabled
- [ ] Security group change alerts configured

### Performance
- [ ] **Custom domain gig-prep.co.uk configured**
- [ ] **SSL/TLS certificate from ACM installed**
- [ ] **CloudFront using custom domain**
- [ ] **ALB using custom domain with SSL**
- [ ] API response time < 200ms (p95)
- [ ] Page load time < 3 seconds (p95)
- [ ] Database queries < 100ms (p95)
- [ ] Auto-scaling working correctly
- [ ] Load testing passed (1,000 concurrent users)

### Cost
- [ ] **Environment with daily teardown costs $10-15/month**
- [ ] Active costs $8-10/month (partial month)
- [ ] Torn down costs $2-5/month
- [ ] **AWS Budgets configured with thresholds at $10, $20, $30**
- [ ] **AWS Cost Anomaly Detection enabled and alerting**
- [ ] **Budget actions sending SNS notifications**
- [ ] **Cost allocation tags applied to all resources**
- [ ] Cost alerts configured and tested
- [ ] No surprise charges in first month
- [ ] **Teardown/rebuild scripts working and documented**

### Documentation
- [ ] README with setup instructions
- [ ] Terraform modules documented
- [ ] Architecture diagrams created
- [ ] Runbooks for common operations
- [ ] Troubleshooting guide
- [ ] Cost optimization guide

### Migration
- [ ] Data successfully migrated to Aurora
- [ ] All existing features working in AWS
- [ ] No data loss during migration
- [ ] Old environment can be decommissioned
- [ ] Users can access application via ALB/CloudFront

## Next Steps

Once these requirements are approved:

1. **Create Design Document** (`design.md`)
   - Detailed architecture diagrams
   - Terraform module specifications
   - Service layer design patterns
   - API endpoint specifications
   - Database schema updates
   - CI/CD pipeline details

2. **Create Task List** (`tasks.md`)
   - Break down into actionable tasks
   - Organize by week (4-week timeline)
   - Assign priorities
   - Define dependencies
   - Estimate effort

3. **Begin Implementation**
   - Week 1: Foundation & Architecture
   - Week 2: Infrastructure Provisioning
   - Week 3: Application Migration
   - Week 4: CI/CD & Production
