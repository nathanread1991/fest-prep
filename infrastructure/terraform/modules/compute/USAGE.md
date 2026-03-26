# Compute Module - Usage Guide

This guide provides detailed examples for using the compute module in different scenarios.

## Table of Contents

- [Basic Setup](#basic-setup)
- [Development Environment](#development-environment)
- [Production Environment](#production-environment)
- [Custom Environment Variables](#custom-environment-variables)
- [HTTPS Configuration](#https-configuration)
- [Auto-Scaling Configuration](#auto-scaling-configuration)
- [Worker Configuration](#worker-configuration)
- [Monitoring and Logging](#monitoring-and-logging)

## Basic Setup

Minimal configuration for getting started:

```hcl
module "compute" {
  source = "./modules/compute"

  project_name = "festival-app"
  environment  = "dev"

  # Networking (from networking module)
  vpc_id                       = module.networking.vpc_id
  public_subnet_ids            = module.networking.public_subnet_ids
  private_subnet_ids           = module.networking.private_subnet_ids
  alb_security_group_id        = module.networking.alb_security_group_id
  ecs_tasks_security_group_id  = module.networking.ecs_tasks_security_group_id

  # ECR (from storage module)
  ecr_repository_url = module.storage.ecr_repository_url

  # Secrets (from database and cache modules)
  secrets_arns = [
    module.database.secret_arn,
    module.cache.secret_arn
  ]
  db_secret_arn    = module.database.secret_arn
  redis_secret_arn = module.cache.secret_arn

  # S3 (from storage module)
  app_data_bucket_arn = module.storage.app_data_bucket_arn

  common_tags = {
    Project     = "festival-app"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

## Development Environment

Configuration optimized for development with cost savings:

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
  api_image_tag      = "dev-latest"
  worker_image_tag   = "dev-latest"

  # Secrets
  secrets_arns = [
    module.database.secret_arn,
    module.cache.secret_arn
  ]
  db_secret_arn    = module.database.secret_arn
  redis_secret_arn = module.cache.secret_arn

  # S3
  app_data_bucket_arn = module.storage.app_data_bucket_arn

  # ECS Configuration - Minimal for dev
  api_cpu            = 256   # 0.25 vCPU
  api_memory         = 512   # 0.5 GB
  api_desired_count  = 1
  api_min_capacity   = 1
  api_max_capacity   = 2     # Lower max for dev

  worker_cpu           = 256
  worker_memory        = 512
  worker_desired_count = 1
  worker_use_spot      = true  # Use SPOT for cost savings

  # Disable auto-scaling in dev
  api_enable_auto_scaling = false

  # CloudWatch Logs - Shorter retention for dev
  log_retention_days = 7

  # ALB Configuration
  alb_enable_deletion_protection = false
  enable_https_listener          = false  # HTTP only for dev

  # Container Insights - Optional for dev
  enable_container_insights = false

  common_tags = {
    Project     = "festival-app"
    Environment = "dev"
    ManagedBy   = "terraform"
    CostCenter  = "development"
  }
}
```

## Production Environment

Configuration optimized for production with high availability:

```hcl
module "compute" {
  source = "./modules/compute"

  project_name = "festival-app"
  environment  = "prod"

  # Networking
  vpc_id                       = module.networking.vpc_id
  public_subnet_ids            = module.networking.public_subnet_ids
  private_subnet_ids           = module.networking.private_subnet_ids
  alb_security_group_id        = module.networking.alb_security_group_id
  ecs_tasks_security_group_id  = module.networking.ecs_tasks_security_group_id

  # ECR
  ecr_repository_url = module.storage.ecr_repository_url
  api_image_tag      = "v1.2.3"  # Use specific version tags in prod
  worker_image_tag   = "v1.2.3"

  # Secrets
  secrets_arns = [
    module.database.secret_arn,
    module.cache.secret_arn,
    aws_secretsmanager_secret.spotify.arn,
    aws_secretsmanager_secret.jwt.arn,
    aws_secretsmanager_secret.setlistfm.arn
  ]
  db_secret_arn         = module.database.secret_arn
  redis_secret_arn      = module.cache.secret_arn
  spotify_secret_arn    = aws_secretsmanager_secret.spotify.arn
  jwt_secret_arn        = aws_secretsmanager_secret.jwt.arn
  setlistfm_secret_arn  = aws_secretsmanager_secret.setlistfm.arn

  # S3
  app_data_bucket_arn = module.storage.app_data_bucket_arn

  # ECS Configuration - Higher capacity for prod
  api_cpu            = 512   # 0.5 vCPU
  api_memory         = 1024  # 1 GB
  api_desired_count  = 2     # Start with 2 tasks
  api_min_capacity   = 2
  api_max_capacity   = 10    # Higher max for prod

  worker_cpu           = 512
  worker_memory        = 1024
  worker_desired_count = 2
  worker_use_spot      = true  # Still use SPOT for workers

  # Enable auto-scaling in prod
  api_enable_auto_scaling = true
  api_cpu_target          = 70
  api_memory_target       = 80

  # CloudWatch Logs - Longer retention for prod
  log_retention_days = 30

  # ALB Configuration
  alb_enable_deletion_protection = true  # Protect ALB in prod
  enable_https_listener          = true
  acm_certificate_arn            = module.security.acm_certificate_arn
  ssl_policy                     = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  # Enable access logs in prod
  alb_enable_access_logs  = true
  alb_access_logs_bucket  = module.storage.cloudfront_logs_bucket_name
  alb_access_logs_prefix  = "alb"

  # Container Insights - Enable for prod
  enable_container_insights = true

  common_tags = {
    Project     = "festival-app"
    Environment = "prod"
    ManagedBy   = "terraform"
    CostCenter  = "production"
    Backup      = "required"
  }
}
```

## Custom Environment Variables

Adding custom environment variables to containers:

```hcl
module "compute" {
  source = "./modules/compute"

  # ... other configuration ...

  # API environment variables
  api_environment_variables = {
    # Application settings
    APP_NAME                = "Festival Playlist Generator"
    APP_VERSION             = "1.2.3"

    # Feature flags
    ENABLE_ANALYTICS        = "true"
    ENABLE_CACHING          = "true"
    ENABLE_RATE_LIMITING    = "true"

    # External API settings
    SPOTIFY_API_TIMEOUT     = "30"
    SETLISTFM_API_TIMEOUT   = "30"

    # Cache settings
    CACHE_DEFAULT_TTL       = "3600"
    CACHE_MAX_CONNECTIONS   = "50"

    # Database settings
    DB_POOL_SIZE            = "20"
    DB_MAX_OVERFLOW         = "10"
    DB_POOL_TIMEOUT         = "30"

    # Logging
    LOG_FORMAT              = "json"
    LOG_LEVEL               = "INFO"
  }

  # Worker environment variables
  worker_environment_variables = {
    # Celery settings
    CELERY_WORKER_CONCURRENCY = "4"
    CELERY_WORKER_PREFETCH    = "4"
    CELERY_TASK_TIMEOUT       = "300"

    # Logging
    LOG_FORMAT                = "json"
    LOG_LEVEL                 = "INFO"
  }
}
```

## HTTPS Configuration

Configuring HTTPS with ACM certificate:

```hcl
# First, create ACM certificate in security module
module "security" {
  source = "./modules/security"
  # ... configuration ...
}

# Then configure compute module with HTTPS
module "compute" {
  source = "./modules/compute"

  # ... other configuration ...

  # Enable HTTPS listener
  enable_https_listener = true
  acm_certificate_arn   = module.security.acm_certificate_arn

  # Use modern SSL policy
  ssl_policy = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  # HTTP listener will automatically redirect to HTTPS
}

# Access the application
output "api_url" {
  value = "https://${module.compute.alb_dns_name}"
}
```

## Auto-Scaling Configuration

Fine-tuning auto-scaling behavior:

```hcl
module "compute" {
  source = "./modules/compute"

  # ... other configuration ...

  # Enable auto-scaling
  api_enable_auto_scaling = true

  # Scaling range
  api_min_capacity = 2   # Always run at least 2 tasks
  api_max_capacity = 10  # Scale up to 10 tasks

  # CPU-based scaling
  api_cpu_target = 70    # Target 70% CPU utilization

  # Memory-based scaling
  api_memory_target = 80 # Target 80% memory utilization

  # Note: ECS will scale based on whichever metric is higher
  # Scale-out cooldown: 60 seconds (fast response to load)
  # Scale-in cooldown: 300 seconds (avoid flapping)
}
```

### Monitoring Auto-Scaling

```bash
# Watch ECS service scaling events
aws ecs describe-services \
  --cluster festival-app-dev-cluster \
  --services festival-app-dev-api \
  --query 'services[0].events[0:10]'

# Check current task count
aws ecs describe-services \
  --cluster festival-app-dev-cluster \
  --services festival-app-dev-api \
  --query 'services[0].[desiredCount,runningCount]'

# View CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=festival-app-dev-api \
              Name=ClusterName,Value=festival-app-dev-cluster \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T23:59:59Z \
  --period 300 \
  --statistics Average
```

## Worker Configuration

Configuring Celery workers:

```hcl
module "compute" {
  source = "./modules/compute"

  # ... other configuration ...

  # Worker configuration
  worker_cpu           = 512   # 0.5 vCPU for more intensive tasks
  worker_memory        = 1024  # 1 GB for processing
  worker_desired_count = 2     # Run 2 workers
  worker_use_spot      = true  # Use SPOT for 70% savings

  # Worker environment variables
  worker_environment_variables = {
    # Celery concurrency (tasks per worker)
    CELERY_WORKER_CONCURRENCY = "4"

    # Task prefetch (tasks to fetch ahead)
    CELERY_WORKER_PREFETCH = "4"

    # Task timeout (seconds)
    CELERY_TASK_TIMEOUT = "300"

    # Task retry settings
    CELERY_TASK_MAX_RETRIES = "3"
    CELERY_TASK_RETRY_DELAY = "60"
  }
}
```

### Scaling Workers Based on Queue Depth

For advanced use cases, you can scale workers based on queue depth:

```hcl
# Create CloudWatch alarm for queue depth
resource "aws_cloudwatch_metric_alarm" "queue_depth_high" {
  alarm_name          = "festival-app-dev-queue-depth-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Average"
  threshold           = 100

  dimensions = {
    QueueName = "festival-app-celery-queue"
  }

  alarm_actions = [aws_appautoscaling_policy.worker_scale_up.arn]
}

# Create scaling policy
resource "aws_appautoscaling_policy" "worker_scale_up" {
  name               = "festival-app-dev-worker-scale-up"
  policy_type        = "StepScaling"
  resource_id        = "service/${module.compute.cluster_name}/${module.compute.worker_service_name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 60
    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_lower_bound = 0
      scaling_adjustment          = 1
    }
  }
}
```

## Monitoring and Logging

### Accessing Logs

```bash
# View API logs
aws logs tail /ecs/festival-app-dev/api --follow

# View worker logs
aws logs tail /ecs/festival-app-dev/worker --follow

# Query logs with CloudWatch Insights
aws logs start-query \
  --log-group-name /ecs/festival-app-dev/api \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20'
```

### Monitoring Metrics

```hcl
# Output key metrics for monitoring
output "monitoring_dashboard_url" {
  value = "https://console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${var.project_name}-${var.environment}"
}

output "ecs_service_url" {
  value = "https://console.aws.amazon.com/ecs/home?region=${data.aws_region.current.name}#/clusters/${module.compute.cluster_name}/services/${module.compute.api_service_name}/tasks"
}

output "alb_target_health_url" {
  value = "https://console.aws.amazon.com/ec2/v2/home?region=${data.aws_region.current.name}#TargetGroup:targetGroupArn=${module.compute.api_target_group_arn}"
}
```

## Complete Example

Here's a complete example combining all features:

```hcl
module "compute" {
  source = "./modules/compute"

  project_name = "festival-app"
  environment  = var.environment

  # Networking
  vpc_id                       = module.networking.vpc_id
  public_subnet_ids            = module.networking.public_subnet_ids
  private_subnet_ids           = module.networking.private_subnet_ids
  alb_security_group_id        = module.networking.alb_security_group_id
  ecs_tasks_security_group_id  = module.networking.ecs_tasks_security_group_id

  # ECR
  ecr_repository_url = module.storage.ecr_repository_url
  api_image_tag      = var.api_image_tag
  worker_image_tag   = var.worker_image_tag

  # Secrets
  secrets_arns = [
    module.database.secret_arn,
    module.cache.secret_arn,
    aws_secretsmanager_secret.spotify.arn,
    aws_secretsmanager_secret.jwt.arn,
    aws_secretsmanager_secret.setlistfm.arn
  ]
  db_secret_arn         = module.database.secret_arn
  redis_secret_arn      = module.cache.secret_arn
  spotify_secret_arn    = aws_secretsmanager_secret.spotify.arn
  jwt_secret_arn        = aws_secretsmanager_secret.jwt.arn
  setlistfm_secret_arn  = aws_secretsmanager_secret.setlistfm.arn

  # S3
  app_data_bucket_arn = module.storage.app_data_bucket_arn

  # ECS Configuration
  api_cpu            = var.environment == "prod" ? 512 : 256
  api_memory         = var.environment == "prod" ? 1024 : 512
  api_desired_count  = var.environment == "prod" ? 2 : 1
  api_min_capacity   = var.environment == "prod" ? 2 : 1
  api_max_capacity   = var.environment == "prod" ? 10 : 4

  worker_cpu           = var.environment == "prod" ? 512 : 256
  worker_memory        = var.environment == "prod" ? 1024 : 512
  worker_desired_count = var.environment == "prod" ? 2 : 1
  worker_use_spot      = true

  # Auto-scaling
  api_enable_auto_scaling = var.environment == "prod"
  api_cpu_target          = 70
  api_memory_target       = 80

  # Logging
  log_retention_days = var.environment == "prod" ? 30 : 7

  # ALB
  alb_enable_deletion_protection = var.environment == "prod"
  enable_https_listener          = var.enable_https
  acm_certificate_arn            = var.enable_https ? module.security.acm_certificate_arn : ""

  # Monitoring
  enable_container_insights = var.environment == "prod"

  # Environment variables
  api_environment_variables = {
    APP_NAME              = "Festival Playlist Generator"
    APP_VERSION           = var.app_version
    ENABLE_ANALYTICS      = var.environment == "prod" ? "true" : "false"
    CACHE_DEFAULT_TTL     = "3600"
    LOG_FORMAT            = "json"
  }

  worker_environment_variables = {
    CELERY_WORKER_CONCURRENCY = var.environment == "prod" ? "4" : "2"
    CELERY_TASK_TIMEOUT       = "300"
    LOG_FORMAT                = "json"
  }

  common_tags = {
    Project     = "festival-app"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Outputs
output "api_endpoint" {
  value = var.enable_https ? "https://${module.compute.alb_dns_name}" : "http://${module.compute.alb_dns_name}"
}

output "cluster_name" {
  value = module.compute.cluster_name
}

output "api_service_name" {
  value = module.compute.api_service_name
}

output "worker_service_name" {
  value = module.compute.worker_service_name
}
```

## Next Steps

1. **Deploy the infrastructure**: `terraform apply`
2. **Build and push Docker image**: See ECR documentation
3. **Update ECS service**: Service will automatically deploy new image
4. **Monitor deployment**: Check ECS console and CloudWatch logs
5. **Test the application**: Access via ALB DNS name
6. **Configure custom domain**: See security module for Route 53 setup
