# Monitoring Module Usage Guide

## Overview

This module creates comprehensive monitoring infrastructure including CloudWatch log groups, alarms, dashboards, and X-Ray tracing for the Festival Playlist Generator application.

## Basic Usage

```hcl
module "monitoring" {
  source = "./modules/monitoring"

  # Required variables
  project_name         = "festival-playlist"
  environment          = "dev"
  cluster_name         = module.compute.cluster_name
  api_service_name     = module.compute.api_service_name
  worker_service_name  = module.compute.worker_service_name
  db_cluster_id        = module.database.cluster_id
  redis_cluster_id     = module.cache.redis_cluster_id
  alb_arn_suffix       = module.compute.alb_arn_suffix
  target_group_arn_suffix = module.compute.target_group_arn_suffix
  alert_email          = "alerts@example.com"

  # Optional variables
  log_retention_days   = 7
  enable_alarms        = true
  enable_dashboard     = true
  enable_xray          = true

  common_tags = {
    Project     = "festival-playlist"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

## Environment-Specific Configuration

### Development Environment

```hcl
module "monitoring" {
  source = "./modules/monitoring"

  project_name    = "festival-playlist"
  environment     = "dev"

  # Shorter log retention for cost savings
  log_retention_days = 7

  # Lower alarm thresholds for testing
  api_error_rate_threshold = 5
  api_latency_threshold    = 2000  # 2 seconds
  db_cpu_threshold         = 90

  # Lower X-Ray sampling for cost savings
  xray_sampling_rate = 0.1  # 10%

  # ... other required variables
}
```

### Production Environment

```hcl
module "monitoring" {
  source = "./modules/monitoring"

  project_name    = "festival-playlist"
  environment     = "prod"

  # Longer log retention for compliance
  log_retention_days = 30

  # Stricter alarm thresholds
  api_error_rate_threshold = 10
  api_latency_threshold    = 1000  # 1 second
  db_cpu_threshold         = 80

  # Higher X-Ray sampling for better visibility
  xray_sampling_rate = 0.2  # 20%

  # ... other required variables
}
```

## Features

### CloudWatch Log Groups

The module creates two log groups:
- `/ecs/{project_name}-{environment}-api` - For API service logs
- `/ecs/{project_name}-{environment}-worker` - For worker service logs

Log retention is configurable via `log_retention_days` variable.

### CloudWatch Alarms

The module creates the following alarms:

1. **API 5XX Errors**: Triggers when 5XX error count exceeds threshold in 5 minutes
2. **API Latency**: Triggers when p95 latency exceeds threshold
3. **RDS CPU**: Triggers when CPU utilization exceeds threshold
4. **RDS Connections**: Triggers when connection count exceeds percentage of max
5. **ECS Task Count**: Triggers when running task count falls below minimum

All alarms send notifications to the configured SNS topic.

### SNS Topic

The module creates an SNS topic for alarm notifications with:
- Email subscription to the configured alert email
- KMS encryption for security
- Automatic key rotation enabled

**Note**: You must confirm the email subscription after the first deployment.

### CloudWatch Dashboard

The module creates a comprehensive dashboard with widgets for:

**API Metrics**:
- Request count
- Latency (p50, p95, p99)
- Error rates (4XX, 5XX)

**Database Metrics**:
- CPU utilization
- Database connections
- Freeable memory

**ECS Metrics**:
- CPU utilization
- Memory utilization
- Running task count

**Redis Metrics**:
- CPU utilization
- Memory usage percentage
- Current connections

**ALB Metrics**:
- Request count
- Target response time

### X-Ray Tracing

The module creates X-Ray sampling rules:

1. **Default Rule**: Samples a percentage of all requests (configurable)
2. **Errors Rule**: Samples 100% of error requests for debugging

## Accessing Monitoring Data

### CloudWatch Logs

View logs in the AWS Console:
```
CloudWatch > Log groups > /ecs/{project_name}-{environment}-api
CloudWatch > Log groups > /ecs/{project_name}-{environment}-worker
```

Query logs using CloudWatch Logs Insights:
```sql
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100
```

### CloudWatch Dashboard

Access the dashboard:
```
CloudWatch > Dashboards > {project_name}-{environment}-dashboard
```

### CloudWatch Alarms

View alarms:
```
CloudWatch > Alarms > All alarms
```

Filter by tag:
```
Environment: {environment}
```

### X-Ray Traces

View traces:
```
X-Ray > Traces
```

Filter by service:
```
Service: {project_name}-{environment}-api
```

## Alarm Notification Setup

After deploying the module:

1. Check your email for an SNS subscription confirmation
2. Click the confirmation link
3. You will now receive alarm notifications

To test alarm notifications:
```bash
# Trigger a test alarm
aws cloudwatch set-alarm-state \
  --alarm-name {project_name}-{environment}-api-5xx-errors \
  --state-value ALARM \
  --state-reason "Testing alarm notification"
```

## Cost Optimization

### Log Retention

Adjust log retention based on environment:
- Dev: 7 days ($0.50/GB/month)
- Staging: 14 days
- Prod: 30 days

### X-Ray Sampling

Adjust sampling rate to control costs:
- Dev: 10% sampling (lower cost)
- Prod: 20% sampling (better visibility)

X-Ray pricing: $5 per 1 million traces recorded

### Dashboard

Dashboards are free for the first 3 dashboards, then $3/month per dashboard.

## Troubleshooting

### Alarms Not Triggering

1. Check that metrics are being published:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/ApplicationELB \
     --metric-name RequestCount \
     --start-time 2024-01-01T00:00:00Z \
     --end-time 2024-01-01T01:00:00Z \
     --period 300 \
     --statistics Sum
   ```

2. Verify alarm configuration:
   ```bash
   aws cloudwatch describe-alarms \
     --alarm-names {project_name}-{environment}-api-5xx-errors
   ```

### Email Notifications Not Received

1. Check SNS subscription status:
   ```bash
   aws sns list-subscriptions-by-topic \
     --topic-arn {sns_topic_arn}
   ```

2. Confirm the subscription if pending:
   - Check your email for confirmation link
   - Click the link to confirm

### Dashboard Not Showing Data

1. Verify that services are running and publishing metrics
2. Check that the correct region is selected in the dashboard
3. Adjust the time range to ensure data is available

### X-Ray Traces Not Appearing

1. Verify X-Ray daemon is running in ECS tasks
2. Check that X-Ray SDK is installed in application
3. Verify IAM permissions for X-Ray
4. Check sampling rules are configured correctly

## Integration with ECS Tasks

To use the log groups in ECS task definitions:

```hcl
resource "aws_ecs_task_definition" "api" {
  # ... other configuration

  container_definitions = jsonencode([{
    name  = "api"
    image = "..."

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = module.monitoring.log_group_api_name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "api"
      }
    }
  }])
}
```

## Integration with X-Ray

To enable X-Ray tracing in ECS tasks:

```hcl
resource "aws_ecs_task_definition" "api" {
  # ... other configuration

  container_definitions = jsonencode([
    {
      name  = "api"
      image = "..."
      # ... other configuration
    },
    {
      name  = "xray-daemon"
      image = "public.ecr.aws/xray/aws-xray-daemon:latest"
      cpu   = 32
      memoryReservation = 256
      portMappings = [{
        containerPort = 2000
        protocol      = "udp"
      }]
    }
  ])
}
```

## Outputs

The module provides the following outputs:

- `log_group_api_name` - Name of the API log group
- `log_group_worker_name` - Name of the worker log group
- `sns_topic_arn` - ARN of the SNS topic for alarms
- `dashboard_name` - Name of the CloudWatch dashboard
- `*_alarm_arn` - ARNs of all created alarms

Use these outputs in other modules:

```hcl
# In compute module
resource "aws_ecs_task_definition" "api" {
  container_definitions = jsonencode([{
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group" = module.monitoring.log_group_api_name
      }
    }
  }])
}
```

## Best Practices

1. **Set appropriate alarm thresholds** based on your application's baseline performance
2. **Use different log retention periods** for different environments to optimize costs
3. **Confirm SNS email subscriptions** immediately after deployment
4. **Review dashboard regularly** to understand application behavior
5. **Adjust X-Ray sampling rates** based on traffic volume and debugging needs
6. **Use CloudWatch Logs Insights** for advanced log analysis
7. **Set up alarm actions** for critical alarms (e.g., auto-scaling, Lambda functions)
8. **Tag all resources** for cost allocation and organization

## References

- [CloudWatch Logs Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/)
- [CloudWatch Alarms Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html)
- [CloudWatch Dashboards Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Dashboards.html)
- [X-Ray Documentation](https://docs.aws.amazon.com/xray/latest/devguide/aws-xray.html)
- [SNS Documentation](https://docs.aws.amazon.com/sns/latest/dg/)
