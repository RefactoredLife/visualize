# --- Variables ---
PROJECT_NAME := visualize
SERVICE_NAME := visualize
VM_HOST := app
REMOTE_DIR := ~/$(PROJECT_NAME)
COMPOSE := docker compose
COMPOSE_FILE := docker-compose.yml
ENV_FILE := .env
REMOTE_COMPOSE_ARGS := -f $(COMPOSE_FILE)
REMOTE_COMPOSE_CMD := cd $(REMOTE_DIR) && $(COMPOSE) $(REMOTE_COMPOSE_ARGS)

# --- Help Window ---
.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Remote Sync ---

.PHONY: sync
sync: ## Copy the compose build context to $(VM_HOST)
	ssh $(VM_HOST) "mkdir -p $(REMOTE_DIR)"
	scp -r app $(COMPOSE_FILE) Dockerfile requirements.txt Makefile README.md $(VM_HOST):$(REMOTE_DIR)/
	@if [ -f $(ENV_FILE) ]; then scp $(ENV_FILE) $(VM_HOST):$(REMOTE_DIR)/$(ENV_FILE); fi

# --- Remote Docker Compose ---

.PHONY: build
build: sync ## Build the compose services on $(VM_HOST)
	ssh $(VM_HOST) "$(REMOTE_COMPOSE_CMD) build"

.PHONY: up
up: sync ## Start the compose stack on $(VM_HOST) in detached mode
	ssh $(VM_HOST) "$(REMOTE_COMPOSE_CMD) up -d"

.PHONY: run
run: up ## Alias for up

.PHONY: down
down: ## Stop and remove the compose stack on $(VM_HOST)
	ssh $(VM_HOST) "$(REMOTE_COMPOSE_CMD) down"

.PHONY: stop
stop: down ## Alias for down

.PHONY: restart
restart: ## Restart the compose stack on $(VM_HOST)
	ssh $(VM_HOST) "$(REMOTE_COMPOSE_CMD) restart"

.PHONY: logs
logs: ## Tail compose logs on $(VM_HOST)
	ssh -t $(VM_HOST) "$(REMOTE_COMPOSE_CMD) logs -f $(SERVICE_NAME)"

.PHONY: shell
shell: ## Open a shell in the service container on $(VM_HOST)
	ssh -t $(VM_HOST) "$(REMOTE_COMPOSE_CMD) exec $(SERVICE_NAME) sh || $(REMOTE_COMPOSE_CMD) run --rm --entrypoint sh $(SERVICE_NAME)"

.PHONY: ps
ps: ## Show compose service status on $(VM_HOST)
	ssh $(VM_HOST) "$(REMOTE_COMPOSE_CMD) ps"

.PHONY: pull
pull: ## Pull newer base images on $(VM_HOST)
	ssh $(VM_HOST) "$(REMOTE_COMPOSE_CMD) pull"

.PHONY: rebuild
rebuild: sync ## Rebuild and restart the compose stack on $(VM_HOST)
	ssh $(VM_HOST) "$(REMOTE_COMPOSE_CMD) up -d --build"

.PHONY: clean
clean: ## Stop compose stack on $(VM_HOST) and prune unused docker data
	ssh $(VM_HOST) "$(REMOTE_COMPOSE_CMD) down --remove-orphans || true"
	ssh $(VM_HOST) "docker system prune -f"
