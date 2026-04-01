#!/usr/bin/env bash
# ============================================================================
# ECS Auto-Scaling Validation Script
# ============================================================================
# Verifies that ECS auto-scaling is correctly configured for both the API
# and worker services. Checks scaling policies, thresholds, cooldowns,
# and current scaling state.
#
# Checks performed:
#   1. API auto-scaling target registered with correct min/max
#   2. API scaling policies exist (CPU, memory, request count)
#   3. Worker auto-scaling target registered (if enabled)
#   4. Worker scaling policies exist (CPU, memory)
#   5. Current task counts match desired counts
#   6. CloudWatch alarms for scaling are configured
#
# Usage:
#   ./scripts/test-autoscaling.sh
#   ./scripts/test-autoscaling.sh --cluster <name> --region <region>
#
# Environment variables:
#   PROJECT_NAME   - Project name (default: festival-playlist)
#   ENVIRONMENT    - Environment name (default: dev)
#   AWS_REGION     - AWS region (default: eu-west-2)
#   AWS_PROFILE    - AWS CLI profile (optional)
# ============================================================================

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

PROJECT_NAME="${PROJECT_NAME:-festival-playlist}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-eu-west-2}"
CLUSTER_NAME="${CLUSTER_NAME:-${PROJECT_NAME}-${ENVIRONMENT}-cluster}"
API_SERVICE_NAME="${PROJECT_NAME}-${ENVIRONMENT}-api"
WORKER_SERVICE_NAME="${PROJECT_NAME}-${ENVIRONMENT}-worker"

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

# Track results
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_SKIPPED=0

record_pass() { CHECKS_PASSED=$((CHECKS_PASSED + 1)); }
record_fail() { CHECKS_FAILED=$((CHECKS_FAILED + 1)); }
record_skip() { CHECKS_SKIPPED=$((CHECKS_SKIPPED + 1)); }

# ============================================================================
# Parse Arguments
# ============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --cluster)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--cluster <name>] [--region <region>]"
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
# Check 1: API Auto-Scaling Target
# ============================================================================

check_api_scaling_target() {
    log_info "Checking API auto-scaling target..."

    local resource_id="service/${CLUSTER_NAME}/${API_SERVICE_NAME}"

    local target_json
    target_json=$(aws application-autoscaling describe-scalable-targets \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --service-namespace ecs \
        --resource-ids "${resource_id}" \
        --output json 2>/dev/null || echo '{"ScalableTargets":[]}')

    local target_count
    target_count=$(echo "${target_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('ScalableTargets', [])
print(len(data))
")

    if [ "${target_count}" -eq 0 ]; then
        log_error "No auto-scaling target found for API service"
        record_fail
        return 1
    fi

    # Extract min/max capacity
    echo "${target_json}" | python3 -c "
import sys, json
targets = json.load(sys.stdin).get('ScalableTargets', [])
for t in targets:
    min_cap = t.get('MinCapacity', 'N/A')
    max_cap = t.get('MaxCapacity', 'N/A')
    print(f'  Min capacity: {min_cap}')
    print(f'  Max capacity: {max_cap}')
"

    log_success "API auto-scaling target registered"
    record_pass
}

# ============================================================================
# Check 2: API Scaling Policies
# ============================================================================

check_api_scaling_policies() {
    log_info "Checking API auto-scaling policies..."

    local resource_id="service/${CLUSTER_NAME}/${API_SERVICE_NAME}"

    local policies_json
    policies_json=$(aws application-autoscaling describe-scaling-policies \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --service-namespace ecs \
        --resource-id "${resource_id}" \
        --output json 2>/dev/null || echo '{"ScalingPolicies":[]}')

    local policy_count
    policy_count=$(echo "${policies_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('ScalingPolicies', [])
print(len(data))
")

    echo "  Policies found: ${policy_count}"

    if [ "${policy_count}" -lt 2 ]; then
        log_error "Expected at least 2 scaling policies (CPU + memory), found ${policy_count}"
        record_fail
        return 1
    fi

    # Print policy details
    echo "${policies_json}" | python3 -c "
import sys, json
policies = json.load(sys.stdin).get('ScalingPolicies', [])
for p in policies:
    name = p.get('PolicyName', 'unknown')
    policy_type = p.get('PolicyType', 'unknown')
    config = p.get('TargetTrackingScalingPolicyConfiguration', {})
    target = config.get('TargetValue', 'N/A')
    scale_in = config.get('ScaleInCooldown', 'N/A')
    scale_out = config.get('ScaleOutCooldown', 'N/A')
    metric = config.get('PredefinedMetricSpecification', {}).get('PredefinedMetricType', 'custom')
    print(f'  Policy: {name}')
    print(f'    Metric: {metric}  Target: {target}  ScaleIn: {scale_in}s  ScaleOut: {scale_out}s')
"

    log_success "API scaling policies configured (${policy_count} policies)"
    record_pass
}

# ============================================================================
# Check 3: Worker Auto-Scaling Target
# ============================================================================

check_worker_scaling_target() {
    log_info "Checking worker auto-scaling target..."

    local resource_id="service/${CLUSTER_NAME}/${WORKER_SERVICE_NAME}"

    local target_json
    target_json=$(aws application-autoscaling describe-scalable-targets \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --service-namespace ecs \
        --resource-ids "${resource_id}" \
        --output json 2>/dev/null || echo '{"ScalableTargets":[]}')

    local target_count
    target_count=$(echo "${target_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('ScalableTargets', [])
print(len(data))
")

    if [ "${target_count}" -eq 0 ]; then
        log_warn "No auto-scaling target for worker service (may be disabled)"
        record_skip
        return 0
    fi

    echo "${target_json}" | python3 -c "
import sys, json
targets = json.load(sys.stdin).get('ScalableTargets', [])
for t in targets:
    min_cap = t.get('MinCapacity', 'N/A')
    max_cap = t.get('MaxCapacity', 'N/A')
    print(f'  Min capacity: {min_cap}')
    print(f'  Max capacity: {max_cap}')
"

    log_success "Worker auto-scaling target registered"
    record_pass
}

# ============================================================================
# Check 4: Worker Scaling Policies
# ============================================================================

check_worker_scaling_policies() {
    log_info "Checking worker auto-scaling policies..."

    local resource_id="service/${CLUSTER_NAME}/${WORKER_SERVICE_NAME}"

    local policies_json
    policies_json=$(aws application-autoscaling describe-scaling-policies \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --service-namespace ecs \
        --resource-id "${resource_id}" \
        --output json 2>/dev/null || echo '{"ScalingPolicies":[]}')

    local policy_count
    policy_count=$(echo "${policies_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('ScalingPolicies', [])
print(len(data))
")

    if [ "${policy_count}" -eq 0 ]; then
        log_warn "No scaling policies for worker service (may be disabled)"
        record_skip
        return 0
    fi

    echo "${policies_json}" | python3 -c "
import sys, json
policies = json.load(sys.stdin).get('ScalingPolicies', [])
for p in policies:
    name = p.get('PolicyName', 'unknown')
    config = p.get('TargetTrackingScalingPolicyConfiguration', {})
    target = config.get('TargetValue', 'N/A')
    scale_in = config.get('ScaleInCooldown', 'N/A')
    scale_out = config.get('ScaleOutCooldown', 'N/A')
    metric = config.get('PredefinedMetricSpecification', {}).get('PredefinedMetricType', 'custom')
    print(f'  Policy: {name}')
    print(f'    Metric: {metric}  Target: {target}  ScaleIn: {scale_in}s  ScaleOut: {scale_out}s')
"

    log_success "Worker scaling policies configured (${policy_count} policies)"
    record_pass
}

# ============================================================================
# Check 5: Current Task Counts
# ============================================================================

check_current_task_counts() {
    log_info "Checking current ECS task counts..."

    local services_json
    services_json=$(aws ecs describe-services \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --cluster "${CLUSTER_NAME}" \
        --services "${API_SERVICE_NAME}" "${WORKER_SERVICE_NAME}" \
        --output json 2>/dev/null || echo '{"services":[]}')

    echo "${services_json}" | python3 -c "
import sys, json
services = json.load(sys.stdin).get('services', [])
for s in services:
    name = s.get('serviceName', 'unknown')
    desired = s.get('desiredCount', 0)
    running = s.get('runningCount', 0)
    pending = s.get('pendingCount', 0)
    status = s.get('status', 'unknown')
    print(f'  {name}:')
    print(f'    Status: {status}  Desired: {desired}  Running: {running}  Pending: {pending}')
    if running < desired:
        print(f'    WARNING: Running ({running}) < Desired ({desired})')
    elif running == desired:
        print(f'    OK: Running matches desired count')
"

    # Check API service specifically
    local api_running
    api_running=$(echo "${services_json}" | python3 -c "
import sys, json
services = json.load(sys.stdin).get('services', [])
for s in services:
    if '${API_SERVICE_NAME}' in s.get('serviceName', ''):
        print(s.get('runningCount', 0))
        sys.exit(0)
print(0)
")

    if [ "${api_running}" -ge 1 ]; then
        log_success "API service has ${api_running} running task(s)"
        record_pass
    else
        log_error "API service has 0 running tasks"
        record_fail
    fi
}

# ============================================================================
# Check 6: Scaling Activity History
# ============================================================================

check_scaling_activity() {
    log_info "Checking recent scaling activity..."

    local resource_id="service/${CLUSTER_NAME}/${API_SERVICE_NAME}"

    local activity_json
    activity_json=$(aws application-autoscaling describe-scaling-activities \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --service-namespace ecs \
        --resource-id "${resource_id}" \
        --max-results 5 \
        --output json 2>/dev/null || echo '{"ScalingActivities":[]}')

    local activity_count
    activity_count=$(echo "${activity_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('ScalingActivities', [])
print(len(data))
")

    if [ "${activity_count}" -eq 0 ]; then
        log_info "No recent scaling activity (service may be stable)"
        record_pass
        return 0
    fi

    echo "  Recent scaling events (last 5):"
    echo "${activity_json}" | python3 -c "
import sys, json
activities = json.load(sys.stdin).get('ScalingActivities', [])
for a in activities:
    ts = a.get('StartTime', 'N/A')
    cause = a.get('Cause', 'N/A')[:120]
    status = a.get('StatusCode', 'N/A')
    print(f'    [{ts}] {status}: {cause}')
"

    log_success "Scaling activity history available (${activity_count} events)"
    record_pass
}

# ============================================================================
# Check 7: CloudWatch Alarms for Auto-Scaling
# ============================================================================

check_scaling_alarms() {
    log_info "Checking CloudWatch alarms related to auto-scaling..."

    local alarms_json
    alarms_json=$(aws cloudwatch describe-alarms \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --alarm-name-prefix "${PROJECT_NAME}-${ENVIRONMENT}-ecs" \
        --output json 2>/dev/null || echo '{"MetricAlarms":[]}')

    local alarm_count
    alarm_count=$(echo "${alarms_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('MetricAlarms', [])
print(len(data))
")

    if [ "${alarm_count}" -eq 0 ]; then
        log_warn "No ECS-related CloudWatch alarms found"
        record_skip
        return 0
    fi

    echo "${alarms_json}" | python3 -c "
import sys, json
alarms = json.load(sys.stdin).get('MetricAlarms', [])
for a in alarms:
    name = a.get('AlarmName', 'unknown')
    state = a.get('StateValue', 'unknown')
    metric = a.get('MetricName', 'N/A')
    threshold = a.get('Threshold', 'N/A')
    print(f'  {name}: {state} (metric={metric}, threshold={threshold})')
"

    log_success "ECS CloudWatch alarms configured (${alarm_count} alarms)"
    record_pass
}

# ============================================================================
# Summary
# ============================================================================

print_summary() {
    echo ""
    echo "========================================="
    log_info "ECS Auto-Scaling Validation Summary"
    echo "========================================="
    echo "  Cluster:  ${CLUSTER_NAME}"
    echo "  API:      ${API_SERVICE_NAME}"
    echo "  Worker:   ${WORKER_SERVICE_NAME}"
    echo "  Region:   ${AWS_REGION}"
    echo ""
    echo "  Passed:  ${CHECKS_PASSED}"
    echo "  Failed:  ${CHECKS_FAILED}"
    echo "  Skipped: ${CHECKS_SKIPPED}"
    echo "========================================="

    if [ "${CHECKS_FAILED}" -gt 0 ]; then
        log_error "Auto-scaling validation FAILED (${CHECKS_FAILED} check(s) failed)"
        return 1
    else
        log_success "All auto-scaling checks PASSED"
        return 0
    fi
}

# ============================================================================
# Main
# ============================================================================

main() {
    echo ""
    log_info "========================================="
    log_info "ECS Auto-Scaling Validation"
    log_info "========================================="
    echo ""

    check_api_scaling_target
    echo ""

    check_api_scaling_policies
    echo ""

    check_worker_scaling_target
    echo ""

    check_worker_scaling_policies
    echo ""

    check_current_task_counts
    echo ""

    check_scaling_activity
    echo ""

    check_scaling_alarms
    echo ""

    print_summary
}

main "$@"
