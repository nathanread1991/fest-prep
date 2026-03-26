# Compute Module - Deployment Checklist

Use this checklist to ensure a successful deployment of the compute module.

## Pre-Deployment Checklist

### Infrastructure Prerequisites
- [ ] Networking module deployed
  - [ ] VPC created
  - [ ] Public subnets created (minimum 2 for ALB)
  - [ ] Private subnets created
  - [ ] Security groups created (ALB, ECS tasks)
  - [ ] VPC endpoints created (ECR, CloudWatch, Secrets Manager)

- [ ] Storage module deployed
  - [ ] ECR repository created
  - [ ] S3 app data bucket created
  - [ ] S3 CloudFront logs bucket created (if using access logs)

- [ ] Database module deployed
  - [ ] Aurora Serverless v2 cluster created
  - [ ] Database secret created in Secrets Manager
  - [ ] Database accessible from ECS security group

- [ ] Cache module deployed
  - [ ] ElastiCache Redis cluster created
  - [ ] Redis secret created in Secrets Manager
  - [ ] Redis accessible from ECS security group

### Application Prerequisites
- [ ] Docker image built
- [ ] Docker image pushed to ECR
- [ ] Image tag noted (e.g., "latest", "v1.0.0")
- [ ] Application has /health endpoint
- [ ] Application reads DATABASE_URL from environment
- [ ] Application reads REDIS_URL from environment

### Secrets Prerequisites
- [ ] Database credentials in Secrets Manager
  - [ ] Secret contains "url" key
  - [ ] Secret contains "host", "port", "username", "password", "database" keys

- [ ] Redis credentials in Secrets Manager
  - [ ] Secret contains "url" key

- [ ] Optional: Spotify credentials in Secrets Manager
  - [ ] Secret contains "client_id" key
  - [ ] Secret contains "client_secret" key

- [ ] Optional: JWT secret in Secrets Manager
  - [ ] Secret contains "secret_key" key

- [ ] Optional: Setlist.fm API key in Secrets Manager
  - [ ] Secret contains "api_key" key

## Deployment Checklist

### Configuration
- [ ] Set project_name variable
- [ ] Set environment variable (dev, staging, prod)
- [ ] Configure VPC and subnet IDs
- [ ] Configure security group IDs
- [ ] Configure ECR repository URL
- [ ] Configure image tags (api_image_tag, worker_image_tag)
- [ ] Configure secret ARNs
- [ ] Configure S3 bucket ARN
- [ ] Set common_tags

### Optional Configuration
- [ ] Configure task sizes (CPU, memory)
- [ ] Configure desired task counts
- [ ] Configure auto-scaling settings
- [ ] Configure log retention
- [ ] Configure ALB settings
- [ ] Configure HTTPS (if ACM certificate available)

### Terraform Commands
- [ ] Run `terraform init`
- [ ] Run `terraform validate`
- [ ] Run `terraform plan`
- [ ] Review plan output carefully
- [ ] Run `terraform apply`
- [ ] Confirm apply

## Post-Deployment Checklist

### Verification
- [ ] ECS cluster created
  - [ ] Check AWS Console: ECS > Clusters
  - [ ] Verify cluster name matches expected

- [ ] ECS services created
  - [ ] API service running
  - [ ] Worker service running
  - [ ] Desired count matches configuration

- [ ] ECS tasks running
  - [ ] API tasks in RUNNING state
  - [ ] Worker tasks in RUNNING state
  - [ ] No tasks in STOPPED state with errors

- [ ] ALB created
  - [ ] Check AWS Console: EC2 > Load Balancers
  - [ ] ALB is active
  - [ ] Target group created
  - [ ] Targets are healthy

- [ ] CloudWatch logs created
  - [ ] API log group exists
  - [ ] Worker log group exists
  - [ ] Logs are being written

### Testing
- [ ] Health check endpoint
  ```bash
  curl http://<ALB_DNS>/health
  ```
  - [ ] Returns 200 OK
  - [ ] Response is valid JSON

- [ ] API endpoints
  ```bash
  curl http://<ALB_DNS>/api/v1/festivals
  ```
  - [ ] Returns expected response
  - [ ] No 500 errors

- [ ] Database connectivity
  - [ ] Check logs for database connection messages
  - [ ] No database connection errors

- [ ] Redis connectivity
  - [ ] Check logs for Redis connection messages
  - [ ] No Redis connection errors

- [ ] External API connectivity (if configured)
  - [ ] Spotify API accessible
  - [ ] Setlist.fm API accessible

### Monitoring
- [ ] CloudWatch logs accessible
  ```bash
  aws logs tail /ecs/<project>-<env>/api --follow
  ```

- [ ] ECS metrics visible
  - [ ] CPU utilization
  - [ ] Memory utilization
  - [ ] Task count

- [ ] ALB metrics visible
  - [ ] Request count
  - [ ] Target response time
  - [ ] Healthy host count

- [ ] Auto-scaling configured (if enabled)
  - [ ] Scaling policies attached
  - [ ] Scaling target configured

### Security
- [ ] IAM roles created
  - [ ] Task execution role
  - [ ] Task role

- [ ] IAM policies attached
  - [ ] ECR pull permissions
  - [ ] CloudWatch logs write permissions
  - [ ] Secrets Manager read permissions
  - [ ] S3 access permissions

- [ ] Security groups configured
  - [ ] ALB accepts traffic from internet (80, 443)
  - [ ] ECS tasks accept traffic only from ALB (8000)
  - [ ] ECS tasks can access database (5432)
  - [ ] ECS tasks can access Redis (6379)

- [ ] Secrets accessible
  - [ ] Tasks can read database secret
  - [ ] Tasks can read Redis secret
  - [ ] Tasks can read application secrets

## Troubleshooting Checklist

### Tasks Not Starting
- [ ] Check CloudWatch logs for errors
- [ ] Verify ECR image exists and is accessible
- [ ] Verify IAM execution role has ECR permissions
- [ ] Verify security group allows outbound traffic
- [ ] Verify subnets have internet access (public IP or NAT)

### Health Checks Failing
- [ ] Verify /health endpoint exists
- [ ] Verify container port matches target group port (8000)
- [ ] Check application logs for errors
- [ ] Verify health check path is correct
- [ ] Verify health check timeout is sufficient

### Database Connection Errors
- [ ] Verify database secret ARN is correct
- [ ] Verify secret contains "url" key
- [ ] Verify security group allows ECS → RDS (5432)
- [ ] Verify database is running
- [ ] Check database credentials are correct

### Redis Connection Errors
- [ ] Verify Redis secret ARN is correct
- [ ] Verify secret contains "url" key
- [ ] Verify security group allows ECS → Redis (6379)
- [ ] Verify Redis cluster is running
- [ ] Check Redis connection string format

### Auto-Scaling Not Working
- [ ] Verify auto-scaling is enabled
- [ ] Verify scaling policies are attached
- [ ] Check CloudWatch metrics for CPU/memory
- [ ] Verify scaling thresholds are appropriate
- [ ] Check scaling cooldown periods

### High Costs
- [ ] Check number of running tasks
- [ ] Verify auto-scaling is working correctly
- [ ] Consider using FARGATE_SPOT for workers
- [ ] Reduce task sizes if over-provisioned
- [ ] Reduce log retention if too long
- [ ] Disable Container Insights in dev

## Rollback Checklist

If deployment fails or issues arise:

- [ ] Check Terraform state
  ```bash
  terraform show
  ```

- [ ] Identify problematic resources
  ```bash
  terraform state list
  ```

- [ ] Option 1: Fix and re-apply
  - [ ] Fix configuration
  - [ ] Run `terraform plan`
  - [ ] Run `terraform apply`

- [ ] Option 2: Destroy and redeploy
  - [ ] Run `terraform destroy`
  - [ ] Fix configuration
  - [ ] Run `terraform apply`

- [ ] Option 3: Rollback to previous image
  - [ ] Update image tag to previous version
  - [ ] Run `terraform apply`
  - [ ] Wait for ECS to deploy old image

## Maintenance Checklist

### Weekly
- [ ] Review CloudWatch logs for errors
- [ ] Check ECS service health
- [ ] Review ALB target health
- [ ] Check auto-scaling metrics

### Monthly
- [ ] Review and optimize task sizes
- [ ] Review and optimize auto-scaling thresholds
- [ ] Review CloudWatch log retention
- [ ] Review costs and optimize

### Quarterly
- [ ] Update Docker images
- [ ] Review and update IAM policies
- [ ] Review and update security groups
- [ ] Review and update Terraform module version

## Documentation Checklist

- [ ] Document custom environment variables
- [ ] Document any manual configuration steps
- [ ] Document troubleshooting procedures
- [ ] Document rollback procedures
- [ ] Update runbooks with lessons learned

## Sign-Off

- [ ] Deployment completed successfully
- [ ] All tests passing
- [ ] Monitoring configured
- [ ] Documentation updated
- [ ] Team notified

**Deployed by**: _______________
**Date**: _______________
**Environment**: _______________
**Version**: _______________
