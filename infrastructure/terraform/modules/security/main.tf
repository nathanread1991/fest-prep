# Security Module - ACM, Route 53, WAF, Secrets Manager
# This module manages security-related resources for the Festival Playlist Generator

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = "~> 5.0"
      configuration_aliases = [aws.us_east_1]
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

# ============================================================================
# ACM Certificate for Custom Domain
# ============================================================================

# ACM certificate for ALB (in primary region eu-west-2)
resource "aws_acm_certificate" "alb" {
  domain_name               = var.domain_name
  subject_alternative_names = ["*.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-alb-cert"
    }
  )
}

# ACM certificate for CloudFront (must be in us-east-1)
resource "aws_acm_certificate" "cloudfront" {
  provider                  = aws.us_east_1
  domain_name               = var.domain_name
  subject_alternative_names = ["*.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-cloudfront-cert"
    }
  )
}

# ============================================================================
# Route 53 Hosted Zone and DNS Records
# ============================================================================

# Look up existing Route 53 hosted zone (created when domain was purchased)
data "aws_route53_zone" "main" {
  name         = var.domain_name
  private_zone = false
}

# DNS validation records for ALB certificate
resource "aws_route53_record" "alb_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.alb.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main.zone_id
}

# DNS validation records for CloudFront certificate
resource "aws_route53_record" "cloudfront_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.cloudfront.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main.zone_id
}

# Wait for ALB certificate validation
resource "aws_acm_certificate_validation" "alb" {
  certificate_arn         = aws_acm_certificate.alb.arn
  validation_record_fqdns = [for record in aws_route53_record.alb_cert_validation : record.fqdn]
}

# Wait for CloudFront certificate validation
resource "aws_acm_certificate_validation" "cloudfront" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.cloudfront.arn
  validation_record_fqdns = [for record in aws_route53_record.cloudfront_cert_validation : record.fqdn]
}

# A record for root domain pointing to CloudFront (will be created in CDN module)
# Placeholder comment - actual record created when CloudFront distribution exists

# A record for API subdomain pointing to ALB (will be created in compute module)
# Placeholder comment - actual record created when ALB exists

# ============================================================================
# AWS WAF for ALB Protection
# ============================================================================

# WAF Web ACL for ALB protection
resource "aws_wafv2_web_acl" "alb" {
  name        = "${var.project_name}-${var.environment}-alb-waf"
  description = "WAF rules for ALB protection"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # Rate limiting rule - 1000 requests per 5 minutes per IP
  rule {
    name     = "rate-limit"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 1000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-${var.environment}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  # AWS Managed Rules - Core Rule Set (SQL injection, XSS, etc.)
  rule {
    name     = "aws-managed-core-rules"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-${var.environment}-core-rules"
      sampled_requests_enabled   = true
    }
  }

  # AWS Managed Rules - Known Bad Inputs
  rule {
    name     = "aws-managed-known-bad-inputs"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-${var.environment}-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  # AWS Managed Rules - SQL Database Protection
  rule {
    name     = "aws-managed-sql-database"
    priority = 4

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-${var.environment}-sql-protection"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.project_name}-${var.environment}-waf"
    sampled_requests_enabled   = true
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-alb-waf"
    }
  )
}

# Associate WAF with ALB
resource "aws_wafv2_web_acl_association" "alb" {
  count        = var.enable_waf_alb_association ? 1 : 0
  resource_arn = var.alb_arn
  web_acl_arn  = aws_wafv2_web_acl.alb.arn
}

# CloudWatch Log Group for WAF logs
resource "aws_cloudwatch_log_group" "waf" {
  name              = "/aws/waf/${var.project_name}-${var.environment}"
  retention_in_days = var.environment == "prod" ? 30 : 7

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-waf-logs"
    }
  )
}

# WAF logging configuration
resource "aws_wafv2_web_acl_logging_configuration" "alb" {
  resource_arn            = aws_wafv2_web_acl.alb.arn
  log_destination_configs = ["${aws_cloudwatch_log_group.waf.arn}:*"]
}

# ============================================================================
# AWS Secrets Manager - Application Secrets
# ============================================================================

# Generate random JWT signing key
resource "random_password" "jwt_secret" {
  length  = 64
  special = true
}

# Spotify API credentials secret (manual population required)
resource "aws_secretsmanager_secret" "spotify" {
  name        = "${var.project_name}-${var.environment}-spotify-credentials"
  description = "Spotify API credentials (client_id, client_secret)"

  recovery_window_in_days = 7

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-spotify"
    }
  )

  lifecycle {
    prevent_destroy = true
  }
}

# Spotify secret version with placeholder (requires manual update)
resource "aws_secretsmanager_secret_version" "spotify" {
  secret_id = aws_secretsmanager_secret.spotify.id
  secret_string = jsonencode({
    client_id     = "REPLACE_WITH_SPOTIFY_CLIENT_ID"
    client_secret = "REPLACE_WITH_SPOTIFY_CLIENT_SECRET"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Setlist.fm API key secret (manual population required)
resource "aws_secretsmanager_secret" "setlistfm" {
  name        = "${var.project_name}-${var.environment}-setlistfm-api-key"
  description = "Setlist.fm API key"

  recovery_window_in_days = 7

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-setlistfm"
    }
  )

  lifecycle {
    prevent_destroy = true
  }
}

# Setlist.fm secret version with placeholder (requires manual update)
resource "aws_secretsmanager_secret_version" "setlistfm" {
  secret_id = aws_secretsmanager_secret.setlistfm.id
  secret_string = jsonencode({
    api_key = "REPLACE_WITH_SETLISTFM_API_KEY"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# JWT signing key secret (auto-generated)
resource "aws_secretsmanager_secret" "jwt" {
  name        = "${var.project_name}-${var.environment}-jwt-secret"
  description = "JWT signing key for authentication"

  recovery_window_in_days = 7

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-jwt"
    }
  )

  lifecycle {
    prevent_destroy = true
  }
}

# JWT secret version with auto-generated key
resource "aws_secretsmanager_secret_version" "jwt" {
  secret_id = aws_secretsmanager_secret.jwt.id
  secret_string = jsonencode({
    secret_key = random_password.jwt_secret.result
  })
}
