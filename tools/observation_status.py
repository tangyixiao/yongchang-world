"""Report how much of the 15-run observation matrix is really recorded.

The matrix is 5 configurations x 3 seeds, and every run needs 30 checkpoint
records (1846/1866/1900 x ten countries) plus launcher mount and DLC evidence
before the release gate can pass. This tool reads the recorded files and shows
what is still missing; it never edits a run and never upgrades a status.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Running `python tools/observation_status.py` puts the tools/ directory on
# sys.path rather than the repository root, so the shared observation schema in
# the tools package has to be made importable explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.summarize_observation import (  # noqa: E402
    CHECKPOINT_YEARS,
    CONFIGS,
    CORE_COUNTRIES,
    SEEDS,
    validate_checkpoint_rows,
    validate_run_metadata,
)

EXPECTED_ROWS = len(CHECKPOINT_YEARS) * len(CORE_COUNTRIES)
FINALIZED_STATUSES = {"observed_to_checkpoint"}


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _checkpoint_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        data = data.get("checkpoints")
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def inspect_run(root: Path, config: str, seed: int) -> dict:
    run_root = root / config / str(seed)
    run_json = run_root / "run.json"
    checkpoint_path = run_root / "checkpoints.json"
    metadata = _read_json(run_json)
    rows = _checkpoint_rows(checkpoint_path)
    pairs = {(row.get("year"), row.get("country")) for row in rows}
    expected_pairs = {
        (year, country)
        for year in CHECKPOINT_YEARS
        for country in CORE_COUNTRIES
    }
    missing = [
        f"{year} {country}"
        for year in CHECKPOINT_YEARS
        for country in CORE_COUNTRIES
        if (year, country) not in pairs
    ]
    mismatched = sorted(
        {
            f"{row.get('year')} {row.get('country')}"
            for row in rows
            if (row.get("year"), row.get("country")) not in expected_pairs
        }
    )
    validation_errors = []
    if checkpoint_path.is_file():
        try:
            validate_checkpoint_rows(checkpoint_path, rows)
        except ValueError as error:
            validation_errors.append(str(error))
    if run_json.is_file() and metadata is not None:
        try:
            validate_run_metadata(run_json, metadata)
        except ValueError as error:
            validation_errors.append(str(error))
    error_rows = sorted(
        f"{row.get('year')} {row.get('country')}"
        for row in rows
        if isinstance(row.get("error_count"), int) and row["error_count"] != 0
    )
    status = metadata.get("status") if metadata else None
    ready = (
        metadata is not None
        and status in FINALIZED_STATUSES
        and not missing
        and not validation_errors
        and not error_rows
        and metadata.get("mod_mount") == "mounted"
        and metadata.get("dlc_state_matches_config") == "yes"
    )
    return {
        "config": config,
        "seed": seed,
        "run_id": f"run-{seed}",
        "directory": str(run_root),
        "run_json": run_json.is_file(),
        "checkpoint_file": checkpoint_path.is_file(),
        "status": status or "no_run_metadata",
        "mod_mount": metadata.get("mod_mount") if metadata else None,
        "dlc_state_matches_config": metadata.get("dlc_state_matches_config") if metadata else None,
        "recorded": len(pairs),
        "expected": EXPECTED_ROWS,
        "missing_years": sorted({str(row.get("year")) for row in rows if row.get("year") not in CHECKPOINT_YEARS}),
        "error_rows": error_rows,
        "ready_for_summary": ready,
        "missing": missing,
        "mismatched": mismatched,
        "validation_errors": validation_errors,
    }


def inspect_matrix(root: Path) -> dict:
    runs = [inspect_run(root, config, seed) for config in CONFIGS for seed in SEEDS]
    return {
        "root": str(root),
        "expected_runs": len(runs),
        "recorded_rows": sum(run["recorded"] for run in runs),
        "expected_rows": EXPECTED_ROWS * len(runs),
        "ready_runs": [f"{run['config']}/{run['seed']}" for run in runs if run["ready_for_summary"]],
        "runs": runs,
    }


def _format_table(report: dict) -> str:
    header = f"{'config/seed':<16}{'status':<24}{'rows':<8}{'mount':<10}{'dlc':<6}ready"
    lines = [header, "-" * len(header)]
    for run in report["runs"]:
        lines.append(
            f"{run['config'] + '/' + str(run['seed']):<16}"
            f"{str(run['status']):<24}"
            f"{str(run['recorded']) + '/' + str(run['expected']):<8}"
            f"{str(run['mod_mount'] or '-'):<10}"
            f"{str(run['dlc_state_matches_config'] or '-'):<6}"
            f"{'yes' if run['ready_for_summary'] else 'no'}"
        )
    lines.append("")
    lines.append(
        f"recorded {report['recorded_rows']}/{report['expected_rows']} checkpoint rows; "
        f"{len(report['ready_runs'])}/{report['expected_runs']} runs ready for summarize_observation.py"
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/observe"))
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args()
    if not args.root.is_dir():
        print(f"observation root does not exist: {args.root}")
        return 1
    report = inspect_matrix(args.root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_format_table(report))
        for run in report["runs"]:
            if run["missing"]:
                preview = ", ".join(run["missing"][:3])
                more = len(run["missing"]) - 3
                suffix = f", +{more} more" if more > 0 else ""
                print(f"  {run['config']}/{run['seed']}: missing {len(run['missing'])} ({preview}{suffix})")
            if run["error_rows"]:
                print(f"  {run['config']}/{run['seed']}: non-zero error_count on {len(run['error_rows'])} rows")
            for error in run["validation_errors"]:
                print(f"  {run['config']}/{run['seed']}: invalid checkpoints: {error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
