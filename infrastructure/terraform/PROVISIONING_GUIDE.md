# AWS Infrastructure Provisioning Guide

## Overview

This guide provides step-by-step instructions for provisioning the Festival Playlist Generator infrastructure on AWS using Terraform.

## Prerequisites

1. **AWS CLI configured** with profile `festival-playlist`
   ```bash
   aws configure --profile festival-playlist
   aws sts get-caller-identity --profile festival-playlist
   ```

2. **Terraform installed** (v1.10+)
   ```bash
   terraform version
   ```

3. **S3 backend bucket created** (already done)
   - Bucket: `festival-playlist-terraform-state`
   - Region: `eu-west-2`

4. **terraform.tfvars configured** with your email address for alerts

## Provisioning Steps

### Step 1: Initialize Terraform

```bash
cd infrastructure/terraform
terraform init
```

Expected output: "Terraform has been successfully initialized!"

### Step 2: Review the Plan

```bash
terraform plan
```

Review the resources that will be created. Expected: ~134 resources.

### Step 3: Apply Infrastructure in Stages

Due to Terraform dependencies and computed values, we need to apply in stages:

#### Stage 1: Foundation Infrastructure

Create networking, storage, database, and cache:

```bash
terraform apply -target=module.billing \
                -target=module.networking \
                -target=module.storage \
                -target=module.database \
                -target=module.cache
```

**What this creates:**
- VPC with public/private subnets
- Security groups
- S3 buckets (app-data, cloudfront-logs)
- ECR repository
- Aurora Serverless v2 PostgreSQL cluster
- ElastiCache Redis cluster
- Secrets Manager secrets for DB and Redis

**Time:** ~10-15 minutes

#### Stage 2: Security and Compute

Create security resources and ECS infrastructure:

```bash
terraform apply -target=module.security \
                -target=module.compute
```

**What this creates:**
- ACM certificates (ALB and CloudFront)
- Route 53 hosted zone
- WAF Web ACL
- Secrets Manager secrets (Spotify, Setlist.fm, JWT)
- ECS Fargate cluster
- ECS task definitions (API and Worker)
- ECS services
- Application Load Balancer
- Auto-scaling policies

**Time:** ~10-15 minutes

**Note:** ACM certificate validation requires DNS records to be added. Terraform will wait for validation.

#### Stage 3: CDN and Monitoring

Create CloudFront distribution and monitoring:

```bash
terraform apply -target=module.cdn \
                -target=module.monitoring
```

**What this creates:**
- CloudFront distribution
- CloudFront Origin Access Identity
- CloudWatch Log Groups
- CloudWatch Alarms
- CloudWatch Dashboard
- SNS topics for alarms

**Time:** ~15-20 minutes (CloudFront distribution takes time)

#### Stage 4: Final Apply

Apply everything to ensure all resources are in sync:

```bash
terraform apply
```

This will create any remaining resources and ensure all dependencies are properly configured.

**Time:** ~5 minutes

### Step 4: Verify Infrastructure

Check that all resources were created successfully:

```bash
# Check ECS cluster
aws ecs list-clusters --profile festival-playlist --region eu-west-2

# Check RDS cluster
aws rds describe-db-clusters --profile festival-playlist --region eu-west-2

# Check ElastiCache cluster
aws elasticache describe-replication-groups --profile festival-playlist --region eu-west-2

# Check ALB
aws elbv2 describe-load-balancers --profile festival-playlist --region eu-west-2

# Check CloudFront distribution
aws cloudfront list-distributions --profile festival-playlist
```

## Post-Provisioning Tasks

### 1. Populate Secrets

The following secrets were created but need to be populated manually:

```bash
# Spotify API credentials
aws secretsmanager put-secret-value \
  --secret-id festival-playlist-dev-spotify \
  --secret-string '{"client_id":"YOUR_SPOTIFY_CLIENT_ID","client_secret":"YOUR_SPOTIFY_CLIENT_SECRET"}' \
  --profile festival-playlist \
  --region eu-west-2

# Setlist.fm API key
aws secretsmanager put-secret-value \
  --secret-id festival-playlist-dev-setlistfm \
  --secret-string '{"api_key":"YOUR_SETLISTFM_API_KEY"}' \
  --profile festival-playlist \
  --region eu-west-2
```

**Note:** JWT secret is auto-generated and doesn't need manual population.

### 2. Configure DNS

Update your domain registrar's nameservers to point to Route 53:

```bash
# Get Route 53 nameservers
terraform output -json | jq -r '.route53_name_servers.value[]'
```

Add these nameservers to your domain registrar (e.g., Namecheap, GoDaddy).

### 3. Wait for Certificate Validation

ACM certificates require DNS validation. Check status:

```bash
# Check ALB certificate
aws acm describe-certificate \
  --certificate-arn $(terraform output -raw alb_certificate_arn) \
  --profile festival-playlist \
  --region eu-west-2

# Check CloudFront certificate
aws acm describe-certificate \
  --certificate-arn $(terraform output -raw cloudfront_certificate_arn) \
  --profile festival-playlist \
  --region us-east-1
```

Wait until status is "ISSUED" (usually 5-30 minutes after DNS propagation).

## Troubleshooting

### Issue: "Error: Invalid count argument" for WAF association

**Solution:** This is expected. The WAF association depends on the ALB ARN which is computed at apply time. Use the staged approach above.

### Issue: Certificate validation stuck

**Solution:** Ensure DNS records are properly configured. Check Route 53 for validation records.

### Issue: ECS tasks not starting

**Solution:**
1. Check CloudWatch Logs: `/ecs/festival-api` and `/ecs/festival-worker`
2. Verify secrets are populated
3. Check security group rules

### Issue: Database connection timeout

**Solution:**
1. Verify RDS cluster is in "available" state
2. Check security group allows traffic from ECS tasks
3. Verify database secret contains correct connection string

## Cost Monitoring

After provisioning, monitor costs:

```bash
# Check current month costs
aws ce get-cost-and-usage \
  --time-period Start=2026-01-01,End=2026-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --profile festival-playlist

# Check budget status
aws budgets describe-budgets \
  --account-id $(aws sts get-caller-identity --query Account --output text --profile festival-playlist) \
  --profile festival-playlist
```

## Teardown

To destroy the infrastructure (save costs when not in use):

```bash
cd infrastructure/terraform/scripts
./teardown.sh
```

This will:
1. Create a database snapshot
2. Destroy all infrastructure except persistent resources (S3, Secrets Manager, ECR)
3. Clean up old snapshots

## Provision from Snapshot

To restore infrastructure from a snapshot:

```bash
cd infrastructure/terraform/scripts
./provision.sh
```

This will:
1. Find the latest database snapshot
2. Apply Terraform with snapshot restore
3. Wait for services to be healthy
4. Display API URL

## Next Steps

After successful provisioning:

1. ✅ Complete Task 18.2: Manually populate secrets
2. ✅ Complete Task 18.3: Validate infrastructure
3. ✅ Build and push Docker image to ECR
4. ✅ Deploy application to ECS
5. ✅ Test application functionality

## Support

For issues or questions:
- Check CloudWatch Logs for application errors
- Review Terraform state: `terraform show`
- Check AWS Console for resource status
- Review task documentation in `.kiro/specs/aws-enterprise-migration/`
