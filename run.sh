#!/usr/bin/env bash
set -euo pipefail

COMMAND="${1:-}"

case "$COMMAND" in
  review)
    uv run python -m list_app.review_app "${@:2}"
    ;;
  generate-readme)
    uv run python -m list_app.generate_readme "${@:2}"
    ;;
  check-urls)
    uv run python -m list_app.check_urls "${@:2}"
    ;;
  merge)
    uv run python -m list_app.merge_json "${@:2}"
    ;;
  *)
    echo "Usage: $0 <command> [args...]"
    echo ""
    echo "Commands:"
    echo "  review          [input_file] [--port PORT] [--page-size N] [--reload]"
    echo "  generate-readme"
    echo "  check-urls      <input_file>"
    echo "  merge           <input_file> [--dry-run] [--overwrite]"
    exit 1
    ;;
esac
