"""Actual generated LAN beyond-gold source with concrete production facts.

Offline only: these tests execute the shipped Clausewitz helpers through the
strict harness. They are written here but not run in this workspace (no shell).
"""
import copy
import json
from pathlib import Path
import unittest

from clausewitz_harness import parse
from kor_partner_protocol_runtime import StateRef
from lan_gold_runtime import LanGoldWorld
from shu_kor_strict_review_runtime import facts, field
from test_v03_shu_provincial_contract import _option_effect, option_nodes, option_legal as _option_legal

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/content/v03/countries/lan.json"
SLUG = "v03_lan_beyond_gold"
JES = ("ywc_je_v03_lan_gold_livelihood", "ywc_je_v03_lan_gold_share_future")
P = "ywc_lan_gold_"
ROUTES = {"processing": "route_processing", "farming": "route_farming",
          "monopoly": "route_monopoly"}
ROUTE_VALUE = {"processing": 1, "farming": 2, "monopoly": 3}
# U = 1000 weekly envelope (52000 / 52). Seed = 1000, or 500 with either source.
# Basis: processing 1000 (750 with leverage), farming 500, monopoly 500 (250
# with precedent). These are the real per-route rates the source applies.
SEED = {"base": 1000, "source": 500}
BASIS = {
    "processing": 1000,
    "farming": 500,
    "monopoly": 500,
}
BASIS_LEVERAGE_PROCESSING = 750
BASIS_PRECEDENT_MONOPOLY = 250


def catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def gold_arc():
    return next(arc for arc in catalog()["arcs"] if arc["slug"] == SLUG)


def force_option(world, event, key):
    nodes = [node for node in _option_effect(option_nodes(event, key))
             if node[0] != "default_option"]
    with world.popup_context(event):
        world.execute(nodes, world.tag)


def option_legal(world, event, key):
    with world.popup_context(event):
        return _option_legal(world, event, key)


def choose(world, arc, event, key):
    assert option_legal(world, event, key), ("illegal_option", key)
    force_option(world, event, key)
    world.refresh(arc)


def _base_state(budget=100000):
    state = facts()
    state["yearly_gross_income"] = 52000  # 1000 / week
    state["gold_reserves"] = budget
    state["country_has_voting_franchise"] = True
    return state


def new_world(route="processing", bare=False, source=False, budget=100000,
              extra_state=None):
    state = _base_state(budget)
    province = state["states"][0]
    province.update(owner="LAN", region="s:STATE_WEST_BORNEO")
    for building in province["buildings"]:
        building["level"] = 2 if building["type"] == "building_government_administration" else 1
    gold = {"type": "building_gold_mine", "groups": ["bg_mining"], "level": 3,
            "occupancy": .75, "shortage": False}
    food = {"type": "building_food_industry", "groups": ["bg_manufacturing"], "level": 2,
            "occupancy": .8, "shortage": False}
    rice = {"type": "building_rice_farm", "groups": ["bg_agriculture"], "level": 2,
            "occupancy": .7, "shortage": False}
    province["buildings"].extend((gold, food, rice))
    laborer = copy.deepcopy(province["pops"][0])
    laborer.update(type="laborers", employed=True, workplace=gold)
    machinist = copy.deepcopy(province["pops"][0])
    machinist.update(type="machinists", employed=True, workplace=food)
    farmer = copy.deepcopy(province["pops"][0])
    farmer.update(type="farmers", employed=True, workplace=rice)
    province["pops"].extend((laborer, machinist, farmer))
    state["igs"] = [
        {"type": kind, "clout": clout, "in_government": True, "approval": 2}
        for kind, clout in (
            ("ig_industrialists", .20), ("ig_petty_bourgeoisie", .15),
            ("ig_rural_folk", .15), ("ig_intelligentsia", .15),
            ("ig_trade_unions", .15), ("ig_landowners", .08))
    ]
    if bare:
        province["buildings"] = [b for b in province["buildings"]
                                 if b["type"] == "building_government_administration"]
        province["pops"] = [province["pops"][0]]
        province["pops"][0]["workplace"] = province["buildings"][0]
    states = [state["states"][0]]
    if extra_state is not None:
        # A second owned West Borneo state placed after the captured pilot; it
        # must never satisfy the pilot-scoped sector checks.
        states.append(extra_state)
        state["states"] = states
    countries = {"LAN": state, "DEI": facts()}
    world = LanGoldWorld(tag="lan", countries=countries)
    world.run("ywc_v03_initialize_country", world.tag)
    if source == "precedent":
        _mark_mine_precedent(state)
    elif source == "leverage":
        _mark_public_leverage(state)
    elif source:
        _mark_mine_precedent(state)
    return world


def _mark_mine_precedent(state):
    state["ywc_v03_lan_v03_lan_mine_accounts_started"] = 1
    state["ywc_v03_lan_v03_lan_mine_accounts_settled"] = 1
    state["ywc_v03_lan_v03_lan_mine_accounts_outcome"] = 1
    state["ywc_lan_mine_established"] = 1
    state["ywc_lan_mine_settled"] = 1
    state["ywc_lan_mine_route"] = 1
    state["ywc_lan_mine_filing_fee_paid"] = 1
    state["ywc_lan_mine_reserve_paid"] = 1
    state["ywc_lan_mine_public_share_taken"] = 1


def _mark_public_leverage(state):
    state["ywc_v03_lan_v03_lan_company_public_started"] = 1
    state["ywc_v03_lan_v03_lan_company_public_settled"] = 1
    state["ywc_v03_lan_v03_lan_company_public_outcome"] = 1
    state["ywc_lan_public_outcome"] = 1
    state["ywc_lan_public_mode"] = 1
    state["ywc_lan_public_charter_paid"] = 1
    state["ywc_lan_public_review_paid"] = 1
    state["ywc_lan_public_charter_paid_amount"] = 500
    state["ywc_lan_public_review_paid_amount"] = 500


def play(world, arc, number, key):
    event = world.deliver(arc, f"ywc_lan.{number}")
    choose(world, arc, event, key)
    return event


def month(world, arc, count=1):
    for _ in range(count):
        world.advance_months(1)
        world.elapsed_months += 1
        world.pulse(arc)


def review_then_finish_event(world, arc):
    # Maturity queues 1125; the real review must be acknowledged before 1126.
    review = world.deliver(arc, 'ywc_lan.1125')
    choose(world, arc, review, 'settle_matured')
    return world.deliver(arc, 'ywc_lan.1126')


def reach_review(world, route="processing", bounded=False, source=False):
    arc = gold_arc()
    world.refresh(arc)
    play(world, arc, 1120, "pay_seed")
    play(world, arc, 1121, ROUTES[route])
    if bounded:
        play(world, arc, 1122, "narrow_basis")
    else:
        play(world, arc, 1122, "pay_basis")
    if bounded:
        play(world, arc, 1123, "name_gap")
    else:
        play(world, arc, 1123, "name_full")
    play(world, arc, 1124, "start_audit")
    return arc


class LanBeyondGold(unittest.TestCase):
    def test_arc_shape_two_journals_eight_events(self):
        arc = gold_arc()
        self.assertEqual([j["id"] for j in arc["journals"]], list(JES))
        self.assertEqual({e["id"] for e in arc["events"]},
                         {f"ywc_lan.{n}" for n in range(1120, 1128)})

    def test_old_popup_cannot_withdraw_after_same_event_is_redelivered(self):
        world = new_world()
        arc = gold_arc()
        world.refresh(arc)
        old = world.deliver(arc, 'ywc_lan.1120')
        choose(world, arc, old, 'wait_seed')
        current = world.deliver(arc, 'ywc_lan.1120')
        self.assertNotEqual(old.saved['ywc_lan_gold_popup_epoch'], current.saved['ywc_lan_gold_popup_epoch'])
        state = world.countries[world.tag]
        before = world.treasury[world.tag]
        force_option(world, old, 'pay_seed')
        self.assertEqual(world.treasury[world.tag], before)
        self.assertNotIn(P + 'seed_paid', state)
        force_option(world, old, 'withdraw')
        self.assertNotIn(P + 'outcome', state)
        self.assertTrue(option_legal(world, current, 'pay_seed'))
        choose(world, arc, current, 'pay_seed')
        self.assertEqual(state[P + 'seed_paid'], 1)

    def test_each_waitable_stage_rejects_its_previous_popup_instance(self):
        steps = ((1120, 'pay_seed', 'wait_seed'),
                 (1121, 'route_processing', 'wait_route'),
                 (1122, 'pay_basis', 'wait_basis'),
                 (1123, 'name_full', 'wait_responsible'),
                 (1124, 'start_audit', 'wait_audit'),
                 (1125, 'settle_matured', 'wait_observation'))
        for target, current_choice, wait_choice in steps:
            with self.subTest(target=target):
                world = new_world()
                arc = gold_arc()
                world.refresh(arc)
                for number, choice, _ in steps:
                    if number == target:
                        break
                    play(world, arc, number, choice)
                if target == 1125:
                    month(world, arc, 6)
                old = world.deliver(arc, f'ywc_lan.{target}')
                choose(world, arc, old, wait_choice)
                current = world.deliver(arc, f'ywc_lan.{target}')
                self.assertNotEqual(old.saved['ywc_lan_gold_popup_epoch'],
                                    current.saved['ywc_lan_gold_popup_epoch'])
                before = copy.deepcopy((world.countries, world.treasury))
                for stale_choice in (wait_choice, 'withdraw', current_choice):
                    force_option(world, old, stale_choice)
                    self.assertEqual((world.countries, world.treasury), before, stale_choice)
                self.assertTrue(option_legal(world, current, current_choice))
                choose(world, arc, current, current_choice)

    def test_processing_full_route_pays_seed_plus_basis_and_settles(self):
        world = new_world("processing")
        arc = reach_review(world)
        state = world.countries[world.tag]
        self.assertEqual(state[P + "seed_paid_amount"], 1000)
        self.assertEqual(state[P + "basis_paid_amount"], 1000)
        month(world, arc, 6)
        self.assertEqual(state[P + "review_streak"], 6)
        self.assertEqual(state[P + "observation_done"], 1)
        finish = review_then_finish_event(world, arc)
        choose(world, arc, finish, "settle_established")
        self.assertEqual(state[P + "outcome"], 1)
        self.assertIn("ywc_v03_lan_v03_lan_beyond_gold_settled", state)
        self.assertEqual(world.treasury[world.tag], -2000)

    def test_farming_and_monopoly_pay_half_basis(self):
        for route, basis in (("farming", 500), ("monopoly", 500)):
            with self.subTest(route=route):
                world = new_world(route)
                arc = reach_review(world, route)
                state = world.countries[world.tag]
                self.assertEqual(state[P + "seed_paid_amount"], 1000)
                self.assertEqual(state[P + "basis_paid_amount"], basis)
                month(world, arc, 6)
                finish = review_then_finish_event(world, arc)
                choose(world, arc, finish, "settle_established")
                self.assertEqual(state[P + "outcome"], 1)
                self.assertEqual(world.treasury[world.tag], -(1000 + basis))

    def test_prior_mine_precedent_changes_both_seed_and_later_monopoly_basis(self):
        # A genuinely earned public mine audit halves the seed AND, when the
        # monopoly route is chosen, quarters a later monopoly basis payment.
        world = new_world("monopoly", source="precedent")
        arc = reach_review(world, "monopoly")
        state = world.countries[world.tag]
        self.assertEqual(state[P + "seed_paid_amount"], 500)
        self.assertEqual(state[P + "seed_source"], 1)
        # Monopoly basis is 0.25 U because the audited mine is a real prior fact.
        self.assertEqual(state[P + "basis_paid_amount"], BASIS_PRECEDENT_MONOPOLY)
        self.assertEqual(state[P + "basis_source_precedent"], 1)
        self.assertEqual(world.treasury[world.tag], -(500 + BASIS_PRECEDENT_MONOPOLY))
        # The line does not modify the old mine obligations or other-arc state.
        self.assertEqual(state["ywc_lan_mine_route"], 1)
        self.assertEqual(state["ywc_lan_mine_reserve_paid"], 1)

    def test_public_leverage_changes_later_processing_basis_and_responsibility(self):
        # A genuinely settled public mandate (mode 1) halves the seed AND, on the
        # processing route, lowers the later basis to three quarters. It also
        # lets a full responsibility arrangement be named through that office.
        world = new_world("processing", source="leverage")
        state = world.countries[world.tag]
        arc = reach_review(world, "processing")
        self.assertEqual(state[P + "seed_paid_amount"], 500)
        self.assertEqual(state[P + "basis_paid_amount"], BASIS_LEVERAGE_PROCESSING)
        self.assertEqual(state[P + "basis_source_leverage"], 1)
        self.assertEqual(state[P + "responsible_recorded"], 2)
        self.assertEqual(world.treasury[world.tag], -(500 + BASIS_LEVERAGE_PROCESSING))

    def test_absent_prior_facts_keep_honest_full_rates(self):
        world = new_world("processing")
        arc = reach_review(world, "processing")
        state = world.countries[world.tag]
        self.assertEqual(state[P + "seed_paid_amount"], SEED["base"])
        self.assertEqual(state[P + "basis_paid_amount"], BASIS["processing"])
        self.assertNotIn(P + "basis_source_leverage", state)
        self.assertNotIn(P + "basis_source_precedent", state)

    def test_creation_day_and_five_months_are_not_six_observations(self):
        world = new_world("processing")
        arc = reach_review(world)
        state = world.countries[world.tag]
        world.pulse(arc)  # same-day callback is gated out
        self.assertEqual(state[P + "review_streak"], 0)
        for count in range(1, 6):
            month(world, arc)
            self.assertEqual(state[P + "review_streak"], count)
            self.assertNotIn(P + "observation_done", state)
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 6)
        self.assertEqual(state[P + "observation_done"], 1)

    def test_zero_maturity_cannot_advance_an_actually_observed_review(self):
        world = new_world()
        arc = reach_review(world)
        month(world, arc, 6)
        state = world.countries[world.tag]
        self.assertEqual(state[P + 'observation_done'], 1)
        event = world.deliver(arc, 'ywc_lan.1125')
        state[P + 'observation_done'] = 0
        self.assertFalse(option_legal(world, event, 'settle_matured'))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, event, 'settle_matured')
        self.assertEqual((state, world.treasury), before)
        state[P + 'observation_done'] = 1
        state[P + 'review_streak'] = 5
        self.assertFalse(option_legal(world, event, 'settle_matured'))
        state[P + 'review_streak'] = 6
        self.assertTrue(option_legal(world, event, 'settle_matured'))

    def test_employment_break_interrupts_and_requires_explicit_restart(self):
        world = new_world("processing")
        arc = reach_review(world)
        state = world.countries[world.tag]
        month(world, arc, 4)
        self.assertEqual(state[P + "review_streak"], 4)
        food = next(b for b in state["states"][0]["buildings"]
                    if b["type"] == "building_food_industry")
        food["occupancy"] = .1
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertIn(P + "observation_interrupted", state)
        event = world.deliver(arc, "ywc_lan.1125")
        self.assertFalse(option_legal(world, event, "settle_matured"))
        self.assertFalse(option_legal(world, event, "restart_audit"))
        food["occupancy"] = .8
        self.assertTrue(option_legal(world, event, "restart_audit"))
        choose(world, arc, event, "restart_audit")
        self.assertNotIn(P + "observation_interrupted", state)
        month(world, arc, 6)
        self.assertEqual(state[P + "review_streak"], 6)

    def test_missing_processing_sector_fails_audit_and_never_claims_full_ending(self):
        world = new_world("processing")
        arc = reach_review(world)
        state = world.countries[world.tag]
        # The workshop was never built: remove it and its workers before the audit.
        state["states"][0]["buildings"] = [
            b for b in state["states"][0]["buildings"]
            if b["type"] != "building_food_industry"]
        state["states"][0]["pops"] = [
            p for p in state["states"][0]["pops"]
            if p["type"] != "machinists"]
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertIn(P + "observation_interrupted", state)
        event = world.deliver(arc, "ywc_lan.1125")
        self.assertFalse(option_legal(world, event, "restart_audit"))
        self.assertFalse(option_legal(world, event, "settle_matured"))

    def test_treasury_recheck_blocks_payment_without_cash(self):
        world = new_world("processing", budget=100)
        arc = gold_arc()
        world.refresh(arc)
        # The seed costs 1000; 100 gold is not enough, so no legal pay option exists.
        event = world.deliver(arc, "ywc_lan.1120")
        state = world.countries[world.tag]
        state["gold_reserves"] = -world.treasury[world.tag]
        self.assertFalse(option_legal(world, event, "pay_seed"))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, event, "pay_seed")
        self.assertEqual((state, world.treasury), before)
        state["gold_reserves"] += 5000
        choose(world, arc, event, "pay_seed")
        self.assertEqual(state[P + "seed_paid"], 1)

    def test_withdraw_releases_once_and_keeps_payments(self):
        world = new_world("processing")
        arc = gold_arc()
        world.refresh(arc)
        play(world, arc, 1120, "pay_seed")
        state = world.countries[world.tag]
        event = world.deliver(arc, "ywc_lan.1121")
        choose(world, arc, event, "withdraw")
        self.assertEqual(state[P + "outcome"], 4)
        self.assertEqual(state[P + "seed_paid_amount"], 1000)
        self.assertEqual(world.treasury[world.tag], -1000)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)

    def test_pilot_captured_at_entry_and_bound_to_that_exact_state(self):
        world = new_world("processing")
        arc = gold_arc()
        world.refresh(arc)
        play(world, arc, 1120, "pay_seed")
        state = world.countries[world.tag]
        self.assertIn(P + "pilot_state", state)
        self.assertIsInstance(state[P + "pilot_state"], StateRef)
        self.assertEqual(state[P + "pilot_state"], StateRef(state["states"][0]["_sid"]))

    def test_second_same_region_state_cannot_substitute_for_the_captured_pilot(self):
        # A second owned West Borneo state with a fully staffed workshop exists
        # next to the captured pilot. The pilot itself lacks a food industry, so
        # the processing route must fail its scoped check despite the decoy.
        world = new_world("processing")
        state = world.countries[world.tag]
        # Strip the pilot's own food industry before the audit.
        state["states"][0]["buildings"] = [
            b for b in state["states"][0]["buildings"]
            if b["type"] != "building_food_industry"]
        state["states"][0]["pops"] = [
            p for p in state["states"][0]["pops"] if p["type"] != "machinists"]
        # Decoy state, same region, staffed workshop.
        decoy = copy.deepcopy(state["states"][0])
        decoy.pop("_sid", None)
        decoy.update(owner="LAN", region="s:STATE_WEST_BORNEO")
        food = {"type": "building_food_industry", "groups": ["bg_manufacturing"],
                "level": 3, "occupancy": .9, "shortage": False}
        decoy["buildings"].append(food)
        worker = copy.deepcopy(decoy["pops"][0])
        worker.update(type="machinists", employed=True, workplace=food)
        decoy["pops"].append(worker)
        arc = reach_review(world, "processing")
        state["states"].append(decoy)
        month(world, arc)
        # The decoy cannot satisfy the captured pilot's scoped processing check.
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertIn(P + "observation_interrupted", state)

    def test_lost_captured_pilot_records_setback_and_never_rewards(self):
        world = new_world("processing")
        arc = reach_review(world)
        state = world.countries[world.tag]
        # The captured pilot falls to a foreign power mid-audit.
        lost = state["states"].pop(0)
        lost["owner"] = "DEI"
        world.countries["DEI"]["states"] = [lost]
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        # Losing the pilot queues an honest setback; it cannot close before delivery.
        self.assertNotIn(P + "outcome", state)
        event = world.deliver(arc, "ywc_lan.1126")
        choose(world, arc, event, "settle_setback")
        self.assertEqual(state[P + "outcome"], 3)
        self.assertIn(P + "setback_recorded", state)
        self.assertIn("ywc_v03_lan_v03_lan_beyond_gold_settled", state)
        # No route benefit is applied on a lost pilot.
        country_names = [fields.get("name") for tag, fields in world.modifiers
                         if tag == world.tag]
        self.assertFalse(any(name in country_names for name in (
            "ywc_lan_gold_processing_country", "ywc_lan_gold_farming_country",
            "ywc_lan_gold_monopoly_country")))
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)

    def test_established_end_applies_route_modifier_to_country_and_pilot(self):
        for route in ("processing", "farming", "monopoly"):
            with self.subTest(route=route):
                world = new_world(route)
                arc = reach_review(world, route)
                month(world, arc, 6)
                finish = review_then_finish_event(world, arc)
                choose(world, arc, finish, "settle_established")
                state = world.countries[world.tag]
                self.assertEqual(state[P + "outcome"], 1)
                country_names = [fields.get("name") for tag, fields in world.modifiers
                                 if tag == world.tag]
                country_name = f"ywc_lan_gold_{route}_country"
                state_name = f"ywc_lan_gold_{route}_state"
                self.assertIn(country_name, country_names)
                self.assertTrue(any(fields.get("name") == country_name and str(fields.get("days")) == "730"
                                    for tag, fields in world.modifiers if tag == world.tag))
                pilot_sid = state[P + "pilot_state"].sid
                pilot_names = [ident for (ref, ident) in world.state_modifiers
                               if ref == StateRef(pilot_sid)]
                self.assertIn(state_name, pilot_names)
                self.assertEqual(str(world.state_modifiers[(StateRef(pilot_sid), state_name)]["fields"]["days"]), "730")

    def test_deferred_review_1127_rechecks_present_facts_and_never_auto_succeeds(self):
        world = new_world("processing")
        arc = reach_review(world)
        state = world.countries[world.tag]
        month(world, arc, 6)
        finish = review_then_finish_event(world, arc)
        choose(world, arc, finish, "late_review")
        self.assertEqual(state[P + "stage"], 1127)
        event = world.deliver(arc, "ywc_lan.1127")
        self.assertTrue(option_legal(world, event, "late_settle"))
        # Conditions lost before the deferred review: settle must become illegal.
        food = next(b for b in state["states"][0]["buildings"]
                    if b["type"] == "building_food_industry")
        food["occupancy"] = .1
        self.assertFalse(option_legal(world, event, "late_settle"))
        self.assertTrue(option_legal(world, event, "late_setback"))

    def test_no_unverified_helpers_or_foreign_money_are_referenced(self):
        arc = gold_arc()
        blob = json.dumps(arc, ensure_ascii=False)
        for forbidden in ("add_building", "create_building", "add_resource",
                          "country_event = { id = ", "treaty", "alliance"):
            self.assertNotIn(forbidden, blob)
        for modifier in (f"ywc_lan_gold_{route}_{scope}"
                         for route in ("processing", "farming", "monopoly")
                         for scope in ("country", "state")):
            self.assertIn(modifier, Path(
                ROOT / "yongchang_world/common/static_modifiers/ywc_v03_lan_modifiers.txt"
            ).read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
