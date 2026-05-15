from sqlalchemy import text
from sqlalchemy.engine import Engine


def _is_sqlite(engine: Engine) -> bool:
    return str(engine.url).startswith("sqlite")


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


def _has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    if not _has_table(engine, table_name):
        return False

    with engine.connect() as con:
        rows = con.execute(text(f"PRAGMA table_info({table_name})")).fetchall()

    return any(row[1] == column_name for row in rows)


def _add_column_if_missing(
    engine: Engine,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    if not _has_table(engine, table_name):
        print(f"Migration: skip {table_name}.{column_name}, table does not exist")
        return

    if _has_column(engine, table_name, column_name):
        return

    with engine.begin() as con:
        con.execute(
            text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")
        )

    print(f"Migration: added {table_name}.{column_name}")


def _create_index_if_missing(
    engine: Engine,
    index_name: str,
    table_name: str,
    columns_sql: str,
) -> None:
    if not _has_table(engine, table_name):
        return

    with engine.connect() as con:
        row = con.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name=:index_name"
            ),
            {"index_name": index_name},
        ).fetchone()

    if row is not None:
        return

    with engine.begin() as con:
        con.execute(
            text(f"CREATE INDEX {index_name} ON {table_name} ({columns_sql})")
        )

    print(f"Migration: created index {index_name}")


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

    print("Migration: created table autoalliance_purchases")


def _migrate_ozon_shops(engine: Engine) -> None:
    _add_column_if_missing(engine, "ozon_shops", "shop_name", "VARCHAR(255)")
    _add_column_if_missing(engine, "ozon_shops", "client_id", "VARCHAR(255)")
    _add_column_if_missing(engine, "ozon_shops", "token", "TEXT")
    _add_column_if_missing(engine, "ozon_shops", "warehouse", "INTEGER")
    _add_column_if_missing(engine, "ozon_shops", "is_active", "BOOLEAN DEFAULT 1")
    _add_column_if_missing(engine, "ozon_shops", "created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
    _add_column_if_missing(engine, "ozon_shops", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")

    _create_index_if_missing(engine, "ix_ozon_shops_shop_name", "ozon_shops", "shop_name")
    _create_index_if_missing(engine, "ix_ozon_shops_is_active", "ozon_shops", "is_active")


def _migrate_ozon_products(engine: Engine) -> None:
    columns = {
        "shop_id": "INTEGER",
        "sku": "INTEGER",
        "name": "VARCHAR(1000)",
        "product_id": "INTEGER",
        "offer_id": "VARCHAR(255)",

        "price_current": "REAL",
        "price_calc": "INTEGER",
        "supplier_price_rub": "REAL",
        "supplier_qty": "INTEGER",

        "length_mm": "INTEGER",
        "width_mm": "INTEGER",
        "height_mm": "INTEGER",
        "weight_g": "INTEGER",

        "barcodes_json": "JSON",
        "fbs_commission_percent": "REAL",
        "fbo_commission_percent": "REAL",
        "rfbs_commission_percent": "REAL",
        "fbp_commission_percent": "REAL",

        "stocks_json": "JSON",
        "has_stock": "BOOLEAN DEFAULT 0",

        "category_id": "INTEGER",
        "description_category_id": "INTEGER",
        "first_image_url": "VARCHAR(1500)",

        "price": "REAL",
        "stock": "INTEGER",
        "warehouse_id": "INTEGER",

        "archived": "BOOLEAN DEFAULT 0",
        "visible": "BOOLEAN",
        "moderate_status": "VARCHAR(255)",

        "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        "raw_json": "JSON",
    }

    for column_name, column_sql in columns.items():
        _add_column_if_missing(engine, "ozon_products", column_name, column_sql)

    _create_index_if_missing(engine, "ix_ozon_products_shop_id", "ozon_products", "shop_id")
    _create_index_if_missing(engine, "ix_ozon_products_sku", "ozon_products", "sku")
    _create_index_if_missing(engine, "ix_ozon_products_product_id", "ozon_products", "product_id")
    _create_index_if_missing(engine, "ix_ozon_products_offer_id", "ozon_products", "offer_id")
    _create_index_if_missing(engine, "ix_ozon_products_category_id", "ozon_products", "category_id")
    _create_index_if_missing(engine, "ix_ozon_products_description_category_id", "ozon_products", "description_category_id")
    _create_index_if_missing(engine, "ix_ozon_products_warehouse_id", "ozon_products", "warehouse_id")
    _create_index_if_missing(engine, "ix_ozon_products_archived", "ozon_products", "archived")
    _create_index_if_missing(engine, "ix_ozon_products_moderate_status", "ozon_products", "moderate_status")


def _migrate_ozon_sync_logs(engine: Engine) -> None:
    columns = {
        "shop_id": "INTEGER",
        "sync_type": "VARCHAR(64)",
        "status": "VARCHAR(32)",
        "message": "TEXT",
        "items_total": "INTEGER DEFAULT 0",
        "items_success": "INTEGER DEFAULT 0",
        "items_failed": "INTEGER DEFAULT 0",
        "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    }

    for column_name, column_sql in columns.items():
        _add_column_if_missing(engine, "ozon_sync_logs", column_name, column_sql)

    _create_index_if_missing(engine, "ix_ozon_sync_logs_shop_id", "ozon_sync_logs", "shop_id")
    _create_index_if_missing(engine, "ix_ozon_sync_logs_sync_type", "ozon_sync_logs", "sync_type")
    _create_index_if_missing(engine, "ix_ozon_sync_logs_status", "ozon_sync_logs", "status")


def _migrate_ozon_postings(engine: Engine) -> None:
    columns = {
        "shop_id": "INTEGER",
        "posting_number": "VARCHAR(255)",
        "order_id": "INTEGER",
        "order_number": "VARCHAR(255)",
        "status": "VARCHAR(255)",
        "substatus": "VARCHAR(255)",
        "in_process_at": "DATETIME",
        "shipment_date": "DATETIME",
        "is_split_parent": "BOOLEAN DEFAULT 0",
        "is_split_child": "BOOLEAN DEFAULT 0",
        "raw_json": "JSON",
        "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",

        "courier_status": "VARCHAR(50) DEFAULT 'new'",
        "courier_user_id": "INTEGER",
        "courier_username": "VARCHAR(255)",
    }

    for column_name, column_sql in columns.items():
        _add_column_if_missing(engine, "ozon_postings", column_name, column_sql)

    _create_index_if_missing(engine, "ix_ozon_postings_shop_id", "ozon_postings", "shop_id")
    _create_index_if_missing(engine, "ix_ozon_postings_posting_number", "ozon_postings", "posting_number")
    _create_index_if_missing(engine, "ix_ozon_postings_order_id", "ozon_postings", "order_id")
    _create_index_if_missing(engine, "ix_ozon_postings_order_number", "ozon_postings", "order_number")
    _create_index_if_missing(engine, "ix_ozon_postings_status", "ozon_postings", "status")
    _create_index_if_missing(engine, "ix_ozon_postings_substatus", "ozon_postings", "substatus")
    _create_index_if_missing(engine, "ix_ozon_postings_courier_status", "ozon_postings", "courier_status")
    _create_index_if_missing(engine, "ix_ozon_postings_courier_user_id", "ozon_postings", "courier_user_id")


def _migrate_ozon_posting_products(engine: Engine) -> None:
    columns = {
        "posting_id": "INTEGER",
        "offer_id": "VARCHAR(255)",
        "sku": "INTEGER",
        "name": "VARCHAR(1000)",
        "quantity": "INTEGER",
        "image_url": "VARCHAR(1500)",
        "manufacturer_article": "VARCHAR(255)",
    }

    for column_name, column_sql in columns.items():
        _add_column_if_missing(engine, "ozon_posting_products", column_name, column_sql)

    _create_index_if_missing(engine, "ix_ozon_posting_products_posting_id", "ozon_posting_products", "posting_id")
    _create_index_if_missing(engine, "ix_ozon_posting_products_offer_id", "ozon_posting_products", "offer_id")
    _create_index_if_missing(engine, "ix_ozon_posting_products_sku", "ozon_posting_products", "sku")
    _create_index_if_missing(engine, "ix_ozon_posting_products_manufacturer_article", "ozon_posting_products", "manufacturer_article")


def _migrate_source_products(engine: Engine) -> None:
    columns = {
        "source_code": "VARCHAR(255)",
        "article": "VARCHAR(255)",
        "manufacturer_article": "VARCHAR(255)",
        "factory_article": "VARCHAR(255)",
        "source_name": "VARCHAR(1000)",
        "source_brand": "VARCHAR(255)",
        "opt4_price": "REAL",
        "opt3_price": "REAL",
        "opt2_price": "REAL",
        "opt1_price": "REAL",
        "retail_price": "REAL",
        "stock_mashkovo": "INTEGER",
        "stock_ketcherskaya": "INTEGER",
        "stock_other": "INTEGER",
        "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    }

    for column_name, column_sql in columns.items():
        _add_column_if_missing(engine, "source_products", column_name, column_sql)

    _create_index_if_missing(engine, "ix_source_products_source_code", "source_products", "source_code")
    _create_index_if_missing(engine, "ix_source_products_article", "source_products", "article")
    _create_index_if_missing(engine, "ix_source_products_manufacturer_article", "source_products", "manufacturer_article")
    _create_index_if_missing(engine, "ix_source_products_factory_article", "source_products", "factory_article")
    _create_index_if_missing(engine, "ix_source_products_source_brand", "source_products", "source_brand")


def _migrate_autoalliance_products(engine: Engine) -> None:
    columns = {
        "source_product_id": "INTEGER",
        "parse_status": "VARCHAR(50)",
        "matched_by": "VARCHAR(100)",
        "search_article": "VARCHAR(255)",
        "search_brand": "VARCHAR(255)",
        "error_message": "TEXT",
        "supplier_code": "VARCHAR(255)",
        "supplier_article": "VARCHAR(255)",
        "supplier_brand": "VARCHAR(255)",
        "supplier_name": "VARCHAR(1000)",
        "price": "REAL",
        "quantity": "INTEGER",
        "for_order": "BOOLEAN",
        "can_return": "BOOLEAN",
        "tnved": "VARCHAR(100)",
        "description_html": "TEXT",
        "description_text": "TEXT",
        "catalog_group": "VARCHAR(500)",
        "catalog_subgroup": "VARCHAR(500)",
        "manual_category": "VARCHAR(500)",
        "manual_subcategory": "VARCHAR(500)",
        "width": "REAL",
        "height": "REAL",
        "length": "REAL",
        "weight": "REAL",
        "barcode": "VARCHAR(255)",
        "site_url": "VARCHAR(1500)",
        "first_picture_url": "VARCHAR(1500)",
        "pictures_json": "JSON",
        "pictures_without_watermark_json": "JSON",
        "warehouses_json": "JSON",
        "analogs_json": "JSON",
        "preview_applicabilities_json": "JSON",
        "preview_certificates_json": "JSON",
        "preview_width": "REAL",
        "preview_height": "REAL",
        "preview_length": "REAL",
        "preview_weight": "REAL",
        "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    }

    for column_name, column_sql in columns.items():
        _add_column_if_missing(engine, "autoalliance_products", column_name, column_sql)

    _create_index_if_missing(engine, "ix_autoalliance_products_source_product_id", "autoalliance_products", "source_product_id")
    _create_index_if_missing(engine, "ix_autoalliance_products_parse_status", "autoalliance_products", "parse_status")
    _create_index_if_missing(engine, "ix_autoalliance_products_matched_by", "autoalliance_products", "matched_by")
    _create_index_if_missing(engine, "ix_autoalliance_products_search_article", "autoalliance_products", "search_article")
    _create_index_if_missing(engine, "ix_autoalliance_products_search_brand", "autoalliance_products", "search_brand")
    _create_index_if_missing(engine, "ix_autoalliance_products_supplier_code", "autoalliance_products", "supplier_code")
    _create_index_if_missing(engine, "ix_autoalliance_products_supplier_article", "autoalliance_products", "supplier_article")
    _create_index_if_missing(engine, "ix_autoalliance_products_supplier_brand", "autoalliance_products", "supplier_brand")
    _create_index_if_missing(engine, "ix_autoalliance_products_catalog_group", "autoalliance_products", "catalog_group")
    _create_index_if_missing(engine, "ix_autoalliance_products_catalog_subgroup", "autoalliance_products", "catalog_subgroup")
    _create_index_if_missing(engine, "ix_autoalliance_products_manual_category", "autoalliance_products", "manual_category")
    _create_index_if_missing(engine, "ix_autoalliance_products_manual_subcategory", "autoalliance_products", "manual_subcategory")
    _create_index_if_missing(engine, "ix_autoalliance_products_barcode", "autoalliance_products", "barcode")


def _migrate_autoalliance_purchases(engine: Engine) -> None:
    _create_autoalliance_purchases_if_missing(engine)

    columns = {
        "shop_id": "INTEGER",
        "posting_number": "VARCHAR(255)",
        "offer_id": "VARCHAR(255)",
        "sku": "INTEGER",
        "supplier_code": "VARCHAR(255)",
        "purchase_index": "INTEGER DEFAULT 1",
        "quantity": "INTEGER DEFAULT 1",
        "status": "VARCHAR(50) DEFAULT 'new'",
        "autoalliance_order_id": "VARCHAR(255)",
        "response_json": "JSON",
        "error_message": "TEXT",
        "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    }

    for column_name, column_sql in columns.items():
        _add_column_if_missing(engine, "autoalliance_purchases", column_name, column_sql)

    _create_index_if_missing(engine, "ix_autoalliance_purchases_shop_id", "autoalliance_purchases", "shop_id")
    _create_index_if_missing(engine, "ix_autoalliance_purchases_posting_number", "autoalliance_purchases", "posting_number")
    _create_index_if_missing(engine, "ix_autoalliance_purchases_offer_id", "autoalliance_purchases", "offer_id")
    _create_index_if_missing(engine, "ix_autoalliance_purchases_sku", "autoalliance_purchases", "sku")
    _create_index_if_missing(engine, "ix_autoalliance_purchases_supplier_code", "autoalliance_purchases", "supplier_code")
    _create_index_if_missing(engine, "ix_autoalliance_purchases_status", "autoalliance_purchases", "status")
    _create_index_if_missing(engine, "ix_autoalliance_purchases_autoalliance_order_id", "autoalliance_purchases", "autoalliance_order_id")


def _migrate_web_users(engine: Engine) -> None:
    columns = {
        "username": "VARCHAR(255)",
        "password_hash": "VARCHAR(255)",
        "role": "VARCHAR(50) DEFAULT 'courier'",
        "is_active": "BOOLEAN DEFAULT 1",
        "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    }

    for column_name, column_sql in columns.items():
        _add_column_if_missing(engine, "web_users", column_name, column_sql)

    _create_index_if_missing(engine, "ix_web_users_username", "web_users", "username")
    _create_index_if_missing(engine, "ix_web_users_role", "web_users", "role")


def _migrate_courier_action_logs(engine: Engine) -> None:
    columns = {
        "user_id": "INTEGER",
        "username": "VARCHAR(255)",
        "posting_id": "INTEGER",
        "posting_number": "VARCHAR(255)",
        "action": "VARCHAR(100)",
        "old_status": "VARCHAR(100)",
        "new_status": "VARCHAR(100)",
        "comment": "TEXT",
        "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    }

    for column_name, column_sql in columns.items():
        _add_column_if_missing(engine, "courier_action_logs", column_name, column_sql)

    _create_index_if_missing(engine, "ix_courier_action_logs_posting_number", "courier_action_logs", "posting_number")
    _create_index_if_missing(engine, "ix_courier_action_logs_action", "courier_action_logs", "action")


def run_sqlite_migrations(engine: Engine) -> None:
    if not _is_sqlite(engine):
        return

    _migrate_ozon_shops(engine)
    _migrate_ozon_products(engine)
    _migrate_ozon_sync_logs(engine)
    _migrate_ozon_postings(engine)
    _migrate_ozon_posting_products(engine)

    _migrate_source_products(engine)
    _migrate_autoalliance_products(engine)
    _migrate_autoalliance_purchases(engine)

    _migrate_web_users(engine)
    _migrate_courier_action_logs(engine)