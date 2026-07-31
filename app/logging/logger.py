import logging

LOGGER_NAME = "smart-sports-calendar"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(log_level: str) -> logging.Logger:
    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        force=True,
    )

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(log_level)

    return logger
