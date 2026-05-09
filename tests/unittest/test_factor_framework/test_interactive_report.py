import pickle

import pandas as pd


def _write_result(path, include_benchmark=True, include_trades=True):
    dates = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    result = {
        "portfolio": pd.DataFrame(
            {"unit_net_value": [1.0, 1.02, 1.05]},
            index=pd.Index(dates, name="date"),
        ),
        "summary": {
            "strategy_name": "demo",
            "total_returns": 0.05789,
            "sharpe": 1.23456,
        },
        "stock_positions": pd.DataFrame(
            {
                "order_book_id": ["600000.XSHG"],
                "symbol": ["浦发银行"],
                "quantity": [1000],
                "last_price": [11.0],
                "avg_price": [10.0],
                "market_value": [11000.0],
            },
            index=pd.Index(pd.to_datetime(["2025-01-06"]), name="date"),
        ),
    }
    if include_benchmark:
        result["benchmark_portfolio"] = pd.DataFrame(
            {"unit_net_value": [1.0, 1.01, 1.03]},
            index=pd.Index(dates, name="date"),
        )
    if include_trades:
        trade_dt = pd.to_datetime(
            [
                "2025-01-03 15:00:00",
                "2025-01-03 15:00:00",
                "2025-01-06 15:00:00",
            ]
        )
        result["trades"] = pd.DataFrame(
            {
                "datetime": trade_dt,
                "trading_datetime": trade_dt,
                "order_book_id": ["600000.XSHG", "000001.XSHE", "000001.XSHE"],
                "symbol": ["浦发银行", "平安银行", "平安银行"],
                "side": ["BUY", "BUY", "SELL"],
                "position_effect": ["OPEN", "OPEN", "CLOSE"],
                "last_quantity": [1000, 500, 500],
                "last_price": [10.0, 12.0, 13.0],
                "transaction_cost": [8.0, 6.0, 7.0],
            },
            index=pd.Index(trade_dt, name="datetime"),
        )
    else:
        result["trades"] = pd.DataFrame()
    with path.open("wb") as result_file:
        pickle.dump(result, result_file)


def test_generate_interactive_report_exports_returns_and_rebalance_events(tmp_path):
    from rqalpha_factor_framework.reports.interactive_report import (
        generate_interactive_report,
    )

    result_path = tmp_path / "result.pkl"
    _write_result(result_path)

    output_path = generate_interactive_report(result_path)

    assert output_path == tmp_path / "result_report.html"
    html = output_path.read_text(encoding="utf-8")
    assert "收益曲线" in html
    assert "benchmark" in html
    assert "2025-01-03" in html
    assert "600000.XSHG" in html
    assert "000001.XSHE" in html
    assert "14.00" in html
    assert "0.05789" not in html
    assert "1.23456" not in html


def test_generate_interactive_report_shows_returns_for_all_traded_symbols(tmp_path):
    from rqalpha_factor_framework.reports.interactive_report import (
        generate_interactive_report,
    )

    result_path = tmp_path / "result.pkl"
    _write_result(result_path)

    output_path = generate_interactive_report(result_path)

    html = output_path.read_text(encoding="utf-8")
    assert "交易股票收益率" in html
    assert "浦发银行" in html
    assert "平安银行" in html
    assert "9.92%" in html
    assert "8.12%" in html


def test_generate_interactive_report_handles_empty_trades(tmp_path):
    from rqalpha_factor_framework.reports.interactive_report import (
        generate_interactive_report,
    )

    result_path = tmp_path / "result.pkl"
    _write_result(result_path, include_trades=False)

    output_path = generate_interactive_report(result_path)

    html = output_path.read_text(encoding="utf-8")
    assert "无调仓记录" in html
    assert "strategy" in html


def test_generate_interactive_report_without_benchmark(tmp_path):
    from rqalpha_factor_framework.reports.interactive_report import (
        generate_interactive_report,
    )

    result_path = tmp_path / "result.pkl"
    _write_result(result_path, include_benchmark=False)

    output_path = generate_interactive_report(result_path)

    html = output_path.read_text(encoding="utf-8")
    assert "收益曲线" in html
    assert "benchmarkData" in html


def test_interactive_report_cli_uses_default_and_custom_output(tmp_path):
    from rqalpha_factor_framework.reports.interactive_report import main

    result_path = tmp_path / "result.pkl"
    custom_path = tmp_path / "custom.html"
    _write_result(result_path)

    assert main([str(result_path)]) == 0
    assert (tmp_path / "result_report.html").exists()

    assert main([str(result_path), "-o", str(custom_path)]) == 0
    assert custom_path.exists()
