all: format lint_fix
	@echo "[INFO] All checks complete!"

lint:
	@echo "[INFO] Running lint..."
	@uv run ruff check list_app

lint_fix:
	@echo "[INFO] Running lint fix..."
	@uv run ruff check --select I --fix list_app
	@uv run ruff check --fix list_app

format:
	@echo "[INFO] Running format..."
	@uv run ruff format list_app

format_toml:
	@echo "[INFO] Running TOML format..."
	@taplo fmt pyproject.toml

type_check:
	@echo "[INFO] Running type check..."
	@uv run mypy list_app

.PHONY: lint lint_fix format format_toml type_check
