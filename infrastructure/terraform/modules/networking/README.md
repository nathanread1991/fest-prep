# Networking Module

This module manages VPC, subnets, security groups, and VPC endpoints for the Festival Playlist Generator.

## Resources Created

- VPC with CIDR 10.0.0.0/16
- Public subnets (2 AZs): 10.0.1.0/24, 10.0.2.0/24
- Private subnets (2 AZs): 10.0.10.0/24, 10.0.11.0/24
- Internet Gateway
- Route tables
- Security groups (ALB, ECS, RDS, Redis, VPC Endpoints)
- VPC Endpoints (S3, ECR, CloudWatch Logs, Secrets Manager)

## Security Groups

### Zero-Trust Model
- ALB: Accepts 80/443 from internet, forwards to ECS only
- ECS: Accepts 8000 from ALB only, accesses RDS/Redis/external APIs
- RDS: Accepts 5432 from ECS only
- Redis: Accepts 6379 from ECS only
- VPC Endpoints: Accept 443 from ECS only

## Usage

```hcl
module "networking" {
  source = "./modules/networking"
  
  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = "10.0.0.0/16"
  common_tags  = var.common_tags
}
```

## Outputs

- vpc_id
- public_subnet_ids
- private_subnet_ids
- security_group_ids (ALB, ECS, RDS, Redis, VPC Endpoints)
- vpc_endpoint_ids
