# Secrets Management Guide

## Overview

This guide explains how to manage secrets for the Festival Playlist Generator application using AWS Secrets Manager.

## Secrets Created by Terraform

The following secrets are automatically created by Terraform but require manual population:

### 1. Database Credentials (`festival-playlist-dev-db-credentials`)

**Status:** ✅ Auto-populated by Terraform

This secret contains the Aurora PostgreSQL database connection information:
- `host`: Database endpoint
- `port`: Database port (5432)
- `database`: Database name
- `username`: Master username
- `password`: Auto-generated password
- `url`: Full PostgreSQL connection string

**No manual action required** - Terraform generates and stores these automatically.

### 2. Redis Connection URL (`festival-playlist-dev-redis-url`)

**Status:** ✅ Auto-populated by Terraform

This secret contains the ElastiCache Redis connection information:
- `url`: Redis connection string (redis://host:port)
- `host`: Redis endpoint
- `port`: Redis port (6379)

**No manual action required** - Terraform generates and stores these automatically.

### 3. Spotify API Credentials (`festival-playlist-dev-spotify`)

**Status:** ⚠️ Requires manual population

This secret must contain your Spotify API credentials:

```json
{
  "client_id": "YOUR_SPOTIFY_CLIENT_ID",
  "client_secret": "YOUR_SPOTIFY_CLIENT_SECRET"
}
```

**How to get Spotify credentials:**
1. Go to https://developer.spotify.com/dashboard
2. Log in with your Spotify account
3. Click "Create an App"
4. Fill in app name and description
5. Copy the Client ID and Client Secret

**How to populate:**

Option 1: Use the helper script (recommended):
```bash
cd infrastructure/terraform/scripts
./populate-secrets.sh
```

Option 2: Use AWS CLI directly:
```bash
aws secretsmanager put-secret-value \
  --secret-id festival-playlist-dev-spotify \
  --secret-string '{"client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_CLIENT_SECRET"}' \
  --profile festival-playlist \
  --region eu-west-2
```

Option 3: Use AWS Console:
1. Go to AWS Secrets Manager console
2. Find secret: `festival-playlist-dev-spotify`
3. Click "Retrieve secret value"
4. Click "Edit"
5. Paste the JSON above with your credentials
6. Click "Save"

### 4. Setlist.fm API Key (`festival-playlist-dev-setlistfm`)

**Status:** ⚠️ Requires manual population

This secret must contain your Setlist.fm API key:

```json
{
  "api_key": "YOUR_SETLISTFM_API_KEY"
}
```

**How to get Setlist.fm API key:**
1. Go to https://api.setlist.fm/docs/1.0/index.html
2. Click "Apply for an API key"
3. Fill in the application form
4. Wait for approval (usually 1-2 days)
5. Copy your API key from the email

**How to populate:**

Option 1: Use the helper script (recommended):
```bash
cd infrastructure/terraform/scripts
./populate-secrets.sh
```

Option 2: Use AWS CLI directly:
```bash
aws secretsmanager put-secret-value \
  --secret-id festival-playlist-dev-setlistfm \
  --secret-string '{"api_key":"YOUR_API_KEY"}' \
  --profile festival-playlist \
  --region eu-west-2
```

Option 3: Use AWS Console:
1. Go to AWS Secrets Manager console
2. Find secret: `festival-playlist-dev-setlistfm`
3. Click "Retrieve secret value"
4. Click "Edit"
5. Paste the JSON above with your API key
6. Click "Save"

### 5. JWT Signing Key (`festival-playlist-dev-jwt-secret`)

**Status:** ✅ Auto-populated by Terraform

This secret contains the JWT signing key for authentication:
- `secret_key`: Auto-generated random string (64 characters)

**No manual action required** - Terraform generates and stores this automatically.

## Verifying Secrets

### Check if secrets exist:

```bash
aws secretsmanager list-secrets \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecretList[?starts_with(Name, `festival-playlist-dev`)].Name' \
  --output table
```

Expected output:
```
-----------------------------------------
|              ListSecrets              |
+---------------------------------------+
|  festival-playlist-dev-db-credentials |
|  festival-playlist-dev-redis-url      |
|  festival-playlist-dev-spotify        |
|  festival-playlist-dev-setlistfm      |
|  festival-playlist-dev-jwt-secret     |
+---------------------------------------+
```

### Check if a secret has a value:

```bash
# Check Spotify secret
aws secretsmanager get-secret-value \
  --secret-id festival-playlist-dev-spotify \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecretString' \
  --output text
```

If the secret is empty, you'll see an error. If it's populated, you'll see the JSON value.

### Verify all secrets are accessible by ECS tasks:

```bash
cd infrastructure/terraform/scripts
./populate-secrets.sh
```

This script will verify that all secrets are properly configured and accessible.

## ECS Task Access

ECS tasks access secrets through environment variables that are automatically injected at runtime:

### API Service Environment Variables:

- `DATABASE_URL` - From `festival-playlist-dev-db-credentials:url`
- `REDIS_URL` - From `festival-playlist-dev-redis-url:url`
- `SPOTIFY_CLIENT_ID` - From `festival-playlist-dev-spotify:client_id`
- `SPOTIFY_CLIENT_SECRET` - From `festival-playlist-dev-spotify:client_secret`
- `SETLISTFM_API_KEY` - From `festival-playlist-dev-setlistfm:api_key`
- `JWT_SECRET_KEY` - From `festival-playlist-dev-jwt-secret:secret_key`

### Worker Service Environment Variables:

- `DATABASE_URL` - From `festival-playlist-dev-db-credentials:url`
- `REDIS_URL` - From `festival-playlist-dev-redis-url:url`
- `SPOTIFY_CLIENT_ID` - From `festival-playlist-dev-spotify:client_id`
- `SPOTIFY_CLIENT_SECRET` - From `festival-playlist-dev-spotify:client_secret`
- `SETLISTFM_API_KEY` - From `festival-playlist-dev-setlistfm:api_key`

## IAM Permissions

ECS tasks have the following permissions to access secrets:

### ECS Task Execution Role:
- `secretsmanager:GetSecretValue` - Read secret values at task startup
- Limited to secrets with prefix: `festival-playlist-dev-*`

### ECS Task Role:
- No direct secrets access (secrets are injected as environment variables)

## Security Best Practices

1. **Never commit secrets to Git**
   - Secrets are stored in AWS Secrets Manager only
   - Never hardcode credentials in code or configuration files

2. **Use least privilege access**
   - ECS tasks can only read secrets they need
   - Secrets are scoped by environment (dev, staging, prod)

3. **Rotate secrets regularly**
   - Database passwords: Auto-rotated by AWS (optional)
   - API keys: Rotate manually when compromised
   - JWT secret: Rotate when security incident occurs

4. **Monitor secret access**
   - CloudTrail logs all secret access
   - Set up alarms for unusual access patterns

5. **Use encryption at rest**
   - All secrets are encrypted with AWS KMS
   - Encryption keys are managed by AWS

## Troubleshooting

### Issue: ECS tasks fail to start with "Cannot retrieve secret"

**Cause:** Secret is not populated or ECS task doesn't have permission

**Solution:**
1. Check if secret exists and has a value:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id festival-playlist-dev-spotify \
     --profile festival-playlist \
     --region eu-west-2
   ```

2. Check ECS task execution role has permission:
   ```bash
   aws iam get-role-policy \
     --role-name festival-playlist-dev-ecs-task-execution-role \
     --policy-name SecretsManagerAccess \
     --profile festival-playlist
   ```

3. Populate the secret using the helper script:
   ```bash
   cd infrastructure/terraform/scripts
   ./populate-secrets.sh
   ```

### Issue: "Access Denied" when trying to read secret

**Cause:** AWS CLI profile doesn't have permission

**Solution:**
1. Verify you're using the correct profile:
   ```bash
   aws sts get-caller-identity --profile festival-playlist
   ```

2. Check your IAM user has `secretsmanager:GetSecretValue` permission

3. Try using the AWS Console instead

### Issue: Secret value is incorrect

**Cause:** Secret was populated with wrong value

**Solution:**
1. Update the secret value:
   ```bash
   aws secretsmanager put-secret-value \
     --secret-id festival-playlist-dev-spotify \
     --secret-string '{"client_id":"CORRECT_ID","client_secret":"CORRECT_SECRET"}' \
     --profile festival-playlist \
     --region eu-west-2
   ```

2. Restart ECS tasks to pick up new value:
   ```bash
   aws ecs update-service \
     --cluster festival-playlist-dev \
     --service festival-playlist-dev-api \
     --force-new-deployment \
     --profile festival-playlist \
     --region eu-west-2
   ```

## Cost Considerations

- **Secrets Manager cost:** $0.40 per secret per month
- **API calls:** $0.05 per 10,000 API calls
- **Total for 5 secrets:** ~$2/month

Secrets are marked as persistent in Terraform (`prevent_destroy = true`) to avoid accidental deletion during teardown.

## Next Steps

After populating secrets:

1. ✅ Verify all secrets are accessible
2. ✅ Build and push Docker image to ECR
3. ✅ Deploy application to ECS
4. ✅ Test application can connect to database and external APIs
5. ✅ Monitor CloudWatch Logs for any secret-related errors
