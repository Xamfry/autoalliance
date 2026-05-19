from src.autoalliance.models import SourceProduct
from src.ozon.models import OzonProduct, OzonShop
from src.ozon.sync.price_stock_sync_service import PriceStockSyncService


def _seed_shop(db):
    shop = OzonShop(
        shop_name="test-shop",
        client_id="client",
        token="token",
        warehouse=123,
        is_active=True,
    )
    db.add(shop)
    db.flush()
    return shop


def test_list_sync_rows_uses_only_approved_non_archived_with_source_match(db_session):
    shop = _seed_shop(db_session)

    good = OzonProduct(
        shop_id=shop.id,
        offer_id="A1",
        product_id=1,
        name="good",
        archived=False,
        moderate_status="approved",
    )
    archived = OzonProduct(
        shop_id=shop.id,
        offer_id="A2",
        product_id=2,
        name="archived",
        archived=True,
        moderate_status="approved",
    )
    not_approved = OzonProduct(
        shop_id=shop.id,
        offer_id="A3",
        product_id=3,
        name="not approved",
        archived=False,
        moderate_status="declined",
    )
    db_session.add_all([good, archived, not_approved])
    db_session.add(SourceProduct(source_code="S1", article="A1", source_brand="BRAND"))
    db_session.add(SourceProduct(source_code="S2", article="A2", source_brand="BRAND"))
    db_session.add(SourceProduct(source_code="S3", article="A3", source_brand="BRAND"))
    db_session.commit()

    rows = PriceStockSyncService(db_session)._list_sync_rows(shop)

    assert len(rows) == 1
    assert rows[0].ozon_product.offer_id == "A1"
    assert rows[0].search_article == "A1"
    assert rows[0].search_brand == "BRAND"


def test_apply_supplier_data_and_calculate_price(db_session):
    product = OzonProduct(
        shop_id=1,
        offer_id="A1",
        product_id=1,
        archived=False,
        moderate_status="approved",
        length_mm=100,
        width_mm=200,
        height_mm=300,
        fbs_commission_percent=15,
    )
    service = PriceStockSyncService(db_session)

    service._apply_supplier_data(
        product,
        {
            "price": "1000.50",
            "quantity": 99,
            "warehouses": [
                {"name": "Машково д.", "quantity": 3},
                {"name": "Другой склад", "quantity": 50},
            ],
        },
    )
    calculated = service._calculate_price(product)

    assert product.supplier_price_rub == 1000.50
    assert product.supplier_qty == 3
    assert product.stock == 3
    assert calculated is True
    assert isinstance(product.price_calc, int)
    assert product.price_calc > 1000


def test_calculate_price_returns_false_without_dimensions(db_session):
    product = OzonProduct(
        shop_id=1,
        offer_id="A1",
        product_id=1,
        supplier_price_rub=1000,
        length_mm=None,
        width_mm=200,
        height_mm=300,
    )

    assert PriceStockSyncService(db_session)._calculate_price(product) is False
