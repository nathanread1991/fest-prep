# Main Terraform Configuration for Festival Playlist Generator
# This file sets up the AWS provider and manages infrastructure modules

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# AWS Provider Configuration
# Region: eu-west-2 (London) - primary region for all resources
provider "aws" {
  region = var.aws_region

  # Default tags applied to all resources for cost tracking and management
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      CostCenter  = var.common_tags["CostCenter"]
      Owner       = var.common_tags["Owner"]
      Region      = var.aws_region
    }
  }
}

# AWS Provider for us-east-1 (required for CloudWatch billing metrics and CloudFront ACM certificates)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      CostCenter  = var.common_tags["CostCenter"]
      Owner       = var.common_tags["Owner"]
      Region      = "us-east-1"
    }
  }
}

# Billing Module
# Manages AWS Budgets, Cost Anomaly Detection, and cost monitoring
module "billing" {
  source = "./modules/billing"

  project_name             = var.project_name
  environment              = var.environment
  monthly_budget_limit     = var.monthly_budget_limit
  alert_email_addresses    = var.alert_email_addresses
  anomaly_threshold        = var.anomaly_threshold
  enable_encryption        = var.enable_encryption
  enable_anomaly_detection = var.enable_anomaly_detection
  common_tags              = var.common_tags
}

# Networking Module
# Manages VPC, subnets, security groups, and VPC endpoints
module "networking" {
  source = "./modules/networking"

  project_name         = var.project_name
  environment          = var.environment
  vpc_cidr             = "10.0.0.0/16"
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
  common_tags          = var.common_tags
}

# Security Module
# Manages Secrets Manager, ACM certificates, Route 53, and WAF
module "security" {
  source = "./modules/security"

  project_name = var.project_name
  environment  = var.environment
  domain_name  = var.domain_name
  vpc_id       = module.networking.vpc_id
  alb_arn      = module.compute.alb_arn
  common_tags  = var.common_tags

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }
}

# Storage Module
# Manages S3 buckets and ECR repository
module "storage" {
  source = "./modules/storage"

  project_name = var.project_name
  environment  = var.environment
  common_tags  = var.common_tags
}

# Database Module
# Manages Aurora Serverless v2 PostgreSQL cluster with snapshot/restore capability
module "database" {
  source = "./modules/database"

  project_name          = var.project_name
  environment           = var.environment
  private_subnet_ids    = module.networking.private_subnet_ids
  rds_security_group_id = module.networking.rds_security_group_id

  # Database Configuration
  database_name   = var.database_name
  master_username = var.database_master_username
  engine_version  = var.database_engine_version

  # Serverless v2 Scaling
  min_capacity = var.database_min_capacity
  max_capacity = var.database_max_capacity

  # Instance Configuration
  instance_count = var.environment == "prod" ? 2 : 1 # Multi-AZ for prod

  # Backup Configuration
  backup_retention_period = var.database_backup_retention_period

  # Snapshot Configuration
  restore_from_snapshot = var.database_restore_from_snapshot
  skip_final_snapshot   = var.environment == "dev" ? true : false

  # CloudWatch Logs
  enabled_cloudwatch_logs_exports = ["postgresql"]

  # Performance Insights
  enable_performance_insights           = true
  performance_insights_retention_period = 7

  # Enhanced Monitoring
  monitoring_interval = 60

  # Deletion Protection
  deletion_protection = var.environment == "prod" ? true : false

  # Apply Changes
  apply_immediately = var.environment == "dev" ? true : false

  # CloudWatch Alarms
  enable_cloudwatch_alarms = true
  alarm_email_addresses    = var.alert_email_addresses

  common_tags = var.common_tags
}

# Cache Module
# Manages ElastiCache Redis cluster
module "cache" {
  source = "./modules/cache"

  project_name            = var.project_name
  environment             = var.environment
  private_subnet_ids      = module.networking.private_subnet_ids
  redis_security_group_id = module.networking.redis_security_group_id
  node_type               = var.redis_node_type
  num_cache_nodes         = var.environment == "prod" ? 2 : 1
  engine_version          = var.redis_engine_version
  common_tags             = var.common_tags
}

# Compute Module
# Manages ECS Fargate cluster, task definitions, services, and ALB
module "compute" {
  source = "./modules/compute"

  project_name                = var.project_name
  environment                 = var.environment
  vpc_id                      = module.networking.vpc_id
  public_subnet_ids           = module.networking.public_subnet_ids
  private_subnet_ids          = module.networking.private_subnet_ids
  alb_security_group_id       = module.networking.alb_security_group_id
  ecs_tasks_security_group_id = module.networking.ecs_tasks_security_group_id
  ecr_repository_url          = module.storage.ecr_repository_url
  app_data_bucket_arn         = module.storage.app_data_bucket_arn
  db_secret_arn               = module.database.secret_arn
  redis_secret_arn            = module.cache.secret_arn
  spotify_secret_arn          = module.security.spotify_secret_arn
  setlistfm_secret_arn        = module.security.setlistfm_secret_arn
  jwt_secret_arn              = module.security.jwt_secret_arn
  secrets_arns = [
    module.database.secret_arn,
    module.cache.secret_arn,
    module.security.spotify_secret_arn,
    module.security.setlistfm_secret_arn,
    module.security.jwt_secret_arn
  ]
  acm_certificate_arn = module.security.alb_certificate_arn
  api_cpu             = var.ecs_api_cpu
  api_memory          = var.ecs_api_memory
  api_desired_count   = var.ecs_api_desired_count
  api_min_capacity    = var.ecs_api_min_capacity
  api_max_capacity    = var.ecs_api_max_capacity
  worker_cpu          = var.ecs_worker_cpu
  worker_memory       = var.ecs_worker_memory
  worker_desired_count = var.ecs_worker_desired_count
  common_tags         = var.common_tags
}

# CDN Module
# Manages CloudFront distribution
module "cdn" {
  source = "./modules/cdn"

  project_name                                = var.project_name
  environment                                 = var.environment
  domain_name                                 = var.domain_name
  alb_dns_name                                = module.compute.alb_dns_name
  static_assets_bucket_regional_domain_name   = module.storage.app_data_bucket_regional_domain_name
  logs_bucket_name                            = module.storage.cloudfront_logs_bucket_name
  acm_certificate_arn                         = module.security.cloudfront_certificate_arn
  common_tags                                 = var.common_tags

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }
}

# Monitoring Module
# Manages CloudWatch Logs, Metrics, Alarms, Dashboards, and X-Ray
module "monitoring" {
  source = "./modules/monitoring"

  project_name            = var.project_name
  environment             = var.environment
  log_retention_days      = var.cloudwatch_log_retention_days
  cluster_name            = module.compute.cluster_name
  api_service_name        = module.compute.api_service_name
  worker_service_name     = module.compute.worker_service_name
  alb_arn_suffix          = module.compute.alb_arn_suffix
  target_group_arn_suffix = module.compute.api_target_group_arn_suffix
  db_cluster_id           = module.database.cluster_id
  redis_cluster_id        = module.cache.replication_group_id
  alert_email             = var.alert_email_addresses[0]
  common_tags             = var.common_tags
}
