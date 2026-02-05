import json
from pathlib import Path

from loguru import logger

from list_app.data import ApplicationData

README_PATH = Path("README.md")
DIRECTORY_DATA_JSON_PATH = Path("data/json")
DATA_APPLICATIONS_PATH = DIRECTORY_DATA_JSON_PATH / "applications.json"
DATA_TAGS_PATH = DIRECTORY_DATA_JSON_PATH / "tags.json"


def sort_application_tags(tags: set[str]) -> list[str]:
    """Sort tags: general tags first, then 'command line: *', then 'source: *'.

    Args:
        tags: Set of tag strings to sort.

    Returns:
        Sorted list of tags.
    """
    general: list[str] = []
    cmd_line: list[str] = []
    source: list[str] = []

    for tag in tags:
        if tag.lower().startswith("source: "):
            source.append(tag)
        elif tag.lower().startswith("command line: "):
            cmd_line.append(tag)
        else:
            general.append(tag)

    general.sort(key=lambda x: x.lower())
    cmd_line.sort(key=lambda x: x.lower())
    source.sort(key=lambda x: x.lower())

    return general + cmd_line + source


def load_applications(path: Path | None = None) -> list[ApplicationData]:
    if path is None:
        path = DATA_APPLICATIONS_PATH

    logger.info(f"Loading data from: {path}")
    with path.open("rt") as file:
        data = json.load(file)

    applications = [ApplicationData(**item) for item in data]
    logger.info(f"Loaded {len(applications)} applications")

    return applications


def save_applications(applications: list[ApplicationData]) -> None:
    applications_to_save = []
    tags = set()
    for application in applications:
        application_data = application.model_dump(mode="json")
        application_data["tags"] = sort_application_tags(application.tags)
        applications_to_save.append(application_data)
        tags.update(application.tags)

    logger.info(f"Saving data to: {DATA_APPLICATIONS_PATH}")
    with DATA_APPLICATIONS_PATH.open("wt") as file:
        json.dump(applications_to_save, file, indent=4, ensure_ascii=True)

    save_tags(list(tags))


def save_tags(tags: list[str]) -> None:
    logger.info(f"Saving data to: {DATA_TAGS_PATH}")
    tags.sort(key=lambda x: x.lower())
    with DATA_TAGS_PATH.open("wt") as file:
        json.dump(tags, file, indent=4, ensure_ascii=True)
