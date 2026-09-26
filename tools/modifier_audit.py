"""Validate Mod modifier keys against the installed game's modifier database.

The 1.13.11 install ships the authoritative list of modifier types in
``game/common/modifier_type_definitions/*.txt`` (2364 entries). A key that is
not in that list is silently ignored by the game, which is exactly how the
earlier `country_tax_capacity_mult` / `country_convoy_capacity_mult` /
`country_migration_pull_mult` mistakes shipped: the modifiers looked correct in
the script and did nothing in game.

Two checks are performed:

* every key used inside a static or scripted modifier body must be a known
  modifier type (metadata keys such as ``icon`` are allowed);
* every ``add_modifier``/``remove_modifier`` ``name = ...`` reference must point
  at a static modifier this repository declares.

Keys that only exist in a DLC-gated definition file are reported separately:
they are valid, but they only work when that DLC is mounted, which matters for
the five-configuration acceptance runs.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MODIFIER_DIRECTORIES = ("common/static_modifiers", "common/scripted_modifiers")
DEFINITION_DIRECTORY = "common/modifier_type_definitions"
METADATA_KEYS = {
    "icon",
    "color",
    "decimals",
    "percent",
    "prefix",
    "suffix",
    "boolean",
    "game_data",
    "texture",
}
DLCA_GATED_FILES = ("12_ip4_script_modifiers.txt", "13_ep2_script_modifiers.txt")
# re.MULTILINE matters: without it `^` only matches the start of the file and a
# definition file yields a single name.
BLOCK_HEADER = re.compile(r"^\s*([a-z][a-z0-9_]*)\s*=\s*\{", re.MULTILINE)
MODIFIER_REFERENCE = re.compile(
    r"(?:add_modifier|remove_modifier)\s*=\s*\{[^}]*?name\s*=\s*([A-Za-z0-9_]+)", re.DOTALL
)


def collect_modifier_types(game_root: Path) -> tuple[set[str], set[str]]:
    """Return the valid modifier keys, split into always-on and DLC-gated."""

    directory = Path(game_root) / DEFINITION_DIRECTORY
    valid: set[str] = set()
    dlc_gated: set[str] = set()
    for path in sorted(directory.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        names = {match.group(1) for match in BLOCK_HEADER.finditer(text)}
        valid |= names
        if path.name in DLCA_GATED_FILES:
            dlc_gated |= names
    return valid, dlc_gated


def _block_bodies(text: str) -> list[tuple[str, str, int]]:
    """Yield (name, body, line) for every top-level block in a modifier file."""

    lines = text.splitlines()
    blocks: list[tuple[str, str, int]] = []
    index = 0
    while index < len(lines):
        match = BLOCK_HEADER.match(lines[index])
        if not match:
            index += 1
            continue
        name = match.group(1)
        start_line = index + 1
        depth = lines[index].count("{") - lines[index].count("}")
        body: list[str] = []
        index += 1
        while index < len(lines) and depth > 0:
            depth += lines[index].count("{") - lines[index].count("}")
            if depth > 0:
                body.append(lines[index])
            index += 1
        blocks.append((name, "\n".join(body), start_line))
    return blocks


def _body_keys(body: str) -> list[tuple[str, int]]:
    """Return keys at the block's own nesting level only."""

    keys: list[tuple[str, int]] = []
    depth = 0
    for offset, line in enumerate(body.splitlines(), 1):
        if depth == 0:
            match = re.match(r"^\s*([a-z][a-z0-9_]*)\s*=", line)
            if match:
                keys.append((match.group(1), offset))
        depth += line.count("{") - line.count("}")
    return keys


def audit(mod_root: Path, game_root: Path) -> dict:
    mod_root = Path(mod_root)
    valid, dlc_gated = collect_modifier_types(game_root)
    declared: set[str] = set()
    diagnostics: list[str] = []
    info: list[str] = []
    checked = 0

    for relative in MODIFIER_DIRECTORIES:
        directory = mod_root / relative
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.txt")):
            text = path.read_text(encoding="utf-8-sig")
            for name, body, start_line in _block_bodies(text):
                declared.add(name)
                for key, offset in _body_keys(body):
                    if key in METADATA_KEYS:
                        continue
                    checked += 1
                    line = start_line + offset
                    if key in valid:
                        if key in dlc_gated:
                            info.append(f"{path}:{line}: {key} is DLC-gated content")
                        continue
                    diagnostics.append(
                        f"{path}:{line}: unknown modifier type {key} in {name}"
                    )

    referenced = {}
    for path in sorted(mod_root.rglob("*.txt")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig")
        for match in MODIFIER_REFERENCE.finditer(text):
            referenced.setdefault(match.group(1), path)

    return {
        "modifier_types": len(valid),
        "checked_keys": checked,
        "static_modifiers": len(declared),
        "unknown_modifier_types": diagnostics,
        "dlc_gated_usage": sorted(set(info)),
        "undeclared_modifier_references": [
            f"{path}: add_modifier/remove_modifier references undeclared {name}"
            for name, path in sorted(referenced.items())
            if name not in declared
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod-root", type=Path, required=True)
    parser.add_argument("--game-root", type=Path, required=True)
    args = parser.parse_args()
    if not (Path(args.game_root) / DEFINITION_DIRECTORY).is_dir():
        print(f"game root has no {DEFINITION_DIRECTORY}: {args.game_root}")
        return 1
    report = audit(args.mod_root, args.game_root)
    print(
        f"modifier types={report['modifier_types']} "
        f"checked keys={report['checked_keys']} static modifiers={report['static_modifiers']}"
    )
    for item in report["dlc_gated_usage"]:
        print(f"info: {item}")
    problems = report["unknown_modifier_types"] + report["undeclared_modifier_references"]
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} modifier problem(s) found")
        return 1
    print("Modifier keys are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
