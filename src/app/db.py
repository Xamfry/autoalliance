from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from src.app.config import settings


IS_SQLITE = settings.database_url.startswith("sqlite")


engine = create_engine(
    settings.database_url,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    }
    if IS_SQLITE
    else {},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    if not IS_SQLITE:
        return

    cursor = dbapi_connection.cursor()

    # WAL позволяет читать базу во время записи.
    cursor.execute("PRAGMA journal_mode=WAL")

    # Если база занята, ждём до 30 секунд, а не падаем сразу.
    cursor.execute("PRAGMA busy_timeout=30000")

    # Включаем внешние ключи SQLite.
    cursor.execute("PRAGMA foreign_keys=ON")

    # Баланс скорости и надёжности для WAL.
    cursor.execute("PRAGMA synchronous=NORMAL")

    # Временные таблицы держим в памяти.
    cursor.execute("PRAGMA temp_store=MEMORY")

    cursor.close()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def init_db() -> None:
    import src.autoalliance.models
    import src.ozon.models
    import src.web.models

    Base.metadata.create_all(bind=engine)

    from src.app.migrations import run_sqlite_migrations

    run_sqlite_migrations(engine)
