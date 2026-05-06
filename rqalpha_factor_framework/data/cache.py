from pathlib import Path
import re

import pandas as pd


_SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9_-]")


class CsvCache:
    def __init__(self, root):
        self.root = Path(root)

    def path_for(self, namespace, key):
        root = self.root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        safe_namespace = _safe_name(namespace)
        safe_key = _safe_name(key)
        directory = root / safe_namespace
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{safe_key}.csv"
        try:
            path.resolve().relative_to(root)
        except ValueError:
            raise ValueError("cache path escaped root")
        return path

    def load_or_fetch(self, namespace, key, fetcher):
        path = self.path_for(namespace, key)
        if path.exists():
            return _read_csv(path)

        frame = fetcher()
        if frame is None:
            frame = pd.DataFrame()
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        return _read_csv(path)


def _safe_name(value):
    safe = _SAFE_NAME_PATTERN.sub("_", str(value))
    return safe or "_"


def _read_csv(path):
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
