import pickle
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from rqalpha_factor_framework.config import load_config


def test_strategy_scripts_import_smoke():
    assert load_config()["portfolio"]["holding_count"] == 30

    from rqalpha_factor_framework.strategies import multi_factor_strategy
    from rqalpha_factor_framework.reports.performance_report import export_result_pickle

    assert multi_factor_strategy.__name__.endswith("multi_factor_strategy")
    assert export_result_pickle.__name__ == "export_result_pickle"


def test_resolve_stock_pool_prefers_configured_symbols(monkeypatch):
    from rqalpha_factor_framework.strategies import multi_factor_strategy

    monkeypatch.setattr(
        multi_factor_strategy,
        "index_components",
        lambda index: (_ for _ in ()).throw(AssertionError("index should not be used")),
    )

    config = {
        "stock_pool": {
            "index": "000300.XSHG",
            "symbols": ["000001.XSHE", "600000.XSHG"],
        }
    }

    assert multi_factor_strategy._resolve_stock_pool(config) == [
        "000001.XSHE",
        "600000.XSHG",
    ]


def test_rebalance_orders_targets_and_sells_positions_outside_targets(monkeypatch):
    from rqalpha_factor_framework.strategies import multi_factor_strategy

    dates = pd.date_range("2023-01-01", periods=131, freq="D")
    stocks = ["000001.XSHE", "000002.XSHE", "000003.XSHE"]

    def make_history(order_book_id):
        rank = stocks.index(order_book_id)
        base = 10 + rank
        close = np.linspace(base, base + 3 - rank, len(dates))
        frame = pd.DataFrame(
            {
                "datetime": dates,
                "open": close - 0.1,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": 1000000 + rank,
                "amount": 100000000 - rank * 1000000,
                "turn": 1.0 + rank * 0.1,
                "tradestatus": 1,
                "peTTM": 10 + rank,
                "pbMRQ": 1 + rank * 0.1,
                "psTTM": 2 + rank * 0.1,
                "isST": 0,
            }
        )
        return frame.to_records(index=False)

    orders = []
    monkeypatch.setattr(
        multi_factor_strategy,
        "history_bars",
        lambda order_book_id, bar_count, frequency, fields, skip_suspended=True, include_now=True, adjust_type="pre": make_history(
            order_book_id
        ),
        raising=False,
    )
    monkeypatch.setattr(
        multi_factor_strategy,
        "get_positions",
        lambda: [
            SimpleNamespace(order_book_id="000001.XSHE", quantity=100),
            SimpleNamespace(order_book_id="000003.XSHE", quantity=100),
            SimpleNamespace(order_book_id="000004.XSHE", quantity=100),
            SimpleNamespace(order_book_id="000005.XSHE", quantity=0),
        ],
        raising=False,
    )
    monkeypatch.setattr(
        multi_factor_strategy,
        "order_target_percent",
        lambda order_book_id, weight: orders.append((order_book_id, weight)),
        raising=False,
    )
    monkeypatch.setattr(
        multi_factor_strategy,
        "logger",
        SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
        ),
    )

    context = SimpleNamespace(
        factor_config={
            "stock_pool": {"index": "000300.XSHG", "symbols": stocks},
            "portfolio": {
                "holding_count": 1,
                "buffer_count": 1,
                "weighting": "equal",
            },
            "factors": {
                "category_weights": {
                    "valuation": 0.15,
                    "quality": 0.20,
                    "growth": 0.20,
                    "momentum": 0.15,
                    "reversal": 0.05,
                    "risk": 0.10,
                    "liquidity": 0.05,
                    "technical": 0.10,
                },
                "factor_weights": {},
            },
            "scoring": {
                "missing": "median",
                "winsorize_quantiles": [0.01, 0.99],
            },
            "filters": {
                "exclude_st": True,
                "min_listed_days": 180,
                "min_avg_amount_20": 1,
                "require_positive_pe_pb": True,
            },
        }
    )

    multi_factor_strategy.rebalance(context, bar_dict={})

    sells = {stock: weight for stock, weight in orders if weight == 0}
    buys = {stock: weight for stock, weight in orders if weight > 0}
    assert sells == {"000003.XSHE": 0, "000004.XSHE": 0}
    assert len(buys) == 1
    assert next(iter(buys.values())) == 1.0


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
