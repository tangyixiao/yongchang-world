"""Focused DMG lifecycle regressions against the authored catalog scripts.

This intentionally inspects/evaluates the real generated JE predicates and
terminal helpers. Engine-only world facts are supplied as country variables.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
from clausewitz_harness import PulseWorld, parse

CATALOG = json.loads((ROOT / "data/content/v03/countries/dmg.json").read_text(encoding="utf-8"))
EFFECTS = (ROOT / "yongchang_world/common/scripted_effects/ywc_v03_dmg_effects.txt").read_text(encoding="utf-8-sig")
SHARED_EFFECTS = (ROOT / "yongchang_world/common/scripted_effects/ywc_v03_effects.txt").read_text(encoding="utf-8-sig")
SHARED_TRIGGERS = (ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt").read_text(encoding="utf-8-sig")
DMG_TRIGGERS = (ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_dmg_triggers.txt").read_text(encoding="utf-8-sig")
DMG_TRIGGER_MAP = {key: body for key, _, body in parse(DMG_TRIGGERS)}
DMG_EFFECT_MAP = {key: body for key, _, body in parse(EFFECTS)}
GENERATED_JE = parse((ROOT / "yongchang_world/common/journal_entries/ywc_v03_country_dmg_journal.txt").read_text(encoding="utf-8-sig"))
GENERATED_EVENTS = parse((ROOT / "yongchang_world/events/ywc_v03_country_dmg_events.txt").read_text(encoding="utf-8-sig"))


class DmgWorld(PulseWorld):
    """Replace the owned-state engine fact while retaining actual script ASTs."""
    def execute(self, nodes, tag):
        expanded = []
        for key, comparison, body in nodes:
            if key in DMG_EFFECT_MAP and body == "yes":
                expanded.extend(DMG_EFFECT_MAP[key])
            else:
                expanded.append((key, comparison, body))
        return super().execute(expanded, tag)

    def condition(self, node, tag):
        if node[0] == "ywc_dmg_v03_has_owned_state":
            return bool(self.countries[tag].get("fixture_owned_state", 0))
        engine_fact_fixtures = {
            "ywc_dmg_v03_government_appointment_ready": "fixture_government_appointment_ready",
            "ywc_dmg_v03_electoral_representative_ready": "fixture_electoral_representative_ready",
            "ywc_dmg_v03_secondary_local_office_ready": "fixture_secondary_office_ready",
            "ywc_dmg_foundation_agriculture_employment": "fixture_agriculture_employment",
            "country_has_voting_franchise": "fixture_has_voting_franchise",
        }
        if node[0] in engine_fact_fixtures:
            actual = bool(self.countries[tag].get(engine_fact_fixtures[node[0]], 0))
            expected = node[2] == "yes"
            return actual == expected
        if node[0] == "any_interest_group":
            return bool(self.countries[tag].get("fixture_landowner_interest_group", 0))
        if node[0] == "has_law_or_variant":
            return bool(self.countries[tag].get("fixture_land_law_ready", 0))
        if node[0] in DMG_TRIGGER_MAP:
            return self.conditions(DMG_TRIGGER_MAP[node[0]], tag)
        if node[0] == "ywc_v03_can_deliver_major":
            trigger = next(body for key, _, body in parse(SHARED_TRIGGERS) if key == node[0])
            return self.conditions(trigger, tag)
        return super().condition(node, tag)


def _arc(slug):
    return next(arc for arc in CATALOG["arcs"] if arc["slug"] == slug)


def _je(slug, je_id):
    return next(je for je in _arc(slug)["journals"] if je["id"] == je_id)


def _field(script, name):
    nodes = parse(script.strip()[1:-1])
    return next(body for key, _, body in nodes if key == name)


def _monthly_effect(script):
    monthly = _field(script, "on_monthly_pulse")
    return next(body for key, _, body in monthly if key == "effect")


def _event_option(slug, event_id, option_key):
    event = next(event for event in _arc(slug)["events"] if event["id"] == f"ywc_dmg.{event_id}")
    return next(option for option in event["options"] if option["key"] == option_key)


def _generated_je(je_id):
    return next(body for key, _, body in GENERATED_JE if key == je_id)


def _generated_event(event_id):
    return next(body for key, _, body in GENERATED_EVENTS if key == event_id)


def _nodes_field(nodes, name):
    return next(body for key, _, body in nodes if key == name)


def _actual_option(event_id, option_key):
    name = f"{event_id}.{option_key}"
    options = [body for key, _, body in _generated_event(event_id) if key == "option"]
    return next(body for body in options
                if any(k == "name" and val == name for k, _, val in body))


def _actual_option_effect(event_id, option_key):
    option = _actual_option(event_id, option_key)
    return [node for node in option if node[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]


def _consume_court_priority_notice(world):
    """Choose an authored wait option from a real court notice popup."""
    self_event = world.events[-1][1]
    event = _generated_event(self_event)
    assert world.conditions(_nodes_field(event, "trigger"), "DMG"), self_event
    world.execute(_nodes_field(event, "immediate"), "DMG")
    option_key = {"ywc_dmg.1016": "defer", "ywc_dmg.1018": "wait_for_posting"}.get(self_event)
    assert option_key, self_event
    option = _actual_option(self_event, option_key)
    assert world.conditions(_nodes_field(option, "trigger"), "DMG"), option_key
    world.execute(_actual_option_effect(self_event, option_key), "DMG")
    world.events.clear()


class DmgFoundationLifecycleTest(unittest.TestCase):
    def test_foundation_routes_reject_default_bankruptcy_and_war_at_effect_time(self):
        cases = (
            ("ywc_dmg_foundation_titles_route_ready", {
                "ywc_dmg_titles_registry_paid": 1, "ywc_dmg_titles_route": 2,
                "net_fixed_income": 0, "fixture_land_law_ready": 1,
                "fixture_agriculture_employment": 1,
            }),
            ("ywc_dmg_foundation_court_route_ready", {
                "ywc_dmg_court_charter_paid": 1, "ywc_dmg_court_budget_paid": 1,
                "ywc_dmg_court_route": 1, "net_fixed_income": 0,
                "fixture_government_appointment_ready": 1,
            }),
        )
        for trigger, base in cases:
            for bad_state in ({"in_default": 1}, {"is_at_war": 1}, {"fixture_declared_bankruptcy": 1}):
                facts = {**base, **bad_state}
                world = DmgWorld("", {"DMG": facts})
                if bad_state.get("fixture_declared_bankruptcy"):
                    world.modifiers.append(("DMG", {"modifier": "declared_bankruptcy"}))
                self.assertFalse(world.conditions(DMG_TRIGGER_MAP[trigger], "DMG"),
                                 f"{trigger} accepted {bad_state}")

    def test_foundation_observation_resets_during_default_and_requires_full_new_window(self):
        cases = (
            ("ywc_je_v03_dmg_land_titles_review", "titles", 6, {
                "ywc_dmg_titles_registry_paid": 1, "ywc_dmg_titles_route": 2,
                "fixture_land_law_ready": 1, "fixture_agriculture_employment": 1,
            }),
            ("ywc_je_v03_dmg_court_charter_review", "court", 9, {
                "ywc_dmg_court_charter_paid": 1, "ywc_dmg_court_budget_paid": 1,
                "ywc_dmg_court_route": 1, "fixture_government_appointment_ready": 1,
            }),
        )
        for je_id, prefix, months, route_facts in cases:
            world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
                "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                "net_fixed_income": 0, **route_facts,
            }})
            entry = _generated_je(je_id)
            world.execute(_nodes_field(entry, "immediate"), "DMG")
            world.journals.append(("DMG", [("type", "=", je_id)]))
            pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
            world.execute(pulse, "DMG")
            world.advance_months(3)
            world.countries["DMG"]["in_default"] = 1
            world.execute(pulse, "DMG")
            vars_ = world.countries["DMG"]
            self.assertNotIn(f"ywc_dmg_{prefix}_review_matured", vars_)
            self.assertNotIn(f"ywc_dmg_{prefix}_observation_started", vars_)
            world.countries["DMG"]["in_default"] = 0
            world.execute(pulse, "DMG")
            world.advance_months(months - 1)
            world.execute(pulse, "DMG")
            world.advance_months(1)
            world.execute(pulse, "DMG")
            self.assertEqual(vars_.get(f"ywc_dmg_{prefix}_review_matured"), 1,
                             f"{je_id} did not restart its full {months}-month observation")

    def test_actual_court_phase_admission_requires_the_preceding_phase_result(self):
        appointment = _je("v03_dmg_court_provinces", "ywc_je_v03_dmg_court_appointment")
        budget = _je("v03_dmg_court_provinces", "ywc_je_v03_dmg_court_budget")
        review = _je("v03_dmg_court_provinces", "ywc_je_v03_dmg_court_charter_review")
        appointment_possible = _field(appointment["script"], "possible")
        budget_possible = _field(budget["script"], "possible")
        review_possible = _field(review["script"], "possible")

        # Simplify the engine facts only. Keep each real JE possible block.
        facts = {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "fixture_owned_state": 1,
        }
        world = DmgWorld("", {"DMG": facts})
        # These are the authored gates that must prevent entering future phases
        # while their actual predecessor result is absent.
        self.assertTrue(world.conditions(appointment_possible, "DMG"))
        self.assertFalse(world.conditions(budget_possible, "DMG"),
                         "budget JE admitted before appointment result")
        self.assertFalse(world.conditions(review_possible, "DMG"),
                         "charter-review JE admitted before budget result")
        facts["ywc_dmg_court_budget_stage"] = 1
        self.assertTrue(world.conditions(budget_possible, "DMG"),
                        "budget JE must open after the real appointment result")
        facts["ywc_dmg_court_defence_veto"] = 1
        self.assertTrue(world.conditions(review_possible, "DMG"),
                        "review JE must open after the real budget result")

    def test_actual_new_je_goal_and_failure_are_disjoint_for_withdrawal(self):
        cases = (
            ("v03_dmg_two_land_titles", "ywc_je_v03_dmg_land_titles_review", "ywc_dmg_titles"),
            ("v03_dmg_court_provinces", "ywc_je_v03_dmg_court_appointment", "ywc_dmg_court"),
            ("v03_dmg_court_provinces", "ywc_je_v03_dmg_court_budget", "ywc_dmg_court"),
            ("v03_dmg_court_provinces", "ywc_je_v03_dmg_court_charter_review", "ywc_dmg_court"),
        )
        for slug, je_id, prefix in cases:
            je = _je(slug, je_id)
            goal = parse(je["goal"].strip()[1:-1])
            exit_conditions = parse(je["exit_conditions"].strip()[1:-1])
            withdrawn = {
                f"{prefix}_outcome": 5,
                f"{prefix}_withdraw_requested": 1,
                "ywc_dmg_court_budget_stage": 1,
                "ywc_dmg_court_defence_veto": 1,
            }
            world = PulseWorld("", {"DMG": withdrawn})
            self.assertFalse(world.conditions(goal, "DMG"), f"{je_id} calls withdrawal success")
            self.assertTrue(world.conditions(exit_conditions, "DMG"), f"{je_id} misses withdrawal exit")
            for terminal in range(1, 5):
                success = {f"{prefix}_outcome": terminal}
                if je_id.endswith("court_appointment"):
                    success["ywc_dmg_court_budget_stage"] = 1
                if je_id.endswith("court_budget"):
                    success["ywc_dmg_court_defence_veto"] = 1
                success_world = PulseWorld("", {"DMG": success})
                self.assertTrue(success_world.conditions(goal, "DMG"),
                                f"{je_id} excludes lawful terminal {terminal}")
                self.assertFalse(success_world.conditions(exit_conditions, "DMG"),
                                 f"{je_id} treats lawful terminal {terminal} as failure")

    def test_titles_withdrawal_helper_marks_failure_without_success_outcome(self):
        world = DmgWorld(EFFECTS, {"DMG": {
            "ywc_v03_dmg_v03_dmg_two_land_titles_started": 1,
            "ywc_v03_active_arc_count": 1,
            "ywc_v03_visible_task_count": 1,
        }})
        world.run("ywc_dmg_foundation_withdraw_titles", "DMG")
        vars_ = world.countries["DMG"]
        self.assertEqual(vars_.get("ywc_dmg_titles_withdraw_requested"), 1)
        self.assertEqual(vars_.get("ywc_dmg_titles_outcome"), 5)
        je = _je("v03_dmg_two_land_titles", "ywc_je_v03_dmg_land_titles_review")
        self.assertFalse(world.conditions(parse(je["goal"].strip()[1:-1]), "DMG"))

    def test_actual_titles_monthly_pulse_matures_at_six_months_and_resets_on_loss(self):
        je = _je("v03_dmg_two_land_titles", "ywc_je_v03_dmg_land_titles_review")
        pulse = _monthly_effect(je["script"])
        world = DmgWorld("", {"DMG": {
            "ywc_v03_dmg_v03_dmg_two_land_titles_started": 1,
            "ywc_dmg_titles_registry_paid": 1,
            "ywc_dmg_titles_route": 2,
            "net_fixed_income": 0,
            "fixture_land_law_ready": 1,
            "fixture_agriculture_employment": 1,
        }})

        for _ in range(5):
            world.execute(pulse, "DMG")
            world.advance_months(1)
        self.assertNotIn("ywc_dmg_titles_review_matured", world.countries["DMG"])
        world.execute(pulse, "DMG")
        world.advance_months(1)
        world.execute(pulse, "DMG")
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_titles_review_matured"), 1)
        self.assertNotIn("ywc_dmg_titles_review_due", world.countries["DMG"])

        world.countries["DMG"]["fixture_land_law_ready"] = 0
        world.countries["DMG"]["fixture_agriculture_employment"] = 0
        world.execute(pulse, "DMG")
        self.assertNotIn("ywc_dmg_titles_review_matured", world.countries["DMG"])
        self.assertNotIn("ywc_dmg_titles_observation_started", world.countries["DMG"])

    def test_titles_blocked_clock_starts_only_while_blocked_and_clears_on_recovery(self):
        entry = _generated_je("ywc_je_v03_dmg_land_titles_review")
        pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
        world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0,
            "ywc_v03_visible_task_count": 0,
            "fixture_owned_state": 1,
        }})
        world.execute(_nodes_field(entry, "immediate"), "DMG")
        self.assertNotIn("ywc_dmg_titles_blocked_12_due", world.countries["DMG"])
        world.journals.append(("DMG", [("type", "=", "ywc_je_v03_dmg_land_titles_review")]))
        world.execute(pulse, "DMG")
        self.assertEqual(world.months_until_expiry["DMG"].get("ywc_dmg_titles_blocked_12_due"), 12)
        world.countries["DMG"].update({
            "ywc_dmg_titles_route": 2,
            "ywc_dmg_titles_registry_paid": 1,
            "net_fixed_income": 0,
            "fixture_land_law_ready": 1,
            "fixture_agriculture_employment": 1,
            "ywc_dmg_titles_blocked_12_notice": 1,
            "ywc_dmg_titles_blocked_36_notice": 1,
        })
        world.execute(pulse, "DMG")
        vars_ = world.countries["DMG"]
        self.assertNotIn("ywc_dmg_titles_blocked_12_due", vars_)
        self.assertNotIn("ywc_dmg_titles_blocked_36_due", vars_)
        self.assertNotIn("ywc_dmg_titles_blocked_12_notice", vars_)
        self.assertNotIn("ywc_dmg_titles_blocked_36_notice", vars_)

    def test_actual_court_monthly_pulse_preserves_nine_continuous_months(self):
        je = _je("v03_dmg_court_provinces", "ywc_je_v03_dmg_court_charter_review")
        pulse = _monthly_effect(je["script"])
        world = DmgWorld("", {"DMG": {
            "ywc_v03_dmg_v03_dmg_court_provinces_started": 1,
            "ywc_dmg_court_charter_paid": 1,
            "ywc_dmg_court_budget_paid": 1,
            "ywc_dmg_court_route": 1,
            "net_fixed_income": 0,
            "fixture_government_appointment_ready": 1,
        }})
        world.execute(pulse, "DMG")
        self.assertEqual(world.months_until_expiry["DMG"]["ywc_dmg_court_review_due"], 9)
        for _ in range(8):
            world.advance_months(1)
            world.execute(pulse, "DMG")
            self.assertNotIn("ywc_dmg_court_review_matured", world.countries["DMG"])
        world.advance_months(1)
        world.execute(pulse, "DMG")
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_review_matured"), 1)
        self.assertNotIn("ywc_dmg_court_review_due", world.countries["DMG"])

    def test_actual_court_pulse_delivers_narrowed_1019_and_1020_pending_nodes(self):
        je = _je("v03_dmg_court_provinces", "ywc_je_v03_dmg_court_budget")
        pulse = _monthly_effect(je["script"])
        for event_id in (1019, 1020):
            world = DmgWorld("", {"DMG": {
                "ywc_v03_dmg_v03_dmg_court_provinces_started": 1,
                "ywc_dmg_court_budget_stage": 1,
                "ywc_dmg_court_task_narrowed": 1,
                "ywc_dmg_court_pending_event": event_id,
            }})
            world.execute(pulse, "DMG")
            self.assertEqual(world.events, [("DMG", f"ywc_dmg.{event_id}")])
            self.assertNotIn("ywc_dmg_court_pending_event", world.countries["DMG"])

    def test_actual_twelve_and_thirty_six_month_blocked_clocks_dispatch_recovery_notices(self):
        cases = (
            ("ywc_je_v03_dmg_land_titles_review", "ywc_dmg_titles", 1010, 1015,
             "ywc_dmg_titles_blocked_12_notice", "ywc_dmg_titles_blocked_36_notice",
             "ywc_v03_dmg_v03_dmg_two_land_titles_started"),
            ("ywc_je_v03_dmg_court_charter_review", "ywc_dmg_court", 1022, 1023,
             "ywc_dmg_court_blocked_12_notice", "ywc_dmg_court_blocked_36_notice",
             "ywc_v03_dmg_v03_dmg_court_provinces_started"),
        )
        for je_id, prefix, queued, remedy, notice12, notice36, started in cases:
            entry = _generated_je(je_id)
            pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
            world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
                started: 1,
                "ywc_v03_active_arc_count": 1,
                "ywc_v03_visible_task_count": 1,
                "fixture_owned_state": 1,
                f"{prefix}_pending_event": queued,
            }})
            if prefix == "ywc_dmg_court":
                world.countries["DMG"].update({
                    "ywc_dmg_court_route": 3, "ywc_dmg_court_lower_target_selected": 1,
                    "ywc_dmg_court_charter_paid": 1, "ywc_dmg_court_budget_paid": 1,
                    "ywc_dmg_court_representation": 3, "ywc_dmg_court_defence_veto": 3,
                })
            world.journals.append(("DMG", [("type", "=", je_id)]))
            world.execute(pulse, "DMG")
            for month in range(1, 37):
                world.advance_months(1)
                world.execute(pulse, "DMG")
                if world.events:
                    dispatched = world.events[-1][1]
                    if dispatched == f"ywc_dmg.{remedy}" and month < 36:
                        event = _generated_event(dispatched)
                        world.execute(_nodes_field(event, "immediate"), "DMG")
                        renegotiate = _actual_option(dispatched, "renegotiate")
                        self.assertTrue(world.conditions(_nodes_field(renegotiate, "trigger"), "DMG"))
                        world.execute(_actual_option_effect(dispatched, "renegotiate"), "DMG")
                        world.events.clear()
                    elif dispatched != f"ywc_dmg.{remedy}":
                        world.events.clear()
                        event = _generated_event(dispatched)
                        world.execute(_nodes_field(event, "immediate"), "DMG")
                        world.execute(_actual_option_effect(dispatched, "defer"), "DMG")
                if month == 11:
                    self.assertNotIn(notice12, world.countries["DMG"])
                if month == 12:
                    self.assertEqual(world.countries["DMG"].get(notice12), 1)
                if month == 35:
                    self.assertNotIn(notice36, world.countries["DMG"])
            self.assertEqual(world.countries["DMG"].get(notice36), 1)
            for _ in range(4):
                if any(event_id == f"ywc_dmg.{remedy}" for _, event_id in world.events):
                    break
                world.advance_days(30)
                world.execute(pulse, "DMG")
                if world.events and world.events[-1][1] != f"ywc_dmg.{remedy}":
                    dispatched = world.events.pop(0)[1]
                    event = _generated_event(dispatched)
                    world.execute(_nodes_field(event, "immediate"), "DMG")
                    world.execute(_actual_option_effect(dispatched, "defer"), "DMG")
            self.assertEqual(world.events[-1], ("DMG", f"ywc_dmg.{remedy}"))
            self.assertEqual(world.countries["DMG"].get(f"{prefix}_pending_event"), queued)


    def test_actual_titles_twelve_month_defer_proposes_target_without_closing(self):
        entry = _generated_je("ywc_je_v03_dmg_land_titles_review")
        pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
        world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "yearly_gross_income": 52000, "gold_reserves": 50000, "net_fixed_income": 0,
            "fixture_owned_state": 1,
        }})
        self.assertTrue(world.conditions(_nodes_field(entry, "possible"), "DMG"))
        world.execute(_nodes_field(entry, "immediate"), "DMG")
        world.journals.append(("DMG", [("type", "=", "ywc_je_v03_dmg_land_titles_review")]))
        delivered_1010 = 0
        for _ in range(50):
            self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == "ywc_je_v03_dmg_land_titles_review"
                                for tag, body in world.journals))
            self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"))
            self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))
            world.execute(pulse, "DMG")
            if world.events:
                event_id = world.events[-1][1]
                event = _generated_event(event_id)
                self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"), event_id)
                world.execute(_nodes_field(event, "immediate"), "DMG")
                if event_id == "ywc_dmg.1010":
                    delivered_1010 += 1
                    option = _actual_option(event_id, "defer")
                    self.assertTrue(world.conditions(_nodes_field(option, "trigger"), "DMG"))
                    world.execute(_actual_option_effect(event_id, "defer"), "DMG")
                elif event_id == "ywc_dmg.1015":
                    limited = _actual_option(event_id, "limited_settlement")
                    self.assertFalse(world.conditions(_nodes_field(limited, "trigger"), "DMG"),
                                     "a twelve-month notice cannot complete without a selected target and fresh review")
                    option = _actual_option(event_id, "renegotiate")
                    self.assertTrue(world.conditions(_nodes_field(option, "trigger"), "DMG"))
                    self.assertEqual(world.countries["DMG"].get("ywc_dmg_titles_blocked_12_delivered"), 1)
                    self.assertFalse(world.countries["DMG"].get("ywc_dmg_titles_blocked_36_delivered"))
                    world.execute(_actual_option_effect(event_id, "renegotiate"), "DMG")
                    vars_ = world.countries["DMG"]
                    self.assertEqual(vars_.get("ywc_dmg_titles_lower_target_proposed"), 1)
                    self.assertNotIn("ywc_dmg_titles_route", vars_, "a proposal is not an actual target selection")
                    self.assertNotIn("ywc_dmg_titles_outcome", vars_)
                    self.assertNotIn("ywc_dmg_two_land_titles_outcome", vars_)
                    self.assertNotIn("ywc_v03_dmg_v03_dmg_two_land_titles_settled", vars_)
                    self.assertEqual(vars_.get("ywc_dmg_titles_pending_event"), 1010)
                    self.assertGreaterEqual(delivered_1010, 4)
                    return
                else:
                    self.fail(f"unexpected event in the real defer chain: {event_id}")
                world.events.clear()
            world.advance_months(1)
        self.fail("the active titles lane did not deliver its first 12-month remedy after real defers")

    def test_limited_option_requires_actual_target_fees_implementation_and_fresh_review(self):
        for event_id, prefix, helper, vars_ in (
            ("ywc_dmg.1015", "ywc_dmg_titles", "ywc_dmg_foundation_limit_titles",
             {"ywc_dmg_titles_blocked_36_delivered": 1}),
            ("ywc_dmg.1023", "ywc_dmg_court", "ywc_dmg_foundation_limit_court",
             {"ywc_dmg_court_blocked_36_delivered": 1}),
        ):
            world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": vars_})
            option = _actual_option(event_id, "limited_settlement")
            self.assertFalse(world.conditions(_nodes_field(option, "trigger"), "DMG"),
                             f"{event_id} cannot offer a free month-36 ending")
            world.run(helper, "DMG")
            self.assertNotIn(f"{prefix}_outcome", world.countries["DMG"])

    def test_actual_court_local_compact_loss_notice_recovery_and_fresh_limited_close(self):
        world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "yearly_gross_income": 52000, "gold_reserves": 50000, "net_fixed_income": 0,
            "fixture_owned_state": 1, "fixture_government_appointment_ready": 1,
            "fixture_secondary_office_ready": 1, "fixture_agriculture_employment": 1,
            "fixture_landowner_interest_group": 1,
        }})
        phases = (
            ("ywc_je_v03_dmg_court_appointment", "ywc_dmg.1016", "local_compact"),
            ("ywc_je_v03_dmg_court_appointment", "ywc_dmg.1017", "local_share_countersign"),
            ("ywc_je_v03_dmg_court_budget", "ywc_dmg.1018", "temporary_deputy"),
            ("ywc_je_v03_dmg_court_budget", "ywc_dmg.1019", "time_limited_amendment"),
            ("ywc_je_v03_dmg_court_budget", "ywc_dmg.1020", "old_ledger_consultation"),
            ("ywc_je_v03_dmg_court_budget", "ywc_dmg.1021", "old_system_no_veto"),
            ("ywc_je_v03_dmg_court_charter_review", "ywc_dmg.1022", "confirm_signed_terms"),
        )
        current_je = "ywc_je_v03_dmg_court_appointment"
        entry = _generated_je(current_je)
        self.assertTrue(world.conditions(_nodes_field(entry, "possible"), "DMG"))
        world.execute(_nodes_field(entry, "immediate"), "DMG")
        world.journals.append(("DMG", [("type", "=", current_je)]))
        for next_je, event_id, option_key in phases:
            if next_je != current_je:
                prior = _generated_je(current_je)
                self.assertTrue(world.conditions(_nodes_field(prior, "complete"), "DMG"), current_je)
                world.journals = [(tag, body) for tag, body in world.journals
                                  if dict((k, v) for k, _, v in body).get("type") != current_je]
                entry = _generated_je(next_je)
                self.assertTrue(world.conditions(_nodes_field(entry, "possible"), "DMG"), next_je)
                world.execute(_nodes_field(entry, "immediate"), "DMG")
                world.journals.append(("DMG", [("type", "=", next_je)]))
                current_je = next_je
            entry = _generated_je(current_je)
            pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
            for _ in range(5):
                self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == current_je
                                    for tag, body in world.journals), f"{current_je} is active before pulse")
                self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"), current_je)
                self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"), current_je)
                world.execute(pulse, "DMG")
                if world.events:
                    break
                world.advance_months(1)
            self.assertEqual(world.events, [("DMG", event_id)], event_id)
            event = _generated_event(event_id)
            self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"), event_id)
            world.execute(_nodes_field(event, "immediate"), "DMG")
            option = _actual_option(event_id, option_key)
            self.assertTrue(world.conditions(_nodes_field(option, "trigger"), "DMG"), f"{event_id}.{option_key}")
            world.execute(_actual_option_effect(event_id, option_key), "DMG")
            world.events.clear()
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_route"), 3)
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_charter_paid"), 1)
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_budget_paid"), 1)
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_lower_target_selected"), 1)
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_representation"), 3)
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_defence_veto"), 3)

        current_je = "ywc_je_v03_dmg_court_charter_review"
        entry = _generated_je(current_je)
        pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
        world.countries["DMG"]["in_default"] = 1
        elapsed_months = 0
        delivered_36 = False
        for _ in range(44):
            self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == current_je
                                for tag, body in world.journals), "court final JE stays active through loss")
            self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"))
            self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))
            world.execute(pulse, "DMG")
            if world.events:
                event_id = world.events[-1][1]
                event = _generated_event(event_id)
                self.assertEqual(event_id, "ywc_dmg.1023")
                self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"), event_id)
                world.execute(_nodes_field(event, "immediate"), "DMG")
                vars_ = world.countries["DMG"]
                if vars_.get("ywc_dmg_court_blocked_36_delivered"):
                    delivered_36 = True
                    self.assertGreaterEqual(elapsed_months, 36,
                                            f"36-month remedy delivered before its real clock expired: {elapsed_months}")
                    limited = _actual_option(event_id, "limited_settlement")
                    self.assertFalse(world.conditions(_nodes_field(limited, "trigger"), "DMG"),
                                     "default blocks terminal close even after real delivery")
                    renegotiate = _actual_option(event_id, "renegotiate")
                    self.assertTrue(world.conditions(_nodes_field(renegotiate, "trigger"), "DMG"))
                    world.execute(_actual_option_effect(event_id, "renegotiate"), "DMG")
                elif vars_.get("ywc_dmg_court_blocked_12_delivered"):
                    limited = _actual_option(event_id, "limited_settlement")
                    self.assertFalse(world.conditions(_nodes_field(limited, "trigger"), "DMG"),
                                     "12-month notice cannot terminate the arc")
                    renegotiate = _actual_option(event_id, "renegotiate")
                    self.assertTrue(world.conditions(_nodes_field(renegotiate, "trigger"), "DMG"))
                    world.execute(_actual_option_effect(event_id, "renegotiate"), "DMG")
                else:
                    self.fail(f"final review event delivered without a real remedy notice: {vars_}")
                world.events.clear()
            world.advance_months(1)
            elapsed_months += 1
            if delivered_36:
                break
        self.assertTrue(delivered_36, f"36-month notice was not delivered after bounded cooldown; elapsed={elapsed_months}")
        self.assertLessEqual(elapsed_months, 40, "notice delivery must remain bounded by the 90-day shared cooldown")
        world.countries["DMG"]["in_default"] = 0
        world.execute(pulse, "DMG")
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_observation_started"), 1)
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_blocked_36_delivered"), 1,
                         f"recovery must preserve an earned limited-review notice: {world.countries['DMG']}")
        self.assertNotIn("ywc_dmg_court_review_matured", world.countries["DMG"])
        for _ in range(10):
            self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"))
            self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))
            world.execute(pulse, "DMG")
            if world.countries["DMG"].get("ywc_dmg_court_review_matured"):
                break
            world.advance_months(1)
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_review_matured"), 1)
        self.assertTrue(world.events, "the actual final review event is retried after the fresh nine-month window")
        event_id = world.events[-1][1]
        event = _generated_event(event_id)
        self.assertEqual(event_id, "ywc_dmg.1023")
        self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"))
        world.execute(_nodes_field(event, "immediate"), "DMG")
        limited = _actual_option(event_id, "limited_settlement")
        self.assertTrue(world.conditions(_nodes_field(limited, "trigger"), "DMG"))
        world.execute(_actual_option_effect(event_id, "limited_settlement"), "DMG")
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_outcome"), 4)
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_provinces_outcome"), 4)
        self.assertEqual(world.countries["DMG"].get("ywc_v03_dmg_v03_dmg_court_provinces_settled"), 1)
        self.assertTrue(world.conditions(_nodes_field(entry, "complete"), "DMG"))
        self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))

    def test_real_court_appointment_and_budget_defers_receive_priority_notice(self):
        def setup():
            return DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
                "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                "yearly_gross_income": 52000, "gold_reserves": 50000, "net_fixed_income": 0,
                "fixture_owned_state": 1, "fixture_government_appointment_ready": 1,
                "fixture_landowner_interest_group": 1,
            }})

        appointment = _generated_je("ywc_je_v03_dmg_court_appointment")
        world = setup()
        self.assertTrue(world.conditions(_nodes_field(appointment, "possible"), "DMG"))
        world.execute(_nodes_field(appointment, "immediate"), "DMG")
        world.journals.append(("DMG", [("type", "=", "ywc_je_v03_dmg_court_appointment")]))
        pulse = _nodes_field(_nodes_field(appointment, "on_monthly_pulse"), "effect")
        count1016 = notices = 0
        for _ in range(40):
            self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == "ywc_je_v03_dmg_court_appointment" for tag, body in world.journals))
            self.assertFalse(world.conditions(_nodes_field(appointment, "complete"), "DMG"))
            self.assertFalse(world.conditions(_nodes_field(appointment, "fail"), "DMG"))
            world.execute(pulse, "DMG")
            if world.events:
                event_id=world.events[-1][1]; self.assertEqual(event_id,"ywc_dmg.1016")
                event=_generated_event(event_id); self.assertTrue(world.conditions(_nodes_field(event,"trigger"),"DMG"))
                if world.countries["DMG"].get("ywc_dmg_court_notice_popup_open"):
                    notices += 1
                world.execute(_nodes_field(event,"immediate"),"DMG")
                defer=_actual_option(event_id,"defer"); self.assertTrue(world.conditions(_nodes_field(defer,"trigger"),"DMG"))
                world.execute(_actual_option_effect(event_id,"defer"),"DMG"); world.events.clear(); count1016 += 1
            world.advance_months(1)
        self.assertGreaterEqual(notices,1,"appointment notice must be delivered despite repeated legal defer")
        self.assertGreater(count1016,8)
        # Withdraw through the actual appointment event after the long defer chain.
        for _ in range(4):
            world.execute(pulse,"DMG")
            if world.events: break
            world.advance_months(1)
        self.assertEqual(world.events[-1],("DMG","ywc_dmg.1016"))
        event=_generated_event("ywc_dmg.1016");self.assertTrue(world.conditions(_nodes_field(event,"trigger"),"DMG"))
        world.execute(_nodes_field(event,"immediate"),"DMG")
        withdraw=_actual_option("ywc_dmg.1016","withdraw_court");self.assertTrue(world.conditions(_nodes_field(withdraw,"trigger"),"DMG"))
        world.execute(_actual_option_effect("ywc_dmg.1016","withdraw_court"),"DMG")
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_withdraw_requested"),1)

        # A second legal chain reaches the actual budget phase and repeatedly waits there.
        world=setup(); self.assertTrue(world.conditions(_nodes_field(appointment,"possible"),"DMG"))
        world.execute(_nodes_field(appointment,"immediate"),"DMG")
        world.journals.append(("DMG",[("type","=","ywc_je_v03_dmg_court_appointment")]))
        pulse=_nodes_field(_nodes_field(appointment,"on_monthly_pulse"),"effect")
        for event_id,option_key in (("ywc_dmg.1016","royal_administration"),("ywc_dmg.1017","central_audit_pays")):
            for _ in range(4):
                world.execute(pulse,"DMG")
                if world.events:break
                world.advance_months(1)
            self.assertEqual(world.events[-1],("DMG",event_id));event=_generated_event(event_id)
            self.assertTrue(world.conditions(_nodes_field(event,"trigger"),"DMG"));world.execute(_nodes_field(event,"immediate"),"DMG")
            option=_actual_option(event_id,option_key);self.assertTrue(world.conditions(_nodes_field(option,"trigger"),"DMG"))
            world.execute(_actual_option_effect(event_id,option_key),"DMG");world.events.clear()
        budget=_generated_je("ywc_je_v03_dmg_court_budget")
        self.assertTrue(world.conditions(_nodes_field(budget,"possible"),"DMG"))
        world.journals=[(tag,body) for tag,body in world.journals if dict((k,v) for k,_,v in body).get("type")!="ywc_je_v03_dmg_court_appointment"]
        world.execute(_nodes_field(budget,"immediate"),"DMG");world.journals.append(("DMG",[("type","=","ywc_je_v03_dmg_court_budget")]))
        world.countries["DMG"]["fixture_government_appointment_ready"] = 0
        pulse=_nodes_field(_nodes_field(budget,"on_monthly_pulse"),"effect"); notices=0
        for _ in range(40):
            self.assertFalse(world.conditions(_nodes_field(budget,"complete"),"DMG"));self.assertFalse(world.conditions(_nodes_field(budget,"fail"),"DMG"))
            world.execute(pulse,"DMG")
            if world.events:
                event_id=world.events[-1][1];self.assertEqual(event_id,"ywc_dmg.1018");event=_generated_event(event_id)
                self.assertTrue(world.conditions(_nodes_field(event,"trigger"),"DMG"))
                if world.countries["DMG"].get("ywc_dmg_court_notice_popup_open"): notices+=1
                world.execute(_nodes_field(event,"immediate"),"DMG")
                wait=_actual_option(event_id,"wait_for_posting");self.assertTrue(world.conditions(_nodes_field(wait,"trigger"),"DMG"))
                world.execute(_actual_option_effect(event_id,"wait_for_posting"),"DMG");world.events.clear()
            world.advance_months(1)
        self.assertGreaterEqual(notices,1,"budget-phase notice must be delivered during real defer/wait")
        for _ in range(4):
            world.execute(pulse,"DMG")
            if world.events: break
            world.advance_months(1)
        self.assertEqual(world.events[-1],("DMG","ywc_dmg.1018"))
        event=_generated_event("ywc_dmg.1018");self.assertTrue(world.conditions(_nodes_field(event,"trigger"),"DMG"))
        world.execute(_nodes_field(event,"immediate"),"DMG")
        withdraw=_actual_option("ywc_dmg.1018","withdraw_court");self.assertTrue(world.conditions(_nodes_field(withdraw,"trigger"),"DMG"))
        world.execute(_actual_option_effect("ywc_dmg.1018","withdraw_court"),"DMG")
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_withdraw_requested"),1)

    def test_remedy_notice_preempts_popup_without_replacing_the_normal_queue(self):
        cases = (
            ("ywc_je_v03_dmg_land_titles_review", "ywc_dmg_titles", 1010, 1015,
             "ywc_dmg_titles_blocked_36_notice"),
            ("ywc_je_v03_dmg_court_charter_review", "ywc_dmg_court", 1022, 1023,
             "ywc_dmg_court_blocked_36_notice"),
        )
        for je_id, prefix, queued, remedy, notice in cases:
            entry = _generated_je(je_id)
            pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
            world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
                "ywc_v03_dmg_v03_dmg_two_land_titles_started" if prefix == "ywc_dmg_titles" else "ywc_v03_dmg_v03_dmg_court_provinces_started": 1,
                "ywc_v03_active_arc_count": 1,
                "ywc_v03_visible_task_count": 1,
                "fixture_owned_state": 1,
                "ywc_dmg_titles_pending_event" if prefix == "ywc_dmg_titles" else "ywc_dmg_court_pending_event": queued,
                notice: 1,
            }})
            world.journals.append(("DMG", [("type", "=", je_id)]))
            world.execute(pulse, "DMG")
            self.assertEqual(world.events, [("DMG", f"ywc_dmg.{remedy}")])
            self.assertEqual(world.countries["DMG"].get(f"{prefix}_pending_event"), queued,
                             "remedy popup must leave the story node queued")

    def test_actual_shared_major_dispatch_waits_for_the_full_ninety_day_cooldown(self):
        je = _je("v03_dmg_two_land_titles", "ywc_je_v03_dmg_land_titles_review")
        pulse = _monthly_effect(je["script"])
        world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
            "ywc_v03_dmg_v03_dmg_two_land_titles_started": 1,
            "ywc_dmg_titles_pending_event": 1010,
            "ywc_dmg_titles_blocked_12_due": 1,
            "ywc_dmg_titles_blocked_36_due": 1,
            "ywc_dmg_titles_registry_paid": 1,
            "ywc_dmg_titles_route": 2,
            "net_fixed_income": 0,
            "fixture_owned_state": 1,
            "fixture_land_law_ready": 1,
            "fixture_agriculture_employment": 1,
        }})
        world.run("ywc_v03_mark_major_delivered", "DMG")
        world.execute(pulse, "DMG")
        self.assertEqual(world.events, [])
        world.advance_days(89)
        world.execute(pulse, "DMG")
        self.assertEqual(world.events, [])
        world.advance_days(1)
        world.execute(pulse, "DMG")
        self.assertEqual(world.events, [("DMG", "ywc_dmg.1010")])
        self.assertNotIn("ywc_dmg_titles_pending_event", world.countries["DMG"])

    def test_actual_titles_event_keeps_current_node_when_payment_fails(self):
        event = next(e for e in _arc("v03_dmg_two_land_titles")["events"] if e["id"] == "ywc_dmg.1010")
        option = next(o for o in event["options"] if o["key"] == "mixed_arbitration")
        world = DmgWorld(EFFECTS, {"DMG": {
            "yearly_gross_income": 52000,
            "gold_reserves": 0,
            "ywc_dmg_titles_pending_event": 1010,
        }})
        world.execute(parse(option["effect"].strip()[1:-1]), "DMG")
        vars_ = world.countries["DMG"]
        self.assertNotIn("ywc_dmg_titles_compensation_paid", vars_)
        self.assertNotIn("ywc_dmg_titles_route", vars_)
        self.assertEqual(vars_["ywc_dmg_titles_pending_event"], 1010)

    def test_court_paid_phase_chain_runs_the_authored_event_options_in_order(self):
        world = DmgWorld(EFFECTS, {"DMG": {
            "yearly_gross_income": 52000,
            "gold_reserves": 50000,
            "net_fixed_income": 0,
        }})
        choices = (
            (1016, "royal_administration", 1017),
            (1017, "central_audit_pays", 1018),
            (1018, "authorize_staffed", 1019),
            (1019, "time_limited_amendment", 1020),
            (1020, "office_charter_cosign", 1021),
            (1021, "court_keeps_control", 1022),
            (1022, "confirm_signed_terms", 1023),
        )
        for event_id, option_key, next_node in choices:
            option = _event_option("v03_dmg_court_provinces", event_id, option_key)
            world.execute(parse(option["effect"].strip()[1:-1]), "DMG")
            self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_pending_event"), next_node,
                             f"{event_id}.{option_key}")
        vars_ = world.countries["DMG"]
        self.assertEqual(vars_.get("ywc_dmg_court_charter_paid"), 1)
        self.assertEqual(vars_.get("ywc_dmg_court_budget_paid"), 1)
        self.assertEqual(vars_.get("ywc_dmg_court_route"), 1)
        self.assertEqual(vars_.get("ywc_dmg_court_budget_stage"), 1)
        self.assertEqual(vars_.get("ywc_dmg_court_defence_veto"), 1)

    def test_actual_entry_phase_options_queue_pulse_and_terminal_complete_one_court_route(self):
        world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "yearly_gross_income": 52000,
            "gold_reserves": 50000,
            "net_fixed_income": 0,
            "fixture_owned_state": 1,
            "fixture_government_appointment_ready": 1,
            "fixture_landowner_interest_group": 1,
        }})
        je_id = "ywc_je_v03_dmg_court_appointment"
        entry = _generated_je(je_id)
        possible = _nodes_field(entry, "possible")
        self.assertTrue(world.conditions(possible, "DMG"))
        world.execute(_nodes_field(entry, "immediate"), "DMG")
        world.journals.append(("DMG", [("type", "=", je_id)]))

        plan = (
            ("ywc_je_v03_dmg_court_appointment", "ywc_dmg.1016", "royal_administration"),
            ("ywc_je_v03_dmg_court_appointment", "ywc_dmg.1017", "central_audit_pays"),
            ("ywc_je_v03_dmg_court_budget", "ywc_dmg.1018", "authorize_staffed"),
            ("ywc_je_v03_dmg_court_budget", "ywc_dmg.1019", "time_limited_amendment"),
            ("ywc_je_v03_dmg_court_budget", "ywc_dmg.1020", "office_charter_cosign"),
            ("ywc_je_v03_dmg_court_budget", "ywc_dmg.1021", "court_keeps_control"),
            ("ywc_je_v03_dmg_court_charter_review", "ywc_dmg.1022", "confirm_signed_terms"),
        )
        current_je = je_id
        for next_je, event_id, option_key in plan:
            if next_je != current_je:
                world.journals = [(tag, body) for tag, body in world.journals
                                  if dict((k, v) for k, _, v in body).get("type") != current_je]
                next_entry = _generated_je(next_je)
                self.assertTrue(world.conditions(_nodes_field(next_entry, "possible"), "DMG"),
                                f"next phase {next_je} is gated by its actual predecessor result")
                self.assertTrue(world.conditions(_nodes_field(_generated_je(current_je), "complete"), "DMG"),
                                f"prior phase {current_je} completes before handoff")
                current_je = next_je
                entry = _generated_je(current_je)
                world.execute(_nodes_field(entry, "immediate"), "DMG")
                world.journals.append(("DMG", [("type", "=", current_je)]))

            entry = _generated_je(current_je)
            pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
            for _ in range(4):
                self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == current_je
                                    for tag, body in world.journals), f"{current_je} must be active before pulse")
                self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"), current_je)
                self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"), current_je)
                world.execute(pulse, "DMG")
                if world.events:
                    break
                world.advance_months(1)
            self.assertEqual(world.events[-1], ("DMG", event_id), f"dispatch {event_id}")
            world.events.clear()
            event = _generated_event(event_id)
            self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"), f"event {event_id} trigger")
            world.execute(_nodes_field(event, "immediate"), "DMG")
            option = _actual_option(event_id, option_key)
            try:
                option_trigger = _nodes_field(option, "trigger")
            except StopIteration:
                option_trigger = None
            if option_trigger:
                self.assertTrue(world.conditions(option_trigger, "DMG"), f"{event_id}.{option_key} trigger")
            world.execute(_actual_option_effect(event_id, option_key), "DMG")

        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_pending_event"), 1023)
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_defence_veto"), 1)
        current_je = "ywc_je_v03_dmg_court_charter_review"
        entry = _generated_je(current_je)
        for _ in range(10):
            self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == current_je
                                for tag, body in world.journals), f"{current_je} must be active before pulse")
            self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"), current_je)
            self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"), current_je)
            world.execute(_nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect"), "DMG")
            if world.events:
                break
            world.advance_months(1)
        self.assertEqual(world.events, [("DMG", "ywc_dmg.1023")])
        event = _generated_event("ywc_dmg.1023")
        self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"), "event 1023 trigger")
        world.execute(_nodes_field(event, "immediate"), "DMG")
        final_option = _actual_option("ywc_dmg.1023", "confirm_royal")
        world.countries["DMG"]["in_default"] = 1
        pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
        world.execute(pulse, "DMG")
        self.assertNotIn("ywc_dmg_court_review_matured", world.countries["DMG"],
                         "default pulse must erase the old court maturity")
        self.assertFalse(world.conditions(_nodes_field(final_option, "trigger"), "DMG"),
                         "stale final choice must close when default starts after the popup")
        world.execute(_actual_option_effect("ywc_dmg.1023", "confirm_royal"), "DMG")
        self.assertNotIn("ywc_dmg_court_outcome", world.countries["DMG"], "effect-time guard must reject stale default")
        self.assertNotIn("ywc_dmg_court_provinces_outcome", world.countries["DMG"])
        self.assertNotIn("ywc_v03_dmg_v03_dmg_court_provinces_settled", world.countries["DMG"])
        self.assertNotIn("ywc_dmg_foundation_court_central", world.modifiers)
        world.countries["DMG"]["in_default"] = 0
        world.execute(pulse, "DMG")
        for _ in range(10):
            self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == current_je
                                for tag, body in world.journals), "final court JE must remain active for retry")
            self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"))
            self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))
            world.execute(pulse, "DMG")
            if world.countries["DMG"].get("ywc_dmg_court_review_matured"):
                break
            world.advance_months(1)
        self.assertTrue(world.countries["DMG"].get("ywc_dmg_court_review_matured"), "court retry must reobserve nine months")
        world.events.clear()
        self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"), "real final court event must retry")
        world.execute(_nodes_field(event, "immediate"), "DMG")
        self.assertTrue(world.conditions(_nodes_field(final_option, "trigger"), "DMG"), "court retry trigger")
        world.execute(_actual_option_effect("ywc_dmg.1023", "confirm_royal"), "DMG")
        vars_ = world.countries["DMG"]
        self.assertEqual(vars_.get("ywc_dmg_court_outcome"), 1, vars_)
        self.assertEqual(vars_.get("ywc_dmg_court_provinces_outcome"), 1, vars_)
        self.assertEqual(vars_.get("ywc_v03_dmg_v03_dmg_court_provinces_settled"), 1)
        final = _generated_je("ywc_je_v03_dmg_court_charter_review")
        self.assertTrue(world.conditions(_nodes_field(final, "complete"), "DMG"))
        self.assertFalse(world.conditions(_nodes_field(final, "fail"), "DMG"))

    def test_actual_titles_je_paid_route_pulse_and_terminal_complete_one_route(self):
        world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "yearly_gross_income": 52000,
            "gold_reserves": 50000,
            "net_fixed_income": 0,
            "fixture_owned_state": 1,
            "fixture_land_law_ready": 1,
            "fixture_agriculture_employment": 1,
        }})
        je_id = "ywc_je_v03_dmg_land_titles_review"
        entry = _generated_je(je_id)
        self.assertTrue(world.conditions(_nodes_field(entry, "possible"), "DMG"))
        world.execute(_nodes_field(entry, "immediate"), "DMG")
        world.journals.append(("DMG", [("type", "=", je_id)]))
        pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
        route = (
            (1010, "unified_contract"),
            (1011, "contract_holders"),
            (1012, "local_joint_guarantee"),
            (1013, "pay_actual_cultivator"),
            (1014, "village_cosignature"),
            (1015, "confirm_contract"),
        )
        for index, (event_number, option_key) in enumerate(route):
            event_id = f"ywc_dmg.{event_number}"
            for _ in range(4):
                self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == je_id
                                    for tag, body in world.journals), "titles JE must be active before pulse")
                self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"))
                self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))
                world.execute(pulse, "DMG")
                if world.events:
                    break
                world.advance_months(1)
            self.assertEqual(world.events, [("DMG", event_id)], f"dispatch {event_id}")
            world.events.clear()
            event = _generated_event(event_id)
            self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"), f"event {event_id} trigger")
            world.execute(_nodes_field(event, "immediate"), "DMG")
            option = _actual_option(event_id, option_key)
            try:
                option_trigger = _nodes_field(option, "trigger")
            except StopIteration:
                option_trigger = None
            if option_trigger:
                self.assertTrue(world.conditions(option_trigger, "DMG"), f"{event_id}.{option_key} trigger")
            if index == len(route) - 1:
                # A genuine loss and default are pulsed after the real final
                # popup opens; neither the target nor the fiscal state may be
                # trusted from the earlier popup trigger.
                world.countries["DMG"]["fixture_agriculture_employment"] = 0
                world.countries["DMG"]["in_default"] = 1
                world.execute(pulse, "DMG")
                self.assertNotIn("ywc_dmg_titles_review_matured", world.countries["DMG"])
                self.assertFalse(world.conditions(option_trigger, "DMG"), "stale title target must close")
                world.execute(_actual_option_effect(event_id, option_key), "DMG")
                for key in ("ywc_dmg_titles_outcome", "ywc_dmg_two_land_titles_outcome",
                            "ywc_v03_dmg_v03_dmg_two_land_titles_settled"):
                    self.assertNotIn(key, world.countries["DMG"], f"stale close leaked {key}")
                self.assertNotIn("ywc_dmg_foundation_titles_contract", world.modifiers)
                world.countries["DMG"]["fixture_agriculture_employment"] = 1
                world.countries["DMG"]["in_default"] = 0
                world.execute(pulse, "DMG")
                self.assertEqual(world.countries["DMG"].get("ywc_dmg_titles_observation_started"), 1)
                self.assertNotIn("ywc_dmg_titles_review_matured", world.countries["DMG"])
                safe_wait = _actual_option(event_id, "renegotiate")
                self.assertTrue(world.conditions(_nodes_field(safe_wait, "trigger"), "DMG"),
                                "recovery popup must offer a safe fresh-review wait")
                world.execute(_actual_option_effect(event_id, "renegotiate"), "DMG")
                self.assertEqual(world.countries["DMG"].get("ywc_dmg_titles_pending_event"), 1015)
                self.assertNotIn("ywc_dmg_titles_outcome", world.countries["DMG"])
                world.events.clear()
                for _ in range(7):
                    self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == je_id
                                        for tag, body in world.journals), "titles JE stays active for fresh review")
                    self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"))
                    self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))
                    world.execute(pulse, "DMG")
                    if world.events:
                        break
                    world.advance_months(1)
                self.assertEqual(world.events, [("DMG", "ywc_dmg.1015")], "real retry node must return after a fresh watch")
                retry_event = _generated_event("ywc_dmg.1015")
                self.assertTrue(world.conditions(_nodes_field(retry_event, "trigger"), "DMG"))
                world.events.clear()
                world.execute(_nodes_field(retry_event, "immediate"), "DMG")
                self.assertTrue(world.conditions(option_trigger, "DMG"), "titles retry trigger")
                world.execute(_actual_option_effect(event_id, option_key), "DMG")
            else:
                world.execute(_actual_option_effect(event_id, option_key), "DMG")
        vars_ = world.countries["DMG"]
        self.assertEqual(vars_.get("ywc_dmg_titles_route"), 2)
        self.assertEqual(vars_.get("ywc_dmg_titles_registry_paid"), 1)
        self.assertEqual(vars_.get("ywc_dmg_titles_compensation_paid"), 1)
        self.assertEqual(vars_.get("ywc_dmg_titles_review_matured"), 1)
        self.assertEqual(vars_.get("ywc_dmg_titles_outcome"), 2)
        self.assertEqual(vars_.get("ywc_dmg_two_land_titles_outcome"), 2)
        self.assertEqual(vars_.get("ywc_v03_dmg_v03_dmg_two_land_titles_settled"), 1)
        self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))

    def test_actual_titles_je_paid_legacy_route_pulse_and_terminal_complete_second_route(self):
        world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "yearly_gross_income": 52000,
            "gold_reserves": 50000,
            "net_fixed_income": 0,
            "fixture_owned_state": 1,
            "fixture_land_law_ready": 1,
            "fixture_agriculture_employment": 1,
        }})
        je_id = "ywc_je_v03_dmg_land_titles_review"
        entry = _generated_je(je_id)
        self.assertTrue(world.conditions(_nodes_field(entry, "possible"), "DMG"))
        world.execute(_nodes_field(entry, "immediate"), "DMG")
        world.journals.append(("DMG", [("type", "=", je_id)]))
        pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
        route = ((1010, "old_boundary"), (1011, "old_register"),
                 (1012, "refuse_mortgage"), (1013, "old_boundary_limit"),
                 (1014, "old_roll_entry"), (1015, "confirm_legacy"))
        for event_number, option_key in route:
            event_id = f"ywc_dmg.{event_number}"
            for _ in range(12):
                self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == je_id for tag, body in world.journals))
                self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"))
                self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))
                world.execute(pulse, "DMG")
                if world.events:
                    break
                world.advance_months(1)
            self.assertEqual(world.events, [("DMG", event_id)], f"dispatch {event_id}")
            world.events.clear()
            event = _generated_event(event_id)
            self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"), event_id)
            world.execute(_nodes_field(event, "immediate"), "DMG")
            option = _actual_option(event_id, option_key)
            self.assertTrue(world.conditions(_nodes_field(option, "trigger"), "DMG"),
                            f"{event_id}.{option_key} trigger")
            world.execute(_actual_option_effect(event_id, option_key), "DMG")
        vars_ = world.countries["DMG"]
        self.assertEqual(vars_.get("ywc_dmg_titles_route"), 3)
        self.assertEqual(vars_.get("ywc_dmg_titles_registry_paid"), 1)
        self.assertEqual(vars_.get("ywc_dmg_titles_review_matured"), 1)
        self.assertEqual(vars_.get("ywc_dmg_titles_outcome"), 3)
        self.assertEqual(vars_.get("ywc_dmg_two_land_titles_outcome"), 3)
        self.assertEqual(vars_.get("ywc_v03_dmg_v03_dmg_two_land_titles_settled"), 1)
        self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))

    def test_actual_titles_legacy_target_36_notice_recovery_and_limited_terminal(self):
        world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "yearly_gross_income": 52000, "gold_reserves": 50000, "net_fixed_income": 0,
            "fixture_owned_state": 1, "fixture_land_law_ready": 1,
            "fixture_agriculture_employment": 1,
        }})
        je_id = "ywc_je_v03_dmg_land_titles_review"
        entry = _generated_je(je_id)
        self.assertTrue(world.conditions(_nodes_field(entry, "possible"), "DMG"))
        world.execute(_nodes_field(entry, "immediate"), "DMG")
        world.journals.append(("DMG", [("type", "=", je_id)]))
        pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
        for event_number, option_key in ((1010, "old_boundary"), (1011, "old_register"),
                                          (1012, "refuse_mortgage"), (1013, "old_boundary_limit"),
                                          (1014, "old_roll_entry")):
            event_id = f"ywc_dmg.{event_number}"
            for _ in range(12):
                self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == je_id
                                    for tag, body in world.journals))
                self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"))
                self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))
                world.execute(pulse, "DMG")
                if world.events:
                    break
                world.advance_months(1)
            self.assertEqual(world.events, [("DMG", event_id)])
            event = _generated_event(event_id)
            self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"))
            world.execute(_nodes_field(event, "immediate"), "DMG")
            option = _actual_option(event_id, option_key)
            self.assertTrue(world.conditions(_nodes_field(option, "trigger"), "DMG"))
            world.execute(_actual_option_effect(event_id, option_key), "DMG")
            world.events.clear()

        # Open the actual final review, then lose fiscal eligibility before
        # selecting the previously legal terminal effect.
        for _ in range(12):
            self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"))
            self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))
            world.execute(pulse, "DMG")
            if world.events:
                break
            world.advance_months(1)
        self.assertEqual(world.events, [("DMG", "ywc_dmg.1015")])
        event = _generated_event("ywc_dmg.1015")
        self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"))
        world.execute(_nodes_field(event, "immediate"), "DMG")
        confirm = _actual_option("ywc_dmg.1015", "confirm_legacy")
        self.assertTrue(world.conditions(_nodes_field(confirm, "trigger"), "DMG"))
        world.countries["DMG"]["in_default"] = 1
        world.execute(pulse, "DMG")
        self.assertNotIn("ywc_dmg_titles_review_matured", world.countries["DMG"])
        self.assertFalse(world.conditions(_nodes_field(confirm, "trigger"), "DMG"))
        world.execute(_actual_option_effect("ywc_dmg.1015", "confirm_legacy"), "DMG")
        for key in ("ywc_dmg_titles_outcome", "ywc_dmg_two_land_titles_outcome",
                    "ywc_v03_dmg_v03_dmg_two_land_titles_settled"):
            self.assertNotIn(key, world.countries["DMG"], f"stale title close leaked {key}")
        world.events.clear()

        elapsed_months = 0
        delivered_36 = False
        for _ in range(44):
            self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == je_id
                                for tag, body in world.journals))
            self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"))
            self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))
            world.execute(pulse, "DMG")
            if world.events:
                event = _generated_event("ywc_dmg.1015")
                self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"))
                world.execute(_nodes_field(event, "immediate"), "DMG")
                vars_ = world.countries["DMG"]
                if vars_.get("ywc_dmg_titles_blocked_36_delivered"):
                    delivered_36 = True
                    self.assertGreaterEqual(elapsed_months, 36)
                    limited = _actual_option("ywc_dmg.1015", "limited_settlement")
                    self.assertFalse(world.conditions(_nodes_field(limited, "trigger"), "DMG"))
                else:
                    self.assertEqual(vars_.get("ywc_dmg_titles_blocked_12_delivered"), 1)
                    limited = _actual_option("ywc_dmg.1015", "limited_settlement")
                    self.assertFalse(world.conditions(_nodes_field(limited, "trigger"), "DMG"))
                renegotiate = _actual_option("ywc_dmg.1015", "renegotiate")
                self.assertTrue(world.conditions(_nodes_field(renegotiate, "trigger"), "DMG"))
                world.execute(_actual_option_effect("ywc_dmg.1015", "renegotiate"), "DMG")
                if vars_.get("ywc_dmg_titles_blocked_12_delivered"):
                    self.assertEqual(vars_.get("ywc_dmg_titles_lower_target_proposed"), 1)
                world.events.clear()
            world.advance_months(1)
            elapsed_months += 1
            if delivered_36:
                break
        self.assertTrue(delivered_36, f"36-month title notice not delivered; elapsed={elapsed_months}")
        self.assertLessEqual(elapsed_months, 40)
        vars_ = world.countries["DMG"]
        self.assertEqual(vars_.get("ywc_dmg_titles_route"), 3)
        self.assertEqual(vars_.get("ywc_dmg_titles_registry_paid"), 1)
        self.assertEqual(vars_.get("ywc_dmg_titles_newcomer_mode"), 3)
        self.assertEqual(vars_.get("ywc_dmg_titles_lower_target_selected"), 1)
        self.assertEqual(vars_.get("ywc_dmg_titles_lower_target_proposed"), 1)

        vars_["in_default"] = 0
        world.execute(pulse, "DMG")
        self.assertEqual(vars_.get("ywc_dmg_titles_observation_started"), 1)
        self.assertNotIn("ywc_dmg_titles_review_matured", vars_)
        self.assertEqual(vars_.get("ywc_dmg_titles_blocked_36_delivered"), 1)
        for _ in range(7):
            self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"))
            self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))
            world.execute(pulse, "DMG")
            if vars_.get("ywc_dmg_titles_review_matured"):
                break
            world.advance_months(1)
        self.assertEqual(vars_.get("ywc_dmg_titles_review_matured"), 1)
        for _ in range(4):
            world.execute(pulse, "DMG")
            if world.events:
                break
            world.advance_months(1)
        self.assertEqual(world.events, [("DMG", "ywc_dmg.1015")])
        event = _generated_event("ywc_dmg.1015")
        self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"))
        world.execute(_nodes_field(event, "immediate"), "DMG")
        limited = _actual_option("ywc_dmg.1015", "limited_settlement")
        self.assertTrue(world.conditions(_nodes_field(limited, "trigger"), "DMG"))
        world.execute(_actual_option_effect("ywc_dmg.1015", "limited_settlement"), "DMG")
        self.assertEqual(vars_.get("ywc_dmg_titles_outcome"), 4)
        self.assertEqual(vars_.get("ywc_dmg_two_land_titles_outcome"), 4)
        self.assertEqual(vars_.get("ywc_v03_dmg_v03_dmg_two_land_titles_settled"), 1)
        self.assertTrue(world.conditions(_nodes_field(entry, "complete"), "DMG"))
        self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))

    def test_actual_court_je_paid_joint_route_and_terminal_complete_second_route(self):
        world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "yearly_gross_income": 52000,
            "gold_reserves": 50000,
            "net_fixed_income": 0,
            "fixture_owned_state": 1,
            "fixture_government_appointment_ready": 1,
            "fixture_landowner_interest_group": 1,
        }})
        je_id = "ywc_je_v03_dmg_court_appointment"
        entry = _generated_je(je_id)
        self.assertTrue(world.conditions(_nodes_field(entry, "possible"), "DMG"))
        world.execute(_nodes_field(entry, "immediate"), "DMG")
        world.journals.append(("DMG", [("type", "=", je_id)]))
        plan = (
            (je_id, "ywc_dmg.1016", "joint_appointment"),
            (je_id, "ywc_dmg.1017", "central_audit_pays"),
            ("ywc_je_v03_dmg_court_budget", "ywc_dmg.1018", "authorize_staffed"),
            ("ywc_je_v03_dmg_court_budget", "ywc_dmg.1019", "time_limited_amendment"),
            ("ywc_je_v03_dmg_court_budget", "ywc_dmg.1020", "office_charter_cosign"),
            ("ywc_je_v03_dmg_court_budget", "ywc_dmg.1021", "court_keeps_control"),
            ("ywc_je_v03_dmg_court_charter_review", "ywc_dmg.1022", "confirm_signed_terms"),
        )
        current_je = je_id
        for next_je, event_id, option_key in plan:
            if next_je != current_je:
                world.journals = [(tag, body) for tag, body in world.journals
                                  if dict((k, v) for k, _, v in body).get("type") != current_je]
                next_entry = _generated_je(next_je)
                self.assertTrue(world.conditions(_nodes_field(next_entry, "possible"), "DMG"), next_je)
                self.assertTrue(world.conditions(_nodes_field(_generated_je(current_je), "complete"), "DMG"), current_je)
                current_je = next_je
                world.execute(_nodes_field(_generated_je(current_je), "immediate"), "DMG")
                world.journals.append(("DMG", [("type", "=", current_je)]))
            pulse = _nodes_field(_nodes_field(_generated_je(current_je), "on_monthly_pulse"), "effect")
            for _ in range(12):
                self.assertTrue(any(tag == "DMG" and dict((k, v) for k, _, v in body).get("type") == current_je
                                    for tag, body in world.journals), f"{current_je} active before pulse")
                self.assertFalse(world.conditions(_nodes_field(_generated_je(current_je), "complete"), "DMG"))
                self.assertFalse(world.conditions(_nodes_field(_generated_je(current_je), "fail"), "DMG"))
                world.execute(pulse, "DMG")
                if world.events and world.events[-1][1] == event_id:
                    break
                if world.events:
                    self.assertIn(world.events[-1][1], ("ywc_dmg.1016", "ywc_dmg.1018"), world.events)
                    _consume_court_priority_notice(world)
                world.advance_months(1)
            self.assertEqual(world.events, [("DMG", event_id)], f"{event_id}: vars={world.countries['DMG']} timers={world.days_until_expiry}")
            world.events.clear()
            event = _generated_event(event_id)
            world.execute(_nodes_field(event, "immediate"), "DMG")
            option = _actual_option(event_id, option_key)
            self.assertTrue(world.conditions(_nodes_field(option, "trigger"), "DMG"), option_key)
            world.execute(_actual_option_effect(event_id, option_key), "DMG")
        final_je = "ywc_je_v03_dmg_court_charter_review"
        entry = _generated_je(final_je)
        pulse = _nodes_field(_nodes_field(entry, "on_monthly_pulse"), "effect")
        for _ in range(10):
            world.execute(pulse, "DMG")
            if world.events:
                break
            world.advance_months(1)
        self.assertEqual(world.events, [("DMG", "ywc_dmg.1023")])
        event = _generated_event("ywc_dmg.1023")
        world.execute(_nodes_field(event, "immediate"), "DMG")
        option = _actual_option("ywc_dmg.1023", "confirm_joint")
        self.assertTrue(world.conditions(_nodes_field(option, "trigger"), "DMG"))
        world.countries["DMG"]["in_default"] = 1
        self.assertFalse(world.conditions(_nodes_field(option, "trigger"), "DMG"),
                         "a real default after popup delivery must invalidate the selected success")
        world.execute(pulse, "DMG")
        self.assertNotIn("ywc_dmg_court_review_matured", world.countries["DMG"])
        world.execute(_actual_option_effect("ywc_dmg.1023", "confirm_joint"), "DMG")
        vars_ = world.countries["DMG"]
        for key in ("ywc_dmg_court_outcome", "ywc_dmg_court_provinces_outcome",
                    "ywc_v03_dmg_v03_dmg_court_provinces_settled"):
            self.assertNotIn(key, vars_, f"stale terminal effect leaked {key}")
        self.assertFalse(any(fields.get("modifier", "").startswith("ywc_dmg_foundation_court_")
                             for tag, fields in world.modifiers if tag == "DMG"))
        self.assertEqual(vars_.get("ywc_v03_active_arc_count"), 1)
        self.assertEqual(vars_.get("ywc_v03_visible_task_count"), 1)
        world.countries["DMG"]["in_default"] = 0
        world.execute(pulse, "DMG")
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_observation_started"), 1)
        safe_wait = _actual_option("ywc_dmg.1023", "renegotiate")
        self.assertTrue(world.conditions(_nodes_field(safe_wait, "trigger"), "DMG"))
        world.execute(_actual_option_effect("ywc_dmg.1023", "renegotiate"), "DMG")
        world.events.clear()
        for _ in range(11):
            self.assertFalse(world.conditions(_nodes_field(entry, "complete"), "DMG"))
            self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))
            world.execute(pulse, "DMG")
            if world.countries["DMG"].get("ywc_dmg_court_review_matured"):
                break
            world.advance_months(1)
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_court_review_matured"), 1)
        for _ in range(4):
            world.execute(pulse, "DMG")
            if world.events:
                break
            world.advance_months(1)
        self.assertEqual(world.events, [("DMG", "ywc_dmg.1023")])
        event = _generated_event("ywc_dmg.1023")
        self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"))
        world.execute(_nodes_field(event, "immediate"), "DMG")
        option = _actual_option("ywc_dmg.1023", "confirm_joint")
        self.assertTrue(world.conditions(_nodes_field(option, "trigger"), "DMG"))
        world.execute(_actual_option_effect("ywc_dmg.1023", "confirm_joint"), "DMG")
        vars_ = world.countries["DMG"]
        self.assertEqual(vars_.get("ywc_dmg_court_route"), 2)
        self.assertEqual(vars_.get("ywc_dmg_court_outcome"), 2)
        self.assertEqual(vars_.get("ywc_dmg_court_provinces_outcome"), 2)
        self.assertEqual(vars_.get("ywc_v03_dmg_v03_dmg_court_provinces_settled"), 1)
        self.assertTrue(world.conditions(_nodes_field(entry, "complete"), "DMG"))
        self.assertFalse(world.conditions(_nodes_field(entry, "fail"), "DMG"))

    def test_actual_route_closers_produce_distinct_success_and_limited_terminals(self):
        routes = (
            ("ywc_dmg_foundation_close_titles", "ywc_dmg_titles", "titles"),
            ("ywc_dmg_foundation_close_court", "ywc_dmg_court", "court"),
        )
        for helper, prefix, route_name in routes:
            route_paid = {
                "titles": {1: "ywc_dmg_titles_compensation_paid", 2: "ywc_dmg_titles_registry_paid", 3: None},
                "court": {1: "ywc_dmg_court_charter_paid", 2: "ywc_dmg_court_charter_paid", 3: "ywc_dmg_court_charter_paid"},
            }[route_name]
            for route, outcome in ((1, 1), (2, 2), (3, 3)):
                vars_ = {
                    "ywc_v03_dmg_v03_dmg_two_land_titles_started" if route_name == "titles" else "ywc_v03_dmg_v03_dmg_court_provinces_started": 1,
                    "ywc_v03_active_arc_count": 1,
                    "ywc_v03_visible_task_count": 1,
                    f"{prefix}_review_matured": 1,
                    f"{prefix}_route_ready": 1,
                    f"{prefix}_route": route,
                    "net_fixed_income": 0,
                }
                paid = route_paid[route]
                if paid:
                    vars_[paid] = 1
                if route_name == "court":
                    vars_["ywc_dmg_court_budget_paid"] = 1
                    vars_["fixture_government_appointment_ready"] = 1
                    if route == 2:
                        vars_["ywc_dmg_joint_appointment_clause"] = 1
                    elif route == 3:
                        vars_["fixture_secondary_office_ready"] = 1
                        vars_["fixture_agriculture_employment"] = 1
                else:
                    vars_["ywc_dmg_titles_registry_paid"] = 1
                    vars_["fixture_land_law_ready"] = 1
                    vars_["fixture_agriculture_employment"] = 1
                    if route == 1:
                        vars_["fixture_secondary_office_ready"] = 1
                world = DmgWorld(EFFECTS, {"DMG": vars_})
                world.run(helper, "DMG")
                self.assertEqual(world.countries["DMG"].get(f"{prefix}_outcome"), outcome)

            world = DmgWorld(EFFECTS, {"DMG": {
                "ywc_v03_dmg_v03_dmg_two_land_titles_started" if route_name == "titles" else "ywc_v03_dmg_v03_dmg_court_provinces_started": 1,
                "ywc_v03_active_arc_count": 1,
                "ywc_v03_visible_task_count": 1,
                f"{prefix}_blocked_12_delivered": 1,
            }})
            world.run("ywc_dmg_foundation_limit_titles" if route_name == "titles" else "ywc_dmg_foundation_limit_court", "DMG")
            self.assertNotIn(f"{prefix}_outcome", world.countries["DMG"])
            self.assertNotIn("ywc_v03_dmg_v03_dmg_two_land_titles_settled" if route_name == "titles" else "ywc_v03_dmg_v03_dmg_court_provinces_settled", world.countries["DMG"])

            qualified = {
                "ywc_v03_dmg_v03_dmg_two_land_titles_started" if route_name == "titles" else "ywc_v03_dmg_v03_dmg_court_provinces_started": 1,
                "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1,
                f"{prefix}_blocked_36_delivered": 1, f"{prefix}_lower_target_proposed": 1,
                f"{prefix}_review_matured": 1, f"{prefix}_route_ready": 1, f"{prefix}_route": 3,
                "net_fixed_income": 0, "fixture_land_law_ready": 1, "fixture_agriculture_employment": 1,
            }
            if route_name == "titles":
                qualified.update({"ywc_dmg_titles_registry_paid": 1, "ywc_dmg_titles_lower_target_selected": 1,
                                  "ywc_dmg_titles_newcomer_mode": 3})
            else:
                qualified.update({"ywc_dmg_court_charter_paid": 1, "ywc_dmg_court_budget_paid": 1,
                                  "ywc_dmg_court_representation": 3, "ywc_dmg_court_defence_veto": 3,
                                  "ywc_dmg_court_lower_target_selected": 1, "fixture_secondary_office_ready": 1})
            world = DmgWorld(EFFECTS + "\n" + SHARED_EFFECTS, {"DMG": qualified})
            world.run("ywc_dmg_foundation_limit_titles" if route_name == "titles" else "ywc_dmg_foundation_limit_court", "DMG")
            self.assertEqual(world.countries["DMG"].get(f"{prefix}_outcome"), 4,
                             f"{route_name} limited completion needs paid, selected, implemented route and a fresh mature review: {world.countries['DMG']}")
            alias = "ywc_dmg_two_land_titles_outcome" if route_name == "titles" else "ywc_dmg_court_provinces_outcome"
            self.assertEqual(world.countries["DMG"].get(alias), 4)

            world = DmgWorld(EFFECTS, {"DMG": {
                "ywc_v03_dmg_v03_dmg_two_land_titles_started" if route_name == "titles" else "ywc_v03_dmg_v03_dmg_court_provinces_started": 1,
                "ywc_v03_active_arc_count": 1,
                "ywc_v03_visible_task_count": 1,
            }})
            world.run("ywc_dmg_foundation_withdraw_titles" if route_name == "titles" else "ywc_dmg_foundation_withdraw_court", "DMG")
            self.assertEqual(world.countries["DMG"].get(f"{prefix}_outcome"), 5)
            self.assertEqual(world.countries["DMG"].get(f"{prefix}_withdraw_requested"), 1)


if __name__ == "__main__":
    unittest.main()
