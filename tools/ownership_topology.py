"""Audit province-group connectivity in the scenario ownership authority.

The ownership table deliberately contains some island and archipelago groups.
This tool makes those exceptions measurable without treating them as parser or
campaign evidence.  Adjacency is derived from the installed game's
``provinces.png`` rather than from province-list order.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Mapping


def component_sizes(
    provinces: Iterable[str],
    adjacency: Mapping[str, set[str]],
) -> list[int]:
    """Return connected-component sizes for one ownership group, descending."""

    remaining = set(provinces)
    sizes: list[int] = []
    while remaining:
        component = {remaining.pop()}
        frontier = list(component)
        while frontier:
            province = frontier.pop()
            for neighbor in adjacency[province] & remaining:
                remaining.remove(neighbor)
                component.add(neighbor)
                frontier.append(neighbor)
        sizes.append(len(component))
    return sorted(sizes, reverse=True)


def _state_adjacency(
    state_provinces: Iterable[str],
    encoded_pixels,
    np,
) -> dict[str, set[str]]:
    province_codes = {int(province[1:], 16): province for province in state_provinces}
    codes = np.array(list(province_codes), dtype=np.uint32)
    adjacency = {province: set() for province in province_codes.values()}
    for first, second in (
        (encoded_pixels[:, :-1], encoded_pixels[:, 1:]),
        (encoded_pixels[:-1, :], encoded_pixels[1:, :]),
    ):
        changed = first != second
        first_values = first[changed]
        second_values = second[changed]
        target = np.isin(first_values, codes) & np.isin(second_values, codes)
        pairs = np.unique(
            np.stack((first_values[target], second_values[target]), axis=1),
            axis=0,
        )
        for first_code, second_code in pairs:
            first_province = province_codes[int(first_code)]
            second_province = province_codes[int(second_code)]
            adjacency[first_province].add(second_province)
            adjacency[second_province].add(first_province)
    return adjacency


def audit_ownership_topology(
    baseline_path: Path,
    overrides_path: Path,
    provinces_map_path: Path,
) -> list[dict[str, object]]:
    """Return connectivity metrics for every multi-owner authority group."""

    try:
        import numpy as np
        from PIL import Image
    except ImportError as error:  # pragma: no cover - environment dependent.
        raise RuntimeError("Pillow and NumPy are required for map topology audits") from error

    if not provinces_map_path.is_file():
        raise RuntimeError(f"province map does not exist: {provinces_map_path}")

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    authority = json.loads(overrides_path.read_text(encoding="utf-8"))
    with Image.open(provinces_map_path) as image:
        pixels = np.asarray(image.convert("RGB"), dtype=np.uint32)
    encoded_pixels = pixels[:, :, 0] * 65536 + pixels[:, :, 1] * 256 + pixels[:, :, 2]

    rows: list[dict[str, object]] = []
    for state_row in authority["states"]:
        state = state_row["state"]
        groups = state_row["groups"]
        if len(groups) <= 1:
            continue
        adjacency = _state_adjacency(
            baseline["state_regions"][state],
            encoded_pixels,
            np,
        )
        for group in groups:
            sizes = component_sizes(group["owned_provinces"], adjacency)
            total = len(group["owned_provinces"])
            rows.append(
                {
                    "state": state,
                    "owner": group["owner"],
                    "province_count": total,
                    "components": sizes,
                    "largest_component_ratio": sizes[0] / total if total else 0.0,
                    "topology_exception": group.get("topology_exception"),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--overrides", type=Path, required=True)
    parser.add_argument("--provinces-map", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--weak-only", action="store_true")
    args = parser.parse_args()

    try:
        rows = audit_ownership_topology(args.baseline, args.overrides, args.provinces_map)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        parser.error(str(error))

    for row in rows:
        if args.weak_only and row["largest_component_ratio"] >= args.threshold:
            continue
        components = ",".join(str(size) for size in row["components"])
        exception = row["topology_exception"] or "none"
        print(
            f'{row["state"]} {row["owner"]} '
            f'{row["province_count"]} provinces [{components}] '
            f'ratio={row["largest_component_ratio"]:.3f} '
            f'exception={exception}'
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
