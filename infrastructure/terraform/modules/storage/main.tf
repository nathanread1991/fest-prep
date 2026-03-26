# Storage Module - S3 Buckets and ECR Repository
# This module creates S3 buckets for application data and logs, plus ECR for container images

# ============================================================================
# S3 Bucket - Application Data
# ============================================================================

# S3 bucket for application data (user uploads, backups, etc.)
resource "aws_s3_bucket" "app_data" {
  bucket = "${var.project_name}-${var.environment}-app-data"

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

# Enable server-side encryption (AES256) on app-data bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
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


# ============================================================================
# S3 Bucket - CloudFront Logs
# ============================================================================

# S3 bucket for CloudFront access logs
resource "aws_s3_bucket" "cloudfront_logs" {
  bucket = "${var.project_name}-${var.environment}-cloudfront-logs"

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

# Enable server-side encryption (AES256) on logs bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
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

# Lifecycle policy for logs bucket (30-day expiration)
resource "aws_s3_bucket_lifecycle_configuration" "cloudfront_logs" {
  bucket = aws_s3_bucket.cloudfront_logs.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    filter {}

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
  acl    = "log-delivery-write"

  depends_on = [
    aws_s3_bucket_ownership_controls.cloudfront_logs
  ]
}

# Ownership controls for CloudFront logs bucket
resource "aws_s3_bucket_ownership_controls" "cloudfront_logs" {
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
  name                 = "${var.project_name}-${var.environment}"
  image_tag_mutability = "MUTABLE"

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
              "s3:x-amz-server-side-encryption" = "AES256"
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
