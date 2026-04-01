# Main Terraform Configuration for Festival Playlist Generator
# This is the EPHEMERAL root — resources here are created/destroyed daily.
# Persistent resources (ECR, S3, Secrets Manager) live in ./persistent/ and
# are referenced via terraform_remote_state.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ============================================================================
# Remote State — Persistent Resources
# ============================================================================

data "terraform_remote_state" "persistent" {
  backend = "s3"
  config = {
    bucket = "festival-playlist-terraform-state"
    key    = "persistent/terraform.tfstate"
    region = "eu-west-2"
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

# ============================================================================
# Persistent Resource References (via remote state)
# ============================================================================
# ECR, S3, and Secrets Manager resources are managed by the persistent module.
# We read their outputs here so downstream modules can consume them.

locals {
  # ECR
  ecr_repository_url = data.terraform_remote_state.persistent.outputs.ecr_repository_url

  # S3
  app_data_bucket_arn                  = data.terraform_remote_state.persistent.outputs.app_data_bucket_arn
  app_data_bucket_regional_domain_name = data.terraform_remote_state.persistent.outputs.app_data_bucket_regional_domain_name
  cloudfront_logs_bucket_name          = data.terraform_remote_state.persistent.outputs.cloudfront_logs_bucket_name

  # Secrets Manager
  spotify_secret_arn   = data.terraform_remote_state.persistent.outputs.spotify_secret_arn
  setlistfm_secret_arn = data.terraform_remote_state.persistent.outputs.setlistfm_secret_arn
  jwt_secret_arn       = data.terraform_remote_state.persistent.outputs.jwt_secret_arn
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

  # Serverless v2 Scaling — prod gets higher capacity
  min_capacity = var.environment == "prod" ? 1 : var.database_min_capacity
  max_capacity = var.environment == "prod" ? 4 : var.database_max_capacity

  # Instance Configuration — multi-AZ for prod
  instance_count = var.environment == "prod" ? 2 : 1

  # Backup Configuration
  backup_retention_period = var.database_backup_retention_period

  # Snapshot Configuration — provision.yml passes these when restoring
  restore_from_snapshot = var.restore_from_snapshot || var.database_restore_from_snapshot
  snapshot_identifier   = var.snapshot_identifier != "" ? var.snapshot_identifier : null
  skip_final_snapshot   = var.environment == "dev" ? true : false

  # CloudWatch Logs
  enabled_cloudwatch_logs_exports = ["postgresql"]

  # Performance Insights
  enable_performance_insights           = true
  performance_insights_retention_period = 7

  # Enhanced Monitoring
  monitoring_interval = 60

  # Deletion Protection — enabled for prod
  deletion_protection = var.environment == "prod" ? true : false

  # Apply Changes — immediate for dev, maintenance window for prod
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
  node_type               = var.environment == "prod" ? "cache.t4g.small" : var.redis_node_type
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
  ecr_repository_url          = local.ecr_repository_url
  app_data_bucket_arn         = local.app_data_bucket_arn
  db_secret_arn               = module.database.secret_arn
  redis_secret_arn            = module.cache.secret_arn
  spotify_secret_arn          = local.spotify_secret_arn
  setlistfm_secret_arn        = local.setlistfm_secret_arn
  jwt_secret_arn              = local.jwt_secret_arn
  secrets_arns = [
    module.database.secret_arn,
    module.cache.secret_arn,
    local.spotify_secret_arn,
    local.setlistfm_secret_arn,
    local.jwt_secret_arn
  ]
  acm_certificate_arn   = module.security.alb_certificate_arn
  enable_https_listener = true
  api_cpu               = var.ecs_api_cpu
  api_memory            = var.ecs_api_memory
  api_desired_count     = var.ecs_api_desired_count
  api_min_capacity      = var.ecs_api_min_capacity
  api_max_capacity      = var.ecs_api_max_capacity
  api_image_tag         = var.api_image_tag
  worker_image_tag      = var.worker_image_tag
  worker_cpu            = var.ecs_worker_cpu
  worker_memory         = var.ecs_worker_memory
  worker_desired_count  = var.ecs_worker_desired_count
  common_tags           = var.common_tags
}

# CDN Module
# Manages CloudFront distribution
module "cdn" {
  source = "./modules/cdn"

  project_name                              = var.project_name
  environment                               = var.environment
  domain_name                               = var.domain_name
  alb_dns_name                              = module.compute.alb_dns_name
  static_assets_bucket_regional_domain_name = local.app_data_bucket_regional_domain_name
  logs_bucket_name                          = local.cloudfront_logs_bucket_name
  acm_certificate_arn                       = module.security.cloudfront_certificate_arn
  common_tags                               = var.common_tags

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }
}

# ============================================================================
# Route 53 DNS Records for Custom Domain
# Created at root level to avoid circular dependency between security and CDN modules
# ============================================================================

# A record for root domain (gig-prep.co.uk) → CloudFront distribution
resource "aws_route53_record" "root_domain" {
  zone_id = module.security.route53_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = module.cdn.distribution_domain_name
    zone_id                = module.cdn.distribution_hosted_zone_id
    evaluate_target_health = false
  }
}

# A record for API subdomain — environment-specific
# dev: api.gig-prep.co.uk, prod: api-prod.gig-prep.co.uk
resource "aws_route53_record" "api_subdomain" {
  zone_id = module.security.route53_zone_id
  name    = var.environment == "prod" ? "api-prod.${var.domain_name}" : "api.${var.domain_name}"
  type    = "A"

  alias {
    name                   = module.compute.alb_dns_name
    zone_id                = module.compute.alb_zone_id
    evaluate_target_health = true
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
