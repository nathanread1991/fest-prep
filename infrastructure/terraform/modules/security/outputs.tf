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
# Summary Outputs
# ============================================================================

output "secrets_summary" {
  description = "Summary of all secrets created"
  value = {
    spotify = {
      arn  = aws_secretsmanager_secret.spotify.arn
      name = aws_secretsmanager_secret.spotify.name
    }
    setlistfm = {
      arn  = aws_secretsmanager_secret.setlistfm.arn
      name = aws_secretsmanager_secret.setlistfm.name
    }
    jwt = {
      arn  = aws_secretsmanager_secret.jwt.arn
      name = aws_secretsmanager_secret.jwt.name
    }
  }
}

output "certificates_summary" {
  description = "Summary of all certificates created"
  value = {
    alb = {
      arn    = aws_acm_certificate.alb.arn
      status = aws_acm_certificate.alb.status
      region = "eu-west-2"
    }
    cloudfront = {
      arn    = aws_acm_certificate.cloudfront.arn
      status = aws_acm_certificate.cloudfront.status
      region = "us-east-1"
    }
  }
}
