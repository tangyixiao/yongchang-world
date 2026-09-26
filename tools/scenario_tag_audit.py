"""Audit scenario data and history for valid runtime country tags."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


DEPRECATED_RUNTIME_TAGS = {
    "SHN": "SHD",
    "MNG": "MGL",
}
RUNTIME_REFERENCE = re.compile(r"(?:c:|region_state:)([A-Z0-9]{3})\b")


def _diagnostic(path: Path, location: str, tag: str, allowed_tags: set[str]) -> str | None:
    replacement = DEPRECATED_RUNTIME_TAGS.get(tag)
    if replacement:
        return f"{path}:{location}: legacy runtime tag {tag}; use {replacement}"
    if tag not in allowed_tags:
        return f"{path}:{location}: unknown runtime country tag {tag}"
    return None


def audit_references(
    text: str,
    path: Path,
    allowed_tags: set[str],
) -> list[str]:
    """Check ``c:TAG`` and ``region_state:TAG`` references in script text."""

    diagnostics: list[str] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        code = line.split("#", 1)[0]
        for match in RUNTIME_REFERENCE.finditer(code):
            diagnostic = _diagnostic(path, str(line_number), match.group(1), allowed_tags)
            if diagnostic:
                diagnostics.append(diagnostic)
    return diagnostics


def _tag_values(value: Any, key: str) -> Iterable[tuple[str, str]]:
    if key == "country_population" and isinstance(value, dict):
        yield from ((str(tag), f"{key}.{tag}") for tag in value)
    elif key == "state_owners" and isinstance(value, dict):
        for state, owners in value.items():
            for tag in str(owners).split("/"):
                yield tag, f"{key}.{state}"
    elif key in {"owner", "target_country"} and isinstance(value, str):
        yield value, key
    elif key in {"starting_tags", "releasable_tags"} and isinstance(value, list):
        yield from ((str(tag), f"{key}[{index}]") for index, tag in enumerate(value))
    elif key.endswith("_owner") and isinstance(value, str):
        yield value, key


def _audit_json_value(
    value: Any,
    path: Path,
    allowed_tags: set[str],
    location: str = "$",
) -> list[str]:
    diagnostics: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            for tag, field in _tag_values(child, str(key)):
                diagnostic = _diagnostic(path, f"{location}.{field}", tag, allowed_tags)
                if diagnostic:
                    diagnostics.append(diagnostic)
            diagnostics.extend(
                _audit_json_value(child, path, allowed_tags, f"{location}.{key}")
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            diagnostics.extend(
                _audit_json_value(child, path, allowed_tags, f"{location}[{index}]")
            )
    return diagnostics


def _allowed_tags(root: Path) -> set[str]:
    baseline = json.loads(
        (root / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8")
    )
    registry = json.loads(
        (root / "data/scenario/tag_registry.json").read_text(encoding="utf-8")
    )
    return set(baseline["country_tags"]) | {
        row["tag"] for row in registry["countries"]
    }


def audit_repository_tags(root: Path) -> list[str]:
    """Return diagnostics for scenario JSON and Mod country-history references."""

    root = Path(root)
    allowed_tags = _allowed_tags(root)
    diagnostics: list[str] = []
    scenario_root = root / "data/scenario"
    for path in sorted(scenario_root.glob("*.json")):
        if path.name == "tag_registry.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        diagnostics.extend(_audit_json_value(payload, path, allowed_tags))

    mod_root = root / "yongchang_world"
    for path in sorted(mod_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".txt", ".gui", ".asset", ".gfx"}:
            diagnostics.extend(
                audit_references(path.read_text(encoding="utf-8-sig"), path, allowed_tags)
            )
    return diagnostics


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    diagnostics = audit_repository_tags(args.root)
    for diagnostic in diagnostics:
        print(diagnostic)
    return 1 if diagnostics else 0


if __name__ == "__main__":
    raise SystemExit(main())
