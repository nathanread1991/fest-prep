# Terraform Troubleshooting Guide

## Common Errors and Solutions

### Error: "Limit exceeded on dimensional spend monitor creation"

**Full Error**:
```
Error: creating Cost Explorer Anomaly Monitor: operation error Cost Explorer: CreateAnomalyMonitor, 
https response error StatusCode: 400, RequestID: ..., api error ValidationException: 
Limit exceeded on dimensional spend monitor creation
```

**Cause**: AWS limits each account to **1 Cost Anomaly Detection monitor**. You likely already have one created (possibly from a previous test or another project).

**Solution 1: Disable Anomaly Detection (Recommended)**

Edit your `terraform/terraform.tfvars`:
```hcl
enable_anomaly_detection = false
```

Then run:
```bash
terraform apply
```

**What you lose**: Automatic anomaly detection alerts
**What you keep**: All budgets, SNS notifications, CloudWatch dashboard

**Solution 2: Delete Existing Monitor**

If you want to use the new monitor instead:

1. List existing monitors:
```bash
aws ce get-anomaly-monitors --profile festival-playlist --region us-east-1
```

2. Delete the existing monitor:
```bash
aws ce delete-anomaly-monitor \
  --monitor-arn "arn:aws:ce::ACCOUNT_ID:anomalymonitor/MONITOR_ID" \
  --profile festival-playlist \
  --region us-east-1
```

3. Run terraform apply again:
```bash
terraform apply
```

**Solution 3: Use Existing Monitor**

If you want to keep the existing monitor, you can import it into Terraform (advanced):

```bash
# Get the monitor ARN from AWS
aws ce get-anomaly-monitors --profile festival-playlist --region us-east-1

# Import into Terraform
terraform import module.billing.aws_ce_anomaly_monitor.service_monitor[0] "arn:aws:ce::ACCOUNT_ID:anomalymonitor/MONITOR_ID"
```

---

### Warning: "Value for undeclared variable"

**Full Warning**:
```
Warning: Value for undeclared variable
The root module does not declare a variable named "aws_profile" but a value was found in file "terraform.tfvars"
```

**Cause**: Missing `variables.tf` file in the root terraform directory.

**Solution**: The `variables.tf` file should now exist. If you still see this error:

1. Verify `terraform/variables.tf` exists
2. Run `terraform init` again
3. Run `terraform plan`

---

### Error: "No configuration files"

**Full Error**:
```
Error: No configuration files
```

**Cause**: Missing `main.tf` file in the terraform directory.

**Solution**: The `main.tf` file should now exist at `terraform/main.tf`. If not:

1. Verify you're in the `terraform/` directory
2. Check that `main.tf`, `variables.tf`, and `outputs.tf` exist
3. Run `terraform init`

---

### Error: "Backend initialization required"

**Full Error**:
```
Error: Backend initialization required, please run "terraform init"
```

**Solution**:
```bash
cd terraform
terraform init
```

---

### Error: "Error loading state: AccessDenied"

**Cause**: AWS credentials not configured or insufficient permissions.

**Solution**:
```bash
# Verify credentials
aws sts get-caller-identity --profile festival-playlist

# If fails, reconfigure
aws configure --profile festival-playlist
```

---

### Error: "AccountId does not match the credentials provided"

**Full Error**:
```
AccessDeniedException: AccountId : 890742576526 does not match the credentials provided
```

**Cause**: You're using AWS credentials for a different account than where the resources exist.

**Solution**:

1. **Check which account your credentials are for**:
```bash
aws sts get-caller-identity --profile festival-playlist
```

2. **If Account ID doesn't match**, you have two options:

**Option A: Get credentials for the correct account**
```bash
# Reconfigure with credentials for account 890742576526
aws configure --profile festival-playlist
# Enter access key and secret for account 890742576526

# Verify
aws sts get-caller-identity --profile festival-playlist
# Should show Account: 890742576526
```

**Option B: Use your own account**
```bash
# Use your own AWS account instead
aws sts get-caller-identity --profile festival-playlist
# Note your Account ID

# Resources will be created in YOUR account, not 890742576526
```

See detailed guide: [docs/aws-credentials-mismatch.md](./aws-credentials-mismatch.md)

---

### Error: "Error creating Budget: AccessDeniedException"

**Cause**: IAM user doesn't have billing permissions.

**Solution**:

1. Sign in as root user
2. Go to **Account** → **IAM User and Role Access to Billing Information**
3. Enable **Activate IAM Access**
4. Attach `Billing` policy to your IAM user

---

### Error: "Provider configuration not present"

**Full Error**:
```
Error: Provider configuration not present
```

**Cause**: Terraform not initialized or provider not configured.

**Solution**:
```bash
terraform init
terraform plan
```

---

## Checking Your Configuration

### Verify Terraform Files Exist

```bash
cd terraform
ls -la

# Should see:
# main.tf
# variables.tf
# outputs.tf
# terraform.tfvars (your config)
# terraform.tfvars.example
# modules/billing/
```

### Verify Terraform Variables

```bash
# Check your configuration
cat terraform.tfvars

# Should include:
# aws_region
# aws_profile
# alert_email_addresses
# enable_anomaly_detection
```

### Verify AWS Credentials

```bash
# Test AWS access
aws sts get-caller-identity --profile festival-playlist

# Should return your account ID and user ARN
```

### Verify Terraform Version

```bash
terraform version

# Should be >= 1.5.0
```

---

## AWS Cost Anomaly Detection Limits

### Per Account Limits

| Resource | Limit | Notes |
|----------|-------|-------|
| Anomaly Monitors | 1 | Only 1 dimensional monitor per account |
| Anomaly Subscriptions | 10 | Per monitor |
| Alert Recipients | 10 | Per subscription |

### Checking Existing Monitors

```bash
# List all anomaly monitors
aws ce get-anomaly-monitors \
  --profile festival-playlist \
  --region us-east-1 \
  --query 'AnomalyMonitors[*].[MonitorName,MonitorArn]' \
  --output table
```

### Checking Existing Subscriptions

```bash
# List all anomaly subscriptions
aws ce get-anomaly-subscriptions \
  --profile festival-playlist \
  --region us-east-1 \
  --query 'AnomalySubscriptions[*].[SubscriptionName,SubscriptionArn]' \
  --output table
```

---

## Recommended Configuration for First-Time Setup

If you're setting up for the first time and encountering errors, use this minimal configuration:

**terraform/terraform.tfvars**:
```hcl
aws_region  = "eu-west-2"
aws_profile = "festival-playlist"

project_name = "festival-playlist"
environment  = "dev"

monthly_budget_limit = "30"

alert_email_addresses = [
  "your-email@example.com"
]

anomaly_threshold = "5"

# Disable features that might cause errors
enable_encryption = false
enable_anomaly_detection = false  # Disable if limit exceeded

common_tags = {
  Project     = "festival-playlist"
  Environment = "dev"
  ManagedBy   = "terraform"
}
```

This configuration:
- ✅ Creates all budgets ($10, $20, $30, monthly)
- ✅ Creates SNS topic for alerts
- ✅ Creates CloudWatch dashboard
- ❌ Skips KMS encryption (saves $1/month)
- ❌ Skips anomaly detection (avoids limit error)

You can enable these features later once the basic setup works.

---

## Getting Help

### Terraform Debug Mode

```bash
# Enable debug logging
export TF_LOG=DEBUG
terraform plan

# Disable debug logging
unset TF_LOG
```

### AWS CLI Debug Mode

```bash
# Enable debug output
aws ce get-anomaly-monitors \
  --profile festival-playlist \
  --region us-east-1\
  --debug
```

### Verify Module Configuration

```bash
# Validate Terraform configuration
terraform validate

# Format Terraform files
terraform fmt -recursive

# Show planned changes
terraform plan
```

---

## Clean Slate (Start Over)

If you want to start completely fresh:

```bash
# Destroy all resources
cd terraform
terraform destroy

# Remove state files
rm -f terraform.tfstate*
rm -rf .terraform/

# Re-initialize
terraform init
terraform plan
terraform apply
```

**Warning**: This will delete all budgets, SNS topics, and dashboards!

---

## Summary

**Most Common Issues**:
1. ✅ **Anomaly monitor limit exceeded** → Set `enable_anomaly_detection = false`
2. ✅ **Missing variables** → Files now created (`main.tf`, `variables.tf`, `outputs.tf`)
3. ✅ **AWS credentials** → Run `aws configure --profile festival-playlist`
4. ✅ **Billing permissions** → Enable IAM billing access as root user

**Quick Fix for Your Current Error**:
```bash
cd terraform

# Edit terraform.tfvars and set:
# enable_anomaly_detection = false

terraform init
terraform plan
terraform apply
```

This will create everything except the anomaly monitor, which you've already hit the limit for.

---

**Last Updated**: January 15, 2026
**Status**: Troubleshooting guide for common Terraform errors
