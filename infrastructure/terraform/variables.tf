# Variables for Festival Playlist Generator Terraform Configuration

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "eu-west-2"
}

variable "aws_profile" {
  description = "AWS CLI profile to use for authentication"
  type        = string
  default     = "festival-playlist"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "festival-playlist"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
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
  description = "Enable Cost Anomaly Detection (disable if limit exceeded)"
  type        = bool
  default     = true
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "festival-playlist"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}

# Domain Configuration
variable "domain_name" {
  description = "Custom domain name for the application"
  type        = string
  default     = "gig-prep.co.uk"
}

# Database Configuration
variable "database_name" {
  description = "Name of the database"
  type        = string
  default     = "festival_playlist"
}

variable "database_master_username" {
  description = "Master username for the database"
  type        = string
  default     = "festival_admin"
}

variable "database_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15.3"
}

variable "database_min_capacity" {
  description = "Minimum ACU capacity for Aurora Serverless v2"
  type        = number
  default     = 0.5
}

variable "database_max_capacity" {
  description = "Maximum ACU capacity for Aurora Serverless v2"
  type        = number
  default     = 2
}

variable "database_backup_retention_period" {
  description = "Number of days to retain database backups"
  type        = number
  default     = 7
}

variable "database_restore_from_snapshot" {
  description = "Whether to restore database from latest snapshot"
  type        = bool
  default     = false
}

# Redis Configuration
variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t4g.micro"
}

variable "redis_parameter_group_family" {
  description = "Redis parameter group family"
  type        = string
  default     = "redis7"
}

variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

# ECS Configuration
variable "ecs_api_cpu" {
  description = "CPU units for API task (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "ecs_api_memory" {
  description = "Memory for API task in MB"
  type        = number
  default     = 512
}

variable "ecs_api_desired_count" {
  description = "Desired number of API tasks"
  type        = number
  default     = 1
}

variable "ecs_api_min_capacity" {
  description = "Minimum number of API tasks for auto-scaling"
  type        = number
  default     = 1
}

variable "ecs_api_max_capacity" {
  description = "Maximum number of API tasks for auto-scaling"
  type        = number
  default     = 4
}

variable "ecs_worker_cpu" {
  description = "CPU units for worker task (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "ecs_worker_memory" {
  description = "Memory for worker task in MB"
  type        = number
  default     = 512
}

variable "ecs_worker_desired_count" {
  description = "Desired number of worker tasks"
  type        = number
  default     = 1
}

# WAF Configuration
variable "enable_waf" {
  description = "Enable AWS WAF for ALB protection"
  type        = bool
  default     = true
}

variable "waf_rate_limit" {
  description = "Rate limit for WAF (requests per 5 minutes per IP)"
  type        = number
  default     = 1000
}

# CloudWatch Configuration
variable "cloudwatch_log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 7
}
