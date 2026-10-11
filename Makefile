.PHONY: help build up down logs shell test lint format typecheck db-migrate db-reset deploy clean

# Default target
help:
	@echo "Oggy Reels Bot - Development Commands"
	@echo ""
	@echo "Docker:"
	@echo "  make build       Build Docker images"
	@echo "  make up          Start all services"
	@echo "  make down        Stop all services"
	@echo "  make logs        Follow logs"
	@echo "  make shell       Open shell in app container"
	@echo ""
	@echo "Development:"
	@echo "  make test        Run tests"
	@echo "  make lint        Run linter (ruff)"
	@echo "  make format      Format code (ruff)"
	@echo "  make typecheck   Run mypy"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate  Run Alembic migrations"
	@echo "  make db-reset    Reset database (WARNING: destroys data)"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy      Deploy to VPS (requires config)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean       Clean up Docker resources"

# Docker commands
build:
	docker compose build --no-cache

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

shell:
	docker compose exec app bash

# Development commands
test:
	docker compose exec app pytest -v

lint:
	docker compose exec app ruff check src/

format:
	docker compose exec app ruff format src/

typecheck:
	docker compose exec app mypy src/

# Database commands
db-migrate:
	docker compose exec app alembic upgrade head

db-reset:
	@read -p "This will destroy all data. Continue? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose exec -T postgres psql -U oggy -d oggy_bot -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"; \
		docker compose exec app alembic upgrade head; \
	fi

# Deployment
deploy:
	./scripts/deploy.sh

# Cleanup
clean:
	docker compose down -v --remove-orphans
	docker system prune -f