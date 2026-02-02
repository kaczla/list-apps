import json
from pathlib import Path

from loguru import logger

from list_app.data import ApplicationData


def load_applications(path: Path) -> list[ApplicationData]:
    logger.info(f"Loading data from: {path}")
    with path.open("rt") as file:
        data = json.load(file)

    return [ApplicationData(**item) for item in data]
