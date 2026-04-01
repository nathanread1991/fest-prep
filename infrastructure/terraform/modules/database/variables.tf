# Variables for Database Module

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for RDS"
  type        = list(string)
}

variable "rds_security_group_id" {
  description = "Security group ID for RDS"
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# Database Configuration
variable "database_name" {
  description = "Name of the default database"
  type        = string
  default     = "festival_playlist"
}

variable "master_username" {
  description = "Master username for the database"
  type        = string
  default     = "festival_admin"
}

variable "engine_version" {
  description = "Aurora PostgreSQL engine version"
  type        = string
  default     = "15.3"
}

# Serverless v2 Scaling Configuration
variable "min_capacity" {
  description = "Minimum ACU capacity for Aurora Serverless v2"
  type        = number
  default     = 0.5
}

variable "max_capacity" {
  description = "Maximum ACU capacity for Aurora Serverless v2"
  type        = number
  default     = 4
}

# Instance Configuration
variable "instance_count" {
  description = "Number of Aurora instances (1 for dev, 2+ for prod multi-AZ)"
  type        = number
  default     = 1
}

# Backup Configuration
variable "backup_retention_period" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7
}

variable "preferred_backup_window" {
  description = "Preferred backup window (UTC)"
  type        = string
  default     = "03:00-04:00"
}

variable "preferred_maintenance_window" {
  description = "Preferred maintenance window (UTC)"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

# Snapshot Configuration
variable "restore_from_snapshot" {
  description = "Whether to restore from the latest snapshot"
  type        = bool
  default     = false
}

variable "snapshot_identifier" {
  description = "Specific snapshot identifier to restore from (optional)"
  type        = string
  default     = null
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot on destroy (set to false for prod)"
  type        = bool
  default     = false
}

# CloudWatch Logs
variable "enabled_cloudwatch_logs_exports" {
  description = "List of log types to export to CloudWatch"
  type        = list(string)
  default     = ["postgresql"]
}

# Performance Insights
variable "enable_performance_insights" {
  description = "Enable Performance Insights"
  type        = bool
  default     = true
}

variable "performance_insights_retention_period" {
  description = "Performance Insights retention period in days"
  type        = number
  default     = 7
}

# Monitoring
variable "monitoring_interval" {
  description = "Enhanced monitoring interval in seconds (0 to disable, 1, 5, 10, 15, 30, 60)"
  type        = number
  default     = 60
}

# Deletion Protection
variable "deletion_protection" {
  description = "Enable deletion protection (recommended for prod)"
  type        = bool
  default     = true
}

# Apply Changes
variable "apply_immediately" {
  description = "Apply changes immediately (true for dev, false for prod)"
  type        = bool
  default     = true
}

# Auto Minor Version Upgrade
variable "auto_minor_version_upgrade" {
  description = "Enable automatic minor version upgrades"
  type        = bool
  default     = true
}


# CloudWatch Alarms Configuration
variable "enable_cloudwatch_alarms" {
  description = "Enable CloudWatch alarms for database monitoring"
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
  default     = 80
}

variable "connections_alarm_threshold" {
  description = "Database connections threshold for alarm"
  type        = number
  default     = 80
}

variable "memory_alarm_threshold" {
  description = "Freeable memory threshold for alarm (bytes)"
  type        = number
  default     = 268435456 # 256 MB
}

variable "read_latency_alarm_threshold" {
  description = "Read latency threshold for alarm (seconds)"
  type        = number
  default     = 0.1 # 100ms
}

variable "write_latency_alarm_threshold" {
  description = "Write latency threshold for alarm (seconds)"
  type        = number
  default     = 0.1 # 100ms
}

variable "acu_alarm_threshold" {
  description = "ACU utilization threshold for alarm (percentage)"
  type        = number
  default     = 90
}
