# ============================================================================
# Variables for Compute Module
# ============================================================================

# ============================================================================
# General Variables
# ============================================================================

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

# ============================================================================
# ECS Cluster Variables
# ============================================================================

variable "enable_container_insights" {
  description = "Enable CloudWatch Container Insights for the ECS cluster"
  type        = bool
  default     = true
}

# ============================================================================
# Networking Variables
# ============================================================================

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs for ECS tasks and ALB"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs (for future use)"
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "ID of the ALB security group"
  type        = string
}

variable "ecs_tasks_security_group_id" {
  description = "ID of the ECS tasks security group"
  type        = string
}

# ============================================================================
# IAM Variables
# ============================================================================

variable "secrets_arns" {
  description = "List of Secrets Manager secret ARNs that ECS tasks need access to"
  type        = list(string)
}

variable "app_data_bucket_arn" {
  description = "ARN of the S3 bucket for application data"
  type        = string
}

variable "allow_task_role_secrets_access" {
  description = "Allow ECS task role to read secrets at runtime (in addition to execution role)"
  type        = bool
  default     = false
}

# ============================================================================
# ECR Variables
# ============================================================================

variable "ecr_repository_url" {
  description = "URL of the ECR repository containing the application image"
  type        = string
}

variable "api_image_tag" {
  description = "Tag of the Docker image to use for the API service"
  type        = string
  default     = "latest"
}

variable "worker_image_tag" {
  description = "Tag of the Docker image to use for the worker service"
  type        = string
  default     = "latest"
}

# ============================================================================
# ECS Task Definition Variables - API Service
# ============================================================================

variable "api_cpu" {
  description = "CPU units for API task (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "api_memory" {
  description = "Memory for API task in MB"
  type        = number
  default     = 512
}

variable "api_container_port" {
  description = "Port the API container listens on"
  type        = number
  default     = 8000
}

variable "api_health_check_path" {
  description = "Health check path for API service"
  type        = string
  default     = "/health"
}

variable "api_health_check_interval" {
  description = "Health check interval in seconds"
  type        = number
  default     = 30
}

variable "api_health_check_timeout" {
  description = "Health check timeout in seconds"
  type        = number
  default     = 10
}

variable "api_health_check_healthy_threshold" {
  description = "Number of consecutive successful health checks required"
  type        = number
  default     = 2
}

variable "api_health_check_unhealthy_threshold" {
  description = "Number of consecutive failed health checks required"
  type        = number
  default     = 3
}

variable "api_environment_variables" {
  description = "Environment variables for API container"
  type        = map(string)
  default     = {}
}

# ============================================================================
# ECS Task Definition Variables - Worker Service
# ============================================================================

variable "worker_cpu" {
  description = "CPU units for worker task (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "worker_memory" {
  description = "Memory for worker task in MB"
  type        = number
  default     = 512
}

variable "worker_environment_variables" {
  description = "Environment variables for worker container"
  type        = map(string)
  default     = {}
}

# ============================================================================
# CloudWatch Logs Variables
# ============================================================================

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 7
}

# ============================================================================
# ECS Service Variables - API
# ============================================================================

variable "api_desired_count" {
  description = "Desired number of API tasks"
  type        = number
  default     = 1
}

variable "api_health_check_grace_period" {
  description = "Seconds to wait before ECS starts health checking a newly launched task"
  type        = number
  default     = 120
}

variable "api_min_capacity" {
  description = "Minimum number of API tasks for auto-scaling"
  type        = number
  default     = 1
}

variable "api_max_capacity" {
  description = "Maximum number of API tasks for auto-scaling"
  type        = number
  default     = 4
}

variable "api_cpu_target" {
  description = "Target CPU utilization percentage for API auto-scaling"
  type        = number
  default     = 70
}

variable "api_memory_target" {
  description = "Target memory utilization percentage for API auto-scaling"
  type        = number
  default     = 80
}

variable "api_enable_auto_scaling" {
  description = "Enable auto-scaling for API service"
  type        = bool
  default     = true
}

# ============================================================================
# ECS Service Variables - Worker
# ============================================================================

variable "worker_desired_count" {
  description = "Desired number of worker tasks"
  type        = number
  default     = 1
}

variable "worker_min_capacity" {
  description = "Minimum number of worker tasks for auto-scaling"
  type        = number
  default     = 0
}

variable "worker_max_capacity" {
  description = "Maximum number of worker tasks for auto-scaling"
  type        = number
  default     = 2
}

variable "worker_enable_auto_scaling" {
  description = "Enable auto-scaling for worker service"
  type        = bool
  default     = false
}

variable "worker_use_spot" {
  description = "Use FARGATE_SPOT for worker tasks (70% cost savings)"
  type        = bool
  default     = true
}

variable "worker_cpu_target" {
  description = "Target CPU utilization percentage for worker auto-scaling"
  type        = number
  default     = 70
}

variable "worker_memory_target" {
  description = "Target memory utilization percentage for worker auto-scaling"
  type        = number
  default     = 80
}

variable "api_request_count_target" {
  description = "Target ALB request count per target for API auto-scaling"
  type        = number
  default     = 1000
}

# ============================================================================
# Application Load Balancer Variables
# ============================================================================

variable "alb_name" {
  description = "Name of the Application Load Balancer"
  type        = string
  default     = null
}

variable "alb_internal" {
  description = "Whether the ALB is internal or internet-facing"
  type        = bool
  default     = false
}

variable "alb_enable_deletion_protection" {
  description = "Enable deletion protection for ALB"
  type        = bool
  default     = false
}

variable "alb_enable_http2" {
  description = "Enable HTTP/2 on the ALB"
  type        = bool
  default     = true
}

variable "alb_enable_cross_zone_load_balancing" {
  description = "Enable cross-zone load balancing"
  type        = bool
  default     = true
}

variable "alb_idle_timeout" {
  description = "Idle timeout for ALB connections in seconds"
  type        = number
  default     = 60
}

variable "alb_deregistration_delay" {
  description = "Time to wait before deregistering targets in seconds"
  type        = number
  default     = 30
}

variable "alb_enable_access_logs" {
  description = "Enable ALB access logs to S3"
  type        = bool
  default     = false
}

variable "alb_access_logs_bucket" {
  description = "S3 bucket name for ALB access logs"
  type        = string
  default     = ""
}

variable "alb_access_logs_prefix" {
  description = "S3 prefix for ALB access logs"
  type        = string
  default     = "alb"
}

# ============================================================================
# SSL/TLS Variables
# ============================================================================

variable "acm_certificate_arn" {
  description = "ARN of the ACM certificate for HTTPS listener (optional for initial setup)"
  type        = string
  default     = ""
}

variable "enable_https_listener" {
  description = "Enable HTTPS listener on ALB (requires ACM certificate)"
  type        = bool
  default     = false
}

variable "ssl_policy" {
  description = "SSL policy for HTTPS listener"
  type        = string
  default     = "ELBSecurityPolicy-TLS13-1-2-2021-06"
}

# ============================================================================
# Secret References
# ============================================================================

variable "db_secret_arn" {
  description = "ARN of the Secrets Manager secret containing database credentials"
  type        = string
}

variable "redis_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Redis connection URL"
  type        = string
}

variable "spotify_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Spotify API credentials"
  type        = string
  default     = ""
}

variable "jwt_secret_arn" {
  description = "ARN of the Secrets Manager secret containing JWT signing key"
  type        = string
  default     = ""
}

variable "setlistfm_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Setlist.fm API key"
  type        = string
  default     = ""
}

