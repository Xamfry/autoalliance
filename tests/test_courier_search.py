from datetime import datetime

from src.autoalliance.models import SourceProduct
from src.ozon.models import OzonPosting, OzonPostingProduct, OzonShop
from src.web.routes.courier import get_courier_rows


def test_courier_search_finds_partial_article_and_posting_number(db_session):
    shop = OzonShop(
        shop_name="shop",
        client_id="client",
        token="token",
        warehouse=1,
        is_active=True,
    )
    db_session.add(shop)
    db_session.flush()

    posting = OzonPosting(
        shop_id=shop.id,
        posting_number="POST-2127-XYZ",
        order_id=1,
        order_number="ORDER-777",
        status="awaiting_packaging",
        in_process_at=datetime(2026, 5, 14, 12, 0, 0),
        raw_json={},
    )
    db_session.add(posting)
    db_session.flush()

    product = OzonPostingProduct(
        posting_id=posting.id,
        offer_id="2127A08M",
        manufacturer_article="08M",
        sku=123,
        name="Фильтр тестовый",
        quantity=1,
    )
    db_session.add(product)
    db_session.add(
        SourceProduct(
            source_code="400443",
            article="2127A08M",
            manufacturer_article="08M",
            factory_article="FACT-1",
            source_name="Фильтр AutoAlliance",
            source_brand="BRAND",
        )
    )
    db_session.commit()

    by_beginning = get_courier_rows(db_session, search="2127")
    by_ending = get_courier_rows(db_session, search="08M")
    by_posting = get_courier_rows(db_session, search="POST-2127")
    by_source_code = get_courier_rows(db_session, search="400443")

    assert len(by_beginning) == 1
    assert len(by_ending) == 1
    assert len(by_posting) == 1
    assert len(by_source_code) == 1
    assert by_beginning[0]["offer_id"] == "2127A08M"
