# Storage Module

This module manages S3 buckets and ECR repository for the Festival Playlist Generator.

## Overview

The storage module creates persistent storage resources that survive daily teardown/rebuild cycles:
- **App Data Bucket**: Stores user uploads, backups, and application data with versioning and Intelligent-Tiering
- **CloudFront Logs Bucket**: Stores CloudFront and ALB access logs with 30-day lifecycle policy
- **ECR Repository**: Stores Docker container images with image scanning and lifecycle policy (keep last 10 images)

## Resources Created

### S3 Buckets

**App Data Bucket** (`{project}-{env}-app-data`):
- Versioning enabled for data protection
- S3 Intelligent-Tiering for automatic cost optimization
- Server-side encryption (AES256)
- Public access blocked
- Bucket policy for CloudFront access
- Secure transport enforcement (HTTPS only)

**CloudFront Logs Bucket** (`{project}-{env}-cloudfront-logs`):
- Lifecycle policy (30-day expiration)
- Server-side encryption (AES256)
- Public access blocked
- Bucket policy for ALB and CloudFront log delivery
- Log delivery ACL configured

### ECR Repository

**Container Registry** (`{project}-{env}`):
- Image scanning on push enabled
- Encryption at rest (AES256)
- Lifecycle policy (keep last 10 images)
- Mutable image tags

## Security Features

### S3 Security
- ✅ All buckets have public access blocked
- ✅ Server-side encryption enabled (AES256)
- ✅ Bucket policies enforce HTTPS-only access
- ✅ Bucket policies enforce encrypted uploads
- ✅ CloudFront access via bucket policy (not public)
- ✅ ALB log delivery via bucket policy (not public)

### ECR Security
- ✅ Image scanning on push
- ✅ Encryption at rest
- ✅ Lifecycle policy prevents unbounded growth

## Persistence Strategy

All resources in this module are marked with `prevent_destroy = true` to ensure they persist across daily teardown/rebuild cycles:

- **S3 Buckets**: Never destroyed, data persists
- **ECR Repository**: Never destroyed, images persist

This allows for:
- Daily infrastructure teardown without data loss
- Fast provisioning (no need to restore data)
- Cost savings (only pay for storage, not compute)

## Cost Optimization

### S3 Intelligent-Tiering
The app-data bucket uses S3 Intelligent-Tiering to automatically move objects between access tiers:
- **Frequent Access**: Objects accessed regularly
- **Infrequent Access**: Objects not accessed for 30 days
- **Archive Access**: Objects not accessed for 90 days
- **Deep Archive Access**: Objects not accessed for 180 days

This can save up to 95% on storage costs for infrequently accessed data.

### Lifecycle Policies
The CloudFront logs bucket automatically deletes logs after 30 days to minimize storage costs.

### ECR Lifecycle Policy
The ECR repository keeps only the last 10 images, automatically deleting older images to minimize storage costs.

## Usage

### Basic Usage

```hcl
module "storage" {
  source = "./modules/storage"

  project_name = var.project_name
  environment  = var.environment
  common_tags  = var.common_tags
}
```

### With CloudFront Distribution

```hcl
module "storage" {
  source = "./modules/storage"

  project_name                 = var.project_name
  environment                  = var.environment
  common_tags                  = var.common_tags
  cloudfront_distribution_arn  = module.cdn.cloudfront_distribution_arn
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project_name | Name of the project | string | - | yes |
| environment | Environment name (dev, staging, prod) | string | - | yes |
| common_tags | Common tags to apply to all resources | map(string) | {} | no |
| cloudfront_distribution_arn | ARN of CloudFront distribution for bucket policy | string | null | no |

## Outputs

### S3 Bucket Outputs

| Name | Description |
|------|-------------|
| app_data_bucket_name | Name of the app data S3 bucket |
| app_data_bucket_arn | ARN of the app data S3 bucket |
| app_data_bucket_domain_name | Domain name of the app data S3 bucket |
| app_data_bucket_regional_domain_name | Regional domain name of the app data S3 bucket |
| cloudfront_logs_bucket_name | Name of the CloudFront logs S3 bucket |
| cloudfront_logs_bucket_arn | ARN of the CloudFront logs S3 bucket |
| cloudfront_logs_bucket_domain_name | Domain name of the CloudFront logs S3 bucket |

### ECR Repository Outputs

| Name | Description |
|------|-------------|
| ecr_repository_name | Name of the ECR repository |
| ecr_repository_arn | ARN of the ECR repository |
| ecr_repository_url | URL of the ECR repository |
| ecr_registry_id | Registry ID of the ECR repository |

## Examples

### Accessing Outputs

```hcl
# Use ECR repository URL in ECS task definition
resource "aws_ecs_task_definition" "app" {
  container_definitions = jsonencode([{
    name  = "app"
    image = "${module.storage.ecr_repository_url}:latest"
    # ...
  }])
}

# Use app data bucket in CloudFront origin
resource "aws_cloudfront_origin_access_identity" "app_data" {
  comment = "Access identity for app data bucket"
}

resource "aws_cloudfront_distribution" "main" {
  origin {
    domain_name = module.storage.app_data_bucket_regional_domain_name
    origin_id   = "S3-app-data"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.app_data.cloudfront_access_identity_path
    }
  }
  # ...
}
```

## Notes

### CloudFront Distribution ARN
The `cloudfront_distribution_arn` variable is optional and can be added after the CloudFront distribution is created. If not provided, the bucket policy will have an empty condition, which should be updated later.

### Bucket Naming
Bucket names must be globally unique across all AWS accounts. The module uses the pattern `{project_name}-{environment}-{purpose}` to ensure uniqueness.

### ECR Image Scanning
Image scanning is enabled on push. Scan results can be viewed in the AWS Console or via the AWS CLI:

```bash
aws ecr describe-image-scan-findings \
  --repository-name {project}-{env} \
  --image-id imageTag=latest
```

### Lifecycle Policies
- **S3 Logs**: Automatically deleted after 30 days
- **ECR Images**: Keep last 10 images, delete older ones

## Troubleshooting

### Bucket Already Exists Error
If you get a "bucket already exists" error, it means:
1. The bucket was created in a previous run (expected for persistent buckets)
2. The bucket name is taken by another AWS account (change project_name)

### CloudFront Access Denied
If CloudFront cannot access the S3 bucket:
1. Ensure `cloudfront_distribution_arn` is set correctly
2. Verify the bucket policy is applied
3. Check CloudFront origin configuration

### ECR Push Permission Denied
If you cannot push images to ECR:
1. Authenticate Docker with ECR: `aws ecr get-login-password | docker login --username AWS --password-stdin {registry_id}.dkr.ecr.{region}.amazonaws.com`
2. Verify IAM permissions for ECR push operations

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5 |
| aws | >= 5.0 |

## Providers

| Name | Version |
|------|---------|
| aws | >= 5.0 |
