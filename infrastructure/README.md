# Infrastructure

This directory contains all Infrastructure as Code (IaC) for the Festival Playlist Generator.

## Structure

```
infrastructure/
└── terraform/              # Terraform configurations
    ├── modules/           # Reusable Terraform modules
    │   ├── billing/      # AWS Budgets, Cost Anomaly Detection
    │   ├── networking/   # VPC, subnets, security groups
    │   ├── database/     # Aurora Serverless v2
    │   ├── cache/        # ElastiCache Redis
    │   ├── compute/      # ECS Fargate, ALB
    │   ├── storage/      # S3, ECR
    │   ├── cdn/          # CloudFront
    │   ├── monitoring/   # CloudWatch, X-Ray
    │   └── security/     # Secrets Manager, ACM, WAF
    ├── scripts/          # Utility scripts
    ├── main.tf           # Root module
    ├── variables.tf      # Input variables
    ├── outputs.tf        # Output values
    └── backend.tf        # Remote state configuration
```

## AWS Architecture

**Region:** eu-west-2 (London)

**Services:**
- **Compute:** ECS Fargate (API + Worker services)
- **Database:** Aurora Serverless v2 PostgreSQL
- **Cache:** ElastiCache Redis
- **Storage:** S3, ECR
- **CDN:** CloudFront
- **Networking:** VPC with public/private subnets
- **Security:** Secrets Manager, ACM, WAF
- **Monitoring:** CloudWatch, X-Ray

## Cost Optimization

**Target:** $10-15/month with daily teardown capability

**Strategy:**
- Aurora Serverless v2 with auto-pause (dev)
- ECS Fargate Spot for worker service (70% savings)
- Native S3 state locking (no DynamoDB costs)
- Daily teardown/provision scripts
- S3 Intelligent-Tiering

## Getting Started

See [terraform/README.md](terraform/README.md) for detailed setup instructions.

## Deployment

All infrastructure changes are managed via Terraform:
```bash
cd infrastructure/terraform
terraform plan
terraform apply
```

## State Management

Terraform state is stored remotely in S3 with native locking (Terraform v1.10+).

**Backend:** `festival-playlist-terraform-state` (S3 bucket in eu-west-2)
