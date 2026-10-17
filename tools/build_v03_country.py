"""Render a single v0.3 country catalog in isolation.

`tools/build_v03_content.py` validates every manifest catalog before rendering,
which makes concurrent country authoring brittle: one half-written sibling
catalog blocks every other author's build. This helper validates and renders
exactly one registered country catalog, so parallel authors never touch each
other's generated outputs. `build_v03_content.py --check` remains the release
gate and still validates the whole manifest.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.build_v03_content import (  # noqa: E402
    _outputs_for,
    _render_event_file,
    _render_journal_file,
    _render_localization,
    _safe_relative,
    read_manifest,
    validate_catalogs_at,
)


def _catalog_path(root: Path, key: str) -> Path:
    manifest = read_manifest(root)
    tag = key.removeprefix("country_")
    matches = [root / relative for relative in manifest["catalogs"] if Path(relative).stem == tag]
    if len(matches) != 1:
        raise ValueError(f"manifest must register exactly one catalog for {key}")
    return matches[0]


def render_country(root: Path, key: str) -> dict[Path, str]:
    """Return {relative output path: text} for one registered country catalog."""
    root = Path(root)
    catalog_path = _catalog_path(root, key)
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read {catalog_path}: {exc}") from exc
    if catalog.get("key") != key:
        raise ValueError(f"{catalog_path} declares key {catalog.get('key')!r}, not {key!r}")
    errors = validate_catalogs_at(root, {key: catalog})
    if errors:
        raise ValueError("invalid catalog:\n" + "\n".join(errors))
    if not any(arc["events"] or arc["journals"] for arc in catalog["arcs"]):
        return {}
    paths = _outputs_for(key)
    rendered = [
        _render_event_file(catalog, root),
        _render_journal_file(catalog),
        _render_localization(catalog, "zh"),
        _render_localization(catalog, "en"),
    ]
    return dict(zip(paths, rendered))


def build_country(root: Path, key: str) -> list[str]:
    root = Path(root)
    try:
        outputs = render_country(root, key)
        owned = set(read_manifest(root)["owned_outputs"])
    except ValueError as exc:
        return [str(exc)]
    if not outputs:
        return [f"{key} has no authored arcs; nothing to render"]
    errors: list[str] = []
    planned: list[tuple[Path, str]] = []
    for relative, text in outputs.items():
        if relative.as_posix() not in owned:
            errors.append(f"manifest.owned_outputs missing catalog path: {relative.as_posix()}")
            continue
        try:
            planned.append((_safe_relative(root / "yongchang_world", relative.as_posix()), text))
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        return errors
    for destination, text in planned:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8-sig", newline="\n")
    return []


def check_country(root: Path, key: str) -> list[str]:
    root = Path(root)
    try:
        outputs = render_country(root, key)
    except ValueError as exc:
        return [str(exc)]
    errors: list[str] = []
    for relative, expected in outputs.items():
        path = root / "yongchang_world" / relative
        if not path.is_file():
            errors.append(f"generated output is missing: {path}")
            continue
        if not path.read_bytes().startswith(b"\xef\xbb\xbf"):
            errors.append(f"generated output is missing UTF-8 BOM: {path}")
            continue
        if path.read_text(encoding="utf-8-sig") != expected:
            errors.append(f"stale generated output mismatch: {path}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--country", required=True, help="catalog key, for example country_jhg")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    errors = check_country(args.root, args.country) if args.check else build_country(args.root, args.country)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"{args.country} output is current" if args.check else f"{args.country} output generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())