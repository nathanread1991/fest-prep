# ============================================================================
# Outputs for Compute Module
# ============================================================================

# ============================================================================
# ECS Cluster Outputs
# ============================================================================

output "cluster_id" {
  description = "ID of the ECS cluster"
  value       = aws_ecs_cluster.main.id
}

output "cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.main.arn
}

output "cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

# ============================================================================
# IAM Role Outputs
# ============================================================================

output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution_role.arn
}

output "ecs_task_execution_role_name" {
  description = "Name of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution_role.name
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = aws_iam_role.ecs_task_role.arn
}

output "ecs_task_role_name" {
  description = "Name of the ECS task role"
  value       = aws_iam_role.ecs_task_role.name
}

# ============================================================================
# CloudWatch Log Groups Outputs
# ============================================================================

output "api_log_group_name" {
  description = "Name of the CloudWatch log group for API service"
  value       = aws_cloudwatch_log_group.api.name
}

output "api_log_group_arn" {
  description = "ARN of the CloudWatch log group for API service"
  value       = aws_cloudwatch_log_group.api.arn
}

output "worker_log_group_name" {
  description = "Name of the CloudWatch log group for worker service"
  value       = aws_cloudwatch_log_group.worker.name
}

output "worker_log_group_arn" {
  description = "ARN of the CloudWatch log group for worker service"
  value       = aws_cloudwatch_log_group.worker.arn
}

# ============================================================================
# ECS Task Definition Outputs
# ============================================================================

output "api_task_definition_arn" {
  description = "ARN of the API task definition"
  value       = aws_ecs_task_definition.api.arn
}

output "api_task_definition_family" {
  description = "Family of the API task definition"
  value       = aws_ecs_task_definition.api.family
}

output "api_task_definition_revision" {
  description = "Revision of the API task definition"
  value       = aws_ecs_task_definition.api.revision
}

output "worker_task_definition_arn" {
  description = "ARN of the worker task definition"
  value       = aws_ecs_task_definition.worker.arn
}

output "worker_task_definition_family" {
  description = "Family of the worker task definition"
  value       = aws_ecs_task_definition.worker.family
}

output "worker_task_definition_revision" {
  description = "Revision of the worker task definition"
  value       = aws_ecs_task_definition.worker.revision
}

# ============================================================================
# ECS Service Outputs
# ============================================================================

output "api_service_id" {
  description = "ID of the API ECS service"
  value       = aws_ecs_service.api.id
}

output "api_service_name" {
  description = "Name of the API ECS service"
  value       = aws_ecs_service.api.name
}

output "worker_service_id" {
  description = "ID of the worker ECS service"
  value       = aws_ecs_service.worker.id
}

output "worker_service_name" {
  description = "Name of the worker ECS service"
  value       = aws_ecs_service.worker.name
}

# ============================================================================
# Application Load Balancer Outputs
# ============================================================================

output "alb_id" {
  description = "ID of the Application Load Balancer"
  value       = aws_lb.main.id
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = aws_lb.main.arn
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Zone ID of the Application Load Balancer"
  value       = aws_lb.main.zone_id
}

output "alb_arn_suffix" {
  description = "ARN suffix of the Application Load Balancer (for CloudWatch metrics)"
  value       = aws_lb.main.arn_suffix
}

# ============================================================================
# Target Group Outputs
# ============================================================================

output "api_target_group_id" {
  description = "ID of the API target group"
  value       = aws_lb_target_group.api.id
}

output "api_target_group_arn" {
  description = "ARN of the API target group"
  value       = aws_lb_target_group.api.arn
}

output "api_target_group_name" {
  description = "Name of the API target group"
  value       = aws_lb_target_group.api.name
}

output "api_target_group_arn_suffix" {
  description = "ARN suffix of the API target group (for CloudWatch metrics)"
  value       = aws_lb_target_group.api.arn_suffix
}

# ============================================================================
# Listener Outputs
# ============================================================================

output "http_listener_arn" {
  description = "ARN of the HTTP listener"
  value       = aws_lb_listener.http.arn
}

output "https_listener_arn" {
  description = "ARN of the HTTPS listener (if enabled)"
  value       = var.enable_https_listener ? aws_lb_listener.https[0].arn : null
}

# ============================================================================
# Auto-Scaling Outputs
# ============================================================================

output "api_autoscaling_target_id" {
  description = "ID of the API auto-scaling target"
  value       = var.api_enable_auto_scaling ? aws_appautoscaling_target.api[0].id : null
}

output "api_cpu_autoscaling_policy_arn" {
  description = "ARN of the API CPU auto-scaling policy"
  value       = var.api_enable_auto_scaling ? aws_appautoscaling_policy.api_cpu[0].arn : null
}

output "api_memory_autoscaling_policy_arn" {
  description = "ARN of the API memory auto-scaling policy"
  value       = var.api_enable_auto_scaling ? aws_appautoscaling_policy.api_memory[0].arn : null
}

output "api_request_count_autoscaling_policy_arn" {
  description = "ARN of the API request count auto-scaling policy"
  value       = var.api_enable_auto_scaling ? aws_appautoscaling_policy.api_request_count[0].arn : null
}

# Worker Auto-Scaling Outputs

output "worker_autoscaling_target_id" {
  description = "ID of the worker auto-scaling target"
  value       = var.worker_enable_auto_scaling ? aws_appautoscaling_target.worker[0].id : null
}

output "worker_cpu_autoscaling_policy_arn" {
  description = "ARN of the worker CPU auto-scaling policy"
  value       = var.worker_enable_auto_scaling ? aws_appautoscaling_policy.worker_cpu[0].arn : null
}

output "worker_memory_autoscaling_policy_arn" {
  description = "ARN of the worker memory auto-scaling policy"
  value       = var.worker_enable_auto_scaling ? aws_appautoscaling_policy.worker_memory[0].arn : null
}

# ============================================================================
# Migration Task Outputs
# ============================================================================

output "migration_task_definition_arn" {
  description = "ARN of the migration task definition"
  value       = aws_ecs_task_definition.migration.arn
}

output "migration_task_definition_family" {
  description = "Family of the migration task definition"
  value       = aws_ecs_task_definition.migration.family
}

output "migration_log_group_name" {
  description = "Name of the CloudWatch log group for migration tasks"
  value       = aws_cloudwatch_log_group.migration.name
}
