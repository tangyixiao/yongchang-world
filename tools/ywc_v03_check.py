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
CANONICAL_COUNTRY_ERAS = ("foundation", "middle", "late")

# Protocol and menu definitions created to operate existing arcs. Keep this
# independent requirement in sync with the documented data-file decisions so
# dropping a known row cannot silently increase release quota counts.
KNOWN_OPERATIONAL_EVENT_IDS = frozenset({
    "ywc_jhg.1030", "ywc_kor.1030", "ywc_kor.1031", "ywc_kor.1033", "ywc_kor.1034",
    "ywc_nmg.1030", "ywc_nmg.1032", "ywc_nmg.1033", "ywc_nqg.1028", "ywc_nqg.1030", "ywc_nqg.1031",
})


def check_complete_quotas(catalogs: dict[str, dict], excluded_event_ids: set[str] | None = None) -> list[str]:
    """Count visible, nonexcluded definitions; narrative quality still needs review."""
    excluded = excluded_event_ids or set()
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
            row[0] += sum(isinstance(event, dict) and event.get("hidden") is not True
                          and (not isinstance(event.get("id"), str) or event["id"] not in excluded)
                          for event in arc.get("events", [])) if isinstance(arc.get("events"), list) else 0
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
        unrecognized = sorted(set(eras) - set(CANONICAL_COUNTRY_ERAS))
        if unrecognized:
            errors.append(f"country owner {owner} has unrecognized era {', '.join(unrecognized)}")
        for era in CANONICAL_COUNTRY_ERAS:
            count = eras.get(era, 0)
            if count < 3:
                errors.append(f"country owner {owner} era {era} arc quota: {count}/3")
        if set(CANONICAL_COUNTRY_ERAS) - set(eras):
            errors.append(f"country owner {owner} must cover canonical eras foundation, middle, late")
    return errors


def read_quota_exclusions(root: Path, catalogs: dict[str, dict], *, required: bool = False) -> tuple[set[str], list[str]]:
    """Read reviewed operational exclusions and verify them against live events."""
    path = Path(root) / "data/content/v03/quota_exclusions.json"
    if not path.is_file():
        return (set(), [f"{path}: quota_exclusions.json is missing"] if required else [])
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key}")
            result[key] = value
        return result

    try:
        document = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (OSError, UnicodeError, ValueError) as error:
        return set(), [f"{path}: invalid quota_exclusions JSON: {error}"]
    if not isinstance(document, dict) or set(document) != {"schema_version", "exclusions"}:
        return set(), [f"{path}: quota_exclusions must contain schema_version and exclusions"]
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        return set(), [f"{path}: quota_exclusions schema_version must be 1"]
    if not isinstance(document["exclusions"], list):
        return set(), [f"{path}: quota_exclusions exclusions must be a list"]

    events: dict[str, dict] = {}
    for catalog in catalogs.values():
        if not isinstance(catalog, dict):
            continue
        arcs = catalog.get("arcs", [])
        for arc in arcs if isinstance(arcs, list) else []:
            if not isinstance(arc, dict):
                continue
            entries = arc.get("events", [])
            for event in entries if isinstance(entries, list) else []:
                if isinstance(event, dict) and isinstance(event.get("id"), str):
                    events[event["id"]] = event

    excluded: set[str] = set()
    errors: list[str] = []
    for index, row in enumerate(document["exclusions"]):
        where = f"{path}: quota_exclusions[{index}]"
        if not isinstance(row, dict) or set(row) != {"event_id", "reason"}:
            errors.append(f"{where} must contain event_id and reason")
            continue
        event_id, reason = row["event_id"], row["reason"]
        if not isinstance(event_id, str) or not event_id.strip() or not isinstance(reason, str) or not reason.strip():
            errors.append(f"{where} requires a nonempty event_id and reason")
            continue
        if event_id in excluded:
            errors.append(f"{where} duplicates {event_id}")
            continue
        excluded.add(event_id)
        if event_id not in events:
            errors.append(f"{where} references unknown event {event_id}")
        elif events[event_id].get("hidden") is True:
            errors.append(f"{where} references hidden event {event_id}, already excluded")
    required_ids = {event_id for event_id in KNOWN_OPERATIONAL_EVENT_IDS
                    if event_id in events and events[event_id].get("hidden") is not True}
    for event_id in sorted(required_ids - excluded):
        errors.append(f"{path}: quota_exclusions is missing known operational event {event_id}")
    return excluded, errors


def check_root(root: Path, require_complete: bool = False) -> list[str]:
    root = Path(root)
    try:
        manifest = read_manifest(root)
        catalogs = load_catalogs(root)
    except ValueError as exc:
        return [str(exc)]
    errors = validate_catalogs_at(root, catalogs)
    errors.extend(check_outputs(root))
    exclusions, exclusion_errors = read_quota_exclusions(root, catalogs, required=require_complete)
    errors.extend(exclusion_errors)
    if require_complete:
        errors.extend(check_complete_quotas(catalogs, exclusions))
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
