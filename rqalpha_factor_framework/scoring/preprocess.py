import numpy as np
import pandas as pd

from rqalpha_factor_framework.factors.base import LOWER_BETTER, MIDDLE_BETTER


def winsorize_quantile(series, lower, upper):
    values = pd.to_numeric(series, errors="coerce")
    lower_bound = values.quantile(lower)
    upper_bound = values.quantile(upper)
    return values.clip(lower=lower_bound, upper=upper_bound)


def zscore(series):
    values = pd.to_numeric(series, errors="coerce")
    std = values.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=values.index)
    return (values - values.mean()) / std


def preprocess_factors(
    raw_factors,
    metadata,
    winsorize_quantiles=(0.01, 0.99),
    missing="median",
):
    factors = raw_factors.apply(pd.to_numeric, errors="coerce")
    factors = factors.replace([np.inf, -np.inf], np.nan)

    if missing == "median":
        factors = factors.fillna(factors.median())
    elif missing == "zero":
        factors = factors.fillna(0)
    else:
        raise ValueError(f"Unsupported missing strategy: {missing}")

    lower, upper = winsorize_quantiles
    processed = pd.DataFrame(index=factors.index)
    for column in factors.columns:
        winsorized = winsorize_quantile(factors[column], lower, upper)
        meta = metadata.get(column)
        if meta is not None and meta.direction == MIDDLE_BETTER:
            score = -zscore((winsorized - winsorized.median()).abs())
        else:
            score = zscore(winsorized)
            if meta is not None and meta.direction == LOWER_BETTER:
                score = -score
        processed[column] = score

    return processed.replace([np.inf, -np.inf], np.nan).fillna(0)
