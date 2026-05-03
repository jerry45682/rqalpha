def can_buy(last_price, limit_up):
    return float(last_price) < float(limit_up)


def can_sell(last_price, limit_down):
    return float(last_price) > float(limit_down)
