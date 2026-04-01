# Terraform Backend Configuration
# This file configures S3 backend for remote state storage with native S3 locking
#
# Terraform v1.10+ includes native S3 state locking - no DynamoDB table needed!
# This is simpler, cheaper, and eliminates the need for a separate locking service.
#
# NOTE: The state key is "ephemeral/terraform.tfstate" to distinguish from the
# persistent module's state at "persistent/terraform.tfstate".
# For multi-environment support, override the key at init time:
#   terraform init -backend-config="key=ephemeral/prod/terraform.tfstate"

terraform {
  backend "s3" {
    bucket       = "festival-playlist-terraform-state"
    key          = "ephemeral/terraform.tfstate"
    region       = "eu-west-2"
    encrypt      = true
    use_lockfile = true # Native S3 locking (Terraform v1.10+)
  }
}

# Backend Resources:
#
# S3 Bucket: festival-playlist-terraform-state
# - Versioning: Enabled (rollback capability)
# - Encryption: AES256 (data at rest)
# - Public Access: Blocked (security)
# - Lifecycle: Delete old versions after 90 days (cost optimization)
# - Native Locking: Enabled via use_lockfile (Terraform v1.10+)

# Benefits of Native S3 Locking:
# ✅ Simpler setup (no DynamoDB table)
# ✅ Lower cost (no DynamoDB charges)
# ✅ Fewer resources to manage
# ✅ Same reliability as DynamoDB locking

# To switch back to local state (not recommended):
# 1. Comment out the backend configuration above
# 2. Run: terraform init -migrate-state
# 3. Confirm migration when prompted
