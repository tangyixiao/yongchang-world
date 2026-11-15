import copy
import unittest

from tests.shu_legacy_baseline import with_engine_modifier_fix


class ShunLegacyBaselineTests(unittest.TestCase):
    def setUp(self):
        self.old = [{"slug": "v03_shu_fiscal_register", "events": [{
            "id": "ywc_shu.1004", "options": [
                {"key": "central_appeal", "effect": "{ add_modifier = { modifier = ywc_shu_central_appeal_cost months = 24 } }"},
                {"key": "local_mediation", "effect": "{ add_modifier = { modifier = ywc_shu_local_appeal_cost months = 24 } }"},
                {"key": "unrelated", "effect": "{ add_modifier = { modifier = unrelated months = 24 } }"},
            ]}]}]

    def test_only_two_original_fragments_change_and_input_stays_frozen(self):
        old_copy = copy.deepcopy(self.old)
        current = with_engine_modifier_fix(self.old)
        self.assertEqual(self.old, old_copy)
        options = current[0]["events"][0]["options"]
        self.assertIn("name = ywc_shu_central_appeal_cost", options[0]["effect"])
        self.assertIn("name = ywc_shu_local_appeal_cost", options[1]["effect"])
        self.assertEqual(options[2], self.old[0]["events"][0]["options"][2])
        self.assertNotEqual(current, self.old, "old invalid syntax must fail the full snapshot comparison")
        broken = copy.deepcopy(current)
        broken[0]["events"][0]["options"][0]["effect"] += " set_variable = { name = extra value = 1 }"
        self.assertNotEqual(broken, current, "other event changes must still fail the full snapshot comparison")

    def test_unexpected_or_already_fixed_historical_input_is_rejected(self):
        fixed = with_engine_modifier_fix(self.old)
        with self.assertRaises(AssertionError):
            with_engine_modifier_fix(fixed)
        missing = copy.deepcopy(self.old)
        missing[0]["events"][0]["options"].pop()
        missing[0]["events"][0]["options"].pop()
        with self.assertRaises(AssertionError):
            with_engine_modifier_fix(missing)


if __name__ == "__main__":
    unittest.main()
