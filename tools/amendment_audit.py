"""Validate Mod law amendments against the installed game and the mod's history.

Amendment support arrived with the 1.13 law rework: an amendment is attached to
an *active law* at script level, and the engine silently ignores a mismatch
instead of reporting it.  This audit guards four failure modes that a static
gate would otherwise miss:

* an amendment whose ``parent`` law is not the law the country actually has
  active in that law group at the opening bookmark (the amendment then has no
  parent and never appears);
* an amendment whose ``parent`` is not listed in its own ``allowed_laws``;
* a modifier key that does not exist in the installed modifier database, which
  the game drops without a warning (the same trap ``modifier_audit.py`` guards
  for static modifiers);
* an amendment with no bilingual localization, or one that is never attached.

Load order matters for the first check.  A mod file sharing a vanilla file name
replaces that file, so it keeps the vanilla slot; mod-only files load afterwards
in name order.  That is the order this audit replays.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

AMENDMENT_DIRECTORY = "common/amendments"
HISTORY_COUNTRY_DIRECTORY = "common/history/countries"
LAW_DIRECTORY = "common/laws"
COUNTRY_DEFINITION_DIRECTORY = "common/country_definitions"
INTEREST_GROUP_DIRECTORY = "common/interest_groups"
MODIFIER_DEFINITION_DIRECTORY = "common/modifier_type_definitions"
LOCALIZATION_DIRECTORY = "localization"
LOCALIZATION_LANGUAGES = ("english", "simp_chinese")

BLOCK_HEADER = re.compile(r"^\s*([a-z][a-z0-9_]*)\s*=\s*\{", re.MULTILINE)
AMENDMENT_HEADER = re.compile(r"^\s*(amendment_[a-z0-9_]+)\s*=\s*\{", re.MULTILINE)
ATTACHMENT = re.compile(
    r"c:([A-Z0-9]{3})\s*\?=\s*\{\s*active_law:(lawgroup_[a-z0-9_]+)\s*\?=\s*\{"
    r"\s*add_amendment\s*=\s*\{\s*type\s*=\s*(amendment_[a-z0-9_]+)",
    re.DOTALL,
)
COUNTRY_BLOCK = re.compile(r"c:([A-Z0-9]{3})\s*\?=\s*\{")
ACTIVATE_LAW = re.compile(r"activate_law\s*=\s*law_type:([a-z0-9_]+)")
PARENT = re.compile(r"\bparent\s*=\s*([a-z0-9_]+)")
GROUP = re.compile(r"\bgroup\s*=\s*(lawgroup_[a-z0-9_]+)")
MODIFIER_BLOCK = re.compile(
    r"(modifier|sponsor_modifier|tax_modifier_[a-z_]+|institution_modifier)\s*=\s*\{"
)
INTEREST_GROUP_TYPE = re.compile(r"is_interest_group_type\s*=\s*([a-z0-9_]+)")
POSSIBLE_BLOCK = re.compile(r"possible\s*=\s*\{([^}]*)\}")
POSSIBLE_TAG = re.compile(r"\bthis\s*=\s*c:([A-Z0-9]{3})")
LOCALIZATION_KEY = re.compile(r"^\s*(amendment_[a-z0-9_]+)\s*:", re.MULTILINE)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _block_body(text: str, opening_brace_index: int) -> str:
    """Return the body of the block whose opening brace sits at the index."""

    depth = 0
    index = opening_brace_index
    while index < len(text):
        character = text[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[opening_brace_index + 1 : index]
        index += 1
    return text[opening_brace_index + 1 :]


def _top_level_blocks(text: str, header: re.Pattern) -> list[tuple[str, str, int]]:
    """Yield (name, body, line) for each depth-0 block header in ``text``.

    Only headers outside every other brace pair count: a nested ``can_impose``
    or ``modifier`` block is not a database entry, and treating one as such is
    how a law file silently yields a single law instead of a hundred.
    """

    blocks: list[tuple[str, str, int]] = []
    depth = 0
    index = 0
    while index < len(text):
        character = text[index]
        if character == "{":
            depth += 1
            index += 1
            continue
        if character == "}":
            depth = max(0, depth - 1)
            index += 1
            continue
        if depth == 0 and (index == 0 or text[index - 1] == "\n"):
            match = header.match(text, index)
            if match:
                opening = text.find("{", match.end() - 1)
                line = text.count("\n", 0, index) + 1
                blocks.append((match.group(1), _block_body(text, opening), line))
                index = opening + 1
                depth = 1
                continue
        index += 1
    return blocks


def _own_level_keys(body: str) -> list[tuple[str, int]]:
    """Return ``key =`` names at the body's own nesting level."""

    keys: list[tuple[str, int]] = []
    depth = 0
    for offset, line in enumerate(body.splitlines(), 1):
        if depth == 0:
            match = re.match(r"^\s*([a-z][a-z0-9_]*)\s*=", line)
            if match:
                keys.append((match.group(1), offset))
        depth += line.count("{") - line.count("}")
    return keys


def _collect_laws(root: Path) -> dict[str, str]:
    """Return law key -> law group for one content root."""

    groups: dict[str, str] = {}
    directory = Path(root) / LAW_DIRECTORY
    if not directory.is_dir():
        return groups
    for path in sorted(directory.glob("*.txt")):
        for name, body, _line in _top_level_blocks(_read(path), BLOCK_HEADER):
            match = GROUP.search(body)
            if match:
                groups[name] = match.group(1)
    return groups


def _collect_names(root: Path, relative: str, pattern: str) -> set[str]:
    """Return every match of ``pattern`` in the .txt files of one directory."""

    names: set[str] = set()
    directory = Path(root) / relative
    if not directory.is_dir():
        return names
    for path in sorted(directory.glob("*.txt")):
        names.update(re.findall(pattern, _read(path), re.MULTILINE))
    return names


def _effective_history(mod_root: Path, game_root: Path | None) -> list[tuple[str, Path]]:
    """Return (origin, path) pairs in the order the engine should load them."""

    vanilla: dict[str, Path] = {}
    if game_root is not None:
        directory = Path(game_root) / HISTORY_COUNTRY_DIRECTORY
        if directory.is_dir():
            vanilla = {path.name: path for path in directory.glob("*.txt")}
    modded: dict[str, Path] = {}
    directory = Path(mod_root) / HISTORY_COUNTRY_DIRECTORY
    if directory.is_dir():
        modded = {path.name: path for path in directory.glob("*.txt")}

    order: list[tuple[str, Path]] = []
    for name in sorted(set(vanilla) | set(modded)):
        if name in modded:
            origin = "mod-replaces-vanilla" if name in vanilla else "mod"
            order.append((f"{origin}:{name}", modded[name]))
        else:
            order.append((f"vanilla:{name}", vanilla[name]))
    return order


def _starting_laws(
    mod_root: Path, game_root: Path | None, law_groups: dict[str, str]
) -> dict[str, dict[str, str]]:
    """Replay country history into tag -> law group -> active law key."""

    active: dict[str, dict[str, str]] = {}
    for _origin, path in _effective_history(mod_root, game_root):
        text = _read(path)
        for match in COUNTRY_BLOCK.finditer(text):
            body = _block_body(text, text.find("{", match.end() - 1))
            for law in ACTIVATE_LAW.findall(body):
                group = law_groups.get(law)
                if group:
                    active.setdefault(match.group(1), {})[group] = law
    return active


def audit(mod_root: Path, game_root: Path | None = None) -> dict:
    mod_root = Path(mod_root)
    game_root = Path(game_root) if game_root is not None else None
    diagnostics: list[str] = []

    have_game = game_root is not None and (game_root / LAW_DIRECTORY).is_dir()
    law_groups = _collect_laws(mod_root)
    tags = _collect_names(mod_root, COUNTRY_DEFINITION_DIRECTORY, r"^([A-Z][A-Z0-9]{2})\s*=\s*\{")
    interest_groups = _collect_names(mod_root, INTEREST_GROUP_DIRECTORY, r"^\s*(ig_[a-z_]+)\s*=\s*\{")
    modifier_types: set[str] = set()
    if game_root is not None:
        law_groups = {**_collect_laws(game_root), **law_groups}
        tags |= _collect_names(game_root, COUNTRY_DEFINITION_DIRECTORY, r"^([A-Z][A-Z0-9]{2})\s*=\s*\{")
        interest_groups |= _collect_names(game_root, INTEREST_GROUP_DIRECTORY, r"^\s*(ig_[a-z_]+)\s*=\s*\{")
        modifier_types = _collect_names(game_root, MODIFIER_DEFINITION_DIRECTORY, r"^\s*([a-z][a-z0-9_]*)\s*=\s*\{")

    amendments: dict[str, tuple[Path, int, str]] = {}
    definition_directory = mod_root / AMENDMENT_DIRECTORY
    if definition_directory.is_dir():
        for path in sorted(definition_directory.glob("*.txt")):
            for name, body, line in _top_level_blocks(_read(path), AMENDMENT_HEADER):
                if name in amendments:
                    first, first_line, _ = amendments[name]
                    diagnostics.append(
                        f"{path}:{line}: duplicate amendment {name} "
                        f"(first defined at {first}:{first_line})"
                    )
                    continue
                amendments[name] = (path, line, body)

    # 1. modifier vocabulary inside every modifier-shaped block
    if modifier_types:
        for name, (path, line, body) in sorted(amendments.items()):
            for match in MODIFIER_BLOCK.finditer(body):
                block = _block_body(body, body.find("{", match.end() - 1))
                for key, offset in _own_level_keys(block):
                    if key not in modifier_types:
                        diagnostics.append(
                            f"{path}:{line + offset}: unknown modifier type {key} in {name}"
                        )

    # 2. parent / allowed_laws
    for name, (path, line, body) in sorted(amendments.items()):
        parent_match = PARENT.search(body)
        allowed_match = re.search(r"allowed_laws\s*=\s*\{([^}]*)\}", body)
        allowed = re.findall(r"[a-z0-9_]+", allowed_match.group(1)) if allowed_match else []
        if parent_match:
            parent = parent_match.group(1)
            if law_groups and parent not in law_groups:
                diagnostics.append(f"{path}:{line}: unknown parent law {parent} in {name}")
            if not allowed:
                diagnostics.append(f"{path}:{line}: {name} has a parent but no allowed_laws")
            elif parent not in allowed:
                diagnostics.append(
                    f"{path}:{line}: {name} parent {parent} is not listed in allowed_laws"
                )
        for law in allowed:
            if law_groups and law not in law_groups:
                diagnostics.append(f"{path}:{line}: unknown law {law} in {name} allowed_laws")

    # 3. possible / would_sponsor vocabularies
    for name, (path, line, body) in sorted(amendments.items()):
        possible = POSSIBLE_BLOCK.search(body)
        if possible is None:
            diagnostics.append(f"{path}:{line}: {name} has no possible block")
        else:
            found = POSSIBLE_TAG.findall(possible.group(1))
            if not found:
                diagnostics.append(
                    f"{path}:{line}: {name} possible block names no country "
                    "(expected this = c:TAG)"
                )
            for tag in found:
                if have_game and tags and tag not in tags:
                    diagnostics.append(f"{path}:{line}: {name} names undefined country c:{tag}")
        for group in INTEREST_GROUP_TYPE.findall(body):
            if interest_groups and group not in interest_groups:
                diagnostics.append(f"{path}:{line}: {name} names unknown {group}")

    # 4. attachments
    known_groups = set(law_groups.values())
    attached: dict[str, list[tuple[str, str, Path, int]]] = {}
    for origin, path in _effective_history(mod_root, game_root):
        if not origin.startswith("mod"):
            continue
        text = _read(path)
        for match in ATTACHMENT.finditer(text):
            tag, group, amendment = match.groups()
            line = text.count("\n", 0, match.start()) + 1
            attached.setdefault(amendment, []).append((tag, group, path, line))
            if amendment not in amendments:
                diagnostics.append(
                    f"{path}:{line}: c:{tag} attaches undefined amendment {amendment}"
                )
            if known_groups and group not in known_groups:
                diagnostics.append(f"{path}:{line}: c:{tag} attaches to unknown {group}")

    for name in sorted(amendments):
        if name not in attached:
            path, line, _body = amendments[name]
            diagnostics.append(f"{path}:{line}: amendment {name} is never attached")

    # 5. the amended law must be the one active in that group at the bookmark.
    # Without the installed game the law groups are unknown, so every country
    # would look like it has no law in the group: skip rather than guess.
    active = _starting_laws(mod_root, game_root, law_groups) if have_game else {}
    for name, entries in sorted(attached.items()):
        if not have_game:
            break
        definition = amendments.get(name)
        parent_match = PARENT.search(definition[2]) if definition else None
        if not parent_match:
            continue
        parent = parent_match.group(1)
        for tag, group, path, line in entries:
            current = active.get(tag, {}).get(group)
            if current != parent:
                diagnostics.append(
                    f"{path}:{line}: c:{tag} attaches {name} (parent {parent}) to {group}, "
                    f"whose opening law is {current or 'none'}"
                )

    # 6. bilingual localization
    for name in sorted(amendments):
        for language in LOCALIZATION_LANGUAGES:
            present: set[str] = set()
            directory = mod_root / LOCALIZATION_DIRECTORY / language
            if directory.is_dir():
                for path in directory.rglob("*.yml"):
                    present.update(LOCALIZATION_KEY.findall(_read(path)))
            for key in (name, f"{name}_desc"):
                if key not in present:
                    diagnostics.append(
                        f"{mod_root}/{LOCALIZATION_DIRECTORY}/{language}: "
                        f"missing localization key {key}"
                    )

    skipped = [] if have_game else ["installed-game vocabulary", "bookmark-law check"]
    return {
        "amendments": len(amendments),
        "attachments": sum(len(entries) for entries in attached.values()),
        "laws": len(law_groups),
        "interest_groups": len(interest_groups),
        "modifier_types": len(modifier_types),
        "skipped": skipped,
        "problems": diagnostics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod-root", type=Path, required=True)
    parser.add_argument("--game-root", type=Path)
    args = parser.parse_args()
    if not (Path(args.mod_root) / AMENDMENT_DIRECTORY).is_dir():
        print(f"mod root has no {AMENDMENT_DIRECTORY}: {args.mod_root}")
        return 1
    if args.game_root is not None and not Path(args.game_root).is_dir():
        print(f"game root does not exist: {args.game_root}")
        return 1
    report = audit(args.mod_root, args.game_root)
    print(
        f"amendments={report['amendments']} attachments={report['attachments']} "
        f"laws={report['laws']} interest groups={report['interest_groups']} "
        f"modifier types={report['modifier_types']}"
    )
    if report["skipped"]:
        print(
            "game root not supplied: skipped " + ", ".join(report["skipped"])
        )
    for problem in report["problems"]:
        print(problem)
    if report["problems"]:
        print(f"{len(report['problems'])} amendment problem(s) found")
        return 1
    print("Amendments are consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
