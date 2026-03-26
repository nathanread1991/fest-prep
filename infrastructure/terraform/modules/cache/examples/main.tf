# Example: Using the Cache Module
# This example demonstrates how to use the cache module in your Terraform configuration

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = "eu-west-2"  # London region
}

# Example: Networking module (prerequisite)
# You would typically have this from your networking module
module "networking" {
  source = "../../networking"

  project_name = "festival-playlist"
  environment  = "dev"
  vpc_cidr     = "10.0.0.0/16"

  # ... other networking configuration
}

# Example: Cache module usage
module "cache" {
  source = "../"  # Points to the cache module

  # Required variables
  project_name           = "festival-playlist"
  environment            = "dev"
  private_subnet_ids     = module.networking.private_subnet_ids
  redis_security_group_id = module.networking.redis_security_group_id

  # Redis configuration
  node_type       = "cache.t4g.micro"
  num_cache_nodes = 1
  engine_version  = "7.0"

  # High availability (disabled for dev)
  automatic_failover_enabled = false
  multi_az_enabled           = false

  # Backup configuration
  snapshot_retention_limit = 1
  skip_final_snapshot      = true

  # Encryption
  at_rest_encryption_enabled = true
  transit_encryption_enabled = false
  auth_token_enabled         = false

  # Operational settings
  apply_immediately          = true
  auto_minor_version_upgrade = true

  # Monitoring
  enable_cloudwatch_alarms = true
  alarm_email_addresses    = ["dev@example.com"]

  # Tags
  common_tags = {
    Project     = "festival-playlist"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}

# Outputs
output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = module.cache.primary_endpoint_address
}

output "redis_port" {
  description = "Redis port"
  value       = module.cache.port
}

output "redis_secret_arn" {
  description = "ARN of Secrets Manager secret containing Redis connection details"
  value       = module.cache.secret_arn
}

output "redis_connection_string" {
  description = "Redis connection string (sensitive)"
  value       = module.cache.connection_string
  sensitive   = true
}
