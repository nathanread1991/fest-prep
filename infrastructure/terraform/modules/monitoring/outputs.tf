# Outputs for Monitoring Module

# CloudWatch Log Groups
output "log_group_api_name" {
  description = "Name of the CloudWatch log group for API service"
  value       = aws_cloudwatch_log_group.api.name
}

output "log_group_api_arn" {
  description = "ARN of the CloudWatch log group for API service"
  value       = aws_cloudwatch_log_group.api.arn
}

output "log_group_worker_name" {
  description = "Name of the CloudWatch log group for worker service"
  value       = aws_cloudwatch_log_group.worker.name
}

output "log_group_worker_arn" {
  description = "ARN of the CloudWatch log group for worker service"
  value       = aws_cloudwatch_log_group.worker.arn
}

# SNS Topic
output "sns_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications"
  value       = aws_sns_topic.alarms.arn
}

output "sns_topic_name" {
  description = "Name of the SNS topic for alarm notifications"
  value       = aws_sns_topic.alarms.name
}

# CloudWatch Alarms
output "api_5xx_alarm_arn" {
  description = "ARN of the API 5XX errors alarm"
  value       = var.enable_alarms ? aws_cloudwatch_metric_alarm.api_5xx_errors[0].arn : null
}

output "api_latency_alarm_arn" {
  description = "ARN of the API latency alarm"
  value       = var.enable_alarms ? aws_cloudwatch_metric_alarm.api_latency[0].arn : null
}

output "rds_cpu_alarm_arn" {
  description = "ARN of the RDS CPU alarm"
  value       = var.enable_alarms ? aws_cloudwatch_metric_alarm.rds_cpu[0].arn : null
}

output "rds_connections_alarm_arn" {
  description = "ARN of the RDS connections alarm"
  value       = var.enable_alarms ? aws_cloudwatch_metric_alarm.rds_connections[0].arn : null
}

output "ecs_task_count_alarm_arn" {
  description = "ARN of the ECS task count alarm"
  value       = var.enable_alarms ? aws_cloudwatch_metric_alarm.ecs_task_count[0].arn : null
}

output "ecs_api_cpu_high_alarm_arn" {
  description = "ARN of the ECS API high-CPU alarm"
  value       = var.enable_alarms ? aws_cloudwatch_metric_alarm.ecs_api_cpu_high[0].arn : null
}

output "ecs_api_memory_high_alarm_arn" {
  description = "ARN of the ECS API high-memory alarm"
  value       = var.enable_alarms ? aws_cloudwatch_metric_alarm.ecs_api_memory_high[0].arn : null
}

output "ecs_worker_task_count_alarm_arn" {
  description = "ARN of the ECS worker task count alarm"
  value       = var.enable_alarms && var.worker_service_name != "" ? aws_cloudwatch_metric_alarm.ecs_worker_task_count[0].arn : null
}

# CloudWatch Dashboard
output "dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = var.enable_dashboard ? aws_cloudwatch_dashboard.main[0].dashboard_name : null
}

output "dashboard_arn" {
  description = "ARN of the CloudWatch dashboard"
  value       = var.enable_dashboard ? aws_cloudwatch_dashboard.main[0].dashboard_arn : null
}

# X-Ray Sampling Rules
output "xray_default_sampling_rule_arn" {
  description = "ARN of the default X-Ray sampling rule"
  value       = var.enable_xray ? aws_xray_sampling_rule.default[0].arn : null
}

output "xray_errors_sampling_rule_arn" {
  description = "ARN of the errors X-Ray sampling rule"
  value       = var.enable_xray ? aws_xray_sampling_rule.errors[0].arn : null
}

# KMS Key
output "kms_key_id" {
  description = "ID of the KMS key for SNS encryption"
  value       = aws_kms_key.sns.id
}

output "kms_key_arn" {
  description = "ARN of the KMS key for SNS encryption"
  value       = aws_kms_key.sns.arn
}

# CloudWatch Logs Insights Queries
output "slow_queries_query_id" {
  description = "ID of the CloudWatch Logs Insights saved query for slow DB queries"
  value       = aws_cloudwatch_query_definition.slow_queries.query_definition_id
}

output "query_performance_query_id" {
  description = "ID of the CloudWatch Logs Insights saved query for DB query performance"
  value       = aws_cloudwatch_query_definition.query_performance.query_definition_id
}
