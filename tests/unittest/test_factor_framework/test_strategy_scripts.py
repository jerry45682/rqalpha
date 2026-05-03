from rqalpha_factor_framework.config import load_config


def test_strategy_scripts_import_smoke():
    assert load_config()["portfolio"]["holding_count"] == 30

    from rqalpha_factor_framework.strategies import multi_factor_strategy
    from rqalpha_factor_framework.reports.performance_report import export_result_pickle

    assert multi_factor_strategy.__name__.endswith("multi_factor_strategy")
    assert export_result_pickle.__name__ == "export_result_pickle"
