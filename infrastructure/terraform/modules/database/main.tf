# Database Module - Aurora Serverless v2 PostgreSQL
# This module creates the RDS Aurora Serverless v2 cluster with snapshot/restore capability

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

# Data source to get the latest snapshot (if exists)
data "aws_db_cluster_snapshot" "latest" {
  count                 = var.restore_from_snapshot ? 1 : 0
  db_cluster_identifier = "${var.project_name}-${var.environment}-aurora-cluster"
  most_recent           = true
  include_shared        = false
  include_public        = false
  snapshot_type         = "manual"
}

# KMS key for encryption at rest
resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption - ${var.project_name}-${var.environment}"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-rds-kms"
    }
  )
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${var.project_name}-${var.environment}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

# DB Subnet Group - uses private subnets
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-db-subnet-group"
    }
  )
}

# Random password for database master user
resource "random_password" "master_password" {
  length  = 32
  special = true
  # Exclude characters that might cause issues in connection strings
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Aurora Serverless v2 Cluster
resource "aws_rds_cluster" "main" {
  cluster_identifier = "${var.project_name}-${var.environment}-aurora-cluster"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = var.engine_version
  database_name      = var.database_name
  master_username    = var.master_username
  master_password    = random_password.master_password.result

  # Snapshot configuration
  snapshot_identifier       = var.restore_from_snapshot && length(data.aws_db_cluster_snapshot.latest) > 0 ? data.aws_db_cluster_snapshot.latest[0].id : var.snapshot_identifier
  final_snapshot_identifier = "${var.project_name}-${var.environment}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  skip_final_snapshot       = var.skip_final_snapshot

  # Network configuration
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.rds_security_group_id]
  port                   = 5432

  # Backup configuration
  backup_retention_period      = var.backup_retention_period
  preferred_backup_window      = var.preferred_backup_window
  preferred_maintenance_window = var.preferred_maintenance_window

  # Encryption
  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn

  # Serverless v2 scaling configuration
  serverlessv2_scaling_configuration {
    min_capacity = var.min_capacity
    max_capacity = var.max_capacity
  }

  # CloudWatch Logs exports
  enabled_cloudwatch_logs_exports = var.enabled_cloudwatch_logs_exports

  # Deletion protection (enabled for prod)
  deletion_protection = var.deletion_protection

  # Apply changes immediately (for dev environment)
  apply_immediately = var.apply_immediately

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-aurora-cluster"
    }
  )

  lifecycle {
    ignore_changes = [
      # Ignore snapshot_identifier after initial creation
      snapshot_identifier,
      # Ignore final_snapshot_identifier as it's dynamic
      final_snapshot_identifier,
    ]
  }
}

# Aurora Serverless v2 Instance
resource "aws_rds_cluster_instance" "main" {
  count              = var.instance_count
  identifier         = "${var.project_name}-${var.environment}-aurora-instance-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version

  # Performance Insights
  performance_insights_enabled          = var.enable_performance_insights
  performance_insights_kms_key_id       = var.enable_performance_insights ? aws_kms_key.rds.arn : null
  performance_insights_retention_period = var.enable_performance_insights ? var.performance_insights_retention_period : null

  # Monitoring
  monitoring_interval = var.monitoring_interval
  monitoring_role_arn = var.monitoring_interval > 0 ? aws_iam_role.rds_monitoring[0].arn : null

  # Auto minor version upgrade
  auto_minor_version_upgrade = var.auto_minor_version_upgrade

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-aurora-instance-${count.index + 1}"
    }
  )
}

# IAM role for enhanced monitoring
resource "aws_iam_role" "rds_monitoring" {
  count = var.monitoring_interval > 0 ? 1 : 0
  name  = "${var.project_name}-${var.environment}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-rds-monitoring-role"
    }
  )
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  count      = var.monitoring_interval > 0 ? 1 : 0
  role       = aws_iam_role.rds_monitoring[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}


# ============================================================================
# Secrets Manager - Database Credentials
# ============================================================================

# Secrets Manager secret for database credentials
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${var.project_name}-${var.environment}-db-credentials"
  description = "Database credentials for ${var.project_name} ${var.environment}"

  # KMS encryption
  kms_key_id = aws_kms_key.rds.id

  # Recovery window (0 for immediate deletion in dev, 30 for prod)
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-db-credentials"
    }
  )

  lifecycle {
    prevent_destroy = false
  }
}

# Secrets Manager secret version with database credentials
resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id

  secret_string = jsonencode({
    username            = aws_rds_cluster.main.master_username
    password            = random_password.master_password.result
    engine              = "postgres"
    host                = aws_rds_cluster.main.endpoint
    port                = aws_rds_cluster.main.port
    dbname              = aws_rds_cluster.main.database_name
    dbClusterIdentifier = aws_rds_cluster.main.cluster_identifier
    # Connection strings
    url      = "postgresql://${aws_rds_cluster.main.master_username}:${random_password.master_password.result}@${aws_rds_cluster.main.endpoint}:${aws_rds_cluster.main.port}/${aws_rds_cluster.main.database_name}"
    jdbc_url = "jdbc:postgresql://${aws_rds_cluster.main.endpoint}:${aws_rds_cluster.main.port}/${aws_rds_cluster.main.database_name}"
  })

  lifecycle {
    ignore_changes = [
      # Ignore changes to secret_string if rotation is enabled
      secret_string,
    ]
  }
}

# Optional: Secrets Manager rotation configuration
# Uncomment to enable automatic password rotation
# resource "aws_secretsmanager_secret_rotation" "db_credentials" {
#   count               = var.enable_secret_rotation ? 1 : 0
#   secret_id           = aws_secretsmanager_secret.db_credentials.id
#   rotation_lambda_arn = var.rotation_lambda_arn
#
#   rotation_rules {
#     automatically_after_days = var.rotation_days
#   }
# }


# ============================================================================
# CloudWatch Alarms - Database Monitoring
# ============================================================================

# SNS Topic for database alarms (if not provided)
resource "aws_sns_topic" "db_alarms" {
  count = var.alarm_sns_topic_arn == null ? 1 : 0
  name  = "${var.project_name}-${var.environment}-db-alarms"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-db-alarms"
    }
  )
}

# SNS Topic subscription for email notifications
resource "aws_sns_topic_subscription" "db_alarms_email" {
  count     = var.alarm_sns_topic_arn == null && length(var.alarm_email_addresses) > 0 ? length(var.alarm_email_addresses) : 0
  topic_arn = aws_sns_topic.db_alarms[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email_addresses[count.index]
}

# Local variable for SNS topic ARN
locals {
  alarm_topic_arn = var.alarm_sns_topic_arn != null ? var.alarm_sns_topic_arn : (length(aws_sns_topic.db_alarms) > 0 ? aws_sns_topic.db_alarms[0].arn : null)
}

# CPU Utilization Alarm
resource "aws_cloudwatch_metric_alarm" "cpu_utilization" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-rds-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = var.cpu_alarm_threshold
  alarm_description   = "RDS CPU utilization is above ${var.cpu_alarm_threshold}%"
  alarm_actions       = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []
  ok_actions          = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-rds-cpu-alarm"
    }
  )
}

# Database Connections Alarm
resource "aws_cloudwatch_metric_alarm" "database_connections" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-rds-connections-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = var.connections_alarm_threshold
  alarm_description   = "RDS database connections are above ${var.connections_alarm_threshold}"
  alarm_actions       = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []
  ok_actions          = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-rds-connections-alarm"
    }
  )
}

# Freeable Memory Alarm
resource "aws_cloudwatch_metric_alarm" "freeable_memory" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-rds-memory-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "FreeableMemory"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = var.memory_alarm_threshold
  alarm_description   = "RDS freeable memory is below ${var.memory_alarm_threshold} bytes"
  alarm_actions       = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []
  ok_actions          = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-rds-memory-alarm"
    }
  )
}

# Read Latency Alarm
resource "aws_cloudwatch_metric_alarm" "read_latency" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-rds-read-latency-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ReadLatency"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = var.read_latency_alarm_threshold
  alarm_description   = "RDS read latency is above ${var.read_latency_alarm_threshold} seconds"
  alarm_actions       = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []
  ok_actions          = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-rds-read-latency-alarm"
    }
  )
}

# Write Latency Alarm
resource "aws_cloudwatch_metric_alarm" "write_latency" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-rds-write-latency-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "WriteLatency"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = var.write_latency_alarm_threshold
  alarm_description   = "RDS write latency is above ${var.write_latency_alarm_threshold} seconds"
  alarm_actions       = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []
  ok_actions          = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-rds-write-latency-alarm"
    }
  )
}

# ACU Utilization Alarm (Serverless v2 specific)
resource "aws_cloudwatch_metric_alarm" "acu_utilization" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-rds-acu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ACUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = var.acu_alarm_threshold
  alarm_description   = "RDS ACU utilization is above ${var.acu_alarm_threshold}%"
  alarm_actions       = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []
  ok_actions          = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-rds-acu-alarm"
    }
  )
}
