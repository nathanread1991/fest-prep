# Infrastructure Validation Guide

## Overview

This guide provides instructions for validating that all AWS infrastructure components are properly configured and accessible after provisioning.

## Quick Validation

Use the automated validation script:

```bash
cd infrastructure/terraform/scripts
./validate-infrastructure.sh
```

This script will check all infrastructure components and provide a summary report.

## Manual Validation Steps

If you prefer to validate manually or need to troubleshoot specific components, follow these steps:

### 1. Validate VPC and Networking

#### Check VPC exists:
```bash
aws ec2 describe-vpcs \
  --filters "Name=tag:Project,Values=festival-playlist" "Name=tag:Environment,Values=dev" \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'Vpcs[0].[VpcId,CidrBlock,State]' \
  --output table
```

**Expected:** VPC ID, CIDR 10.0.0.0/16, State: available

#### Check subnets:
```bash
# Public subnets
aws ec2 describe-subnets \
  --filters "Name=tag:Project,Values=festival-playlist" "Name=tag:Type,Values=public" \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'Subnets[].[SubnetId,CidrBlock,AvailabilityZone]' \
  --output table

# Private subnets
aws ec2 describe-subnets \
  --filters "Name=tag:Project,Values=festival-playlist" "Name=tag:Type,Values=private" \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'Subnets[].[SubnetId,CidrBlock,AvailabilityZone]' \
  --output table
```

**Expected:**
- 2 public subnets (10.0.1.0/24, 10.0.2.0/24) in different AZs
- 2 private subnets (10.0.10.0/24, 10.0.11.0/24) in different AZs

#### Check Internet Gateway:
```bash
aws ec2 describe-internet-gateways \
  --filters "Name=tag:Project,Values=festival-playlist" \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'InternetGateways[0].[InternetGatewayId,Attachments[0].State]' \
  --output table
```

**Expected:** IGW ID, State: available

### 2. Validate Security Groups

#### Check all security groups:
```bash
aws ec2 describe-security-groups \
  --filters "Name=tag:Project,Values=festival-playlist" \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecurityGroups[].[GroupId,GroupName,Description]' \
  --output table
```

**Expected security groups:**
- ALB security group (allows 80/443 from internet)
- ECS tasks security group (allows 8000 from ALB)
- RDS security group (allows 5432 from ECS)
- Redis security group (allows 6379 from ECS)
- VPC endpoints security group (allows 443 from ECS)

#### Verify security group rules:

**ALB Security Group:**
```bash
# Get ALB security group ID
ALB_SG=$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=*alb*" "Name=tag:Project,Values=festival-playlist" \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecurityGroups[0].GroupId' \
  --output text)

# Check inbound rules
aws ec2 describe-security-groups \
  --group-ids $ALB_SG \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecurityGroups[0].IpPermissions[].[FromPort,ToPort,IpRanges[0].CidrIp]' \
  --output table
```

**Expected:** Port 80 and 443 from 0.0.0.0/0

**ECS Tasks Security Group:**
```bash
# Get ECS security group ID
ECS_SG=$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=*ecs*" "Name=tag:Project,Values=festival-playlist" \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecurityGroups[0].GroupId' \
  --output text)

# Check inbound rules
aws ec2 describe-security-groups \
  --group-ids $ECS_SG \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecurityGroups[0].IpPermissions[].[FromPort,ToPort,UserIdGroupPairs[0].GroupId]' \
  --output table
```

**Expected:** Port 8000 from ALB security group only

### 3. Validate RDS Aurora Cluster

#### Check cluster status:
```bash
aws rds describe-db-clusters \
  --db-cluster-identifier festival-playlist-dev \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'DBClusters[0].[DBClusterIdentifier,Status,Engine,EngineVersion,Endpoint]' \
  --output table
```

**Expected:** Status: available, Engine: aurora-postgresql, Endpoint: *.rds.amazonaws.com

#### Check cluster instances:
```bash
aws rds describe-db-cluster-members \
  --db-cluster-identifier festival-playlist-dev \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'DBClusterMembers[].[DBInstanceIdentifier,IsClusterWriter,DBClusterParameterGroupStatus]' \
  --output table
```

**Expected:** At least 1 instance (writer)

#### Test database connectivity from ECS:

**Note:** This requires ECS tasks to be running. You can test connectivity by:
1. Checking CloudWatch Logs for database connection errors
2. Running a test query from an ECS task
3. Using AWS Systems Manager Session Manager to connect to an ECS task

### 4. Validate ElastiCache Redis

#### Check Redis cluster status:
```bash
aws elasticache describe-replication-groups \
  --replication-group-id festival-playlist-dev \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'ReplicationGroups[0].[ReplicationGroupId,Status,NodeGroups[0].PrimaryEndpoint.Address,NodeGroups[0].PrimaryEndpoint.Port]' \
  --output table
```

**Expected:** Status: available, Endpoint: *.cache.amazonaws.com, Port: 6379

#### Check cache nodes:
```bash
aws elasticache describe-cache-clusters \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'CacheClusters[?starts_with(CacheClusterId, `festival-playlist-dev`)].[CacheClusterId,CacheNodeType,CacheClusterStatus]' \
  --output table
```

**Expected:** At least 1 node, Type: cache.t4g.micro, Status: available

### 5. Validate S3 Buckets

#### Check buckets exist:
```bash
aws s3 ls --profile festival-playlist | grep festival-playlist-dev
```

**Expected:**
- festival-playlist-dev-app-data
- festival-playlist-dev-cloudfront-logs

#### Check bucket versioning:
```bash
aws s3api get-bucket-versioning \
  --bucket festival-playlist-dev-app-data \
  --profile festival-playlist
```

**Expected:** Status: Enabled

#### Check bucket encryption:
```bash
aws s3api get-bucket-encryption \
  --bucket festival-playlist-dev-app-data \
  --profile festival-playlist
```

**Expected:** SSEAlgorithm: AES256

#### Check public access block:
```bash
aws s3api get-public-access-block \
  --bucket festival-playlist-dev-app-data \
  --profile festival-playlist
```

**Expected:** All settings: true (no public access)

### 6. Validate ECR Repository

#### Check repository exists:
```bash
aws ecr describe-repositories \
  --repository-names festival-playlist \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'repositories[0].[repositoryName,repositoryUri,imageScanningConfiguration.scanOnPush]' \
  --output table
```

**Expected:** Repository name, URI, Image scanning: True

#### Check lifecycle policy:
```bash
aws ecr get-lifecycle-policy \
  --repository-name festival-playlist \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'lifecyclePolicyText' \
  --output text | jq
```

**Expected:** Policy to keep last 10 images

### 7. Validate Secrets Manager

#### List all secrets:
```bash
aws secretsmanager list-secrets \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecretList[?starts_with(Name, `festival-playlist-dev`)].Name' \
  --output table
```

**Expected secrets:**
- festival-playlist-dev-db-credentials
- festival-playlist-dev-redis-url
- festival-playlist-dev-spotify
- festival-playlist-dev-setlistfm
- festival-playlist-dev-jwt-secret

#### Check if secrets have values:
```bash
# Database credentials (auto-populated)
aws secretsmanager get-secret-value \
  --secret-id festival-playlist-dev-db-credentials \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecretString' \
  --output text | jq

# Redis URL (auto-populated)
aws secretsmanager get-secret-value \
  --secret-id festival-playlist-dev-redis-url \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecretString' \
  --output text | jq

# Spotify (requires manual population)
aws secretsmanager get-secret-value \
  --secret-id festival-playlist-dev-spotify \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecretString' \
  --output text | jq

# Setlist.fm (requires manual population)
aws secretsmanager get-secret-value \
  --secret-id festival-playlist-dev-setlistfm \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecretString' \
  --output text | jq

# JWT secret (auto-populated)
aws secretsmanager get-secret-value \
  --secret-id festival-playlist-dev-jwt-secret \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'SecretString' \
  --output text | jq
```

**Expected:** All secrets should return JSON values. If Spotify or Setlist.fm return errors, they need to be populated manually.

### 8. Validate CloudWatch Logs

#### Check log groups exist:
```bash
aws logs describe-log-groups \
  --log-group-name-prefix /ecs/festival-playlist-dev \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'logGroups[].[logGroupName,retentionInDays]' \
  --output table
```

**Expected log groups:**
- /ecs/festival-playlist-dev-api (retention: 7 days)
- /ecs/festival-playlist-dev-worker (retention: 7 days)

#### Check for log streams (after ECS tasks start):
```bash
aws logs describe-log-streams \
  --log-group-name /ecs/festival-playlist-dev-api \
  --profile festival-playlist \
  --region eu-west-2 \
  --max-items 5 \
  --query 'logStreams[].[logStreamName,lastEventTime]' \
  --output table
```

**Expected:** Log streams from ECS tasks (after deployment)

## Validation Checklist

Use this checklist to track validation progress:

- [ ] VPC created with correct CIDR (10.0.0.0/16)
- [ ] 2 public subnets in different AZs
- [ ] 2 private subnets in different AZs
- [ ] Internet Gateway attached
- [ ] 5 security groups created (ALB, ECS, RDS, Redis, VPC Endpoints)
- [ ] Security group rules configured correctly (zero-trust model)
- [ ] RDS Aurora cluster available
- [ ] RDS cluster has at least 1 instance
- [ ] RDS endpoint accessible
- [ ] ElastiCache Redis cluster available
- [ ] Redis endpoint accessible
- [ ] App data S3 bucket created with versioning and encryption
- [ ] CloudFront logs S3 bucket created
- [ ] ECR repository created with image scanning enabled
- [ ] 5 Secrets Manager secrets created
- [ ] Database and Redis secrets auto-populated
- [ ] Spotify and Setlist.fm secrets populated manually
- [ ] JWT secret auto-populated
- [ ] CloudWatch log groups created for API and worker

## Troubleshooting

### Issue: VPC or subnets not found

**Cause:** Terraform apply didn't complete successfully

**Solution:**
```bash
cd infrastructure/terraform
terraform apply -target=module.networking
```

### Issue: RDS cluster status is "creating"

**Cause:** RDS cluster is still being provisioned

**Solution:** Wait 10-15 minutes for cluster to become available. Check status:
```bash
aws rds describe-db-clusters \
  --db-cluster-identifier festival-playlist-dev \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'DBClusters[0].Status' \
  --output text
```

### Issue: Redis cluster status is "creating"

**Cause:** Redis cluster is still being provisioned

**Solution:** Wait 5-10 minutes for cluster to become available. Check status:
```bash
aws elasticache describe-replication-groups \
  --replication-group-id festival-playlist-dev \
  --profile festival-playlist \
  --region eu-west-2 \
  --query 'ReplicationGroups[0].Status' \
  --output text
```

### Issue: Secrets not found

**Cause:** Security module not applied

**Solution:**
```bash
cd infrastructure/terraform
terraform apply -target=module.security
```

### Issue: Cannot access secrets

**Cause:** IAM permissions issue

**Solution:** Verify your AWS CLI profile has secretsmanager:GetSecretValue permission

### Issue: Security groups have no rules

**Cause:** Networking module not fully applied

**Solution:**
```bash
cd infrastructure/terraform
terraform apply -target=module.networking
```

## Next Steps

After successful validation:

1. ✅ Populate secrets (if not already done): `./populate-secrets.sh`
2. ✅ Build Docker image
3. ✅ Push image to ECR
4. ✅ Deploy application to ECS
5. ✅ Test application functionality

## Automated Validation

For continuous validation, you can run the validation script in a cron job or CI/CD pipeline:

```bash
# Run validation every hour
0 * * * * cd /path/to/infrastructure/terraform/scripts && ./validate-infrastructure.sh >> /var/log/infra-validation.log 2>&1
```

Or integrate into GitHub Actions:

```yaml
- name: Validate Infrastructure
  run: |
    cd infrastructure/terraform/scripts
    ./validate-infrastructure.sh
```
