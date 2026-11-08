"""Deterministic renderer for the explicitly registered v0.3 content catalogs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from tools.v03_owners import COUNTRY_NAMESPACES, EXPECTED_OWNERS, NAMESPACE_LIMITS, arc_owner, owner_slot
except ModuleNotFoundError:
    from v03_owners import COUNTRY_NAMESPACES, EXPECTED_OWNERS, NAMESPACE_LIMITS, arc_owner, owner_slot

try:
    from tools.ywc_check import _without_comments_and_strings
except ModuleNotFoundError:
    from ywc_check import _without_comments_and_strings

try:
    from tools.v03_delivery_scheduler import validate_catalogue_adapters, render_country_adapters
    from tools.v03_inline_delivery_adapter import validate_inline_catalog, validate_nqg_native_helper_source, render_inline_country_adapters
except ModuleNotFoundError:
    from v03_delivery_scheduler import validate_catalogue_adapters, render_country_adapters
    from v03_inline_delivery_adapter import validate_inline_catalog, validate_nqg_native_helper_source, render_inline_country_adapters


ROOT = Path(__file__).resolve().parents[1]
V03_DIR = Path("data/content/v03")
LAYERS = {"country", "crisis", "regional", "theme"}
TARGETS = {
    "country": {"events": 720, "journals": 180},
    "crisis": {"events": 96, "journals": 24},
    "regional": {"events": 378, "journals": 126},
    "theme": {"events": 96, "journals": 12},
}
LANGUAGES = {"zh": "simp_chinese", "en": "english"}


def _json_file(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def read_manifest(root: Path) -> dict:
    manifest = _json_file(root / V03_DIR / "manifest.json")
    if manifest.get("schema_version") != 1 or manifest.get("release") != "0.3":
        raise ValueError("manifest must declare schema_version=1 and release='0.3'")
    catalogs = manifest.get("catalogs")
    if not isinstance(catalogs, list) or any(not isinstance(path, str) for path in catalogs):
        raise ValueError("manifest.catalogs must be a list of explicit relative paths")
    if len(catalogs) != len(set(catalogs)):
        raise ValueError("manifest.catalogs contains duplicate paths")
    for relative in catalogs:
        _safe_relative(root, relative, under_v03=True)
    targets = manifest.get("targets")
    if targets != TARGETS:
        raise ValueError("manifest.targets must match the fixed four-layer v0.3 quotas")
    owned = manifest.get("owned_outputs")
    if not isinstance(owned, list) or any(not isinstance(path, str) for path in owned):
        raise ValueError("manifest.owned_outputs must be a list of explicit relative paths")
    if len(owned) != len(set(owned)):
        raise ValueError("manifest.owned_outputs contains duplicate paths")
    for relative in owned:
        _safe_relative(root / "yongchang_world", relative)
        if not _is_output_path(relative):
            raise ValueError(f"owned output is outside v0.3 output areas: {relative}")
    return manifest


def _safe_relative(base: Path, relative: str, *, under_v03: bool = False) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"unsafe path: {relative}")
    resolved_base = base.resolve()
    resolved = (base / candidate).resolve()
    try:
        resolved.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError(f"path escapes root: {relative}") from exc
    if under_v03:
        try:
            resolved.relative_to((base / V03_DIR).resolve())
        except ValueError as exc:
            raise ValueError(f"catalog path must stay under {V03_DIR}: {relative}") from exc
    return resolved


def _is_output_path(relative: str) -> bool:
    path = Path(relative)
    name = path.name
    return (
        path.parent == Path("events") and re.fullmatch(r"ywc_v03_[a-z0-9_]+_events\.txt", name) is not None
    ) or (
        path.parent == Path("common/journal_entries")
        and re.fullmatch(r"ywc_v03_[a-z0-9_]+_journal\.txt", name) is not None
    ) or (
        path.parent in {Path("localization/simp_chinese"), Path("localization/english")}
        and re.fullmatch(r"ywc_v03_[a-z0-9_]+_l_(simp_chinese|english)\.yml", name) is not None
    ) or (
        path.parent in {Path("common/scripted_effects"), Path("common/scripted_triggers")}
        and re.fullmatch(r"ywc_v03_delivery_[a-z0-9_]+_(effects|triggers)\.txt", name) is not None
    )


def load_catalogs(root: Path) -> dict[str, dict]:
    root = Path(root)
    manifest = read_manifest(root)
    catalogs: dict[str, dict] = {}
    for relative in manifest["catalogs"]:
        catalog = _json_file(_safe_relative(root, relative, under_v03=True))
        key = catalog.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError(f"catalog {relative} has no string key")
        if key in catalogs:
            raise ValueError(f"duplicate catalog key: {key}")
        catalogs[key] = catalog
    return catalogs


def _registry(root: Path) -> dict:
    value = _json_file(root / V03_DIR / "id_registry.json")
    if value.get("schema_version") != 1:
        raise ValueError("id_registry must declare schema_version=1")
    return value


def _script_block(value: object, where: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where} must be a non-empty Clausewitz block")
        return False
    raw = value.strip()
    if not (raw.startswith("{") and raw.endswith("}")):
        errors.append(f"{where} must be wrapped in a Clausewitz block")
        return False
    depth = 0
    quoted = False
    escaped = False
    in_comment = False
    for char in raw:
        if in_comment:
            if char == "\n":
                in_comment = False
            continue
        if escaped:
            escaped = False
        elif char == "\\" and quoted:
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif char == "#" and not quoted:
            in_comment = True
        elif not quoted and char == "{":
            depth += 1
        elif not quoted and char == "}":
            depth -= 1
            if depth < 0:
                break
    if depth != 0 or quoted:
        errors.append(f"{where} has unbalanced Clausewitz braces or quotes")
        return False
    cleaned = _without_comments_and_strings(raw)
    for match in re.finditer(r"(?<![A-Za-z0-9_])(AND|OR|NOT|NOR)(?![A-Za-z0-9_])", cleaned):
        if re.match(r"\s*=\s*\{", cleaned[match.end():]) is None:
            errors.append(
                f"{where} uses {match.group(1)} without a Clausewitz logic block; "
                "logic operators must be followed by '= {'"
            )
            return False
    return True


def _localized(value: object, where: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{where} must provide zh and en")
        return
    for language in ("zh", "en"):
        if not isinstance(value.get(language), str) or not value[language].strip():
            errors.append(f"{where}.{language} must be non-empty")
    extra = set(value) - {"zh", "en"}
    if extra:
        errors.append(f"{where} has unknown language fields: {sorted(extra)}")


def validate_catalogs(catalogs: dict[str, dict]) -> list[str]:
    """Validate against this checkout's ID registry; no game script is executed."""
    return validate_catalogs_at(ROOT, catalogs)


def validate_catalogs_at(root: Path, catalogs: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    try:
        registry = _registry(root)
    except ValueError as exc:
        return [str(exc)]
    limits = registry.get("namespace_limits", {})
    if not isinstance(limits, dict):
        limits = {}
        errors.append("id_registry.namespace_limits must be an object")
    reservations = registry.get("reservations", [])
    if set(limits) != LAYERS:
        errors.append(f"id_registry.namespace_limits must declare exactly {sorted(LAYERS)}")
    for layer in LAYERS:
        interval = limits.get(layer, {}) if isinstance(limits, dict) else {}
        if not isinstance(interval, dict) or type(interval.get("start")) is not int or type(interval.get("end")) is not int or interval["start"] > interval["end"]:
            errors.append(f"id_registry has invalid namespace interval for {layer}")
        elif (interval["start"], interval["end"]) != NAMESPACE_LIMITS[layer]:
            errors.append(f"id_registry namespace interval for {layer} must match fixed bounds {NAMESPACE_LIMITS[layer]}")
    if not isinstance(reservations, list):
        return ["id_registry.reservations must be a list"]
    reservations_by_key = {}
    for item in reservations:
        if not isinstance(item, dict):
            errors.append("id_registry.reservations entries must be objects")
            continue
        if set(item) != {"key", "layer", "namespace"}:
            errors.append(f"invalid ID reservation fields for {item.get('key', '<unknown>')}")
        key = item.get("key")
        if not isinstance(key, str) or key in reservations_by_key:
            errors.append(f"duplicate or invalid ID reservation key: {key}")
            continue
        if not isinstance(item.get("layer"), str) or item.get("layer") not in LAYERS or not isinstance(item.get("namespace"), str) or not re.fullmatch(r"ywc_[a-z0-9_]+", item["namespace"]):
            errors.append(f"invalid ID reservation for {key}")
        reservations_by_key[key] = item
    ranges = registry.get("arc_ranges", [])
    if not isinstance(ranges, list):
        return ["id_registry.arc_ranges must be a list"]
    ranges_by_arc = {}
    ranges_by_namespace: dict[str, list[tuple[int, int, str]]] = {}
    for item in ranges:
        if not isinstance(item, dict):
            errors.append("id_registry.arc_ranges entries must be objects")
            continue
        catalog_key, slug = item.get("catalog_key"), item.get("slug")
        if not isinstance(catalog_key, str) or not isinstance(slug, str):
            errors.append("ID arc range catalog_key and slug must be strings")
            continue
        pair = (catalog_key, slug)
        if pair in ranges_by_arc:
            errors.append(f"duplicate ID range for arc {pair[0]}/{pair[1]}")
        ranges_by_arc[pair] = item
        if set(item) != {"catalog_key", "slug", "namespace", "start", "end"}:
            errors.append(f"invalid ID arc range fields for {pair[0]}/{pair[1]}")
        reservation = reservations_by_key.get(pair[0])
        if reservation is None:
            errors.append(f"ID range has no catalog reservation for {pair[0]}")
            continue
        layer = reservation.get("layer")
        interval = limits.get(layer, {}) if isinstance(limits, dict) else {}
        start, end = item.get("start"), item.get("end")
        namespace = item.get("namespace")
        if type(start) is not int or type(end) is not int or start > end:
            errors.append(f"invalid ID arc range bounds for {pair[0]}/{pair[1]}")
            continue
        if not isinstance(namespace, str):
            errors.append(f"invalid ID arc range namespace for {pair[0]}/{pair[1]}")
            continue
        if namespace != reservation.get("namespace"):
            errors.append(f"ID arc range namespace does not match catalog reservation for {pair[0]}/{pair[1]}")
        if isinstance(interval, dict) and not (interval.get("start", 0) <= start <= end <= interval.get("end", -1)):
            errors.append(f"ID arc range outside {layer} namespace bounds for {pair[0]}/{pair[1]}")
        for old_start, old_end, old_slug in ranges_by_namespace.setdefault(namespace, []):
            if start <= old_end and old_start <= end:
                errors.append(f"overlapping ID arc ranges in {namespace}: {old_slug} and {pair[1]}")
        ranges_by_namespace[namespace].append((start, end, f"{pair[0]}/{pair[1]}"))

    all_ids: dict[str, str] = {}
    all_arcs: dict[str, tuple[str, dict]] = {}
    for mapping_key, catalog in catalogs.items():
        where = f"catalog[{mapping_key}]"
        if not isinstance(catalog, dict):
            errors.append(f"{where} must be an object")
            continue
        _fields(catalog, {"key", "layer", "runtime_tags", "arcs"}, where, errors, optional={"delivery_adapter"})
        key = catalog.get("key")
        if any("delivery_adapter" in arc for arc in catalog.get("arcs", [])):
            if key != "country_oir":
                errors.append(f"{where}.delivery_adapter is currently enabled only for country_oir")
            else:
                try:
                    validate_catalogue_adapters(catalog)
                except ValueError as exc:
                    errors.append(f"{where}.delivery_adapter: {exc}")
        if any("inline_delivery_adapter" in arc for arc in catalog.get("arcs", [])):
            if key not in {"country_dmg", "country_kor", "country_nqg", "country_shu"}:
                errors.append(f"{where}.inline_delivery_adapter is not registered for {key}")
            else:
                try:
                    validate_inline_catalog(catalog)
                    if key == "country_nqg":
                        native_effects = _safe_relative(root, "yongchang_world/common/scripted_effects/ywc_v03_nqg_effects.txt")
                        validate_nqg_native_helper_source(catalog, native_effects.read_text(encoding="utf-8"))
                except ValueError as exc:
                    errors.append(f"{where}.inline_delivery_adapter: {exc}")
                except OSError as exc:
                    errors.append(f"{where}.inline_delivery_adapter: cannot read native NQG helper source: {exc}")
        layer = catalog.get("layer")
        if key != mapping_key:
            errors.append(f"{where}.key must match its catalog map key")
        if not isinstance(key, str) or re.fullmatch(r"(country|crisis|regional|theme)_[a-z0-9_]+", key) is None:
            errors.append(f"{where}.key is unsafe or malformed")
        if not isinstance(layer, str) or layer not in LAYERS:
            errors.append(f"{where}.layer must be one of {sorted(LAYERS)}")
        reservation = reservations_by_key.get(key) if isinstance(key, str) else None
        if reservation is None:
            errors.append(f"{where}.key has no explicit id_registry reservation")
        elif reservation.get("layer") != layer:
            errors.append(f"{where}.layer does not match id_registry reservation")
        tags = catalog.get("runtime_tags")
        if not isinstance(tags, list) or not tags or any(not isinstance(tag, str) or not re.fullmatch(r"[A-Z0-9]{2,4}", tag) for tag in tags):
            errors.append(f"{where}.runtime_tags must be a non-empty list of runtime tags")
        arcs = catalog.get("arcs")
        if not isinstance(arcs, list):
            errors.append(f"{where}.arcs must be a list")
            continue
        for index, arc in enumerate(arcs):
            arc_where = f"{where}.arcs[{index}]"
            if not isinstance(arc, dict):
                errors.append(f"{arc_where} must be an object")
                continue
            arc_optional = {"owner"} | ({"delivery_adapter"} if key == "country_oir" else set()) | ({"inline_delivery_adapter"} if key in {"country_dmg", "country_kor", "country_nqg", "country_shu"} else set())
            _fields(arc, {"slug", "era", "participants", "depends_on", "journals", "events", "outcomes", "legacy_links"}, arc_where, errors, optional=arc_optional)
            owner = arc_owner(layer, arc, tags)
            if layer == "country":
                if not isinstance(tags, list) or len(tags) != 1 or owner != (tags[0] if isinstance(tags, list) and len(tags) == 1 else None):
                    errors.append(f"{arc_where}.owner must match the single country runtime_tag")
                elif COUNTRY_NAMESPACES.get(owner) != (reservation or {}).get("namespace"):
                    errors.append(f"{arc_where} country owner {owner} does not match fixed namespace")
            elif owner not in EXPECTED_OWNERS.get(layer, ()):
                errors.append(f"{arc_where}.owner must be one of fixed {layer} owners")
            elif layer == "regional" and (owner not in tags or owner not in arc.get("participants", [])):
                errors.append(f"{arc_where}.owner must be in runtime_tags and participants")
            elif layer in {"crisis", "theme"}:
                expected_namespace = "ywc_crisis" if layer == "crisis" else "ywc_society"
                if (reservation or {}).get("namespace") != expected_namespace:
                    errors.append(f"{arc_where} {layer} reservation must use {expected_namespace}")
            elif layer == "regional" and (reservation or {}).get("namespace") != "ywc_regional":
                errors.append(f"{arc_where} regional reservation must use ywc_regional")
            slot = owner_slot(layer, owner)
            if slot:
                arc_range = ranges_by_arc.get((key, arc.get("slug")))
                if arc_range and not (slot[0] <= arc_range.get("start", -1) <= arc_range.get("end", -1) <= slot[1]):
                    errors.append(f"ID arc range for {key}/{arc.get('slug')} must stay within fixed {layer} owner {owner} slot {slot}")
            slug = arc.get("slug")
            if not isinstance(slug, str) or re.fullmatch(r"[a-z0-9_]+", slug) is None:
                errors.append(f"{arc_where}.slug is unsafe or malformed")
                continue
            if slug in all_arcs:
                errors.append(f"duplicate arc slug: {slug}")
            all_arcs[slug] = (key, arc)
            if not isinstance(arc.get("era"), str) or not arc["era"].strip():
                errors.append(f"{arc_where}.era must be non-empty")
            for field in ("participants", "depends_on", "outcomes", "legacy_links"):
                entries = arc.get(field)
                if not isinstance(entries, list) or any(not isinstance(x, str) or not x for x in entries):
                    errors.append(f"{arc_where}.{field} must be a list of non-empty strings")
            if not isinstance(arc.get("participants"), list) or not arc.get("participants"):
                errors.append(f"{arc_where}.participants cannot be empty")
            for field in ("journals", "events"):
                if not isinstance(arc.get(field), list):
                    errors.append(f"{arc_where}.{field} must be a list")
            for jindex, journal in enumerate(arc.get("journals", []) if isinstance(arc.get("journals"), list) else []):
                _validate_journal(journal, f"{arc_where}.journals[{jindex}]", owner, all_ids, errors)
            for eindex, event in enumerate(arc.get("events", []) if isinstance(arc.get("events"), list) else []):
                _validate_event(event, f"{arc_where}.events[{eindex}]", key, slug, reservation, ranges_by_arc, limits, all_ids, errors)

    for key, catalog in catalogs.items():
        for arc in catalog.get("arcs", []) if isinstance(catalog, dict) and isinstance(catalog.get("arcs"), list) else []:
            if not isinstance(arc, dict) or not isinstance(arc.get("slug"), str):
                continue
            deps = arc.get("depends_on", [])
            if not isinstance(deps, list):
                continue
            for dep in deps:
                if not isinstance(dep, str):
                    continue
                if dep not in all_arcs:
                    errors.append(f"arc {arc['slug']} has unknown dependency {dep}")
    errors.extend(_dependency_cycles(all_arcs))
    return errors


def _fields(value: dict, expected: set[str], where: str, errors: list[str], optional: set[str] | None = None) -> None:
    optional = optional or set()
    missing = expected - set(value)
    extra = set(value) - expected - optional
    if missing:
        errors.append(f"{where} missing fields: {sorted(missing)}")
    if extra:
        errors.append(f"{where} has unknown fields: {sorted(extra)}")


def _unique_id(identifier: object, where: str, all_ids: dict[str, str], errors: list[str]) -> None:
    if not isinstance(identifier, str) or not identifier.strip():
        errors.append(f"{where}.id must be non-empty")
    elif identifier in all_ids:
        errors.append(f"duplicate ID {identifier} at {where} and {all_ids[identifier]}")
    else:
        all_ids[identifier] = where


def _validate_journal(value: object, where: str, owner: str | None, all_ids: dict[str, str], errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{where} must be an object")
        return
    _fields(value, {"id", "title", "desc", "script", "goal", "exit_conditions"}, where, errors)
    identifier = value.get("id")
    _unique_id(identifier, where, all_ids, errors)
    if not isinstance(identifier, str) or not re.fullmatch(r"ywc_je_v03_[a-z0-9_]+", identifier):
        errors.append(f"{where}.id must use ywc_je_v03_<country>_<slug>_<phase>")
    elif isinstance(owner, str) and not identifier.startswith(f"ywc_je_v03_{owner.lower()}_"):
        errors.append(f"{where}.id prefix must match owner {owner}")
    for field in ("title", "desc"):
        _localized(value.get(field), f"{where}.{field}", errors)
    script_ok = _script_block(value.get("script"), f"{where}.script", errors)
    if script_ok and re.search(r"(?<![a-z0-9_])(?:complete|fail)\s*=", value["script"].strip()[1:-1]):
        errors.append(f"{where}.script must not define complete or fail; use goal and exit_conditions")
    for field in ("goal", "exit_conditions"):
        _script_block(value.get(field), f"{where}.{field}", errors)


def _validate_event(value: object, where: str, key: str, slug: str, reservation: dict | None,
                    ranges_by_arc: dict, limits: dict, all_ids: dict[str, str], errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{where} must be an object")
        return
    _fields(value, {"id", "title", "desc", "trigger", "immediate", "options", "purpose", "reads", "writes"}, where, errors)
    identifier = value.get("id")
    _unique_id(identifier, where, all_ids, errors)
    if reservation is None:
        return
    namespace = reservation.get("namespace")
    match = re.fullmatch(r"([a-z][a-z0-9_]*)\.(\d{4})", identifier) if isinstance(identifier, str) else None
    if not match or match.group(1) != namespace:
        errors.append(f"{where}.id must use registered event namespace {namespace}.NNNN")
    else:
        number = int(match.group(2))
        layer = reservation.get("layer")
        layer_limits = limits.get(layer, {})
        if not isinstance(layer_limits, dict) or type(layer_limits.get("start")) is not int or type(layer_limits.get("end")) is not int:
            errors.append(f"{where}.id has no valid registered interval for {layer}")
        elif not (layer_limits["start"] <= number <= layer_limits["end"]):
            errors.append(f"{where}.id {identifier} outside registered {layer} interval")
        arc_range = ranges_by_arc.get((key, slug))
        if arc_range is None:
            errors.append(f"{where}.id has no explicit arc ID range for {key}/{slug}")
        elif (
            arc_range.get("namespace") != namespace
            or type(arc_range.get("start")) is not int
            or type(arc_range.get("end")) is not int
            or not (arc_range["start"] <= number <= arc_range["end"])
        ):
            errors.append(f"{where}.id {identifier} outside explicit arc range {key}/{slug}")
    for field in ("title", "desc", "purpose"):
        _localized(value.get(field), f"{where}.{field}", errors)
    for field in ("trigger", "immediate"):
        _script_block(value.get(field), f"{where}.{field}", errors)
    for field in ("reads", "writes"):
        entries = value.get(field)
        if not isinstance(entries, list) or any(not isinstance(item, str) or not item for item in entries):
            errors.append(f"{where}.{field} must be a list of non-empty strings")
    options = value.get("options")
    if not isinstance(options, list) or not options:
        errors.append(f"{where}.options must contain at least one option")
        return
    option_keys: set[str] = set()
    for index, option in enumerate(options):
        option_where = f"{where}.options[{index}]"
        if not isinstance(option, dict):
            errors.append(f"{option_where} must be an object")
            continue
        _fields(
            option,
            {"key", "label", "effect", "ai_chance", "cost_note", "consequence_note"},
            option_where,
            errors,
            optional={"trigger"},
        )
        option_key = option.get("key")
        if not isinstance(option_key, str) or re.fullmatch(r"[a-z0-9_]+", option_key) is None:
            errors.append(f"{option_where}.key is malformed")
        elif option_key in option_keys:
            errors.append(f"{option_where}.key is duplicated")
        else:
            option_keys.add(option_key)
        for field in ("label", "cost_note", "consequence_note"):
            _localized(option.get(field), f"{option_where}.{field}", errors)
        _script_block(option.get("effect"), f"{option_where}.effect", errors)
        _script_block(option.get("ai_chance"), f"{option_where}.ai_chance", errors)
        if "trigger" in option:
            _script_block(option["trigger"], f"{option_where}.trigger", errors)
        if isinstance(option.get("ai_chance"), str) and not re.search(r"\bbase\s*=|\bmodifier\s*=", option["ai_chance"]):
            errors.append(f"{option_where}.ai_chance must use base/modifier structure")


def _dependency_cycles(arcs: dict[str, tuple[str, dict]]) -> list[str]:
    result: list[str] = []
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(slug: str) -> None:
        state[slug] = 1
        path.append(slug)
        arc = arcs[slug][1]
        for dep in arc.get("depends_on", []) if isinstance(arc.get("depends_on"), list) else []:
            if not isinstance(dep, str):
                continue
            if dep not in arcs:
                continue
            if state.get(dep) == 1:
                cycle = path[path.index(dep):] + [dep]
                result.append("arc dependency cycle: " + " -> ".join(cycle))
            elif state.get(dep, 0) == 0:
                visit(dep)
        path.pop()
        state[slug] = 2

    for slug in arcs:
        if state.get(slug, 0) == 0:
            visit(slug)
    return result


def _inner(block: str) -> str:
    return block.strip()[1:-1].strip()


def _event_namespace(catalog: dict, root: Path) -> str:
    reservation = next((item for item in _registry(root).get("reservations", []) if item.get("key") == catalog["key"]), None)
    if reservation is None:
        raise ValueError(f"no ID reservation for {catalog['key']}")
    return reservation["namespace"]


def _outputs_for(key: str, *, adapter: bool = False) -> list[Path]:
    paths = [
        Path(f"events/ywc_v03_{key}_events.txt"),
        Path(f"common/journal_entries/ywc_v03_{key}_journal.txt"),
        Path(f"localization/simp_chinese/ywc_v03_{key}_l_simp_chinese.yml"),
        Path(f"localization/english/ywc_v03_{key}_l_english.yml"),
    ]
    if adapter:
        country = "oir" if key == "country_oir" else "dmg" if key == "country_dmg" else "kor" if key == "country_kor" else "nqg" if key == "country_nqg" else "shu" if key == "country_shu" else None
        if not country: raise ValueError(f"no registered adapter output namespace for {key}")
        paths.extend((Path(f"common/scripted_effects/ywc_v03_delivery_{country}_effects.txt"),
                      Path(f"common/scripted_triggers/ywc_v03_delivery_{country}_triggers.txt")))
    return paths


def _catalog_outputs(catalog: dict) -> list[Path]:
    return _outputs_for(catalog["key"], adapter=any("delivery_adapter" in arc or "inline_delivery_adapter" in arc for arc in catalog.get("arcs", [])))


def _append_to_named_block(block: str, field: str, insertion: str) -> str:
    match = re.search(rf"(?<![a-z0-9_]){re.escape(field)}\s*=\s*\{{", block)
    if not match:
        raise ValueError(f"cannot find {field} block for scheduler hook")
    start = block.find("{", match.start())
    depth = 0; quoted = False; escaped = False
    for i in range(start, len(block)):
        ch = block[i]
        if escaped: escaped = False; continue
        if ch == "\\": escaped = True; continue
        if ch == '"': quoted = not quoted; continue
        if not quoted:
            if ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return block[:i].rstrip() + " " + insertion + " " + block[i:]
    raise ValueError(f"unbalanced {field} block")


def _append_or_add_named_block(block: str, field: str, insertion: str) -> str:
    if re.search(rf"(?<![a-z0-9_]){re.escape(field)}\s*=\s*\{{", block):
        return _append_to_named_block(block, field, insertion)
    value = block.rstrip()
    if not value.endswith("}"):
        raise ValueError(f"cannot add {field} to an unbalanced source block")
    return value[:-1].rstrip() + f" {field} = {{ {insertion} }} " + value[-1:] + ("\n" if block.endswith("\n") else "")


def _quote(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _render_script_assignment(name: str, block: str, indent: str) -> list[str]:
    body = block.strip()[1:-1]
    if "\n" not in body:
        return [f"{indent}{name} = {{ {body.strip()} }}"]
    body = body.strip("\r\n")
    lines = [f"{indent}{name} = {{"]
    lines.extend(f"{indent}{line}" if line.strip() else "" for line in body.splitlines())
    lines.append(f"{indent}}}")
    return lines


def _render_event_file(catalog: dict, root: Path, adapter: dict | None = None) -> str:
    namespace = _event_namespace(catalog, root)
    lines = [f"# Generated by tools/build_v03_content.py from data/content/v03/{catalog['key']}.json.", "", f"namespace = {namespace}", ""]
    for arc in catalog["arcs"]:
        for event in arc["events"]:
            lines.extend([
                f"{event['id']} = {{",
                "    type = country_event",
                '    event_image = { video = "unspecific_politicians_arguing" }',
                f"    title = {event['id']}.t",
                f"    desc = {event['id']}.d",
                f"    trigger = {_adapter_event_trigger(event, adapter)}",
                f"    immediate = {_adapter_event_immediate(event, adapter)}",
            ])
            for option in event["options"]:
                lines.extend([
                    "    option = {",
                    f"        name = {event['id']}.{option['key']}",
                ])
                if "trigger" in option:
                    lines.extend(_render_script_assignment("trigger", option["trigger"], "        "))
                lines.extend([
                    f"        ai_chance = {option['ai_chance'].strip()}",
                    "        custom_tooltip = { text = "
                    f"{event['id']}.{option['key']}.cost_tooltip }}",
                    "        custom_tooltip = { text = "
                    f"{event['id']}.{option['key']}.consequence_tooltip }}",
                    f"        { _inner(option['effect']).replace(chr(10), chr(10) + '        ') }",
                    "    }",
                ])
            lines.extend(["}", ""])
    return "\n".join(lines).rstrip() + "\n"


def _adapter_event_trigger(event: dict, adapter: dict | None) -> str:
    original = event["trigger"].strip()
    hooks = (adapter or {}).get("event_hooks", {}).get(event["id"], [])
    if not hooks:
        return original
    gate = " OR = { " + " ".join(f"{name} = yes" for name in hooks) + " }"
    return "{ AND = { " + _inner(original) + " " + gate + " } }"


def _adapter_event_immediate(event: dict, adapter: dict | None) -> str:
    original = event["immediate"].strip()
    hooks = (adapter or {}).get("ack_hooks", {}).get(event["id"], [])
    guards = (adapter or {}).get("event_hooks", {}).get(event["id"], [])
    if not hooks:
        return original
    if event["id"] not in (adapter or {}).get("guarded_immediate_events", []):
        # Preserve the original scripted-dispatch renderer contract byte for
        # byte. Only inline adapters opt into rechecking the event gate around
        # native immediate effects.
        return "{ " + " ".join(part for part in (_inner(original), " ".join(f"{name} = yes" for name in hooks)) if part) + " }"
    if not guards:
        raise ValueError(f"guarded immediate {event['id']} has no source dispatch guard")
    # Revalidate the exact source queue/phase at the start of the actual
    # immediate. Native DMG notice helpers may clear multiple queues, so ACK
    # itself must use the captured snapshot after this guarded source operation.
    guard = " OR = { " + " ".join(f"{name} = yes" for name in guards) + " }"
    body = _inner(original)
    proofs = (adapter or {}).get("inline_proofs", {}).get(event["id"], [])
    effects = " ".join(part for part in (body, " ".join(proofs), " ".join(f"{name} = yes" for name in hooks)) if part)
    return "{ if = { limit = {" + guard + "} " + effects + " } }"


def _render_journal_file(catalog: dict, adapter: dict | None = None) -> str:
    lines = [f"# Generated by tools/build_v03_content.py from data/content/v03/{catalog['key']}.json.", ""]
    live_by_journal = {phase["journal"]: phase["live_witness"] for arc in catalog["arcs"] if adapter and "delivery_adapter" in arc for phase in arc["delivery_adapter"]["live_phases"]}
    live_by_journal.update((adapter or {}).get("live_witnesses", {}))
    callers = (adapter or {}).get("journal_calls", {})
    for arc in catalog["arcs"]:
        for journal in arc["journals"]:
            lines.extend([f"{journal['id']} = {{"])
            script = (adapter or {}).get("journal_scripts", {}).get(journal["id"], journal["script"])
            witness = live_by_journal.get(journal["id"])
            add_on_complete = False
            add_on_fail = False
            if witness:
                caller = callers.get(journal["id"])
                if journal["id"] in callers:
                    old_dispatch = arc["delivery_adapter"]["source_dispatch_effect"]
                    if not caller or not re.search(rf"\b{re.escape(old_dispatch)}\s*=\s*yes", script):
                        raise ValueError(f"adapter cannot bind source dispatcher for {journal['id']}")
                    script = re.sub(rf"\b{re.escape(old_dispatch)}\s*=\s*yes", f"{caller} = yes", script, count=1)
                elif journal["id"] not in (adapter or {}).get("journal_scripts", {}):
                    raise ValueError(f"adapter cannot bind source journal for {journal['id']}")
                script = _append_or_add_named_block(script, "immediate", f"set_variable = {{ name = {witness} value = 1 }}")
                if re.search(r"(?<![a-z0-9_])on_fail\s*=\s*\{", script):
                    script = _append_to_named_block(script, "on_fail", f"remove_variable = {witness}")
                else:
                    add_on_fail = True
                if re.search(r"(?<![a-z0-9_])on_complete\s*=\s*\{", script):
                    script = _append_to_named_block(script, "on_complete", f"remove_variable = {witness}")
                else:
                    add_on_complete = True
            body = _inner(script)
            if body:
                lines.extend("    " + line if line.strip() else "" for line in body.splitlines())
            lines.extend([
                f"    complete = {journal['goal'].strip()}",
                f"    fail = {journal['exit_conditions'].strip()}",
            ])
            if add_on_fail:
                lines.append(f"    on_fail = {{ remove_variable = {witness} }}")
            if add_on_complete:
                lines.append(f"    on_complete = {{ remove_variable = {witness} }}")
            lines.extend(["}", ""])
    return "\n".join(lines).rstrip() + "\n"


def _render_localization(catalog: dict, language: str) -> str:
    loc_language = LANGUAGES[language]
    lines = [f"l_{loc_language}:"]
    for arc in catalog["arcs"]:
        for journal in arc["journals"]:
            lines.append(f" {journal['id']}:0 {_quote(journal['title'][language])}")
            lines.append(f" {journal['id']}_reason:0 {_quote(journal['desc'][language])}")
        for event in arc["events"]:
            lines.append(f" {event['id']}.t:0 {_quote(event['title'][language])}")
            lines.append(f" {event['id']}.d:0 {_quote(event['desc'][language])}")
            for option in event["options"]:
                lines.append(f" {event['id']}.{option['key']}:0 {_quote(option['label'][language])}")
                lines.append(
                    f" {event['id']}.{option['key']}.cost_tooltip:0 "
                    f"{_quote(option['cost_note'][language])}"
                )
                lines.append(
                    f" {event['id']}.{option['key']}.consequence_tooltip:0 "
                    f"{_quote(option['consequence_note'][language])}"
                )
    return "\n".join(lines) + "\n"


def render_all(root: Path) -> dict[Path, str]:
    root = Path(root)
    catalogs = load_catalogs(root)
    errors = validate_catalogs_at(root, catalogs)
    if errors:
        raise ValueError("invalid v0.3 catalogs:\n" + "\n".join(errors))
    outputs: dict[Path, str] = {}
    for key, catalog in catalogs.items():
        if not any(arc["events"] or arc["journals"] for arc in catalog["arcs"]):
            continue
        has_country_adapter = any("delivery_adapter" in arc for arc in catalog["arcs"])
        has_inline_adapter = any("inline_delivery_adapter" in arc for arc in catalog["arcs"])
        adapter = render_country_adapters(catalog) if has_country_adapter else render_inline_country_adapters(catalog) if has_inline_adapter else None
        paths = _catalog_outputs(catalog)
        rendered = [
            _render_event_file(catalog, root, adapter),
            _render_journal_file(catalog, adapter),
            _render_localization(catalog, "zh"),
            _render_localization(catalog, "en"),
        ]
        if adapter:
            if key == "country_oir":
                rendered += ["# Generated OIR scheduler scripted effects.\n\n" + adapter["effects"],
                             "# Generated OIR scheduler scripted triggers.\n\n" + adapter["triggers"]]
            else:
                country = "SHU" if key == "country_shu" else "KOR" if key == "country_kor" else "NQG" if key == "country_nqg" else "DMG"
                rendered += [f"# Generated {country} inline delivery scheduler scripted effects.\n\n" + adapter["effects"],
                             f"# Generated {country} inline delivery scheduler scripted triggers.\n\n" + adapter["triggers"]]
        outputs.update(zip(paths, rendered))
    return outputs


def check_outputs(root: Path) -> list[str]:
    root = Path(root)
    try:
        manifest = read_manifest(root)
        rendered = render_all(root)
    except ValueError as exc:
        return [str(exc)]
    expected_paths = {path.as_posix() for path in rendered}
    allowed_paths = {path.as_posix() for catalog in load_catalogs(root).values() for path in _catalog_outputs(catalog)}
    owned_paths = set(manifest["owned_outputs"])
    errors = [f"manifest.owned_outputs missing catalog path: {path}" for path in sorted(allowed_paths - owned_paths)]
    errors.extend(f"manifest.owned_outputs includes unregistered path: {path}" for path in sorted(owned_paths - allowed_paths))
    inactive_paths = owned_paths - expected_paths
    for relative in sorted(inactive_paths):
        if (root / "yongchang_world" / relative).exists():
            errors.append(f"stale output for empty catalog: {relative}")
    for relative, expected in rendered.items():
        path = root / "yongchang_world" / relative
        if not path.is_file():
            errors.append(f"generated output is missing: {path}")
            continue
        try:
            if not path.read_bytes().startswith(b"\xef\xbb\xbf"):
                errors.append(f"generated output is missing UTF-8 BOM: {path}")
            actual = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            errors.append(f"cannot read generated output {path}: {exc}")
            continue
        if actual != expected:
            errors.append(f"stale generated output mismatch: {path}")
    return errors


def build(root: Path) -> list[str]:
    root = Path(root)
    try:
        manifest = read_manifest(root)
        outputs = render_all(root)
    except ValueError as exc:
        return [str(exc)]
    owned_paths = set(manifest["owned_outputs"])
    expected_paths = {relative.as_posix() for relative in outputs}
    allowed_paths = {path.as_posix() for catalog in load_catalogs(root).values() for path in _catalog_outputs(catalog)}
    if not expected_paths.issubset(owned_paths) or not allowed_paths.issuperset(owned_paths):
        errors = [f"manifest.owned_outputs missing catalog path: {path}" for path in sorted(allowed_paths - owned_paths)]
        errors.extend(f"manifest.owned_outputs includes unregistered path: {path}" for path in sorted(owned_paths - allowed_paths))
        return errors
    stale = [relative for relative in sorted(owned_paths - expected_paths)
             if (root / "yongchang_world" / relative).exists()]
    if stale:
        return [f"stale output for empty catalog: {relative}" for relative in stale]
    planned: list[tuple[Path, str]] = []
    for relative, text in outputs.items():
        path_text = relative.as_posix()
        if path_text not in owned_paths:
            return [f"refusing to write unowned output: {path_text}"]
        try:
            destination = _safe_relative(root / "yongchang_world", path_text)
        except ValueError as exc:
            return [str(exc)]
        planned.append((destination, text))
    for destination, text in planned:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8-sig", newline="\n")
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    errors = check_outputs(args.root) if args.check else build(args.root)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("v0.3 generated output is current" if args.check else "v0.3 output generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
