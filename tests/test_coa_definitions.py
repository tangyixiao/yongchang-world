import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
COA = ROOT / "yongchang_world/common/coat_of_arms/coat_of_arms/ywc_core_coas.txt"


class CoADefinitionsTest(unittest.TestCase):
    def test_custom_coas_use_vanilla_geometric_patterns(self):
        text = COA.read_text("utf-8")
        definitions = re.findall(
            r"(?m)^(YWC_[A-Z]+(?:_MARITIME)?)\s*=\s*\{([^}]*)\}",
            text,
        )
        self.assertEqual(len(definitions), 20)
        allowed_patterns = {
            "pattern_circle.dds",
            "pattern_cross.dds",
             "pattern_gironny_8.dds",
             "pattern_gironny_12.dds",
             "pattern_gironny_16.dds",
             "pattern_lozengy_bend.dds",
            "pattern_per_bend.dds",
            "pattern_per_saltire.dds",
            "pattern_border_of_3.dds",
            "pattern_border_of_4.dds",
        }
        for name, body in definitions:
            match = re.search(r'pattern\s*=\s*"([^"]+)"', body)
            self.assertIsNotNone(match, name)
            self.assertNotEqual(match.group(1), "pattern_solid.tga", name)
            self.assertIn(match.group(1), allowed_patterns, name)


if __name__ == "__main__":
    unittest.main()
