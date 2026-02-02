# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A curated list of applications worth knowing, maintained as a README.md file with automated sorting and tag management. The project includes a Python script that parses, sorts, and normalizes the application entries.

## Development Commands

```bash
# Run all checks (format + lint fix)
make

# Individual commands
make lint          # Run ruff linter
make lint_fix      # Auto-fix lint issues
make format        # Format code with ruff
make type_check    # Run mypy type checking

# Run the main script (sorts README and generates JSON data)
uv run python scripts/sort_readme.py
```

## Architecture

The project has a single main script (`scripts/sort_readme.py`) that:

1. Parses the `README.md` file into sections, extracting the "List of application" section
2. Parses each application entry into `ParsedApplication` objects (name, link, description, tags)
3. Sorts applications alphabetically by name (case-insensitive)
4. Normalizes tags (merges duplicates with different casing, prioritizes capitalized versions)
5. Sorts tags within each application (general tags first, then `command line: *` tags, then `source: *` tags)
6. Generates a "Tags" section with occurrence counts
7. Exports structured data to `data/json/applications.json` and `data/json/tags.json`

## Code Style

- Line length: 120 characters
- Type annotations required on all functions (strict mypy settings)
- Uses loguru for logging
- Uses Pydantic for data validation where needed
- Google-style docstrings
