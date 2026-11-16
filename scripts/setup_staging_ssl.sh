#!/bin/bash
# =============================================================================
# PLUTO vProctor — Staging SSL/TLS Certificate Initialization Helper
# Prepares certificates in ./certs for Nginx TLS termination on port 443
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
CERTS_DIR="$ROOT_DIR/certs"

mkdir -p "$CERTS_DIR"

if [[ -f "$CERTS_DIR/fullchain.pem" && -f "$CERTS_DIR/privkey.pem" ]]; then
    echo "✓ Existing TLS certificates found in $CERTS_DIR"
    exit 0
fi

echo "No existing certificates found in $CERTS_DIR."
echo "Generating self-signed fallback certificate for staging initial bootstrap..."

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$CERTS_DIR/privkey.pem" \
    -out "$CERTS_DIR/fullchain.pem" \
    -subj "/C=US/ST=State/L=City/O=PLUTO-vProctor/CN=staging.local"

chmod 600 "$CERTS_DIR/privkey.pem"
chmod 644 "$CERTS_DIR/fullchain.pem"

echo "✓ Self-signed staging certificates generated successfully in $CERTS_DIR."
echo ""
echo "NOTE FOR PRODUCTION / PUBLIC STAGING:"
echo "To replace with real Let's Encrypt certificates, run:"
echo "  sudo certbot certonly --webroot -w /var/www/certbot -d staging.yourdomain.com"
echo "  sudo cp /etc/letsencrypt/live/staging.yourdomain.com/fullchain.pem $CERTS_DIR/"
echo "  sudo cp /etc/letsencrypt/live/staging.yourdomain.com/privkey.pem $CERTS_DIR/"
echo "  docker compose -f docker-compose.staging.yml exec frontend nginx -s reload"
