# Example Terraform variables for Production Environment
# This file demonstrates how to configure the cache module for a prod environment

project_name = "festival-playlist"
environment  = "prod"

# Network Configuration (from networking module outputs)
# private_subnet_ids     = ["subnet-abc123", "subnet-def456"]
# redis_security_group_id = "sg-xyz789"

# Redis Configuration - Multi-Node for Prod
node_type       = "cache.t4g.small"
num_cache_nodes = 2
engine_version  = "7.0"

# High Availability - Enabled for Prod
automatic_failover_enabled = true
multi_az_enabled           = true

# Backup Configuration - Extended for Prod
snapshot_retention_limit = 7
snapshot_window          = "03:00-04:00"
maintenance_window       = "sun:04:00-sun:05:00"
skip_final_snapshot      = false

# Encryption - Full Encryption for Prod
at_rest_encryption_enabled = true
transit_encryption_enabled = true
auth_token_enabled         = true

# Operational Settings
auto_minor_version_upgrade = true
apply_immediately          = false  # Apply during maintenance window

# CloudWatch Logs
log_retention_days = 30

# CloudWatch Alarms
enable_cloudwatch_alarms = true
# alarm_sns_topic_arn = "arn:aws:sns:us-east-1:123456789012:prod-alarms"

# Alarm Thresholds (more conservative for prod)
cpu_alarm_threshold              = 70
memory_alarm_threshold           = 85
evictions_alarm_threshold        = 500
connections_alarm_threshold      = 60000
replication_lag_alarm_threshold  = 15

# Common Tags
common_tags = {
  Project     = "festival-playlist"
  Environment = "prod"
  ManagedBy   = "terraform"
  CostCenter  = "engineering"
  Owner       = "platform-team"
  Compliance  = "required"
  Backup      = "daily"
}
