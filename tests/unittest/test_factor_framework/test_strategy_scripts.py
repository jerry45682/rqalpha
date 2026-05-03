import pickle
from unittest.mock import patch

import pandas as pd

from rqalpha_factor_framework.config import load_config


def test_strategy_scripts_import_smoke():
    assert load_config()["portfolio"]["holding_count"] == 30

    from rqalpha_factor_framework.strategies import multi_factor_strategy
    from rqalpha_factor_framework.reports.performance_report import export_result_pickle

    assert multi_factor_strategy.__name__.endswith("multi_factor_strategy")
    assert export_result_pickle.__name__ == "export_result_pickle"


def test_build_rqalpha_config_sets_factor_config_path():
    from rqalpha_factor_framework.backtest.run_backtest import build_rqalpha_config

    config = build_rqalpha_config()

    assert config["extra"]["context_vars"]["factor_config_path"]


def test_run_backtest_main_calls_rqalpha_run_with_strategy_contract():
    from rqalpha_factor_framework.backtest import run_backtest

    with patch.object(run_backtest.rqalpha, "run", return_value={"ok": True}) as run:
        result = run_backtest.main()

    assert result == {"ok": True}
    run.assert_called_once()
    config = run.call_args.args[0]
    assert config["base"]["start_date"] == "2023-01-03"
    assert config["base"]["end_date"] == "2023-04-28"
    assert config["base"]["frequency"] == "1d"
    assert config["base"]["accounts"] == {"stock": 1000000}
    assert config["extra"]["context_vars"]["factor_config_path"]
    assert config["mod"]["baostock"]["lib"] == "rqalpha.mod.rqalpha_mod_baostock"
    assert "source_code" in run.call_args.kwargs
    assert "def init" in run.call_args.kwargs["source_code"]


def test_export_result_pickle_exports_dataframe_as_result_csv(tmp_path):
    from rqalpha_factor_framework.reports.performance_report import export_result_pickle

    result_path = tmp_path / "result.pkl"
    with result_path.open("wb") as result_file:
        pickle.dump(pd.DataFrame({"value": [1, 2]}), result_file)

    exported = export_result_pickle(result_path)

    assert exported == [tmp_path / "result" / "result.csv"]
    assert exported[0].read_text(encoding="utf-8-sig").splitlines()[0] == ",value"


def test_export_result_pickle_exports_mapping_values_by_key(tmp_path):
    from rqalpha_factor_framework.reports.performance_report import export_result_pickle

    result_path = tmp_path / "result.pkl"
    payload = {
        "portfolio": pd.DataFrame({"value": [1]}),
        "ignored": object(),
    }
    with result_path.open("wb") as result_file:
        pickle.dump(payload, result_file)

    exported = export_result_pickle(result_path)

    assert exported == [tmp_path / "result" / "portfolio.csv"]
    assert exported[0].read_text(encoding="utf-8-sig").splitlines()[0] == ",value"
