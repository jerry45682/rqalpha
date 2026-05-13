from collections import namedtuple

import numpy as np
import pandas as pd


FactorMeta = namedtuple("FactorMeta", ["name", "category", "direction"])

HIGHER_BETTER = "higher_better"
LOWER_BETTER = "lower_better"
MIDDLE_BETTER = "middle_better"


FACTOR_METADATA = {
    "pe_ttm": FactorMeta("pe_ttm", "valuation", LOWER_BETTER),
    "pb": FactorMeta("pb", "valuation", LOWER_BETTER),
    "ps_ttm": FactorMeta("ps_ttm", "valuation", LOWER_BETTER),
    "pcf_ncf_ttm": FactorMeta("pcf_ncf_ttm", "valuation", LOWER_BETTER),
    "roe": FactorMeta("roe", "quality", HIGHER_BETTER),
    "roa": FactorMeta("roa", "quality", HIGHER_BETTER),
    "gross_margin": FactorMeta("gross_margin", "quality", HIGHER_BETTER),
    "debt_to_asset": FactorMeta("debt_to_asset", "quality", LOWER_BETTER),
    "asset_turnover": FactorMeta("asset_turnover", "quality", HIGHER_BETTER),
    "inventory_turnover": FactorMeta("inventory_turnover", "quality", HIGHER_BETTER),
    "receivables_turnover": FactorMeta(
        "receivables_turnover", "quality", HIGHER_BETTER
    ),
    "revenue_growth_yoy": FactorMeta("revenue_growth_yoy", "growth", HIGHER_BETTER),
    "net_profit_growth_yoy": FactorMeta("net_profit_growth_yoy", "growth", HIGHER_BETTER),
    "operating_cashflow_growth_yoy": FactorMeta(
        "operating_cashflow_growth_yoy", "growth", HIGHER_BETTER
    ),
    "return_20": FactorMeta("return_20", "momentum", HIGHER_BETTER),
    "return_60": FactorMeta("return_60", "momentum", HIGHER_BETTER),
    "return_120": FactorMeta("return_120", "momentum", HIGHER_BETTER),
    "price_ma60_strength": FactorMeta("price_ma60_strength", "momentum", HIGHER_BETTER),
    "return_5": FactorMeta("return_5", "reversal", LOWER_BETTER),
    "rsi": FactorMeta("rsi", "reversal", LOWER_BETTER),
    "volatility_60": FactorMeta("volatility_60", "risk", LOWER_BETTER),
    "max_drawdown_120": FactorMeta("max_drawdown_120", "risk", LOWER_BETTER),
    "avg_amount_20": FactorMeta("avg_amount_20", "liquidity", HIGHER_BETTER),
    "avg_turnover_20": FactorMeta("avg_turnover_20", "liquidity", MIDDLE_BETTER),
    "macd_hist": FactorMeta("macd_hist", "technical", HIGHER_BETTER),
    "obv_trend": FactorMeta("obv_trend", "technical", HIGHER_BETTER),
}


def sorted_frame(frame):
    if frame is None or frame.empty:
        return pd.DataFrame()
    if "date" in frame.columns:
        return frame.sort_values("date")
    return frame


def sorted_financial_frame(frame):
    if frame is None or frame.empty:
        return pd.DataFrame()
    for column in ("pubDate", "statDate", "date"):
        if column in frame.columns:
            col = pd.to_numeric(
                pd.to_datetime(frame[column], errors="coerce").astype(np.int64),
                errors="coerce",
            )
            if col.is_monotonic_increasing:
                return frame
            return frame.sort_values(column)
    return frame


def numeric_value(value):
    return pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]


def latest_financial_numeric(frame, column):
    data = sorted_financial_frame(frame)
    if data.empty or column not in data.columns:
        return np.nan
    return numeric_value(data.iloc[-1].get(column, np.nan))


def numeric_series(frame, column):
    if frame.empty or column not in frame.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def build_factor_frame(rows, columns):
    frame = pd.DataFrame(rows, columns=["order_book_id"] + columns)
    if frame.empty:
        return pd.DataFrame(columns=columns, index=pd.Index([], name="order_book_id"))
    return frame.set_index("order_book_id")


def nan_row(order_book_id, columns):
    row = {"order_book_id": order_book_id}
    row.update({column: np.nan for column in columns})
    return row
