# AWS Account Setup Guide

This guide walks you through setting up your AWS account and configuring billing alerts for the Festival Playlist Generator migration.

## Prerequisites

- AWS account (new or existing)
- Email address for billing alerts
- Credit card for AWS billing
- AWS CLI installed (optional but recommended)

## Step 1: Create or Access AWS Account

### For New AWS Account

1. Go to [https://aws.amazon.com](https://aws.amazon.com)
2. Click **Create an AWS Account**
3. Follow the registration process:
   - Provide email address and account name
   - Enter contact information
   - Add payment method (credit card)
   - Verify identity (phone verification)
   - Choose **Basic Support Plan** (free)
4. Wait for account activation (usually instant)

### For Existing AWS Account

1. Sign in to [AWS Console](https://console.aws.amazon.com)
2. Verify you have administrative access
3. Ensure billing information is up to date

## Step 2: Enable IAM User Access to Billing

By default, only the root account can access billing. Enable IAM access:

1. Sign in as **root user** (not IAM user)
2. Navigate to **Account** → **Account Settings**
3. Scroll to **IAM User and Role Access to Billing Information**
4. Click **Edit**
5. Check **Activate IAM Access**
6. Click **Update**

## Step 3: Create IAM User for Terraform

Create a dedicated IAM user for infrastructure management:

1. Navigate to **IAM** → **Users** → **Create user**
2. User name: `terraform-admin`
3. Enable **Programmatic access** (Access key)
4. Attach policies:
   - `AdministratorAccess` (for initial setup)
   - Or create custom policy with required permissions
5. Click **Create user**
6. **IMPORTANT**: Save the Access Key ID and Secret Access Key
7. Store credentials securely (use AWS Secrets Manager or password manager)

### Configure AWS CLI

```bash
# Configure AWS CLI with Terraform user credentials
aws configure --profile festival-playlist

# Enter when prompted:
# AWS Access Key ID: <your-access-key-id>
# AWS Secret Access Key: <your-secret-access-key>
# Default region name: eu-west-2
# Default output format: json

# Test configuration
aws sts get-caller-identity --profile festival-playlist
```

## Step 4: Enable Cost Explorer

Cost Explorer must be enabled before using AWS Budgets and Cost Anomaly Detection:

1. Navigate to **AWS Cost Management** → **Cost Explorer**
2. Click **Enable Cost Explorer**
3. Wait 24 hours for initial data population
4. Cost Explorer is **free** to use

## Step 5: Set Up Cost Allocation Tags (Optional - Can Do Later)

Cost allocation tags help track spending by project, environment, etc. **Note**: This step can be completed after deploying resources, as tags need to exist before they can be activated.

**Option A: Activate Now (Tags won't appear until resources are created)**
1. Navigate to **AWS Cost Management** → **Cost Allocation Tags**
2. You won't see any tags yet (no resources created)
3. Skip to Step 6 and return here after deploying Terraform

**Option B: Activate After Deployment (Recommended)**
1. Deploy Terraform resources first (Step 6)
2. Wait 24 hours for tags to appear in AWS
3. Return to **Cost Allocation Tags** page
4. Click **Activate** for these user-defined tags:
   - `Project`
   - `Environment`
   - `ManagedBy`
   - `Module`
   - `CostCenter`
   - `Owner`
5. Wait another 24 hours for tags to appear in Cost Explorer

**Why Optional**: 
- Tags are automatically applied to resources by Terraform
- Cost tracking works without activating tags
- Activating tags just makes them filterable in Cost Explorer
- You can activate them anytime (even months later)

**Recommendation**: Skip this step for now, deploy resources first, then activate tags after 24 hours.

## Step 6: Deploy Billing Module with Terraform

### Create Terraform Configuration

Create `terraform/main.tf`:

```hcl
terraform {
  required_version = ">= 1.5"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = "eu-west-2"
  profile = "festival-playlist"
  
  default_tags {
    tags = {
      Project     = "festival-playlist"
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}

module "billing" {
  source = "./modules/billing"

  project_name         = "festival-playlist"
  environment          = "dev"
  monthly_budget_limit = "30"
  
  alert_email_addresses = [
    "your-email@example.com"  # Replace with your email
  ]
  
  anomaly_threshold = "5"
  enable_encryption = false
  
  common_tags = {
    Project     = "festival-playlist"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}

output "sns_topic_arn" {
  value       = module.billing.sns_topic_arn
  description = "SNS topic ARN for budget alerts"
}

output "budget_names" {
  value       = module.billing.budget_names
  description = "Names of created budgets"
}
```

### Initialize and Apply Terraform

```bash
# Navigate to terraform directory
cd terraform

# Initialize Terraform
terraform init

# Review planned changes
terraform plan

# Apply configuration
terraform apply

# Type 'yes' when prompted
```

### Confirm Email Subscriptions

After applying Terraform:

1. Check your email inbox
2. Look for emails from **AWS Notifications**
3. Click **Confirm subscription** in each email
4. You should receive 1 confirmation email per email address configured

## Step 7: Verify Budget Configuration

### Via AWS Console

1. Navigate to **AWS Cost Management** → **Budgets**
2. Verify the following budgets exist:
   - `festival-playlist-dev-monthly-total` (with 50%, 80%, 100% alerts)
   - `festival-playlist-dev-threshold-10` ($10 limit)
   - `festival-playlist-dev-threshold-20` ($20 limit)
   - `festival-playlist-dev-threshold-30` ($30 limit)
3. Click each budget to view details and alert configuration

### Via AWS CLI

```bash
# First, verify which account you're using
aws sts get-caller-identity --profile festival-playlist
# Should show YOUR account ID (e.g., 671018259555)

# List all budgets in YOUR account
aws budgets describe-budgets \
  --account-id $(aws sts get-caller-identity --query Account --output text --profile festival-playlist) \
  --profile festival-playlist

# Describe specific budget
aws budgets describe-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text --profile festival-playlist) \
  --budget-name festival-playlist-dev-monthly-total \
  --profile festival-playlist
```

**Troubleshooting**: If you get an error like "AccountId does not match the credentials provided":
- This means there are old budgets in a different account
- The command above should work because it uses YOUR account ID dynamically
- If it still fails, the budgets might not exist yet (run `terraform apply` first)
- Or there might be cached credentials - try: `aws sts get-caller-identity --profile festival-playlist` to verify

## Step 8: Verify Cost Anomaly Detection

1. Navigate to **AWS Cost Management** → **Cost Anomaly Detection**
2. Verify monitor exists: `festival-playlist-dev-service-monitor`
3. Verify subscription exists: `festival-playlist-dev-anomaly-alerts`
4. Note: Anomaly detection requires 10-14 days of billing data to establish baseline

## Step 9: View CloudWatch Cost Dashboard

1. Navigate to **CloudWatch** → **Dashboards**
2. Open `festival-playlist-dev-cost-monitoring`
3. View estimated monthly charges graph
4. Bookmark dashboard for easy access

## Step 10: Test Budget Alerts (Optional)

To test that alerts are working:

1. Create a small EC2 instance or other resource
2. Wait 24 hours for billing data to update
3. Check if you receive budget notifications
4. Terminate test resources to avoid charges

**Note**: This is optional and will incur small charges (~$1-2).

## Cost Allocation Strategy

### Tagging Strategy

All resources should be tagged with:

```hcl
tags = {
  Project     = "festival-playlist"
  Environment = "dev|staging|prod"
  ManagedBy   = "terraform"
  Module      = "networking|database|compute|etc"
  CostCenter  = "hobby-project"
}
```

### Viewing Costs by Tag

1. Navigate to **Cost Explorer**
2. Click **Cost & Usage Reports**
3. Group by: **Tag** → **Project**
4. Filter by: `Project = festival-playlist`
5. View costs by service, time period, or environment

## Monitoring and Maintenance

### Daily Tasks
- Check email for budget alerts
- Review any cost anomaly notifications

### Weekly Tasks
- Review Cost Explorer for spending trends
- Verify resources are properly tagged
- Check for unused resources

### Monthly Tasks
- Review total monthly costs vs. budget
- Adjust budget thresholds if needed
- Optimize resources based on usage patterns

## Troubleshooting

### Issue: Not Receiving Email Alerts

**Solution**:
1. Check spam/junk folder
2. Verify SNS subscription status:
   ```bash
   aws sns list-subscriptions-by-topic \
     --topic-arn <sns-topic-arn> \
     --profile festival-playlist
   ```
3. Confirm email subscription in AWS Console
4. Re-subscribe if needed:
   ```bash
   aws sns subscribe \
     --topic-arn <sns-topic-arn> \
     --protocol email \
     --notification-endpoint your-email@example.com \
     --profile festival-playlist
   ```

### Issue: Cost Explorer Not Available

**Solution**:
1. Enable Cost Explorer in AWS Console
2. Wait 24 hours for data population
3. Refresh browser and try again

### Issue: Budgets Not Showing Costs

**Solution**:
1. Verify resources are tagged correctly
2. Check budget filters match your tags
3. Wait 24 hours for billing data to update
4. Ensure Cost Allocation Tags are activated

### Issue: Cost Allocation Tags Not Visible

**Solution**:
1. Tags only appear after resources with those tags are created
2. Deploy Terraform resources first (Step 6)
3. Wait 24 hours for AWS to detect the tags
4. Return to Cost Allocation Tags page to activate them
5. **Note**: This is normal - you can't activate tags that don't exist yet

### Issue: "This account is not in an AWS Organization"

**Solution**:
1. This message is normal for standalone AWS accounts
2. Cost allocation tags work fine without AWS Organizations
3. Simply ignore this message and proceed
4. AWS Organizations is only needed for multi-account management

### Issue: Terraform Apply Fails

**Solution**:
1. Check AWS credentials are configured correctly
2. Verify IAM user has required permissions
3. Check Terraform version (>= 1.5 required)
4. Review error message and fix configuration
5. Run `terraform init` again if providers changed

## Security Best Practices

1. **Never commit AWS credentials to Git**
   - Use AWS CLI profiles
   - Use environment variables
   - Use AWS Secrets Manager for production

2. **Enable MFA for root account**
   - Navigate to **IAM** → **Dashboard**
   - Click **Activate MFA on your root account**
   - Follow setup instructions

3. **Use IAM roles instead of access keys when possible**
   - For EC2 instances
   - For Lambda functions
   - For ECS tasks

4. **Rotate access keys regularly**
   - Every 90 days minimum
   - Use AWS IAM Access Analyzer

5. **Enable CloudTrail for audit logging**
   - Track all API calls
   - Store logs in S3
   - Enable log file validation

## Next Steps

After completing this setup:

1. ✅ AWS account configured
2. ✅ Billing alerts enabled
3. ✅ Cost monitoring active
4. ✅ Email notifications confirmed

**Proceed to**: Task 2 - Initialize Terraform project structure

## Additional Resources

- [AWS Cost Management Documentation](https://docs.aws.amazon.com/cost-management/)
- [AWS Budgets Best Practices](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-best-practices.html)
- [Cost Optimization Pillar - AWS Well-Architected](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/)
- [AWS Free Tier](https://aws.amazon.com/free/)
- [AWS Pricing Calculator](https://calculator.aws/)

## Support

For issues or questions:
- AWS Support (if you have a support plan)
- AWS Forums: [https://forums.aws.amazon.com](https://forums.aws.amazon.com)
- Project documentation: `docs/` directory
