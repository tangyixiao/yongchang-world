"""Export the small, deterministic Victoria 3 data baseline used by the mod tests."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


BASELINE_VERSION = "1.13.11"
_COUNTRY_START = re.compile(r"(?m)^\s*([A-Z][A-Z0-9]{2})\s*=\s*\{")
_STATE_REGION_START = re.compile(r"(?m)^\s*(STATE_[A-Z0-9_]+)\s*=\s*\{")
_HISTORY_STATE_START = re.compile(r"(?m)^\s*s:(STATE_[A-Z0-9_]+)\s*=\s*\{")
_CREATE_STATE_START = re.compile(r"(?m)\b(create_state)\s*=\s*\{")


def strip_comments(text: str) -> str:
    """Remove Clausewitz line comments without touching quoted strings."""

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
            output.append(char)
            escaped = False
            continue
        if char == "\\" and in_string:
            output.append(char)
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            output.append(char)
            continue
        if char == "#" and not in_string:
            in_comment = True
            output.append(" ")
            continue
        output.append(char)
    return "".join(output)


def _matching_brace(text: str, opening: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unclosed brace")


def _blocks(text: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    cleaned = strip_comments(text)
    blocks: list[tuple[str, str]] = []
    for match in pattern.finditer(cleaned):
        opening = cleaned.find("{", match.start(), match.end())
        closing = _matching_brace(cleaned, opening)
        blocks.append((match.group(1), cleaned[opening + 1 : closing]))
    return blocks


def _values_in_block(body: str, key: str) -> list[str]:
    match = re.search(
        rf"(?m)\b{re.escape(key)}\s*=\s*\{{(?P<body>.*?)\}}",
        body,
        re.DOTALL,
    )
    if not match:
        return []
    return sorted(set(re.findall(r'"([^"]+)"|\b(x[0-9A-Fa-f]{6})\b', match.group("body"))))


def _flatten_values(values: list[tuple[str, str]]) -> list[str]:
    return sorted({quoted or bare for quoted, bare in values})


def _state_provinces(body: str) -> list[str]:
    match = re.search(
        r"(?m)\b(?:provinces|owned_provinces)\s*=\s*\{(?P<body>.*?)\}",
        body,
        re.DOTALL,
    )
    if not match:
        return []
    return _flatten_values(
        re.findall(r'"(x[0-9A-Fa-f]{6})"|\b(x[0-9A-Fa-f]{6})\b', match.group("body"))
    )


def _country_tags(game_root: Path) -> list[str]:
    tags: set[str] = set()
    directory = game_root / "common/country_definitions"
    for path in sorted(directory.glob("*.txt")):
        tags.update(tag for tag, _ in _blocks(path.read_text(encoding="utf-8-sig"), _COUNTRY_START))
    return sorted(tags)


def _state_regions(game_root: Path) -> dict[str, list[str]]:
    regions: dict[str, list[str]] = {}
    directory = game_root / "map_data/state_regions"
    for path in sorted(directory.glob("*.txt")):
        for name, body in _blocks(path.read_text(encoding="utf-8-sig"), _STATE_REGION_START):
            regions[name] = _state_provinces(body)
    return dict(sorted(regions.items()))


def _history_states(game_root: Path) -> dict[str, list[dict[str, object]]]:
    path = game_root / "common/history/states/00_states.txt"
    states: dict[str, list[dict[str, object]]] = {}
    for name, body in _blocks(path.read_text(encoding="utf-8-sig"), _HISTORY_STATE_START):
        owners: list[dict[str, object]] = []
        for _, create_body in _blocks(body, _CREATE_STATE_START):
            country_match = re.search(r"\bcountry\s*=\s*c:([A-Z0-9]{3})\b", create_body)
            owners.append(
                {
                    "country": country_match.group(1) if country_match else None,
                    "owned_provinces": _state_provinces(create_body),
                }
            )
        states[name] = owners
    return dict(sorted(states.items()))


def export_baseline(game_root: Path) -> dict[str, object]:
    game_root = Path(game_root)
    required = [
        game_root / "common/country_definitions",
        game_root / "map_data/state_regions",
        game_root / "common/history/states/00_states.txt",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Victoria 3 baseline input missing: " + ", ".join(missing))
    return {
        "version": BASELINE_VERSION,
        "country_tags": _country_tags(game_root),
        "state_regions": _state_regions(game_root),
        "states": _history_states(game_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = export_baseline(args.game_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
