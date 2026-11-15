"""OIR military requirements use native battalion counts, not soldier totals."""
from pathlib import Path
import unittest

from clausewitz_harness import parse
from test_v03_oir_foundation import OIRWorld


class OirBattalionUnitTests(unittest.TestCase):
    def test_supply_thresholds_keep_distinct_attainable_battalion_boundaries(self):
        world = OIRWorld()
        helpers = (("unified", 7), ("quota", 5), ("capped", 2), ("reduced", 1))
        for size in (0, 1, 2, 3, 4, 5, 6, 7, 10):
            world.countries["OIR"]["army_size"] = size
            for suffix, minimum in helpers:
                with self.subTest(battalions=size, route=suffix):
                    self.assertEqual(world.conditions(world.triggers[
                        f"ywc_oir_v03_supply_{suffix}_ready"], "OIR"), size >= minimum)

    def test_existing_two_battalions_can_support_the_capped_route_without_inflating_history(self):
        path = Path(__file__).resolve().parents[1] / "yongchang_world/common/history/military_formations/ywc_regional_military_formations.txt"
        top = parse(path.read_text(encoding="utf-8-sig"))
        def walk(nodes):
            for key, _, value in nodes:
                yield key, value
                if isinstance(value, list):
                    yield from walk(value)
        country = next(value for key, value in walk(top) if key == "c:OIR")
        count = sum(int(value) for key, value in walk(country) if key == "count")
        self.assertEqual(count, 2)
        world = OIRWorld(); world.countries["OIR"]["army_size"] = count
        self.assertTrue(world.conditions(world.triggers["ywc_oir_v03_supply_capped_ready"], "OIR"))
        self.assertFalse(world.conditions(world.triggers["ywc_oir_v03_supply_quota_ready"], "OIR"))
        self.assertFalse(world.conditions(world.triggers["ywc_oir_v03_supply_unified_ready"], "OIR"))


if __name__ == "__main__":
    unittest.main()
