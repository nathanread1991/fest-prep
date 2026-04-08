# Cache Module - ElastiCache Redis
# This module creates the ElastiCache Redis cluster for caching and session management

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

# ElastiCache Subnet Group - uses private subnets
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-redis-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-subnet-group"
    }
  )
}

# ElastiCache Parameter Group for Redis 7.0
resource "aws_elasticache_parameter_group" "main" {
  name   = "${var.project_name}-${var.environment}-redis-params"
  family = "redis7"

  # Set maxmemory-policy to allkeys-lru (evict any key using LRU when memory is full)
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  # Enable cluster mode compatibility (optional, for future scaling)
  parameter {
    name  = "cluster-enabled"
    value = "no"
  }

  # Timeout for idle connections (5 minutes)
  parameter {
    name  = "timeout"
    value = "300"
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-params"
    }
  )
}

# ElastiCache Replication Group (Redis Cluster)
resource "aws_elasticache_replication_group" "main" {
  #checkov:skip=CKV_AWS_191:Redis 7.0 is the target version
  #checkov:skip=CKV_AWS_31:Transit encryption enabled via variable
  #checkov:skip=CKV_AWS_30:At-rest encryption enabled via variable
  #checkov:skip=CKV2_AWS_50:auto_minor_version_upgrade enabled via variable
  replication_group_id = "${var.project_name}-${var.environment}-redis"
  description          = "Redis cluster for ${var.project_name} ${var.environment}"

  # Engine configuration
  engine               = "redis"
  engine_version       = var.engine_version
  parameter_group_name = aws_elasticache_parameter_group.main.name

  # Node configuration
  node_type          = var.node_type
  num_cache_clusters = var.num_cache_nodes
  port               = 6379

  # Pin to eu-west-2a to avoid AZ capacity issues with t4g.micro
  preferred_cache_cluster_azs = [for _ in range(var.num_cache_nodes) : var.preferred_availability_zone]

  # Network configuration
  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [var.redis_security_group_id]

  # Automatic failover (requires at least 2 nodes)
  automatic_failover_enabled = var.num_cache_nodes > 1 ? var.automatic_failover_enabled : false
  multi_az_enabled           = var.num_cache_nodes > 1 ? var.multi_az_enabled : false

  # Backup configuration
  snapshot_retention_limit  = var.snapshot_retention_limit
  snapshot_window           = var.snapshot_window
  maintenance_window        = var.maintenance_window
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.project_name}-${var.environment}-redis-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  # Encryption
  at_rest_encryption_enabled = var.at_rest_encryption_enabled
  transit_encryption_enabled = var.transit_encryption_enabled
  auth_token                 = var.transit_encryption_enabled && var.auth_token_enabled ? random_password.auth_token[0].result : null

  # Auto minor version upgrade
  auto_minor_version_upgrade = var.auto_minor_version_upgrade

  # Apply changes immediately (for dev environment)
  apply_immediately = var.apply_immediately

  # Notification configuration
  notification_topic_arn = var.notification_topic_arn

  # CloudWatch Logs
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_engine_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "engine-log"
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-redis"
    }
  )

  lifecycle {
    ignore_changes = [
      # Ignore final_snapshot_identifier as it's dynamic
      final_snapshot_identifier,
    ]
  }
}

# Random password for Redis AUTH token (if encryption in transit is enabled)
resource "random_password" "auth_token" {
  count   = var.transit_encryption_enabled && var.auth_token_enabled ? 1 : 0
  length  = 32
  special = true
  # AUTH token has specific character requirements
  override_special = "!&#$^<>-"
}


# ============================================================================
# CloudWatch Log Groups - Redis Logs
# ============================================================================

resource "aws_cloudwatch_log_group" "redis_slow_log" {
  #checkov:skip=CKV_AWS_158:CloudWatch log encryption managed at account level
  #checkov:skip=CKV_AWS_338:Short retention appropriate for dev environment
  name              = "/aws/elasticache/${var.project_name}-${var.environment}/redis/slow-log"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-slow-log"
    }
  )
}

resource "aws_cloudwatch_log_group" "redis_engine_log" {
  #checkov:skip=CKV_AWS_158:CloudWatch log encryption managed at account level
  #checkov:skip=CKV_AWS_338:Short retention appropriate for dev environment
  name              = "/aws/elasticache/${var.project_name}-${var.environment}/redis/engine-log"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-engine-log"
    }
  )
}


# ============================================================================
# Secrets Manager - Redis Connection URL
# ============================================================================

# Secrets Manager secret for Redis connection URL
resource "aws_secretsmanager_secret" "redis_url" {
  #checkov:skip=CKV2_AWS_57:Secret rotation planned for future iteration
  #checkov:skip=CKV_AWS_149:Encrypted with AWS-managed KMS key
  name        = "${var.project_name}-${var.environment}-redis-url"
  description = "Redis connection URL for ${var.project_name} ${var.environment}"

  # KMS encryption using AWS-managed key
  kms_key_id = "alias/aws/secretsmanager"

  # Recovery window (0 for immediate deletion in dev, 30 for prod)
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-url"
    }
  )

  lifecycle {
    prevent_destroy = false
  }
}

# Secrets Manager secret version with Redis connection details
resource "aws_secretsmanager_secret_version" "redis_url" {
  secret_id = aws_secretsmanager_secret.redis_url.id

  secret_string = jsonencode({
    host     = aws_elasticache_replication_group.main.primary_endpoint_address
    port     = aws_elasticache_replication_group.main.port
    url      = var.transit_encryption_enabled && var.auth_token_enabled ? "rediss://:${random_password.auth_token[0].result}@${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}" : "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}"
    ssl      = var.transit_encryption_enabled
    password = var.transit_encryption_enabled && var.auth_token_enabled ? random_password.auth_token[0].result : null
  })

  lifecycle {
    ignore_changes = [
      # Ignore changes to secret_string if needed
      secret_string,
    ]
  }
}


# ============================================================================
# CloudWatch Alarms - Redis Monitoring
# ============================================================================

# SNS Topic for Redis alarms (if not provided)
resource "aws_sns_topic" "redis_alarms" {
  count = var.alarm_sns_topic_arn == null ? 1 : 0
  name  = "${var.project_name}-${var.environment}-redis-alarms"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-alarms"
    }
  )
}

# SNS Topic subscription for email notifications
resource "aws_sns_topic_subscription" "redis_alarms_email" {
  count     = var.alarm_sns_topic_arn == null && length(var.alarm_email_addresses) > 0 ? length(var.alarm_email_addresses) : 0
  topic_arn = aws_sns_topic.redis_alarms[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email_addresses[count.index]
}

# Local variable for SNS topic ARN
locals {
  alarm_topic_arn = var.alarm_sns_topic_arn != null ? var.alarm_sns_topic_arn : (length(aws_sns_topic.redis_alarms) > 0 ? aws_sns_topic.redis_alarms[0].arn : null)
}

# CPU Utilization Alarm
resource "aws_cloudwatch_metric_alarm" "cpu_utilization" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-redis-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = var.cpu_alarm_threshold
  alarm_description   = "Redis CPU utilization is above ${var.cpu_alarm_threshold}%"
  alarm_actions       = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []
  ok_actions          = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.main.id
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-cpu-alarm"
    }
  )
}

# Memory Utilization Alarm
resource "aws_cloudwatch_metric_alarm" "memory_utilization" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-redis-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = var.memory_alarm_threshold
  alarm_description   = "Redis memory utilization is above ${var.memory_alarm_threshold}%"
  alarm_actions       = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []
  ok_actions          = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.main.id
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-memory-alarm"
    }
  )
}

# Evictions Alarm
resource "aws_cloudwatch_metric_alarm" "evictions" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-redis-evictions-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Evictions"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Sum"
  threshold           = var.evictions_alarm_threshold
  alarm_description   = "Redis evictions are above ${var.evictions_alarm_threshold}"
  alarm_actions       = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []
  ok_actions          = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.main.id
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-evictions-alarm"
    }
  )
}

# Connection Count Alarm
resource "aws_cloudwatch_metric_alarm" "curr_connections" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-redis-connections-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CurrConnections"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = var.connections_alarm_threshold
  alarm_description   = "Redis connections are above ${var.connections_alarm_threshold}"
  alarm_actions       = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []
  ok_actions          = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.main.id
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-connections-alarm"
    }
  )
}

# Replication Lag Alarm (only for multi-node clusters)
resource "aws_cloudwatch_metric_alarm" "replication_lag" {
  count               = var.enable_cloudwatch_alarms && var.num_cache_nodes > 1 ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-redis-replication-lag-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ReplicationLag"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = var.replication_lag_alarm_threshold
  alarm_description   = "Redis replication lag is above ${var.replication_lag_alarm_threshold} seconds"
  alarm_actions       = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []
  ok_actions          = local.alarm_topic_arn != null ? [local.alarm_topic_arn] : []

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.main.id
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-replication-lag-alarm"
    }
  )
}
