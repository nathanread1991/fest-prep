# CDN Module Outputs

# ============================================================================
# CloudFront Distribution Outputs
# ============================================================================

output "distribution_id" {
  description = "ID of the CloudFront distribution"
  value       = aws_cloudfront_distribution.main.id
}

output "distribution_arn" {
  description = "ARN of the CloudFront distribution"
  value       = aws_cloudfront_distribution.main.arn
}

output "distribution_domain_name" {
  description = "Domain name of the CloudFront distribution"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "distribution_hosted_zone_id" {
  description = "Route 53 zone ID of the CloudFront distribution"
  value       = aws_cloudfront_distribution.main.hosted_zone_id
}

output "distribution_status" {
  description = "Current status of the CloudFront distribution"
  value       = aws_cloudfront_distribution.main.status
}

output "distribution_etag" {
  description = "ETag of the CloudFront distribution"
  value       = aws_cloudfront_distribution.main.etag
}

# ============================================================================
# Origin Access Identity Outputs
# ============================================================================

output "oai_id" {
  description = "ID of the CloudFront Origin Access Identity"
  value       = aws_cloudfront_origin_access_identity.s3_oai.id
}

output "oai_iam_arn" {
  description = "IAM ARN of the CloudFront Origin Access Identity"
  value       = aws_cloudfront_origin_access_identity.s3_oai.iam_arn
}

output "oai_cloudfront_access_identity_path" {
  description = "CloudFront access identity path for S3 bucket policy"
  value       = aws_cloudfront_origin_access_identity.s3_oai.cloudfront_access_identity_path
}

# ============================================================================
# Summary Output
# ============================================================================

output "cloudfront_summary" {
  description = "Summary of CloudFront distribution configuration"
  value = {
    distribution_id = aws_cloudfront_distribution.main.id
    domain_name     = aws_cloudfront_distribution.main.domain_name
    custom_domain   = var.domain_name
    status          = aws_cloudfront_distribution.main.status
    price_class     = var.price_class
    oai_id          = aws_cloudfront_origin_access_identity.s3_oai.id
  }
}
