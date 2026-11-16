#!/bin/bash
# =============================================================================
# PLUTO vProctor — EBS Volume Disk Capacity Monitoring Script
# Checks filesystem usage and alerts when utilization crosses warning threshold
# =============================================================================
set -euo pipefail

TARGET_MOUNT="${1:-/}"
WARNING_THRESHOLD_PERCENT="${2:-80}"
CRITICAL_THRESHOLD_PERCENT=90

echo "=== PLUTO vProctor: Disk Capacity Check ==="
echo "Target Mount : $TARGET_MOUNT"
echo "Warning Level: ${WARNING_THRESHOLD_PERCENT}%"

USAGE_PERCENT=$(df -P "$TARGET_MOUNT" | awk 'NR==2 {gsub("%","",$5); print $5}')
AVAIL_HUMAN=$(df -h "$TARGET_MOUNT" | awk 'NR==2 {print $4}')
TOTAL_HUMAN=$(df -h "$TARGET_MOUNT" | awk 'NR==2 {print $2}')

echo "Disk Utilization: ${USAGE_PERCENT}% (${AVAIL_HUMAN} available of ${TOTAL_HUMAN})"

if [[ "$USAGE_PERCENT" -ge "$CRITICAL_THRESHOLD_PERCENT" ]]; then
    echo "🚨 CRITICAL ALERT: Disk usage on $TARGET_MOUNT is at ${USAGE_PERCENT}%! Immediate cleanup required!" >&2
    echo "Action required: purge dangling docker images, prune old recordings, or expand EBS volume." >&2
    exit 2
elif [[ "$USAGE_PERCENT" -ge "$WARNING_THRESHOLD_PERCENT" ]]; then
    echo "⚠️ WARNING: Disk usage on $TARGET_MOUNT is at ${USAGE_PERCENT}%, exceeding ${WARNING_THRESHOLD_PERCENT}% threshold." >&2
    exit 1
else
    echo "✓ Disk capacity is healthy (below ${WARNING_THRESHOLD_PERCENT}% threshold)."
    exit 0
fi
