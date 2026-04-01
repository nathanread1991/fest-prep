# CDN Module - CloudFront Distribution
# This module creates a CloudFront distribution for the Festival Playlist Generator
# with origins for ALB (API traffic) and S3 (static assets)

terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = "~> 5.0"
      configuration_aliases = [aws, aws.us_east_1]
    }
  }
}

# ============================================================================
# CloudFront Origin Access Identity (OAI)
# ============================================================================

# Create OAI for S3 bucket access
resource "aws_cloudfront_origin_access_identity" "s3_oai" {
  comment = "${var.project_name}-${var.environment} S3 OAI for static assets"
}


# ============================================================================
# CloudFront Distribution
# ============================================================================

resource "aws_cloudfront_distribution" "main" {
  enabled         = true
  is_ipv6_enabled = true
  comment         = "${var.project_name}-${var.environment} CDN"
  price_class     = var.price_class
  http_version    = "http2and3"

  # Custom domain aliases
  aliases = var.domain_name != null ? [var.domain_name] : []

  # ============================================================================
  # Origin 1: Application Load Balancer (API traffic)
  # ============================================================================

  origin {
    domain_name = var.alb_dns_name
    origin_id   = "alb-origin"

    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "https-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 60
      origin_keepalive_timeout = 5
    }
  }

  # ============================================================================
  # Origin 2: S3 Bucket (static assets)
  # ============================================================================

  origin {
    domain_name = var.static_assets_bucket_regional_domain_name
    origin_id   = "s3-origin"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.s3_oai.cloudfront_access_identity_path
    }
  }

  # ============================================================================
  # Default Cache Behavior (forward to ALB, no caching)
  # ============================================================================

  default_cache_behavior {
    target_origin_id       = "alb-origin"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # No caching for API traffic - forward everything to ALB
    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0

    forwarded_values {
      query_string = true
      headers      = ["*"]

      cookies {
        forward = "all"
      }
    }
  }

  # ============================================================================
  # Cache Behavior: /static/* (S3 origin, 1 day TTL)
  # ============================================================================

  ordered_cache_behavior {
    path_pattern           = "/static/*"
    target_origin_id       = "alb-origin"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # Cache static assets for 1 day
    min_ttl     = 0
    default_ttl = 86400    # 1 day
    max_ttl     = 31536000 # 1 year

    forwarded_values {
      query_string = false
      headers      = ["Host"]

      cookies {
        forward = "none"
      }
    }
  }

  # ============================================================================
  # SSL/TLS Certificate Configuration
  # ============================================================================

  viewer_certificate {
    # Use ACM certificate if provided, otherwise use default CloudFront certificate
    acm_certificate_arn            = var.acm_certificate_arn
    ssl_support_method             = var.acm_certificate_arn != null ? "sni-only" : null
    minimum_protocol_version       = var.acm_certificate_arn != null ? "TLSv1.2_2021" : "TLSv1"
    cloudfront_default_certificate = var.acm_certificate_arn == null
  }

  # ============================================================================
  # Logging Configuration
  # ============================================================================

  logging_config {
    include_cookies = false
    bucket          = "${var.logs_bucket_name}.s3.amazonaws.com"
    prefix          = var.log_prefix
  }

  # ============================================================================
  # Restrictions
  # ============================================================================

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # ============================================================================
  # Tags
  # ============================================================================

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.project_name}-${var.environment}-cloudfront"
      Purpose = "CDN for API and static assets"
    }
  )
}
