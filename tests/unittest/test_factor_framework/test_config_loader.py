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
