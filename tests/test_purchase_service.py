import asyncio
from datetime import datetime

from sqlalchemy import select

from src.autoalliance.client import AutoAllianceClient
from src.autoalliance.models import AutoAlliancePurchase, SourceProduct
from src.autoalliance.purchase_service import AutoAlliancePurchaseService
from src.ozon.models import OzonPosting, OzonPostingProduct, OzonShop


def _seed_posting(db, *, quantity=2, offer_id="2127A08M", manufacturer_article="08M"):
    shop = OzonShop(
        shop_name="test-shop",
        client_id="client",
        token="token",
        warehouse=123,
        is_active=True,
    )
    db.add(shop)
    db.flush()

    posting = OzonPosting(
        shop_id=shop.id,
        posting_number="POST-1",
        order_id=1,
        order_number="ORDER-1",
        status="awaiting_packaging",
        in_process_at=datetime(2026, 5, 14, 12, 0, 0),
        raw_json={},
    )
    db.add(posting)
    db.flush()

    product = OzonPostingProduct(
        posting_id=posting.id,
        offer_id=offer_id,
        manufacturer_article=manufacturer_article,
        sku=111,
        name="Test product",
        quantity=quantity,
    )
    db.add(product)
    db.commit()
    return shop, posting, product


def test_purchase_new_postings_splits_quantity_to_single_orders(db_session, monkeypatch):
    _seed_posting(db_session, quantity=2)
    db_session.add(
        SourceProduct(
            source_code="400443",
            article="2127A08M",
            manufacturer_article="08M",
            source_brand="TEST",
        )
    )
    db_session.commit()

    calls = []

    async def fake_create_order_from_items(self, *, items, profile_id=None, comment=None):
        calls.append({"items": items, "profile_id": profile_id, "comment": comment})
        return {"orderId": f"AA-{len(calls)}"}
    
    async def fake_sleep(*args, **kwargs):
        return None

    monkeypatch.setattr(AutoAllianceClient, "create_order_from_items", fake_create_order_from_items)
    monkeypatch.setattr("src.autoalliance.purchase_service.asyncio.sleep", fake_sleep)

    result = asyncio.run(AutoAlliancePurchaseService(db_session, delay=0).purchase_new_postings())

    assert result["candidates"] == 1
    assert result["purchased"] == 2
    assert result["failed"] == 0
    assert len(calls) == 2
    assert calls[0]["items"] == [{"code": "400443", "quantity": 1}]
    assert "unit=1" in calls[0]["comment"]
    assert "unit=2" in calls[1]["comment"]

    purchases = list(db_session.scalars(select(AutoAlliancePurchase).order_by(AutoAlliancePurchase.purchase_index)))
    assert len(purchases) == 2
    assert [p.status for p in purchases] == ["done", "done"]
    assert [p.autoalliance_order_id for p in purchases] == ["AA-1", "AA-2"]


def test_purchase_new_postings_is_idempotent_for_done_units(db_session, monkeypatch):
    _seed_posting(db_session, quantity=1)
    db_session.add(
        SourceProduct(
            source_code="400443",
            article="2127A08M",
            source_brand="TEST",
        )
    )
    db_session.commit()

    calls = []

    async def fake_create_order_from_items(self, *, items, profile_id=None, comment=None):
        calls.append(items)
        return {"orderId": "AA-1"}
    
    async def fake_sleep(*args, **kwargs):
        return None

    monkeypatch.setattr(AutoAllianceClient, "create_order_from_items", fake_create_order_from_items)
    monkeypatch.setattr("src.autoalliance.purchase_service.asyncio.sleep", fake_sleep)

    first = asyncio.run(AutoAlliancePurchaseService(db_session, delay=0).purchase_new_postings())
    second = asyncio.run(AutoAlliancePurchaseService(db_session, delay=0).purchase_new_postings())

    assert first["purchased"] == 1
    assert second["purchased"] == 0
    assert second["skipped"] == 1
    assert len(calls) == 1


def test_purchase_new_postings_counts_no_match(db_session, monkeypatch):
    _seed_posting(db_session, quantity=1, offer_id="NO-MATCH", manufacturer_article=None)

    async def fail_if_called(self, *, items, profile_id=None, comment=None):
        raise AssertionError("AutoAlliance API must not be called without source match")

    monkeypatch.setattr(AutoAllianceClient, "create_order_from_items", fail_if_called)

    result = asyncio.run(AutoAlliancePurchaseService(db_session, delay=0).purchase_new_postings())

    assert result["candidates"] == 1
    assert result["no_match"] == 1
    assert result["purchased"] == 0
