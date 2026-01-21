#!/bin/bash
# Initialize Terraform Backend (S3 + DynamoDB Locking)
# This script creates the S3 bucket and DynamoDB table for Terraform remote state
# Use this script if you have Terraform < 1.11.0 (DynamoDB locking required)
# For Terraform >= 1.11.0, use init-backend.sh instead (native S3 locking)

set -e

# Configuration
PROJECT_NAME="festival-playlist"
AWS_REGION="eu-west-2"
AWS_PROFILE="${AWS_PROFILE:-festival-playlist}"
BUCKET_NAME="${PROJECT_NAME}-terraform-state"
DYNAMODB_TABLE="${PROJECT_NAME}-terraform-locks"

echo "=========================================="
echo "Terraform Backend Initialization"
echo "=========================================="
echo "Project: ${PROJECT_NAME}"
echo "Region: ${AWS_REGION}"
echo "Profile: ${AWS_PROFILE}"
echo "Bucket: ${BUCKET_NAME}"
echo "DynamoDB Table: ${DYNAMODB_TABLE}"
echo "Locking: DynamoDB (Terraform < 1.11.0)"
echo "=========================================="
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ Error: AWS CLI is not installed"
    echo "Please install AWS CLI: https://aws.amazon.com/cli/"
    exit 1
fi

# Check Terraform version
if command -v terraform &> /dev/null; then
    TERRAFORM_VERSION=$(terraform version -json 2>/dev/null | grep -o '"terraform_version":"[^"]*' | cut -d'"' -f4 || echo "unknown")
    echo "ℹ️  Terraform version: ${TERRAFORM_VERSION}"
    
    # Check if version is >= 1.11.0
    if [ "${TERRAFORM_VERSION}" != "unknown" ]; then
        MAJOR=$(echo "${TERRAFORM_VERSION}" | cut -d. -f1)
        MINOR=$(echo "${TERRAFORM_VERSION}" | cut -d. -f2)
        
        if [ "${MAJOR}" -gt 1 ] || ([ "${MAJOR}" -eq 1 ] && [ "${MINOR}" -ge 11 ]); then
            echo "⚠️  Warning: Terraform ${TERRAFORM_VERSION} supports native S3 locking"
            echo "   Consider using init-backend.sh instead (no DynamoDB needed)"
            echo ""
            read -p "Continue with DynamoDB setup anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    fi
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
            "Id": "DeleteOldVersions",
            "Status": "Enabled",
            "NoncurrentVersionExpiration": {
                "NoncurrentDays": 90
            }
        }]
    }'
echo "✅ Lifecycle policy added"

echo ""

# Create DynamoDB table for state locking
echo "Creating DynamoDB table: ${DYNAMODB_TABLE}"
if aws dynamodb describe-table --table-name "${DYNAMODB_TABLE}" --profile "${AWS_PROFILE}" --region "${AWS_REGION}" &> /dev/null; then
    echo "⚠️  DynamoDB table already exists: ${DYNAMODB_TABLE}"
else
    aws dynamodb create-table \
        --table-name "${DYNAMODB_TABLE}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --tags Key=Project,Value="${PROJECT_NAME}" Key=ManagedBy,Value=terraform
    
    echo "⏳ Waiting for DynamoDB table to be active..."
    aws dynamodb wait table-exists \
        --table-name "${DYNAMODB_TABLE}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}"
    
    echo "✅ DynamoDB table created: ${DYNAMODB_TABLE}"
fi

echo ""
echo "=========================================="
echo "✅ Backend initialization complete!"
echo "=========================================="
echo ""
echo "DynamoDB Locking Configuration:"
echo "- DynamoDB table: ${DYNAMODB_TABLE}"
echo "- Partition key: LockID (String)"
echo "- Billing mode: PAY_PER_REQUEST"
echo ""
echo "Next steps:"
echo "1. Update terraform/backend.tf with OPTION 2 configuration:"
echo ""
echo "terraform {"
echo "  backend \"s3\" {"
echo "    bucket         = \"${BUCKET_NAME}\""
echo "    key            = \"terraform.tfstate\""
echo "    region         = \"${AWS_REGION}\""
echo "    encrypt        = true"
echo "    dynamodb_table = \"${DYNAMODB_TABLE}\""
echo "    profile        = \"${AWS_PROFILE}\""
echo "  }"
echo "}"
echo ""
echo "2. Run: terraform init"
echo "3. If you have existing local state, run: terraform init -migrate-state"
echo ""
echo "Note: Consider upgrading to Terraform >= 1.11.0 for native S3 locking"
echo "      (no DynamoDB needed, simpler setup, lower cost)"
echo ""
echo "=========================================="
