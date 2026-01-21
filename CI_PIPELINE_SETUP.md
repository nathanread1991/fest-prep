# CI Pipeline Setup and Testing Guide

## Current Status

The GitHub Actions workflow (`.github/workflows/pr.yml`) is **configured but never tested** because this is not yet a git repository.

## Steps to Test CI Pipeline

### 1. Initialize Git Repository

```bash
# Initialize git in project root
git init

# Create .gitignore if not exists
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
*.egg-info/
dist/
build/

# Testing
.pytest_cache/
.coverage
htmlcov/
*.cover
.hypothesis/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# Environment
.env
.env.local

# Terraform
*.tfstate
*.tfstate.*
.terraform/
*.tfvars
!*.tfvars.example

# Logs
*.log
logs/

# OS
.DS_Store
Thumbs.db

# Node
node_modules/
npm-debug.log*

# Test results
test-results/
playwright-report/
EOF

# Add all files
git add .

# Initial commit
git commit -m "Initial commit: Week 1 AWS Enterprise Migration foundation"
```

### 2. Create GitHub Repository

```bash
# Option A: Using GitHub CLI (if installed)
gh repo create gigprep --private --source=. --remote=origin

# Option B: Manual
# 1. Go to https://github.com/new
# 2. Create repository named "gigprep" (or your preferred name)
# 3. Choose private/public
# 4. Don't initialize with README (we already have code)
# 5. Copy the repository URL
```

### 3. Push to GitHub

```bash
# Add remote (if not using gh CLI)
git remote add origin https://github.com/YOUR_USERNAME/gigprep.git

# Create main branch
git branch -M main

# Push to GitHub
git push -u origin main
```

### 4. Create Test Pull Request

```bash
# Create a test branch
git checkout -b test/ci-pipeline

# Make a small change (e.g., update README)
echo "\n## CI Pipeline Test" >> README.md

# Commit and push
git add README.md
git commit -m "test: Verify CI pipeline works"
git push -u origin test/ci-pipeline

# Create PR using GitHub CLI
gh pr create --title "Test: CI Pipeline Verification" --body "Testing GitHub Actions workflow"

# Or create PR manually at:
# https://github.com/YOUR_USERNAME/gigprep/compare/main...test/ci-pipeline
```

### 5. Monitor CI Pipeline

Once the PR is created, GitHub Actions will automatically trigger. Monitor at:
```
https://github.com/YOUR_USERNAME/gigprep/actions
```

**Expected Jobs (7 total):**
1. ✅ Lint (Black, isort, flake8)
2. ✅ Type Check (mypy)
3. ✅ Security (Bandit, Safety)
4. ✅ Unit Tests (with coverage)
5. ✅ Integration Tests (PostgreSQL + Redis)
6. ✅ Docker Build (with Trivy scan)
7. ✅ Quality Gate (summary)

### 6. Troubleshooting Common Issues

#### Issue: Tests fail due to missing dependencies

**Solution:** Ensure `requirements.txt` is complete
```bash
cd services/api
pip freeze > requirements.txt
git add requirements.txt
git commit -m "fix: Update requirements.txt"
git push
```

#### Issue: Docker build fails

**Solution:** Check Dockerfile exists and is valid
```bash
# Validate Dockerfile locally
docker build -t test services/api/

# If it works locally, check GitHub Actions logs for specific error
```

#### Issue: Coverage threshold not met

**Solution:** The checkpoint report shows 90% coverage for repositories, but overall coverage may be lower due to untested services. Options:
1. Adjust threshold in workflow (line 177): `--fail-under=80` → `--fail-under=70`
2. Configure coverage to only measure specific modules
3. Add more tests to reach 80% overall

#### Issue: Integration tests fail

**Solution:** Check PostgreSQL/Redis service configuration in workflow
- Ensure connection strings match service configuration
- Verify test database migrations run correctly

### 7. Configure Secrets (Optional)

Some jobs may need secrets:

```bash
# Using GitHub CLI
gh secret set CODECOV_TOKEN --body "your-codecov-token"

# Or manually at:
# https://github.com/YOUR_USERNAME/gigprep/settings/secrets/actions
```

**Required Secrets:**
- `CODECOV_TOKEN` - For coverage upload (optional, can disable)

### 8. Verify Success

Once all jobs pass:
- ✅ All 7 jobs show green checkmarks
- ✅ Coverage report is generated
- ✅ Docker image builds successfully
- ✅ Security scans complete
- ✅ Quality gate passes

You can then merge the PR or close it (it was just for testing).

## Quick Test Without PR

If you want to test locally before pushing:

```bash
# Test linting
cd services/api
black --check .
isort --check-only .
flake8 .

# Test type checking
mypy festival_playlist_generator --ignore-missing-imports

# Test security
bandit -r festival_playlist_generator -ll
safety check

# Run tests
pytest tests/ --cov=festival_playlist_generator --cov-report=term

# Build Docker image
docker build -t festival-api:test .
```

## Estimated Time

- **Setup (steps 1-3):** 15-30 minutes
- **Create test PR (step 4):** 5 minutes
- **CI pipeline execution:** 10-15 minutes
- **Troubleshooting (if needed):** 30-60 minutes

**Total:** 1-2 hours

## Next Steps After CI Passes

1. ✅ Mark task 7 as fully complete
2. Update checkpoint report with actual CI results
3. Proceed with controller refactoring
4. Begin Week 2 infrastructure provisioning

## Notes

- The workflow is configured to run on PRs to `main` and `develop` branches
- It only triggers when files in `services/api/`, `.github/workflows/`, or `infrastructure/terraform/` change
- Concurrency control cancels in-progress runs when new commits are pushed
- Artifacts (coverage reports, security scans) are retained for 30 days
