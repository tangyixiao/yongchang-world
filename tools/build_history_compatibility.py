"""Build vanilla history overrides compatible with Yongchang ownership splits."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    from tools.build_state_history import balanced_end, extract_groups, state_blocks
except ModuleNotFoundError:  # pragma: no cover - supports direct script execution
    from build_state_history import balanced_end, extract_groups, state_blocks


STATE_ENTRY_RE = re.compile(r"(?m)^[ \t]*s:(STATE_[A-Z0-9_]+)[ \t]*=[ \t]*\{")
REGION_STATE_RE = re.compile(r"(?m)^[ \t]*region_state:([A-Z0-9_]+)[ \t]*=[ \t]*\{")
COUNTRY_BLOCK_RE = re.compile(r"(?m)^[ \t]*c:([A-Z0-9_]+)[ \t]*\?=[ \t]*\{")
FORMATION_RE = re.compile(r"(?m)^[ \t]*create_military_formation[ \t]*=[ \t]*\{")
COMBAT_UNIT_RE = re.compile(r"(?m)^[ \t]*combat_unit[ \t]*=[ \t]*\{")
SCOPE_BLOCK_RE = re.compile(r"(?m)^[ \t]*scope:([A-Za-z0-9_]+)[ \t]*=[ \t]*\{")
STATE_REGION_REF_RE = re.compile(r"state_region[ \t]*=[ \t]*s:(STATE_[A-Z0-9_]+)")
HQ_REGION_RE = re.compile(r"hq_region[ \t]*=[ \t]*sr:([A-Za-z0-9_]+)")
SAVE_SCOPE_RE = re.compile(r"save_scope_as[ \t]*=[ \t]*([A-Za-z0-9_]+)")
HISTORY_GROUPS = ("pops", "buildings", "trade")
MILITARY_GROUP = "military_formations"
UNSUPPORTED_DLC_FEATURES = {"ip4_content"}


def ownership_by_state(state_history: str) -> dict[str, set[str]]:
    """Return country owners for every state block in a full state history."""

    owners: dict[str, set[str]] = {}
    for state, block in state_blocks(
        state_history,
        {"states": {match.group(1): {} for match in STATE_ENTRY_RE.finditer(state_history)}},
    ).items():
        owners[state] = {group["owner"] for group in extract_groups(block)}
    return owners


def strip_invalid_region_states(text: str, owners: dict[str, set[str]]) -> tuple[str, int]:
    """Remove region-state history blocks whose owner is absent from the state ledger."""

    replacements: list[tuple[int, int]] = []
    for state_match in STATE_ENTRY_RE.finditer(text):
        state = state_match.group(1)
        allowed = owners.get(state)
        if allowed is None:
            continue
        opening = text.find("{", state_match.start(), state_match.end())
        state_end = balanced_end(text, opening)
        body = text[opening + 1 : state_end]
        for region_match in REGION_STATE_RE.finditer(body):
            if region_match.group(1) in allowed:
                continue
            start = opening + 1 + region_match.start()
            region_opening = text.find("{", start, opening + 1 + region_match.end())
            end = balanced_end(text, region_opening) + 1
            replacements.append((start, end))

    result = text
    for start, end in reversed(replacements):
        result = result[:start] + result[end:]
    return result, len(replacements)


def strip_scenario_states(text: str, scenario_states: set[str]) -> tuple[str, int]:
    """Remove complete vanilla state-history blocks replaced by Mod history."""

    replacements: list[tuple[int, int]] = []
    for match in STATE_ENTRY_RE.finditer(text):
        if match.group(1) not in scenario_states:
            continue
        opening = text.find("{", match.start(), match.end())
        replacements.append((match.start(), balanced_end(text, opening) + 1))
    result = text
    for start, end in reversed(replacements):
        result = result[:start] + result[end:]
    return result, len(replacements)


def strip_unsupported_dlc_history(text: str) -> tuple[str, int]:
    """Drop vanilla conditional blocks for DLC features outside this mod's matrix."""

    replacements: list[tuple[int, int]] = []
    for match in re.finditer(r"(?m)^[ \t]*if[ \t]*=[ \t]*\{", text):
        opening = text.find("{", match.start(), match.end())
        end = balanced_end(text, opening)
        block = text[match.start() : end + 1]
        if any(f"has_dlc_feature = {feature}" in block for feature in UNSUPPORTED_DLC_FEATURES):
            replacements.append((match.start(), end + 1))
    result = text
    for start, end in reversed(replacements):
        result = result[:start] + result[end:]
    return result, len(replacements)


def strip_invalid_military_units(
    text: str,
    owners: dict[str, set[str]],
    country_states: dict[str, set[str]],
    strategic_region_states: dict[str, set[str]] | None = None,
) -> tuple[str, int]:
    """Remove vanilla formation units that no longer belong to their country.

    The history parser aborts individual formation effects when a combat unit
    points at a state owned by somebody else.  Keep the surviving units and
    remove a formation only when it has no state-backed army left.  Countries
    without any state are omitted wholesale because their HQ lookup cannot
    succeed either.
    """

    country_replacements: list[tuple[int, int]] = []
    for country_match in COUNTRY_BLOCK_RE.finditer(text):
        country = country_match.group(1)
        opening = text.find("{", country_match.start(), country_match.end())
        country_end = balanced_end(text, opening)
        if not country_states.get(country):
            country_replacements.append((country_match.start(), country_end + 1))
            continue

        body_start = opening + 1
        body_end = country_end
        body = text[body_start:body_end]
        replacements: list[tuple[int, int, str]] = []
        removed_scopes: set[str] = set()
        for formation_match in FORMATION_RE.finditer(body):
            formation_opening = body.find("{", formation_match.start(), formation_match.end())
            formation_end = balanced_end(body, formation_opening)
            formation = body[formation_match.start() : formation_end + 1]
            invalid_units: list[tuple[int, int]] = []
            valid_units = 0
            for unit_match in COMBAT_UNIT_RE.finditer(formation):
                unit_opening = formation.find("{", unit_match.start(), unit_match.end())
                unit_end = balanced_end(formation, unit_opening)
                unit = formation[unit_match.start() : unit_end + 1]
                refs = STATE_REGION_REF_RE.findall(unit)
                if not refs or all(country in owners.get(state, set()) for state in refs):
                    valid_units += 1
                    continue
                invalid_units.append((unit_match.start(), unit_end + 1))

            formation_scopes = set(SAVE_SCOPE_RE.findall(formation))
            hq_match = HQ_REGION_RE.search(formation)
            hq_states = (
                strategic_region_states.get(hq_match.group(1), set())
                if hq_match and strategic_region_states is not None
                else None
            )
            hq_is_valid = hq_states is None or bool(country_states.get(country, set()) & hq_states)
            if invalid_units:
                filtered = formation
                for start, end in reversed(invalid_units):
                    filtered = filtered[:start] + filtered[end:]
            else:
                filtered = formation
            if not hq_is_valid or (invalid_units and valid_units == 0):
                removed_scopes.update(formation_scopes)
                replacement = ""
            elif invalid_units:
                replacement = filtered
            else:
                continue
            replacements.append(
                (
                    formation_match.start(),
                    formation_end + 1,
                    replacement,
                )
            )

        # A removed formation leaves a transfer_to_formation scope call behind.
        # Remove only those direct scope blocks; unrelated character history is
        # preserved.
        interim = body
        for start, end, replacement in reversed(replacements):
            interim = interim[:start] + replacement + interim[end:]

        if removed_scopes:
            scope_replacements: list[tuple[int, int]] = []
            for scope_match in SCOPE_BLOCK_RE.finditer(interim):
                scope_opening = interim.find("{", scope_match.start(), scope_match.end())
                scope_end = balanced_end(interim, scope_opening)
                scope_body = interim[scope_match.start() : scope_end + 1]
                if any(f"transfer_to_formation = scope:{scope}" in scope_body for scope in removed_scopes):
                    scope_replacements.append((scope_match.start(), scope_end + 1))
            for start, end in reversed(scope_replacements):
                interim = interim[:start] + interim[end:]

        if interim != body:
            country_replacements.append((body_start, body_end, interim))

    result = text
    for replacement in reversed(country_replacements):
        if len(replacement) == 2:
            start, end = replacement
            result = result[:start] + result[end:]
        else:
            start, end, value = replacement
            result = result[:start] + value + result[end:]
    return result, len(country_replacements)


def build_compatibility_files(game_root: Path, mod_root: Path) -> list[tuple[Path, int]]:
    """Write same-path vanilla history overrides and return changed files."""

    vanilla_state_path = game_root / "game/common/history/states/00_states.txt"
    mod_state_path = mod_root / "common/history/states/00_states.txt"
    vanilla_state = vanilla_state_path.read_text(encoding="utf-8-sig")
    vanilla_owners = ownership_by_state(vanilla_state)
    owners = ownership_by_state(mod_state_path.read_text(encoding="utf-8-sig"))
    country_states: dict[str, set[str]] = {}
    for state, state_owners in owners.items():
        for owner in state_owners:
            country_states.setdefault(owner, set()).add(state)
    strategic_region_states: dict[str, set[str]] = {}
    strategic_root = game_root / "game/common/strategic_regions"
    for source in strategic_root.glob("*.txt"):
        strategic_text = source.read_text(encoding="utf-8-sig")
        for region_match in re.finditer(
            r"(?m)^([a-z0-9_]+)[ \t]*=[ \t]*\{", strategic_text
        ):
            opening = strategic_text.find("{", region_match.start(), region_match.end())
            end = balanced_end(strategic_text, opening)
            block = strategic_text[opening : end + 1]
            states_match = re.search(r"states[ \t]*=[ \t]*\{([^}]*)\}", block)
            if states_match:
                strategic_region_states[region_match.group(1)] = set(
                    re.findall(r"STATE_[A-Z0-9_]+", states_match.group(1))
                )
    scenario_states = {
        state for state, state_owners in owners.items() if state_owners != vanilla_owners.get(state, set())
    }
    changed: list[tuple[Path, int]] = []
    for group in HISTORY_GROUPS:
        source_root = game_root / f"game/common/history/{group}"
        target_root = mod_root / f"common/history/{group}"
        for source in source_root.glob("*.txt"):
            original = source.read_text(encoding="utf-8-sig")
            filtered, removed = strip_scenario_states(original, scenario_states)
            filtered, invalid = strip_invalid_region_states(filtered, owners)
            removed += invalid
            filtered, unsupported = strip_unsupported_dlc_history(filtered)
            removed += unsupported
            if not removed:
                continue
            target = target_root / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(filtered, encoding="utf-8-sig", newline="")
            changed.append((target, removed))
    source_root = game_root / f"game/common/history/{MILITARY_GROUP}"
    target_root = mod_root / f"common/history/{MILITARY_GROUP}"
    for source in source_root.glob("*.txt"):
        original = source.read_text(encoding="utf-8-sig")
        filtered, removed = strip_invalid_military_units(
            original, owners, country_states, strategic_region_states
        )
        if not removed:
            continue
        target = target_root / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(filtered, encoding="utf-8-sig", newline="")
        changed.append((target, removed))
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--mod-root", type=Path, required=True)
    args = parser.parse_args()
    # Keep the explicit path check: the state source is part of the versioned
    # baseline even though the current implementation reads the mod ledger.
    vanilla_state_path = args.game_root / "game/common/history/states/00_states.txt"
    if not vanilla_state_path.is_file():
        raise SystemExit(f"missing game state history: {vanilla_state_path}")
    for path, removed in build_compatibility_files(args.game_root, args.mod_root):
        print(f"{path}: removed {removed} incompatible history blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
