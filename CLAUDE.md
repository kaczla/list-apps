# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A curated list of applications worth knowing, maintained as a README.md file with automated sorting and tag management. The project includes Python tools that parse, sort, and normalize the application entries.

## Development Commands

```bash
# Run all checks (format + lint fix)
make

# Individual commands
make lint          # Run ruff linter
make lint_fix      # Auto-fix lint issues
make format        # Format code with ruff
make type_check    # Run mypy type checking

# Generate README from applications.json
uv run python -m list_app.generate_readme

# Merge new applications from JSON file
uv run python -m list_app.merge_json new_apps.json
uv run python -m list_app.merge_json new_apps.json --dry-run  # Preview changes

# Review new applications via browser UI (NiceGUI)
uv run python -m list_app.review_app new_apps.json
uv run python -m list_app.review_app new_apps.json --port 9090  # Custom port
```

## Adding New Applications

### Extracting Application Data

When given a GitHub URL, use WebFetch to extract:
- **Name**: The project/repository name
- **Description**: A concise summary of what the application does
- **Tags**: Based on programming language, features, and use cases

### JSON Format

Create a JSON file with the current date and time in the name using format `YYYYMMDDTHHMM` (e.g., `new_apps_20240115T1430.json`) with a list of applications:

```json
[
    {
        "name": "Ruff",
        "url": "https://github.com/charliermarsh/ruff",
        "description": "An extremely fast Python linter and code formatter with 800+ built-in rules, compatible with Flake8, isort, and Black.",
        "tags": [
            "caching",
            "code formatting",
            "linter",
            "Python linter",
            "command line",
            "source: Rust"
        ]
    }
]
```

### Tag Conventions

1. Check existing tags in `data/json/tags.json` and prefer using them. New tags can be created if needed.
2. Tag ordering:
   - General tags first (e.g., `database`, `linter`, `editor`)
   - `command line: <tool>` for CLI tool alternatives (e.g., `command line: grep`)
   - `source: <language>` for implementation language (e.g., `source: Rust`, `source: Python`)

### Merging and Generating README

```bash
uv run python -m list_app.merge_json new_apps_20240115T1430.json --dry-run  # Preview first
uv run python -m list_app.merge_json new_apps_20240115T1430.json            # Apply changes
uv run python -m list_app.generate_readme                                   # Generate README
```

## Architecture

### Data Flow

The canonical data lives in `data/json/applications.json`. The README.md is generated from this JSON file.

### Main Package (`list_app/`)

- `data.py` - Pydantic model `ApplicationData` (name, url, description, tags)
- `generate_readme.py` - Generates README.md from applications.json, sorts apps alphabetically, generates Tags section with occurrence counts
- `merge_json.py` - Merges new applications into applications.json with duplicate detection
- `review_app.py` - NiceGUI browser UI for reviewing, editing, and merging new applications (file selection → per-app review with iframe preview → summary & merge)
- `data_utils.py` - JSON loading utilities

### Tag Sorting Order

Tags within each application are sorted: general tags first, then `command line: *` tags, then `source: *` tags.

## Code Style

- Line length: 120 characters
- Type annotations required on all functions (strict mypy settings)
- Uses loguru for logging
- Uses Pydantic for data validation
- Google-style docstrings
