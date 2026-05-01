# Baostock 数据源 Mod 实现计划

## 目标

实现 `rqalpha_mod_baostock`，通过 RQAlpha Mod 机制把 A 股日线数据源切换到 Baostock，并复用 RQAlpha 默认 bundle 的合约、交易日历、账户、撮合和风控能力。

## 设计

- `rqalpha/mod/rqalpha_mod_baostock/__init__.py`：导出默认配置和 `load_mod()`。
- `rqalpha/mod/rqalpha_mod_baostock/mod.py`：在 `start_up()` 中创建 `BaostockDataSource` 并调用 `env.set_data_source()`。
- `rqalpha/mod/rqalpha_mod_baostock/data_source.py`：继承 `BaseDataSource`，覆盖 `get_bar`、`history_bars`、`available_data_range`，仅支持 A 股日线。
- `rqalpha/mod/rqalpha_mod_baostock/cache.py`：封装本地 CSV 缓存，优先读缓存，缺失时调用 Baostock。
- `rqalpha/mod/rqalpha_mod_baostock/code_map.py`：负责 `600000.XSHG <-> sh.600000`、`000001.XSHE <-> sz.000001` 转换。
- `rqalpha/mod/rqalpha_mod_baostock/config.yml`：提供 YAML 配置示例。
- `rqalpha/examples/multi_factor_strategy/run_backtest.py`：增加 Baostock Mod 示例配置，继续使用已有多因子策略作为示例。

## 测试

- 单元测试覆盖代码互转、Baostock 字段转换、缓存命中/缺失、`get_bar`、`history_bars`、`available_data_range`。
- 示例回测前先用 Baostock 下载配置股票池的离线数据到缓存目录，再用离线缓存运行回测。

## 约束

- 只支持 `frequency="1d"`。
- 默认 `adjustflag="2"`，即 Baostock 前复权。
- Baostock 不提供 RQAlpha 完整 bundle，所以仍需要 `base.data_bundle_path` 指向现有 bundle，用于合约和交易日历。
