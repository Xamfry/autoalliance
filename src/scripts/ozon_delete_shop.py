import argparse

from src.app.db import SessionLocal, init_db
from src.ozon.models import OzonShop
from src.ozon.repository import OzonRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete Ozon shop and all related products")
    parser.add_argument("shop_id", type=int, nargs="?", help="Ozon shop ID from ozon_shops")
    parser.add_argument("--yes", action="store_true", help="Delete without confirmation")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        repo = OzonRepository(db)

        shop_id = args.shop_id
        if shop_id is None:
            shops = repo.list_shops()
            if not shops:
                print("Магазины не найдены.")
                return
            print("Подключённые магазины:")
            for shop in shops:
                products_count = repo.count_products_by_shop_id(shop.id)
                print(f"{shop.id}. {shop.shop_name} | products={products_count}")
            raw = input("Введите ID магазина для удаления: ").strip()
            if not raw.isdigit():
                print("Некорректный ID.")
                return
            shop_id = int(raw)

        shop = db.get(OzonShop, shop_id)
        if shop is None:
            print(f"Магазин с ID={shop_id} не найден.")
            return

        products_count = repo.count_products_by_shop_id(shop_id)
        if not args.yes:
            answer = input(
                f"Удалить магазин '{shop.shop_name}' ID={shop.id} и товары: {products_count}? Введите YES: "
            ).strip()
            if answer != "YES":
                print("Удаление отменено.")
                return

        deleted = repo.delete_shop_with_products(shop_id)
        if deleted:
            print(f"Удалено: магазин ID={shop_id}, товары={products_count}.")
        else:
            print(f"Магазин с ID={shop_id} не найден.")


if __name__ == "__main__":
    main()
