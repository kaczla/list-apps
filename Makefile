all: format lint_fix
	@echo "[INFO] All checks complete!"

lint:
	@echo "[INFO] Running lint..."
	@uv run ruff check scripts

lint_fix:
	@echo "[INFO] Running lint fix..."
	@uv run ruff check --select I --fix scripts
	@uv run ruff check --fix scripts

format:
	@echo "[INFO] Running format..."
	@uv run ruff format scripts

format_toml:
	@echo "[INFO] Running TOML format..."
	@taplo fmt pyproject.toml

type_check:
	@echo "[INFO] Running type check..."
	@uv run mypy scripts

.PHONY: lint lint_fix format format_toml type_check
