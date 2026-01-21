# Terraform Scripts

This directory contains utility scripts for managing Terraform infrastructure.

## init-backend.sh

Initializes the Terraform backend by creating the required S3 bucket for remote state storage with native S3 locking (Terraform v1.10+).

### What it does:

Creates S3 bucket: `festival-playlist-terraform-state`
- Enables versioning (rollback capability)
- Enables server-side encryption (AES256)
- Blocks public access (security)
- Adds lifecycle policy (delete old versions after 90 days)
- Configures for native S3 locking (no DynamoDB needed!)

### Native S3 Locking (Terraform v1.10+)

Terraform v1.10 introduced native S3 state locking, eliminating the need for DynamoDB:

**Benefits:**
- ✅ Simpler setup (one resource instead of two)
- ✅ Lower cost (no DynamoDB charges)
- ✅ Fewer resources to manage
- ✅ Same reliability as DynamoDB locking

**How it works:**
- Uses S3's conditional writes for atomic operations
- Stores lock information in S3 metadata
- Automatically handles lock acquisition and release

### Prerequisites:

- Terraform v1.10 or higher
- AWS CLI installed
- AWS credentials configured for profile `festival-playlist`
- Appropriate IAM permissions (S3 only - no DynamoDB needed!)

### Usage:

```bash
# Run from terraform directory
cd terraform
./scripts/init-backend.sh

# Or run from project root
./terraform/scripts/init-backend.sh
```

### After running:

1. Uncomment the backend configuration in `terraform/backend.tf`
2. Run `terraform init` to initialize the backend
3. If you have existing local state, run `terraform init -migrate-state`

### Environment Variables:

- `AWS_PROFILE`: Override the default AWS profile (default: `festival-playlist`)

Example:
```bash
AWS_PROFILE=my-profile ./scripts/init-backend.sh
```

### Troubleshooting:

**Error: Bucket already exists**
- The bucket name is globally unique across all AWS accounts
- If you get a conflict, update the bucket name in the script

**Error: AWS credentials not configured**
- Run: `aws configure --profile festival-playlist`
- Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables

**Error: Access Denied**
- Ensure your IAM user/role has permissions for:
  - s3:CreateBucket, s3:PutBucketVersioning, s3:PutBucketEncryption
  - s3:PutBucketPublicAccessBlock, s3:PutLifecycleConfiguration

**Error: Terraform version too old**
- Native S3 locking requires Terraform v1.10+
- Check version: `terraform version`
- Upgrade if needed

### Cost:

- S3 bucket: ~$0.023/GB/month + request costs
- No DynamoDB costs (native S3 locking is free!)
- Estimated monthly cost: < $1 for typical usage

### Cleanup:

To delete the backend resources (not recommended unless decommissioning):

```bash
# Empty and delete S3 bucket
aws s3 rm s3://festival-playlist-terraform-state --recursive --profile festival-playlist
aws s3api delete-bucket \
  --bucket festival-playlist-terraform-state \
  --profile festival-playlist \
  --region eu-west-2
```

**Warning**: Deleting the backend will lose all Terraform state history!

### Migration from DynamoDB Locking:

If you previously used DynamoDB locking and want to migrate:

1. Run this script to create the S3 bucket (if not exists)
2. Update `backend.tf` to use `use_lockfile = true`
3. Run `terraform init -migrate-state`
4. Delete the old DynamoDB table (optional):
   ```bash
   aws dynamodb delete-table \
     --table-name festival-playlist-terraform-locks \
     --profile festival-playlist \
     --region eu-west-2
   ```
