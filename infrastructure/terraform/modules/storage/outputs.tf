# Storage Module Outputs

# ============================================================================
# S3 Bucket Outputs - App Data
# ============================================================================

output "app_data_bucket_name" {
  description = "Name of the app data S3 bucket"
  value       = aws_s3_bucket.app_data.id
}

output "app_data_bucket_arn" {
  description = "ARN of the app data S3 bucket"
  value       = aws_s3_bucket.app_data.arn
}

output "app_data_bucket_domain_name" {
  description = "Domain name of the app data S3 bucket"
  value       = aws_s3_bucket.app_data.bucket_domain_name
}

output "app_data_bucket_regional_domain_name" {
  description = "Regional domain name of the app data S3 bucket"
  value       = aws_s3_bucket.app_data.bucket_regional_domain_name
}


# ============================================================================
# S3 Bucket Outputs - CloudFront Logs
# ============================================================================

output "cloudfront_logs_bucket_name" {
  description = "Name of the CloudFront logs S3 bucket"
  value       = aws_s3_bucket.cloudfront_logs.id
}

output "cloudfront_logs_bucket_arn" {
  description = "ARN of the CloudFront logs S3 bucket"
  value       = aws_s3_bucket.cloudfront_logs.arn
}

output "cloudfront_logs_bucket_domain_name" {
  description = "Domain name of the CloudFront logs S3 bucket"
  value       = aws_s3_bucket.cloudfront_logs.bucket_domain_name
}


# ============================================================================
# ECR Repository Outputs
# ============================================================================

output "ecr_repository_name" {
  description = "Name of the ECR repository"
  value       = aws_ecr_repository.app.name
}

output "ecr_repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.app.arn
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.app.repository_url
}

output "ecr_registry_id" {
  description = "Registry ID of the ECR repository"
  value       = aws_ecr_repository.app.registry_id
}
