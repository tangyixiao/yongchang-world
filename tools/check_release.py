"""Run the structural release gate without changing game or save data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CONFIGS = {"none", "sphere", "charters", "wave", "all"}
SEEDS = {11, 23, 47}
YEARS = [1846, 1866, 1900]
COUNTRIES = ["SHU", "JHG", "DMG", "NQG", "OIR", "MNG", "TIB", "KOR", "LAN", "NMG"]
GAME_VERSION = "1.13.11 (Matcha)"
EXPECTED_DLC = {
    "none": [],
    "sphere": ["dlc010_ep1"],
    "charters": ["dlc013_mp1"],
    "wave": ["dlc018_ep2"],
    "all": ["dlc010_ep1", "dlc013_mp1", "dlc018_ep2"],
}


def _require(run: dict, field: str, errors: list[str], index: int) -> object:
    if field not in run:
        errors.append(f"run {index} missing {field}")
        return None
    return run[field]


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
        if not isinstance(run.get("evidence"), dict) or not run["evidence"]:
            errors.append(f"run {index} missing evidence")
        if run.get("observed_seed") is not None and run.get("evidence", {}).get("observed_seed") != run.get("observed_seed"):
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
