# Example Terraform variables for Development Environment
# This file demonstrates how to configure the cache module for a dev environment

project_name = "festival-playlist"
environment  = "dev"

# Network Configuration (from networking module outputs)
# private_subnet_ids     = ["subnet-abc123", "subnet-def456"]
# redis_security_group_id = "sg-xyz789"

# Redis Configuration - Single Node for Dev
node_type       = "cache.t4g.micro"
num_cache_nodes = 1
engine_version  = "7.0"

# High Availability - Disabled for Dev
automatic_failover_enabled = false
multi_az_enabled           = false

# Backup Configuration - Minimal for Dev
snapshot_retention_limit = 1
snapshot_window          = "03:00-04:00"
maintenance_window       = "sun:04:00-sun:05:00"
skip_final_snapshot      = true

# Encryption - At Rest Only for Dev
at_rest_encryption_enabled = true
transit_encryption_enabled = false
auth_token_enabled         = false

# Operational Settings
auto_minor_version_upgrade = true
apply_immediately          = true

# CloudWatch Logs
log_retention_days = 7

# CloudWatch Alarms
enable_cloudwatch_alarms = true
alarm_email_addresses    = ["dev@example.com"]

# Alarm Thresholds
cpu_alarm_threshold             = 75
memory_alarm_threshold          = 90
evictions_alarm_threshold       = 1000
connections_alarm_threshold     = 65000
replication_lag_alarm_threshold = 30

# Common Tags
common_tags = {
  Project     = "festival-playlist"
  Environment = "dev"
  ManagedBy   = "terraform"
  CostCenter  = "engineering"
  Owner       = "platform-team"
}
