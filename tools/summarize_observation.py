"""Validate real Victoria 3 observation checkpoints and build one schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CORE_COUNTRIES = ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG")
CONFIGS = ("none", "sphere", "charters", "wave", "all")
SEEDS = (11, 23, 47)
GAME_VERSION = "1.13.11 (Matcha)"
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
CHECKPOINT_YEARS = (1846, 1866, 1900)
EXPECTED_DLC = {
    "none": (),
    "sphere": ("dlc010_ep1",),
    "charters": ("dlc013_mp1",),
    "wave": ("dlc018_ep2",),
    "all": ("dlc010_ep1", "dlc013_mp1", "dlc018_ep2"),
}


def _checkpoint_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.rglob("checkpoints.json"))
    raise ValueError(f"input does not exist: {input_path}")


def _load_json(path: Path) -> object:
    return json.loads(path.read_text("utf-8"))


def _load_rows(path: Path) -> list[dict]:
    data = _load_json(path)
    if isinstance(data, dict):
        data = data.get("checkpoints")
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ValueError(f"{path}: expected a JSON list of checkpoint objects")
    return data


def _require_nonnegative_integer(path: Path, index: int, field: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path}:{index}: {field} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{path}:{index}: negative {field}")
    return value


def validate_checkpoint_rows(path: Path, rows: list[dict]) -> tuple[list[int], list[str]]:
    """Validate the canonical 30-row observation checkpoint schema.

    Status, recording, and final release tools share this function so a run
    cannot be considered ready by one layer and rejected as malformed by the
    next.
    """
    if len(rows) != len(CHECKPOINT_YEARS) * len(CORE_COUNTRIES):
        raise ValueError(f"{path}: expected 30 unique checkpoints, got {len(rows)}")
    pairs = [(row.get("year"), row.get("country")) for row in rows]
    if len(set(pairs)) != len(pairs):
        raise ValueError(f"{path}: checkpoints must contain 30 unique year/country pairs")
    for index, row in enumerate(rows, 1):
        missing = REQUIRED_FIELDS - set(row)
        if missing:
            raise ValueError(f"{path}:{index}: missing fields: {sorted(missing)}")
        if row["country"] not in CORE_COUNTRIES:
            raise ValueError(f"{path}:{index}: unknown country {row['country']}")
        if isinstance(row["year"], bool) or not isinstance(row["year"], int):
            raise ValueError(f"{path}:{index}: year must be an integer")
        _require_nonnegative_integer(path, index, "population", row["population"])
        _require_nonnegative_integer(path, index, "wars", row["wars"])
        _require_nonnegative_integer(path, index, "subjects", row["subjects"])
        error_count = _require_nonnegative_integer(path, index, "error_count", row["error_count"])
        if error_count > 0:
            raise ValueError(f"{path}:{index}: error_count > 0")
        if "capital_count" in row and row["capital_count"] != 1:
            raise ValueError(f"{path}:{index}: multiple capitals")
        if "capitals" in row and (not isinstance(row["capitals"], list) or len(row["capitals"]) != 1):
            raise ValueError(f"{path}:{index}: multiple capitals")
    years = sorted({row["year"] for row in rows})
    countries = sorted({row["country"] for row in rows})
    if years != list(CHECKPOINT_YEARS):
        raise ValueError(f"{path}: checkpoint years must be {list(CHECKPOINT_YEARS)}")
    if countries != sorted(CORE_COUNTRIES):
        raise ValueError(f"{path}: checkpoint countries must contain all ten core countries")
    return years, countries


def validate_run_metadata(run_path: Path, metadata: dict) -> dict:
    """Validate the evidence contract shared by status and release tools."""
    required = {
        "config",
        "run_id",
        "requested_seed",
        "observed_seed",
        "status",
        "game_version",
        "mod_mount",
        "version_match_evidence",
        "expected_mounted_dlc",
        "observed_mounted_dlc",
        "dlc_state_matches_config",
        "evidence",
    }
    missing = required - set(metadata)
    if missing:
        raise ValueError(f"{run_path}: missing evidence fields: {sorted(missing)}")
    config = metadata["config"]
    if config not in CONFIGS:
        raise ValueError(f"{run_path}: unknown config {config}")
    if metadata["requested_seed"] not in SEEDS:
        raise ValueError(f"{run_path}: requested_seed must be one of {list(SEEDS)}")
    if metadata["status"] != "observed_to_checkpoint":
        raise ValueError(f"{run_path}: status is not an observed checkpoint run")
    if metadata["game_version"] != GAME_VERSION:
        raise ValueError(f"{run_path}: game version must be {GAME_VERSION}")
    if metadata["mod_mount"] != "mounted":
        raise ValueError(f"{run_path}: mod is not mounted")
    if not metadata["version_match_evidence"]:
        raise ValueError(f"{run_path}: missing version-match evidence")
    if tuple(metadata["expected_mounted_dlc"]) != EXPECTED_DLC[config]:
        raise ValueError(f"{run_path}: expected DLC evidence does not match config")
    if tuple(metadata["observed_mounted_dlc"]) != EXPECTED_DLC[config]:
        raise ValueError(f"{run_path}: observed DLC evidence does not match config")
    if metadata["dlc_state_matches_config"] != "yes":
        raise ValueError(f"{run_path}: DLC state does not match config")
    if not isinstance(metadata["evidence"], dict) or not metadata["evidence"]:
        raise ValueError(f"{run_path}: missing campaign evidence")
    campaign_evidence = metadata["evidence"].get("campaign")
    if not isinstance(campaign_evidence, str) or not campaign_evidence.strip():
        raise ValueError(f"{run_path}: campaign evidence must be non-empty text")
    if campaign_evidence == "not_recorded_until_campaign_checkpoint_export":
        raise ValueError(f"{run_path}: preload metadata cannot be used as campaign evidence")
    if metadata["observed_seed"] is not None:
        if metadata["observed_seed"] not in SEEDS:
            raise ValueError(f"{run_path}: observed_seed is not one of {list(SEEDS)}")
        if metadata["evidence"].get("observed_seed") != metadata["observed_seed"]:
            raise ValueError(f"{run_path}: observed_seed lacks matching evidence")
    return metadata


def _load_run(path: Path) -> dict:
    run_path = path.parent / "run.json"
    if not run_path.is_file():
        raise ValueError(f"{path}: missing run.json evidence")
    metadata = _load_json(run_path)
    if not isinstance(metadata, dict):
        raise ValueError(f"{run_path}: expected an object")
    return validate_run_metadata(run_path, metadata)


def summarize(input_path: Path) -> dict:
    files = _checkpoint_files(input_path)
    if not files:
        raise ValueError(f"{input_path}: no checkpoints.json files found")
    runs = []
    identities: set[tuple[str, str]] = set()
    for path in files:
        rows = _load_rows(path)
        years, countries = validate_checkpoint_rows(path, rows)
        metadata = _load_run(path)
        identity = (metadata["config"], metadata["run_id"])
        if identity in identities:
            raise ValueError(f"duplicate config/run_id: {metadata['config']}/{metadata['run_id']}")
        identities.add(identity)
        runs.append(
            {
                "config": metadata["config"],
                "run_id": metadata["run_id"],
                "requested_seed": metadata["requested_seed"],
                "observed_seed": metadata["observed_seed"],
                "status": "verified",
                "checkpoint_years": years,
                "checkpoint_count": len(rows),
                "countries": countries,
                "source": str(path),
                "evidence": {
                    **metadata["evidence"],
                    "checkpoint_file": str(path),
                    "run_metadata": str(path.parent / "run.json"),
                },
                "game_version": metadata["game_version"],
                "version_match_evidence": metadata["version_match_evidence"],
                "mod_mount": metadata["mod_mount"],
                "expected_mounted_dlc": metadata["expected_mounted_dlc"],
                "observed_mounted_dlc": metadata["observed_mounted_dlc"],
                "dlc_state_matches_config": metadata["dlc_state_matches_config"],
            }
        )
    runs.sort(key=lambda run: (run["config"], run["run_id"]))
    return {
        "schema_version": 1,
        "configs": sorted({run["config"] for run in runs}),
        "seeds": sorted({run["requested_seed"] for run in runs}),
        "run_ids": [f"{run['config']}/{run['run_id']}" for run in runs],
        "runs": runs,
        "checkpoint_count": sum(run["checkpoint_count"] for run in runs),
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
