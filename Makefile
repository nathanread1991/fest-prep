# Festival Playlist Generator — Local Development Makefile
# Wraps Docker Compose commands for common dev operations.

COMPOSE_DIR := services/api
COMPOSE     := docker compose -f $(COMPOSE_DIR)/docker-compose.yml
COMPOSE_AWS := $(COMPOSE) -f $(COMPOSE_DIR)/docker-compose.aws.yml
CONTAINER   := festival_app

.PHONY: up down test lint typecheck format migrate localstack logs

## Start all services
up:
	$(COMPOSE) up -d

## Stop all services
down:
	$(COMPOSE) down

## Run pytest inside the app container
test:
	docker exec $(CONTAINER) python -m pytest tests/ -v

## Run linting checks (black --check, isort --check, flake8)
lint:
	docker exec $(CONTAINER) black --check festival_playlist_generator/ tests/
	docker exec $(CONTAINER) isort --check-only festival_playlist_generator/ tests/
	docker exec $(CONTAINER) flake8 festival_playlist_generator/ tests/ --max-line-length=88 --extend-ignore=E203,W503

## Run mypy type checking
typecheck:
	docker exec $(CONTAINER) python -m mypy festival_playlist_generator/ --config-file=setup.cfg

## Auto-format code (black + isort)
format:
	docker exec $(CONTAINER) black festival_playlist_generator/ tests/
	docker exec $(CONTAINER) isort festival_playlist_generator/ tests/

## Run Alembic database migrations
migrate:
	docker exec $(CONTAINER) alembic upgrade head

## Start services with LocalStack AWS overlay
localstack:
	$(COMPOSE_AWS) up -d

## Follow app container logs
logs:
	$(COMPOSE) logs -f app
