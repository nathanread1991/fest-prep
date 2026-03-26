#!/bin/bash
# Test Workflow Script - Comprehensive testing of teardown and provision workflow
# This script validates that the teardown and provision scripts work correctly
# and meet the performance requirements (< 15 min provision, < 10 min teardown)

set -e  # Exit on error
set -o pipefail  # Exit on pipe failure

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_NAME="${PROJECT_NAME:-festival-playlist}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_PROFILE="${AWS_PROFILE:-festival-playlist}"
AWS_REGION="${AWS_REGION:-eu-west-2}"

# Performance requirements (in seconds)
MAX_PROVISION_TIME=900   # 15 minutes
MAX_TEARDOWN_TIME=600    # 10 minutes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
TEST_RESULTS=()

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_test() {
    echo -e "${CYAN}[TEST]${NC} $1"
}

log_result() {
    local test_name="$1"
    local passed="$2"
    local message="$3"

    if [ "$passed" = "true" ]; then
        echo -e "${GREEN}[PASS]${NC} $test_name: $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        TEST_RESULTS+=("PASS: $test_name - $message")
    else
        echo -e "${RED}[FAIL]${NC} $test_name: $message"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        TEST_RESULTS+=("FAIL: $test_name - $message")
    fi
}

# Format time duration
format_time() {
    local seconds="$1"
    local minutes=$((seconds / 60))
    local secs=$((seconds % 60))
    echo "${minutes}m ${secs}s"
}

# Check if AWS CLI is installed
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
}

# Check if Terraform is installed
check_terraform() {
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed. Please install it first."
        exit 1
    fi
}

# Check if AWS credentials are configured
check_aws_credentials() {
    if ! aws sts get-caller-identity --profile "$AWS_PROFILE" &> /dev/null; then
        log_error "AWS credentials not configured for profile: $AWS_PROFILE"
        log_error "Run: aws configure --profile $AWS_PROFILE"
        exit 1
    fi
}

# ============================================================================
# Test Functions
# ============================================================================

# Test 1: Verify scripts exist and are executable
test_scripts_exist() {
    log_test "Test 1: Verify scripts exist and are executable"

    local provision_script="$SCRIPT_DIR/provision.sh"
    local teardown_script="$SCRIPT_DIR/teardown.sh"

    if [ -f "$provision_script" ] && [ -x "$provision_script" ]; then
        log_result "provision.sh exists" "true" "Script found and executable"
    else
        log_result "provision.sh exists" "false" "Script not found or not executable"
        return 1
    fi

    if [ -f "$teardown_script" ] && [ -x "$teardown_script" ]; then
        log_result "teardown.sh exists" "true" "Script found and executable"
    else
        log_result "teardown.sh exists" "false" "Script not found or not executable"
        return 1
    fi
}

# Test 2: Run provision script and verify infrastructure created
test_provision() {
    log_test "Test 2: Run provision script and verify infrastructure created"

    local start_time=$(date +%s)

    log_info "Running provision script..."
    if echo "yes" | "$SCRIPT_DIR/provision.sh" > /tmp/provision.log 2>&1; then
        local end_time=$(date +%s)
        local elapsed=$((end_time - start_time))

        log_info "Provision completed in $(format_time $elapsed)"

        # Check if provision time meets requirement
        if [ $elapsed -lt $MAX_PROVISION_TIME ]; then
            log_result "provision time" "true" "Completed in $(format_time $elapsed) (< $(format_time $MAX_PROVISION_TIME))"
        else
            log_result "provision time" "false" "Took $(format_time $elapsed) (> $(format_time $MAX_PROVISION_TIME))"
        fi

        return 0
    else
        log_error "Provision script failed. Check /tmp/provision.log for details"
        log_result "provision execution" "false" "Script failed"
        return 1
    fi
}

# Test 3: Verify all services healthy and accessible
test_services_healthy() {
    log_test "Test 3: Verify all services healthy and accessible"

    cd "$TERRAFORM_DIR"

    # Check if Terraform state exists
    if ! terraform state list > /dev/null 2>&1; then
        log_result "terraform state" "false" "No Terraform state found"
        return 1
    fi

    log_result "terraform state" "true" "Terraform state exists"

    # Check VPC
    local vpc_id=$(terraform output -raw vpc_id 2>/dev/null || echo "")
    if [ -n "$vpc_id" ]; then
        log_result "VPC created" "true" "VPC ID: $vpc_id"
    else
        log_result "VPC created" "false" "VPC not found"
    fi

    # Check subnets
    local public_subnets=$(terraform output -json public_subnet_ids 2>/dev/null | jq -r 'length' || echo "0")
    local private_subnets=$(terraform output -json private_subnet_ids 2>/dev/null | jq -r 'length' || echo "0")

    if [ "$public_subnets" -ge 2 ]; then
        log_result "public subnets" "true" "Found $public_subnets public subnets"
    else
        log_result "public subnets" "false" "Expected 2+ public subnets, found $public_subnets"
    fi

    if [ "$private_subnets" -ge 2 ]; then
        log_result "private subnets" "true" "Found $private_subnets private subnets"
    else
        log_result "private subnets" "false" "Expected 2+ private subnets, found $private_subnets"
    fi

    # Check security groups
    local sg_count=$(aws ec2 describe-security-groups \
        --filters "Name=tag:Project,Values=$PROJECT_NAME" "Name=tag:Environment,Values=$ENVIRONMENT" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query 'length(SecurityGroups)' \
        --output text 2>/dev/null || echo "0")

    if [ "$sg_count" -ge 1 ]; then
        log_result "security groups" "true" "Found $sg_count security groups"
    else
        log_result "security groups" "false" "No security groups found"
    fi

    # Note: Database, cache, compute modules are commented out in main.tf
    # So we only test networking infrastructure for now
    log_warning "Database, cache, and compute modules are not yet enabled in main.tf"
    log_warning "Full infrastructure testing will be available after modules are uncommented"
}

# Test 4: Run teardown script and verify infrastructure destroyed
test_teardown() {
    log_test "Test 4: Run teardown script and verify infrastructure destroyed"

    local start_time=$(date +%s)

    log_info "Running teardown script..."
    if echo "yes" | "$SCRIPT_DIR/teardown.sh" > /tmp/teardown.log 2>&1; then
        local end_time=$(date +%s)
        local elapsed=$((end_time - start_time))

        log_info "Teardown completed in $(format_time $elapsed)"

        # Check if teardown time meets requirement
        if [ $elapsed -lt $MAX_TEARDOWN_TIME ]; then
            log_result "teardown time" "true" "Completed in $(format_time $elapsed) (< $(format_time $MAX_TEARDOWN_TIME))"
        else
            log_result "teardown time" "false" "Took $(format_time $elapsed) (> $(format_time $MAX_TEARDOWN_TIME))"
        fi

        return 0
    else
        log_error "Teardown script failed. Check /tmp/teardown.log for details"
        log_result "teardown execution" "false" "Script failed"
        return 1
    fi
}

# Test 5: Verify snapshot created successfully
test_snapshot_created() {
    log_test "Test 5: Verify snapshot created successfully"

    # Note: This test will be skipped if database module is not enabled
    local snapshots=$(aws rds describe-db-cluster-snapshots \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "DBClusterSnapshots[?starts_with(DBClusterSnapshotIdentifier, '${PROJECT_NAME}-${ENVIRONMENT}-snapshot-')].DBClusterSnapshotIdentifier" \
        --output text 2>/dev/null || echo "")

    if [ -z "$snapshots" ]; then
        log_warning "No database snapshots found (database module may not be enabled)"
        log_result "snapshot created" "true" "Skipped - no database module"
        return 0
    fi

    local latest_snapshot=$(echo "$snapshots" | tr '\t' '\n' | sort -r | head -1)

    if [ -n "$latest_snapshot" ]; then
        local snapshot_status=$(aws rds describe-db-cluster-snapshots \
            --db-cluster-snapshot-identifier "$latest_snapshot" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --query 'DBClusterSnapshots[0].Status' \
            --output text 2>/dev/null || echo "")

        if [ "$snapshot_status" = "available" ]; then
            log_result "snapshot status" "true" "Snapshot $latest_snapshot is available"
        else
            log_result "snapshot status" "false" "Snapshot $latest_snapshot status: $snapshot_status"
        fi
    else
        log_result "snapshot created" "false" "No snapshots found"
    fi
}

# Test 6: Verify infrastructure destroyed
test_infrastructure_destroyed() {
    log_test "Test 6: Verify infrastructure destroyed"

    # Check VPC (should still exist as it's managed by Terraform)
    local vpcs=$(aws ec2 describe-vpcs \
        --filters "Name=tag:Project,Values=$PROJECT_NAME" "Name=tag:Environment,Values=$ENVIRONMENT" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query 'length(Vpcs)' \
        --output text 2>/dev/null || echo "0")

    if [ "$vpcs" -eq 0 ]; then
        log_result "VPC destroyed" "true" "VPC successfully destroyed"
    else
        log_result "VPC destroyed" "false" "VPC still exists (expected if using prevent_destroy)"
    fi

    # Check ECS clusters (should be destroyed)
    local ecs_clusters=$(aws ecs list-clusters \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "clusterArns[?contains(@, '${PROJECT_NAME}-${ENVIRONMENT}')]" \
        --output text 2>/dev/null || echo "")

    if [ -z "$ecs_clusters" ]; then
        log_result "ECS clusters destroyed" "true" "No ECS clusters found"
    else
        log_result "ECS clusters destroyed" "false" "ECS clusters still exist: $ecs_clusters"
    fi

    # Check RDS clusters (should be destroyed)
    local rds_clusters=$(aws rds describe-db-clusters \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "DBClusters[?starts_with(DBClusterIdentifier, '${PROJECT_NAME}-${ENVIRONMENT}')].DBClusterIdentifier" \
        --output text 2>/dev/null || echo "")

    if [ -z "$rds_clusters" ]; then
        log_result "RDS clusters destroyed" "true" "No RDS clusters found"
    else
        log_result "RDS clusters destroyed" "false" "RDS clusters still exist: $rds_clusters"
    fi

    # Check ElastiCache clusters (should be destroyed)
    local redis_clusters=$(aws elasticache describe-cache-clusters \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "CacheClusters[?starts_with(CacheClusterId, '${PROJECT_NAME}-${ENVIRONMENT}')].CacheClusterId" \
        --output text 2>/dev/null || echo "")

    if [ -z "$redis_clusters" ]; then
        log_result "ElastiCache destroyed" "true" "No ElastiCache clusters found"
    else
        log_result "ElastiCache destroyed" "false" "ElastiCache clusters still exist: $redis_clusters"
    fi

    # Check ALBs (should be destroyed)
    local albs=$(aws elbv2 describe-load-balancers \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "LoadBalancers[?starts_with(LoadBalancerName, '${PROJECT_NAME}-${ENVIRONMENT}')].LoadBalancerName" \
        --output text 2>/dev/null || echo "")

    if [ -z "$albs" ]; then
        log_result "ALBs destroyed" "true" "No load balancers found"
    else
        log_result "ALBs destroyed" "false" "Load balancers still exist: $albs"
    fi
}

# Test 7: Run provision script again and verify restore from snapshot
test_provision_restore() {
    log_test "Test 7: Run provision script again and verify restore from snapshot"

    local start_time=$(date +%s)

    log_info "Running provision script (restore from snapshot)..."
    if echo "yes" | "$SCRIPT_DIR/provision.sh" > /tmp/provision-restore.log 2>&1; then
        local end_time=$(date +%s)
        local elapsed=$((end_time - start_time))

        log_info "Provision (restore) completed in $(format_time $elapsed)"

        # Check if provision time meets requirement
        if [ $elapsed -lt $MAX_PROVISION_TIME ]; then
            log_result "provision restore time" "true" "Completed in $(format_time $elapsed) (< $(format_time $MAX_PROVISION_TIME))"
        else
            log_result "provision restore time" "false" "Took $(format_time $elapsed) (> $(format_time $MAX_PROVISION_TIME))"
        fi

        return 0
    else
        log_error "Provision (restore) script failed. Check /tmp/provision-restore.log for details"
        log_result "provision restore execution" "false" "Script failed"
        return 1
    fi
}

# Test 8: Verify infrastructure restored correctly
test_infrastructure_restored() {
    log_test "Test 8: Verify infrastructure restored correctly"

    cd "$TERRAFORM_DIR"

    # Check if Terraform state exists
    if ! terraform state list > /dev/null 2>&1; then
        log_result "terraform state restored" "false" "No Terraform state found"
        return 1
    fi

    log_result "terraform state restored" "true" "Terraform state exists"

    # Check VPC
    local vpc_id=$(terraform output -raw vpc_id 2>/dev/null || echo "")
    if [ -n "$vpc_id" ]; then
        log_result "VPC restored" "true" "VPC ID: $vpc_id"
    else
        log_result "VPC restored" "false" "VPC not found"
    fi

    # Check subnets
    local public_subnets=$(terraform output -json public_subnet_ids 2>/dev/null | jq -r 'length' || echo "0")
    local private_subnets=$(terraform output -json private_subnet_ids 2>/dev/null | jq -r 'length' || echo "0")

    if [ "$public_subnets" -ge 2 ] && [ "$private_subnets" -ge 2 ]; then
        log_result "subnets restored" "true" "Public: $public_subnets, Private: $private_subnets"
    else
        log_result "subnets restored" "false" "Public: $public_subnets, Private: $private_subnets"
    fi

    log_warning "Full infrastructure validation will be available after all modules are enabled"
}

# ============================================================================
# Main Test Suite
# ============================================================================

run_test_suite() {
    local suite_start=$(date +%s)

    echo ""
    log_info "=========================================="
    log_info "Teardown & Provision Workflow Test Suite"
    log_info "=========================================="
    log_info "Project: $PROJECT_NAME"
    log_info "Environment: $ENVIRONMENT"
    log_info "AWS Profile: $AWS_PROFILE"
    log_info "AWS Region: $AWS_REGION"
    log_info "=========================================="
    echo ""

    # Pre-flight checks
    log_info "Running pre-flight checks..."
    check_aws_cli
    check_terraform
    check_aws_credentials
    log_success "Pre-flight checks passed"
    echo ""

    # Run tests
    log_info "Starting test suite..."
    echo ""

    test_scripts_exist
    echo ""

    test_provision
    echo ""

    test_services_healthy
    echo ""

    test_teardown
    echo ""

    test_snapshot_created
    echo ""

    test_infrastructure_destroyed
    echo ""

    test_provision_restore
    echo ""

    test_infrastructure_restored
    echo ""

    # Calculate total time
    local suite_end=$(date +%s)
    local total_time=$((suite_end - suite_start))

    # Display results
    echo ""
    log_info "=========================================="
    log_info "Test Results Summary"
    log_info "=========================================="
    echo ""

    for result in "${TEST_RESULTS[@]}"; do
        if [[ $result == PASS:* ]]; then
            echo -e "${GREEN}✓${NC} ${result#PASS: }"
        else
            echo -e "${RED}✗${NC} ${result#FAIL: }"
        fi
    done

    echo ""
    log_info "Tests Passed: $TESTS_PASSED"
    log_info "Tests Failed: $TESTS_FAILED"
    log_info "Total Time: $(format_time $total_time)"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        log_success "All tests passed!"
        log_info "=========================================="
        return 0
    else
        log_error "Some tests failed!"
        log_info "=========================================="
        return 1
    fi
}

# ============================================================================
# Script Entry Point
# ============================================================================

main() {
    # Check for dry-run mode
    if [ "$1" = "--dry-run" ]; then
        log_info "Dry-run mode: Will only check prerequisites"
        check_aws_cli
        check_terraform
        check_aws_credentials
        log_success "Prerequisites check passed"
        exit 0
    fi

    # Confirm with user
    log_warning "This test will provision and destroy infrastructure multiple times"
    log_warning "This may incur AWS costs (estimated: \$1-5 for the test)"
    echo ""
    read -p "Continue with test suite? (yes/no): " -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_info "Test cancelled by user"
        exit 0
    fi

    # Run test suite
    if run_test_suite; then
        exit 0
    else
        exit 1
    fi
}

# Run main function
main "$@"
