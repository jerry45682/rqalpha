from rqalpha.interface import AbstractMod
from rqalpha.utils.logger import user_system_log

from .data_source import BaostockDataSource, fetch_baostock_index_components


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _dedupe(values):
    result = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _prefetch_component_date(env, mod_config):
    end_date = getattr(mod_config, "end_date", None)
    if end_date:
        return end_date
    return getattr(env.config.base, "end_date", None)


def _resolve_prefetch_symbols(env, mod_config):
    symbols = _as_list(getattr(mod_config, "symbols", []) or [])
    component_date = _prefetch_component_date(env, mod_config)
    for index in _as_list(getattr(mod_config, "index_symbols", []) or []):
        symbols.extend(fetch_baostock_index_components(index, date=component_date))
    return _dedupe(symbols)


def _filter_bundle_symbols(data_source, symbols):
    if not hasattr(data_source, "get_instruments"):
        return symbols

    valid = {
        instrument.order_book_id
        for instrument in data_source.get_instruments(symbols)
        if getattr(instrument, "order_book_id", None)
    }
    filtered = [symbol for symbol in symbols if symbol in valid]
    skipped = [symbol for symbol in symbols if symbol not in valid]
    if skipped:
        user_system_log.warn(
            "Baostock prefetch skipped {} symbols not found in bundle: {}",
            len(skipped),
            skipped[:10],
        )
    return filtered


class BaostockMod(AbstractMod):
    def start_up(self, env, mod_config):
        data_source = BaostockDataSource(env.config.base, mod_config)
        env.set_data_source(data_source)

        if getattr(mod_config, "prefetch", False):
            symbols = _resolve_prefetch_symbols(env, mod_config)
            symbols = _filter_bundle_symbols(data_source, symbols)
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
