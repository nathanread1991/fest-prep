# Outputs for Festival Playlist Generator Terraform Configuration

# ============================================================================
# Billing Module Outputs
# ============================================================================

output "sns_topic_arn" {
  description = "ARN of the SNS topic for budget alerts"
  value       = module.billing.sns_topic_arn
}

output "sns_topic_name" {
  description = "Name of the SNS topic for budget alerts"
  value       = module.billing.sns_topic_name
}

output "budget_names" {
  description = "Names of all created budgets"
  value       = module.billing.budget_names
}

output "anomaly_monitor_arn" {
  description = "ARN of the cost anomaly detection monitor"
  value       = try(module.billing.anomaly_monitor_arn, "Not created - limit exceeded")
}

output "anomaly_subscription_arn" {
  description = "ARN of the cost anomaly detection subscription"
  value       = try(module.billing.anomaly_subscription_arn, "Not created - limit exceeded")
}

output "cost_dashboard_name" {
  description = "Name of the CloudWatch cost monitoring dashboard"
  value       = module.billing.cost_dashboard_name
}

# ============================================================================
# Environment Information
# ============================================================================

output "environment" {
  description = "Current environment name"
  value       = var.environment
}

output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}

output "project_name" {
  description = "Project name used for resource naming"
  value       = var.project_name
}

# ============================================================================
# Future Module Outputs (will be uncommented as modules are implemented)
# ============================================================================

# Networking Module
# output "vpc_id" {
#   description = "ID of the VPC"
#   value       = module.networking.vpc_id
# }

# output "public_subnet_ids" {
#   description = "IDs of public subnets"
#   value       = module.networking.public_subnet_ids
# }

# output "private_subnet_ids" {
#   description = "IDs of private subnets"
#   value       = module.networking.private_subnet_ids
# }

# Database Module
# output "db_cluster_endpoint" {
#   description = "Aurora cluster endpoint"
#   value       = module.database.cluster_endpoint
#   sensitive   = true
# }

# Compute Module
# output "alb_dns_name" {
#   description = "DNS name of the Application Load Balancer"
#   value       = module.compute.alb_dns_name
# }

# output "api_url" {
#   description = "URL of the API endpoint"
#   value       = "https://${module.compute.alb_dns_name}"
# }
