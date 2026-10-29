"""Actual SHU public-deliberation source; never synthesize a business result."""
import copy
import unittest

from shu_public_runtime import ShuPublicWorld
from shu_kor_strict_review_runtime import field
from test_v03_shu_public_runtime import public_facts
from test_v03_shu_provincial_contract import (
    choose as _choose, force_option as _force_option, option_legal as _option_legal,
)


SLUG = "v03_shu_public_deliberation"
JES = ("ywc_je_v03_shu_deliberation_eligibility",
       "ywc_je_v03_shu_deliberation_appeal_execution")
P = "ywc_shu_delib_"
L = "ywc_v03_shu_v03_shu_public_deliberation_"
ROUTES = {"court": "court_consultation", "property": "property_representation",
          "sealed": "sealed_appeal"}
RELEASE_EFFECT = "ywc_v03_release_arc_shu_v03_shu_public_deliberation"


def _actual_option_key(event, key):
    keys = [field(body, "name").rsplit(".", 1)[-1] for name, _, body in event if name == "option"]
    if key in keys:
        return key
    if key == "withdraw":
        matches = [name for name in keys if name.startswith("withdraw_at_")]
        if len(matches) == 1:
            return matches[0]
    if key == "recount" and "recount_from_close" in keys:
        return "recount_from_close"
    return key


def choose(world, arc, event, key):
    return _choose(world, arc, event, _actual_option_key(event, key))


def force_option(world, event, key):
    return _force_option(world, event, _actual_option_key(event, key))


def option_legal(world, event, key):
    return _option_legal(world, event, _actual_option_key(event, key))


def current_facts(route="court", bare=False):
    if route not in ROUTES:
        raise ValueError(route)
    state = public_facts()
    controlled = {"law_monarchy", "law_presidential_republic", "law_parliamentary_republic",
                  "law_appointed_bureaucrats", "law_elected_bureaucrats", "law_hereditary_bureaucrats",
                  "law_wealth_voting", "law_census_voting", "law_universal_suffrage",
                  "law_autocracy", "law_oligarchy", "law_censorship", "law_right_of_assembly",
                  "law_protected_speech", "law_outlawed_dissent"}
    state["laws"] = [law for law in state["laws"] if law not in controlled]
    state["laws"] += {
        "court": ["law_monarchy", "law_appointed_bureaucrats", "law_censorship"],
        "property": ["law_monarchy", "law_census_voting", "law_right_of_assembly"],
        "sealed": ["law_monarchy", "law_autocracy", "law_censorship"],
    }[route]
    state["country_has_voting_franchise"] = route == "property"
    state["igs"] = [{"type": kind, "in_government": True, "clout": .10, "approval": 0}
                    for kind in ("ig_intelligentsia", "ig_industrialists", "ig_rural_folk",
                                 "ig_landowners", "ig_armed_forces", "ig_devout",
                                 "ig_petty_bourgeoisie", "ig_trade_unions")]
    province = state["states"][0]
    local_office = next(building for building in province["buildings"]
                        if building["type"] == "building_government_administration")
    # A new full witness needs .8 even where the selected policy needs only .5.
    local_office["occupancy"] = .8
    if bare:
        state["laws"] = ["law_monarchy", "law_autocracy", "law_outlawed_dissent",
                         "law_no_schools", "law_serfdom"]
        state["institutions"] = {"institution_schools": 0}
        state["country_has_voting_franchise"] = False
        local_office["occupancy"] = .25
        province["buildings"] = [local_office]
        province["pops"] = [province["pops"][0]]
        for group in state["igs"]:
            group["in_government"] = False
    return state


def new_world(route="court", bare=False):
    world = ShuPublicWorld()
    world.countries["SHU"] = current_facts(route, bare)
    world.run("ywc_v03_initialize_country", "SHU")
    return world


def deliberation_arc(catalog):
    return next(arc for arc in catalog["arcs"] if arc["slug"] == SLUG)


def play(world, arc, number, key):
    event = world.deliver(arc, f"ywc_shu.{number}")
    choose(world, arc, event, key)
    return event


def month(world, arc, count=1):
    for _ in range(count):
        world.advance_months(1)
        world.elapsed_months += 1
        world.pulse(arc)


def office(world, index=0):
    return next(building for building in world.countries[world.tag]["states"][index]["buildings"]
                if building["type"] == "building_government_administration")


def office_pop(world, index=0):
    return next(pop for pop in world.countries[world.tag]["states"][index]["pops"]
                if pop["type"] == "bureaucrats")


def group(world, kind):
    return next(ig for ig in world.countries[world.tag]["igs"] if ig["type"] == kind)


def world_facts(world):
    state = world.countries[world.tag]
    return copy.deepcopy({key: state[key] for key in
        ("laws", "igs", "states", "institutions", "literacy_rate", "bureaucracy",
         "legitimacy", "authority", "net_fixed_income", "is_at_war", "in_default")})


def ready_for_review(world, route="court", limited=False, witness=None):
    """Fresh real1120..1124 choices, ending at continuous observation1125."""
    arc = deliberation_arc(world.cat)
    play(world, arc, 1120, "limited_appeal" if limited else ROUTES[route])
    play(world, arc, 1121, "pay_register")
    play(world, arc, 1122, witness or ("local_witness" if limited else "new_witness"))
    play(world, arc, 1123, "sign_budget")
    play(world, arc, 1124, "register_local_appeal" if limited else
         "register_sealed_appeal" if route == "sealed" else "register_public_appeal")
    assert world.history[world.tag][JES[0]] == "complete"
    assert JES[1] in world.active[world.tag]
    return arc


def finish_review(world, arc, outcome=1):
    """Actual mature payment/request/close for full1 or explicitly limited2."""
    suffix = {1: "full", 2: "limited"}[outcome]
    action = "advance_paid_review" if P + "review_paid" in world.countries[world.tag] else "pay_review"
    play(world, arc, 1125, action)
    play(world, arc, 1126, "request_" + suffix)
    play(world, arc, 1127, "close_" + suffix)


class ShuPublicDeliberation(unittest.TestCase):
    def assert_capacity(self, world, expected):
        state = world.countries[world.tag]
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]),
                         (expected, expected))

    def assert_closed(self, world, outcome, remaining=0):
        state = world.countries[world.tag]
        self.assertEqual(state[P + "outcome"], outcome)
        self.assertEqual(state[L + "outcome"], outcome)
        self.assertEqual(state[L + "settled"], 1)
        self.assert_capacity(world, remaining)
        self.assertFalse(any(journal in world.active[world.tag] for journal in JES))

    def assert_paid(self, world, register, review):
        state = world.countries[world.tag]
        for bill, expected in (("register", register), ("review", review)):
            self.assertEqual(state[P + bill + "_paid"], 1)
            self.assertEqual(state[P + bill + "_paid_amount"], expected)
            self.assertGreater(state[P + bill + "_paid_amount"], 0)

    def test_actual_catalog_contains_the_approved_eight_event_two_journal_card(self):
        world = new_world()
        self.assertIn(SLUG, [arc["slug"] for arc in world.cat["arcs"]])
        arc = deliberation_arc(world.cat)
        self.assertEqual([event["id"] for event in arc["events"]],
                         [f"ywc_shu.{number}" for number in range(1120, 1128)])
        self.assertEqual([journal["id"] for journal in arc["journals"]], list(JES))

    def test_three_complete_policies_pay_two_distinct_real_bills_without_world_grants(self):
        for route, amount in (("court", 1000), ("property", 1500), ("sealed", 500)):
            with self.subTest(route=route):
                world = new_world(route)
                original = world_facts(world)
                original_modifiers = copy.deepcopy(world.modifiers)
                arc = ready_for_review(world, route)
                state = world.countries[world.tag]
                self.assertEqual((state[P + "phase"], state[P + "stage"]), (2, 1125))
                self.assertEqual(state[P + "target"], 1)
                self.assert_capacity(world, 1)
                self.assertEqual(world.treasury[world.tag], -amount)
                month(world, arc, 6)
                finish_review(world, arc)
                self.assert_paid(world, amount, amount)
                self.assertEqual(world.treasury[world.tag], -2 * amount)
                self.assert_closed(world, 1)
                self.assertTrue(all(world.history[world.tag][journal] == "complete" for journal in JES))
                self.assertEqual(world_facts(world), original)
                self.assertEqual(world.modifiers, original_modifiers)

    def test_explicit_finite_has_real_quarter_office_and_needs_no_old_story_school_or_group(self):
        for regime in (("law_monarchy", "law_autocracy"),
                       ("law_presidential_republic", "law_universal_suffrage")):
            with self.subTest(regime=regime):
                world = new_world(bare=True)
                state = world.countries[world.tag]
                state["laws"] = list(regime) + ["law_outlawed_dissent", "law_no_schools", "law_serfdom"]
                state["legitimacy"] = 20
                original = world_facts(world)
                arc = ready_for_review(world, limited=True)
                self.assertEqual((state[P + "mode"], state[P + "target"]), (3, 2))
                self.assertEqual(len(state["states"][0]["buildings"]), 1)
                month(world, arc, 6)
                finish_review(world, arc, outcome=2)
                self.assert_closed(world, 2)
                self.assert_paid(world, 500, 500)
                self.assertEqual(world.treasury[world.tag], -1000)
                self.assertEqual(world_facts(world), original)

    def test_complete_choices_use_their_distinct_current_laws_and_staffing(self):
        cases = (("court", "law_monarchy", "law_presidential_republic", .79),
                 ("court", "law_appointed_bureaucrats", "law_elected_bureaucrats", .79),
                 ("property", "law_census_voting", "law_autocracy", .49),
                 ("property", "law_right_of_assembly", "law_censorship", .49),
                 ("sealed", "law_autocracy", "law_census_voting", .49),
                 ("sealed", "law_censorship", "law_protected_speech", .49))
        for route, actual_law, wrong_law, low_staff in cases:
            for loss in ("law", "staff"):
                with self.subTest(route=route, law=actual_law, loss=loss):
                    world = new_world(route)
                    arc = deliberation_arc(world.cat)
                    event = world.deliver(arc, "ywc_shu.1120")
                    self.assertTrue(option_legal(world, event, ROUTES[route]))
                    state = world.countries[world.tag]
                    if loss == "law":
                        state["laws"].remove(actual_law)
                        state["laws"].append(wrong_law)
                    else:
                        office(world)["occupancy"] = low_staff
                    self.assertFalse(option_legal(world, event, ROUTES[route]))
                    before = copy.deepcopy((state, world.treasury))
                    force_option(world, event, ROUTES[route])
                    self.assertEqual((state, world.treasury), before)

    def test_policy_specific_bureaucracy_income_authority_and_legitimacy_are_current(self):
        cases = (("court", "bureaucracy", -1), ("court", "legitimacy", 24),
                 ("property", "net_fixed_income", -1), ("property", "legitimacy", 24),
                 ("sealed", "authority", 49), ("sealed", "legitimacy", 24))
        for route, fact, value in cases:
            with self.subTest(route=route, fact=fact):
                world = new_world(route)
                arc = deliberation_arc(world.cat)
                event = world.deliver(arc, "ywc_shu.1120")
                self.assertTrue(option_legal(world, event, ROUTES[route]))
                world.countries[world.tag][fact] = value
                self.assertFalse(option_legal(world, event, ROUTES[route]))

    def test_government_clout_and_approval_must_be_satisfied_by_the_same_supporter(self):
        for route, kind in (("court", "ig_intelligentsia"), ("property", "ig_industrialists"),
                            ("sealed", "ig_landowners")):
            with self.subTest(route=route):
                world = new_world(route)
                arc = deliberation_arc(world.cat)
                event = world.deliver(arc, "ywc_shu.1120")
                self.assertTrue(option_legal(world, event, ROUTES[route]))
                state = world.countries[world.tag]
                for ig in state["igs"]:
                    ig["in_government"] = False
                sponsor = group(world, kind)
                sponsor.update(in_government=False, clout=.2, approval=1)
                split = {**sponsor, "in_government": True, "clout": .099}
                state["igs"].append(split)
                self.assertFalse(option_legal(world, event, ROUTES[route]))
                split.update(clout=.10, approval=-1)
                self.assertFalse(option_legal(world, event, ROUTES[route]))
                split["approval"] = 0
                self.assertTrue(option_legal(world, event, ROUTES[route]))

    def test_claim_uses_first_owned_region_and_never_silently_reselects_after_loss(self):
        regions = ("s:STATE_SICHUAN", "s:STATE_CHONGQING", "s:STATE_YUNNAN", "s:STATE_GUIZHOU")
        for selected in range(4):
            with self.subTest(selected=selected + 1):
                world = new_world()
                state = world.countries[world.tag]
                template = state["states"][0]
                states = []
                for index, region in enumerate(regions):
                    province = copy.deepcopy(template)
                    province.update(region=region, owner="CHI" if index < selected else "SHU")
                    states.append(province)
                # Reversing enumeration must not override the explicit priority.
                state["states"] = list(reversed(states))
                arc = deliberation_arc(world.cat)
                play(world, arc, 1120, ROUTES["court"])
                self.assertEqual(state[P + "pilot"], selected + 1)
                states[selected]["owner"] = "CHI"
                event = world.deliver(arc, "ywc_shu.1121")
                self.assertFalse(option_legal(world, event, "pay_register"))
                self.assertEqual(state[P + "pilot"], selected + 1)
                choose(world, arc, event, "withdraw")
                self.assert_closed(world, 4)

    def test_real_employment_in_original_office_is_required_without_culture_gate(self):
        for route in ROUTES:
            for defect in ("unemployed", "wrong_workplace", "shortage"):
                with self.subTest(route=route, defect=defect):
                    world = new_world(route)
                    arc = deliberation_arc(world.cat)
                    event = world.deliver(arc, "ywc_shu.1120")
                    self.assertTrue(option_legal(world, event, ROUTES[route]))
                    province = world.countries[world.tag]["states"][0]
                    other = copy.deepcopy(province)
                    other["region"] = "s:STATE_CHONGQING"
                    foreign = copy.deepcopy(province)
                    foreign["owner"] = "CHI"
                    world.countries[world.tag]["states"].extend((other, foreign))
                    if defect == "unemployed":
                        office_pop(world)["employed"] = False
                    elif defect == "wrong_workplace":
                        office_pop(world)["workplace"] = next(b for b in province["buildings"]
                                                              if b["type"] == "building_maize_farm")
                    else:
                        office(world)["shortage"] = True
                    self.assertFalse(option_legal(world, event, ROUTES[route]))
        for primary, acceptance in ((True, 5), (False, 4)):
            world = new_world()
            office_pop(world).update(primary=primary, acceptance=acceptance)
            arc = ready_for_review(world)
            month(world, arc, 6)
            finish_review(world, arc)
            self.assert_closed(world, 1)

    def test_zero_missing_mode_target_phase_stage_or_private_receipt_never_pays(self):
        for payment in (1121, 1125):
            for field_name in ("mode", "target", "phase", "stage", "last_event"):
                for bad in (None, 0):
                    with self.subTest(payment=payment, field=field_name, bad=bad):
                        world = new_world()
                        arc = deliberation_arc(world.cat)
                        if payment == 1121:
                            play(world, arc, 1120, ROUTES["court"])
                        else:
                            arc = ready_for_review(world)
                            month(world, arc, 6)
                        event = world.deliver(arc, f"ywc_shu.{payment}")
                        action = "pay_register" if payment == 1121 else "pay_review"
                        self.assertTrue(option_legal(world, event, action))
                        state = world.countries[world.tag]
                        name = P + field_name
                        self.assertIn(name, state)
                        if bad is None:
                            del state[name]
                        else:
                            state[name] = bad
                        self.assertFalse(option_legal(world, event, action))
                        before = copy.deepcopy((state, world.treasury, world.active, world.history))
                        force_option(world, event, action)
                        self.assertEqual((state, world.treasury, world.active, world.history), before)

    def test_actual_event_number_receipt_does_not_accept_an_ordinal_or_another_stage(self):
        world = new_world()
        arc = deliberation_arc(world.cat)
        play(world, arc, 1120, ROUTES["court"])
        event = world.deliver(arc, "ywc_shu.1121")
        state = world.countries[world.tag]
        self.assertEqual(state[P + "last_event"], 1121)
        for bad in (2, 1120, 1127):
            state[P + "last_event"] = bad
            self.assertFalse(option_legal(world, event, "pay_register"))
            before = copy.deepcopy((state, world.treasury))
            force_option(world, event, "pay_register")
            self.assertEqual((state, world.treasury), before)

    def test_both_real_payments_check_exact_cash_default_bankruptcy_and_current_law(self):
        for payment in (1121, 1125):
            for denial in ("cash", "default", "bankruptcy", "law"):
                with self.subTest(payment=payment, denial=denial):
                    world = new_world()
                    arc = deliberation_arc(world.cat)
                    if payment == 1121:
                        play(world, arc, 1120, ROUTES["court"])
                    else:
                        arc = ready_for_review(world)
                        month(world, arc, 6)
                    event = world.deliver(arc, f"ywc_shu.{payment}")
                    action = "pay_register" if payment == 1121 else "pay_review"
                    state = world.countries[world.tag]
                    state["gold_reserves"] = 1000 - world.treasury[world.tag]
                    self.assertTrue(option_legal(world, event, action))
                    if denial == "cash":
                        state["gold_reserves"] -= .01
                    elif denial == "default":
                        state["in_default"] = True
                    elif denial == "bankruptcy":
                        world.modifiers.append((world.tag, {"modifier": "declared_bankruptcy"}))
                    else:
                        state["laws"].remove("law_appointed_bureaucrats")
                        state["laws"].append("law_elected_bureaucrats")
                    self.assertFalse(option_legal(world, event, action))
                    before = copy.deepcopy((state, world.treasury, world.modifiers))
                    force_option(world, event, action)
                    self.assertEqual((state, world.treasury, world.modifiers), before)

    def test_claim_captures_budget_once_with_a_real_hundred_minimum(self):
        for gross, total in ((52000, 2000), (0, 200)):
            with self.subTest(gross=gross):
                world = new_world()
                state = world.countries[world.tag]
                state["yearly_gross_income"] = gross
                arc = deliberation_arc(world.cat)
                play(world, arc, 1120, ROUTES["court"])
                state["yearly_gross_income"] = 520000
                for number, key in ((1121, "pay_register"), (1122, "new_witness"),
                                    (1123, "sign_budget"), (1124, "register_public_appeal")):
                    play(world, arc, number, key)
                month(world, arc, 6)
                finish_review(world, arc)
                self.assertEqual(world.treasury[world.tag], -total)
                self.assert_closed(world, 1)

    def test_witness_does_not_finish_first_journal_and_real_appeal_starts_observation(self):
        world = new_world()
        arc = deliberation_arc(world.cat)
        for number, key in ((1120, ROUTES["court"]), (1121, "pay_register"), (1122, "new_witness")):
            play(world, arc, number, key)
        state = world.countries[world.tag]
        self.assertIn(P + "phase", state)
        self.assertEqual((state[P + "phase"], state[P + "stage"]), (1, 1123))
        self.assertIn(JES[0], world.active[world.tag])
        self.assertNotIn(JES[1], world.history[world.tag])
        self.assertNotIn(P + "review_running", state)
        play(world, arc, 1123, "sign_budget")
        self.assertEqual((state[P + "phase"], state[P + "stage"]), (2, 1124))
        self.assertNotIn(P + "review_running", state)
        play(world, arc, 1124, "register_public_appeal")
        self.assertEqual(state[P + "stage"], 1125)
        self.assertEqual(state[P + "review_running"], 1)
        self.assertEqual(state[P + "review_streak"], 0)

    def test_half_staffed_property_policy_cannot_substitute_for_new_full_witness(self):
        world = new_world("property")
        office(world)["occupancy"] = .5
        arc = deliberation_arc(world.cat)
        play(world, arc, 1120, ROUTES["property"])
        play(world, arc, 1121, "pay_register")
        event = world.deliver(arc, "ywc_shu.1122")
        self.assertFalse(option_legal(world, event, "reuse_local_witness"))
        self.assertFalse(option_legal(world, event, "new_witness"))
        self.assertFalse(option_legal(world, event, "local_witness"))
        office(world)["occupancy"] = .8
        choose(world, arc, event, "new_witness")
        budget = world.deliver(arc, "ywc_shu.1123")
        self.assertTrue(option_legal(world, budget, "sign_budget"))
        office(world)["occupancy"] = .5
        self.assertFalse(option_legal(world, budget, "sign_budget"))
        state = world.countries[world.tag]
        before = copy.deepcopy((state, world.treasury))
        force_option(world, budget, "sign_budget")
        self.assertEqual((state, world.treasury), before)
        office(world)["occupancy"] = .8
        for snapshot in ("witness_mode", "witness_target", "witness_pilot"):
            probe = copy.deepcopy(world)
            saved = probe.countries[probe.tag]
            self.assertIn(P + snapshot, saved)
            saved[P + snapshot] = 0
            self.assertFalse(option_legal(probe, budget, "sign_budget"))
            before = copy.deepcopy((saved, probe.treasury))
            force_option(probe, budget, "sign_budget")
            self.assertEqual((saved, probe.treasury), before)
        choose(world, arc, budget, "sign_budget")
        self.assertEqual(world.history[world.tag][JES[0]], "complete")

    def test_all_routes_creation_day_duplicate_and_five_vs_six_months_are_real(self):
        for route, limited in (("court", False), ("property", False), ("sealed", False), ("court", True)):
            with self.subTest(route=route, limited=limited):
                world = new_world(route, bare=limited)
                arc = ready_for_review(world, route, limited=limited)
                state = world.countries[world.tag]
                for _ in range(3):
                    world.pulse(arc)
                self.assertEqual(state[P + "review_streak"], 0)
                for count in range(1, 6):
                    month(world, arc)
                    self.assertEqual(state[P + "review_streak"], count)
                    world.pulse(arc)
                    self.assertEqual(state[P + "review_streak"], count)
                    self.assertNotIn(P + "review_mature", state)
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 6)
                self.assertEqual(state[P + "review_mature"], 1)

    def test_war_default_bankruptcy_pilot_law_group_and_real_post_loss_need_explicit_restart(self):
        for loss in ("war", "default", "bankruptcy", "pilot", "law", "government", "clout", "approval", "employment"):
            with self.subTest(loss=loss):
                world = new_world()
                arc = ready_for_review(world)
                state = world.countries[world.tag]
                actual = world_facts(world)
                modifiers = copy.deepcopy(world.modifiers)
                month(world, arc, 4)
                if loss == "war": state["is_at_war"] = True
                elif loss == "default": state["in_default"] = True
                elif loss == "bankruptcy": world.modifiers.append((world.tag, {"modifier": "declared_bankruptcy"}))
                elif loss == "pilot": state["states"][0]["owner"] = "CHI"
                elif loss == "law": state["laws"].remove("law_appointed_bureaucrats")
                elif loss == "government": group(world, "ig_intelligentsia")["in_government"] = False
                elif loss == "clout": group(world, "ig_intelligentsia")["clout"] = .099
                elif loss == "approval": group(world, "ig_intelligentsia")["approval"] = -1
                else: office_pop(world)["employed"] = False
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 0)
                self.assertEqual(state[P + "review_interrupted"], 1)
                self.assertNotIn(P + "review_running", state)
                self.assertNotIn(P + "review_mature", state)
                state.update(copy.deepcopy(actual))
                world.modifiers = modifiers
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 0)
                event = world.deliver(arc, "ywc_shu.1125")
                self.assertFalse(option_legal(world, event, "pay_review"))
                choose(world, arc, event, "restart_review")
                self.assertEqual(state[P + "review_streak"], 0)
                month(world, arc, 5)
                self.assertNotIn(P + "review_mature", state)
                month(world, arc)
                finish_review(world, arc)
                self.assert_closed(world, 1)

    def test_both_late_recounts_need_six_new_months_and_never_charge_paid_fees_again(self):
        for late in (1126, 1127):
            with self.subTest(late=late):
                world = new_world()
                arc = ready_for_review(world)
                month(world, arc, 6)
                play(world, arc, 1125, "pay_review")
                if late == 1127:
                    play(world, arc, 1126, "request_full")
                event = world.deliver(arc, f"ywc_shu.{late}")
                state = world.countries[world.tag]
                self.assertEqual(world.treasury[world.tag], -2000)
                choose(world, arc, event, "recount")
                self.assertEqual(state[P + "stage"], 1125)
                self.assertEqual(state[P + "review_streak"], 0)
                self.assertNotIn(P + "review_mature", state)
                self.assertNotIn(P + "request", state)
                state["gold_reserves"] = -world.treasury[world.tag]
                month(world, arc, 5)
                self.assertNotIn(P + "review_mature", state)
                month(world, arc)
                finish_review(world, arc)
                self.assert_closed(world, 1)
                self.assert_paid(world, 1000, 1000)
                self.assertEqual(world.treasury[world.tag], -2000)

    def test_setback_requires_paid_maturity_and_current_failure_and_rechecks_recovery(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        future = world.event_defs["ywc_shu.1126"]
        self.assertFalse(option_legal(world, future, "request_setback"))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, future, "request_setback")
        self.assertEqual((state, world.treasury), before)
        month(world, arc, 6)
        play(world, arc, 1125, "pay_review")
        event = world.deliver(arc, "ywc_shu.1126")
        self.assertFalse(option_legal(world, event, "request_setback"))
        self.assertTrue(option_legal(world, event, "request_full"))
        state["is_at_war"] = True
        month(world, arc)
        self.assertEqual(state[P + "stage"], 1126)
        self.assertIn(state.get(P + "pending_event"), (None, 1126))
        self.assertEqual(state[P + "review_streak"], 6)
        self.assertEqual(state[P + "review_mature"], 1)
        self.assertNotIn(P + "review_running", state)
        self.assertFalse(option_legal(world, event, "request_full"))
        choose(world, arc, event, "request_setback")
        final = world.deliver(arc, "ywc_shu.1127")
        self.assertTrue(option_legal(world, final, "close_setback"))
        state["is_at_war"] = False
        self.assertFalse(option_legal(world, final, "close_setback"))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, final, "close_setback")
        self.assertEqual((state, world.treasury), before)
        state["is_at_war"] = True
        choose(world, arc, final, "close_setback")
        self.assert_closed(world, 3)
        self.assertEqual(world.history[world.tag][JES[1]], "complete")
        self.assertEqual(world.treasury[world.tag], -2000)

    def test_explicit_finite_resigning_updates_real_duties_and_blocks_old_full_buttons(self):
        world = new_world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1125, "pay_review")
        old_request = world.deliver(arc, "ywc_shu.1126")
        self.assertTrue(option_legal(world, old_request, "request_full"))
        choose(world, arc, old_request, "recount")
        state = world.countries[world.tag]
        state["laws"].remove("law_appointed_bureaucrats")
        office(world)["occupancy"] = .25
        original = world_facts(world)
        month(world, arc)
        event = world.deliver(arc, "ywc_shu.1125")
        self.assertFalse(option_legal(world, event, "restart_review"))
        choose(world, arc, event, "narrow_and_recount")
        self.assertEqual(state[P + "target"], 2)
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertNotIn(P + "review_mature", state)
        self.assertNotIn(P + "request", state)
        for snapshot in ("witness_target", "sign_target", "accept_target"):
            self.assertEqual(state[P + snapshot], 2)
        self.assertEqual(world_facts(world), original)
        self.assertEqual(world.treasury[world.tag], -2000)
        before = copy.deepcopy((state, world.treasury))
        force_option(world, old_request, "request_full")
        self.assertEqual((state, world.treasury), before)
        month(world, arc, 5)
        self.assertNotIn(P + "review_mature", state)
        month(world, arc)
        play(world, arc, 1125, "advance_paid_review")
        current = world.deliver(arc, "ywc_shu.1126")
        self.assertFalse(option_legal(world, current, "request_full"))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, old_request, "request_full")
        self.assertEqual((state, world.treasury), before)
        choose(world, arc, current, "request_limited")
        play(world, arc, 1127, "close_limited")
        self.assert_closed(world, 2)
        self.assert_paid(world, 1000, 1000)
        self.assertEqual(world_facts(world), original)

    def test_every_cached_option_including_withdraw_is_inert_at_each_later_stage(self):
        world = new_world()
        arc = deliberation_arc(world.cat)
        cached = []
        path = ((1120, ROUTES["court"]), (1121, "pay_register"), (1122, "new_witness"),
                (1123, "sign_budget"), (1124, "register_public_appeal"),
                (1125, "pay_review"), (1126, "request_full"), (1127, "close_full"))
        for number, action in path:
            if number == 1125:
                month(world, arc, 6)
            current = world.deliver(arc, f"ywc_shu.{number}")
            state = world.countries[world.tag]
            # The CURRENT event really has its own valid receipt here. This
            # catches an old withdraw delegating to a generic live-stage guard.
            before = copy.deepcopy((state, world.treasury, world.active, world.history, world.events))
            for old_event in cached:
                for name, _, body in old_event:
                    if name == "option":
                        key = field(body, "name").rsplit(".", 1)[-1]
                        self.assertFalse(option_legal(world, old_event, key), (number, key))
                        force_option(world, old_event, key)
            self.assertEqual((state, world.treasury, world.active, world.history, world.events), before)
            # Negative probes are copies of a genuinely delivered world; the
            # original receipt/phase is never forged or restored to progress.
            for required in ("phase", "last_event"):
                for bad in (None, 0):
                    probe = copy.deepcopy(world)
                    probe_state = probe.countries[probe.tag]
                    self.assertIn(P + required, probe_state, (number, required))
                    if bad is None:
                        del probe_state[P + required]
                    else:
                        probe_state[P + required] = bad
                    untouched = copy.deepcopy((probe_state, probe.treasury, probe.active,
                                               probe.history, probe.events))
                    for name, _, body in current:
                        if name == "option":
                            key = field(body, "name").rsplit(".", 1)[-1]
                            self.assertFalse(option_legal(probe, current, key), (number, required, bad, key))
                            force_option(probe, current, key)
                    self.assertEqual((probe_state, probe.treasury, probe.active, probe.history,
                                      probe.events), untouched)
            choose(world, arc, current, action)
            cached.append(current)
            before = copy.deepcopy((state, world.treasury, world.active, world.history, world.events))
            for old_event in cached:
                for name, _, body in old_event:
                    if name != "option":
                        continue
                    key = field(body, "name").rsplit(".", 1)[-1]
                    self.assertFalse(option_legal(world, old_event, key), (number, key))
                    force_option(world, old_event, key)
            self.assertEqual((state, world.treasury, world.active, world.history, world.events), before)
        self.assertEqual(len(cached), 8)
        self.assert_closed(world, 1)

    def test_sign_then_immediate_pilot_loss_and_full_capacity_still_handoff_and_exit(self):
        for capacity in (1, 3):
            with self.subTest(capacity=capacity):
                world = new_world()
                arc = deliberation_arc(world.cat)
                for number, action in ((1120, ROUTES["court"]), (1121, "pay_register"),
                                       (1122, "new_witness")):
                    play(world, arc, number, action)
                event = world.deliver(arc, "ywc_shu.1123")
                self.assertTrue(option_legal(world, event, "sign_budget"))
                force_option(world, event, "sign_budget")
                state = world.countries[world.tag]
                state["states"][0]["owner"] = "CHI"
                # Literal shared-capacity boundary, representing other agenda
                # reservations; it does not manufacture this arc's signature.
                state["ywc_v03_active_arc_count"] = capacity
                state["ywc_v03_visible_task_count"] = capacity
                world.refresh(arc)
                self.assertEqual(world.history[world.tag][JES[0]], "complete")
                self.assertIn(JES[1], world.active[world.tag])
                self.assertEqual((state[P + "phase"], state[P + "stage"]), (2, 1124))
                self.assert_capacity(world, capacity)
                appeal = world.deliver(arc, "ywc_shu.1124")
                self.assertFalse(option_legal(world, appeal, "register_public_appeal"))
                self.assertTrue(option_legal(world, appeal, "withdraw"))
                choose(world, arc, appeal, "withdraw")
                self.assert_closed(world, 4, remaining=capacity - 1)
                self.assertEqual(world.history[world.tag][JES[1]], "failed")

    def test_final_full_button_rechecks_current_law_support_employment_and_pilot(self):
        for loss in ("law", "government", "employment", "pilot"):
            with self.subTest(loss=loss):
                world = new_world()
                arc = ready_for_review(world)
                month(world, arc, 6)
                play(world, arc, 1125, "pay_review")
                play(world, arc, 1126, "request_full")
                event = world.deliver(arc, "ywc_shu.1127")
                self.assertTrue(option_legal(world, event, "close_full"))
                state = world.countries[world.tag]
                if loss == "law": state["laws"].remove("law_appointed_bureaucrats")
                elif loss == "government": group(world, "ig_intelligentsia")["in_government"] = False
                elif loss == "employment": office_pop(world)["employed"] = False
                else: state["states"][0]["owner"] = "CHI"
                self.assertFalse(option_legal(world, event, "close_full"))
                before = copy.deepcopy((state, world.treasury))
                force_option(world, event, "close_full")
                self.assertEqual((state, world.treasury), before)
                choose(world, arc, event, "withdraw")
                self.assert_closed(world, 4)

    def test_release_once_preserves_real_other_arc_capacity_queue_and_live_reservation(self):
        world = new_world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1125, "pay_review")
        play(world, arc, 1126, "request_full")
        final = world.deliver(arc, "ywc_shu.1127")
        old_arc = next(row for row in world.cat["arcs"] if row["slug"] == "v03_shu_fiscal_register")
        world.refresh(old_arc)
        self.assert_capacity(world, 2)
        world.advance_days(90)
        world.pulse(old_arc)
        state = world.countries[world.tag]
        self.assertTrue(any(eid == "ywc_shu.1000" for _, eid in world.events))
        self.assertEqual(state["ywc_v03_shu_inline_reservation"], 1)
        witness = old_arc["inline_delivery_adapter"]["live_phases"][0]["live_witness"]
        retained = {name: state.get(name) for name in
                    ("ywc_shu_pending_event", "ywc_v03_shu_inline_reservation", witness)}
        self.assertEqual(retained["ywc_shu_pending_event"], 1000)
        self.assertEqual(retained[witness], 1)
        choose(world, arc, final, "close_full")
        self.assert_closed(world, 1, remaining=1)
        self.assertEqual({name: state.get(name) for name in retained}, retained)
        before = copy.deepcopy((state, world.treasury, world.active, world.history, world.events))
        for name, _, body in final:
            if name == "option":
                force_option(world, final, field(body, "name").rsplit(".", 1)[-1])
        world.run(RELEASE_EFFECT, world.tag)
        self.assertEqual((state, world.treasury, world.active, world.history, world.events), before)
