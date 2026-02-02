import logging


def init_logs(debug: bool = False, warning: bool = False) -> None:
    if debug:
        level = logging.DEBUG
    elif warning:
        level = logging.WARNING
    else:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if debug:
        logging.getLogger("urllib3").setLevel(logging.INFO)
