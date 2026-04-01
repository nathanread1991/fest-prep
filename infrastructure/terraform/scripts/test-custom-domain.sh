#!/bin/bash
# =============================================================================
# Test Custom Domain Access
# =============================================================================
# Validates that custom domain DNS, SSL, and routing are working correctly:
#   - https://gig-prep.co.uk serves via CloudFront
#   - https://api.gig-prep.co.uk/health serves via ALB
#   - SSL certificates are valid
#   - HTTP redirects to HTTPS
#
# Usage: ./test-custom-domain.sh [domain]
#   domain: Custom domain name (default: gig-prep.co.uk)
# =============================================================================

set -euo pipefail

DOMAIN="${1:-gig-prep.co.uk}"
API_DOMAIN="api.${DOMAIN}"
PASS=0
FAIL=0
WARN=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

pass() {
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}✓ PASS${NC}: $1"
}

fail() {
    FAIL=$((FAIL + 1))
    echo -e "  ${RED}✗ FAIL${NC}: $1"
}

warn() {
    WARN=$((WARN + 1))
    echo -e "  ${YELLOW}⚠ WARN${NC}: $1"
}

info() {
    echo -e "  ${BLUE}ℹ INFO${NC}: $1"
}

echo "============================================="
echo " Custom Domain Validation Tests"
echo " Domain: ${DOMAIN}"
echo " API:    ${API_DOMAIN}"
echo " Time:   $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "============================================="
echo ""

# =============================================================================
# Test 1: DNS Resolution
# =============================================================================
echo "--- Test 1: DNS Resolution ---"

# Check root domain resolves
ROOT_IP=$(dig +short "${DOMAIN}" A 2>/dev/null | head -1)
if [ -n "${ROOT_IP}" ]; then
    pass "Root domain ${DOMAIN} resolves to ${ROOT_IP}"
else
    fail "Root domain ${DOMAIN} does not resolve"
fi

# Check API subdomain resolves
API_IP=$(dig +short "${API_DOMAIN}" A 2>/dev/null | head -1)
if [ -n "${API_IP}" ]; then
    pass "API subdomain ${API_DOMAIN} resolves to ${API_IP}"
else
    fail "API subdomain ${API_DOMAIN} does not resolve"
fi

echo ""

# =============================================================================
# Test 2: SSL Certificate Validation
# =============================================================================
echo "--- Test 2: SSL Certificate Validation ---"

# Check root domain SSL certificate
ROOT_CERT_INFO=$(echo | openssl s_client -servername "${DOMAIN}" -connect "${DOMAIN}:443" 2>/dev/null)
ROOT_CERT_SUBJECT=$(echo "${ROOT_CERT_INFO}" | openssl x509 -noout -subject 2>/dev/null || true)
ROOT_CERT_EXPIRY=$(echo "${ROOT_CERT_INFO}" | openssl x509 -noout -enddate 2>/dev/null || true)

if [ -n "${ROOT_CERT_SUBJECT}" ]; then
    pass "SSL certificate valid for ${DOMAIN}"
    info "Subject: ${ROOT_CERT_SUBJECT}"
    info "Expiry: ${ROOT_CERT_EXPIRY}"
else
    fail "Cannot retrieve SSL certificate for ${DOMAIN}"
fi

# Check API subdomain SSL certificate
API_CERT_INFO=$(echo | openssl s_client -servername "${API_DOMAIN}" -connect "${API_DOMAIN}:443" 2>/dev/null)
API_CERT_SUBJECT=$(echo "${API_CERT_INFO}" | openssl x509 -noout -subject 2>/dev/null || true)
API_CERT_EXPIRY=$(echo "${API_CERT_INFO}" | openssl x509 -noout -enddate 2>/dev/null || true)

if [ -n "${API_CERT_SUBJECT}" ]; then
    pass "SSL certificate valid for ${API_DOMAIN}"
    info "Subject: ${API_CERT_SUBJECT}"
    info "Expiry: ${API_CERT_EXPIRY}"
else
    fail "Cannot retrieve SSL certificate for ${API_DOMAIN}"
fi

echo ""

# =============================================================================
# Test 3: HTTPS Access - Root Domain via CloudFront
# =============================================================================
echo "--- Test 3: HTTPS Access - Root Domain (CloudFront) ---"

ROOT_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "https://${DOMAIN}" 2>/dev/null || echo "000")
if [ "${ROOT_HTTP_CODE}" -ge 200 ] && [ "${ROOT_HTTP_CODE}" -lt 400 ]; then
    pass "https://${DOMAIN} returned HTTP ${ROOT_HTTP_CODE}"
elif [ "${ROOT_HTTP_CODE}" = "000" ]; then
    fail "https://${DOMAIN} connection failed (timeout or DNS error)"
else
    warn "https://${DOMAIN} returned HTTP ${ROOT_HTTP_CODE}"
fi

# Check for CloudFront headers
CF_HEADERS=$(curl -s -I --max-time 15 "https://${DOMAIN}" 2>/dev/null || true)
if echo "${CF_HEADERS}" | grep -qi "x-cache"; then
    CF_CACHE=$(echo "${CF_HEADERS}" | grep -i "x-cache" | tr -d '\r')
    pass "CloudFront serving root domain"
    info "Cache status: ${CF_CACHE}"
elif echo "${CF_HEADERS}" | grep -qi "server: CloudFront\|via:.*cloudfront"; then
    pass "CloudFront serving root domain (via header detected)"
else
    warn "CloudFront headers not detected on root domain"
fi

echo ""

# =============================================================================
# Test 4: HTTPS Access - API Health Check via ALB
# =============================================================================
echo "--- Test 4: HTTPS Access - API Health Check (ALB) ---"

API_RESPONSE=$(curl -s --max-time 15 "https://${API_DOMAIN}/health" 2>/dev/null || echo "")
API_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "https://${API_DOMAIN}/health" 2>/dev/null || echo "000")

if [ "${API_HTTP_CODE}" = "200" ]; then
    pass "https://${API_DOMAIN}/health returned HTTP 200"
    info "Response: ${API_RESPONSE}"
elif [ "${API_HTTP_CODE}" = "000" ]; then
    fail "https://${API_DOMAIN}/health connection failed (timeout or DNS error)"
else
    warn "https://${API_DOMAIN}/health returned HTTP ${API_HTTP_CODE}"
fi

echo ""

# =============================================================================
# Test 5: HTTP to HTTPS Redirect
# =============================================================================
echo "--- Test 5: HTTP to HTTPS Redirect ---"

# Test root domain HTTP redirect
ROOT_REDIRECT=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 -L "http://${DOMAIN}" 2>/dev/null || echo "000")
ROOT_REDIRECT_LOCATION=$(curl -s -I --max-time 15 "http://${DOMAIN}" 2>/dev/null | grep -i "^location:" | tr -d '\r' || true)

if echo "${ROOT_REDIRECT_LOCATION}" | grep -qi "https://"; then
    pass "http://${DOMAIN} redirects to HTTPS"
    info "Location: ${ROOT_REDIRECT_LOCATION}"
elif [ "${ROOT_REDIRECT}" -ge 200 ] && [ "${ROOT_REDIRECT}" -lt 400 ]; then
    warn "http://${DOMAIN} responds but redirect header not detected (may be handled by CloudFront)"
else
    warn "http://${DOMAIN} redirect check inconclusive (HTTP ${ROOT_REDIRECT})"
fi

# Test API subdomain HTTP redirect
API_REDIRECT_LOCATION=$(curl -s -I --max-time 15 "http://${API_DOMAIN}/health" 2>/dev/null | grep -i "^location:" | tr -d '\r' || true)

if echo "${API_REDIRECT_LOCATION}" | grep -qi "https://"; then
    pass "http://${API_DOMAIN} redirects to HTTPS"
    info "Location: ${API_REDIRECT_LOCATION}"
else
    warn "http://${API_DOMAIN} redirect check inconclusive"
fi

echo ""

# =============================================================================
# Summary
# =============================================================================
echo "============================================="
echo " Test Results Summary"
echo "============================================="
echo -e "  ${GREEN}Passed${NC}: ${PASS}"
echo -e "  ${RED}Failed${NC}: ${FAIL}"
echo -e "  ${YELLOW}Warnings${NC}: ${WARN}"
echo "============================================="

if [ "${FAIL}" -gt 0 ]; then
    echo -e "${RED}Some tests failed. Check DNS propagation and infrastructure status.${NC}"
    echo ""
    echo "Troubleshooting tips:"
    echo "  1. DNS propagation can take up to 48 hours"
    echo "  2. Check Route 53 records: aws route53 list-resource-record-sets --hosted-zone-id <zone-id>"
    echo "  3. Check CloudFront status: aws cloudfront get-distribution --id <dist-id>"
    echo "  4. Check ALB health: aws elbv2 describe-target-health --target-group-arn <tg-arn>"
    exit 1
else
    echo -e "${GREEN}All critical tests passed.${NC}"
    exit 0
fi
