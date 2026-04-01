# Implementation Plan: CI/CD Pipeline Rework

## Overview

Rework the monolithic CI/CD pipelines into six focused GitHub Actions workflows, split Terraform into persistent/ephemeral modules, add OIDC-based AWS auth, create a Makefile for local dev, and add property-based tests for workflow correctness. Old monolithic workflow files are removed at the end.

## Tasks

- [x] 1. Create the persistent Terraform module
  - [x] 1.1 Create `infrastructure/terraform/persistent/` directory with `main.tf`, `variables.tf`, `outputs.tf`, and `backend.tf`
    - Move ECR repository, S3 buckets (app_data, cloudfront_logs), and Secrets Manager secret resources into `persistent/main.tf`
    - Add `prevent_destroy = true` lifecycle rules to all persistent resources
    - Configure `backend.tf` with S3 backend using key `persistent/${var.environment}/terraform.tfstate`
    - Define `environment` variable in `variables.tf`
    - Export resource ARNs and IDs in `outputs.tf` for consumption by the ephemeral root
    - _Requirements: 6.1, 6.5, 8.1_

  - [x] 1.2 Add OIDC IAM resources to the persistent module
    - Create `aws_iam_openid_connect_provider.github` for GitHub Actions OIDC
    - Create `aws_iam_role.github_actions` with OIDC trust policy scoped to the repository
    - Attach IAM policies granting ECR push, ECS deploy, Terraform state access, and Secrets Manager read
    - _Requirements: 11.2_

  - [ ]* 1.3 Write property test: all persistent resources have `prevent_destroy = true`
    - **Property 4: Persistent resources survive teardown**
    - **Property 5: Teardown only destroys ephemeral resources**
    - Parse `infrastructure/terraform/persistent/main.tf` with HCL parser or regex
    - Assert every `resource` block contains `lifecycle { prevent_destroy = true }`
    - **Validates: Requirements 6.2, 6.5, 7.3**

- [x] 2. Refactor the ephemeral Terraform root to reference persistent outputs
  - [x] 2.1 Add `terraform_remote_state` data source to the existing root module
    - Add `data "terraform_remote_state" "persistent"` block pointing to the persistent state key
    - Replace hardcoded ECR, S3, and Secrets Manager references with `data.terraform_remote_state.persistent.outputs.*`
    - Add `restore_from_snapshot` variable (bool, default false) and `snapshot_identifier` variable (string, default empty) for provisioning use
    - _Requirements: 6.1, 6.3, 7.2_

  - [x] 2.2 Add environment variable support to the ephemeral root
    - Ensure `var.environment` controls resource naming, sizing, and configuration for dev vs prod
    - Ensure ECS services, task definitions, and subdomains are environment-specific
    - _Requirements: 8.1, 8.2, 8.3_

- [x] 3. Checkpoint — Validate Terraform modules
  - Ensure `terraform validate` passes for both `infrastructure/terraform/persistent/` and `infrastructure/terraform/` roots
  - Ensure `terraform fmt -check` passes for all `.tf` files
  - Ask the user if questions arise.

- [x] 4. Create `ci-app.yml` workflow
  - [x] 4.1 Create `.github/workflows/ci-app.yml`
    - Trigger on `pull_request` and `push` to `main` with path filter `services/api/**`
    - Define parallel jobs: `gitleaks`, `lint` (black, isort, flake8), `type-check` (mypy), `security` (bandit, pip-audit), `unit-tests`, `integration-tests` (with postgres + redis service containers)
    - Add `quality-gate` summary job that `needs` all check jobs and fails if any failed
    - Set `concurrency` with `cancel-in-progress: true` per branch
    - Use OIDC-based AWS credentials via `aws-actions/configure-aws-credentials@v4` where needed
    - Set `permissions: id-token: write, contents: read`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 11.1, 11.2, 11.3, 11.4, 11.5, 12.3_

  - [ ]* 4.2 Write property tests for `ci-app.yml` trigger paths and concurrency
    - **Property 1: App CI does not trigger on infra-only changes**
    - Parse `ci-app.yml` YAML, assert `on.pull_request.paths` and `on.push.paths` only include `services/api/**`
    - **Property 3: Quality gate blocks on any check failure**
    - Assert `quality-gate` job `needs` includes all check job names
    - **Property 10: Gitleaks blocks PRs containing secrets**
    - Assert `gitleaks` job exists and is included in `quality-gate` needs
    - **Property 11: CI pipeline cancels stale runs**
    - Assert `concurrency.cancel-in-progress` is `true`
    - **Validates: Requirements 1.2, 1.3, 1.4, 11.4, 11.5, 12.3**

- [x] 5. Create `ci-infra.yml` workflow
  - [x] 5.1 Create `.github/workflows/ci-infra.yml`
    - Trigger on `pull_request` and `push` to `main` with path filter `infrastructure/terraform/**`
    - Define jobs: `static-analysis` (terraform fmt, validate, tflint, tfsec/checkov), `plan` (PR only — runs `terraform plan`, posts diff as PR comment via `actions/github-script`), `apply` (push to main only — `terraform apply` against dev, needs `static-analysis`)
    - Set `concurrency` group `infra-${{ github.event.inputs.environment || 'dev' }}` with `cancel-in-progress: false`
    - Use OIDC credentials and Terraform version >= 1.10
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.2, 11.2, 12.2, 12.3_

  - [x] 5.2 Write property test for `ci-infra.yml` trigger paths and concurrency
    - **Property 2: Infra CI does not trigger on app-only changes**
    - Parse `ci-infra.yml` YAML, assert `on.pull_request.paths` and `on.push.paths` only include `infrastructure/terraform/**`
    - **Property 11: CI pipeline cancels stale runs** (infra variant)
    - Assert `concurrency.cancel-in-progress` is `false` for infra (Terraform state safety)
    - **Validates: Requirements 2.3, 12.2, 12.3**

- [x] 6. Create `build.yml` workflow
  - [x] 6.1 Create `.github/workflows/build.yml`
    - Trigger on `push` to `main` with path filter `services/api/**` and `workflow_dispatch` with optional `image_tag` input
    - Define `build-push` job: hadolint Dockerfile validation, Docker Buildx with GHA cache, Trivy vulnerability scan (SARIF upload), ECR push with tags `{sha}` and `latest`
    - Output `image_tag` from `build-push` job
    - Define `trigger-deploy` job that calls `deploy.yml` as a reusable workflow with `environment: dev` and the built `image_tag`
    - Use OIDC credentials for ECR login
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 5.1, 6.4, 11.2_

  - [ ]* 6.2 Write property test for image tag flow
    - **Property 9: Image tag flows from build to deploy without mutation**
    - Parse `build.yml` YAML, trace `image_tag` output from `build-push` through `trigger-deploy` inputs
    - Assert the value passed to `deploy.yml` is `${{ needs.build-push.outputs.image_tag }}` with no transformation
    - **Validates: Requirements 3.2, 5.1**

- [x] 7. Create `deploy.yml` reusable workflow
  - [x] 7.1 Create `.github/workflows/deploy.yml`
    - Define as `workflow_call` with inputs: `environment` (dev | prod), `image_tag` (string)
    - Also support `workflow_dispatch` with the same inputs for manual prod deploys
    - Define `deploy` job: set `environment: ${{ inputs.environment }}` for GitHub Environment protection rules, update ECS task definitions for API and worker with the image tag, `aws ecs wait services-stable`, ALB target group health check
    - Define `migrate` job (needs deploy): ECS run-task with `alembic upgrade head`
    - Define `smoke-test` job (needs migrate): GET `/health`, `/docs`, `/api/v1/festivals`, `/nonexistent-route`
    - Define `rollback` job (needs smoke-test, if failure and prod): revert to previous task definition revision
    - Set `concurrency` group `deploy-${{ inputs.environment }}` with `cancel-in-progress: false`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 5.1, 5.3, 8.4, 8.5, 12.1, 12.4_

  - [ ]* 7.2 Write property tests for deploy workflow
    - **Property 6: Deploy pipeline is environment-isolated**
    - Parse `deploy.yml`, assert `concurrency` group includes environment variable and `cancel-in-progress: false`
    - **Property 7: Prod deployment requires approval**
    - Assert `deploy` job uses `environment` input that maps to a GitHub Environment
    - **Property 8: Prod smoke-test failure triggers rollback**
    - Assert `rollback` job exists with `if: failure() && inputs.environment == 'prod'` condition
    - **Validates: Requirements 4.6, 4.7, 8.5, 12.1, 12.4**

- [x] 8. Create `teardown.yml` workflow
  - [x] 8.1 Create `.github/workflows/teardown.yml`
    - Trigger on `schedule` (cron `0 18 * * 1-5` for 18:00 GMT Mon-Fri) and `workflow_dispatch`
    - Define `snapshot` job: create RDS cluster snapshot, wait for availability
    - Define `destroy` job (needs snapshot): `terraform destroy` targeting only the ephemeral root module
    - Define `verify` job (needs destroy): assert ECR, S3, Secrets Manager, Route 53 resources still exist via AWS CLI
    - Define `cleanup` job (needs destroy): delete snapshots older than 7 days
    - Use OIDC credentials
    - _Requirements: 7.1, 7.3, 7.5, 6.2, 11.2_

- [x] 9. Create `provision.yml` workflow
  - [x] 9.1 Create `.github/workflows/provision.yml`
    - Trigger on `schedule` (cron `0 9 * * 1-5` for 09:00 GMT Mon-Fri) and `workflow_dispatch`
    - Define `find-snapshot` job: query RDS for latest available snapshot, output snapshot identifier (or empty if none)
    - Define `apply` job (needs find-snapshot): `terraform apply` ephemeral module with `restore_from_snapshot` and `snapshot_identifier` variables
    - Define `wait-services` job (needs apply): `aws ecs wait services-stable`
    - Define `health-check` job (needs wait-services): poll `/health` endpoint
    - Use OIDC credentials
    - _Requirements: 7.2, 7.4, 7.6, 6.3, 11.2_

- [x] 10. Checkpoint — Validate all workflows
  - Ensure all six workflow YAML files are valid (use `actionlint` or manual YAML syntax check)
  - Verify path filters, concurrency groups, and job dependencies are correctly configured
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Create Makefile for local development
  - [x] 11.1 Create `Makefile` at the repository root
    - Add targets: `up`, `down`, `test`, `lint`, `typecheck`, `format`, `migrate`, `localstack`, `logs`
    - `up` / `down` wrap `docker compose up -d` / `docker compose down`
    - `test` runs `pytest` inside the container
    - `lint` runs black check, isort check, flake8
    - `typecheck` runs mypy
    - `format` runs black + isort auto-fix
    - `migrate` runs `alembic upgrade head` inside the container
    - `localstack` runs `docker compose -f docker-compose.yml -f docker-compose.aws.yml up -d`
    - `logs` runs `docker compose logs -f app`
    - _Requirements: 9.6_

- [x] 12. Update CI/CD documentation
  - [x] 12.1 Update `.github/workflows/README.md` and create/update `docs/cicd.md`
    - Document the pipeline architecture: all six workflows, their triggers, and relationships
    - Document local development setup with step-by-step first-time instructions referencing the Makefile
    - Document deployment procedures: dev (automatic on push to main), prod (manual workflow_dispatch with approval)
    - Document teardown/provisioning cycle including snapshot management
    - Document persistent vs ephemeral resource split and rationale
    - Document testing procedures: unit tests, integration tests, smoke tests (local and CI)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 13. Remove old monolithic workflow files
  - [x] 13.1 Delete old workflow files
    - Remove `.github/workflows/pr.yml`
    - Remove `.github/workflows/deploy-app.yml`
    - Remove `.github/workflows/deploy-infra.yml`
    - Remove `.github/workflows/deploy-prod.yml`
    - Remove `.github/workflows/scheduled-teardown.yml`
    - Remove `.github/workflows/scheduled-provision.yml`
    - _Requirements: 1.1, 1.2, 2.1, 2.3_

- [x] 14. Final checkpoint — Ensure all tests pass
  - Run all property-based tests and unit tests
  - Verify `terraform validate` passes for both persistent and ephemeral roots
  - Verify all workflow YAML files are syntactically valid
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties by parsing YAML and HCL files
- The design specifies Python (Hypothesis + pytest) for property-based tests
- Old workflow files are removed last to avoid breaking CI during the transition
