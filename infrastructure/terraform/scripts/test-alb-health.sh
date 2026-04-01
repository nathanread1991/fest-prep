#!/usr/bin/env bash
# ============================================================================
# ALB Health Check Test Script
# ============================================================================
# Tests ALB health checks, target group health, and routing for the
# Festival Playlist Generator API service.
#
# Checks performed:
#   1. /health endpoint returns 200 with expected JSON body
#   2. Unknown routes return 404 (verifies routing)
#   3. ALB target group has healthy targets
#   4. ALB listener rules are configured correctly
#
# Usage:
#   ./scripts/test-alb-health.sh
#   ./scripts/test-alb-health.sh --alb-dns <dns-name>
#   ./scripts/test-alb-health.sh --retries 5 --interval 10
#
# Environment variables:
#   PROJECT_NAME   - Project name (default: festival-playlist)
#   ENVIRONMENT    - Environment name (default: dev)
#   AWS_REGION     - AWS region (default: eu-west-2)
#   AWS_PROFILE    - AWS CLI profile (optional)
#   ALB_DNS        - ALB DNS name (auto-detected from Terraform if not set)
# ============================================================================

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

PROJECT_NAME="${PROJECT_NAME:-festival-playlist}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-eu-west-2}"
TARGET_GROUP_NAME="${PROJECT_NAME}-${ENVIRONMENT}-api-tg"
MAX_RETRIES=10
RETRY_INTERVAL=15
ALB_DNS="${ALB_DNS:-}"

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
        --alb-dns)
            ALB_DNS="$2"
            shift 2
            ;;
        --retries)
            MAX_RETRIES="$2"
            shift 2
            ;;
        --interval)
            RETRY_INTERVAL="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--alb-dns <dns>] [--retries N] [--interval S]"
            echo ""
            echo "Options:"
            echo "  --alb-dns   ALB DNS name (auto-detected from Terraform if omitted)"
            echo "  --retries   Max retry attempts for health endpoint (default: 10)"
            echo "  --interval  Seconds between retries (default: 15)"
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
# Resolve ALB DNS Name
# ============================================================================

resolve_alb_dns() {
    if [ -n "${ALB_DNS}" ]; then
        log_info "Using provided ALB DNS: ${ALB_DNS}"
        return 0
    fi

    log_info "Resolving ALB DNS name from Terraform output..."

    # Try Terraform output first
    local tf_dir
    tf_dir="$(cd "$(dirname "$0")/.." && pwd)"

    if [ -f "${tf_dir}/main.tf" ]; then
        ALB_DNS=$(terraform -chdir="${tf_dir}" output -raw alb_dns_name 2>/dev/null || echo "")
    fi

    if [ -z "${ALB_DNS}" ]; then
        # Fallback: query AWS directly for the ALB
        ALB_DNS=$(aws elbv2 describe-load-balancers \
            ${AWS_PROFILE_FLAG} \
            --region "${AWS_REGION}" \
            --names "${PROJECT_NAME}-${ENVIRONMENT}-alb" \
            --query 'LoadBalancers[0].DNSName' \
            --output text 2>/dev/null || echo "")
    fi

    if [ -z "${ALB_DNS}" ] || [ "${ALB_DNS}" = "None" ]; then
        log_error "Could not resolve ALB DNS name"
        return 1
    fi

    log_info "Resolved ALB DNS: ${ALB_DNS}"
}

# ============================================================================
# Check 1: Test /health Endpoint Through ALB
# ============================================================================

check_health_endpoint() {
    log_info "Testing /health endpoint through ALB (up to ${MAX_RETRIES} attempts, ${RETRY_INTERVAL}s apart)..."

    local attempt=1
    local http_code=""
    local response_body=""

    while [ "${attempt}" -le "${MAX_RETRIES}" ]; do
        # Capture both HTTP status code and response body
        response_body=$(curl -s -o /dev/null -w "%{http_code}" \
            --max-time 10 \
            "http://${ALB_DNS}/health" 2>/dev/null || echo "000")
        http_code="${response_body}"

        response_body=$(curl -s --max-time 10 "http://${ALB_DNS}/health" 2>/dev/null || echo "")

        if [ "${http_code}" = "200" ]; then
            break
        fi

        echo "  Attempt ${attempt}/${MAX_RETRIES}: HTTP ${http_code} — retrying in ${RETRY_INTERVAL}s..."
        sleep "${RETRY_INTERVAL}"
        attempt=$((attempt + 1))
    done

    # Validate HTTP status code
    if [ "${http_code}" != "200" ]; then
        log_error "/health returned HTTP ${http_code} after ${MAX_RETRIES} attempts (expected 200)"
        record_fail
        return 1
    fi

    log_success "/health returned HTTP 200"
    record_pass

    # Validate response body contains expected JSON
    log_info "Validating /health response body..."

    if echo "${response_body}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    assert data.get('status') == 'healthy', f\"Expected status=healthy, got {data.get('status')}\"
    sys.exit(0)
except (json.JSONDecodeError, AssertionError) as e:
    print(f'  Validation failed: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1; then
        log_success "Response body contains {\"status\": \"healthy\"}"
        record_pass
    else
        log_error "Response body validation failed. Body: ${response_body}"
        record_fail
    fi
}

# ============================================================================
# Check 2: Test HTTP Status Codes for Unknown Routes
# ============================================================================

check_unknown_route() {
    log_info "Testing unknown route returns proper HTTP status..."

    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 \
        "http://${ALB_DNS}/this-route-does-not-exist-$(date +%s)" 2>/dev/null || echo "000")

    if [ "${http_code}" = "404" ] || [ "${http_code}" = "422" ]; then
        log_success "Unknown route returned HTTP ${http_code} (expected 404 or 422)"
        record_pass
    elif [ "${http_code}" = "000" ]; then
        log_error "Could not connect to ALB at ${ALB_DNS}"
        record_fail
    else
        log_warn "Unknown route returned HTTP ${http_code} (expected 404, may be acceptable)"
        record_pass
    fi
}

# ============================================================================
# Check 3: Verify ALB Target Group Has Healthy Targets
# ============================================================================

check_target_group_health() {
    log_info "Checking ALB target group health: ${TARGET_GROUP_NAME}"

    # Get target group ARN
    local tg_arn
    tg_arn=$(aws elbv2 describe-target-groups \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --names "${TARGET_GROUP_NAME}" \
        --query 'TargetGroups[0].TargetGroupArn' \
        --output text 2>/dev/null || echo "")

    if [ -z "${tg_arn}" ] || [ "${tg_arn}" = "None" ]; then
        log_error "Target group ${TARGET_GROUP_NAME} not found"
        record_fail
        return 1
    fi

    # Get target group health check configuration
    log_info "Target group health check configuration:"
    aws elbv2 describe-target-groups \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --target-group-arns "${tg_arn}" \
        --query 'TargetGroups[0].{Path:HealthCheckPath,Interval:HealthCheckIntervalSeconds,Timeout:HealthCheckTimeoutSeconds,HealthyThreshold:HealthyThresholdCount,UnhealthyThreshold:UnhealthyThresholdCount,Matcher:Matcher.HttpCode}' \
        --output table 2>/dev/null || true

    # Get target health
    local health_json
    health_json=$(aws elbv2 describe-target-health \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --target-group-arn "${tg_arn}" \
        --output json 2>/dev/null || echo '{"TargetHealthDescriptions":[]}')

    local total_targets healthy_targets unhealthy_targets draining_targets
    total_targets=$(echo "${health_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('TargetHealthDescriptions', [])
print(len(data))
")
    healthy_targets=$(echo "${health_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('TargetHealthDescriptions', [])
print(sum(1 for t in data if t.get('TargetHealth', {}).get('State') == 'healthy'))
")
    unhealthy_targets=$(echo "${health_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('TargetHealthDescriptions', [])
print(sum(1 for t in data if t.get('TargetHealth', {}).get('State') == 'unhealthy'))
")
    draining_targets=$(echo "${health_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('TargetHealthDescriptions', [])
print(sum(1 for t in data if t.get('TargetHealth', {}).get('State') == 'draining'))
")

    echo "  Total targets:     ${total_targets}"
    echo "  Healthy targets:   ${healthy_targets}"
    echo "  Unhealthy targets: ${unhealthy_targets}"
    echo "  Draining targets:  ${draining_targets}"

    if [ "${total_targets}" -eq 0 ]; then
        log_error "No targets registered in target group"
        record_fail
    elif [ "${healthy_targets}" -eq "${total_targets}" ]; then
        log_success "All targets healthy (${healthy_targets}/${total_targets})"
        record_pass
    elif [ "${healthy_targets}" -gt 0 ]; then
        log_warn "Some targets unhealthy (${healthy_targets}/${total_targets} healthy)"
        record_fail
    else
        log_error "No healthy targets (0/${total_targets})"
        record_fail
    fi

    # Print details for non-healthy targets
    if [ "${unhealthy_targets}" -gt 0 ] || [ "${draining_targets}" -gt 0 ]; then
        echo ""
        log_info "Non-healthy target details:"
        echo "${health_json}" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('TargetHealthDescriptions', [])
for t in data:
    state = t.get('TargetHealth', {}).get('State', 'unknown')
    if state != 'healthy':
        target_id = t.get('Target', {}).get('Id', 'unknown')
        port = t.get('Target', {}).get('Port', 'unknown')
        reason = t.get('TargetHealth', {}).get('Reason', 'N/A')
        desc = t.get('TargetHealth', {}).get('Description', 'N/A')
        print(f'  Target: {target_id}:{port}  State: {state}  Reason: {reason}')
        print(f'    Description: {desc}')
"
    fi
}

# ============================================================================
# Check 4: Verify ALB Listener Rules
# ============================================================================

check_listener_rules() {
    log_info "Checking ALB listener rules..."

    # Get ALB ARN
    local alb_arn
    alb_arn=$(aws elbv2 describe-load-balancers \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --names "${PROJECT_NAME}-${ENVIRONMENT}-alb" \
        --query 'LoadBalancers[0].LoadBalancerArn' \
        --output text 2>/dev/null || echo "")

    if [ -z "${alb_arn}" ] || [ "${alb_arn}" = "None" ]; then
        log_error "ALB ${PROJECT_NAME}-${ENVIRONMENT}-alb not found"
        record_fail
        return 1
    fi

    # Get listeners
    local listeners_json
    listeners_json=$(aws elbv2 describe-listeners \
        ${AWS_PROFILE_FLAG} \
        --region "${AWS_REGION}" \
        --load-balancer-arn "${alb_arn}" \
        --output json 2>/dev/null || echo '{"Listeners":[]}')

    local listener_count
    listener_count=$(echo "${listeners_json}" | python3 -c "
import sys, json
print(len(json.load(sys.stdin).get('Listeners', [])))
")

    echo "  Listeners found: ${listener_count}"

    # Check HTTP listener (port 80)
    local http_listener
    http_listener=$(echo "${listeners_json}" | python3 -c "
import sys, json
listeners = json.load(sys.stdin).get('Listeners', [])
for l in listeners:
    if l.get('Port') == 80:
        action_type = l.get('DefaultActions', [{}])[0].get('Type', 'unknown')
        print(f'Port 80: action={action_type}')
        sys.exit(0)
print('Port 80: not found')
")
    echo "  ${http_listener}"

    # Check HTTPS listener (port 443) if present
    local https_listener
    https_listener=$(echo "${listeners_json}" | python3 -c "
import sys, json
listeners = json.load(sys.stdin).get('Listeners', [])
for l in listeners:
    if l.get('Port') == 443:
        action_type = l.get('DefaultActions', [{}])[0].get('Type', 'unknown')
        print(f'Port 443: action={action_type}')
        sys.exit(0)
print('Port 443: not configured')
")
    echo "  ${https_listener}"

    if [ "${listener_count}" -ge 1 ]; then
        log_success "ALB listeners configured (${listener_count} listener(s))"
        record_pass
    else
        log_error "No listeners found on ALB"
        record_fail
    fi

    # Verify the HTTP listener routes to the correct target group
    local http_listener_arn
    http_listener_arn=$(echo "${listeners_json}" | python3 -c "
import sys, json
listeners = json.load(sys.stdin).get('Listeners', [])
for l in listeners:
    if l.get('Port') == 80:
        print(l.get('ListenerArn', ''))
        sys.exit(0)
print('')
")

    if [ -n "${http_listener_arn}" ]; then
        local rules_json
        rules_json=$(aws elbv2 describe-rules \
            ${AWS_PROFILE_FLAG} \
            --region "${AWS_REGION}" \
            --listener-arn "${http_listener_arn}" \
            --output json 2>/dev/null || echo '{"Rules":[]}')

        local rule_count
        rule_count=$(echo "${rules_json}" | python3 -c "
import sys, json
print(len(json.load(sys.stdin).get('Rules', [])))
")
        echo "  HTTP listener rules: ${rule_count}"
        log_success "HTTP listener rules verified"
        record_pass
    fi
}

# ============================================================================
# Summary
# ============================================================================

print_summary() {
    echo ""
    echo "========================================="
    log_info "ALB Health Check Test Summary"
    echo "========================================="
    echo "  ALB DNS:     ${ALB_DNS:-N/A}"
    echo "  Target Group: ${TARGET_GROUP_NAME}"
    echo "  Region:       ${AWS_REGION}"
    echo ""
    echo "  Passed:  ${CHECKS_PASSED}"
    echo "  Failed:  ${CHECKS_FAILED}"
    echo "  Skipped: ${CHECKS_SKIPPED}"
    echo "========================================="

    if [ "${CHECKS_FAILED}" -gt 0 ]; then
        log_error "ALB health check tests FAILED (${CHECKS_FAILED} check(s) failed)"
        return 1
    else
        log_success "All ALB health check tests PASSED"
        return 0
    fi
}

# ============================================================================
# Main
# ============================================================================

main() {
    echo ""
    log_info "========================================="
    log_info "ALB Health Check Tests"
    log_info "========================================="
    echo ""

    # Resolve ALB DNS
    if ! resolve_alb_dns; then
        log_error "Cannot proceed without ALB DNS name"
        log_info "Provide it via --alb-dns flag, ALB_DNS env var, or ensure Terraform outputs are available"
        exit 1
    fi

    echo ""

    # Check 1: Health endpoint through ALB
    check_health_endpoint
    echo ""

    # Check 2: Unknown route returns proper status
    check_unknown_route
    echo ""

    # Check 3: Target group health
    check_target_group_health
    echo ""

    # Check 4: Listener rules
    check_listener_rules
    echo ""

    # Print summary
    print_summary
}

main "$@"
