import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "multi_factor_config.yaml"
DEFAULT_RESULT_PATH = ROOT / "backtest" / "multi_factor_result.pkl"
STRATEGY_PATH = ROOT / "strategies" / "multi_factor_strategy.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import rqalpha  # noqa: E402
from rqalpha_factor_framework.config import load_config  # noqa: E402


def _resolve_path(path, default):
    if not path:
        return default
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def build_rqalpha_config(config_path=None):
    factor_config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    factor_config = load_config(factor_config_path)
    backtest_config = factor_config["backtest"]
    data_config = factor_config["data"]
    result_path = _resolve_path(backtest_config.get("result_path"), DEFAULT_RESULT_PATH)
    result_path.parent.mkdir(parents=True, exist_ok=True)

    base_config = {
        "start_date": backtest_config["start_date"],
        "end_date": backtest_config["end_date"],
        "frequency": backtest_config["frequency"],
        "strategy_file": str(STRATEGY_PATH),
        "accounts": {"stock": backtest_config["initial_cash"]},
    }
    data_bundle_path = backtest_config.get("data_bundle_path")
    if data_bundle_path:
        base_config["data_bundle_path"] = str(_resolve_path(data_bundle_path, None))

    return {
        "base": base_config,
        "extra": {
            "log_level": "info",
            "context_vars": {
                # 传入因子配置路径。
                "factor_config_path": str(factor_config_path),
            },
        },
        "mod": {
            "sys_analyser": {
                "enabled": True,
                "benchmark": backtest_config["benchmark"],
                "output_file": str(result_path),
                "plot": False,
            },
            "baostock": {
                "enabled": True,
                "lib": "rqalpha.mod.rqalpha_mod_baostock",
                "cache_dir": data_config["cache_dir"],
                "adjustflag": data_config["adjustflag"],
                "start_date": data_config["start_date"],
                "end_date": data_config["end_date"],
            },
        },
    }


def main(config_path=None):
    rqalpha_config = build_rqalpha_config(config_path)
    source_code = STRATEGY_PATH.read_text(encoding="utf-8")
    return rqalpha.run(rqalpha_config, source_code=source_code)


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_path", nargs="?")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(args.config_path)
