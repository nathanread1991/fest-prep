# Implementation Plan: AWS Enterprise Migration

## Overview

This implementation plan guides the migration of the Festival Playlist Generator from local Docker deployment to AWS infrastructure over 4 weeks. The plan prioritizes cost optimization through daily teardown capability, clean architecture refactoring, and Infrastructure as Code principles. All tasks are designed for a solo developer working on a hobby project with a target cost of $10-15/month.

## Timeline

- **Week 1**: Foundation & Architecture (clean architecture, repos, services, tests)
- **Week 2**: Infrastructure Provisioning (Terraform modules, AWS setup)
- **Week 3**: Application Migration (containerization, ECS deployment, integration)
- **Week 4**: CI/CD & Production (GitHub Actions, monitoring, go-live)

## Tasks

### Week 1: Foundation & Architecture

- [x] 1. Set up AWS account and configure billing alerts
  - Create AWS account or use existing account
  - Enable AWS Cost Explorer and Cost Anomaly Detection
  - Configure AWS Budgets with alerts at $10, $20, $30 thresholds
  - Set up SNS topic for budget notifications
  - Configure cost allocation tags strategy
  - _Requirements: US-3.6, US-3.7_

- [x] 2. Initialize Terraform project structure
  - [x] 2.1 Create Terraform directory structure with modules
    - Create `terraform/` root directory
    - Create module directories: `networking/`, `database/`, `cache/`, `compute/`, `storage/`, `cdn/`, `monitoring/`, `security/`
    - Create `main.tf`, `variables.tf`, `outputs.tf`, `backend.tf` in root
    - Create `terraform.tfvars.example` for variable documentation
    - _Requirements: US-1.1, US-8.7_
  
  - [x] 2.2 Set up S3 backend for Terraform state
    - Create S3 bucket for Terraform state with versioning enabled
    - Create DynamoDB table for state locking
    - Configure backend.tf with S3 and DynamoDB
    - Enable server-side encryption on state bucket
    - Test state initialization with `terraform init`
    - _Requirements: US-1.2, US-8.7_
  
  - [x] 2.3 Create base Terraform configuration
    - Define AWS provider configuration
    - Create common variables (region, environment, project name)
    - Set up cost allocation tags as default tags
    - Create outputs for key resource identifiers
    - _Requirements: US-3.5, US-8.7_


- [x] 3. Implement Repository layer for all entities
  - [x] 3.1 Create BaseRepository abstract class
    - Implement generic CRUD operations (get_by_id, get_all, create, update, delete)
    - Add async/await support with AsyncSession
    - Include type hints with Generic[T]
    - Add docstrings for all methods
    - _Requirements: US-4.1, US-4.3_
  
  - [x] 3.2 Create FestivalRepository
    - Extend BaseRepository with Festival model
    - Implement get_by_name, get_upcoming_festivals, search_festivals methods
    - Add proper indexing hints in queries
    - _Requirements: US-4.1_
  
  - [x] 3.3 Create PlaylistRepository
    - Extend BaseRepository with Playlist model
    - Implement get_by_user, get_by_festival, get_by_spotify_id methods
    - Add relationship loading for festival and tracks
    - _Requirements: US-4.1_
  
  - [x] 3.4 Create SetlistRepository
    - Extend BaseRepository with Setlist model
    - Implement get_by_artist, get_by_setlistfm_id, get_recent_setlists methods
    - Add relationship loading for songs
    - _Requirements: US-4.1_
  
  - [x] 3.5 Create UserRepository
    - Extend BaseRepository with User model
    - Implement get_by_email, get_by_username, get_by_spotify_id methods
    - Add secure password handling methods
    - _Requirements: US-4.1_
  
  - [x] 3.6 Write unit tests for all repositories
    - Test CRUD operations for each repository
    - Use in-memory SQLite for test database
    - Mock database sessions with pytest fixtures
    - Achieve 90%+ coverage for repository layer
    - _Requirements: US-4.7_

- [x] 4. Implement Service layer with business logic
  - [x] 4.1 Create CacheService for Redis operations
    - Implement get, set, delete, delete_pattern, exists methods
    - Add TTL support and JSON serialization
    - Include connection pooling configuration
    - _Requirements: US-4.2_
  
  - [x] 4.2 Create ArtistService
    - Inject ArtistRepository and CacheService dependencies
    - Implement get_artist_by_id with caching (1 hour TTL)
    - Implement search_artists with caching (5 min TTL)
    - Add cache invalidation on create/update/delete
    - _Requirements: US-4.2, US-4.6_
  
  - [x] 4.3 Create FestivalService
    - Inject FestivalRepository, ArtistRepository, and CacheService
    - Implement get_festival_by_id, create_festival, search_festivals
    - Add artist validation in create_festival
    - Implement cache invalidation strategy
    - _Requirements: US-4.2, US-4.6_
  
  - [x] 4.4 Create PlaylistService
    - Inject PlaylistRepository, FestivalRepository, and CacheService
    - Implement create_playlist, get_user_playlists, sync_to_spotify
    - Add Spotify API integration with circuit breaker
    - Implement retry logic with exponential backoff
    - _Requirements: US-4.2, US-4.6, US-7.6_
  
  - [x] 4.5 Create SpotifyService with circuit breaker
    - Implement CircuitBreaker class (closed/open/half-open states)
    - Add search_artist, create_playlist, add_tracks_to_playlist methods
    - Implement token refresh logic
    - Add comprehensive error handling
    - _Requirements: US-7.6_
  
  - [x] 4.6 Create SetlistFmService with circuit breaker
    - Implement circuit breaker for Setlist.fm API
    - Add get_artist_setlists, get_setlist_by_id methods
    - Implement retry logic with exponential backoff
    - Add rate limiting awareness
    - _Requirements: US-7.6_
  
  - [x] 4.7 Write unit tests for all services
    - Mock repository dependencies with AsyncMock
    - Test caching behavior (cache hit/miss scenarios)
    - Test circuit breaker states and transitions
    - Test error handling and retry logic
    - Achieve 90%+ coverage for service layer
    - _Requirements: US-4.7_


- [x] 5. Refactor Controllers to use Service layer
  - [x] 5.1 Set up dependency injection container
    - Install dependency-injector package
    - Create Container class in core/container.py
    - Configure providers for all repositories and services
    - Add database session and Redis client providers
    - _Requirements: US-4.4_
  
  - [x] 5.2 Refactor artist endpoints to use ArtistService
    - Update api/v1/controllers/artist_controller.py
    - Remove direct database access (session.query, etc.)
    - Inject ArtistService via Depends()
    - Keep only HTTP concerns (validation, serialization, status codes)
    - _Requirements: US-4.4, US-4.5_
  
  - [x] 5.3 Refactor festival endpoints to use FestivalService
    - Update api/v1/controllers/festival_controller.py
    - Remove direct database access
    - Inject FestivalService via Depends()
    - Add proper error handling with ErrorResponse model
    - _Requirements: US-4.4, US-4.5_
  
  - [x] 5.4 Refactor playlist endpoints to use PlaylistService
    - Update api/v1/controllers/playlist_controller.py
    - Remove direct database access
    - Inject PlaylistService via Depends()
    - Add authentication/authorization checks
    - _Requirements: US-4.4, US-4.5_
  
  - [x] 5.5 Refactor user endpoints to use UserService
    - Update api/v1/controllers/user_controller.py
    - Remove direct database access
    - Inject UserService via Depends()
    - Implement JWT authentication middleware
    - _Requirements: US-4.4, US-4.5_
  
  - [x] 5.6 Write integration tests for refactored endpoints
    - Use testcontainers for PostgreSQL and Redis
    - Test all API endpoints with real database
    - Verify clean architecture (no direct DB access in controllers)
    - Test authentication and authorization flows
    - Achieve 90%+ coverage within Controllers
    - _Requirements: US-4.7_

- [x] 6. Implement structured logging and error handling
  - [x] 6.1 Create JSONFormatter for structured logging
    - Implement custom logging formatter with JSON output
    - Include required fields: timestamp, level, message, request_id, service_name
    - Add exception tracking with stack traces
    - Configure log levels per environment
    - _Requirements: US-5.1, US-5.7_
  
  - [x] 6.2 Add request ID middleware
    - Create FastAPI middleware to generate/extract request IDs
    - Store request ID in context variable
    - Add X-Request-ID header to all responses
    - Propagate request ID to all log entries
    - _Requirements: US-5.7_
  
  - [x] 6.3 Implement global exception handlers
    - Create handlers for ValidationError, SQLAlchemyError, HTTPException
    - Return standardized ErrorResponse format
    - Log all exceptions with request context
    - Add circuit breaker exception handler
    - _Requirements: US-7.6_
  
  - [x] 6.4 Add transaction context manager
    - Create async context manager for database transactions
    - Implement automatic rollback on exceptions
    - Add transaction logging
    - _Requirements: US-4.2_

- [x] 7. Set up GitHub Actions CI workflow
  - [x] 7.1 Create PR validation workflow
    - Create .github/workflows/pr.yml
    - Add linting jobs (black, isort, flake8)
    - Add type checking with mypy
    - Add security scanning (bandit, safety)
    - _Requirements: US-2.2_
  
  - [x] 7.2 Add test jobs to PR workflow
    - Configure PostgreSQL and Redis services
    - Run unit tests with coverage reporting
    - Run integration tests with testcontainers
    - Upload coverage to Codecov
    - Fail PR if coverage < 80%
    - _Requirements: US-2.2, US-4.7_
  
  - [x] 7.3 Add Docker build job
    - Build Docker image in PR workflow
    - Use Docker layer caching
    - Validate Dockerfile
    - _Requirements: US-2.6_

- [x] 8. Checkpoint - Week 1 Review
  - Verify all repositories implemented and tested
  - Verify all services implemented and tested
  - Verify controllers refactored (no direct DB access)
  - Verify 90%+ test coverage achieved
  - Verify CI pipeline running successfully
  - Ensure all tests pass, ask the user if questions arise.


### Week 2: Infrastructure Provisioning

- [ ] 9. Create Terraform networking module
  - [ ] 9.1 Implement VPC and subnets
    - Create VPC with CIDR 10.0.0.0/16
    - Create 2 public subnets (10.0.1.0/24, 10.0.2.0/24) in different AZs
    - Create 2 private subnets (10.0.10.0/24, 10.0.11.0/24) in different AZs
    - Create Internet Gateway and attach to VPC
    - Create route tables for public subnets (route to IGW)
    - _Requirements: US-6.4_
  
  - [ ] 9.2 Implement security groups with zero-trust model
    - Create ALB security group (allow 80/443 from 0.0.0.0/0, egress to ECS SG only)
    - Create ECS security group (allow 8000 from ALB SG, egress to RDS/Redis/internet)
    - Create RDS security group (allow 5432 from ECS SG only, no egress)
    - Create Redis security group (allow 6379 from ECS SG only, no egress)
    - Create VPC Endpoints security group (allow 443 from ECS SG)
    - Use security group references instead of CIDR blocks
    - _Requirements: US-6.1_
  
  - [ ] 9.3 Create VPC Endpoints for AWS services
    - Create VPC endpoints for S3 (gateway endpoint, free)
    - Create VPC endpoints for ECR API and Docker (interface endpoints)
    - Create VPC endpoint for CloudWatch Logs
    - Create VPC endpoint for Secrets Manager
    - Associate endpoints with private subnets
    - _Requirements: US-6.4_
  
  - [ ] 9.4 Add networking module outputs
    - Output VPC ID, subnet IDs, security group IDs
    - Output VPC endpoint IDs
    - Document all outputs in README.md
    - _Requirements: US-1.9_

- [ ] 10. Create Terraform database module
  - [ ] 10.1 Implement Aurora Serverless v2 cluster
    - Create RDS subnet group with private subnets
    - Create Aurora PostgreSQL cluster (engine version 15.3)
    - Configure serverless v2 scaling (0.5-4 ACU)
    - Enable auto-pause for dev environment (5 min timeout)
    - Configure backup retention (7 days)
    - Enable encryption at rest with KMS
    - _Requirements: US-1.3, US-6.6_
  
  - [ ] 10.2 Configure snapshot and restore capability
    - Add snapshot_identifier variable for restore
    - Configure final snapshot on destroy
    - Add data source to find latest snapshot
    - Implement conditional restore logic
    - _Requirements: US-1.3, US-1.4, US-1.5_
  
  - [ ] 10.3 Create database credentials in Secrets Manager
    - Generate random password with Terraform
    - Create Secrets Manager secret for DB credentials
    - Store connection URL, host, port, username, password
    - Enable automatic rotation (optional for hobby project)
    - Mark secret as persistent (prevent_destroy = true)
    - _Requirements: US-6.2_
  
  - [ ] 10.4 Enable CloudWatch logging and monitoring
    - Enable PostgreSQL logs export to CloudWatch
    - Enable Performance Insights
    - Create CloudWatch alarms for CPU, memory, connections
    - _Requirements: US-5.2, US-5.3_

- [ ] 11. Create Terraform cache module
  - [ ] 11.1 Implement ElastiCache Redis cluster
    - Create ElastiCache subnet group with private subnets
    - Create Redis cluster (cache.t4g.micro, single node for dev)
    - Configure Redis 7.0 with parameter group
    - Set maxmemory-policy to allkeys-lru
    - Associate with Redis security group
    - _Requirements: US-6.4_
  
  - [ ] 11.2 Store Redis connection URL in Secrets Manager
    - Create Secrets Manager secret for Redis URL
    - Store connection string with host and port
    - Mark secret as persistent
    - _Requirements: US-6.2_


- [ ] 12. Create Terraform storage module
  - [ ] 12.1 Create S3 buckets with security controls
    - Create app-data bucket with versioning enabled
    - Create cloudfront-logs bucket with lifecycle policy (30 day expiration)
    - Enable S3 Intelligent-Tiering on app-data bucket
    - Enable server-side encryption (AES256) on all buckets
    - Block all public access on all buckets
    - Mark buckets as persistent (prevent_destroy = true)
    - _Requirements: US-6.9, US-1.6_
  
  - [ ] 12.2 Create ECR repository for container images
    - Create ECR repository for application images
    - Enable image scanning on push
    - Configure lifecycle policy (keep last 10 images)
    - Mark repository as persistent
    - _Requirements: US-2.6_
  
  - [ ] 12.3 Configure S3 bucket policies
    - Create bucket policy for CloudFront access to app-data
    - Create bucket policy for ALB logs
    - Ensure no public access allowed
    - _Requirements: US-6.9_

- [ ] 13. Create Terraform compute module
  - [ ] 13.1 Create ECS cluster and IAM roles
    - Create ECS Fargate cluster
    - Create ECS task execution role (pull images, write logs, read secrets)
    - Create ECS task role (access to S3, RDS, Redis)
    - Add IAM policies with least privilege
    - _Requirements: US-6.3_
  
  - [ ] 13.2 Create ECS task definition for API service
    - Define task with 0.25 vCPU, 0.5 GB memory
    - Configure container with port 8000
    - Load secrets from Secrets Manager (DB, Redis, Spotify, JWT)
    - Configure CloudWatch Logs with awslogs driver
    - Add health check command (curl /health)
    - _Requirements: US-5.1_
  
  - [ ] 13.3 Create ECS task definition for worker service
    - Define task with 0.25 vCPU, 0.5 GB memory
    - Configure Celery worker command
    - Load secrets from Secrets Manager
    - Configure CloudWatch Logs
    - _Requirements: US-5.1_
  
  - [ ] 13.4 Create ECS services with auto-scaling
    - Create API service (desired count: 1, launch type: FARGATE)
    - Create worker service (desired count: 1, capacity provider: FARGATE_SPOT)
    - Configure network settings (public subnets, ECS security group, assign public IP)
    - Set up auto-scaling for API (1-4 tasks, target CPU 70%)
    - _Requirements: US-6.4_
  
  - [ ] 13.5 Create Application Load Balancer
    - Create ALB in public subnets with ALB security group
    - Create target group for API (port 8000, health check /health)
    - Create HTTPS listener (port 443) with ACM certificate
    - Create HTTP listener (port 80) with redirect to HTTPS
    - Configure deregistration delay (30 seconds)
    - _Requirements: US-7.1, US-7.2_

- [ ] 14. Create Terraform security module
  - [ ] 14.1 Create ACM certificate for custom domain
    - Request certificate for gig-prep.co.uk and *.gig-prep.co.uk
    - Add DNS validation records to Route 53
    - Wait for certificate validation
    - _Requirements: US-7.1, US-7.2_
  
  - [ ] 14.2 Create Route 53 hosted zone and records
    - Create hosted zone for gig-prep.co.uk (or use existing)
    - Create A record for root domain pointing to CloudFront
    - Create A record for api.gig-prep.co.uk pointing to ALB
    - Add CNAME records for certificate validation
    - _Requirements: US-7.3_
  
  - [ ] 14.3 Create AWS WAF for ALB protection
    - Create WAF web ACL
    - Add rate limiting rule (1000 requests per 5 min per IP)
    - Add AWS managed rules (SQL injection, XSS protection)
    - Associate WAF with ALB
    - _Requirements: US-6.7_
  
  - [ ] 14.4 Create additional Secrets Manager secrets
    - Create secret for Spotify API credentials (manual population)
    - Create secret for Setlist.fm API key (manual population)
    - Create secret for JWT signing key (auto-generated)
    - Mark all secrets as persistent
    - _Requirements: US-6.2_


- [ ] 15. Create Terraform CDN module
  - [ ] 15.1 Create CloudFront distribution
    - Create origin for ALB (API traffic)
    - Create origin for S3 (static assets)
    - Configure default cache behavior (forward to ALB, no caching)
    - Configure /static/* cache behavior (S3 origin, 1 day TTL)
    - Use ACM certificate for custom domain
    - Enable compression and HTTP/2
    - _Requirements: US-7.4_
  
  - [ ] 15.2 Configure CloudFront logging
    - Enable access logs to cloudfront-logs S3 bucket
    - Configure log prefix
    - _Requirements: US-5.1_
  
  - [ ] 15.3 Create CloudFront Origin Access Identity
    - Create OAI for S3 bucket access
    - Update S3 bucket policy to allow OAI
    - _Requirements: US-6.9_

- [ ] 16. Create Terraform monitoring module
  - [ ] 16.1 Create CloudWatch Log Groups
    - Create log groups for ECS API service (/ecs/festival-api)
    - Create log groups for ECS worker service (/ecs/festival-worker)
    - Set retention period (7 days for dev, 30 days for prod)
    - _Requirements: US-5.1, US-3.3_
  
  - [ ] 16.2 Create CloudWatch Alarms for critical metrics
    - Create alarm for API error rate (5XX > 10 in 5 min)
    - Create alarm for API latency (p95 > 1000ms)
    - Create alarm for RDS CPU (> 80%)
    - Create alarm for RDS connections (> 80% of max)
    - Create alarm for ECS task count (< 1)
    - Create SNS topic for alarm notifications
    - _Requirements: US-5.3_
  
  - [ ] 16.3 Create CloudWatch Dashboard
    - Add widgets for API request count, latency, errors
    - Add widgets for RDS CPU, memory, connections
    - Add widgets for ECS CPU, memory, task count
    - Add widgets for Redis CPU, memory, connections
    - Add widgets for ALB request count, latency, errors
    - _Requirements: US-5.4_
  
  - [ ] 16.4 Enable AWS X-Ray tracing
    - Enable X-Ray on ECS tasks
    - Add X-Ray daemon sidecar to task definitions
    - Install X-Ray SDK in application
    - Configure sampling rules
    - _Requirements: US-5.5_

- [ ] 17. Create teardown and provision scripts
  - [ ] 17.1 Create teardown script (scripts/teardown.sh)
    - Implement database snapshot creation before destroy
    - Wait for snapshot completion
    - Run terraform destroy (exclude persistent resources)
    - Verify destruction of compute resources
    - Clean up old snapshots (keep last 7 days)
    - Display cost summary
    - _Requirements: US-1.3, US-1.4, US-3.1_
  
  - [ ] 17.2 Create provision script (scripts/provision.sh)
    - Find latest database snapshot
    - Run terraform init
    - Run terraform plan with snapshot identifier
    - Run terraform apply
    - Wait for ECS services to be stable
    - Run health checks
    - Display provision time and API URL
    - _Requirements: US-1.3, US-1.5, US-3.1_
  
  - [ ] 17.3 Create cost reporting script (scripts/cost-report.sh)
    - Query AWS Cost Explorer for environment costs
    - Display cost by service
    - Display total monthly cost
    - Display daily cost breakdown
    - _Requirements: US-3.4_
  
  - [ ]* 17.4 Test teardown and provision workflow
    - Run provision script and verify infrastructure created
    - Verify all services healthy and accessible
    - Run teardown script and verify infrastructure destroyed
    - Verify snapshot created successfully
    - Run provision script again and verify restore from snapshot
    - Verify provision time < 15 minutes
    - Verify teardown time < 10 minutes
    - _Requirements: US-1.5, US-1.6, US-3.1_

- [ ] 18. Provision dev environment and validate
  - [ ] 18.1 Run terraform apply for dev environment
    - Initialize Terraform backend
    - Run terraform plan and review changes
    - Run terraform apply to create all infrastructure
    - Verify all resources created successfully
    - _Requirements: US-1.7_
  
  - [ ] 18.2 Manually populate secrets
    - Add Spotify API credentials to Secrets Manager
    - Add Setlist.fm API key to Secrets Manager
    - Verify secrets accessible by ECS tasks
    - _Requirements: US-6.2_
  
  - [ ] 18.3 Validate infrastructure
    - Verify VPC and subnets created
    - Verify security groups configured correctly
    - Verify RDS cluster accessible from ECS
    - Verify Redis cluster accessible from ECS
    - Verify S3 buckets created with correct policies
    - Verify CloudWatch logs receiving data
    - _Requirements: US-1.7_

- [ ] 19. Checkpoint - Week 2 Review
  - Verify all Terraform modules complete and tested
  - Verify dev environment provisioned successfully
  - Verify teardown/provision scripts working
  - Verify cost tracking configured
  - Verify infrastructure meets security requirements
  - Ensure all tests pass, ask the user if questions arise.


### Week 3: Application Migration

- [ ] 20. Update application configuration for AWS
  - [ ] 20.1 Create AWS-specific configuration module
    - Create config/aws.py for AWS service configuration
    - Add functions to load secrets from Secrets Manager
    - Add functions to get RDS and Redis connection strings
    - Add environment variable validation
    - _Requirements: US-6.2_
  
  - [ ] 20.2 Update database connection configuration
    - Replace local PostgreSQL connection with RDS endpoint
    - Load database credentials from Secrets Manager
    - Configure connection pooling for Aurora Serverless
    - Add SSL/TLS configuration for RDS connection
    - _Requirements: US-6.6, US-6.8_
  
  - [ ] 20.3 Update Redis connection configuration
    - Replace local Redis connection with ElastiCache endpoint
    - Load Redis URL from Secrets Manager
    - Configure connection pooling
    - Add retry logic for connection failures
    - _Requirements: US-6.2_
  
  - [ ] 20.4 Update external API configuration
    - Load Spotify credentials from Secrets Manager
    - Load Setlist.fm API key from Secrets Manager
    - Load JWT secret from Secrets Manager
    - Remove all hardcoded credentials from code
    - _Requirements: US-6.2_

- [ ] 21. Implement CloudWatch metrics publishing
  - [ ] 21.1 Create MetricsClient for CloudWatch
    - Implement put_metric and put_metrics_batch methods
    - Configure namespace (FestivalApp)
    - Add dimension support for metrics
    - _Requirements: US-5.2_
  
  - [ ] 21.2 Add request tracking middleware
    - Track API request count by endpoint and method
    - Track API latency by endpoint
    - Track API errors by status code
    - Publish metrics to CloudWatch
    - _Requirements: US-5.2, US-5.8_
  
  - [ ] 21.3 Add database query metrics
    - Track database query count
    - Track database query latency
    - Publish metrics to CloudWatch
    - _Requirements: US-5.2_
  
  - [ ] 21.4 Add cache metrics
    - Track cache hits and misses
    - Track cache operation latency
    - Publish metrics to CloudWatch
    - _Requirements: US-5.2_
  
  - [ ] 21.5 Add business metrics
    - Track festival creation count
    - Track playlist creation count
    - Track user registration count
    - Track Spotify sync count
    - _Requirements: US-5.2_

- [ ] 22. Integrate AWS X-Ray tracing
  - [ ] 22.1 Install and configure X-Ray SDK
    - Install aws-xray-sdk package
    - Configure X-Ray middleware for FastAPI
    - Add X-Ray recorder configuration
    - _Requirements: US-5.5_
  
  - [ ] 22.2 Add X-Ray instrumentation
    - Instrument database queries with X-Ray
    - Instrument Redis operations with X-Ray
    - Instrument external API calls with X-Ray
    - Add custom subsegments for business logic
    - _Requirements: US-5.5_
  
  - [ ] 22.3 Configure X-Ray sampling rules
    - Create sampling rule for all requests (10% sample rate)
    - Create sampling rule for errors (100% sample rate)
    - Create sampling rule for slow requests (100% sample rate)
    - _Requirements: US-5.5_

- [ ] 23. Build and test Docker image
  - [ ] 23.1 Update Dockerfile for production
    - Use multi-stage build for smaller image size
    - Install production dependencies only
    - Configure non-root user for security
    - Add health check command
    - Optimize layer caching
    - _Requirements: US-6.3_
  
  - [ ] 23.2 Create docker-compose for local AWS testing
    - Create docker-compose.aws.yml
    - Use LocalStack for AWS service mocking
    - Configure environment variables for AWS services
    - Test application with mocked AWS services
    - _Requirements: US-8.1_
  
  - [ ] 23.3 Build and push Docker image to ECR
    - Authenticate Docker with ECR
    - Build Docker image with proper tags
    - Push image to ECR repository
    - Verify image in ECR console
    - _Requirements: US-2.6_


- [ ] 24. Deploy application to ECS and test
  - [ ] 24.1 Update ECS task definitions with new image
    - Update Terraform with new ECR image tag
    - Run terraform apply to update task definitions
    - Verify new task definitions created
    - _Requirements: US-2.7_
  
  - [ ] 24.2 Deploy API service to ECS
    - Update ECS service to use new task definition
    - Wait for service to reach stable state
    - Verify tasks running and healthy
    - Check CloudWatch logs for startup errors
    - _Requirements: US-2.7_
  
  - [ ] 24.3 Deploy worker service to ECS
    - Update ECS worker service to use new task definition
    - Wait for service to reach stable state
    - Verify Celery workers running
    - Check CloudWatch logs for worker activity
    - _Requirements: US-2.7_
  
  - [ ] 24.4 Test ALB health checks
    - Verify ALB target group shows healthy targets
    - Test /health endpoint through ALB
    - Verify ALB routing to ECS tasks
    - _Requirements: US-7.5_
  
  - [ ] 24.5 Test application functionality
    - Test user registration and login
    - Test festival search and creation
    - Test playlist creation
    - Test Spotify integration
    - Test Setlist.fm integration
    - Verify all features working in AWS environment
    - _Requirements: US-7.1_

- [ ] 25. Run database migrations in AWS
  - [ ] 25.1 Create database migration Lambda function
    - Create Lambda function to run Alembic migrations
    - Package Alembic and application code
    - Configure Lambda to access RDS via VPC
    - Add IAM role with RDS and Secrets Manager access
    - _Requirements: US-8.1_
  
  - [ ] 25.2 Run initial database migrations
    - Invoke Lambda function to run migrations
    - Verify all tables created in RDS
    - Verify indexes created
    - Check CloudWatch logs for migration output
    - _Requirements: US-8.1_
  
  - [ ] 25.3 Create migration workflow for future updates
    - Document migration process
    - Create script to invoke migration Lambda
    - Add migration step to deployment workflow
    - _Requirements: US-8.1_

- [ ] 26. Configure CloudFront and custom domain
  - [ ] 26.1 Update CloudFront distribution with custom domain
    - Add gig-prep.co.uk as alternate domain name
    - Associate ACM certificate with distribution
    - Update origin to use ALB DNS name
    - _Requirements: US-7.3, US-7.4_
  
  - [ ] 26.2 Update Route 53 DNS records
    - Create A record for gig-prep.co.uk pointing to CloudFront
    - Create A record for api.gig-prep.co.uk pointing to ALB
    - Wait for DNS propagation
    - _Requirements: US-7.3_
  
  - [ ] 26.3 Test custom domain access
    - Test https://gig-prep.co.uk (should serve via CloudFront)
    - Test https://api.gig-prep.co.uk/health (should serve via ALB)
    - Verify SSL certificates valid
    - Verify HTTP redirects to HTTPS
    - _Requirements: US-7.1, US-7.2, US-7.3_

- [ ] 27. Performance testing and optimization
  - [ ]* 27.1 Run load tests with Locust
    - Create Locust test scenarios (search, create playlist, etc.)
    - Run load test with 100 concurrent users
    - Measure API response times (p50, p95, p99)
    - Identify bottlenecks
    - _Requirements: US-7.4_
  
  - [ ] 27.2 Optimize database queries
    - Review slow query logs in CloudWatch
    - Add missing indexes
    - Optimize N+1 query problems
    - Verify query performance improvements
    - _Requirements: US-7.4_
  
  - [ ] 27.3 Optimize caching strategy
    - Review cache hit/miss ratios
    - Adjust cache TTLs based on usage patterns
    - Add caching for frequently accessed data
    - Verify cache performance improvements
    - _Requirements: US-7.4_
  
  - [ ] 27.4 Configure ECS auto-scaling
    - Verify auto-scaling policies working
    - Test scale-out under load
    - Test scale-in after load decreases
    - Adjust scaling thresholds if needed
    - _Requirements: US-7.5_

- [ ] 28. Checkpoint - Week 3 Review
  - Verify application deployed to ECS successfully
  - Verify all features working in AWS environment
  - Verify custom domain configured and accessible
  - Verify performance meets requirements (< 200ms p95)
  - Verify monitoring and logging working
  - Ensure all tests pass, ask the user if questions arise.


### Week 4: CI/CD & Production

- [ ] 29. Create GitHub Actions deployment workflows
  - [ ] 29.1 Create deploy-dev workflow
    - Create .github/workflows/deploy-dev.yml
    - Trigger on push to main branch
    - Run all tests before deployment
    - Build and push Docker image to ECR
    - Update ECS task definition with new image
    - Deploy to ECS and wait for stability
    - Run smoke tests after deployment
    - Send deployment notifications
    - _Requirements: US-2.1, US-2.3, US-2.7_
  
  - [ ] 29.2 Create deploy-prod workflow
    - Create .github/workflows/deploy-prod.yml
    - Trigger on manual workflow dispatch
    - Add manual approval gate
    - Run all tests before deployment
    - Build and push Docker image to ECR
    - Run terraform plan and require review
    - Deploy to ECS with blue-green strategy
    - Run smoke tests after deployment
    - Implement automatic rollback on failure
    - Send deployment notifications
    - _Requirements: US-2.4, US-2.5, US-2.7_
  
  - [ ] 29.3 Create scheduled teardown workflow
    - Create .github/workflows/scheduled-teardown.yml
    - Schedule for 6 PM EST on weekdays (cron: '0 23 * * 1-5')
    - Allow manual trigger
    - Run teardown script
    - Send completion notification
    - _Requirements: US-3.1, US-3.2_
  
  - [ ] 29.4 Create scheduled provision workflow
    - Create .github/workflows/scheduled-provision.yml
    - Schedule for 9 AM EST on weekdays (cron: '0 14 * * 1-5')
    - Allow manual trigger
    - Run provision script
    - Send completion notification with API URL
    - _Requirements: US-3.1, US-3.2_
  
  - [ ] 29.5 Configure GitHub Actions secrets
    - Add AWS_ACCESS_KEY_ID secret
    - Add AWS_SECRET_ACCESS_KEY secret
    - Add AWS_REGION secret
    - Add SLACK_WEBHOOK secret (optional)
    - Add INFRACOST_API_KEY secret (optional)
    - _Requirements: US-2.1_

- [ ] 30. Test CI/CD pipeline end-to-end
  - [ ]* 30.1 Test PR workflow
    - Create test PR with code changes
    - Verify linting, type checking, security scanning run
    - Verify all tests run successfully
    - Verify Docker build succeeds
    - Verify Terraform validation passes
    - Verify coverage report posted
    - _Requirements: US-2.2_
  
  - [ ]* 30.2 Test deploy-dev workflow
    - Merge PR to main branch
    - Verify deploy-dev workflow triggers
    - Verify Docker image built and pushed to ECR
    - Verify ECS service updated
    - Verify smoke tests pass
    - Verify deployment notification sent
    - _Requirements: US-2.3, US-2.7, US-2.8_
  
  - [ ]* 30.3 Test scheduled teardown/provision
    - Manually trigger teardown workflow
    - Verify infrastructure destroyed
    - Verify snapshot created
    - Manually trigger provision workflow
    - Verify infrastructure restored from snapshot
    - Verify application accessible
    - _Requirements: US-3.1, US-3.2_

- [ ] 31. Create production environment
  - [ ] 31.1 Create prod Terraform workspace
    - Create new Terraform workspace for prod
    - Copy terraform.tfvars to terraform.prod.tfvars
    - Update variables for production (multi-AZ, larger instances)
    - _Requirements: US-8.7_
  
  - [ ] 31.2 Provision production infrastructure
    - Run terraform plan for prod workspace
    - Review plan carefully
    - Run terraform apply for prod workspace
    - Verify all resources created
    - _Requirements: US-8.7_
  
  - [ ] 31.3 Configure production-specific settings
    - Enable multi-AZ for RDS (2 instances)
    - Disable auto-pause for RDS
    - Increase ECS task count (2 API tasks)
    - Enable ALB deletion protection
    - Increase CloudWatch log retention (30 days)
    - _Requirements: US-8.7_
  
  - [ ] 31.4 Run database migrations in production
    - Invoke migration Lambda for prod database
    - Verify all tables created
    - _Requirements: US-8.1_


- [ ] 32. Deploy to production
  - [ ] 32.1 Run production deployment workflow
    - Trigger deploy-prod workflow manually
    - Approve deployment in GitHub Actions
    - Monitor deployment progress
    - Verify ECS tasks healthy
    - _Requirements: US-2.4, US-2.7_
  
  - [ ] 32.2 Run production smoke tests
    - Test /health endpoint
    - Test user registration and login
    - Test festival search
    - Test playlist creation
    - Test Spotify integration
    - Verify all features working
    - _Requirements: US-7.1_
  
  - [ ] 32.3 Verify production monitoring
    - Check CloudWatch logs for errors
    - Verify metrics being published
    - Verify alarms configured correctly
    - Check X-Ray traces
    - Review CloudWatch dashboard
    - _Requirements: US-5.1, US-5.2, US-5.3, US-5.4, US-5.5_
  
  - [ ] 32.4 Test production custom domain
    - Test https://gig-prep.co.uk
    - Test https://api.gig-prep.co.uk
    - Verify SSL certificates valid
    - Verify CloudFront caching working
    - _Requirements: US-7.1, US-7.2, US-7.3_

- [ ] 33. Validate security and compliance
  - [ ] 33.1 Review security group configurations
    - Verify ECS tasks only accept traffic from ALB
    - Verify RDS only accepts traffic from ECS
    - Verify Redis only accepts traffic from ECS
    - Verify no public access to databases
    - _Requirements: US-6.1_
  
  - [ ] 33.2 Verify secrets management
    - Verify no hardcoded credentials in code
    - Verify all secrets in Secrets Manager
    - Verify secrets rotation configured (optional)
    - _Requirements: US-6.2_
  
  - [ ] 33.3 Verify encryption settings
    - Verify RDS encryption at rest enabled
    - Verify S3 encryption enabled
    - Verify TLS 1.2+ for all connections
    - Verify SSL certificates valid
    - _Requirements: US-6.6, US-6.8, US-7.2_
  
  - [ ] 33.4 Review IAM roles and policies
    - Verify least privilege principle applied
    - Verify no overly permissive policies
    - Review ECS task role permissions
    - Review ECS execution role permissions
    - _Requirements: US-6.3_
  
  - [ ] 33.5 Enable AWS security services
    - Verify CloudTrail enabled for audit logging
    - Verify VPC Flow Logs enabled
    - Verify AWS Config enabled (optional)
    - Verify GuardDuty enabled (optional)
    - _Requirements: US-6.10, US-6.11_

- [ ] 34. Validate cost optimization
  - [ ] 34.1 Review current costs
    - Run cost-report.sh script
    - Review costs by service
    - Verify costs within budget ($10-15/month for dev)
    - _Requirements: US-3.4_
  
  - [ ] 34.2 Verify cost allocation tags
    - Verify all resources have required tags
    - Verify tags visible in Cost Explorer
    - Create cost allocation report by tag
    - _Requirements: US-3.5_
  
  - [ ] 34.3 Verify budget alerts working
    - Check AWS Budgets configuration
    - Verify alerts at $10, $20, $30 thresholds
    - Verify SNS notifications configured
    - Test alert by approaching threshold (optional)
    - _Requirements: US-3.6_
  
  - [ ] 34.4 Verify Cost Anomaly Detection
    - Check Cost Anomaly Detection enabled
    - Verify anomaly alerts configured
    - Review anomaly detection settings
    - _Requirements: US-3.7_
  
  - [ ] 34.5 Test daily teardown cost savings
    - Run teardown script
    - Wait 24 hours
    - Check costs for torn-down environment
    - Verify costs reduced to $2-5/month
    - Run provision script to restore
    - _Requirements: US-3.1, US-3.2, US-3.3_


- [ ] 35. Create documentation and runbooks
  - [ ] 35.1 Create architecture documentation
    - Document high-level architecture with diagrams
    - Document network architecture and security groups
    - Document data flow and integrations
    - Document cost optimization strategies
    - _Requirements: US-8.2_
  
  - [ ] 35.2 Create operational runbooks
    - Create runbook for daily teardown/provision
    - Create runbook for deployment process
    - Create runbook for database migrations
    - Create runbook for rollback procedures
    - Create runbook for troubleshooting common issues
    - _Requirements: US-8.6_
  
  - [ ] 35.3 Create developer documentation
    - Document local development setup
    - Document testing procedures
    - Document CI/CD workflows
    - Document code structure and patterns
    - _Requirements: US-8.2_
  
  - [ ] 35.4 Create monitoring and alerting guide
    - Document CloudWatch dashboards
    - Document alarm thresholds and actions
    - Document log query examples
    - Document X-Ray trace analysis
    - _Requirements: US-8.6_
  
  - [ ] 35.5 Update README.md
    - Add project overview and architecture
    - Add setup instructions for AWS deployment
    - Add links to detailed documentation
    - Add cost information and optimization tips
    - Add troubleshooting section
    - _Requirements: US-8.2_

- [ ] 36. Final validation and go-live
  - [ ] 36.1 Run comprehensive end-to-end tests
    - Test complete user journey (registration → playlist creation)
    - Test all API endpoints
    - Test error handling and edge cases
    - Test performance under load
    - _Requirements: US-7.1_
  
  - [ ] 36.2 Verify monitoring and alerting
    - Trigger test alarms to verify notifications
    - Review CloudWatch dashboard completeness
    - Verify log aggregation working
    - Verify X-Ray traces captured
    - _Requirements: US-5.1, US-5.2, US-5.3, US-5.4, US-5.5_
  
  - [ ] 36.3 Verify backup and recovery procedures
    - Test database snapshot creation
    - Test restore from snapshot
    - Verify RTO and RPO meet requirements
    - Document backup schedule
    - _Requirements: US-1.3, US-1.4, US-1.5_
  
  - [ ] 36.4 Perform security audit
    - Run security scanning tools
    - Review security group rules
    - Review IAM policies
    - Review encryption settings
    - Address any security findings
    - _Requirements: US-6.1, US-6.2, US-6.3_
  
  - [ ] 36.5 Final cost validation
    - Review actual costs vs. budget
    - Verify cost optimization measures working
    - Document actual monthly costs
    - Create cost projection for next 3 months
    - _Requirements: US-3.4_
  
  - [ ] 36.6 Go-live checklist
    - Verify production environment stable
    - Verify custom domain accessible
    - Verify all features working
    - Verify monitoring and alerting active
    - Verify backup procedures in place
    - Verify documentation complete
    - Announce go-live to stakeholders
    - _Requirements: US-7.1, US-8.1_

- [ ] 37. Post-migration tasks
  - [ ] 37.1 Monitor production for first week
    - Check CloudWatch logs daily for errors
    - Review performance metrics
    - Review cost metrics
    - Address any issues promptly
    - _Requirements: US-5.1, US-5.2, US-3.4_
  
  - [ ] 37.2 Optimize based on production data
    - Adjust cache TTLs based on usage patterns
    - Adjust auto-scaling thresholds based on load
    - Optimize database queries based on slow query logs
    - Adjust alarm thresholds based on baseline
    - _Requirements: US-7.4, US-5.3_
  
  - [ ] 37.3 Schedule regular maintenance tasks
    - Schedule weekly cost reviews
    - Schedule monthly security reviews
    - Schedule quarterly disaster recovery tests
    - Schedule dependency updates
    - _Requirements: US-8.6_
  
  - [ ] 37.4 Decommission local Docker environment
    - Backup local data if needed
    - Document local setup for reference
    - Remove local Docker Compose files (optional)
    - Update documentation to reflect AWS-only deployment
    - _Requirements: US-8.1_

- [ ] 38. Final Checkpoint - Migration Complete
  - Verify all infrastructure provisioned and working
  - Verify application deployed to production
  - Verify CI/CD pipeline operational
  - Verify monitoring and alerting configured
  - Verify cost optimization measures in place
  - Verify documentation complete
  - Verify all requirements met
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at the end of each week
- Focus on cost optimization throughout (target: $10-15/month with daily teardown)
- Prioritize security with zero-trust security groups
- Maintain clean architecture (Repository → Service → Controller)
- All infrastructure changes via Terraform only (no manual AWS console changes)

## Success Criteria

- ✅ Application running on AWS ECS Fargate
- ✅ Infrastructure 100% managed by Terraform
- ✅ CI/CD pipeline automated with GitHub Actions
- ✅ Daily teardown/provision capability working (< 15 min provision, < 10 min teardown)
- ✅ Cost target achieved ($10-15/month with daily teardown)
- ✅ Custom domain (gig-prep.co.uk) configured and accessible
- ✅ Monitoring and alerting operational
- ✅ Security best practices implemented
- ✅ 80%+ test coverage maintained
- ✅ Documentation complete

## Estimated Effort

- **Week 1**: 20-25 hours (clean architecture refactoring, testing)
- **Week 2**: 20-25 hours (Terraform modules, infrastructure provisioning)
- **Week 3**: 15-20 hours (application migration, integration testing)
- **Week 4**: 15-20 hours (CI/CD, production deployment, documentation)
- **Total**: 70-90 hours over 4 weeks (solo developer, part-time)
