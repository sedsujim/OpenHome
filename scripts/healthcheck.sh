#!/usr/bin/env bash
set -euo pipefail

# OpenHome health check for Docker/Kubernetes
# Returns 0 if the API is responsive

URL="${1:-http://localhost:8000/api/v1/health}"

response=$(curl -sf --max-time 5 "$URL" 2>/dev/null || true)

if [ -z "$response" ]; then
    echo "UNHEALTHY: No response from $URL"
    exit 1
fi

status=$(echo "$response" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ "$status" = "ok" ]; then
    echo "HEALTHY"
    exit 0
else
    echo "UNHEALTHY: status=$status"
    exit 1
fi
