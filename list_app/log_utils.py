import logging
import sys

from loguru import logger


def init_logs(debug: bool = False, warning: bool = False) -> None:
    """Configure loguru log level and stdlib logging (for third-party libraries).

    Args:
        debug: Enable DEBUG level logging.
        warning: Show only WARNING level and above (ignored when debug is True).
    """
    if debug:
        level = logging.DEBUG
    elif warning:
        level = logging.WARNING
    else:
        level = logging.INFO

    logger.remove()
    logger.add(sys.stderr, level=level)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if debug:
        logging.getLogger("urllib3").setLevel(logging.INFO)
