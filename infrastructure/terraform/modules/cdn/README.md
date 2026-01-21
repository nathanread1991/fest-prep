# CDN Module

This module manages CloudFront distribution for the Festival Playlist Generator.

## Resources Created

- CloudFront distribution
- CloudFront Origin Access Identity (OAI)
- Cache behaviors for API and static assets
- SSL/TLS certificate association

## Configuration

### Origins
- ALB origin for API traffic
- S3 origin for static assets

### Cache Behaviors
- Default: Forward to ALB, no caching
- /static/*: S3 origin, 1-day TTL
- Compression and HTTP/2 enabled

### Logging
- Access logs to cloudfront-logs S3 bucket

## Usage

```hcl
module "cdn" {
  source = "./modules/cdn"
  
  project_name              = var.project_name
  environment               = var.environment
  alb_dns_name              = module.compute.alb_dns_name
  static_assets_bucket_name = module.storage.app_data_bucket_name
  logs_bucket_name          = module.storage.cloudfront_logs_bucket_name
  acm_certificate_arn       = module.security.acm_certificate_arn
  domain_name               = var.domain_name
  common_tags               = var.common_tags
}
```

## Outputs

- distribution_id
- distribution_domain_name
- distribution_hosted_zone_id
