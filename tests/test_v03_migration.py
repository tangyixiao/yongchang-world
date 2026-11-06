"""Execute forward migration and real JE gates without a game process."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from clausewitz_harness import PulseWorld, parse

COUNTRIES = (
    ("SHU", "shu", "court", "v03_shu_fiscal_register"),
    ("DMG", "dmg", "compact", "v03_dmg_common_subjects"),
    ("KOR", "kor", "reform", "v03_kor_military_accounts"),
)

LEGACY_ADMISSION_STATES = {
    "SHU": {"ywc_campaign_shu_c1_outcome": 2, "ywc_shu_fiscal_cost": -123,
            "ywc_shu_merchant_advance_unpaid": 1, "ywc_shu_pending_event": 1004,
            "ywc_shu_service_route": 2},
    # No country-specific debt variable is defined for JHG in this repo.
    "JHG": {"ywc_campaign_jhg_c1_outcome": 2, "ywc_jhg_court_capture_cost_base": -234,
            "ywc_jhg_pending_event": 1004, "ywc_jhg_court_route": 2},
    "DMG": {"ywc_campaign_dmg_c1_outcome": 2, "ywc_dmg_court_budget_cost": -345,
            "ywc_dmg_court_inherited_land_debt": 456, "ywc_dmg_court_pending_event": 1004,
            "ywc_dmg_court_route": 2},
    # No country-specific debt variable is defined for NQG in this repo.
    "NQG": {"ywc_campaign_nqg_c1_outcome": 2, "ywc_nqg_hunting_capture_cost_base": -456,
            "ywc_nqg_hunting_pending": 1004, "ywc_nqg_hunting_route": 2},
    # No country-specific debt variable is defined for OIR in this repo.
    "OIR": {"ywc_campaign_oir_c1_outcome": 2, "ywc_oir_weekly_cost": -567,
            "ywc_oir_pasture_pending_event": 1004, "ywc_oir_pasture_route": 2},
    "MGL": {"ywc_campaign_mng_c1_outcome": 2, "ywc_mgl_debt_fee": -678,
            "ywc_mgl_debt_close_value": 789, "ywc_mgl_debt_pending_event": 1014,
            "ywc_mgl_debt_route": 2},
    # No country-specific debt variable is defined for TIB in this repo.
    "TIB": {"ywc_campaign_tib_c1_outcome": 2, "ywc_tib_register_route_cost_1": -789,
            "ywc_tib_register_pending_event": 1004, "ywc_tib_register_route": 2},
    "KOR": {"ywc_campaign_kor_c1_outcome": 2, "ywc_kor_capture_cost_base": -891,
            "ywc_kor_court_trust_debt": 912, "ywc_kor_pending_event": 1004,
            "ywc_kor_ports_route": 2},
    "LAN": {"ywc_campaign_lan_c1_outcome": 2, "ywc_lan_fund_filing_fee_paid": 1,
            "ywc_lan_fund_company_debt": 123, "ywc_lan_pending_event": 1004,
            "ywc_lan_fund_route": 2},
    # No country-specific debt variable is defined for NMG in this repo.
    "NMG": {"ywc_campaign_nmg_c1_outcome": 2, "ywc_nmg_revenue_quota_paid": 1,
            "ywc_nmg_land_pending": 1004, "ywc_nmg_land_route": 2},
}


def field(nodes, name):
    return next(value for key, _, value in nodes if key == name)


class V03ForwardMigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = (ROOT / "yongchang_world/common/scripted_effects/ywc_v03_effects.txt").read_text(encoding="utf-8-sig")
        decision = parse((ROOT / "yongchang_world/common/decisions/ywc_v03_migration.txt").read_text(encoding="utf-8-sig"))
        cls.decision = field(decision, "ywc_v03_enable_legacy_save")
        cls.triggers = {}
        for path in (ROOT / "yongchang_world/common/scripted_triggers").glob("ywc_v03*_triggers.txt"):
            cls.triggers.update((key, body) for key, _, body in parse(path.read_text(encoding="utf-8-sig")))

    def world(self, tag, state):
        world = PulseWorld(self.effects, {tag: state})
        original_condition = world.condition

        def condition(node, scope):
            # Only ownership/candidate objects are injected; lifecycle, unsettled,
            # variable comparisons and legacy pulse guards execute from real source.
            if node[0] in {"ywc_shu_v03_has_candidate_state", "ywc_dmg_v03_has_owned_state", "ywc_kor_v03_has_owned_state"}:
                return True
            if node[0] in self.triggers:
                return world.conditions(self.triggers[node[0]], scope)
            return original_condition(node, scope)

        world.condition = condition
        return world

    def possible(self, short):
        arc = json.loads((ROOT / f"data/content/v03/countries/{short}.json").read_text(encoding="utf-8"))["arcs"][0]
        return field(parse(arc["journals"][0]["script"].strip()[1:-1]), "possible")

    def old_pulse_gate(self, short, legacy):
        source = (ROOT / f"yongchang_world/common/journal_entries/ywc_{short}.txt").read_text(encoding="utf-8-sig")
        journal = field(parse(source), f"ywc_je_flavor_{short}_{legacy}_1")
        pulse = field(field(journal, "on_monthly_pulse"), "effect")
        return field(field(pulse, "if"), "limit")

    def test_three_legacy_states_control_actual_new_entry_for_each_country(self):
        for tag, short, legacy, slug in COUNTRIES:
            for status, old, available, compatibility in (
                ("unstarted", {}, True, 1),
                ("ongoing", {f"ywc_campaign_{short}_c1_prelude": 1}, False, 2),
                ("completed", {f"ywc_campaign_{short}_c1_outcome": 1,
                               f"ywc_je_flavor_{short}_{legacy}_1_resolved": 1}, False, 3),
            ):
                with self.subTest(tag=tag, status=status):
                    state = {"gold_reserves": 900, f"ywc_{short}_fiscal_cost": 123, **old}
                    before = copy.deepcopy(state)
                    world = self.world(tag, state)
                    world.execute(field(self.decision, "when_taken"), tag)
                    self.assertEqual(world.conditions(self.possible(short), tag), available)
                    self.assertEqual(state.get(f"ywc_v03_{short}_{slug}_compatibility"), compatibility)
                    self.assertNotIn(f"ywc_v03_{short}_{slug}_started", state)
                    self.assertEqual(state.get(f"ywc_v03_{short}_{slug}_settled"), None if available else 1)
                    for key, value in before.items():
                        self.assertEqual(state[key], value)
                    self.assertEqual(world.treasury[tag], 0)
                    self.assertEqual(world.events, [])
                    self.assertEqual(world.journals, [])
                    if status == "ongoing":
                        self.assertTrue(world.conditions(self.old_pulse_gate(short, legacy), tag))
                    snapshot = copy.deepcopy(state)
                    world.execute(field(self.decision, "when_taken"), tag)
                    self.assertEqual(state, snapshot)

    def test_zero_valued_old_progress_still_continues_in_place(self):
        for tag, short, legacy, slug in COUNTRIES:
            for suffix in ("prelude", "score", "e100_done", "e101_done", "e102_done", "e103_done", "e104_done"):
                with self.subTest(tag=tag, marker=suffix):
                    state = {f"ywc_campaign_{short}_c1_{suffix}": 0}
                    world = self.world(tag, state)
                    world.run("ywc_v03_initialize_country", tag)
                    self.assertFalse(world.conditions(self.possible(short), tag))
                    self.assertEqual(state.get(f"ywc_v03_{short}_{slug}_compatibility"), 2)
                    self.assertTrue(world.conditions(self.old_pulse_gate(short, legacy), tag))
                    self.assertNotIn(f"ywc_v03_{short}_{slug}_outcome", state)

    def test_each_old_terminal_marker_preserves_finished_chain_without_new_success(self):
        for tag, short, legacy, slug in COUNTRIES:
            for marker in (f"ywc_campaign_{short}_c1_outcome", f"ywc_je_flavor_{short}_{legacy}_1_resolved", f"ywc_je_flavor_{short}_{legacy}_1_failed"):
                with self.subTest(tag=tag, marker=marker):
                    state = {marker: 1, f"ywc_campaign_{short}_c2_e105_done": 1}
                    world = self.world(tag, state)
                    world.run("ywc_v03_initialize_country", tag)
                    self.assertFalse(world.conditions(self.possible(short), tag))
                    self.assertEqual(state.get(f"ywc_v03_{short}_{slug}_compatibility"), 3)
                    self.assertNotIn(f"ywc_v03_{short}_{slug}_outcome", state)
                    self.assertEqual(state[marker], 1)
                    self.assertEqual(state[f"ywc_campaign_{short}_c2_e105_done"], 1)
                    self.assertEqual(world.journals, [])

    def test_started_v03_always_wins_without_counter_cost_timer_or_debt_reset(self):
        for tag, short, legacy, slug in COUNTRIES:
            for initialized in (False, True):
                with self.subTest(tag=tag, initialized=initialized):
                    state = {
                        f"ywc_v03_{short}_{slug}_started": 1,
                        f"ywc_campaign_{short}_c1_score": 0,
                        "ywc_v03_active_arc_count": 2,
                        "ywc_v03_visible_task_count": 4,
                        f"ywc_{short}_pending_event": 1006,
                        f"ywc_{short}_cost": 222,
                        f"ywc_{short}_debt_unpaid": 1,
                        f"ywc_v03_{short}_{slug}_outcome": 2,
                        f"ywc_{short}_review_due": 1,
                    }
                    if initialized:
                        state.update(ywc_v03_initialized=1, ywc_v03_release_version=3)
                    original = copy.deepcopy(state)
                    world = self.world(tag, state)
                    world.days_until_expiry[tag][f"ywc_{short}_review_due"] = 77
                    world.run("ywc_v03_initialize_country", tag)
                    for key, value in original.items():
                        self.assertEqual(state[key], value)
                    self.assertNotIn(f"ywc_v03_{short}_{slug}_compatibility", state)
                    self.assertNotIn(f"ywc_v03_{short}_{slug}_settled", state)
                    self.assertEqual(world.days_until_expiry[tag][f"ywc_{short}_review_due"], 77)
                    self.assertEqual(world.treasury[tag], 0)
                    self.assertFalse(world.conditions(self.old_pulse_gate(short, legacy), tag))

    def test_absent_countries_are_not_created_and_other_tags_are_not_classified(self):
        state = {"ywc_campaign_shu_c1_score": 0, "gold_reserves": 111}
        world = self.world("FRA", state)
        world.run("ywc_v03_initialize_country", "FRA")
        self.assertEqual(set(world.countries), {"FRA"})
        self.assertFalse(any(key.endswith("_compatibility") or key.endswith("_settled") for key in state))
        self.assertEqual(world.treasury["FRA"], 0)

    def test_partial_initialized_state_fills_only_missing_defaults(self):
        defaults = {"ywc_v03_release_version": 3, "ywc_v03_active_arc_count": 0,
                    "ywc_v03_visible_task_count": 0}
        for tag, short, legacy, slug in COUNTRIES:
            for missing, value in defaults.items():
                with self.subTest(tag=tag, missing=missing):
                    state = {"ywc_v03_initialized": 1, "ywc_v03_release_version": 4,
                             "ywc_v03_active_arc_count": 2, "ywc_v03_visible_task_count": 4,
                             f"ywc_v03_{short}_{slug}_started": 1}
                    del state[missing]
                    original = dict(state)
                    world = self.world(tag, state)
                    world.run("ywc_v03_initialize_country", tag)
                    self.assertEqual(state.get(missing), value)
                    for key, existing in original.items():
                        self.assertEqual(state[key], existing)


    def test_explicit_legacy_decision_gates_admit_all_ten_runtime_countries(self):
        supported = ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG")
        for tag in supported:
            with self.subTest(tag=tag):
                state = {
                    "ywc_v03_active_arc_count": 2,
                    "ywc_v03_visible_task_count": 4,
                    **LEGACY_ADMISSION_STATES[tag],
                }
                preserved = copy.deepcopy(state)
                world = self.world(tag, state)
                self.assertTrue(world.conditions(field(self.decision, "is_shown"), tag))
                self.assertTrue(world.conditions(field(self.decision, "possible"), tag))

                world.execute(field(self.decision, "when_taken"), tag)

                self.assertEqual(state.get("ywc_v03_initialized"), 1)
                self.assertEqual(state.get("ywc_v03_migration_recorded"), 1)
                for key, value in preserved.items():
                    self.assertEqual(state[key], value)
                self.assertEqual(state["ywc_v03_active_arc_count"], 2)
                self.assertEqual(state["ywc_v03_visible_task_count"], 4)
                once_state = copy.deepcopy(state)
                once_treasury = copy.deepcopy(world.treasury)
                once_events = copy.deepcopy(world.events)
                once_journals = copy.deepcopy(world.journals)
                once_modifiers = copy.deepcopy(world.modifiers)
                once_month_timers = copy.deepcopy(world.months_until_expiry)
                once_day_timers = copy.deepcopy(world.days_until_expiry)
                world.execute(field(self.decision, "when_taken"), tag)
                self.assertEqual(state, once_state)
                self.assertEqual(world.treasury, once_treasury)
                self.assertEqual(world.events, once_events)
                self.assertEqual(world.journals, once_journals)
                self.assertEqual(world.modifiers, once_modifiers)
                self.assertEqual(world.months_until_expiry, once_month_timers)
                self.assertEqual(world.days_until_expiry, once_day_timers)
                self.assertFalse(world.conditions(field(self.decision, "is_shown"), tag))
                self.assertFalse(world.conditions(field(self.decision, "possible"), tag))

    def test_explicit_legacy_decision_gates_reject_unsupported_countries(self):
        for tag in ("FRA", "MNG", "CHI", "MHG", "RKN"):
            with self.subTest(tag=tag):
                world = self.world(tag, {})
                self.assertFalse(world.conditions(field(self.decision, "is_shown"), tag))
                self.assertTrue(world.conditions(field(self.decision, "possible"), tag))

    def test_explicit_legacy_decision_is_unavailable_after_initialization_or_recording(self):
        for state, expected_shown, expected_possible in (
                ({"ywc_v03_initialized": 1}, False, True),
                ({"ywc_v03_migration_recorded": 1}, True, False),
                ({"ywc_v03_initialized": 1, "ywc_v03_migration_recorded": 1}, False, False)):
            with self.subTest(state=state):
                world = self.world("JHG", copy.deepcopy(state))
                self.assertEqual(world.conditions(field(self.decision, "is_shown"), "JHG"), expected_shown)
                self.assertEqual(world.conditions(field(self.decision, "possible"), "JHG"), expected_possible)


if __name__ == "__main__":
    unittest.main()
