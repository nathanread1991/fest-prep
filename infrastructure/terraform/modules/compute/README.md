# Compute Module

This module manages ECS Fargate cluster, task definitions, and services for the Festival Playlist Generator.

## Resources Created

- ECS Fargate cluster
- ECS task definitions (API and Worker)
- ECS services with auto-scaling
- Application Load Balancer (ALB)
- ALB target groups and listeners
- IAM roles (task execution and task roles)
- CloudWatch log groups

## Services

### API Service
- Task: 0.25 vCPU, 0.5 GB memory
- Auto-scaling: 1-4 tasks based on CPU (70% target)
- Launch type: FARGATE (on-demand)
- Port: 8000

### Worker Service
- Task: 0.25 vCPU, 0.5 GB memory
- Auto-scaling: 0-2 tasks based on queue depth
- Launch type: FARGATE_SPOT (70% cost savings)
- Celery worker

## Usage

```hcl
module "compute" {
  source = "./modules/compute"
  
  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.networking.vpc_id
  public_subnet_ids     = module.networking.public_subnet_ids
  alb_security_group_id = module.networking.alb_security_group_id
  ecs_security_group_id = module.networking.ecs_security_group_id
  ecr_repository_url    = module.storage.ecr_repository_url
  db_secret_arn         = module.database.secret_arn
  redis_secret_arn      = module.cache.secret_arn
  common_tags           = var.common_tags
}
```

## Outputs

- cluster_id
- api_service_name
- worker_service_name
- alb_dns_name
- alb_zone_id
