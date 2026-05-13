from pathlib import Path

import pytest

from rqalpha_factor_framework.config.loader import load_config


def test_load_default_config_has_required_sections():
    config = load_config()

    assert set(config) == {
        "stock_pool",
        "rebalance",
        "portfolio",
        "factors",
        "scoring",
        "filters",
        "risk",
        "data",
        "backtest",
    }
    assert config["stock_pool"]["index"] == "000300.XSHG"
    assert config["stock_pool"]["symbols"] is None
    assert config["rebalance"]["frequency"] == "monthly"
    assert config["rebalance"]["tradingday"] == 1
    assert config["portfolio"]["holding_count"] == 14
    assert config["portfolio"]["buffer_count"] == 21
    assert config["portfolio"]["weighting"] == "score"
    assert config["factors"]["enabled_categories"] == [
        "valuation",
        "quality",
        "growth",
        "momentum",
        "reversal",
        "risk",
        "liquidity",
        "technical",
    ]
    w = config["factors"]["category_weights"]
    assert set(w.keys()) == { "valuation", "quality", "growth", "momentum",
                              "reversal", "risk", "liquidity", "technical" }
    assert sum(w.values()) == pytest.approx(1.0)
    assert config["factors"]["factor_weights"] == {}
    assert config["scoring"]["missing"] == "median"
    assert config["scoring"]["min_factor_coverage"] == 0.3
    assert config["scoring"]["winsorize_quantiles"] == [0.01, 0.99]
    assert config["scoring"]["standardize"] == "zscore"
    assert config["scoring"]["neutralize"] == "none"
    assert config["filters"]["exclude_st"] is True
    assert config["filters"]["exclude_suspended"] is True
    assert config["filters"]["min_listed_days"] == 180
    assert config["filters"]["min_avg_amount_20"] == 44047790
    assert config["filters"]["require_positive_pe_pb"] is True
    assert config["filters"]["skip_limit_up_buy"] is True
    assert config["filters"]["skip_limit_down_sell"] is True
    assert config["risk"]["max_stock_weight"] == pytest.approx(0.09, abs=0.01)
    assert config["risk"]["max_industry_weight"] == 0.25
    assert config["risk"]["market_timing"]["enabled"] is True
    assert config["risk"]["market_timing"]["index"] == "000300.XSHG"
    assert config["risk"]["market_timing"]["ma120_exposure"] == 0.50
    assert config["risk"]["market_timing"]["ma250_exposure"] == 0.30
    assert config["risk"]["market_timing"]["full_exposure"] == 1.00
    assert config["data"]["cache_dir"] == ".rqalpha_factor_cache"
    assert config["data"]["adjustflag"] == "2"
    assert config["data"]["start_date"] == "2024-01-01"
    assert config["data"]["end_date"] is None
    assert config["data"]["prefetch"] is False
    assert config["data"]["runtime_fetch"] is True
    assert config["data"]["runtime_fetch_financial"] is False
    assert config["data"]["runtime_fetch_industry"] is True
    assert config["data"]["financial_tables"] == [
        "profit",
        "balance",
        "growth",
        "cash_flow",
        "dupont",
        "operation",
    ]
    assert config["backtest"]["start_date"] == "2025-01-05"
    assert config["backtest"]["end_date"] == "2025-12-25"
    assert config["backtest"]["frequency"] == "1d"
    assert config["backtest"]["benchmark"] == "000300.XSHG"
    assert config["backtest"]["initial_cash"] == 1000000
    assert config["backtest"]["data_bundle_path"] is None
    assert (
        config["backtest"]["result_path"]
        == "rqalpha_factor_framework/backtest/multi_factor_result.pkl"
    )
    assert abs(sum(config["factors"]["category_weights"].values()) - 1.0) < 1e-12
    assert "quality" in config["factors"]["enabled_categories"]
    assert "growth" in config["factors"]["enabled_categories"]


def test_load_config_merges_user_overrides(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "portfolio:\n"
        "  holding_count: 5\n"
        "stock_pool:\n"
        "  symbols:\n"
        "    - 600000.XSHG\n",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config["portfolio"]["holding_count"] == 5
    assert config["portfolio"]["buffer_count"] == 21
    assert config["stock_pool"]["symbols"] == ["600000.XSHG"]


def test_load_config_rejects_invalid_category_weight_sum(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "factors:\n"
        "  category_weights:\n"
        "    valuation: 0.9\n"
        "    quality: 0.9\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="category weights"):
        load_config(path)


def test_load_config_rejects_non_mapping_root(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("- portfolio\n- factors\n", encoding="utf-8")

    with pytest.raises(ValueError, match="config root must be a mapping"):
        load_config(path)


def test_load_config_rejects_invalid_yaml(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("portfolio: [", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid YAML|invalid yaml"):
        load_config(path)


def test_load_config_rejects_null_category_weights(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "factors:\n"
        "  category_weights:\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="factors.category_weights"):
        load_config(path)


def test_load_config_rejects_non_numeric_category_weight(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "factors:\n"
        "  category_weights:\n"
        "    valuation: many\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="factors.category_weights"):
        load_config(path)


def test_load_config_rejects_buffer_count_below_holding_count(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "portfolio:\n"
        "  holding_count: 30\n"
        "  buffer_count: 29\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="portfolio.buffer_count"):
        load_config(path)


def test_load_config_rejects_non_numeric_holding_count(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "portfolio:\n"
        "  holding_count: many\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="portfolio.holding_count"):
        load_config(path)


def test_load_config_rejects_non_numeric_buffer_count(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "portfolio:\n"
        "  buffer_count: many\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="portfolio.buffer_count"):
        load_config(path)


@pytest.mark.parametrize("value", ["many", -0.1, 1.1])
def test_load_config_rejects_invalid_min_factor_coverage(tmp_path, value):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "scoring:\n"
        f"  min_factor_coverage: {value}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="scoring.min_factor_coverage"):
        load_config(path)


def test_load_config_returns_are_isolated_between_calls(tmp_path):
    first = load_config()
    first["portfolio"]["holding_count"] = 1
    first["factors"]["category_weights"]["valuation"] = 1.0

    path = tmp_path / "config.yaml"
    path.write_text(
        "portfolio:\n"
        "  holding_count: 5\n",
        encoding="utf-8",
    )
    second = load_config(path)
    third = load_config()

    assert second["portfolio"]["holding_count"] == 5
    assert second["portfolio"]["buffer_count"] == 21
    assert second["factors"]["category_weights"]["valuation"] == pytest.approx(0.15, abs=0.01)
    assert third["portfolio"]["holding_count"] == 14
    assert third["factors"]["category_weights"]["valuation"] == pytest.approx(0.15, abs=0.01)


def test_load_aggressive_template_config():
    config = load_config(
        Path("rqalpha_factor_framework/config/multi_factor_config_aggressive.yaml")
    )

    assert config["rebalance"]["frequency"] == "weekly"
    assert config["portfolio"]["holding_count"] == 10
    assert config["portfolio"]["buffer_count"] == 20
    assert config["portfolio"]["weighting"] == "score"
    assert config["factors"]["category_weights"]["growth"] == 0.30
    assert config["factors"]["category_weights"]["momentum"] == 0.25
    assert config["factors"]["category_weights"]["technical"] == 0.20
    assert config["filters"]["min_listed_days"] == 90
    assert config["filters"]["min_avg_amount_20"] == 10000000
    assert config["filters"]["require_positive_pe_pb"] is False
    assert config["risk"]["max_stock_weight"] == 0.40
    assert config["risk"]["max_industry_weight"] == 0.60
    assert (
        config["backtest"]["result_path"]
        == "rqalpha_factor_framework/backtest/multi_factor_result_aggressive_weekly.pkl"
    )
    assert abs(sum(config["factors"]["category_weights"].values()) - 1.0) < 1e-12
