"""Static checks for The Yongchang World Clausewitz scripts."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

try:
    from tools.scenario_tag_audit import audit_repository_tags
except ModuleNotFoundError:  # Running this file directly puts ``tools`` on sys.path.
    from scenario_tag_audit import audit_repository_tags


SCRIPT_SUFFIXES = {".txt", ".gui", ".asset", ".gfx", ".mod"}
LOCALIZATION_SUFFIXES = {".yml", ".yaml"}
DECLARED_KEY = re.compile(r"^(ywc_[A-Za-z0-9_]+|[A-Z][A-Z0-9]{2})\s*=")
LOCALIZATION_KEY = re.compile(r"^\s*(ywc_[A-Za-z0-9_]+|[A-Z][A-Z0-9]{2}(?:_[A-Za-z0-9_]+)?)\s*:")
ROUTE_COOLDOWN_OR_PATTERNS = (
    re.compile(
        r"OR\s*=\s*\{\s*"
        r"NOT\s*=\s*\{\s*has_variable\s*=\s*"
        r"(?P<route>ywc_route_[A-Za-z0-9_]+)_abandon\s*\}\s*"
        r"NOT\s*=\s*\{\s*has_variable\s*=\s*"
        r"(?P=route)_abandonment_cooldown\s*\}",
        re.DOTALL,
    ),
    re.compile(
        r"OR\s*=\s*\{\s*"
        r"NOT\s*=\s*\{\s*has_variable\s*=\s*"
        r"(?P<route>ywc_route_[A-Za-z0-9_]+)_abandonment_cooldown\s*\}\s*"
        r"NOT\s*=\s*\{\s*has_variable\s*=\s*"
        r"(?P=route)_abandon\s*\}",
        re.DOTALL,
    ),
)


def _without_comments_and_strings(text: str) -> str:
    output: list[str] = []
    in_string = False
    escaped = False
    in_comment = False
    for char in text:
        if in_comment:
            if char == "\n":
                in_comment = False
                output.append(char)
            else:
                output.append(" ")
            continue
        if escaped:
            output.append(" ")
            escaped = False
            continue
        if char == "\\" and in_string:
            output.append(" ")
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            output.append(" ")
            continue
        if char == "#" and not in_string:
            in_comment = True
            output.append(" ")
            continue
        output.append(" " if in_string else char)
    return "".join(output)


def scan_braces(text: str) -> list[str]:
    """Return structural brace errors while ignoring comments and strings."""

    cleaned = _without_comments_and_strings(text)
    depth = 0
    errors: list[str] = []
    for char in cleaned:
        if char == "{":
            depth += 1
        elif char == "}":
            if depth == 0:
                errors.append("unexpected closing brace")
            else:
                depth -= 1
    if depth:
        errors.append("unclosed brace")
    return errors


def _script_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SCRIPT_SUFFIXES:
            yield path


def _localization_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in LOCALIZATION_SUFFIXES:
            yield path


def _declared_key_occurrences(root: Path) -> dict[str, list[tuple[Path, int]]]:
    occurrences: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    for path in _script_files(root):
        text = path.read_text(encoding="utf-8-sig")
        for line_number, line in enumerate(text.splitlines(), 1):
            match = DECLARED_KEY.match(line)
            if match:
                occurrences[match.group(1)].append((path, line_number))
    return dict(occurrences)


def _declaration_namespace(path: Path) -> str:
    """Return the Clausewitz database namespace represented by a script path."""

    parts = {part.lower() for part in path.parts}
    for namespace in (
        "dynamic_country_names",
        "dynamic_country_map_colors",
        "flag_definitions",
        "coat_of_arms",
        "on_actions",
    ):
        if namespace in parts:
            return namespace
    return "global"


def _is_localization_bearing(path: Path) -> bool:
    """Visual/database identifiers are not UI localization keys."""

    parts = {part.lower() for part in path.parts}
    return not bool(
        parts
        & {
            "dynamic_country_names",
            "dynamic_country_map_colors",
            "flag_definitions",
            "coat_of_arms",
            "on_actions",
        }
    )


def collect_declared_keys(root: Path) -> set[str]:
    occurrences = _declared_key_occurrences(Path(root))
    return {
        key
        for key, locations in occurrences.items()
        if any(_is_localization_bearing(path) for path, _line in locations)
    }


def collect_localization_keys(root: Path) -> set[str]:
    keys: set[str] = set()
    for path in _localization_files(Path(root)):
        text = path.read_text(encoding="utf-8-sig")
        for line in text.splitlines():
            match = LOCALIZATION_KEY.match(line)
            if match:
                keys.add(match.group(1))
    return keys


def find_duplicate_keys(root: Path) -> set[str]:
    grouped: dict[tuple[str, str], list[tuple[Path, int]]] = defaultdict(list)
    for key, occurrences in _declared_key_occurrences(Path(root)).items():
        for path, line in occurrences:
            grouped[(_declaration_namespace(path), key)].append((path, line))
    return {key for (_namespace, key), occurrences in grouped.items() if len(occurrences) > 1}


# Vanilla reads each ``common/history/<folder>`` with exactly one root key and
# silently discards any file whose root key it does not recognise.  A typo or an
# invented root key therefore produces a mod that passes every content regex
# while having no effect in game, so the folder -> root key contract is checked
# against the installed game rather than remembered.
VANILLA_HISTORY_ROOT_KEYS = {
    "ai": "AI",
    "buildings": "BUILDINGS",
    "characters": "CHARACTERS",
    "conscription": "CONSCRIPTION",
    "countries": "COUNTRIES",
    "cultures": "CULTURES",
    "diplomacy": "DIPLOMACY",
    "diplomatic_plays": "DIPLOMATIC_PLAYS",
    "global": "GLOBAL",
    "government_setup": "GOVERNMENT_SETUP",
    "governments": "GOVERNMENT",
    "lobbies": "LOBBIES",
    "military_deployments": "MILITARY_DEPLOYMENTS",
    "military_formations": "MILITARY_FORMATIONS",
    "political_movements": "POLITICAL_MOVEMENTS",
    "pops": "POPS",
    "population": "POPULATION",
    "power_blocs": "POWER_BLOCS",
    "production_methods": "PRODUCTION_METHODS",
    "states": "STATES",
    "trade": "TRADE",
    "treaties": "TREATIES",
}


def find_top_level_keys(text: str) -> list[str]:
    """Return the keys whose block opens at brace depth zero.

    Comments and strings are blanked first, so a commented-out root key or a
    brace inside a quoted name can never be mistaken for the file's root.
    """

    cleaned = _without_comments_and_strings(text)
    keys: list[str] = []
    depth = 0
    pending: str | None = None
    index = 0
    length = len(cleaned)
    while index < length:
        char = cleaned[index]
        if char == "{":
            if depth == 0 and pending is not None:
                keys.append(pending)
            depth += 1
            pending = None
            index += 1
            continue
        if char == "}":
            depth -= 1
            index += 1
            continue
        if depth == 0 and (char.isalpha() or char == "_"):
            end = index
            while end < length and (cleaned[end].isalnum() or cleaned[end] == "_"):
                end += 1
            cursor = end
            while cursor < length and cleaned[cursor] in " \t":
                cursor += 1
            if cursor < length and cleaned[cursor] == "=":
                pending = cleaned[index:end]
                index = cursor + 1
                continue
        index += 1
    return keys


def _history_root_key_vocabulary(game_root: Path | None) -> dict[str, set[str]]:
    """Folder -> accepted root keys, from the installed game when available."""

    vocabulary = {folder: {key} for folder, key in VANILLA_HISTORY_ROOT_KEYS.items()}
    if game_root is None:
        return vocabulary
    vanilla_history = Path(game_root) / "common/history"
    if not vanilla_history.is_dir():
        return vocabulary
    derived: dict[str, set[str]] = {}
    for folder in sorted(vanilla_history.iterdir()):
        if not folder.is_dir():
            continue
        keys: set[str] = set()
        for path in sorted(folder.rglob("*.txt")):
            keys.update(find_top_level_keys(path.read_text(encoding="utf-8-sig")))
        if keys:
            derived[folder.name] = keys
    if derived:
        vocabulary.update(derived)
    return vocabulary


def _history_root_key_diagnostics(mod_root: Path, game_root: Path | None = None) -> list[str]:
    """Reject history files the game would silently ignore."""

    history_root = Path(mod_root) / "common/history"
    if not history_root.is_dir():
        return []
    vocabulary = _history_root_key_vocabulary(game_root)
    diagnostics: list[str] = []
    for path in sorted(history_root.rglob("*.txt")):
        folder = path.parent.name
        keys = find_top_level_keys(path.read_text(encoding="utf-8-sig"))
        accepted = vocabulary.get(folder)
        if accepted is None:
            diagnostics.append(
                f"{path}:1: history folder '{folder}' has no vanilla counterpart; "
                "the game loads common/history by folder name, so this file is ignored"
            )
            continue
        if not keys:
            diagnostics.append(f"{path}:1: no top-level key; the game ignores this history file")
            continue
        for key in keys:
            if key not in accepted:
                diagnostics.append(
                    f"{path}:1: root key {key} is not accepted in common/history/{folder} "
                    f"(vanilla uses {', '.join(sorted(accepted))})"
                )
    return diagnostics


def _country_history_blocks(text: str):
    """Yield (country tag, original-text block, one-based start line)."""

    cleaned = _without_comments_and_strings(text)
    pattern = re.compile(r"(?m)^\s*c:([A-Z0-9]{3})\s*\?=\s*\{")
    for match in pattern.finditer(cleaned):
        opening = cleaned.find("{", match.start(), match.end())
        depth = 1
        index = opening + 1
        while depth and index < len(cleaned):
            if cleaned[index] == "{":
                depth += 1
            elif cleaned[index] == "}":
                depth -= 1
            index += 1
        if depth == 0:
            yield (
                match.group(1),
                text[match.start():index],
                text.count("\n", 0, match.start()) + 1,
            )


def _shared_variable_initialization_diagnostics(mod_root: Path) -> list[str]:
    """Ensure every country custom journal follows its shared-state reset."""

    history_root = Path(mod_root) / "common/history/countries"
    if not history_root.is_dir():
        return []
    country_blocks: dict[str, list[tuple[Path, str, int]]] = defaultdict(list)
    for path in sorted(history_root.rglob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        for tag, block, start_line in _country_history_blocks(text):
            country_blocks[tag].append((path, block, start_line))

    journal_pattern = re.compile(
        r"add_journal_entry\s*=\s*\{\s*type\s*=\s*(ywc_[A-Za-z0-9_]+)"
    )
    reset_pattern = re.compile(r"ywc_reset_shared_variables\s*=\s*yes")
    diagnostics: list[str] = []
    for tag, block_records in sorted(country_blocks.items()):
        combined = "\n".join(record[1] for record in block_records)
        reset = reset_pattern.search(combined)
        for journal in journal_pattern.finditer(combined):
            if reset is None or reset.start() > journal.start():
                offset = 0
                journal_path = history_root
                journal_line = 1
                for path, block, start_line in block_records:
                    block_end = offset + len(block)
                    if offset <= journal.start() < block_end:
                        journal_path = path
                        journal_line = start_line + combined[offset:journal.start()].count("\n")
                        break
                    offset = block_end + 1
                diagnostics.append(
                    f"{journal_path}:{journal_line}: country {tag} adds {journal.group(1)} "
                    "before ywc_reset_shared_variables = yes"
                )
    return diagnostics


def _route_cooldown_diagnostics(mod_root: Path) -> list[str]:
    """Reject route gates that can bypass recovery when one flag is absent."""

    diagnostics: list[str] = []
    for path in _script_files(Path(mod_root)):
        text = path.read_text(encoding="utf-8-sig")
        for pattern in ROUTE_COOLDOWN_OR_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                diagnostics.append(
                    f"{path}:{line}: route cooldown guard for {match.group('route')} "
                    "must require the cooldown variable directly, not OR it with the "
                    "abandonment flag"
                )
    return diagnostics


FLAVOR_DIRECTION_EFFECTS = {
    "SHU": ("bureaucracy", "local"),
    "JHG": ("maritime", "tribute"),
    "DMG": ("monarchy", "republic"),
    "NQG": ("restoration", "island"),
    "OIR": ("bureaucracy", "federation"),
    "MNG": ("south", "north"),
    "TIB": ("reform", "league"),
    "KOR": ("court", "national"),
    "LAN": ("company", "community"),
    "NMG": ("federal", "defense"),
}


def _flavor_contract_diagnostics(mod_root: Path) -> list[str]:
    """Check the catalog-backed journal, event, effect, and clamp contract."""

    repository_root = Path(mod_root).parent
    catalog_path = repository_root / "data/content/content_catalog.json"
    if not catalog_path.is_file():
        return []
    try:
        catalog = json.loads(catalog_path.read_text("utf-8"))["countries"]
    except (OSError, ValueError, KeyError) as error:
        return [f"{catalog_path}:1: flavor catalog failed to load: {error}"]

    journal_root = Path(mod_root) / "common/journal_entries"
    event_root = Path(mod_root) / "events"
    effects_path = Path(mod_root) / "common/scripted_effects/ywc_flavor_effects.txt"
    modifiers_path = Path(mod_root) / "common/static_modifiers/ywc_static_modifiers.txt"
    journal_text = "\n".join(
        path.read_text("utf-8-sig") for path in sorted(journal_root.rglob("*.txt"))
    ) if journal_root.is_dir() else ""
    event_text = "\n".join(
        path.read_text("utf-8-sig") for path in sorted(event_root.rglob("*.txt"))
    ) if event_root.is_dir() else ""
    effects_text = effects_path.read_text("utf-8-sig") if effects_path.is_file() else ""
    modifiers_text = modifiers_path.read_text("utf-8-sig") if modifiers_path.is_file() else ""
    diagnostics: list[str] = []

    for tag, row in sorted(catalog.items()):
        flavor = row.get("flavor")
        if not isinstance(flavor, dict):
            diagnostics.append(f"{catalog_path}:1: {tag} is missing its flavor object")
            continue
        variable = flavor.get("variable", "")
        if not isinstance(variable, str) or not variable.startswith("ywc_flavor_"):
            diagnostics.append(f"{catalog_path}:1: {tag} flavor variable must use ywc_flavor_ prefix")
            continue
        for journal in flavor.get("journals", []):
            if f"{journal} =" not in journal_text:
                diagnostics.append(f"{journal_root}:1: missing flavor journal {journal}")
        for event in flavor.get("events", []):
            if f"{event} =" not in event_text:
                diagnostics.append(f"{event_root}:1: missing flavor event {event}")
        for field in ("high_modifier", "low_modifier"):
            modifier = flavor.get(field, "")
            if f"{modifier} =" not in modifiers_text:
                diagnostics.append(f"{modifiers_path}:1: missing flavor modifier {modifier}")

        prefix = f"ywc_flavor_{tag.lower()}_"
        if f"{prefix}initialize =" not in effects_text:
            diagnostics.append(f"{effects_path}:1: missing flavor initializer for {tag}")
        for direction in FLAVOR_DIRECTION_EFFECTS.get(tag, ()):
            if f"{prefix}{direction} =" not in effects_text:
                diagnostics.append(f"{effects_path}:1: missing {tag} flavor direction {direction}")
        clamp_pattern = re.compile(
            rf"clamp_variable\s*=\s*\{{\s*name\s*=\s*{re.escape(variable)}\s+min\s*=\s*0\s+max\s*=\s*100\s*\}}"
        )
        if len(clamp_pattern.findall(effects_text)) < 3:
            diagnostics.append(
                f"{effects_path}:1: {variable} must be clamped in initializer and both direction effects"
            )
    return diagnostics


ON_ACTION_BLOCK = re.compile(r"^\s*([a-z][a-z0-9_]*)\s*=\s*\{", re.MULTILINE)
ON_ACTIONS_LIST = re.compile(r"on_actions\s*=\s*\{([^}]*)\}")


def _on_action_hook_diagnostics(mod_root: Path, game_root: Path) -> list[str]:
    """Attached hooks must exist in vanilla; called on_actions must be declared.

    A misspelled hook name is silent in game: the mod's startup wiring simply
    never runs. Vanilla's ``common/on_actions`` is the authoritative hook list.
    """

    directory = Path(mod_root) / "common/on_actions"
    vanilla_directory = Path(game_root) / "common/on_actions"
    if not directory.is_dir() or not vanilla_directory.is_dir():
        return []

    vanilla_names: set[str] = set()
    for path in sorted(vanilla_directory.glob("*.txt")):
        vanilla_names |= {
            match.group(1)
            for match in ON_ACTION_BLOCK.finditer(path.read_text(encoding="utf-8-sig"))
        }

    declared: set[str] = set()
    called: set[str] = set()
    texts: dict[Path, str] = {}
    for path in sorted(directory.rglob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        texts[path] = text
        declared |= {match.group(1) for match in ON_ACTION_BLOCK.finditer(text)}
        for block in ON_ACTIONS_LIST.findall(text):
            called |= set(re.findall(r"[a-z][a-z0-9_]*", block))

    diagnostics: list[str] = []
    for present in sorted(declared):
        if present not in vanilla_names and present not in called:
            diagnostics.append(
                f"{directory}:1: on_action {present} is neither a vanilla hook nor called by any on_actions list"
            )
    for name in sorted(called):
        if name not in declared and name not in vanilla_names:
            diagnostics.append(f"{directory}:1: on_action {name} is not declared")
    return diagnostics


def validate(mod_root: Path, game_root: Path | None = None) -> list[str]:
    mod_root = Path(mod_root)
    diagnostics: list[str] = []
    if not mod_root.is_dir():
        return [f"{mod_root}:1: mod root does not exist"]

    for path in _script_files(mod_root):
        errors = scan_braces(path.read_text(encoding="utf-8-sig"))
        for error in errors:
            diagnostics.append(f"{path}:1: {error}")

    diagnostics.extend(_shared_variable_initialization_diagnostics(mod_root))
    diagnostics.extend(_route_cooldown_diagnostics(mod_root))
    diagnostics.extend(_flavor_contract_diagnostics(mod_root))
    diagnostics.extend(
        _history_root_key_diagnostics(mod_root, Path(game_root) if game_root else None)
    )

    for key in sorted(find_duplicate_keys(mod_root)):
        all_occurrences = _declared_key_occurrences(mod_root)[key]
        by_namespace: dict[str, list[tuple[Path, int]]] = defaultdict(list)
        for path, line in all_occurrences:
            by_namespace[_declaration_namespace(path)].append((path, line))
        occurrences = next(
            locations for locations in by_namespace.values() if len(locations) > 1
        )
        locations = ", ".join(f"{path}:{line}" for path, line in occurrences)
        diagnostics.append(f"{locations}: duplicate key {key}")

    available_localization = collect_localization_keys(mod_root)
    # Reused country tags keep their vanilla localization.  A mod may still
    # override the country definition without shadowing the base localization
    # key, which would make the game report duplicate localization entries.
    if game_root is not None and Path(game_root).is_dir():
        available_localization |= collect_localization_keys(Path(game_root))
    missing = collect_declared_keys(mod_root) - available_localization
    for key in sorted(missing):
        diagnostics.append(f"{mod_root}:1: missing localization key {key}")

    if game_root is not None and not Path(game_root).is_dir():
        diagnostics.append(f"{game_root}:1: game root does not exist")

    repository_root = mod_root.parent
    if (repository_root / "data/scenario/tag_registry.json").is_file():
        try:
            diagnostics.extend(audit_repository_tags(repository_root))
        except (OSError, ValueError, KeyError) as error:
            diagnostics.append(f"{repository_root}:1: scenario tag audit failed: {error}")

    # Hook and modifier vocabularies both come from the installed game, so
    # these two checks only run when a game root is supplied.
    if game_root is not None and (Path(game_root) / "common/on_actions").is_dir():
        diagnostics.extend(_on_action_hook_diagnostics(mod_root, Path(game_root)))

    if game_root is not None and (Path(game_root) / "common/modifier_type_definitions").is_dir():
        try:
            from tools.modifier_audit import audit as audit_modifiers
        except ModuleNotFoundError:  # Running this file directly puts ``tools`` on sys.path.
            from modifier_audit import audit as audit_modifiers

        report = audit_modifiers(mod_root, Path(game_root))
        diagnostics.extend(report["unknown_modifier_types"])
        diagnostics.extend(report["undeclared_modifier_references"])

    # Imported lazily: the reachability audit reuses this module's script
    # readers, so a top-level import would be circular.
    allowlist_path = repository_root / "data/content/reachability_allowlist.json"
    if allowlist_path.is_file():
        try:
            from tools.content_reachability import audit as audit_content_reachability
        except ModuleNotFoundError:  # Running this file directly puts ``tools`` on sys.path.
            from content_reachability import audit as audit_content_reachability

        try:
            report = audit_content_reachability(mod_root, allowlist_path)
        except (OSError, ValueError, KeyError) as error:
            diagnostics.append(f"{allowlist_path}:1: content reachability audit failed: {error}")
        else:
            for field, label in (
                ("dangling_references", "dangling content reference"),
                ("unreferenced_events", "unreachable event"),
                ("unreferenced_journals", "unreachable journal entry"),
                ("unused_scripted_helpers", "unused scripted helper"),
            ):
                for name in report[field]:
                    diagnostics.append(f"{mod_root}:1: {label} {name}")
    return diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod-root", type=Path, required=True)
    parser.add_argument("--game-root", type=Path)
    args = parser.parse_args()
    diagnostics = validate(args.mod_root, args.game_root)
    for diagnostic in diagnostics:
        print(diagnostic)
    return 1 if diagnostics else 0


if __name__ == "__main__":
    raise SystemExit(main())
