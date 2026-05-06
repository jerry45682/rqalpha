import math


def _finite_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def can_buy(last_price, limit_up):
    price = _finite_float(last_price)
    limit = _finite_float(limit_up)
    if price is None or limit is None:
        return False
    return price < limit


def can_sell(last_price, limit_down):
    price = _finite_float(last_price)
    limit = _finite_float(limit_down)
    if price is None or limit is None:
        return False
    return price > limit
