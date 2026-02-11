.PHONY: up down db-up redis-up migrate seed backend frontend install test lint

# Infrastructure
up:
	docker compose up -d

down:
	docker compose down

db-up:
	docker compose up -d db

redis-up:
	docker compose up -d redis

# Backend
install-backend:
	cd backend && pip install -e ".[dev]"

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	cd backend && alembic upgrade head

migrate-new:
	cd backend && alembic revision --autogenerate -m "$(msg)"

seed:
	cd backend && python -m app.seed.run

test-backend:
	cd backend && pytest -v

lint-backend:
	cd backend && ruff check . && ruff format --check .

format-backend:
	cd backend && ruff check --fix . && ruff format .

# Frontend
install-frontend:
	cd frontend && npm install

frontend:
	cd frontend && npm run dev

build-frontend:
	cd frontend && npm run build

lint-frontend:
	cd frontend && npm run lint

# Combined
install: install-backend install-frontend

test: test-backend

lint: lint-backend lint-frontend
