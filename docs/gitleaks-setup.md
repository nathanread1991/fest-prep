# Gitleaks Setup

## Overview
Gitleaks is configured as a pre-commit hook to prevent secrets from being committed to the repository.

## Installation
Gitleaks is installed via Homebrew:
```bash
brew install gitleaks
```

## Pre-commit Hook
The pre-commit hook (`.git/hooks/pre-commit`) automatically scans staged files before each commit.

### Behavior
- ✅ Allows commit if no secrets detected
- ❌ Blocks commit if secrets are found
- Provides clear error messages with file locations

### Bypass (NOT RECOMMENDED)
If you absolutely need to bypass the check:
```bash
git commit --no-verify
```

## Configuration
The `.gitleaks.toml` file contains:
- Base configuration extending gitleaks defaults
- Allowlist for known false positives
- Path exclusions for test/example files
- Localhost SSL certificates are allowed (development only)

## Manual Scanning

### Scan entire repository
```bash
gitleaks detect --verbose
```

### Scan staged files only
```bash
gitleaks protect --staged --verbose
```

### Scan specific commit
```bash
gitleaks detect --log-opts="<commit-hash>"
```

## CI/CD Integration
Gitleaks is also integrated into the GitHub Actions CI pipeline (`.github/workflows/pr.yml`) to scan all pull requests.

## Allowlisted Items
- `.env.example` files
- `terraform.tfvars.example` files
- Test and mock files
- Localhost SSL certificates (`ssl/localhost.key`, `ssl/localhost.crt`)

## Troubleshooting

### False Positives
If gitleaks flags a false positive:
1. Add the pattern to `.gitleaks.toml` allowlist
2. Commit the updated configuration
3. Re-run the scan

### Hook Not Running
Ensure the hook is executable:
```bash
chmod +x .git/hooks/pre-commit
```

## Resources
- [Gitleaks Documentation](https://github.com/gitleaks/gitleaks)
- [Gitleaks Configuration](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml)
