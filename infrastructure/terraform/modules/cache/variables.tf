# Variables for Cache Module

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ElastiCache"
  type        = list(string)
}

variable "redis_security_group_id" {
  description = "Security group ID for Redis"
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# Redis Configuration
variable "engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

variable "node_type" {
  description = "ElastiCache node type (e.g., cache.t4g.micro, cache.t4g.small)"
  type        = string
  default     = "cache.t4g.micro"
}

variable "num_cache_nodes" {
  description = "Number of cache nodes (1 for dev, 2+ for prod multi-AZ)"
  type        = number
  default     = 1
}

# High Availability Configuration
variable "automatic_failover_enabled" {
  description = "Enable automatic failover (requires at least 2 nodes)"
  type        = bool
  default     = false
}

variable "multi_az_enabled" {
  description = "Enable Multi-AZ (requires at least 2 nodes)"
  type        = bool
  default     = false
}

# Backup Configuration
variable "snapshot_retention_limit" {
  description = "Number of days to retain snapshots (0 to disable)"
  type        = number
  default     = 1
}

variable "snapshot_window" {
  description = "Daily time range for snapshots (UTC)"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "Weekly maintenance window (UTC)"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot on destroy (set to false for prod)"
  type        = bool
  default     = false
}

# Encryption Configuration
variable "at_rest_encryption_enabled" {
  description = "Enable encryption at rest"
  type        = bool
  default     = true
}

variable "transit_encryption_enabled" {
  description = "Enable encryption in transit (TLS)"
  type        = bool
  default     = true
}

variable "auth_token_enabled" {
  description = "Enable AUTH token (requires transit encryption)"
  type        = bool
  default     = false
}

# Auto Minor Version Upgrade
variable "auto_minor_version_upgrade" {
  description = "Enable automatic minor version upgrades"
  type        = bool
  default     = true
}

# Apply Changes
variable "apply_immediately" {
  description = "Apply changes immediately (true for dev, false for prod)"
  type        = bool
  default     = true
}

# Notification Configuration
variable "notification_topic_arn" {
  description = "ARN of SNS topic for ElastiCache notifications"
  type        = string
  default     = null
}

# CloudWatch Logs Configuration
variable "log_retention_days" {
  description = "CloudWatch Logs retention period in days"
  type        = number
  default     = 7
}

# CloudWatch Alarms Configuration
variable "enable_cloudwatch_alarms" {
  description = "Enable CloudWatch alarms for Redis monitoring"
  type        = bool
  default     = true
}

variable "alarm_sns_topic_arn" {
  description = "ARN of existing SNS topic for alarms (creates new topic if null)"
  type        = string
  default     = null
}

variable "alarm_email_addresses" {
  description = "List of email addresses to receive alarm notifications"
  type        = list(string)
  default     = []
}

variable "cpu_alarm_threshold" {
  description = "CPU utilization threshold for alarm (percentage)"
  type        = number
  default     = 75
}

variable "memory_alarm_threshold" {
  description = "Memory utilization threshold for alarm (percentage)"
  type        = number
  default     = 90
}

variable "evictions_alarm_threshold" {
  description = "Evictions threshold for alarm (count per 5 minutes)"
  type        = number
  default     = 1000
}

variable "connections_alarm_threshold" {
  description = "Current connections threshold for alarm"
  type        = number
  default     = 65000
}

variable "replication_lag_alarm_threshold" {
  description = "Replication lag threshold for alarm (seconds)"
  type        = number
  default     = 30
}
