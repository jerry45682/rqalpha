from collections.abc import Mapping
import pickle
import re
from pathlib import Path


def _csv_name(name):
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", str(name)).strip("_") or "result"


def export_result_pickle(path, output_dir=None):
    path = Path(path)
    output_dir = Path(output_dir) if output_dir is not None else path.with_suffix("")
    output_dir.mkdir(parents=True, exist_ok=True)

    with path.open("rb") as result_file:
        result = pickle.load(result_file)

    if hasattr(result, "to_csv"):
        output_path = output_dir / "result.csv"
        result.to_csv(output_path, encoding="utf-8-sig")
        return [output_path]

    exported = []
    if not isinstance(result, Mapping):
        return exported

    items = result.items()
    for name, value in items:
        if not hasattr(value, "to_csv"):
            continue
        output_path = output_dir / "{}.csv".format(_csv_name(name))
        value.to_csv(output_path, encoding="utf-8-sig")
        exported.append(output_path)

    return exported
