#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x backend/.venv/bin/python ]] || ! command -v npx >/dev/null; then
  echo "Run make setup first; Python and Node/npx are required."
  exit 1
fi
paypool_run_dir=$(mktemp -d "${TMPDIR:-/tmp}/paypool-postman.XXXXXX")
paypool_api_pid=""
cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$paypool_api_pid" ]]; then
    kill "$paypool_api_pid" 2>/dev/null || true
    wait "$paypool_api_pid" 2>/dev/null || true
  fi
  rm -rf "$paypool_run_dir"
}
trap cleanup EXIT INT TERM
backend/.venv/bin/python - <<'PY'
import socket
try:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 8200))
except OSError:
    raise SystemExit("Port 8200 is already in use; refusing to run against an existing API.")
PY
# An independent database and explicit providers keep the walkthrough isolated.
(cd backend && exec env DATABASE_URL="sqlite:///$paypool_run_dir/demo.db" \
  PAYPOOL_DEMO_MODE=true PAYPOOL_PAYMENT_PROVIDER=demo PAYPOOL_LLM_PROVIDER=deterministic \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8200) \
  >"$paypool_run_dir/api.log" 2>&1 &
paypool_api_pid=$!
backend/.venv/bin/python - "$paypool_api_pid" <<'PY'
import os
import sys
import time
import httpx
for _ in range(50):
    try:
        os.kill(int(sys.argv[1]), 0)
    except ProcessLookupError:
        raise SystemExit("Disposable API failed to start. Check that port 8200 is free.")
    try:
        if httpx.get("http://127.0.0.1:8200/health", timeout=1).is_success:
            break
    except httpx.HTTPError:
        pass
    time.sleep(0.2)
else:
    raise SystemExit("Disposable API did not become ready.")
PY
# Keep tooling outside application dependencies. The collection contains no key.
npx --yes newman@6.2.3 run contracts/postman/paypool.postman_collection.json --bail
