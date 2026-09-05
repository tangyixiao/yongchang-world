import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
CATALOG = ROOT / "data/content/content_catalog.json"
ZH = ROOT / "yongchang_world/localization/simp_chinese/ywc_content_l_simp_chinese.yml"
EN = ROOT / "yongchang_world/localization/english/ywc_content_l_english.yml"
ZH_DIR = ZH.parent
EN_DIR = EN.parent
IG = ROOT / "yongchang_world/common/interest_groups/ywc_interest_groups.txt"
IDEOLOGY = ROOT / "yongchang_world/common/ideologies/ywc_ideologies.txt"
NAMES = ROOT / "yongchang_world/common/dynamic_country_names/ywc_dynamic_names.txt"
COLORS = ROOT / "yongchang_world/common/dynamic_country_map_colors/ywc_dynamic_colors.txt"
FLAGS = ROOT / "yongchang_world/common/flag_definitions/ywc_flags.txt"


def load_yaml_keys(path):
    paths = [path] if path.is_file() else sorted(path.rglob("*.yml"))
    return {
        match.group(1)
        for source in paths
        for line in source.read_text("utf-8-sig").splitlines()
        if (match := re.match(r"^\s*([A-Za-z0-9_.]+):", line))
    }


class ContentLocalizationTest(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG.read_text("utf-8"))["countries"]

    def test_every_catalog_key_exists_in_both_languages(self):
        expected = set()
        for row in self.catalog.values():
            journals = [row["main_journal"], *row["auxiliary_journals"]]
            journals.extend(route["id"] for route in row["routes"])
            for journal in journals:
                expected.update({journal, f"{journal}_reason"})
            for event in row["events"]:
                expected.update(f"{event}{suffix}" for suffix in (".t", ".d", ".a", ".b"))
        self.assertTrue(expected.issubset(load_yaml_keys(ZH_DIR)))
        self.assertTrue(expected.issubset(load_yaml_keys(EN_DIR)))

    def test_political_and_visual_resources_cover_ten_countries(self):
        for path in (IG, IDEOLOGY, NAMES, COLORS, FLAGS):
            text = path.read_text("utf-8")
            for tag in self.catalog:
                self.assertIn(tag, text, f"{tag} missing from {path.name}")


if __name__ == "__main__":
    unittest.main()
