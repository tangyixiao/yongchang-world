"""Render one registered v0.3 catalog in isolation, for any layer.

`tools/build_v03_country.py` only accepts `country_*` catalogs because it strips
that prefix to find the file. The crisis, regional and theme layers need the
same isolated build path so parallel authors never regenerate each other's
outputs, so this helper matches the catalog by its registered path stem
instead of by a hardcoded prefix.

`tools/build_v03_content.py --check` remains the release gate and still
validates the whole manifest.
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
    load_catalogs,
    read_manifest,
    render_country_adapters,
    render_inline_country_adapters,
    validate_catalogs_at,
)

_ADAPTER_COUNTRIES = {
    "country_dmg": "DMG",
    "country_kor": "KOR",
    "country_nqg": "NQG",
    "country_shu": "SHU",
    "country_lan": "LAN",
    "country_nmg": "NMG",
    "country_mgl": "MGL",
    "country_jhg": "JHG",
    "country_tib": "TIB",
}


def _catalog_path(root: Path, key: str) -> Path:
    manifest = read_manifest(root)
    matches = [root / relative for relative in manifest["catalogs"] if Path(relative).stem == key]
    if len(matches) != 1:
        raise ValueError(f"manifest must register exactly one catalog for {key}")
    return matches[0]


def render_catalog(root: Path, key: str) -> dict[Path, str]:
    """Return {relative output path: text} for one registered catalog."""
    root = Path(root)
    catalog_path = _catalog_path(root, key)
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read {catalog_path}: {exc}") from exc
    if catalog.get("key") != key:
        raise ValueError(f"{catalog_path} declares key {catalog.get('key')!r}, not {key!r}")
    # Arcs may legitimately depend on an arc owned by another catalog (a theme arc
    # gated on a country settlement, a crisis arc gated on a regional decision).
    # Validate the whole registry so the dependency graph is complete, but render
    # only this catalog's own outputs.
    catalogs = load_catalogs(root)
    catalogs[key] = catalog
    errors = validate_catalogs_at(root, catalogs)
    if errors:
        raise ValueError("invalid catalog:\n" + "\n".join(errors))
    if not any(arc["events"] or arc["journals"] for arc in catalog["arcs"]):
        return {}
    arcs = catalog.get("arcs", [])
    has_delivery = any("delivery_adapter" in arc for arc in arcs)
    has_inline = any("inline_delivery_adapter" in arc for arc in arcs)
    has_adapter = has_delivery or has_inline
    if has_delivery:
        adapter = render_country_adapters(catalog)
    elif has_inline:
        adapter = render_inline_country_adapters(catalog)
    else:
        adapter = None
    paths = _outputs_for(key, adapter=has_adapter)
    rendered = [
        _render_event_file(catalog, root, adapter),
        _render_journal_file(catalog, adapter),
        _render_localization(catalog, "zh"),
        _render_localization(catalog, "en"),
    ]
    if adapter:
        if key == "country_oir":
            rendered += [
                "# Generated OIR scheduler scripted effects.\n\n" + adapter["effects"],
                "# Generated OIR scheduler scripted triggers.\n\n" + adapter["triggers"],
            ]
        else:
            country = _ADAPTER_COUNTRIES.get(key)
            if not country:
                raise ValueError(f"{key} declares an adapter but has no scheduler output contract")
            rendered += [
                f"# Generated {country} inline delivery scheduler scripted effects.\n\n" + adapter["effects"],
                f"# Generated {country} inline delivery scheduler scripted triggers.\n\n" + adapter["triggers"],
            ]
    return dict(zip(paths, rendered))


def build_catalog(root: Path, key: str) -> list[str]:
    root = Path(root)
    try:
        outputs = render_catalog(root, key)
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


def check_catalog(root: Path, key: str) -> list[str]:
    root = Path(root)
    try:
        outputs = render_catalog(root, key)
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
    parser.add_argument("--key", required=True, help="catalog key, for example crisis_c01 or theme_t01")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    errors = check_catalog(args.root, args.key) if args.check else build_catalog(args.root, args.key)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"{args.key} output is current" if args.check else f"{args.key} output generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
