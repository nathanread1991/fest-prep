# Terraform Backend Configuration for Persistent Module
# Uses a separate state key from the ephemeral root to isolate persistent resources.

terraform {
  backend "s3" {
    bucket       = "festival-playlist-terraform-state"
    key          = "persistent/terraform.tfstate"
    region       = "eu-west-2"
    encrypt      = true
    use_lockfile = true # Native S3 locking (Terraform v1.10+)
  }
}

# NOTE: The state key uses "persistent/terraform.tfstate" to keep it separate
# from the ephemeral root's "terraform.tfstate". The ephemeral root references
# this state via a terraform_remote_state data source.
