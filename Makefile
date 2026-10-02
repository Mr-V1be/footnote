SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose
BACKEND := cd backend && uv run --frozen
RUN_DIR := .run

.PHONY: help env up down migrate models corpus seed setup api worker web gate demo-documents stop

help: ## Show available targets
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'

env: ## Create .env with random secrets (keeps existing values)
	@python3 scripts/init-env.py

up: ## Start PostgreSQL, Redis, Keycloak and Mailpit
	$(COMPOSE) up -d --wait

down: ## Stop the infrastructure containers (data is kept)
	$(COMPOSE) stop

migrate: ## Apply database migrations
	$(BACKEND) snoska db migrate

models: ## Start Ollama on the project port and pull the models
	scripts/ollama-setup.sh

corpus: ## Ingest 152-FZ from the bundled snapshot and embed it
	$(BACKEND) snoska corpus sync --source snapshot --embed

seed: ## Provision demo organizations, members and documents
	$(BACKEND) snoska demo seed

setup: env up migrate models corpus seed ## Everything needed for a first run

api: ## Run the API on :46301
	$(BACKEND) snoska api

worker: ## Run background jobs and the outbox relay
	$(BACKEND) snoska worker

web: ## Run the web app on :46300
	cd frontend && pnpm dev

gate: ## Lint, typecheck, tests and source limits
	scripts/gate.sh

demo-documents: ## Rebuild the demo documents (needs LibreOffice)
	backend/.venv/bin/python scripts/demo/build_documents.py

stop: ## Stop Ollama and the containers
	-scripts/ollama-setup.sh stop
	$(COMPOSE) stop
