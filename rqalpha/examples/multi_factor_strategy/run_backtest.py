import os
from pathlib import Path

from rqalpha import run_file


ROOT = Path(__file__).resolve().parent

# RQAlpha 回测配置：时间区间、基准、账户资金和策略运行参数。
config = {
    "base": {
        "start_date": "2026-01-01",
        "end_date": "2026-04-30",
        "benchmark": "000300.XSHG",
        # 使用当前仓库下已下载好的 bundle 数据；如需使用默认目录可删除该配置。
        "data_bundle_path": str(ROOT.parents[2] / "bundle" / "bundle"),
        # 如需使用 PE/PB/ROE 和沪深300成分股，请设置环境变量 RQDATAC_URI。
        "rqdatac_uri": os.environ.get("RQDATAC_URI"),
        "accounts": {
            "stock": 1000000,
        },
    },
    "extra": {
        "log_level": "info",
        "context_vars": {
            # 通过 context_vars 将多因子策略的 YAML 配置路径传入 strategy.py。
            "multi_factor_config": str(ROOT / "config.yml"),
        },
    },
    "mod": {
        "sys_analyser": {
            "enabled": True,
            # 将回测结果保存为 pickle，便于后续生成报告或进一步分析。
            "output_file": str(ROOT / "multi_factor_result.pkl"),
        },
    },
}


if __name__ == "__main__":
    # 使用 RQAlpha 的 run_file 入口运行当前目录下的策略文件。
    run_file(str(ROOT / "strategy.py"), config)
