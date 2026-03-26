# Billing and Cost Management Module
# This module sets up AWS Budgets, Cost Anomaly Detection, and SNS notifications
# for cost monitoring and alerting

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# SNS Topic for Budget Notifications
resource "aws_sns_topic" "budget_alerts" {
  name              = "${var.project_name}-${var.environment}-budget-alerts"
  display_name      = "AWS Budget Alerts for ${var.project_name}"
  kms_master_key_id = var.enable_encryption ? aws_kms_key.sns[0].id : null

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-budget-alerts"
      Module      = "billing"
      Description = "SNS topic for AWS budget and cost anomaly alerts"
    }
  )
}

# KMS Key for SNS Encryption (optional)
resource "aws_kms_key" "sns" {
  count = var.enable_encryption ? 1 : 0

  description             = "KMS key for SNS topic encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(
    var.common_tags,
    {
      Name   = "${var.project_name}-${var.environment}-sns-key"
      Module = "billing"
    }
  )
}

resource "aws_kms_alias" "sns" {
  count = var.enable_encryption ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-sns"
  target_key_id = aws_kms_key.sns[0].key_id
}

# SNS Topic Subscription (Email)
resource "aws_sns_topic_subscription" "budget_alerts_email" {
  for_each = toset(var.alert_email_addresses)

  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = each.value
}

# AWS Budget - Monthly Total Cost
resource "aws_budgets_budget" "monthly_total" {
  name              = "${var.project_name}-${var.environment}-monthly-total"
  budget_type       = "COST"
  limit_amount      = var.monthly_budget_limit
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2026-01-01_00:00"

  cost_filter {
    name = "TagKeyValue"
    values = [
      "Environment$${var.environment}",
      "Project$${var.project_name}"
    ]
  }

  # Alert at 50% of budget
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 50
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  # Alert at 80% of budget
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  # Alert at 100% of budget
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  # Forecasted alert at 100%
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "FORECASTED"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  tags = merge(
    var.common_tags,
    {
      Name   = "${var.project_name}-${var.environment}-monthly-total"
      Module = "billing"
    }
  )
}

# AWS Budget - $10 Threshold
resource "aws_budgets_budget" "threshold_10" {
  name              = "${var.project_name}-${var.environment}-threshold-10"
  budget_type       = "COST"
  limit_amount      = "10"
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2026-01-01_00:00"

  cost_filter {
    name = "TagKeyValue"
    values = [
      "Environment$${var.environment}",
      "Project$${var.project_name}"
    ]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  tags = merge(
    var.common_tags,
    {
      Name   = "${var.project_name}-${var.environment}-threshold-10"
      Module = "billing"
    }
  )
}

# AWS Budget - $20 Threshold
resource "aws_budgets_budget" "threshold_20" {
  name              = "${var.project_name}-${var.environment}-threshold-20"
  budget_type       = "COST"
  limit_amount      = "20"
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2026-01-01_00:00"

  cost_filter {
    name = "TagKeyValue"
    values = [
      "Environment$${var.environment}",
      "Project$${var.project_name}"
    ]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  tags = merge(
    var.common_tags,
    {
      Name   = "${var.project_name}-${var.environment}-threshold-20"
      Module = "billing"
    }
  )
}

# AWS Budget - $30 Threshold
resource "aws_budgets_budget" "threshold_30" {
  name              = "${var.project_name}-${var.environment}-threshold-30"
  budget_type       = "COST"
  limit_amount      = "30"
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2026-01-01_00:00"

  cost_filter {
    name = "TagKeyValue"
    values = [
      "Environment$${var.environment}",
      "Project$${var.project_name}"
    ]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  tags = merge(
    var.common_tags,
    {
      Name   = "${var.project_name}-${var.environment}-threshold-30"
      Module = "billing"
    }
  )
}

# Cost Anomaly Detection Monitor
resource "aws_ce_anomaly_monitor" "service_monitor" {
  count = var.enable_anomaly_detection ? 1 : 0

  name              = "${var.project_name}-${var.environment}-service-monitor"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"

  tags = merge(
    var.common_tags,
    {
      Name   = "${var.project_name}-${var.environment}-service-monitor"
      Module = "billing"
    }
  )
}

# Cost Anomaly Detection Subscription
resource "aws_ce_anomaly_subscription" "anomaly_alerts" {
  count = var.enable_anomaly_detection ? 1 : 0

  name      = "${var.project_name}-${var.environment}-anomaly-alerts"
  frequency = "DAILY"

  monitor_arn_list = [
    aws_ce_anomaly_monitor.service_monitor[0].arn
  ]

  subscriber {
    type    = "SNS"
    address = aws_sns_topic.budget_alerts.arn
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      values        = [var.anomaly_threshold]
      match_options = ["GREATER_THAN_OR_EQUAL"]
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name   = "${var.project_name}-${var.environment}-anomaly-alerts"
      Module = "billing"
    }
  )
}

# CloudWatch Dashboard for Cost Monitoring
resource "aws_cloudwatch_dashboard" "cost_monitoring" {
  dashboard_name = "${var.project_name}-${var.environment}-cost-monitoring"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Billing", "EstimatedCharges", { stat = "Maximum", label = "Estimated Charges" }]
          ]
          period = 86400
          stat   = "Maximum"
          region = "us-east-1"
          title  = "Estimated Monthly Charges"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      }
    ]
  })
}
