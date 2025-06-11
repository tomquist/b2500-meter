import logging


def setLogLevel(inLevel: str):
    level = levels.get(inLevel.lower())
    if level is None:
        level = logging.WARNING
    logging.basicConfig(level=level)


levels = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}

logger = logging.getLogger("b2500-meter")
