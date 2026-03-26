# Security Module Usage Guide

## Overview

The security module manages all security-related resources for the Festival Playlist Generator, including SSL certificates, DNS configuration, WAF protection, and secrets management.

## Prerequisites

1. **Domain Name**: You must own the domain `gig-prep.co.uk` (or configure a different domain)
2. **AWS Provider Configuration**: Two AWS providers must be configured:
   - Default provider for `eu-west-2` (primary region)
   - Aliased provider for `us-east-1` (required for CloudFront certificates)

## Provider Configuration

In your root `main.tf`, configure both providers:

```hcl
provider "aws" {
  region = "eu-west-2"

  default_tags {
    tags = {
      Project     = "festival-playlist-generator"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Required for CloudFront ACM certificates
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "festival-playlist-generator"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
```

## Module Usage

### Basic Usage

```hcl
module "security" {
  source = "./modules/security"

  # Required variables
  project_name = "festival-playlist"
  environment  = "dev"
  domain_name  = "gig-prep.co.uk"
  vpc_id       = module.networking.vpc_id

  # Optional - ALB ARN for WAF association
  alb_arn = module.compute.alb_arn

  # Common tags
  common_tags = {
    Project     = "festival-playlist-generator"
    Environment = "dev"
    ManagedBy   = "terraform"
  }

  # Pass the us-east-1 provider for CloudFront certificate
  providers = {
    aws.us_east_1 = aws.us_east_1
  }
}
```

### With Dependencies

```hcl
# First create networking
module "networking" {
  source = "./modules/networking"
  # ... configuration
}

# Then create security (needs VPC ID)
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

# Then create compute (needs certificates)
module "compute" {
  source = "./modules/compute"

  # Use ALB certificate from security module
  alb_certificate_arn = module.security.alb_certificate_arn

  # ... other configuration
}

# Finally, update security with ALB ARN for WAF association
# This creates a circular dependency, so handle it carefully
```

## Resources Created

### 1. ACM Certificates

**ALB Certificate (eu-west-2)**:
- Domain: `gig-prep.co.uk`
- SANs: `*.gig-prep.co.uk`
- Validation: DNS via Route 53
- Use: Application Load Balancer

**CloudFront Certificate (us-east-1)**:
- Domain: `gig-prep.co.uk`
- SANs: `*.gig-prep.co.uk`
- Validation: DNS via Route 53
- Use: CloudFront distribution

### 2. Route 53 Hosted Zone

- Zone: `gig-prep.co.uk`
- DNS validation records for both certificates
- Name servers (output for domain registrar configuration)

### 3. AWS WAF Web ACL

**Rules Configured**:
1. **Rate Limiting**: 1000 requests per 5 minutes per IP
2. **Core Rule Set**: SQL injection, XSS, LFI, RFI protection
3. **Known Bad Inputs**: Protection against known malicious patterns
4. **SQL Database Protection**: Additional SQL injection protection

**Logging**:
- CloudWatch Logs: `/aws/waf/festival-playlist-{environment}`
- Retention: 7 days (dev), 30 days (prod)

### 4. Secrets Manager Secrets

**Spotify Credentials** (manual population required):
```json
{
  "client_id": "REPLACE_WITH_SPOTIFY_CLIENT_ID",
  "client_secret": "REPLACE_WITH_SPOTIFY_CLIENT_SECRET"
}
```

**Setlist.fm API Key** (manual population required):
```json
{
  "api_key": "REPLACE_WITH_SETLISTFM_API_KEY"
}
```

**JWT Signing Key** (auto-generated):
```json
{
  "secret_key": "<64-character-random-string>"
}
```

## Post-Deployment Steps

### 1. Configure Domain Name Servers

After the first `terraform apply`, configure your domain registrar with the Route 53 name servers:

```bash
# Get name servers from Terraform output
terraform output -json | jq '.security_name_servers.value'

# Example output:
# [
#   "ns-123.awsdns-12.com",
#   "ns-456.awsdns-45.net",
#   "ns-789.awsdns-78.org",
#   "ns-012.awsdns-01.co.uk"
# ]
```

Update your domain registrar (e.g., Namecheap, GoDaddy) with these name servers.

### 2. Wait for Certificate Validation

Certificate validation typically takes 5-30 minutes after DNS propagation:

```bash
# Check certificate status
aws acm describe-certificate \
  --certificate-arn $(terraform output -raw alb_certificate_arn) \
  --region eu-west-2

# Check CloudFront certificate status
aws acm describe-certificate \
  --certificate-arn $(terraform output -raw cloudfront_certificate_arn) \
  --region us-east-1
```

### 3. Populate Secrets Manually

**Update Spotify Credentials**:
```bash
aws secretsmanager update-secret \
  --secret-id $(terraform output -raw spotify_secret_name) \
  --secret-string '{
    "client_id": "your-spotify-client-id",
    "client_secret": "your-spotify-client-secret"
  }' \
  --region eu-west-2
```

**Update Setlist.fm API Key**:
```bash
aws secretsmanager update-secret \
  --secret-id $(terraform output -raw setlistfm_secret_name) \
  --secret-string '{
    "api_key": "your-setlistfm-api-key"
  }' \
  --region eu-west-2
```

**Verify JWT Secret** (auto-generated, no action needed):
```bash
aws secretsmanager get-secret-value \
  --secret-id $(terraform output -raw jwt_secret_name) \
  --region eu-west-2 \
  --query SecretString \
  --output text | jq .
```

### 4. Verify WAF Association

After ALB is created and associated:

```bash
# Check WAF association
aws wafv2 list-web-acls \
  --scope REGIONAL \
  --region eu-west-2

# Check WAF metrics in CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace AWS/WAFV2 \
  --metric-name AllowedRequests \
  --dimensions Name=WebACL,Value=festival-playlist-dev-alb-waf \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region eu-west-2
```

## Outputs

### Certificate Outputs
- `alb_certificate_arn`: ARN of ALB certificate (use in compute module)
- `cloudfront_certificate_arn`: ARN of CloudFront certificate (use in CDN module)
- `alb_certificate_status`: Validation status of ALB certificate
- `cloudfront_certificate_status`: Validation status of CloudFront certificate

### Route 53 Outputs
- `route53_zone_id`: Zone ID (use for creating DNS records)
- `route53_zone_name`: Zone name
- `route53_name_servers`: Name servers (configure in domain registrar)

### WAF Outputs
- `waf_web_acl_id`: WAF Web ACL ID
- `waf_web_acl_arn`: WAF Web ACL ARN
- `waf_web_acl_capacity`: WCU capacity used

### Secrets Outputs
- `spotify_secret_arn`: Spotify credentials secret ARN
- `setlistfm_secret_arn`: Setlist.fm API key secret ARN
- `jwt_secret_arn`: JWT signing key secret ARN
- `secrets_summary`: Summary of all secrets

## Cost Breakdown

### Monthly Costs (eu-west-2)

| Resource | Cost | Notes |
|----------|------|-------|
| ACM Certificates | $0 | Free for public certificates |
| Route 53 Hosted Zone | $0.50 | Per hosted zone |
| Route 53 Queries | ~$0.40 | First 1B queries: $0.40/million |
| WAF Web ACL | $5.00 | Base price |
| WAF Rules | $4.00 | 4 rules × $1.00 each |
| WAF Requests | ~$0.60 | First 1M requests free, then $0.60/million |
| Secrets Manager | $1.20 | 3 secrets × $0.40/month |
| CloudWatch Logs | ~$0.50 | WAF logs, 7-day retention |
| **Total** | **~$12.20/month** | |

### Cost Optimization Tips

1. **WAF Rules**: Start with essential rules, add more as needed
2. **Log Retention**: Use 7 days for dev, 30 days for prod
3. **Secrets**: Consolidate secrets where possible
4. **DNS Queries**: Use CloudFront caching to reduce Route 53 queries

## Security Best Practices

### 1. Certificate Management
- ✅ Auto-renewal enabled (ACM handles this)
- ✅ Wildcard certificates for subdomains
- ✅ Separate certificates for ALB and CloudFront
- ✅ DNS validation (more secure than email)

### 2. WAF Configuration
- ✅ Rate limiting prevents DDoS attacks
- ✅ AWS managed rules updated automatically
- ✅ CloudWatch logging for audit trail
- ✅ Metrics for monitoring attack patterns

### 3. Secrets Management
- ✅ All secrets in Secrets Manager (not environment variables)
- ✅ Secrets marked as persistent (survive teardown)
- ✅ JWT key auto-generated (no manual creation)
- ✅ 7-day recovery window for accidental deletion

### 4. DNS Security
- ✅ DNSSEC can be enabled on Route 53 (optional)
- ✅ DNS validation records auto-created
- ✅ Name servers managed by AWS

## Troubleshooting

### Certificate Validation Stuck

**Problem**: Certificate status remains "Pending Validation"

**Solutions**:
1. Check DNS propagation:
   ```bash
   dig _acme-challenge.gig-prep.co.uk
   ```

2. Verify name servers configured correctly at registrar

3. Wait 30 minutes for DNS propagation

4. Check Route 53 validation records exist:
   ```bash
   aws route53 list-resource-record-sets \
     --hosted-zone-id $(terraform output -raw route53_zone_id)
   ```

### WAF Blocking Legitimate Traffic

**Problem**: WAF blocking valid requests

**Solutions**:
1. Check WAF logs:
   ```bash
   aws logs tail /aws/waf/festival-playlist-dev --follow
   ```

2. Identify blocked rule in CloudWatch Logs

3. Add exception to WAF rule if needed

4. Adjust rate limit threshold if too aggressive

### Secrets Not Accessible

**Problem**: Application can't read secrets

**Solutions**:
1. Verify IAM role has `secretsmanager:GetSecretValue` permission

2. Check secret ARN is correct:
   ```bash
   terraform output secrets_summary
   ```

3. Verify secret exists and has value:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id festival-playlist-dev-spotify-credentials \
     --region eu-west-2
   ```

### Circular Dependency with ALB

**Problem**: Security module needs ALB ARN, but compute module needs certificate ARN

**Solutions**:
1. First apply without `alb_arn`:
   ```bash
   terraform apply -target=module.security
   ```

2. Then apply compute module:
   ```bash
   terraform apply -target=module.compute
   ```

3. Finally, update security with ALB ARN:
   ```bash
   terraform apply
   ```

## Maintenance

### Regular Tasks

**Weekly**:
- Review WAF logs for attack patterns
- Check certificate expiration (should auto-renew)

**Monthly**:
- Review WAF rules effectiveness
- Audit secrets access logs
- Review DNS query patterns

**Quarterly**:
- Update WAF managed rules (AWS handles this)
- Review and rotate secrets if needed
- Test certificate renewal process

## References

- [AWS ACM Documentation](https://docs.aws.amazon.com/acm/)
- [AWS WAF Documentation](https://docs.aws.amazon.com/waf/)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [Route 53 Documentation](https://docs.aws.amazon.com/route53/)
