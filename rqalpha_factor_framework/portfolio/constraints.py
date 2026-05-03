import pandas as pd


def apply_stock_weight_cap(weights, max_weight):
    max_weight = float(max_weight)
    if max_weight < 0:
        raise ValueError("max_weight must be non-negative")
    return {stock: min(float(weight), max_weight) for stock, weight in weights.items()}


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
