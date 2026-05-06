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
            "symbols": ["600000.XSHG", "000001.XSHE", "000002.XSHE"],
        }
    }

    assert multi_factor_strategy._resolve_stock_pool(config) == [
        "600000.XSHG",
        "000001.XSHE",
        "000002.XSHE",
    ]


def test_history_fields_omit_unsupported_ps_ttm():
    from rqalpha_factor_framework.strategies import multi_factor_strategy

    assert "psTTM" not in multi_factor_strategy.HISTORY_FIELDS


def test_bars_to_frame_converts_numeric_datetime():
    from rqalpha_factor_framework.strategies import multi_factor_strategy

    bars = np.array(
        [(20230103, 10.0), (20230104000000, 11.0)],
        dtype=[("datetime", "i8"), ("close", "f8")],
    )

    frame = multi_factor_strategy._bars_to_frame(bars, "000001.XSHE")

    assert frame.loc[0, "date"] == pd.Timestamp("2023-01-03")
    assert frame.loc[1, "date"] == pd.Timestamp("2023-01-04")
    assert frame["order_book_id"].tolist() == ["000001.XSHE", "000001.XSHE"]


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
                "isST": 0,
            }
        )
        return frame.to_records(index=False)

    orders = []
    info_messages = []
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
            info=lambda message, *args, **kwargs: info_messages.append(str(message)),
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
            "risk": {
                "max_stock_weight": 1.0,
                "market_timing": {"enabled": False},
            },
        }
    )

    multi_factor_strategy.rebalance(context, bar_dict={})

    sells = {stock: weight for stock, weight in orders if weight == 0}
    buys = {stock: weight for stock, weight in orders if weight > 0}
    assert sells == {"000003.XSHE": 0, "000004.XSHE": 0}
    assert len(buys) == 1
    assert next(iter(buys.values())) == 1.0
    score_logs = [
        message
        for message in info_messages
        if message.startswith("target factor score:")
    ]
    assert score_logs
    assert "valuation=" in score_logs[0]
    assert "quality=" in score_logs[0]
    assert "growth=" in score_logs[0]
    assert "momentum=" in score_logs[0]


def test_rebalance_tolerates_empty_financial_data(monkeypatch):
    from rqalpha_factor_framework.strategies import multi_factor_strategy

    dates = pd.date_range("2023-01-01", periods=131, freq="D")
    stocks = ["000001.XSHE", "000002.XSHE"]

    def make_history(order_book_id):
        rank = stocks.index(order_book_id)
        close = np.linspace(10 + rank, 12 + rank, len(dates))
        frame = pd.DataFrame(
            {
                "datetime": dates,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 1000000,
                "amount": 100000000,
                "turn": 1.0,
                "tradestatus": 1,
                "peTTM": 10 + rank,
                "pbMRQ": 1 + rank,
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
    monkeypatch.setattr(multi_factor_strategy, "get_positions", lambda: [], raising=False)
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
        financial_data={},
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
            "risk": {
                "max_stock_weight": 1.0,
                "market_timing": {"enabled": False},
            },
        },
    )

    multi_factor_strategy.rebalance(context, bar_dict={})

    assert any(weight > 0 for _, weight in orders)


def test_rebalance_excludes_latest_suspended_stock(monkeypatch):
    from rqalpha_factor_framework.strategies import multi_factor_strategy

    dates = pd.date_range("2023-01-01", periods=131, freq="D")
    stocks = ["000001.XSHE"]

    def make_history(order_book_id):
        close = np.linspace(10.0, 12.0, len(dates))
        frame = pd.DataFrame(
            {
                "datetime": dates,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 1000000,
                "amount": 100000000,
                "turn": 1.0,
                "tradestatus": [1] * (len(dates) - 1) + [0],
                "peTTM": 10.0,
                "pbMRQ": 1.0,
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
    monkeypatch.setattr(multi_factor_strategy, "get_positions", lambda: [], raising=False)
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
        financial_data={},
        factor_config={
            "stock_pool": {"index": "000300.XSHG", "symbols": stocks},
            "portfolio": {
                "holding_count": 1,
                "buffer_count": 1,
                "weighting": "equal",
            },
            "factors": {
                "enabled_categories": [
                    "valuation",
                    "momentum",
                    "reversal",
                    "risk",
                    "liquidity",
                    "technical",
                ],
                "category_weights": {
                    "valuation": 0.25,
                    "momentum": 0.25,
                    "reversal": 0.10,
                    "risk": 0.15,
                    "liquidity": 0.10,
                    "technical": 0.15,
                },
                "factor_weights": {},
            },
            "scoring": {
                "missing": "median",
                "winsorize_quantiles": [0.01, 0.99],
            },
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_listed_days": 180,
                "min_avg_amount_20": 1,
                "require_positive_pe_pb": True,
            },
            "risk": {
                "max_stock_weight": 1.0,
                "market_timing": {"enabled": False},
            },
        },
    )

    multi_factor_strategy.rebalance(context, bar_dict={})

    assert not any(weight > 0 for _, weight in orders)


def test_rebalance_uses_only_enabled_factor_categories(monkeypatch):
    from rqalpha_factor_framework.strategies import multi_factor_strategy

    dates = pd.date_range("2023-01-01", periods=131, freq="D")
    stocks = ["000001.XSHE", "000002.XSHE"]
    captured = {}

    def make_history(order_book_id):
        rank = stocks.index(order_book_id)
        close = np.linspace(10 + rank, 12 + rank, len(dates))
        frame = pd.DataFrame(
            {
                "datetime": dates,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 1000000,
                "amount": 100000000,
                "turn": 1.0,
                "tradestatus": 1,
                "peTTM": 10 + rank,
                "pbMRQ": 1 + rank,
                "isST": 0,
            }
        )
        return frame.to_records(index=False)

    def capture_preprocess(raw, metadata, **kwargs):
        captured["preprocess_columns"] = list(raw.columns)
        return pd.DataFrame(1.0, index=raw.index, columns=raw.columns)

    def capture_scores(processed, metadata, category_weights, factor_weights=None):
        captured["score_columns"] = list(processed.columns)
        return pd.DataFrame(
            {
                "score": [2.0, 1.0],
                "valuation_score": [1.0, 0.5],
                "momentum_score": [1.0, 0.5],
            },
            index=processed.index,
        )

    orders = []
    info_messages = []
    monkeypatch.setattr(
        multi_factor_strategy,
        "history_bars",
        lambda order_book_id, bar_count, frequency, fields, skip_suspended=True, include_now=True, adjust_type="pre": make_history(
            order_book_id
        ),
        raising=False,
    )
    monkeypatch.setattr(multi_factor_strategy, "preprocess_factors", capture_preprocess)
    monkeypatch.setattr(multi_factor_strategy, "build_factor_scores", capture_scores)
    monkeypatch.setattr(multi_factor_strategy, "get_positions", lambda: [], raising=False)
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
            info=lambda message, *args, **kwargs: info_messages.append(str(message)),
            warning=lambda *args, **kwargs: None,
        ),
    )

    context = SimpleNamespace(
        financial_data={},
        factor_config={
            "stock_pool": {"index": "000300.XSHG", "symbols": stocks},
            "portfolio": {
                "holding_count": 1,
                "buffer_count": 1,
                "weighting": "equal",
            },
            "factors": {
                "enabled_categories": ["valuation", "momentum"],
                "category_weights": {
                    "valuation": 0.5,
                    "momentum": 0.5,
                },
                "factor_weights": {},
            },
            "scoring": {
                "missing": "median",
                "winsorize_quantiles": [0.01, 0.99],
            },
            "filters": {
                "exclude_st": True,
                "exclude_suspended": True,
                "min_listed_days": 180,
                "min_avg_amount_20": 1,
                "require_positive_pe_pb": True,
            },
            "risk": {
                "max_stock_weight": 1.0,
                "market_timing": {"enabled": False},
            },
        },
    )

    multi_factor_strategy.rebalance(context, bar_dict={})

    assert captured["preprocess_columns"]
    assert captured["score_columns"] == captured["preprocess_columns"]
    assert not {"roe", "roa", "gross_margin", "debt_to_asset"}.intersection(
        captured["preprocess_columns"]
    )
    assert not {
        "revenue_growth_yoy",
        "net_profit_growth_yoy",
        "operating_cashflow_growth_yoy",
    }.intersection(captured["preprocess_columns"])
    assert any(weight > 0 for _, weight in orders)
    score_logs = [
        message
        for message in info_messages
        if message.startswith("target factor score:")
    ]
    assert score_logs
    assert "valuation=" in score_logs[0]
    assert "momentum=" in score_logs[0]
    assert "quality=" not in score_logs[0]
    assert "growth=" not in score_logs[0]


def test_build_targets_applies_market_timing_exposure_and_stock_cap(monkeypatch):
    from rqalpha_factor_framework.strategies import multi_factor_strategy

    scored = pd.DataFrame(
        {"score": [2.0, 1.0]},
        index=["000001.XSHE", "000002.XSHE"],
    )

    monkeypatch.setattr(
        multi_factor_strategy,
        "history_bars",
        lambda order_book_id, bar_count, frequency, fields, skip_suspended=True, include_now=True, adjust_type="pre": pd.DataFrame(
            {"close": [100.0] * 129 + [50.0]}
        ),
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

    targets = multi_factor_strategy._build_targets(
        scored,
        current_positions=[],
        config={
            "portfolio": {
                "holding_count": 2,
                "buffer_count": 2,
                "weighting": "equal",
            },
            "risk": {
                "max_stock_weight": 0.2,
                "market_timing": {
                    "enabled": True,
                    "index": "000300.XSHG",
                    "ma120_exposure": 0.6,
                    "ma250_exposure": 0.3,
                    "full_exposure": 1.0,
                },
            },
        },
    )

    assert targets == {"000001.XSHE": 0.2, "000002.XSHE": 0.2}


def test_build_rqalpha_config_sets_factor_config_path():
    from rqalpha_factor_framework.backtest.run_backtest import build_rqalpha_config

    config = build_rqalpha_config()

    assert config["extra"]["context_vars"]["factor_config_path"]


def test_build_rqalpha_config_sets_configured_data_bundle_path(tmp_path):
    from rqalpha_factor_framework.backtest.run_backtest import build_rqalpha_config

    bundle_path = tmp_path / "bundle"
    bundle_path.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "backtest:\n"
        "  data_bundle_path: {}\n".format(bundle_path.as_posix()),
        encoding="utf-8",
    )

    config = build_rqalpha_config(config_path)

    assert config["base"]["data_bundle_path"] == str(bundle_path)


def test_build_rqalpha_config_uses_env_bundle_path_when_config_is_null(
    monkeypatch, tmp_path
):
    from rqalpha_factor_framework.backtest.run_backtest import build_rqalpha_config

    bundle_path = tmp_path / "bundle"
    bundle_path.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("backtest:\n  data_bundle_path:\n", encoding="utf-8")
    monkeypatch.setenv("RQALPHA_FACTOR_BUNDLE_PATH", str(bundle_path))
    monkeypatch.delenv("RQALPHA_DATA_BUNDLE_PATH", raising=False)

    config = build_rqalpha_config(config_path)

    assert config["base"]["data_bundle_path"] == str(bundle_path)


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
