#!/bin/bash

# ============================================================================
# Populate Secrets Script
# ============================================================================
# This script helps populate AWS Secrets Manager secrets for the application
#
# Usage:
#   ./populate-secrets.sh
#
# Prerequisites:
#   - AWS CLI configured with festival-playlist profile
#   - Terraform infrastructure already provisioned
#   - Spotify API credentials (from https://developer.spotify.com/)
#   - Setlist.fm API key (from https://api.setlist.fm/)
# ============================================================================

set -e

# Configuration
PROFILE="festival-playlist"
REGION="eu-west-2"
PROJECT="festival-playlist"
ENVIRONMENT="dev"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    log_success "AWS CLI is installed"
}

check_aws_credentials() {
    if ! aws sts get-caller-identity --profile "$PROFILE" &> /dev/null; then
        log_error "AWS credentials not configured for profile: $PROFILE"
        exit 1
    fi
    log_success "AWS credentials are configured"
}

get_secret_arn() {
    local secret_name=$1
    aws secretsmanager describe-secret \
        --secret-id "$secret_name" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query 'ARN' \
        --output text 2>/dev/null || echo ""
}

check_secret_exists() {
    local secret_name=$1
    local arn=$(get_secret_arn "$secret_name")
    if [ -z "$arn" ]; then
        log_error "Secret not found: $secret_name"
        log_error "Please provision infrastructure first with: terraform apply"
        return 1
    fi
    log_success "Secret exists: $secret_name"
    return 0
}

populate_spotify_secret() {
    local secret_name="${PROJECT}-${ENVIRONMENT}-spotify"

    log_info "Populating Spotify API credentials..."

    if ! check_secret_exists "$secret_name"; then
        return 1
    fi

    echo ""
    log_info "Please provide your Spotify API credentials"
    log_info "Get them from: https://developer.spotify.com/dashboard"
    echo ""

    read -p "Spotify Client ID: " spotify_client_id
    read -sp "Spotify Client Secret: " spotify_client_secret
    echo ""

    if [ -z "$spotify_client_id" ] || [ -z "$spotify_client_secret" ]; then
        log_error "Spotify credentials cannot be empty"
        return 1
    fi

    local secret_value=$(cat <<EOF
{
  "client_id": "$spotify_client_id",
  "client_secret": "$spotify_client_secret"
}
EOF
)

    if aws secretsmanager put-secret-value \
        --secret-id "$secret_name" \
        --secret-string "$secret_value" \
        --profile "$PROFILE" \
        --region "$REGION" &> /dev/null; then
        log_success "Spotify credentials populated successfully"
        return 0
    else
        log_error "Failed to populate Spotify credentials"
        return 1
    fi
}

populate_setlistfm_secret() {
    local secret_name="${PROJECT}-${ENVIRONMENT}-setlistfm"

    log_info "Populating Setlist.fm API key..."

    if ! check_secret_exists "$secret_name"; then
        return 1
    fi

    echo ""
    log_info "Please provide your Setlist.fm API key"
    log_info "Get it from: https://api.setlist.fm/docs/1.0/index.html"
    echo ""

    read -sp "Setlist.fm API Key: " setlistfm_api_key
    echo ""

    if [ -z "$setlistfm_api_key" ]; then
        log_error "Setlist.fm API key cannot be empty"
        return 1
    fi

    local secret_value=$(cat <<EOF
{
  "api_key": "$setlistfm_api_key"
}
EOF
)

    if aws secretsmanager put-secret-value \
        --secret-id "$secret_name" \
        --secret-string "$secret_value" \
        --profile "$PROFILE" \
        --region "$REGION" &> /dev/null; then
        log_success "Setlist.fm API key populated successfully"
        return 0
    else
        log_error "Failed to populate Setlist.fm API key"
        return 1
    fi
}

verify_secret() {
    local secret_name=$1
    local display_name=$2

    log_info "Verifying $display_name secret..."

    if aws secretsmanager get-secret-value \
        --secret-id "$secret_name" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query 'SecretString' \
        --output text &> /dev/null; then
        log_success "$display_name secret is accessible"
        return 0
    else
        log_error "$display_name secret is not accessible"
        return 1
    fi
}

verify_all_secrets() {
    log_info "Verifying all secrets..."
    echo ""

    local all_ok=true

    if ! verify_secret "${PROJECT}-${ENVIRONMENT}-db-credentials" "Database"; then
        all_ok=false
    fi

    if ! verify_secret "${PROJECT}-${ENVIRONMENT}-redis-url" "Redis"; then
        all_ok=false
    fi

    if ! verify_secret "${PROJECT}-${ENVIRONMENT}-spotify" "Spotify"; then
        all_ok=false
    fi

    if ! verify_secret "${PROJECT}-${ENVIRONMENT}-setlistfm" "Setlist.fm"; then
        all_ok=false
    fi

    if ! verify_secret "${PROJECT}-${ENVIRONMENT}-jwt-secret" "JWT"; then
        all_ok=false
    fi

    echo ""
    if [ "$all_ok" = true ]; then
        log_success "All secrets are properly configured!"
        return 0
    else
        log_error "Some secrets are not properly configured"
        return 1
    fi
}

# ============================================================================
# Main Script
# ============================================================================

main() {
    echo "============================================================================"
    echo "  Festival Playlist Generator - Populate Secrets"
    echo "============================================================================"
    echo ""

    # Check prerequisites
    log_info "Checking prerequisites..."
    check_aws_cli
    check_aws_credentials
    echo ""

    # Populate secrets
    log_info "Starting secret population..."
    echo ""

    populate_spotify_secret
    echo ""

    populate_setlistfm_secret
    echo ""

    # Verify all secrets
    verify_all_secrets

    echo ""
    echo "============================================================================"
    log_success "Secret population complete!"
    echo "============================================================================"
    echo ""
    log_info "Next steps:"
    echo "  1. Verify infrastructure: ./validate-infrastructure.sh"
    echo "  2. Build and push Docker image to ECR"
    echo "  3. Deploy application to ECS"
    echo ""
}

# Run main function
main
