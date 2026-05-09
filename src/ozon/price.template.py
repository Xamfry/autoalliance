import math


def _calc_delivery(volume):
    if volume > 1000:
        return 9432.87

    # до одного литра
    price = 81.34

    if volume > 1:  # за каждый литр после первого литра до трех литров включительно
        liters = math.ceil(volume - 1)  # пропускаем первый литр
        liters = min(liters, 3 - 1)  # считаем максимум для двух добавочных литров
        price += liters * 18.3

    if volume > 3:
        liters = math.ceil(volume - 3)  # пропускаем первые три литра
        liters = min(liters, 190 - 3)  # максимум для 187 добавочных литров
        price += liters * 23.39

    if volume > 190:
        liters = math.ceil(volume - 190)  # пропускаем первые 190 литров
        # Максимум тут считать не нужно, так как ограничение в 1000 проверили в самом начале
        price += liters * 6.1

    return price


# Себес 100р
# Прибыль 20% от себеса но меньше 50р +
# Логистика 100р (считаем по формуле) + 20% +
# Комиссия 14% +
# Эквайринг 1,9% +

# Обработка 24 +
# Доставка до места 30 +
# Оплата сотрудника 70р +
# Налог = прибыли + оплата сотрудника * 15% +

# Процент за продажу = Себес+прибыль+налог+оплата сотрудника*2,5% ?
# Оплата за вывоз: если товар до 1 литра то 8р (включитильно) за каждый следующий литр 2р +
# Ошибки при отгрузке (задержка товара)  10р +
#
# Себес+прибыль+логистика+обработка+доставка до места+ оплата сотрубника+ошибки+ оплата за вывоз + налог + процент за продажу = x
#
# Y = итоговая цена без акции
#
# X/0,841 = X / (1 -(комисссия 14+эквайринг 1,9)/100)) = Y
#
# Z = Итоговая цена с акцией
#
# Y+90%=Z

PROFIT_PERCENT = 0.20  # Процент чистой прибыли от себеса
MIN_NET_PROFIT = 50  # Минимальна чистая прибыль в рублях
PROCESSING_FEE = 24  # Обработка
DELIVERY_FEE = 30  # Доставка до места (Last mile)
WORKER_FEE = 70  # Работа сотрудника (обновлено с 72)
ERROR_FEE = 10  # Ошибки при отгрузке
TAX_PERCENT = 0.15  # Налог (15%)
ACQUIRING_PERCENT = 0.020  # Эквайринг (2%)
SALES_PERCENT_RATE = 0  # Процент за продажу 0.025 = (`2.5`%)
LOGISTICS_MARKUP = 1.25  # Логистика + 25%
# ---

ACTION_MARKUP = 1.90  # Наценка для цены с акцией (Y + 90% = Z)


def calc_ozon_price(base, volume, commission=0.14):
    """
    Рассчитывает итоговую цену без акции (Y).
    X = Себес+прибыль+логистика+обработка+доставка до места+
        оплата сотрудника+ошибки+оплата за вывоз + налог + процент за продажу
    Y = X / (1 - (комиссия + эквайринг))
    """
    base = float(base)  # Себес

    net_profit = base * PROFIT_PERCENT

    # контролируем минимальный профит
    net_profit = max(net_profit, MIN_NET_PROFIT)

    # Логистика по формуле + 20%
    logistics = _calc_delivery(volume) * LOGISTICS_MARKUP

    # Оплата за вывоз
    export_fee = _calc_export_fee(volume)

    # Налог = (прибыль + оплата сотрудника) * 15%
    tax = (net_profit + WORKER_FEE) * TAX_PERCENT

    # Процент за продажу = (Себес + прибыль + налог + оплата сотрудника) * 2.5%
    sales_percent_base = base + net_profit + tax + WORKER_FEE
    sales_fee = sales_percent_base * SALES_PERCENT_RATE

    # Сумма всех расходов (X)
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

    # Расчет Y (цена без акции)
    # X / 0.841 (при дефолтной комиссии)
    multiplier = 1 - commission - ACQUIRING_PERCENT
    price_y = total_cost_x / multiplier

    return math.ceil(price_y)


def _calc_export_fee(volume):
    """Считает оплату за вывоз: 8р до 1л, далее 2р за каждый литр"""
    if volume <= 1:
        return 8.0

    extra_liters = math.ceil(volume - 1)
    return 8.0 + (extra_liters * 2.0)


def calc_net_profit(price, base, volume, commission=0.14):
    """
    Возвращает чистую прибыль
    """
    base = float(base)  # себес
    price = float(price)  # цена продажи

    # Сначала получаем X (сумма всех расходов + прибыль)
    multiplier = 1 - commission - ACQUIRING_PERCENT
    total_cost_x = price * multiplier

    # Считаем фиксированные расходы, которые не зависят от размера прибыли
    logistics = _calc_delivery(volume) * LOGISTICS_MARKUP
    export_fee = _calc_export_fee(volume)

    fixed_costs = logistics + PROCESSING_FEE + DELIVERY_FEE + ERROR_FEE + export_fee

    # --- Расчет коэффициентов ---
    # Прибыль (P) входит в итоговую сумму X следующим образом:
    # 1. Сама прибыль: P
    # 2. В налоге: P * TAX_PERCENT
    # 3. В проценте за продажу: (P + (P * TAX_PERCENT)) * SALES_PERCENT_RATE
    #
    # Если вынести P за скобки:
    # P * (1 + TAX_PERCENT + (1 + TAX_PERCENT) * SALES_PERCENT_RATE)
    # P * (1 + TAX_PERCENT) * (1 + SALES_PERCENT_RATE)

    # Коэффициент нагрузки на прибыль и сотрудника (у них одинаковая формула налогообложения)
    tax_load_factor = (1 + TAX_PERCENT) * (1 + SALES_PERCENT_RATE)

    # Коэффициент нагрузки на базу (она не облагается налогом 15%, только процентом с продаж)
    base_load_factor = 1 + SALES_PERCENT_RATE

    # Часть суммы X, которая НЕ зависит от P (вычитаем из общей суммы):
    # 1. Фикс расходы (логистика и т.д.)
    # 2. База (с учетом процента с продаж)
    # 3. Сотрудник (с учетом налога и процента с продаж — формула как у прибыли)
    constant_part = (
        fixed_costs + (base * base_load_factor) + (WORKER_FEE * tax_load_factor)
    )

    # Решаем уравнение: tax_load_factor * Profit = X - constant_part
    net_profit = (total_cost_x - constant_part) / tax_load_factor

    return net_profit


def is_promotional(price, base, volume, commission):
    # товар считается акционным если при текущей наценке его чистая прибыль составляет не менее 35% от розничной цены
    profit = calc_net_profit(
        price=price, base=base, volume=volume, commission=commission
    )
    return float(profit) >= float(base) * 0.35


if __name__ == "__main__":
    price = calc_ozon_price(base=1000, volume=10, commission=0.41)
    # print(540 * 350 * 150 / 1_000_000)
    # print(f"{price=}")
    # exit()

    net_profit = calc_net_profit(price=price, base=1000, volume=10, commission=0.41)
    print(f"{net_profit=}")

    # is_promo = is_promotional(price=price, base=1000, volume=20, commission=0.14)
    # print(f"{is_promo=}")


"""
14% комиссия для первого импорта на Ozon, что б товары прогрузились, СДЕЛАТЬ ОТДЕЛЬНЫМ СКРИПТОМ В ТАБЛИЦУ
комиссия категории (где 41%) - это уже выходное на Ozon, ОСТАВИТЬ УЖЕ В ЭТОЙМ СКРИПТЕ
"""
