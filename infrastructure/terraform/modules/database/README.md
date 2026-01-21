# Database Module

This module manages Aurora Serverless v2 PostgreSQL cluster for the Festival Playlist Generator.

## Resources Created

- Aurora Serverless v2 PostgreSQL cluster
- RDS subnet group
- Database credentials in Secrets Manager
- CloudWatch log groups for PostgreSQL logs
- CloudWatch alarms for monitoring

## Features

- Auto-scaling: 0.5-4 ACU
- Auto-pause in dev environment (5 min timeout)
- Automated backups (7-day retention)
- Encryption at rest with KMS
- Snapshot and restore capability
- Performance Insights enabled

## Usage

```hcl
module "database" {
  source = "./modules/database"
  
  project_name         = var.project_name
  environment          = var.environment
  vpc_id               = module.networking.vpc_id
  private_subnet_ids   = module.networking.private_subnet_ids
  security_group_id    = module.networking.rds_security_group_id
  snapshot_identifier  = var.db_snapshot_identifier
  common_tags          = var.common_tags
}
```

## Outputs

- cluster_endpoint
- cluster_reader_endpoint
- cluster_id
- database_name
- secret_arn
