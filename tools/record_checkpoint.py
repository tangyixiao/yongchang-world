"""Record one real observation checkpoint year into a run's checkpoints.json.

The release gate rejects invented evidence, so this tool never generates,
estimates, or back-fills campaign numbers: every row comes from a file the
operator exported from a real session (or typed from the in-game panels). What
it does add is validation and merging, so a 15-run / 30-row-per-run matrix can
be filled in one checkpoint year at a time without corrupting a run that is
already partly recorded.

Typical use after finishing a checkpoint year in a real campaign:

    python tools/record_checkpoint.py --config none --seed 11 --year 1846 ^
        --input checkpoints-1846.csv

and, once all three years of a run are present:

    python tools/record_checkpoint.py --config none --seed 11 --finalize ^
        --campaign "manual 1836-1900 campaign, launcher playset none" ^
        --logs artifacts/observe/none/11/userdata/logs/debug.log
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable

# Running `python tools/record_checkpoint.py` puts the tools/ directory on
# sys.path rather than the repository root, so the shared observation schema in
# the tools package has to be made importable explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.summarize_observation import (  # noqa: E402
    CHECKPOINT_YEARS,
    CONFIGS,
    CORE_COUNTRIES,
    REQUIRED_FIELDS,
    SEEDS,
    validate_checkpoint_rows,
    validate_run_metadata,
)

NUMERIC_FIELDS = ("year", "population", "wars", "subjects", "error_count")
TEXT_FIELDS = ("country", "rank", "market")
CSV_COLUMNS = ("year", "country", "rank", "population", "market", "wars", "subjects", "error_count")


class RecordCheckpointError(Exception):
    """Raised when operator-supplied checkpoint data cannot be accepted."""


def _coerce_row(row: dict, source: str, index: int) -> dict:
    if not isinstance(row, dict):
        raise RecordCheckpointError(f"{source}:{index}: expected an object")
    missing = REQUIRED_FIELDS - set(row)
    if missing:
        raise RecordCheckpointError(f"{source}:{index}: missing fields: {sorted(missing)}")
    coerced: dict = {}
    for field in NUMERIC_FIELDS:
        value = row[field]
        if isinstance(value, bool):
            raise RecordCheckpointError(f"{source}:{index}: {field} must be an integer")
        if isinstance(value, str):
            if not value.strip().lstrip("-").isdigit():
                raise RecordCheckpointError(f"{source}:{index}: {field} must be an integer")
            value = int(value)
        if not isinstance(value, int):
            raise RecordCheckpointError(f"{source}:{index}: {field} must be an integer")
        if value < 0:
            raise RecordCheckpointError(f"{source}:{index}: negative {field}")
        coerced[field] = value
    for field in TEXT_FIELDS:
        value = row[field]
        if not isinstance(value, str) or not value.strip():
            raise RecordCheckpointError(f"{source}:{index}: {field} must be non-empty text")
        coerced[field] = value
    return coerced


def validate_rows(rows: Iterable[dict], year: int, source: str = "input") -> list[dict]:
    """Validate one checkpoint year's ten country rows and return them sorted."""

    coerced = [_coerce_row(row, source, index) for index, row in enumerate(rows, 1)]
    if not coerced:
        raise RecordCheckpointError(f"{source}: no checkpoint rows supplied")
    wrong_year = sorted({row["year"] for row in coerced if row["year"] != year})
    if wrong_year:
        raise RecordCheckpointError(
            f"{source}: rows for years {wrong_year} do not match --year {year}"
        )
    countries = [row["country"] for row in coerced]
    duplicates = sorted({name for name in countries if countries.count(name) > 1})
    if duplicates:
        raise RecordCheckpointError(f"{source}: duplicate countries: {duplicates}")
    unknown = sorted(set(countries) - set(CORE_COUNTRIES))
    if unknown:
        raise RecordCheckpointError(f"{source}: unknown countries: {unknown}")
    missing = sorted(set(CORE_COUNTRIES) - set(countries))
    if missing:
        raise RecordCheckpointError(f"{source}: missing countries: {missing}")
    with_errors = sorted(row["country"] for row in coerced if row["error_count"] != 0)
    if with_errors:
        raise RecordCheckpointError(
            f"{source}: error_count must be 0; fix the run before recording: {with_errors}"
        )
    return sorted(coerced, key=lambda row: (row["year"], row["country"]))


def load_rows(input_path: Path, year: int) -> list[dict]:
    """Read one checkpoint year from a JSON list or a CSV table."""

    if not input_path.is_file():
        raise RecordCheckpointError(f"input does not exist: {input_path}")
    suffix = input_path.suffix.lower()
    if suffix == ".json":
        data = json.loads(input_path.read_text("utf-8"))
        if isinstance(data, dict):
            data = data.get("checkpoints")
        if not isinstance(data, list):
            raise RecordCheckpointError(f"{input_path}: expected a JSON list of checkpoint rows")
        return validate_rows(data, year, str(input_path))
    if suffix == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise RecordCheckpointError(f"{input_path}: empty CSV")
            headers = [name.strip() for name in reader.fieldnames]
            unknown = [name for name in headers if name not in CSV_COLUMNS]
            if unknown:
                raise RecordCheckpointError(f"{input_path}: unknown CSV columns: {unknown}")
            rows = []
            for record in reader:
                row = {key.strip(): value for key, value in record.items() if key is not None}
                row.pop("year", None)
                row["year"] = year
                rows.append(row)
        return validate_rows(rows, year, str(input_path))
    raise RecordCheckpointError(f"{input_path}: unsupported input format (use .json or .csv)")


def _load_existing(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text("utf-8"))
    if isinstance(data, dict):
        data = data.get("checkpoints")
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise RecordCheckpointError(f"{path}: expected a JSON list of checkpoint rows")
    return list(data)


def merge_rows(existing: list[dict], new_rows: list[dict], replace: bool) -> list[dict]:
    """Merge one year into the run's rows, keeping one row per year/country.

    Already recorded year/country pairs are only overwritten with --replace, so
    real evidence cannot be silently replaced by a later export.
    """

    new_pairs = {(row["year"], row["country"]) for row in new_rows}
    overlaps = sorted(
        f"{year} {country}"
        for year, country in {
            (row.get("year"), row.get("country")) for row in existing
        }
        & new_pairs
    )
    if overlaps and not replace:
        raise RecordCheckpointError(
            "already recorded (use --replace to overwrite): " + ", ".join(overlaps)
        )
    kept = [
        row
        for row in existing
        if (row.get("year"), row.get("country")) not in new_pairs
    ]
    merged = kept + new_rows
    merged.sort(key=lambda row: (int(row["year"]), str(row["country"])))
    return merged


def missing_pairs(rows: list[dict]) -> list[tuple[int, str]]:
    present = {(row.get("year"), row.get("country")) for row in rows}
    return [
        (year, country)
        for year in CHECKPOINT_YEARS
        for country in CORE_COUNTRIES
        if (year, country) not in present
    ]


def emit_template(path: Path, year: int) -> None:
    """Write an empty checkpoint CSV skeleton for one year.

    Only the year and country columns are filled: leaving the measured columns
    empty means a forgotten value fails validation loudly instead of being
    accepted as a placeholder.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(CSV_COLUMNS)]
    for country in CORE_COUNTRIES:
        lines.append(f"{year},{country},,,,,")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def finalize_run(
    run_json_path: Path,
    checkpoint_path: Path,
    campaign: str,
    logs_path: Path,
    observed_seed: int | None,
    screenshot_path: Path | None,
) -> dict:
    """Promote a fully recorded run to `observed_to_checkpoint`.

    Only the fields the gate requires the operator to confirm are written; DLC
    and mount evidence must already be in `run.json` from the launcher step, so
    a preload-only run can never be promoted here.
    """

    if not run_json_path.is_file():
        raise RecordCheckpointError(f"run metadata does not exist: {run_json_path}")
    metadata = json.loads(run_json_path.read_text("utf-8"))
    if not isinstance(metadata, dict):
        raise RecordCheckpointError(f"{run_json_path}: expected an object")
    rows = _load_existing(checkpoint_path)
    gaps = missing_pairs(rows)
    if gaps:
        raise RecordCheckpointError(
            f"{checkpoint_path}: {len(gaps)} of 30 checkpoint records are still missing"
        )
    try:
        validate_checkpoint_rows(checkpoint_path, rows)
    except ValueError as error:
        raise RecordCheckpointError(str(error)) from error
    if not campaign.strip():
        raise RecordCheckpointError("--campaign must describe the real campaign session")
    if not logs_path.is_file():
        raise RecordCheckpointError(f"log evidence does not exist: {logs_path}")
    if metadata.get("mod_mount") != "mounted":
        raise RecordCheckpointError(
            f"{run_json_path}: mod_mount is {metadata.get('mod_mount')!r}; launcher mount evidence is required first"
        )
    if metadata.get("dlc_state_matches_config") != "yes":
        raise RecordCheckpointError(
            f"{run_json_path}: dlc_state_matches_config is {metadata.get('dlc_state_matches_config')!r}; record the real DLC set first"
        )
    if observed_seed is not None and observed_seed not in SEEDS:
        raise RecordCheckpointError(f"observed seed must be one of {list(SEEDS)}")

    metadata["status"] = "observed_to_checkpoint"
    metadata["observed_seed"] = observed_seed
    evidence = metadata.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}
    evidence["campaign"] = campaign.strip()
    evidence["logs"] = str(logs_path)
    evidence["checkpoint_file"] = str(checkpoint_path)
    evidence["run_metadata"] = str(run_json_path)
    if observed_seed is not None:
        evidence["observed_seed"] = observed_seed
    if screenshot_path is not None:
        if not screenshot_path.is_file():
            raise RecordCheckpointError(f"screenshot evidence does not exist: {screenshot_path}")
        evidence["screenshot"] = str(screenshot_path)
    metadata["evidence"] = evidence
    try:
        validate_run_metadata(run_json_path, metadata)
    except ValueError as error:
        raise RecordCheckpointError(str(error)) from error
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/observe"))
    parser.add_argument("--config", choices=sorted(CONFIGS), required=True)
    parser.add_argument("--seed", type=int, choices=sorted(SEEDS), required=True)
    parser.add_argument("--year", type=int, choices=list(CHECKPOINT_YEARS))
    parser.add_argument("--input", type=Path, help="JSON list or CSV of ten country rows")
    parser.add_argument(
        "--emit-template",
        type=Path,
        help="write an empty CSV skeleton for --year and exit",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="overwrite already recorded rows for the supplied year",
    )
    parser.add_argument("--finalize", action="store_true", help="promote a complete run")
    parser.add_argument("--campaign", help="non-empty description of the real campaign session")
    parser.add_argument("--logs", type=Path, help="existing debug.log for the finalized run")
    parser.add_argument("--observed-seed", type=int, choices=sorted(SEEDS))
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()

    run_root = args.root / args.config / str(args.seed)
    checkpoint_path = run_root / "checkpoints.json"
    run_json_path = run_root / "run.json"

    try:
        if args.emit_template is not None:
            if args.year is None:
                raise RecordCheckpointError("--emit-template requires --year")
            emit_template(args.emit_template, args.year)
            print(f"Wrote checkpoint template: {args.emit_template}")
            print("Fill the measured columns, then record it with --input.")
            return 0

        if args.finalize:
            if args.campaign is None or args.logs is None:
                raise RecordCheckpointError("--finalize requires --campaign and --logs")
            metadata = finalize_run(
                run_json_path,
                checkpoint_path,
                args.campaign,
                args.logs,
                args.observed_seed,
                args.screenshot,
            )
            run_json_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(f"Finalized {args.config}/{args.seed}: status=observed_to_checkpoint")
            return 0

        if args.year is None or args.input is None:
            raise RecordCheckpointError("recording a checkpoint requires --year and --input")
        rows = load_rows(args.input, args.year)
        existing = _load_existing(checkpoint_path)
        merged = merge_rows(existing, rows, args.replace)
        run_root.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, RecordCheckpointError) as error:
        print(error)
        return 1

    total = len(CHECKPOINT_YEARS) * len(CORE_COUNTRIES)
    gaps = missing_pairs(merged)
    print(f"Recorded {len(rows)} rows for {args.year} in {checkpoint_path}")
    print(f"checkpoints={len(merged)}/{total} missing={len(gaps)}")
    if not run_json_path.is_file():
        print(f"warning: no run.json beside {checkpoint_path}; launcher evidence is still pending")
    for year, country in gaps[:10]:
        print(f"missing: {year} {country}")
    if len(gaps) > 10:
        print(f"... and {len(gaps) - 10} more")
    if not gaps:
        print("all 30 checkpoint records present; finalize the run with --finalize")
    return 0


if __name__ == "__main__":
    sys.exit(main())
