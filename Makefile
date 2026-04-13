# InfinityRx Platform — developer task runner.
#
# Targets:
#   make security-scan   — pip-audit + bandit against the whole tree
#   make test            — full pytest suite with coverage enforcement
#   make lint            — ruff + mypy
#   make format          — ruff format (writes)
#   make clean           — remove __pycache__, .pytest_cache, coverage dbs
#   make freeze-lock     — regenerate requirements.txt from the uv lockfile
#
# By default, targets assume the project venv at .venv; override with
# PY= to run against a different interpreter.

PY ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?##"};{printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

.PHONY: security-scan
security-scan: pip-audit bandit ## Run dependency + static security scans

.PHONY: pip-audit
pip-audit: ## Scan installed packages for known CVEs (OSV + PyPI advisories)
	$(PY) -m pip install --quiet pip-audit
	$(PY) -m pip_audit --strict

.PHONY: bandit
bandit: ## Static security analysis on shared/ + modules/
	$(PY) -m pip install --quiet 'bandit[toml]'
	$(PY) -m bandit -q -r shared modules -c pyproject.toml

# ---------------------------------------------------------------------------
# Test / lint / format
# ---------------------------------------------------------------------------

.PHONY: test
test: ## Run full pytest suite
	$(PY) -m pytest

.PHONY: lint
lint: ## ruff + mypy
	$(PY) -m ruff check .
	$(PY) -m mypy shared modules

.PHONY: format
format: ## Apply ruff formatter
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

.PHONY: clean
clean: ## Remove caches and coverage databases
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov .hypothesis

.PHONY: freeze-lock
freeze-lock: ## Regenerate requirements.txt (pip-audit input)
	$(PIP) freeze > requirements.txt
	@echo "requirements.txt regenerated — run 'make pip-audit' to rescan"
