# Security Module

This module manages security-related resources for the Festival Playlist Generator, including SSL certificates, DNS configuration, WAF protection, and secrets management.

## Overview

The security module provides comprehensive security infrastructure for the application:
- **SSL/TLS Certificates**: ACM certificates for ALB and CloudFront
- **DNS Management**: Route 53 hosted zone and validation records
- **WAF Protection**: Web Application Firewall with rate limiting and AWS managed rules
- **Secrets Management**: Secure storage for API credentials and signing keys

## Resources Created

### ACM Certificates
- **ALB Certificate** (eu-west-2): For Application Load Balancer
- **CloudFront Certificate** (us-east-1): For CloudFront distribution (AWS requirement)
- Domain: `gig-prep.co.uk` and `*.gig-prep.co.uk`
- Validation: DNS via Route 53
- Auto-renewal: Enabled

### Route 53
- Hosted zone for `gig-prep.co.uk`
- DNS validation records for both certificates
- Name servers for domain registrar configuration

### AWS WAF
- Web ACL with 4 protection rules:
  1. Rate limiting (1000 requests per 5 min per IP)
  2. AWS Core Rule Set (SQL injection, XSS, etc.)
  3. Known Bad Inputs protection
  4. SQL Database protection
- CloudWatch logging and metrics
- Association with ALB

### Secrets Manager
- **Spotify API credentials** (manual population required)
- **Setlist.fm API key** (manual population required)
- **JWT signing key** (auto-generated)
- All secrets marked as persistent (`prevent_destroy = true`)

## Prerequisites

1. **Domain Ownership**: You must own `gig-prep.co.uk` (or configure a different domain)
2. **AWS Providers**: Two providers required:
   - Default provider for `eu-west-2` (primary region)
   - Aliased provider for `us-east-1` (CloudFront certificates)

## Usage

### Basic Configuration

```hcl
# Configure providers
provider "aws" {
  region = "eu-west-2"
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

# Use security module
module "security" {
  source = "./modules/security"

  project_name = "festival-playlist"
  environment  = "dev"
  domain_name  = "gig-prep.co.uk"
  vpc_id       = module.networking.vpc_id
  alb_arn      = module.compute.alb_arn  # Optional, for WAF association

  common_tags = {
    Project     = "festival-playlist-generator"
    Environment = "dev"
    ManagedBy   = "terraform"
  }

  providers = {
    aws.us_east_1 = aws.us_east_1
  }
}
```

### With Dependencies

```hcl
# Networking module (provides VPC ID)
module "networking" {
  source = "./modules/networking"
  # ... configuration
}

# Security module (provides certificates)
module "security" {
  source = "./modules/security"

  project_name = "festival-playlist"
  environment  = "dev"
  domain_name  = "gig-prep.co.uk"
  vpc_id       = module.networking.vpc_id

  common_tags = var.common_tags

  providers = {
    aws.us_east_1 = aws.us_east_1
  }
}

# Compute module (uses ALB certificate)
module "compute" {
  source = "./modules/compute"

  alb_certificate_arn = module.security.alb_certificate_arn
  # ... other configuration
}
```

## Post-Deployment Steps

### 1. Configure Domain Name Servers

After first deployment, update your domain registrar with Route 53 name servers:

```bash
terraform output -json | jq '.security_name_servers.value'
```

### 2. Wait for Certificate Validation

Certificates typically validate in 5-30 minutes after DNS propagation.

### 3. Populate Secrets

Update Spotify and Setlist.fm secrets with actual credentials:

```bash
# Update Spotify credentials
aws secretsmanager update-secret \
  --secret-id $(terraform output -raw spotify_secret_name) \
  --secret-string '{"client_id":"your-id","client_secret":"your-secret"}' \
  --region eu-west-2

# Update Setlist.fm API key
aws secretsmanager update-secret \
  --secret-id $(terraform output -raw setlistfm_secret_name) \
  --secret-string '{"api_key":"your-key"}' \
  --region eu-west-2
```

## Outputs

### Certificates
- `alb_certificate_arn`: ARN of ALB certificate (use in compute module)
- `cloudfront_certificate_arn`: ARN of CloudFront certificate (use in CDN module)
- `alb_certificate_status`: Validation status
- `cloudfront_certificate_status`: Validation status

### Route 53
- `route53_zone_id`: Zone ID for creating DNS records
- `route53_zone_name`: Zone name
- `route53_name_servers`: Name servers for domain registrar

### WAF
- `waf_web_acl_id`: WAF Web ACL ID
- `waf_web_acl_arn`: WAF Web ACL ARN
- `waf_web_acl_capacity`: WCU capacity used

### Secrets
- `spotify_secret_arn`: Spotify credentials secret ARN
- `spotify_secret_name`: Spotify credentials secret name
- `setlistfm_secret_arn`: Setlist.fm API key secret ARN
- `setlistfm_secret_name`: Setlist.fm API key secret name
- `jwt_secret_arn`: JWT signing key secret ARN
- `jwt_secret_name`: JWT signing key secret name
- `secrets_summary`: Summary of all secrets
- `certificates_summary`: Summary of all certificates

## Cost Breakdown

| Resource | Monthly Cost |
|----------|--------------|
| ACM Certificates | $0 (free) |
| Route 53 Hosted Zone | $0.50 |
| Route 53 Queries | ~$0.40 |
| WAF Web ACL | $5.00 |
| WAF Rules (4) | $4.00 |
| WAF Requests | ~$0.60 |
| Secrets Manager (3) | $1.20 |
| CloudWatch Logs | ~$0.50 |
| **Total** | **~$12.20/month** |

## Security Features

### ✅ Certificate Security
- Auto-renewal enabled
- DNS validation (more secure than email)
- Wildcard certificates for subdomains
- Separate certificates for ALB and CloudFront

### ✅ WAF Protection
- Rate limiting prevents DDoS attacks
- AWS managed rules protect against OWASP Top 10
- CloudWatch logging for audit trail
- Metrics for monitoring attack patterns

### ✅ Secrets Management
- All secrets in Secrets Manager (not environment variables)
- Secrets encrypted at rest and in transit
- IAM-based access control
- 7-day recovery window for accidental deletion
- Secrets persist across teardown/rebuild cycles

### ✅ DNS Security
- Route 53 managed name servers
- DNS validation records auto-created
- DNSSEC can be enabled (optional)

## Documentation

- **USAGE.md**: Detailed usage guide with examples and troubleshooting
- **IMPLEMENTATION_SUMMARY.md**: Complete implementation details and decisions

## Requirements

This module satisfies the following requirements:
- **US-6.2**: All secrets in AWS Secrets Manager
- **US-6.7**: AWS WAF protecting ALB with rate limiting
- **US-7.1**: Custom domain configured (gig-prep.co.uk)
- **US-7.2**: SSL/TLS certificate from AWS Certificate Manager
- **US-7.3**: Domain registered via Route 53

## Maintenance

### Regular Tasks
- **Weekly**: Review WAF logs for attack patterns
- **Monthly**: Audit secrets access logs, review DNS query patterns
- **Quarterly**: Review WAF rules effectiveness, test certificate renewal

## References

- [AWS ACM Documentation](https://docs.aws.amazon.com/acm/)
- [AWS WAF Documentation](https://docs.aws.amazon.com/waf/)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [Route 53 Documentation](https://docs.aws.amazon.com/route53/)
