#!/usr/bin/env bash
# =============================================================================
# Run Database Migrations via ECS Run-Task
# =============================================================================
# Runs Alembic commands against the AWS database by launching a one-off
# ECS Fargate task using the migration task definition.
#
# Usage:
#   ./scripts/run-migrations.sh [command] [environment]
#
# Commands:
#   upgrade   - Run pending migrations (default)
#   stamp     - Stamp DB at head without running migrations
#   current   - Show current migration revision
#   history   - Show migration history
#
# Examples:
#   ./scripts/run-migrations.sh                  # upgrade head on dev
#   ./scripts/run-migrations.sh upgrade dev      # upgrade head on dev
#   ./scripts/run-migrations.sh stamp dev        # stamp head on dev
#   ./scripts/run-migrations.sh current dev      # show current revision
# =============================================================================

set -euo pipefail

COMMAND="${1:-upgrade}"
ENVIRONMENT="${2:-dev}"

PROJECT_NAME="festival-playlist"
AWS_REGION="eu-west-2"
CLUSTER_NAME="${PROJECT_NAME}-${ENVIRONMENT}-cluster"
TASK_FAMILY="${PROJECT_NAME}-${ENVIRONMENT}-migration"
LOG_GROUP="/ecs/${PROJECT_NAME}-${ENVIRONMENT}/migration"

# Map command to alembic args
case "${COMMAND}" in
    upgrade)  CMD_JSON='["alembic","upgrade","head"]' ;;
    stamp)    CMD_JSON='["alembic","stamp","head"]' ;;
    current)  CMD_JSON='["alembic","current"]' ;;
    history)  CMD_JSON='["alembic","history","--verbose"]' ;;
    *)
        echo "Unknown command: ${COMMAND}"
        echo "Valid commands: upgrade, stamp, current, history"
        exit 1
        ;;
esac

OVERRIDES="{\"containerOverrides\":[{\"name\":\"migration\",\"command\":${CMD_JSON}}]}"

echo "============================================"
echo "  Database Migration Runner"
echo "============================================"
echo "Command:     ${COMMAND}"
echo "Environment: ${ENVIRONMENT}"
echo "Cluster:     ${CLUSTER_NAME}"
echo "Region:      ${AWS_REGION}"
echo "============================================"
echo ""

# Get the latest task definition ARN
echo "→ Looking up latest migration task definition..."
TASK_DEF_ARN=$(aws ecs describe-task-definition \
    --task-definition "${TASK_FAMILY}" \
    --region "${AWS_REGION}" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text 2>&1)

if [[ "${TASK_DEF_ARN}" == *"Unable to describe"* ]] || [[ -z "${TASK_DEF_ARN}" ]]; then
    echo "✗ Migration task definition not found. Run 'terraform apply' first."
    exit 1
fi
echo "  Task Definition: ${TASK_DEF_ARN}"

# Get network configuration from the running API service
echo "→ Getting network configuration from API service..."
NETWORK_CONFIG=$(aws ecs describe-services \
    --cluster "${CLUSTER_NAME}" \
    --services "${PROJECT_NAME}-${ENVIRONMENT}-api" \
    --region "${AWS_REGION}" \
    --query 'services[0].networkConfiguration.awsvpcConfiguration' \
    --output json 2>&1)

SUBNETS=$(echo "${NETWORK_CONFIG}" | python3 -c "import sys,json; print(','.join(json.load(sys.stdin)['subnets']))")
SECURITY_GROUPS=$(echo "${NETWORK_CONFIG}" | python3 -c "import sys,json; print(','.join(json.load(sys.stdin)['securityGroups']))")

echo "  Subnets:         ${SUBNETS}"
echo "  Security Groups: ${SECURITY_GROUPS}"
echo ""

# Run the migration task
echo "→ Starting migration task..."
RUN_RESULT=$(aws ecs run-task \
    --cluster "${CLUSTER_NAME}" \
    --task-definition "${TASK_DEF_ARN}" \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SECURITY_GROUPS}],assignPublicIp=ENABLED}" \
    --overrides "${OVERRIDES}" \
    --region "${AWS_REGION}" \
    --output json)

TASK_ARN=$(echo "${RUN_RESULT}" | python3 -c "import sys,json; print(json.load(sys.stdin)['tasks'][0]['taskArn'])")
TASK_ID=$(echo "${TASK_ARN}" | awk -F'/' '{print $NF}')

echo "  Task ARN: ${TASK_ARN}"
echo "  Task ID:  ${TASK_ID}"
echo ""

# Wait for the task to complete
echo "→ Waiting for migration task to complete..."
aws ecs wait tasks-stopped \
    --cluster "${CLUSTER_NAME}" \
    --tasks "${TASK_ARN}" \
    --region "${AWS_REGION}"

echo "  Task stopped."
echo ""

# Check the exit code
EXIT_CODE=$(aws ecs describe-tasks \
    --cluster "${CLUSTER_NAME}" \
    --tasks "${TASK_ARN}" \
    --region "${AWS_REGION}" \
    --query 'tasks[0].containers[0].exitCode' \
    --output text)

STOP_REASON=$(aws ecs describe-tasks \
    --cluster "${CLUSTER_NAME}" \
    --tasks "${TASK_ARN}" \
    --region "${AWS_REGION}" \
    --query 'tasks[0].stoppedReason' \
    --output text)

echo "→ Result:"
echo "  Exit Code:   ${EXIT_CODE}"
echo "  Stop Reason: ${STOP_REASON}"
echo ""

# Fetch logs
echo "→ Logs:"
echo "--------------------------------------------"
sleep 3
aws logs get-log-events \
    --log-group-name "${LOG_GROUP}" \
    --log-stream-name "migration/migration/${TASK_ID}" \
    --region "${AWS_REGION}" \
    --query 'events[*].message' \
    --output text 2>/dev/null || echo "  (logs not yet available — check CloudWatch: ${LOG_GROUP})"
echo ""
echo "--------------------------------------------"

if [[ "${EXIT_CODE}" == "0" ]]; then
    echo "✓ Migration '${COMMAND}' completed successfully!"
    exit 0
else
    echo "✗ Migration '${COMMAND}' failed with exit code ${EXIT_CODE}"
    echo "  Check CloudWatch logs: ${LOG_GROUP}"
    exit 1
fi
