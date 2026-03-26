# ============================================================================
# ECS Compute Module - Main Configuration
# ============================================================================
# This module creates:
# - ECS Fargate cluster
# - IAM roles for ECS task execution and task runtime
# - ECS task definitions for API and Worker services
# - ECS services with auto-scaling
# - Application Load Balancer with target groups
# ============================================================================

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ============================================================================
# Data Sources
# ============================================================================

data "aws_region" "current" {}

data "aws_caller_identity" "current" {}

# ============================================================================
# ECS Cluster
# ============================================================================

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}-cluster"

  setting {
    name  = "containerInsights"
    value = var.enable_container_insights ? "enabled" : "disabled"
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-ecs-cluster"
    }
  )
}

# Enable ECS Cluster Capacity Providers
resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1
  }
}

# ============================================================================
# IAM Role - ECS Task Execution Role
# ============================================================================
# This role is used by ECS to:
# - Pull container images from ECR
# - Write logs to CloudWatch
# - Read secrets from Secrets Manager
# ============================================================================

resource "aws_iam_role" "ecs_task_execution_role" {
  name               = "${var.project_name}-${var.environment}-ecs-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume_role.json

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-ecs-execution-role"
    }
  )
}

data "aws_iam_policy_document" "ecs_task_execution_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Custom policy for Secrets Manager access
resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name   = "${var.project_name}-${var.environment}-ecs-execution-secrets"
  role   = aws_iam_role.ecs_task_execution_role.id
  policy = data.aws_iam_policy_document.ecs_task_execution_secrets.json
}

data "aws_iam_policy_document" "ecs_task_execution_secrets" {
  statement {
    effect = "Allow"

    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]

    resources = var.secrets_arns
  }

  # Allow decryption of secrets if they're encrypted with KMS
  statement {
    effect = "Allow"

    actions = [
      "kms:Decrypt",
      "kms:DescribeKey"
    ]

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${data.aws_region.current.name}.amazonaws.com"]
    }
  }
}

# ============================================================================
# IAM Role - ECS Task Role
# ============================================================================
# This role is used by the application running in the container to:
# - Access S3 buckets
# - Access RDS (via security groups, not IAM)
# - Access ElastiCache (via security groups, not IAM)
# - Publish CloudWatch metrics
# - Send X-Ray traces
# ============================================================================

resource "aws_iam_role" "ecs_task_role" {
  name               = "${var.project_name}-${var.environment}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-ecs-task-role"
    }
  )
}

data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# Custom policy for S3 access
resource "aws_iam_role_policy" "ecs_task_s3" {
  name   = "${var.project_name}-${var.environment}-ecs-task-s3"
  role   = aws_iam_role.ecs_task_role.id
  policy = data.aws_iam_policy_document.ecs_task_s3.json
}

data "aws_iam_policy_document" "ecs_task_s3" {
  statement {
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ]

    resources = [
      var.app_data_bucket_arn,
      "${var.app_data_bucket_arn}/*"
    ]
  }
}

# Custom policy for CloudWatch metrics
resource "aws_iam_role_policy" "ecs_task_cloudwatch" {
  name   = "${var.project_name}-${var.environment}-ecs-task-cloudwatch"
  role   = aws_iam_role.ecs_task_role.id
  policy = data.aws_iam_policy_document.ecs_task_cloudwatch.json
}

data "aws_iam_policy_document" "ecs_task_cloudwatch" {
  statement {
    effect = "Allow"

    actions = [
      "cloudwatch:PutMetricData"
    ]

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["${var.project_name}/${var.environment}"]
    }
  }
}

# Custom policy for X-Ray tracing
resource "aws_iam_role_policy" "ecs_task_xray" {
  name   = "${var.project_name}-${var.environment}-ecs-task-xray"
  role   = aws_iam_role.ecs_task_role.id
  policy = data.aws_iam_policy_document.ecs_task_xray.json
}

data "aws_iam_policy_document" "ecs_task_xray" {
  statement {
    effect = "Allow"

    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "xray:GetSamplingRules",
      "xray:GetSamplingTargets",
      "xray:GetSamplingStatisticSummaries"
    ]

    resources = ["*"]
  }
}

# Optional: Allow reading secrets at runtime (in addition to execution role)
resource "aws_iam_role_policy" "ecs_task_secrets" {
  count = var.allow_task_role_secrets_access ? 1 : 0

  name   = "${var.project_name}-${var.environment}-ecs-task-secrets"
  role   = aws_iam_role.ecs_task_role.id
  policy = data.aws_iam_policy_document.ecs_task_secrets[0].json
}

data "aws_iam_policy_document" "ecs_task_secrets" {
  count = var.allow_task_role_secrets_access ? 1 : 0

  statement {
    effect = "Allow"

    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]

    resources = var.secrets_arns
  }
}


# ============================================================================
# CloudWatch Log Groups
# ============================================================================

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project_name}-${var.environment}/api"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-api-logs"
    }
  )
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project_name}-${var.environment}/worker"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-worker-logs"
    }
  )
}

# ============================================================================
# ECS Task Definition - API Service
# ============================================================================

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project_name}-${var.environment}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${var.ecr_repository_url}:${var.api_image_tag}"
      essential = true

      portMappings = [
        {
          containerPort = var.api_container_port
          protocol      = "tcp"
        }
      ]

      # Environment variables (non-sensitive)
      environment = concat(
        [
          {
            name  = "ENVIRONMENT"
            value = var.environment
          },
          {
            name  = "AWS_REGION"
            value = data.aws_region.current.name
          },
          {
            name  = "PORT"
            value = tostring(var.api_container_port)
          },
          {
            name  = "LOG_LEVEL"
            value = var.environment == "prod" ? "INFO" : "DEBUG"
          }
        ],
        [
          for key, value in var.api_environment_variables : {
            name  = key
            value = value
          }
        ]
      )

      # Secrets from Secrets Manager
      secrets = concat(
        [
          {
            name      = "DATABASE_URL"
            valueFrom = "${var.db_secret_arn}:url::"
          },
          {
            name      = "REDIS_URL"
            valueFrom = "${var.redis_secret_arn}:url::"
          }
        ],
        var.spotify_secret_arn != "" ? [
          {
            name      = "SPOTIFY_CLIENT_ID"
            valueFrom = "${var.spotify_secret_arn}:client_id::"
          },
          {
            name      = "SPOTIFY_CLIENT_SECRET"
            valueFrom = "${var.spotify_secret_arn}:client_secret::"
          }
        ] : [],
        var.jwt_secret_arn != "" ? [
          {
            name      = "JWT_SECRET_KEY"
            valueFrom = "${var.jwt_secret_arn}:secret_key::"
          }
        ] : [],
        var.setlistfm_secret_arn != "" ? [
          {
            name      = "SETLISTFM_API_KEY"
            valueFrom = "${var.setlistfm_secret_arn}:api_key::"
          }
        ] : []
      )

      # CloudWatch Logs configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "api"
        }
      }

      # Health check
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:${var.api_container_port}${var.api_health_check_path} || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }

      # Resource limits
      ulimits = [
        {
          name      = "nofile"
          softLimit = 65536
          hardLimit = 65536
        }
      ]
    }
  ])

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-api-task"
    }
  )
}


# ============================================================================
# ECS Task Definition - Worker Service
# ============================================================================

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-${var.environment}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = "${var.ecr_repository_url}:${var.worker_image_tag}"
      essential = true

      # Celery worker command
      command = [
        "celery",
        "-A",
        "festival_playlist_generator.celery_app",
        "worker",
        "--loglevel=info",
        "--concurrency=2"
      ]

      # Environment variables (non-sensitive)
      environment = concat(
        [
          {
            name  = "ENVIRONMENT"
            value = var.environment
          },
          {
            name  = "AWS_REGION"
            value = data.aws_region.current.name
          },
          {
            name  = "LOG_LEVEL"
            value = var.environment == "prod" ? "INFO" : "DEBUG"
          },
          {
            name  = "CELERY_BROKER_URL"
            value = "redis://placeholder" # Will be overridden by secret
          },
          {
            name  = "CELERY_RESULT_BACKEND"
            value = "redis://placeholder" # Will be overridden by secret
          }
        ],
        [
          for key, value in var.worker_environment_variables : {
            name  = key
            value = value
          }
        ]
      )

      # Secrets from Secrets Manager
      secrets = concat(
        [
          {
            name      = "DATABASE_URL"
            valueFrom = "${var.db_secret_arn}:url::"
          },
          {
            name      = "REDIS_URL"
            valueFrom = "${var.redis_secret_arn}:url::"
          },
          {
            name      = "CELERY_BROKER_URL"
            valueFrom = "${var.redis_secret_arn}:url::"
          },
          {
            name      = "CELERY_RESULT_BACKEND"
            valueFrom = "${var.redis_secret_arn}:url::"
          }
        ],
        var.spotify_secret_arn != "" ? [
          {
            name      = "SPOTIFY_CLIENT_ID"
            valueFrom = "${var.spotify_secret_arn}:client_id::"
          },
          {
            name      = "SPOTIFY_CLIENT_SECRET"
            valueFrom = "${var.spotify_secret_arn}:client_secret::"
          }
        ] : [],
        var.setlistfm_secret_arn != "" ? [
          {
            name      = "SETLISTFM_API_KEY"
            valueFrom = "${var.setlistfm_secret_arn}:api_key::"
          }
        ] : []
      )

      # CloudWatch Logs configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "worker"
        }
      }

      # Resource limits
      ulimits = [
        {
          name      = "nofile"
          softLimit = 65536
          hardLimit = 65536
        }
      ]
    }
  ])

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-worker-task"
    }
  )
}


# ============================================================================
# ECS Service - API
# ============================================================================

resource "aws_ecs_service" "api" {
  name            = "${var.project_name}-${var.environment}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [var.ecs_tasks_security_group_id]
    assign_public_ip = true # Required for tasks in public subnets to pull images and access internet
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = var.api_container_port
  }

  # Wait for ALB to be ready before creating service
  depends_on = [
    aws_lb_listener.http,
    aws_lb_target_group.api
  ]

  # Enable ECS managed tags
  enable_ecs_managed_tags = true
  propagate_tags          = "SERVICE"

  # Health check grace period (time to wait before starting health checks)
  health_check_grace_period_seconds = 60

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-api-service"
    }
  )

  lifecycle {
    ignore_changes = [desired_count] # Allow auto-scaling to manage desired count
  }
}

# ============================================================================
# ECS Service - Worker
# ============================================================================

resource "aws_ecs_service" "worker" {
  name            = "${var.project_name}-${var.environment}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count

  # Use FARGATE_SPOT for cost savings (70% cheaper)
  capacity_provider_strategy {
    capacity_provider = var.worker_use_spot ? "FARGATE_SPOT" : "FARGATE"
    weight            = 100
    base              = var.worker_desired_count > 0 ? 1 : 0
  }

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [var.ecs_tasks_security_group_id]
    assign_public_ip = true # Required for tasks in public subnets
  }

  # Enable ECS managed tags
  enable_ecs_managed_tags = true
  propagate_tags          = "SERVICE"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-worker-service"
    }
  )

  lifecycle {
    ignore_changes = [desired_count] # Allow auto-scaling to manage desired count
  }
}

# ============================================================================
# Auto-Scaling - API Service
# ============================================================================

resource "aws_appautoscaling_target" "api" {
  count = var.api_enable_auto_scaling ? 1 : 0

  max_capacity       = var.api_max_capacity
  min_capacity       = var.api_min_capacity
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# Auto-scaling policy based on CPU utilization
resource "aws_appautoscaling_policy" "api_cpu" {
  count = var.api_enable_auto_scaling ? 1 : 0

  name               = "${var.project_name}-${var.environment}-api-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api[0].resource_id
  scalable_dimension = aws_appautoscaling_target.api[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.api[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }

    target_value       = var.api_cpu_target
    scale_in_cooldown  = 300 # 5 minutes
    scale_out_cooldown = 60  # 1 minute
  }
}

# Auto-scaling policy based on memory utilization
resource "aws_appautoscaling_policy" "api_memory" {
  count = var.api_enable_auto_scaling ? 1 : 0

  name               = "${var.project_name}-${var.environment}-api-memory-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api[0].resource_id
  scalable_dimension = aws_appautoscaling_target.api[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.api[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }

    target_value       = var.api_memory_target
    scale_in_cooldown  = 300 # 5 minutes
    scale_out_cooldown = 60  # 1 minute
  }
}


# ============================================================================
# Application Load Balancer
# ============================================================================

resource "aws_lb" "main" {
  name               = var.alb_name != null ? var.alb_name : "${var.project_name}-${var.environment}-alb"
  internal           = var.alb_internal
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection       = var.alb_enable_deletion_protection
  enable_http2                     = var.alb_enable_http2
  enable_cross_zone_load_balancing = var.alb_enable_cross_zone_load_balancing
  idle_timeout                     = var.alb_idle_timeout

  # Access logs (optional)
  dynamic "access_logs" {
    for_each = var.alb_enable_access_logs ? [1] : []
    content {
      bucket  = var.alb_access_logs_bucket
      prefix  = var.alb_access_logs_prefix
      enabled = true
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-alb"
    }
  )
}

# ============================================================================
# Target Group for API Service
# ============================================================================

resource "aws_lb_target_group" "api" {
  name        = "${var.project_name}-${var.environment}-api-tg"
  port        = var.api_container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip" # Required for Fargate

  # Health check configuration
  health_check {
    enabled             = true
    healthy_threshold   = var.api_health_check_healthy_threshold
    unhealthy_threshold = var.api_health_check_unhealthy_threshold
    timeout             = var.api_health_check_timeout
    interval            = var.api_health_check_interval
    path                = var.api_health_check_path
    protocol            = "HTTP"
    matcher             = "200-299"
  }

  # Deregistration delay (time to wait before removing targets)
  deregistration_delay = var.alb_deregistration_delay

  # Stickiness (optional, disabled by default for stateless API)
  stickiness {
    type    = "lb_cookie"
    enabled = false
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-api-target-group"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# ============================================================================
# HTTP Listener (Port 80)
# ============================================================================

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  # Default action: redirect to HTTPS if enabled, otherwise forward to target group
  default_action {
    type = var.enable_https_listener ? "redirect" : "forward"

    dynamic "redirect" {
      for_each = var.enable_https_listener ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }

    target_group_arn = var.enable_https_listener ? null : aws_lb_target_group.api.arn
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-http-listener"
    }
  )
}

# ============================================================================
# HTTPS Listener (Port 443) - Optional
# ============================================================================

resource "aws_lb_listener" "https" {
  count = var.enable_https_listener ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = var.ssl_policy
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-https-listener"
    }
  )
}
