#!/bin/bash
# Provision Script - Restore AWS infrastructure from database snapshot
# This script provisions infrastructure and restores the database from
# the latest snapshot for fast environment restoration.

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
MAX_HEALTH_CHECK_WAIT="${MAX_HEALTH_CHECK_WAIT:-600}"  # 10 minutes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Find latest database snapshot
find_latest_snapshot() {
    log_info "Searching for latest database snapshot..."

    local snapshot_id=$(aws rds describe-db-cluster-snapshots \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "reverse(sort_by(DBClusterSnapshots[?starts_with(DBClusterSnapshotIdentifier, '${PROJECT_NAME}-${ENVIRONMENT}-snapshot-') && Status=='available'], &SnapshotCreateTime))[0].DBClusterSnapshotIdentifier" \
        --output text 2>/dev/null || echo "")

    if [ -z "$snapshot_id" ] || [ "$snapshot_id" = "None" ]; then
        log_warning "No snapshot found. Will create fresh database."
        echo ""
    else
        log_success "Found latest snapshot: $snapshot_id"
        local snapshot_time=$(aws rds describe-db-cluster-snapshots \
            --db-cluster-snapshot-identifier "$snapshot_id" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --query 'DBClusterSnapshots[0].SnapshotCreateTime' \
            --output text 2>/dev/null || echo "")
        log_info "Snapshot created: $snapshot_time"
        echo "$snapshot_id"
    fi
}

# Run Terraform init
terraform_init() {
    cd "$TERRAFORM_DIR"

    log_info "Initializing Terraform..."

    if terraform init -upgrade; then
        log_success "Terraform initialized successfully"
        return 0
    else
        log_error "Terraform init failed"
        return 1
    fi
}

# Run Terraform plan
terraform_plan() {
    local snapshot_id="$1"
    cd "$TERRAFORM_DIR"

    log_info "Running Terraform plan..."

    local plan_args=""
    if [ -n "$snapshot_id" ]; then
        plan_args="-var=\"restore_from_snapshot=true\""
        log_info "Will restore database from snapshot: $snapshot_id"
    else
        plan_args="-var=\"restore_from_snapshot=false\""
        log_info "Will create fresh database (no snapshot found)"
    fi

    if eval "terraform plan $plan_args -out=tfplan"; then
        log_success "Terraform plan completed successfully"
        return 0
    else
        log_error "Terraform plan failed"
        return 1
    fi
}

# Run Terraform apply
terraform_apply() {
    cd "$TERRAFORM_DIR"

    log_info "Applying Terraform configuration..."
    log_warning "This will provision AWS infrastructure"

    if terraform apply tfplan; then
        log_success "Terraform apply completed successfully"
        rm -f tfplan
        return 0
    else
        log_error "Terraform apply failed"
        rm -f tfplan
        return 1
    fi
}

# Wait for ECS services to be stable
wait_for_ecs_services() {
    log_info "Waiting for ECS services to stabilize..."

    # Get ECS cluster name
    local cluster_name=$(cd "$TERRAFORM_DIR" && terraform output -raw ecs_cluster_name 2>/dev/null || echo "")

    if [ -z "$cluster_name" ]; then
        log_warning "Could not get ECS cluster name. Skipping ECS health check."
        return 0
    fi

    # Get ECS service names
    local services=$(aws ecs list-services \
        --cluster "$cluster_name" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query 'serviceArns[*]' \
        --output text 2>/dev/null || echo "")

    if [ -z "$services" ]; then
        log_warning "No ECS services found. Skipping ECS health check."
        return 0
    fi

    log_info "Found ECS services in cluster: $cluster_name"

    # Wait for each service
    for service_arn in $services; do
        local service_name=$(basename "$service_arn")
        log_info "Waiting for service: $service_name"

        if aws ecs wait services-stable \
            --cluster "$cluster_name" \
            --services "$service_name" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" 2>/dev/null; then
            log_success "Service stable: $service_name"
        else
            log_warning "Service may not be stable: $service_name"
        fi
    done

    log_success "All ECS services checked"
}

# Run health checks
run_health_checks() {
    log_info "Running health checks..."

    # Get ALB DNS name
    local alb_dns=$(cd "$TERRAFORM_DIR" && terraform output -raw alb_dns_name 2>/dev/null || echo "")

    if [ -z "$alb_dns" ]; then
        log_warning "Could not get ALB DNS name. Skipping health check."
        return 0
    fi

    log_info "ALB DNS: $alb_dns"

    # Wait for ALB to be ready
    local max_attempts=30
    local attempt=0
    local health_url="http://${alb_dns}/health"

    log_info "Checking health endpoint: $health_url"

    while [ $attempt -lt $max_attempts ]; do
        if curl -sf "$health_url" > /dev/null 2>&1; then
            log_success "Health check passed!"
            return 0
        fi

        echo -n "."
        sleep 10
        attempt=$((attempt + 1))
    done

    echo ""
    log_warning "Health check did not pass within timeout. Service may still be starting."
    log_info "You can manually check: $health_url"
}

# Display provision summary
display_provision_summary() {
    cd "$TERRAFORM_DIR"

    log_info "=========================================="
    log_info "Provision Summary"
    log_info "=========================================="

    # Get outputs
    local alb_dns=$(terraform output -raw alb_dns_name 2>/dev/null || echo "N/A")
    local api_url=$(terraform output -raw api_url 2>/dev/null || echo "N/A")
    local db_endpoint=$(terraform output -raw db_endpoint 2>/dev/null || echo "N/A")
    local redis_endpoint=$(terraform output -raw redis_endpoint 2>/dev/null || echo "N/A")

    echo ""
    log_info "API Endpoints:"
    log_info "  ALB DNS: $alb_dns"
    log_info "  API URL: $api_url"
    log_info "  Health Check: http://${alb_dns}/health"
    echo ""
    log_info "Database:"
    log_info "  Endpoint: $db_endpoint"
    echo ""
    log_info "Cache:"
    log_info "  Endpoint: $redis_endpoint"
    echo ""
}

# Display cost estimate
display_cost_estimate() {
    log_info "Estimated monthly costs (if running 24/7):"
    log_info "  Aurora Serverless v2: \$15-25"
    log_info "  ECS Fargate API: \$8-20"
    log_info "  ECS Fargate Worker (Spot): \$2-5"
    log_info "  ALB: \$16"
    log_info "  ElastiCache Redis: \$3"
    log_info "  Other: \$5-10"
    log_info "  Total: \$49-79/month"
    echo ""
    log_info "With daily teardown (8hrs/day, 5 days/week):"
    log_info "  Active time: \$8-10/month"
    log_info "  Torn down: \$2-5/month"
    log_info "  Total: \$10-15/month"
}

# ============================================================================
# Main Script
# ============================================================================

main() {
    local start_time=$(date +%s)

    echo ""
    log_info "=========================================="
    log_info "Festival Playlist Generator - Provision"
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

    # Find latest snapshot
    local snapshot_id=$(find_latest_snapshot)
    echo ""

    # Terraform init
    if ! terraform_init; then
        log_error "Provision failed during Terraform init"
        exit 1
    fi
    echo ""

    # Terraform plan
    if ! terraform_plan "$snapshot_id"; then
        log_error "Provision failed during Terraform plan"
        exit 1
    fi
    echo ""

    # Confirm apply
    log_warning "About to provision infrastructure for environment: $ENVIRONMENT"
    if [ -n "$snapshot_id" ]; then
        log_info "Database will be restored from snapshot: $snapshot_id"
    else
        log_info "Fresh database will be created (no snapshot found)"
    fi
    echo ""
    read -p "Continue with provisioning? (yes/no): " -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_info "Provision cancelled by user"
        exit 0
    fi

    # Terraform apply
    if ! terraform_apply; then
        log_error "Provision failed during Terraform apply"
        exit 1
    fi
    echo ""

    # Wait for ECS services
    wait_for_ecs_services
    echo ""

    # Run health checks
    run_health_checks
    echo ""

    # Display summary
    display_provision_summary

    # Display cost estimate
    display_cost_estimate

    # Calculate elapsed time
    local end_time=$(date +%s)
    local elapsed=$((end_time - start_time))
    local minutes=$((elapsed / 60))
    local seconds=$((elapsed % 60))

    echo ""
    log_info "=========================================="
    log_success "Provision completed successfully!"
    log_info "Time elapsed: ${minutes}m ${seconds}s"
    log_info "=========================================="
    echo ""
    log_info "Next steps:"
    log_info "  1. Test the API: curl http://\$(terraform output -raw alb_dns_name)/health"
    log_info "  2. View logs: aws logs tail /ecs/festival-api --follow"
    log_info "  3. Monitor costs: ./scripts/cost-report.sh"
    log_info "  4. Teardown when done: ./scripts/teardown.sh"
    echo ""
}

# Run main function
main "$@"
