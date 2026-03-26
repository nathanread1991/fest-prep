# Database Module - Quick Start Guide

This guide provides quick examples for common database module usage scenarios.

## Table of Contents

1. [Initial Setup](#initial-setup)
2. [Daily Teardown/Rebuild Workflow](#daily-teardownrebuild-workflow)
3. [Snapshot Management](#snapshot-management)
4. [Monitoring and Alarms](#monitoring-and-alarms)
5. [Troubleshooting](#troubleshooting)

## Initial Setup

### Step 1: Enable the Database Module

Edit `infrastructure/terraform/main.tf` and uncomment the database module:

```hcl
module "database" {
  source = "./modules/database"

  project_name           = var.project_name
  environment            = var.environment
  private_subnet_ids     = module.networking.private_subnet_ids
  rds_security_group_id  = module.networking.rds_security_group_id

  # Start with minimal configuration
  min_capacity = 0.5
  max_capacity = 2
  instance_count = 1
  skip_final_snapshot = true  # For initial testing

  common_tags = var.common_tags
}
```

### Step 2: Initialize and Apply

```bash
cd infrastructure/terraform
terraform init
terraform plan
terraform apply
```

**Expected Time**: 10-15 minutes for initial cluster creation

### Step 3: Verify Database Connection

```bash
# Get connection details from Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id festival-playlist-dev-db-credentials \
  --query SecretString \
  --output text | jq .

# Test connection (requires psql client)
psql "$(aws secretsmanager get-secret-value \
  --secret-id festival-playlist-dev-db-credentials \
  --query SecretString \
  --output text | jq -r .url)"
```

## Daily Teardown/Rebuild Workflow

### Teardown (End of Day)

```bash
cd infrastructure/terraform

# Step 1: Ensure final snapshot will be created
# Edit main.tf and set: skip_final_snapshot = false

# Step 2: Destroy infrastructure
terraform destroy -target=module.database

# Step 3: Verify snapshot was created
./scripts/list-snapshots.sh festival-playlist-dev-aurora-cluster
```

**Expected Time**: 5-10 minutes

**Cost While Torn Down**: $0-1/month (snapshots free for 7 days)

### Rebuild (Start of Day)

```bash
cd infrastructure/terraform

# Step 1: Enable restore from snapshot
# Edit main.tf and set: restore_from_snapshot = true

# Step 2: Provision infrastructure
terraform apply

# Step 3: Verify database is accessible
psql "$(aws secretsmanager get-secret-value \
  --secret-id festival-playlist-dev-db-credentials \
  --query SecretString \
  --output text | jq -r .url)" -c "SELECT version();"
```

**Expected Time**: 5-10 minutes (faster than initial creation)

**Data Restored**: All data from the latest snapshot

## Snapshot Management

### List All Snapshots

```bash
cd infrastructure/terraform
./scripts/list-snapshots.sh festival-playlist-dev-aurora-cluster
```

**Output Example**:
```
=== RDS Cluster Snapshots ===
Cluster: festival-playlist-dev-aurora-cluster

Found 5 snapshot(s):

Snapshot ID                                              Created                   Status       Size (GB) Engine               Version
-------------------------------------------------------- ------------------------- ------------ --------- -------------------- ----------
festival-playlist-dev-final-snapshot-2024-01-22-1430    2024-01-22T14:30:00Z     available    10        aurora-postgresql    15.3
festival-playlist-dev-final-snapshot-2024-01-21-1430    2024-01-21T14:30:00Z     available    10        aurora-postgresql    15.3

Total snapshots: 5
Total storage: 50GB
```

### Clean Up Old Snapshots

```bash
cd infrastructure/terraform

# Keep only last 7 days
./scripts/cleanup-old-snapshots.sh festival-playlist-dev-aurora-cluster 7

# Keep only last 3 days (more aggressive)
./scripts/cleanup-old-snapshots.sh festival-playlist-dev-aurora-cluster 3
```

**Cost Savings**: Each 10GB snapshot costs ~$1/month after 7 days

### Manual Snapshot Creation

```bash
# Create a manual snapshot before major changes
aws rds create-db-cluster-snapshot \
  --db-cluster-identifier festival-playlist-dev-aurora-cluster \
  --db-cluster-snapshot-identifier festival-playlist-dev-manual-$(date +%Y%m%d-%H%M%S)
```

### Restore from Specific Snapshot

```hcl
# In main.tf
module "database" {
  # ... other config ...

  restore_from_snapshot = false  # Disable auto-restore
  snapshot_identifier   = "festival-playlist-dev-final-snapshot-2024-01-22-1430"
}
```

## Monitoring and Alarms

### View CloudWatch Logs

```bash
# View PostgreSQL logs
aws logs tail /aws/rds/cluster/festival-playlist-dev-aurora-cluster/postgresql --follow

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/rds/cluster/festival-playlist-dev-aurora-cluster/postgresql \
  --filter-pattern "ERROR"
```

### Check Performance Insights

```bash
# Open Performance Insights in AWS Console
aws rds describe-db-clusters \
  --db-cluster-identifier festival-playlist-dev-aurora-cluster \
  --query 'DBClusters[0].PerformanceInsightsEnabled'
```

Or visit: https://console.aws.amazon.com/rds/home?region=eu-west-2#performance-insights:

### View CloudWatch Metrics

```bash
# CPU Utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBClusterIdentifier,Value=festival-playlist-dev-aurora-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average

# Database Connections
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBClusterIdentifier,Value=festival-playlist-dev-aurora-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average

# ACU Utilization (Serverless v2 specific)
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name ACUUtilization \
  --dimensions Name=DBClusterIdentifier,Value=festival-playlist-dev-aurora-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

### Test Alarms

```bash
# List all alarms for the database
aws cloudwatch describe-alarms \
  --alarm-name-prefix festival-playlist-dev-rds

# Check alarm state
aws cloudwatch describe-alarms \
  --alarm-names festival-playlist-dev-rds-cpu-high \
  --query 'MetricAlarms[0].StateValue'
```

## Troubleshooting

### Issue: Cluster Creation Fails

**Symptoms**: Terraform apply fails with "Error creating RDS Cluster"

**Solutions**:
1. Check CloudWatch Logs for detailed error messages
2. Verify security group allows traffic from ECS tasks
3. Verify subnet group has subnets in at least 2 AZs
4. Check AWS service quotas for RDS

```bash
# Check service quotas
aws service-quotas get-service-quota \
  --service-code rds \
  --quota-code L-952B80B8  # DB clusters per region
```

### Issue: Cannot Connect to Database

**Symptoms**: Connection timeout or "could not connect to server"

**Solutions**:
1. Verify database is in "available" state
2. Check security group rules
3. Verify connection string is correct
4. Ensure you're connecting from ECS task (not local machine)

```bash
# Check cluster status
aws rds describe-db-clusters \
  --db-cluster-identifier festival-playlist-dev-aurora-cluster \
  --query 'DBClusters[0].Status'

# Check security group rules
aws ec2 describe-security-groups \
  --group-ids $(terraform output -raw rds_security_group_id) \
  --query 'SecurityGroups[0].IpPermissions'
```

### Issue: High Costs

**Symptoms**: Database costs higher than expected

**Solutions**:
1. Check ACU usage in CloudWatch
2. Reduce max_capacity if not needed
3. Implement daily teardown workflow
4. Clean up old snapshots

```bash
# Check average ACU usage
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name ACUUtilization \
  --dimensions Name=DBClusterIdentifier,Value=festival-playlist-dev-aurora-cluster \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Average

# List old snapshots
./scripts/list-snapshots.sh festival-playlist-dev-aurora-cluster
```

### Issue: Snapshot Restore Fails

**Symptoms**: Terraform apply fails when restoring from snapshot

**Solutions**:
1. Verify snapshot exists and is available
2. Check snapshot is from same engine version
3. Ensure snapshot is not encrypted with different KMS key

```bash
# Check snapshot status
aws rds describe-db-cluster-snapshots \
  --db-cluster-snapshot-identifier <snapshot-id> \
  --query 'DBClusterSnapshots[0].[Status,Engine,EngineVersion]'
```

### Issue: Performance Issues

**Symptoms**: Slow queries, high latency

**Solutions**:
1. Check Performance Insights for slow queries
2. Review CloudWatch metrics for resource constraints
3. Increase max_capacity if needed
4. Add database indexes

```bash
# Check for resource constraints
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBClusterIdentifier,Value=festival-playlist-dev-aurora-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Maximum
```

## Best Practices

### Development Environment

1. **Use Daily Teardown**: Save ~50% on costs
2. **Skip Final Snapshot**: Faster teardown (but keep for important work)
3. **Single Instance**: No need for Multi-AZ in dev
4. **Lower Max Capacity**: 2 ACU is usually enough for dev
5. **Clean Up Snapshots**: Keep only last 7 days

### Production Environment

1. **Enable Deletion Protection**: Prevent accidental deletion
2. **Multi-AZ Deployment**: 2+ instances for high availability
3. **Higher Max Capacity**: 4+ ACU for production workloads
4. **Longer Backup Retention**: 30 days recommended
5. **Enable Secret Rotation**: Automatic password rotation
6. **Monitor Alarms**: Set up SNS notifications

### Cost Optimization

1. **Monitor ACU Usage**: Adjust min/max capacity based on actual usage
2. **Use Spot Instances**: For non-critical workloads (not applicable to RDS)
3. **Clean Up Snapshots**: Automate cleanup with scripts
4. **Right-Size Capacity**: Start small, scale up as needed
5. **Daily Teardown**: For dev environments not in use

### Security

1. **Never Expose Publicly**: Keep in private subnets
2. **Use Secrets Manager**: Never hardcode credentials
3. **Enable Encryption**: Both at rest and in transit
4. **Rotate Passwords**: Regularly or automatically
5. **Audit Access**: Use CloudTrail to monitor access

## Quick Reference Commands

```bash
# List snapshots
./scripts/list-snapshots.sh festival-playlist-dev-aurora-cluster

# Clean up old snapshots
./scripts/cleanup-old-snapshots.sh festival-playlist-dev-aurora-cluster 7

# View logs
aws logs tail /aws/rds/cluster/festival-playlist-dev-aurora-cluster/postgresql --follow

# Check cluster status
aws rds describe-db-clusters --db-cluster-identifier festival-playlist-dev-aurora-cluster

# Get connection string
aws secretsmanager get-secret-value --secret-id festival-playlist-dev-db-credentials --query SecretString --output text | jq -r .url

# Test connection
psql "$(aws secretsmanager get-secret-value --secret-id festival-playlist-dev-db-credentials --query SecretString --output text | jq -r .url)" -c "SELECT version();"

# Terraform commands
terraform init
terraform plan
terraform apply
terraform destroy -target=module.database
```

## Additional Resources

- [Aurora Serverless v2 Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html)
- [RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [Performance Insights](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PerfInsights.html)
- [Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html)
