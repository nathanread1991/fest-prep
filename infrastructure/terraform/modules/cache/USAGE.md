# Cache Module Usage Guide

This guide provides practical examples and best practices for using the ElastiCache Redis cache module.

## Quick Start

### 1. Development Environment (Single Node)

```hcl
module "cache" {
  source = "./modules/cache"

  project_name           = "festival-playlist"
  environment            = "dev"
  private_subnet_ids     = module.networking.private_subnet_ids
  redis_security_group_id = module.networking.redis_security_group_id

  # Single node for dev
  node_type       = "cache.t4g.micro"
  num_cache_nodes = 1

  # Minimal configuration
  snapshot_retention_limit = 1
  skip_final_snapshot      = true
  apply_immediately        = true

  # No encryption for dev (simpler)
  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = false
  auth_token_enabled          = false

  # Alarms
  enable_cloudwatch_alarms = true
  alarm_email_addresses    = ["dev@example.com"]

  common_tags = {
    Project     = "festival-playlist"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

**Cost**: ~$12/month

### 2. Production Environment (Multi-Node with HA)

```hcl
module "cache" {
  source = "./modules/cache"

  project_name           = "festival-playlist"
  environment            = "prod"
  private_subnet_ids     = module.networking.private_subnet_ids
  redis_security_group_id = module.networking.redis_security_group_id

  # Multi-node for high availability
  node_type       = "cache.t4g.small"
  num_cache_nodes = 2

  # High availability
  automatic_failover_enabled = true
  multi_az_enabled           = true

  # Extended backups
  snapshot_retention_limit = 7
  skip_final_snapshot      = false
  apply_immediately        = false

  # Full encryption
  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = true
  auth_token_enabled          = true

  # Alarms
  enable_cloudwatch_alarms = true
  alarm_sns_topic_arn      = aws_sns_topic.prod_alarms.arn

  common_tags = {
    Project     = "festival-playlist"
    Environment = "prod"
    ManagedBy   = "terraform"
  }
}
```

**Cost**: ~$50-60/month

## Accessing Redis Connection Details

### From Terraform Outputs

```hcl
# Get connection details from module outputs
output "redis_endpoint" {
  value = module.cache.primary_endpoint_address
}

output "redis_port" {
  value = module.cache.port
}

output "redis_secret_arn" {
  value = module.cache.secret_arn
}
```

### From Secrets Manager (Python)

```python
import boto3
import json

def get_redis_config(environment: str) -> dict:
    """Load Redis configuration from Secrets Manager."""
    secrets_client = boto3.client('secretsmanager')
    secret_name = f"festival-playlist-{environment}-redis-url"

    response = secrets_client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage
redis_config = get_redis_config('dev')
print(f"Redis host: {redis_config['host']}")
print(f"Redis port: {redis_config['port']}")
print(f"Redis URL: {redis_config['url']}")
```

### From Secrets Manager (AWS CLI)

```bash
# Get Redis connection details
aws secretsmanager get-secret-value \
  --secret-id festival-playlist-dev-redis-url \
  --query SecretString \
  --output text | jq .

# Output:
# {
#   "host": "festival-dev-redis.abc123.ng.0001.use1.cache.amazonaws.com",
#   "port": 6379,
#   "url": "redis://festival-dev-redis.abc123.ng.0001.use1.cache.amazonaws.com:6379",
#   "ssl": false,
#   "password": null
# }
```

## Application Integration

### Python with redis-py

```python
import boto3
import json
import redis
from typing import Optional

class RedisClient:
    """Redis client with Secrets Manager integration."""

    def __init__(self, environment: str):
        self.environment = environment
        self._client: Optional[redis.Redis] = None

    def _load_config(self) -> dict:
        """Load Redis configuration from Secrets Manager."""
        secrets_client = boto3.client('secretsmanager')
        secret_name = f"festival-playlist-{self.environment}-redis-url"

        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])

    def connect(self) -> redis.Redis:
        """Connect to Redis using Secrets Manager configuration."""
        if self._client is None:
            config = self._load_config()

            self._client = redis.Redis(
                host=config['host'],
                port=config['port'],
                password=config.get('password'),
                ssl=config['ssl'],
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # Test connection
            self._client.ping()

        return self._client

    def close(self):
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None

# Usage
redis_client = RedisClient('dev')
redis = redis_client.connect()

# Set a value
redis.set('key', 'value', ex=3600)  # 1 hour TTL

# Get a value
value = redis.get('key')

# Close connection
redis_client.close()
```

### Python with aioredis (Async)

```python
import boto3
import json
import aioredis
from typing import Optional

class AsyncRedisClient:
    """Async Redis client with Secrets Manager integration."""

    def __init__(self, environment: str):
        self.environment = environment
        self._pool: Optional[aioredis.Redis] = None

    def _load_config(self) -> dict:
        """Load Redis configuration from Secrets Manager."""
        secrets_client = boto3.client('secretsmanager')
        secret_name = f"festival-playlist-{self.environment}-redis-url"

        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])

    async def connect(self) -> aioredis.Redis:
        """Connect to Redis using Secrets Manager configuration."""
        if self._pool is None:
            config = self._load_config()

            self._pool = await aioredis.create_redis_pool(
                config['url'],
                encoding='utf-8',
                minsize=5,
                maxsize=10
            )

            # Test connection
            await self._pool.ping()

        return self._pool

    async def close(self):
        """Close Redis connection pool."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

# Usage
async def main():
    redis_client = AsyncRedisClient('dev')
    redis = await redis_client.connect()

    # Set a value
    await redis.set('key', 'value', expire=3600)

    # Get a value
    value = await redis.get('key')

    # Close connection
    await redis_client.close()
```

### FastAPI Dependency Injection

```python
from fastapi import Depends, FastAPI
import redis
from functools import lru_cache

app = FastAPI()

@lru_cache()
def get_redis_client() -> redis.Redis:
    """Get Redis client (cached)."""
    redis_client = RedisClient('dev')
    return redis_client.connect()

@app.get("/cache/{key}")
async def get_cached_value(
    key: str,
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """Get value from cache."""
    value = redis_client.get(key)
    if value is None:
        return {"error": "Key not found"}
    return {"key": key, "value": value}

@app.post("/cache/{key}")
async def set_cached_value(
    key: str,
    value: str,
    ttl: int = 3600,
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """Set value in cache."""
    redis_client.set(key, value, ex=ttl)
    return {"key": key, "value": value, "ttl": ttl}
```

## Common Operations

### Caching Pattern

```python
import json
from typing import Optional, Any
from functools import wraps

def cache_result(key_prefix: str, ttl: int = 3600):
    """Decorator to cache function results in Redis."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            redis_client = get_redis_client()

            # Generate cache key
            cache_key = f"{key_prefix}:{args}:{kwargs}"

            # Try to get from cache
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Call function
            result = await func(*args, **kwargs)

            # Store in cache
            redis_client.set(cache_key, json.dumps(result), ex=ttl)

            return result
        return wrapper
    return decorator

# Usage
@cache_result("festival", ttl=3600)
async def get_festival_by_id(festival_id: int):
    """Get festival by ID (cached for 1 hour)."""
    # Fetch from database
    return await db.fetch_festival(festival_id)
```

### Cache Invalidation

```python
def invalidate_cache(pattern: str):
    """Invalidate all cache keys matching pattern."""
    redis_client = get_redis_client()

    # Find all keys matching pattern
    keys = redis_client.keys(pattern)

    # Delete keys
    if keys:
        redis_client.delete(*keys)

    return len(keys)

# Usage
# Invalidate all festival caches
invalidate_cache("festival:*")

# Invalidate specific festival cache
invalidate_cache("festival:123:*")
```

### Session Management

```python
import uuid
from datetime import timedelta

class SessionManager:
    """Redis-based session manager."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.session_prefix = "session:"
        self.default_ttl = 3600  # 1 hour

    def create_session(self, user_id: int, data: dict) -> str:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        session_key = f"{self.session_prefix}{session_id}"

        session_data = {
            "user_id": user_id,
            **data
        }

        self.redis.set(
            session_key,
            json.dumps(session_data),
            ex=self.default_ttl
        )

        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session data."""
        session_key = f"{self.session_prefix}{session_id}"
        data = self.redis.get(session_key)

        if data:
            return json.loads(data)
        return None

    def delete_session(self, session_id: str):
        """Delete session."""
        session_key = f"{self.session_prefix}{session_id}"
        self.redis.delete(session_key)

    def refresh_session(self, session_id: str):
        """Refresh session TTL."""
        session_key = f"{self.session_prefix}{session_id}"
        self.redis.expire(session_key, self.default_ttl)

# Usage
session_manager = SessionManager(get_redis_client())

# Create session
session_id = session_manager.create_session(
    user_id=123,
    data={"username": "john", "role": "admin"}
)

# Get session
session_data = session_manager.get_session(session_id)

# Refresh session
session_manager.refresh_session(session_id)

# Delete session
session_manager.delete_session(session_id)
```

## Monitoring and Troubleshooting

### Check Redis Health

```bash
# Check if Redis is accessible
aws elasticache describe-replication-groups \
  --replication-group-id festival-dev-redis \
  --query 'ReplicationGroups[0].Status'

# Check node status
aws elasticache describe-cache-clusters \
  --cache-cluster-id festival-dev-redis-001 \
  --show-cache-node-info
```

### View CloudWatch Metrics

```bash
# Get CPU utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ElastiCache \
  --metric-name CPUUtilization \
  --dimensions Name=ReplicationGroupId,Value=festival-dev-redis \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T23:59:59Z \
  --period 3600 \
  --statistics Average

# Get memory utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ElastiCache \
  --metric-name DatabaseMemoryUsagePercentage \
  --dimensions Name=ReplicationGroupId,Value=festival-dev-redis \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T23:59:59Z \
  --period 3600 \
  --statistics Average
```

### View CloudWatch Logs

```bash
# View slow logs
aws logs tail /aws/elasticache/festival-dev/redis/slow-log --follow

# View engine logs
aws logs tail /aws/elasticache/festival-dev/redis/engine-log --follow
```

### Test Connection from ECS Task

```bash
# Connect to ECS task
aws ecs execute-command \
  --cluster festival-dev-cluster \
  --task <task-id> \
  --container api \
  --interactive \
  --command "/bin/bash"

# Inside container, test Redis connection
redis-cli -h festival-dev-redis.abc123.ng.0001.use1.cache.amazonaws.com -p 6379 ping
# Expected: PONG
```

## Performance Optimization

### Connection Pooling

```python
import redis
from redis.connection import ConnectionPool

# Create connection pool
pool = ConnectionPool(
    host='redis-host',
    port=6379,
    max_connections=50,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True
)

# Use pool for all connections
redis_client = redis.Redis(connection_pool=pool)
```

### Pipeline for Bulk Operations

```python
# Use pipeline for multiple operations
pipe = redis_client.pipeline()

for i in range(1000):
    pipe.set(f"key:{i}", f"value:{i}")

# Execute all at once
pipe.execute()
```

### Lua Scripts for Atomic Operations

```python
# Lua script for atomic increment with max value
lua_script = """
local current = redis.call('GET', KEYS[1])
if current and tonumber(current) >= tonumber(ARGV[1]) then
    return current
end
return redis.call('INCR', KEYS[1])
"""

# Register script
increment_with_max = redis_client.register_script(lua_script)

# Execute script
result = increment_with_max(keys=['counter'], args=[100])
```

## Cost Optimization Tips

1. **Use Graviton2 instances** (t4g family) - 20% cheaper than t3
2. **Single node for dev** - No replication overhead
3. **Adjust snapshot retention** - Minimum needed for your use case
4. **Monitor evictions** - If high, consider upgrading node type
5. **Use appropriate TTLs** - Don't cache data longer than needed
6. **Implement cache warming** - Reduce cache misses during startup

## Security Best Practices

1. **Use private subnets** - No public access to Redis
2. **Restrict security groups** - Only allow ECS tasks
3. **Enable encryption at rest** - Protect data on disk
4. **Enable encryption in transit** - Protect data in flight (prod)
5. **Use AUTH tokens** - Add authentication layer (prod)
6. **Rotate AUTH tokens** - Regular rotation for security
7. **Monitor access patterns** - CloudWatch Logs and metrics

## Backup and Recovery

### Manual Snapshot

```bash
# Create manual snapshot
aws elasticache create-snapshot \
  --replication-group-id festival-dev-redis \
  --snapshot-name festival-dev-redis-manual-$(date +%Y%m%d-%H%M%S)
```

### Restore from Snapshot

```bash
# List available snapshots
aws elasticache describe-snapshots \
  --replication-group-id festival-dev-redis

# Restore from snapshot (requires new cluster)
aws elasticache create-replication-group \
  --replication-group-id festival-dev-redis-restored \
  --snapshot-name festival-dev-redis-manual-20240101-120000 \
  --cache-node-type cache.t4g.micro
```

## References

- [AWS ElastiCache for Redis Documentation](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/)
- [Redis Documentation](https://redis.io/documentation)
- [redis-py Documentation](https://redis-py.readthedocs.io/)
- [aioredis Documentation](https://aioredis.readthedocs.io/)
