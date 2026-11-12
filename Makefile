.PHONY: setup dev demo sandbox backend frontend worker migrate test postman-demo

setup:
	python3.12 -m venv backend/.venv
	backend/.venv/bin/python -m pip install --upgrade "pip>=26.2,<27"
	backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

backend:
	cd backend && .venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev -- --hostname localhost --port 3000

worker:
	cd backend && .venv/bin/python -m app.platform.worker

postman-demo:
	bash scripts/postman-demo.sh

migrate:
	cd backend && mkdir -p data && .venv/bin/python -m alembic upgrade head

dev:
	bash scripts/dev.sh

demo:
	bash scripts/demo.sh

sandbox:
	bash scripts/sandbox.sh

test:
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npm run typecheck
