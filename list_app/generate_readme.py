"""Generate README.md from applications.json data."""

from collections import Counter
from typing import Counter as CounterType

from loguru import logger

from list_app.data import ApplicationData, Tag
from list_app.data_utils import DATA_APPLICATIONS_PATH, README_PATH, load_applications, sort_application_tags
from list_app.log_utils import init_logs

HEADER_LIST_OF_APPS = "List of application"


def calculate_tag_occurrences(apps: list[ApplicationData]) -> list[Tag]:
    """Count tags across all applications and return sorted alphabetically.

    Args:
        apps: List of application data.

    Returns:
        List of Tag objects with names and occurrence counts, sorted alphabetically.
    """
    tags_counter: CounterType[str] = Counter()

    for app in apps:
        tags_counter.update(app.tags)

    logger.info(f"Found {len(tags_counter)} unique tags")
    tags = [Tag(name=name, occurrence=count) for name, count in tags_counter.items()]
    tags.sort(key=lambda x: x.name.lower())

    return tags


def generate_header_section() -> str:
    """Generate the static header section of README.

    Returns:
        Header section content.
    """
    return """# list-apps

List of applications worth knowing.

Some descriptions are from:
- the project README/documentations,
- [TLDR newsletter](https://tldr.tech).

"""


def format_application(app: ApplicationData) -> str:
    """Format a single application as markdown.

    Args:
        app: Application data to format.

    Returns:
        Formatted markdown string for the application.
    """
    sorted_tags = sort_application_tags(app.tags)
    tags_str = ", ".join(sorted_tags)
    return f"- {app.name} [🛈]({app.url})\n  - {app.description}\n  - Tags: {tags_str}"


def generate_applications_section(apps: list[ApplicationData]) -> str:
    """Generate the full 'List of application' section.

    Args:
        apps: List of application data to include.

    Returns:
        Complete applications section as markdown.
    """
    logger.info(f"Generating section for {len(apps)} applications")
    formatted_apps = [format_application(app) for app in apps]
    apps_content = "\n".join(formatted_apps)
    return f"# {HEADER_LIST_OF_APPS}\n\n{apps_content}\n\n"


def generate_tags_section(tags: list[Tag]) -> str:
    """Generate the Tags section with occurrence counts.

    Args:
        tags: List of Tag objects with names and counts.

    Returns:
        Tags section as markdown.
    """
    tag_lines = [f"- {tag.name} ({tag.occurrence})" for tag in tags]
    tags_content = "\n".join(tag_lines)
    return f"# Tags\n\nList of tags with occurrences in the brackets:\n\n{tags_content}\n"


def generate_readme(apps: list[ApplicationData]) -> str:
    """Combine all sections to generate complete README content.

    Args:
        apps: List of application data.

    Returns:
        Complete README.md content.
    """
    tags = calculate_tag_occurrences(apps)

    content = generate_header_section()
    content += generate_applications_section(apps)
    content += generate_tags_section(tags)

    return content


def generate_and_save_readme(apps: list[ApplicationData]) -> None:
    readme_content = generate_readme(apps)

    logger.info(f"Writing README to: {README_PATH}")
    README_PATH.write_text(readme_content)
    logger.info("README generated")


def main() -> None:
    """Entry point: load JSON, generate README, and write to file."""
    init_logs(debug=False)
    logger.info(f"Loading applications from: {DATA_APPLICATIONS_PATH}")

    if not DATA_APPLICATIONS_PATH.exists():
        logger.error(f"Applications JSON file not found: {DATA_APPLICATIONS_PATH}")
        raise FileNotFoundError(f"Applications JSON file not found: {DATA_APPLICATIONS_PATH}")

    apps = load_applications(DATA_APPLICATIONS_PATH)
    apps.sort(key=lambda x: x.name.lower())

    logger.info(f"Loaded {len(apps)} applications")
    generate_and_save_readme(apps)

    logger.info("README generation complete")


if __name__ == "__main__":
    main()
