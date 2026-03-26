# Compute Module - Quick Start Guide

## Prerequisites

Before using this module, ensure you have:

1. ✅ Networking module deployed (VPC, subnets, security groups)
2. ✅ Storage module deployed (ECR repository, S3 buckets)
3. ✅ Database module deployed (Aurora Serverless, secrets)
4. ✅ Cache module deployed (ElastiCache Redis, secrets)
5. ✅ Docker image built and pushed to ECR

## Minimal Configuration

```hcl
module "compute" {
  source = "./modules/compute"

  # Required: Basic info
  project_name = "festival-app"
  environment  = "dev"

  # Required: Networking (from networking module)
  vpc_id                       = module.networking.vpc_id
  public_subnet_ids            = module.networking.public_subnet_ids
  private_subnet_ids           = module.networking.private_subnet_ids
  alb_security_group_id        = module.networking.alb_security_group_id
  ecs_tasks_security_group_id  = module.networking.ecs_tasks_security_group_id

  # Required: ECR (from storage module)
  ecr_repository_url = module.storage.ecr_repository_url

  # Required: Secrets (from database and cache modules)
  secrets_arns = [
    module.database.secret_arn,
    module.cache.secret_arn
  ]
  db_secret_arn    = module.database.secret_arn
  redis_secret_arn = module.cache.secret_arn

  # Required: S3 (from storage module)
  app_data_bucket_arn = module.storage.app_data_bucket_arn

  common_tags = {
    Project     = "festival-app"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

## Deploy

```bash
# Initialize Terraform
terraform init

# Plan the deployment
terraform plan

# Apply the configuration
terraform apply

# Get the ALB DNS name
terraform output alb_dns_name
```

## Access Your Application

```bash
# Get the ALB DNS name
ALB_DNS=$(terraform output -raw alb_dns_name)

# Test the health endpoint
curl http://${ALB_DNS}/health

# Access the API
curl http://${ALB_DNS}/api/v1/festivals
```

## Monitor Your Deployment

```bash
# View ECS service status
aws ecs describe-services \
  --cluster festival-app-dev-cluster \
  --services festival-app-dev-api

# View running tasks
aws ecs list-tasks \
  --cluster festival-app-dev-cluster \
  --service-name festival-app-dev-api

# View logs
aws logs tail /ecs/festival-app-dev/api --follow
```

## Common Issues

### Issue: Tasks not starting

**Solution**: Check CloudWatch logs
```bash
aws logs tail /ecs/festival-app-dev/api --follow
```

### Issue: Health checks failing

**Solution**: Verify the /health endpoint
```bash
# Get task IP
TASK_ARN=$(aws ecs list-tasks --cluster festival-app-dev-cluster --service-name festival-app-dev-api --query 'taskArns[0]' --output text)
TASK_IP=$(aws ecs describe-tasks --cluster festival-app-dev-cluster --tasks $TASK_ARN --query 'tasks[0].containers[0].networkInterfaces[0].privateIpv4Address' --output text)

# Test health endpoint directly
curl http://${TASK_IP}:8000/health
```

### Issue: Can't pull ECR image

**Solution**: Verify IAM permissions
```bash
# Check task execution role
aws iam get-role --role-name festival-app-dev-ecs-execution-role

# Verify ECR permissions
aws iam list-role-policies --role-name festival-app-dev-ecs-execution-role
```

## Next Steps

1. **Enable HTTPS**: Deploy security module for ACM certificate
2. **Add Custom Domain**: Configure Route 53 in security module
3. **Enable Monitoring**: Deploy monitoring module for dashboards and alarms
4. **Add CDN**: Deploy CDN module for CloudFront distribution
5. **Configure CI/CD**: Set up GitHub Actions for automated deployments

## Cost Estimate

### Development (8 hours/day, 5 days/week)
- API Service: ~$2-3/month
- Worker Service: ~$1/month
- ALB: ~$2/month
- **Total**: ~$5-6/month

### Production (24/7)
- API Service: ~$15-30/month
- Worker Service: ~$2-4/month
- ALB: ~$16/month
- **Total**: ~$33-50/month

## Teardown

```bash
# Destroy all compute resources
terraform destroy

# Note: This will NOT destroy:
# - ECR images
# - S3 buckets
# - Secrets Manager secrets
# - Database snapshots
```

## Support

For detailed documentation, see:
- [README.md](./README.md) - Complete module documentation
- [USAGE.md](./USAGE.md) - Detailed usage examples
- [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) - Implementation details
