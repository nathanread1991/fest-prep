# Requirements Document

## Introduction

The Festival Playlist Generator project currently has tightly coupled CI/CD pipelines where application code checks, infrastructure provisioning, Docker image builds, and ECS deployments are mixed together in monolithic GitHub Actions workflows. This feature reworks the CI/CD architecture to decouple pipelines by concern, add Terraform static analysis and validation, support multi-environment deployments (dev and prod), ensure persistent resources survive daily teardowns, improve the local development experience, and provide comprehensive documentation.

## Glossary

- **CI_Pipeline**: A GitHub Actions workflow that runs automated checks (linting, testing, type checking, security scanning) on code changes without deploying
- **App_CI_Pipeline**: A CI pipeline scoped to application code changes under `services/api/`
- **Infra_CI_Pipeline**: A CI pipeline scoped to infrastructure code changes under `infrastructure/terraform/`
- **Docker_Build_Pipeline**: A GitHub Actions workflow that builds, scans, and pushes Docker images to ECR
- **ECS_Deploy_Pipeline**: A GitHub Actions workflow that deploys a specific Docker image tag to an ECS environment
- **Terraform_Plan**: A Terraform command that previews infrastructure changes without applying them
- **Terraform_Apply**: A Terraform command that applies infrastructure changes to the target environment
- **Persistent_Resource**: An AWS resource (ECR repository, S3 bucket, Secrets Manager secret, Route 53 hosted zone) that must survive daily teardown cycles
- **Ephemeral_Resource**: An AWS resource (ECS cluster, Aurora database, ElastiCache, ALB, CloudFront, VPC) that is created during provisioning and destroyed during teardown
- **Teardown**: The scheduled or manual destruction of ephemeral infrastructure resources to reduce costs
- **Provisioning**: The scheduled or manual creation of ephemeral infrastructure resources
- **Local_Dev_Environment**: A Docker Compose-based local development setup that mirrors the AWS production architecture
- **Quality_Gate**: A set of required checks that must all pass before code can be merged or deployed
- **Smoke_Test**: A lightweight post-deployment test that verifies core application health and routing

## Requirements

### Requirement 1: Decoupled Application CI Pipeline

**User Story:** As a developer, I want application code checks to run independently from infrastructure checks, so that I get faster feedback on my Python code changes without waiting for Terraform validation.

#### Acceptance Criteria

1. WHEN a pull request modifies files under `services/api/`, THE App_CI_Pipeline SHALL run Python linting (black, isort, flake8), type checking (mypy), security scanning (bandit, pip-audit), unit tests, and integration tests
2. WHEN a pull request modifies only files under `infrastructure/terraform/`, THE App_CI_Pipeline SHALL NOT be triggered
3. THE App_CI_Pipeline SHALL report a Quality_Gate status that aggregates the results of all application checks
4. IF any application check fails, THEN THE App_CI_Pipeline SHALL block the pull request from merging
5. WHEN a push to the `main` branch modifies files under `services/api/`, THE App_CI_Pipeline SHALL run the same checks as for pull requests

### Requirement 2: Decoupled Infrastructure CI Pipeline

**User Story:** As a developer, I want infrastructure code to be validated with static analysis and Terraform plan on every PR, so that I catch misconfigurations before they reach the main branch.

#### Acceptance Criteria

1. WHEN a pull request modifies files under `infrastructure/terraform/`, THE Infra_CI_Pipeline SHALL run `terraform fmt -check`, `terraform validate`, tflint, and tfsec or checkov static analysis
2. WHEN a pull request modifies files under `infrastructure/terraform/`, THE Infra_CI_Pipeline SHALL execute `terraform plan` and post the plan output as a PR comment
3. WHEN a pull request modifies only files under `services/api/`, THE Infra_CI_Pipeline SHALL NOT be triggered
4. IF any infrastructure check fails, THEN THE Infra_CI_Pipeline SHALL block the pull request from merging
5. THE Infra_CI_Pipeline SHALL use the same Terraform version (>= 1.10) as the deployment pipelines

### Requirement 3: Decoupled Docker Image Build Pipeline

**User Story:** As a developer, I want Docker image builds to be a separate pipeline, so that images can be built, scanned, and pushed to ECR independently of infrastructure lifecycle and application deployment.

#### Acceptance Criteria

1. WHEN a push to the `main` branch modifies files under `services/api/`, THE Docker_Build_Pipeline SHALL build the Docker image using the multi-stage Dockerfile
2. THE Docker_Build_Pipeline SHALL tag the image with both the git SHA and `latest`
3. THE Docker_Build_Pipeline SHALL push the image to the ECR repository
4. THE Docker_Build_Pipeline SHALL scan the built image for vulnerabilities using Trivy
5. THE Docker_Build_Pipeline SHALL validate the Dockerfile using hadolint before building
6. WHEN triggered manually via workflow_dispatch, THE Docker_Build_Pipeline SHALL accept an optional custom image tag parameter
7. THE Docker_Build_Pipeline SHALL use Docker Buildx with GitHub Actions cache for layer caching

### Requirement 4: Decoupled ECS Deployment Pipeline

**User Story:** As a developer, I want ECS deployments to be a separate pipeline that takes an image tag as input, so that I can deploy any previously built image to any environment.

#### Acceptance Criteria

1. WHEN triggered, THE ECS_Deploy_Pipeline SHALL accept an environment parameter (dev or prod) and an image tag parameter
2. THE ECS_Deploy_Pipeline SHALL update the ECS task definitions for both the API and worker services with the specified image tag
3. THE ECS_Deploy_Pipeline SHALL wait for ECS service stability after deployment
4. THE ECS_Deploy_Pipeline SHALL verify ALB target group health after deployment
5. THE ECS_Deploy_Pipeline SHALL run Smoke_Tests against the deployed environment
6. IF the Smoke_Test fails for a prod deployment, THEN THE ECS_Deploy_Pipeline SHALL initiate an automatic rollback to the previous task definition
7. WHEN deploying to prod, THE ECS_Deploy_Pipeline SHALL require manual approval via a GitHub environment protection rule
8. THE ECS_Deploy_Pipeline SHALL run database migrations via ECS run-task after updating services

### Requirement 5: Automated Dev Deployment on Main Push

**User Story:** As a developer, I want changes pushed to main to automatically build and deploy to the dev environment, so that the dev environment always reflects the latest code.

#### Acceptance Criteria

1. WHEN a push to the `main` branch modifies files under `services/api/`, THE Docker_Build_Pipeline SHALL trigger, and upon success, THE ECS_Deploy_Pipeline SHALL trigger for the dev environment with the newly built image tag
2. WHEN a push to the `main` branch modifies files under `infrastructure/terraform/`, THE Infra_CI_Pipeline SHALL run validation, and upon success, Terraform_Apply SHALL execute against the dev environment
3. THE ECS_Deploy_Pipeline for dev SHALL NOT require manual approval

### Requirement 6: Persistent Resources Through Teardown

**User Story:** As a developer, I want ECR, S3, Secrets Manager, and Route 53 resources to survive daily teardowns, so that Docker images, application data, secrets, and DNS configuration persist across infrastructure cycles.

#### Acceptance Criteria

1. THE Terraform configuration SHALL separate Persistent_Resources (ECR, S3 buckets, Secrets Manager secrets, Route 53 hosted zone) from Ephemeral_Resources (ECS, Aurora, ElastiCache, ALB, CloudFront, VPC, monitoring)
2. WHEN the Teardown workflow executes, THE Teardown workflow SHALL destroy only Ephemeral_Resources
3. WHEN the Provisioning workflow executes, THE Provisioning workflow SHALL create Ephemeral_Resources and reference existing Persistent_Resources
4. THE Docker_Build_Pipeline SHALL be able to push images to ECR regardless of whether Ephemeral_Resources exist
5. IF a Persistent_Resource is accidentally targeted for destruction, THEN Terraform SHALL prevent the destruction via lifecycle rules

### Requirement 7: Infrastructure Teardown and Provisioning Workflows

**User Story:** As a developer, I want the scheduled teardown and provisioning workflows to work correctly with the decoupled persistent/ephemeral resource split, so that daily cost savings continue without data loss.

#### Acceptance Criteria

1. THE Teardown workflow SHALL create a database snapshot before destroying Ephemeral_Resources
2. THE Provisioning workflow SHALL restore the database from the latest snapshot when available
3. THE Teardown workflow SHALL verify that Persistent_Resources remain intact after destruction of Ephemeral_Resources
4. THE Provisioning workflow SHALL run a health check after all Ephemeral_Resources are created
5. WHEN triggered on a schedule, THE Teardown workflow SHALL execute at 6 PM GMT on weekdays
6. WHEN triggered on a schedule, THE Provisioning workflow SHALL execute at 9 AM GMT on weekdays

### Requirement 8: Multi-Environment Support

**User Story:** As a developer, I want the pipeline architecture to support deploying to both dev and prod environments, so that the same infrastructure code and Docker images can be promoted across environments.

#### Acceptance Criteria

1. THE Terraform configuration SHALL accept an `environment` variable that controls resource naming, sizing, and configuration for dev and prod
2. THE prod environment SHALL use the same shared Persistent_Resources (ECR repository pattern, S3 bucket pattern) but with environment-specific naming
3. THE prod environment SHALL use a separate ECS service, task definition, and subdomain from the dev environment
4. THE ECS_Deploy_Pipeline SHALL use the environment parameter to determine the target ECS cluster, service names, and domain for Smoke_Tests
5. WHILE deploying to prod, THE ECS_Deploy_Pipeline SHALL enforce stricter checks including manual approval and automatic rollback on failure

### Requirement 9: Local Development Environment

**User Story:** As a developer, I want a Docker Compose-based local development setup that mirrors the AWS architecture, so that I can develop and test locally before pushing changes.

#### Acceptance Criteria

1. THE Local_Dev_Environment SHALL provide PostgreSQL, Redis, and the FastAPI application via Docker Compose
2. THE Local_Dev_Environment SHALL include a Celery worker and Celery beat scheduler
3. THE Local_Dev_Environment SHALL include an nginx reverse proxy for image caching, matching the production CDN behavior
4. THE Local_Dev_Environment SHALL support hot-reloading of application code via volume mounts
5. THE Local_Dev_Environment SHALL provide a LocalStack-based AWS services overlay (S3, Secrets Manager, CloudWatch) via a separate compose file
6. THE Local_Dev_Environment SHALL include a convenience script or Makefile for common operations (start, stop, test, lint, format, migrate)

### Requirement 10: CI/CD Documentation

**User Story:** As a developer, I want comprehensive documentation covering the CI/CD pipeline architecture, local development setup, and deployment procedures, so that any team member can understand and operate the system.

#### Acceptance Criteria

1. THE documentation SHALL include a pipeline architecture diagram or description showing all workflows and their triggers
2. THE documentation SHALL describe the local development setup with step-by-step instructions for first-time setup
3. THE documentation SHALL describe the deployment procedure for each environment (dev automatic, prod manual)
4. THE documentation SHALL describe the teardown and provisioning cycle including snapshot management
5. THE documentation SHALL describe the persistent vs ephemeral resource split and the rationale
6. THE documentation SHALL describe the testing procedures including how to run unit tests, integration tests, and smoke tests locally and in CI

### Requirement 11: Pipeline Security and Secrets Management

**User Story:** As a developer, I want CI/CD pipelines to follow security best practices for credential handling, so that secrets are never exposed in logs or artifacts.

#### Acceptance Criteria

1. THE CI/CD pipelines SHALL use GitHub Actions secrets for all AWS credentials and API keys
2. THE CI/CD pipelines SHALL use OIDC-based authentication with AWS where supported, instead of long-lived access keys
3. THE CI/CD pipelines SHALL mask sensitive values in workflow logs
4. THE App_CI_Pipeline SHALL run gitleaks to detect accidentally committed secrets
5. IF gitleaks detects a secret in a pull request, THEN THE App_CI_Pipeline SHALL block the pull request from merging

### Requirement 12: Pipeline Concurrency and Ordering

**User Story:** As a developer, I want pipelines to handle concurrent runs safely, so that simultaneous pushes or deployments do not cause conflicts or race conditions.

#### Acceptance Criteria

1. THE ECS_Deploy_Pipeline SHALL use concurrency groups to prevent simultaneous deployments to the same environment
2. THE Infra_CI_Pipeline SHALL use concurrency groups to prevent simultaneous Terraform operations against the same environment
3. WHEN a newer pipeline run is queued for the same CI pipeline and branch, THE CI_Pipeline SHALL cancel the older in-progress run
4. THE ECS_Deploy_Pipeline SHALL NOT cancel in-progress deployment runs when a newer run is queued
