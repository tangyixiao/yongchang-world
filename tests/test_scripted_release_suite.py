import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SUITE = ROOT / "yongchang_world/tools/scripted_tests/ywc_release_smoke.txt"


class ScriptedReleaseSuiteTest(unittest.TestCase):
    def test_release_suite_checks_startup_invariants(self):
        self.assertTrue(SUITE.is_file())
        text = SUITE.read_text("utf-8")
        self.assertIn("last_date = 1900.1.1", text)
        self.assertIn("ywc_core_country_presence", text)
        self.assertIn("ywc_nmg_subject_boundary", text)
        self.assertIn("ywc_startup_compatibility_path", text)
        self.assertIn("has_variable = ywc_dlc_base_path", text)
        self.assertIn("is_subject_of = c:MEX", text)

    def test_release_suite_checks_autonomy_action_readiness(self):
        text = SUITE.read_text("utf-8")
        self.assertIn("ywc_nmg_autonomy_action_ready", text)
        self.assertIn("has_journal_entry = ywc_je_new_ming_mexican_chain", text)
        self.assertIn("has_variable = ywc_nmg_autonomy_negotiation_opened", text)

    def test_release_suite_uses_unquoted_date_literals(self):
        # Vanilla scripts write game_date/last_date as bare date literals
        # (game_date >= 1846.1.1); the suite has never been parsed by the
        # game, so it must stick to the proven form.
        text = SUITE.read_text("utf-8")
        self.assertNotRegex(text, r'=\s*"\d{4}\.\d+\.\d+"')
        self.assertIn("last_date = 1900.1.1", text)
        self.assertIn("game_date > 1836.2.1", text)


if __name__ == "__main__":
    unittest.main()
