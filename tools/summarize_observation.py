"""Validate and summarize deterministic Victoria 3 observation checkpoints."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CORE_COUNTRIES = {"SHU", "JHG", "DMG", "NQG", "OIR", "MNG", "TIB", "KOR", "LAN", "NMG"}
REQUIRED_FIELDS = {
    "year",
    "country",
    "rank",
    "population",
    "market",
    "wars",
    "subjects",
    "error_count",
}
CHECKPOINT_YEARS = {1846, 1866, 1900}


def _checkpoint_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.rglob("checkpoints.json"))
    raise ValueError(f"input does not exist: {input_path}")


def _load_rows(path: Path) -> list[dict]:
    data = json.loads(path.read_text("utf-8"))
    if isinstance(data, dict):
        data = data.get("checkpoints")
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ValueError(f"{path}: expected a JSON list of checkpoint objects")
    return data


def _validate_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"{path}: no checkpoints")
    years = set()
    for index, row in enumerate(rows, 1):
        missing = REQUIRED_FIELDS - set(row)
        if missing:
            raise ValueError(f"{path}:{index}: missing fields: {sorted(missing)}")
        if row["country"] not in CORE_COUNTRIES:
            raise ValueError(f"{path}:{index}: unknown country {row['country']}")
        if not isinstance(row["year"], int):
            raise ValueError(f"{path}:{index}: year must be an integer")
        years.add(row["year"])
        if row["population"] < 0:
            raise ValueError(f"{path}:{index}: negative population")
        if row["wars"] < 0 or row["subjects"] < 0:
            raise ValueError(f"{path}:{index}: negative wars or subjects")
        if row["error_count"] > 0:
            raise ValueError(f"{path}:{index}: error_count > 0")
        if "capital_count" in row and row["capital_count"] != 1:
            raise ValueError(f"{path}:{index}: multiple capitals")
        if "capitals" in row:
            capitals = row["capitals"]
            if not isinstance(capitals, list) or len(capitals) != 1:
                raise ValueError(f"{path}:{index}: multiple capitals")
    missing_years = CHECKPOINT_YEARS - years
    if missing_years:
        raise ValueError(f"{path}: missing checkpoint years: {sorted(missing_years)}")


def summarize(input_path: Path) -> dict:
    files = _checkpoint_files(input_path)
    if not files:
        raise ValueError(f"{input_path}: no checkpoints.json files found")
    run_summaries = []
    all_rows: list[dict] = []
    for path in files:
        rows = _load_rows(path)
        _validate_rows(path, rows)
        all_rows.extend(rows)
        run_summaries.append(
            {
                "source": str(path),
                "checkpoint_count": len(rows),
                "countries": sorted({row["country"] for row in rows}),
                "years": sorted({row["year"] for row in rows}),
            }
        )
    return {
        "runs": len(run_summaries),
        "checkpoint_count": len(all_rows),
        "countries": sorted({row["country"] for row in all_rows}),
        "years": sorted({row["year"] for row in all_rows}),
        "run_summaries": run_summaries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = summarize(args.input)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(error)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote observation summary: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
