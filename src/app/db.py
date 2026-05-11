from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.app.config import settings


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)

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