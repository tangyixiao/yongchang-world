"""DMG crown scenarios execute generated native ASTs with current world facts.

Fixtures describe laws, offices, employees and interest groups only.  They do
not manufacture qualification, payment, observation or historical story state.
"""
import copy
import unittest

from lan_public_runtime import LanPublicWorld
from shu_kor_strict_review_runtime import facts, field
from test_v03_shu_provincial_contract import choose, force_option, option_legal


SLUG = "v03_dmg_representative_crown"
JES = ("ywc_je_v03_dmg_crown_representation", "ywc_je_v03_dmg_crown_budget",
       "ywc_je_v03_dmg_crown_continuity")
P = "ywc_dmg_crown_"
L = "ywc_v03_dmg_v03_dmg_representative_crown_"
ROUTES = {"constitutional": "constitutional_crown", "federal": "united_republic",
          "consultative": "consultative_crown"}
ACTIONS = {1111: "pay_registry", 1112: "new_hearing", 1113: "sign_appointment",
           1114: "pay_share", 1115: "write_statement", 1116: "handoff_continuity",
           1117: "pay_review", "select_limited": "narrow_consultation",
           "limited_hearing": "limited_hearing", "limited_statement": "write_limited_statement",
           "restart": "restart_review",
           "request_full": "request_full", "request_limited": "request_limited",
           "request_setback": "request_setback", "close_full": "close_full",
           "close_limited": "close_limited", "close_setback": "close_setback",
           "recount": "recount", "withdraw": "withdraw"}


def crown_arc(catalog):
    return next(arc for arc in catalog["arcs"] if arc["slug"] == SLUG)


def current_facts(route="constitutional", bare=False):
    """A real original Luzon office and its employed accepted bureaucrat."""
    if route not in ("constitutional", "federal", "consultative"):
        raise ValueError(route)
    state = facts()
    state["literacy_rate"] = .35
    route_laws = {
        "constitutional": ["law_monarchy", "law_census_voting"],
        "federal": ["law_presidential_republic", "law_universal_suffrage"],
        "consultative": ["law_monarchy", "law_autocracy"],
    }
    state["laws"] += route_laws[route]
    state["country_has_voting_franchise"] = route != "consultative"
    state["igs"] = [
        {"type": kind, "in_government": True, "clout": .15, "approval": 2}
        for kind in ("ig_intelligentsia", "ig_rural_folk", "ig_landowners",
                     "ig_armed_forces", "ig_industrialists", "ig_petty_bourgeoisie",
                     "ig_trade_unions", "ig_devout")
    ]
    province = state["states"][0]
    province.update(owner="DMG", region="s:STATE_LUZON")
    for building in province["buildings"]:
        building["level"] = 1
    office = next(b for b in province["buildings"]
                  if b["type"] == "building_government_administration")
    office["occupancy"] = .8 if route == "constitutional" else .5
    # The inherited native adapter represents acceptance_status_5 as tier 5.
    province["pops"][0].update(primary=False, acceptance=5, employed=True,
                                type="bureaucrats", workplace=office)
    if bare:
        state["laws"] = ["law_monarchy", "law_autocracy", "law_serfdom",
                         "law_no_schools", "law_state_religion"]
        state["country_has_voting_franchise"] = False
        state["institutions"] = {}
        province["buildings"] = [office]
        province["pops"] = [province["pops"][0]]
        office["occupancy"] = .25
        for group in state["igs"]:
            group["in_government"] = group["type"] == "ig_devout"
    return state


def new_world(route="constitutional", bare=False):
    world = LanPublicWorld("dmg", load_inline=True)
    world.countries[world.tag] = current_facts(route, bare)
    world.run("ywc_v03_initialize_country", world.tag)
    return world


def play(world, arc, number, key):
    event = world.deliver(arc, f"ywc_dmg.{number}")
    choose(world, arc, event, key)
    return event


def month(world, arc, count=1):
    for _ in range(count):
        world.advance_months(1)
        world.elapsed_months += 1
        world.pulse(arc)


def ready_for_review(world, route="constitutional", limited=False):
    """Play all seven real appointment/budget events into continuity."""
    arc = crown_arc(world.cat)
    play(world, arc, 1110, ACTIONS["select_limited"] if limited else ROUTES[route])
    for number in range(1111, 1117):
        action = (ACTIONS["limited_hearing"] if limited and number == 1112 else
                  ACTIONS["limited_statement"] if limited and number == 1115 else ACTIONS[number])
        play(world, arc, number, action)
    assert all(world.history[world.tag][jid] == "complete" for jid in JES[:2])
    assert JES[2] in world.active[world.tag]
    return arc


def finish_review(world, arc, outcome=1):
    """Pay the actual mature review bill and request/close the chosen outcome."""
    play(world, arc, 1117, ACTIONS[1117])
    suffix = {1: "full", 2: "limited", 3: "setback"}[outcome]
    play(world, arc, 1118, ACTIONS["request_" + suffix])
    play(world, arc, 1119, ACTIONS["close_" + suffix])


def office(world):
    return next(b for b in world.countries[world.tag]["states"][0]["buildings"]
                if b["type"] == "building_government_administration")


def office_pop(world):
    return next(p for p in world.countries[world.tag]["states"][0]["pops"]
                if p["type"] == "bureaucrats")


def group(world, kind):
    return next(g for g in world.countries[world.tag]["igs"] if g["type"] == kind)


def world_facts(world):
    state = world.countries[world.tag]
    return copy.deepcopy({key: state[key] for key in
                          ("laws", "institutions", "states", "igs", "literacy_rate")})


class DmgRepresentativeCrown(unittest.TestCase):
    def assert_capacity(self, world, expected):
        state = world.countries[world.tag]
        self.assertEqual((state["ywc_v03_active_arc_count"],
                          state["ywc_v03_visible_task_count"]), (expected, expected))

    def assert_closed(self, world, outcome):
        state = world.countries[world.tag]
        self.assertEqual(state[P + "outcome"], outcome)
        self.assertEqual(state[L + "outcome"], outcome)
        self.assertEqual(state[L + "settled"], 1)
        self.assert_capacity(world, 0)
        self.assertFalse(any(jid in world.active[world.tag] for jid in JES))

    def assert_paid(self, world, amounts):
        state = world.countries[world.tag]
        for bill, amount in zip(("registry", "share", "review"), amounts):
            self.assertEqual(state[P + bill + "_paid"], 1)
            self.assertEqual(state[P + bill + "_paid_amount"], amount)
            self.assertGreater(state[P + bill + "_paid_amount"], 0)

    def test_three_current_policy_routes_pay_three_real_bills_without_granting_world_facts(self):
        for route, charge in (("constitutional", 3000), ("federal", 3500),
                              ("consultative", 1500)):
            with self.subTest(route=route):
                world = new_world(route)
                original = world_facts(world)
                original_modifiers = copy.deepcopy(world.modifiers)
                arc = ready_for_review(world, route)
                state = world.countries[world.tag]
                self.assert_capacity(world, 1)
                self.assertEqual(state[P + "phase"], 3)
                self.assertEqual(state[P + "stage"], 1117)
                self.assertTrue(all(world.history[world.tag][jid] == "complete"
                                    for jid in JES[:2]))
                month(world, arc, 6)
                finish_review(world, arc)
                self.assertEqual(world.treasury[world.tag], -charge)
                self.assert_paid(world, {"constitutional": (1000, 1000, 1000),
                                         "federal": (1000, 1500, 1000),
                                         "consultative": (500, 500, 500)}[route])
                self.assert_closed(world, 1)
                self.assertTrue(all(world.history[world.tag][jid] == "complete" for jid in JES))
                self.assertEqual(world_facts(world), original)
                self.assertEqual(world.modifiers, original_modifiers)

    def test_autocracy_without_school_industry_or_partner_has_explicit_finite_route(self):
        for regime in (("law_monarchy", "law_autocracy"),
                       ("law_presidential_republic", "law_universal_suffrage")):
            with self.subTest(regime=regime):
                world = new_world(bare=True)
                state = world.countries[world.tag]
                state["laws"] = list(regime) + ["law_serfdom", "law_no_schools", "law_state_religion"]
                original = world_facts(world)
                arc = ready_for_review(world, limited=True)
                self.assertEqual(state[P + "target"], 2)
                month(world, arc, 6)
                finish_review(world, arc, outcome=2)
                self.assert_closed(world, 2)
                self.assertEqual(world.treasury[world.tag], -1500)
                self.assert_paid(world, (500, 500, 500))
                self.assertEqual(world_facts(world), original)

    def test_each_full_policy_checks_its_own_current_law_and_office_threshold(self):
        cases = (
            ("constitutional", "law_census_voting", "law_autocracy", .79),
            ("federal", "law_universal_suffrage", "law_census_voting", .49),
            ("consultative", "law_autocracy", "law_universal_suffrage", .49),
        )
        for route, actual_law, wrong_law, understaffed in cases:
            for loss in ("law", "office"):
                with self.subTest(route=route, loss=loss):
                    world = new_world(route)
                    arc = crown_arc(world.cat)
                    for number in (1110, 1111, 1112):
                        play(world, arc, number, ROUTES[route] if number == 1110 else ACTIONS[number])
                    event = world.deliver(arc, "ywc_dmg.1113")
                    self.assertTrue(option_legal(world, event, ACTIONS[1113]))
                    state = world.countries[world.tag]
                    if loss == "law":
                        state["laws"].remove(actual_law)
                        state["laws"].append(wrong_law)
                    else:
                        office(world)["occupancy"] = understaffed
                    self.assertFalse(option_legal(world, event, ACTIONS[1113]))
                    before = copy.deepcopy((state, world.treasury, world.active, world.history))
                    force_option(world, event, ACTIONS[1113])
                    self.assertEqual((state, world.treasury, world.active, world.history), before)

    def test_support_type_government_clout_and_approval_must_belong_to_same_group(self):
        for route, kind in (("constitutional", "ig_intelligentsia"),
                            ("federal", "ig_rural_folk"),
                            ("consultative", "ig_landowners")):
            with self.subTest(route=route):
                world = new_world(route)
                arc = crown_arc(world.cat)
                for number in (1110, 1111, 1112):
                    play(world, arc, number, ROUTES[route] if number == 1110 else ACTIONS[number])
                event = world.deliver(arc, "ywc_dmg.1113")
                self.assertTrue(option_legal(world, event, ACTIONS[1113]))
                state = world.countries[world.tag]
                for candidate in state["igs"]:
                    candidate["in_government"] = False
                # Neither instance satisfies all three current native facts.
                original = group(world, kind)
                original.update(in_government=False, clout=.2, approval=2)
                split = copy.deepcopy(original)
                split.update(in_government=True, clout=.09, approval=2)
                state["igs"].append(split)
                self.assertFalse(option_legal(world, event, ACTIONS[1113]))
                split.update(clout=.2, approval=-1)
                self.assertFalse(option_legal(world, event, ACTIONS[1113]))
                split["approval"] = 0
                self.assertTrue(option_legal(world, event, ACTIONS[1113]))

    def test_policy_specific_bureaucracy_income_legitimacy_and_authority_stay_current(self):
        cases = (("constitutional", "bureaucracy", -1),
                 ("constitutional", "legitimacy", 24),
                 ("federal", "net_fixed_income", -1),
                 ("federal", "legitimacy", 24),
                 ("consultative", "authority", 49))
        for route, fact, failed_value in cases:
            with self.subTest(route=route, fact=fact):
                world = new_world(route)
                arc = crown_arc(world.cat)
                for number in (1110, 1111, 1112):
                    play(world, arc, number, ROUTES[route] if number == 1110 else ACTIONS[number])
                event = world.deliver(arc, "ywc_dmg.1113")
                self.assertTrue(option_legal(world, event, ACTIONS[1113]))
                world.countries[world.tag][fact] = failed_value
                self.assertFalse(option_legal(world, event, ACTIONS[1113]))

    def test_missing_or_zero_target_does_not_silently_mean_finite_consultation(self):
        for bad_target in (None, 0):
            with self.subTest(target=bad_target):
                world = new_world(bare=True)
                arc = crown_arc(world.cat)
                play(world, arc, 1110, ACTIONS["select_limited"])
                event = world.deliver(arc, "ywc_dmg.1111")
                self.assertTrue(option_legal(world, event, ACTIONS[1111]))
                state = world.countries[world.tag]
                if bad_target is None:
                    del state[P + "target"]
                else:
                    state[P + "target"] = bad_target
                self.assertFalse(option_legal(world, event, ACTIONS[1111]))
                before = copy.deepcopy((state, world.treasury))
                force_option(world, event, ACTIONS[1111])
                self.assertEqual((state, world.treasury), before)

    def test_employees_and_office_must_be_in_the_original_owned_luzon_pilot(self):
        for loss in ("unemployed", "wrong_workplace", "foreign_partition", "other_region",
                     "unaccepted", "primary"):
            with self.subTest(loss=loss):
                world = new_world("federal")
                arc = crown_arc(world.cat)
                for number in (1110, 1111, 1112):
                    play(world, arc, number, ROUTES["federal"] if number == 1110 else ACTIONS[number])
                event = world.deliver(arc, "ywc_dmg.1113")
                self.assertTrue(option_legal(world, event, ACTIONS[1113]))
                state = world.countries[world.tag]
                province = state["states"][0]
                if loss == "unemployed":
                    office_pop(world)["employed"] = False
                elif loss == "wrong_workplace":
                    office_pop(world)["workplace"] = next(b for b in province["buildings"]
                                                         if b["type"] == "building_maize_farm")
                elif loss == "unaccepted":
                    office_pop(world)["acceptance"] = 4
                elif loss == "primary":
                    office_pop(world)["primary"] = True
                else:
                    replacement = copy.deepcopy(province)
                    replacement["owner"] = "PHI" if loss == "foreign_partition" else "DMG"
                    replacement["region"] = "s:STATE_LUZON" if loss == "foreign_partition" else "s:STATE_BEIJING"
                    state["states"].append(replacement)
                    province["pops"] = []
                self.assertFalse(option_legal(world, event, ACTIONS[1113]))
                before = copy.deepcopy((state, world.treasury))
                force_option(world, event, ACTIONS[1113])
                self.assertEqual((state, world.treasury), before)

    def test_only_federal_full_policy_requires_non_primary_fully_accepted_clerk(self):
        for route, limited in (("constitutional", False), ("consultative", False),
                               ("constitutional", True)):
            # Separate native controls: primary culture is fully accepted;
            # non-primary culture may have a lower current acceptance tier.
            for primary, acceptance in ((True, 5), (False, 4)):
                with self.subTest(route=route, limited=limited, primary=primary,
                                  acceptance=acceptance):
                    world = new_world(route, bare=limited)
                    office_pop(world).update(primary=primary, acceptance=acceptance)
                    original = world_facts(world)
                    arc = ready_for_review(world, route, limited=limited)
                    month(world, arc, 6)
                    finish_review(world, arc, outcome=2 if limited else 1)
                    self.assert_closed(world, 2 if limited else 1)
                    self.assertEqual(world_facts(world), original)

    def test_creation_day_duplicate_pulses_and_five_observations_cannot_mature(self):
        for route, limited in (("constitutional", False), ("federal", False),
                               ("consultative", False), ("constitutional", True)):
            with self.subTest(route=route, limited=limited):
                world = new_world(route, bare=limited)
                arc = ready_for_review(world, route, limited=limited)
                state = world.countries[world.tag]
                self.assertEqual(state[P + "review_streak"], 0)
                for _ in range(3):
                    world.pulse(arc)
                self.assertEqual(state[P + "review_streak"], 0)
                for count in range(1, 6):
                    month(world, arc)
                    self.assertEqual(state[P + "review_streak"], count)
                    for _ in range(3):
                        world.pulse(arc)
                    self.assertEqual(state[P + "review_streak"], count)
                    self.assertNotIn(P + "review_mature", state)
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 6)
                self.assertEqual(state[P + "review_mature"], 1)

    def test_war_default_pilot_law_and_same_group_loss_require_explicit_restart(self):
        for loss in ("war", "default", "bankruptcy", "pilot", "law", "government", "clout", "approval"):
            with self.subTest(loss=loss):
                world = new_world()
                arc = ready_for_review(world)
                state = world.countries[world.tag]
                original = world_facts(world)
                original_modifiers = copy.deepcopy(world.modifiers)
                month(world, arc, 4)
                if loss == "war":
                    state["is_at_war"] = True
                elif loss == "default":
                    state["in_default"] = True
                elif loss == "bankruptcy":
                    world.modifiers.append((world.tag, {"modifier": "declared_bankruptcy"}))
                elif loss == "pilot":
                    state["states"][0]["owner"] = "PHI"
                elif loss == "law":
                    state["laws"].remove("law_census_voting")
                    state["laws"].append("law_autocracy")
                elif loss == "government":
                    group(world, "ig_intelligentsia")["in_government"] = False
                elif loss == "clout":
                    group(world, "ig_intelligentsia")["clout"] = .09
                else:
                    group(world, "ig_intelligentsia")["approval"] = -1
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 0)
                self.assertNotIn(P + "review_mature", state)
                self.assertNotIn(P + "review_running", state)
                self.assertEqual(state[P + "review_interrupted"], 1)
                state["is_at_war"] = state["in_default"] = False
                world.modifiers = original_modifiers
                state.update(copy.deepcopy(original))
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 0)
                restart = world.deliver(arc, "ywc_dmg.1117")
                self.assertFalse(option_legal(world, restart, ACTIONS[1117]))
                choose(world, arc, restart, ACTIONS["restart"])
                self.assertEqual(state[P + "review_streak"], 0)
                month(world, arc, 5)
                self.assertNotIn(P + "review_mature", state)
                month(world, arc)
                finish_review(world, arc)
                self.assert_closed(world, 1)

    def test_both_handoffs_keep_owned_state_loss_wait_and_exit_reachable(self):
        for phase in (2, 3):
            with self.subTest(phase=phase):
                world = new_world()
                arc = crown_arc(world.cat)
                handoff = 1113 if phase == 2 else 1116
                for number in range(1110, handoff):
                    play(world, arc, number, ROUTES["constitutional"] if number == 1110 else ACTIONS[number])
                state = world.countries[world.tag]
                event = world.deliver(arc, f"ywc_dmg.{handoff}")
                self.assertTrue(option_legal(world, event, ACTIONS[handoff]))
                # Execute the real currently legal handoff, then lose Luzon
                # before the journal refresh processes the actual transition.
                force_option(world, event, ACTIONS[handoff])
                state["states"][0]["owner"] = "PHI"
                world.refresh(arc)
                self.assertEqual(state[P + "phase"], phase)
                self.assertIn(JES[phase - 1], world.active[world.tag])
                self.assert_capacity(world, 1)
                number = 1114 if phase == 2 else 1117
                event = world.deliver(arc, f"ywc_dmg.{number}")
                self.assertFalse(option_legal(world, event, ACTIONS[number]))
                self.assertTrue(option_legal(world, event, ACTIONS["withdraw"]))
                choose(world, arc, event, ACTIONS["withdraw"])
                self.assert_closed(world, 4)
                self.assertNotEqual(world.history[world.tag][JES[phase - 1]], "complete")

    def test_all_three_bills_recheck_current_cash_default_and_stale_effects_atomically(self):
        for payment, already_paid in ((1111, 0), (1114, 1000), (1117, 2000)):
            for denial in ("cash", "default", "bankruptcy"):
                with self.subTest(payment=payment, denial=denial):
                    world = new_world()
                    arc = crown_arc(world.cat)
                    for number in range(1110, payment):
                        play(world, arc, number, ROUTES["constitutional"] if number == 1110 else ACTIONS[number])
                    if payment == 1117:
                        month(world, arc, 6)
                    event = world.deliver(arc, f"ywc_dmg.{payment}")
                    state = world.countries[world.tag]
                    self.assertTrue(option_legal(world, event, ACTIONS[payment]))
                    self.assertEqual(world.treasury[world.tag], -already_paid)
                    cash = state["gold_reserves"]
                    current_modifiers = copy.deepcopy(world.modifiers)
                    if denial == "cash":
                        state["gold_reserves"] = -world.treasury[world.tag]
                    elif denial == "default":
                        state["in_default"] = True
                    else:
                        world.modifiers.append((world.tag, {"modifier": "declared_bankruptcy"}))
                    self.assertFalse(option_legal(world, event, ACTIONS[payment]))
                    before = copy.deepcopy((state, world.treasury, world.active, world.history,
                                            world.modifiers))
                    force_option(world, event, ACTIONS[payment])
                    self.assertEqual((state, world.treasury, world.active, world.history,
                                      world.modifiers), before)
                    state["gold_reserves"] = cash
                    state["in_default"] = False
                    world.modifiers = current_modifiers
                    choose(world, arc, event, ACTIONS[payment])
                    self.assertEqual(world.treasury[world.tag], -(already_paid + 1000))
                    before = copy.deepcopy((state, world.treasury))
                    force_option(world, event, ACTIONS[payment])
                    self.assertEqual((state, world.treasury), before)

    def test_all_three_payment_actions_recheck_the_actual_selected_current_policy(self):
        for payment in (1111, 1114, 1117):
            with self.subTest(payment=payment):
                world = new_world()
                arc = crown_arc(world.cat)
                for number in range(1110, payment):
                    play(world, arc, number, ROUTES["constitutional"] if number == 1110 else ACTIONS[number])
                if payment == 1117:
                    month(world, arc, 6)
                event = world.deliver(arc, f"ywc_dmg.{payment}")
                self.assertTrue(option_legal(world, event, ACTIONS[payment]))
                state = world.countries[world.tag]
                state["laws"].remove("law_census_voting")
                state["laws"].append("law_autocracy")
                self.assertFalse(option_legal(world, event, ACTIONS[payment]))
                before = copy.deepcopy((state, world.treasury))
                force_option(world, event, ACTIONS[payment])
                self.assertEqual((state, world.treasury), before)

    def test_claim_captures_income_budget_once_with_a_real_minimum(self):
        for gross, expected in ((52000, 3000), (0, 300)):
            with self.subTest(gross=gross):
                world = new_world()
                state = world.countries[world.tag]
                state["yearly_gross_income"] = gross
                arc = crown_arc(world.cat)
                play(world, arc, 1110, ROUTES["constitutional"])
                state["yearly_gross_income"] = 520000
                for number in range(1111, 1117):
                    play(world, arc, number, ACTIONS[number])
                month(world, arc, 6)
                finish_review(world, arc)
                self.assertEqual(world.treasury[world.tag], -expected)
                self.assert_closed(world, 1)

    def test_each_late_recount_requires_six_new_months_without_recharging_paid_bills(self):
        for late in (1118, 1119):
            with self.subTest(late=late):
                world = new_world()
                arc = ready_for_review(world)
                month(world, arc, 6)
                play(world, arc, 1117, ACTIONS[1117])
                if late == 1119:
                    play(world, arc, 1118, ACTIONS["request_full"])
                event = world.deliver(arc, f"ywc_dmg.{late}")
                state = world.countries[world.tag]
                self.assertEqual(world.treasury[world.tag], -3000)
                choose(world, arc, event, ACTIONS["recount"])
                self.assertEqual(state[P + "stage"], 1117)
                self.assertEqual(state[P + "review_streak"], 0)
                self.assertNotIn(P + "review_mature", state)
                self.assertNotIn(P + "requested_outcome", state)
                before = copy.deepcopy((state, world.treasury))
                force_option(world, event, ACTIONS["recount"])
                self.assertEqual((state, world.treasury), before)
                # These three bills are already genuinely paid. A fresh count
                # must not demand a second cash balance for the settled bill.
                state["gold_reserves"] = -world.treasury[world.tag]
                month(world, arc, 5)
                self.assertNotIn(P + "review_mature", state)
                month(world, arc)
                finish_review(world, arc)
                self.assert_closed(world, 1)
                self.assertEqual(world.treasury[world.tag], -3000)

    def test_setback_requires_actual_mature_paid_history_and_current_failure(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        future = world.event_defs["ywc_dmg.1118"]
        self.assertFalse(option_legal(world, future, ACTIONS["request_setback"]))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, future, ACTIONS["request_setback"])
        self.assertEqual((state, world.treasury), before)
        month(world, arc, 6)
        play(world, arc, 1117, ACTIONS[1117])
        event = world.deliver(arc, "ywc_dmg.1118")
        self.assertFalse(option_legal(world, event, ACTIONS["request_setback"]))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, event, ACTIONS["request_setback"])
        self.assertEqual((state, world.treasury), before)
        state["is_at_war"] = True
        self.assertTrue(option_legal(world, event, ACTIONS["request_setback"]))
        choose(world, arc, event, ACTIONS["request_setback"])
        final = world.deliver(arc, "ywc_dmg.1119")
        self.assertTrue(option_legal(world, final, ACTIONS["close_setback"]))
        state["is_at_war"] = False
        self.assertFalse(option_legal(world, final, ACTIONS["close_setback"]))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, final, ACTIONS["close_setback"])
        self.assertEqual((state, world.treasury), before)
        state["is_at_war"] = True
        choose(world, arc, final, ACTIONS["close_setback"])
        self.assert_closed(world, 3)
        self.assertEqual(world.treasury[world.tag], -3000)

    def test_late_monthly_pulses_preserve_delivered_stage_and_mature_evidence(self):
        world = new_world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1117, ACTIONS[1117])
        state = world.countries[world.tag]
        for number, action in ((1118, ACTIONS["request_full"]),
                               (1119, ACTIONS["close_full"])):
            event = world.deliver(arc, f"ywc_dmg.{number}")
            pending = state.get(P + "pending_event")
            # Inspect the actual tracker independently: it may not rewrite a
            # late stage or its queue. The separate normal queue preparer may
            # legitimately re-offer this SAME still-unanswered issue later.
            world.run("ywc_dmg_crown_track_review", world.tag)
            self.assertEqual(state.get(P + "pending_event"), pending)
            month(world, arc, 2)
            self.assertEqual(state[P + "stage"], number)
            self.assertIn(state.get(P + "pending_event"), (None, number))
            self.assertEqual(state[P + "review_streak"], 6)
            self.assertEqual(state[P + "review_mature"], 1)
            self.assertNotIn(P + "review_running", state)
            choose(world, arc, event, action)
        self.assert_closed(world, 1)

    def test_final_full_settlement_rechecks_current_law_same_group_and_original_pilot(self):
        for route, loss in (("constitutional", "law"), ("federal", "employee"),
                            ("consultative", "government"), ("constitutional", "pilot")):
            with self.subTest(route=route, loss=loss):
                world = new_world(route)
                arc = ready_for_review(world, route)
                month(world, arc, 6)
                play(world, arc, 1117, ACTIONS[1117])
                play(world, arc, 1118, ACTIONS["request_full"])
                event = world.deliver(arc, "ywc_dmg.1119")
                state = world.countries[world.tag]
                self.assertTrue(option_legal(world, event, ACTIONS["close_full"]))
                if loss == "law":
                    state["laws"].remove("law_census_voting")
                    state["laws"].append("law_autocracy")
                elif loss == "employee":
                    office_pop(world)["employed"] = False
                elif loss == "government":
                    for kind in ("ig_landowners", "ig_armed_forces"):
                        group(world, kind)["in_government"] = False
                else:
                    state["states"][0]["owner"] = "PHI"
                self.assertFalse(option_legal(world, event, ACTIONS["close_full"]))
                before = copy.deepcopy((state, world.treasury, world.active, world.history))
                force_option(world, event, ACTIONS["close_full"])
                self.assertEqual((state, world.treasury, world.active, world.history), before)
                self.assertTrue(option_legal(world, event, ACTIONS["withdraw"]))

    def test_new_native_opposition_interrupts_and_explicit_restart_records_it_without_grants(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        self.assertEqual(state[P + "statement_opposition"], 0)
        self.assertEqual(state[P + "terms_opposition"], 0)
        month(world, arc, 4)
        opponent = group(world, "ig_devout")
        opponent.update(in_government=False, clout=.05, approval=-1)
        actual = world_facts(world)
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertEqual(state[P + "review_interrupted"], 1)
        self.assertNotIn(P + "review_running", state)
        event = world.deliver(arc, "ywc_dmg.1117")
        self.assertTrue(option_legal(world, event, ACTIONS["restart"]))
        paid = world.treasury[world.tag]
        choose(world, arc, event, ACTIONS["restart"])
        self.assertEqual(state[P + "statement_opposition"], 1)
        self.assertEqual(state[P + "terms_opposition"], 1)
        self.assertEqual(world_facts(world), actual)
        self.assertEqual(world.treasury[world.tag], paid)
        self.assertEqual(state[P + "review_streak"], 0)
        month(world, arc, 5)
        self.assertNotIn(P + "review_mature", state)
        month(world, arc)
        finish_review(world, arc)
        self.assert_closed(world, 1)
        self.assertEqual(world_facts(world), actual)

    def test_opposition_requires_same_group_outside_government_with_weight_and_disapproval(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        opponent = group(world, "ig_devout")
        for count, changes in enumerate((
                {"in_government": False, "clout": .049, "approval": -1},
                {"in_government": False, "clout": .05, "approval": 0},
                {"in_government": True, "clout": .05, "approval": -1}), 1):
            opponent.update(changes)
            month(world, arc)
            self.assertEqual(state[P + "review_streak"], count)
            self.assertNotIn(P + "review_interrupted", state)
        opponent["in_government"] = False
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertEqual(state[P + "review_interrupted"], 1)

    def test_final_terms_explicitly_capture_opposition_that_appears_after_public_statement(self):
        for appears_after_statement in (False, True):
            with self.subTest(after_statement=appears_after_statement):
                world = new_world()
                arc = crown_arc(world.cat)
                for number in range(1110, 1115):
                    play(world, arc, number, ROUTES["constitutional"] if number == 1110 else ACTIONS[number])
                opponent = group(world, "ig_devout")
                if not appears_after_statement:
                    opponent.update(in_government=False, clout=.05, approval=-1)
                play(world, arc, 1115, ACTIONS[1115])
                state = world.countries[world.tag]
                self.assertEqual(state[P + "statement_opposition"], int(not appears_after_statement))
                if appears_after_statement:
                    opponent.update(in_government=False, clout=.05, approval=-1)
                actual = world_facts(world)
                play(world, arc, 1116, ACTIONS[1116])
                self.assertEqual(state[P + "statement_opposition"], 1)
                self.assertEqual(state[P + "terms_opposition"], 1)
                month(world, arc, 6)
                self.assertEqual(state[P + "review_streak"], 6)
                self.assertEqual(state[P + "review_mature"], 1)
                finish_review(world, arc)
                self.assert_closed(world, 1)
                self.assertEqual(world_facts(world), actual)

    def test_explicit_finite_renegotiation_resigns_local_hearing_and_blocks_cached_full_request(self):
        world = new_world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1117, ACTIONS[1117])
        old_request = world.deliver(arc, "ywc_dmg.1118")
        self.assertTrue(option_legal(world, old_request, ACTIONS["request_full"]))
        choose(world, arc, old_request, ACTIONS["recount"])
        state = world.countries[world.tag]
        state["laws"].remove("law_census_voting")
        state["laws"].append("law_autocracy")
        office(world)["occupancy"] = .25
        actual = world_facts(world)
        month(world, arc)
        event = world.deliver(arc, "ywc_dmg.1117")
        self.assertFalse(option_legal(world, event, ACTIONS["restart"]))
        self.assertTrue(option_legal(world, event, "narrow_and_recount"))
        choose(world, arc, event, "narrow_and_recount")
        self.assertEqual(state[P + "target"], 2)
        self.assertEqual(state[P + "hearing"], 3)
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertEqual(world.treasury[world.tag], -3000)
        self.assertEqual(world_facts(world), actual)
        for snapshot in ("hearing_target", "terms_target", "statement_target"):
            self.assertEqual(state[P + snapshot], 2)
        before = copy.deepcopy((state, world.treasury))
        force_option(world, old_request, ACTIONS["request_full"])
        self.assertEqual((state, world.treasury), before)
        month(world, arc, 5)
        self.assertNotIn(P + "review_mature", state)
        month(world, arc)
        play(world, arc, 1117, ACTIONS[1117])
        new_request = world.deliver(arc, "ywc_dmg.1118")
        self.assertFalse(option_legal(world, new_request, ACTIONS["request_full"]))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, old_request, ACTIONS["request_full"])
        self.assertEqual((state, world.treasury), before)
        choose(world, arc, new_request, ACTIONS["request_limited"])
        play(world, arc, 1119, ACTIONS["close_limited"])
        self.assert_closed(world, 2)
        self.assertEqual(world.treasury[world.tag], -3000)
        self.assertEqual(world_facts(world), actual)

    def test_terminal_release_is_exactly_once_and_preserves_other_line_queues_and_witness(self):
        world = new_world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1117, ACTIONS[1117])
        play(world, arc, 1118, ACTIONS["request_full"])
        final = world.deliver(arc, "ywc_dmg.1119")
        state = world.countries[world.tag]
        # These unrelated delivery records are collision probes after the real
        # final receipt; none is used to progress or qualify this crown arc.
        unrelated = {"ywc_dmg_school_pending_event": 1120,
                     "ywc_dmg_market_pending_event": 1100,
                     "ywc_v03_dmg_inline_reservation": 55,
                     "ywc_v03_dmg_inline_live_v03_dmg_school_languages": 1}
        state.update(unrelated)
        choose(world, arc, final, ACTIONS["close_full"])
        self.assert_closed(world, 1)
        self.assertEqual({key: state.get(key) for key in unrelated}, unrelated)
        before = copy.deepcopy((state, world.treasury, world.active, world.history))
        for key in (ACTIONS["close_full"], ACTIONS["withdraw"], ACTIONS["recount"]):
            force_option(world, final, key)
        world.run("ywc_dmg_crown_release_once", world.tag)
        self.assertEqual((state, world.treasury, world.active, world.history), before)

    def test_all_ten_cached_events_including_wait_and_exit_buttons_are_inert_after_close(self):
        world = new_world()
        arc = crown_arc(world.cat)
        cached = []
        for number in range(1110, 1117):
            cached.append(play(world, arc, number,
                               ROUTES["constitutional"] if number == 1110 else ACTIONS[number]))
        month(world, arc, 6)
        for number, action in ((1117, ACTIONS[1117]), (1118, ACTIONS["request_full"]),
                               (1119, ACTIONS["close_full"])):
            cached.append(play(world, arc, number, action))
        self.assertEqual(len(cached), 10)
        self.assert_closed(world, 1)
        state = world.countries[world.tag]
        before = copy.deepcopy((state, world.treasury, world.active, world.history))
        for event in cached:
            for name, _, body in event:
                if name == "option":
                    key = field(body, "name").rsplit(".", 1)[-1]
                    self.assertFalse(option_legal(world, event, key), (field(event, "title"), key))
                    force_option(world, event, key)
        self.assertEqual((state, world.treasury, world.active, world.history), before)
