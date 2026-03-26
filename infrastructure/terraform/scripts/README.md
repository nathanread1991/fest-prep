# Terraform Scripts

This directory contains utility scripts for managing Terraform infrastructure.

## Overview

- **init-backend.sh** - Initialize S3 backend for Terraform state
- **teardown.sh** - Safely destroy infrastructure with database snapshot
- **provision.sh** - Restore infrastructure from latest snapshot
- **cost-report.sh** - Generate detailed cost reports
- **test-workflow.sh** - Test teardown and provision workflow (Task 17.4)
- **cleanup-old-snapshots.sh** - Clean up old database snapshots
- **list-snapshots.sh** - List available database snapshots

## init-backend.sh

Initializes the Terraform backend by creating the required S3 bucket for remote state storage with native S3 locking (Terraform v1.10+).

### What it does:

Creates S3 bucket: `festival-playlist-terraform-state`
- Enables versioning (rollback capability)
- Enables server-side encryption (AES256)
- Blocks public access (security)
- Adds lifecycle policy (delete old versions after 90 days)
- Configures for native S3 locking (no DynamoDB needed!)

### Native S3 Locking (Terraform v1.10+)

Terraform v1.10 introduced native S3 state locking, eliminating the need for DynamoDB:

**Benefits:**
- ✅ Simpler setup (one resource instead of two)
- ✅ Lower cost (no DynamoDB charges)
- ✅ Fewer resources to manage
- ✅ Same reliability as DynamoDB locking

**How it works:**
- Uses S3's conditional writes for atomic operations
- Stores lock information in S3 metadata
- Automatically handles lock acquisition and release

### Prerequisites:

- Terraform v1.10 or higher
- AWS CLI installed
- AWS credentials configured for profile `festival-playlist`
- Appropriate IAM permissions (S3 only - no DynamoDB needed!)

### Usage:

```bash
# Run from terraform directory
cd terraform
./scripts/init-backend.sh

# Or run from project root
./terraform/scripts/init-backend.sh
```

### After running:

1. Uncomment the backend configuration in `terraform/backend.tf`
2. Run `terraform init` to initialize the backend
3. If you have existing local state, run `terraform init -migrate-state`

### Environment Variables:

- `AWS_PROFILE`: Override the default AWS profile (default: `festival-playlist`)

Example:
```bash
AWS_PROFILE=my-profile ./scripts/init-backend.sh
```

### Troubleshooting:

**Error: Bucket already exists**
- The bucket name is globally unique across all AWS accounts
- If you get a conflict, update the bucket name in the script

**Error: AWS credentials not configured**
- Run: `aws configure --profile festival-playlist`
- Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables

**Error: Access Denied**
- Ensure your IAM user/role has permissions for:
  - s3:CreateBucket, s3:PutBucketVersioning, s3:PutBucketEncryption
  - s3:PutBucketPublicAccessBlock, s3:PutLifecycleConfiguration

**Error: Terraform version too old**
- Native S3 locking requires Terraform v1.10+
- Check version: `terraform version`
- Upgrade if needed

### Cost:

- S3 bucket: ~$0.023/GB/month + request costs
- No DynamoDB costs (native S3 locking is free!)
- Estimated monthly cost: < $1 for typical usage

### Cleanup:

To delete the backend resources (not recommended unless decommissioning):

```bash
# Empty and delete S3 bucket
aws s3 rm s3://festival-playlist-terraform-state --recursive --profile festival-playlist
aws s3api delete-bucket \
  --bucket festival-playlist-terraform-state \
  --profile festival-playlist \
  --region eu-west-2
```

**Warning**: Deleting the backend will lose all Terraform state history!

### Migration from DynamoDB Locking:

If you previously used DynamoDB locking and want to migrate:

1. Run this script to create the S3 bucket (if not exists)
2. Update `backend.tf` to use `use_lockfile = true`
3. Run `terraform init -migrate-state`
4. Delete the old DynamoDB table (optional):
   ```bash
   aws dynamodb delete-table \
     --table-name festival-playlist-terraform-locks \
     --profile festival-playlist \
     --region eu-west-2
   ```


## teardown.sh

Safely destroys AWS infrastructure while preserving data through database snapshots.

### What it does:

1. Creates a database snapshot before destruction
2. Waits for snapshot completion (max 30 minutes)
3. Runs `terraform destroy` to remove compute resources
4. Cleans up old snapshots (keeps last 7 days)
5. Verifies destruction of compute resources
6. Displays cost summary

### Features:

- ✅ Automated database backup before teardown
- ✅ Snapshot verification and waiting
- ✅ Old snapshot cleanup (configurable retention)
- ✅ Destruction verification
- ✅ Cost summary display
- ✅ Persistent resources preserved (S3, Secrets Manager, ECR)

### Prerequisites:

- Terraform initialized and configured
- AWS CLI installed
- AWS credentials configured for profile `festival-playlist`
- Existing infrastructure deployed

### Usage:

```bash
# Run from terraform directory
cd terraform
./scripts/teardown.sh

# Or run from project root
./terraform/scripts/teardown.sh

# With custom environment
ENVIRONMENT=staging ./scripts/teardown.sh

# With custom snapshot retention
SNAPSHOT_RETENTION_DAYS=14 ./scripts/teardown.sh
```

### Environment Variables:

- `PROJECT_NAME`: Project name (default: `festival-playlist`)
- `ENVIRONMENT`: Environment name (default: `dev`)
- `AWS_PROFILE`: AWS profile to use (default: `festival-playlist`)
- `AWS_REGION`: AWS region (default: `eu-west-2`)
- `SNAPSHOT_RETENTION_DAYS`: Days to keep snapshots (default: `7`)

### What Gets Destroyed:

- ✅ ECS Fargate clusters and tasks
- ✅ RDS Aurora Serverless v2 cluster (after snapshot)
- ✅ ElastiCache Redis cluster
- ✅ Application Load Balancer
- ✅ VPC and networking resources
- ✅ CloudWatch log groups (optional)

### What Persists:

- ✅ S3 buckets (data, logs, Terraform state)
- ✅ Secrets Manager secrets
- ✅ ECR container images
- ✅ Database snapshots
- ✅ Route 53 hosted zones

### Cost Impact:

After teardown, costs reduce to ~$2-5/month:
- S3 storage: ~$1-2/month
- Secrets Manager: ~$1-2/month
- RDS snapshots: Free for 7 days, then ~$0.095/GB/month

### Time:

- Typical teardown time: 8-12 minutes
- Snapshot creation: 5-10 minutes
- Resource destruction: 3-5 minutes

### Troubleshooting:

**Error: Snapshot creation failed**
- Check RDS cluster is running
- Check AWS permissions for RDS snapshots
- Check snapshot quota limits

**Error: Terraform destroy failed**
- Check for resources with deletion protection
- Check for dependencies preventing deletion
- Run `terraform destroy` manually to see detailed errors

**Warning: Resources still exist after teardown**
- Some resources may take time to fully delete
- Check AWS console to verify deletion
- Re-run teardown script if needed

## provision.sh

Provisions AWS infrastructure and restores database from the latest snapshot.

### What it does:

1. Finds the latest database snapshot
2. Runs `terraform init` to initialize backend
3. Runs `terraform plan` with snapshot restore
4. Runs `terraform apply` to create infrastructure
5. Waits for ECS services to stabilize
6. Runs health checks on API endpoints
7. Displays provision summary and API URLs

### Features:

- ✅ Automatic snapshot discovery and restore
- ✅ Fresh database creation if no snapshot exists
- ✅ ECS service stability checks
- ✅ API health checks
- ✅ Provision time tracking
- ✅ Cost estimates
- ✅ Comprehensive output summary

### Prerequisites:

- Terraform installed (v1.10+)
- AWS CLI installed
- AWS credentials configured for profile `festival-playlist`
- Backend initialized (S3 bucket exists)

### Usage:

```bash
# Run from terraform directory
cd terraform
./scripts/provision.sh

# Or run from project root
./terraform/scripts/provision.sh

# With custom environment
ENVIRONMENT=staging ./scripts/provision.sh
```

### Environment Variables:

- `PROJECT_NAME`: Project name (default: `festival-playlist`)
- `ENVIRONMENT`: Environment name (default: `dev`)
- `AWS_PROFILE`: AWS profile to use (default: `festival-playlist`)
- `AWS_REGION`: AWS region (default: `eu-west-2`)
- `MAX_HEALTH_CHECK_WAIT`: Max wait for health checks in seconds (default: `600`)

### What Gets Created:

- ✅ VPC with public/private subnets
- ✅ Security groups (zero-trust model)
- ✅ RDS Aurora Serverless v2 (restored from snapshot)
- ✅ ElastiCache Redis cluster
- ✅ ECS Fargate cluster with API and worker services
- ✅ Application Load Balancer
- ✅ CloudWatch log groups and alarms
- ✅ VPC endpoints for AWS services

### Snapshot Restore:

If a snapshot exists:
- Database restored from latest snapshot
- Data preserved from previous teardown
- Restore time: ~5-10 minutes

If no snapshot exists:
- Fresh database created
- Empty schema (migrations needed)
- Creation time: ~5-10 minutes

### Time:

- Typical provision time: 12-18 minutes
- Terraform apply: 10-15 minutes
- ECS service stabilization: 2-5 minutes
- Health checks: 1-3 minutes

### Health Checks:

The script performs the following checks:
1. ECS services reach stable state
2. ALB target groups show healthy targets
3. API `/health` endpoint responds successfully

### Output:

After successful provision, you'll see:
- ALB DNS name
- API URL
- Database endpoint
- Redis endpoint
- Health check URL
- Cost estimates

### Troubleshooting:

**Error: Terraform init failed**
- Check S3 backend bucket exists
- Run `./scripts/init-backend.sh` first
- Check AWS credentials

**Error: Terraform apply failed**
- Check AWS service quotas
- Check for conflicting resources
- Review Terraform error messages

**Warning: Health check failed**
- Service may still be starting
- Check ECS task logs: `aws logs tail /ecs/festival-api --follow`
- Verify security groups allow ALB → ECS traffic

**Error: No snapshot found**
- This is normal for first provision
- Database will be created fresh
- Run migrations after provision

## cost-report.sh

Generates detailed cost reports from AWS Cost Explorer.

### What it does:

1. Queries AWS Cost Explorer for environment costs
2. Displays cost by service (RDS, ECS, ALB, etc.)
3. Shows daily cost breakdown
4. Calculates monthly projection
5. Compares to budget and shows alerts
6. Provides cost optimization tips

### Features:

- ✅ Cost by service breakdown
- ✅ Daily cost trends (last 7 days)
- ✅ Monthly projection based on current usage
- ✅ Budget comparison and alerts
- ✅ Cost optimization recommendations
- ✅ Formatted output with colors

### Prerequisites:

- AWS CLI installed
- AWS credentials configured for profile `festival-playlist`
- Cost Explorer enabled in AWS account
- `jq` installed (optional, for better formatting)

### Usage:

```bash
# Run from terraform directory
cd terraform
./scripts/cost-report.sh

# Or run from project root
./terraform/scripts/cost-report.sh

# With custom environment
ENVIRONMENT=staging ./scripts/cost-report.sh

# With custom date range
DAYS_BACK=60 ./scripts/cost-report.sh
```

### Environment Variables:

- `PROJECT_NAME`: Project name (default: `festival-playlist`)
- `ENVIRONMENT`: Environment name (default: `dev`)
- `AWS_PROFILE`: AWS profile to use (default: `festival-playlist`)
- `AWS_REGION`: AWS region (default: `us-east-1` - Cost Explorer only)
- `DAYS_BACK`: Days of history to query (default: `30`)

### Output Sections:

**1. Cost Summary**
- Month-to-date total
- Last 7 days total
- Last 30 days total

**2. Cost by Service**
- Breakdown by AWS service
- Sorted by cost (highest first)
- Only shows services with cost > $0.01

**3. Daily Cost Breakdown**
- Last 7 days of daily costs
- Helps identify cost trends
- Shows cost spikes

**4. Monthly Projection**
- Projected monthly cost based on current usage
- Daily average calculation
- Budget comparison
- Overage/remaining budget

**5. Budget Alerts Status**
- Shows configured budget limits
- Alert thresholds
- Current status

**6. Cost Optimization Tips**
- Daily teardown savings
- Fargate Spot usage
- Aurora auto-pause
- S3 Intelligent-Tiering
- Log retention optimization

### Cost Targets:

**With Daily Teardown (8hrs/day, 5 days/week):**
- Active time: $8-10/month
- Torn down: $2-5/month
- **Total: $10-15/month**

**Running 24/7:**
- Aurora Serverless v2: $15-25
- ECS Fargate: $10-25
- ALB: $16
- ElastiCache: $3
- Other: $5-10
- **Total: $49-79/month**

### Troubleshooting:

**Error: Cost Explorer not enabled**
- Enable Cost Explorer in AWS Console
- Go to: Billing → Cost Explorer → Enable
- Wait 24 hours for data to populate

**Warning: No cost data available**
- Cost data may take 24-48 hours to appear
- Check that resources are tagged with Environment tag
- Verify Cost Explorer is enabled

**Error: jq not installed**
- Script will work without jq (less formatted)
- Install jq for better output:
  - macOS: `brew install jq`
  - Linux: `apt-get install jq` or `yum install jq`

**Error: Access denied**
- Ensure IAM user has `ce:GetCostAndUsage` permission
- Add Cost Explorer read permissions to IAM policy

### Cost Explorer Permissions:

Required IAM permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast",
        "budgets:ViewBudget"
      ],
      "Resource": "*"
    }
  ]
}
```

## test-workflow.sh

Comprehensive automated test suite for validating the teardown and provision workflow (Task 17.4).

### What it does:

1. Verifies scripts exist and are executable
2. Runs provision script and measures time
3. Verifies all services are healthy
4. Runs teardown script and measures time
5. Verifies snapshot creation
6. Verifies infrastructure destruction
7. Runs provision again (restore from snapshot)
8. Verifies infrastructure restoration

### Features:

- ✅ Automated end-to-end testing
- ✅ Performance validation (< 15 min provision, < 10 min teardown)
- ✅ Infrastructure health checks
- ✅ Snapshot creation and restoration validation
- ✅ Detailed test results with pass/fail status
- ✅ Color-coded output
- ✅ Dry-run mode for prerequisite checking

### Prerequisites:

- Terraform installed (v1.10+)
- AWS CLI installed
- AWS credentials configured for profile `festival-playlist`
- `jq` installed (optional, for better output)
- Backend initialized (S3 bucket exists)

### Usage:

```bash
# Run full test suite (30-45 minutes)
cd terraform
./scripts/test-workflow.sh

# Run dry-run test (< 1 minute, no cost)
./scripts/test-workflow.sh --dry-run

# Or run from project root
./terraform/scripts/test-workflow.sh
```

### Environment Variables:

- `PROJECT_NAME`: Project name (default: `festival-playlist`)
- `ENVIRONMENT`: Environment name (default: `dev`)
- `AWS_PROFILE`: AWS profile to use (default: `festival-playlist`)
- `AWS_REGION`: AWS region (default: `eu-west-2`)
- `MAX_PROVISION_TIME`: Max provision time in seconds (default: `900` = 15 min)
- `MAX_TEARDOWN_TIME`: Max teardown time in seconds (default: `600` = 10 min)

### Test Coverage:

**Test 1: Scripts Exist**
- Verifies provision.sh exists and is executable
- Verifies teardown.sh exists and is executable

**Test 2: Provision Infrastructure**
- Runs provision script
- Measures provision time
- Validates time < 15 minutes

**Test 3: Services Healthy**
- Verifies Terraform state exists
- Checks VPC created
- Checks subnets created (2+ public, 2+ private)
- Checks security groups created
- Checks database, cache, compute (when modules enabled)

**Test 4: Teardown Infrastructure**
- Runs teardown script
- Measures teardown time
- Validates time < 10 minutes

**Test 5: Snapshot Created**
- Verifies database snapshot created
- Checks snapshot status is "available"
- Skipped if database module not enabled

**Test 6: Infrastructure Destroyed**
- Verifies VPC destroyed (or persistent)
- Verifies ECS clusters destroyed
- Verifies RDS clusters destroyed
- Verifies ElastiCache destroyed
- Verifies ALBs destroyed

**Test 7: Provision Restore**
- Runs provision script again
- Restores from snapshot
- Measures provision time
- Validates time < 15 minutes

**Test 8: Infrastructure Restored**
- Verifies Terraform state exists
- Checks VPC restored
- Checks subnets restored
- Checks all services restored

### Output:

```
[TEST] Test 1: Verify scripts exist and are executable
[PASS] provision.sh exists: Script found and executable
[PASS] teardown.sh exists: Script found and executable

[TEST] Test 2: Run provision script and verify infrastructure created
[INFO] Running provision script...
[INFO] Provision completed in 12m 34s
[PASS] provision time: Completed in 12m 34s (< 15m 0s)

[TEST] Test 3: Verify all services healthy and accessible
[PASS] terraform state: Terraform state exists
[PASS] VPC created: VPC ID: vpc-xxxxx
[PASS] public subnets: Found 2 public subnets
[PASS] private subnets: Found 2 private subnets
[PASS] security groups: Found 5 security groups

[TEST] Test 4: Run teardown script and verify infrastructure destroyed
[INFO] Running teardown script...
[INFO] Teardown completed in 8m 12s
[PASS] teardown time: Completed in 8m 12s (< 10m 0s)

[TEST] Test 5: Verify snapshot created successfully
[PASS] snapshot created: Skipped - no database module

[TEST] Test 6: Verify infrastructure destroyed
[PASS] VPC destroyed: VPC successfully destroyed
[PASS] ECS clusters destroyed: No ECS clusters found
[PASS] RDS clusters destroyed: No RDS clusters found
[PASS] ElastiCache destroyed: No ElastiCache clusters found
[PASS] ALBs destroyed: No load balancers found

[TEST] Test 7: Run provision script again and verify restore from snapshot
[INFO] Running provision script (restore from snapshot)...
[INFO] Provision (restore) completed in 11m 45s
[PASS] provision restore time: Completed in 11m 45s (< 15m 0s)

[TEST] Test 8: Verify infrastructure restored correctly
[PASS] terraform state restored: Terraform state exists
[PASS] VPC restored: VPC ID: vpc-xxxxx
[PASS] subnets restored: Public: 2, Private: 2

========================================
Test Results Summary
========================================

✓ provision.sh exists - Script found and executable
✓ teardown.sh exists - Script found and executable
✓ provision time - Completed in 12m 34s (< 15m 0s)
✓ terraform state - Terraform state exists
✓ VPC created - VPC ID: vpc-xxxxx
✓ public subnets - Found 2 public subnets
✓ private subnets - Found 2 private subnets
✓ security groups - Found 5 security groups
✓ teardown time - Completed in 8m 12s (< 10m 0s)
✓ snapshot created - Skipped - no database module
✓ VPC destroyed - VPC successfully destroyed
✓ ECS clusters destroyed - No ECS clusters found
✓ RDS clusters destroyed - No RDS clusters found
✓ ElastiCache destroyed - No ElastiCache clusters found
✓ ALBs destroyed - No load balancers found
✓ provision restore time - Completed in 11m 45s (< 15m 0s)
✓ terraform state restored - Terraform state exists
✓ VPC restored - VPC ID: vpc-xxxxx
✓ subnets restored - Public: 2, Private: 2

Tests Passed: 18
Tests Failed: 0
Total Time: 32m 31s

[SUCCESS] All tests passed!
========================================
```

### Performance Requirements:

| Requirement | Target | Validation |
|-------------|--------|------------|
| Provision time (initial) | < 15 minutes | ✅ Measured in test |
| Teardown time | < 10 minutes | ✅ Measured in test |
| Provision time (restore) | < 15 minutes | ✅ Measured in test |

### Cost:

- **Dry-run test**: $0 (no infrastructure created)
- **Full test (current modules)**: $1-5 (VPC, subnets for ~30-45 min)
- **Full test (all modules)**: $5-10 (full infrastructure for ~45-60 min)

### Time:

- **Dry-run test**: < 1 minute
- **Full test (current modules)**: 30-45 minutes
- **Full test (all modules)**: 45-60 minutes

### Troubleshooting:

**Error: AWS credentials not configured**
- Run: `aws configure --profile festival-playlist`
- Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

**Error: Terraform not initialized**
- Run: `cd terraform && terraform init`
- Or run: `./scripts/init-backend.sh`

**Test fails: Provision time exceeds 15 minutes**
- Check AWS API throttling
- Verify network connectivity
- Review CloudWatch logs for errors
- Consider increasing MAX_PROVISION_TIME for initial testing

**Test fails: Teardown time exceeds 10 minutes**
- Check for resources with deletion protection
- Verify no manual resources blocking deletion
- Review Terraform destroy logs

**Test fails: Snapshot not created**
- This is expected if database module not enabled
- Uncomment database module in main.tf
- Re-run test suite

### Documentation:

For detailed documentation, see:
- `TEST_WORKFLOW.md` - Complete testing guide
- `TASK_17.4_SUMMARY.md` - Implementation summary

### Next Steps:

After tests pass:
1. Enable additional modules in `main.tf`
2. Re-run test suite with full infrastructure
3. Proceed to Week 3 tasks (Application Migration)

**Error: Access denied**
- Ensure IAM user has `ce:GetCostAndUsage` permission
- Add Cost Explorer read permissions to IAM policy

### Cost Explorer Permissions:

Required IAM permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast",
        "budgets:ViewBudget"
      ],
      "Resource": "*"
    }
  ]
}
```

## Daily Teardown/Provision Workflow

For maximum cost savings, use this daily workflow:

### End of Day (6 PM):

```bash
cd terraform
./scripts/teardown.sh
```

This will:
1. Create database snapshot (~5-10 min)
2. Destroy infrastructure (~3-5 min)
3. Reduce costs to ~$2-5/month

### Start of Day (9 AM):

```bash
cd terraform
./scripts/provision.sh
```

This will:
1. Restore from latest snapshot (~5-10 min)
2. Provision infrastructure (~10-15 min)
3. Run health checks (~1-3 min)

### Automation:

You can automate this with GitHub Actions:
- `.github/workflows/scheduled-teardown.yml` (6 PM weekdays)
- `.github/workflows/scheduled-provision.yml` (9 AM weekdays)

See Week 4 tasks for CI/CD automation setup.

## Cost Savings Summary

| Scenario | Monthly Cost | Savings |
|----------|-------------|---------|
| Running 24/7 | $49-79 | - |
| Daily teardown (8hrs/day, 5 days/week) | $10-15 | ~$39-64 (80%) |
| Weekend teardown only | $30-40 | ~$19-39 (40%) |

**Recommendation**: Use daily teardown for dev environment to maximize savings.

## Support

For issues or questions:
1. Check the troubleshooting sections above
2. Review Terraform error messages
3. Check AWS CloudWatch logs
4. Consult the main project README
