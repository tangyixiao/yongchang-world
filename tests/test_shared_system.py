import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
TRIGGERS = ROOT / "yongchang_world/common/scripted_triggers/ywc_shared_triggers.txt"
EFFECTS = ROOT / "yongchang_world/common/scripted_effects/ywc_shared_effects.txt"
MODIFIERS = ROOT / "yongchang_world/common/scripted_modifiers/ywc_shared_modifiers.txt"
STATIC_MODIFIERS = ROOT / "yongchang_world/common/static_modifiers/ywc_static_modifiers.txt"
ENGLISH = ROOT / "yongchang_world/localization/english/ywc_content_l_english.yml"
CHINESE = ROOT / "yongchang_world/localization/simp_chinese/ywc_content_l_simp_chinese.yml"
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

    def test_heritage_legitimacy_refresh_has_visible_political_effect(self):
        effects = EFFECTS.read_text("utf-8")
        modifiers = STATIC_MODIFIERS.read_text("utf-8")
        english = ENGLISH.read_text("utf-8")
        chinese = CHINESE.read_text("utf-8")

        self.assertIn("ywc_refresh_heritage_legitimacy_modifier = {", effects)
        self.assertIn("var:ywc_heritage_legitimacy >= 70", effects)
        self.assertIn("var:ywc_heritage_legitimacy <= 30", effects)
        self.assertIn("remove_modifier = ywc_heritage_legitimacy_high", effects)
        self.assertIn("remove_modifier = ywc_heritage_legitimacy_low", effects)
        self.assertIn("add_modifier = { name = ywc_heritage_legitimacy_high }", effects)
        self.assertIn("add_modifier = { name = ywc_heritage_legitimacy_low }", effects)
        self.assertIn("ywc_heritage_legitimacy_high = {", modifiers)
        self.assertIn("ywc_heritage_legitimacy_low = {", modifiers)
        self.assertIn("country_legitimacy_base_add = 5", modifiers)
        self.assertIn("country_legitimacy_base_add = -5", modifiers)
        self.assertIn("ywc_heritage_legitimacy_high:0", english)
        self.assertIn("ywc_heritage_legitimacy_low:0", english)
        self.assertIn("ywc_heritage_legitimacy_high:0", chinese)
        self.assertIn("ywc_heritage_legitimacy_low:0", chinese)

    def test_heritage_mutations_route_through_refresh_effect(self):
        effects = EFFECTS.read_text("utf-8")
        event_text = "\n".join(path.read_text("utf-8") for path in (ROOT / "yongchang_world/events").glob("*.txt"))

        self.assertIn("ywc_refresh_heritage_legitimacy_modifier = yes", effects)
        self.assertNotIn("change_variable = { name = ywc_heritage_legitimacy", event_text)
        self.assertNotIn("set_variable = { name = ywc_heritage_legitimacy", event_text)

    def test_autonomy_pressure_changes_subject_liberty_desire(self):
        effects = EFFECTS.read_text("utf-8")
        modifiers = STATIC_MODIFIERS.read_text("utf-8")
        english = ENGLISH.read_text("utf-8")
        chinese = CHINESE.read_text("utf-8")

        self.assertIn("ywc_refresh_autonomy_pressure_modifier = {", effects)
        self.assertIn("is_subject = yes", effects)
        self.assertIn("var:ywc_autonomy_pressure >= 70", effects)
        self.assertIn("var:ywc_autonomy_pressure <= 30", effects)
        self.assertIn("remove_modifier = ywc_autonomy_pressure_high", effects)
        self.assertIn("remove_modifier = ywc_autonomy_pressure_low", effects)
        self.assertIn("add_modifier = { name = ywc_autonomy_pressure_high }", effects)
        self.assertIn("add_modifier = { name = ywc_autonomy_pressure_low }", effects)
        self.assertIn("ywc_autonomy_pressure_high = {", modifiers)
        self.assertIn("ywc_autonomy_pressure_low = {", modifiers)
        self.assertIn("country_liberty_desire_add = 0.10", modifiers)
        self.assertIn("country_liberty_desire_add = -0.05", modifiers)
        self.assertIn("ywc_autonomy_pressure_high:0", english)
        self.assertIn("ywc_autonomy_pressure_low:0", english)
        self.assertIn("ywc_refresh_autonomy_pressure_modifier:0", english)
        self.assertIn("ywc_autonomy_pressure_high:0", chinese)
        self.assertIn("ywc_autonomy_pressure_low:0", chinese)
        self.assertIn("ywc_refresh_autonomy_pressure_modifier:0", chinese)

    def test_autonomy_mutations_refresh_subject_effect(self):
        effects = EFFECTS.read_text("utf-8")
        self.assertIn("ywc_raise_autonomy_pressure = {\n    change_variable", effects)
        self.assertIn("ywc_lower_autonomy_pressure = {\n    change_variable", effects)
        self.assertIn("clamp_variable = { name = ywc_autonomy_pressure min = 0 max = 100 }\n    ywc_refresh_autonomy_pressure_modifier = yes", effects)
        self.assertIn("ywc_set_heritage_legitimacy = yes\n    set_variable = { name = ywc_maritime_network_level", effects)
        self.assertIn("set_variable = { name = ywc_autonomy_pressure value = 0 }\n    ywc_refresh_maritime_network_modifier = yes", effects)
        self.assertIn("ywc_refresh_maritime_network_modifier = yes\n    ywc_refresh_autonomy_pressure_modifier = yes", effects)

    def test_maritime_network_changes_trade_and_port_capacity(self):
        effects = EFFECTS.read_text("utf-8")
        modifiers = STATIC_MODIFIERS.read_text("utf-8")
        english = ENGLISH.read_text("utf-8")
        chinese = CHINESE.read_text("utf-8")

        self.assertIn("ywc_refresh_maritime_network_modifier = {", effects)
        self.assertIn("var:ywc_maritime_network_level >= 60", effects)
        self.assertIn("remove_modifier = ywc_maritime_network_established", effects)
        self.assertIn("add_modifier = { name = ywc_maritime_network_established }", effects)
        self.assertIn("ywc_maritime_network_established = {", modifiers)
        self.assertIn("building_port_throughput_add = 0.10", modifiers)
        self.assertIn("state_trade_capacity_mult = 0.10", modifiers)
        self.assertIn("state_trade_advantage_mult = 0.05", modifiers)
        self.assertIn("ywc_maritime_network_established:0", english)
        self.assertIn("ywc_reduce_maritime_network:0", english)
        self.assertIn("ywc_refresh_maritime_network_modifier:0", english)
        self.assertIn("ywc_maritime_network_established:0", chinese)
        self.assertIn("ywc_reduce_maritime_network:0", chinese)
        self.assertIn("ywc_refresh_maritime_network_modifier:0", chinese)

    def test_maritime_mutations_route_through_refresh_effect(self):
        effects = EFFECTS.read_text("utf-8")
        event_text = "\n".join(path.read_text("utf-8") for path in (ROOT / "yongchang_world/events").glob("*.txt"))

        self.assertIn("ywc_open_trade_route = {\n    change_variable", effects)
        self.assertIn("ywc_add_maritime_network = {\n    change_variable", effects)
        self.assertIn("ywc_reduce_maritime_network = {\n    change_variable", effects)
        self.assertIn("clamp_variable = { name = ywc_maritime_network_level min = 0 max = 100 }\n    ywc_refresh_maritime_network_modifier = yes", effects)
        self.assertNotIn("change_variable = { name = ywc_maritime_network_level", event_text)
        self.assertNotIn("set_variable = { name = ywc_maritime_network_level", event_text)

    def test_shared_journal_and_event_are_connected(self):
        journal = JOURNAL.read_text("utf-8")
        events = EVENTS.read_text("utf-8")
        self.assertIn("ywc_je_who_inherits_china =", journal)
        self.assertIn("namespace = ywc_shared", events)
        self.assertIn("ywc_shared.1 =", events)
        self.assertIn("trigger_event = { id = ywc_shared.1", journal)

    def test_ocean_frontier_decision_changes_shared_maritime_state(self):
        events = EVENTS.read_text("utf-8")
        start = events.index("ywc_shared.2 = {")
        ocean = events[start:]
        self.assertIn("name = ywc_shared.2.a", ocean)
        self.assertIn("ywc_open_trade_route = yes", ocean)
        self.assertIn("name = ywc_shared.2.b", ocean)
        self.assertIn("ywc_reduce_maritime_network = yes", ocean)


if __name__ == "__main__":
    unittest.main()
