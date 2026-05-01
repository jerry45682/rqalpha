import numpy as np
import pandas as pd

from rqalpha.examples.multi_factor_strategy.config import load_config
from rqalpha.examples.multi_factor_strategy.factors import (
    build_factor_scores,
    calculate_momentum,
    fetch_baostock_factors,
    zscore,
)
from rqalpha.examples.multi_factor_strategy.filters import resolve_stock_pool
from rqalpha.examples.multi_factor_strategy.portfolio import build_equal_weight_targets
from rqalpha.examples.multi_factor_strategy.rebalancer import plan_rebalance_orders


def test_load_config_merges_defaults(tmp_path):
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        """
stock_pool:
  symbols: [000001.XSHE, 000002.XSHE]
portfolio:
  size: 3
factors:
  weights:
    pe: 0.2
    momentum_60: 0.8
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config["stock_pool"]["symbols"] == ["000001.XSHE", "000002.XSHE"]
    assert config["stock_pool"]["index"] == "000300.XSHG"
    assert config["portfolio"]["size"] == 3
    assert config["rebalance"]["frequency"] == "monthly"
    assert config["factors"]["weights"]["pe"] == 0.2
    assert config["factors"]["weights"]["pb"] == 0.25


def test_zscore_returns_zero_for_constant_series():
    result = zscore(pd.Series([5.0, 5.0, 5.0], index=["a", "b", "c"]))

    assert result.to_dict() == {"a": 0.0, "b": 0.0, "c": 0.0}


def test_build_factor_scores_applies_direction_and_weights():
    raw = pd.DataFrame(
        {
            "pe": [10.0, 20.0, 30.0],
            "pb": [1.0, 2.0, 3.0],
            "roe": [0.10, 0.20, 0.30],
            "momentum_60": [0.01, 0.03, 0.05],
        },
        index=["low_value", "middle", "growth"],
    )

    scores = build_factor_scores(
        raw,
        weights={"pe": 0.25, "pb": 0.25, "roe": 0.25, "momentum_60": 0.25},
        winsorize_quantiles=(0.0, 1.0),
    )

    assert scores.loc["growth", "score"] > scores.loc["middle", "score"]
    assert scores.loc["middle", "score"] > scores.loc["low_value", "score"]
    assert set(["pe_score", "pb_score", "roe_score", "momentum_60_score", "score"]).issubset(scores.columns)


def test_calculate_momentum_uses_first_and_last_close():
    def history_bars(order_book_id, count, frequency, field):
        assert order_book_id == "000001.XSHE"
        assert count == 61
        assert frequency == "1d"
        assert field == "close"
        return np.array([10.0, 11.0, 12.0, 15.0])

    assert calculate_momentum("000001.XSHE", history_bars, window=60) == 0.5


def test_fetch_baostock_factors_reads_latest_bar_fields():
    def history_bars(order_book_id, count, frequency, fields, include_now=True):
        assert count == 1
        assert frequency == "1d"
        assert fields == ["peTTM", "pbMRQ"]
        assert include_now is True
        return np.array([(8.0, 1.2)], dtype=[("peTTM", "f8"), ("pbMRQ", "f8")])

    result = fetch_baostock_factors(["600000.XSHG"], history_bars)

    assert result.loc["600000.XSHG", "pe"] == 8.0
    assert result.loc["600000.XSHG", "pb"] == 1.2


def test_resolve_stock_pool_prefers_explicit_symbols():
    config = {"stock_pool": {"index": "000300.XSHG", "symbols": ["000001.XSHE"]}}

    result = resolve_stock_pool(config, index_components=lambda index: ["000002.XSHE"])

    assert result == ["000001.XSHE"]


def test_build_equal_weight_targets_selects_top_names():
    scores = pd.DataFrame(
        {"score": [0.1, 0.9, 0.8]},
        index=["000001.XSHE", "000002.XSHE", "000003.XSHE"],
    )

    targets = build_equal_weight_targets(scores, portfolio_size=2)

    assert targets == {"000002.XSHE": 0.5, "000003.XSHE": 0.5}


def test_plan_rebalance_orders_sells_removed_positions_before_buys():
    orders = plan_rebalance_orders(
        current_positions=["000001.XSHE", "000002.XSHE"],
        target_weights={"000002.XSHE": 0.5, "000003.XSHE": 0.5},
    )

    assert orders == [
        ("000001.XSHE", 0.0),
        ("000002.XSHE", 0.5),
        ("000003.XSHE", 0.5),
    ]
