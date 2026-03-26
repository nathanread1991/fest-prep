# Outputs for Database Module

# Cluster Outputs
output "cluster_id" {
  description = "ID of the Aurora cluster"
  value       = aws_rds_cluster.main.id
}

output "cluster_arn" {
  description = "ARN of the Aurora cluster"
  value       = aws_rds_cluster.main.arn
}

output "cluster_endpoint" {
  description = "Writer endpoint for the Aurora cluster"
  value       = aws_rds_cluster.main.endpoint
}

output "cluster_reader_endpoint" {
  description = "Reader endpoint for the Aurora cluster"
  value       = aws_rds_cluster.main.reader_endpoint
}

output "cluster_port" {
  description = "Port of the Aurora cluster"
  value       = aws_rds_cluster.main.port
}

output "cluster_database_name" {
  description = "Name of the default database"
  value       = aws_rds_cluster.main.database_name
}

output "cluster_master_username" {
  description = "Master username for the database"
  value       = aws_rds_cluster.main.master_username
  sensitive   = true
}

output "cluster_master_password" {
  description = "Master password for the database"
  value       = random_password.master_password.result
  sensitive   = true
}

output "cluster_resource_id" {
  description = "Resource ID of the Aurora cluster"
  value       = aws_rds_cluster.main.cluster_resource_id
}

# Instance Outputs
output "instance_ids" {
  description = "IDs of the Aurora instances"
  value       = aws_rds_cluster_instance.main[*].id
}

output "instance_endpoints" {
  description = "Endpoints of the Aurora instances"
  value       = aws_rds_cluster_instance.main[*].endpoint
}

# Connection String Output
output "connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://${aws_rds_cluster.main.master_username}:${random_password.master_password.result}@${aws_rds_cluster.main.endpoint}:${aws_rds_cluster.main.port}/${aws_rds_cluster.main.database_name}"
  sensitive   = true
}

# KMS Key Outputs
output "kms_key_id" {
  description = "ID of the KMS key used for encryption"
  value       = aws_kms_key.rds.id
}

output "kms_key_arn" {
  description = "ARN of the KMS key used for encryption"
  value       = aws_kms_key.rds.arn
}

# Subnet Group Output
output "db_subnet_group_name" {
  description = "Name of the DB subnet group"
  value       = aws_db_subnet_group.main.name
}

# Monitoring Role Output
output "monitoring_role_arn" {
  description = "ARN of the enhanced monitoring IAM role"
  value       = var.monitoring_interval > 0 ? aws_iam_role.rds_monitoring[0].arn : null
}


# Secrets Manager Outputs
output "secret_arn" {
  description = "ARN of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "secret_id" {
  description = "ID of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.db_credentials.id
}

output "secret_name" {
  description = "Name of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.db_credentials.name
}


# CloudWatch Alarms Outputs
output "alarm_sns_topic_arn" {
  description = "ARN of the SNS topic for database alarms"
  value       = local.alarm_topic_arn
}

output "cpu_alarm_arn" {
  description = "ARN of the CPU utilization alarm"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.cpu_utilization[0].arn : null
}

output "connections_alarm_arn" {
  description = "ARN of the database connections alarm"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.database_connections[0].arn : null
}

output "memory_alarm_arn" {
  description = "ARN of the freeable memory alarm"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.freeable_memory[0].arn : null
}

output "read_latency_alarm_arn" {
  description = "ARN of the read latency alarm"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.read_latency[0].arn : null
}

output "write_latency_alarm_arn" {
  description = "ARN of the write latency alarm"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.write_latency[0].arn : null
}

output "acu_alarm_arn" {
  description = "ARN of the ACU utilization alarm"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.acu_utilization[0].arn : null
}
