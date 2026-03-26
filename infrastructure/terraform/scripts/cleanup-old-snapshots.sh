#!/bin/bash
# Script to clean up old RDS cluster snapshots
# Usage: ./cleanup-old-snapshots.sh <cluster-identifier> <days-to-keep>
# Example: ./cleanup-old-snapshots.sh festival-playlist-dev-aurora-cluster 7

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -ne 2 ]; then
    echo -e "${RED}Error: Invalid number of arguments${NC}"
    echo "Usage: $0 <cluster-identifier> <days-to-keep>"
    echo "Example: $0 festival-playlist-dev-aurora-cluster 7"
    exit 1
fi

CLUSTER_ID=$1
DAYS_TO_KEEP=$2

echo -e "${GREEN}=== RDS Snapshot Cleanup ===${NC}"
echo "Cluster: $CLUSTER_ID"
echo "Keeping snapshots from last $DAYS_TO_KEEP days"
echo ""

# Calculate cutoff date
CUTOFF_DATE=$(date -u -d "$DAYS_TO_KEEP days ago" +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-${DAYS_TO_KEEP}d +%Y-%m-%dT%H:%M:%S)
echo "Cutoff date: $CUTOFF_DATE"
echo ""

# Get all manual snapshots for the cluster
echo -e "${YELLOW}Fetching snapshots...${NC}"
SNAPSHOTS=$(aws rds describe-db-cluster-snapshots \
    --db-cluster-identifier "$CLUSTER_ID" \
    --snapshot-type manual \
    --query "DBClusterSnapshots[?SnapshotCreateTime<'$CUTOFF_DATE'].[DBClusterSnapshotIdentifier,SnapshotCreateTime,AllocatedStorage]" \
    --output text)

if [ -z "$SNAPSHOTS" ]; then
    echo -e "${GREEN}No old snapshots found. Nothing to delete.${NC}"
    exit 0
fi

# Count snapshots
SNAPSHOT_COUNT=$(echo "$SNAPSHOTS" | wc -l)
echo -e "${YELLOW}Found $SNAPSHOT_COUNT snapshot(s) older than $DAYS_TO_KEEP days:${NC}"
echo ""

# Display snapshots to be deleted
echo "$SNAPSHOTS" | while IFS=$'\t' read -r SNAPSHOT_ID CREATE_TIME SIZE; do
    echo "  - $SNAPSHOT_ID (Created: $CREATE_TIME, Size: ${SIZE}GB)"
done
echo ""

# Confirm deletion
read -p "Do you want to delete these snapshots? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Deletion cancelled.${NC}"
    exit 0
fi

# Delete snapshots
echo ""
echo -e "${YELLOW}Deleting snapshots...${NC}"
DELETED_COUNT=0
FAILED_COUNT=0

echo "$SNAPSHOTS" | while IFS=$'\t' read -r SNAPSHOT_ID CREATE_TIME SIZE; do
    echo -n "Deleting $SNAPSHOT_ID... "
    if aws rds delete-db-cluster-snapshot \
        --db-cluster-snapshot-identifier "$SNAPSHOT_ID" \
        --output text > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Deleted${NC}"
        DELETED_COUNT=$((DELETED_COUNT + 1))
    else
        echo -e "${RED}✗ Failed${NC}"
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
done

echo ""
echo -e "${GREEN}=== Cleanup Complete ===${NC}"
echo "Deleted: $DELETED_COUNT snapshot(s)"
if [ $FAILED_COUNT -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED_COUNT snapshot(s)${NC}"
fi
