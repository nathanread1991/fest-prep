#!/bin/bash
# Initialize Terraform Backend (S3 with Native Locking)
# This script creates the S3 bucket needed for Terraform remote state
# Uses Terraform v1.10+ native S3 locking (no DynamoDB required)
# Run this script ONCE before running terraform init

set -e

# Configuration
PROJECT_NAME="festival-playlist"
AWS_REGION="eu-west-2"
AWS_PROFILE="${AWS_PROFILE:-festival-playlist}"
BUCKET_NAME="${PROJECT_NAME}-terraform-state"

echo "=========================================="
echo "Terraform Backend Initialization"
echo "=========================================="
echo "Project: ${PROJECT_NAME}"
echo "Region: ${AWS_REGION}"
echo "Profile: ${AWS_PROFILE}"
echo "Bucket: ${BUCKET_NAME}"
echo "Locking: Native S3 (Terraform v1.10+)"
echo "=========================================="
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ Error: AWS CLI is not installed"
    echo "Please install AWS CLI: https://aws.amazon.com/cli/"
    exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity --profile "${AWS_PROFILE}" &> /dev/null; then
    echo "❌ Error: AWS credentials not configured for profile '${AWS_PROFILE}'"
    echo "Please run: aws configure --profile ${AWS_PROFILE}"
    exit 1
fi

echo "✅ AWS CLI configured"
echo ""

# Create S3 bucket for Terraform state
echo "Creating S3 bucket: ${BUCKET_NAME}"
if aws s3api head-bucket --bucket "${BUCKET_NAME}" --profile "${AWS_PROFILE}" 2>/dev/null; then
    echo "⚠️  S3 bucket already exists: ${BUCKET_NAME}"
else
    # Create bucket with region-specific configuration
    if [ "${AWS_REGION}" = "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "${BUCKET_NAME}" \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}"
    else
        aws s3api create-bucket \
            --bucket "${BUCKET_NAME}" \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}" \
            --create-bucket-configuration LocationConstraint="${AWS_REGION}"
    fi
    echo "✅ S3 bucket created: ${BUCKET_NAME}"
fi

# Enable versioning on S3 bucket
echo "Enabling versioning on S3 bucket..."
aws s3api put-bucket-versioning \
    --bucket "${BUCKET_NAME}" \
    --profile "${AWS_PROFILE}" \
    --versioning-configuration Status=Enabled
echo "✅ Versioning enabled"

# Enable server-side encryption on S3 bucket
echo "Enabling server-side encryption on S3 bucket..."
aws s3api put-bucket-encryption \
    --bucket "${BUCKET_NAME}" \
    --profile "${AWS_PROFILE}" \
    --server-side-encryption-configuration '{
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            },
            "BucketKeyEnabled": true
        }]
    }'
echo "✅ Encryption enabled"

# Block public access to S3 bucket
echo "Blocking public access to S3 bucket..."
aws s3api put-public-access-block \
    --bucket "${BUCKET_NAME}" \
    --profile "${AWS_PROFILE}" \
    --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
echo "✅ Public access blocked"

# Add lifecycle policy to manage old versions
echo "Adding lifecycle policy to S3 bucket..."
aws s3api put-bucket-lifecycle-configuration \
    --bucket "${BUCKET_NAME}" \
    --profile "${AWS_PROFILE}" \
    --lifecycle-configuration '{
        "Rules": [{
            "ID": "DeleteOldVersions",
            "Status": "Enabled",
            "Filter": {},
            "NoncurrentVersionExpiration": {
                "NoncurrentDays": 90
            }
        }]
    }'
echo "✅ Lifecycle policy added"

echo ""
echo "=========================================="
echo "✅ Backend initialization complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Update terraform/backend.tf with the following configuration:"
echo ""
echo "terraform {"
echo "  backend \"s3\" {"
echo "    bucket  = \"${BUCKET_NAME}\""
echo "    key     = \"terraform.tfstate\""
echo "    region  = \"${AWS_REGION}\""
echo "    encrypt = true"
echo "    profile = \"${AWS_PROFILE}\""
echo "    use_lockfile = true  # Native S3 locking (Terraform v1.10+)"
echo "  }"
echo "}"
echo ""
echo "2. Run: terraform init"
echo "3. If you have existing local state, run: terraform init -migrate-state"
echo ""
echo "Note: No DynamoDB table needed! Terraform v1.10+ uses native S3 locking."
echo "=========================================="
