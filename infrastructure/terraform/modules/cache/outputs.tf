# Outputs for Cache Module

# Replication Group Outputs
output "replication_group_id" {
  description = "ID of the ElastiCache replication group"
  value       = aws_elasticache_replication_group.main.id
}

output "replication_group_arn" {
  description = "ARN of the ElastiCache replication group"
  value       = aws_elasticache_replication_group.main.arn
}

output "primary_endpoint_address" {
  description = "Primary endpoint address for the Redis cluster"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "reader_endpoint_address" {
  description = "Reader endpoint address for the Redis cluster (if multi-node)"
  value       = aws_elasticache_replication_group.main.reader_endpoint_address
}

output "port" {
  description = "Port number for Redis"
  value       = aws_elasticache_replication_group.main.port
}

output "member_clusters" {
  description = "List of member cluster IDs"
  value       = aws_elasticache_replication_group.main.member_clusters
}

# Connection String Output
output "connection_string" {
  description = "Redis connection string"
  value       = try(var.transit_encryption_enabled && var.auth_token_enabled ? "rediss://:${random_password.auth_token[0].result}@${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}" : "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}", "")
  sensitive   = true
}

# AUTH Token Output
output "auth_token" {
  description = "Redis AUTH token (if enabled)"
  value       = var.transit_encryption_enabled && var.auth_token_enabled ? random_password.auth_token[0].result : null
  sensitive   = true
}

# Subnet Group Output
output "subnet_group_name" {
  description = "Name of the ElastiCache subnet group"
  value       = aws_elasticache_subnet_group.main.name
}

# Parameter Group Output
output "parameter_group_name" {
  description = "Name of the ElastiCache parameter group"
  value       = aws_elasticache_parameter_group.main.name
}

# CloudWatch Log Groups Outputs
output "slow_log_group_name" {
  description = "Name of the CloudWatch log group for slow logs"
  value       = aws_cloudwatch_log_group.redis_slow_log.name
}

output "engine_log_group_name" {
  description = "Name of the CloudWatch log group for engine logs"
  value       = aws_cloudwatch_log_group.redis_engine_log.name
}

# Secrets Manager Outputs
output "secret_arn" {
  description = "ARN of the Secrets Manager secret containing Redis connection URL"
  value       = aws_secretsmanager_secret.redis_url.arn
}

output "secret_id" {
  description = "ID of the Secrets Manager secret containing Redis connection URL"
  value       = aws_secretsmanager_secret.redis_url.id
}

output "secret_name" {
  description = "Name of the Secrets Manager secret containing Redis connection URL"
  value       = aws_secretsmanager_secret.redis_url.name
}

# CloudWatch Alarms Outputs
output "alarm_sns_topic_arn" {
  description = "ARN of the SNS topic for Redis alarms"
  value       = local.alarm_topic_arn
}

output "cpu_alarm_arn" {
  description = "ARN of the CPU utilization alarm"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.cpu_utilization[0].arn : null
}

output "memory_alarm_arn" {
  description = "ARN of the memory utilization alarm"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.memory_utilization[0].arn : null
}

output "evictions_alarm_arn" {
  description = "ARN of the evictions alarm"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.evictions[0].arn : null
}

output "connections_alarm_arn" {
  description = "ARN of the connections alarm"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.curr_connections[0].arn : null
}

output "replication_lag_alarm_arn" {
  description = "ARN of the replication lag alarm (if multi-node)"
  value       = var.enable_cloudwatch_alarms && var.num_cache_nodes > 1 ? aws_cloudwatch_metric_alarm.replication_lag[0].arn : null
}
