import numpy as np
import pandas as pd


LOWER_IS_BETTER = {"pe", "pb"}
HIGHER_IS_BETTER = {"roe", "momentum_60"}


def winsorize_quantile(series, lower=0.05, upper=0.95):
    series = pd.to_numeric(series, errors="coerce")
    clean = series.dropna()
    if clean.empty:
        return series
    low = clean.quantile(lower)
    high = clean.quantile(upper)
    return series.clip(lower=low, upper=high)


def zscore(series):
    series = pd.to_numeric(series, errors="coerce")
    mean = series.mean()
    std = series.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=series.index)
    return (series - mean) / std


def calculate_momentum(order_book_id, history_bars, window=60):
    prices = history_bars(order_book_id, window + 1, "1d", "close")
    prices = np.asarray(prices, dtype=float)
    prices = prices[~np.isnan(prices)]
    if len(prices) < 2 or prices[0] == 0:
        return np.nan
    return prices[-1] / prices[0] - 1.0


def add_momentum_factor(factors, history_bars, window=60):
    factors = factors.copy()
    factors["momentum_60"] = [
        calculate_momentum(order_book_id, history_bars, window=window)
        for order_book_id in factors.index
    ]
    return factors


def build_factor_scores(raw_factors, weights, winsorize_quantiles=(0.05, 0.95)):
    lower, upper = winsorize_quantiles
    result = raw_factors.copy()
    score_parts = []

    for factor_name, weight in weights.items():
        if factor_name not in result.columns:
            continue
        normalized = zscore(winsorize_quantile(result[factor_name], lower, upper))
        if factor_name in LOWER_IS_BETTER:
            normalized = -normalized
        elif factor_name not in HIGHER_IS_BETTER:
            raise ValueError("Unsupported factor: {}".format(factor_name))
        result["{}_score".format(factor_name)] = normalized
        score_parts.append(normalized * float(weight))

    if not score_parts:
        result["score"] = np.nan
        return result

    result["score"] = sum(score_parts)
    return result.dropna(subset=["score"])


def fetch_fundamental_factors(order_book_ids, get_factor):
    fields = ["pe_ratio", "pb_ratio", "roe"]
    data = get_factor(
        order_book_ids,
        fields,
        count=1,
        expect_df=True,
    )
    if data is None or len(data) == 0:
        return pd.DataFrame(index=order_book_ids, columns=["pe", "pb", "roe"], dtype=float)

    frame = data.reset_index()
    order_col = "order_book_id" if "order_book_id" in frame.columns else "level_1"
    if order_col not in frame.columns:
        order_col = frame.columns[0]
    latest = frame.drop_duplicates(order_col, keep="last").set_index(order_col)
    return pd.DataFrame(
        {
            "pe": pd.to_numeric(latest.get("pe_ratio"), errors="coerce"),
            "pb": pd.to_numeric(latest.get("pb_ratio"), errors="coerce"),
            "roe": pd.to_numeric(latest.get("roe"), errors="coerce"),
        }
    )
