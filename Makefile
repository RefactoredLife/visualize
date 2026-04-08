# --- Variables ---
PROJECT_NAME := visualize
IMAGE_NAME := $(PROJECT_NAME):latest
VM_HOST := app
PORT := 8501

# --- Help Window ---
.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Local Development ---

.PHONY: build
build: ## Build the Docker image locally
	docker build -t $(IMAGE_NAME) .

.PHONY: run
run: ## Run the container locally for testing
	docker run -d --name $(PROJECT_NAME) -p $(PORT):$(PORT) $(IMAGE_NAME)

.PHONY: stop
stop: ## Stop local container
	docker stop $(PROJECT_NAME) || true
	docker rm $(PROJECT_NAME) || true

# --- Proxmox VM Deployment ---

.PHONY: push-vm
push-vm: build ## Save image and push it to the VM via SSH (no registry needed)
	@echo "Transferring image to Proxmox VM..."
	docker save $(IMAGE_NAME) | ssh $(VM_HOST) "docker load"

.PHONY: deploy
deploy: push-vm ## Deploy/Restart the container on the Proxmox VM
	@echo "Starting container on VM..."
	ssh $(VM_HOST) "docker stop $(PROJECT_NAME) || true && \
		docker rm $(PROJECT_NAME) || true && \
		docker run -d --name $(PROJECT_NAME) -p $(PORT):$(PORT) --restart unless-stopped $(IMAGE_NAME)"

.PHONY: vm-logs
vm-logs: ## Tail logs from the VM
	ssh @$(VM_HOST) "docker logs -f $(PROJECT_NAME)"

.PHONY: vm-status
vm-status: ## Check container status on the VM
	ssh @$(VM_HOST) "docker ps -a --filter name=$(PROJECT_NAME)"

# --- Cleanup ---

.PHONY: clean
clean: ## Remove local images and prune
	docker rmi $(IMAGE_NAME) || true
	docker system prune -f
