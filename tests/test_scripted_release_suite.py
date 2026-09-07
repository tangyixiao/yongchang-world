import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
STARTUP_SUITE = ROOT / "yongchang_world/tools/scripted_tests/ywc_startup_smoke.txt"
LONGRUN_SUITE = ROOT / "yongchang_world/tools/scripted_tests/ywc_longrun_invariants.txt"
LEGACY_SUITE = ROOT / "yongchang_world/tools/scripted_tests/ywc_release_smoke.txt"


class ScriptedReleaseSuiteTest(unittest.TestCase):
    def setUp(self):
        self.startup = STARTUP_SUITE.read_text("utf-8")
        self.longrun = LONGRUN_SUITE.read_text("utf-8")

    def test_startup_suite_checks_only_1836_invariants(self):
        self.assertTrue(STARTUP_SUITE.is_file())
        self.assertIn("last_date = 1836.2.1", self.startup)
        self.assertNotIn("last_date = 1900.1.1", self.startup)
        for tag in ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG"):
            self.assertIn(f"exists = c:{tag}", self.startup)
        self.assertIn("is_subject_of = c:SHU", self.startup)
        self.assertIn("is_subject_of = c:MEX", self.startup)
        self.assertIn("has_variable = ywc_dlc_base_path", self.startup)

    def test_startup_suite_checks_country_content_entries(self):
        for key in (
            "ywc_je_yongchang_century",
            "ywc_route_shu_bureaucratic_integration",
            "ywc_route_jhg_naval_tributary_state",
            "ywc_route_dmg_huafei_monarchy",
            "ywc_route_nqg_sakhalin_restoration",
            "ywc_route_oir_bureaucratic_khanate",
            "ywc_route_mng_southern_trade",
            "ywc_route_tib_monastic_reform",
            "ywc_route_kor_small_china",
            "ywc_route_lan_company_republic",
            "ywc_route_nmg_catholic_autonomy",
        ):
            self.assertIn(key, self.startup)

    def test_longrun_suite_does_not_freeze_starting_subject_or_country_set(self):
        self.assertTrue(LONGRUN_SUITE.is_file())
        self.assertIn("last_date = 1900.1.1", self.longrun)
        self.assertIn("ywc_longrun_no_negative_population", self.longrun)
        self.assertIn("ywc_longrun_no_orphaned_capital", self.longrun)
        self.assertIn("ywc_longrun_shared_variables_bounded", self.longrun)
        self.assertNotIn("is_subject_of = c:MEX", self.longrun)
        self.assertNotIn("exists = c:NMG", self.longrun)

    def test_legacy_monolithic_suite_is_removed(self):
        self.assertFalse(LEGACY_SUITE.exists())

    def test_suites_use_unquoted_date_literals(self):
        for text in (self.startup, self.longrun):
            self.assertNotRegex(text, r'=\s*"\d{4}\.\d+\.\d+"')


if __name__ == "__main__":
    unittest.main()
