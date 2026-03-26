# Database Module - Aurora Serverless v2

This module creates an Amazon Aurora Serverless v2 PostgreSQL cluster with snapshot/restore capability for daily teardown/rebuild workflows.

## Features

- **Aurora Serverless v2**: Auto-scaling PostgreSQL cluster (0.5-4 ACU)
- **Snapshot/Restore**: Automated snapshot creation and restore capability
- **Encryption**: KMS encryption at rest with automatic key rotation
- **High Availability**: Multi-AZ support for production environments
- **Monitoring**: CloudWatch Logs, Performance Insights, Enhanced Monitoring
- **Backup**: Automated daily backups with configurable retention
- **Security**: Private subnet deployment with security group integration

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Aurora Serverless v2                      │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Aurora Cluster                                       │   │
│  │  - Engine: PostgreSQL 15.3                           │   │
│  │  - Scaling: 0.5-4 ACU                                │   │
│  │  - Encryption: KMS                                   │   │
│  │  - Backups: 7 days retention                         │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Aurora Instance(s)                                   │   │
│  │  - Class: db.serverless                              │   │
│  │  - Performance Insights: Enabled                     │   │
│  │  - Enhanced Monitoring: 60s interval                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### Basic Usage (Dev Environment)

```hcl
module "database" {
  source = "./modules/database"

  project_name           = "festival-playlist"
  environment            = "dev"
  private_subnet_ids     = module.networking.private_subnet_ids
  rds_security_group_id  = module.networking.rds_security_group_id

  # Serverless v2 scaling
  min_capacity = 0.5
  max_capacity = 2

  # Single instance for dev
  instance_count = 1

  # Skip final snapshot for dev (faster teardown)
  skip_final_snapshot = true

  common_tags = var.common_tags
}
```

### Production Usage (Multi-AZ)

```hcl
module "database" {
  source = "./modules/database"

  project_name           = "festival-playlist"
  environment            = "prod"
  private_subnet_ids     = module.networking.private_subnet_ids
  rds_security_group_id  = module.networking.rds_security_group_id

  # Serverless v2 scaling
  min_capacity = 0.5
  max_capacity = 4

  # Multi-AZ with 2 instances
  instance_count = 2

  # Production settings
  skip_final_snapshot = false
  deletion_protection = true
  apply_immediately   = false

  common_tags = var.common_tags
}
```

### Restore from Snapshot

```hcl
module "database" {
  source = "./modules/database"

  project_name           = "festival-playlist"
  environment            = "dev"
  private_subnet_ids     = module.networking.private_subnet_ids
  rds_security_group_id  = module.networking.rds_security_group_id

  # Restore from latest snapshot
  restore_from_snapshot = true

  # Or restore from specific snapshot
  # snapshot_identifier = "festival-playlist-dev-final-snapshot-2024-01-22-1430"

  common_tags = var.common_tags
}
```

## Snapshot and Restore Workflow

### Daily Teardown Workflow

1. **Before Destroy**: Terraform automatically creates a final snapshot
   - Snapshot name: `{project}-{env}-final-snapshot-{timestamp}`
   - Retention: Snapshots are retained even after cluster deletion
   - Cost: Free for first 7 days, then $0.095/GB/month

2. **Destroy**: Run `terraform destroy`
   - Cluster is deleted
   - Final snapshot is created automatically
   - Snapshot is preserved for restore

3. **Provision**: Run `terraform apply` with `restore_from_snapshot = true`
   - Finds latest snapshot automatically
   - Restores cluster from snapshot
   - Provision time: ~5-10 minutes

### Snapshot Management

**Automatic Snapshots:**
- Created before every `terraform destroy`
- Named with timestamp for easy identification
- Retained indefinitely (manual cleanup required)

**Finding Latest Snapshot:**
```bash
# List all snapshots for the cluster
aws rds describe-db-cluster-snapshots \
  --db-cluster-identifier festival-playlist-dev-aurora-cluster \
  --snapshot-type manual \
  --query 'DBClusterSnapshots[*].[DBClusterSnapshotIdentifier,SnapshotCreateTime]' \
  --output table
```

**Deleting Old Snapshots:**
```bash
# Delete snapshot by identifier
aws rds delete-db-cluster-snapshot \
  --db-cluster-snapshot-identifier festival-playlist-dev-final-snapshot-2024-01-15-1430
```

**List All Snapshots:**
```bash
# List all snapshots for the cluster
cd infrastructure/terraform
./scripts/list-snapshots.sh festival-playlist-dev-aurora-cluster
```

**Automated Cleanup Script:**
```bash
# Keep only last 7 days of snapshots
cd infrastructure/terraform
./scripts/cleanup-old-snapshots.sh festival-playlist-dev-aurora-cluster 7
```

The cleanup script will:
1. List all snapshots older than the specified number of days
2. Show the total size and estimated cost
3. Ask for confirmation before deleting
4. Delete snapshots one by one with progress feedback

## Variables

### Required Variables

| Name | Description | Type |
|------|-------------|------|
| `project_name` | Name of the project | `string` |
| `environment` | Environment name (dev, staging, prod) | `string` |
| `private_subnet_ids` | List of private subnet IDs for RDS | `list(string)` |
| `rds_security_group_id` | Security group ID for RDS | `string` |

### Optional Variables

| Name | Description | Type | Default |
|------|-------------|------|---------|
| `database_name` | Name of the default database | `string` | `"festival_playlist"` |
| `master_username` | Master username for the database | `string` | `"festival_admin"` |
| `engine_version` | Aurora PostgreSQL engine version | `string` | `"15.3"` |
| `min_capacity` | Minimum ACU capacity | `number` | `0.5` |
| `max_capacity` | Maximum ACU capacity | `number` | `4` |
| `instance_count` | Number of Aurora instances | `number` | `1` |
| `backup_retention_period` | Days to retain backups | `number` | `7` |
| `restore_from_snapshot` | Restore from latest snapshot | `bool` | `false` |
| `snapshot_identifier` | Specific snapshot to restore from | `string` | `null` |
| `skip_final_snapshot` | Skip final snapshot on destroy | `bool` | `false` |
| `deletion_protection` | Enable deletion protection | `bool` | `false` |
| `enable_performance_insights` | Enable Performance Insights | `bool` | `true` |
| `monitoring_interval` | Enhanced monitoring interval (seconds) | `number` | `60` |

## Outputs

| Name | Description | Sensitive |
|------|-------------|-----------|
| `cluster_id` | ID of the Aurora cluster | No |
| `cluster_endpoint` | Writer endpoint for the cluster | No |
| `cluster_reader_endpoint` | Reader endpoint for the cluster | No |
| `cluster_port` | Port of the cluster | No |
| `cluster_database_name` | Name of the default database | No |
| `cluster_master_username` | Master username | Yes |
| `cluster_master_password` | Master password | Yes |
| `connection_string` | PostgreSQL connection string | Yes |
| `kms_key_arn` | ARN of the KMS encryption key | No |

## Cost Optimization

### Dev Environment (with daily teardown)

**Active (8 hours/day, 5 days/week = ~173 hours/month):**
- Aurora Serverless v2 (0.5 ACU average): ~$2-3/month
- Storage (10 GB): ~$0.20/month
- Backup storage (7 days): Free
- **Subtotal: $2-3/month**

**Torn Down (~557 hours/month):**
- Snapshots (first 7 days): Free
- Snapshots (after 7 days, 10 GB): ~$1/month
- **Subtotal: $0-1/month**

**Total: $2-4/month**

### Production Environment (24/7)

**Always Running:**
- Aurora Serverless v2 (0.5-1 ACU average): ~$15-25/month
- Storage (50 GB): ~$1/month
- Backup storage: ~$1/month
- Multi-AZ (2 instances): 2x cost
- **Total: $30-50/month**

## Monitoring

### CloudWatch Logs

PostgreSQL logs are exported to CloudWatch Logs:
- Log group: `/aws/rds/cluster/{cluster-id}/postgresql`
- Retention: 7 days (dev), 30 days (prod)
- Query logs for errors, slow queries, connections

### Performance Insights

- Enabled by default
- Retention: 7 days (free tier)
- Metrics: CPU, memory, I/O, connections
- Query performance analysis

### Enhanced Monitoring

- Interval: 60 seconds
- OS-level metrics: CPU, memory, disk I/O, network
- CloudWatch Logs: `/aws/rds/instance/{instance-id}/enhanced-monitoring`

### CloudWatch Alarms

Create alarms for critical metrics:
```hcl
# CPU utilization alarm
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${var.project_name}-${var.environment}-rds-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "RDS CPU utilization is too high"

  dimensions = {
    DBClusterIdentifier = module.database.cluster_id
  }
}
```

## Security

### Encryption

- **At Rest**: KMS encryption with automatic key rotation
- **In Transit**: SSL/TLS required for all connections
- **Key Management**: Dedicated KMS key per environment

### Network Security

- **Private Subnets**: Database instances in private subnets only
- **Security Groups**: Only ECS tasks can connect (port 5432)
- **No Public Access**: Database is not accessible from internet

### Access Control

- **Master Credentials**: Stored in AWS Secrets Manager
- **IAM Authentication**: Supported (optional)
- **Password Rotation**: Automatic rotation via Secrets Manager (optional)

## Troubleshooting

### Cluster Won't Start

**Issue**: Cluster stuck in "creating" state
**Solution**: Check CloudWatch Logs for errors, verify subnet group and security group

### Snapshot Restore Fails

**Issue**: Restore from snapshot fails
**Solution**:
- Verify snapshot exists and is available
- Check snapshot is from same engine version
- Ensure sufficient capacity in target region

### Connection Timeout

**Issue**: Cannot connect to database
**Solution**:
- Verify security group allows traffic from ECS tasks
- Check database is in "available" state
- Verify connection string is correct

### High Costs

**Issue**: Database costs higher than expected
**Solution**:
- Check ACU usage in CloudWatch metrics
- Reduce max_capacity if not needed
- Enable auto-pause for dev (not supported in Serverless v2)
- Consider daily teardown for dev environments

## References

- [Aurora Serverless v2 Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html)
- [Aurora PostgreSQL Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.AuroraPostgreSQL.html)
- [RDS Snapshots Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_CreateSnapshot.html)
- [Performance Insights Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PerfInsights.html)
