import pandas as pd
import pytest

from rqalpha_factor_framework.factors.base import FACTOR_METADATA
from rqalpha_factor_framework.scoring.factor_score import build_factor_scores
from rqalpha_factor_framework.scoring.preprocess import preprocess_factors


def test_preprocess_factors_fills_winsorizes_standardizes_and_flips_direction():
    raw = pd.DataFrame(
        {
            "pe_ttm": [5.0, 10.0, 1000.0, None],
            "return_20": [0.01, 0.02, 0.03, 0.04],
        },
        index=["a", "b", "c", "d"],
    )

    processed = preprocess_factors(
        raw,
        FACTOR_METADATA,
        winsorize_quantiles=(0.01, 0.99),
        missing="median",
    )

    assert processed.notna().all().all()
    assert processed.loc["a", "pe_ttm"] > processed.loc["c", "pe_ttm"]
    assert abs(processed["return_20"].mean()) < 1e-12


def test_build_factor_scores_calculates_category_and_total_scores():
    processed = pd.DataFrame(
        {
            "pe_ttm": [1.0, -1.0],
            "pb": [1.0, -1.0],
            "return_20": [-1.0, 1.0],
        },
        index=["a", "b"],
    )
    weights = {"valuation": 0.5, "momentum": 0.5}

    scored = build_factor_scores(processed, FACTOR_METADATA, weights)

    assert "valuation_score" in scored.columns
    assert "momentum_score" in scored.columns
    assert "score" in scored.columns


def test_preprocess_factors_supports_zero_missing_fill():
    raw = pd.DataFrame({"return_20": [1.0, None, 3.0]}, index=["a", "b", "c"])

    processed = preprocess_factors(raw, FACTOR_METADATA, missing="zero")

    assert processed.notna().all().all()
    assert abs(processed["return_20"].mean()) < 1e-12


def test_preprocess_factors_rejects_unsupported_missing_strategy():
    raw = pd.DataFrame({"return_20": [1.0, None, 3.0]}, index=["a", "b", "c"])

    with pytest.raises(ValueError, match="missing"):
        preprocess_factors(raw, FACTOR_METADATA, missing="drop")


def test_preprocess_factors_scores_middle_better_near_median_higher():
    raw = pd.DataFrame(
        {"avg_turnover_20": [10.0, 11.0, 100.0]},
        index=["near", "median", "far"],
    )

    processed = preprocess_factors(raw, FACTOR_METADATA, missing="median")

    assert processed.loc["median", "avg_turnover_20"] > processed.loc["far", "avg_turnover_20"]
    assert processed.loc["near", "avg_turnover_20"] > processed.loc["far", "avg_turnover_20"]


def test_build_factor_scores_normalizes_configured_factor_weights():
    processed = pd.DataFrame(
        {
            "pe_ttm": [10.0, 0.0],
            "pb": [0.0, 10.0],
        },
        index=["a", "b"],
    )
    factor_weights = {"valuation": {"pe_ttm": 9.0, "pb": 1.0}}

    scored = build_factor_scores(
        processed,
        FACTOR_METADATA,
        {"valuation": 1.0},
        factor_weights=factor_weights,
    )

    assert scored.loc["a", "valuation_score"] == 9.0
    assert scored.loc["b", "valuation_score"] == 1.0
    assert list(scored.index) == ["a", "b"]


def test_unknown_factor_columns_are_processed_without_direction_adjustment():
    raw = pd.DataFrame({"custom_factor": [1.0, 2.0, 3.0]}, index=["a", "b", "c"])

    processed = preprocess_factors(raw, FACTOR_METADATA)

    assert processed.loc["c", "custom_factor"] > processed.loc["a", "custom_factor"]
