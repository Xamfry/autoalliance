from src.app.db import SessionLocal, init_db
from src.ozon.repository import OzonRepository


def main() -> None:
    init_db()
    with SessionLocal() as db:
        repo = OzonRepository(db)
        shops = repo.list_shops()

        if not shops:
            print("Магазины не найдены.")
            return

        print("Подключённые магазины:")
        for shop in shops:
            products_count = repo.count_products_by_shop_id(shop.id)
            status = "active" if shop.is_active else "inactive"
            warehouse = shop.warehouse if shop.warehouse is not None else "N/A"
            print(f"{shop.id}. {shop.shop_name} | client_id={shop.client_id} | status={status} | products={products_count} | warehouse={warehouse}")


if __name__ == "__main__":
    main()
