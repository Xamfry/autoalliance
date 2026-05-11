from sqlalchemy import text
from sqlalchemy.engine import Engine


def _has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as con:
        rows = con.execute(text(f"PRAGMA table_info({table_name})")).fetchall()

    return any(row[1] == column_name for row in rows)


def _add_column_if_missing(
    engine: Engine,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    if not _has_column(engine, table_name, column_name):
        with engine.begin() as con:
            con.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")
            )
        print(f"Migration: added {table_name}.{column_name}")


def run_sqlite_migrations(engine: Engine) -> None:
    if not str(engine.url).startswith("sqlite"):
        return

    # Ozon price calc fields
    _add_column_if_missing(engine, "ozon_products", "price_current", "REAL")
    _add_column_if_missing(engine, "ozon_products", "price_calc", "INTEGER")

    # Supplier fields from AutoAlliance
    _add_column_if_missing(engine, "ozon_products", "supplier_price_rub", "REAL")
    _add_column_if_missing(engine, "ozon_products", "supplier_qty", "INTEGER")

    # Ozon dimensions
    _add_column_if_missing(engine, "ozon_products", "length_mm", "INTEGER")
    _add_column_if_missing(engine, "ozon_products", "width_mm", "INTEGER")
    _add_column_if_missing(engine, "ozon_products", "height_mm", "INTEGER")
    _add_column_if_missing(engine, "ozon_products", "weight_g", "INTEGER")
    
    _add_column_if_missing(engine, "ozon_shops", "warehouse", "INTEGER")

    _add_column_if_missing(engine, "ozon_postings", "courier_status", "TEXT")
    _add_column_if_missing(engine, "ozon_postings", "courier_user_id", "INTEGER")
    _add_column_if_missing(engine, "ozon_postings", "courier_username", "TEXT")