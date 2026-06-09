# Makefile — developer entry points (CLAUDE.md "Commands").
# Works with GNU Make on Linux/macOS and on Windows (Git Bash / WSL / choco make).
# If `make` is unavailable, the README documents the equivalent raw commands.

# Cross-platform venv bin directory: Scripts on Windows, bin elsewhere.
ifeq ($(OS),Windows_NT)
	VENV_BIN := .venv/Scripts
else
	VENV_BIN := .venv/bin
endif

# Invoke pip as `python -m pip` so `pip install --upgrade pip` works on Windows
# (the pip.exe wrapper can't replace itself while running).
PY := $(VENV_BIN)/python
PIP := $(VENV_BIN)/python -m pip

.PHONY: install run seed reset test eval fmt help

help:  ## Show available targets
	@echo "Targets: install run seed reset test eval fmt"

install:  ## Create a venv and install dependencies
	python -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "Installed. Next: cp .env.example .env, then 'make run'."

run:  ## Start the dev server with autoreload
	$(VENV_BIN)/uvicorn app.main:app --reload

seed:  ## Load synthetic use cases into SQLite
	$(PY) -m app.seed

reset:  ## Delete the db and re-seed for a clean demo
	$(PY) -m app.seed --reset

test:  ## Run the test suite
	$(PY) -m pytest -q

eval:  ## Run the scoring evaluation harness (Phase 5)
	@echo "eval: not implemented until Phase 5." && exit 1

fmt:  ## Format and lint-fix the codebase
	$(VENV_BIN)/ruff format .
	$(VENV_BIN)/ruff check --fix .
