# GitHub Actions CI/CD Workflows

This directory contains GitHub Actions workflows for the Festival Playlist Generator AWS migration project.

## Workflows

### 1. Pull Request Validation (`pr.yml`)

**Trigger**: Pull requests to `main` or `develop` branches

**Purpose**: Validates code quality, runs tests, and builds Docker images for all pull requests.

**Jobs**:

1. **Code Quality (Linting & Formatting)**
   - Runs `black` to check code formatting
   - Runs `isort` to check import sorting
   - Runs `flake8` for linting

2. **Type Checking**
   - Runs `mypy` for static type checking
   - Ensures type safety across the codebase

3. **Security Scanning**
   - Runs `bandit` for security vulnerability detection
   - Runs `safety` for dependency vulnerability checking
   - Uploads security reports as artifacts

4. **Unit Tests**
   - Runs unit tests (non-integration tests)
   - Generates coverage reports
   - Enforces 80% minimum coverage threshold

5. **Integration Tests**
   - Spins up PostgreSQL and Redis services
   - Runs integration tests against real services
   - Generates coverage reports

6. **Upload Coverage to Codecov**
   - Uploads coverage reports to Codecov
   - Provides coverage visualization and tracking

7. **Docker Build & Validation**
   - Validates Dockerfile with hadolint
   - Builds Docker image with layer caching
   - Tests the built image
   - Scans for vulnerabilities with Trivy

8. **Quality Gate Summary**
   - Aggregates results from all jobs
   - Fails if any job fails
   - Provides clear summary of what passed/failed

**Required Secrets**:
- `CODECOV_TOKEN` (optional): For uploading coverage to Codecov

**Caching**:
- Python dependencies cached via `setup-python` action
- Docker layers cached via GitHub Actions cache

## Configuration

### Python Version
All jobs use Python 3.11 to match the production environment.

### Coverage Threshold
The minimum coverage threshold is set to 80%. PRs with lower coverage will fail.

### Service Versions
- PostgreSQL: 15-alpine
- Redis: 7-alpine

### Test Environment Variables
Integration tests use the following environment variables:
- `DATABASE_URL`: postgresql+asyncpg://test_user:test_password@localhost:5432/test_db
- `REDIS_URL`: redis://localhost:6379/0
- `ENVIRONMENT`: test

## Local Testing

To run the same checks locally before pushing:

```bash
# Navigate to the API directory
cd services/api

# Install dependencies
pip install -r requirements.txt
pip install black isort flake8 mypy bandit safety pytest-cov

# Run linting
black --check .
isort --check-only .
flake8 .

# Run type checking
mypy festival_playlist_generator --ignore-missing-imports

# Run security scanning
bandit -r festival_playlist_generator
safety check

# Run tests with coverage
pytest tests/ --cov=festival_playlist_generator --cov-report=term

# Build Docker image
cd ../..
docker build -t festival-api:local services/api/
```

## Troubleshooting

### Coverage Below Threshold
If your PR fails due to coverage below 80%, add tests for uncovered code:
```bash
# Generate HTML coverage report to see what's missing
pytest tests/ --cov=festival_playlist_generator --cov-report=html
open htmlcov/index.html
```

### Linting Failures
Auto-fix formatting issues:
```bash
black .
isort .
```

### Type Checking Failures
Add type hints to functions and variables. Use `# type: ignore` sparingly for third-party libraries.

### Docker Build Failures
Test Docker build locally:
```bash
docker build -t festival-api:test services/api/
docker run --rm festival-api:test python -c "import festival_playlist_generator; print('OK')"
```

## Future Enhancements

The following workflows will be added in later tasks:
- `deploy-dev.yml`: Automated deployment to dev environment
- `deploy-prod.yml`: Manual deployment to production
- `scheduled-teardown.yml`: Daily infrastructure teardown
- `scheduled-provision.yml`: Daily infrastructure provisioning

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Python setup-python action](https://github.com/actions/setup-python)
- [Docker build-push-action](https://github.com/docker/build-push-action)
- [Codecov GitHub Action](https://github.com/codecov/codecov-action)
