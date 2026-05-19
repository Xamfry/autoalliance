import logging
import sqlite3
import time
from functools import wraps
from typing import Callable, TypeVar, ParamSpec

from sqlalchemy.exc import OperationalError


log = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def _is_sqlite_locked_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "database is locked" in text or "database table is locked" in text


def retry_db_lock(
    retries: int = 5,
    delay: float = 1.0,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Повторяет короткую операцию с БД, если SQLite временно занят записью.

    Использовать только вокруг небольших операций записи:

        @retry_db_lock()
        def save_status(...):
            ...

    Не нужно оборачивать долгие операции, внутри которых есть запросы к Ozon
    или AutoAlliance API.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exc: BaseException | None = None

            for attempt in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)

                except sqlite3.OperationalError as exc:
                    if not _is_sqlite_locked_error(exc):
                        raise

                    last_exc = exc
                    log.warning(
                        "SQLite database is locked. Retry %s/%s after %.1fs. func=%s",
                        attempt,
                        retries,
                        delay,
                        func.__name__,
                    )
                    time.sleep(delay)

                except OperationalError as exc:
                    if not _is_sqlite_locked_error(exc):
                        raise

                    last_exc = exc
                    log.warning(
                        "SQLAlchemy SQLite database is locked. Retry %s/%s after %.1fs. func=%s",
                        attempt,
                        retries,
                        delay,
                        func.__name__,
                    )
                    time.sleep(delay)

            if last_exc:
                raise last_exc

            return func(*args, **kwargs)

        return wrapper

    return decorator
