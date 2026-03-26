# Quick Start Guide - Teardown & Provision Scripts

## TL;DR

```bash
# End of day - save costs
./scripts/teardown.sh

# Start of day - restore environment
./scripts/provision.sh

# Check costs anytime
./scripts/cost-report.sh
```

## Prerequisites

1. **AWS CLI** installed and configured
   ```bash
   aws configure --profile festival-playlist
   ```

2. **Terraform** installed (v1.10+)
   ```bash
   terraform version
   ```

3. **Backend initialized**
   ```bash
   ./scripts/init-backend.sh
   ```

## Daily Workflow

### Morning (9 AM) - Start Work

```bash
cd infrastructure/terraform
./scripts/provision.sh
```

**What happens**:
- Finds latest database snapshot
- Provisions AWS infrastructure
- Restores database from snapshot
- Waits for services to be healthy
- Shows API URLs

**Time**: ~12-18 minutes

**Output**:
```
API URL: http://festival-dev-alb-123456789.eu-west-2.elb.amazonaws.com
Health Check: http://festival-dev-alb-123456789.eu-west-2.elb.amazonaws.com/health
```

### Evening (6 PM) - End Work

```bash
cd infrastructure/terraform
./scripts/teardown.sh
```

**What happens**:
- Creates database snapshot
- Waits for snapshot completion
- Destroys infrastructure
- Cleans up old snapshots
- Shows cost summary

**Time**: ~8-12 minutes

**Cost Impact**: Reduces from $49-79/month to $2-5/month

### Weekly - Check Costs

```bash
cd infrastructure/terraform
./scripts/cost-report.sh
```

**What you see**:
- Month-to-date costs
- Cost by service (RDS, ECS, ALB, etc.)
- Daily cost breakdown
- Monthly projection
- Budget comparison
- Optimization tips

## Common Scenarios

### First Time Setup

```bash
# 1. Initialize backend
./scripts/init-backend.sh

# 2. Provision infrastructure (no snapshot exists yet)
./scripts/provision.sh

# 3. Deploy application (separate step)
# ... deploy your app ...

# 4. At end of day, teardown
./scripts/teardown.sh
```

### Daily Use

```bash
# Morning
./scripts/provision.sh

# Work on your project...

# Evening
./scripts/teardown.sh
```

### Cost Monitoring

```bash
# Quick cost check
./scripts/cost-report.sh

# Check last 60 days
DAYS_BACK=60 ./scripts/cost-report.sh
```

### Different Environments

```bash
# Staging environment
ENVIRONMENT=staging ./scripts/provision.sh
ENVIRONMENT=staging ./scripts/teardown.sh
ENVIRONMENT=staging ./scripts/cost-report.sh

# Production (be careful!)
ENVIRONMENT=prod ./scripts/provision.sh
```

## Troubleshooting

### Provision Failed

**Problem**: Terraform apply failed

**Solution**:
```bash
# Check Terraform state
cd infrastructure/terraform
terraform state list

# Try manual apply
terraform apply

# Check AWS console for errors
```

### Teardown Failed

**Problem**: Snapshot creation failed

**Solution**:
```bash
# Check RDS cluster exists
aws rds describe-db-clusters --profile festival-playlist

# Try manual snapshot
aws rds create-db-cluster-snapshot \
  --db-cluster-identifier festival-dev-aurora-cluster \
  --db-cluster-snapshot-identifier manual-snapshot-$(date +%Y%m%d)

# Then run teardown again
./scripts/teardown.sh
```

### Health Check Failed

**Problem**: API not responding after provision

**Solution**:
```bash
# Check ECS tasks
aws ecs list-tasks --cluster festival-dev-ecs-cluster

# Check task logs
aws logs tail /ecs/festival-api --follow

# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn <your-target-group-arn>

# Wait a few more minutes - services may still be starting
```

### Cost Report Shows No Data

**Problem**: Cost Explorer returns no data

**Solution**:
1. Enable Cost Explorer in AWS Console
2. Wait 24-48 hours for data to populate
3. Ensure resources are tagged with `Environment` tag
4. Check IAM permissions for Cost Explorer

## Cost Savings

### Comparison

| Scenario | Monthly Cost | Savings |
|----------|-------------|---------|
| Running 24/7 | $49-79 | - |
| Daily teardown (8hrs/day, 5 days/week) | $10-15 | $39-64 (80%) |
| Weekend teardown only | $30-40 | $19-39 (40%) |

### Breakdown

**When Active** ($8-10/month for 8hrs/day, 5 days/week):
- Aurora Serverless v2: $2-3
- ECS Fargate: $3-4
- ALB: $2
- ElastiCache: $1

**When Torn Down** ($2-5/month):
- S3 storage: $1-2
- Secrets Manager: $1-2
- RDS snapshots: $0-1

## Tips

### Maximize Savings

1. **Use daily teardown** - Save 80% on costs
2. **Teardown on weekends** - Even more savings
3. **Monitor costs weekly** - Catch anomalies early
4. **Use Fargate Spot for workers** - Already configured
5. **Enable Aurora auto-pause** - Already configured

### Automation

Set up GitHub Actions for automatic teardown/provision:

```yaml
# .github/workflows/scheduled-teardown.yml
schedule:
  - cron: '0 23 * * 1-5'  # 6 PM EST weekdays

# .github/workflows/scheduled-provision.yml
schedule:
  - cron: '0 14 * * 1-5'  # 9 AM EST weekdays
```

See Week 4 tasks for full CI/CD setup.

### Best Practices

1. **Always teardown at end of day** - Don't forget!
2. **Check costs weekly** - Stay within budget
3. **Keep snapshots for 7 days** - Balance cost and recovery
4. **Test provision regularly** - Ensure snapshots work
5. **Monitor health checks** - Catch issues early

## Environment Variables

### Common Variables

```bash
export PROJECT_NAME=festival-playlist
export ENVIRONMENT=dev
export AWS_PROFILE=festival-playlist
export AWS_REGION=eu-west-2
```

### Script-Specific Variables

**teardown.sh**:
```bash
export SNAPSHOT_RETENTION_DAYS=7  # Keep snapshots for 7 days
```

**provision.sh**:
```bash
export MAX_HEALTH_CHECK_WAIT=600  # Wait up to 10 minutes for health checks
```

**cost-report.sh**:
```bash
export DAYS_BACK=30  # Show last 30 days of costs
```

## Getting Help

1. **Check script output** - Detailed error messages
2. **Read README.md** - Comprehensive documentation
3. **Check AWS Console** - Verify resource states
4. **Review Terraform logs** - Detailed error information
5. **Check CloudWatch logs** - Application errors

## Next Steps

After mastering these scripts:

1. **Week 3**: Deploy application to ECS
2. **Week 4**: Set up CI/CD automation
3. **Production**: Create prod environment
4. **Monitoring**: Set up alerts and dashboards

## Quick Reference

| Command | Purpose | Time |
|---------|---------|------|
| `./scripts/provision.sh` | Start environment | 12-18 min |
| `./scripts/teardown.sh` | Stop environment | 8-12 min |
| `./scripts/cost-report.sh` | Check costs | 1-2 min |
| `./scripts/init-backend.sh` | Setup backend | 1-2 min |
| `./scripts/list-snapshots.sh` | List snapshots | < 1 min |
| `./scripts/cleanup-old-snapshots.sh` | Clean snapshots | 1-2 min |

## Support

For detailed documentation, see:
- **README.md** - Full documentation
- **IMPLEMENTATION_SUMMARY.md** - Technical details
- **Main project README** - Overall architecture

---

**Remember**: Daily teardown saves ~$40/month! 💰
