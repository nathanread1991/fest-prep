# CDN Module Usage Guide

## Overview

The CDN module creates a CloudFront distribution for the Festival Playlist Generator with two origins:
1. **ALB Origin**: For API traffic (no caching)
2. **S3 Origin**: For static assets (1-day TTL caching)

## Basic Usage

```hcl
module "cdn" {
  source = "./modules/cdn"

  # Required variables
  project_name                               = "festival-app"
  environment                                = "dev"
  alb_dns_name                              = module.compute.alb_dns_name
  static_assets_bucket_regional_domain_name = module.storage.app_data_bucket_regional_domain_name
  logs_bucket_name                          = module.storage.cloudfront_logs_bucket_name

  # Optional: Custom domain configuration
  acm_certificate_arn = module.security.cloudfront_certificate_arn
  domain_name         = "gig-prep.co.uk"

  # Optional: Cost optimization
  price_class = "PriceClass_100"  # North America and Europe only

  # Optional: Logging configuration
  log_prefix = "cloudfront-logs/"

  # Tags
  common_tags = {
    Project     = "festival-app"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

## Configuration Options

### Required Variables

| Variable | Type | Description |
|----------|------|-------------|
| `project_name` | string | Name of the project |
| `environment` | string | Environment name (dev, staging, prod) |
| `alb_dns_name` | string | DNS name of the Application Load Balancer |
| `static_assets_bucket_regional_domain_name` | string | Regional domain name of the S3 bucket for static assets |
| `logs_bucket_name` | string | Name of the S3 bucket for CloudFront access logs |

### Optional Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `acm_certificate_arn` | string | null | ARN of ACM certificate (must be in us-east-1) |
| `domain_name` | string | null | Custom domain name for CloudFront |
| `price_class` | string | "PriceClass_100" | CloudFront price class |
| `log_prefix` | string | "cloudfront-logs/" | Prefix for CloudFront logs in S3 |
| `custom_header_value` | string | "cloudfront-origin" | Custom header for origin verification |
| `common_tags` | map(string) | {} | Common tags for all resources |

## Price Classes

CloudFront offers three price classes:

- **PriceClass_100**: North America and Europe only (cheapest, ~$0.085/GB)
- **PriceClass_200**: North America, Europe, Asia, Middle East, Africa (~$0.120/GB)
- **PriceClass_All**: All edge locations globally (~$0.170/GB)

For cost optimization, use `PriceClass_100` for hobby projects.

## Cache Behaviors

### Default Behavior (API Traffic)
- **Target**: ALB origin
- **Caching**: Disabled (TTL = 0)
- **Methods**: All HTTP methods allowed
- **Headers**: All headers forwarded
- **Cookies**: All cookies forwarded
- **Query Strings**: Forwarded
- **Compression**: Enabled

### /static/* Behavior (Static Assets)
- **Target**: S3 origin
- **Caching**: Enabled (1 day default, 1 year max)
- **Methods**: GET, HEAD, OPTIONS only
- **Headers**: CORS headers only
- **Cookies**: None forwarded
- **Query Strings**: Not forwarded
- **Compression**: Enabled

## Custom Domain Setup

To use a custom domain with CloudFront:

1. **Create ACM certificate in us-east-1** (CloudFront requirement):
   ```hcl
   # In security module
   resource "aws_acm_certificate" "cloudfront" {
     provider          = aws.us_east_1
     domain_name       = "gig-prep.co.uk"
     validation_method = "DNS"
   }
   ```

2. **Pass certificate ARN to CDN module**:
   ```hcl
   module "cdn" {
     # ... other config
     acm_certificate_arn = module.security.cloudfront_certificate_arn
     domain_name         = "gig-prep.co.uk"
   }
   ```

3. **Create Route 53 alias record**:
   ```hcl
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

## Origin Access Identity (OAI)

The module creates a CloudFront Origin Access Identity to securely access S3 without making the bucket public.

### S3 Bucket Policy Update

Update the storage module to allow OAI access:

```hcl
module "storage" {
  source = "./modules/storage"

  # ... other config

  # Pass OAI ARN for bucket policy
  cloudfront_oai_iam_arn = module.cdn.oai_iam_arn
}
```

The storage module will automatically grant the OAI read access to the S3 bucket.

## Logging

CloudFront access logs are written to the specified S3 bucket with the configured prefix.

### Log Format

Logs include:
- Date and time
- Edge location
- Bytes sent
- Client IP
- HTTP method
- Host
- URI
- Status code
- Referrer
- User agent
- Query string
- Cookie (excluded by default)
- Result type (Hit, Miss, Error)
- Request ID

### Log Retention

Configure lifecycle policy in the storage module:
```hcl
# In storage module
resource "aws_s3_bucket_lifecycle_configuration" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    expiration {
      days = 30  # Keep logs for 30 days
    }
  }
}
```

## Outputs

The module provides the following outputs:

| Output | Description |
|--------|-------------|
| `distribution_id` | CloudFront distribution ID |
| `distribution_arn` | CloudFront distribution ARN |
| `distribution_domain_name` | CloudFront domain name (e.g., d123456.cloudfront.net) |
| `distribution_hosted_zone_id` | Route 53 zone ID for alias records |
| `distribution_status` | Current status (Deployed, InProgress) |
| `oai_id` | Origin Access Identity ID |
| `oai_iam_arn` | OAI IAM ARN for S3 bucket policy |
| `cloudfront_summary` | Summary of all configuration |

## Integration with Other Modules

### With Compute Module (ALB)

```hcl
module "cdn" {
  source = "./modules/cdn"

  alb_dns_name = module.compute.alb_dns_name
  # ... other config
}
```

### With Storage Module (S3)

```hcl
module "cdn" {
  source = "./modules/cdn"

  static_assets_bucket_regional_domain_name = module.storage.app_data_bucket_regional_domain_name
  logs_bucket_name                          = module.storage.cloudfront_logs_bucket_name
  # ... other config
}

module "storage" {
  source = "./modules/storage"

  # Grant OAI access to S3 bucket
  cloudfront_oai_iam_arn = module.cdn.oai_iam_arn
  # ... other config
}
```

### With Security Module (ACM, Route 53)

```hcl
module "cdn" {
  source = "./modules/cdn"

  acm_certificate_arn = module.security.cloudfront_certificate_arn
  domain_name         = "gig-prep.co.uk"
  # ... other config
}

# Create Route 53 record pointing to CloudFront
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

## Cost Optimization Tips

1. **Use PriceClass_100**: Limits edge locations to North America and Europe (~40% cheaper)
2. **Cache static assets**: 1-day TTL reduces origin requests
3. **Enable compression**: Reduces data transfer costs
4. **Monitor usage**: Use CloudWatch metrics to track data transfer
5. **Set log expiration**: Delete old logs after 30 days

### Estimated Costs (PriceClass_100)

- **Data transfer out**: $0.085/GB (first 10 TB)
- **HTTP/HTTPS requests**: $0.0075 per 10,000 requests
- **Invalidation requests**: First 1,000 free, then $0.005 per path

**Example**: 10 GB data transfer + 100K requests = ~$0.93/month

## Deployment Time

- **Initial deployment**: 15-20 minutes (CloudFront distribution creation)
- **Updates**: 5-10 minutes (configuration changes)
- **Invalidations**: 1-5 minutes (cache clearing)

## Troubleshooting

### Distribution not deploying

Check CloudFront distribution status:
```bash
aws cloudfront get-distribution --id <distribution-id>
```

### Custom domain not working

1. Verify ACM certificate is in us-east-1
2. Check certificate validation status
3. Verify Route 53 alias record points to CloudFront
4. Wait for DNS propagation (up to 48 hours)

### S3 access denied

1. Verify OAI is created
2. Check S3 bucket policy includes OAI ARN
3. Verify bucket is not public (should be private)

### Cache not working

1. Check cache behavior path patterns
2. Verify TTL settings
3. Check CloudWatch metrics for cache hit ratio
4. Create invalidation if needed:
   ```bash
   aws cloudfront create-invalidation \
     --distribution-id <id> \
     --paths "/*"
   ```

## Security Considerations

1. **HTTPS only**: All traffic redirected to HTTPS
2. **TLS 1.2+**: Minimum protocol version enforced
3. **Private S3 bucket**: Access only via OAI
4. **Custom header**: Verify requests from CloudFront
5. **No public access**: S3 bucket blocks all public access
6. **Encrypted logs**: S3 server-side encryption enabled

## Monitoring

### CloudWatch Metrics

Monitor these CloudFront metrics:
- `Requests`: Total number of requests
- `BytesDownloaded`: Data transfer out
- `BytesUploaded`: Data transfer in
- `4xxErrorRate`: Client error rate
- `5xxErrorRate`: Server error rate
- `CacheHitRate`: Percentage of cached requests

### Alarms

Create alarms for:
- High error rate (> 5%)
- Low cache hit rate (< 50%)
- High data transfer (cost monitoring)

## Best Practices

1. **Use custom domain**: Better branding and SEO
2. **Enable compression**: Reduces bandwidth costs
3. **Set appropriate TTLs**: Balance freshness vs. cost
4. **Monitor cache hit ratio**: Optimize cache behaviors
5. **Use invalidations sparingly**: They cost money
6. **Enable access logs**: Track usage patterns
7. **Tag all resources**: Cost allocation and management
8. **Test before production**: Use dev environment first

## Example: Complete Setup

```hcl
# main.tf

module "cdn" {
  source = "./modules/cdn"

  project_name                               = "festival-app"
  environment                                = "prod"
  alb_dns_name                              = module.compute.alb_dns_name
  static_assets_bucket_regional_domain_name = module.storage.app_data_bucket_regional_domain_name
  logs_bucket_name                          = module.storage.cloudfront_logs_bucket_name
  acm_certificate_arn                       = module.security.cloudfront_certificate_arn
  domain_name                                = "gig-prep.co.uk"
  price_class                                = "PriceClass_100"

  common_tags = {
    Project     = "festival-app"
    Environment = "prod"
    ManagedBy   = "terraform"
    CostCenter  = "engineering"
  }
}

# Route 53 record
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

# Outputs
output "cloudfront_url" {
  value = "https://${module.cdn.distribution_domain_name}"
}

output "custom_domain_url" {
  value = "https://gig-prep.co.uk"
}
```
