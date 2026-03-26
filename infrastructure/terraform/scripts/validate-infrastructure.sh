#!/bin/bash

# ============================================================================
# Validate Infrastructure Script
# ============================================================================
# This script validates that all AWS infrastructure components are properly
# configured and accessible.
#
# Usage:
#   ./validate-infrastructure.sh
#
# Prerequisites:
#   - AWS CLI configured with festival-playlist profile
#   - Terraform infrastructure already provisioned
# ============================================================================

set -e

# Configuration
PROFILE="festival-playlist"
REGION="eu-west-2"
PROJECT="festival-playlist"
ENVIRONMENT="dev"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((PASSED_CHECKS++))
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    ((FAILED_CHECKS++))
}

check_command() {
    ((TOTAL_CHECKS++))
    local description=$1
    local command=$2

    if eval "$command" &> /dev/null; then
        log_success "$description"
        return 0
    else
        log_error "$description"
        return 1
    fi
}

get_resource_count() {
    local command=$1
    eval "$command" 2>/dev/null | wc -l | tr -d ' '
}

# ============================================================================
# Validation Functions
# ============================================================================

validate_vpc() {
    log_info "Validating VPC and Networking..."
    echo ""

    # Check VPC exists
    check_command "VPC exists" \
        "aws ec2 describe-vpcs --filters 'Name=tag:Project,Values=$PROJECT' 'Name=tag:Environment,Values=$ENVIRONMENT' --profile $PROFILE --region $REGION --query 'Vpcs[0].VpcId' --output text | grep -q 'vpc-'"

    # Check public subnets
    local public_subnets=$(get_resource_count "aws ec2 describe-subnets --filters 'Name=tag:Project,Values=$PROJECT' 'Name=tag:Type,Values=public' --profile $PROFILE --region $REGION --query 'Subnets[].SubnetId' --output text")
    if [ "$public_subnets" -ge 2 ]; then
        log_success "Public subnets exist (count: $public_subnets)"
        ((PASSED_CHECKS++))
    else
        log_error "Public subnets missing or insufficient (count: $public_subnets, expected: 2)"
        ((FAILED_CHECKS++))
    fi
    ((TOTAL_CHECKS++))

    # Check private subnets
    local private_subnets=$(get_resource_count "aws ec2 describe-subnets --filters 'Name=tag:Project,Values=$PROJECT' 'Name=tag:Type,Values=private' --profile $PROFILE --region $REGION --query 'Subnets[].SubnetId' --output text")
    if [ "$private_subnets" -ge 2 ]; then
        log_success "Private subnets exist (count: $private_subnets)"
        ((PASSED_CHECKS++))
    else
        log_error "Private subnets missing or insufficient (count: $private_subnets, expected: 2)"
        ((FAILED_CHECKS++))
    fi
    ((TOTAL_CHECKS++))

    # Check Internet Gateway
    check_command "Internet Gateway attached" \
        "aws ec2 describe-internet-gateways --filters 'Name=tag:Project,Values=$PROJECT' --profile $PROFILE --region $REGION --query 'InternetGateways[0].InternetGatewayId' --output text | grep -q 'igw-'"

    echo ""
}

validate_security_groups() {
    log_info "Validating Security Groups..."
    echo ""

    # Check ALB security group
    check_command "ALB security group exists" \
        "aws ec2 describe-security-groups --filters 'Name=tag:Name,Values=*alb*' 'Name=tag:Project,Values=$PROJECT' --profile $PROFILE --region $REGION --query 'SecurityGroups[0].GroupId' --output text | grep -q 'sg-'"

    # Check ECS tasks security group
    check_command "ECS tasks security group exists" \
        "aws ec2 describe-security-groups --filters 'Name=tag:Name,Values=*ecs*' 'Name=tag:Project,Values=$PROJECT' --profile $PROFILE --region $REGION --query 'SecurityGroups[0].GroupId' --output text | grep -q 'sg-'"

    # Check RDS security group
    check_command "RDS security group exists" \
        "aws ec2 describe-security-groups --filters 'Name=tag:Name,Values=*rds*' 'Name=tag:Project,Values=$PROJECT' --profile $PROFILE --region $REGION --query 'SecurityGroups[0].GroupId' --output text | grep -q 'sg-'"

    # Check Redis security group
    check_command "Redis security group exists" \
        "aws ec2 describe-security-groups --filters 'Name=tag:Name,Values=*redis*' 'Name=tag:Project,Values=$PROJECT' --profile $PROFILE --region $REGION --query 'SecurityGroups[0].GroupId' --output text | grep -q 'sg-'"

    echo ""
}

validate_rds() {
    log_info "Validating RDS Aurora Cluster..."
    echo ""

    # Check cluster exists
    check_command "RDS cluster exists" \
        "aws rds describe-db-clusters --db-cluster-identifier $PROJECT-$ENVIRONMENT --profile $PROFILE --region $REGION --query 'DBClusters[0].DBClusterIdentifier' --output text | grep -q '$PROJECT-$ENVIRONMENT'"

    # Check cluster status
    local cluster_status=$(aws rds describe-db-clusters --db-cluster-identifier $PROJECT-$ENVIRONMENT --profile $PROFILE --region $REGION --query 'DBClusters[0].Status' --output text 2>/dev/null || echo "unknown")
    if [ "$cluster_status" = "available" ]; then
        log_success "RDS cluster is available"
        ((PASSED_CHECKS++))
    else
        log_error "RDS cluster status: $cluster_status (expected: available)"
        ((FAILED_CHECKS++))
    fi
    ((TOTAL_CHECKS++))

    # Check instances
    local instance_count=$(get_resource_count "aws rds describe-db-cluster-members --db-cluster-identifier $PROJECT-$ENVIRONMENT --profile $PROFILE --region $REGION --query 'DBClusterMembers[].DBInstanceIdentifier' --output text")
    if [ "$instance_count" -ge 1 ]; then
        log_success "RDS instances exist (count: $instance_count)"
        ((PASSED_CHECKS++))
    else
        log_error "RDS instances missing (count: $instance_count, expected: >= 1)"
        ((FAILED_CHECKS++))
    fi
    ((TOTAL_CHECKS++))

    # Check endpoint
    check_command "RDS cluster endpoint accessible" \
        "aws rds describe-db-clusters --db-cluster-identifier $PROJECT-$ENVIRONMENT --profile $PROFILE --region $REGION --query 'DBClusters[0].Endpoint' --output text | grep -q '.rds.amazonaws.com'"

    echo ""
}

validate_elasticache() {
    log_info "Validating ElastiCache Redis..."
    echo ""

    # Check replication group exists
    check_command "Redis replication group exists" \
        "aws elasticache describe-replication-groups --replication-group-id $PROJECT-$ENVIRONMENT --profile $PROFILE --region $REGION --query 'ReplicationGroups[0].ReplicationGroupId' --output text | grep -q '$PROJECT-$ENVIRONMENT'"

    # Check status
    local redis_status=$(aws elasticache describe-replication-groups --replication-group-id $PROJECT-$ENVIRONMENT --profile $PROFILE --region $REGION --query 'ReplicationGroups[0].Status' --output text 2>/dev/null || echo "unknown")
    if [ "$redis_status" = "available" ]; then
        log_success "Redis cluster is available"
        ((PASSED_CHECKS++))
    else
        log_error "Redis cluster status: $redis_status (expected: available)"
        ((FAILED_CHECKS++))
    fi
    ((TOTAL_CHECKS++))

    # Check endpoint
    check_command "Redis primary endpoint accessible" \
        "aws elasticache describe-replication-groups --replication-group-id $PROJECT-$ENVIRONMENT --profile $PROFILE --region $REGION --query 'ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint.Address' --output text | grep -q '.cache.amazonaws.com'"

    echo ""
}

validate_s3() {
    log_info "Validating S3 Buckets..."
    echo ""

    # Check app-data bucket
    check_command "App data bucket exists" \
        "aws s3api head-bucket --bucket $PROJECT-$ENVIRONMENT-app-data --profile $PROFILE 2>&1"

    # Check cloudfront-logs bucket
    check_command "CloudFront logs bucket exists" \
        "aws s3api head-bucket --bucket $PROJECT-$ENVIRONMENT-cloudfront-logs --profile $PROFILE 2>&1"

    # Check versioning on app-data bucket
    check_command "App data bucket versioning enabled" \
        "aws s3api get-bucket-versioning --bucket $PROJECT-$ENVIRONMENT-app-data --profile $PROFILE --query 'Status' --output text | grep -q 'Enabled'"

    # Check encryption on app-data bucket
    check_command "App data bucket encryption enabled" \
        "aws s3api get-bucket-encryption --bucket $PROJECT-$ENVIRONMENT-app-data --profile $PROFILE --query 'ServerSideEncryptionConfiguration.Rules[0].ApplyServerSideEncryptionByDefault.SSEAlgorithm' --output text | grep -q 'AES256'"

    echo ""
}

validate_ecr() {
    log_info "Validating ECR Repository..."
    echo ""

    # Check repository exists
    check_command "ECR repository exists" \
        "aws ecr describe-repositories --repository-names $PROJECT --profile $PROFILE --region $REGION --query 'repositories[0].repositoryName' --output text | grep -q '$PROJECT'"

    # Check image scanning enabled
    check_command "ECR image scanning enabled" \
        "aws ecr describe-repositories --repository-names $PROJECT --profile $PROFILE --region $REGION --query 'repositories[0].imageScanningConfiguration.scanOnPush' --output text | grep -q 'True'"

    echo ""
}

validate_secrets() {
    log_info "Validating Secrets Manager..."
    echo ""

    # Check database secret
    check_command "Database credentials secret exists" \
        "aws secretsmanager describe-secret --secret-id $PROJECT-$ENVIRONMENT-db-credentials --profile $PROFILE --region $REGION --query 'ARN' --output text | grep -q 'arn:aws:secretsmanager'"

    # Check Redis secret
    check_command "Redis connection secret exists" \
        "aws secretsmanager describe-secret --secret-id $PROJECT-$ENVIRONMENT-redis-url --profile $PROFILE --region $REGION --query 'ARN' --output text | grep -q 'arn:aws:secretsmanager'"

    # Check Spotify secret
    check_command "Spotify credentials secret exists" \
        "aws secretsmanager describe-secret --secret-id $PROJECT-$ENVIRONMENT-spotify --profile $PROFILE --region $REGION --query 'ARN' --output text | grep -q 'arn:aws:secretsmanager'"

    # Check Setlist.fm secret
    check_command "Setlist.fm API key secret exists" \
        "aws secretsmanager describe-secret --secret-id $PROJECT-$ENVIRONMENT-setlistfm --profile $PROFILE --region $REGION --query 'ARN' --output text | grep -q 'arn:aws:secretsmanager'"

    # Check JWT secret
    check_command "JWT signing key secret exists" \
        "aws secretsmanager describe-secret --secret-id $PROJECT-$ENVIRONMENT-jwt-secret --profile $PROFILE --region $REGION --query 'ARN' --output text | grep -q 'arn:aws:secretsmanager'"

    echo ""
}

validate_cloudwatch() {
    log_info "Validating CloudWatch Logs..."
    echo ""

    # Check API log group
    check_command "API log group exists" \
        "aws logs describe-log-groups --log-group-name-prefix /ecs/$PROJECT-$ENVIRONMENT-api --profile $PROFILE --region $REGION --query 'logGroups[0].logGroupName' --output text | grep -q '/ecs/'"

    # Check worker log group
    check_command "Worker log group exists" \
        "aws logs describe-log-groups --log-group-name-prefix /ecs/$PROJECT-$ENVIRONMENT-worker --profile $PROFILE --region $REGION --query 'logGroups[0].logGroupName' --output text | grep -q '/ecs/'"

    echo ""
}

# ============================================================================
# Main Script
# ============================================================================

main() {
    echo "============================================================================"
    echo "  Festival Playlist Generator - Infrastructure Validation"
    echo "============================================================================"
    echo ""

    log_info "Starting infrastructure validation..."
    log_info "Profile: $PROFILE"
    log_info "Region: $REGION"
    log_info "Environment: $ENVIRONMENT"
    echo ""

    # Run all validations
    validate_vpc
    validate_security_groups
    validate_rds
    validate_elasticache
    validate_s3
    validate_ecr
    validate_secrets
    validate_cloudwatch

    # Summary
    echo "============================================================================"
    echo "  Validation Summary"
    echo "============================================================================"
    echo ""
    echo "Total checks: $TOTAL_CHECKS"
    echo -e "${GREEN}Passed: $PASSED_CHECKS${NC}"
    echo -e "${RED}Failed: $FAILED_CHECKS${NC}"
    echo ""

    if [ $FAILED_CHECKS -eq 0 ]; then
        log_success "All infrastructure validation checks passed!"
        echo ""
        log_info "Next steps:"
        echo "  1. Populate secrets: ./populate-secrets.sh"
        echo "  2. Build and push Docker image to ECR"
        echo "  3. Deploy application to ECS"
        echo ""
        exit 0
    else
        log_error "Some infrastructure validation checks failed"
        echo ""
        log_info "Please review the errors above and fix the issues"
        log_info "You may need to run: terraform apply"
        echo ""
        exit 1
    fi
}

# Run main function
main
