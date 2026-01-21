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
  region  = var.aws_region
  profile = var.aws_profile
  
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
  alias   = "us_east_1"
  region  = "us-east-1"
  profile = var.aws_profile
  
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

  project_name              = var.project_name
  environment               = var.environment
  monthly_budget_limit      = var.monthly_budget_limit
  alert_email_addresses     = var.alert_email_addresses
  anomaly_threshold         = var.anomaly_threshold
  enable_encryption         = var.enable_encryption
  enable_anomaly_detection  = var.enable_anomaly_detection
  common_tags               = var.common_tags
}

# Future modules will be added here as they are implemented:
# - module "networking" - VPC, subnets, security groups
# - module "database" - Aurora Serverless v2
# - module "cache" - ElastiCache Redis
# - module "storage" - S3 buckets, ECR
# - module "compute" - ECS Fargate, ALB
# - module "cdn" - CloudFront
# - module "monitoring" - CloudWatch, X-Ray
# - module "security" - Secrets Manager, ACM, WAF
