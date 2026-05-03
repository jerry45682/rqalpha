import pandas as pd

from rqalpha_factor_framework.portfolio.constraints import (
    apply_stock_weight_cap,
    market_timing_exposure,
)
from rqalpha_factor_framework.portfolio.equal_weight import build_equal_weight_targets
from rqalpha_factor_framework.portfolio.score_weight import build_score_weight_targets


def test_equal_weight_targets_use_buffer_for_existing_positions():
    scored = pd.DataFrame({"score": [5, 4, 3, 2, 1]}, index=["a", "b", "c", "d", "e"])

    targets = build_equal_weight_targets(
        scored, ["d"], holding_count=2, buffer_count=4, total_exposure=1.0
    )

    assert "d" in targets
    assert len(targets) == 2
    assert abs(sum(targets.values()) - 1.0) < 1e-12


def test_equal_weight_targets_never_exceed_holding_count_with_many_buffer_holds():
    scored = pd.DataFrame(
        {"score": [6, 5, 4, 3, 2, 1]},
        index=["a", "b", "c", "d", "e", "f"],
    )

    targets = build_equal_weight_targets(
        scored,
        ["b", "c", "d", "e"],
        holding_count=3,
        buffer_count=5,
        total_exposure=0.9,
    )

    assert len(targets) == 3
    assert list(targets) == ["b", "c", "d"]
    assert abs(sum(targets.values()) - 0.9) < 1e-12


def test_stock_weight_cap_redistributes_excess_to_cash():
    weights = {"a": 0.8, "b": 0.2}

    capped = apply_stock_weight_cap(weights, 0.5)

    assert capped["a"] == 0.5
    assert capped["b"] == 0.2


def test_stock_weight_cap_rejects_negative_cap():
    try:
        apply_stock_weight_cap({"a": 0.1}, -0.1)
    except ValueError as exc:
        assert "max_weight" in str(exc)
    else:
        raise AssertionError("negative cap should raise ValueError")


def test_score_weight_targets_sum_to_exposure():
    scored = pd.DataFrame({"score": [3.0, 1.0]}, index=["a", "b"])

    weights = build_score_weight_targets(scored, holding_count=2, total_exposure=0.5)

    assert abs(sum(weights.values()) - 0.5) < 1e-12
    assert weights["a"] > weights["b"]


def test_score_weight_targets_returns_empty_for_empty_input():
    scored = pd.DataFrame({"score": []})

    assert build_score_weight_targets(scored, holding_count=2) == {}


def test_score_weight_targets_shift_scores_to_non_negative_weights():
    scored = pd.DataFrame({"score": [-1.0, -3.0]}, index=["a", "b"])

    weights = build_score_weight_targets(scored, holding_count=2, total_exposure=1.0)

    assert weights == {"a": 1.0, "b": 0.0}


def test_market_timing_exposure_uses_moving_averages():
    assert market_timing_exposure(pd.Series([1.0] * 119), 1.0, 0.5, 0.3) == 1.0
    assert market_timing_exposure(pd.Series([10.0] * 250), 1.0, 0.5, 0.3) == 1.0

    below_250 = pd.Series([10.0] * 249 + [1.0])
    assert market_timing_exposure(below_250, 1.0, 0.5, 0.3) == 0.3

    below_120_only = pd.Series([1.0] * 130 + [10.0] * 119 + [9.0])
    assert market_timing_exposure(below_120_only, 1.0, 0.5, 0.3) == 0.5
