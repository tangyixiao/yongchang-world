"""KOR provincial revenue runs native source against literal current facts.

Fixtures describe present laws, same-group government support, owned Korean
states, scoped turmoil and real employed populations linked to their workplace.
They do not manufacture a business route, payment, receipt or observation result.
"""
import copy
import unittest

from kor_revenue_runtime import KorRevenueWorld
from shu_kor_strict_review_runtime import facts
from test_v03_shu_provincial_contract import choose, force_option, option_legal
from kor_partner_protocol_runtime import StateRef


SLUG = "v03_kor_provincial_revenue"
JES = ("ywc_je_v03_kor_provincial_revenue_settlement",
       "ywc_je_v03_kor_provincial_revenue_review")
P = "ywc_kor_revenue_"
L = "ywc_v03_kor_v03_kor_provincial_revenue_"
TAX_LAWS = {
    "law_land_based_taxation", "law_per_capita_based_taxation",
    "law_proportional_taxation", "law_graduated_taxation", "law_consumption_based_taxation",
}
ROUTES = {"provincial": "written_shares", "central": "central_collection",
          "project": "project_grants"}


def revenue_arc(catalog):
    return next(arc for arc in catalog["arcs"] if arc["slug"] == SLUG)


def current_facts(route="provincial", bare=False):
    if route not in ("provincial", "central", "project"):
        raise ValueError(route)
    state = facts()
    state["literacy_rate"] = .35
    state["laws"] = [law for law in state["laws"] if law not in TAX_LAWS]
    state["laws"].append({
        "provincial": "law_proportional_taxation",
        "central": "law_per_capita_based_taxation",
        "project": "law_land_based_taxation",
    }[route])
    if route == "central":
        state["laws"].append("law_appointed_bureaucrats")
    state["igs"] = [
        {"type": kind, "in_government": True, "clout": .15, "approval": 2}
        for kind in ("ig_rural_folk", "ig_intelligentsia", "ig_armed_forces",
                     "ig_landowners", "ig_devout", "ig_industrialists",
                     "ig_petty_bourgeoisie", "ig_trade_unions")
    ]
    province = state["states"][0]
    # Literal region from installed map_data/state_regions/11_east_asia.txt.
    # Authored pilot encoding is inspected only after production is frozen.
    province.update(owner="KOR", region="s:STATE_SEOUL", turmoil=.10)
    for building in province["buildings"]:
        building["level"] = 1
        if building["type"] == "building_maize_farm":
            building["type"] = "building_rice_farm"
    by_type = {building["type"]: building for building in province["buildings"]}
    office_building = by_type["building_government_administration"]
    office_building["occupancy"] = .5 if route == "project" else .8
    bureaucrat = province["pops"][0]
    bureaucrat.update(primary=False, acceptance=5, employed=True,
                      type="bureaucrats", workplace=office_building)
    for kind, workplace in (("academics", "building_university"),
                             ("officers", "building_barrack"),
                             ("farmers", "building_rice_farm")):
        pop = copy.deepcopy(bureaucrat)
        pop.update(type=kind, workplace=by_type[workplace])
        province["pops"].append(pop)
    if bare:
        state["laws"] = ["law_land_based_taxation", "law_serfdom",
                         "law_no_schools", "law_state_religion"]
        state["institutions"] = {}
        province["buildings"] = [office_building]
        province["pops"] = [bureaucrat]
        office_building["occupancy"] = .25
        province["turmoil"] = .40
        for interest_group in state["igs"]:
            interest_group["in_government"] = False
    return state


def new_world(route="provincial", bare=False):
    world = KorRevenueWorld("kor", load_inline=True,
        countries={"KOR": current_facts(route, bare), "CHI": {"states": []}})
    world.run("ywc_v03_initialize_country", world.tag)
    return world


def play(world, arc, number, key):
    event = world.deliver(arc, f"ywc_kor.{number}")
    choose(world, arc, event, key)
    return event


def month(world, arc, count=1):
    for _ in range(count):
        world.advance_months(1)
        world.pulse(arc)


def office(world):
    return next(building for building in world.countries[world.tag]["states"][0]["buildings"]
                if building["type"] == "building_government_administration")


def office_pop(world):
    return next(pop for pop in world.countries[world.tag]["states"][0]["pops"]
                if pop["type"] == "bureaucrats")


def group(world, kind):
    return next(interest_group for interest_group in world.countries[world.tag]["igs"]
                if interest_group["type"] == kind)


def world_facts(world):
    state = world.countries[world.tag]
    return copy.deepcopy({key: state[key] for key in
        ("laws", "institutions", "states", "igs", "literacy_rate", "bureaucracy",
         "legitimacy", "net_fixed_income", "is_at_war", "in_default")})


def ready_for_review(world, route="provincial", limited=False):
    arc = revenue_arc(world.cat)
    for number, key in ((1100, "finite_target" if limited else ROUTES[route]),
                        (1101, "pay_charter"), (1102, "settle_reviewer"), (1103, "sign")):
        play(world, arc, number, key)
    return arc


def finish_review(world, arc, outcome=1):
    state = world.countries[world.tag]
    if P + "review_paid" not in state:
        play(world, arc, 1104, "pay_review")
    # Paying after six months must retain the real evidence already earned.
    assert state.get(P + "review_mature") == 1, "payment erased genuine six-month maturity"
    assert state[P + "review_streak"] == 6, "payment restarted an already matured observation"
    play(world, arc, 1104, "submit")
    play(world, arc, 1105, "review_responsibility")
    play(world, arc, 1106, "verify")
    return play(world, arc, 1107, {1: "request_full", 2: "request_finite",
                                  3: "request_setback"}[outcome])


def native(world, suffix):
    return world.conditions(world.trigger_defs[P + suffix], world.tag)


def pilot(world):
    reference = world.countries[world.tag][P + "pilot_state"]
    assert isinstance(reference, StateRef), reference
    return world._state_dict(reference.sid)


class KorProvincialRevenue(unittest.TestCase):
    def assert_capacity(self, world, number):
        state = world.countries[world.tag]
        self.assertEqual((state["ywc_v03_active_arc_count"],
                          state["ywc_v03_visible_task_count"]), (number, number))

    def assert_closed(self, world, outcome):
        state = world.countries[world.tag]
        self.assertEqual(state.get(P + "outcome"), outcome)
        self.assertEqual(state[L + "outcome"], outcome)
        self.assertEqual(state[L + "settled"], 1)
        self.assert_capacity(world, 0)
        self.assertFalse(any(jid in world.active[world.tag] for jid in JES))

    def start(self, world, route="provincial", limited=False):
        arc = revenue_arc(world.cat)
        play(world, arc, 1100, "finite_target" if limited else ROUTES[route])
        self.assertIsInstance(world.countries[world.tag][P + "pilot_state"], StateRef)
        self.assertEqual(world.countries[world.tag][P + "phase"], 1)
        return arc

    def test_three_complete_policies_pay_two_real_bills_and_preserve_current_facts(self):
        for route, charter, review in (("provincial", 1000, 1000),
                                       ("central", 2000, 1500), ("project", 500, 500)):
            with self.subTest(route=route):
                world = new_world(route)
                original = world_facts(world)
                arc = ready_for_review(world, route)
                state = world.countries[world.tag]
                self.assertEqual(state[P + "target"], 1)
                self.assertEqual(state[P + "phase"], 2)
                self.assertEqual(state[P + "charter_paid_amount"], charter)
                self.assertEqual(world.history[world.tag][JES[0]], "complete")
                self.assertIn(JES[1], world.active[world.tag])
                self.assert_capacity(world, 1)
                month(world, arc, 6)
                finish_review(world, arc)
                self.assertEqual(state[P + "review_paid_amount"], review)
                self.assertEqual(world.treasury[world.tag], -charter - review)
                self.assert_closed(world, 1)
                self.assertEqual(world_facts(world), original)
                self.assertTrue(all(world.history[world.tag][jid] == "complete" for jid in JES))

    def test_explicit_finite_goal_finishes_with_only_quarter_office_and_point_four_turmoil(self):
        world = new_world(bare=True)
        original = world_facts(world)
        arc = ready_for_review(world, limited=True)
        state = world.countries[world.tag]
        self.assertEqual(state[P + "target"], 2)
        self.assertEqual(state[P + "finite_chosen"], 1)
        self.assertEqual(state[P + "charter_paid_amount"], 500)
        month(world, arc, 6)
        finish_review(world, arc, outcome=2)
        self.assertEqual(state[P + "review_paid_amount"], 500)
        self.assertEqual(world.treasury[world.tag], -1000)
        self.assert_closed(world, 2)
        self.assertEqual(world_facts(world), original)

    def test_three_policy_law_sets_are_current_and_appointed_bureaucrats_is_a_law(self):
        cases = (("provincial", "law_proportional_taxation", "law_land_based_taxation"),
                 ("central", "law_per_capita_based_taxation", "law_land_based_taxation"),
                 ("project", "law_land_based_taxation", "law_graduated_taxation"))
        for route, correct, wrong in cases:
            with self.subTest(route=route):
                world = new_world(route)
                self.start(world, route)
                self.assertTrue(native(world, "selected_current_ready"))
                state = world.countries[world.tag]
                state["laws"].remove(correct)
                state["laws"].append(wrong)
                self.assertFalse(native(world, "selected_current_ready"))
                state["laws"].remove(wrong)
                state["laws"].append(correct)
                self.assertTrue(native(world, "selected_current_ready"))
                if route == "central":
                    state["laws"].remove("law_appointed_bureaucrats")
                    self.assertFalse(native(world, "selected_current_ready"))
                if route == "provincial":
                    arc = revenue_arc(world.cat)
                    play(world, arc, 1101, "pay_charter")
                    play(world, arc, 1102, "settle_reviewer")
                    event = world.deliver(arc, "ywc_kor.1103")
                    state["laws"].remove(correct)
                    state["laws"].append(wrong)
                    self.assertFalse(option_legal(world, event, "sign"),
                                     "signature must recheck the actual current tax policy")

    def test_support_type_government_clout_and_approval_belong_to_the_same_actual_group(self):
        for route, kind in (("provincial", "ig_rural_folk"), ("central", "ig_armed_forces"),
                            ("project", "ig_landowners")):
            with self.subTest(route=route):
                world = new_world(route)
                self.start(world, route)
                state = world.countries[world.tag]
                for candidate in state["igs"]:
                    candidate["in_government"] = False
                selected = group(world, kind)
                selected.update(in_government=False, clout=.2, approval=1)
                split = copy.deepcopy(selected)
                split.update(in_government=True, clout=.09, approval=1)
                state["igs"].append(split)
                self.assertFalse(native(world, "selected_current_ready"))
                split.update(clout=.10, approval=-1)
                self.assertFalse(native(world, "selected_current_ready"))
                split["approval"] = 0
                self.assertTrue(native(world, "selected_current_ready"))

    def test_real_employment_office_and_route_specific_resources_are_required(self):
        cases = (("provincial", "office", .79), ("provincial", "school", None),
                 ("central", "officers", None), ("central", "barracks", .79),
                 ("project", "office", .49), ("project", "farmers", None),
                 ("project", "farm", .49), ("project", "wrong_farm", None))
        for route, loss, value in cases:
            with self.subTest(route=route, loss=loss):
                world = new_world(route)
                self.start(world, route)
                self.assertTrue(native(world, "selected_current_ready"))
                state = world.countries[world.tag]
                if loss == "office":
                    office(world)["occupancy"] = value
                elif loss == "school":
                    state["institutions"] = {}
                elif loss in ("officers", "farmers"):
                    next(pop for pop in pilot(world)["pops"] if pop["type"] == loss)["employed"] = False
                else:
                    workplace = next(pop["workplace"] for pop in pilot(world)["pops"]
                                     if pop["type"] == ("officers" if loss == "barracks" else "farmers"))
                    if loss == "wrong_farm":
                        workplace["type"] = "building_tea_plantation"
                    else:
                        workplace["occupancy"] = value
                self.assertFalse(native(world, "selected_current_ready"))

    def test_saved_pilot_cannot_borrow_healthy_posts_turmoil_or_ownership_from_another_state(self):
        state = current_facts()
        other = copy.deepcopy(state["states"][0])
        other["region"] = "s:STATE_BUSAN"
        state["states"].append(other)
        world = KorRevenueWorld("kor", countries={"KOR": state, "CHI": {"states": []}})
        world.run("ywc_v03_initialize_country", world.tag)
        arc = self.start(world)
        selected = pilot(world)
        reference = state[P + "pilot_state"]
        self.assertTrue(native(world, "selected_current_ready"))
        selected["turmoil"] = .26
        self.assertFalse(native(world, "selected_current_ready"))
        selected["turmoil"] = .1
        clerk = next(pop for pop in selected["pops"] if pop["type"] == "bureaucrats")
        clerk["employed"] = False
        self.assertFalse(native(world, "selected_current_ready"))
        clerk["employed"] = True
        selected["owner"] = "CHI"
        self.assertFalse(native(world, "selected_current_ready"))
        month(world, arc)
        self.assertEqual(state[P + "pilot_state"], reference)
        self.assertFalse(native(world, "pilot_owned"))
        self.assertTrue(any(s["owner"] == "KOR" for s in state["states"]))

    def test_turmoil_boundaries_are_scoped_and_inclusive_for_full_and_finite(self):
        for limited, boundary in ((False, .25), (True, .40)):
            with self.subTest(limited=limited):
                world = new_world(bare=limited)
                self.start(world, limited=limited)
                selected = pilot(world)
                condition = "target2_finite" if limited else "full_conditions"
                selected["turmoil"] = boundary
                self.assertTrue(native(world, condition))
                selected["turmoil"] = boundary + .000001
                self.assertFalse(native(world, condition))
                selected["turmoil"] = boundary
                self.assertTrue(native(world, condition))

    def test_both_real_fees_atomically_recheck_current_cash_default_and_bankruptcy(self):
        for number, key, paid in ((1101, "pay_charter", "charter"), (1104, "pay_review", "review")):
            for loss in ("cash", "default", "bankruptcy", "phase_zero", "phase_missing", "stage_missing"):
                with self.subTest(number=number, loss=loss):
                    world = new_world()
                    arc = self.start(world) if number == 1101 else ready_for_review(world)
                    if number == 1104:
                        month(world, arc, 6)
                    event = world.deliver(arc, f"ywc_kor.{number}")
                    state = world.countries[world.tag]
                    state["gold_reserves"] = 1000 - world.treasury[world.tag]
                    self.assertTrue(option_legal(world, event, key))
                    if loss == "cash":
                        state["gold_reserves"] -= 1
                    elif loss == "default":
                        state["in_default"] = True
                    elif loss == "bankruptcy":
                        world.execute([("add_modifier", "=", [("name", "=", "declared_bankruptcy"),
                                                               ("months", "=", "12")])], world.tag)
                    elif loss == "phase_zero":
                        state[P + "phase"] = 0
                    elif loss == "phase_missing":
                        state.pop(P + "phase")
                    else:
                        state.pop(P + "stage")
                    self.assertFalse(option_legal(world, event, key))
                    before = copy.deepcopy((world.countries, world.treasury, world.history, world.active))
                    force_option(world, event, key)
                    self.assertEqual((world.countries, world.treasury, world.history, world.active), before)
                    self.assertNotIn(P + paid + "_paid", state)

    def test_budget_is_captured_once_with_minimum_and_a_paid_charter_cannot_charge_again(self):
        world = new_world()
        state = world.countries[world.tag]
        state["yearly_gross_income"] = 520
        arc = self.start(world)
        self.assertEqual(state[P + "budget"], 100)
        state["yearly_gross_income"] = 104000
        event = world.deliver(arc, "ywc_kor.1101")
        before = world.treasury[world.tag]
        choose(world, arc, event, "pay_charter")
        self.assertEqual(world.treasury[world.tag] - before, -100)
        self.assertEqual(state[P + "charter_paid_amount"], 100)
        before = copy.deepcopy((world.countries, world.treasury, world.active, world.history))
        force_option(world, event, "pay_charter")
        self.assertEqual((world.countries, world.treasury, world.active, world.history), before)

    def test_creation_day_duplicate_and_five_months_cannot_mature_or_pay_review(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        start_month = world.elapsed_months
        world.pulse(arc)
        self.assertEqual(state[P + "review_streak"], 0)
        for count in range(1, 6):
            month(world, arc)
            self.assertEqual(world.elapsed_months - start_month, count)
            self.assertEqual(state[P + "review_streak"], count)
            world.pulse(arc)
            self.assertEqual(state[P + "review_streak"], count)
            self.assertNotIn(P + "review_mature", state)
        # A source may keep the popup queued until maturity, or show a genuine
        # waiting popup early. Only an already delivered/queued early popup
        # supplies a real receipt here; delivery must not advance into month6.
        if any(event_id == "ywc_kor.1104" for _, event_id in world.events):
            probe = copy.deepcopy(world)
            early = probe.deliver(arc, "ywc_kor.1104")
            self.assertEqual(probe.elapsed_months, world.elapsed_months)
            self.assertFalse(option_legal(probe, early, "pay_review"))
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 6)
        self.assertEqual(state[P + "review_mature"], 1)

    def test_interruption_clears_continuity_and_unpaid_recovery_requires_an_explicit_restart(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        month(world, arc, 2)
        self.assertEqual(state[P + "review_streak"], 2)
        state["bureaucracy"] = -1
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertNotIn(P + "review_running", state)
        self.assertEqual(state[P + "review_interrupted"], 1)
        state["bureaucracy"] = 100
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        event = world.deliver(arc, "ywc_kor.1104")
        self.assertTrue(option_legal(world, event, "restart_review"))
        before = world.treasury[world.tag]
        choose(world, arc, event, "restart_review")
        self.assertEqual(world.treasury[world.tag], before)
        self.assertNotIn(P + "review_paid", state)
        month(world, arc, 6)
        finish_review(world, arc)
        self.assert_closed(world, 1)

    def test_state_loss_before_handoff_refresh_still_admits_review_and_has_an_exit(self):
        world = new_world()
        arc = self.start(world)
        play(world, arc, 1101, "pay_charter")
        play(world, arc, 1102, "settle_reviewer")
        event = world.deliver(arc, "ywc_kor.1103")
        self.assertTrue(option_legal(world, event, "sign"))
        force_option(world, event, "sign")
        pilot(world)["owner"] = "CHI"
        world.refresh(arc)
        state = world.countries[world.tag]
        self.assertEqual(world.history[world.tag][JES[0]], "complete")
        self.assertIn(JES[1], world.active[world.tag])
        event = world.deliver(arc, "ywc_kor.1104")
        self.assertFalse(option_legal(world, event, "pay_review"))
        self.assertTrue(option_legal(world, event, "withdraw"))
        before = world.treasury[world.tag]
        choose(world, arc, event, "withdraw")
        self.assertEqual(world.treasury[world.tag], before)
        self.assertEqual(state[P + "charter_paid_amount"], 1000)
        self.assert_closed(world, 4)
        self.assertEqual(world.history[world.tag][JES[1]], "failed")

    def test_paid_late_recount_preserves_both_fees_and_late_setback_buttons_recheck_recovery(self):
        for action in ("recount", "finite_recount", "setback_close", "setback_recovery"):
            with self.subTest(action=action):
                world = new_world()
                arc = ready_for_review(world)
                state = world.countries[world.tag]
                month(world, arc, 6)
                play(world, arc, 1104, "pay_review")
                self.assertEqual(state.get(P + "review_mature"), 1,
                                 "paying a mature bill must preserve the earned observation")
                if action == "finite_recount":
                    before = world.treasury[world.tag]
                    event = world.deliver(arc, "ywc_kor.1104")
                    choose(world, arc, event, "narrow_finite")
                    self.assertEqual(state[P + "target"], 2)
                    self.assertEqual(state[P + "review_streak"], 0)
                    self.assertNotIn(P + "review_mature", state)
                    self.assertEqual(state[P + "stage"], 1104)
                    self.assertEqual((state[P + "charter_paid_amount"],
                                      state[P + "review_paid_amount"]), (1000, 1000))
                    if P + "review_running" not in state:
                        event = world.deliver(arc, "ywc_kor.1104")
                        choose(world, arc, event, "restart_review")
                    month(world, arc, 6)
                    finish_review(world, arc, outcome=2)
                    self.assert_closed(world, 2)
                    self.assertEqual(world.treasury[world.tag], before)
                    continue
                play(world, arc, 1104, "submit")
                play(world, arc, 1105, "review_responsibility")
                event = world.deliver(arc, "ywc_kor.1106")
                if action == "recount":
                    before = world.treasury[world.tag]
                    choose(world, arc, event, "recount")
                    self.assertEqual(state[P + "review_streak"], 0)
                    self.assertNotIn(P + "review_mature", state)
                    self.assertEqual(state[P + "stage"], 1104)
                    self.assertEqual((state[P + "charter_paid_amount"],
                                      state[P + "review_paid_amount"]), (1000, 1000))
                    event = world.deliver(arc, "ywc_kor.1104")
                    choose(world, arc, event, "restart_review")
                    month(world, arc, 6)
                    play(world, arc, 1104, "submit")
                    play(world, arc, 1105, "review_responsibility")
                    play(world, arc, 1106, "verify")
                    play(world, arc, 1107, "request_full")
                    self.assert_closed(world, 1)
                    self.assertEqual(world.treasury[world.tag], before)
                else:
                    choose(world, arc, event, "verify")
                    final = world.deliver(arc, "ywc_kor.1107")
                    state["institutions"] = {}
                    self.assertTrue(option_legal(world, final, "request_setback"))
                    if action == "setback_close":
                        choose(world, arc, final, "request_setback")
                        self.assert_closed(world, 3)
                        self.assertEqual(world.history[world.tag][JES[1]], "complete")
                        continue
                    state["institutions"] = {"institution_schools": 2}
                    self.assertFalse(option_legal(world, final, "request_setback"))
                    before = copy.deepcopy((world.countries, world.treasury, world.active, world.history))
                    force_option(world, final, "request_setback")
                    self.assertEqual((world.countries, world.treasury, world.active, world.history), before)
                    self.assertTrue(option_legal(world, final, "request_full"))
                    choose(world, arc, final, "request_full")
                    self.assert_closed(world, 1)

    def test_withdrawal_and_repeated_release_preserve_unrelated_queues_and_paid_charter(self):
        world = new_world()
        arc = self.start(world)
        play(world, arc, 1101, "pay_charter")
        state = world.countries[world.tag]
        event = world.deliver(arc, "ywc_kor.1102")
        # Earn an unrelated military queue through its actual journal admission.
        military = next(a for a in world.cat["arcs"] if a["slug"] == "v03_kor_military_accounts")
        world.refresh(military)
        unrelated = {key: copy.deepcopy(value) for key, value in state.items()
                     if "pending_event" in key and not key.startswith(P)}
        self.assertTrue(unrelated, "control must contain a genuine unrelated pending story")
        self.assert_capacity(world, 2)
        before_cash = world.treasury[world.tag]
        choose(world, arc, event, "withdraw")
        self.assertEqual(world.treasury[world.tag], before_cash)
        self.assertEqual(state[P + "charter_paid_amount"], 1000)
        self.assertEqual({key: state[key] for key in unrelated}, unrelated)
        self.assert_capacity(world, 1)
        before = copy.deepcopy((world.countries, world.treasury, world.active, world.history))
        world.run("ywc_kor_revenue_release_once", world.tag)
        force_option(world, event, "withdraw")
        world.refresh(arc)
        self.assertEqual((world.countries, world.treasury, world.active, world.history), before)


if __name__ == "__main__":
    unittest.main()
