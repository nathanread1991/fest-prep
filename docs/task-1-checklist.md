# Task 1: AWS Account Setup and Billing Alerts - Checklist

This checklist helps you complete Task 1 from the AWS Enterprise Migration plan.

## Task Overview

**Goal**: Set up AWS account and configure comprehensive billing alerts to monitor costs and prevent budget overruns.

**Target Cost**: $10-15/month with daily teardown strategy

**Requirements**: US-3.6, US-3.7

## Pre-Setup Checklist

- [ ] AWS account created or accessible
- [ ] Credit card added for billing
- [ ] Email address ready for alerts
- [ ] AWS CLI installed locally
- [ ] Terraform >= 1.5 installed locally
- [ ] Git repository cloned

## Step 1: AWS Account Configuration

### 1.1 Account Access
- [ ] Sign in to AWS Console as root user
- [ ] Verify account is active and billing information is current
- [ ] Note your AWS Account ID: `________________`

### 1.2 Enable IAM Billing Access
- [ ] Navigate to Account → Account Settings
- [ ] Enable "IAM User and Role Access to Billing Information"
- [ ] Click "Activate IAM Access"

### 1.3 Create IAM User for Terraform
- [ ] Create IAM user: `terraform-admin`
- [ ] Enable programmatic access (Access Key)
- [ ] Attach `AdministratorAccess` policy (or custom policy)
- [ ] Save Access Key ID: `________________`
- [ ] Save Secret Access Key: `________________` (store securely!)

### 1.4 Configure AWS CLI
- [ ] Run: `aws configure --profile festival-playlist`
- [ ] Enter Access Key ID
- [ ] Enter Secret Access Key
- [ ] Set region: `eu-west-2` (London)
- [ ] Set output format: `json`
- [ ] Test: `aws sts get-caller-identity --profile festival-playlist`

## Step 2: Enable Cost Management Services

### 2.1 Enable Cost Explorer
- [ ] Navigate to AWS Cost Management → Cost Explorer
- [ ] Click "Enable Cost Explorer"
- [ ] Wait 24 hours for initial data (note: can proceed with other steps)
- [ ] Bookmark Cost Explorer URL

### 2.2 Activate Cost Allocation Tags (Optional - Can Do After Deployment)
- [ ] **Option A**: Skip this step for now (recommended)
- [ ] **Option B**: Navigate to Cost Management → Cost Allocation Tags
- [ ] Note: Tags won't appear until resources are created
- [ ] **After deploying resources**: Return here and activate tags:
  - [ ] Activate tag: `Project`
  - [ ] Activate tag: `Environment`
  - [ ] Activate tag: `ManagedBy`
  - [ ] Activate tag: `Module`
  - [ ] Activate tag: `CostCenter`
  - [ ] Activate tag: `Owner`
- [ ] Wait 24 hours for tags to appear in Cost Explorer
- [ ] **Note**: This step can be completed anytime, even weeks later

## Step 3: Deploy Billing Module with Terraform

### 3.1 Prepare Terraform Configuration
- [ ] Navigate to `terraform/` directory
- [ ] Copy: `cp terraform.tfvars.example terraform.tfvars`
- [ ] Edit `terraform.tfvars`:
  - [ ] Update `alert_email_addresses` with your email(s)
  - [ ] Verify `monthly_budget_limit = "30"`
  - [ ] Verify `anomaly_threshold = "5"`
  - [ ] Update `common_tags` with your information
- [ ] Verify `.gitignore` excludes `terraform.tfvars`

### 3.2 Initialize Terraform
- [ ] Run: `terraform init`
- [ ] Verify providers downloaded successfully
- [ ] Check for any initialization errors

### 3.3 Review Terraform Plan
- [ ] Run: `terraform plan`
- [ ] Review resources to be created:
  - [ ] SNS topic for alerts
  - [ ] 4 AWS Budgets (monthly total, $10, $20, $30)
  - [ ] Cost Anomaly Detection monitor
  - [ ] Cost Anomaly Detection subscription
  - [ ] CloudWatch dashboard
- [ ] Verify no unexpected resources
- [ ] Check estimated costs (~$1.80/month for budgets)

### 3.4 Apply Terraform Configuration
- [ ] Run: `terraform apply`
- [ ] Review plan one more time
- [ ] Type `yes` to confirm
- [ ] Wait for resources to be created (~2-3 minutes)
- [ ] Verify "Apply complete!" message
- [ ] Note SNS topic ARN: `________________`

### 3.5 Save Terraform Outputs
- [ ] Run: `terraform output`
- [ ] Save outputs for reference:
  ```
  sns_topic_arn = "________________"
  budget_names = [
    "________________",
    "________________",
    "________________",
    "________________"
  ]
  ```

## Step 4: Confirm Email Subscriptions

### 4.1 Check Email Inbox
- [ ] Check inbox for "AWS Notification - Subscription Confirmation"
- [ ] Check spam/junk folder if not in inbox
- [ ] Note: You should receive 1 email per email address configured

### 4.2 Confirm Subscriptions
- [ ] Open each confirmation email
- [ ] Click "Confirm subscription" link
- [ ] Verify confirmation page loads successfully
- [ ] Repeat for all email addresses

### 4.3 Verify Subscriptions Active
- [ ] Navigate to SNS → Topics in AWS Console
- [ ] Find topic: `festival-playlist-dev-budget-alerts`
- [ ] Click on topic
- [ ] Verify subscriptions show "Confirmed" status (not "PendingConfirmation")

## Step 5: Verify Budget Configuration

### 5.1 Check AWS Budgets Console
- [ ] Navigate to AWS Cost Management → Budgets
- [ ] Verify 4 budgets exist:
  - [ ] `festival-playlist-dev-monthly-total`
  - [ ] `festival-playlist-dev-threshold-10`
  - [ ] `festival-playlist-dev-threshold-20`
  - [ ] `festival-playlist-dev-threshold-30`

### 5.2 Verify Budget Details
For each budget:
- [ ] Click budget name
- [ ] Verify budget amount is correct
- [ ] Check "Alerts" tab shows configured thresholds
- [ ] Verify SNS topic is configured for notifications
- [ ] Check "Filters" tab shows correct tags

### 5.3 Test Budget Alerts (Optional)
- [ ] Create small test resource (e.g., t3.micro EC2 instance)
- [ ] Wait 24 hours for billing data update
- [ ] Check if budget notifications received
- [ ] Terminate test resource
- [ ] **Note**: This is optional and will incur small charges

## Step 6: Verify Cost Anomaly Detection

### 6.1 Check Anomaly Detection Console
- [ ] Navigate to Cost Management → Cost Anomaly Detection
- [ ] Verify monitor exists: `festival-playlist-dev-service-monitor`
- [ ] Click monitor to view details
- [ ] Verify monitor type: "Dimensional" (SERVICE)

### 6.2 Verify Anomaly Subscription
- [ ] Click "Subscriptions" tab
- [ ] Verify subscription exists: `festival-playlist-dev-anomaly-alerts`
- [ ] Check frequency: "Daily"
- [ ] Verify SNS topic configured
- [ ] Check threshold: $5 minimum impact

### 6.3 Note Anomaly Detection Limitations
- [ ] Understand: Requires 10-14 days of billing data to establish baseline
- [ ] Understand: Won't detect anomalies immediately
- [ ] Plan to review after 2 weeks of AWS usage

## Step 7: Verify CloudWatch Dashboard

### 7.1 Access Dashboard
- [ ] Navigate to CloudWatch → Dashboards
- [ ] Find dashboard: `festival-playlist-dev-cost-monitoring`
- [ ] Click to open dashboard

### 7.2 Review Dashboard Widgets
- [ ] Verify "Estimated Monthly Charges" widget displays
- [ ] Check if data is showing (may be empty initially)
- [ ] Bookmark dashboard URL for easy access

### 7.3 Customize Dashboard (Optional)
- [ ] Add additional cost metrics if desired
- [ ] Adjust time ranges
- [ ] Save customizations

## Step 8: Run Verification Script

### 8.1 Execute Verification
- [ ] Run: `./scripts/verify-billing-setup.sh`
- [ ] Review output for any errors or warnings
- [ ] Verify all checks pass (green checkmarks)

### 8.2 Address Any Issues
- [ ] Fix any failed checks identified by script
- [ ] Re-run script to confirm fixes
- [ ] Document any unresolved issues

## Step 9: Documentation and Cleanup

### 9.1 Document Configuration
- [ ] Save AWS Account ID in secure location
- [ ] Document IAM user credentials (securely)
- [ ] Note SNS topic ARN
- [ ] Save budget names for reference

### 9.2 Security Hardening
- [ ] Enable MFA on root account
- [ ] Enable MFA on IAM user (optional but recommended)
- [ ] Review IAM policies for least privilege
- [ ] Rotate access keys if needed

### 9.3 Update Project Documentation
- [ ] Update README.md with billing setup status
- [ ] Add notes about cost monitoring
- [ ] Document any deviations from standard setup

## Step 10: Final Verification

### 10.1 Complete Checklist Review
- [ ] All items above marked as complete
- [ ] No outstanding errors or warnings
- [ ] Email subscriptions confirmed
- [ ] Budgets visible in AWS Console
- [ ] Cost Anomaly Detection configured

### 10.2 Test Notifications (Optional)
- [ ] Send test notification via SNS console
- [ ] Verify email received
- [ ] Check email formatting and content

### 10.3 Mark Task Complete
- [ ] Update tasks.md: Change task 1 status to completed
- [ ] Commit Terraform code to Git (excluding terraform.tfvars)
- [ ] Push changes to repository

## Success Criteria

All of the following must be true:

- ✅ AWS account configured with billing access
- ✅ Cost Explorer enabled
- ✅ 4 AWS Budgets created ($10, $20, $30, monthly total)
- ✅ Budget alerts configured at correct thresholds
- ✅ SNS topic created for notifications
- ✅ Email subscriptions confirmed (not pending)
- ✅ Cost Anomaly Detection monitor created
- ✅ Cost Anomaly Detection subscription configured
- ✅ CloudWatch cost dashboard created
- ✅ Cost allocation tags activated
- ✅ Verification script passes all checks
- ✅ Documentation updated

## Expected Costs

| Service | Cost |
|---------|------|
| AWS Budgets (4 budgets) | ~$1.80/month |
| Cost Anomaly Detection | Free |
| SNS (email notifications) | Free (first 1,000) |
| CloudWatch Dashboard | Free (first 3) |
| Cost Explorer | Free |
| **Total** | **~$1.80/month** |

## Troubleshooting

### Issue: Email subscriptions pending
**Solution**: Check spam folder, click confirmation link in email

### Issue: Cost Explorer not available
**Solution**: Enable in AWS Console, wait 24 hours

### Issue: Terraform apply fails
**Solution**: Check AWS credentials, verify IAM permissions, review error message

### Issue: Budgets not showing costs
**Solution**: Wait 24 hours for billing data, verify resources are tagged correctly

### Issue: Verification script fails
**Solution**: Review specific check that failed, fix issue, re-run script

## Next Steps

After completing this checklist:

1. ✅ Task 1 complete
2. ➡️ Proceed to Task 2: Initialize Terraform project structure
3. 📧 Monitor email for budget alerts over next few days
4. 📊 Check Cost Explorer after 24 hours to see initial data

## References

- [Full Setup Guide](./aws-account-setup.md)
- [Quick Start Guide](./billing-setup-quickstart.md)
- [Billing Module README](../terraform/modules/billing/README.md)
- [AWS Budgets Documentation](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
- [Cost Anomaly Detection](https://docs.aws.amazon.com/cost-management/latest/userguide/manage-ad.html)

## Notes

- Billing data updates once per day (usually around midnight UTC)
- Cost Anomaly Detection needs 10-14 days to establish baseline
- Budget alerts trigger when thresholds are exceeded
- SNS email subscriptions must be confirmed to receive alerts
- Cost allocation tags take 24 hours to appear in Cost Explorer
- Keep terraform.tfvars secure and never commit to Git

---

**Task Status**: ⬜ Not Started | 🔄 In Progress | ✅ Complete

**Completion Date**: ________________

**Completed By**: ________________

**Notes**: ________________
