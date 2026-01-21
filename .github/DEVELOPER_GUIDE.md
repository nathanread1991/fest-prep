# Developer Guide: GitHub Actions CI Workflow

## Quick Start

Every pull request to `main` or `develop` automatically triggers the CI workflow. Here's what you need to know:

## What Gets Checked

### 1. Code Quality ✨
- **Black**: Code must be formatted correctly
- **isort**: Imports must be sorted
- **flake8**: Code must pass linting

**Fix locally:**
```bash
cd services/api
black .
isort .
flake8 .
```

### 2. Type Safety 🔍
- **mypy**: Type hints must be correct

**Fix locally:**
```bash
cd services/api
mypy festival_playlist_generator --ignore-missing-imports
```

### 3. Security 🔒
- **Bandit**: No security vulnerabilities in code
- **Safety**: No vulnerable dependencies

**Check locally:**
```bash
cd services/api
bandit -r festival_playlist_generator
safety check
```

### 4. Tests ✅
- **Unit Tests**: Must pass with 80%+ coverage
- **Integration Tests**: Must pass with real PostgreSQL and Redis

**Run locally:**
```bash
cd services/api
pytest tests/ -m "not integration" --cov=festival_playlist_generator
pytest tests/ -m integration  # Requires Docker services
```

### 5. Docker Build 🐳
- Dockerfile must be valid
- Image must build successfully
- No critical vulnerabilities

**Test locally:**
```bash
docker build -t festival-api:test services/api/
docker run --rm festival-api:test python -c "import festival_playlist_generator; print('OK')"
```

## Pre-Push Checklist

Before pushing your code, run these commands:

```bash
# Navigate to API directory
cd services/api

# Format code
black .
isort .

# Run all checks
flake8 .
mypy festival_playlist_generator --ignore-missing-imports
bandit -r festival_playlist_generator

# Run tests
pytest tests/ --cov=festival_playlist_generator --cov-report=term

# Build Docker image
cd ../..
docker build -t festival-api:local services/api/
```

## Common Issues and Solutions

### ❌ "Black formatting check failed"
**Solution:**
```bash
cd services/api
black .
git add .
git commit -m "Fix formatting"
```

### ❌ "Import sorting check failed"
**Solution:**
```bash
cd services/api
isort .
git add .
git commit -m "Fix import sorting"
```

### ❌ "Coverage below 80%"
**Solution:**
1. Generate HTML coverage report:
   ```bash
   pytest tests/ --cov=festival_playlist_generator --cov-report=html
   open htmlcov/index.html
   ```
2. Add tests for uncovered code
3. Commit and push

### ❌ "Type checking failed"
**Solution:**
1. Add type hints to functions:
   ```python
   def my_function(name: str, age: int) -> dict:
       return {"name": name, "age": age}
   ```
2. For third-party libraries without types, use `# type: ignore`:
   ```python
   import some_library  # type: ignore
   ```

### ❌ "Integration tests failed"
**Solution:**
1. Ensure you have Docker running locally
2. Start PostgreSQL and Redis:
   ```bash
   docker-compose up -d postgres redis
   ```
3. Run integration tests:
   ```bash
   pytest tests/ -m integration
   ```

### ❌ "Docker build failed"
**Solution:**
1. Check Dockerfile syntax
2. Ensure all dependencies in requirements.txt
3. Test build locally:
   ```bash
   docker build -t festival-api:test services/api/
   ```

## Workflow Artifacts

After the workflow runs, you can download:

1. **Bandit Security Report** (JSON)
   - Security vulnerability scan results
   - Download from Actions tab → Artifacts

2. **Coverage Reports** (XML + HTML)
   - Detailed coverage information
   - Shows which lines are covered/uncovered

3. **Trivy Scan Results** (SARIF)
   - Docker image vulnerability scan
   - Lists all vulnerabilities found

## Workflow Performance

Expected run times:
- **Linting**: ~1-2 minutes
- **Type Checking**: ~2-3 minutes
- **Security Scanning**: ~2-3 minutes
- **Unit Tests**: ~3-5 minutes
- **Integration Tests**: ~5-7 minutes
- **Docker Build**: ~3-5 minutes

**Total**: ~8-12 minutes (jobs run in parallel)

## Skipping Workflow

To skip the workflow for documentation-only changes:

```bash
git commit -m "docs: Update README [skip ci]"
```

Note: This is generally discouraged. Let the workflow run to ensure nothing breaks.

## Getting Help

If you're stuck:

1. Check the workflow logs in GitHub Actions tab
2. Look for the specific job that failed
3. Read the error message carefully
4. Try reproducing the issue locally
5. Ask for help in the team chat with:
   - Link to the failed workflow run
   - What you've tried so far
   - Error message

## Best Practices

### ✅ DO:
- Run checks locally before pushing
- Write tests for new code
- Keep coverage above 80%
- Use type hints
- Format code with black and isort
- Fix security issues immediately

### ❌ DON'T:
- Push without running tests locally
- Ignore linting errors
- Skip type hints
- Commit unformatted code
- Ignore security warnings
- Push broken Docker builds

## IDE Integration

### VS Code
Install these extensions:
- Python (Microsoft)
- Pylance (Microsoft)
- Black Formatter (Microsoft)
- isort (Microsoft)

Add to `.vscode/settings.json`:
```json
{
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "editor.formatOnSave": true,
  "python.sortImports.args": ["--profile", "black"]
}
```

### PyCharm
1. Settings → Tools → Black → Enable
2. Settings → Tools → External Tools → Add isort
3. Settings → Editor → Inspections → Enable flake8
4. Settings → Editor → Code Style → Python → Set line length to 88

## Questions?

- Check `.github/workflows/README.md` for detailed workflow documentation
- Check `.github/IMPLEMENTATION_SUMMARY.md` for implementation details
- Ask in team chat or create an issue

---

**Remember**: The CI workflow is here to help you catch issues early. Don't fight it, embrace it! 🚀
