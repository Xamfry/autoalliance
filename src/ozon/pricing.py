import math


PROFIT_PERCENT = 0.20
MIN_NET_PROFIT = 50
PROCESSING_FEE = 24
DELIVERY_FEE = 30
WORKER_FEE = 70
ERROR_FEE = 10
TAX_PERCENT = 0.15
ACQUIRING_PERCENT = 0.020
SALES_PERCENT_RATE = 0
LOGISTICS_MARKUP = 1.25


def calc_volume_liters_from_meters(
    *,
    length_m: float | None,
    width_m: float | None,
    height_m: float | None,
) -> float | None:
    if not length_m or not width_m or not height_m:
        return None

    return float(length_m) * float(width_m) * float(height_m) * 1000


def _calc_delivery(volume: float) -> float:
    if volume > 1000:
        return 9432.87

    price = 81.34

    if volume > 1:
        liters = math.ceil(volume - 1)
        liters = min(liters, 3 - 1)
        price += liters * 18.3

    if volume > 3:
        liters = math.ceil(volume - 3)
        liters = min(liters, 190 - 3)
        price += liters * 23.39

    if volume > 190:
        liters = math.ceil(volume - 190)
        price += liters * 6.1

    return price


def _calc_export_fee(volume: float) -> float:
    if volume <= 1:
        return 8.0

    extra_liters = math.ceil(volume - 1)
    return 8.0 + (extra_liters * 2.0)


def calc_ozon_price(
    *,
    base: float,
    volume: float,
    commission: float = 0.14,
) -> int:
    base = float(base)
    volume = float(volume)

    net_profit = base * PROFIT_PERCENT
    net_profit = max(net_profit, MIN_NET_PROFIT)

    logistics = _calc_delivery(volume) * LOGISTICS_MARKUP
    export_fee = _calc_export_fee(volume)

    tax = (net_profit + WORKER_FEE) * TAX_PERCENT

    sales_percent_base = base + net_profit + tax + WORKER_FEE
    sales_fee = sales_percent_base * SALES_PERCENT_RATE

    total_cost_x = (
        base
        + net_profit
        + logistics
        + PROCESSING_FEE
        + DELIVERY_FEE
        + WORKER_FEE
        + ERROR_FEE
        + export_fee
        + tax
        + sales_fee
    )

    multiplier = 1 - commission - ACQUIRING_PERCENT

    if multiplier <= 0:
        raise ValueError(f"Некорректная комиссия: {commission}")

    return math.ceil(total_cost_x / multiplier)