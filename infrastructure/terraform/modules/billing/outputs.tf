# Outputs for Billing Module

output "sns_topic_arn" {
  description = "ARN of the SNS topic for budget alerts"
  value       = aws_sns_topic.budget_alerts.arn
}

output "sns_topic_name" {
  description = "Name of the SNS topic for budget alerts"
  value       = aws_sns_topic.budget_alerts.name
}

output "budget_names" {
  description = "Names of all created budgets"
  value = [
    aws_budgets_budget.monthly_total.name,
    aws_budgets_budget.threshold_10.name,
    aws_budgets_budget.threshold_20.name,
    aws_budgets_budget.threshold_30.name
  ]
}

output "anomaly_monitor_arn" {
  description = "ARN of the cost anomaly detection monitor"
  value       = var.enable_anomaly_detection ? aws_ce_anomaly_monitor.service_monitor[0].arn : null
}

output "anomaly_subscription_arn" {
  description = "ARN of the cost anomaly detection subscription"
  value       = var.enable_anomaly_detection ? aws_ce_anomaly_subscription.anomaly_alerts[0].arn : null
}

output "cost_dashboard_name" {
  description = "Name of the CloudWatch cost monitoring dashboard"
  value       = aws_cloudwatch_dashboard.cost_monitoring.dashboard_name
}
