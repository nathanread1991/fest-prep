#!/bin/bash
# Script to list RDS cluster snapshots
# Usage: ./list-snapshots.sh <cluster-identifier>
# Example: ./list-snapshots.sh festival-playlist-dev-aurora-cluster

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -ne 1 ]; then
    echo "Usage: $0 <cluster-identifier>"
    echo "Example: $0 festival-playlist-dev-aurora-cluster"
    exit 1
fi

CLUSTER_ID=$1

echo -e "${GREEN}=== RDS Cluster Snapshots ===${NC}"
echo "Cluster: $CLUSTER_ID"
echo ""

# Get all manual snapshots for the cluster
echo -e "${YELLOW}Fetching snapshots...${NC}"
SNAPSHOTS=$(aws rds describe-db-cluster-snapshots \
    --db-cluster-identifier "$CLUSTER_ID" \
    --snapshot-type manual \
    --query "DBClusterSnapshots[*].[DBClusterSnapshotIdentifier,SnapshotCreateTime,Status,AllocatedStorage,Engine,EngineVersion]" \
    --output text | sort -r)

if [ -z "$SNAPSHOTS" ]; then
    echo "No snapshots found for cluster: $CLUSTER_ID"
    exit 0
fi

# Count snapshots
SNAPSHOT_COUNT=$(echo "$SNAPSHOTS" | wc -l)
echo -e "${BLUE}Found $SNAPSHOT_COUNT snapshot(s):${NC}"
echo ""

# Display snapshots in a table format
printf "%-60s %-25s %-12s %-8s %-20s %-10s\n" "Snapshot ID" "Created" "Status" "Size (GB)" "Engine" "Version"
printf "%-60s %-25s %-12s %-8s %-20s %-10s\n" "$(printf '%.0s-' {1..60})" "$(printf '%.0s-' {1..25})" "$(printf '%.0s-' {1..12})" "$(printf '%.0s-' {1..8})" "$(printf '%.0s-' {1..20})" "$(printf '%.0s-' {1..10})"

echo "$SNAPSHOTS" | while IFS=$'\t' read -r SNAPSHOT_ID CREATE_TIME STATUS SIZE ENGINE VERSION; do
    printf "%-60s %-25s %-12s %-8s %-20s %-10s\n" "$SNAPSHOT_ID" "$CREATE_TIME" "$STATUS" "$SIZE" "$ENGINE" "$VERSION"
done

echo ""
echo -e "${GREEN}Total snapshots: $SNAPSHOT_COUNT${NC}"

# Calculate total storage
TOTAL_SIZE=$(echo "$SNAPSHOTS" | awk '{sum += $4} END {print sum}')
echo -e "${GREEN}Total storage: ${TOTAL_SIZE}GB${NC}"

# Estimate cost (first 7 days free, then $0.095/GB/month)
echo ""
echo -e "${YELLOW}Cost Estimate:${NC}"
echo "  - First 7 days: Free"
echo "  - After 7 days: \$0.095/GB/month"
echo "  - Current total if all > 7 days old: ~\$$(echo "scale=2; $TOTAL_SIZE * 0.095" | bc)/month"
