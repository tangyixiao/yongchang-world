import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
EVENTS = ROOT / "yongchang_world/events/ywc_shu_jhg_events.txt"
BOOTSTRAP_EVENTS = ROOT / "yongchang_world/events/ywc_bootstrap_events.txt"
SHU_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_shu.txt"
JHG_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_jhg.txt"
BOOTSTRAP_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_bootstrap_journal.txt"
EFFECTS = ROOT / "yongchang_world/common/scripted_effects/ywc_shared_effects.txt"
TRIGGERS = ROOT / "yongchang_world/common/scripted_triggers/ywc_shared_triggers.txt"
MODIFIERS = ROOT / "yongchang_world/common/static_modifiers/ywc_static_modifiers.txt"


def block_for(text: str, key: str) -> str:
    start = text.index(f"{key} = {{")
    opening = text.index("{", start)
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unclosed block: {key}")


class PlayableRouteTest(unittest.TestCase):
    def setUp(self):
        self.events = EVENTS.read_text("utf-8")
        self.bootstrap_events = BOOTSTRAP_EVENTS.read_text("utf-8")
        self.shu_journal = SHU_JOURNAL.read_text("utf-8")
        self.jhg_journal = JHG_JOURNAL.read_text("utf-8")
        self.bootstrap_journal = BOOTSTRAP_JOURNAL.read_text("utf-8")

    def test_shared_variables_have_real_threshold_triggers(self):
        triggers = TRIGGERS.read_text("utf-8")
        for variable, threshold in (
            ("ywc_heritage_legitimacy", ">= 70"),
            ("ywc_maritime_network_level", ">= 60"),
            ("ywc_autonomy_pressure", ">= 70"),
        ):
            self.assertIn(f"var:{variable} {threshold}", triggers)
            self.assertIn(f"clamp_variable = {{ name = {variable} min = 0 max = 100 }}", EFFECTS.read_text("utf-8"))

    def test_shu_routes_require_progress_for_success(self):
        for route, progress in (
            ("ywc_route_shu_bureaucratic_integration", "ywc_route_shu_bureaucratic_integration_progress"),
            ("ywc_route_shu_customs_reform", "ywc_route_shu_customs_reform_progress"),
        ):
            journal = block_for(self.shu_journal, route)
            event = block_for(self.events, "ywc_shu.4" if "bureaucratic" in route else "ywc_shu.5")
            self.assertIn(f"var:{progress} >= 100", journal)
            self.assertIn(f"var:{progress} >= 100", event)
            self.assertRegex(event, r"ywc_(add_heritage_legitimacy|open_trade_route|raise_autonomy_pressure)")
            self.assertIn("add_modifier", event)
            self.assertIn("remove_variable", event)
            self.assertEqual(event.count("ai_chance = {"), 3)
            self.assertGreaterEqual(event.count("var:ywc_"), 6)

    def test_jhg_routes_have_costs_and_mutual_exclusion(self):
        for route, progress, event_id, other_active in (
            (
                "ywc_route_jhg_naval_tributary_state",
                "ywc_route_jhg_naval_tributary_state_progress",
                "ywc_jhg.4",
                "ywc_route_jhg_south_sea_council_active",
            ),
            (
                "ywc_route_jhg_south_sea_council",
                "ywc_route_jhg_south_sea_council_progress",
                "ywc_jhg.5",
                "ywc_route_jhg_naval_tributary_state_active",
            ),
        ):
            journal = block_for(self.jhg_journal, route)
            event = block_for(self.events, event_id)
            self.assertIn(f"var:{progress} >= 100", journal)
            self.assertIn(f"var:{progress} >= 100", event)
            self.assertIn(f"NOT = {{ has_variable = {other_active} }}", event)
            self.assertIn("ywc_raise_autonomy_pressure", event)
            self.assertIn("change_variable", event)
            self.assertIn("add_modifier", event)
            self.assertEqual(event.count("ai_chance = {"), 3)
            self.assertGreaterEqual(event.count("var:ywc_"), 6)

    def test_main_shu_and_jhg_journals_are_progress_gated(self):
        shu_event = block_for(self.events, "ywc_shu.6")
        jhg_event = block_for(self.bootstrap_events, "ywc_bootstrap.2")
        self.assertIn("ywc_je_yongchang_century_progress", self.shu_journal)
        self.assertIn("var:ywc_je_yongchang_century_progress >= 100", shu_event)
        self.assertIn("ywc_jinghai_autonomy_progress", self.bootstrap_journal)
        self.assertIn("var:ywc_jinghai_autonomy_progress >= 100", jhg_event)
        for event in (shu_event, jhg_event):
            self.assertIn("add_modifier", event)
            self.assertIn("change_variable", event)

    def test_route_outcomes_clean_up_active_state(self):
        for event_id in ("ywc_shu.4", "ywc_shu.5", "ywc_jhg.4", "ywc_jhg.5"):
            event = block_for(self.events, event_id)
            self.assertGreaterEqual(event.count("remove_variable"), 2, event_id)
            self.assertRegex(event, r"_(failure|abandon)\s+value\s*=\s*1")

    def test_route_modifiers_are_defined(self):
        modifiers = MODIFIERS.read_text("utf-8")
        for name in (
            "ywc_shu_bureaucratic_commitment",
            "ywc_shu_customs_network",
            "ywc_jhg_naval_tributary",
            "ywc_jhg_south_sea_council",
            "ywc_route_failure_backlash",
        ):
            self.assertRegex(modifiers, rf"(?m)^{re.escape(name)}\s*=\s*\{{")


if __name__ == "__main__":
    unittest.main()
