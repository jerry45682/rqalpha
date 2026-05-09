import pandas as pd


def apply_stock_weight_cap(weights, max_weight):
    max_weight = float(max_weight)
    if max_weight < 0:
        raise ValueError("max_weight must be non-negative")
    return {stock: min(float(weight), max_weight) for stock, weight in weights.items()}


def apply_industry_weight_cap(weights, industry_map, max_industry_weight):
    max_industry_weight = float(max_industry_weight)
    if max_industry_weight < 0:
        raise ValueError("max_industry_weight must be non-negative")

    result = {stock: float(weight) for stock, weight in weights.items()}
    industry_totals = {}
    for stock, weight in result.items():
        industry = industry_map.get(stock) if industry_map else None
        if not industry:
            continue
        industry_totals[industry] = industry_totals.get(industry, 0.0) + weight

    for industry, total_weight in industry_totals.items():
        if total_weight <= max_industry_weight or total_weight <= 0:
            continue
        scale = max_industry_weight / total_weight
        for stock in result:
            if industry_map.get(stock) == industry:
                result[stock] *= scale
    return result


def market_timing_exposure(index_close, full_exposure, ma120_exposure, ma250_exposure):
    close = pd.to_numeric(index_close, errors="coerce").dropna()
    if len(close) < 120:
        return float(full_exposure)

    latest = close.iloc[-1]
    if len(close) >= 250 and latest < close.tail(250).mean():
        return float(ma250_exposure)
    if latest < close.tail(120).mean():
        return float(ma120_exposure)
    return float(full_exposure)
