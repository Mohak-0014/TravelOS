#!/bin/bash
# fetch_secrets.sh — Pull production secrets from AWS Secrets Manager
# and write them to /opt/TravelOS/.env
#
# Usage:
#   ./infra/fetch_secrets.sh [secret-name]
#
# Prerequisites:
#   - AWS CLI installed and configured (or EC2 IAM role with SecretsManager access)
#   - Python 3 available (for JSON parsing)
#
# The script is idempotent — safe to re-run on every deploy.

set -euo pipefail

SECRET_NAME="${1:-travelos/prod}"
ENV_FILE="$(dirname "$(dirname "$(realpath "$0")")")/.env"

echo "▸ Fetching secret '${SECRET_NAME}' from AWS Secrets Manager..."
SECRET_JSON=$(aws secretsmanager get-secret-value \
  --secret-id "${SECRET_NAME}" \
  --query SecretString \
  --output text)

# Parse the JSON secret into KEY=VALUE .env format
echo "$SECRET_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for k, v in d.items():
    # Quote values that contain special characters
    if isinstance(v, str) and any(c in v for c in ' []{}\"'):
        print(f'{k}=\"{v}\"')
    else:
        print(f'{k}={v}')
" > "${ENV_FILE}"

# Append non-secret configuration that doesn't belong in Secrets Manager
cat >> "${ENV_FILE}" << 'EOF'

# ── Non-secret config (appended by fetch_secrets.sh) ────────────────────
ENVIRONMENT=production
LOG_LEVEL=INFO
RATE_LIMIT_ENABLED=true
RESILIENCE_ENABLED=true
QDRANT_HOST=qdrant
QDRANT_PORT=6333
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIM=384
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
EOF

chmod 600 "${ENV_FILE}"
echo "✔ Secrets written to ${ENV_FILE} (mode 600)"
