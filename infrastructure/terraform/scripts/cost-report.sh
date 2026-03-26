#!/bin/bash
# Cost Report Script - Query AWS Cost Explorer for environment costs
# This script provides detailed cost breakdowns by service and time period

set -e  # Exit on error
set -o pipefail  # Exit on pipe failure

# ============================================================================
# Configuration
# ============================================================================

PROJECT_NAME="${PROJECT_NAME:-festival-playlist}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_PROFILE="${AWS_PROFILE:-festival-playlist}"
AWS_REGION="${AWS_REGION:-us-east-1}"  # Cost Explorer is only in us-east-1
DAYS_BACK="${DAYS_BACK:-30}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_header() {
    echo -e "${CYAN}$1${NC}"
}

log_cost() {
    local service="$1"
    local cost="$2"
    printf "  %-30s %s\$%.2f%s\n" "$service" "${GREEN}" "$cost" "${NC}"
}

# Check if AWS CLI is installed
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
}

# Check if jq is installed
check_jq() {
    if ! command -v jq &> /dev/null; then
        log_warning "jq is not installed. Output will be less formatted."
        log_warning "Install with: brew install jq (macOS) or apt-get install jq (Linux)"
        return 1
    fi
    return 0
}

# Check if AWS credentials are configured
check_aws_credentials() {
    if ! aws sts get-caller-identity --profile "$AWS_PROFILE" &> /dev/null; then
        log_error "AWS credentials not configured for profile: $AWS_PROFILE"
        log_error "Run: aws configure --profile $AWS_PROFILE"
        exit 1
    fi
}

# Get total cost for date range
get_total_cost() {
    local start_date="$1"
    local end_date="$2"

    local result=$(aws ce get-cost-and-usage \
        --time-period Start="$start_date",End="$end_date" \
        --granularity MONTHLY \
        --metrics "UnblendedCost" \
        --filter file://<(cat <<EOF
{
  "Tags": {
    "Key": "Environment",
    "Values": ["$ENVIRONMENT"]
  }
}
EOF
) \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query 'ResultsByTime[0].Total.UnblendedCost.Amount' \
        --output text 2>/dev/null || echo "0")

    echo "$result"
}

# Get cost by service
get_cost_by_service() {
    local start_date="$1"
    local end_date="$2"

    aws ce get-cost-and-usage \
        --time-period Start="$start_date",End="$end_date" \
        --granularity MONTHLY \
        --metrics "UnblendedCost" \
        --group-by Type=DIMENSION,Key=SERVICE \
        --filter file://<(cat <<EOF
{
  "Tags": {
    "Key": "Environment",
    "Values": ["$ENVIRONMENT"]
  }
}
EOF
) \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        2>/dev/null || echo "{}"
}

# Get daily cost breakdown
get_daily_costs() {
    local start_date="$1"
    local end_date="$2"

    aws ce get-cost-and-usage \
        --time-period Start="$start_date",End="$end_date" \
        --granularity DAILY \
        --metrics "UnblendedCost" \
        --filter file://<(cat <<EOF
{
  "Tags": {
    "Key": "Environment",
    "Values": ["$ENVIRONMENT"]
  }
}
EOF
) \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        2>/dev/null || echo "{}"
}

# Display cost by service
display_cost_by_service() {
    local start_date="$1"
    local end_date="$2"

    log_header "Cost by Service ($start_date to $end_date)"
    echo ""

    local result=$(get_cost_by_service "$start_date" "$end_date")

    if command -v jq &> /dev/null; then
        # Parse with jq for better formatting
        echo "$result" | jq -r '.ResultsByTime[0].Groups[] | "\(.Keys[0])|\(.Metrics.UnblendedCost.Amount)"' | \
        while IFS='|' read -r service cost; do
            if (( $(echo "$cost > 0.01" | bc -l) )); then
                log_cost "$service" "$cost"
            fi
        done | sort -t'$' -k2 -rn
    else
        # Fallback without jq
        echo "$result" | grep -o '"Keys":\["[^"]*"\],"Metrics":{"UnblendedCost":{"Amount":"[^"]*"' | \
        sed 's/"Keys":\["\([^"]*\)"\],"Metrics":{"UnblendedCost":{"Amount":"\([^"]*\)"/\1|\2/' | \
        while IFS='|' read -r service cost; do
            if (( $(echo "$cost > 0.01" | bc -l) )); then
                log_cost "$service" "$cost"
            fi
        done
    fi

    echo ""
}

# Display daily cost breakdown
display_daily_costs() {
    local start_date="$1"
    local end_date="$2"
    local days="$3"

    log_header "Daily Cost Breakdown (Last $days days)"
    echo ""

    local result=$(get_daily_costs "$start_date" "$end_date")

    if command -v jq &> /dev/null; then
        # Parse with jq for better formatting
        echo "$result" | jq -r '.ResultsByTime[] | "\(.TimePeriod.Start)|\(.Total.UnblendedCost.Amount)"' | \
        while IFS='|' read -r date cost; do
            if (( $(echo "$cost > 0.01" | bc -l) )); then
                printf "  %-12s %s\$%.2f%s\n" "$date" "${GREEN}" "$cost" "${NC}"
            fi
        done
    else
        # Fallback without jq
        echo "$result" | grep -o '"Start":"[^"]*","End":"[^"]*"},"Total":{"UnblendedCost":{"Amount":"[^"]*"' | \
        sed 's/"Start":"\([^"]*\)","End":"[^"]*"},"Total":{"UnblendedCost":{"Amount":"\([^"]*\)"/\1|\2/' | \
        while IFS='|' read -r date cost; do
            if (( $(echo "$cost > 0.01" | bc -l) )); then
                printf "  %-12s %s\$%.2f%s\n" "$date" "${GREEN}" "$cost" "${NC}"
            fi
        done
    fi

    echo ""
}

# Display monthly projection
display_monthly_projection() {
    local mtd_cost="$1"
    local days_in_month="$2"
    local current_day="$3"

    log_header "Monthly Projection"
    echo ""

    if (( $(echo "$mtd_cost > 0" | bc -l) )); then
        local daily_avg=$(echo "scale=2; $mtd_cost / $current_day" | bc)
        local projected=$(echo "scale=2; $daily_avg * $days_in_month" | bc)

        log_info "Month-to-date cost: \$$(printf "%.2f" "$mtd_cost")"
        log_info "Daily average: \$$(printf "%.2f" "$daily_avg")"
        log_info "Projected monthly cost: \$$(printf "%.2f" "$projected")"

        # Compare to budget
        local budget=30.00
        if (( $(echo "$projected > $budget" | bc -l) )); then
            log_warning "Projected cost exceeds budget of \$$budget"
            local overage=$(echo "scale=2; $projected - $budget" | bc)
            log_warning "Projected overage: \$$(printf "%.2f" "$overage")"
        else
            log_success "Projected cost is within budget of \$$budget"
            local remaining=$(echo "scale=2; $budget - $projected" | bc)
            log_info "Remaining budget: \$$(printf "%.2f" "$remaining")"
        fi
    else
        log_warning "No cost data available for projection"
    fi

    echo ""
}

# Display cost optimization tips
display_optimization_tips() {
    log_header "Cost Optimization Tips"
    echo ""
    log_info "1. Use daily teardown to reduce costs by ~50%"
    log_info "   - Run: ./scripts/teardown.sh at end of day"
    log_info "   - Run: ./scripts/provision.sh to restore"
    log_info "   - Saves: ~\$5-9/month"
    echo ""
    log_info "2. Use Fargate Spot for worker tasks (70% savings)"
    log_info "   - Already configured in Terraform"
    log_info "   - Saves: ~\$1-3/month"
    echo ""
    log_info "3. Enable Aurora auto-pause in dev (5 min timeout)"
    log_info "   - Already configured in Terraform"
    log_info "   - Saves: ~\$5-10/month when idle"
    echo ""
    log_info "4. Use S3 Intelligent-Tiering for storage"
    log_info "   - Already configured in Terraform"
    log_info "   - Saves: ~\$0.50-2/month"
    echo ""
    log_info "5. Set CloudWatch log retention to 7 days"
    log_info "   - Already configured in Terraform"
    log_info "   - Saves: ~\$1-2/month"
    echo ""
}

# Display budget alerts status
display_budget_status() {
    log_header "Budget Alerts Status"
    echo ""

    local budgets=$(aws budgets describe-budgets \
        --account-id "$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text)" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query "Budgets[?BudgetName=='${PROJECT_NAME}-${ENVIRONMENT}-monthly-budget']" \
        2>/dev/null || echo "[]")

    if [ "$budgets" = "[]" ] || [ -z "$budgets" ]; then
        log_warning "No budget configured for environment: $ENVIRONMENT"
        log_info "Configure budget in Terraform to enable alerts"
    else
        log_success "Budget configured for environment: $ENVIRONMENT"

        if command -v jq &> /dev/null; then
            local budget_limit=$(echo "$budgets" | jq -r '.[0].BudgetLimit.Amount')
            log_info "Budget limit: \$$budget_limit/month"
        fi
    fi

    echo ""
}

# ============================================================================
# Main Script
# ============================================================================

main() {
    echo ""
    log_info "=========================================="
    log_info "Festival Playlist Generator - Cost Report"
    log_info "=========================================="
    log_info "Project: $PROJECT_NAME"
    log_info "Environment: $ENVIRONMENT"
    log_info "AWS Profile: $AWS_PROFILE"
    log_info "=========================================="
    echo ""

    # Pre-flight checks
    log_info "Running pre-flight checks..."
    check_aws_cli
    check_jq
    check_aws_credentials
    log_success "Pre-flight checks passed"
    echo ""

    # Calculate date ranges
    local end_date=$(date -u +%Y-%m-%d)
    local start_date_30=$(date -u -d "30 days ago" +%Y-%m-%d 2>/dev/null || date -u -v-30d +%Y-%m-%d)
    local start_date_7=$(date -u -d "7 days ago" +%Y-%m-%d 2>/dev/null || date -u -v-7d +%Y-%m-%d)
    local month_start=$(date -u +%Y-%m-01)
    local current_day=$(date -u +%d | sed 's/^0*//')
    local days_in_month=$(date -u -d "$(date -u +%Y-%m-01) +1 month -1 day" +%d 2>/dev/null || date -u -v1d -v+1m -v-1d +%d)

    # Get total costs
    log_info "Fetching cost data from AWS Cost Explorer..."
    local mtd_cost=$(get_total_cost "$month_start" "$end_date")
    local last_7_days_cost=$(get_total_cost "$start_date_7" "$end_date")
    local last_30_days_cost=$(get_total_cost "$start_date_30" "$end_date")
    echo ""

    # Display summary
    log_header "Cost Summary"
    echo ""
    log_info "Month-to-date ($(date -u +%B)): \$$(printf "%.2f" "$mtd_cost")"
    log_info "Last 7 days: \$$(printf "%.2f" "$last_7_days_cost")"
    log_info "Last 30 days: \$$(printf "%.2f" "$last_30_days_cost")"
    echo ""

    # Display cost by service
    display_cost_by_service "$month_start" "$end_date"

    # Display daily costs
    display_daily_costs "$start_date_7" "$end_date" "7"

    # Display monthly projection
    display_monthly_projection "$mtd_cost" "$days_in_month" "$current_day"

    # Display budget status
    display_budget_status

    # Display optimization tips
    display_optimization_tips

    log_info "=========================================="
    log_success "Cost report completed"
    log_info "=========================================="
    echo ""
    log_info "For more details, visit AWS Cost Explorer:"
    log_info "https://console.aws.amazon.com/cost-management/home#/cost-explorer"
    echo ""
}

# Run main function
main "$@"
