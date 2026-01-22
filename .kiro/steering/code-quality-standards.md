---
title: Code Quality Standards
inclusion: always
---

# Code Quality Standards

This project enforces strict code quality standards that MUST be followed for all code changes.

## Pre-Commit Hooks

Pre-commit hooks are configured and MUST be installed before making any commits:

```bash
pip install pre-commit
pre-commit install
```

## Required Checks

All code MUST pass the following checks before being committed:

### 1. Gitleaks - Secret Scanning
- **Tool**: gitleaks
- **Purpose**: Prevent secrets and credentials from being committed
- **Failure**: Commit will be blocked if secrets are detected
- **Fix**: Remove secrets and add patterns to .gitignore

### 2. Black - Code Formatting
- **Tool**: black
- **Config**: `services/api/pyproject.toml`
- **Purpose**: Enforce consistent Python code formatting
- **Command**: `docker exec festival_app black festival_playlist_generator/ tests/`
- **Failure**: CI pipeline will fail if code is not formatted
- **CRITICAL**: Always run black before committing Python code

### 3. isort - Import Sorting
- **Tool**: isort
- **Config**: `services/api/pyproject.toml`
- **Purpose**: Sort and organize Python imports
- **Command**: `docker exec festival_app isort festival_playlist_generator/ tests/`
- **Failure**: CI pipeline will fail if imports are not sorted

### 4. Flake8 - Linting
- **Tool**: flake8
- **Config**: `services/api/setup.cfg`
- **Purpose**: Enforce Python code style and catch common errors
- **Command**: `docker exec festival_app flake8 festival_playlist_generator/ tests/ --max-line-length=88 --extend-ignore=E203,W503`
- **Failure**: CI pipeline will fail on linting errors

### 5. MyPy - Type Checking
- **Tool**: mypy
- **Config**: `services/api/setup.cfg`
- **Mode**: STRICT MODE ENABLED
- **Purpose**: Enforce type safety across all Python code
- **Command**: `docker exec festival_app python -m mypy festival_playlist_generator/ --config-file=setup.cfg`
- **Failure**: CI pipeline will fail on type errors
- **Rules**:
  - All functions must have type annotations
  - No `Any` types without justification
  - All return types must be specified
  - Strict optional checking enabled

## CI Pipeline Requirements

The CI pipeline will run ALL of these checks. You CANNOT merge code that fails any check.

### Pipeline Order:
1. Gitleaks (secrets)
2. Black (formatting)
3. isort (imports)
4. Flake8 (linting)
5. MyPy (type checking)
6. Tests (pytest)

## Local Development Workflow

### Before Every Commit:

```bash
# 1. Format code
docker exec festival_app black festival_playlist_generator/ tests/

# 2. Sort imports
docker exec festival_app isort festival_playlist_generator/ tests/

# 3. Check linting
docker exec festival_app flake8 festival_playlist_generator/ tests/ --max-line-length=88 --extend-ignore=E203,W503

# 4. Check types
docker exec festival_app python -m mypy festival_playlist_generator/ --config-file=setup.cfg

# 5. Run tests
docker exec festival_app python -m pytest tests/ -v

# 6. Commit (pre-commit hooks will run automatically)
git add .
git commit -m "your message"
```

### Or use the convenience script:

```bash
./festival.sh format    # Runs black and isort
./festival.sh lint      # Runs flake8 and mypy
./festival.sh typecheck # Runs mypy only
./festival.sh test      # Runs pytest
```

## Common Issues and Fixes

### Black Formatting Failures
**Error**: "50 files would be reformatted"
**Fix**: Run `docker exec festival_app black festival_playlist_generator/ tests/`

### Import Sorting Failures
**Error**: "Imports are incorrectly sorted"
**Fix**: Run `docker exec festival_app isort festival_playlist_generator/ tests/`

### MyPy Type Errors
**Error**: Various type checking errors
**Fix**: Add proper type annotations, fix type mismatches
**Note**: Do NOT use `# type: ignore` without a specific reason

### Gitleaks Failures
**Error**: "leaks found"
**Fix**: Remove secrets, add to .gitignore, use environment variables

## Configuration Files

- **Pre-commit**: `.pre-commit-config.yaml`
- **Black**: `services/api/pyproject.toml`
- **isort**: `services/api/pyproject.toml`
- **Flake8**: `services/api/setup.cfg`
- **MyPy**: `services/api/setup.cfg`
- **Pytest**: `services/api/pyproject.toml`

## Enforcement

These standards are ENFORCED at multiple levels:
1. **Pre-commit hooks**: Run automatically on `git commit`
2. **CI Pipeline**: Runs on every push and PR
3. **Code Review**: Reviewers will check for compliance

**IMPORTANT**: The CI pipeline will FAIL if any check fails. You must fix all issues before your PR can be merged.
