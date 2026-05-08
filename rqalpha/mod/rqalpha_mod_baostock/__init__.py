from .mod import BaostockMod


__config__ = {
    "enabled": False,
    "priority": 50,
    "cache_dir": ".rqalpha_baostock_cache",
    "adjustflag": "2",
    "start_date": "2010-01-01",
    "end_date": None,
    "prefetch": False,
    "symbols": [],
    "index_symbols": [],
    "runtime_fetch": True,
    "financial_tables": ["profit", "balance", "growth", "cash_flow", "dupont"],
}


def load_mod():
    return BaostockMod()

