from pathlib import Path

import pytest

from rqalpha_factor_framework.config.loader import load_config


def test_load_default_config_has_required_sections():
    config = load_config()

    assert config["stock_pool"]["index"] == "000300.XSHG"
    assert config["rebalance"]["frequency"] == "monthly"
    assert config["portfolio"]["holding_count"] == 30
    assert config["portfolio"]["buffer_count"] == 60
    assert config["scoring"]["winsorize_quantiles"] == [0.01, 0.99]
    assert abs(sum(config["factors"]["category_weights"].values()) - 1.0) < 1e-12


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
    assert config["portfolio"]["buffer_count"] == 60
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
    assert second["portfolio"]["buffer_count"] == 60
    assert second["factors"]["category_weights"]["valuation"] == 0.25
    assert third["portfolio"]["holding_count"] == 30
    assert third["factors"]["category_weights"]["valuation"] == 0.25
