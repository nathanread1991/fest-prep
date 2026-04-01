#!/usr/bin/env bash
# =============================================================================
# ECR Push Script
# Build and push Docker image to Amazon ECR
#
# Usage:
#   ./scripts/ecr-push.sh                  # Build and push with git SHA + latest
#   ./scripts/ecr-push.sh --tag v1.0.0     # Build and push with custom tag + latest
#   ./scripts/ecr-push.sh --dry-run        # Build only, don't push
# =============================================================================

set -euo pipefail

# Configuration
AWS_REGION="${AWS_REGION:-eu-west-2}"
PROJECT_NAME="${PROJECT_NAME:-festival-playlist}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
ECR_REPO="${PROJECT_NAME}-${ENVIRONMENT}"
DOCKERFILE_PATH="services/api/Dockerfile"
BUILD_CONTEXT="services/api"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
CUSTOM_TAG=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --tag)
            CUSTOM_TAG="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--tag TAG] [--dry-run]"
            echo ""
            echo "Options:"
            echo "  --tag TAG    Custom image tag (default: git SHA)"
            echo "  --dry-run    Build only, don't push to ECR"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Determine image tag
if [ -n "$CUSTOM_TAG" ]; then
    IMAGE_TAG="$CUSTOM_TAG"
else
    IMAGE_TAG=$(git rev-parse --short HEAD)
fi

echo -e "${GREEN}=== ECR Push Script ===${NC}"
echo "Region:      $AWS_REGION"
echo "Repository:  $ECR_REPO"
echo "Tag:         $IMAGE_TAG"
echo "Dry run:     $DRY_RUN"
echo ""

# Step 1: Get AWS account ID
echo -e "${YELLOW}[1/5] Getting AWS account ID...${NC}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
FULL_IMAGE="${ECR_REGISTRY}/${ECR_REPO}"
echo "  Registry: $ECR_REGISTRY"

# Step 2: Authenticate Docker with ECR
echo -e "${YELLOW}[2/5] Authenticating Docker with ECR...${NC}"
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$ECR_REGISTRY"
echo "  Authentication successful"

# Step 3: Build Docker image
echo -e "${YELLOW}[3/5] Building Docker image...${NC}"
docker build \
    -t "${FULL_IMAGE}:${IMAGE_TAG}" \
    -t "${FULL_IMAGE}:latest" \
    -f "$DOCKERFILE_PATH" \
    "$BUILD_CONTEXT"
echo "  Build complete"

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo -e "${GREEN}=== Dry run complete (image built but not pushed) ===${NC}"
    echo "  Image: ${FULL_IMAGE}:${IMAGE_TAG}"
    echo "  Image: ${FULL_IMAGE}:latest"
    exit 0
fi

# Step 4: Push to ECR
echo -e "${YELLOW}[4/5] Pushing image to ECR...${NC}"
docker push "${FULL_IMAGE}:${IMAGE_TAG}"
docker push "${FULL_IMAGE}:latest"
echo "  Push complete"

# Step 5: Verify image in ECR
echo -e "${YELLOW}[5/5] Verifying image in ECR...${NC}"
aws ecr describe-images \
    --repository-name "$ECR_REPO" \
    --image-ids imageTag="$IMAGE_TAG" \
    --region "$AWS_REGION" \
    --query 'imageDetails[0].{digest:imageDigest,tags:imageTags,pushed:imagePushedAt,size:imageSizeInBytes}' \
    --output table

echo ""
echo -e "${GREEN}=== ECR push complete ===${NC}"
echo "  Image: ${FULL_IMAGE}:${IMAGE_TAG}"
echo "  Image: ${FULL_IMAGE}:latest"
