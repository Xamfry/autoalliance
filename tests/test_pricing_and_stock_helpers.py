import pytest

from src.ozon.pricing import calc_ozon_price
from src.ozon.sync.price_stock_sync_service import (
    _commission_to_fraction,
    _quantity_by_warehouses,
    _volume_liters_from_mm,
)


def test_volume_liters_from_mm():
    assert _volume_liters_from_mm(length_mm=100, width_mm=200, height_mm=300) == 6.0
    assert _volume_liters_from_mm(length_mm=None, width_mm=200, height_mm=300) is None


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, 0.14),
        (15, 0.15),
        (0.12, 0.12),
    ],
)
def test_commission_to_fraction(value, expected):
    assert _commission_to_fraction(value) == expected


def test_quantity_by_selected_warehouses_partial_name_match():
    offer = {
        "quantity": 99,
        "warehouses": [
            {"name": "Машково д., Люберецкий р-н", "quantity": "4"},
            {"name": "Кетчерская", "quantity": 7},
            {"name": "Другой склад", "quantity": 100},
        ],
    }

    assert _quantity_by_warehouses(offer, ["машково", "кетчерская"]) == 11


def test_quantity_by_warehouses_fallback_to_total_quantity():
    assert _quantity_by_warehouses({"quantity": "12"}, []) == 12


def test_calc_ozon_price_returns_positive_int():
    price = calc_ozon_price(base=1000, volume=5.5, commission=0.15)
    assert isinstance(price, int)
    assert price > 1000
