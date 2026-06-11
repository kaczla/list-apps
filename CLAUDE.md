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
./run.sh generate-readme

# Merge new applications from JSON file
./run.sh merge new_apps.json
./run.sh merge new_apps.json --dry-run  # Preview changes

# Review new applications via browser UI (NiceGUI)
./run.sh review new_apps.json
./run.sh review new_apps.json --port 9090  # Custom port
```

## Adding New Applications

### Extracting Application Data

When given a GitHub URL, use WebFetch to extract:
- **Name**: The project/repository name
- **Description**: A concise summary of what the application does
- **Tags**: Based on programming language, features, and use cases

**Important**: Fetch URLs in batches of 3 at a time to avoid overloading. Wait for each batch to complete before starting the next one.

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

### Working with applications.json and tags.json

**`data/json/applications.json`** is a large file (~6400+ lines, 500+ applications). Key points:
- The `Read` tool truncates at 2000 lines — always read it in multiple passes using `offset` and `limit` parameters (e.g., offsets 0, 2000, 4000, 6000).
- To find a specific application, use `Grep` on the file rather than reading the whole file (e.g., search for `"name": "AppName"`).
- For bulk tag fixes across many apps, use `Edit` with `replace_all: true` — safe when the search string is a quoted JSON value (e.g., `"old-tag"`) that only appears as a standalone tag, not embedded in descriptions.
- For targeted edits to a single app, use the app's URL or a unique part of its description as anchor context to ensure uniqueness.

**`data/json/tags.json`** is small (~420 lines) and can be read in one pass. It is a sorted JSON array of tag strings. When adding or removing tags, maintain alphabetical order.

### Tag Conventions

1. Check existing tags in `data/json/tags.json` and prefer using them. New tags can be created if needed.
2. Tag ordering:
   - General tags first (e.g., `database`, `linter`, `editor`)
   - `command line: <tool>` for CLI tool alternatives (e.g., `command line: grep`)
   - `source: <language>` for implementation language (e.g., `source: Rust`, `source: Python`)

### Creating New Tags

Before creating a tag, search `tags.json` for an existing one with the same meaning — including singular/plural,
hyphenation, and word-order variants (e.g., use existing `deduplication`, not `unique`; `API testing`, not
`testing API`). When creating one:

- **Casing**: lowercase by default (`encryption`, `monitoring`); capitalize proper nouns and acronyms as officially
  spelled (`Docker`, `Kubernetes`, `PostgreSQL`, `macOS`, `SSH`, `LLM`, `SSL/TLS`). Exception: `git` stays lowercase.
- **Naming**: use nouns/noun phrases (`customization`, not `customizing`; `note-taking`, not `note`). Prefer the
  established technical term (`steganography`, `tracing`, `HTTP client`) over an ad-hoc description (`hide`, `trace`,
  `requests`).
- **Granularity**: don't create compound tags when two existing tags cover it (use `Deep Learning` + `framework`,
  not `Deep Learning framework`). Qualified variants are fine when the qualifier adds meaning (`Python linter`,
  `vector database`).
- **Avoid one-off vague tags** (`space`, `detector`, `engineering`) — if a tag would apply to only one app and an
  existing tag already covers the idea, use the existing tag instead.
- Use `LLM` for large-language-model topics (consistent with `LLM gateway`, `LLM management`, `LLM-ready`) and
  `AI-powered` (hyphenated) for AI-assisted tools.

### Bulk Tag Renames

For renaming/merging tags across many apps, prefer a small Python script over manual edits: load
`applications.json`, apply a `{old_tag: [new_tags]}` mapping per app, deduplicate via a `set`, and re-sort with
`list_app.data_utils.sort_application_tags()`. Then run `./run.sh generate-readme` — it re-saves both
`applications.json` and `tags.json` through the canonical code path (sorting, formatting, and tag index are
regenerated automatically), so `tags.json` never needs hand-editing after a rename.

### Merging and Generating README

**Option A: Direct merge (no review)**

```bash
./run.sh merge new_apps_20240115T1430.json --dry-run  # Preview first
./run.sh merge new_apps_20240115T1430.json            # Apply changes
./run.sh generate-readme                              # Generate README
```

**Option B: Interactive review via browser UI**

```bash
./run.sh review new_apps_20240115T1430.json            # Opens browser UI on default port
./run.sh review new_apps_20240115T1430.json --port 9090  # Custom port
```

The review UI lets you inspect each app (with iframe preview), edit name/description/tags, and then merge and generate the README from within the browser.

**Important**: After creating the JSON file, do NOT run any of the above commands automatically. Just inform the user that the file has been created and show them the commands they can run to merge and generate the README.

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
