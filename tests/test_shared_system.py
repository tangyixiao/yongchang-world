import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
TRIGGERS = ROOT / "yongchang_world/common/scripted_triggers/ywc_shared_triggers.txt"
EFFECTS = ROOT / "yongchang_world/common/scripted_effects/ywc_shared_effects.txt"
MODIFIERS = ROOT / "yongchang_world/common/scripted_modifiers/ywc_shared_modifiers.txt"
JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_shared_journal.txt"
EVENTS = ROOT / "yongchang_world/events/ywc_shared_events.txt"


class SharedSystemTest(unittest.TestCase):
    def test_shared_interfaces_are_declared(self):
        self.assertIn("ywc_is_chinese_heritage_country", TRIGGERS.read_text("utf-8"))
        self.assertIn("ywc_has_maritime_network", TRIGGERS.read_text("utf-8"))
        self.assertIn("ywc_set_heritage_legitimacy", EFFECTS.read_text("utf-8"))
        self.assertIn("ywc_open_trade_route", EFFECTS.read_text("utf-8"))
        self.assertIn("ywc_subject_autonomy_modifier", MODIFIERS.read_text("utf-8"))

    def test_legitimacy_effect_has_bounded_input(self):
        text = EFFECTS.read_text("utf-8")
        self.assertIn("clamp = { min = 0 max = 100", text)
        self.assertIn("ywc_heritage_legitimacy", text)
        self.assertIn("ywc_maritime_network_level", text)
        self.assertIn("ywc_autonomy_pressure", text)

    def test_shared_journal_and_event_are_connected(self):
        journal = JOURNAL.read_text("utf-8")
        events = EVENTS.read_text("utf-8")
        self.assertIn("ywc_je_who_inherits_china =", journal)
        self.assertIn("namespace = ywc_shared", events)
        self.assertIn("ywc_shared.1 =", events)
        self.assertIn("trigger_event = { id = ywc_shared.1", journal)


if __name__ == "__main__":
    unittest.main()
