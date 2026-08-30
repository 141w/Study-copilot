.PHONY: help build up down restart logs logs-backend logs-frontend logs-db \
        shell backend-shell migrate migrate-create clean pull prune test-backend

SHELL := /bin/bash
COMPOSE := docker compose

help: ## Show this help
	@echo "Study Copilot - Docker Commands"
	@echo "================================"
	@grep -E '(^[a-zA-Z_-]+:.*?## .*)' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build all Docker images
	$(COMPOSE) build --parallel

up: ## Start all services (detached)
	$(COMPOSE) up -d

down: ## Stop all services (keep volumes)
	$(COMPOSE) down

restart: down up ## Restart all services

logs: ## Tail all service logs
	$(COMPOSE) logs -f --tail=100

logs-backend: ## Tail backend logs
	$(COMPOSE) logs -f --tail=100 backend

logs-frontend: ## Tail frontend logs
	$(COMPOSE) logs -f --tail=100 frontend

logs-db: ## Tail database logs
	$(COMPOSE) logs -f --tail=100 db

shell: ## Open shell in backend container
	$(COMPOSE) exec backend bash

backend-shell: shell ## Alias: open backend shell

migrate: ## Run database migrations manually
	$(COMPOSE) exec backend alembic upgrade head

migrate-create: ## Create a new alembic migration (MSG="description")
	@if [ -z "$(MSG)" ]; then echo "Usage: make migrate-create MSG=\"description\""; exit 1; fi
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(MSG)"

clean: ## Stop and remove all containers + volumes (data loss!)
	$(COMPOSE) down -v

pull: ## Pull latest base images
	$(COMPOSE) pull

prune: ## Remove unused Docker resources
	docker system prune -f --volumes

test-backend: ## Run backend tests in container
	$(COMPOSE) exec backend pytest tests/ -v --tb=short
