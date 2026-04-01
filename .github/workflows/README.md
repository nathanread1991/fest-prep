# GitHub Actions CI/CD Workflows

This directory contains six focused GitHub Actions workflows for the Festival Playlist Generator project. Each workflow handles a single concern — app CI, infra CI, Docker builds, ECS deployments, nightly teardown, and morning provisioning.

## Workflow Overview

| Workflow | File | Trigger | Purpose |
|---|---|---|---|
| App CI | `ci-app.yml` | PR / push to `main` on `services/api/**` | Lint, type-check, security scan, unit + integration tests, gitleaks |
| Infra CI | `ci-infra.yml` | PR / push to `main` on `infrastructure/terraform/**` | fmt, validate, tflint, checkov, plan (PR comment), apply (main push) |
| Build & Push | `build.yml` | Push to `main` on `services/api/**`, `workflow_dispatch` | hadolint, Docker build, Trivy scan, ECR push |
| Deploy | `deploy.yml` | Called by `build.yml` (dev) or `workflow_dispatch` (prod) | ECS task def update, migration, smoke-test, rollback |
| Teardown | `teardown.yml` | Schedule 18:00 GMT Mon–Fri, `workflow_dispatch` | DB snapshot, destroy ephemeral infra, verify persistent resources |
| Provision | `provision.yml` | Schedule 09:00 GMT Mon–Fri, `workflow_dispatch` | Find snapshot, terraform apply ephemeral, health-check |

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
  └── deploy.yml (env=prod)  →  GitHub Environment approval → deploy → smoke-test → rollback on failure

Schedule
  ├── teardown.yml  (18:00 GMT Mon–Fri)  →  snapshot → destroy ephemeral → verify persistent
  └── provision.yml (09:00 GMT Mon–Fri)  →  find snapshot → apply ephemeral → health-check
```

## Workflow Details

### ci-app.yml — App CI

Runs six parallel jobs gated by a `quality-gate` summary job:

- **gitleaks** — secret scanning via `gitleaks/gitleaks-action`
- **lint** — black, isort, flake8
- **type-check** — mypy strict mode
- **security** — bandit, pip-audit
- **unit-tests** — pytest (non-integration) with coverage
- **integration-tests** — pytest with PostgreSQL 15 + Redis 7 service containers

Concurrency: `cancel-in-progress: true` per branch.

### ci-infra.yml — Infra CI

- **static-analysis** — terraform fmt, validate, tflint, checkov
- **plan** (PR only) — terraform plan with output posted as PR comment
- **apply** (push to main only) — terraform apply against dev

Concurrency: `infra-dev` with `cancel-in-progress: false` (Terraform state safety).

### build.yml — Build & Push

- **build-push** — hadolint, Docker Buildx with GHA cache, Trivy SARIF scan, ECR push (tags: `{sha}` + `latest`)
- **trigger-deploy** — calls `deploy.yml` with `environment: dev` and the built image tag

Supports `workflow_dispatch` with an optional custom `image_tag` input.

### deploy.yml — Deploy to ECS

Reusable workflow (`workflow_call`) and manual trigger (`workflow_dispatch`).

- **deploy** — updates ECS task definitions (API + worker) via targeted Terraform apply, waits for service stability, verifies ALB target group health. Uses GitHub Environment protection rules (`production` for prod).
- **migrate** — runs `alembic upgrade head` via ECS run-task
- **smoke-test** — `GET /health`, `/docs`, `/api/v1/festivals`, `/nonexistent-route`
- **rollback** — reverts to previous task definition (prod only, on failure)

Concurrency: `deploy-{environment}` with `cancel-in-progress: false`.

### teardown.yml — Teardown Ephemeral Infrastructure

- **snapshot** — creates RDS cluster snapshot, waits for availability
- **destroy** — `terraform destroy` on the ephemeral root module
- **verify** — asserts ECR, S3, Secrets Manager, Route 53 still exist
- **cleanup** — deletes snapshots older than 7 days

### provision.yml — Provision Ephemeral Infrastructure

- **find-snapshot** — queries RDS for latest available snapshot
- **apply** — `terraform apply` with `restore_from_snapshot` and `snapshot_identifier` variables
- **wait-services** — `aws ecs wait services-stable`
- **health-check** — polls `/health` endpoint

## Authentication

All workflows use OIDC-based AWS authentication via `aws-actions/configure-aws-credentials@v4` with `role-to-assume`. No long-lived AWS access keys are stored as secrets.

Required permissions on every workflow:
```yaml
permissions:
  id-token: write
  contents: read
```

## Legacy Workflows (to be removed)

The following files are from the old monolithic pipeline and will be deleted once the new workflows are validated:

- `pr.yml`
- `deploy-app.yml`
- `deploy-infra.yml`
- `deploy-prod.yml`
- `scheduled-teardown.yml`
- `scheduled-provision.yml`

## Further Reading

- [docs/cicd.md](../../docs/cicd.md) — full CI/CD documentation including local dev setup, deployment procedures, and resource architecture
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
