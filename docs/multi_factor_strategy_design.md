# Multi-Factor Strategy Design

## Goal

Provide an extensible RQAlpha-compatible stock selection strategy that rebalances monthly by default, ranks a stock pool with PE, PB, ROE, and 60-day momentum, then holds the top-scoring names at equal weight.

## Scope

The framework lives under `rqalpha/examples/multi_factor_strategy/` so it can be used as an example without changing RQAlpha core behavior. It assumes RQData is available for index components and fundamentals in real backtests, and supports a YAML-configured stock list as a fallback for environments without RQData.

## Modules

- `config.py`: load YAML and merge defaults.
- `filters.py`: resolve the stock pool from an index, explicit symbols, or a passed API function.
- `factors.py`: fetch/calculate factor values, apply quantile winsorization, Z-score normalization, factor direction, and weighted scoring.
- `portfolio.py`: select the top N names and create equal target weights.
- `rebalancer.py`: translate target weights into sell and buy instructions, with logging.
- `strategy.py`: RQAlpha entry point using `init` and scheduled rebalancing.
- `run_backtest.py`: runnable example using `rqalpha.run_file`.

## Testing

Unit tests cover pure logic without requiring live RQData: config merging, winsorization, Z-score, factor direction, weighted scoring, top-N portfolio construction, and rebalance instruction generation.
