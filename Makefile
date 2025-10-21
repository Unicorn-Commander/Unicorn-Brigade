.PHONY: help install dev test lint format clean docker-build docker-up docker-down docker-logs docker-test

help:
	@echo "Unicorn Brigade - Development Commands"
	@echo "======================================"
	@echo "install       - Install dependencies"
	@echo "dev           - Run in development mode"
	@echo "test          - Run tests"
	@echo "test-llm      - Run tests including LLM calls"
	@echo "lint          - Run linters"
	@echo "format        - Format code"
	@echo "clean         - Clean temporary files"
	@echo "docker-build  - Build Docker images"
	@echo "docker-up     - Start Docker services"
	@echo "docker-down   - Stop Docker services"
	@echo "docker-logs   - View Docker logs"
	@echo "docker-test   - Run tests in Docker"

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8100

test:
	pytest tests/ -v

test-llm:
	pytest tests/ -v --run-llm-tests

lint:
	ruff check app/ tests/
	mypy app/ --ignore-missing-imports

format:
	black app/ tests/
	ruff check app/ tests/ --fix

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f brigade-api

docker-test:
	docker compose exec brigade-api pytest tests/ -v

docker-restart:
	docker compose restart brigade-api

docker-clean:
	docker compose down -v
	docker system prune -f
