from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path("data/logs")
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 10


def configure_logging(
    log_name: str,
    *,
    level: int = logging.INFO,
    console: bool = True,
    force: bool = True,
) -> Path:
    """Configure project logging.

    Creates:
    - data/logs/<log_name>.log for the current script/service;
    - data/logs/errors.log for all ERROR/CRITICAL messages.

    The function is safe to call from any script entrypoint.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_path = LOG_DIR / f"{log_name}.log"
    error_path = LOG_DIR / "errors.log"

    handlers: list[logging.Handler] = []

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    handlers.append(file_handler)

    error_handler = RotatingFileHandler(
        error_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    handlers.append(error_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        handlers.append(console_handler)

    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=force,
    )

    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.getLogger(__name__).critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = handle_exception

    logging.getLogger(__name__).info("Logging started: %s", log_path)
    return log_path
