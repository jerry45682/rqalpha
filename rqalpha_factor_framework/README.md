# RQAlpha + Baostock 多因子选股框架

`rqalpha_factor_framework` 是一个基于 RQAlpha 和 Baostock 数据源扩展的 A 股多因子选股回测框架。它将因子计算、股票过滤、综合打分、组合构建、调仓交易、回测入口和结果导出拆成独立模块，方便继续扩展新的因子、过滤器和组合权重模型。

更完整的说明见正式文档：`docs/source/intro/rqalpha_factor_framework.rst`。

## 快速运行

在项目根目录准备依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install baostock
```

指定 RQAlpha bundle 路径：

```powershell
$env:RQALPHA_FACTOR_BUNDLE_PATH = "E:\CodexWorkspace\rqalpha\bundle\bundle"
```

运行默认回测：

```powershell
.\.venv\Scripts\python.exe rqalpha_factor_framework\backtest\run_backtest.py
```

也可以传入自定义配置文件：

```powershell
.\.venv\Scripts\python.exe rqalpha_factor_framework\backtest\run_backtest.py path\to\multi_factor_config.yaml
```

## 默认配置

默认配置文件位于：

```text
rqalpha_factor_framework/config/multi_factor_config.yaml
```

主要配置块包括：

- `stock_pool`：指数股票池和自定义股票列表。
- `rebalance`：调仓频率和调仓日。
- `portfolio`：持仓数量、缓冲区和权重方式。
- `factors`：启用因子大类、大类权重和因子权重。
- `scoring`：缺失值处理、去极值和标准化方式。
- `filters`：ST、停牌、上市天数、成交额、PE/PB、涨跌停过滤。
- `risk`：单股权重上限、行业权重上限和指数择时仓位。
- `data`：Baostock 缓存目录、复权方式和数据起止日期。
- `backtest`：回测起止日期、基准、初始资金、bundle 和结果路径。

## 输出结果

默认结果文件：

```text
rqalpha_factor_framework/backtest/multi_factor_result.pkl
```

导出 CSV：

```powershell
.\.venv\Scripts\python.exe -c "from rqalpha_factor_framework.reports.performance_report import export_result_pickle; print(export_result_pickle('rqalpha_factor_framework/backtest/multi_factor_result.pkl'))"
```

生成交互式 HTML 报告：

```powershell
.\.venv\Scripts\python.exe -m rqalpha_factor_framework.reports.interactive_report rqalpha_factor_framework/backtest/multi_factor_result.pkl
```

生成激进模板回测报告：

```powershell
.\.venv\Scripts\python.exe -m rqalpha_factor_framework.reports.interactive_report rqalpha_factor_framework/backtest/multi_factor_result_aggressive.pkl -o rqalpha_factor_framework/backtest/multi_factor_result_aggressive_report.html
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework -q
```

同时验证 Baostock Mod：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework tests\unittest\test_mod\test_baostock\test_baostock_mod.py -q
```

## 注意事项

- Baostock 数据源当前面向 A 股日线，频率应使用 `1d`。
- Baostock Mod 不是 RQAlpha bundle 的完整替代品，仍需要 bundle 提供交易日历、合约等基础数据。
- 默认示例优先使用 `stock_pool.symbols` 中配置的股票列表，适合离线测试。
- 质量和成长因子模块已经预留，但通常需要额外财务数据支持，默认示例未启用。
