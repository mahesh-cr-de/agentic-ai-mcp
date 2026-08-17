.DEFAULT_GOAL := help
.PHONY: help install install-dev lint format typecheck security test test-cov \
        run validate-config docker-build docker-run clean

VENV ?= .venv
PYTHON ?= python3
CONFIG ?= configs/default.yaml

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime dependencies only.
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .

install-dev: ## Install with dev/lint/test/cloud extras.
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[all]"
	pre-commit install

lint: ## Run ruff (lint only, no fixes).
	ruff check src tests

format: ## Auto-format with ruff + black.
	ruff check --fix src tests
	black src tests

typecheck: ## Run mypy in strict mode.
	mypy

security: ## Run bandit static security analysis.
	bandit -c pyproject.toml -r src

test: ## Run the test suite.
	pytest

test-cov: ## Run the test suite with coverage (fails under 85%).
	pytest --cov --cov-report=term-missing --cov-report=xml

validate-config: ## Validate a config file (CONFIG=path/to/file.yaml).
	mcp-data-tools validate-config --config $(CONFIG)

run: ## Run the MCP server over stdio using CONFIG.
	mcp-data-tools serve --config $(CONFIG)

docker-build: ## Build the production Docker image.
	docker build -t mcp-data-tools:local .

docker-run: ## Run the server in Docker (interactive stdio).
	docker compose run --rm mcp-data-tools

clean: ## Remove build artifacts and caches.
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
