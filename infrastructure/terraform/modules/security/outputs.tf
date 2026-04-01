# Security Module Outputs

# ============================================================================
# ACM Certificate Outputs
# ============================================================================

output "alb_certificate_arn" {
  description = "ARN of the ACM certificate for ALB (eu-west-2)"
  value       = aws_acm_certificate.alb.arn
}

output "alb_certificate_status" {
  description = "Status of the ALB certificate validation"
  value       = aws_acm_certificate.alb.status
}

output "cloudfront_certificate_arn" {
  description = "ARN of the ACM certificate for CloudFront (us-east-1)"
  value       = aws_acm_certificate.cloudfront.arn
}

output "cloudfront_certificate_status" {
  description = "Status of the CloudFront certificate validation"
  value       = aws_acm_certificate.cloudfront.status
}

# ============================================================================
# Route 53 Outputs
# ============================================================================

output "route53_zone_id" {
  description = "ID of the Route 53 hosted zone"
  value       = data.aws_route53_zone.main.zone_id
}

output "route53_zone_name" {
  description = "Name of the Route 53 hosted zone"
  value       = data.aws_route53_zone.main.name
}

output "route53_name_servers" {
  description = "Name servers for the Route 53 hosted zone"
  value       = data.aws_route53_zone.main.name_servers
}

# ============================================================================
# WAF Outputs
# ============================================================================

output "waf_web_acl_id" {
  description = "ID of the WAF Web ACL"
  value       = aws_wafv2_web_acl.alb.id
}

output "waf_web_acl_arn" {
  description = "ARN of the WAF Web ACL"
  value       = aws_wafv2_web_acl.alb.arn
}

output "waf_web_acl_capacity" {
  description = "Web ACL capacity units (WCUs) used by the WAF"
  value       = aws_wafv2_web_acl.alb.capacity
}

# ============================================================================
# Secrets Manager Outputs
# ============================================================================
# NOTE: Secrets Manager secrets have been moved to the persistent module.
# The ephemeral root reads their ARNs via terraform_remote_state.
# These outputs are kept as pass-through for backward compatibility with
# any code that references module.security.* secret outputs.
# They are no longer populated from this module.
