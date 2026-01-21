# AWS Credentials Mismatch - Troubleshooting Guide

## Error: "AccountId does not match the credentials provided"

**Full Error**:
```
An error occurred (AccessDeniedException) when calling the DescribeBudgets operation: 
AccountId : 890742576526 does not match the credentials provided.
```

## What This Means

You're trying to access resources in AWS account **890742576526**, but your current AWS credentials are for a **different account**.

This typically happens when:
1. You have multiple AWS accounts
2. You're using the wrong AWS CLI profile
3. Your credentials are for a different account than where resources exist
4. You're trying to access resources created by someone else

## Quick Diagnosis

### Step 1: Check Which Account Your Credentials Are For

```bash
aws sts get-caller-identity --profile festival-playlist
```

**Expected Output**:
```json
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "890742576526",  # Should match the account in error
    "Arn": "arn:aws:iam::890742576526:user/your-username"
}
```

**If the Account ID doesn't match 890742576526**, you're using credentials for the wrong account.

### Step 2: Check What Profiles You Have

```bash
# List all configured profiles
cat ~/.aws/credentials

# Or check config
cat ~/.aws/config
```

You might see multiple profiles like:
```
[default]
[festival-playlist]
[work-account]
[personal-account]
```

## Solutions

### Solution 1: Use the Correct Profile

If you have multiple AWS accounts, make sure you're using the right profile:

```bash
# Check which account each profile is for
aws sts get-caller-identity --profile default
aws sts get-caller-identity --profile festival-playlist
aws sts get-caller-identity --profile another-profile

# Find the one that returns Account: 890742576526
```

Once you find the correct profile, update your Terraform configuration:

**Edit `terraform/terraform.tfvars`**:
```hcl
aws_profile = "correct-profile-name"  # Use the profile that matches account 890742576526
```

### Solution 2: Configure Credentials for Account 890742576526

If you don't have credentials configured for account 890742576526:

```bash
# Configure a new profile for this account
aws configure --profile festival-playlist

# Enter credentials for account 890742576526:
# AWS Access Key ID: [your-access-key-for-890742576526]
# AWS Secret Access Key: [your-secret-key-for-890742576526]
# Default region name: eu-west-2
# Default output format: json

# Verify it's the right account
aws sts get-caller-identity --profile festival-playlist
# Should show Account: 890742576526
```

### Solution 3: Resources in Different Account

If the budgets were created in account 890742576526 but you want to use a different account:

**Option A: Delete old budgets and create new ones**
1. Sign in to account 890742576526 (via AWS Console)
2. Go to AWS Budgets
3. Delete the old budgets
4. Use your current account credentials to create new ones

**Option B: Use account 890742576526**
1. Get credentials for account 890742576526
2. Configure them in AWS CLI
3. Use that profile in Terraform

## Verification Steps

### 1. Verify Your Current Credentials

```bash
# Check which account you're authenticated to
aws sts get-caller-identity --profile festival-playlist

# Output should show:
# Account: 890742576526
```

### 2. Verify Profile in Terraform

```bash
# Check your Terraform configuration
cd terraform
grep aws_profile terraform.tfvars

# Should show:
# aws_profile = "festival-playlist"
```

### 3. Test Access to Budgets

```bash
# Try to list budgets with your profile
aws budgets describe-budgets \
  --account-id 890742576526 \
  --profile festival-playlist

# If this works, your credentials are correct
# If this fails, you need different credentials
```

## Common Scenarios

### Scenario 1: Multiple AWS Accounts

**Problem**: You have a work AWS account and a personal AWS account.

**Solution**: 
```bash
# Configure separate profiles
aws configure --profile work
aws configure --profile personal

# Use the correct one in Terraform
# terraform.tfvars:
aws_profile = "personal"  # or "work"
```

### Scenario 2: Switched AWS Accounts

**Problem**: You created resources in one account, now using a different account.

**Solution**: Either:
- Switch back to the original account credentials
- Delete resources in old account and recreate in new account
- Use cross-account access (advanced)

### Scenario 3: Team Member's Account

**Problem**: Resources were created by a team member in their account.

**Solution**: 
- Get your own AWS account
- Create resources in your own account
- Don't try to access someone else's account

## Environment Variables vs Profile

### Using Profile (Recommended)

```bash
# In terraform.tfvars
aws_profile = "festival-playlist"

# Terraform will use this profile automatically
terraform plan
```

### Using Environment Variables (Alternative)

```bash
# Set environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="eu-west-2"

# Remove profile from terraform.tfvars or comment it out
# aws_profile = "festival-playlist"  # Comment this out

# Run Terraform
terraform plan
```

## Fixing the Verification Script

The verification script also needs the correct profile:

```bash
# Run with correct profile
AWS_PROFILE=festival-playlist ./scripts/verify-billing-setup.sh

# Or set it as default
export AWS_PROFILE=festival-playlist
./scripts/verify-billing-setup.sh
```

## Security Best Practices

### 1. Never Share AWS Credentials

- ❌ Don't use someone else's credentials
- ❌ Don't share your credentials with others
- ✅ Each person should have their own AWS account or IAM user

### 2. Use IAM Users, Not Root

- ❌ Don't use root account credentials for daily work
- ✅ Create IAM user with appropriate permissions
- ✅ Enable MFA on both root and IAM users

### 3. Rotate Credentials Regularly

```bash
# Create new access key
aws iam create-access-key --user-name your-username

# Update credentials
aws configure --profile festival-playlist

# Delete old access key
aws iam delete-access-key --access-key-id OLD_KEY_ID --user-name your-username
```

## Complete Reset (If Confused)

If you're completely confused about which account is which:

### Step 1: Clear All Credentials

```bash
# Backup first
cp ~/.aws/credentials ~/.aws/credentials.backup
cp ~/.aws/config ~/.aws/config.backup

# Clear credentials
rm ~/.aws/credentials
rm ~/.aws/config
```

### Step 2: Reconfigure from Scratch

```bash
# Configure for account 890742576526
aws configure --profile festival-playlist

# Enter credentials for account 890742576526
# AWS Access Key ID: [your-key]
# AWS Secret Access Key: [your-secret]
# Default region name: eu-west-2
# Default output format: json
```

### Step 3: Verify

```bash
# Should show Account: 890742576526
aws sts get-caller-identity --profile festival-playlist
```

### Step 4: Update Terraform

```bash
cd terraform

# Make sure terraform.tfvars has:
# aws_profile = "festival-playlist"

# Re-initialize
terraform init
terraform plan
```

## Quick Fix Checklist

- [ ] Run `aws sts get-caller-identity --profile festival-playlist`
- [ ] Verify Account ID matches 890742576526
- [ ] If not, find the correct profile or reconfigure credentials
- [ ] Update `terraform.tfvars` with correct profile name
- [ ] Run `terraform init` and `terraform plan`
- [ ] Verify no more credential errors

## Getting the Right Credentials

If you don't have credentials for account 890742576526:

### Option 1: You Own This Account
1. Sign in to AWS Console for account 890742576526
2. Go to IAM → Users → Your User → Security Credentials
3. Create new access key
4. Configure in AWS CLI

### Option 2: Someone Else Owns This Account
1. Ask the account owner for access
2. They should create an IAM user for you
3. They give you the access key and secret
4. Configure in AWS CLI

### Option 3: Use Your Own Account
1. Create your own AWS account
2. Configure credentials for your account
3. Create resources in your own account
4. Update account ID references in scripts

## Summary

**The error means**: Your AWS credentials are for a different account than 890742576526.

**Quick fix**:
1. Find credentials for account 890742576526
2. Configure them: `aws configure --profile festival-playlist`
3. Verify: `aws sts get-caller-identity --profile festival-playlist`
4. Should show Account: 890742576526

**If you can't get credentials for 890742576526**:
- Use your own AWS account instead
- Create new resources in your account
- Don't try to access resources in someone else's account

---

**Last Updated**: January 15, 2026
**Issue**: AWS credentials mismatch
**Account in Error**: 890742576526
