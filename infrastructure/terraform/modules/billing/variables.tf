# Variables for Billing Module

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "festival-playlist"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "monthly_budget_limit" {
  description = "Monthly budget limit in USD"
  type        = string
  default     = "30"
}

variable "alert_email_addresses" {
  description = "List of email addresses to receive budget alerts"
  type        = list(string)
}

variable "anomaly_threshold" {
  description = "Minimum dollar amount for anomaly detection alerts"
  type        = string
  default     = "5"
}

variable "enable_encryption" {
  description = "Enable KMS encryption for SNS topic"
  type        = bool
  default     = false
}

variable "enable_anomaly_detection" {
  description = "Enable Cost Anomaly Detection (may fail if limit exceeded)"
  type        = bool
  default     = true
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
