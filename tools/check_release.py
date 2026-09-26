"""Run the structural release gate without changing game or save data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CONFIGS = {"none", "sphere", "charters", "wave", "all"}
SEEDS = {11, 23, 47}
YEARS = [1846, 1866, 1900]
COUNTRIES = ["SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG"]
GAME_VERSION = "1.13.11 (Matcha)"
EXPECTED_DLC = {
    "none": [],
    "sphere": ["dlc010_ep1"],
    "charters": ["dlc013_mp1"],
    "wave": ["dlc018_ep2"],
    "all": ["dlc010_ep1", "dlc013_mp1", "dlc018_ep2"],
}
CHECKPOINT_NUMERIC_FIELDS = ("population", "wars", "subjects", "error_count")
CHECKPOINT_REQUIRED_FIELDS = {
    "year",
    "country",
    "rank",
    "population",
    "market",
    "wars",
    "subjects",
    "error_count",
}


def _require(run: dict, field: str, errors: list[str], index: int) -> object:
    if field not in run:
        errors.append(f"run {index} missing {field}")
        return None
    return run[field]


def _resolve_evidence_path(matrix_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidates = (Path.cwd() / path, matrix_path.parent / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def check(matrix_path: Path, mod_root: Path) -> list[str]:
    errors: list[str] = []
    if not mod_root.is_dir():
        errors.append(f"mod root does not exist: {mod_root}")
    try:
        data = json.loads(matrix_path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"cannot read matrix: {error}"]
    if data.get("schema_version") != 1:
        errors.append("matrix schema_version must be 1")
    if set(data.get("configs", [])) != CONFIGS:
        errors.append("matrix configs are incomplete")
    runs = data.get("runs")
    if not isinstance(runs, list) or len(runs) != 15:
        errors.append("matrix must contain exactly 15 runs")
        runs = runs if isinstance(runs, list) else []
    identities: set[tuple[object, object]] = set()
    run_ids: set[str] = set()
    expected_identities = {(config, seed) for config in CONFIGS for seed in SEEDS}
    seen_identities: set[tuple[str, int]] = set()
    for index, run in enumerate(runs, 1):
        if not isinstance(run, dict):
            errors.append(f"run {index} is not an object")
            continue
        config = _require(run, "config", errors, index)
        run_id = _require(run, "run_id", errors, index)
        requested_seed = _require(run, "requested_seed", errors, index)
        identity = (config, run_id)
        if identity in identities:
            errors.append(f"duplicate config/run_id in run {index}")
        identities.add(identity)
        if isinstance(config, str) and isinstance(run_id, str):
            full_id = f"{config}/{run_id}"
            if full_id in run_ids:
                errors.append(f"duplicate run_id in run {index}")
            run_ids.add(full_id)
        if config not in CONFIGS:
            errors.append(f"run {index} has unknown config: {config}")
        if requested_seed not in SEEDS:
            errors.append(f"run {index} has invalid requested_seed: {requested_seed}")
        elif config in CONFIGS:
            seen_identities.add((config, requested_seed))
        observed_seed = _require(run, "observed_seed", errors, index)
        if observed_seed is not None and observed_seed not in SEEDS:
            errors.append(f"run {index} has invalid observed_seed")
        if run.get("status") != "verified":
            errors.append(f"run {index} is not verified: {run.get('status')}")
        if run.get("checkpoint_years") != YEARS:
            errors.append(f"run {index} has invalid checkpoint years")
        if run.get("checkpoint_count") != 30:
            errors.append(f"run {index} must contain 30 checkpoints")
        if sorted(run.get("countries", [])) != sorted(COUNTRIES):
            errors.append(f"run {index} does not contain all ten countries")
        if not isinstance(run.get("source"), str) or not run["source"]:
            errors.append(f"run {index} missing checkpoint source")
        version_match_evidence = run.get("version_match_evidence")
        if (
            not isinstance(version_match_evidence, list)
            or not any(isinstance(item, str) and item.strip() for item in version_match_evidence)
        ):
            errors.append(f"run {index} missing version-match evidence")
        evidence = run.get("evidence")
        if not isinstance(evidence, dict) or not evidence:
            errors.append(f"run {index} missing evidence")
        else:
            campaign = evidence.get("campaign")
            if not isinstance(campaign, str) or not campaign.strip():
                errors.append(f"run {index} missing campaign evidence")
            elif campaign == "not_recorded_until_campaign_checkpoint_export":
                errors.append(f"run {index} has preload-only campaign evidence")
            resolved_paths: dict[str, Path] = {}
            for field in ("logs", "checkpoint_file", "run_metadata"):
                value = evidence.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"run {index} missing evidence path {field}")
                    continue
                resolved = _resolve_evidence_path(matrix_path, value)
                if not resolved.is_file():
                    errors.append(f"run {index} evidence path does not exist: {field}={value}")
                else:
                    resolved_paths[field] = resolved
            metadata_path = resolved_paths.get("run_metadata")
            if metadata_path is not None:
                try:
                    metadata = json.loads(metadata_path.read_text("utf-8"))
                except (OSError, json.JSONDecodeError) as error:
                    errors.append(f"run {index} run metadata is not valid JSON: {error}")
                else:
                    if not isinstance(metadata, dict):
                        errors.append(f"run {index} run metadata is not an object")
                    else:
                        for field in (
                            "config",
                            "run_id",
                            "requested_seed",
                            "observed_seed",
                            "game_version",
                            "mod_mount",
                            "version_match_evidence",
                            "expected_mounted_dlc",
                            "observed_mounted_dlc",
                            "dlc_state_matches_config",
                        ):
                            if metadata.get(field) != run.get(field):
                                errors.append(f"run {index} run metadata {field} does not match")
                        if metadata.get("version_match_evidence") != run.get("version_match_evidence"):
                            errors.append(f"run {index} run metadata version_match_evidence does not match")
                        if metadata.get("status") != "observed_to_checkpoint":
                            errors.append(f"run {index} run metadata is not an observed checkpoint")
            checkpoint_path = resolved_paths.get("checkpoint_file")
            if checkpoint_path is not None:
                if run.get("source") != evidence.get("checkpoint_file"):
                    errors.append(f"run {index} checkpoint source does not match evidence")
                try:
                    checkpoint_data = json.loads(checkpoint_path.read_text("utf-8"))
                except (OSError, json.JSONDecodeError) as error:
                    errors.append(f"run {index} checkpoint evidence is not valid JSON: {error}")
                else:
                    rows = checkpoint_data
                    if isinstance(checkpoint_data, dict):
                        rows = checkpoint_data.get("checkpoints")
                    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                        errors.append(f"run {index} checkpoint evidence is not a list of objects")
                    elif len(rows) != 30:
                        errors.append(f"run {index} checkpoint evidence must contain 30 rows")
                    else:
                        for row_number, row in enumerate(rows, 1):
                            missing_fields = CHECKPOINT_REQUIRED_FIELDS - set(row)
                            if missing_fields:
                                errors.append(
                                    f"run {index} checkpoint evidence row {row_number} missing {', '.join(sorted(missing_fields))}"
                                )
                                continue
                            for field in CHECKPOINT_NUMERIC_FIELDS:
                                value = row.get(field)
                                if isinstance(value, bool) or not isinstance(value, int):
                                    errors.append(
                                        f"run {index} checkpoint evidence row {row_number} {field} must be a non-negative integer"
                                    )
                                elif value < 0:
                                    errors.append(
                                        f"run {index} checkpoint evidence row {row_number} negative {field}"
                                    )
                            if row.get("error_count") != 0:
                                errors.append(
                                    f"run {index} checkpoint evidence row {row_number} error_count must be 0"
                                )
                        pairs = {(row.get("year"), row.get("country")) for row in rows}
                        years = sorted({row.get("year") for row in rows})
                        countries = sorted({row.get("country") for row in rows})
                        if len(pairs) != 30:
                            errors.append(f"run {index} checkpoint evidence has duplicate year/country pairs")
                        if years != YEARS:
                            errors.append(f"run {index} checkpoint evidence has invalid years")
                        if countries != sorted(COUNTRIES):
                            errors.append(f"run {index} checkpoint evidence does not cover all ten countries")
        if (
            run.get("observed_seed") is not None
            and isinstance(evidence, dict)
            and evidence.get("observed_seed") != run.get("observed_seed")
        ):
            errors.append(f"run {index} observed_seed lacks matching evidence")
        if run.get("game_version") != GAME_VERSION:
            errors.append(f"run {index} has incompatible game version")
        if run.get("mod_mount") != "mounted":
            errors.append(f"run {index} does not prove the Mod is mounted")
        if run.get("expected_mounted_dlc") != EXPECTED_DLC.get(config):
            errors.append(f"run {index} has invalid expected DLC evidence")
        if run.get("observed_mounted_dlc") != EXPECTED_DLC.get(config):
            errors.append(f"run {index} has invalid observed DLC evidence")
        if run.get("dlc_state_matches_config") != "yes":
            errors.append(f"run {index} DLC evidence does not match config")
    if seen_identities != expected_identities:
        errors.append("matrix must contain every config/requested_seed combination exactly once")
    declared_ids = data.get("run_ids")
    if not isinstance(declared_ids, list) or set(declared_ids) != run_ids or len(declared_ids) != len(run_ids):
        errors.append("matrix run_ids do not match the run records")
    if "seeds" in data and set(data["seeds"]) != SEEDS:
        errors.append("matrix seeds are incomplete")
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
