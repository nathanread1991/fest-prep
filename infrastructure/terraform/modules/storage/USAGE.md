# Storage Module - Usage Guide

This guide provides practical examples and best practices for using the storage module.

## Quick Start

### Minimal Configuration

```hcl
module "storage" {
  source = "./modules/storage"

  project_name = "festival-app"
  environment  = "dev"
  common_tags = {
    Project     = "Festival Playlist Generator"
    Environment = "dev"
    ManagedBy   = "Terraform"
  }
}
```

### Full Configuration with CloudFront

```hcl
module "storage" {
  source = "./modules/storage"

  project_name                = "festival-app"
  environment                 = "dev"
  cloudfront_distribution_arn = module.cdn.cloudfront_distribution_arn

  common_tags = {
    Project     = "Festival Playlist Generator"
    Environment = "dev"
    ManagedBy   = "Terraform"
    CostCenter  = "Engineering"
  }
}
```

## Integration Examples

### Using with ECS Task Definition

```hcl
# Storage module
module "storage" {
  source = "./modules/storage"

  project_name = var.project_name
  environment  = var.environment
  common_tags  = var.common_tags
}

# ECS task definition using ECR image
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project_name}-${var.environment}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode            = "awsvpc"
  cpu                     = "256"
  memory                  = "512"

  container_definitions = jsonencode([{
    name  = "api"
    image = "${module.storage.ecr_repository_url}:latest"

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    environment = [
      {
        name  = "S3_BUCKET"
        value = module.storage.app_data_bucket_name
      }
    ]
  }])
}
```

### Using with CloudFront Distribution

```hcl
# Storage module
module "storage" {
  source = "./modules/storage"

  project_name = var.project_name
  environment  = var.environment
  common_tags  = var.common_tags
}

# CloudFront Origin Access Identity
resource "aws_cloudfront_origin_access_identity" "app_data" {
  comment = "Access identity for ${var.project_name} ${var.environment} app data"
}

# CloudFront distribution with S3 origin
resource "aws_cloudfront_distribution" "main" {
  enabled = true

  # S3 origin for static assets
  origin {
    domain_name = module.storage.app_data_bucket_regional_domain_name
    origin_id   = "S3-app-data"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.app_data.cloudfront_access_identity_path
    }
  }

  # Cache behavior for static assets
  ordered_cache_behavior {
    path_pattern     = "/static/*"
    target_origin_id = "S3-app-data"

    allowed_methods = ["GET", "HEAD", "OPTIONS"]
    cached_methods  = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 86400  # 1 day
    max_ttl                = 31536000  # 1 year
    compress               = true
  }

  # Logging configuration
  logging_config {
    bucket = module.storage.cloudfront_logs_bucket_domain_name
    prefix = "cloudfront-logs/"
  }

  # ... other configuration
}

# Update storage module with CloudFront ARN
module "storage" {
  source = "./modules/storage"

  project_name                = var.project_name
  environment                 = var.environment
  common_tags                 = var.common_tags
  cloudfront_distribution_arn = aws_cloudfront_distribution.main.arn
}
```

### Using with Application Load Balancer Logs

```hcl
# Storage module
module "storage" {
  source = "./modules/storage"

  project_name = var.project_name
  environment  = var.environment
  common_tags  = var.common_tags
}

# ALB with access logs
resource "aws_lb" "main" {
  name               = "${var.project_name}-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  # Enable access logs
  access_logs {
    bucket  = module.storage.cloudfront_logs_bucket_name
    prefix  = "alb-logs"
    enabled = true
  }

  tags = var.common_tags
}
```

## Working with ECR

### Building and Pushing Docker Images

```bash
# Authenticate Docker with ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  $(terraform output -raw ecr_repository_url | cut -d'/' -f1)

# Build Docker image
docker build -t festival-app:latest .

# Tag image for ECR
docker tag festival-app:latest \
  $(terraform output -raw ecr_repository_url):latest

# Push image to ECR
docker push $(terraform output -raw ecr_repository_url):latest
```

### Viewing Image Scan Results

```bash
# Get scan findings for latest image
aws ecr describe-image-scan-findings \
  --repository-name $(terraform output -raw ecr_repository_name) \
  --image-id imageTag=latest \
  --region us-east-1

# List all images with scan status
aws ecr describe-images \
  --repository-name $(terraform output -raw ecr_repository_name) \
  --region us-east-1
```

## Working with S3 Buckets

### Uploading Files to App Data Bucket

```bash
# Upload a file
aws s3 cp local-file.txt \
  s3://$(terraform output -raw app_data_bucket_name)/path/to/file.txt

# Upload a directory
aws s3 sync ./local-directory \
  s3://$(terraform output -raw app_data_bucket_name)/path/to/directory/

# List files
aws s3 ls s3://$(terraform output -raw app_data_bucket_name)/
```

### Viewing S3 Intelligent-Tiering Status

```bash
# Get Intelligent-Tiering configuration
aws s3api get-bucket-intelligent-tiering-configuration \
  --bucket $(terraform output -raw app_data_bucket_name) \
  --id EntireBucket

# Get object storage class
aws s3api head-object \
  --bucket $(terraform output -raw app_data_bucket_name) \
  --key path/to/file.txt
```

### Viewing CloudFront Logs

```bash
# List log files
aws s3 ls s3://$(terraform output -raw cloudfront_logs_bucket_name)/cloudfront-logs/

# Download logs
aws s3 sync \
  s3://$(terraform output -raw cloudfront_logs_bucket_name)/cloudfront-logs/ \
  ./local-logs/
```

## IAM Permissions

### ECS Task Role for S3 Access

```hcl
# IAM policy for ECS tasks to access S3
resource "aws_iam_role_policy" "ecs_s3_access" {
  name = "${var.project_name}-${var.environment}-ecs-s3-access"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          module.storage.app_data_bucket_arn,
          "${module.storage.app_data_bucket_arn}/*"
        ]
      }
    ]
  })
}
```

### ECS Execution Role for ECR Access

```hcl
# IAM policy for ECS execution role to pull images from ECR
resource "aws_iam_role_policy" "ecs_ecr_access" {
  name = "${var.project_name}-${var.environment}-ecs-ecr-access"
  role = aws_iam_role.ecs_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
}
```

## Cost Optimization Tips

### S3 Intelligent-Tiering
- Automatically moves objects between access tiers based on usage
- No retrieval fees (unlike Glacier)
- Small monthly monitoring fee per object
- Best for objects > 128 KB that are accessed unpredictably

### Lifecycle Policies
- CloudFront logs automatically deleted after 30 days
- Consider adding lifecycle policies for app data if needed:

```hcl
resource "aws_s3_bucket_lifecycle_configuration" "app_data_custom" {
  bucket = module.storage.app_data_bucket_name

  rule {
    id     = "archive-old-backups"
    status = "Enabled"

    filter {
      prefix = "backups/"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}
```

### ECR Image Management
- Lifecycle policy keeps last 10 images
- Consider tagging images with semantic versions
- Delete unused images manually if needed:

```bash
# List images
aws ecr list-images \
  --repository-name $(terraform output -raw ecr_repository_name)

# Delete specific image
aws ecr batch-delete-image \
  --repository-name $(terraform output -raw ecr_repository_name) \
  --image-ids imageTag=old-tag
```

## Security Best Practices

### Bucket Policies
- All buckets block public access by default
- HTTPS-only access enforced
- Encrypted uploads required
- CloudFront access via bucket policy (not public)

### ECR Security
- Image scanning enabled on push
- Review scan findings regularly
- Use specific image tags (not just `latest`)
- Implement image signing for production

### Access Control
- Use IAM roles for service access (not IAM users)
- Follow principle of least privilege
- Enable CloudTrail for audit logging
- Monitor S3 access logs

## Troubleshooting

### Bucket Already Exists
**Error**: `BucketAlreadyExists` or `BucketAlreadyOwnedByYou`

**Solution**: This is expected for persistent buckets. If the bucket exists from a previous run, Terraform will import it. If the name is taken by another account, change `project_name`.

### CloudFront Access Denied
**Error**: CloudFront returns 403 when accessing S3 objects

**Solutions**:
1. Verify `cloudfront_distribution_arn` is set correctly
2. Check bucket policy is applied: `aws s3api get-bucket-policy --bucket {bucket-name}`
3. Verify CloudFront origin configuration uses OAI

### ECR Push Permission Denied
**Error**: `denied: User: ... is not authorized to perform: ecr:PutImage`

**Solutions**:
1. Authenticate Docker: `aws ecr get-login-password | docker login ...`
2. Verify IAM permissions for ECR operations
3. Check repository exists: `aws ecr describe-repositories`

### S3 Upload Fails
**Error**: `Access Denied` when uploading to S3

**Solutions**:
1. Verify IAM permissions for S3 operations
2. Ensure HTTPS is used (HTTP is denied by bucket policy)
3. Verify encryption is specified: `--sse AES256`

## Monitoring and Alerts

### CloudWatch Metrics

```hcl
# S3 bucket size metric
resource "aws_cloudwatch_metric_alarm" "s3_bucket_size" {
  alarm_name          = "${var.project_name}-${var.environment}-s3-size-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BucketSizeBytes"
  namespace           = "AWS/S3"
  period              = "86400"  # 1 day
  statistic           = "Average"
  threshold           = 10737418240  # 10 GB
  alarm_description   = "S3 bucket size is above 10 GB"

  dimensions = {
    BucketName  = module.storage.app_data_bucket_name
    StorageType = "StandardStorage"
  }
}

# ECR image count metric
resource "aws_cloudwatch_metric_alarm" "ecr_image_count" {
  alarm_name          = "${var.project_name}-${var.environment}-ecr-images-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "RepositoryImageCount"
  namespace           = "AWS/ECR"
  period              = "86400"  # 1 day
  statistic           = "Average"
  threshold           = 15
  alarm_description   = "ECR repository has more than 15 images"

  dimensions = {
    RepositoryName = module.storage.ecr_repository_name
  }
}
```

## Additional Resources

- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [AWS ECR Documentation](https://docs.aws.amazon.com/ecr/)
- [S3 Intelligent-Tiering](https://aws.amazon.com/s3/storage-classes/intelligent-tiering/)
- [ECR Image Scanning](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning.html)
