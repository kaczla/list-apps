"""Merge JSON data into LM data or links files."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import ValidationError

from list_app.data import ApplicationData
from list_app.data_utils import load_applications, save_applications
from list_app.generate_readme import generate_and_save_readme
from list_app.log_utils import init_logs


def load_input_json(input_path: Path) -> list[dict[str, Any]]:
    """Load input JSON file containing list of dictionaries."""
    if not input_path.exists():
        logger.error(f"Input file does not exist: {input_path}")
        sys.exit(1)

    try:
        data = json.loads(input_path.read_text())
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in input file: {e}")
        sys.exit(1)

    if not isinstance(data, list):
        logger.error("Input JSON must be a list of dictionaries")
        sys.exit(1)

    return data


def merge_applications(input_data: list[dict[str, Any]], dry_run: bool = False, overwrite: bool = False) -> int:
    """
    Merge input data into application.json.

    Returns:
        Error count
    """
    existing_list = load_applications()

    # Build lookup for duplicate detection
    existing_names: set[str] = {m.name for m in existing_list}
    url_to_idx: dict[str, int] = {m.url: i for i, m in enumerate(existing_list)}

    added_count = 0
    replaced_count = 0
    duplicate_count = 0
    error_count = 0
    new_items: list[ApplicationData] = []

    for idx, item in enumerate(input_data):
        try:
            model_info = ApplicationData(**item)
        except ValidationError as e:
            logger.error(f"[{idx + 1}] Invalid ModelInfo data: {e}")
            error_count += 1
            continue

        # Check for duplicate URL
        if model_info.url in url_to_idx:
            if overwrite:
                existing_idx = url_to_idx[model_info.url]
                old_name = existing_list[existing_idx].name
                existing_list[existing_idx] = model_info
                # Update name lookup if name changed
                if old_name != model_info.name:
                    existing_names.discard(old_name)
                    existing_names.add(model_info.name)
                replaced_count += 1
                logger.info(f"[{idx + 1}] Replacing model: {model_info.name}")
            else:
                logger.error(f"[{idx + 1}] Duplicate URL for {model_info.name!r}: {model_info.url} - skipping")
                duplicate_count += 1
            continue

        # Check for duplicate name (different URL)
        if model_info.name in existing_names:
            logger.warning(f"[{idx + 1}] Duplicate model name for {model_info.name!r}: {model_info.url} - continuing")

        # Add to new items and update lookup sets
        new_items.append(model_info)
        existing_names.add(model_info.name)
        url_to_idx[model_info.url] = -1  # Mark as seen (index not needed for new items)
        added_count += 1
        logger.info(f"[{idx + 1}] Adding model: {model_info.name}")

    has_changes = new_items or replaced_count > 0
    if has_changes and not dry_run:
        merged_list = existing_list + new_items
        merged_list.sort(key=lambda x: x.name.lower())
        logger.info(f"Saving {len(merged_list)} models")
        save_applications(merged_list)
        generate_and_save_readme(merged_list)

    logger.info(
        f"Summary: {added_count} added, {replaced_count} replaced, "
        f"{duplicate_count} duplicates skipped, {error_count} errors"
    )
    changes_count = added_count + replaced_count
    if dry_run and changes_count > 0:
        logger.info(f"Run without --dry-run to merge {changes_count} items")

    return error_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge JSON data into application file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge applications from a JSON file
  uv run python -m list_lm.merge_json new_apps.json

  # Dry run to preview what would be added
  uv run python -m list_lm.merge_json new_apps.json --dry-run

  # Overwrite existing entries instead of skipping
  uv run python -m list_lm.merge_json new_apps.json--overwrite
        """,
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to JSON file containing list of items to merge",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be merged without making changes",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing entries instead of skipping duplicates",
    )

    args = parser.parse_args()
    init_logs()

    input_data = load_input_json(args.input_file)
    logger.info(f"Loaded {len(input_data)} items from: {args.input_file}")

    if args.dry_run:
        logger.info("DRY RUN MODE - no changes will be made")

    errors = merge_applications(input_data, dry_run=args.dry_run, overwrite=args.overwrite)

    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
