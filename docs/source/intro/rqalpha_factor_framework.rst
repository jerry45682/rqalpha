RQAlpha + Baostock 多因子选股框架
==================================

``rqalpha_factor_framework`` 是一个基于 RQAlpha 和 Baostock 数据源扩展的 A 股多因子选股回测框架。它把股票池、因子计算、因子预处理、过滤规则、组合构建、调仓交易和回测入口拆成独立模块，便于在同一套工程结构中继续扩展新的因子、过滤器、权重模型和报告输出。

框架默认面向日线级别的 A 股选股回测。示例配置使用沪深 300 作为股票池语义，并通过配置文件中的股票列表提供可离线运行的示例股票池。

功能概览
--------

框架当前提供以下能力：

* 月度调仓，默认在每月第一个交易日执行。
* 默认持仓 30 只股票，支持缓冲区换仓：新买入选择综合得分前 30 名，已持仓股票跌出前 60 名才卖出。
* 支持等权组合，并预留得分加权组合模块。
* 支持价值、质量、成长、动量、反转、风险、流动性和技术类因子。
* 对因子做缺失值处理、分位数去极值、Z-score 标准化和方向统一。
* 先计算大类得分，再按大类权重计算综合得分。
* 支持 ST、停牌、上市天数、成交额、PE/PB、涨跌停等过滤规则。
* 支持单只股票权重上限、行业权重上限和基于沪深 300 均线的指数择时仓位控制。
* 回测日志会输出调仓日期、目标股票、因子得分和交易指令。

目录结构
--------

核心代码位于 ``rqalpha_factor_framework`` 目录下：

.. code-block:: text

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

其中：

* ``strategies`` 保存 RQAlpha 策略入口。
* ``factors`` 保存各类因子计算逻辑。
* ``filters`` 保存股票池和交易过滤规则。
* ``scoring`` 保存因子预处理、标准化和综合打分逻辑。
* ``portfolio`` 保存目标权重构建和组合约束逻辑。
* ``data`` 保存 Baostock 访问、缓存和因子数据组织逻辑。
* ``backtest`` 保存单次回测和批量回测入口。
* ``reports`` 保存回测结果导出工具。
* ``config`` 保存默认 YAML 配置。

快速开始
--------

先确认项目依赖和 Baostock 可用。如果使用当前仓库的虚拟环境，可以在项目根目录执行：

.. code-block:: powershell

    .\.venv\Scripts\python.exe -m pip install -e .
    .\.venv\Scripts\python.exe -m pip install baostock

回测仍需要 RQAlpha bundle 提供合约、交易日历等基础数据。可以通过环境变量指定 bundle 路径：

.. code-block:: powershell

    $env:RQALPHA_FACTOR_BUNDLE_PATH = "E:\CodexWorkspace\rqalpha\bundle\bundle"

然后运行默认回测：

.. code-block:: powershell

    .\.venv\Scripts\python.exe rqalpha_factor_framework\backtest\run_backtest.py

也可以使用模块方式运行：

.. code-block:: powershell

    .\.venv\Scripts\python.exe -m rqalpha_factor_framework.backtest.run_backtest

指定自定义配置文件：

.. code-block:: powershell

    .\.venv\Scripts\python.exe rqalpha_factor_framework\backtest\run_backtest.py path\to\multi_factor_config.yaml

配置文件
--------

默认配置文件是 ``rqalpha_factor_framework/config/multi_factor_config.yaml``。常用配置项如下：

``stock_pool``
    股票池配置。``index`` 表示指数股票池语义，例如 ``000300.XSHG``；``symbols`` 非空时优先使用自定义股票列表。离线测试时建议显式配置 ``symbols``，避免依赖指数成分在线查询。

``rebalance``
    调仓配置。默认 ``frequency: monthly``、``tradingday: 1``，表示每月第一个交易日调仓。

``portfolio``
    组合配置。``holding_count`` 控制目标持仓数量，``buffer_count`` 控制缓冲区卖出阈值，``weighting`` 控制权重方式，当前默认是 ``equal``。

``factors``
    因子配置。``enabled_categories`` 控制启用的大类，``category_weights`` 控制大类权重，``factor_weights`` 可用于细化因子权重。

``scoring``
    因子处理配置。默认使用中位数补缺失值、1% 和 99% 分位数去极值、Z-score 标准化。

``filters``
    过滤规则配置。包括剔除 ST、剔除停牌、上市天数、20 日平均成交额、PE/PB 正值要求和涨跌停交易约束。

``risk``
    风控配置。包括单只股票最大权重、单一行业最大权重，以及指数择时仓位。

``data``
    Baostock 数据配置。``cache_dir`` 是本地缓存目录，``adjustflag`` 是复权类型，默认 ``"2"`` 表示前复权。

``backtest``
    回测配置。包括起止日期、频率、基准、初始资金、bundle 路径和结果文件路径。

数据与缓存
----------

框架通过 RQAlpha Mod 机制启用 ``rqalpha.mod.rqalpha_mod_baostock``。Baostock 数据源用于补充 A 股日线行情字段，本地缓存优先读取，缓存缺失时再请求 Baostock。

需要注意：

* Baostock 数据源当前面向 A 股日线，频率应使用 ``1d``。
* Baostock 代码和 RQAlpha 代码会自动互转，例如 ``600000.XSHG`` 对应 ``sh.600000``，``000001.XSHE`` 对应 ``sz.000001``。
* 仍需要 RQAlpha bundle 提供基础数据。Baostock 数据源不是完整的 bundle 替代品。
* 默认示例启用了价值、动量、反转、风险、流动性和技术类因子。质量和成长因子模块已经存在，但通常需要额外财务数据支持，默认示例未启用。

因子与打分
----------

因子按大类拆分：

* 价值：PE_TTM、PB、PS_TTM，越低越好。
* 质量：ROE、ROA、毛利率、资产负债率。
* 成长：营收同比增长率、净利润同比增长率、经营现金流同比增长率。
* 动量：20 日、60 日、120 日收益率，以及价格相对 60 日均线强度。
* 反转：5 日收益率和 RSI。
* 风险：60 日波动率和 120 日最大回撤。
* 流动性：20 日平均成交额和 20 日平均换手率。
* 技术：MACD 柱状线和 OBV 趋势。

每个因子会先完成缺失值处理、去极值和标准化。对于“越低越好”的因子，标准化后会取负，使所有因子统一为“分数越高越好”。之后先计算大类得分，再根据 ``category_weights`` 计算综合得分。

调仓逻辑
--------

每次调仓时，策略会执行以下步骤：

1. 获取股票池。
2. 拉取历史行情和基础字段。
3. 执行 ST、停牌、上市时间、成交额、PE/PB 和涨停买入过滤。
4. 计算启用因子和综合得分。
5. 按得分选择目标股票，并应用缓冲区换仓。
6. 根据等权或得分加权模型生成目标权重。
7. 应用单股权重上限、行业权重上限和指数择时总仓位。
8. 对不在目标组合中的股票下达卖出指令；对目标组合股票下达目标权重指令。

如果配置启用跌停卖出过滤，跌停股票会跳过卖出指令，等待后续调仓或可交易日处理。

输出结果
--------

默认回测结果输出到：

.. code-block:: text

    rqalpha_factor_framework/backtest/multi_factor_result.pkl

该文件由 ``sys_analyser`` 生成，是 pickle 格式。可以使用框架提供的导出函数转换为 CSV：

.. code-block:: powershell

    .\.venv\Scripts\python.exe -c "from rqalpha_factor_framework.reports.performance_report import export_result_pickle; print(export_result_pickle('rqalpha_factor_framework/backtest/multi_factor_result.pkl'))"

导出目录默认与结果文件同名但不带后缀，例如：

.. code-block:: text

    rqalpha_factor_framework/backtest/multi_factor_result/

测试
----

运行框架相关单元测试：

.. code-block:: powershell

    .\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework -q

如果同时需要验证 Baostock Mod：

.. code-block:: powershell

    .\.venv\Scripts\python.exe -m pytest tests\unittest\test_factor_framework tests\unittest\test_mod\test_baostock\test_baostock_mod.py -q

扩展方式
--------

新增因子时，建议优先按以下方式扩展：

1. 在 ``factors`` 目录中选择对应大类文件，新增计算函数或因子定义。
2. 在 ``factors/base.py`` 中确认因子元数据，包括因子名称、方向和所属类别。
3. 在配置文件的 ``enabled_categories``、``category_weights`` 或 ``factor_weights`` 中启用和调权。
4. 为新增因子补充单元测试，至少覆盖正常数据、缺失值和极端值。

新增过滤器、组合权重模型或报告导出时，也应保持当前模块边界：过滤逻辑放在 ``filters``，组合构建放在 ``portfolio``，结果导出放在 ``reports``。

常见问题
--------

为什么配置了沪深 300，但示例只跑少量股票？
    默认配置中的 ``stock_pool.symbols`` 提供了离线可跑的示例股票列表。只要该列表非空，策略会优先使用它。若要改为真实指数成分，需要清空 ``symbols`` 并确保运行环境可以获取 ``index_components``。

为什么质量和成长因子默认没有启用？
    这些因子依赖更完整的财务数据。当前 Baostock 日线字段不能完整覆盖所有质量和成长因子，因此默认示例先启用可以基于行情和已有字段稳定运行的因子类别。

Baostock 能否替代 RQAlpha bundle？
    不能。Baostock Mod 负责提供日线行情和部分字段，RQAlpha 仍需要 bundle 提供交易日历、合约等基础数据。

结果文件为什么不是 CSV？
    ``sys_analyser`` 默认输出 pickle。使用 ``rqalpha_factor_framework.reports.performance_report.export_result_pickle`` 可以把 pickle 内容导出为 CSV。
