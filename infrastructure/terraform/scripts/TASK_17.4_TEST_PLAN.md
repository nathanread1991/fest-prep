# Task 17.4 Test Plan - Teardown and Provision Workflow

## Test Objective

Validate that the teardown and provision workflow meets the requirements specified in task 17.4:
- Run provision script and verify infrastructure created
- Verify all services healthy and accessible
- Run teardown script and verify infrastructure destroyed
- Verify snapshot created successfully (when database module enabled)
- Run provision script again and verify restore from snapshot
- Verify provision time < 15 minutes
- Verify teardown time < 10 minutes

## Current Infrastructure Status

### Modules Enabled
- ✅ **Billing Module**: AWS Budgets, Cost Anomaly Detection, SNS alerts
- ✅ **Networking Module**: VPC, subnets, security groups, VPC endpoints

### Modules Disabled (Commented Out)
- ❌ Database Module (Aurora Serverless v2)
- ❌ Cache Module (ElastiCache Redis)
- ❌ Storage Module (S3, ECR)
- ❌ Compute Module (ECS Fargate, ALB)
- ❌ CDN Module (CloudFront)
- ❌ Monitoring Module (CloudWatch, X-Ray)
- ❌ Security Module (Secrets Manager, ACM, WAF)

## Prerequisites Check

✅ **AWS CLI**: Installed and configured
✅ **Terraform**: Version >= 1.10 installed
✅ **AWS Credentials**: Configured for profile `festival-playlist`
✅ **Terraform Backend**: S3 bucket exists with state
✅ **Terraform Validation**: Configuration is valid

## Test Approach

Given that only billing and networking modules are currently enabled, the test will validate:

### Phase 1: Initial Provision
1. Run `provision.sh` script
2. Measure provision time
3. Verify Terraform state created
4. Verify VPC created
5. Verify subnets created (2 public, 2 private)
6. Verify security groups created
7. Verify VPC endpoints created

### Phase 2: Teardown
1. Run `teardown.sh` script
2. Measure teardown time
3. Verify infrastructure destroyed
4. Verify persistent resources remain (S3 backend)
5. Note: Snapshot creation will be skipped (no database)

### Phase 3: Restore Provision
1. Run `provision.sh` script again
2. Measure provision time
3. Verify infrastructure restored
4. Verify all resources match initial provision

## Expected Results

### Performance Targets
- **Initial Provision**: < 15 minutes (expected: 5-10 minutes with limited modules)
- **Teardown**: < 10 minutes (expected: 3-5 minutes with limited modules)
- **Restore Provision**: < 15 minutes (expected: 5-10 minutes with limited modules)

### Cost Estimate
- **Test Duration**: 30-45 minutes total
- **Resources**: VPC, subnets, security groups (minimal cost)
- **Estimated Cost**: $1-5 for the complete test

### Success Criteria
- ✅ All scripts execute without errors
- ✅ Provision time < 15 minutes
- ✅ Teardown time < 10 minutes
- ✅ Infrastructure created correctly
- ✅ Infrastructure destroyed correctly
- ✅ Infrastructure restored correctly

## Test Execution Options

### Option 1: Automated Test Suite (Recommended)
```bash
cd infrastructure/terraform/scripts
./test-workflow.sh
```

**Pros:**
- Comprehensive automated testing
- Measures all performance metrics
- Validates all requirements
- Generates detailed test report

**Cons:**
- Takes 30-45 minutes
- Incurs AWS costs ($1-5)
- Requires user confirmation

### Option 2: Manual Testing
```bash
# Step 1: Provision
cd infrastructure/terraform/scripts
time ./provision.sh

# Step 2: Verify (check AWS console or terraform state)
cd ../
terraform state list

# Step 3: Teardown
cd scripts
time ./teardown.sh

# Step 4: Verify destruction
cd ../
terraform state list

# Step 5: Provision again
cd scripts
time ./provision.sh
```

**Pros:**
- More control over each step
- Can pause between steps
- Can inspect infrastructure manually

**Cons:**
- More time-consuming
- Manual verification required
- No automated test report

### Option 3: Dry Run Only
```bash
cd infrastructure/terraform/scripts
./test-workflow.sh --dry-run
```

**Pros:**
- No AWS costs
- Quick validation
- Checks prerequisites only

**Cons:**
- Doesn't validate actual workflow
- Doesn't test performance
- Task 17.4 not fully completed

## Limitations with Current Infrastructure

Since only billing and networking modules are enabled:

1. **No Database Snapshots**: Snapshot creation/restore tests will be skipped
2. **No Service Health Checks**: No ECS services to verify
3. **No ALB Health Endpoints**: No load balancer to test
4. **Limited Infrastructure**: Only VPC and networking resources

These limitations are expected and documented. The test will validate the core workflow with the available infrastructure.

## Next Steps After Testing

1. **Mark task 17.4 as complete** if tests pass
2. **Enable additional modules** in `main.tf`:
   - Database module (for snapshot testing)
   - Cache module
   - Storage module
   - Compute module (for service health checks)
3. **Re-run test suite** with full infrastructure
4. **Proceed to Week 3 tasks** (Application Migration)

## Risk Assessment

### Low Risk
- ✅ Billing module already provisioned (no changes)
- ✅ Networking resources are simple (VPC, subnets)
- ✅ Terraform configuration validated
- ✅ Backend state exists and accessible

### Medium Risk
- ⚠️ First time running provision/teardown workflow
- ⚠️ Performance targets may not be met initially
- ⚠️ AWS costs will be incurred

### Mitigation
- Start with dry-run to verify prerequisites
- Monitor AWS console during provision
- Check CloudWatch logs for errors
- Verify teardown completes successfully
- Monitor costs in AWS Cost Explorer

## Recommendation

**Proceed with automated test suite** (`./test-workflow.sh`) because:
1. Comprehensive validation of all requirements
2. Automated performance measurement
3. Detailed test report for documentation
4. Low cost ($1-5) for high confidence
5. Validates core workflow before enabling more modules

The test will take 30-45 minutes but provides complete validation of task 17.4 requirements.
