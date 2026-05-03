import numpy as np
import pandas as pd

from rqalpha_factor_framework.factors.liquidity import calculate_liquidity_factors
from rqalpha_factor_framework.factors.momentum import calculate_momentum_factors
from rqalpha_factor_framework.factors.reversal import calculate_reversal_factors
from rqalpha_factor_framework.factors.risk import calculate_risk_factors
from rqalpha_factor_framework.factors.technical import calculate_technical_factors
from rqalpha_factor_framework.factors.valuation import calculate_valuation_factors


def sample_daily(order_book_id="600000.XSHG", periods=130):
    dates = pd.date_range("2023-01-01", periods=periods, freq="D")
    close = pd.Series(np.linspace(10.0, 20.0, periods))
    frame = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "order_book_id": order_book_id,
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.arange(periods) + 1000,
            "amount": (np.arange(periods) + 1000) * close,
            "turn": np.linspace(1.0, 3.0, periods),
            "tradestatus": 1,
            "peTTM": 10.0,
            "pbMRQ": 1.5,
            "psTTM": 2.0,
            "isST": 0,
        }
    )
    return frame


def test_market_factor_modules_return_expected_columns():
    daily = {"600000.XSHG": sample_daily()}

    valuation = calculate_valuation_factors(daily)
    momentum = calculate_momentum_factors(daily)
    reversal = calculate_reversal_factors(daily)
    risk = calculate_risk_factors(daily)
    liquidity = calculate_liquidity_factors(daily)
    technical = calculate_technical_factors(daily)

    assert valuation.loc["600000.XSHG", "pe_ttm"] == 10.0
    assert momentum.loc["600000.XSHG", "return_20"] > 0
    assert reversal.loc["600000.XSHG", "rsi"] > 0
    assert risk.loc["600000.XSHG", "max_drawdown_120"] >= 0
    assert liquidity.loc["600000.XSHG", "avg_amount_20"] > 0
    assert "macd_hist" in technical.columns
    assert "obv_trend" in technical.columns


def test_valuation_factors_convert_baostock_values_to_numeric():
    daily = {
        "600000.XSHG": pd.DataFrame(
            [
                {
                    "date": "2023-01-01",
                    "order_book_id": "600000.XSHG",
                    "peTTM": "10.5",
                    "pbMRQ": "",
                    "psTTM": None,
                }
            ]
        )
    }

    result = calculate_valuation_factors(daily)

    assert result.loc["600000.XSHG", "pe_ttm"] == 10.5
    assert np.isnan(result.loc["600000.XSHG", "pb"])
    assert np.isnan(result.loc["600000.XSHG", "ps_ttm"])


def test_risk_factors_report_positive_max_drawdown_with_minimum_window():
    close = np.concatenate([np.linspace(10.0, 20.0, 60), np.linspace(20.0, 14.0, 60)])
    daily = {"600000.XSHG": sample_daily(periods=120).assign(close=close)}

    result = calculate_risk_factors(daily)

    assert np.isclose(result.loc["600000.XSHG", "max_drawdown_120"], 0.3)


def test_risk_factors_return_nan_for_short_max_drawdown_window():
    daily = {"600000.XSHG": sample_daily(periods=119)}

    result = calculate_risk_factors(daily)

    assert np.isnan(result.loc["600000.XSHG", "max_drawdown_120"])


def test_factor_calculations_sort_unsorted_daily_data():
    ascending = sample_daily(periods=130)
    descending = ascending.iloc[::-1].reset_index(drop=True)

    expected = calculate_momentum_factors({"600000.XSHG": ascending})
    result = calculate_momentum_factors({"600000.XSHG": descending})

    assert result.loc["600000.XSHG", "return_20"] == expected.loc["600000.XSHG", "return_20"]
