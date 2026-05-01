from collections.abc import Mapping
from copy import deepcopy
from numbers import Real
from pathlib import Path

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).with_name("multi_factor_config.yaml")


def _deep_merge(base, overrides):
    if not isinstance(base, Mapping) or not isinstance(overrides, Mapping):
        raise ValueError("config root must be a mapping")

    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _read_yaml(path):
    with Path(path).open("r", encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)
    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise ValueError("config root must be a mapping")
    return data


def _require_mapping(value, path):
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be a mapping")
    return value


def _require_int(value, path):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{path} must be an integer")
    converted = int(value)
    if converted != value:
        raise ValueError(f"{path} must be an integer")
    return converted


def _validate_config(config):
    config = _require_mapping(config, "config root")
    factors = _require_mapping(config.get("factors"), "factors")
    category_weights = _require_mapping(
        factors.get("category_weights"), "factors.category_weights"
    )
    for name, weight in category_weights.items():
        if isinstance(weight, bool) or not isinstance(weight, Real):
            raise ValueError(f"factors.category_weights.{name} must be numeric")

    if abs(sum(category_weights.values()) - 1.0) > 1e-12:
        raise ValueError("factors.category_weights category weights must sum to 1")

    portfolio = _require_mapping(config.get("portfolio"), "portfolio")
    holding_count = _require_int(
        portfolio.get("holding_count"), "portfolio.holding_count"
    )
    buffer_count = _require_int(
        portfolio.get("buffer_count"), "portfolio.buffer_count"
    )

    if holding_count <= 0:
        raise ValueError("portfolio.holding_count must be positive")
    if buffer_count < holding_count:
        raise ValueError(
            "portfolio.buffer_count must be greater than or equal to "
            "portfolio.holding_count"
        )


def load_config(path=None):
    config = _read_yaml(DEFAULT_CONFIG_PATH)
    if path is not None:
        config = _deep_merge(config, _read_yaml(path))
    _validate_config(config)
    return config
