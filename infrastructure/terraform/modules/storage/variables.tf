# Storage Module Variables

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "cloudfront_distribution_arn" {
  description = "ARN of the CloudFront distribution for bucket policy (optional, can be added later)"
  type        = string
  default     = null
}

variable "cloudfront_oai_iam_arn" {
  description = "IAM ARN of the CloudFront Origin Access Identity for S3 bucket policy"
  type        = string
  default     = null
}
