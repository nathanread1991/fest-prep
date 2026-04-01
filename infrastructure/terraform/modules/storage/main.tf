# Storage Module - S3 Buckets and ECR Repository
# This module creates S3 buckets for application data and logs, plus ECR for container images

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Get the current AWS account's canonical user ID for S3 ACL grants
data "aws_canonical_user_id" "current" {}
data "aws_caller_identity" "current" {}

# ============================================================================
# KMS Key for S3 Bucket Encryption
# ============================================================================

resource "aws_kms_key" "s3" {
  description             = "KMS key for S3 bucket encryption - ${var.project_name}-${var.environment}"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      }
    ]
  })

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-s3-kms"
    }
  )
}

resource "aws_kms_alias" "s3" {
  name          = "alias/${var.project_name}-${var.environment}-s3"
  target_key_id = aws_kms_key.s3.key_id
}

# ============================================================================
# S3 Bucket - Application Data
# ============================================================================

# S3 bucket for application data (user uploads, backups, etc.)
resource "aws_s3_bucket" "app_data" {
  #checkov:skip=CKV2_AWS_62:Event notifications not required for this bucket
  #checkov:skip=CKV_AWS_144:Cross-region replication not required for dev
  #checkov:skip=CKV_AWS_18:Access logging configured via aws_s3_bucket_logging resource
  bucket        = "${var.project_name}-${var.environment}-app-data"
  force_destroy = true

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-app-data"
      Purpose     = "Application data storage"
      Persistence = "true"
    }
  )

  lifecycle {
    # Persistent resource - survives teardown/rebuild cycles
    # Set to true in production to prevent accidental deletion
    prevent_destroy = false
  }
}

# Enable versioning on app-data bucket
resource "aws_s3_bucket_versioning" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Enable server-side encryption (KMS) on app-data bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

# Block all public access on app-data bucket
resource "aws_s3_bucket_public_access_block" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable S3 Intelligent-Tiering on app-data bucket
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


# ============================================================================
# S3 Bucket - CloudFront Logs
# ============================================================================

# S3 bucket for CloudFront access logs
resource "aws_s3_bucket" "cloudfront_logs" {
  #checkov:skip=CKV2_AWS_62:Event notifications not required for this bucket
  #checkov:skip=CKV_AWS_144:Cross-region replication not required for dev
  #checkov:skip=CKV_AWS_18:This is the logging destination bucket
  bucket        = "${var.project_name}-${var.environment}-cloudfront-logs"
  force_destroy = true

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-cloudfront-logs"
      Purpose     = "CloudFront access logs"
      Persistence = "true"
    }
  )

  lifecycle {
    # Persistent resource - survives teardown/rebuild cycles
    prevent_destroy = false
  }
}

# Enable server-side encryption (KMS) on logs bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

# Block all public access on logs bucket
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

# Lifecycle policy for logs bucket (30-day expiration)
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

# Grant CloudFront log delivery permissions
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

  depends_on = [
    aws_s3_bucket_ownership_controls.cloudfront_logs
  ]
}

# Ownership controls for CloudFront logs bucket
resource "aws_s3_bucket_ownership_controls" "cloudfront_logs" {
  #checkov:skip=CKV2_AWS_65:BucketOwnerPreferred required for CloudFront log delivery
  bucket = aws_s3_bucket.cloudfront_logs.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}



# ============================================================================
# ECR Repository - Container Images
# ============================================================================

# ECR repository for application container images
resource "aws_ecr_repository" "app" {
  #checkov:skip=CKV_AWS_136:Basic scanning enabled, enhanced scanning configured at registry level
  name                 = "${var.project_name}-${var.environment}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  # Enable image scanning on push
  image_scanning_configuration {
    scan_on_push = true
  }

  # Enable encryption at rest
  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-${var.environment}-ecr"
      Purpose     = "Container image storage"
      Persistence = "true"
    }
  )

  lifecycle {
    # Persistent resource - survives teardown/rebuild cycles
    prevent_destroy = false
  }
}

# ECR lifecycle policy - keep last 10 images
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
# S3 Bucket Policies
# ============================================================================

# Bucket policy for app-data bucket - CloudFront OAI access
resource "aws_s3_bucket_policy" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      # Allow CloudFront OAI access if OAI ARN is provided
      var.cloudfront_oai_iam_arn != null ? [
        {
          Sid    = "AllowCloudFrontOAIAccess"
          Effect = "Allow"
          Principal = {
            AWS = var.cloudfront_oai_iam_arn
          }
          Action   = "s3:GetObject"
          Resource = "${aws_s3_bucket.app_data.arn}/*"
        }
      ] : [],
      # Allow CloudFront service access if distribution ARN is provided (alternative method)
      var.cloudfront_distribution_arn != null ? [
        {
          Sid    = "AllowCloudFrontServiceAccess"
          Effect = "Allow"
          Principal = {
            Service = "cloudfront.amazonaws.com"
          }
          Action   = "s3:GetObject"
          Resource = "${aws_s3_bucket.app_data.arn}/*"
          Condition = {
            StringEquals = {
              "AWS:SourceArn" = var.cloudfront_distribution_arn
            }
          }
        }
      ] : [],
      # Security policies (always applied)
      [
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
              "s3:x-amz-server-side-encryption" = "aws:kms"
            }
          }
        }
      ]
    )
  })

  depends_on = [
    aws_s3_bucket_public_access_block.app_data
  ]
}

# Bucket policy for CloudFront logs bucket - ALB log delivery
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
        Sid    = "AllowCloudFrontLogDelivery"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.cloudfront_logs.arn}/cloudfront-logs/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = var.cloudfront_distribution_arn != null ? var.cloudfront_distribution_arn : ""
          }
        }
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
      },
      {
        Sid       = "DenyPublicAccess"
        Effect    = "Deny"
        Principal = "*"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.cloudfront_logs.arn,
          "${aws_s3_bucket.cloudfront_logs.arn}/*"
        ]
        Condition = {
          StringNotEquals = {
            "aws:PrincipalServiceName" = [
              "elasticloadbalancing.amazonaws.com",
              "cloudfront.amazonaws.com"
            ]
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
