#!/bin/bash
# =============================================================================
# PLUTO vProctor — Ollama AI Model Readiness & Inference Smoke Test
# Verifies daemon health, local model availability, and GPU inference execution
# =============================================================================
set -euo pipefail

OLLAMA_HOST="${OLLAMA_BASE_URL:-http://localhost:11434}"
MODEL_NAME="${1:-qwen2.5:3b}"
TIMEOUT_SEC=30

echo "=== PLUTO vProctor: Ollama Readiness & Smoke Test ==="
echo "Target Endpoint: $OLLAMA_HOST"
echo "Target Model   : $MODEL_NAME"

# 1. Daemon Liveness Check
echo -n "Checking Ollama daemon liveness... "
if ! curl -sf "${OLLAMA_HOST}/api/tags" > /dev/null 2>&1; then
    echo "FAILED"
    echo "🚨 ERROR: Ollama daemon is not responding at ${OLLAMA_HOST}." >&2
    echo "Ensure the pluto-staging-ollama container is running and port 11434 is accessible." >&2
    exit 1
fi
echo "ONLINE"

# 2. Model Availability Check
echo -n "Checking if model '${MODEL_NAME}' is present in local storage... "
TAGS_JSON=$(curl -sf "${OLLAMA_HOST}/api/tags")
if ! echo "$TAGS_JSON" | grep -q "\"name\":\"${MODEL_NAME}\""; then
    echo "NOT FOUND"
    echo "⚠️ Model '${MODEL_NAME}' is not downloaded in the Ollama persistent volume." >&2
    echo "Run the following command to pull the model:" >&2
    echo "  docker exec -it pluto-staging-ollama ollama pull ${MODEL_NAME}" >&2
    exit 2
fi
echo "FOUND"

# 3. Model Inference Smoke Test
echo "Executing forward inference smoke test against /api/generate..."
START_TIME=$(date +%s%N)

RESPONSE_JSON=$(curl -sf --max-time "$TIMEOUT_SEC" "${OLLAMA_HOST}/api/generate" \
    -H "Content-Type: application/json" \
    -d "{
        \"model\": \"${MODEL_NAME}\",
        \"prompt\": \"Respond with the single word OK if you are ready.\",
        \"stream\": false,
        \"options\": {
            \"temperature\": 0.1,
            \"num_ctx\": 1024
        }
    }")

END_TIME=$(date +%s%N)
ELAPSED_MS=$(( (END_TIME - START_TIME) / 1000000 ))

echo "Inference Response:"
echo "$RESPONSE_JSON" | jq '.' 2>/dev/null || echo "$RESPONSE_JSON"

GENERATED_TEXT=$(echo "$RESPONSE_JSON" | jq -r '.response' 2>/dev/null || echo "")

if [[ -z "$GENERATED_TEXT" ]]; then
    echo "🚨 ERROR: Model produced an empty response or invalid JSON." >&2
    exit 3
fi

echo "✓ Inference Smoke Test PASSED in ${ELAPSED_MS}ms."
echo "✓ Generated output: '${GENERATED_TEXT}'"
exit 0
