.PHONY: help install dev test lint format build push deploy clean

# Variables
IMAGE_NAME ?= ai-sre-agent
IMAGE_TAG ?= latest
REGISTRY ?= ghcr.io/yourorg
HELM_RELEASE ?= ai-sre-agent
HELM_NAMESPACE ?= ai-sre-agent
PYTHON_VERSION ?= 3.10

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# Development
# =============================================================================

install: ## Install dependencies with uv
	uv venv
	uv pip install -e ".[all]"

dev: ## Run development server
	uvicorn examples.webhook_handler:app --reload --host 0.0.0.0 --port 8000

demo: ## Run demo with sample data
	sre-agent demo

test: ## Run tests
	pytest -v

test-cov: ## Run tests with coverage
	pytest --cov=src --cov-report=html --cov-report=term

lint: ## Run linters
	ruff check src tests
	mypy src

format: ## Format code
	ruff format src tests
	ruff check src tests --fix

pre-commit: ## Run pre-commit hooks
	pre-commit run --all-files

# =============================================================================
# Docker
# =============================================================================

build: ## Build Docker images
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) --target agent .
	docker build -t $(IMAGE_NAME)-mcp-jira:$(IMAGE_TAG) --target mcp-jira .
	docker build -t $(IMAGE_NAME)-mcp-confluence:$(IMAGE_TAG) --target mcp-confluence .
	docker build -t $(IMAGE_NAME)-mcp-gitlab:$(IMAGE_TAG) --target mcp-gitlab .

build-agent: ## Build only agent image
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) --target agent .

build-mcp: ## Build MCP server images
	docker build -t $(IMAGE_NAME)-mcp-jira:$(IMAGE_TAG) --target mcp-jira .
	docker build -t $(IMAGE_NAME)-mcp-confluence:$(IMAGE_TAG) --target mcp-confluence .
	docker build -t $(IMAGE_NAME)-mcp-gitlab:$(IMAGE_TAG) --target mcp-gitlab .

push: ## Push images to registry
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	docker tag $(IMAGE_NAME)-mcp-jira:$(IMAGE_TAG) $(REGISTRY)/$(IMAGE_NAME)-mcp-jira:$(IMAGE_TAG)
	docker tag $(IMAGE_NAME)-mcp-confluence:$(IMAGE_TAG) $(REGISTRY)/$(IMAGE_NAME)-mcp-confluence:$(IMAGE_TAG)
	docker tag $(IMAGE_NAME)-mcp-gitlab:$(IMAGE_TAG) $(REGISTRY)/$(IMAGE_NAME)-mcp-gitlab:$(IMAGE_TAG)
	docker push $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	docker push $(REGISTRY)/$(IMAGE_NAME)-mcp-jira:$(IMAGE_TAG)
	docker push $(REGISTRY)/$(IMAGE_NAME)-mcp-confluence:$(IMAGE_TAG)
	docker push $(REGISTRY)/$(IMAGE_NAME)-mcp-gitlab:$(IMAGE_TAG)

docker-compose-up: ## Start with docker-compose
	docker-compose up -d

docker-compose-down: ## Stop docker-compose
	docker-compose down

docker-compose-logs: ## View docker-compose logs
	docker-compose logs -f

# =============================================================================
# Helm / Kubernetes
# =============================================================================

helm-lint: ## Lint Helm chart
	helm lint helm/ai-sre-agent

helm-template: ## Template Helm chart (dry-run)
	helm template $(HELM_RELEASE) helm/ai-sre-agent --namespace $(HELM_NAMESPACE)

helm-install: ## Install Helm chart
	helm upgrade --install $(HELM_RELEASE) helm/ai-sre-agent \
		--namespace $(HELM_NAMESPACE) \
		--create-namespace

helm-install-prod: ## Install Helm chart with production values
	helm upgrade --install $(HELM_RELEASE) helm/ai-sre-agent \
		--namespace $(HELM_NAMESPACE) \
		--create-namespace \
		-f helm/ai-sre-agent/values-production.yaml

helm-uninstall: ## Uninstall Helm chart
	helm uninstall $(HELM_RELEASE) --namespace $(HELM_NAMESPACE)

helm-package: ## Package Helm chart
	helm package helm/ai-sre-agent

k8s-logs: ## View Kubernetes logs
	kubectl logs -n $(HELM_NAMESPACE) -l app.kubernetes.io/instance=$(HELM_RELEASE) -f

k8s-status: ## Check Kubernetes status
	kubectl get pods,svc,ingress -n $(HELM_NAMESPACE) -l app.kubernetes.io/instance=$(HELM_RELEASE)

# =============================================================================
# CI/CD Helpers
# =============================================================================

ci-test: ## Run CI tests
	pytest --junitxml=test-results.xml --cov=src --cov-report=xml

ci-lint: ## Run CI linting
	ruff check src tests --output-format=github
	mypy src --no-error-summary

# =============================================================================
# Cleanup
# =============================================================================

clean: ## Clean build artifacts
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov .coverage coverage.xml
	rm -rf test-results.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-docker: ## Clean Docker images
	docker rmi $(IMAGE_NAME):$(IMAGE_TAG) || true
	docker rmi $(IMAGE_NAME)-mcp-jira:$(IMAGE_TAG) || true
	docker rmi $(IMAGE_NAME)-mcp-confluence:$(IMAGE_TAG) || true
	docker rmi $(IMAGE_NAME)-mcp-gitlab:$(IMAGE_TAG) || true

clean-all: clean clean-docker ## Clean everything
