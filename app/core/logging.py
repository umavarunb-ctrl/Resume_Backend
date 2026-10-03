import logging
import sys
from app.core.config import settings


def setup_logging() -> logging.Logger:
    """Configure structured logging for the application without exposing sensitive data."""
    log_level = logging.DEBUG if settings.APP_ENV.lower() == "development" else logging.INFO

    # Root logger configuration
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Suppress overly verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("pymongo").setLevel(logging.WARNING)

    logger = logging.getLogger(settings.APP_NAME)
    logger.setLevel(log_level)
    return logger


logger = setup_logging()
