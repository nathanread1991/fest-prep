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
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = module.networking.vpc_cidr
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = module.networking.private_subnet_ids
}

output "alb_security_group_id" {
  description = "ID of the ALB security group"
  value       = module.networking.alb_security_group_id
}

output "ecs_tasks_security_group_id" {
  description = "ID of the ECS tasks security group"
  value       = module.networking.ecs_tasks_security_group_id
}

output "rds_security_group_id" {
  description = "ID of the RDS security group"
  value       = module.networking.rds_security_group_id
}

output "redis_security_group_id" {
  description = "ID of the Redis security group"
  value       = module.networking.redis_security_group_id
}

# Database Module
# output "db_cluster_endpoint" {
#   description = "Aurora cluster endpoint"
#   value       = module.database.cluster_endpoint
#   sensitive   = true
# }

# Compute Module
output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.compute.alb_dns_name
}

output "api_task_definition_arn" {
  description = "ARN of the current API task definition"
  value       = module.compute.api_task_definition_arn
}

output "worker_task_definition_arn" {
  description = "ARN of the current worker task definition"
  value       = module.compute.worker_task_definition_arn
}

output "api_task_definition_revision" {
  description = "Current revision of the API task definition"
  value       = module.compute.api_task_definition_revision
}

output "worker_task_definition_revision" {
  description = "Current revision of the worker task definition"
  value       = module.compute.worker_task_definition_revision
}


# Migration Task
output "migration_task_definition_arn" {
  description = "ARN of the migration task definition"
  value       = module.compute.migration_task_definition_arn
}

output "migration_task_definition_family" {
  description = "Family of the migration task definition"
  value       = module.compute.migration_task_definition_family
}

# ============================================================================
# CDN Module Outputs
# ============================================================================

output "cloudfront_distribution_id" {
  description = "ID of the CloudFront distribution"
  value       = module.cdn.distribution_id
}

output "cloudfront_distribution_domain_name" {
  description = "Domain name of the CloudFront distribution"
  value       = module.cdn.distribution_domain_name
}

output "cloudfront_distribution_status" {
  description = "Current status of the CloudFront distribution"
  value       = module.cdn.distribution_status
}

# ============================================================================
# DNS / Custom Domain Outputs
# ============================================================================

output "root_domain_fqdn" {
  description = "FQDN of the root domain A record (gig-prep.co.uk → CloudFront)"
  value       = aws_route53_record.root_domain.fqdn
}

output "api_domain_fqdn" {
  description = "FQDN of the API subdomain A record (api.gig-prep.co.uk → ALB)"
  value       = aws_route53_record.api_subdomain.fqdn
}

output "application_url" {
  description = "Primary application URL"
  value       = "https://${var.domain_name}"
}

output "api_url" {
  description = "API endpoint URL"
  value       = var.environment == "prod" ? "https://api-prod.${var.domain_name}" : "https://api.${var.domain_name}"
}
