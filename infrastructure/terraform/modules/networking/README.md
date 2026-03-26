# Networking Module

This module creates the network infrastructure for the Festival Playlist Generator, including VPC, subnets, security groups, and VPC endpoints.

## Features

- **VPC**: 10.0.0.0/16 CIDR with DNS support
- **Public Subnets**: 2 subnets (10.0.1.0/24, 10.0.2.0/24) across 2 AZs for ECS tasks and ALB
- **Private Subnets**: 2 subnets (10.0.10.0/24, 10.0.11.0/24) across 2 AZs for RDS and Redis
- **Internet Gateway**: For public subnet internet access
- **Zero-Trust Security Groups**: Least privilege access with security group references
- **VPC Endpoints**: PrivateLink for S3, ECR, CloudWatch Logs, and Secrets Manager

## Architecture

### Network Design

```
VPC (10.0.0.0/16)
├── Public Subnets (Internet Gateway)
│   ├── 10.0.1.0/24 (AZ 1) - ECS tasks, ALB
│   └── 10.0.2.0/24 (AZ 2) - ECS tasks, ALB
└── Private Subnets (No internet access)
    ├── 10.0.10.0/24 (AZ 1) - RDS, Redis
    └── 10.0.11.0/24 (AZ 2) - RDS, Redis
```

### Security Groups (Zero-Trust Model)

**ALB Security Group**
- Inbound: 80/443 from 0.0.0.0/0
- Outbound: 8000 to ECS Security Group only

**ECS Tasks Security Group**
- Inbound: 8000 from ALB Security Group only
- Outbound:
  - 443 to 0.0.0.0/0 (external APIs)
  - 5432 to RDS Security Group
  - 6379 to Redis Security Group
  - 443 to VPC CIDR (VPC endpoints)

**RDS Security Group**
- Inbound: 5432 from ECS Security Group only
- Outbound: None

**Redis Security Group**
- Inbound: 6379 from ECS Security Group only
- Outbound: None

**VPC Endpoints Security Group**
- Inbound: 443 from ECS Security Group
- Outbound: None

### VPC Endpoints

**Gateway Endpoints (Free)**
- S3: For container images and static assets

**Interface Endpoints**
- ECR API: For pulling container images
- ECR Docker: For Docker registry operations
- CloudWatch Logs: For log streaming
- Secrets Manager: For retrieving secrets

## Usage

```hcl
module "networking" {
  source = "./modules/networking"

  project_name = "festival-playlist"
  environment  = "dev"

  vpc_cidr             = "10.0.0.0/16"
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]

  common_tags = {
    Project     = "festival-playlist"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project_name | Name of the project | string | - | yes |
| environment | Environment name (dev, staging, prod) | string | - | yes |
| vpc_cidr | CIDR block for VPC | string | "10.0.0.0/16" | no |
| public_subnet_cidrs | CIDR blocks for public subnets | list(string) | ["10.0.1.0/24", "10.0.2.0/24"] | no |
| private_subnet_cidrs | CIDR blocks for private subnets | list(string) | ["10.0.10.0/24", "10.0.11.0/24"] | no |
| common_tags | Common tags to apply to all resources | map(string) | {} | no |

## Outputs

### VPC Outputs
- `vpc_id`: ID of the VPC
- `vpc_cidr`: CIDR block of the VPC

### Subnet Outputs
- `public_subnet_ids`: IDs of public subnets
- `private_subnet_ids`: IDs of private subnets
- `public_subnet_cidrs`: CIDR blocks of public subnets
- `private_subnet_cidrs`: CIDR blocks of private subnets

### Network Outputs
- `internet_gateway_id`: ID of the Internet Gateway
- `public_route_table_id`: ID of the public route table
- `private_route_table_id`: ID of the private route table

### Security Group Outputs
- `alb_security_group_id`: ID of the ALB security group
- `ecs_tasks_security_group_id`: ID of the ECS tasks security group
- `rds_security_group_id`: ID of the RDS security group
- `redis_security_group_id`: ID of the Redis security group
- `vpc_endpoints_security_group_id`: ID of the VPC endpoints security group

### VPC Endpoint Outputs
- `s3_vpc_endpoint_id`: ID of the S3 VPC endpoint
- `ecr_api_vpc_endpoint_id`: ID of the ECR API VPC endpoint
- `ecr_dkr_vpc_endpoint_id`: ID of the ECR Docker VPC endpoint
- `logs_vpc_endpoint_id`: ID of the CloudWatch Logs VPC endpoint
- `secretsmanager_vpc_endpoint_id`: ID of the Secrets Manager VPC endpoint

### Other Outputs
- `availability_zones`: List of availability zones used

## Security Considerations

1. **No NAT Gateway**: ECS tasks in public subnets with direct internet access saves $32-96/month
2. **Zero-Trust Model**: All security groups use least privilege with explicit allow rules
3. **Security Group References**: Rules use SG references instead of CIDR blocks where possible
4. **Private Subnets**: Databases have no internet access
5. **VPC Endpoints**: AWS service traffic stays within AWS network

## Cost Optimization

- **No NAT Gateway**: Saves $32-96/month
- **S3 Gateway Endpoint**: Free
- **Interface Endpoints**: ~$7/month per endpoint (ECR, Logs, Secrets Manager)
- **Total VPC Cost**: ~$21/month for interface endpoints (worth it for security and performance)

## Requirements

- Terraform >= 1.5
- AWS Provider >= 5.0

## Notes

- All resources are tagged with project, environment, and managed-by tags
- Security groups use `name_prefix` with `create_before_destroy` for safe updates
- VPC endpoints use private DNS for seamless integration
- Public subnets have `map_public_ip_on_launch = true` for ECS tasks
- Private subnets have no internet access (no NAT gateway)

## Related Modules

- `database`: Uses `rds_security_group_id` and `private_subnet_ids`
- `cache`: Uses `redis_security_group_id` and `private_subnet_ids`
- `compute`: Uses `ecs_tasks_security_group_id` and `public_subnet_ids`
- `storage`: Uses `s3_vpc_endpoint_id`
- `security`: Uses `alb_security_group_id`
