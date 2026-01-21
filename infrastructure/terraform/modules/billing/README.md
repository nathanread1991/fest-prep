# Billing and Cost Management Module

This Terraform module sets up comprehensive AWS billing alerts and cost monitoring for the Festival Playlist Generator project.

## Features

- **AWS Budgets**: Multiple budget thresholds ($10, $20, $30) with email notifications
- **Cost Anomaly Detection**: Automatic detection of unusual spending patterns
- **SNS Notifications**: Centralized alert delivery via email
- **CloudWatch Dashboard**: Visual cost monitoring dashboard
- **Cost Allocation Tags**: Automatic tagging for cost tracking

## Important: Region Configuration

**Primary Region**: This module deploys to your configured AWS region (default: `eu-west-2` for London).

**Special Case - CloudWatch Billing Metrics**: AWS billing metrics are ONLY available in `us-east-1` region. The CloudWatch dashboard in this module will need to query `us-east-1` for billing data, even if your other resources are in `eu-west-2`.

**What this means**:
- SNS topics, budgets, and anomaly detection: Deploy to your primary region (`eu-west-2`)
- CloudWatch billing dashboard: Must query `us-east-1` for billing metrics
- This is an AWS limitation, not a module limitation
- All other infrastructure (ECS, RDS, etc.) will be in `eu-west-2`

## Resources Created

1. **SNS Topic**: `festival-playlist-{env}-budget-alerts`
   - Receives all budget and anomaly alerts
   - Supports email subscriptions
   - Optional KMS encryption

2. **AWS Budgets**:
   - Monthly total budget with 50%, 80%, 100% alerts
   - $10 threshold budget
   - $20 threshold budget
   - $30 threshold budget

3. **Cost Anomaly Detection**:
   - Service-level anomaly monitoring
   - Daily anomaly reports
   - Configurable threshold ($5 default)

4. **CloudWatch Dashboard**:
   - Estimated monthly charges visualization
   - Real-time cost tracking

## Usage

```hcl
module "billing" {
  source = "./modules/billing"

  project_name         = "festival-playlist"
  environment          = "dev"
  monthly_budget_limit = "30"
  
  alert_email_addresses = [
    "developer@example.com",
    "admin@example.com"
  ]
  
  anomaly_threshold = "5"
  enable_encryption = false
  
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
| project_name | Name of the project | string | "festival-playlist" | no |
| environment | Environment name (dev, staging, prod) | string | - | yes |
| monthly_budget_limit | Monthly budget limit in USD | string | "30" | no |
| alert_email_addresses | List of email addresses for alerts | list(string) | - | yes |
| anomaly_threshold | Minimum dollar amount for anomaly alerts | string | "5" | no |
| enable_encryption | Enable KMS encryption for SNS | bool | false | no |
| common_tags | Common tags for all resources | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| sns_topic_arn | ARN of the SNS topic for budget alerts |
| sns_topic_name | Name of the SNS topic |
| budget_names | Names of all created budgets |
| anomaly_monitor_arn | ARN of the cost anomaly monitor |
| anomaly_subscription_arn | ARN of the anomaly subscription |
| cost_dashboard_name | Name of the CloudWatch dashboard |

## Budget Alert Thresholds

### Monthly Total Budget
- **50% Alert**: Early warning when half the budget is consumed
- **80% Alert**: Critical warning to review spending
- **100% Alert**: Budget exceeded notification
- **Forecasted 100%**: Predictive alert if spending trends indicate budget will be exceeded

### Fixed Thresholds
- **$10 Alert**: First cost threshold
- **$20 Alert**: Second cost threshold
- **$30 Alert**: Third cost threshold (matches default monthly limit)

## Cost Anomaly Detection

The module monitors spending patterns and alerts when:
- Spending increases significantly compared to historical patterns
- New services are used unexpectedly
- Service costs spike above normal levels

**Default threshold**: $5 (alerts when anomaly impact >= $5)

## Email Subscription Confirmation

After applying this module, AWS will send confirmation emails to all addresses in `alert_email_addresses`. Recipients must click the confirmation link to start receiving alerts.

## Cost Allocation Tags

All resources are tagged with:
- `Project`: Project name
- `Environment`: Environment name
- `Module`: "billing"
- `ManagedBy`: "terraform"

These tags enable cost tracking and filtering in AWS Cost Explorer.

## Viewing Costs

### AWS Console
1. Navigate to **AWS Cost Management** → **Cost Explorer**
2. Enable Cost Explorer (free, one-time setup)
3. Filter by tags: `Project=festival-playlist` and `Environment=dev`
4. View costs by service, time period, or custom groupings

### CloudWatch Dashboard
1. Navigate to **CloudWatch** → **Dashboards**
2. Open `festival-playlist-{env}-cost-monitoring`
3. View estimated monthly charges graph

### AWS Budgets
1. Navigate to **AWS Cost Management** → **Budgets**
2. View all configured budgets and their current status
3. See alerts history and forecasts

## Terraform Commands

```bash
# Initialize module
terraform init

# Plan changes
terraform plan

# Apply configuration
terraform apply

# View outputs
terraform output

# Destroy resources (keeps historical data)
terraform destroy
```

## Notes

- **Cost Explorer**: Must be enabled manually in AWS Console (one-time, free)
- **Email Confirmation**: Required for SNS subscriptions to work
- **Billing Data Delay**: AWS billing data updates every 24 hours
- **Anomaly Detection**: Requires 10-14 days of data to establish baseline
- **Budget Filters**: Budgets filter by Project and Environment tags

## Troubleshooting

### Not Receiving Alerts
1. Check SNS subscription status in AWS Console
2. Confirm email addresses in spam/junk folders
3. Verify budget thresholds are configured correctly
4. Check CloudWatch Logs for SNS delivery failures

### Cost Explorer Not Available
1. Enable Cost Explorer in AWS Console: **Cost Management** → **Cost Explorer** → **Enable**
2. Wait 24 hours for initial data population

### Anomaly Detection Not Working
1. Ensure at least 10 days of billing data exists
2. Check anomaly threshold is appropriate for spending levels
3. Verify SNS topic permissions allow Cost Explorer to publish

## Security Considerations

- SNS topic can optionally use KMS encryption (set `enable_encryption = true`)
- Email addresses are stored in Terraform state (use remote state with encryption)
- Budget data is not sensitive but alerts contain cost information
- Consider using AWS Chatbot for Slack/Teams integration instead of email

## Cost of This Module

- **AWS Budgets**: First 2 budgets free, then $0.02/day per budget
  - This module creates 4 budgets = $0.06/day = ~$1.80/month
- **Cost Anomaly Detection**: Free
- **SNS**: First 1,000 email notifications free, then $2 per 100,000
- **CloudWatch Dashboard**: First 3 dashboards free, then $3/month per dashboard

**Total estimated cost**: ~$1.80/month (assuming < 1,000 notifications)

## Related Documentation

- [AWS Budgets Documentation](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
- [Cost Anomaly Detection](https://docs.aws.amazon.com/cost-management/latest/userguide/manage-ad.html)
- [AWS Cost Explorer](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-what-is.html)
- [SNS Email Notifications](https://docs.aws.amazon.com/sns/latest/dg/sns-email-notifications.html)
