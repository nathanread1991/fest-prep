# Terraform Infrastructure

This directory contains all Terraform configurations for the Festival Playlist Generator AWS infrastructure.

## Directory Structure

```
terraform/
├── main.tf                    # Main Terraform configuration (to be created)
├── variables.tf               # Input variables (to be created)
├── outputs.tf                 # Output values (to be created)
├── backend.tf                 # S3 backend configuration (to be created)
├── terraform.tfvars.example   # Example variables file
├── terraform.tfvars           # Actual variables (DO NOT COMMIT)
├── modules/
│   └── billing/               # Billing and cost management module
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── README.md
└── README.md                  # This file
```

## Quick Start

### Prerequisites

- AWS account with admin access
- AWS CLI configured with profile `festival-playlist`
- Terraform >= 1.5 installed
- Git repository cloned

### Initial Setup

1. **Configure variables**:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your values
   ```

2. **Initialize Terraform**:
   ```bash
   terraform init
   ```

3. **Review plan**:
   ```bash
   terraform plan
   ```

4. **Apply configuration**:
   ```bash
   terraform apply
   ```

5. **Confirm email subscriptions** (check your inbox)

## Current Modules

### Billing Module

**Status**: ✅ Complete (Task 1)

**Purpose**: AWS Budgets, Cost Anomaly Detection, and SNS notifications for cost monitoring

**Resources**:
- SNS topic for budget alerts
- 4 AWS Budgets ($10, $20, $30, monthly total)
- Cost Anomaly Detection monitor and subscription
- CloudWatch cost monitoring dashboard

**Documentation**: [modules/billing/README.md](./modules/billing/README.md)

**Usage**:
```hcl
module "billing" {
  source = "./modules/billing"

  project_name          = "festival-playlist"
  environment           = "dev"
  monthly_budget_limit  = "30"
  alert_email_addresses = ["your-email@example.com"]
  anomaly_threshold     = "5"
  
  common_tags = {
    Project     = "festival-playlist"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

### Upcoming Modules

The following modules will be created in subsequent tasks:

- **networking**: VPC, subnets, security groups, VPC endpoints (Task 9)
- **database**: Aurora Serverless v2 PostgreSQL (Task 10)
- **cache**: ElastiCache Redis (Task 11)
- **storage**: S3 buckets, ECR repository (Task 12)
- **compute**: ECS Fargate cluster, task definitions, services (Task 13)
- **security**: ACM certificates, Route 53, WAF, Secrets Manager (Task 14)
- **cdn**: CloudFront distribution (Task 15)
- **monitoring**: CloudWatch Logs, Metrics, Alarms, X-Ray (Task 16)

## Terraform State Management

### Local State (Current)

Currently using local state file (`terraform.tfstate`). This is acceptable for initial setup but should be migrated to remote state.

**⚠️ Important**: Do not commit `terraform.tfstate` to Git!

### Remote State (Task 2)

In Task 2, we'll configure S3 backend for remote state:

```hcl
terraform {
  backend "s3" {
    bucket         = "festival-playlist-terraform-state"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "festival-playlist-terraform-locks"
  }
}
```

## Terraform Workspaces

We'll use Terraform workspaces for environment separation:

- `dev`: Development environment (daily teardown)
- `staging`: Staging environment (optional)
- `prod`: Production environment (always running)

```bash
# List workspaces
terraform workspace list

# Create new workspace
terraform workspace new dev

# Switch workspace
terraform workspace select dev
```

## Common Commands

### Basic Operations

```bash
# Initialize (download providers, modules)
terraform init

# Format code
terraform fmt -recursive

# Validate configuration
terraform validate

# Plan changes
terraform plan

# Apply changes
terraform apply

# Destroy resources
terraform destroy

# Show current state
terraform show

# List resources
terraform state list

# View outputs
terraform output
```

### Advanced Operations

```bash
# Plan with variable file
terraform plan -var-file="terraform.tfvars"

# Apply specific module
terraform apply -target=module.billing

# Import existing resource
terraform import aws_sns_topic.budget_alerts arn:aws:sns:...

# Refresh state
terraform refresh

# Taint resource (force recreation)
terraform taint aws_instance.example

# Untaint resource
terraform untaint aws_instance.example
```

## Cost Estimation

Use Infracost to estimate costs before applying:

```bash
# Install Infracost
brew install infracost  # macOS
# or
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh

# Generate cost estimate
infracost breakdown --path .

# Compare with previous estimate
infracost diff --path .
```

## Security Best Practices

### Secrets Management

- ❌ Never hardcode credentials in Terraform files
- ✅ Use AWS Secrets Manager for sensitive values
- ✅ Use environment variables for Terraform variables
- ✅ Use `.gitignore` to exclude sensitive files

### State File Security

- ❌ Never commit `terraform.tfstate` to Git
- ✅ Use S3 backend with encryption
- ✅ Enable versioning on state bucket
- ✅ Use DynamoDB for state locking

### Access Control

- ✅ Use IAM roles instead of access keys when possible
- ✅ Apply least privilege principle
- ✅ Rotate access keys regularly
- ✅ Enable MFA for sensitive operations

## Tagging Strategy

All resources should be tagged with:

```hcl
tags = {
  Project     = "festival-playlist"
  Environment = "dev|staging|prod"
  ManagedBy   = "terraform"
  Module      = "billing|networking|database|etc"
  CostCenter  = "hobby-project"
  Owner       = "your-name"
}
```

These tags enable:
- Cost tracking and allocation
- Resource organization
- Automated operations
- Compliance reporting

## Troubleshooting

### Common Issues

**Issue**: `Error: No valid credential sources found`
```bash
# Solution: Configure AWS CLI
aws configure --profile festival-playlist
```

**Issue**: `Error: Backend initialization required`
```bash
# Solution: Run terraform init
terraform init
```

**Issue**: `Error: Resource already exists`
```bash
# Solution: Import existing resource or remove from state
terraform import <resource_type>.<resource_name> <resource_id>
# or
terraform state rm <resource_type>.<resource_name>
```

**Issue**: State file locked
```bash
# Solution: Force unlock (use with caution!)
terraform force-unlock <lock-id>
```

### Getting Help

```bash
# Get help for command
terraform plan -help

# Get help for resource
terraform providers schema -json | jq '.provider_schemas["registry.terraform.io/hashicorp/aws"].resource_schemas["aws_sns_topic"]'
```

## Development Workflow

### Making Changes

1. Create feature branch
2. Make Terraform changes
3. Run `terraform fmt`
4. Run `terraform validate`
5. Run `terraform plan` and review
6. Commit changes (excluding sensitive files)
7. Create pull request
8. Review plan in PR
9. Merge to main
10. Apply changes in dev environment

### Testing Changes

1. Test in `dev` workspace first
2. Verify resources created correctly
3. Test functionality
4. Destroy and recreate to test idempotency
5. Promote to `staging` if applicable
6. Finally apply to `prod` with approval

## CI/CD Integration

Terraform will be integrated with GitHub Actions (Task 7):

- **PR Workflow**: `terraform plan` on every PR
- **Deploy Workflow**: `terraform apply` on merge to main
- **Cost Estimation**: Infracost comment on PRs
- **Security Scanning**: tfsec, checkov on PRs

## Documentation

- [AWS Account Setup Guide](../docs/aws-account-setup.md)
- [Billing Setup Quick Start](../docs/billing-setup-quickstart.md)
- [Task 1 Checklist](../docs/task-1-checklist.md)
- [Billing Module README](./modules/billing/README.md)

## Support

For issues or questions:
- Check module README files
- Review AWS documentation
- Check Terraform registry docs
- Create GitHub issue

## Version Requirements

- Terraform: >= 1.5
- AWS Provider: ~> 5.0
- AWS CLI: >= 2.0

## License

This infrastructure code is part of the Festival Playlist Generator project.

---

**Last Updated**: January 2026
**Maintained By**: Solo Developer
**Status**: In Development (Week 1)
