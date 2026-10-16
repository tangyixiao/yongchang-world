"""Static schema, ownership and quota checker for the v0.3 content pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from tools.build_v03_content import (
        TARGETS,
        check_outputs,
        load_catalogs,
        read_manifest,
        validate_catalogs_at,
    )
    from tools.v03_owners import EXPECTED_OWNERS, arc_owner
except ModuleNotFoundError:  # direct `python tools/ywc_v03_check.py` invocation
    from build_v03_content import TARGETS, check_outputs, load_catalogs, read_manifest, validate_catalogs_at
    from v03_owners import EXPECTED_OWNERS, arc_owner


ROOT = Path(__file__).resolve().parents[1]
OWNER_QUOTAS = {
    "country": (72, 18),
    "crisis": (12, 3),
    "regional": (6, 2),
    "theme": (8, 1),
}


def check_complete_quotas(catalogs: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    counts = {layer: {owner: [0, 0] for owner in owners} for layer, owners in EXPECTED_OWNERS.items()}
    country_eras = {owner: {} for owner in EXPECTED_OWNERS["country"]}
    for catalog in catalogs.values():
        if not isinstance(catalog, dict):
            continue
        layer, tags = catalog.get("layer"), catalog.get("runtime_tags")
        if layer not in counts:
            continue
        for arc in catalog.get("arcs", []) if isinstance(catalog.get("arcs"), list) else []:
            if not isinstance(arc, dict):
                continue
            owner = arc_owner(layer, arc, tags)
            if owner not in counts[layer]:
                continue
            row = counts[layer][owner]
            row[0] += len(arc.get("events", [])) if isinstance(arc.get("events"), list) else 0
            row[1] += len(arc.get("journals", [])) if isinstance(arc.get("journals"), list) else 0
            if layer == "country":
                era = arc.get("era")
                if isinstance(era, str):
                    country_eras[owner][era] = country_eras[owner].get(era, 0) + 1
    for layer, owners in counts.items():
        min_events, min_journals = OWNER_QUOTAS[layer]
        for owner, (events, journals) in owners.items():
            if events < min_events:
                errors.append(f"{layer} owner {owner} event quota: {events}/{min_events}")
            if journals < min_journals:
                errors.append(f"{layer} owner {owner} journal quota: {journals}/{min_journals}")
            if layer == "country" and sum(country_eras[owner].values()) < 9:
                errors.append(f"country owner {owner} arc quota: {sum(country_eras[owner].values())}/9")
    for owner, eras in country_eras.items():
        if len(eras) < 3 or any(count < 3 for count in eras.values()):
            errors.append(f"country owner {owner} must cover three eras with three arcs each")
    return errors


def check_root(root: Path, require_complete: bool = False) -> list[str]:
    root = Path(root)
    try:
        manifest = read_manifest(root)
        catalogs = load_catalogs(root)
    except ValueError as exc:
        return [str(exc)]
    errors = validate_catalogs_at(root, catalogs)
    errors.extend(check_outputs(root))
    if require_complete:
        errors.extend(check_complete_quotas(catalogs))
        del manifest
    return errors


def _registry_or_empty(root: Path) -> dict:
    path = root / "data/content/v03/id_registry.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    errors = check_root(args.root, require_complete=args.require_complete)
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    elif errors:
        print("\n".join(errors), file=sys.stderr)
    else:
        print("v0.3 catalogs and generated outputs are valid")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
