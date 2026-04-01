#!/usr/bin/env bash
# ============================================================================
# Deploy Image Script
# ============================================================================
# Updates ECS task definitions with a new Docker image tag via Terraform
# and triggers a rolling deployment of ECS services.
#
# Usage:
#   ./scripts/deploy-image.sh <image-tag>
#   ./scripts/deploy-image.sh abc123def   # deploy specific commit SHA
#   ./scripts/deploy-image.sh latest      # deploy latest tag
#
# Requirements:
#   - AWS CLI configured with appropriate credentials
#   - Terraform initialized in the parent directory
#   - ECR image already pushed with the specified tag
# ============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_NAME="${PROJECT_NAME:-festival-playlist}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-eu-west-2}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Validate arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <image-tag>"
    echo ""
    echo "Examples:"
    echo "  $0 abc123def456    # Deploy specific commit SHA"
    echo "  $0 latest          # Deploy latest tag"
    echo "  $0 v1.2.3          # Deploy version tag"
    exit 1
fi

IMAGE_TAG="$1"
CLUSTER="${PROJECT_NAME}-${ENVIRONMENT}-cluster"
API_SERVICE="${PROJECT_NAME}-${ENVIRONMENT}-api"
WORKER_SERVICE="${PROJECT_NAME}-${ENVIRONMENT}-worker"

log_info "Deploying image tag: ${IMAGE_TAG}"
log_info "Cluster: ${CLUSTER}"
log_info "Region: ${AWS_REGION}"
echo ""

# Step 1: Verify the image exists in ECR
log_info "Verifying image exists in ECR..."
ECR_REPO="${PROJECT_NAME}-${ENVIRONMENT}"
if aws ecr describe-images \
    --repository-name "${ECR_REPO}" \
    --image-ids imageTag="${IMAGE_TAG}" \
    --region "${AWS_REGION}" > /dev/null 2>&1; then
    log_info "Image ${ECR_REPO}:${IMAGE_TAG} found in ECR"
else
    log_error "Image ${ECR_REPO}:${IMAGE_TAG} not found in ECR"
    log_error "Push the image first, then retry."
    exit 1
fi

# Step 2: Record current task definitions (for rollback reference)
log_info "Recording current task definitions..."
CURRENT_API_TD=$(aws ecs describe-services \
    --cluster "${CLUSTER}" \
    --services "${API_SERVICE}" \
    --region "${AWS_REGION}" \
    --query 'services[0].taskDefinition' \
    --output text 2>/dev/null || echo "none")
CURRENT_WORKER_TD=$(aws ecs describe-services \
    --cluster "${CLUSTER}" \
    --services "${WORKER_SERVICE}" \
    --region "${AWS_REGION}" \
    --query 'services[0].taskDefinition' \
    --output text 2>/dev/null || echo "none")
log_info "Current API task definition: ${CURRENT_API_TD}"
log_info "Current Worker task definition: ${CURRENT_WORKER_TD}"
echo ""

# Step 3: Update task definitions via Terraform
log_info "Updating ECS task definitions via Terraform..."
cd "${TF_DIR}"

terraform init -backend=true -input=false > /dev/null 2>&1

terraform apply -auto-approve \
    -var="api_image_tag=${IMAGE_TAG}" \
    -var="worker_image_tag=${IMAGE_TAG}" \
    -target=module.compute.aws_ecs_task_definition.api \
    -target=module.compute.aws_ecs_task_definition.worker \
    -target=module.compute.aws_ecs_service.api \
    -target=module.compute.aws_ecs_service.worker

echo ""

# Step 4: Verify new task definitions were created
log_info "Verifying new task definitions..."
NEW_API_TD=$(aws ecs describe-services \
    --cluster "${CLUSTER}" \
    --services "${API_SERVICE}" \
    --region "${AWS_REGION}" \
    --query 'services[0].taskDefinition' \
    --output text)
NEW_WORKER_TD=$(aws ecs describe-services \
    --cluster "${CLUSTER}" \
    --services "${WORKER_SERVICE}" \
    --region "${AWS_REGION}" \
    --query 'services[0].taskDefinition' \
    --output text)

log_info "New API task definition: ${NEW_API_TD}"
log_info "New Worker task definition: ${NEW_WORKER_TD}"

if [ "${CURRENT_API_TD}" = "${NEW_API_TD}" ] && [ "${IMAGE_TAG}" != "latest" ]; then
    log_warn "API task definition did not change — image tag may already be deployed"
fi
echo ""

# Step 5: Wait for services to stabilize
log_info "Waiting for API service to stabilize..."
if aws ecs wait services-stable \
    --cluster "${CLUSTER}" \
    --services "${API_SERVICE}" \
    --region "${AWS_REGION}" 2>/dev/null; then
    log_info "API service is stable"
else
    log_error "API service did not stabilize within timeout"
    log_error "Previous API task definition: ${CURRENT_API_TD}"
    log_error "Run the following to rollback:"
    log_error "  aws ecs update-service --cluster ${CLUSTER} --service ${API_SERVICE} --task-definition ${CURRENT_API_TD}"
    exit 1
fi

log_info "Waiting for Worker service to stabilize..."
if aws ecs wait services-stable \
    --cluster "${CLUSTER}" \
    --services "${WORKER_SERVICE}" \
    --region "${AWS_REGION}" 2>/dev/null; then
    log_info "Worker service is stable"
else
    log_warn "Worker service did not stabilize (may be expected if desired count is 0)"
fi
echo ""

# Step 6: Summary
log_info "========================================="
log_info "Deployment complete!"
log_info "========================================="
log_info "Image tag:    ${IMAGE_TAG}"
log_info "API task def: ${NEW_API_TD}"
log_info "Worker task:  ${NEW_WORKER_TD}"
log_info "========================================="
