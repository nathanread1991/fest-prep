# Security Module Variables

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "domain_name" {
  description = "Custom domain name (e.g., gig-prep.co.uk)"
  type        = string
}

variable "alb_arn" {
  description = "ARN of the Application Load Balancer to associate with WAF"
  type        = string
  default     = ""
}

variable "enable_waf_alb_association" {
  description = "Whether to associate WAF with ALB (set to true after ALB is created)"
  type        = bool
  default     = true
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
