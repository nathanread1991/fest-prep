#!/bin/bash

# Simple script to check which AWS account you're using
# and what resources exist

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

AWS_PROFILE="${AWS_PROFILE:-festival-playlist}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AWS Account Diagnostic${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get account info
echo -e "${BLUE}Checking AWS credentials...${NC}"
ACCOUNT_INFO=$(aws sts get-caller-identity --profile "$AWS_PROFILE" 2>&1)

if [ $? -eq 0 ]; then
    ACCOUNT_ID=$(echo "$ACCOUNT_INFO" | grep -o '"Account": "[0-9]*"' | grep -o '[0-9]*')
    USER_ARN=$(echo "$ACCOUNT_INFO" | grep -o '"Arn": "[^"]*"' | cut -d'"' -f4)
    
    echo -e "${GREEN}✓${NC} AWS credentials valid"
    echo -e "${BLUE}Account ID:${NC} $ACCOUNT_ID"
    echo -e "${BLUE}User ARN:${NC} $USER_ARN"
    echo -e "${BLUE}Profile:${NC} $AWS_PROFILE"
else
    echo -e "${YELLOW}✗${NC} Failed to get AWS credentials"
    echo "$ACCOUNT_INFO"
    exit 1
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Resources in Account $ACCOUNT_ID${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check SNS topics
echo -e "${BLUE}SNS Topics:${NC}"
SNS_TOPICS=$(aws sns list-topics --profile "$AWS_PROFILE" --region eu-west-2 --query 'Topics[*].TopicArn' --output text 2>&1)
if [ $? -eq 0 ] && [ -n "$SNS_TOPICS" ]; then
    echo "$SNS_TOPICS" | while read -r topic; do
        if [[ "$topic" == *"festival"* ]] || [[ "$topic" == *"budget"* ]]; then
            echo -e "  ${GREEN}✓${NC} $topic"
        fi
    done
else
    echo -e "  ${YELLOW}No SNS topics found or error accessing${NC}"
fi

echo ""

# Check budgets
echo -e "${BLUE}AWS Budgets:${NC}"
BUDGETS=$(aws budgets describe-budgets --account-id "$ACCOUNT_ID" --profile "$AWS_PROFILE" --query 'Budgets[*].BudgetName' --output text 2>&1)
if [ $? -eq 0 ] && [ -n "$BUDGETS" ]; then
    echo "$BUDGETS" | tr '\t' '\n' | while read -r budget; do
        if [ -n "$budget" ]; then
            echo -e "  ${GREEN}✓${NC} $budget"
        fi
    done
else
    if [[ "$BUDGETS" == *"AccessDenied"* ]]; then
        echo -e "  ${YELLOW}✗ Access denied - check IAM permissions${NC}"
    elif [[ "$BUDGETS" == *"does not match"* ]]; then
        echo -e "  ${YELLOW}✗ Account mismatch error${NC}"
        echo -e "  ${YELLOW}This usually means budgets exist in a different account${NC}"
    else
        echo -e "  ${YELLOW}No budgets found${NC}"
    fi
fi

echo ""

# Check CloudWatch dashboards
echo -e "${BLUE}CloudWatch Dashboards:${NC}"
DASHBOARDS=$(aws cloudwatch list-dashboards --profile "$AWS_PROFILE" --region eu-west-2 --query 'DashboardEntries[*].DashboardName' --output text 2>&1)
if [ $? -eq 0 ] && [ -n "$DASHBOARDS" ]; then
    echo "$DASHBOARDS" | tr '\t' '\n' | while read -r dashboard; do
        if [[ "$dashboard" == *"festival"* ]] || [[ "$dashboard" == *"cost"* ]]; then
            echo -e "  ${GREEN}✓${NC} $dashboard"
        fi
    done
else
    echo -e "  ${YELLOW}No dashboards found${NC}"
fi

echo ""

# Check Terraform state
echo -e "${BLUE}Terraform State:${NC}"
if [ -f "terraform/terraform.tfstate" ]; then
    STATE_ACCOUNT=$(grep -o '"account_id": "[0-9]*"' terraform/terraform.tfstate | head -1 | grep -o '[0-9]*')
    if [ -n "$STATE_ACCOUNT" ]; then
        if [ "$STATE_ACCOUNT" == "$ACCOUNT_ID" ]; then
            echo -e "  ${GREEN}✓${NC} Terraform state matches current account ($STATE_ACCOUNT)"
        else
            echo -e "  ${YELLOW}⚠${NC} Terraform state is for account $STATE_ACCOUNT"
            echo -e "  ${YELLOW}⚠${NC} But you're using account $ACCOUNT_ID"
            echo -e "  ${YELLOW}This might cause issues!${NC}"
        fi
    else
        echo -e "  ${BLUE}ℹ${NC} Terraform state exists but no account ID found"
    fi
else
    echo -e "  ${YELLOW}No terraform.tfstate file found${NC}"
    echo -e "  ${BLUE}ℹ${NC} Run 'terraform apply' to create resources"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Your AWS Account:${NC} $ACCOUNT_ID"
echo -e "${GREEN}Profile:${NC} $AWS_PROFILE"
echo ""
echo "All resources will be created in account: $ACCOUNT_ID"
echo ""
