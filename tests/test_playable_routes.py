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
ROUTE_EVENT_FILES = (
    ROOT / "yongchang_world/events/ywc_shu_jhg_events.txt",
    ROOT / "yongchang_world/events/ywc_dmg_nqg_events.txt",
    ROOT / "yongchang_world/events/ywc_steppe_highland_events.txt",
    ROOT / "yongchang_world/events/ywc_kor_lan_nmg_events.txt",
)
ROUTE_JOURNAL_FILES = (
    ROOT / "yongchang_world/common/journal_entries/ywc_shu.txt",
    ROOT / "yongchang_world/common/journal_entries/ywc_jhg.txt",
    ROOT / "yongchang_world/common/journal_entries/ywc_dmg.txt",
    ROOT / "yongchang_world/common/journal_entries/ywc_nqg.txt",
    ROOT / "yongchang_world/common/journal_entries/ywc_oir.txt",
    ROOT / "yongchang_world/common/journal_entries/ywc_mng.txt",
    ROOT / "yongchang_world/common/journal_entries/ywc_tib.txt",
    ROOT / "yongchang_world/common/journal_entries/ywc_kor.txt",
    ROOT / "yongchang_world/common/journal_entries/ywc_lan.txt",
    ROOT / "yongchang_world/common/journal_entries/ywc_nmg.txt",
)


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


def block_at(text: str, start: int) -> str:
    opening = text.index("{", start)
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError("unclosed block")


def outcome_branch(event: str, outcome: str) -> str:
    marker = f"set_variable = {{ name = {outcome} value = 1 }}"
    start = event.index(marker) + len(marker)
    end = event.index("\n        }", start)
    return event[start:end]


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

    def test_each_shu_jhg_outcome_has_numeric_and_persistent_consequences(self):
        routes = (
            (
                "ywc_shu.4",
                "ywc_route_shu_bureaucratic_integration",
                ("ywc_add_heritage_legitimacy", "ywc_lower_heritage_legitimacy", "ywc_lower_heritage_legitimacy"),
            ),
            (
                "ywc_shu.5",
                "ywc_route_shu_customs_reform",
                ("ywc_add_maritime_network", "ywc_reduce_maritime_network", "ywc_reduce_maritime_network"),
            ),
            (
                "ywc_jhg.4",
                "ywc_route_jhg_naval_tributary_state",
                ("ywc_add_maritime_network", "ywc_raise_autonomy_pressure", "ywc_lower_autonomy_pressure"),
            ),
            (
                "ywc_jhg.5",
                "ywc_route_jhg_south_sea_council",
                ("ywc_open_trade_route", "ywc_raise_autonomy_pressure", "ywc_lower_autonomy_pressure"),
            ),
        )
        for event_id, route, outcome_effects in routes:
            event = block_for(self.events, event_id)
            journal = block_for(
                self.shu_journal if event_id.startswith("ywc_shu") else self.jhg_journal,
                route,
            )
            for outcome, effect in zip(("success", "failure", "abandon"), outcome_effects):
                result = f"{route}_{outcome}"
                branch = outcome_branch(event, result)
                self.assertIn(effect, branch, f"{event_id} {outcome} lacks its numeric/shared-state change")
                self.assertIn("add_modifier", branch, f"{event_id} {outcome} lacks a persistent consequence")
                self.assertIn(result, journal, f"{event_id} {outcome} is not visible in the journal state")

    def test_abandonment_uses_a_timed_cooldown_and_reopens_the_route(self):
        routes = (
            ("ywc_shu.4", "ywc_route_shu_bureaucratic_integration", self.shu_journal),
            ("ywc_shu.5", "ywc_route_shu_customs_reform", self.shu_journal),
            ("ywc_jhg.4", "ywc_route_jhg_naval_tributary_state", self.jhg_journal),
            ("ywc_jhg.5", "ywc_route_jhg_south_sea_council", self.jhg_journal),
        )
        for event_id, route, journal_text in routes:
            event = block_for(self.events, event_id)
            cooldown = f"{route}_abandonment_cooldown"
            self.assertIn(f"set_variable = {{ name = {cooldown} days = 365 }}", event)
            self.assertIn(f"remove_variable = {route}_abandon", event)
            self.assertIn(f"NOT = {{ has_variable = {cooldown} }}", event)
            journal = block_for(journal_text, route)
            self.assertIn(f"has_variable = {cooldown}", journal)
            self.assertIn(f"NOT = {{ has_variable = {cooldown} }}", journal)

    def test_route_start_is_blocked_by_any_active_abandonment_cooldown(self):
        route_count = 0
        for path in ROUTE_EVENT_FILES:
            text = path.read_text("utf-8")
            for match in re.finditer(
                r"set_variable = \{ name = (ywc_route_[a-z0-9_]+)_active value = 1 \}",
                text,
            ):
                route_count += 1
                option_start = text.rfind("option = {", 0, match.start())
                option_text = text[option_start:]
                trigger_start = option_text.index("trigger = {\n            NOT =")
                trigger = block_at(option_text, trigger_start)
                cooldown = f"{match.group(1)}_abandonment_cooldown"
                self.assertIn(
                    f"NOT = {{ has_variable = {cooldown} }}",
                    trigger,
                    match.group(1),
                )
                self.assertNotIn("OR = {", trigger, match.group(1))
        self.assertEqual(route_count, 20)

    def test_route_monthly_pulse_is_blocked_by_any_active_abandonment_cooldown(self):
        route_count = 0
        for path in ROUTE_JOURNAL_FILES:
            text = path.read_text("utf-8")
            for match in re.finditer(
                r"(?m)^(ywc_route_[a-z0-9_]+) = \{", text
            ):
                route_count += 1
                route_block = block_at(text, match.start())
                monthly_pulse = block_for(route_block, "on_monthly_pulse")
                limit = block_for(monthly_pulse, "limit")
                cooldown = f"{match.group(1)}_abandonment_cooldown"
                self.assertIn(
                    f"NOT = {{ has_variable = {cooldown} }}",
                    limit,
                    match.group(1),
                )
                self.assertNotIn("OR = {", limit, match.group(1))
        self.assertEqual(route_count, 20)

    def test_route_modifiers_are_defined(self):
        modifiers = MODIFIERS.read_text("utf-8")
        for name in (
            "ywc_shu_bureaucratic_commitment",
            "ywc_shu_customs_network",
            "ywc_jhg_naval_tributary",
            "ywc_jhg_south_sea_council",
            "ywc_route_failure_backlash",
            "ywc_route_abandonment_recovery",
        ):
            self.assertRegex(modifiers, rf"(?m)^{re.escape(name)}\s*=\s*\{{")

    def test_jhg_naval_tributary_route_has_an_explicit_fiscal_cost(self):
        modifiers = MODIFIERS.read_text("utf-8")
        naval_modifier = block_for(modifiers, "ywc_jhg_naval_tributary")
        self.assertIn("country_loan_interest_rate_mult = 0.05", naval_modifier)

        event = block_for(self.events, "ywc_jhg.4")
        self.assertIn(
            "add_modifier = { name = ywc_jhg_naval_tributary months = 12 }",
            event,
        )
        self.assertIn(
            "add_modifier = { name = ywc_jhg_naval_tributary months = 120 }",
            event,
        )


if __name__ == "__main__":
    unittest.main()
