import pandas as pd

from rqalpha_factor_framework import (
    apply_stock_weight_cap as package_apply_stock_weight_cap,
    build_equal_weight_targets as package_build_equal_weight_targets,
    build_score_weight_targets as package_build_score_weight_targets,
    can_buy as package_can_buy,
    can_sell as package_can_sell,
    filter_by_avg_amount as package_filter_by_avg_amount,
    filter_stocks as package_filter_stocks,
    market_timing_exposure as package_market_timing_exposure,
)
from rqalpha_factor_framework.filters.liquidity_filter import filter_by_avg_amount
from rqalpha_factor_framework.filters.stock_filter import filter_stocks
from rqalpha_factor_framework.filters.trading_filter import can_buy, can_sell
from rqalpha_factor_framework.portfolio.constraints import (
    apply_stock_weight_cap,
    market_timing_exposure,
)
from rqalpha_factor_framework.portfolio.equal_weight import build_equal_weight_targets
from rqalpha_factor_framework.portfolio.score_weight import build_score_weight_targets


def test_top_level_package_exports_core_helpers():
    assert package_filter_stocks is filter_stocks
    assert package_filter_by_avg_amount is filter_by_avg_amount
    assert package_can_buy is can_buy
    assert package_can_sell is can_sell
    assert package_build_equal_weight_targets is build_equal_weight_targets
    assert package_build_score_weight_targets is build_score_weight_targets
    assert package_apply_stock_weight_cap is apply_stock_weight_cap
    assert package_market_timing_exposure is market_timing_exposure


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


def test_trading_filter_rejects_invalid_prices():
    invalid_cases = [
        (None, 10.0),
        (10.0, None),
        (float("nan"), 10.0),
        (10.0, float("nan")),
        (float("inf"), 10.0),
        (float("-inf"), 10.0),
        (10.0, float("inf")),
        (10.0, float("-inf")),
        ("bad", 10.0),
        (10.0, "bad"),
    ]

    for last_price, limit_price in invalid_cases:
        assert not can_buy(last_price, limit_price)
        assert not can_sell(last_price, limit_price)
