from pathlib import Path

import pandas as pd


class CsvCache:
    def __init__(self, root):
        self.root = Path(root)

    def path_for(self, namespace, key):
        directory = self.root / namespace
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{str(key).replace('.', '_').replace('/', '_')}.csv"
        return directory / filename

    def load_or_fetch(self, namespace, key, fetcher):
        path = self.path_for(namespace, key)
        if path.exists():
            try:
                return pd.read_csv(path)
            except pd.errors.EmptyDataError:
                return pd.DataFrame()

        frame = fetcher()
        if frame is None:
            frame = pd.DataFrame()
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        return frame
