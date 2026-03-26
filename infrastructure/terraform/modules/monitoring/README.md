# Monitoring Module

This Terraform module creates comprehensive monitoring infrastructure for the Festival Playlist Generator, including CloudWatch log groups, alarms, dashboards, and AWS X-Ray tracing configuration.

## Features

- **CloudWatch Log Groups**: Centralized logging for ECS API and worker services
- **CloudWatch Alarms**: Automated alerting for critical metrics (API errors, latency, RDS, ECS)
- **SNS Notifications**: Email alerts for alarm events with KMS encryption
- **CloudWatch Dashboard**: Comprehensive visualization of application and infrastructure metrics
- **X-Ray Tracing**: Distributed tracing with configurable sampling rules
- **Cost Optimized**: Configurable retention periods and sampling rates

## Resources Created

### CloudWatch Log Groups
- `/ecs/{project_name}-{environment}-api` - API service logs
- `/ecs/{project_name}-{environment}-worker` - Worker service logs

### CloudWatch Alarms
- **API 5XX Errors**: Triggers when error count > 10 in 5 minutes
- **API Latency**: Triggers when p95 latency > 1000ms
- **RDS CPU**: Triggers when CPU utilization > 80%
- **RDS Connections**: Triggers when connections > 80% of max
- **ECS Task Count**: Triggers when running tasks < 1

### SNS Topic
- Alarm notification topic with email subscription
- KMS encryption with automatic key rotation

### CloudWatch Dashboard
Includes widgets for:
- API metrics (requests, latency, errors)
- RDS metrics (CPU, memory, connections)
- ECS metrics (CPU, memory, task count)
- Redis metrics (CPU, memory, connections)
- ALB metrics (requests, response time)

### X-Ray Sampling Rules
- Default rule: 10% sampling (configurable)
- Errors rule: 100% sampling for debugging

## Usage

```hcl
module "monitoring" {
  source = "./modules/monitoring"

  # Required variables
  project_name            = "festival-playlist"
  environment             = "dev"
  cluster_name            = module.compute.cluster_name
  api_service_name        = module.compute.api_service_name
  worker_service_name     = module.compute.worker_service_name
  db_cluster_id           = module.database.cluster_id
  redis_cluster_id        = module.cache.redis_cluster_id
  alb_arn_suffix          = module.compute.alb_arn_suffix
  target_group_arn_suffix = module.compute.target_group_arn_suffix
  alert_email             = "alerts@example.com"

  # Optional variables
  log_retention_days      = 7
  enable_alarms           = true
  enable_dashboard        = true
  enable_xray             = true
  xray_sampling_rate      = 0.1

  common_tags = {
    Project     = "festival-playlist"
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

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project | `string` | n/a | yes |
| environment | Environment name (dev, staging, prod) | `string` | n/a | yes |
| cluster_name | Name of the ECS cluster | `string` | n/a | yes |
| api_service_name | Name of the API ECS service | `string` | n/a | yes |
| worker_service_name | Name of the worker ECS service | `string` | n/a | yes |
| db_cluster_id | ID of the RDS cluster | `string` | n/a | yes |
| redis_cluster_id | ID of the ElastiCache Redis cluster | `string` | n/a | yes |
| alb_arn_suffix | ARN suffix of the Application Load Balancer | `string` | n/a | yes |
| target_group_arn_suffix | ARN suffix of the ALB target group | `string` | n/a | yes |
| alert_email | Email address for alarm notifications | `string` | n/a | yes |
| log_retention_days | Number of days to retain CloudWatch logs | `number` | `7` | no |
| enable_alarms | Enable CloudWatch alarms | `bool` | `true` | no |
| enable_dashboard | Enable CloudWatch dashboard | `bool` | `true` | no |
| enable_xray | Enable AWS X-Ray tracing | `bool` | `true` | no |
| xray_sampling_rate | X-Ray sampling rate (0.0 to 1.0) | `number` | `0.1` | no |
| api_error_rate_threshold | Threshold for API 5XX error count in 5 minutes | `number` | `10` | no |
| api_latency_threshold | Threshold for API p95 latency in milliseconds | `number` | `1000` | no |
| db_cpu_threshold | Threshold for RDS CPU utilization percentage | `number` | `80` | no |
| db_connections_threshold_percent | Threshold for RDS connections as percentage of max | `number` | `80` | no |
| ecs_min_task_count | Minimum number of ECS tasks (alarm if below) | `number` | `1` | no |
| common_tags | Common tags to apply to all resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| log_group_api_name | Name of the CloudWatch log group for API service |
| log_group_api_arn | ARN of the CloudWatch log group for API service |
| log_group_worker_name | Name of the CloudWatch log group for worker service |
| log_group_worker_arn | ARN of the CloudWatch log group for worker service |
| sns_topic_arn | ARN of the SNS topic for alarm notifications |
| sns_topic_name | Name of the SNS topic for alarm notifications |
| dashboard_name | Name of the CloudWatch dashboard |
| dashboard_arn | ARN of the CloudWatch dashboard |
| api_5xx_alarm_arn | ARN of the API 5XX errors alarm |
| api_latency_alarm_arn | ARN of the API latency alarm |
| rds_cpu_alarm_arn | ARN of the RDS CPU alarm |
| rds_connections_alarm_arn | ARN of the RDS connections alarm |
| ecs_task_count_alarm_arn | ARN of the ECS task count alarm |
| xray_default_sampling_rule_arn | ARN of the default X-Ray sampling rule |
| xray_errors_sampling_rule_arn | ARN of the errors X-Ray sampling rule |
| kms_key_id | ID of the KMS key for SNS encryption |
| kms_key_arn | ARN of the KMS key for SNS encryption |

## Post-Deployment Steps

1. **Confirm SNS Email Subscription**
   - Check your email for an SNS subscription confirmation
   - Click the confirmation link to start receiving alarm notifications

2. **Verify Log Groups**
   - Deploy ECS tasks with log configuration pointing to the created log groups
   - Verify logs are appearing in CloudWatch

3. **Test Alarms**
   - Trigger test alarms to verify notifications are working
   - Adjust thresholds based on actual application behavior

4. **Review Dashboard**
   - Access the CloudWatch dashboard in AWS Console
   - Verify all widgets are showing data
   - Customize as needed

5. **Enable X-Ray in Application**
   - Install X-Ray SDK in application code
   - Add X-Ray daemon sidecar to ECS task definitions
   - Verify traces are appearing in X-Ray console

## Cost Estimate

- **CloudWatch Logs**: $2-5/month (depends on log volume)
- **CloudWatch Alarms**: Free (5 alarms, first 10 are free)
- **CloudWatch Dashboard**: Free (1 dashboard, first 3 are free)
- **X-Ray**: Free (with 10% sampling, under 100K traces/month)
- **SNS**: Free (typical alarm volume)
- **KMS**: $1-2/month (key storage)

**Total**: $3-8/month

## Documentation

- [USAGE.md](./USAGE.md) - Detailed usage guide with examples
- [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) - Implementation details
- [CHECKLIST.md](./CHECKLIST.md) - Implementation checklist

## Requirements Met

- **US-5.1**: Structured JSON logging to CloudWatch Logs
- **US-5.2**: CloudWatch Metrics for key performance indicators
- **US-5.3**: CloudWatch Alarms for critical issues
- **US-5.4**: CloudWatch Dashboards for application and infrastructure metrics
- **US-5.5**: AWS X-Ray distributed tracing
- **US-3.3**: Cost optimization through configurable retention

## License

This module is part of the Festival Playlist Generator project.
