SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose
BACKEND := cd backend && uv run --frozen
RUN_DIR := .run

.PHONY: help env up down migrate corpus index seed setup api worker web gate recheck benchmark wait demo-refresh watch demo-documents stop

help: ## Show available targets
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'

env: ## Create .env with random secrets (keeps existing values)
	@python3 scripts/init-env.py

up: ## Start PostgreSQL, Redis, Keycloak, Mailpit and MinIO
	$(COMPOSE) up -d --wait

down: ## Stop the infrastructure containers (data is kept)
	$(COMPOSE) stop

migrate: ## Apply database migrations
	$(BACKEND) snoska db migrate

corpus: ## Ingest 152-FZ from the bundled snapshot
	$(BACKEND) snoska corpus sync --source snapshot

index: ## Embed the corpus with the configured embedding API (after setting a model)
	$(BACKEND) snoska corpus reindex

seed: ## Provision demo organizations, members and documents
	$(BACKEND) snoska demo seed

setup: env up migrate corpus seed ## Everything needed for a first run

api: ## Run the API on :46301
	$(BACKEND) snoska api

worker: ## Run background jobs and the outbox relay
	$(BACKEND) snoska worker

web: ## Run the web app on :46300
	cd frontend && pnpm dev

gate: ## Lint, typecheck, tests and source limits
	scripts/gate.sh

recheck: ## Check every document's latest version again (after the checks change)
	$(BACKEND) snoska checks recheck

benchmark: ## Measure the checks on the reference set, the model timed (writes data/quality and docs/quality.md)
	$(BACKEND) snoska checks benchmark --markdown ../docs/quality.md

wait: ## Wait until uploaded documents are read and checked
	$(BACKEND) snoska checks wait

demo-refresh: ## Refresh all that depends on the model: index, reset, recheck, benchmark, screenshots, landing media, video
	scripts/demo-refresh.sh

watch: ## Check now for a new edition of 152-FZ (weekly in the worker; mail goes to Mailpit)
	$(BACKEND) snoska corpus watch

demo-documents: ## Rebuild the demo documents and the reference set (needs LibreOffice)
	backend/.venv/bin/python scripts/demo/build_documents.py

stop: ## Stop the containers
	$(COMPOSE) stop
