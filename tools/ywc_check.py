"""Static checks for The Yongchang World Clausewitz scripts."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path


SCRIPT_SUFFIXES = {".txt", ".gui", ".asset", ".gfx", ".mod"}
LOCALIZATION_SUFFIXES = {".yml", ".yaml"}
DECLARED_KEY = re.compile(r"^(ywc_[A-Za-z0-9_]+|[A-Z][A-Z0-9]{2})\s*=")
LOCALIZATION_KEY = re.compile(r"^\s*(ywc_[A-Za-z0-9_]+|[A-Z][A-Z0-9]{2}(?:_[A-Za-z0-9_]+)?)\s*:")


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


def validate(mod_root: Path, game_root: Path | None = None) -> list[str]:
    mod_root = Path(mod_root)
    diagnostics: list[str] = []
    if not mod_root.is_dir():
        return [f"{mod_root}:1: mod root does not exist"]

    for path in _script_files(mod_root):
        errors = scan_braces(path.read_text(encoding="utf-8-sig"))
        for error in errors:
            diagnostics.append(f"{path}:1: {error}")

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
