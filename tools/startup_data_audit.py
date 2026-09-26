"""Audit 1836 startup data (pops and buildings) against the installed game.

Both file types are hand written and are only read at campaign start, so a bad
key costs a real 1836 session to discover. This class of bug already bit the
project once: KUC's logging camp, a wheat farm in Outer Manchuria and a fishing
wharf in Western Australia all had zero capacity in their state and were only
exposed by starting the game.

Capacity is taken from the installed game's own `map_data/state_regions`:

* `arable_resources` lists the farms a state can host;
* `capped_resources` lists mining/logging/fishing buildings with their max
  levels;
* everything else is an urban building, which vanilla is allowed to place
  anywhere. Rather than hard-code that list, it is derived from vanilla's own
  building history: any building type vanilla places in a state without that
  state listing it under arable/capped resources is treated as unconstrained.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BUILDING_DIRECTORY = "common/buildings"
STATE_REGION_DIRECTORY = "map_data/state_regions"
CULTURE_DIRECTORY = "common/cultures"
RELIGION_DIRECTORY = "common/religions"
POP_TYPE_DIRECTORY = "common/pop_types"
VANILLA_BUILDING_HISTORY = "common/history/buildings"

DECLARATION = re.compile(r"^([a-zA-Z][A-Za-z0-9_]*)\s*=\s*\{", re.MULTILINE)
STATE_REFERENCE = re.compile(r"\bs:(STATE_[A-Z0-9_]+)\b")
CREATE_BUILDING = re.compile(r"create_building\s*=\s*\{")
CREATE_POP = re.compile(r"create_pop\s*=\s*\{")
BUILDING_NAME = re.compile(r'building\s*=\s*"([A-Za-z0-9_]+)"')
# Vanilla writes `levels = N` inside add_ownership but `level = N` for the
# monument buildings it ships directly, so both spellings are valid.
LEVELS = re.compile(r"\blevels?\s*=\s*(-?\d+)")
FIELD = re.compile(r"\b(culture|religion|pop_type)\s*=\s*([A-Za-z0-9_]+)")


def _files(root: Path, directory: str) -> list[Path]:
    path = Path(root) / directory
    if not path.is_dir():
        return []
    return sorted(candidate for candidate in path.rglob("*.txt") if candidate.is_file())


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:  # pragma: no cover - a locked file must not stop the audit.
        return ""


def _declarations(root: Path, directory: str) -> set[str]:
    names: set[str] = set()
    for path in _files(Path(root), directory):
        names.update(match.group(1) for match in DECLARATION.finditer(_read(path)))
    return names


def load_state_regions(game_root: Path) -> dict[str, dict]:
    """Return each state region with its arable and capped building capacity."""

    regions: dict[str, dict] = {}
    for path in _files(Path(game_root), STATE_REGION_DIRECTORY):
        text = _read(path)
        for match in DECLARATION.finditer(text):
            name = match.group(1)
            if not name.startswith("STATE_"):
                continue
            body = _block_body(text, match.end())
            arable = set(re.findall(r'"([A-Za-z0-9_]+)"', _inner(body, "arable_resources")))
            capped_block = _inner(body, "capped_resources")
            capped = {
                key: int(value)
                for key, value in re.findall(r"([A-Za-z0-9_]+)\s*=\s*(\d+)", capped_block)
            }
            regions[name] = {"arable": arable, "capped": capped}
    return regions


def _block_body(text: str, open_index: int) -> str:
    """Return the body of the block whose opening brace is at ``open_index``."""

    depth = 1
    index = open_index
    while index < len(text) and depth:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
        index += 1
    return text[open_index:index]


def _inner(body: str, key: str) -> str:
    match = re.search(rf"{key}\s*=\s*\{{", body)
    if not match:
        return ""
    return _block_body(body, match.end())


def load_unconstrained_buildings(game_root: Path, regions: dict[str, dict]) -> set[str]:
    """Building types vanilla places without a state capacity entry."""

    unconstrained: set[str] = set()
    for path in _files(Path(game_root), VANILLA_BUILDING_HISTORY):
        text = _read(path)
        for state, body in _state_blocks(text):
            capacity = regions.get(state)
            for building, _levels in _buildings_in(body):
                if capacity is None or (
                    building not in capacity["arable"] and building not in capacity["capped"]
                ):
                    unconstrained.add(building)
    return unconstrained


def _state_blocks(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for match in re.finditer(r"s:(STATE_[A-Z0-9_]+)\s*=\s*\{", text):
        blocks.append((match.group(1), _block_body(text, match.end())))
    return blocks


def _buildings_in(body: str) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    for match in CREATE_BUILDING.finditer(body):
        block = _block_body(body, match.end())
        name_match = BUILDING_NAME.search(block)
        if not name_match:
            continue
        level_match = LEVELS.search(block)
        entries.append((name_match.group(1), int(level_match.group(1)) if level_match else None))
    return entries


def _pops_in(body: str) -> list[str]:
    values: list[str] = []
    for match in CREATE_POP.finditer(body):
        block = _block_body(body, match.end())
        values.extend(f"{key}={value}" for key, value in FIELD.findall(block))
    return values


def audit(mod_root: Path, game_root: Path) -> dict:
    mod_root = Path(mod_root)
    game_root = Path(game_root)
    regions = load_state_regions(game_root)
    vanilla_buildings = _declarations(game_root, BUILDING_DIRECTORY)
    mod_buildings = _declarations(mod_root, BUILDING_DIRECTORY)
    buildings = vanilla_buildings | mod_buildings
    cultures = _declarations(game_root, CULTURE_DIRECTORY)
    religions = _declarations(game_root, RELIGION_DIRECTORY)
    pop_types = _declarations(game_root, POP_TYPE_DIRECTORY)
    unconstrained = load_unconstrained_buildings(game_root, regions)

    problems: list[str] = []
    checked_buildings = 0
    checked_pops = 0
    for path in sorted(mod_root.rglob("*.txt")):
        if not path.is_file():
            continue
        text = _read(path)
        if not text:
            continue
        is_buildings = "create_building" in text
        is_pops = "create_pop" in text
        if not (is_buildings or is_pops):
            continue
        for state, body in _state_blocks(text):
            if state not in regions:
                problems.append(f"{path}: unknown state region {state}")
            if is_buildings:
                for building, levels in _buildings_in(body):
                    checked_buildings += 1
                    if building not in buildings:
                        problems.append(f"{path}: unknown building {building} in {state}")
                    # A missing level is not an error: vanilla omits it for some
                    # entries and defaults them, so only explicit bad values are
                    # reported.
                    if levels is not None and levels < 1:
                        problems.append(
                            f"{path}: {building} in {state} has non-positive level {levels}"
                        )
                    if building in mod_buildings:
                        # Capacity for a custom building comes from its own
                        # definition, not from vanilla state capacity lists.
                        continue
                    capacity = regions.get(state)
                    if capacity is None:
                        continue
                    if (
                        building not in capacity["arable"]
                        and building not in capacity["capped"]
                        and building not in unconstrained
                    ):
                        problems.append(
                            f"{path}: {building} in {state} has zero capacity "
                            "(not in arable_resources, capped_resources or vanilla urban history)"
                        )
            if is_pops:
                for entry in _pops_in(body):
                    checked_pops += 1
                    key, _, value = entry.partition("=")
                    known = {
                        "culture": cultures,
                        "religion": religions,
                        "pop_type": pop_types,
                    }[key]
                    if value not in known:
                        problems.append(f"{path}: unknown {key} {value} in {state}")
    return {
        "state_regions": len(regions),
        "buildings": len(buildings),
        "cultures": len(cultures),
        "religions": len(religions),
        "pop_types": len(pop_types),
        "unconstrained_buildings": sorted(unconstrained),
        "checked_buildings": checked_buildings,
        "checked_pops": checked_pops,
        "problems": problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod-root", type=Path, default=Path("yongchang_world"))
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = audit(args.mod_root, args.game_root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"checked buildings={report['checked_buildings']} pop fields={report['checked_pops']} "
            f"(state regions={report['state_regions']}, buildings={report['buildings']})"
        )
        for problem in report["problems"]:
            print(problem)
        if report["problems"]:
            print(f"{len(report['problems'])} startup data problem(s) found")
            return 1
        print("Startup data is valid.")
    return 0 if not report["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
