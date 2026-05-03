import pandas as pd

from rqalpha_factor_framework.filters.liquidity_filter import filter_by_avg_amount
from rqalpha_factor_framework.filters.stock_filter import filter_stocks
from rqalpha_factor_framework.filters.trading_filter import can_buy, can_sell


def test_stock_filter_removes_st_invalid_valuation_and_recent_listing():
    frame = pd.DataFrame(
        {
            "is_st": [0, 1, 0],
            "listed_days": [200, 200, 10],
            "pe_ttm": [10.0, 10.0, -1.0],
            "pb": [1.0, 1.0, 1.0],
        },
        index=["a", "b", "c"],
    )

    assert filter_stocks(frame, min_listed_days=180).index.tolist() == ["a"]


def test_stock_filter_filters_all_when_required_valuation_fields_are_missing():
    frame = pd.DataFrame(
        {"is_st": [0], "listed_days": [200], "pe_ttm": [10.0]},
        index=["a"],
    )

    assert filter_stocks(frame).empty


def test_liquidity_filter_removes_low_amount():
    frame = pd.DataFrame({"avg_amount_20": [50000000, 1000000]}, index=["a", "b"])

    assert filter_by_avg_amount(frame, 30000000).index.tolist() == ["a"]


def test_trading_filter_handles_limit_prices():
    assert can_buy(last_price=10.0, limit_up=10.1)
    assert not can_buy(last_price=10.1, limit_up=10.1)
    assert can_sell(last_price=10.0, limit_down=9.9)
    assert not can_sell(last_price=9.9, limit_down=9.9)
