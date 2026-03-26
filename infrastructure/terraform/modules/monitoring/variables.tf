# Variables for Monitoring Module

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

# CloudWatch Log Groups Configuration
variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 7
}

# ECS Configuration
variable "cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
}

variable "api_service_name" {
  description = "Name of the API ECS service"
  type        = string
}

variable "worker_service_name" {
  description = "Name of the worker ECS service"
  type        = string
}

# Database Configuration
variable "db_cluster_id" {
  description = "ID of the RDS cluster"
  type        = string
}

variable "db_max_connections" {
  description = "Maximum number of database connections"
  type        = number
  default     = 100
}

# Cache Configuration
variable "redis_cluster_id" {
  description = "ID of the ElastiCache Redis cluster"
  type        = string
}

# ALB Configuration
variable "alb_arn_suffix" {
  description = "ARN suffix of the Application Load Balancer"
  type        = string
}

variable "target_group_arn_suffix" {
  description = "ARN suffix of the ALB target group"
  type        = string
}

# Alarm Configuration
variable "alert_email" {
  description = "Email address for alarm notifications"
  type        = string
}

variable "enable_alarms" {
  description = "Enable CloudWatch alarms"
  type        = bool
  default     = true
}

# API Alarm Thresholds
variable "api_error_rate_threshold" {
  description = "Threshold for API 5XX error count in 5 minutes"
  type        = number
  default     = 10
}

variable "api_latency_threshold" {
  description = "Threshold for API p95 latency in milliseconds"
  type        = number
  default     = 1000
}

# Database Alarm Thresholds
variable "db_cpu_threshold" {
  description = "Threshold for RDS CPU utilization percentage"
  type        = number
  default     = 80
}

variable "db_connections_threshold_percent" {
  description = "Threshold for RDS connections as percentage of max"
  type        = number
  default     = 80
}

# ECS Alarm Thresholds
variable "ecs_min_task_count" {
  description = "Minimum number of ECS tasks (alarm if below)"
  type        = number
  default     = 1
}

# X-Ray Configuration
variable "enable_xray" {
  description = "Enable AWS X-Ray tracing"
  type        = bool
  default     = true
}

variable "xray_sampling_rate" {
  description = "X-Ray sampling rate (0.0 to 1.0)"
  type        = number
  default     = 0.1
}

# Dashboard Configuration
variable "enable_dashboard" {
  description = "Enable CloudWatch dashboard"
  type        = bool
  default     = true
}
