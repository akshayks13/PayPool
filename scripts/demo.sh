#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x backend/.venv/bin/python || ! -d frontend/node_modules ]]; then
  echo "Run make setup first."
  exit 1
fi
backend/.venv/bin/python - <<'PY'
import socket
for port in (3000, 8000):
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family) as client:
                client.settimeout(0.3)
                occupied = client.connect_ex((host, port)) == 0
        except OSError:
            occupied = False
        if occupied:
            raise SystemExit(f"Port {port} is in use. Stop the existing PayPool process before starting a clean demo.")
    try:
        with socket.socket() as server:
            server.bind(("127.0.0.1", port))
    except OSError:
        raise SystemExit(f"Port {port} is in use. Stop the existing PayPool process before starting a clean demo.")
PY
paypool_demo_dir=$(mktemp -d "${TMPDIR:-/tmp}/paypool-demo.XXXXXX")
echo "Fresh PayPool simulator database: $paypool_demo_dir/demo.db"
echo "This run preserves your existing database. The new demo database is retained after stopping."
export DATABASE_URL="sqlite:///$paypool_demo_dir/demo.db"
export PAYPOOL_DEMO_MODE=true
export PAYPOOL_PAYMENT_PROVIDER=demo
export PAYPOOL_ENABLE_LEGACY_API=false
export PAYPOOL_POSTGIS=false
export PAYPOOL_COOKIE_SECURE=false
export PAYPOOL_FRONTEND_URL=http://localhost:3000
export API_BASE_URL=http://127.0.0.1:8000
export PAYPAL_LOGIN_ENABLED=false
export ACP_ENABLED=false
exec bash scripts/dev.sh
