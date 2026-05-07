import numpy as np
import pandas as pd

from .base import build_factor_frame, latest_financial_numeric, nan_row


FACTOR_COLUMNS = [
    "revenue_growth_yoy",
    "net_profit_growth_yoy",
    "operating_cashflow_growth_yoy",
]


def calculate_growth_factors(financial_data):
    rows = []
    for order_book_id, tables in financial_data.items():
        growth = tables.get("growth", pd.DataFrame())
        profit = tables.get("profit", pd.DataFrame())
        cash_flow = tables.get("cash_flow", pd.DataFrame())
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        row["revenue_growth_yoy"] = latest_financial_numeric(
            growth, "revenue_growth_yoy"
        )
        if pd.isna(row["revenue_growth_yoy"]):
            row["revenue_growth_yoy"] = _same_quarter_yoy(profit, "MBRevenue")
        row["net_profit_growth_yoy"] = latest_financial_numeric(
            growth, "net_profit_growth_yoy"
        )
        row["operating_cashflow_growth_yoy"] = latest_financial_numeric(
            growth, "operating_cashflow_growth_yoy"
        )
        if pd.isna(row["operating_cashflow_growth_yoy"]):
            row["operating_cashflow_growth_yoy"] = _same_quarter_yoy(
                _operating_cashflow_proxy(profit, cash_flow),
                "operating_cashflow_proxy",
            )
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)


def _same_quarter_yoy(frame, column):
    if frame is None or frame.empty or column not in frame.columns:
        return np.nan
    if "year" not in frame.columns or "quarter" not in frame.columns:
        return np.nan

    data = frame.copy()
    data["year"] = pd.to_numeric(data["year"], errors="coerce")
    data["quarter"] = pd.to_numeric(data["quarter"], errors="coerce")
    data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["year", "quarter", column])
    if data.empty:
        return np.nan
    sort_columns = ["year", "quarter"]
    for date_column in ("pub_date", "pubDate", "stat_date", "statDate", "date"):
        if date_column in data.columns:
            sort_column = f"__sort_{date_column}"
            data[sort_column] = pd.to_datetime(data[date_column], errors="coerce")
            sort_columns.append(sort_column)
    data = data.sort_values(sort_columns, na_position="first")

    latest = data.iloc[-1]
    previous = data[
        (data["year"] == latest["year"] - 1)
        & (data["quarter"] == latest["quarter"])
    ]
    if previous.empty:
        return np.nan
    base = previous.iloc[-1][column]
    if pd.isna(base) or base == 0:
        return np.nan
    return latest[column] / base - 1.0


def _operating_cashflow_proxy(profit, cash_flow):
    if (
        profit is None
        or cash_flow is None
        or profit.empty
        or cash_flow.empty
        or "MBRevenue" not in profit.columns
    ):
        return pd.DataFrame()

    cash_flow_column = None
    for column in ("CFOToOR", "operating_cashflow_to_revenue"):
        if column in cash_flow.columns:
            cash_flow_column = column
            break
    if cash_flow_column is None:
        return pd.DataFrame()

    merge_keys = [
        column
        for column in ("year", "quarter")
        if column in profit.columns and column in cash_flow.columns
    ]
    if len(merge_keys) != 2:
        return pd.DataFrame()

    merged = profit[merge_keys + ["MBRevenue"]].merge(
        cash_flow[merge_keys + [cash_flow_column]],
        on=merge_keys,
        how="inner",
    )
    if merged.empty:
        return merged

    merged["MBRevenue"] = pd.to_numeric(merged["MBRevenue"], errors="coerce")
    merged[cash_flow_column] = pd.to_numeric(merged[cash_flow_column], errors="coerce")
    merged["operating_cashflow_proxy"] = (
        merged["MBRevenue"] * merged[cash_flow_column]
    )
    return merged
