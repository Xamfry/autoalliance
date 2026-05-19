import sqlite3

from sqlalchemy import create_engine, inspect, text

from src.app.db_utils import retry_db_lock
from src.app.migrations import run_sqlite_migrations


def test_migration_creates_autoalliance_purchases_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")

    run_sqlite_migrations(engine)

    inspector = inspect(engine)
    assert "autoalliance_purchases" in inspector.get_table_names()

    columns = {column["name"] for column in inspector.get_columns("autoalliance_purchases")}
    assert {
        "posting_number",
        "offer_id",
        "supplier_code",
        "purchase_index",
        "status",
        "response_json",
    }.issubset(columns)


def test_migration_adds_missing_columns_to_existing_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as con:
        con.execute(text("CREATE TABLE ozon_products (id INTEGER PRIMARY KEY AUTOINCREMENT)"))

    run_sqlite_migrations(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("ozon_products")}
    assert "length_mm" in columns
    assert "width_mm" in columns
    assert "height_mm" in columns
    assert "fbs_commission_percent" in columns


def test_retry_db_lock_retries_locked_error(monkeypatch):
    calls = {"count": 0}
    sleeps = []

    monkeypatch.setattr("src.app.db_utils.time.sleep", lambda delay: sleeps.append(delay))

    @retry_db_lock(retries=3, delay=0.01)
    def unstable_operation():
        calls["count"] += 1
        if calls["count"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    assert unstable_operation() == "ok"
    assert calls["count"] == 2
    assert sleeps == [0.01]
