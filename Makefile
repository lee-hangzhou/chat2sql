.PHONY: help setup install dev test lint format clean \
       fe-install fe-dev fe-build \
       services-up services-down \
       docker-build docker-up docker-down docker-logs

# 帮助

help:
	@echo "Available commands:"
	@echo ""
	@echo "  Quick Start (local development):"
	@echo "    make setup          First-time project initialization"
	@echo "    make services-up    Start infrastructure services (MySQL, Redis, Milvus, Phoenix)"
	@echo "    make services-down  Stop infrastructure services"
	@echo "    make dev            Start backend dev server"
	@echo "    make fe-dev         Start frontend dev server"
	@echo ""
	@echo "  Backend:"
	@echo "    make install        Install backend dependencies"
	@echo "    make test           Run tests"
	@echo "    make lint           Run linter"
	@echo "    make format         Format code"
	@echo "    make clean          Clean cache files"
	@echo ""
	@echo "  Frontend:"
	@echo "    make fe-install     Install frontend dependencies"
	@echo "    make fe-build       Build frontend for production"
	@echo ""
	@echo "  Docker (full-stack):"
	@echo "    make docker-build   Build Docker image"
	@echo "    make docker-up      Start all services via Docker Compose"
	@echo "    make docker-down    Stop all services"
	@echo "    make docker-logs    Tail application logs"

# 项目初始化

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "[OK] .env created from .env.example — please edit it before starting."; \
	else \
		echo "[SKIP] .env already exists."; \
	fi
	pip install -r requirements.txt
	cd web && npm install
	@echo ""
	@echo "Setup complete. Next steps:"
	@echo "  1. Edit .env with your configuration"
	@echo "  2. make services-up"
	@echo "  3. make db-init"
	@echo "  4. make dev"

db-init:
	@. .env 2>/dev/null; \
	DB_NAME=$$(echo $$DATABASE_URL | sed -n 's|.*\/\([^?]*\).*|\1|p'); \
	DB_HOST=$$(echo $$DATABASE_URL | sed -n 's|.*@\([^:]*\):.*|\1|p'); \
	DB_PORT=$$(echo $$DATABASE_URL | sed -n 's|.*:\([0-9]*\)/.*|\1|p'); \
	DB_USER=$$(echo $$DATABASE_URL | sed -n 's|.*://\([^:]*\):.*|\1|p'); \
	DB_PASS=$$(echo $$DATABASE_URL | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p'); \
	echo "Creating database '$$DB_NAME' if not exists..."; \
	mysql -h $$DB_HOST -P $$DB_PORT -u $$DB_USER -p$$DB_PASS \
		-e "CREATE DATABASE IF NOT EXISTS \`$$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" \
		&& echo "[OK] Database '$$DB_NAME' ready." \
		|| echo "[FAIL] Could not create database. Check your DATABASE_URL and MySQL connection."

# 基础设施服务

services-up:
	docker compose up -d mysql redis etcd minio milvus-standalone phoenix
	@echo "Waiting for services to be healthy..."
	@docker compose ps

services-down:
	docker compose stop mysql redis etcd minio milvus-standalone phoenix
	docker compose rm -f mysql redis etcd minio milvus-standalone phoenix
	@echo "Infrastructure services stopped."

# 后端

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install pytest pytest-cov pytest-asyncio black ruff mypy pre-commit
	pre-commit install

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port $${PORT:-8000}

test:
	pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	ruff check app/ tests/

format:
	ruff check --fix app/ tests/
	ruff format app/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# 前端

fe-install:
	cd web && npm install

fe-dev:
	cd web && npm run dev

fe-build:
	cd web && npm run build

# Docker 全栈

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f app
