"""Actual generated-source scenarios for SHU's first middle arc."""
import copy
import json
from pathlib import Path
import unittest

from shu_kor_strict_review_runtime import facts, field
from shu_provincial_runtime import ProvincialWorld

ROOT = Path(__file__).resolve().parents[1]
SLUG = "v03_shu_provincial_contract"
JES = ("ywc_je_v03_shu_provincial_charter", "ywc_je_v03_shu_provincial_ledger")


def middle_arc(catalog):
    return next(arc for arc in catalog["arcs"] if arc["slug"] == SLUG)


def bare_facts():
    state = facts()
    state["institutions"] = {}
    state["laws"] = ["law_tenant_farmers"]
    for province in state["states"]:
        province["buildings"] = [b for b in province["buildings"] if b["type"] != "building_university"]
        for building in province["buildings"]:
            if building["type"] == "building_government_administration":
                building["occupancy"] = 0.25
    return state


def new_world(bare=False):
    world = ProvincialWorld("shu")
    world.countries[world.tag] = bare_facts() if bare else facts()
    return world


def option_nodes(event, key):
    return next(value for name, _, value in event
                if name == "option" and field(value, "name").endswith("." + key))


def option_legal(world, event, key):
    return world.conditions(field(option_nodes(event, key), "trigger"), world.tag)


def _option_effect(nodes):
    result = []
    for node in nodes:
        key, _, value = node
        if key == "custom_tooltip":
            result.extend(child for child in value if child[0] != "text")
        elif key not in ("name", "trigger", "ai_chance"):
            result.append(node)
    return result


def force_option(world, event, key):
    world.execute(_option_effect(option_nodes(event, key)), world.tag)


def choose(world, arc, event, key):
    assert option_legal(world, event, key), ("illegal_option", key)
    force_option(world, event, key)
    world.refresh(arc)


def play(world, arc, number, key):
    event = world.deliver(arc, f"ywc_shu.{number}")
    choose(world, arc, event, key)
    return event


def month(world, arc, count=1):
    for _ in range(count):
        world.advance_months(1)
        world.elapsed_months += 1
        world.pulse(arc)


def ready_for_review(world, route="central"):
    arc = middle_arc(world.cat)
    play(world, arc, 1100, "pilot_sichuan")
    play(world, arc, 1101, {"central": "central_funding", "shared": "provincial_funding",
                          "legacy": "keep_old_office"}[route])
    play(world, arc, 1102, {"central": "pay_relief_once", "shared": "provincial_self_raise",
                          "legacy": "push_old_quota"}[route])
    play(world, arc, {"central": 1103, "shared": 1104, "legacy": 1105}[route],
         {"central": "establish_central", "shared": "write_share_terms",
          "legacy": "confirm_old_quota"}[route])
    assert world.history[world.tag][JES[0]] == "complete"
    assert JES[1] in world.active[world.tag]
    return arc


def finish_review(world, arc, outcome=1):
    play(world, arc, 1106, "settle_on_time")
    play(world, arc, 1107, "close_established" if outcome == 1 else "close_compromise")


class ShuProvincialContractMiddle(unittest.TestCase):
    def test_registered_content_keeps_all_foundation_events_and_has_no_calendar_force(self):
        world = new_world()
        arc = middle_arc(world.cat)
        self.assertEqual(arc["era"], "middle")
        self.assertEqual(arc["depends_on"], [])
        self.assertEqual([j["id"] for j in arc["journals"]], list(JES))
        self.assertEqual({e["id"] for e in arc["events"]},
                         {f"ywc_shu.{n}" for n in range(1100, 1108)})
        self.assertNotIn("PENDING_ROOT", json.dumps(arc))
        for journal in arc["journals"]:
            self.assertNotRegex(journal["script"], r"\bdate\s*[<>=]")
        self.assertEqual(len([a for a in world.cat["arcs"] if a["era"] == "foundation"]), 3)
        self.assertTrue({f"ywc_shu.{n}" for n in range(1000, 1026)} <= set(world.event_defs))

    def test_three_routes_use_distinct_real_resources_and_close_both_journals(self):
        for route, charge, outcome in (("central", 2000, 1), ("shared", 500, 2), ("legacy", 0, 2)):
            with self.subTest(route=route):
                world = new_world(bare=route != "central")
                state = world.countries[world.tag]
                original_facts = copy.deepcopy((state["laws"], state["institutions"], state["states"]))
                before = world.treasury[world.tag]
                arc = ready_for_review(world, route)
                self.assertEqual(state["ywc_v03_active_arc_count"], 1)
                self.assertEqual(state["ywc_v03_visible_task_count"], 1)
                self.assertEqual(world.treasury[world.tag] - before, -charge)
                month(world, arc, 6)
                finish_review(world, arc, outcome)
                self.assertEqual(state["ywc_shu_prov_outcome"], outcome)
                self.assertEqual(state["ywc_v03_active_arc_count"], 0)
                self.assertEqual(state["ywc_v03_visible_task_count"], 0)
                self.assertEqual([world.history[world.tag][j] for j in JES],
                                 ["complete", "complete"])
                self.assertEqual(world.treasury[world.tag] - before, -charge)
                self.assertEqual((state["laws"], state["institutions"], state["states"]), original_facts)

    def test_five_months_are_immature_sixth_matures_and_same_day_does_not_double_count(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        for i in range(1, 6):
            month(world, arc)
            self.assertEqual(state["ywc_shu_prov_review_streak"], i)
            self.assertNotIn("ywc_shu_prov_review_mature", state)
            world.pulse(arc)
            self.assertEqual(state["ywc_shu_prov_review_streak"], i)
            self.assertFalse(world.events)
        month(world, arc)
        self.assertEqual(state["ywc_shu_prov_review_streak"], 6)
        self.assertEqual(state["ywc_shu_prov_review_mature"], 1)
        self.assertEqual(state["ywc_shu_prov_pending_event"], 1106)
        # Source preparation precedes the native counter update. A subsequent
        # opportunity can dispatch the ready queue without another month counted.
        world.pulse(arc)
        self.assertEqual(state["ywc_shu_prov_review_streak"], 6)
        self.assertEqual([event for _, event in world.events], ["ywc_shu.1106"])

    def test_callback_on_ledger_creation_day_is_not_a_first_observation_month(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_shu_prov_review_streak"], 0)
        world.pulse(arc)
        self.assertEqual(state["ywc_shu_prov_review_streak"], 0)
        month(world, arc, 5)
        self.assertEqual(state["ywc_shu_prov_review_streak"], 5)
        self.assertNotIn("ywc_shu_prov_review_mature", state)
        month(world, arc)
        self.assertEqual(state["ywc_shu_prov_review_streak"], 6)

    def test_war_or_lost_pilot_requires_explicit_deferral_and_six_fresh_months(self):
        for fault in ("war", "lost_pilot"):
            with self.subTest(fault=fault):
                world = new_world()
                arc = ready_for_review(world)
                state = world.countries[world.tag]
                before = world.treasury[world.tag]
                month(world, arc, 2)
                if fault == "war":
                    state["is_at_war"] = True
                else:
                    state["states"][0]["owned"] = False
                month(world, arc)
                self.assertEqual(state["ywc_shu_prov_review_streak"], 0)
                self.assertNotIn("ywc_shu_prov_review_mature", state)
                event = world.deliver(arc, "ywc_shu.1106")
                self.assertFalse(option_legal(world, event, "settle_on_time"))
                state["is_at_war"] = False
                state["states"][0]["owned"] = True
                choose(world, arc, event, "defer_no_fee")
                self.assertNotIn("ywc_shu_prov_review_interrupted", state)
                self.assertEqual(state["ywc_shu_prov_review_streak"], 0)
                for i in range(1, 6):
                    month(world, arc)
                    self.assertEqual(state["ywc_shu_prov_review_streak"], i)
                    self.assertNotIn("ywc_shu_prov_review_mature", state)
                month(world, arc)
                finish_review(world, arc)
                self.assertEqual(state["ywc_shu_prov_outcome"], 1)
                self.assertEqual(world.treasury[world.tag], before)

    def test_current_cash_and_stale_effects_cannot_charge_or_advance(self):
        world = new_world()
        arc = middle_arc(world.cat)
        state = world.countries[world.tag]
        play(world, arc, 1100, "pilot_sichuan")
        school = world.deliver(arc, "ywc_shu.1101")
        state["gold_reserves"] = -world.treasury[world.tag]
        queue = state.get("ywc_shu_prov_pending_event")
        self.assertFalse(option_legal(world, school, "central_funding"))
        force_option(world, school, "central_funding")
        self.assertEqual(world.treasury[world.tag], 0)
        self.assertEqual(state["ywc_shu_prov_stage"], 1101)
        self.assertEqual(state.get("ywc_shu_prov_pending_event"), queue)
        state["gold_reserves"] = 100000
        choose(world, arc, school, "central_funding")
        relief = play(world, arc, 1102, "pay_relief_once")
        before = copy.deepcopy(state)
        treasury = world.treasury[world.tag]
        force_option(world, school, "central_funding")
        force_option(world, relief, "pay_relief_once")
        self.assertEqual(state, before)
        self.assertEqual(world.treasury[world.tag], treasury)
        self.assertEqual(treasury, -2000)

    def test_late_condition_loss_offers_honest_setback_and_old_review_cannot_overwrite(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        month(world, arc, 6)
        old_review = play(world, arc, 1106, "settle_on_time")
        before = copy.deepcopy(state)
        force_option(world, old_review, "defer_no_fee")
        self.assertEqual(state, before)
        state["states"][0]["owned"] = False
        ending = world.deliver(arc, "ywc_shu.1107")
        self.assertFalse(option_legal(world, ending, "close_established"))
        before = copy.deepcopy(state)
        force_option(world, ending, "close_established")
        self.assertEqual(state, before)
        choose(world, arc, ending, "close_setback")
        self.assertEqual(state["ywc_shu_prov_outcome"], 3)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(world.treasury[world.tag], -2000)

    def test_capacity_full_does_not_open_or_claim_a_fourth_arc(self):
        world = new_world()
        state = world.countries[world.tag]
        state["ywc_v03_active_arc_count"] = 3
        state["ywc_v03_visible_task_count"] = 6
        world.run("ywc_v03_claim_arc_shu_v03_shu_provincial_contract")
        world.run("ywc_shu_open_provincial_ledger_once")
        self.assertNotIn("ywc_v03_shu_v03_shu_provincial_contract_started", state)
        self.assertNotIn("ywc_shu_prov_stage", state)
        self.assertNotIn("ywc_shu_prov_ledger_open", state)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 6))

    def test_withdrawal_fails_active_journal_and_repeated_release_is_a_noop(self):
        world = new_world()
        arc = middle_arc(world.cat)
        state = world.countries[world.tag]
        play(world, arc, 1100, "pilot_sichuan")
        world.run("ywc_shu_prov_close_withdrawn")
        world.refresh(arc)
        self.assertEqual(world.history[world.tag][JES[0]], "failed")
        self.assertEqual(state["ywc_shu_prov_outcome"], 4)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
        before = copy.deepcopy(state)
        world.run("ywc_shu_prov_close_withdrawn")
        self.assertEqual(state, before)
        self.assertEqual(world.treasury[world.tag], 0)

    def test_unrest_reads_the_selected_state_and_rejects_a_country_scope_query(self):
        world = new_world()
        arc = middle_arc(world.cat)
        state = world.countries[world.tag]
        other = copy.deepcopy(state["states"][0])
        other["region"] = "s:STATE_CHONGQING"
        other["turmoil"] = 0.4
        state["states"].append(other)
        state["states"][0]["turmoil"] = 0.14
        play(world, arc, 1100, "pilot_sichuan")
        query = world.trigger_defs["ywc_shu_v03_prov_unrest_present"]
        self.assertFalse(world.conditions(query, world.tag))
        state["states"][0]["turmoil"] = 0.16
        self.assertTrue(world.conditions(query, world.tag))
        with self.assertRaisesRegex(AssertionError, "turmoil_outside_state_scope"):
            world.condition(("turmoil", ">", "0.15"), world.tag)
