import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
ACTION_FILE = ROOT / "yongchang_world/common/diplomatic_actions/ywc_diplomatic_actions.txt"
ACTION_KEY = "ywc_nmg_autonomy_negotiation"
LOC_KEYS = {
    "ywc_nmg_autonomy_negotiation",
    "ywc_nmg_autonomy_negotiation_desc",
    "ywc_nmg_autonomy_negotiation_action_name",
    "ywc_nmg_autonomy_negotiation_action_propose_name",
    "ywc_nmg_autonomy_negotiation_action_break_name",
    "ywc_nmg_autonomy_negotiation_pact_desc",
    "ywc_diplo_requirement_subject_relation",
}


def read_action_text() -> str:
    return ACTION_FILE.read_text("utf-8")


class DiplomaticActionFileTest(unittest.TestCase):
    def setUp(self):
        self.text = read_action_text()

    def test_file_declares_the_autonomy_negotiation_action(self):
        self.assertRegex(self.text, rf"(?m)^{ACTION_KEY}\s*=\s*\{{")

    def test_action_uses_only_verified_dlc_feature_ids(self):
        # The action is a base-game pact; if a DLC capability is ever added it
        # must be gated by one of the three verified feature ids.
        for feature in re.findall(r"has_dlc_feature\s*=\s*([A-Za-z0-9_]+)", self.text):
            self.assertIn(feature, {"ep1_content", "mp1_content", "ep2_content"})

    def test_action_is_gated_to_the_new_ming_mexico_pair(self):
        self.assertRegex(self.text, r"potential\s*=\s*\{[^}]*c:NMG")
        self.assertRegex(self.text, r"potential\s*=\s*\{[^}]*c:MEX")
        self.assertRegex(self.text, r"possible\s*=\s*\{[^}]*is_subject_of\s*=\s*scope:target_country")

    def test_action_ties_into_the_new_ming_mexican_chain(self):
        self.assertIn("has_journal_entry = ywc_je_new_ming_mexican_chain", self.text)
        self.assertIn("set_variable = ywc_je_new_ming_mexican_chain_resolved", self.text)

    def test_acceptance_resolves_the_chain_and_reduces_autonomy_pressure(self):
        self.assertIn("ywc_lower_autonomy_pressure = yes", self.text)
        self.assertIn("set_variable = ywc_je_new_ming_mexican_chain_resolved", self.text)
        self.assertIn("relations_progress_per_day = 1", self.text)

    def test_pact_uses_minimal_verified_structure(self):
        self.assertIn("requires_approval = yes", self.text)
        self.assertIn("forced_duration = 12", self.text)  # PACT_REQUIRES_APPROVAL_MIN_FORCED_MONTHS
        self.assertIn("relations_progress_per_day", self.text)
        self.assertRegex(
            self.text,
            r"requirement_to_maintain\s*=\s*\{(?s:.*?)is_subject_of\s*=\s*scope:target_country",
        )

    def test_ai_block_scores_exist(self):
        self.assertRegex(self.text, r"accept_score\s*=\s*\{")
        self.assertRegex(self.text, r"will_propose\s*=\s*\{")
        self.assertRegex(self.text, r"propose_score\s*=\s*\{")

    def test_no_duplicate_action_keys_in_file(self):
        keys = re.findall(r"^(ywc_[A-Za-z0-9_]+)\s*=", self.text, re.MULTILINE)
        self.assertEqual(len(keys), len(set(keys)), keys)


class DiplomaticActionLocalizationTest(unittest.TestCase):
    def test_required_keys_localized_in_every_language(self):
        for language in ("english", "simp_chinese"):
            loc_file = ROOT / f"yongchang_world/localization/{language}/ywc_diplomacy_l_{language}.yml"
            text = loc_file.read_text("utf-8-sig")
            for key in LOC_KEYS:
                self.assertRegex(
                    text,
                    rf"(?m)^\s*{re.escape(key)}:[0-9]+",
                    f"{loc_file} missing {key}",
                )


if __name__ == "__main__":
    unittest.main()
