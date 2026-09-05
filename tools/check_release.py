"""Run the structural release gate without changing game or save data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CONFIGS = {"none", "sphere", "charters", "wave", "all"}
SEEDS = {11, 23, 47}
YEARS = [1846, 1866, 1900]


def check(matrix_path: Path, mod_root: Path) -> list[str]:
    errors: list[str] = []
    if not mod_root.is_dir():
        errors.append(f"mod root does not exist: {mod_root}")
    try:
        data = json.loads(matrix_path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"cannot read matrix: {error}"]
    runs = data.get("runs")
    if not isinstance(runs, list) or len(runs) != 15:
        errors.append("matrix must contain exactly 15 runs")
        runs = runs if isinstance(runs, list) else []
    if set(data.get("configs", [])) != CONFIGS:
        errors.append("matrix configs are incomplete")
    if set(data.get("seeds", [])) != SEEDS:
        errors.append("matrix seeds are incomplete")
    for index, run in enumerate(runs, 1):
        if run.get("checkpoint_years") != YEARS:
            errors.append(f"run {index} has invalid checkpoint years")
        if run.get("status") != "verified":
            errors.append(f"run {index} is not verified: {run.get('status')}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--mod-root", type=Path, required=True)
    args = parser.parse_args()
    errors = check(args.matrix, args.mod_root)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Release gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
