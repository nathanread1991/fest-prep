# Monitoring Module - CloudWatch Logs, Metrics, Alarms, and X-Ray

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ============================================================================
# CloudWatch Log Groups
# ============================================================================

# Log group for ECS API service
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project_name}-${var.environment}-api"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-api-logs"
      Service     = "api"
      Environment = var.environment
    }
  )
}

# Log group for ECS worker service
resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project_name}-${var.environment}-worker"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-worker-logs"
      Service     = "worker"
      Environment = var.environment
    }
  )
}

# ============================================================================
# SNS Topic for Alarm Notifications
# ============================================================================

resource "aws_sns_topic" "alarms" {
  name              = "${var.project_name}-${var.environment}-alarms"
  display_name      = "CloudWatch Alarms for ${var.project_name} ${var.environment}"
  kms_master_key_id = aws_kms_key.sns.id

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-alarms"
      Environment = var.environment
    }
  )
}

# KMS key for SNS encryption
resource "aws_kms_key" "sns" {
  description             = "KMS key for SNS topic encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-sns-key"
      Environment = var.environment
    }
  )
}

resource "aws_kms_alias" "sns" {
  name          = "alias/${var.project_name}-${var.environment}-sns"
  target_key_id = aws_kms_key.sns.key_id
}

# SNS topic subscription for email notifications
resource "aws_sns_topic_subscription" "alarm_email" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ============================================================================
# CloudWatch Alarms - API Service
# ============================================================================

# Alarm for API 5XX errors
resource "aws_cloudwatch_metric_alarm" "api_5xx_errors" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-api-5xx-errors"
  alarm_description   = "API 5XX error rate exceeds threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = var.api_error_rate_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-api-5xx-errors"
      Service     = "api"
      Environment = var.environment
    }
  )
}

# Alarm for API latency (p95)
resource "aws_cloudwatch_metric_alarm" "api_latency" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-api-latency"
  alarm_description   = "API p95 latency exceeds threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = var.api_latency_threshold / 1000 # Convert ms to seconds

  metric_query {
    id          = "m1"
    return_data = true

    metric {
      metric_name = "TargetResponseTime"
      namespace   = "AWS/ApplicationELB"
      period      = 300
      stat        = "p95"

      dimensions = {
        LoadBalancer = var.alb_arn_suffix
        TargetGroup  = var.target_group_arn_suffix
      }
    }
  }

  treat_missing_data = "notBreaching"
  alarm_actions      = [aws_sns_topic.alarms.arn]
  ok_actions         = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-api-latency"
      Service     = "api"
      Environment = var.environment
    }
  )
}

# ============================================================================
# CloudWatch Alarms - RDS Database
# ============================================================================

# Alarm for RDS CPU utilization
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-rds-cpu"
  alarm_description   = "RDS CPU utilization exceeds threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = var.db_cpu_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = var.db_cluster_id
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-rds-cpu"
      Service     = "database"
      Environment = var.environment
    }
  )
}

# Alarm for RDS database connections
resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-rds-connections"
  alarm_description   = "RDS connection count exceeds threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = var.db_max_connections * var.db_connections_threshold_percent / 100
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = var.db_cluster_id
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-rds-connections"
      Service     = "database"
      Environment = var.environment
    }
  )
}

# ============================================================================
# CloudWatch Alarms - ECS Service
# ============================================================================

# Alarm for ECS task count (API service)
resource "aws_cloudwatch_metric_alarm" "ecs_task_count" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-ecs-task-count"
  alarm_description   = "ECS API task count below minimum"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Average"
  threshold           = var.ecs_min_task_count
  treat_missing_data  = "breaching"

  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.api_service_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-ecs-task-count"
      Service     = "ecs"
      Environment = var.environment
    }
  )
}

# Alarm for ECS API CPU utilization (high — indicates scaling pressure)
resource "aws_cloudwatch_metric_alarm" "ecs_api_cpu_high" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-ecs-api-cpu-high"
  alarm_description   = "ECS API CPU utilization exceeds scaling threshold — auto-scaling should be active"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = var.ecs_api_cpu_alarm_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.api_service_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-ecs-api-cpu-high"
      Service     = "ecs"
      Environment = var.environment
    }
  )
}

# Alarm for ECS API memory utilization (high)
resource "aws_cloudwatch_metric_alarm" "ecs_api_memory_high" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-ecs-api-memory-high"
  alarm_description   = "ECS API memory utilization exceeds threshold — auto-scaling should be active"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = var.ecs_api_memory_alarm_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.api_service_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-ecs-api-memory-high"
      Service     = "ecs"
      Environment = var.environment
    }
  )
}

# Alarm for ECS worker task count (below minimum when scaling is enabled)
resource "aws_cloudwatch_metric_alarm" "ecs_worker_task_count" {
  count = var.enable_alarms && var.worker_service_name != "" ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-ecs-worker-task-count"
  alarm_description   = "ECS worker task count below minimum"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Average"
  threshold           = 1
  treat_missing_data  = "breaching"

  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.worker_service_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-ecs-worker-task-count"
      Service     = "ecs-worker"
      Environment = var.environment
    }
  )
}

# ============================================================================
# CloudWatch Dashboard
# ============================================================================

resource "aws_cloudwatch_dashboard" "main" {
  count = var.enable_dashboard ? 1 : 0

  dashboard_name = "${var.project_name}-${var.environment}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      # API Request Count
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", { stat = "Sum", label = "Total Requests" }]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "API Request Count"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 12
        height = 6
        x      = 0
        y      = 0
      },
      # API Latency
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", { stat = "p50", label = "p50" }],
            ["...", { stat = "p95", label = "p95" }],
            ["...", { stat = "p99", label = "p99" }]
          ]
          period = 300
          region = data.aws_region.current.name
          title  = "API Latency (seconds)"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 12
        height = 6
        x      = 12
        y      = 0
      },
      # API Errors
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count", { stat = "Sum", label = "4XX Errors" }],
            [".", "HTTPCode_Target_5XX_Count", { stat = "Sum", label = "5XX Errors" }]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "API Errors"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 12
        height = 6
        x      = 0
        y      = 6
      },
      # RDS CPU
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", { stat = "Average", label = "CPU %" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "RDS CPU Utilization"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
        width  = 8
        height = 6
        x      = 12
        y      = 6
      },
      # RDS Connections
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/RDS", "DatabaseConnections", { stat = "Average", label = "Connections" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "RDS Database Connections"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 8
        height = 6
        x      = 20
        y      = 6
      },
      # RDS Memory
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/RDS", "FreeableMemory", { stat = "Average", label = "Free Memory (bytes)" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "RDS Freeable Memory"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 8
        height = 6
        x      = 0
        y      = 12
      },
      # ECS CPU
      {
        type = "metric"
        properties = {
          metrics = [
            ["ECS/ContainerInsights", "CpuUtilized", { stat = "Average", label = "CPU Utilized" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "ECS CPU Utilization"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 8
        height = 6
        x      = 8
        y      = 12
      },
      # ECS Memory
      {
        type = "metric"
        properties = {
          metrics = [
            ["ECS/ContainerInsights", "MemoryUtilized", { stat = "Average", label = "Memory Utilized" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "ECS Memory Utilization"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 8
        height = 6
        x      = 16
        y      = 12
      },
      # ECS Task Count
      {
        type = "metric"
        properties = {
          metrics = [
            ["ECS/ContainerInsights", "RunningTaskCount", { stat = "Average", label = "Running Tasks" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "ECS Running Task Count"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 8
        height = 6
        x      = 0
        y      = 18
      },
      # Redis CPU
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", { stat = "Average", label = "CPU %" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "Redis CPU Utilization"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
        width  = 8
        height = 6
        x      = 8
        y      = 18
      },
      # Redis Memory
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ElastiCache", "DatabaseMemoryUsagePercentage", { stat = "Average", label = "Memory %" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "Redis Memory Usage"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
        width  = 8
        height = 6
        x      = 16
        y      = 18
      },
      # Redis Connections
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ElastiCache", "CurrConnections", { stat = "Average", label = "Connections" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "Redis Current Connections"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 8
        height = 6
        x      = 0
        y      = 24
      },
      # ALB Request Count
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", { stat = "Sum", label = "Requests" }]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "ALB Request Count"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 8
        height = 6
        x      = 8
        y      = 24
      },
      # ALB Target Response Time
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", { stat = "Average", label = "Response Time" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "ALB Target Response Time"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 8
        height = 6
        x      = 16
        y      = 24
      },
      # ECS API Auto-Scaling: Desired vs Running Task Count
      {
        type = "metric"
        properties = {
          metrics = [
            ["ECS/ContainerInsights", "DesiredTaskCount", "ClusterName", var.cluster_name, "ServiceName", var.api_service_name, { stat = "Average", label = "Desired" }],
            ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", var.cluster_name, "ServiceName", var.api_service_name, { stat = "Average", label = "Running" }]
          ]
          period = 60
          region = data.aws_region.current.name
          title  = "API Auto-Scaling: Desired vs Running Tasks"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 12
        height = 6
        x      = 0
        y      = 30
      },
      # ECS API CPU + Memory for scaling correlation
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", var.cluster_name, "ServiceName", var.api_service_name, { stat = "Average", label = "CPU %" }],
            ["AWS/ECS", "MemoryUtilization", "ClusterName", var.cluster_name, "ServiceName", var.api_service_name, { stat = "Average", label = "Memory %" }]
          ]
          period = 60
          region = data.aws_region.current.name
          title  = "API CPU & Memory (scaling triggers)"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
          annotations = {
            horizontal = [
              { label = "CPU target (70%)", value = 70, color = "#ff9900" },
              { label = "Memory target (80%)", value = 80, color = "#d13212" }
            ]
          }
        }
        width  = 12
        height = 6
        x      = 12
        y      = 30
      },
      # ECS Worker Auto-Scaling: Desired vs Running Task Count
      {
        type = "metric"
        properties = {
          metrics = [
            ["ECS/ContainerInsights", "DesiredTaskCount", "ClusterName", var.cluster_name, "ServiceName", var.worker_service_name, { stat = "Average", label = "Desired" }],
            ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", var.cluster_name, "ServiceName", var.worker_service_name, { stat = "Average", label = "Running" }]
          ]
          period = 60
          region = data.aws_region.current.name
          title  = "Worker Auto-Scaling: Desired vs Running Tasks"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 12
        height = 6
        x      = 0
        y      = 36
      },
      # ALB Request Count Per Target (scaling metric)
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCountPerTarget", { stat = "Sum", label = "Requests/Target" }]
          ]
          period = 60
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "ALB Requests Per Target (scaling trigger)"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 12
        height = 6
        x      = 12
        y      = 36
      }
    ]
  })
}

# ============================================================================
# X-Ray Sampling Rules
# ============================================================================

resource "aws_xray_sampling_rule" "default" {
  count = var.enable_xray ? 1 : 0

  rule_name      = "${var.project_name}-${var.environment}-default"
  priority       = 1000
  version        = 1
  reservoir_size = 1
  fixed_rate     = var.xray_sampling_rate
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = "*"
  resource_arn   = "*"

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-xray-default"
      Environment = var.environment
    }
  )
}

# X-Ray sampling rule for errors (100% sampling)
resource "aws_xray_sampling_rule" "errors" {
  count = var.enable_xray ? 1 : 0

  rule_name      = "${var.project_name}-${var.environment}-errors"
  priority       = 100
  version        = 1
  reservoir_size = 1
  fixed_rate     = 1.0 # 100% sampling for errors
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = "*"
  resource_arn   = "*"

  # Note: X-Ray sampling rules don't have built-in error filtering
  # This will be handled by the application code

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-xray-errors"
      Environment = var.environment
    }
  )
}

# ============================================================================
# CloudWatch Logs Insights - Slow Query Monitoring
# ============================================================================

# Saved query for identifying slow database queries (> 100ms)
resource "aws_cloudwatch_query_definition" "slow_queries" {
  name = "${var.project_name}-${var.environment}-slow-db-queries"

  log_group_names = [
    aws_cloudwatch_log_group.api.name,
    aws_cloudwatch_log_group.worker.name,
  ]

  query_string = <<-EOT
    fields @timestamp, @message, @logStream
    | filter @message like /slow_query/
    | parse @message '"duration_ms": *,' as duration_ms
    | parse @message '"query": "*"' as query
    | sort duration_ms desc
    | limit 50
  EOT
}

# Saved query for database query performance overview
resource "aws_cloudwatch_query_definition" "query_performance" {
  name = "${var.project_name}-${var.environment}-db-query-performance"

  log_group_names = [
    aws_cloudwatch_log_group.api.name,
  ]

  query_string = <<-EOT
    fields @timestamp, @message
    | filter @message like /slow_query/
    | parse @message '"duration_ms": *,' as duration_ms
    | stats avg(duration_ms) as avg_ms, max(duration_ms) as max_ms, count(*) as total by bin(5m)
    | sort @timestamp desc
  EOT
}

# ============================================================================
# Data Sources
# ============================================================================

data "aws_region" "current" {}
