# RQAlpha + Baostock 综合多因子选股框架设计

## 背景

当前仓库已经具备两个基础能力：

- 一个轻量版 `multi_factor_strategy` 示例，支持基于配置的 PE、PB、动量打分和 RQAlpha 回测。
- 一个 `rqalpha_mod_baostock` 数据源扩展，支持通过 Baostock 日线数据驱动 A 股回测，并具备本地 CSV 缓存。

本次需求是在此基础上实现一个独立的、可扩展的综合多因子选股框架。新框架不继续堆叠旧示例，而是按清晰模块边界放在 `rqalpha_factor_framework/` 下，作为更完整的策略系统。

## 目标

实现一个基于 RQAlpha + Baostock 的 A 股多因子选股系统，具备以下能力：

- 支持沪深300、中证500、中证800、自定义股票列表。
- 支持月度调仓，默认每月第一个交易日调仓。
- 默认持仓 30 只股票。
- 默认等权组合，保留得分加权扩展接口。
- 支持缓冲区换仓：新买入选择前 30 名，已有持仓跌出前 60 名才卖出。
- 覆盖价值、质量、成长、动量、反转、风险、流动性、技术八类因子。
- 统一完成缺失值处理、1%/99% 分位数去极值、Z-score 标准化、方向调整、大类得分和综合得分。
- 支持 ST、停牌、上市时间、成交额、估值有效性、涨跌停交易限制过滤。
- 支持单票权重、行业权重、指数择时仓位控制。
- 输出调仓日期、目标持仓、因子得分和交易记录。

## 非目标

- 不在首版实现复杂组合优化器，例如均值方差优化、风险平价或行业中性优化。
- 不依赖 RQData 作为默认数据源，首版以 Baostock 为默认可运行数据源。
- 不保证 Baostock 没有覆盖的财务字段在所有股票和日期上完整可用；首版会通过缓存、缺失值处理和日志暴露数据质量问题。

## 总体架构

框架目录如下：

```text
rqalpha_factor_framework/
├── strategies/
│   └── multi_factor_strategy.py
├── factors/
│   ├── valuation.py
│   ├── quality.py
│   ├── growth.py
│   ├── momentum.py
│   ├── reversal.py
│   ├── risk.py
│   ├── liquidity.py
│   └── technical.py
├── filters/
│   ├── stock_filter.py
│   ├── liquidity_filter.py
│   └── trading_filter.py
├── scoring/
│   ├── preprocess.py
│   ├── neutralize.py
│   └── factor_score.py
├── portfolio/
│   ├── equal_weight.py
│   ├── score_weight.py
│   └── constraints.py
├── data/
│   ├── baostock_client.py
│   ├── factor_store.py
│   └── cache.py
├── backtest/
│   ├── run_backtest.py
│   └── batch_backtest.py
├── reports/
│   └── performance_report.py
└── config/
    └── multi_factor_config.yaml
```

策略入口只做流程编排：读取配置、解析股票池、过滤股票、计算因子、打分、构建组合、执行调仓、记录日志。具体数据获取、因子计算、打分和组合约束都放到独立模块。

## 数据设计

### Baostock 日线数据

日线数据优先使用现有 `rqalpha_mod_baostock` 支持的字段：

- `open`
- `high`
- `low`
- `close`
- `volume`
- `amount`
- `turn`
- `tradestatus`
- `peTTM`
- `pbMRQ`
- `isST`

这些字段用于价值、动量、反转、风险、流动性和技术因子。

### Baostock 财务数据

质量和成长因子需要使用 Baostock 财务接口补充，包括：

- ROE
- ROA
- 毛利率
- 资产负债率
- 营收同比增长率
- 净利润同比增长率
- 经营现金流同比增长率

`data/baostock_client.py` 负责调用 Baostock 接口，`data/factor_store.py` 负责将财务数据按股票和日期对齐到调仓日。所有原始数据写入本地缓存，回测时优先读取缓存。

### 股票池

股票池由配置决定：

- `index: 000300.XSHG` 表示沪深300。
- `index: 000905.XSHG` 表示中证500。
- `index: 000906.XSHG` 表示中证800。
- `symbols` 非空时优先使用自定义股票列表。

如果指数成分接口在离线环境不可用，示例配置会允许使用 `symbols` 列表作为兜底。

## 因子设计

每个因子模块返回统一结构的 `DataFrame`：

- 索引：RQAlpha 股票代码，例如 `600000.XSHG`。
- 列：因子名称，例如 `pe_ttm`、`momentum_60`。
- 值：调仓日可获得的截面因子值。

因子方向由元数据定义，避免在打分逻辑中硬编码：

- `higher_better`：越高越好。
- `lower_better`：越低越好，标准化后取负。
- `middle_better`：适中更好，首版用于 20 日平均换手率，按偏离目标换手率的绝对距离取负。

首版实现以下因子：

- 价值：`pe_ttm`、`pb`、`ps_ttm`。
- 质量：`roe`、`roa`、`gross_margin`、`debt_to_asset`。
- 成长：`revenue_growth_yoy`、`net_profit_growth_yoy`、`operating_cashflow_growth_yoy`。
- 动量：`return_20`、`return_60`、`return_120`、`price_ma60_strength`。
- 反转：`return_5`、`rsi`。
- 风险：`volatility_60`、`max_drawdown_120`。
- 流动性：`avg_amount_20`、`avg_turnover_20`。
- 技术：`macd_hist`、`obv_trend`。

如果某个 Baostock 财务字段在当前股票或日期缺失，因子模块不自行补值，由统一预处理模块处理。

## 因子处理和打分

`scoring/preprocess.py` 负责：

- 将非数值转换为缺失值。
- 按配置进行缺失值处理，默认使用截面中位数填充。
- 对每个因子做 1% 和 99% 分位数去极值。
- 对每个因子做 Z-score 标准化。
- 对越低越好的因子取负。

`scoring/factor_score.py` 负责：

- 按因子所属大类计算大类得分。
- 大类内部默认等权，也支持配置单因子权重。
- 按大类权重计算综合得分。
- 默认大类权重：
  - 价值：15%
  - 质量：20%
  - 成长：20%
  - 动量：15%
  - 反转：5%
  - 风险：10%
  - 流动性：5%
  - 技术：10%

`scoring/neutralize.py` 首版提供预留接口，不默认做行业、市值中性化，避免在 Baostock 数据不完整时引入额外不稳定性。

## 过滤规则

过滤流程分三层：

1. `filters/stock_filter.py`
   - 剔除 ST 和 *ST。
   - 剔除上市不足 180 天。
   - 剔除 PE <= 0 或 PB <= 0。

2. `filters/liquidity_filter.py`
   - 剔除最近 20 日平均成交额低于 3000 万的股票。

3. `filters/trading_filter.py`
   - 剔除调仓日停牌股票。
   - 买入时剔除涨停无法买入的股票。
   - 卖出时遇到跌停无法卖出的股票则保留，并记录日志。

过滤阈值全部写入 YAML 配置。

## 组合构建和风控

`portfolio/equal_weight.py` 首版实现等权组合：

- 根据综合得分排序。
- 新买入选择前 30 名。
- 已持仓股票只有跌出前 60 名才卖出。
- 目标持仓数不足时从高分股票中补足。

`portfolio/score_weight.py` 提供得分加权接口，首版可实现但默认不启用。

`portfolio/constraints.py` 负责：

- 单只股票最大权重不超过 5%。
- 单一行业最大权重不超过 25%。
- 根据沪深300指数择时调整总仓位：
  - 指数高于 120 日均线：总仓位 100%。
  - 指数低于 120 日均线：总仓位 50%。
  - 指数低于 250 日均线：总仓位 30%。

行业权重约束依赖行业分类数据。首版会提供接口和配置；如果行业数据缺失，则记录警告并跳过行业上限约束，不阻塞基础回测。

## RQAlpha 策略流程

`strategies/multi_factor_strategy.py` 使用 RQAlpha 标准策略方式运行：

1. `init(context)` 读取 YAML 配置。
2. 注册每月第一个交易日调仓。
3. 调仓日解析股票池。
4. 下载或读取 Baostock 缓存数据。
5. 执行股票过滤。
6. 计算所有启用因子。
7. 完成因子预处理和综合评分。
8. 使用缓冲区换仓逻辑生成目标组合。
9. 应用单票、行业和指数择时约束。
10. 卖出不在目标组合且可卖出的股票。
11. 买入或调整目标组合股票。
12. 输出调仓日志、目标持仓、因子得分和交易记录。

## 配置设计

`config/multi_factor_config.yaml` 至少包含：

- 股票池配置。
- 调仓频率和调仓日配置。
- 持仓数量和缓冲区排名。
- 因子启用状态、大类权重、单因子权重。
- 缺失值处理、去极值、标准化参数。
- 过滤阈值。
- 风控参数。
- Baostock 缓存路径、下载日期范围、复权方式。
- 回测起止日期、初始资金、基准指数。

配置中的默认示例使用沪深300。

## 日志和输出

每次调仓输出：

- 调仓日期。
- 股票池数量。
- 过滤后股票数量。
- 各过滤规则剔除数量。
- 目标股票列表。
- 目标股票的大类得分和综合得分。
- 卖出、买入、调仓失败或因涨跌停跳过的交易指令。

回测脚本保存 RQAlpha 回测结果，并由 `reports/performance_report.py` 提供基础导出能力。

## 错误处理

- Baostock 登录失败时直接抛出清晰错误。
- 缓存损坏时记录日志并重新下载。
- 某个财务因子缺失较多时记录警告，但不终止回测。
- 某类因子全部缺失时，该大类得分记为缺失，并在综合得分中自动忽略或按配置终止。
- 涨停无法买入、跌停无法卖出时记录交易跳过原因。
- 行业数据缺失时跳过行业约束并记录警告。

## 测试计划

首版测试包括：

- Baostock 代码和 RQAlpha 代码互转。
- 缓存命中和缓存缺失下载。
- 各类因子在小样本行情上的计算结果。
- 缺失值、去极值、Z-score、方向调整。
- 大类得分和综合得分。
- 过滤规则。
- 缓冲区换仓逻辑。
- 单票权重和择时仓位约束。
- `backtest/run_backtest.py` 使用小股票池和离线缓存完成一次可运行回测。

## 实施顺序

1. 创建 `rqalpha_factor_framework/` 包结构和配置文件。
2. 实现数据层缓存和 Baostock 客户端。
3. 实现行情类因子。
4. 实现财务类因子和财务数据对齐。
5. 实现统一预处理和评分。
6. 实现过滤器。
7. 实现等权组合、缓冲区换仓和基础风控。
8. 实现 RQAlpha 策略入口。
9. 实现回测脚本和报告导出。
10. 增加单元测试和一次离线回测验证。

