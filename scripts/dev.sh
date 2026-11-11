#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x backend/.venv/bin/python || ! -d frontend/node_modules ]]; then
  echo "Run make setup first."
  exit 1
fi
mkdir -p backend/data
(cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -c "from app.main import app")
pids=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait || true
}
trap cleanup EXIT INT TERM
(cd backend && exec .venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
pids+=("$!")
(cd backend && exec .venv/bin/python -m app.platform.worker) &
pids+=("$!")
(cd frontend && exec npm run dev -- --hostname localhost --port 3000) &
pids+=("$!")
echo "PayPool: http://localhost:3000 | API: http://localhost:8000/docs | worker active"
while true; do
  for pid in "${pids[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then exit 1; fi
  done
  sleep 1
done
