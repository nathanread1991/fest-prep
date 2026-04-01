#!/usr/bin/env bash
# ============================================================================
# Deployment Verification Script
# ============================================================================
# Verifies that an ECS deployment completed successfully by checking:
# - ECS service status (desired vs running task counts)
# - ALB target group health
# - CloudWatch Logs for recent startup errors
#
# Usage:
#   ./scripts/verify-deployment.sh
#   ./scripts/verify-deployment.sh --service api
#   ./scripts/verify-deployment.sh --log-minutes 10
#
# Environment variables:
#   PROJECT_NAME   - Project name (default: festival-playlist)
#   ENVIRONMENT    - Environment name (default: dev)
#   AWS_REGION     - AWS region (default: eu-west-2)
#   AWS_PROFILE    - AWS CLI profile (optional)
# ============================================================================

set -euo pipefail

# Configuration
PROJECT_NAME="${PROJECT_NAME:-festival-playlist}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-eu-west-2}"
CLUSTER="${PROJECT_NAME}-${ENVIRONMENT}-cluster"
API_SERVICE="${PROJECT_NAME}-${ENVIRONMENT}-api"
LOG_GROUP="/ecs/${PROJECT_NAME}-${ENVIRONMENT}/api"
LOG_MINUTES="${LOG_MINUTES:-5}"
SERVICE_FILTER=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[PASS]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[FAIL]${NC} $*"; }

# Track overall status
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNED=0

record_pass() { CHECKS_PASSED=$((CHECKS_PASSED + 1)); }
record_fail() { CHECKS_FAILED=$((CHECKS_FAILED + 1)); }
record_warn() { CHECKS_WARNED=$((CHECKS_WARNED + 1)); }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --service)
            SERVICE_FILTER="$2"
            shift 2
            ;;
        --log-minutes)
            LOG_MINUTES="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--service api|worker] [--log-minutes N]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build AWS CLI profile flag
AWS_PROFILE_FLAG=""
if [ -n "${AWS_PROFILE:-}" ]; then
    AWS_PROFILE_FLAG="--profile ${AWS_PROFILE}"
fi

# ============================================================================
# Check 1: ECS Service Status
# ============================================================================
check_ecs_service() {
    local service_name="$1"
    log_info "Checking ECS service: ${service_name}"

    local service_json
    service_json=$(aws ecs describe-services \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --cluster "${CLUSTER}" \
        --services "${service_name}" \
        --query 'services[0]' \
        --output json 2>/dev/null || echo "{}")

    if [ "${service_json}" = "{}" ] || [ "${service_json}" = "null" ]; then
        log_error "Service ${service_name} not found in cluster ${CLUSTER}"
        record_fail
        return 1
    fi

    local status desired_count running_count pending_count
    status=$(echo "${service_json}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','UNKNOWN'))")
    desired_count=$(echo "${service_json}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('desiredCount',0))")
    running_count=$(echo "${service_json}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('runningCount',0))")
    pending_count=$(echo "${service_json}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('pendingCount',0))")

    echo "  Status:        ${status}"
    echo "  Desired count: ${desired_count}"
    echo "  Running count: ${running_count}"
    echo "  Pending count: ${pending_count}"

    if [ "${status}" != "ACTIVE" ]; then
        log_error "Service status is ${status}, expected ACTIVE"
        record_fail
        return 1
    fi

    if [ "${running_count}" -eq "${desired_count}" ] && [ "${desired_count}" -gt 0 ]; then
        log_success "Running count matches desired count (${running_count}/${desired_count})"
        record_pass
    elif [ "${desired_count}" -eq 0 ]; then
        log_warn "Desired count is 0 — service is scaled down"
        record_warn
    else
        log_error "Running count (${running_count}) does not match desired count (${desired_count}), pending: ${pending_count}"
        record_fail
    fi

    # Check for recent deployment issues
    local deployment_count
    deployment_count=$(echo "${service_json}" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('deployments',[])))")
    if [ "${deployment_count}" -gt 1 ]; then
        log_warn "Multiple active deployments detected (${deployment_count}) — rolling update may be in progress"
        record_warn
    fi
}

# ============================================================================
# Check 2: ALB Target Group Health
# ============================================================================
check_target_group_health() {
    log_info "Checking ALB target group health..."

    # Find the target group ARN for the API service
    local tg_arn
    tg_arn=$(aws elbv2 describe-target-groups \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --names "${PROJECT_NAME}-${ENVIRONMENT}-api-tg" \
        --query 'TargetGroups[0].TargetGroupArn' \
        --output text 2>/dev/null || echo "")

    if [ -z "${tg_arn}" ] || [ "${tg_arn}" = "None" ]; then
        log_warn "Target group ${PROJECT_NAME}-${ENVIRONMENT}-api-tg not found — skipping health check"
        record_warn
        return 0
    fi

    local health_json
    health_json=$(aws elbv2 describe-target-health \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --target-group-arn "${tg_arn}" \
        --output json 2>/dev/null || echo '{"TargetHealthDescriptions":[]}')

    local total_targets healthy_targets unhealthy_targets
    total_targets=$(echo "${health_json}" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('TargetHealthDescriptions',[])))")
    healthy_targets=$(echo "${health_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('TargetHealthDescriptions', [])
print(sum(1 for t in data if t.get('TargetHealth',{}).get('State') == 'healthy'))
")
    unhealthy_targets=$(echo "${health_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('TargetHealthDescriptions', [])
print(sum(1 for t in data if t.get('TargetHealth',{}).get('State') == 'unhealthy'))
")

    echo "  Total targets:     ${total_targets}"
    echo "  Healthy targets:   ${healthy_targets}"
    echo "  Unhealthy targets: ${unhealthy_targets}"

    if [ "${total_targets}" -eq 0 ]; then
        log_error "No targets registered in target group"
        record_fail
    elif [ "${healthy_targets}" -eq "${total_targets}" ]; then
        log_success "All targets healthy (${healthy_targets}/${total_targets})"
        record_pass
    elif [ "${healthy_targets}" -gt 0 ]; then
        log_warn "Some targets unhealthy (${healthy_targets}/${total_targets} healthy)"
        record_warn
    else
        log_error "No healthy targets (0/${total_targets})"
        record_fail
    fi

    # Print details for unhealthy targets
    if [ "${unhealthy_targets}" -gt 0 ]; then
        echo ""
        log_info "Unhealthy target details:"
        echo "${health_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('TargetHealthDescriptions', [])
for t in data:
    state = t.get('TargetHealth', {}).get('State', 'unknown')
    if state != 'healthy':
        target_id = t.get('Target', {}).get('Id', 'unknown')
        reason = t.get('TargetHealth', {}).get('Reason', 'N/A')
        desc = t.get('TargetHealth', {}).get('Description', 'N/A')
        print(f'  Target: {target_id}  State: {state}  Reason: {reason}  Description: {desc}')
"
    fi
}

# ============================================================================
# Check 3: CloudWatch Logs for Startup Errors
# ============================================================================
check_cloudwatch_logs() {
    local log_group="$1"
    local minutes="$2"
    log_info "Checking CloudWatch logs for errors (last ${minutes} min): ${log_group}"

    # Calculate start time in milliseconds
    local start_time
    start_time=$(python3 -c "import time; print(int((time.time() - ${minutes} * 60) * 1000))")

    # Check if log group exists
    if ! aws logs describe-log-groups \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --log-group-name-prefix "${log_group}" \
        --query "logGroups[?logGroupName=='${log_group}']" \
        --output text 2>/dev/null | grep -q "${log_group}"; then
        log_warn "Log group ${log_group} not found — skipping log check"
        record_warn
        return 0
    fi

    # Search for error patterns in recent logs
    local error_events
    error_events=$(aws logs filter-log-events \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --log-group-name "${log_group}" \
        --start-time "${start_time}" \
        --filter-pattern "?ERROR ?Error ?error ?CRITICAL ?FATAL ?Traceback ?Exception" \
        --max-items 20 \
        --query 'events[*].message' \
        --output text 2>/dev/null || echo "")

    if [ -z "${error_events}" ] || [ "${error_events}" = "None" ]; then
        log_success "No startup errors found in recent logs"
        record_pass
    else
        local error_count
        error_count=$(echo "${error_events}" | wc -l | tr -d ' ')
        log_warn "Found ${error_count} error entries in recent logs"
        record_warn
        echo ""
        echo "  Recent error log entries (up to 5):"
        echo "${error_events}" | head -5 | while IFS= read -r line; do
            echo "    ${line}" | cut -c1-200
        done
    fi
}

# ============================================================================
# Check 4: Worker Celery Health (CloudWatch Logs)
# ============================================================================
check_worker_celery_logs() {
    local log_group="$1"
    local minutes="$2"
    log_info "Checking Celery worker health in logs (last ${minutes} min): ${log_group}"

    # Calculate start time in milliseconds
    local start_time
    start_time=$(python3 -c "import time; print(int((time.time() - ${minutes} * 60) * 1000))")

    # Check if log group exists
    if ! aws logs describe-log-groups \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --log-group-name-prefix "${log_group}" \
        --query "logGroups[?logGroupName=='${log_group}']" \
        --output text 2>/dev/null | grep -q "${log_group}"; then
        log_warn "Log group ${log_group} not found — skipping Celery health check"
        record_warn
        return 0
    fi

    # Search for Celery startup/ready messages
    local celery_events
    celery_events=$(aws logs filter-log-events \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --log-group-name "${log_group}" \
        --start-time "${start_time}" \
        --filter-pattern "?\"celery@\" ?\"ready.\" ?\"Connected to\" ?\"mingle\" ?\"celery worker\"" \
        --max-items 10 \
        --query 'events[*].message' \
        --output text 2>/dev/null || echo "")

    if [ -z "${celery_events}" ] || [ "${celery_events}" = "None" ]; then
        log_warn "No Celery startup messages found (worker may be scaled to 0 or still starting)"
        record_warn
    else
        log_success "Celery worker startup messages found in recent logs"
        record_pass
        echo "  Recent Celery log entries (up to 3):"
        echo "${celery_events}" | head -3 | while IFS= read -r line; do
            echo "    ${line}" | cut -c1-200
        done
    fi
}

# ============================================================================
# Summary
# ============================================================================
print_summary() {
    echo ""
    echo "========================================="
    log_info "Deployment Verification Summary"
    echo "========================================="
    echo "  Cluster:     ${CLUSTER}"
    echo "  Region:      ${AWS_REGION}"
    echo "  Passed:      ${CHECKS_PASSED}"
    echo "  Warnings:    ${CHECKS_WARNED}"
    echo "  Failed:      ${CHECKS_FAILED}"
    echo "========================================="

    if [ "${CHECKS_FAILED}" -gt 0 ]; then
        log_error "Deployment verification FAILED (${CHECKS_FAILED} check(s) failed)"
        return 1
    elif [ "${CHECKS_WARNED}" -gt 0 ]; then
        log_warn "Deployment verification PASSED with warnings"
        return 0
    else
        log_success "Deployment verification PASSED"
        return 0
    fi
}

# ============================================================================
# Main
# ============================================================================
main() {
    echo ""
    log_info "========================================="
    log_info "Deployment Verification"
    log_info "========================================="
    echo ""

    # Check 1: ECS service status
    if [ -z "${SERVICE_FILTER}" ] || [ "${SERVICE_FILTER}" = "api" ]; then
        check_ecs_service "${API_SERVICE}"
        echo ""
    fi

    if [ -z "${SERVICE_FILTER}" ] || [ "${SERVICE_FILTER}" = "worker" ]; then
        check_ecs_service "${PROJECT_NAME}-${ENVIRONMENT}-worker"
        echo ""
    fi

    # Check 2: ALB target group health (API only)
    if [ -z "${SERVICE_FILTER}" ] || [ "${SERVICE_FILTER}" = "api" ]; then
        check_target_group_health
        echo ""
    fi

    # Check 3: CloudWatch logs for errors
    if [ -z "${SERVICE_FILTER}" ] || [ "${SERVICE_FILTER}" = "api" ]; then
        check_cloudwatch_logs "${LOG_GROUP}" "${LOG_MINUTES}"
        echo ""
    fi

    if [ -z "${SERVICE_FILTER}" ] || [ "${SERVICE_FILTER}" = "worker" ]; then
        check_cloudwatch_logs "/ecs/${PROJECT_NAME}-${ENVIRONMENT}/worker" "${LOG_MINUTES}"
        echo ""
        check_worker_celery_logs "/ecs/${PROJECT_NAME}-${ENVIRONMENT}/worker" "${LOG_MINUTES}"
        echo ""
    fi

    # Print summary
    print_summary
}

main "$@"
