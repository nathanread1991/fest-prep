# Variables for the Persistent Terraform Module

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "eu-west-2"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "festival-playlist"
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be 'dev' or 'prod'."
  }
}

variable "github_repository" {
  description = "GitHub repository in the format 'owner/repo' for OIDC trust policy"
  type        = string
}

variable "terraform_state_bucket" {
  description = "Name of the S3 bucket used for Terraform state storage"
  type        = string
  default     = "festival-playlist-terraform-state"
}
