# CI/CD Pipeline Documentation

## Overview

The Festival Playlist Generator uses six GitHub Actions workflows, each handling a single concern. Application CI, infrastructure CI, Docker builds, ECS deployments, nightly teardown, and morning provisioning are fully decoupled. Path-filtered triggers ensure only relevant pipelines run for a given change.

All workflows authenticate to AWS via OIDC (no long-lived access keys). Prod deployments require manual approval through GitHub Environment protection rules.

## Pipeline Architecture

```
Push to main (services/api/**)
  ├── ci-app.yml  →  quality gate (lint, types, security, tests)
  └── build.yml   →  Docker build + ECR push
                        └── deploy.yml (env=dev, automatic)

Push to main (infrastructure/terraform/**)
  └── ci-infra.yml  →  static analysis → terraform apply (dev)

Pull Request
  ├── ci-app.yml   (if services/api/** changed)
  └── ci-infra.yml (if infrastructure/terraform/** changed)
                        └── terraform plan → PR comment

Manual (workflow_dispatch)
  └── deploy.yml (env=prod)  →  approval → deploy → smoke-test → rollback on failure

Schedule
  ├── teardown.yml  (18:00 GMT Mon–Fri)
  └── provision.yml (09:00 GMT Mon–Fri)
```

### Workflow Summary

| Workflow | File | Trigger | Purpose |
|---|---|---|---|
| App CI | `ci-app.yml` | PR / push to `main` on `services/api/**` | Lint, type-check, security, tests, gitleaks |
| Infra CI | `ci-infra.yml` | PR / push to `main` on `infrastructure/terraform/**` | fmt, validate, tflint, checkov, plan/apply |
| Build | `build.yml` | Push to `main` on `services/api/**`, manual | hadolint, Docker build, Trivy, ECR push |
| Deploy | `deploy.yml` | Called by build (dev) or manual (prod) | ECS deploy, migrate, smoke-test, rollback |
| Teardown | `teardown.yml` | Cron 18:00 GMT Mon–Fri, manual | Snapshot, destroy ephemeral, verify persistent |
| Provision | `provision.yml` | Cron 09:00 GMT Mon–Fri, manual | Restore snapshot, apply ephemeral, health-check |

### Concurrency

| Workflow | Concurrency Group | Cancel In-Progress |
|---|---|---|
| ci-app.yml | `App CI-{ref}` | Yes |
| ci-infra.yml | `infra-dev` | No (Terraform state safety) |
| build.yml | `Build & Push-{ref}` | Yes |
| deploy.yml | `deploy-{environment}` | No (deployment safety) |
| teardown.yml | `infra-dev` | No |
| provision.yml | `infra-dev` | No |

---

## Local Development Setup

### Prerequisites

- Docker and Docker Compose
- GNU Make
- Git

### First-Time Setup

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd festival-playlist-generator
   ```

2. Copy the environment file:

   ```bash
   cp .env.example .env
   # Edit .env with your Spotify API credentials and other secrets
   ```

3. Start all services (PostgreSQL, Redis, FastAPI, Celery worker, Celery beat, nginx):

   ```bash
   make up
   ```

4. Run database migrations:

   ```bash
   make migrate
   ```

5. Verify the app is running:

   ```bash
   curl http://localhost:8000/health
   ```

### Makefile Targets

| Target | Command | Description |
|---|---|---|
| `make up` | `docker compose up -d` | Start all services |
| `make down` | `docker compose down` | Stop all services |
| `make test` | `pytest` inside container | Run test suite |
| `make lint` | black, isort, flake8 | Check code style |
| `make typecheck` | mypy | Run type checking |
| `make format` | black + isort | Auto-fix formatting |
| `make migrate` | `alembic upgrade head` | Run database migrations |
| `make localstack` | docker compose with AWS overlay | Start LocalStack (S3, Secrets Manager, CloudWatch) |
| `make logs` | `docker compose logs -f app` | Follow app logs |

### LocalStack (Optional)

To develop against AWS services locally:

```bash
make localstack
```

This starts a LocalStack container providing S3, Secrets Manager, and CloudWatch, matching the production AWS architecture.

---

## Deployment Procedures

### Dev Environment (Automatic)

Dev deployments happen automatically when code is pushed to `main`:

1. Push changes to `services/api/**` on `main`
2. `ci-app.yml` runs all quality checks in parallel
3. `build.yml` builds the Docker image, scans it with Trivy, and pushes to ECR
4. `build.yml` automatically triggers `deploy.yml` with `environment: dev` and the new image tag
5. `deploy.yml` updates ECS task definitions, waits for stability, runs migrations, and executes smoke tests

For infrastructure changes:

1. Push changes to `infrastructure/terraform/**` on `main`
2. `ci-infra.yml` runs static analysis then `terraform apply` against dev

No manual approval is required for dev deployments.

### Prod Environment (Manual)

Prod deployments require explicit manual action and approval:

1. Go to Actions → "Deploy to ECS" → "Run workflow"
2. Select `environment: prod` and enter the `image_tag` to deploy (use a git SHA from a previous build)
3. The workflow pauses at the `deploy` job, waiting for a reviewer to approve via the `production` GitHub Environment
4. After approval: ECS task definitions are updated, migrations run, and smoke tests execute
5. If smoke tests fail, the `rollback` job automatically reverts both API and worker services to their previous task definitions

### Rollback

Automatic rollback only triggers for prod when smoke tests fail. For manual rollback:

1. Find the previous image tag (git SHA) from the ECR repository or a previous workflow run
2. Trigger `deploy.yml` manually with that image tag

---

## Teardown and Provisioning Cycle

To reduce costs, the dev environment is torn down each evening and re-provisioned each morning.

### Teardown (18:00 GMT Mon–Fri)

1. **Snapshot** — creates an RDS cluster snapshot before any destruction
2. **Destroy** — runs `terraform destroy` on the ephemeral root module (VPC, ECS, Aurora, ElastiCache, ALB, CloudFront, WAF, monitoring)
3. **Verify** — confirms persistent resources (ECR, S3, Secrets Manager, Route 53) still exist
4. **Cleanup** — deletes snapshots older than 7 days

### Provisioning (09:00 GMT Mon–Fri)

1. **Find snapshot** — queries RDS for the latest available snapshot
2. **Apply** — runs `terraform apply` on the ephemeral module, restoring the database from the snapshot if one exists (otherwise creates a fresh cluster)
3. **Wait** — waits for ECS services to stabilize
4. **Health check** — polls the `/health` endpoint to confirm the application is running

### Manual Trigger

Both workflows support `workflow_dispatch` for on-demand teardown or provisioning outside the schedule.

---

## Persistent vs Ephemeral Resources

### Why the Split

The original Terraform setup managed all resources in a single root module. Nightly teardowns destroyed everything — including ECR images, S3 data, and secrets — causing data loss and requiring full rebuilds each morning.

The new architecture separates resources into two Terraform root modules:

```
infrastructure/terraform/
├── persistent/          # Survives teardown — separate state file
│   ├── main.tf          # ECR, S3, Secrets Manager, OIDC IAM
│   ├── variables.tf
│   ├── outputs.tf
│   └── backend.tf       # State key: persistent/{env}/terraform.tfstate
└── (existing root)      # Ephemeral — destroyed nightly, recreated daily
    ├── main.tf           # VPC, ECS, Aurora, ElastiCache, ALB, CloudFront, WAF
    └── ...               # References persistent outputs via remote_state
```

### Persistent Resources

These resources have `prevent_destroy = true` lifecycle rules and are never targeted by teardown:

| Resource | Purpose |
|---|---|
| ECR repository | Docker images persist across teardown cycles |
| S3 app-data bucket | Application data (festival images, exports) |
| S3 cloudfront-logs bucket | CDN access logs |
| Secrets Manager secrets | Spotify credentials, SetlistFM API key, JWT secret |
| OIDC IAM provider + role | GitHub Actions AWS authentication |

### Ephemeral Resources

Created during provisioning, destroyed during teardown:

- VPC, subnets, security groups
- Aurora PostgreSQL cluster (snapshotted before teardown)
- ElastiCache Redis
- ECS cluster, services, task definitions
- ALB, CloudFront distribution
- WAF, CloudWatch monitoring

---

## Testing

### Unit Tests

Run locally:

```bash
make test
```

Or target only unit tests:

```bash
docker exec festival_app python -m pytest tests/ -m "not integration" -v
```

In CI (`ci-app.yml`): runs as the `unit-tests` job with coverage reporting.

### Integration Tests

Require PostgreSQL and Redis. In CI, these run as service containers. Locally:

```bash
make up
docker exec festival_app python -m pytest tests/ -m integration -v
```

In CI (`ci-app.yml`): runs as the `integration-tests` job. Exit code 5 (no tests collected) is treated as success during the transition period.

### Smoke Tests (Post-Deployment)

Run automatically by `deploy.yml` after every deployment. The smoke test job hits four endpoints:

| Endpoint | Expected |
|---|---|
| `GET /health` | `{"status": "healthy"}` |
| `GET /docs` | Non-5xx response |
| `GET /api/v1/festivals` | Non-5xx response |
| `GET /nonexistent-route` | 404 (not 5xx) |

Dev URL: `https://api.gig-prep.co.uk`
Prod URL: `https://api-prod.gig-prep.co.uk`

### Security Scanning

- **gitleaks** — detects committed secrets in PRs
- **bandit** — Python security linting
- **pip-audit** — dependency vulnerability scanning
- **Trivy** — Docker image vulnerability scanning (SARIF uploaded to GitHub Security)
- **checkov** — Terraform security misconfiguration scanning

### Linting and Type Checking

```bash
make lint       # black --check, isort --check, flake8
make typecheck  # mypy strict mode
make format     # auto-fix with black + isort
```

---

## Security

- All workflows use OIDC-based AWS authentication — no long-lived access keys
- Sensitive values are masked in workflow logs
- gitleaks blocks PRs containing accidentally committed secrets
- Trivy scans Docker images for vulnerabilities before ECR push
- checkov scans Terraform for security misconfigurations
- GitHub Environment protection rules enforce manual approval for prod deployments
