"""Application logging setup for clean, structured development logs."""

import logging
import sys
from app.core.config import get_settings


class SafeLogFormatter(logging.Formatter):
    """Custom log formatter ensuring readable timestamps, module paths, and safe output."""

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s"
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def setup_logging() -> logging.Logger:
    """Initialize application logging configuration."""
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if reloaded in development
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        handler.setFormatter(SafeLogFormatter())
        root_logger.addHandler(handler)

    # Silence overly verbose third-party loggers in dev
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logger = logging.getLogger("ai_research_assistant")
    logger.setLevel(log_level)
    return logger
