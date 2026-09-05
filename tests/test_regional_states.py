import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
REGISTRY_FILE = ROOT / "data/scenario/tag_registry.json"
COUNTRY_FILE = ROOT / "yongchang_world/common/country_definitions/ywc_regional_countries.txt"

REGIONAL_NEW = {
    "MHG", "WBK", "KHQ", "HUL", "SOL", "AMR", "OIR", "KJU", "MJU", "GJU",
    "KHO", "HMI", "TRF", "KUC", "KSH", "YRK", "KHT", "DER", "KAM", "GYL",
    "LXJ", "LJG", "SIP", "KTG", "WAA", "KCH", "AHM", "AMD", "DLI", "PNP",
    "PLW", "YAP", "MHL", "MRG",
}


class RegionalTagRegistryTest(unittest.TestCase):
    def test_regional_tags_are_new_and_registered(self):
        registry = json.loads(REGISTRY_FILE.read_text("utf-8"))
        rows = {row["tag"]: row for row in registry["countries"]}
        self.assertTrue(REGIONAL_NEW.issubset(rows))
        for tag in REGIONAL_NEW:
            self.assertEqual(rows[tag]["mode"], "new")
            self.assertIsNone(rows[tag]["source_tag"])


class RegionalCountryDefinitionTest(unittest.TestCase):
    def test_regional_country_definitions_have_capital_and_culture(self):
        text = COUNTRY_FILE.read_text("utf-8")
        for tag in REGIONAL_NEW:
            match = re.search(rf"(?m)^\s*{tag}\s*=\s*\{{[^\n]*\}}", text)
            self.assertIsNotNone(match, tag)
            block = match.group(0)
            self.assertRegex(block, r"capital\s*=\s*STATE_[A-Z0-9_]+")
            self.assertRegex(block, r"cultures\s*=\s*\{[^}]+\}")


if __name__ == "__main__":
    unittest.main()
