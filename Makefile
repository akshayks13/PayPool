.PHONY: setup backend frontend test

setup:
	python3.12 -m venv backend/.venv
	backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

backend:
	cd backend && .venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npm run typecheck
