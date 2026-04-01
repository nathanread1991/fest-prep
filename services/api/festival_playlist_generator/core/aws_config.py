"""AWS-specific configuration for loading secrets and service endpoints.

This module provides functions to load configuration from AWS Secrets Manager
when running in an AWS environment (ECS Fargate). In local/Docker environments,
it falls back to environment variables and .env file defaults.

The ECS task definitions inject most secrets as environment variables via
Secrets Manager references. This module handles:
- Runtime secret loading for secrets not injected via ECS task definition
- Environment detection (local vs AWS)
- Environment variable validation for required AWS settings
- Connection string construction for RDS and ElastiCache
"""

import json
import logging
import os
from functools import lru_cache
from typing import Any, Dict

logger = logging.getLogger(__name__)


def is_aws_environment() -> bool:
    """Detect if running in an AWS ECS environment.

    Checks for ECS-specific environment variables that are automatically
    set by the Fargate runtime.

    Returns:
        True if running in AWS ECS, False otherwise.
    """
    return bool(
        os.environ.get("ECS_CONTAINER_METADATA_URI_V4")
        or os.environ.get("ECS_CONTAINER_METADATA_URI")
        or os.environ.get("AWS_EXECUTION_ENV")
    )


def get_aws_region() -> str:
    """Get the AWS region from environment.

    Returns:
        AWS region string, defaults to eu-west-2.
    """
    return os.environ.get("AWS_REGION", "eu-west-2")


def _get_secrets_client() -> Any:
    """Create a boto3 Secrets Manager client.

    Returns:
        boto3 Secrets Manager client instance.

    Raises:
        ImportError: If boto3 is not installed.
    """
    try:
        import boto3

        return boto3.client(
            "secretsmanager",
            region_name=get_aws_region(),
        )
    except ImportError:
        logger.error("boto3 is not installed. " "Install it with: pip install boto3")
        raise


def get_secret(secret_name: str) -> Dict[str, Any]:
    """Load a secret from AWS Secrets Manager.

    Retrieves and parses a JSON secret from Secrets Manager.
    Results are not cached to ensure fresh values after rotation.

    Args:
        secret_name: The name or ARN of the secret.

    Returns:
        Parsed JSON secret as a dictionary.

    Raises:
        RuntimeError: If the secret cannot be retrieved or parsed.
    """
    try:
        client = _get_secrets_client()
        response: Dict[str, Any] = client.get_secret_value(SecretId=secret_name)
        secret_string = response.get("SecretString", "")
        if not secret_string:
            raise RuntimeError(f"Secret '{secret_name}' has no SecretString value")
        result: Dict[str, Any] = json.loads(secret_string)
        return result
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Secret '{secret_name}' is not valid JSON: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve secret '{secret_name}': {e}") from e


def get_database_url_from_secret(secret_name: str) -> str:
    """Build a PostgreSQL connection URL from a Secrets Manager secret.

    The secret is expected to contain a 'url' key with the full
    connection string, as created by the Terraform database module.

    Args:
        secret_name: The name or ARN of the database credentials secret.

    Returns:
        PostgreSQL connection URL string.

    Raises:
        RuntimeError: If the secret cannot be retrieved or is missing 'url'.
    """
    secret = get_secret(secret_name)
    url = secret.get("url")
    if url:
        return str(url)

    # Fallback: construct from individual fields
    host = secret.get("host", "")
    port = secret.get("port", 5432)
    username = secret.get("username", "")
    password = secret.get("password", "")
    dbname = secret.get("dbname", "")

    if not all([host, username, password, dbname]):
        raise RuntimeError(
            f"Secret '{secret_name}' missing required database fields "
            "(url, or host/username/password/dbname)"
        )

    return f"postgresql://{username}:{password}@{host}:{port}/{dbname}"


def get_redis_url_from_secret(secret_name: str) -> str:
    """Build a Redis connection URL from a Secrets Manager secret.

    The secret is expected to contain a 'url' key with the full
    connection string, as created by the Terraform cache module.

    Args:
        secret_name: The name or ARN of the Redis URL secret.

    Returns:
        Redis connection URL string.

    Raises:
        RuntimeError: If the secret cannot be retrieved or is missing 'url'.
    """
    secret = get_secret(secret_name)
    url = secret.get("url")
    if url:
        return str(url)

    # Fallback: construct from individual fields
    host = secret.get("host", "")
    port = secret.get("port", 6379)
    password = secret.get("password")
    ssl = secret.get("ssl", False)

    scheme = "rediss" if ssl else "redis"
    if password:
        return f"{scheme}://:{password}@{host}:{port}"
    return f"{scheme}://{host}:{port}"


@lru_cache(maxsize=1)
def get_environment_name() -> str:
    """Get the current deployment environment name.

    Returns:
        Environment name (e.g., 'dev', 'staging', 'prod').
        Defaults to 'local' when not in AWS.
    """
    return os.environ.get("ENVIRONMENT", "local")


class AWSEnvironmentError(Exception):
    """Raised when required AWS environment variables are missing."""


def validate_aws_environment() -> None:
    """Validate that required environment variables are set for AWS deployment.

    In AWS (ECS), secrets are injected as environment variables by the
    task definition. This function verifies the critical ones are present.

    Raises:
        AWSEnvironmentError: If required variables are missing.
    """
    if not is_aws_environment():
        logger.debug("Not running in AWS environment, skipping validation")
        return

    required_vars = [
        "DATABASE_URL",
        "REDIS_URL",
    ]

    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing:
        raise AWSEnvironmentError(
            f"Missing required environment variables for AWS: "
            f"{', '.join(missing)}. "
            f"Ensure ECS task definition injects these from "
            f"Secrets Manager."
        )

    logger.info(
        "AWS environment validation passed. "
        f"Environment: {get_environment_name()}, "
        f"Region: {get_aws_region()}"
    )
