from rqalpha_factor_framework.backtest import run_backtest


def run_batch(config_paths):
    return [run_backtest.main(config_path) for config_path in config_paths]
