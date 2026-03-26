# Compute Module

This Terraform module creates and manages the compute infrastructure for the Festival Playlist Generator application on AWS ECS Fargate.

## Overview

The compute module provisions:

- **ECS Fargate Cluster**: Serverless container orchestration
- **IAM Roles**: Task execution and task runtime roles with least privilege
- **ECS Task Definitions**: For API and Worker services
- **ECS Services**: With auto-scaling capabilities
- **Application Load Balancer**: With HTTP/HTTPS listeners and target groups
- **CloudWatch Log Groups**: For application logs
- **Auto-Scaling Policies**: CPU and memory-based scaling for API service

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Internet Users                            │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/HTTPS
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Application Load Balancer                       │
│  - HTTP Listener (Port 80) → Redirect to HTTPS             │
│  - HTTPS Listener (Port 443) → Forward to Target Group     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Target Group (API)                         │
│  - Health Check: /health                                    │
│  - Deregistration Delay: 30s                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    ECS Fargate Cluster                       │
│                                                              │
│  ┌──────────────────────┐    ┌──────────────────────┐      │
│  │   API Service        │    │   Worker Service     │      │
│  │   - 1-4 tasks        │    │   - 0-2 tasks        │      │
│  │   - FARGATE          │    │   - FARGATE_SPOT     │      │
│  │   - Auto-scaling     │    │   - Celery workers   │      │
│  │   - Port 8000        │    │                      │      │
│  └──────────────────────┘    └──────────────────────┘      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Features

### ECS Cluster
- **Container Insights**: Optional CloudWatch Container Insights for enhanced monitoring
- **Capacity Providers**: FARGATE and FARGATE_SPOT for cost optimization

### IAM Roles
- **Task Execution Role**: Pulls images from ECR, writes logs to CloudWatch, reads secrets from Secrets Manager
- **Task Role**: Application runtime permissions for S3, CloudWatch metrics, X-Ray tracing

### Task Definitions
- **API Service**: FastAPI application (0.25 vCPU, 0.5 GB memory)
- **Worker Service**: Celery workers (0.25 vCPU, 0.5 GB memory)
- **Secrets Integration**: Automatic injection from Secrets Manager
- **Health Checks**: Container-level health checks for API service

### ECS Services
- **API Service**:
  - Runs in public subnets with public IP
  - Integrated with ALB target group
  - Auto-scaling based on CPU and memory
  - Deployment: Rolling updates with 100% minimum healthy

- **Worker Service**:
  - Runs in public subnets with public IP
  - Uses FARGATE_SPOT for 70% cost savings
  - No load balancer integration
  - Processes background jobs via Celery

### Application Load Balancer
- **HTTP Listener**: Redirects to HTTPS (when enabled)
- **HTTPS Listener**: SSL/TLS termination with ACM certificate
- **Target Group**: Health checks on /health endpoint
- **Deregistration Delay**: 30 seconds for graceful shutdown

### Auto-Scaling
- **API Service**:
  - CPU-based scaling (target: 70%)
  - Memory-based scaling (target: 80%)
  - Scale range: 1-4 tasks
  - Scale-out cooldown: 60 seconds
  - Scale-in cooldown: 300 seconds

## Usage

See [USAGE.md](./USAGE.md) for detailed usage examples.

### Basic Example

```hcl
module "compute" {
  source = "./modules/compute"

  project_name = "festival-app"
  environment  = "dev"

  # Networking
  vpc_id                       = module.networking.vpc_id
  public_subnet_ids            = module.networking.public_subnet_ids
  private_subnet_ids           = module.networking.private_subnet_ids
  alb_security_group_id        = module.networking.alb_security_group_id
  ecs_tasks_security_group_id  = module.networking.ecs_tasks_security_group_id

  # ECR
  ecr_repository_url = module.storage.ecr_repository_url
  api_image_tag      = "latest"
  worker_image_tag   = "latest"

  # Secrets
  secrets_arns = [
    module.database.secret_arn,
    module.cache.secret_arn
  ]
  db_secret_arn    = module.database.secret_arn
  redis_secret_arn = module.cache.secret_arn

  # S3
  app_data_bucket_arn = module.storage.app_data_bucket_arn

  # SSL/TLS (optional)
  enable_https_listener = false  # Enable after ACM certificate is created
  acm_certificate_arn   = ""

  common_tags = {
    Project     = "festival-app"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5 |
| aws | ~> 5.0 |

## Providers

| Name | Version |
|------|---------|
| aws | ~> 5.0 |

## Resources Created

### ECS Resources
- `aws_ecs_cluster.main` - ECS Fargate cluster
- `aws_ecs_cluster_capacity_providers.main` - Capacity provider configuration
- `aws_ecs_task_definition.api` - API task definition
- `aws_ecs_task_definition.worker` - Worker task definition
- `aws_ecs_service.api` - API service
- `aws_ecs_service.worker` - Worker service

### IAM Resources
- `aws_iam_role.ecs_task_execution_role` - Task execution role
- `aws_iam_role.ecs_task_role` - Task runtime role
- `aws_iam_role_policy.ecs_task_execution_secrets` - Secrets Manager access
- `aws_iam_role_policy.ecs_task_s3` - S3 access
- `aws_iam_role_policy.ecs_task_cloudwatch` - CloudWatch metrics
- `aws_iam_role_policy.ecs_task_xray` - X-Ray tracing

### Load Balancer Resources
- `aws_lb.main` - Application Load Balancer
- `aws_lb_target_group.api` - API target group
- `aws_lb_listener.http` - HTTP listener
- `aws_lb_listener.https` - HTTPS listener (optional)

### CloudWatch Resources
- `aws_cloudwatch_log_group.api` - API logs
- `aws_cloudwatch_log_group.worker` - Worker logs

### Auto-Scaling Resources
- `aws_appautoscaling_target.api` - API scaling target
- `aws_appautoscaling_policy.api_cpu` - CPU-based scaling
- `aws_appautoscaling_policy.api_memory` - Memory-based scaling

## Inputs

See [variables.tf](./variables.tf) for all available inputs.

### Required Inputs

| Name | Description | Type |
|------|-------------|------|
| project_name | Name of the project | string |
| environment | Environment name (dev, staging, prod) | string |
| vpc_id | ID of the VPC | string |
| public_subnet_ids | List of public subnet IDs | list(string) |
| alb_security_group_id | ID of the ALB security group | string |
| ecs_tasks_security_group_id | ID of the ECS tasks security group | string |
| ecr_repository_url | URL of the ECR repository | string |
| secrets_arns | List of Secrets Manager secret ARNs | list(string) |
| db_secret_arn | ARN of database secret | string |
| redis_secret_arn | ARN of Redis secret | string |
| app_data_bucket_arn | ARN of S3 bucket | string |

### Optional Inputs

| Name | Description | Default |
|------|-------------|---------|
| enable_container_insights | Enable CloudWatch Container Insights | true |
| api_cpu | CPU units for API task | 256 |
| api_memory | Memory for API task in MB | 512 |
| api_desired_count | Desired number of API tasks | 1 |
| api_min_capacity | Minimum API tasks for auto-scaling | 1 |
| api_max_capacity | Maximum API tasks for auto-scaling | 4 |
| worker_desired_count | Desired number of worker tasks | 1 |
| worker_use_spot | Use FARGATE_SPOT for workers | true |
| enable_https_listener | Enable HTTPS listener | false |
| log_retention_days | CloudWatch log retention | 7 |

## Outputs

See [outputs.tf](./outputs.tf) for all available outputs.

### Key Outputs

| Name | Description |
|------|-------------|
| cluster_id | ID of the ECS cluster |
| cluster_arn | ARN of the ECS cluster |
| alb_dns_name | DNS name of the ALB |
| api_service_name | Name of the API service |
| worker_service_name | Name of the worker service |

## Cost Optimization

### FARGATE_SPOT for Workers
- Workers use FARGATE_SPOT capacity provider
- 70% cost savings compared to on-demand
- Suitable for background jobs that can tolerate interruptions

### Auto-Scaling
- API service scales based on CPU and memory
- Scales down to 1 task during low traffic
- Scales up to 4 tasks during high traffic

### Daily Teardown
- All resources can be destroyed with `terraform destroy`
- No persistent compute costs when torn down
- Provision time: ~5-10 minutes

## Security

### IAM Least Privilege
- Task execution role: Only ECR, CloudWatch, Secrets Manager
- Task role: Only S3, CloudWatch metrics, X-Ray
- No wildcard permissions

### Network Security
- ECS tasks in public subnets with public IP
- Security groups enforce zero-trust model
- Tasks only accept traffic from ALB
- No direct public access to tasks

### Secrets Management
- All secrets injected from Secrets Manager
- No hardcoded credentials in task definitions
- Secrets encrypted at rest with KMS

## Monitoring

### CloudWatch Logs
- API logs: `/ecs/{project}-{env}/api`
- Worker logs: `/ecs/{project}-{env}/worker`
- Retention: 7 days (dev), 30 days (prod)

### CloudWatch Metrics
- ECS service metrics (CPU, memory, task count)
- ALB metrics (request count, latency, errors)
- Target group metrics (healthy/unhealthy targets)

### Container Insights
- Optional enhanced monitoring
- Task-level CPU and memory metrics
- Network metrics

## Troubleshooting

### Tasks Not Starting
1. Check CloudWatch logs for errors
2. Verify security group allows outbound traffic
3. Verify IAM roles have correct permissions
4. Check ECR image exists and is accessible

### Health Checks Failing
1. Verify /health endpoint returns 200
2. Check health check timeout and interval
3. Review application logs in CloudWatch
4. Verify container port matches target group port

### Auto-Scaling Not Working
1. Check CloudWatch metrics for CPU/memory
2. Verify auto-scaling policies are attached
3. Check scaling cooldown periods
4. Review ECS service events

## Examples

See [USAGE.md](./USAGE.md) for complete examples including:
- Basic setup
- Production configuration
- Custom environment variables
- HTTPS with ACM certificate
- Auto-scaling configuration

## License

This module is part of the Festival Playlist Generator project.
