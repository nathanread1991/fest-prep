# Outputs for the Persistent Terraform Module
# These are consumed by the ephemeral root via terraform_remote_state.

# ============================================================================
# ECR
# ============================================================================

output "ecr_repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.app.arn
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.app.repository_url
}

output "ecr_repository_name" {
  description = "Name of the ECR repository"
  value       = aws_ecr_repository.app.name
}

output "ecr_registry_id" {
  description = "Registry ID of the ECR repository"
  value       = aws_ecr_repository.app.registry_id
}

# ============================================================================
# S3 - App Data
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
# S3 - CloudFront Logs
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
# Secrets Manager
# ============================================================================

output "spotify_secret_arn" {
  description = "ARN of the Spotify credentials secret"
  value       = aws_secretsmanager_secret.spotify.arn
}

output "spotify_secret_name" {
  description = "Name of the Spotify credentials secret"
  value       = aws_secretsmanager_secret.spotify.name
}

output "setlistfm_secret_arn" {
  description = "ARN of the Setlist.fm API key secret"
  value       = aws_secretsmanager_secret.setlistfm.arn
}

output "setlistfm_secret_name" {
  description = "Name of the Setlist.fm API key secret"
  value       = aws_secretsmanager_secret.setlistfm.name
}

output "jwt_secret_arn" {
  description = "ARN of the JWT signing key secret"
  value       = aws_secretsmanager_secret.jwt.arn
}

output "jwt_secret_name" {
  description = "Name of the JWT signing key secret"
  value       = aws_secretsmanager_secret.jwt.name
}

# ============================================================================
# GitHub Actions OIDC
# ============================================================================

output "github_actions_role_arn" {
  description = "ARN of the IAM role for GitHub Actions OIDC"
  value       = aws_iam_role.github_actions.arn
}

output "github_oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider"
  value       = aws_iam_openid_connect_provider.github.arn
}
