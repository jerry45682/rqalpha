from copy import deepcopy
from pathlib import Path

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).with_name("multi_factor_config.yaml")


def _deep_merge(base, overrides):
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _read_yaml(path):
    with Path(path).open("r", encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)
    return data or {}


def _validate_config(config):
    category_weights = config.get("factors", {}).get("category_weights", {})
    if abs(sum(category_weights.values()) - 1.0) > 1e-12:
        raise ValueError("factor category weights must sum to 1")

    portfolio = config.get("portfolio", {})
    holding_count = portfolio.get("holding_count")
    buffer_count = portfolio.get("buffer_count")

    if holding_count is None or holding_count <= 0:
        raise ValueError("portfolio holding_count must be positive")
    if buffer_count is None or buffer_count < holding_count:
        raise ValueError("portfolio buffer_count must be greater than or equal to holding_count")


def load_config(path=None):
    config = _read_yaml(DEFAULT_CONFIG_PATH)
    if path is not None:
        config = _deep_merge(config, _read_yaml(path))
    _validate_config(config)
    return config
