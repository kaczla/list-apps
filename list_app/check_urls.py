"""Check URLs from a file for validity and uniqueness.

This module loads URLs from a text file, filters out duplicates and URLs that
already exist in the applications database, and saves the unique URLs to a new
file called 'unique_urls.txt'.

The script only processes HTTP and HTTPS URLs, skipping any other formats.
"""

import argparse
import sys
from pathlib import Path

from loguru import logger

from list_app.data_utils import load_applications


def load_links(file: Path) -> list[str]:
    """Load links from a file and return only HTTP/HTTPS URLs."""
    logger.info(f"Loading links from: {file}")
    links = []
    with file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if line.startswith(("http://", "https://")):
                links.append(line)
            else:
                logger.warning(f"Skipping URL: {line!r}")

    logger.info(f"Loaded {len(links)} URLs")
    return links


def save_links(links: list[str], save_path: Path) -> None:
    logger.info(f"Saving links to: {save_path}")
    save_path.write_text("\n".join(sorted(links)))


def parse_args(cmd_args: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(
        description="Check URLs from a file for validity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check URLs from a file and save unique URLs
  uv run python -m list_app.check_urls urls.txt

  # The script will:
  # 1. Load URLs from the input file
  # 2. Filter out duplicates and existing application URLs
  # 3. Save unique URLs to 'unique_urls.txt'
        """,
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to text file containing URLs to check",
    )

    args = parser.parse_args(cmd_args)

    file_path: Path = args.input_file
    if not file_path.exists():
        logger.error(f"Input file does not exist: {file_path}")
        sys.exit(1)

    return file_path


def main(cmd_args: list[str] | None = None) -> None:
    input_file = parse_args(cmd_args)

    links = load_links(input_file)

    applications = load_applications()
    application_urls = {app.url for app in applications}

    uniq_links = set()
    for link in links:
        if link in application_urls or link in uniq_links:
            continue

        uniq_links.add(link)

    logger.info(f"Found {len(uniq_links)} unique URLs")
    save_links(list(uniq_links), input_file.with_name("unique_urls.txt"))


if __name__ == "__main__":
    main()
