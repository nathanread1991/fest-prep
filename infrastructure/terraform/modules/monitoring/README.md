# Monitoring Module

This module manages CloudWatch logs, metrics, alarms, and X-Ray tracing for the Festival Playlist Generator.

## Resources Created

- CloudWatch log groups (ECS API, ECS Worker)
- CloudWatch alarms (API errors, latency, RDS, ECS)
- CloudWatch dashboard
- SNS topic for alarm notifications
- X-Ray sampling rules

## Alarms

### API Alarms
- Error rate (5XX > 10 in 5 min)
- Latency (p95 > 1000ms)

### Database Alarms
- CPU utilization (> 80%)
- Connection count (> 80% of max)

### ECS Alarms
- Task count (< 1)

## Dashboard Widgets

- API request count, latency, errors
- RDS CPU, memory, connections
- ECS CPU, memory, task count
- Redis CPU, memory, connections
- ALB request count, latency, errors

## Usage

```hcl
module "monitoring" {
  source = "./modules/monitoring"
  
  project_name         = var.project_name
  environment          = var.environment
  cluster_name         = module.compute.cluster_id
  api_service_name     = module.compute.api_service_name
  worker_service_name  = module.compute.worker_service_name
  db_cluster_id        = module.database.cluster_id
  redis_cluster_id     = module.cache.redis_cluster_id
  alb_arn_suffix       = module.compute.alb_arn_suffix
  alert_email          = var.alert_email
  common_tags          = var.common_tags
}
```

## Outputs

- log_group_api_name
- log_group_worker_name
- dashboard_name
- sns_topic_arn
