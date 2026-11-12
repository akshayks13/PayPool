#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x backend/.venv/bin/python || ! -d frontend/node_modules ]]; then
  echo "Run make setup first."
  exit 1
fi
backend/.venv/bin/python - <<'PY'
import socket
from dotenv import dotenv_values
import os
values = {**dotenv_values("backend/.env"), **os.environ}
if not all(values.get(k) for k in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET")):
    raise SystemExit("Add your sandbox PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET privately to backend/.env.")
for port in (3000, 8000):
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family) as client:
                client.settimeout(0.3)
                occupied = client.connect_ex((host, port)) == 0
        except OSError:
            occupied = False
        if occupied:
            raise SystemExit(f"Port {port} is in use. Stop the existing PayPool run before starting sandbox mode.")
PY
mkdir -p backend/data
export DATABASE_URL="sqlite:///$PWD/backend/data/paypal-sandbox.db"
export PAYPOOL_DEMO_MODE=true
export PAYPOOL_PAYMENT_PROVIDER=paypal_sandbox
export PAYPOOL_FRONTEND_URL=http://localhost:3000
export PAYPOOL_COOKIE_SECURE=false
export PAYPOOL_ENABLE_LEGACY_API=false
export PAYPOOL_POSTGIS=false
export PAYPOOL_PREPARE_DEMO=false
export PAYPOOL_PREPARE_JUDGES=true
export API_BASE_URL=http://127.0.0.1:8000
export PAYPAL_LOGIN_ENABLED=false
export ACP_ENABLED=false
echo "PayPal Sandbox checkout enabled. No real money moves."
echo "Separate persistent database: backend/data/paypal-sandbox.db"
echo "Labelled buying examples are prepared by the worker; payments require sandbox buyer approval."
exec bash scripts/dev.sh
