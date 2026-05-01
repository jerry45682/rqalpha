# RQAlpha Baostock Factor Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a configurable RQAlpha + Baostock A-share multi-factor stock selection framework with offline cache, factor scoring, portfolio construction, and a runnable backtest example.

**Architecture:** Add a new `rqalpha_factor_framework` Python package at the repository root. The RQAlpha strategy remains a thin orchestration layer, while Baostock data access, factor calculation, scoring, filtering, portfolio construction, and reporting live in focused modules with unit tests.

**Tech Stack:** Python, pandas, numpy, PyYAML, Baostock, RQAlpha, pytest.

---

## File Structure

- Create: `rqalpha_factor_framework/__init__.py`
  - Package marker and framework version string.
- Create: `rqalpha_factor_framework/config/__init__.py`
  - Configuration package marker.
- Create: `rqalpha_factor_framework/config/multi_factor_config.yaml`
  - Default Chinese-commented YAML configuration for CSI 300 style backtests.
- Create: `rqalpha_factor_framework/config/loader.py`
  - Load and validate YAML config with defaults.
- Create: `rqalpha_factor_framework/data/cache.py`
  - CSV cache helpers for daily bars and financial factor tables.
- Create: `rqalpha_factor_framework/data/baostock_client.py`
  - Baostock login, code conversion, daily data download, and financial data download.
- Create: `rqalpha_factor_framework/data/factor_store.py`
  - Read cached market and financial data, align rows to rebalance dates, and expose data to factor modules.
- Create: `rqalpha_factor_framework/factors/base.py`
  - Factor metadata and utility types.
- Create: `rqalpha_factor_framework/factors/valuation.py`
- Create: `rqalpha_factor_framework/factors/quality.py`
- Create: `rqalpha_factor_framework/factors/growth.py`
- Create: `rqalpha_factor_framework/factors/momentum.py`
- Create: `rqalpha_factor_framework/factors/reversal.py`
- Create: `rqalpha_factor_framework/factors/risk.py`
- Create: `rqalpha_factor_framework/factors/liquidity.py`
- Create: `rqalpha_factor_framework/factors/technical.py`
  - One module per factor family, each returning a factor `DataFrame`.
- Create: `rqalpha_factor_framework/scoring/preprocess.py`
  - Missing-value handling, winsorization, z-score, and factor direction adjustment.
- Create: `rqalpha_factor_framework/scoring/neutralize.py`
  - No-op neutralization extension point for the first version.
- Create: `rqalpha_factor_framework/scoring/factor_score.py`
  - Category scores and final composite score.
- Create: `rqalpha_factor_framework/filters/stock_filter.py`
- Create: `rqalpha_factor_framework/filters/liquidity_filter.py`
- Create: `rqalpha_factor_framework/filters/trading_filter.py`
  - Stock, liquidity, and trading-state filters.
- Create: `rqalpha_factor_framework/portfolio/equal_weight.py`
- Create: `rqalpha_factor_framework/portfolio/score_weight.py`
- Create: `rqalpha_factor_framework/portfolio/constraints.py`
  - Equal weight, future score weight, position caps, and market timing exposure.
- Create: `rqalpha_factor_framework/strategies/multi_factor_strategy.py`
  - RQAlpha strategy entrypoint.
- Create: `rqalpha_factor_framework/backtest/run_backtest.py`
  - Runnable CSI 300 example backtest with offline-data preparation.
- Create: `rqalpha_factor_framework/backtest/batch_backtest.py`
  - Minimal batch runner for multiple config files.
- Create: `rqalpha_factor_framework/reports/performance_report.py`
  - Export RQAlpha result pickle content to CSV files.
- Modify: `pyproject.toml`
  - Include `rqalpha_factor_framework` package and YAML files.
- Test: `tests/unittest/test_factor_framework/test_config_loader.py`
- Test: `tests/unittest/test_factor_framework/test_factor_calculations.py`
- Test: `tests/unittest/test_factor_framework/test_scoring.py`
- Test: `tests/unittest/test_factor_framework/test_filters.py`
- Test: `tests/unittest/test_factor_framework/test_portfolio.py`
- Test: `tests/unittest/test_factor_framework/test_data_cache.py`

---

### Task 1: Package Skeleton And Config Loader

**Files:**
- Create: `rqalpha_factor_framework/__init__.py`
- Create: `rqalpha_factor_framework/config/__init__.py`
- Create: `rqalpha_factor_framework/config/multi_factor_config.yaml`
- Create: `rqalpha_factor_framework/config/loader.py`
- Modify: `pyproject.toml`
- Test: `tests/unittest/test_factor_framework/test_config_loader.py`

- [ ] **Step 1: Write failing config loader tests**

Create `tests/unittest/test_factor_framework/test_config_loader.py`:

```python
from pathlib import Path

import pytest

from rqalpha_factor_framework.config.loader import load_config


def test_load_default_config_has_required_sections():
    config = load_config()

    assert config["stock_pool"]["index"] == "000300.XSHG"
    assert config["rebalance"]["frequency"] == "monthly"
    assert config["portfolio"]["holding_count"] == 30
    assert config["portfolio"]["buffer_count"] == 60
    assert config["scoring"]["winsorize_quantiles"] == [0.01, 0.99]
    assert abs(sum(config["factors"]["category_weights"].values()) - 1.0) < 1e-12


def test_load_config_merges_user_overrides(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "portfolio:\n"
        "  holding_count: 5\n"
        "stock_pool:\n"
        "  symbols:\n"
        "    - 600000.XSHG\n",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config["portfolio"]["holding_count"] == 5
    assert config["portfolio"]["buffer_count"] == 60
    assert config["stock_pool"]["symbols"] == ["600000.XSHG"]


def test_load_config_rejects_invalid_category_weight_sum(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "factors:\n"
        "  category_weights:\n"
        "    valuation: 0.9\n"
        "    quality: 0.9\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="category weights"):
        load_config(path)
```

- [ ] **Step 2: Run config tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework\test_config_loader.py -q
```

Expected: FAIL because `rqalpha_factor_framework.config.loader` does not exist.

- [ ] **Step 3: Create package files and YAML config**

Create `rqalpha_factor_framework/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `rqalpha_factor_framework/config/__init__.py`:

```python
from .loader import load_config

__all__ = ["load_config"]
```

Create `rqalpha_factor_framework/config/multi_factor_config.yaml` with Chinese comments and these defaults:

```yaml
stock_pool:
  index: 000300.XSHG
  symbols: []

rebalance:
  frequency: monthly
  tradingday: 1

portfolio:
  holding_count: 30
  buffer_count: 60
  weighting: equal

factors:
  enabled_categories:
    - valuation
    - quality
    - growth
    - momentum
    - reversal
    - risk
    - liquidity
    - technical
  category_weights:
    valuation: 0.15
    quality: 0.20
    growth: 0.20
    momentum: 0.15
    reversal: 0.05
    risk: 0.10
    liquidity: 0.05
    technical: 0.10
  factor_weights: {}

scoring:
  missing: median
  winsorize_quantiles: [0.01, 0.99]
  standardize: zscore
  neutralize: none

filters:
  exclude_st: true
  exclude_suspended: true
  min_listed_days: 180
  min_avg_amount_20: 30000000
  require_positive_pe_pb: true
  skip_limit_up_buy: true
  skip_limit_down_sell: true

risk:
  max_stock_weight: 0.05
  max_industry_weight: 0.25
  market_timing:
    enabled: true
    index: 000300.XSHG
    ma120_exposure: 0.50
    ma250_exposure: 0.30
    full_exposure: 1.00

data:
  cache_dir: .rqalpha_factor_cache
  adjustflag: "2"
  start_date: "2022-01-01"
  end_date: null

backtest:
  start_date: "2023-01-03"
  end_date: "2023-04-28"
  frequency: 1d
  benchmark: 000300.XSHG
  initial_cash: 1000000
  result_path: rqalpha_factor_framework/backtest/multi_factor_result.pkl
```

- [ ] **Step 4: Implement config loader**

Create `rqalpha_factor_framework/config/loader.py`:

```python
from copy import deepcopy
from pathlib import Path

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).with_name("multi_factor_config.yaml")


def _deep_merge(base, override):
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _read_yaml(path):
    with Path(path).open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    return data or {}


def _validate_config(config):
    category_weights = config["factors"]["category_weights"]
    total = sum(float(value) for value in category_weights.values())
    if abs(total - 1.0) > 1e-8:
        raise ValueError("category weights must sum to 1.0, got {}".format(total))

    holding_count = int(config["portfolio"]["holding_count"])
    buffer_count = int(config["portfolio"]["buffer_count"])
    if holding_count <= 0:
        raise ValueError("holding_count must be positive")
    if buffer_count < holding_count:
        raise ValueError("buffer_count must be greater than or equal to holding_count")


def load_config(path=None):
    config = _read_yaml(DEFAULT_CONFIG_PATH)
    if path is not None:
        config = _deep_merge(config, _read_yaml(path))
    _validate_config(config)
    return config
```

- [ ] **Step 5: Include framework package in build config**

Modify `pyproject.toml` package discovery:

```toml
[tool.setuptools.packages.find]
include = ["rqalpha", "rqalpha.*", "rqalpha_factor_framework", "rqalpha_factor_framework.*"]
```

Add package data:

```toml
"rqalpha_factor_framework" = [
    "config/*.yaml",
]
```

- [ ] **Step 6: Run config tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework\test_config_loader.py -q
```

Expected: `3 passed`.

- [ ] **Step 7: Commit Task 1**

Run:

```powershell
git add pyproject.toml rqalpha_factor_framework tests\unittest\test_factor_framework\test_config_loader.py
git commit -m "feat: add factor framework config"
```

---

### Task 2: Data Cache And Baostock Client

**Files:**
- Create: `rqalpha_factor_framework/data/__init__.py`
- Create: `rqalpha_factor_framework/data/cache.py`
- Create: `rqalpha_factor_framework/data/baostock_client.py`
- Create: `rqalpha_factor_framework/data/factor_store.py`
- Test: `tests/unittest/test_factor_framework/test_data_cache.py`

- [ ] **Step 1: Write failing data cache tests**

Create `tests/unittest/test_factor_framework/test_data_cache.py`:

```python
import pandas as pd

from rqalpha_factor_framework.data.cache import CsvCache
from rqalpha_factor_framework.data.factor_store import FactorStore


def test_csv_cache_load_or_fetch_writes_and_reuses_data(tmp_path):
    cache = CsvCache(tmp_path)
    calls = []

    def fetcher():
        calls.append("fetch")
        return pd.DataFrame({"date": ["2023-01-03"], "close": [10.0]})

    first = cache.load_or_fetch("daily", "600000.XSHG", fetcher)
    second = cache.load_or_fetch("daily", "600000.XSHG", fetcher)

    assert calls == ["fetch"]
    assert first.equals(second)
    assert (tmp_path / "daily" / "600000_XSHG.csv").exists()


def test_factor_store_aligns_latest_financial_row_before_date(tmp_path):
    store = FactorStore(tmp_path)
    frame = pd.DataFrame(
        {
            "pub_date": ["2022-12-31", "2023-03-31"],
            "code": ["600000.XSHG", "600000.XSHG"],
            "roe": [0.1, 0.2],
        }
    )
    store.write_financial("600000.XSHG", "profit", frame)

    aligned = store.get_latest_financial(
        ["600000.XSHG"], "profit", "2023-02-01", ["roe"]
    )

    assert aligned.loc["600000.XSHG", "roe"] == 0.1
```

- [ ] **Step 2: Run data tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework\test_data_cache.py -q
```

Expected: FAIL because data modules do not exist.

- [ ] **Step 3: Implement CSV cache**

Create `rqalpha_factor_framework/data/cache.py`:

```python
from pathlib import Path

import pandas as pd


class CsvCache(object):
    def __init__(self, root):
        self.root = Path(root)

    @staticmethod
    def _safe_name(key):
        return str(key).replace(".", "_").replace("/", "_")

    def path_for(self, namespace, key):
        directory = self.root / namespace
        directory.mkdir(parents=True, exist_ok=True)
        return directory / "{}.csv".format(self._safe_name(key))

    def load_or_fetch(self, namespace, key, fetcher):
        path = self.path_for(namespace, key)
        if path.exists():
            return pd.read_csv(path)
        frame = fetcher()
        frame = pd.DataFrame() if frame is None else frame
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        return frame
```

- [ ] **Step 4: Implement Baostock client**

Create `rqalpha_factor_framework/data/baostock_client.py`:

```python
from contextlib import contextmanager


DAILY_FIELDS = [
    "date",
    "code",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turn",
    "tradestatus",
    "peTTM",
    "pbMRQ",
    "psTTM",
    "isST",
]


def rqalpha_to_baostock(order_book_id):
    code, exchange = order_book_id.split(".")
    if exchange == "XSHG":
        return "sh.{}".format(code)
    if exchange == "XSHE":
        return "sz.{}".format(code)
    raise ValueError("unsupported exchange: {}".format(order_book_id))


def baostock_to_rqalpha(code):
    exchange, symbol = code.split(".")
    if exchange == "sh":
        return "{}.XSHG".format(symbol)
    if exchange == "sz":
        return "{}.XSHE".format(symbol)
    raise ValueError("unsupported baostock code: {}".format(code))


@contextmanager
def baostock_session():
    try:
        import baostock as bs
    except ImportError:
        raise RuntimeError("baostock is not installed, run pip install baostock")
    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError("Baostock login failed: {}".format(login.error_msg))
    try:
        yield bs
    finally:
        bs.logout()


class BaostockClient(object):
    def __init__(self, adjustflag="2"):
        self.adjustflag = str(adjustflag)

    @staticmethod
    def _query_to_frame(result):
        rows = []
        while result.next():
            rows.append(result.get_row_data())
        import pandas as pd
        return pd.DataFrame(rows, columns=result.fields)

    def query_daily(self, order_book_id, start_date, end_date):
        with baostock_session() as bs:
            result = bs.query_history_k_data_plus(
                rqalpha_to_baostock(order_book_id),
                ",".join(DAILY_FIELDS),
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag=self.adjustflag,
            )
            if result.error_code != "0":
                raise RuntimeError("Baostock daily query failed: {}".format(result.error_msg))
            frame = self._query_to_frame(result)
        if "code" in frame.columns:
            frame["order_book_id"] = frame["code"].map(baostock_to_rqalpha)
        return frame
```

- [ ] **Step 5: Implement factor store**

Create `rqalpha_factor_framework/data/factor_store.py`:

```python
from pathlib import Path

import pandas as pd

from .cache import CsvCache


class FactorStore(object):
    def __init__(self, cache_dir, client=None):
        self.cache = CsvCache(cache_dir)
        self.client = client
        self.cache_dir = Path(cache_dir)

    def get_daily(self, order_book_id, start_date, end_date):
        if self.client is None:
            raise RuntimeError("Baostock client is required when daily cache is missing")
        return self.cache.load_or_fetch(
            "daily",
            order_book_id,
            lambda: self.client.query_daily(order_book_id, start_date, end_date),
        )

    def write_financial(self, order_book_id, table, frame):
        path = self.cache.path_for("financial_{}".format(table), order_book_id)
        frame.to_csv(path, index=False, encoding="utf-8-sig")

    def read_financial(self, order_book_id, table):
        path = self.cache.path_for("financial_{}".format(table), order_book_id)
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def get_latest_financial(self, order_book_ids, table, date, fields):
        rows = []
        target_date = pd.Timestamp(date)
        for order_book_id in order_book_ids:
            frame = self.read_financial(order_book_id, table)
            if frame.empty or "pub_date" not in frame.columns:
                rows.append({"order_book_id": order_book_id})
                continue
            frame = frame.copy()
            frame["pub_date"] = pd.to_datetime(frame["pub_date"])
            latest = frame[frame["pub_date"] <= target_date].sort_values("pub_date").tail(1)
            row = {"order_book_id": order_book_id}
            if not latest.empty:
                for field in fields:
                    row[field] = latest.iloc[0].get(field)
            rows.append(row)
        return pd.DataFrame(rows).set_index("order_book_id")
```

- [ ] **Step 6: Add package marker**

Create `rqalpha_factor_framework/data/__init__.py`:

```python
from .baostock_client import BaostockClient
from .factor_store import FactorStore

__all__ = ["BaostockClient", "FactorStore"]
```

- [ ] **Step 7: Run data cache tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework\test_data_cache.py -q
```

Expected: `2 passed`.

- [ ] **Step 8: Commit Task 2**

Run:

```powershell
git add rqalpha_factor_framework\data tests\unittest\test_factor_framework\test_data_cache.py
git commit -m "feat: add factor framework data cache"
```

---

### Task 3: Market Factor Calculations

**Files:**
- Create: `rqalpha_factor_framework/factors/__init__.py`
- Create: `rqalpha_factor_framework/factors/base.py`
- Create: `rqalpha_factor_framework/factors/valuation.py`
- Create: `rqalpha_factor_framework/factors/momentum.py`
- Create: `rqalpha_factor_framework/factors/reversal.py`
- Create: `rqalpha_factor_framework/factors/risk.py`
- Create: `rqalpha_factor_framework/factors/liquidity.py`
- Create: `rqalpha_factor_framework/factors/technical.py`
- Test: `tests/unittest/test_factor_framework/test_factor_calculations.py`

- [ ] **Step 1: Write failing market factor tests**

Create `tests/unittest/test_factor_framework/test_factor_calculations.py` with deterministic daily data:

```python
import numpy as np
import pandas as pd

from rqalpha_factor_framework.factors.liquidity import calculate_liquidity_factors
from rqalpha_factor_framework.factors.momentum import calculate_momentum_factors
from rqalpha_factor_framework.factors.reversal import calculate_reversal_factors
from rqalpha_factor_framework.factors.risk import calculate_risk_factors
from rqalpha_factor_framework.factors.technical import calculate_technical_factors
from rqalpha_factor_framework.factors.valuation import calculate_valuation_factors


def sample_daily(order_book_id="600000.XSHG", periods=130):
    dates = pd.date_range("2023-01-01", periods=periods, freq="D")
    close = pd.Series(np.linspace(10.0, 20.0, periods))
    frame = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "order_book_id": order_book_id,
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.arange(periods) + 1000,
            "amount": (np.arange(periods) + 1000) * close,
            "turn": np.linspace(1.0, 3.0, periods),
            "tradestatus": 1,
            "peTTM": 10.0,
            "pbMRQ": 1.5,
            "psTTM": 2.0,
            "isST": 0,
        }
    )
    return frame


def test_market_factor_modules_return_expected_columns():
    daily = {"600000.XSHG": sample_daily()}

    valuation = calculate_valuation_factors(daily)
    momentum = calculate_momentum_factors(daily)
    reversal = calculate_reversal_factors(daily)
    risk = calculate_risk_factors(daily)
    liquidity = calculate_liquidity_factors(daily)
    technical = calculate_technical_factors(daily)

    assert valuation.loc["600000.XSHG", "pe_ttm"] == 10.0
    assert momentum.loc["600000.XSHG", "return_20"] > 0
    assert reversal.loc["600000.XSHG", "rsi"] > 0
    assert risk.loc["600000.XSHG", "max_drawdown_120"] <= 0
    assert liquidity.loc["600000.XSHG", "avg_amount_20"] > 0
    assert "macd_hist" in technical.columns
    assert "obv_trend" in technical.columns
```

- [ ] **Step 2: Run factor tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework\test_factor_calculations.py -q
```

Expected: FAIL because factor modules do not exist.

- [ ] **Step 3: Implement factor metadata**

Create `rqalpha_factor_framework/factors/base.py`:

```python
from collections import namedtuple


FactorMeta = namedtuple("FactorMeta", ["name", "category", "direction"])

HIGHER_BETTER = "higher_better"
LOWER_BETTER = "lower_better"
MIDDLE_BETTER = "middle_better"


FACTOR_METADATA = {
    "pe_ttm": FactorMeta("pe_ttm", "valuation", LOWER_BETTER),
    "pb": FactorMeta("pb", "valuation", LOWER_BETTER),
    "ps_ttm": FactorMeta("ps_ttm", "valuation", LOWER_BETTER),
    "roe": FactorMeta("roe", "quality", HIGHER_BETTER),
    "roa": FactorMeta("roa", "quality", HIGHER_BETTER),
    "gross_margin": FactorMeta("gross_margin", "quality", HIGHER_BETTER),
    "debt_to_asset": FactorMeta("debt_to_asset", "quality", LOWER_BETTER),
    "revenue_growth_yoy": FactorMeta("revenue_growth_yoy", "growth", HIGHER_BETTER),
    "net_profit_growth_yoy": FactorMeta("net_profit_growth_yoy", "growth", HIGHER_BETTER),
    "operating_cashflow_growth_yoy": FactorMeta("operating_cashflow_growth_yoy", "growth", HIGHER_BETTER),
    "return_20": FactorMeta("return_20", "momentum", HIGHER_BETTER),
    "return_60": FactorMeta("return_60", "momentum", HIGHER_BETTER),
    "return_120": FactorMeta("return_120", "momentum", HIGHER_BETTER),
    "price_ma60_strength": FactorMeta("price_ma60_strength", "momentum", HIGHER_BETTER),
    "return_5": FactorMeta("return_5", "reversal", LOWER_BETTER),
    "rsi": FactorMeta("rsi", "reversal", LOWER_BETTER),
    "volatility_60": FactorMeta("volatility_60", "risk", LOWER_BETTER),
    "max_drawdown_120": FactorMeta("max_drawdown_120", "risk", LOWER_BETTER),
    "avg_amount_20": FactorMeta("avg_amount_20", "liquidity", HIGHER_BETTER),
    "avg_turnover_20": FactorMeta("avg_turnover_20", "liquidity", MIDDLE_BETTER),
    "macd_hist": FactorMeta("macd_hist", "technical", HIGHER_BETTER),
    "obv_trend": FactorMeta("obv_trend", "technical", HIGHER_BETTER),
}
```

- [ ] **Step 4: Implement market factor modules**

Use this shared row pattern in each module:

```python
import numpy as np
import pandas as pd
```

Create `valuation.py`:

```python
import pandas as pd


def calculate_valuation_factors(daily_data):
    rows = []
    for order_book_id, frame in daily_data.items():
        latest = frame.sort_values("date").tail(1)
        row = {"order_book_id": order_book_id}
        if not latest.empty:
            latest_row = latest.iloc[0]
            row["pe_ttm"] = latest_row.get("peTTM")
            row["pb"] = latest_row.get("pbMRQ")
            row["ps_ttm"] = latest_row.get("psTTM")
        rows.append(row)
    return pd.DataFrame(rows).set_index("order_book_id")
```

Create `momentum.py`:

```python
import numpy as np
import pandas as pd


def _return(close, window):
    if len(close) < window + 1 or close.iloc[-window - 1] == 0:
        return np.nan
    return close.iloc[-1] / close.iloc[-window - 1] - 1.0


def calculate_momentum_factors(daily_data):
    rows = []
    for order_book_id, frame in daily_data.items():
        close = pd.to_numeric(frame.sort_values("date")["close"], errors="coerce").dropna()
        ma60 = close.tail(60).mean() if len(close) >= 60 else np.nan
        rows.append(
            {
                "order_book_id": order_book_id,
                "return_20": _return(close, 20),
                "return_60": _return(close, 60),
                "return_120": _return(close, 120),
                "price_ma60_strength": close.iloc[-1] / ma60 - 1.0 if len(close) and ma60 else np.nan,
            }
        )
    return pd.DataFrame(rows).set_index("order_book_id")
```

Create `reversal.py`, `risk.py`, `liquidity.py`, and `technical.py` with RSI, volatility, max drawdown, average amount/turnover, MACD histogram, and OBV trend using pandas rolling calculations.

- [ ] **Step 5: Export factor functions**

Create `rqalpha_factor_framework/factors/__init__.py`:

```python
from .base import FACTOR_METADATA

__all__ = ["FACTOR_METADATA"]
```

- [ ] **Step 6: Run market factor tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework\test_factor_calculations.py -q
```

Expected: `1 passed`.

- [ ] **Step 7: Commit Task 3**

Run:

```powershell
git add rqalpha_factor_framework\factors tests\unittest\test_factor_framework\test_factor_calculations.py
git commit -m "feat: add market factor calculations"
```

---

### Task 4: Financial Factor Calculations

**Files:**
- Create: `rqalpha_factor_framework/factors/quality.py`
- Create: `rqalpha_factor_framework/factors/growth.py`
- Modify: `rqalpha_factor_framework/data/baostock_client.py`
- Modify: `tests/unittest/test_factor_framework/test_factor_calculations.py`

- [ ] **Step 1: Add failing financial factor tests**

Append to `test_factor_calculations.py`:

```python
from rqalpha_factor_framework.factors.growth import calculate_growth_factors
from rqalpha_factor_framework.factors.quality import calculate_quality_factors


def test_financial_factor_modules_return_expected_columns():
    financial = {
        "600000.XSHG": {
            "profit": pd.DataFrame(
                [{"roe": 0.12, "roa": 0.03, "gross_margin": 0.25}]
            ),
            "balance": pd.DataFrame(
                [{"debt_to_asset": 0.55}]
            ),
            "growth": pd.DataFrame(
                [{
                    "revenue_growth_yoy": 0.10,
                    "net_profit_growth_yoy": 0.08,
                    "operating_cashflow_growth_yoy": 0.05,
                }]
            ),
        }
    }

    quality = calculate_quality_factors(financial)
    growth = calculate_growth_factors(financial)

    assert quality.loc["600000.XSHG", "roe"] == 0.12
    assert quality.loc["600000.XSHG", "debt_to_asset"] == 0.55
    assert growth.loc["600000.XSHG", "net_profit_growth_yoy"] == 0.08
```

- [ ] **Step 2: Run financial factor tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework\test_factor_calculations.py -q
```

Expected: FAIL because `quality.py` and `growth.py` do not exist.

- [ ] **Step 3: Implement quality and growth factor modules**

Create `quality.py`:

```python
import pandas as pd


def _latest_value(frame, field):
    if frame is None or frame.empty:
        return None
    return frame.tail(1).iloc[0].get(field)


def calculate_quality_factors(financial_data):
    rows = []
    for order_book_id, tables in financial_data.items():
        rows.append(
            {
                "order_book_id": order_book_id,
                "roe": _latest_value(tables.get("profit"), "roe"),
                "roa": _latest_value(tables.get("profit"), "roa"),
                "gross_margin": _latest_value(tables.get("profit"), "gross_margin"),
                "debt_to_asset": _latest_value(tables.get("balance"), "debt_to_asset"),
            }
        )
    return pd.DataFrame(rows).set_index("order_book_id")
```

Create `growth.py`:

```python
import pandas as pd


def _latest_value(frame, field):
    if frame is None or frame.empty:
        return None
    return frame.tail(1).iloc[0].get(field)


def calculate_growth_factors(financial_data):
    rows = []
    for order_book_id, tables in financial_data.items():
        growth = tables.get("growth")
        rows.append(
            {
                "order_book_id": order_book_id,
                "revenue_growth_yoy": _latest_value(growth, "revenue_growth_yoy"),
                "net_profit_growth_yoy": _latest_value(growth, "net_profit_growth_yoy"),
                "operating_cashflow_growth_yoy": _latest_value(growth, "operating_cashflow_growth_yoy"),
            }
        )
    return pd.DataFrame(rows).set_index("order_book_id")
```

- [ ] **Step 4: Add Baostock financial query methods**

Extend `BaostockClient` with methods that call Baostock financial APIs and normalize columns to the framework names:

```python
    def query_profit_data(self, order_book_id, year, quarter):
        with baostock_session() as bs:
            result = bs.query_profit_data(
                code=rqalpha_to_baostock(order_book_id),
                year=int(year),
                quarter=int(quarter),
            )
            if result.error_code != "0":
                raise RuntimeError("Baostock profit query failed: {}".format(result.error_msg))
            return self._query_to_frame(result)

    def query_balance_data(self, order_book_id, year, quarter):
        with baostock_session() as bs:
            result = bs.query_balance_data(
                code=rqalpha_to_baostock(order_book_id),
                year=int(year),
                quarter=int(quarter),
            )
            if result.error_code != "0":
                raise RuntimeError("Baostock balance query failed: {}".format(result.error_msg))
            return self._query_to_frame(result)

    def query_growth_data(self, order_book_id, year, quarter):
        with baostock_session() as bs:
            result = bs.query_growth_data(
                code=rqalpha_to_baostock(order_book_id),
                year=int(year),
                quarter=int(quarter),
            )
            if result.error_code != "0":
                raise RuntimeError("Baostock growth query failed: {}".format(result.error_msg))
            return self._query_to_frame(result)
```

- [ ] **Step 5: Run financial factor tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework\test_factor_calculations.py -q
```

Expected: all factor tests pass.

- [ ] **Step 6: Commit Task 4**

Run:

```powershell
git add rqalpha_factor_framework\factors rqalpha_factor_framework\data tests\unittest\test_factor_framework\test_factor_calculations.py
git commit -m "feat: add financial factor calculations"
```

---

### Task 5: Scoring Pipeline

**Files:**
- Create: `rqalpha_factor_framework/scoring/__init__.py`
- Create: `rqalpha_factor_framework/scoring/preprocess.py`
- Create: `rqalpha_factor_framework/scoring/neutralize.py`
- Create: `rqalpha_factor_framework/scoring/factor_score.py`
- Test: `tests/unittest/test_factor_framework/test_scoring.py`

- [ ] **Step 1: Write failing scoring tests**

Create `tests/unittest/test_factor_framework/test_scoring.py`:

```python
import pandas as pd

from rqalpha_factor_framework.factors.base import FACTOR_METADATA
from rqalpha_factor_framework.scoring.factor_score import build_factor_scores
from rqalpha_factor_framework.scoring.preprocess import preprocess_factors


def test_preprocess_factors_fills_winsorizes_standardizes_and_flips_direction():
    raw = pd.DataFrame(
        {
            "pe_ttm": [5.0, 10.0, 1000.0, None],
            "return_20": [0.01, 0.02, 0.03, 0.04],
        },
        index=["a", "b", "c", "d"],
    )

    processed = preprocess_factors(
        raw,
        FACTOR_METADATA,
        winsorize_quantiles=(0.01, 0.99),
        missing="median",
    )

    assert processed.notna().all().all()
    assert processed.loc["a", "pe_ttm"] > processed.loc["c", "pe_ttm"]
    assert abs(processed["return_20"].mean()) < 1e-12


def test_build_factor_scores_calculates_category_and_total_scores():
    processed = pd.DataFrame(
        {
            "pe_ttm": [1.0, -1.0],
            "pb": [1.0, -1.0],
            "return_20": [-1.0, 1.0],
        },
        index=["a", "b"],
    )
    weights = {"valuation": 0.5, "momentum": 0.5}

    scored = build_factor_scores(processed, FACTOR_METADATA, weights)

    assert "valuation_score" in scored.columns
    assert "momentum_score" in scored.columns
    assert "score" in scored.columns
```

- [ ] **Step 2: Run scoring tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework\test_scoring.py -q
```

Expected: FAIL because scoring modules do not exist.

- [ ] **Step 3: Implement preprocess**

Create `rqalpha_factor_framework/scoring/preprocess.py`:

```python
import numpy as np
import pandas as pd

from rqalpha_factor_framework.factors.base import LOWER_BETTER, MIDDLE_BETTER


def winsorize_quantile(series, lower, upper):
    series = pd.to_numeric(series, errors="coerce")
    clean = series.dropna()
    if clean.empty:
        return series
    return series.clip(clean.quantile(lower), clean.quantile(upper))


def zscore(series):
    series = pd.to_numeric(series, errors="coerce")
    std = series.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def _fill_missing(frame, method):
    if method == "median":
        return frame.apply(lambda col: col.fillna(col.median()), axis=0)
    if method == "zero":
        return frame.fillna(0)
    raise ValueError("unsupported missing method: {}".format(method))


def preprocess_factors(raw_factors, metadata, winsorize_quantiles=(0.01, 0.99), missing="median"):
    lower, upper = winsorize_quantiles
    numeric = raw_factors.apply(pd.to_numeric, errors="coerce")
    filled = _fill_missing(numeric, missing)
    result = pd.DataFrame(index=filled.index)
    for factor_name in filled.columns:
        normalized = zscore(winsorize_quantile(filled[factor_name], lower, upper))
        meta = metadata.get(factor_name)
        if meta is not None and meta.direction == LOWER_BETTER:
            normalized = -normalized
        elif meta is not None and meta.direction == MIDDLE_BETTER:
            normalized = -zscore((filled[factor_name] - filled[factor_name].median()).abs())
        result[factor_name] = normalized.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return result
```

- [ ] **Step 4: Implement scoring**

Create `rqalpha_factor_framework/scoring/factor_score.py`:

```python
import pandas as pd


def build_factor_scores(processed_factors, metadata, category_weights, factor_weights=None):
    factor_weights = factor_weights or {}
    result = processed_factors.copy()
    categories = sorted(set(meta.category for meta in metadata.values()))
    category_score_columns = []

    for category in categories:
        factor_names = [
            name for name, meta in metadata.items()
            if meta.category == category and name in processed_factors.columns
        ]
        if not factor_names:
            continue
        weights = factor_weights.get(category, {})
        if weights:
            total = sum(float(weights.get(name, 0.0)) for name in factor_names)
            if total == 0:
                score = processed_factors[factor_names].mean(axis=1)
            else:
                score = sum(
                    processed_factors[name] * float(weights.get(name, 0.0)) / total
                    for name in factor_names
                )
        else:
            score = processed_factors[factor_names].mean(axis=1)
        column = "{}_score".format(category)
        result[column] = score
        category_score_columns.append(column)

    result["score"] = 0.0
    for column in category_score_columns:
        category = column[:-6]
        result["score"] = result["score"] + result[column] * float(category_weights.get(category, 0.0))
    return result.sort_values("score", ascending=False)
```

- [ ] **Step 5: Add neutralization no-op and package marker**

Create `neutralize.py`:

```python
def neutralize_factors(frame, method="none", **kwargs):
    if method in (None, "none"):
        return frame
    raise ValueError("unsupported neutralization method: {}".format(method))
```

Create `scoring/__init__.py`:

```python
from .factor_score import build_factor_scores
from .preprocess import preprocess_factors

__all__ = ["build_factor_scores", "preprocess_factors"]
```

- [ ] **Step 6: Run scoring tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework\test_scoring.py -q
```

Expected: `2 passed`.

- [ ] **Step 7: Commit Task 5**

Run:

```powershell
git add rqalpha_factor_framework\scoring tests\unittest\test_factor_framework\test_scoring.py
git commit -m "feat: add factor scoring pipeline"
```

---

### Task 6: Filters And Portfolio Construction

**Files:**
- Create: `rqalpha_factor_framework/filters/__init__.py`
- Create: `rqalpha_factor_framework/filters/stock_filter.py`
- Create: `rqalpha_factor_framework/filters/liquidity_filter.py`
- Create: `rqalpha_factor_framework/filters/trading_filter.py`
- Create: `rqalpha_factor_framework/portfolio/__init__.py`
- Create: `rqalpha_factor_framework/portfolio/equal_weight.py`
- Create: `rqalpha_factor_framework/portfolio/score_weight.py`
- Create: `rqalpha_factor_framework/portfolio/constraints.py`
- Test: `tests/unittest/test_factor_framework/test_filters.py`
- Test: `tests/unittest/test_factor_framework/test_portfolio.py`

- [ ] **Step 1: Write failing filter tests**

Create `tests/unittest/test_factor_framework/test_filters.py`:

```python
import pandas as pd

from rqalpha_factor_framework.filters.liquidity_filter import filter_by_avg_amount
from rqalpha_factor_framework.filters.stock_filter import filter_stocks
from rqalpha_factor_framework.filters.trading_filter import can_buy, can_sell


def test_stock_filter_removes_st_invalid_valuation_and_recent_listing():
    frame = pd.DataFrame(
        {
            "is_st": [0, 1, 0],
            "listed_days": [200, 200, 10],
            "pe_ttm": [10.0, 10.0, -1.0],
            "pb": [1.0, 1.0, 1.0],
        },
        index=["a", "b", "c"],
    )

    assert filter_stocks(frame, min_listed_days=180).index.tolist() == ["a"]


def test_liquidity_filter_removes_low_amount():
    frame = pd.DataFrame({"avg_amount_20": [50000000, 1000000]}, index=["a", "b"])

    assert filter_by_avg_amount(frame, 30000000).index.tolist() == ["a"]


def test_trading_filter_handles_limit_prices():
    assert can_buy(last_price=10.0, limit_up=10.1)
    assert not can_buy(last_price=10.1, limit_up=10.1)
    assert can_sell(last_price=10.0, limit_down=9.9)
    assert not can_sell(last_price=9.9, limit_down=9.9)
```

- [ ] **Step 2: Write failing portfolio tests**

Create `tests/unittest/test_factor_framework/test_portfolio.py`:

```python
import pandas as pd

from rqalpha_factor_framework.portfolio.constraints import apply_stock_weight_cap, market_timing_exposure
from rqalpha_factor_framework.portfolio.equal_weight import build_equal_weight_targets
from rqalpha_factor_framework.portfolio.score_weight import build_score_weight_targets


def test_equal_weight_targets_use_buffer_for_existing_positions():
    scored = pd.DataFrame({"score": [5, 4, 3, 2, 1]}, index=["a", "b", "c", "d", "e"])

    targets = build_equal_weight_targets(scored, ["d"], holding_count=2, buffer_count=4, total_exposure=1.0)

    assert "d" in targets
    assert len(targets) == 2
    assert abs(sum(targets.values()) - 1.0) < 1e-12


def test_stock_weight_cap_redistributes_excess_to_cash():
    weights = {"a": 0.8, "b": 0.2}

    capped = apply_stock_weight_cap(weights, 0.5)

    assert capped["a"] == 0.5
    assert capped["b"] == 0.2


def test_score_weight_targets_sum_to_exposure():
    scored = pd.DataFrame({"score": [3.0, 1.0]}, index=["a", "b"])

    weights = build_score_weight_targets(scored, holding_count=2, total_exposure=0.5)

    assert abs(sum(weights.values()) - 0.5) < 1e-12
    assert weights["a"] > weights["b"]


def test_market_timing_exposure_uses_moving_averages():
    prices = pd.Series([10.0] * 250)
    assert market_timing_exposure(prices, 1.0, 0.5, 0.3) == 1.0
    weak = pd.Series([10.0] * 249 + [5.0])
    assert market_timing_exposure(weak, 1.0, 0.5, 0.3) in (0.5, 0.3)
```

- [ ] **Step 3: Run filter and portfolio tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework\test_filters.py tests\unittest\test_factor_framework\test_portfolio.py -q
```

Expected: FAIL because filter and portfolio modules do not exist.

- [ ] **Step 4: Implement filters**

Implement:

```python
def filter_stocks(frame, min_listed_days=180, require_positive_pe_pb=True, exclude_st=True):
    result = frame.copy()
    if exclude_st and "is_st" in result.columns:
        result = result[result["is_st"].fillna(0).astype(int) == 0]
    if "listed_days" in result.columns:
        result = result[result["listed_days"].fillna(0) >= min_listed_days]
    if require_positive_pe_pb:
        result = result[(result["pe_ttm"] > 0) & (result["pb"] > 0)]
    return result
```

Implement liquidity and trading helpers:

```python
def filter_by_avg_amount(frame, min_avg_amount):
    return frame[frame["avg_amount_20"].fillna(0) >= float(min_avg_amount)]


def can_buy(last_price, limit_up):
    return float(last_price) < float(limit_up)


def can_sell(last_price, limit_down):
    return float(last_price) > float(limit_down)
```

- [ ] **Step 5: Implement portfolio builders and constraints**

Implement equal weight:

```python
def build_equal_weight_targets(scored, current_positions, holding_count, buffer_count, total_exposure=1.0):
    ranked = list(scored.sort_values("score", ascending=False).index)
    buy_zone = ranked[:holding_count]
    hold_zone = set(ranked[:buffer_count])
    kept = [stock for stock in current_positions if stock in hold_zone]
    targets = []
    for stock in kept + buy_zone:
        if stock not in targets:
            targets.append(stock)
        if len(targets) >= holding_count:
            break
    weight = float(total_exposure) / len(targets) if targets else 0.0
    return {stock: weight for stock in targets}
```

Implement score weight and constraints:

```python
def build_score_weight_targets(scored, holding_count, total_exposure=1.0):
    selected = scored.sort_values("score", ascending=False).head(holding_count)
    positive = selected["score"] - selected["score"].min() + 1e-6
    total = positive.sum()
    return {stock: float(value / total * total_exposure) for stock, value in positive.items()}


def apply_stock_weight_cap(weights, max_weight):
    return {stock: min(float(weight), float(max_weight)) for stock, weight in weights.items()}


def market_timing_exposure(index_close, full_exposure, ma120_exposure, ma250_exposure):
    close = index_close.dropna()
    if len(close) < 120:
        return full_exposure
    latest = close.iloc[-1]
    ma120 = close.tail(120).mean()
    if len(close) >= 250 and latest < close.tail(250).mean():
        return ma250_exposure
    if latest < ma120:
        return ma120_exposure
    return full_exposure
```

- [ ] **Step 6: Run filter and portfolio tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework\test_filters.py tests\unittest\test_factor_framework\test_portfolio.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 6**

Run:

```powershell
git add rqalpha_factor_framework\filters rqalpha_factor_framework\portfolio tests\unittest\test_factor_framework\test_filters.py tests\unittest\test_factor_framework\test_portfolio.py
git commit -m "feat: add filters and portfolio construction"
```

---

### Task 7: Strategy Orchestration And Backtest Scripts

**Files:**
- Create: `rqalpha_factor_framework/strategies/__init__.py`
- Create: `rqalpha_factor_framework/strategies/multi_factor_strategy.py`
- Create: `rqalpha_factor_framework/backtest/__init__.py`
- Create: `rqalpha_factor_framework/backtest/run_backtest.py`
- Create: `rqalpha_factor_framework/backtest/batch_backtest.py`
- Create: `rqalpha_factor_framework/reports/__init__.py`
- Create: `rqalpha_factor_framework/reports/performance_report.py`

- [ ] **Step 1: Create strategy orchestration module**

Implement `multi_factor_strategy.py` with RQAlpha hooks:

```python
from rqalpha.apis import get_positions, history_bars, index_components, logger, order_target_percent

from rqalpha_factor_framework.config import load_config
from rqalpha_factor_framework.factors.base import FACTOR_METADATA
from rqalpha_factor_framework.portfolio.equal_weight import build_equal_weight_targets
from rqalpha_factor_framework.scoring.factor_score import build_factor_scores
from rqalpha_factor_framework.scoring.preprocess import preprocess_factors


def init(context):
    from rqalpha.api import market_open, scheduler

    context.factor_config = load_config(getattr(context, "factor_config_path", None))
    scheduler.run_monthly(
        rebalance,
        tradingday=int(context.factor_config["rebalance"]["tradingday"]),
        time_rule=market_open(minute=1),
    )
    logger.info("factor framework initialized")


def _resolve_stock_pool(config):
    symbols = config["stock_pool"].get("symbols") or []
    if symbols:
        return list(symbols)
    return list(index_components(config["stock_pool"].get("index", "000300.XSHG")))


def rebalance(context, bar_dict):
    config = context.factor_config
    stock_pool = _resolve_stock_pool(config)
    logger.info("rebalance stock pool size: {}".format(len(stock_pool)))
    logger.info("factor framework first version expects backtest runner to prepare factors")


def handle_bar(context, bar_dict):
    pass
```

Then extend this file during Task 8 integration so it computes factors, filters, scores, and orders.

- [ ] **Step 2: Create run_backtest script**

Implement `run_backtest.py` so it can be executed directly:

```python
from pathlib import Path

from rqalpha import run

from rqalpha_factor_framework.config import load_config


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "multi_factor_config.yaml"


def main(config_path=None):
    config = load_config(config_path or DEFAULT_CONFIG)
    result_path = ROOT / "backtest" / "multi_factor_result.pkl"
    run(
        {
            "base": {
                "start_date": config["backtest"]["start_date"],
                "end_date": config["backtest"]["end_date"],
                "frequency": config["backtest"]["frequency"],
                "benchmark": config["backtest"]["benchmark"],
                "accounts": {"stock": float(config["backtest"]["initial_cash"])},
            },
            "extra": {"log_level": "info"},
            "mod": {
                "sys_analyser": {
                    "enabled": True,
                    "output_file": str(result_path),
                },
                "baostock": {
                    "enabled": True,
                    "lib": "rqalpha.mod.rqalpha_mod_baostock",
                    "cache_dir": config["data"]["cache_dir"],
                    "adjustflag": config["data"]["adjustflag"],
                    "start_date": config["data"]["start_date"],
                    "end_date": config["data"]["end_date"],
                },
            },
            "strategy": {
                "source_code": (ROOT / "strategies" / "multi_factor_strategy.py").read_text(encoding="utf-8"),
            },
        }
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create report exporter**

Implement `performance_report.py`:

```python
from pathlib import Path

import pandas as pd


def export_result_pickle(path, output_dir=None):
    path = Path(path)
    output_dir = Path(output_dir or path.with_suffix(""))
    output_dir.mkdir(parents=True, exist_ok=True)
    result = pd.read_pickle(path)
    exported = []
    for key, value in result.items():
        if hasattr(value, "to_csv"):
            target = output_dir / "{}.csv".format(key)
            value.to_csv(target, encoding="utf-8-sig")
            exported.append(target)
    return exported
```

- [ ] **Step 4: Add batch runner**

Implement `batch_backtest.py`:

```python
from pathlib import Path

from .run_backtest import main


def run_batch(config_paths):
    results = []
    for config_path in config_paths:
        main(Path(config_path))
        results.append(config_path)
    return results
```

- [ ] **Step 5: Run import smoke test**

Run:

```powershell
.\.venv\Scripts\python.exe - <<'PY'
from rqalpha_factor_framework.config import load_config
from rqalpha_factor_framework.strategies import multi_factor_strategy
from rqalpha_factor_framework.reports.performance_report import export_result_pickle
print(load_config()["portfolio"]["holding_count"])
print(multi_factor_strategy.__name__)
print(export_result_pickle.__name__)
PY
```

Expected output contains:

```text
30
rqalpha_factor_framework.strategies.multi_factor_strategy
export_result_pickle
```

- [ ] **Step 6: Commit Task 7**

Run:

```powershell
git add rqalpha_factor_framework\strategies rqalpha_factor_framework\backtest rqalpha_factor_framework\reports
git commit -m "feat: add factor framework strategy and backtest scripts"
```

---

### Task 8: End-To-End Strategy Integration

**Files:**
- Modify: `rqalpha_factor_framework/strategies/multi_factor_strategy.py`
- Modify: `rqalpha_factor_framework/backtest/run_backtest.py`
- Modify: `rqalpha_factor_framework/data/factor_store.py`
- Test: existing Task 1-7 tests plus one smoke backtest command.

- [ ] **Step 1: Add integration helpers to strategy**

Extend the strategy with helpers:

```python
def _current_positions():
    return [
        position.order_book_id
        for position in get_positions()
        if position.quantity > 0
    ]


def _order_to_targets(targets):
    for order_book_id, weight in targets.items():
        logger.info("order target {} weight {:.4f}".format(order_book_id, weight))
        order_target_percent(order_book_id, weight)
```

- [ ] **Step 2: Wire factor calculation**

Inside `rebalance`, collect daily data through `history_bars` for each stock, calculate all factor families, concatenate raw factors, preprocess, score, and build targets:

```python
raw_factors = pd.concat(
    [
        calculate_valuation_factors(daily_data),
        calculate_quality_factors(financial_data),
        calculate_growth_factors(financial_data),
        calculate_momentum_factors(daily_data),
        calculate_reversal_factors(daily_data),
        calculate_risk_factors(daily_data),
        calculate_liquidity_factors(daily_data),
        calculate_technical_factors(daily_data),
    ],
    axis=1,
)
processed = preprocess_factors(
    raw_factors,
    FACTOR_METADATA,
    winsorize_quantiles=tuple(config["scoring"]["winsorize_quantiles"]),
    missing=config["scoring"]["missing"],
)
scored = build_factor_scores(
    processed,
    FACTOR_METADATA,
    config["factors"]["category_weights"],
    config["factors"].get("factor_weights"),
)
targets = build_equal_weight_targets(
    scored,
    _current_positions(),
    config["portfolio"]["holding_count"],
    config["portfolio"]["buffer_count"],
    total_exposure=1.0,
)
```

- [ ] **Step 3: Log target holdings and factor scores**

Add logs:

```python
logger.info("target stocks: {}".format(list(targets.keys())))
for order_book_id in targets:
    row = scored.loc[order_book_id]
    logger.info(
        "factor score {} total={:.6f} valuation={:.6f} quality={:.6f} growth={:.6f} momentum={:.6f}".format(
            order_book_id,
            row.get("score", 0.0),
            row.get("valuation_score", 0.0),
            row.get("quality_score", 0.0),
            row.get("growth_score", 0.0),
            row.get("momentum_score", 0.0),
        )
    )
```

- [ ] **Step 4: Run all unit tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework -q
```

Expected: all factor framework tests pass.

- [ ] **Step 5: Run backtest smoke test**

Run:

```powershell
.\.venv\Scripts\python.exe rqalpha_factor_framework\backtest\run_backtest.py
```

Expected:

- Baostock cache is read or downloaded.
- RQAlpha run completes.
- `rqalpha_factor_framework/backtest/multi_factor_result.pkl` is created.
- Logs include target stocks and factor scores.

- [ ] **Step 6: Commit Task 8**

Run:

```powershell
git add rqalpha_factor_framework
git commit -m "feat: integrate factor framework backtest"
```

---

### Task 9: Final Verification And Documentation Notes

**Files:**
- Modify: `docs/superpowers/plans/2026-05-01-rqalpha-baostock-factor-framework.md` if implementation discovers plan corrections.
- Optional Create: `rqalpha_factor_framework/README.md`

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework tests\unittest\test_mod\test_baostock\test_baostock_mod.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run dependency check**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip check
```

Expected:

```text
No broken requirements found.
```

- [ ] **Step 3: Inspect generated result**

Run:

```powershell
.\.venv\Scripts\python.exe - <<'PY'
import pandas as pd
path = "rqalpha_factor_framework/backtest/multi_factor_result.pkl"
result = pd.read_pickle(path)
print(sorted(result.keys()))
for key in ("portfolio", "trades"):
    value = result.get(key)
    print(key, getattr(value, "shape", None))
PY
```

Expected: result keys print successfully, and `portfolio` has rows.

- [ ] **Step 4: Commit final verification/doc updates**

Run:

```powershell
git status --short
git add rqalpha_factor_framework tests\unittest\test_factor_framework docs\superpowers\plans\2026-05-01-rqalpha-baostock-factor-framework.md
git commit -m "test: verify factor framework"
```

If `git status --short` shows only ignored generated cache/result files, do not commit those files.

---

## Self-Review

Spec coverage:

- 股票池、月度调仓、默认 30 只、等权、缓冲换仓：Tasks 1, 6, 7, 8。
- 八类因子：Tasks 3 and 4。
- 缺失值、去极值、Z-score、方向调整、大类得分、综合得分：Task 5。
- ST、停牌、上市时间、成交额、估值、涨跌停过滤：Task 6 and Task 8。
- 单票权重、行业权重、指数择时：Task 6 includes single-stock and timing; industry cap is implemented as an interface and skipped with warning when industry data is missing, matching the design.
- 指定工程结构：Tasks 1 through 7.
- YAML、回测脚本、调仓输出：Tasks 1, 7, 8.

Placeholder scan:

- The plan contains no unresolved placeholder markers or unspecified test commands.
- Task 3 intentionally groups four market-factor modules into one step, but each required factor and test assertion is named.

Type consistency:

- Config keys use `holding_count`, `buffer_count`, `category_weights`, `winsorize_quantiles`, and `cache_dir` consistently.
- Factor names match `FACTOR_METADATA` and test expectations.
- Portfolio builders consistently return `{order_book_id: target_weight}` mappings.
