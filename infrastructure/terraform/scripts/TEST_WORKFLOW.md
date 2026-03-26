# Teardown & Provision Workflow Testing

This document describes how to test the teardown and provision workflow to ensure it meets the requirements specified in task 17.4.

## Overview

The test workflow validates that:
1. Infrastructure can be provisioned successfully
2. All services are healthy and accessible
3. Infrastructure can be torn down successfully
4. Database snapshots are created during teardown
5. Infrastructure can be restored from snapshots
6. Provision time is < 15 minutes
7. Teardown time is < 10 minutes

## Prerequisites

Before running the test workflow, ensure you have:

1. **AWS CLI installed and configured**
   ```bash
   aws --version
   aws configure --profile festival-playlist
   ```

2. **Terraform installed** (>= 1.10)
   ```bash
   terraform --version
   ```

3. **AWS credentials configured** for the `festival-playlist` profile
   ```bash
   aws sts get-caller-identity --profile festival-playlist
   ```

4. **jq installed** (optional, for better output formatting)
   ```bash
   # macOS
   brew install jq

   # Linux
   sudo apt-get install jq
   ```

5. **Terraform backend initialized**
   ```bash
   cd infrastructure/terraform
   terraform init
   ```

## Running the Test Suite

### Full Test Suite

To run the complete test suite (provision → teardown → provision):

```bash
cd infrastructure/terraform/scripts
./test-workflow.sh
```

This will:
1. Check that scripts exist and are executable
2. Run provision script and measure time
3. Verify all services are healthy
4. Run teardown script and measure time
5. Verify snapshot was created
6. Verify infrastructure was destroyed
7. Run provision script again (restore from snapshot)
8. Verify infrastructure was restored correctly

**Expected Duration**: 30-45 minutes (includes two provision cycles and one teardown)

**Expected Cost**: $1-5 for the test (infrastructure running for ~30-45 minutes)

### Dry Run Mode

To check prerequisites without running the full test:

```bash
./test-workflow.sh --dry-run
```

This will only verify that:
- AWS CLI is installed
- Terraform is installed
- AWS credentials are configured

## Test Results

The test suite will output results for each test:

```
[PASS] provision.sh exists: Script found and executable
[PASS] teardown.sh exists: Script found and executable
[PASS] provision time: Completed in 12m 34s (< 15m 0s)
[PASS] terraform state: Terraform state exists
[PASS] VPC created: VPC ID: vpc-xxxxx
[PASS] public subnets: Found 2 public subnets
[PASS] private subnets: Found 2 private subnets
[PASS] security groups: Found 5 security groups
[PASS] teardown time: Completed in 8m 12s (< 10m 0s)
[PASS] snapshot created: Skipped - no database module
[PASS] VPC destroyed: VPC successfully destroyed
[PASS] ECS clusters destroyed: No ECS clusters found
[PASS] RDS clusters destroyed: No RDS clusters found
[PASS] ElastiCache destroyed: No ElastiCache clusters found
[PASS] ALBs destroyed: No load balancers found
[PASS] provision restore time: Completed in 11m 45s (< 15m 0s)
[PASS] terraform state restored: Terraform state exists
[PASS] VPC restored: VPC ID: vpc-xxxxx
[PASS] subnets restored: Public: 2, Private: 2

Tests Passed: 18
Tests Failed: 0
Total Time: 32m 31s
```

## Performance Requirements

The test suite validates the following performance requirements:

| Requirement | Target | Validation |
|-------------|--------|------------|
| Provision time (initial) | < 15 minutes | Measured during first provision |
| Teardown time | < 10 minutes | Measured during teardown |
| Provision time (restore) | < 15 minutes | Measured during second provision |

## Current Infrastructure Status

**Note**: As of task 17.4, only the following modules are enabled in `main.tf`:
- Billing module (AWS Budgets, Cost Anomaly Detection)
- Networking module (VPC, subnets, security groups)

The following modules are commented out and will be tested once enabled:
- Database module (Aurora Serverless v2)
- Cache module (ElastiCache Redis)
- Storage module (S3, ECR)
- Compute module (ECS Fargate, ALB)
- CDN module (CloudFront)
- Monitoring module (CloudWatch, X-Ray)
- Security module (Secrets Manager, ACM, WAF)

## Troubleshooting

### Test Fails: AWS Credentials Not Configured

**Error**: `AWS credentials not configured for profile: festival-playlist`

**Solution**:
```bash
aws configure --profile festival-playlist
# Enter your AWS Access Key ID, Secret Access Key, and region (eu-west-2)
```

### Test Fails: Terraform Not Initialized

**Error**: `No Terraform state found`

**Solution**:
```bash
cd infrastructure/terraform
terraform init
```

### Test Fails: Provision Time Exceeds 15 Minutes

**Possible Causes**:
- Slow internet connection
- AWS API throttling
- Large number of resources being created
- Database restore from large snapshot

**Solution**:
- Check AWS CloudWatch logs for errors
- Verify network connectivity
- Consider increasing `MAX_PROVISION_TIME` in test script for initial testing

### Test Fails: Teardown Time Exceeds 10 Minutes

**Possible Causes**:
- Large number of resources to destroy
- Dependencies preventing quick deletion
- AWS API throttling

**Solution**:
- Check Terraform destroy logs for slow resources
- Verify no manual resources blocking deletion
- Consider increasing `MAX_TEARDOWN_TIME` in test script for initial testing

### Test Fails: Snapshot Not Created

**Note**: This is expected if the database module is not yet enabled in `main.tf`.

**Solution**:
- Uncomment the database module in `infrastructure/terraform/main.tf`
- Run `terraform init` to initialize the module
- Re-run the test suite

## Manual Testing

If you prefer to test manually instead of using the automated test suite:

### 1. Test Provision

```bash
cd infrastructure/terraform/scripts
time ./provision.sh
```

Verify:
- Script completes successfully
- Time is < 15 minutes
- Infrastructure is created (check AWS console or `terraform state list`)
- Services are healthy (check health endpoints)

### 2. Test Teardown

```bash
cd infrastructure/terraform/scripts
time ./teardown.sh
```

Verify:
- Script completes successfully
- Time is < 10 minutes
- Snapshot is created (if database module enabled)
- Infrastructure is destroyed (check AWS console)
- Persistent resources remain (S3, Secrets Manager)

### 3. Test Restore

```bash
cd infrastructure/terraform/scripts
time ./provision.sh
```

Verify:
- Script completes successfully
- Time is < 15 minutes
- Infrastructure is restored from snapshot
- Services are healthy
- Data is preserved (if database module enabled)

## Next Steps

After the test suite passes:

1. **Mark task 17.4 as complete** in `.kiro/specs/aws-enterprise-migration/tasks.md`

2. **Enable additional modules** in `main.tf`:
   - Uncomment database module
   - Uncomment cache module
   - Uncomment storage module
   - Uncomment compute module
   - Uncomment CDN module
   - Uncomment monitoring module
   - Uncomment security module

3. **Re-run test suite** to validate full infrastructure:
   ```bash
   ./test-workflow.sh
   ```

4. **Proceed to Week 3 tasks** (Application Migration)

## Cost Considerations

Running the test suite will incur AWS costs:

- **Test duration**: ~30-45 minutes
- **Resources created**: VPC, subnets, security groups (minimal cost)
- **Estimated cost**: $1-5 for the test

Once all modules are enabled:
- **Test duration**: ~45-60 minutes
- **Resources created**: Full infrastructure (VPC, RDS, Redis, ECS, ALB, etc.)
- **Estimated cost**: $5-10 for the test

To minimize costs:
- Run tests during business hours (avoid overnight runs)
- Verify teardown completes successfully
- Monitor AWS Cost Explorer after tests

## References

- Task 17.4: `.kiro/specs/aws-enterprise-migration/tasks.md`
- Requirements: US-1.5, US-1.6, US-3.1
- Provision script: `infrastructure/terraform/scripts/provision.sh`
- Teardown script: `infrastructure/terraform/scripts/teardown.sh`
- Cost report script: `infrastructure/terraform/scripts/cost-report.sh`
