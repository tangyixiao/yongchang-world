"""Regression checks for the expanded northern frontier and rebuilt history."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
BASELINE = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text("utf-8"))
AUTHORITY = json.loads((ROOT / "data/scenario/ownership_overrides.json").read_text("utf-8"))
MANIFEST = json.loads((ROOT / "data/scenario/northern_expansion_manifest.json").read_text("utf-8"))
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")

from tools.build_state_history import balanced_end


def blocks(text: str, pattern: str):
    for match in re.finditer(pattern, text):
        opening = text.index("{", match.start(), match.end())
        end = balanced_end(text, opening) + 1
        yield match.group(1), text[match.start():end]


def final_owners() -> dict[str, str]:
    owners = {
        province: group["country"]
        for groups in BASELINE["states"].values()
        for group in groups
        for province in group["owned_provinces"]
    }
    for row in AUTHORITY["states"]:
        for province in BASELINE["state_regions"][row["state"]]:
            owners.pop(province, None)
        for group in row["groups"]:
            for province in group["owned_provinces"]:
                owners[province] = group["owner"]
    return owners


class NorthernExpansionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
            from PIL import Image
        except ImportError as error:
            raise unittest.SkipTest(f"map topology dependencies unavailable: {error}")
        map_path = GAME / "map_data/provinces.png"
        if not map_path.is_file():
            raise unittest.SkipTest(f"installed province map unavailable: {map_path}")
        with Image.open(map_path) as image:
            rgb = np.asarray(image.convert("RGB"), dtype=np.uint32)
        pixels = rgb[:, :, 0] * 65536 + rgb[:, :, 1] * 256 + rgb[:, :, 2]
        provinces = {province for state in BASELINE["state_regions"].values() for province in state}
        code_to_province = {int(province[1:], 16): province for province in provinces}
        province_codes = np.asarray(list(code_to_province), dtype=np.uint32)
        cls.adjacency = {province: set() for province in provinces}
        for first, second in ((pixels[:, :-1], pixels[:, 1:]), (pixels[:-1, :], pixels[1:, :])):
            changed = first != second
            pairs = np.unique(np.stack((first[changed], second[changed]), axis=1), axis=0)
            pairs = pairs[np.isin(pairs[:, 0], province_codes) & np.isin(pairs[:, 1], province_codes)]
            for left, right in pairs:
                a, b = code_to_province[int(left)], code_to_province[int(right)]
                cls.adjacency[a].add(b)
                cls.adjacency[b].add(a)
        cls.owners = final_owners()

    def components(self, provinces: set[str]) -> list[int]:
        remaining = set(provinces)
        sizes = []
        while remaining:
            component = {remaining.pop()}
            frontier = list(component)
            while frontier:
                for neighbor in self.adjacency[frontier.pop()] & remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    frontier.append(neighbor)
            sizes.append(len(component))
        return sorted(sizes, reverse=True)

    def test_frontier_polities_and_russia_keep_a_connected_mainland(self):
        for tag in ("BYL", "JTR", "KZH", "KER", "OZH", "NMN", "UZH", "ZHL", "ABN",
                    "BKY", "OIR", "CHI", "MGL", "SOL", "HUL"):
            with self.subTest(tag=tag):
                provinces = {province for province, owner in self.owners.items() if owner == tag}
                self.assertEqual(self.components(provinces), [len(provinces)])
        russian = {province for province, owner in self.owners.items() if owner == "RUS"}
        russian_components = self.components(russian)
        self.assertGreaterEqual(russian_components[0] / len(russian), 0.98)
        # BKY is Russia's protectorate and must physically touch Russian land.
        bukey = {province for province, owner in self.owners.items() if owner == "BKY"}
        self.assertTrue(any(self.adjacency[province] & russian for province in bukey))

    def test_northern_history_conserves_population_and_building_levels(self):
        expected = {
            "pops": sum(row["before"] for row in MANIFEST["population_totals"]),
            "buildings": sum(row["before"] for row in MANIFEST["building_totals"]),
        }
        paths = {
            "pops": ROOT / "yongchang_world/common/history/pops/ywc_northern_expansion_pops.txt",
            "buildings": ROOT / "yongchang_world/common/history/buildings/ywc_northern_expansion_buildings.txt",
        }
        for category, path in paths.items():
            actual = 0
            text = path.read_text("utf-8-sig")
            effect = "create_pop" if category == "pops" else "create_building"
            for _, record in blocks(text, rf"(?m)^\s*({effect})\s*=\s*\{{"):
                match = re.search(r"\b(?:size|levels?)\s*=\s*(\d+)", record)
                actual += int(match.group(1)) if match else 1
            self.assertEqual(actual, expected[category], category)
        self.assertNotIn("pm_irregular_infantry", paths["buildings"].read_text("utf-8-sig"))

    def test_custom_buildings_only_reference_regions_the_owner_holds(self):
        owner_states: dict[str, set[str]] = {}
        for state, groups in BASELINE["states"].items():
            for group in groups:
                owner_states.setdefault(group["country"], set()).add(state)
        for row in AUTHORITY["states"]:
            for group in row["groups"]:
                owner_states.setdefault(group["owner"], set()).add(row["state"])
        for path in (ROOT / "yongchang_world/common/history/buildings").glob("ywc_*.txt"):
            text = path.read_text("utf-8-sig")
            for state, state_body in blocks(text, r"(?m)^\s*s:(STATE_[A-Z0-9_]+)\s*=\s*\{"):
                for _, record in blocks(state_body, r"(?m)^\s*(create_building)\s*=\s*\{"):
                    owner = re.search(r'\bcountry\s*=\s*"c:([A-Z0-9_]+)"', record)
                    region = re.search(r'\bregion\s*=\s*"(STATE_[A-Z0-9_]+)"', record)
                    if owner and region:
                        with self.subTest(path=path.name, owner=owner.group(1), region=region.group(1)):
                            self.assertIn(region.group(1), owner_states.get(owner.group(1), set()))

    def test_manifest_reports_the_current_russian_and_internal_transfers(self):
        russian = sum(row["province_count"] for row in MANIFEST["transfers"] if row["from"] == "RUS")
        internal = sum(row["province_count"] for row in MANIFEST["transfers"] if row["from"] != "RUS")
        self.assertEqual(russian, MANIFEST["russian_land_acquired_increment"])
        self.assertEqual(internal, MANIFEST["internal_frontier_increment"])
        self.assertEqual(russian, 311)


if __name__ == "__main__":
    unittest.main()
