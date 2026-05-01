import pickle
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        raise SystemExit("missing pkl file")

    pkl_path = Path(sys.argv[1]).resolve()
    if not pkl_path.exists():
        raise SystemExit("file not found: {}".format(pkl_path))

    output_dir = pkl_path.with_suffix("")
    output_dir.mkdir(exist_ok=True)

    with pkl_path.open("rb") as f:
        result = pickle.load(f)

    exported = []
    for key, value in result.items():
        if hasattr(value, "to_csv"):
            csv_path = output_dir / "{}.csv".format(key)
            value.to_csv(csv_path, encoding="utf-8-sig")
            exported.append(csv_path.name)

    summary = result.get("summary")
    if summary is not None:
        (output_dir / "summary.txt").write_text(str(summary), encoding="utf-8")

    print("Output directory: {}".format(output_dir))
    print("CSV files: {}".format(", ".join(exported)))
    print("Summary: summary.txt")


if __name__ == "__main__":
    main()
