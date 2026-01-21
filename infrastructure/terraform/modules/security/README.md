# Security Module

This module manages security-related resources for the Festival Playlist Generator.

## Resources Created

- AWS Secrets Manager secrets (Spotify, Setlist.fm, JWT)
- ACM certificate for custom domain
- Route 53 hosted zone and DNS records
- AWS WAF web ACL for ALB protection
- CloudTrail for audit logging
- VPC Flow Logs

## Secrets

All secrets are marked with `prevent_destroy = true` to persist across teardown/rebuild cycles.

### Managed Secrets
- Spotify API credentials (manual population required)
- Setlist.fm API key (manual population required)
- JWT signing key (auto-generated)

### Database and Redis Secrets
- Managed by database and cache modules respectively

## ACM Certificate

- Domain: gig-prep.co.uk and *.gig-prep.co.uk
- DNS validation via Route 53
- Auto-renewal enabled

## AWS WAF Rules

- Rate limiting (1000 requests per 5 min per IP)
- AWS managed rules (SQL injection, XSS protection)

## Usage

```hcl
module "security" {
  source = "./modules/security"
  
  project_name  = var.project_name
  environment   = var.environment
  domain_name   = var.domain_name
  alb_arn       = module.compute.alb_arn
  vpc_id        = module.networking.vpc_id
  common_tags   = var.common_tags
}
```

## Outputs

- acm_certificate_arn
- route53_zone_id
- waf_web_acl_id
- spotify_secret_arn
- setlistfm_secret_arn
- jwt_secret_arn
