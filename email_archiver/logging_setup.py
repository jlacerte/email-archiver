"""
Professional logging setup: stdout + rotating file logs.

Logs are written to logs/archive-ACCOUNT-YYYY-MM-DD.log with timestamps
and severity levels. A log must allow reconstructing exactly what happened.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def setup_logging(account: str, level: int = logging.INFO) -> logging.Logger:
    """Configure logger for a specific account session.

    Returns a logger that writes to both stdout and a date-stamped file.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"email_archiver.{account}")
    logger.setLevel(level)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # File handler (one file per account per day)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"archive-{account}-{today}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
