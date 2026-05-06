from rqalpha.interface import AbstractMod
from rqalpha.utils.logger import user_system_log

from .data_source import BaostockDataSource


class BaostockMod(AbstractMod):
    def start_up(self, env, mod_config):
        data_source = BaostockDataSource(env.config.base, mod_config)
        env.set_data_source(data_source)

        if getattr(mod_config, "prefetch", False):
            symbols = list(getattr(mod_config, "symbols", []) or [])
            if symbols:
                data_source.prepare_data(symbols)
                user_system_log.info(
                    "Baostock cache warmed, symbol count: {}", len(symbols)
                )
            else:
                user_system_log.warn("Baostock prefetch is enabled but symbols is empty")

        user_system_log.info("Baostock data source enabled, cache dir: {}", mod_config.cache_dir)

    def tear_down(self, code, exception=None):
        pass
