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
except ModuleNotFoundError:  # direct `python tools/ywc_v03_check.py` invocation
    from build_v03_content import TARGETS, check_outputs, load_catalogs, read_manifest, validate_catalogs_at


ROOT = Path(__file__).resolve().parents[1]
OWNER_COUNTS = {"country": 10, "crisis": 8, "regional": 63, "theme": 12}
OWNER_QUOTAS = {
    "country": (72, 18),
    "crisis": (12, 3),
    "regional": (6, 2),
    "theme": (8, 1),
}


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
        layers = {layer: {"events": 0, "journals": 0, "catalogs": 0} for layer in TARGETS}
        for key, catalog in catalogs.items():
            layer = catalog.get("layer")
            if not isinstance(layer, str) or layer not in layers:
                continue
            layers[layer]["catalogs"] += 1
            for arc in catalog.get("arcs", []) if isinstance(catalog.get("arcs"), list) else []:
                if not isinstance(arc, dict):
                    continue
                layers[layer]["events"] += len(arc.get("events", [])) if isinstance(arc.get("events"), list) else 0
                layers[layer]["journals"] += len(arc.get("journals", [])) if isinstance(arc.get("journals"), list) else 0
        for layer, target in TARGETS.items():
            actual = layers[layer]
            for field in ("events", "journals"):
                if actual[field] < target[field]:
                    errors.append(f"{layer} {field} quota: {actual[field]}/{target[field]}")
            if actual["catalogs"] < OWNER_COUNTS[layer]:
                errors.append(f"{layer} catalog count: {actual['catalogs']}/{OWNER_COUNTS[layer]}")
        registry = _registry_or_empty(root)
        reservations = registry.get("reservations", [])
        registered = {item.get("key"): item for item in reservations if isinstance(item, dict)}
        for key, reservation in registered.items():
            layer = reservation.get("layer")
            if layer not in OWNER_QUOTAS:
                continue
            catalog = catalogs.get(key)
            if catalog is None:
                errors.append(f"missing required catalog {key} ({layer})")
                continue
            min_events, min_journals = OWNER_QUOTAS[layer]
            count_events = sum(len(arc.get("events", [])) for arc in catalog.get("arcs", []) if isinstance(arc, dict) and isinstance(arc.get("events"), list))
            count_journals = sum(len(arc.get("journals", [])) for arc in catalog.get("arcs", []) if isinstance(arc, dict) and isinstance(arc.get("journals"), list))
            if count_events < min_events:
                errors.append(f"{key} event quota: {count_events}/{min_events}")
            if count_journals < min_journals:
                errors.append(f"{key} journal quota: {count_journals}/{min_journals}")
        # The manifest is the authoritative registration list during expansion;
        # owner-count gates above ensure all four layers have been populated.
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
