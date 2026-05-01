from .mod import BaostockMod


__config__ = {
    "enabled": False,
    "priority": 50,
    "cache_dir": ".rqalpha_baostock_cache",
    "adjustflag": "2",
    "start_date": "2010-01-01",
    "end_date": None,
}


def load_mod():
    return BaostockMod()

