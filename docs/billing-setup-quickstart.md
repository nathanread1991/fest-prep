# Billing Setup Quick Start

This is a condensed guide for setting up AWS billing alerts. For detailed instructions, see [aws-account-setup.md](./aws-account-setup.md).

## Prerequisites

- AWS account with admin access
- AWS CLI installed and configured
- Terraform >= 1.5 installed

## Quick Setup (5 minutes)

### 1. Configure AWS CLI

```bash
aws configure --profile festival-playlist
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: eu-west-2
# Default output format: json
```

### 2. Enable Cost Explorer

1. Go to [AWS Cost Explorer](https://console.aws.amazon.com/cost-management/home#/cost-explorer)
2. Click **Enable Cost Explorer**
3. Wait 24 hours for data population

**Note**: Skip "Cost Allocation Tags" for now - activate them after deploying resources.

### 3. Configure Terraform Variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and update:
- `alert_email_addresses`: Your email address(es)
- Other values as needed

### 4. Deploy Billing Module

```bash
# Initialize Terraform
terraform init

# Review changes
terraform plan

# Apply configuration
terraform apply
# Type 'yes' when prompted
```

### 5. Confirm Email Subscriptions

1. Check your email inbox
2. Look for "AWS Notification - Subscription Confirmation"
3. Click **Confirm subscription** in each email

### 6. Verify Setup

```bash
# Run verification script
./scripts/verify-billing-setup.sh
```

## What Gets Created

- **4 AWS Budgets**: $10, $20, $30 thresholds + monthly total
- **SNS Topic**: For email notifications
- **Cost Anomaly Detection**: Automatic spending anomaly alerts
- **CloudWatch Dashboard**: Visual cost monitoring

## Budget Alert Thresholds

| Budget | Threshold | Alert When |
|--------|-----------|------------|
| Monthly Total | 50% | Half budget consumed |
| Monthly Total | 80% | Critical warning |
| Monthly Total | 100% | Budget exceeded |
| Threshold $10 | 100% | Spending exceeds $10 |
| Threshold $20 | 100% | Spending exceeds $20 |
| Threshold $30 | 100% | Spending exceeds $30 |

## Viewing Costs

### AWS Console
- **Budgets**: [AWS Budgets Console](https://console.aws.amazon.com/billing/home#/budgets)
- **Cost Explorer**: [Cost Explorer](https://console.aws.amazon.com/cost-management/home#/cost-explorer)
- **Dashboard**: CloudWatch → Dashboards → `festival-playlist-dev-cost-monitoring`

### AWS CLI

```bash
# View current month costs
aws ce get-cost-and-usage \
  --time-period Start=2026-01-01,End=2026-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --profile festival-playlist

# List all budgets
aws budgets describe-budgets \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --profile festival-playlist
```

## Cost of Billing Module

- **AWS Budgets**: First 2 free, then $0.02/day per budget
  - 4 budgets = $0.06/day = ~$1.80/month
- **Cost Anomaly Detection**: Free
- **SNS Email**: First 1,000 notifications free
- **CloudWatch Dashboard**: First 3 dashboards free

**Total**: ~$1.80/month

## Troubleshooting

### Not receiving emails?
1. Check spam/junk folder
2. Verify subscription confirmed (check SNS console)
3. Re-run `terraform apply` if needed

### Cost Explorer not available?
1. Enable in AWS Console (one-time setup)
2. Wait 24 hours for data

### Cost Allocation Tags not visible?
1. Tags only appear after resources are created
2. Deploy resources first, then activate tags
3. Wait 24 hours after deployment
4. This is normal - not an error

### "Account not in AWS Organization" message?
1. This is normal for standalone accounts
2. Ignore this message - it doesn't affect functionality
3. AWS Organizations is only for multi-account setups

### Terraform errors?
1. Check AWS credentials: `aws sts get-caller-identity --profile festival-playlist`
2. Verify IAM permissions (need admin or billing access)
3. Check Terraform version: `terraform version` (need >= 1.5)

## Next Steps

After billing setup is complete:

1. ✅ Billing alerts configured
2. ✅ Email notifications confirmed
3. ✅ Cost monitoring active

**Proceed to**: Task 2 - Initialize Terraform project structure

## Important Notes

- **Email confirmation required**: Alerts won't work until you confirm subscriptions
- **24-hour delay**: Billing data updates once per day
- **Anomaly detection**: Needs 10-14 days to establish baseline
- **Cost allocation tags**: Activate AFTER deploying resources (not before)
  - Tags won't appear until resources exist
  - Wait 24 hours after deployment
  - Then activate in Cost Management → Cost Allocation Tags
  - This is optional but helpful for detailed cost tracking

## Support

- Full documentation: [aws-account-setup.md](./aws-account-setup.md)
- Terraform module: [terraform/modules/billing/README.md](../terraform/modules/billing/README.md)
- Verification script: `./scripts/verify-billing-setup.sh`
