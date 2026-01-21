# Cache Module

This module manages ElastiCache Redis cluster for the Festival Playlist Generator.

## Resources Created

- ElastiCache Redis cluster
- ElastiCache subnet group
- Redis connection URL in Secrets Manager
- CloudWatch alarms for monitoring

## Configuration

- Instance type: cache.t4g.micro (dev), cache.t4g.small (prod)
- Redis version: 7.0
- Deployment: Single node (dev), Multi-AZ (prod)
- Parameter group: maxmemory-policy = allkeys-lru

## Usage

```hcl
module "cache" {
  source = "./modules/cache"
  
  project_name        = var.project_name
  environment         = var.environment
  vpc_id              = module.networking.vpc_id
  private_subnet_ids  = module.networking.private_subnet_ids
  security_group_id   = module.networking.redis_security_group_id
  common_tags         = var.common_tags
}
```

## Outputs

- redis_endpoint
- redis_port
- secret_arn
