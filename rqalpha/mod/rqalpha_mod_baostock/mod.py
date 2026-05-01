from rqalpha.interface import AbstractMod
from rqalpha.utils.logger import user_system_log

from .data_source import BaostockDataSource


class BaostockMod(AbstractMod):
    def start_up(self, env, mod_config):
        data_source = BaostockDataSource(env.config.base, mod_config)
        env.set_data_source(data_source)
        user_system_log.info("Baostock 数据源已启用，缓存目录: {}", mod_config.cache_dir)

    def tear_down(self, code, exception=None):
        pass

