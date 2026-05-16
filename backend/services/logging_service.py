"""Structured logging for Platapicker. Writes to console and log file."""
import logging
import os
from pathlib import Path
from rich.logging import RichHandler

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(rich_tracebacks=True, markup=True),
        logging.FileHandler(LOG_DIR / "platapicker.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger("platapicker")


def get_logger(name: str = "platapicker") -> logging.Logger:
    return logging.getLogger(name)
