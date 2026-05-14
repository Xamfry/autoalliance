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


def _has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as con:
        row = con.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name=:table_name"
            ),
            {"table_name": table_name},
        ).fetchone()

    return row is not None


def _create_autoalliance_purchases_if_missing(engine: Engine) -> None:
    if _has_table(engine, "autoalliance_purchases"):
        return

    with engine.begin() as con:
        con.execute(text("""
            CREATE TABLE autoalliance_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER,
                posting_number VARCHAR(255) NOT NULL,
                offer_id VARCHAR(255),
                sku INTEGER,
                supplier_code VARCHAR(255) NOT NULL,
                purchase_index INTEGER NOT NULL DEFAULT 1,
                quantity INTEGER NOT NULL DEFAULT 1,
                status VARCHAR(50) NOT NULL DEFAULT 'new',
                autoalliance_order_id VARCHAR(255),
                response_json JSON,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_autoalliance_purchase_unit UNIQUE (
                    posting_number,
                    offer_id,
                    supplier_code,
                    purchase_index
                )
            )
        """))

        con.execute(text("CREATE INDEX ix_autoalliance_purchases_shop_id ON autoalliance_purchases(shop_id)"))
        con.execute(text("CREATE INDEX ix_autoalliance_purchases_posting_number ON autoalliance_purchases(posting_number)"))
        con.execute(text("CREATE INDEX ix_autoalliance_purchases_offer_id ON autoalliance_purchases(offer_id)"))
        con.execute(text("CREATE INDEX ix_autoalliance_purchases_supplier_code ON autoalliance_purchases(supplier_code)"))
        con.execute(text("CREATE INDEX ix_autoalliance_purchases_status ON autoalliance_purchases(status)"))

    print("Migration: created autoalliance_purchases")


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
    
    _create_autoalliance_purchases_if_missing(engine)