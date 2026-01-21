# Storage Module

This module manages S3 buckets and ECR repository for the Festival Playlist Generator.

## Resources Created

- S3 bucket for application data (with versioning and Intelligent-Tiering)
- S3 bucket for CloudFront logs (with lifecycle policy)
- ECR repository for container images
- S3 bucket policies
- Lifecycle policies

## Security

- All buckets have public access blocked
- Server-side encryption enabled (AES256)
- Versioning enabled on app-data bucket
- Lifecycle policy on logs bucket (30-day expiration)

## Persistence

- S3 buckets marked with `prevent_destroy = true`
- ECR repository marked with `prevent_destroy = true`
- These resources persist across teardown/rebuild cycles

## Usage

```hcl
module "storage" {
  source = "./modules/storage"
  
  project_name = var.project_name
  environment  = var.environment
  common_tags  = var.common_tags
}
```

## Outputs

- app_data_bucket_name
- app_data_bucket_arn
- cloudfront_logs_bucket_name
- ecr_repository_url
- ecr_repository_arn
