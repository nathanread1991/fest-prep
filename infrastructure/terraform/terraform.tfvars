# Terraform Variables Example
# Copy this file to terraform.tfvars and update with your values
# DO NOT commit terraform.tfvars to Git (it contains sensitive information)

# AWS Configuration
aws_region = "eu-west-2" # London region
# aws_profile is set locally via TF_VAR_aws_profile or defaults to "festival-playlist"
# In CI, TF_VAR_aws_profile="" overrides the default to use env var auth

# Project Configuration
project_name = "festival-playlist"
environment  = "dev"

# Billing Configuration
monthly_budget_limit = "30" # USD

# Alert Email Addresses
# Add all email addresses that should receive budget and cost anomaly alerts
alert_email_addresses = [
  "nathanread1991@gmail.com",

]

# Cost Anomaly Detection
# Minimum dollar amount to trigger anomaly alerts
anomaly_threshold = "5" # USD

# Security
# Enable KMS encryption for SNS topic (adds ~$1/month cost)
enable_encryption = false

# Cost Anomaly Detection Feature
# Set to false if you get "Limit exceeded" error (AWS allows 1 monitor per account)
# If you already have an anomaly monitor, disable this
enable_anomaly_detection = false # Set to false to skip anomaly detection

# Common Tags
# These tags will be applied to all resources for cost tracking
common_tags = {
  Project     = "festival-playlist"
  Environment = "dev"
  ManagedBy   = "terraform"
  CostCenter  = "hobby-project"
  Owner       = "Nathan Read"
  Region      = "eu-west-2"
}
