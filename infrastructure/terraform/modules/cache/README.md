# Cache Module - ElastiCache Redis

This Terraform module creates an AWS ElastiCache Redis cluster for caching and session management. The module supports single-node (dev) and multi-node (prod) configurations with automatic failover, encryption, monitoring, and CloudWatch alarms.

## Features

- **ElastiCache Redis 7.0** with configurable node types
- **Single-node (dev)** or **Multi-node with automatic failover (prod)**
- **Encryption at rest** and **in transit (TLS)** support
- **AUTH token** for secure authentication
- **Automatic backups** with configurable retention
- **CloudWatch Logs** for slow logs and engine logs
- **CloudWatch Alarms** for CPU, memory, evictions, connections, and replication lag
- **Secrets Manager integration** for connection URL storage
- **Parameter group** with `maxmemory-policy` set to `allkeys-lru`
- **Cost-optimized** with Graviton2 instances (t4g family)

## Usage

### Basic Usage (Development - Single Node)

```hcl
module "cache" {
  source = "./modules/cache"

  project_name           = "festival-playlist"
  environment            = "dev"
  private_subnet_ids     = module.networking.private_subnet_ids
  redis_security_group_id = module.networking.redis_security_group_id

  # Single node configuration for dev
  node_type       = "cache.t4g.micro"
  num_cache_nodes = 1

  # Disable high availability for dev
  automatic_failover_enabled = false
  multi_az_enabled           = false

  # Minimal backups for dev
  snapshot_retention_limit = 1
  skip_final_snapshot      = true

  # No encryption for dev (simpler, faster)
  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = false
  auth_token_enabled          = false

  # Apply changes immediately
  apply_immediately = true

  # CloudWatch alarms
  enable_cloudwatch_alarms = true
  alarm_email_addresses    = ["dev@example.com"]

  common_tags = {
    Project     = "festival-playlist"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

### Production Usage (Multi-Node with High Availability)

```hcl
module "cache" {
  source = "./modules/cache"

  project_name           = "festival-playlist"
  environment            = "prod"
  private_subnet_ids     = module.networking.private_subnet_ids
  redis_security_group_id = module.networking.redis_security_group_id

  # Multi-node configuration for prod
  node_type       = "cache.t4g.small"
  num_cache_nodes = 2

  # Enable high availability
  automatic_failover_enabled = true
  multi_az_enabled           = true

  # Extended backups for prod
  snapshot_retention_limit = 7
  skip_final_snapshot      = false

  # Enable encryption for prod
  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = true
  auth_token_enabled          = true

  # Apply changes during maintenance window
  apply_immediately = false

  # CloudWatch alarms
  enable_cloudwatch_alarms = true
  alarm_sns_topic_arn      = aws_sns_topic.prod_alarms.arn

  common_tags = {
    Project     = "festival-playlist"
    Environment = "prod"
    ManagedBy   = "terraform"
  }
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5 |
| aws | >= 5.0 |
| random | >= 3.5 |

## Providers

| Name | Version |
|------|---------|
| aws | >= 5.0 |
| random | >= 3.5 |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project | `string` | n/a | yes |
| environment | Environment name (dev, staging, prod) | `string` | n/a | yes |
| private_subnet_ids | List of private subnet IDs for ElastiCache | `list(string)` | n/a | yes |
| redis_security_group_id | Security group ID for Redis | `string` | n/a | yes |
| common_tags | Common tags to apply to all resources | `map(string)` | `{}` | no |
| engine_version | Redis engine version | `string` | `"7.0"` | no |
| node_type | ElastiCache node type | `string` | `"cache.t4g.micro"` | no |
| num_cache_nodes | Number of cache nodes | `number` | `1` | no |
| automatic_failover_enabled | Enable automatic failover | `bool` | `false` | no |
| multi_az_enabled | Enable Multi-AZ | `bool` | `false` | no |
| snapshot_retention_limit | Number of days to retain snapshots | `number` | `1` | no |
| snapshot_window | Daily time range for snapshots (UTC) | `string` | `"03:00-04:00"` | no |
| maintenance_window | Weekly maintenance window (UTC) | `string` | `"sun:04:00-sun:05:00"` | no |
| skip_final_snapshot | Skip final snapshot on destroy | `bool` | `false` | no |
| at_rest_encryption_enabled | Enable encryption at rest | `bool` | `true` | no |
| transit_encryption_enabled | Enable encryption in transit (TLS) | `bool` | `false` | no |
| auth_token_enabled | Enable AUTH token | `bool` | `false` | no |
| auto_minor_version_upgrade | Enable automatic minor version upgrades | `bool` | `true` | no |
| apply_immediately | Apply changes immediately | `bool` | `true` | no |
| notification_topic_arn | ARN of SNS topic for notifications | `string` | `null` | no |
| log_retention_days | CloudWatch Logs retention period | `number` | `7` | no |
| enable_cloudwatch_alarms | Enable CloudWatch alarms | `bool` | `true` | no |
| alarm_sns_topic_arn | ARN of SNS topic for alarms | `string` | `null` | no |
| alarm_email_addresses | Email addresses for alarm notifications | `list(string)` | `[]` | no |
| cpu_alarm_threshold | CPU utilization threshold (%) | `number` | `75` | no |
| memory_alarm_threshold | Memory utilization threshold (%) | `number` | `90` | no |
| evictions_alarm_threshold | Evictions threshold (count per 5 min) | `number` | `1000` | no |
| connections_alarm_threshold | Connections threshold | `number` | `65000` | no |
| replication_lag_alarm_threshold | Replication lag threshold (seconds) | `number` | `30` | no |

## Outputs

| Name | Description |
|------|-------------|
| replication_group_id | ID of the ElastiCache replication group |
| replication_group_arn | ARN of the ElastiCache replication group |
| primary_endpoint_address | Primary endpoint address for Redis |
| reader_endpoint_address | Reader endpoint address (if multi-node) |
| port | Port number for Redis |
| member_clusters | List of member cluster IDs |
| connection_string | Redis connection string (sensitive) |
| auth_token | Redis AUTH token (sensitive) |
| subnet_group_name | Name of the ElastiCache subnet group |
| parameter_group_name | Name of the ElastiCache parameter group |
| slow_log_group_name | CloudWatch log group for slow logs |
| engine_log_group_name | CloudWatch log group for engine logs |
| secret_arn | ARN of Secrets Manager secret |
| secret_id | ID of Secrets Manager secret |
| secret_name | Name of Secrets Manager secret |
| alarm_sns_topic_arn | ARN of SNS topic for alarms |
| cpu_alarm_arn | ARN of CPU alarm |
| memory_alarm_arn | ARN of memory alarm |
| evictions_alarm_arn | ARN of evictions alarm |
| connections_alarm_arn | ARN of connections alarm |
| replication_lag_alarm_arn | ARN of replication lag alarm |

## Architecture

### Network Configuration

- **Subnet Group**: Uses private subnets (no public access)
- **Security Group**: Accepts connections only from ECS tasks security group
- **Port**: 6379 (default Redis port)

### High Availability (Production)

- **Multi-AZ**: Nodes distributed across multiple availability zones
- **Automatic Failover**: Automatic promotion of replica to primary on failure
- **Read Replicas**: Reader endpoint for read-heavy workloads

### Security

- **Encryption at Rest**: Data encrypted using AWS-managed keys
- **Encryption in Transit**: TLS encryption for all connections (optional)
- **AUTH Token**: Password-based authentication (optional, requires TLS)
- **Network Isolation**: Private subnets with security group restrictions
- **Secrets Manager**: Connection details stored securely

### Monitoring

- **CloudWatch Logs**: Slow logs and engine logs
- **CloudWatch Metrics**: CPU, memory, evictions, connections, replication lag
- **CloudWatch Alarms**: Automated alerts for critical metrics
- **SNS Notifications**: Email alerts for alarm triggers

### Backup and Recovery

- **Automatic Snapshots**: Daily snapshots with configurable retention
- **Final Snapshot**: Optional snapshot on cluster deletion
- **Point-in-Time Recovery**: Restore from any snapshot

## Parameter Group Configuration

The module creates a custom parameter group with the following settings:

- **maxmemory-policy**: `allkeys-lru` - Evict any key using LRU when memory is full
- **cluster-enabled**: `no` - Cluster mode disabled (can be changed for future scaling)
- **timeout**: `300` - Close idle connections after 5 minutes

## Cost Optimization

### Development Environment

- **Node Type**: `cache.t4g.micro` (~$12/month)
- **Single Node**: No replication overhead
- **Minimal Backups**: 1-day retention
- **No Encryption in Transit**: Simpler, faster
- **Estimated Cost**: ~$12/month

### Production Environment

- **Node Type**: `cache.t4g.small` (~$25/month per node)
- **Multi-Node**: 2 nodes for high availability (~$50/month)
- **Extended Backups**: 7-day retention
- **Full Encryption**: At rest and in transit
- **Estimated Cost**: ~$50-60/month

### Cost Savings Tips

1. Use **Graviton2 instances** (t4g family) - 20% cheaper than t3
2. Use **single node** for dev/staging environments
3. Set **snapshot_retention_limit** to minimum needed
4. Enable **auto_minor_version_upgrade** for free performance improvements
5. Monitor **evictions** - if high, consider upgrading node type

## CloudWatch Alarms

The module creates the following alarms:

1. **CPU Utilization**: Triggers when CPU > 75% (configurable)
2. **Memory Utilization**: Triggers when memory > 90% (configurable)
3. **Evictions**: Triggers when evictions > 1000 per 5 minutes (configurable)
4. **Connections**: Triggers when connections > 65000 (configurable)
5. **Replication Lag**: Triggers when lag > 30 seconds (multi-node only)

## Secrets Manager Integration

The module automatically stores Redis connection details in AWS Secrets Manager:

```json
{
  "host": "festival-dev-redis.abc123.ng.0001.use1.cache.amazonaws.com",
  "port": 6379,
  "url": "redis://festival-dev-redis.abc123.ng.0001.use1.cache.amazonaws.com:6379",
  "ssl": false,
  "password": null
}
```

For encrypted connections with AUTH token:

```json
{
  "host": "festival-prod-redis.abc123.ng.0001.use1.cache.amazonaws.com",
  "port": 6379,
  "url": "rediss://:<AUTH_TOKEN>@festival-prod-redis.abc123.ng.0001.use1.cache.amazonaws.com:6379",
  "ssl": true,
  "auth_token": "<AUTH_TOKEN>"
}
```

## Application Integration

### Python (redis-py)

```python
import boto3
import json
import redis

# Load connection details from Secrets Manager
secrets_client = boto3.client('secretsmanager')
secret = secrets_client.get_secret_value(SecretId='festival-dev-redis-url')
redis_config = json.loads(secret['SecretString'])

# Connect to Redis
redis_client = redis.Redis(
    host=redis_config['host'],
    port=redis_config['port'],
    password=redis_config.get('password'),
    ssl=redis_config['ssl'],
    decode_responses=True
)

# Test connection
redis_client.ping()
```

### Python (aioredis)

```python
import boto3
import json
import aioredis

# Load connection details from Secrets Manager
secrets_client = boto3.client('secretsmanager')
secret = secrets_client.get_secret_value(SecretId='festival-dev-redis-url')
redis_config = json.loads(secret['SecretString'])

# Connect to Redis
redis_client = await aioredis.create_redis_pool(
    redis_config['url'],
    encoding='utf-8'
)

# Test connection
await redis_client.ping()
```

## Maintenance

### Upgrading Redis Version

1. Update `engine_version` variable
2. Set `apply_immediately = false` for production
3. Run `terraform plan` to review changes
4. Run `terraform apply` during maintenance window

### Scaling Node Type

1. Update `node_type` variable
2. Set `apply_immediately = false` for production
3. Run `terraform plan` to review changes
4. Run `terraform apply` during maintenance window

### Adding Nodes (Single to Multi-AZ)

1. Update `num_cache_nodes = 2`
2. Set `automatic_failover_enabled = true`
3. Set `multi_az_enabled = true`
4. Run `terraform apply`

## Troubleshooting

### High Evictions

**Symptom**: CloudWatch alarm for evictions triggered frequently

**Solutions**:
1. Increase node type (more memory)
2. Review cache TTLs (reduce if too long)
3. Implement cache key expiration strategy
4. Consider using Redis cluster mode for horizontal scaling

### High CPU

**Symptom**: CloudWatch alarm for CPU triggered frequently

**Solutions**:
1. Increase node type (more CPU)
2. Review slow logs for expensive operations
3. Optimize application queries
4. Consider read replicas for read-heavy workloads

### Connection Timeouts

**Symptom**: Application cannot connect to Redis

**Solutions**:
1. Verify security group allows traffic from ECS tasks
2. Verify ECS tasks are in correct subnets
3. Check CloudWatch logs for connection errors
4. Verify AUTH token if encryption in transit is enabled

### Replication Lag

**Symptom**: CloudWatch alarm for replication lag triggered

**Solutions**:
1. Increase node type (more network bandwidth)
2. Reduce write load
3. Check for network issues between AZs
4. Review slow logs for expensive operations

## References

- [AWS ElastiCache for Redis Documentation](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/)
- [Redis Documentation](https://redis.io/documentation)
- [AWS ElastiCache Best Practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/BestPractices.html)
- [Redis Persistence](https://redis.io/topics/persistence)
- [Redis Security](https://redis.io/topics/security)

## License

This module is part of the Festival Playlist Generator project.
