"""Build the Yongchang state-history override from one ownership authority."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


GAME_VERSION = "1.13.11"
STATE_ENTRY_RE = re.compile(r"(?m)^[ \t]*s:([A-Z0-9_]+)[ \t]*=[ \t]*\{")
CREATE_STATE_RE = re.compile(r"(?m)^[ \t]*create_state[ \t]*=[ \t]*\{")
COUNTRY_RE = re.compile(r"(?m)^([ \t]*)country[ \t]*=[ \t]*c:([A-Z0-9_]+)")
PROVINCE_OPEN_RE = re.compile(r"(?m)^([ \t]*)owned_provinces[ \t]*=[ \t]*\{")

HAN_CORE_STATES = {
    "STATE_BEIJING",
    "STATE_ZHILI",
    "STATE_SHANXI",
    "STATE_SHANDONG",
    "STATE_HENAN",
    "STATE_XIAN",
    "STATE_NINGXIA",
    "STATE_GANSU",
    "STATE_SICHUAN",
    "STATE_CHONGQING",
    "STATE_GUIZHOU",
    "STATE_YUNNAN",
    "STATE_GUANGXI",
    "STATE_GUANGDONG",
    "STATE_SHAOZHOU",
    "STATE_FUJIAN",
    "STATE_ZHEJIANG",
    "STATE_JIANGXI",
    "STATE_HUNAN",
    "STATE_EASTERN_HUBEI",
    "STATE_WESTERN_HUBEI",
    "STATE_NORTHERN_ANHUI",
    "STATE_SOUTHERN_ANHUI",
    "STATE_JIANGSU",
    "STATE_NANJING",
    "STATE_SUZHOU",
}


def balanced_end(text: str, opening: int) -> int:
    depth = 0
    quoted = False
    escaped = False
    comment = False
    for index in range(opening, len(text)):
        char = text[index]
        if comment:
            if char == "\n":
                comment = False
            continue
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == "#":
            comment = True
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"unclosed brace at offset {opening}")


def load_baseline(path: Path) -> dict:
    data = json.loads(path.read_text("utf-8"))
    if data.get("version") != GAME_VERSION:
        raise ValueError(f"baseline version must be {GAME_VERSION}")
    if not isinstance(data.get("state_regions"), dict) or not isinstance(data.get("states"), dict):
        raise ValueError("baseline must contain state_regions and states")
    return data


def state_blocks(text: str, baseline: dict) -> dict[str, str]:
    matches = list(STATE_ENTRY_RE.finditer(text))
    blocks: dict[str, str] = {}
    for match in matches:
        state = match.group(1)
        if state in blocks:
            raise ValueError(f"duplicate runtime state block: {state}")
        opening = text.find("{", match.start(), match.end())
        end = balanced_end(text, opening)
        blocks[state] = text[match.start() : end + 1]
    expected = set(baseline["states"])
    if set(blocks) != expected:
        missing = sorted(expected - set(blocks))
        extra = sorted(set(blocks) - expected)
        raise ValueError(f"runtime state coverage differs from baseline: missing={missing[:5]} extra={extra[:5]}")
    return blocks


def extract_groups(block: str) -> list[dict]:
    groups = []
    for match in CREATE_STATE_RE.finditer(block):
        opening = block.find("{", match.start(), match.end())
        end = balanced_end(block, opening)
        create = block[match.start() : end + 1]
        country = COUNTRY_RE.search(create)
        provinces = PROVINCE_OPEN_RE.search(create)
        if country is None or provinces is None:
            raise ValueError("create_state must contain country and owned_provinces")
        province_opening = create.find("{", provinces.start(), provinces.end())
        province_end = balanced_end(create, province_opening)
        values = create[province_opening + 1 : province_end].split()
        groups.append({"owner": country.group(2), "owned_provinces": values})
    if not groups:
        raise ValueError("state has no create_state block")
    return groups


def validate_overrides(overrides: dict, baseline: dict) -> None:
    rows = overrides.get("states")
    if overrides.get("version") != GAME_VERSION or not isinstance(rows, list):
        raise ValueError("overrides must use the 1.13.11 states schema")
    names = [row.get("state") for row in rows]
    if len(names) != len(set(names)):
        raise ValueError("duplicate state in ownership overrides")
    for row in rows:
        state = row.get("state")
        if state not in baseline["state_regions"]:
            raise ValueError(f"unknown state in ownership overrides: {state}")
        groups = row.get("groups")
        if not isinstance(groups, list) or not groups:
            raise ValueError(f"{state}: groups must be non-empty")
        provinces = []
        for group in groups:
            owner = group.get("owner")
            if not isinstance(owner, str) or owner in {"AIN", "ALK"}:
                raise ValueError(f"{state}: invalid owner {owner}")
            values = group.get("owned_provinces")
            if not isinstance(values, list) or not values:
                raise ValueError(f"{state}: group {owner} has no provinces")
            provinces.extend(values)
        if len(provinces) != len(set(provinces)):
            raise ValueError(f"{state}: overlapping provinces")
        if set(provinces) != set(baseline["state_regions"][state]):
            raise ValueError(f"{state}: override does not cover vanilla state exactly")


def override_map(overrides: dict) -> dict[str, list[dict]]:
    return {row["state"]: row["groups"] for row in overrides["states"]}


def replace_state_block(block: str, groups: list[dict]) -> str:
    matches = list(CREATE_STATE_RE.finditer(block))
    if len(matches) != len(groups):
        raise ValueError(f"runtime group count {len(matches)} differs from override count {len(groups)}")
    replacements = []
    for match, group in zip(matches, groups):
        opening = block.find("{", match.start(), match.end())
        end = balanced_end(block, opening)
        create = block[match.start() : end + 1]
        country = COUNTRY_RE.search(create)
        provinces = PROVINCE_OPEN_RE.search(create)
        if country is None or provinces is None:
            raise ValueError("create_state must contain country and owned_provinces")
        create = create[: country.start(2)] + group["owner"] + create[country.end(2) :]
        provinces = PROVINCE_OPEN_RE.search(create)
        province_opening = create.find("{", provinces.start(), provinces.end())
        province_end = balanced_end(create, province_opening)
        indent = provinces.group(1)
        replacement = f"{indent}owned_provinces = {{ {' '.join(group['owned_provinces'])} }}"
        create = create[: provinces.start()] + replacement + create[province_end + 1 :]
        replacements.append((match.start(), end + 1, create))
    result = block
    for start, end, replacement in reversed(replacements):
        result = result[:start] + replacement + result[end:]
    return result


def apply_overrides(template: str, baseline: dict, overrides: dict) -> str:
    validate_overrides(overrides, baseline)
    blocks = state_blocks(template, baseline)
    mapping = override_map(overrides)
    result = template
    replacements = []
    for match in STATE_ENTRY_RE.finditer(template):
        state = match.group(1)
        if state not in mapping:
            continue
        opening = template.find("{", match.start(), match.end())
        end = balanced_end(template, opening)
        replacements.append((match.start(), end + 1, replace_state_block(blocks[state], mapping[state])))
    for start, end, replacement in reversed(replacements):
        result = result[:start] + replacement + result[end:]
    return result


def scenario_source_states(scenario_root: Path) -> set[str]:
    names = set()
    core = json.loads((scenario_root / "core_states.json").read_text("utf-8"))
    names.update(row["state"] for row in core["states"])
    for name in ("northeast_states", "inner_asia_states", "southwest_states", "ocean_states"):
        data = json.loads((scenario_root / f"{name}.json").read_text("utf-8"))
        names.update(data["source_states"])
    return names


def bootstrap_overrides(template: str, baseline: dict, scenario_root: Path) -> dict:
    blocks = state_blocks(template, baseline)
    custom_states = scenario_source_states(scenario_root)
    rows = []
    for state in sorted(custom_states | HAN_CORE_STATES):
        if state in custom_states:
            groups = extract_groups(blocks[state])
        else:
            groups = extract_groups(blocks[state])
            for group in groups:
                if group["owner"] == "CHI":
                    group["owner"] = "SHU"
        rows.append({"state": state, "groups": groups})
    overrides = {"version": GAME_VERSION, "states": rows}
    validate_overrides(overrides, baseline)
    return overrides


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--game-root", type=Path, default=None)
    parser.add_argument("--overrides", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario-root", type=Path, default=None)
    parser.add_argument("--bootstrap", action="store_true")
    args = parser.parse_args()
    try:
        baseline = load_baseline(args.baseline)
        template = args.template.read_text("utf-8-sig")
        if args.bootstrap:
            scenario_root = args.scenario_root or args.baseline.parents[1] / "scenario"
            write_json(args.overrides, bootstrap_overrides(template, baseline, scenario_root))
            print(f"Wrote ownership authority: {args.overrides}")
            return 0
        overrides = json.loads(args.overrides.read_text("utf-8"))
        result = apply_overrides(template, baseline, overrides)
        encoding = "utf-8-sig" if args.template.read_bytes().startswith(b"\xef\xbb\xbf") else "utf-8"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding=encoding, newline="")
        print(f"Wrote state history: {args.output}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
