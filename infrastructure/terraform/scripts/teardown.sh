#!/bin/bash
# Teardown Script - Safely destroy AWS infrastructure with database snapshot
# This script creates a database snapshot before destroying infrastructure
# to enable fast restoration later.

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
SNAPSHOT_RETENTION_DAYS="${SNAPSHOT_RETENTION_DAYS:-7}"

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

# Get RDS cluster identifier from Terraform state
get_cluster_identifier() {
    cd "$TERRAFORM_DIR"
    terraform output -raw db_cluster_identifier 2>/dev/null || echo ""
}

# Create database snapshot
create_snapshot() {
    local cluster_id="$1"
    local snapshot_id="${PROJECT_NAME}-${ENVIRONMENT}-snapshot-$(date +%Y%m%d-%H%M%S)"

    log_info "Creating database snapshot: $snapshot_id"

    aws rds create-db-cluster-snapshot \
        --db-cluster-identifier "$cluster_id" \
        --db-cluster-snapshot-identifier "$snapshot_id" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --tags "Key=Project,Value=$PROJECT_NAME" \
               "Key=Environment,Value=$ENVIRONMENT" \
               "Key=ManagedBy,Value=terraform" \
               "Key=CreatedBy,Value=teardown-script" \
        > /dev/null

    log_success "Snapshot creation initiated: $snapshot_id"
    echo "$snapshot_id"
}

# Wait for snapshot to complete
wait_for_snapshot() {
    local snapshot_id="$1"
    local max_wait=1800  # 30 minutes
    local elapsed=0
    local interval=30

    log_info "Waiting for snapshot to complete (max ${max_wait}s)..."

    while [ $elapsed -lt $max_wait ]; do
        local status=$(aws rds describe-db-cluster-snapshots \
            --db-cluster-snapshot-identifier "$snapshot_id" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --query 'DBClusterSnapshots[0].Status' \
            --output text 2>/dev/null || echo "error")

        if [ "$status" = "available" ]; then
            log_success "Snapshot completed successfully"
            return 0
        elif [ "$status" = "error" ] || [ "$status" = "failed" ]; then
            log_error "Snapshot creation failed"
            return 1
        fi

        echo -n "."
        sleep $interval
        elapsed=$((elapsed + interval))
    done

    echo ""
    log_error "Snapshot creation timed out after ${max_wait}s"
    return 1
}

# Clean up old snapshots (keep last N days)
cleanup_old_snapshots() {
    local retention_days="$1"
    local cutoff_date=$(date -u -d "$retention_days days ago" +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-${retention_days}d +%Y-%m-%dT%H:%M:%S)

    log_info "Cleaning up snapshots older than $retention_days days..."

    local snapshots=$(aws rds describe-db-cluster-snapshots \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "DBClusterSnapshots[?starts_with(DBClusterSnapshotIdentifier, '${PROJECT_NAME}-${ENVIRONMENT}-snapshot-') && SnapshotCreateTime < '$cutoff_date'].DBClusterSnapshotIdentifier" \
        --output text 2>/dev/null || echo "")

    if [ -z "$snapshots" ]; then
        log_info "No old snapshots to clean up"
        return 0
    fi

    local count=0
    for snapshot in $snapshots; do
        log_info "Deleting old snapshot: $snapshot"
        aws rds delete-db-cluster-snapshot \
            --db-cluster-snapshot-identifier "$snapshot" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            > /dev/null 2>&1 || log_warning "Failed to delete snapshot: $snapshot"
        count=$((count + 1))
    done

    log_success "Cleaned up $count old snapshot(s)"
}

# Run Terraform destroy
terraform_destroy() {
    cd "$TERRAFORM_DIR"

    log_info "Running Terraform destroy..."
    log_warning "This will destroy all non-persistent resources"

    # Run terraform destroy with auto-approve
    if terraform destroy -auto-approve; then
        log_success "Terraform destroy completed successfully"
        return 0
    else
        log_error "Terraform destroy failed"
        return 1
    fi
}

# Verify destruction of compute resources
verify_destruction() {
    log_info "Verifying destruction of compute resources..."

    # Check ECS clusters
    local ecs_clusters=$(aws ecs list-clusters \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "clusterArns[?contains(@, '${PROJECT_NAME}-${ENVIRONMENT}')]" \
        --output text 2>/dev/null || echo "")

    if [ -n "$ecs_clusters" ]; then
        log_warning "ECS clusters still exist: $ecs_clusters"
    else
        log_success "ECS clusters destroyed"
    fi

    # Check RDS clusters
    local rds_clusters=$(aws rds describe-db-clusters \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "DBClusters[?starts_with(DBClusterIdentifier, '${PROJECT_NAME}-${ENVIRONMENT}')].DBClusterIdentifier" \
        --output text 2>/dev/null || echo "")

    if [ -n "$rds_clusters" ]; then
        log_warning "RDS clusters still exist: $rds_clusters"
    else
        log_success "RDS clusters destroyed"
    fi

    # Check ElastiCache clusters
    local redis_clusters=$(aws elasticache describe-cache-clusters \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "CacheClusters[?starts_with(CacheClusterId, '${PROJECT_NAME}-${ENVIRONMENT}')].CacheClusterId" \
        --output text 2>/dev/null || echo "")

    if [ -n "$redis_clusters" ]; then
        log_warning "ElastiCache clusters still exist: $redis_clusters"
    else
        log_success "ElastiCache clusters destroyed"
    fi

    # Check ALBs
    local albs=$(aws elbv2 describe-load-balancers \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "LoadBalancers[?starts_with(LoadBalancerName, '${PROJECT_NAME}-${ENVIRONMENT}')].LoadBalancerName" \
        --output text 2>/dev/null || echo "")

    if [ -n "$albs" ]; then
        log_warning "Load balancers still exist: $albs"
    else
        log_success "Load balancers destroyed"
    fi
}

# Display cost summary
display_cost_summary() {
    log_info "Fetching cost summary..."

    # Get costs for the last 7 days
    local start_date=$(date -u -d "7 days ago" +%Y-%m-%d 2>/dev/null || date -u -v-7d +%Y-%m-%d)
    local end_date=$(date -u +%Y-%m-%d)

    local cost=$(aws ce get-cost-and-usage \
        --time-period Start="$start_date",End="$end_date" \
        --granularity DAILY \
        --metrics "UnblendedCost" \
        --filter file://<(cat <<EOF
{
  "Tags": {
    "Key": "Environment",
    "Values": ["$ENVIRONMENT"]
  }
}
EOF
) \
        --profile "$AWS_PROFILE" \
        --region us-east-1 \
        --query 'ResultsByTime[-1].Total.UnblendedCost.Amount' \
        --output text 2>/dev/null || echo "N/A")

    if [ "$cost" != "N/A" ]; then
        log_info "Estimated daily cost (last day): \$$(printf "%.2f" "$cost")"
        log_info "Estimated monthly cost (if running 24/7): \$$(printf "%.2f" "$(echo "$cost * 30" | bc)")"
        log_info "After teardown, costs will be ~\$2-5/month (S3, Secrets Manager, snapshots)"
    else
        log_warning "Could not fetch cost data. Cost Explorer may not be enabled."
    fi
}

# ============================================================================
# Main Script
# ============================================================================

main() {
    local start_time=$(date +%s)

    echo ""
    log_info "=========================================="
    log_info "Festival Playlist Generator - Teardown"
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

    # Get cluster identifier
    log_info "Checking for RDS cluster..."
    local cluster_id=$(get_cluster_identifier)

    if [ -n "$cluster_id" ]; then
        log_success "Found RDS cluster: $cluster_id"
        echo ""

        # Create snapshot
        local snapshot_id=$(create_snapshot "$cluster_id")

        # Wait for snapshot to complete
        if wait_for_snapshot "$snapshot_id"; then
            echo ""
            log_success "Database snapshot created: $snapshot_id"
        else
            echo ""
            log_error "Snapshot creation failed. Aborting teardown."
            exit 1
        fi

        echo ""
        # Clean up old snapshots
        cleanup_old_snapshots "$SNAPSHOT_RETENTION_DAYS"
    else
        log_warning "No RDS cluster found. Skipping snapshot creation."
    fi

    echo ""
    # Confirm destruction
    log_warning "About to destroy infrastructure for environment: $ENVIRONMENT"
    read -p "Are you sure you want to continue? (yes/no): " -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_info "Teardown cancelled by user"
        exit 0
    fi

    # Run Terraform destroy
    if ! terraform_destroy; then
        log_error "Teardown failed during Terraform destroy"
        exit 1
    fi

    echo ""
    # Verify destruction
    verify_destruction

    echo ""
    # Display cost summary
    display_cost_summary

    # Calculate elapsed time
    local end_time=$(date +%s)
    local elapsed=$((end_time - start_time))
    local minutes=$((elapsed / 60))
    local seconds=$((elapsed % 60))

    echo ""
    log_info "=========================================="
    log_success "Teardown completed successfully!"
    log_info "Time elapsed: ${minutes}m ${seconds}s"
    log_info "=========================================="
    echo ""
    log_info "Next steps:"
    log_info "  1. Infrastructure is now torn down"
    log_info "  2. Database snapshot: $snapshot_id"
    log_info "  3. To restore, run: ./scripts/provision.sh"
    log_info "  4. Persistent resources (S3, Secrets Manager) remain intact"
    echo ""
}

# Run main function
main "$@"
