# Persistent Terraform Module - Festival Playlist Generator
# Resources in this module survive daily teardown/provisioning cycles.
# All resources have prevent_destroy = true to guard against accidental deletion.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Persistence = "true"
    }
  }
}

# ============================================================================
# Data Sources
# ============================================================================

data "aws_canonical_user_id" "current" {}

# ============================================================================
# ECR Repository
# ============================================================================

resource "aws_ecr_repository" "app" {
  #checkov:skip=CKV_AWS_136:Basic scanning enabled, enhanced scanning configured at registry level
  name                 = "${var.project_name}-${var.environment}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-ecr"
    Purpose     = "Container image storage"
    Persistence = "true"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ============================================================================
# S3 Bucket - Application Data
# ============================================================================

resource "aws_s3_bucket" "app_data" {
  #checkov:skip=CKV2_AWS_62:Event notifications not required for this bucket
  #checkov:skip=CKV_AWS_144:Cross-region replication not required for dev
  #checkov:skip=CKV_AWS_145:AES256 server-side encryption is configured
  #checkov:skip=CKV_AWS_18:Access logging configured via aws_s3_bucket_logging resource
  bucket        = "${var.project_name}-${var.environment}-app-data"
  force_destroy = false

  tags = {
    Name        = "${var.project_name}-${var.environment}-app-data"
    Purpose     = "Application data storage"
    Persistence = "true"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_intelligent_tiering_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id
  name   = "EntireBucket"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90
  }

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180
  }
}

# Access logging for app-data bucket
resource "aws_s3_bucket_logging" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  target_bucket = aws_s3_bucket.cloudfront_logs.id
  target_prefix = "s3-access-logs/app-data/"
}

# Lifecycle configuration for app-data bucket
resource "aws_s3_bucket_lifecycle_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  rule {
    id     = "transition-old-objects"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

resource "aws_s3_bucket_policy" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.app_data.arn,
          "${aws_s3_bucket.app_data.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid       = "DenyUnencryptedObjectUploads"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.app_data.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "AES256"
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.app_data]
}

# ============================================================================
# S3 Bucket - CloudFront Logs
# ============================================================================

resource "aws_s3_bucket" "cloudfront_logs" {
  #checkov:skip=CKV2_AWS_62:Event notifications not required for this bucket
  #checkov:skip=CKV_AWS_144:Cross-region replication not required for dev
  #checkov:skip=CKV_AWS_145:AES256 server-side encryption is configured
  #checkov:skip=CKV_AWS_18:This is the logging destination bucket
  bucket        = "${var.project_name}-${var.environment}-cloudfront-logs"
  force_destroy = false

  tags = {
    Name        = "${var.project_name}-${var.environment}-cloudfront-logs"
    Purpose     = "CloudFront access logs"
    Persistence = "true"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning on cloudfront-logs bucket
resource "aws_s3_bucket_versioning" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "cloudfront_logs" {
  #checkov:skip=CKV2_AWS_65:BucketOwnerPreferred required for CloudFront log delivery
  bucket = aws_s3_bucket.cloudfront_logs.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  access_control_policy {
    owner {
      id = data.aws_canonical_user_id.current.id
    }

    grant {
      grantee {
        id   = data.aws_canonical_user_id.current.id
        type = "CanonicalUser"
      }
      permission = "FULL_CONTROL"
    }

    # CloudFront log delivery canonical user ID
    grant {
      grantee {
        id   = "c4c1ede66af53448b93c283ce9448c4ba468c9432aa01d700d3878632f77d2d0"
        type = "CanonicalUser"
      }
      permission = "FULL_CONTROL"
    }
  }

  depends_on = [aws_s3_bucket_ownership_controls.cloudfront_logs]
}

resource "aws_s3_bucket_policy" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowALBLogDelivery"
        Effect = "Allow"
        Principal = {
          Service = "elasticloadbalancing.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.cloudfront_logs.arn}/alb-logs/*"
      },
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.cloudfront_logs.arn,
          "${aws_s3_bucket.cloudfront_logs.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })

  depends_on = [
    aws_s3_bucket_public_access_block.cloudfront_logs,
    aws_s3_bucket_ownership_controls.cloudfront_logs
  ]
}

# ============================================================================
# Secrets Manager - Application Secrets
# ============================================================================

resource "random_password" "jwt_secret" {
  length  = 64
  special = true
}

resource "aws_secretsmanager_secret" "spotify" {
  #checkov:skip=CKV2_AWS_57:Secret rotation planned for future iteration
  #checkov:skip=CKV_AWS_149:Encrypted with AWS-managed KMS key
  name                    = "${var.project_name}-${var.environment}-spotify-credentials"
  description             = "Spotify API credentials (client_id, client_secret)"
  recovery_window_in_days = 0
  kms_key_id              = "alias/aws/secretsmanager"

  tags = {
    Name        = "${var.project_name}-${var.environment}-spotify"
    Persistence = "true"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_secretsmanager_secret_version" "spotify" {
  secret_id = aws_secretsmanager_secret.spotify.id
  secret_string = jsonencode({
    client_id     = "REPLACE_WITH_SPOTIFY_CLIENT_ID"
    client_secret = "REPLACE_WITH_SPOTIFY_CLIENT_SECRET"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "setlistfm" {
  #checkov:skip=CKV2_AWS_57:Secret rotation planned for future iteration
  #checkov:skip=CKV_AWS_149:Encrypted with AWS-managed KMS key
  name                    = "${var.project_name}-${var.environment}-setlistfm-api-key"
  description             = "Setlist.fm API key"
  recovery_window_in_days = 0
  kms_key_id              = "alias/aws/secretsmanager"

  tags = {
    Name        = "${var.project_name}-${var.environment}-setlistfm"
    Persistence = "true"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_secretsmanager_secret_version" "setlistfm" {
  secret_id = aws_secretsmanager_secret.setlistfm.id
  secret_string = jsonencode({
    api_key = "REPLACE_WITH_SETLISTFM_API_KEY"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "jwt" {
  #checkov:skip=CKV2_AWS_57:Secret rotation planned for future iteration
  #checkov:skip=CKV_AWS_149:Encrypted with AWS-managed KMS key
  name                    = "${var.project_name}-${var.environment}-jwt-secret"
  description             = "JWT signing key for authentication"
  recovery_window_in_days = 0
  kms_key_id              = "alias/aws/secretsmanager"

  tags = {
    Name        = "${var.project_name}-${var.environment}-jwt"
    Persistence = "true"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_secretsmanager_secret_version" "jwt" {
  secret_id = aws_secretsmanager_secret.jwt.id
  secret_string = jsonencode({
    secret_key = random_password.jwt_secret.result
  })
}

# ============================================================================
# GitHub Actions OIDC Provider and IAM Role
# ============================================================================

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = {
    Name = "${var.project_name}-github-oidc"
  }
}

data "aws_iam_policy_document" "github_oidc_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:*"]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${var.project_name}-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust.json

  tags = {
    Name = "${var.project_name}-github-actions-role"
  }
}

# ============================================================================
# IAM Policies for GitHub Actions Role
# ============================================================================

# ECR push/pull access
data "aws_iam_policy_document" "ecr_access" {
  statement {
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeRepositories",
      "ecr:ListImages",
    ]
    resources = [aws_ecr_repository.app.arn]
  }
}

resource "aws_iam_role_policy" "ecr_access" {
  name   = "ecr-access"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.ecr_access.json
}

# ECS deploy access
data "aws_iam_policy_document" "ecs_deploy" {
  #checkov:skip=CKV_AWS_111:ECS operations require wildcard resources
  #checkov:skip=CKV_AWS_356:ECS operations require wildcard resources
  statement {
    effect = "Allow"
    actions = [
      "ecs:DescribeServices",
      "ecs:UpdateService",
      "ecs:DescribeTaskDefinition",
      "ecs:RegisterTaskDefinition",
      "ecs:DeregisterTaskDefinition",
      "ecs:ListTasks",
      "ecs:DescribeTasks",
      "ecs:RunTask",
      "ecs:StopTask",
      "ecs:DescribeClusters",
      "ecs:ListServices",
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "iam:PassRole",
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }

  statement {
    effect = "Allow"
    actions = [
      "elasticloadbalancing:DescribeTargetGroups",
      "elasticloadbalancing:DescribeTargetHealth",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "ecs_deploy" {
  #checkov:skip=CKV_AWS_111:ECS operations require wildcard resources
  #checkov:skip=CKV_AWS_356:ECS operations require wildcard resources
  name   = "ecs-deploy"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.ecs_deploy.json
}

# Terraform state access (S3 + locking)
data "aws_iam_policy_document" "terraform_state" {
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketVersioning",
      "s3:GetBucketLocation",
    ]
    resources = [
      "arn:aws:s3:::${var.terraform_state_bucket}",
      "arn:aws:s3:::${var.terraform_state_bucket}/*",
    ]
  }
}

resource "aws_iam_role_policy" "terraform_state" {
  name   = "terraform-state"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.terraform_state.json
}

# Secrets Manager read access
data "aws_iam_policy_document" "secrets_read" {
  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
      "secretsmanager:ListSecrets",
    ]
    resources = [
      aws_secretsmanager_secret.spotify.arn,
      aws_secretsmanager_secret.setlistfm.arn,
      aws_secretsmanager_secret.jwt.arn,
    ]
  }
}

resource "aws_iam_role_policy" "secrets_read" {
  name   = "secrets-read"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.secrets_read.json
}

# RDS snapshot access (for teardown/provision workflows)
data "aws_iam_policy_document" "rds_snapshots" {
  #checkov:skip=CKV_AWS_111:RDS snapshot operations require wildcard resources
  #checkov:skip=CKV_AWS_356:RDS snapshot operations require wildcard resources
  statement {
    effect = "Allow"
    actions = [
      "rds:CreateDBClusterSnapshot",
      "rds:DescribeDBClusterSnapshots",
      "rds:DeleteDBClusterSnapshot",
      "rds:DescribeDBClusters",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "rds_snapshots" {
  #checkov:skip=CKV_AWS_111:RDS operations require wildcard resources
  #checkov:skip=CKV_AWS_356:RDS operations require wildcard resources
  name   = "rds-snapshots"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.rds_snapshots.json
}
