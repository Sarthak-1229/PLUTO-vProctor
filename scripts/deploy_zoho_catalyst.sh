#!/usr/bin/env bash
# ==============================================================================
# PLUTO vProctor — Zoho Catalyst Automated Deployment Script (POSIX/Bash)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== [PLUTO vProctor] Initializing Zoho Catalyst Deployment ==="

# 1. Detect Catalyst CLI (Global catalyst or npx zcatalyst-cli)
if command -v catalyst &> /dev/null; then
    CATALYST_CMD="catalyst"
else
    echo "[PLUTO vProctor] 'catalyst' not found in PATH. Using 'npx --yes zcatalyst-cli'..."
    CATALYST_CMD="npx --yes zcatalyst-cli"
fi

# 2. Verify Authentication
if ! ${CATALYST_CMD} whoami &> /dev/null; then
    echo "[AUTHENTICATION REQUIRED] You are not currently logged in to Zoho Catalyst."
    echo "Please authenticate by executing:"
    echo "    ${CATALYST_CMD} login"
    echo "Or if logging in to India Data Center (ap-south-1):"
    echo "    ${CATALYST_CMD} login --dc in"
    echo "After logging in, re-run this script to execute deployment."
    exit 1
fi

# 3. Build Frontend Distribution
echo "[PLUTO vProctor] Building Frontend Production SPA..."
cd "${ROOT_DIR}/frontend"
npm install
npm run build

# 4. Validate Deployment Package
echo "[PLUTO vProctor] Validating Deployment Package..."
cd "${ROOT_DIR}"
if [ -f "backend/.venv/bin/python" ]; then
    PY_BIN="backend/.venv/bin/python"
elif [ -f "backend/.venv/Scripts/python.exe" ]; then
    PY_BIN="backend/.venv/Scripts/python.exe"
else
    PY_BIN="python3"
fi

"${PY_BIN}" scripts/validate_deployment_package.py

# 5. Deploy AppSail and Client Hosting
echo "[PLUTO vProctor] Deploying AppSail and Web Client to Zoho Catalyst..."
${CATALYST_CMD} deploy --only appsail,client

echo "=== [PLUTO vProctor] Deployment Completed Successfully! ==="
echo "Inspect live logs via: ${CATALYST_CMD} appsail:logs --name pluto-backend"
