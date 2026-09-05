import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
COUNTRY_FILE = ROOT / "yongchang_world/common/country_definitions/ywc_core_countries.txt"
ZH_FILE = ROOT / "yongchang_world/localization/simp_chinese/ywc_core_l_simp_chinese.yml"
EN_FILE = ROOT / "yongchang_world/localization/english/ywc_core_l_english.yml"

EXPECTED = {
    "SHU": ("STATE_BEIJING", "empire", ["han"]),
    "JHG": ("STATE_FORMOSA", "kingdom", ["han", "hakka"]),
    "DMG": ("STATE_LUZON", "kingdom", ["han", "ilocano", "filipino"]),
    "NQG": ("STATE_SAKHALIN", "principality", ["manchu", "siberian", "ainu"]),
}


class CoreCountryDefinitionTest(unittest.TestCase):
    def test_four_core_country_definitions(self):
        text = COUNTRY_FILE.read_text("utf-8")
        for tag, (capital, tier, cultures) in EXPECTED.items():
            self.assertRegex(text, rf"(?m)^\s*{tag}\s*=\s*\{{")
            block_match = re.search(
                rf"(?ms)^\s*{tag}\s*=\s*\{{.*?^\}}", text
            )
            self.assertIsNotNone(block_match)
            block = block_match.group(0)
            self.assertIn("country_type = unrecognized", block)
            self.assertIn(f"tier = {tier}", block)
            self.assertIn(f"capital = {capital}", block)
            for culture in cultures:
                self.assertIn(culture, block)

    def test_four_core_countries_have_colors(self):
        text = COUNTRY_FILE.read_text("utf-8")
        for tag in EXPECTED:
            block = re.search(rf"(?ms)^\s*{tag}\s*=\s*\{{.*?^\}}", text).group(0)
            self.assertRegex(block, r"color\s*=\s*\{\s*\d+\s+\d+\s+\d+\s*\}")

    def test_four_core_countries_have_bilingual_names(self):
        zh = ZH_FILE.read_text("utf-8")
        en = EN_FILE.read_text("utf-8")
        for tag in EXPECTED:
            self.assertRegex(zh, rf"(?m)^\s*{tag}:0\s+\".+\"")
            self.assertRegex(en, rf"(?m)^\s*{tag}:0\s+\".+\"")


if __name__ == "__main__":
    unittest.main()
