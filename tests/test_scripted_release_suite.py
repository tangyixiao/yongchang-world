import pathlib
import re
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
        # Vanilla suites (game/tools/scripted_tests/italy.txt) quote date
        # literals; the in-game test loader never produced results with the
        # old unquoted form, so the quoted vanilla format is the contract.
        self.assertIn('last_date = "1836.2.1"', self.startup)
        self.assertNotIn('last_date = "1900.1.1"', self.startup)
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
        self.assertIn('last_date = "1900.1.1"', self.longrun)
        self.assertIn("YWC_LONGRUN_NO_NEGATIVE_POPULATION", self.longrun)
        self.assertIn("YWC_LONGRUN_NO_ORPHANED_CAPITAL", self.longrun)
        self.assertIn("YWC_LONGRUN_SHARED_VARIABLES_BOUNDED", self.longrun)
        self.assertNotIn("is_subject_of = c:MEX", self.longrun)
        self.assertNotIn("exists = c:NMG", self.longrun)

    def test_longrun_shared_variable_bounds_require_initialization(self):
        bounds = self.longrun[self.longrun.index("YWC_LONGRUN_SHARED_VARIABLES_BOUNDED") :]
        first_comparison = min(
            bounds.index(f"var:{variable}")
            for variable in (
                "ywc_heritage_legitimacy",
                "ywc_maritime_network_level",
                "ywc_autonomy_pressure",
            )
        )
        for variable in (
            "ywc_heritage_legitimacy",
            "ywc_maritime_network_level",
            "ywc_autonomy_pressure",
        ):
            initialization = bounds.find(f"has_variable = {variable}")
            self.assertGreaterEqual(initialization, 0, variable)
            self.assertLess(
                initialization,
                first_comparison,
                variable,
            )

    def test_legacy_monolithic_suite_is_removed(self):
        self.assertFalse(LEGACY_SUITE.exists())

    def test_suites_follow_vanilla_loader_format(self):
        # The engine's own suites ship without a BOM and quote every date
        # literal; deviating from that format left tests.txt header-only in
        # real 1836 sessions, so the vanilla format is required here.
        for text in (self.startup, self.longrun):
            self.assertRegex(text, r'last_date\s*=\s*"\d{4}\.\d+\.\d+"')
            self.assertRegex(text, r'game_date\s*>\s*"\d{4}\.\d+\.\d+"')
            self.assertNotRegex(text, r'last_date\s*=\s*\d')

    def test_test_case_names_use_engine_safe_uppercase_prefix(self):
        # A real 1.13.11 campaign rejected the lowercase ywc_* test keys as
        # unexpected tokens and left tests.txt header-only. Keep the suite
        # identifiers in the same conservative uppercase style as vanilla
        # GER_formed and ITA_formed cases.
        for text in (self.startup, self.longrun):
            names = re.findall(r"(?m)^ {4}([A-Za-z][A-Za-z0-9_]*)\s*=\s*\{", text)
            self.assertTrue(names)
            for name in names:
                self.assertRegex(name, r"^YWC_[A-Z0-9_]+$")


if __name__ == "__main__":
    unittest.main()
