import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
CATALOG_FILE = ROOT / "data/content/content_catalog.json"
AI_FILE = ROOT / "yongchang_world/common/ai_strategies/ywc_core_country_ai.txt"
JOURNAL_DIR = ROOT / "yongchang_world/common/journal_entries"


class ContentCatalogTest(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG_FILE.read_text("utf-8"))["countries"]

    def test_catalog_contains_ten_core_countries(self):
        self.assertEqual(
            set(self.catalog),
            {"SHU", "JHG", "DMG", "NQG", "OIR", "MNG", "TIB", "KOR", "LAN", "NMG"},
        )

    def test_each_core_country_has_required_content(self):
        for tag, row in self.catalog.items():
            self.assertGreaterEqual(len(row["events"]), 8, tag)
            self.assertLessEqual(len(row["events"]), 15, tag)
            self.assertEqual(len(row["routes"]), 2, tag)
            self.assertTrue(row["main_journal"], tag)
            self.assertEqual(len(row["routes"][0]["outcomes"]), 3, tag)
            self.assertEqual(len(row["routes"][1]["outcomes"]), 3, tag)

    def test_event_ids_and_journal_ids_are_unique(self):
        events = [event for row in self.catalog.values() for event in row["events"]]
        journals = [row["main_journal"] for row in self.catalog.values()]
        journals.extend(journal for row in self.catalog.values() for journal in row["auxiliary_journals"])
        self.assertEqual(len(events), len(set(events)))
        self.assertEqual(len(journals), len(set(journals)))

    def test_catalog_journals_and_ai_strategies_are_materialized(self):
        self.assertTrue(AI_FILE.exists())
        ai_text = AI_FILE.read_text("utf-8")
        for tag, row in self.catalog.items():
            self.assertIn(row["ai_strategy"], ai_text)
            journal_file = JOURNAL_DIR / f"ywc_{tag.lower()}.txt"
            if tag in {"SHU", "JHG", "DMG", "NQG"}:
                journal_text = journal_file.read_text("utf-8") if journal_file.exists() else ""
                journal_text += (ROOT / "yongchang_world/common/journal_entries/ywc_bootstrap_journal.txt").read_text("utf-8")
            else:
                journal_text = journal_file.read_text("utf-8")
            for journal in [row["main_journal"], *row["auxiliary_journals"], *(route["id"] for route in row["routes"])]:
                self.assertIn(f"{journal} =", journal_text, journal)


class OverseasMingTest(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG_FILE.read_text("utf-8"))["countries"]

    def test_overseas_ming_countries_keep_small_scale(self):
        self.assertEqual(self.catalog["DMG"]["forbidden_effects"], ["own_manila", "inherit_jinghai_core"])
        self.assertEqual(self.catalog["NQG"]["population_cap"], [30000, 60000])


class SteppeHighlandTest(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG_FILE.read_text("utf-8"))["countries"]

    def test_steppe_routes_do_not_restore_qing_empire(self):
        for tag in ("OIR", "MNG", "TIB"):
            self.assertNotIn("restore_qing_inner_asia", self.catalog[tag]["effects"])


class KorLanNmgTest(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG_FILE.read_text("utf-8"))["countries"]

    def test_new_ming_never_starts_as_great_power(self):
        self.assertEqual(self.catalog["NMG"]["subject_overlord"], "MEX")
        self.assertEqual(self.catalog["NMG"]["max_rank_at_start"], "minor_power")


if __name__ == "__main__":
    unittest.main()
