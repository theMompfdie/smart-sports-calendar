import logging

LOGGER_NAME = "smart-sports-calendar"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(
    log_level: str,
    instance_name: str = "default",
) -> logging.Logger:
    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        force=True,
    )

    logger = logging.getLogger(f"{LOGGER_NAME}.{instance_name}")
    logger.setLevel(log_level)

    return logger
