from pathlib import Path

from rqalpha import run_file
from rqalpha.examples.multi_factor_strategy.config import load_config
from rqalpha.mod.rqalpha_mod_baostock.cache import BaostockCache
from rqalpha.mod.rqalpha_mod_baostock.data_source import fetch_baostock_daily_data


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[2]
STRATEGY_CONFIG = ROOT / "config.yml"
BAOSTOCK_CACHE_DIR = PROJECT_ROOT / ".rqalpha_baostock_cache"
BAOSTOCK_START_DATE = "2022-01-01"
BAOSTOCK_END_DATE = "2023-04-30"
BAOSTOCK_ADJUSTFLAG = "2"


def download_offline_baostock_data():
    """回测前预下载配置股票池的 Baostock 日线数据到本地缓存。"""
    strategy_config = load_config(STRATEGY_CONFIG)
    cache = BaostockCache(BAOSTOCK_CACHE_DIR)
    for order_book_id in strategy_config["stock_pool"]["symbols"]:
        cache.load_or_fetch(
            order_book_id,
            BAOSTOCK_START_DATE,
            BAOSTOCK_END_DATE,
            BAOSTOCK_ADJUSTFLAG,
            fetch_baostock_daily_data,
        )


# RQAlpha 回测配置：时间区间、数据源、账户资金和策略运行参数。
config = {
    "base": {
        "start_date": "2023-01-03",
        "end_date": "2023-04-28",
        # BaseDataSource 仍使用本地 bundle 提供合约、交易日历等基础数据。
        "data_bundle_path": str(PROJECT_ROOT / "bundle" / "bundle"),
        "accounts": {
            "stock": 1000000,
        },
    },
    "extra": {
        "log_level": "info",
        "context_vars": {
            # 通过 context_vars 将多因子策略的 YAML 配置路径传入 strategy.py。
            "multi_factor_config": str(STRATEGY_CONFIG),
        },
    },
    "mod": {
        "baostock": {
            "enabled": True,
            "lib": "rqalpha.mod.rqalpha_mod_baostock",
            "cache_dir": str(BAOSTOCK_CACHE_DIR),
            "adjustflag": BAOSTOCK_ADJUSTFLAG,
            "start_date": BAOSTOCK_START_DATE,
            "end_date": BAOSTOCK_END_DATE,
        },
        "sys_analyser": {
            "enabled": True,
            "benchmark": "000300.XSHG",
            # 将回测结果保存为 pickle，便于后续生成报告或进一步分析。
            "output_file": str(ROOT / "multi_factor_result.pkl"),
        },
    },
}


if __name__ == "__main__":
    download_offline_baostock_data()
    # 使用 RQAlpha 的 run_file 入口运行当前目录下的策略文件。
    run_file(str(ROOT / "strategy.py"), config)
