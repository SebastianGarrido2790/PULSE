"""Centralized logging configuration for the PULSE Engine.

Usage:
    from src.utils.logger import get_logger
    logger = get_logger(__name__, headline="state_monitor")
    logger.info("Evaluating point leverage...")
"""

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = PROJECT_ROOT / "logs" / "pulse_engine.log"


def get_logger(name: str | None = None, headline: str | None = None) -> logging.Logger:
    """Returns a configured logger with consistent formatting.

    Args:
        name: Optional logger name, typically __name__.
        headline: Optional headline text for visual log separation.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger_name = name or "PULSE"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5_000_000,  # 5 MB per log file
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)

        try:
            from rich.logging import RichHandler

            console_handler = RichHandler(rich_tracebacks=True, markup=True)
            console_handler.setFormatter(logging.Formatter("%(message)s"))
        except ImportError:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.propagate = False

        if LOG_FILE.parent.exists():
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write("\n")

            if headline:
                headline_text = (
                    f"========================= START: {headline} "
                    f"({datetime.now():%Y-%m-%d %H:%M:%S}) =========================\n"
                )
                with LOG_FILE.open("a", encoding="utf-8") as f:
                    f.write(headline_text)

    return logger


def log_spacer() -> None:
    """Appends a raw newline to the log file for visual spacing."""
    if LOG_FILE.parent.exists():
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write("\n")
