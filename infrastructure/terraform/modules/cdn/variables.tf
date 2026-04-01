# CDN Module Variables

# ============================================================================
# Required Variables
# ============================================================================

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  type        = string
}

variable "static_assets_bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket for static assets"
  type        = string
}

variable "logs_bucket_name" {
  description = "Name of the S3 bucket for CloudFront access logs"
  type        = string
}

# ============================================================================
# Optional Variables
# ============================================================================

variable "acm_certificate_arn" {
  description = "ARN of the ACM certificate for custom domain (must be in us-east-1)"
  type        = string
  default     = null
}

variable "domain_name" {
  description = "Custom domain name for the CloudFront distribution"
  type        = string
  default     = null
}

variable "price_class" {
  description = "CloudFront price class (PriceClass_All, PriceClass_200, PriceClass_100)"
  type        = string
  default     = "PriceClass_100" # Use only North America and Europe edge locations (cheapest)
}

variable "log_prefix" {
  description = "Prefix for CloudFront access logs in S3"
  type        = string
  default     = "cloudfront-logs/"
}

variable "custom_header_value" {
  description = "Value for custom header sent to ALB origin (for origin verification)"
  type        = string
  default     = "cloudfront-origin"
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
