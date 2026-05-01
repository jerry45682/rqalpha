from copy import deepcopy
from pathlib import Path

import yaml


DEFAULT_CONFIG = {
    "stock_pool": {
        "index": "000300.XSHG",
        "symbols": [],
    },
    "factors": {
        "source": "rqdatac",
        "weights": {
            "pe": 0.25,
            "pb": 0.25,
            "roe": 0.25,
            "momentum_60": 0.25,
        },
        "winsorize_quantiles": [0.05, 0.95],
    },
    "portfolio": {
        "size": 20,
    },
    "rebalance": {
        "frequency": "monthly",
        "tradingday": 1,
    },
}


def deep_merge(base, override):
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path=None):
    if path is None:
        path = Path(__file__).with_name("config.yml")
    path = Path(path)
    data = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    return deep_merge(DEFAULT_CONFIG, data)
