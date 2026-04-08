# --- Variables ---
PROJECT_NAME := visualize
SERVICE_NAME := visualize
IMAGE_NAME := $(PROJECT_NAME):latest
COMPOSE := docker compose
COMPOSE_FILE := docker-compose.yml
COMPOSE_ARGS := -f $(COMPOSE_FILE)
VM_HOST := app
REMOTE_DIR := ~/$(PROJECT_NAME)

# --- Help Window ---
.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Local Development ---

.PHONY: build
build: ## Build the compose services
	$(COMPOSE) $(COMPOSE_ARGS) build

.PHONY: up
up: ## Start the compose stack in detached mode
	$(COMPOSE) $(COMPOSE_ARGS) up -d

.PHONY: run
run: up ## Alias for up

.PHONY: down
down: ## Stop and remove the compose stack
	$(COMPOSE) $(COMPOSE_ARGS) down

.PHONY: stop
stop: down ## Alias for down

.PHONY: restart
restart: ## Restart the compose stack
	$(COMPOSE) $(COMPOSE_ARGS) restart

.PHONY: logs
logs: ## Tail compose logs
	$(COMPOSE) $(COMPOSE_ARGS) logs -f $(SERVICE_NAME)

.PHONY: ps
ps: ## Show compose service status
	$(COMPOSE) $(COMPOSE_ARGS) ps

.PHONY: pull
pull: ## Pull newer base images referenced by compose
	$(COMPOSE) $(COMPOSE_ARGS) pull

.PHONY: rebuild
rebuild: ## Rebuild and restart the compose stack
	$(COMPOSE) $(COMPOSE_ARGS) up -d --build

# --- Proxmox VM Deployment ---

.PHONY: push-vm
push-vm: ## Copy compose build context to the VM
	ssh $(VM_HOST) "mkdir -p $(REMOTE_DIR)"
	scp -r app $(COMPOSE_FILE) Dockerfile requirements.txt Makefile README.md $(VM_HOST):$(REMOTE_DIR)/

.PHONY: deploy
deploy: push-vm ## Rebuild and restart the compose stack on the VM
	ssh $(VM_HOST) "cd $(REMOTE_DIR) && $(COMPOSE) $(COMPOSE_ARGS) up -d --build"

.PHONY: vm-logs
vm-logs: ## Tail compose logs from the VM
	ssh $(VM_HOST) "cd $(REMOTE_DIR) && $(COMPOSE) $(COMPOSE_ARGS) logs -f $(SERVICE_NAME)"

.PHONY: vm-status
vm-status: ## Check compose service status on the VM
	ssh $(VM_HOST) "cd $(REMOTE_DIR) && $(COMPOSE) $(COMPOSE_ARGS) ps"

# --- Cleanup ---

.PHONY: clean
clean: ## Stop compose stack and prune unused docker data
	$(COMPOSE) $(COMPOSE_ARGS) down --remove-orphans || true
	docker image rm $(IMAGE_NAME) || true
	docker system prune -f
