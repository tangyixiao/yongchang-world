import pathlib
import tempfile
import unittest

from tools.ywc_check import (
    collect_declared_keys,
    collect_localization_keys,
    find_duplicate_keys,
    scan_braces,
)


ROOT = pathlib.Path(__file__).parents[1]


class ScriptStructureTest(unittest.TestCase):
    def test_reports_unclosed_brace(self):
        self.assertIn("unclosed brace", scan_braces("SHU = { color = { 1 2 3 }"))

    def test_ignores_comments_and_quoted_braces(self):
        text = 'key = { value = "}" } # comment with {\n'
        self.assertEqual(scan_braces(text), [])
        self.assertEqual(scan_braces('key = { value = "}" } # { }'), [])

    def test_ywc_keys_are_localized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "common").mkdir()
            (root / "localization/simp_chinese").mkdir(parents=True)
            (root / "common/example.txt").write_text(
                "ywc_example = { value = 1 }\n", encoding="utf-8"
            )
            (root / "localization/simp_chinese/example.yml").write_text(
                'l_simp_chinese:\n ywc_example:0 "示例"\n', encoding="utf-8"
            )
            self.assertEqual(
                collect_declared_keys(root) - collect_localization_keys(root), set()
            )

    def test_reports_duplicate_declared_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "common").mkdir()
            (root / "common/one.txt").write_text("ywc_same = {}\n", encoding="utf-8")
            (root / "common/two.txt").write_text("ywc_same = {}\n", encoding="utf-8")
            duplicates = find_duplicate_keys(root)
            self.assertIn("ywc_same", duplicates)

    def test_nested_scripted_effect_calls_are_not_declarations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "common").mkdir()
            (root / "common/example.txt").write_text(
                "ywc_example = {\n    ywc_example = yes\n}\n", encoding="utf-8"
            )
            self.assertEqual(collect_declared_keys(root), {"ywc_example"})

    def test_visual_database_tags_do_not_collide_with_country_definitions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "common/country_definitions").mkdir(parents=True)
            (root / "common/flag_definitions").mkdir(parents=True)
            (root / "localization/simp_chinese").mkdir(parents=True)
            (root / "common/country_definitions/country.txt").write_text(
                "SHU = {}\n", encoding="utf-8"
            )
            (root / "common/flag_definitions/flag.txt").write_text(
                "SHU = {}\n", encoding="utf-8"
            )
            (root / "localization/simp_chinese/country.yml").write_text(
                'l_simp_chinese:\n SHU:0 "蜀"\n', encoding="utf-8"
            )
            self.assertEqual(find_duplicate_keys(root), set())
            self.assertEqual(collect_declared_keys(root), {"SHU"})

    def test_repo_fixtures_are_available(self):
        self.assertTrue((ROOT / "tests/fixtures/broken_brace.txt").exists())
        self.assertTrue((ROOT / "tests/fixtures/missing_localization.txt").exists())


if __name__ == "__main__":
    unittest.main()
