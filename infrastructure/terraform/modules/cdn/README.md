# CDN Module

This module creates a CloudFront distribution for the Festival Playlist Generator with optimized caching strategies for both API traffic and static assets.

## Features

- **Dual Origins**: ALB for API traffic, S3 for static assets
- **Smart Caching**: No caching for API, 1-day TTL for static assets
- **Global CDN**: CloudFront edge locations worldwide
- **Secure Access**: Origin Access Identity (OAI) for private S3 access
- **HTTPS Enforcement**: All traffic redirected to HTTPS with TLS 1.2+
- **Compression**: Enabled for all content types
- **HTTP/2 & HTTP/3**: Modern protocol support
- **Cost Optimized**: PriceClass_100 (North America and Europe only)
- **Access Logging**: CloudFront logs to S3 bucket
- **Custom Domain**: Support for custom domains with ACM certificates

## Resources Created

- **CloudFront Distribution**: Global CDN with dual origins
- **Origin Access Identity (OAI)**: Secure S3 access without public bucket
- **Cache Behaviors**: Optimized for API and static content
- **Logging Configuration**: Access logs to S3

## Quick Start

```hcl
module "cdn" {
  source = "./modules/cdn"

  # Required
  project_name                               = "festival-app"
  environment                                = "dev"
  alb_dns_name                              = module.compute.alb_dns_name
  static_assets_bucket_regional_domain_name = module.storage.app_data_bucket_regional_domain_name
  logs_bucket_name                          = module.storage.cloudfront_logs_bucket_name

  # Optional - Custom Domain
  acm_certificate_arn = module.security.cloudfront_certificate_arn
  domain_name         = "gig-prep.co.uk"

  # Optional - Cost Optimization
  price_class = "PriceClass_100"

  # Tags
  common_tags = var.common_tags
}

# Update storage module to grant OAI access
module "storage" {
  source = "./modules/storage"

  # ... other config

  cloudfront_oai_iam_arn = module.cdn.oai_iam_arn
}

# Create Route 53 alias record for custom domain
resource "aws_route53_record" "cloudfront" {
  zone_id = module.security.route53_zone_id
  name    = "gig-prep.co.uk"
  type    = "A"

  alias {
    name                   = module.cdn.distribution_domain_name
    zone_id                = module.cdn.distribution_hosted_zone_id
    evaluate_target_health = false
  }
}
```

## Architecture

### Origins

1. **ALB Origin** (API Traffic)
   - HTTPS only (TLS 1.2+)
   - Custom header for origin verification
   - 60-second read timeout

2. **S3 Origin** (Static Assets)
   - Access via OAI (private bucket)
   - Regional domain name
   - Server-side encryption

### Cache Behaviors

1. **Default** (`/*`) - API Traffic
   - Target: ALB
   - Caching: Disabled
   - Methods: All
   - Headers/Cookies: All forwarded

2. **Static Assets** (`/static/*`)
   - Target: S3
   - Caching: 1 day (max 1 year)
   - Methods: GET, HEAD, OPTIONS
   - Compression: Enabled

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project_name | Project name | string | - | yes |
| environment | Environment (dev/staging/prod) | string | - | yes |
| alb_dns_name | ALB DNS name | string | - | yes |
| static_assets_bucket_regional_domain_name | S3 regional domain | string | - | yes |
| logs_bucket_name | CloudFront logs bucket | string | - | yes |
| acm_certificate_arn | ACM certificate ARN (us-east-1) | string | null | no |
| domain_name | Custom domain name | string | null | no |
| price_class | CloudFront price class | string | "PriceClass_100" | no |
| log_prefix | Log prefix in S3 | string | "cloudfront-logs/" | no |
| custom_header_value | Custom header value | string | "cloudfront-origin" | no |
| common_tags | Common resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| distribution_id | CloudFront distribution ID |
| distribution_arn | CloudFront distribution ARN |
| distribution_domain_name | CloudFront domain name |
| distribution_hosted_zone_id | Route 53 zone ID for alias records |
| distribution_status | Distribution status |
| oai_id | Origin Access Identity ID |
| oai_iam_arn | OAI IAM ARN for S3 bucket policy |
| cloudfront_summary | Configuration summary |

## Cost Optimization

### Price Classes

- **PriceClass_100** (default): North America & Europe (~$0.085/GB)
- **PriceClass_200**: + Asia, Middle East, Africa (~$0.120/GB)
- **PriceClass_All**: All locations (~$0.170/GB)

### Estimated Costs

**Example**: 10 GB data transfer + 100K requests
- Data transfer: 10 GB × $0.085 = $0.85
- Requests: 100K × $0.0075/10K = $0.75
- **Total**: ~$1.60/month

**Free Tier** (first 12 months):
- 1 TB data transfer out
- 10 million requests
- **Effective cost**: $0/month

## Security

- ✅ HTTPS enforcement (redirect HTTP to HTTPS)
- ✅ TLS 1.2+ minimum protocol version
- ✅ Private S3 bucket (access via OAI only)
- ✅ Custom header for origin verification
- ✅ No public S3 access
- ✅ Encrypted logs (S3 server-side encryption)
- ✅ ACM certificate support

## Monitoring

### CloudWatch Metrics

- `Requests`: Total number of requests
- `BytesDownloaded`: Data transfer out
- `4xxErrorRate`: Client error rate
- `5xxErrorRate`: Server error rate
- `CacheHitRate`: Cache efficiency

### Recommended Alarms

1. High error rate (> 5%)
2. Low cache hit rate (< 50%)
3. High data transfer (cost monitoring)

## Deployment

### Initial Deployment
```bash
terraform init
terraform plan
terraform apply
```
**Time**: 15-20 minutes

### Updates
```bash
terraform apply
```
**Time**: 5-10 minutes

## Testing

```bash
# Test CloudFront URL
curl -I https://<distribution-domain>.cloudfront.net

# Test custom domain
curl -I https://gig-prep.co.uk

# Check cache behavior
curl -I https://<distribution-domain>.cloudfront.net/static/logo.png
# Look for: X-Cache: Hit from cloudfront
```

## Troubleshooting

### Distribution Not Deploying
- Check ACM certificate is in us-east-1
- Verify S3 bucket exists
- Wait 15-20 minutes for initial deployment

### Custom Domain Not Working
- Verify ACM certificate validated
- Check Route 53 alias record
- Wait for DNS propagation (up to 48 hours)

### S3 Access Denied
- Verify OAI created
- Check S3 bucket policy includes OAI ARN
- Ensure bucket is private

## Documentation

- **USAGE.md**: Detailed usage guide with examples
- **IMPLEMENTATION_SUMMARY.md**: Implementation details and architecture
- **CHECKLIST.md**: Implementation checklist and validation

## Requirements Satisfied

- ✅ **US-7.4**: CloudFront CDN for static assets with global distribution
- ✅ **US-5.1**: CloudFront access logs to S3 bucket
- ✅ **US-6.9**: S3 bucket policy with OAI (no public access)

## Module Dependencies

- **Compute Module**: ALB DNS name
- **Storage Module**: S3 bucket names and domain names
- **Security Module**: ACM certificate ARN (optional)

## Best Practices

1. Use PriceClass_100 for cost optimization
2. Enable compression for all content
3. Set appropriate TTLs for static assets
4. Use OAI for S3 access (not public bucket)
5. Enable access logging for monitoring
6. Use custom domain with ACM certificate
7. Monitor cache hit rate and optimize
8. Tag all resources for cost allocation

## Support

For detailed usage instructions, see [USAGE.md](./USAGE.md).

For implementation details, see [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md).
