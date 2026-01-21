# AWS Region Configuration

## Primary Region: eu-west-2 (London)

This project is configured to deploy to the **London (eu-west-2)** AWS region by default.

## Why London?

- **Geographic Proximity**: Closer to UK-based developer and primary user base
- **Lower Latency**: Better performance for UK and European users
- **Data Residency**: Keeps data within UK/EU for compliance preferences
- **Cost Competitive**: Similar pricing to us-east-1
- **Availability**: All required AWS services available in eu-west-2

## Region-Specific Considerations

### Services in eu-west-2 (Primary Region)

The following services will be deployed to **eu-west-2**:

- ✅ VPC and networking
- ✅ ECS Fargate (API and worker services)
- ✅ Aurora Serverless v2 (PostgreSQL)
- ✅ ElastiCache Redis
- ✅ Application Load Balancer (ALB)
- ✅ S3 buckets
- ✅ ECR container registry
- ✅ Secrets Manager
- ✅ CloudWatch Logs and Metrics
- ✅ SNS topics for alerts
- ✅ AWS Budgets
- ✅ Cost Anomaly Detection
- ✅ X-Ray tracing
- ✅ Route 53 (global service, but records point to eu-west-2 resources)

### Services in us-east-1 (Required by AWS)

Some AWS services have limitations that require us-east-1:

- ⚠️ **CloudWatch Billing Metrics**: AWS billing data is ONLY available in us-east-1
  - Impact: CloudWatch dashboard queries us-east-1 for billing metrics
  - Workaround: Dashboard deployed in eu-west-2 but queries us-east-1 for billing data
  
- ⚠️ **ACM Certificates for CloudFront**: CloudFront requires certificates in us-east-1
  - Impact: SSL certificate for CloudFront must be created in us-east-1
  - Workaround: Create separate ACM certificate in us-east-1 for CloudFront
  - Note: ALB certificate can be in eu-west-2

### Global Services (Region-Independent)

- 🌍 **CloudFront**: Global CDN, origin can be in any region (eu-west-2 ALB)
- 🌍 **Route 53**: Global DNS service
- 🌍 **IAM**: Global identity and access management
- 🌍 **AWS Organizations**: Global account management

## Configuration Files

All configuration files have been updated to use **eu-west-2** as the default:

### Terraform Configuration

**File**: `terraform/terraform.tfvars.example`
```hcl
aws_region = "eu-west-2"  # London region
```

### AWS CLI Configuration

**Command**:
```bash
aws configure --profile festival-playlist
# Default region name: eu-west-2
```

### Verification Script

**File**: `scripts/verify-billing-setup.sh`
```bash
AWS_REGION="${AWS_REGION:-eu-west-2}"
```

## Multi-Region Architecture (Future)

### Phase 1 (Current): Single Region
- All resources in eu-west-2
- CloudFront provides global CDN
- Sufficient for MVP and initial users

### Phase 2 (Future): Multi-Region Active-Passive
- Primary: eu-west-2 (London)
- Secondary: us-east-1 (N. Virginia) for disaster recovery
- Route 53 health checks and failover
- Cross-region RDS replication

### Phase 3 (Future): Multi-Region Active-Active
- Multiple regions serving traffic
- Route 53 geolocation routing
- DynamoDB Global Tables
- Aurora Global Database

## Cost Implications

### Regional Pricing Comparison

| Service | us-east-1 | eu-west-2 | Difference |
|---------|-----------|-----------|------------|
| ECS Fargate (vCPU-hour) | $0.04048 | $0.04456 | +10% |
| ECS Fargate (GB-hour) | $0.004445 | $0.004890 | +10% |
| Aurora Serverless v2 (ACU-hour) | $0.12 | $0.142 | +18% |
| ElastiCache (cache.t4g.micro) | $0.016/hr | $0.018/hr | +13% |
| ALB (per hour) | $0.0225 | $0.0243 | +8% |
| S3 Standard (per GB) | $0.023 | $0.024 | +4% |

**Impact**: eu-west-2 is approximately 10-15% more expensive than us-east-1.

**Monthly Cost Estimate**:
- us-east-1: $10-15/month with daily teardown
- eu-west-2: $11-17/month with daily teardown
- **Additional cost**: ~$1-2/month

**Justification**: The latency improvement and data residency benefits outweigh the small cost increase for UK-based users.

## Latency Comparison

### From London, UK

| Region | Typical Latency |
|--------|-----------------|
| eu-west-2 (London) | 1-5ms |
| eu-west-1 (Ireland) | 10-15ms |
| us-east-1 (N. Virginia) | 70-90ms |
| us-west-2 (Oregon) | 140-160ms |

**Impact**: Using eu-west-2 provides 70-85ms lower latency compared to us-east-1 for UK users.

## Data Residency and Compliance

### UK/EU Data Residency

- ✅ All user data stored in eu-west-2 (London)
- ✅ Database backups remain in eu-west-2
- ✅ Logs and metrics in eu-west-2
- ✅ Compliant with UK data protection preferences

### GDPR Considerations

- ✅ Data processing in EU region
- ✅ Data subject rights easier to implement
- ✅ No transatlantic data transfers for primary data
- ⚠️ CloudFront may cache data globally (can be configured)

## Changing Regions

If you need to deploy to a different region:

### 1. Update Terraform Variables

Edit `terraform/terraform.tfvars`:
```hcl
aws_region = "your-preferred-region"  # e.g., "us-east-1", "eu-west-1"
```

### 2. Update AWS CLI Profile

```bash
aws configure set region your-preferred-region --profile festival-playlist
```

### 3. Update Environment Variables

```bash
export AWS_REGION=your-preferred-region
```

### 4. Verify Service Availability

Check that all required services are available in your chosen region:
- [AWS Regional Services](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/)

### 5. Update Documentation

Update any hardcoded region references in:
- README files
- Documentation
- Scripts
- Configuration files

## Testing Multi-Region Setup

To test deployment in multiple regions:

```bash
# Deploy to eu-west-2 (primary)
terraform workspace new eu-west-2
terraform apply -var="aws_region=eu-west-2"

# Deploy to us-east-1 (secondary)
terraform workspace new us-east-1
terraform apply -var="aws_region=us-east-1"

# Compare costs and performance
```

## Availability Zones

Each region has multiple Availability Zones (AZs):

### eu-west-2 (London)
- eu-west-2a
- eu-west-2b
- eu-west-2c

**Configuration**: Resources will be distributed across 2 AZs for high availability:
- Public subnets: eu-west-2a, eu-west-2b
- Private subnets: eu-west-2a, eu-west-2b
- RDS Multi-AZ: eu-west-2a (primary), eu-west-2b (standby)

## Troubleshooting

### Issue: Service not available in eu-west-2

**Solution**: Check [AWS Regional Services](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/) and either:
1. Use alternative service available in eu-west-2
2. Deploy that specific service to different region
3. Choose different primary region

### Issue: Higher costs than expected

**Solution**: 
1. Verify pricing in [AWS Pricing Calculator](https://calculator.aws/)
2. Consider us-east-1 if cost is primary concern
3. Optimize resource usage (smaller instances, spot instances)

### Issue: Billing metrics not showing

**Solution**: 
1. Billing metrics are only in us-east-1 (AWS limitation)
2. CloudWatch dashboard must query us-east-1 for billing data
3. This is normal and expected

## References

- [AWS Global Infrastructure](https://aws.amazon.com/about-aws/global-infrastructure/)
- [AWS Regional Services List](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/)
- [AWS Pricing Calculator](https://calculator.aws/)
- [CloudFront Edge Locations](https://aws.amazon.com/cloudfront/features/)
- [Route 53 Routing Policies](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy.html)

## Summary

- ✅ **Primary Region**: eu-west-2 (London)
- ✅ **All main resources**: Deploy to eu-west-2
- ⚠️ **Billing metrics**: Query us-east-1 (AWS limitation)
- ⚠️ **CloudFront ACM**: Certificate in us-east-1 (AWS requirement)
- 💰 **Cost Impact**: +10-15% vs us-east-1 (~$1-2/month)
- ⚡ **Latency Benefit**: 70-85ms faster for UK users
- 🇬🇧 **Data Residency**: UK/EU compliance

---

**Last Updated**: January 15, 2026
**Default Region**: eu-west-2 (London)
**Status**: Configured and documented
