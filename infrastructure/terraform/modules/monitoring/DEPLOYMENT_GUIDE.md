# Monitoring Module - Deployment Guide

## Overview

This guide walks through deploying the monitoring module and integrating it with your infrastructure.

## Prerequisites

- Terraform >= 1.5
- AWS CLI configured with appropriate credentials
- Existing infrastructure modules deployed (compute, database, cache)
- Valid email address for alarm notifications

## Deployment Steps

### Step 1: Add Module to Root Configuration

In your root `main.tf`, add the monitoring module:

```hcl
module "monitoring" {
  source = "./modules/monitoring"

  # Required variables
  project_name            = var.project_name
  environment             = var.environment
  cluster_name            = module.compute.cluster_name
  api_service_name        = module.compute.api_service_name
  worker_service_name     = module.compute.worker_service_name
  db_cluster_id           = module.database.cluster_id
  redis_cluster_id        = module.cache.redis_cluster_id
  alb_arn_suffix          = module.compute.alb_arn_suffix
  target_group_arn_suffix = module.compute.target_group_arn_suffix
  alert_email             = var.alert_email

  # Environment-specific configuration
  log_retention_days = var.environment == "prod" ? 30 : 7

  common_tags = var.common_tags
}
```

### Step 2: Add Required Variables

In your root `variables.tf`, add:

```hcl
variable "alert_email" {
  description = "Email address for alarm notifications"
  type        = string
}
```

In your `terraform.tfvars`:

```hcl
alert_email = "your-email@example.com"
```

### Step 3: Update Compute Module

Update your ECS task definitions to use the monitoring log groups:

```hcl
# In modules/compute/main.tf

resource "aws_ecs_task_definition" "api" {
  # ... existing configuration

  container_definitions = jsonencode([
    {
      name  = "api"
      image = "${var.ecr_repository_url}:latest"

      # Add log configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.log_group_api_name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "api"
        }
      }

      # ... rest of configuration
    }
  ])
}

resource "aws_ecs_task_definition" "worker" {
  # ... existing configuration

  container_definitions = jsonencode([
    {
      name  = "worker"
      image = "${var.ecr_repository_url}:latest"

      # Add log configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.log_group_worker_name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "worker"
        }
      }

      # ... rest of configuration
    }
  ])
}
```

Add to `modules/compute/variables.tf`:

```hcl
variable "log_group_api_name" {
  description = "Name of the CloudWatch log group for API service"
  type        = string
}

variable "log_group_worker_name" {
  description = "Name of the CloudWatch log group for worker service"
  type        = string
}
```

Update root `main.tf` to pass log group names:

```hcl
module "compute" {
  source = "./modules/compute"

  # ... existing variables

  log_group_api_name    = module.monitoring.log_group_api_name
  log_group_worker_name = module.monitoring.log_group_worker_name
}
```

### Step 4: Enable X-Ray in ECS Tasks

Add X-Ray daemon sidecar to your ECS task definitions:

```hcl
resource "aws_ecs_task_definition" "api" {
  # ... existing configuration

  container_definitions = jsonencode([
    {
      name  = "api"
      # ... existing configuration

      environment = [
        # ... existing environment variables
        {
          name  = "AWS_XRAY_DAEMON_ADDRESS"
          value = "xray-daemon:2000"
        }
      ]
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

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.log_group_api_name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "xray-daemon"
        }
      }
    }
  ])
}
```

Update ECS task role to allow X-Ray:

```hcl
resource "aws_iam_role_policy_attachment" "ecs_task_xray" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}
```

### Step 5: Deploy the Module

```bash
# Initialize Terraform (if not already done)
terraform init

# Review the plan
terraform plan

# Apply the changes
terraform apply
```

### Step 6: Confirm SNS Email Subscription

1. Check your email for an SNS subscription confirmation
2. Click the confirmation link
3. You should see a confirmation message in your browser

### Step 7: Verify Deployment

```bash
# Verify log groups created
aws logs describe-log-groups \
  --log-group-name-prefix "/ecs/festival-playlist"

# Verify alarms created
aws cloudwatch describe-alarms \
  --alarm-name-prefix "festival-playlist-${ENVIRONMENT}"

# Verify dashboard created
aws cloudwatch list-dashboards

# Verify X-Ray sampling rules
aws xray get-sampling-rules
```

### Step 8: Test Alarm Notifications

```bash
# Trigger a test alarm
aws cloudwatch set-alarm-state \
  --alarm-name "festival-playlist-${ENVIRONMENT}-api-5xx-errors" \
  --state-value ALARM \
  --state-reason "Testing alarm notification"

# Check your email for the notification
```

### Step 9: View Dashboard

1. Open AWS Console
2. Navigate to CloudWatch > Dashboards
3. Select `festival-playlist-${ENVIRONMENT}-dashboard`
4. Verify widgets are showing data (may take a few minutes)

### Step 10: Install X-Ray SDK in Application

In your application code:

```python
# Install X-Ray SDK
# pip install aws-xray-sdk

# In your FastAPI application
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.ext.flask.middleware import XRayMiddleware

app = FastAPI()

# Configure X-Ray
xray_recorder.configure(
    service='festival-playlist-api',
    sampling=False,  # Use sampling rules from AWS
    context_missing='LOG_ERROR'
)

# Add X-Ray middleware
app.add_middleware(XRayMiddleware, recorder=xray_recorder)

# Instrument database queries
from aws_xray_sdk.core import patch_all
patch_all()
```

## Verification Checklist

- [ ] Log groups created in CloudWatch
- [ ] Logs appearing in log groups
- [ ] All 5 alarms created
- [ ] SNS topic created
- [ ] Email subscription confirmed
- [ ] Test alarm notification received
- [ ] Dashboard created and showing data
- [ ] X-Ray sampling rules created
- [ ] X-Ray traces appearing in console
- [ ] KMS key created with rotation enabled

## Troubleshooting

### Logs Not Appearing

**Problem**: No logs in CloudWatch log groups

**Solution**:
1. Verify ECS task definition has correct log configuration
2. Check ECS task execution role has CloudWatch Logs permissions
3. Verify log group names match exactly
4. Check ECS task logs for errors

### Alarms Not Triggering

**Problem**: Alarms not sending notifications

**Solution**:
1. Verify SNS email subscription is confirmed
2. Check that metrics are being published
3. Verify alarm thresholds are appropriate
4. Test alarm manually with `set-alarm-state`

### Dashboard Not Showing Data

**Problem**: Dashboard widgets are empty

**Solution**:
1. Wait a few minutes for metrics to populate
2. Verify services are running and generating metrics
3. Check time range in dashboard
4. Verify metric names and dimensions are correct

### X-Ray Traces Not Appearing

**Problem**: No traces in X-Ray console

**Solution**:
1. Verify X-Ray daemon is running in ECS task
2. Check X-Ray SDK is installed in application
3. Verify ECS task role has X-Ray permissions
4. Check X-Ray daemon logs for errors
5. Verify sampling rules are configured

## Cost Monitoring

After deployment, monitor costs:

```bash
# Get cost estimate for monitoring resources
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter file://filter.json

# filter.json
{
  "Tags": {
    "Key": "Module",
    "Values": ["monitoring"]
  }
}
```

Expected costs:
- CloudWatch Logs: $2-5/month
- CloudWatch Alarms: Free (under 10 alarms)
- CloudWatch Dashboard: Free (under 3 dashboards)
- X-Ray: Free (under 100K traces/month)
- SNS: Free (typical volume)
- KMS: $1-2/month

**Total**: $3-8/month

## Next Steps

1. **Customize Alarm Thresholds**: Adjust based on actual application behavior
2. **Add Custom Metrics**: Publish application-specific metrics
3. **Create Log Insights Queries**: Save common queries for quick access
4. **Set Up Anomaly Detection**: Enable CloudWatch anomaly detection
5. **Add More Alarms**: Create alarms for additional metrics as needed
6. **Integrate with PagerDuty**: Add PagerDuty integration for on-call alerting
7. **Create Runbooks**: Document response procedures for each alarm

## References

- [Module README](./README.md)
- [Usage Guide](./USAGE.md)
- [Implementation Summary](./IMPLEMENTATION_SUMMARY.md)
- [AWS CloudWatch Documentation](https://docs.aws.amazon.com/cloudwatch/)
- [AWS X-Ray Documentation](https://docs.aws.amazon.com/xray/)
