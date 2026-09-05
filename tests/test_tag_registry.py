import json
import pathlib
import tempfile
import unittest

from tools.export_vic3_baseline import export_baseline


ROOT = pathlib.Path(__file__).parents[1]


class TagRegistryTest(unittest.TestCase):
    def setUp(self):
        self.baseline = json.loads(
            (ROOT / "data/baseline/vic3-1.13.11.json").read_text("utf-8")
        )
        self.registry = json.loads(
            (ROOT / "data/scenario/tag_registry.json").read_text("utf-8")
        )

    def test_new_tags_do_not_collide_with_base(self):
        base = set(self.baseline["country_tags"])
        rows = self.registry["countries"]
        self.assertEqual({row["mode"] for row in rows}, {"new", "reuse"})
        for row in rows:
            if row["mode"] == "new":
                self.assertNotIn(row["tag"], base)
                self.assertIsNone(row["source_tag"])
            else:
                self.assertIn(row["tag"], base)
                self.assertEqual(row["source_tag"], row["tag"])

    def test_registry_has_expected_core_tags(self):
        rows = {row["tag"]: row for row in self.registry["countries"]}
        for tag in ("SHU", "JHG", "DMG", "NQG"):
            self.assertEqual(rows[tag]["mode"], "new")
        for tag in ("MNG", "TIB", "KOR", "LAN", "EZO"):
            self.assertEqual(rows[tag]["mode"], "reuse")


class BaselineExporterTest(unittest.TestCase):
    def test_exporter_extracts_tags_states_and_provinces(self):
        with tempfile.TemporaryDirectory() as directory:
            game_root = pathlib.Path(directory)
            (game_root / "common/country_definitions").mkdir(parents=True)
            (game_root / "map_data/state_regions").mkdir(parents=True)
            (game_root / "common/history/states").mkdir(parents=True)
            (game_root / "common/country_definitions/00.txt").write_text(
                "AAA = { color = { 1 2 3 } }\n# BBB = { }\nCCC={}",
                encoding="utf-8",
            )
            (game_root / "map_data/state_regions/00.txt").write_text(
                'STATE_TEST = { provinces = { "xABCDEF" "x010203" } }',
                encoding="utf-8",
            )
            (game_root / "common/history/states/00_states.txt").write_text(
                "s:STATE_TEST = { create_state = { country = c:AAA owned_provinces = { xABCDEF x010203 } } }",
                encoding="utf-8",
            )

            baseline = export_baseline(game_root)

        self.assertEqual(baseline["country_tags"], ["AAA", "CCC"])
        self.assertEqual(
            baseline["state_regions"]["STATE_TEST"],
            ["x010203", "xABCDEF"],
        )
        self.assertIn("STATE_TEST", baseline["states"])
        self.assertEqual(
            baseline["states"]["STATE_TEST"][0]["owned_provinces"],
            ["x010203", "xABCDEF"],
        )


if __name__ == "__main__":
    unittest.main()
