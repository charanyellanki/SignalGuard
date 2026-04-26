.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

.PHONY: watch
watch: ## Run stack with Compose Watch (live-sync frontend; run from repo root)
	$(COMPOSE) watch

.PHONY: up
up: ## Build and start the full stack
	$(COMPOSE) up --build -d
	@echo ""
	@echo "Frontend:  http://localhost:${FRONTEND_PORT:-5173}  (nginx static build; host port maps to container :80)"
	@echo "API:       http://localhost:8000"
	@echo "API docs:  http://localhost:8000/docs"
	@echo ""
	@echo "Tail logs with:  make logs"

.PHONY: down
down: ## Stop the stack (keeps volumes)
	$(COMPOSE) down

.PHONY: clean
clean: ## Stop the stack and wipe volumes (postgres data, trained models)
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Tail logs from all services
	$(COMPOSE) logs -f --tail=100

.PHONY: logs-%
logs-%: ## Tail logs from one service (e.g. make logs-api)
	$(COMPOSE) logs -f --tail=200 $*

.PHONY: ps
ps: ## Show service status
	$(COMPOSE) ps

.PHONY: train
train: ## Force-retrain detection models (writes to detection_models volume)
	$(COMPOSE) run --rm --no-deps detection-service python train.py --force

.PHONY: migrate
migrate: ## Apply latest Alembic migrations against running postgres
	$(COMPOSE) run --rm --no-deps api alembic upgrade head

.PHONY: revision
revision: ## Create a new Alembic revision (usage: make revision MSG="add foo")
	$(COMPOSE) run --rm --no-deps api alembic revision --autogenerate -m "$(MSG)"

.PHONY: validate-skab
validate-skab: ## Run SKAB validation notebook headless
	$(COMPOSE) run --rm --no-deps detection-service \
		jupyter nbconvert --to notebook --execute /workspace/notebooks/skab-validation.ipynb \
		--output skab-validation.out.ipynb

.PHONY: shell-api
shell-api: ## Open a shell in the api container
	$(COMPOSE) exec api bash

.PHONY: shell-db
shell-db: ## Open psql against the postgres container
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-signalguard} -d $${POSTGRES_DB:-signalguard}

.PHONY: restart-%
restart-%: ## Restart one service (e.g. make restart-detection-service)
	$(COMPOSE) restart $*
