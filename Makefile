.PHONY: up down logs migrate seed test test-unit test-int lint format shell build

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

migrate:
	docker compose -f infra/docker-compose.yml exec api alembic upgrade head

seed:
	docker compose -f infra/docker-compose.yml exec api python scripts/seed_dev.py

test:
	cd backend && pytest

test-unit:
	cd backend && pytest tests/unit/ -v

test-int:
	cd backend && pytest tests/integration/ -v --timeout=30

lint:
	cd backend && ruff check . && mypy app/connectors app/policy_engine

format:
	cd backend && ruff format .

shell:
	docker compose -f infra/docker-compose.yml exec api bash

build:
	docker compose -f infra/docker-compose.yml build
