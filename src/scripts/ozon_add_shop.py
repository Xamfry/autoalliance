from getpass import getpass

from src.app.logging_config import configure_logging
from src.app.db import SessionLocal, init_db
from src.ozon.repository import OzonRepository


def main() -> None:
    configure_logging("ozon_add_shop")
    init_db()
    shop_name = input("Shop name: ").strip()
    client_id = input("Ozon Client-Id: ").strip()
    token = getpass("Ozon Api-Key/token: ").strip()
    warehouse_raw = input("Warehouse ID: ").strip()
    warehouse = int(warehouse_raw) if warehouse_raw else None
    if not shop_name or not client_id or not token:
        raise SystemExit("shop_name, client_id and token are required")
    with SessionLocal() as db:
        repo = OzonRepository(db)
        shop = repo.create_or_update_shop(shop_name=shop_name, client_id=client_id, token=token, warehouse=warehouse)
        print(f"Saved shop: id={shop.id}, shop_name={shop.shop_name}")


if __name__ == "__main__":
    main()
