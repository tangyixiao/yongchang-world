"""KOR court-public business contracts against actual generated inline source."""
import copy
import unittest

from clausewitz_harness import parse
from kor_public_runtime import KorPublicWorld
from test_v03_kor_provincial_revenue import current_facts as revenue_facts
from test_v03_shu_provincial_contract import choose as native_choose, force_option as native_force, option_legal as native_legal
from shu_kor_strict_review_runtime import field
from kor_partner_protocol_runtime import StateRef


SLUG = "v03_kor_court_public"
P = "ywc_kor_public_"
L = "ywc_v03_kor_v03_kor_court_public_"
R = L + "last_event"
JES = ("ywc_je_v03_kor_court_public_deliberation", "ywc_je_v03_kor_court_public_review")
ROUTES = {"court": "court_open", "local": "local_delegates", "conservative": "conservative_petition"}
CHANNELS = {"court": "court_read_reply", "local": "local_open_reply", "conservative": "sealed_royal_reply"}
RELEASE_EFFECT = P + "release_once"


def current_facts(route="court", bare=False):
    if route not in ROUTES:
        raise ValueError(route)
    state = revenue_facts("provincial", bare)
    state["movements"] = []
    political = {"law_monarchy", "law_presidential_republic", "law_parliamentary_republic",
                 "law_appointed_bureaucrats", "law_elected_bureaucrats", "law_hereditary_bureaucrats",
                 "law_autocracy", "law_oligarchy", "law_technocracy", "law_wealth_voting",
                 "law_census_voting", "law_universal_suffrage", "law_censorship",
                 "law_outlawed_dissent", "law_right_of_assembly", "law_protected_speech"}
    state["laws"] = [law for law in state["laws"] if law not in political]
    state["laws"] += {
        "court": ["law_monarchy", "law_appointed_bureaucrats", "law_autocracy", "law_censorship"],
        "local": ["law_monarchy", "law_census_voting", "law_right_of_assembly"],
        "conservative": ["law_monarchy", "law_autocracy", "law_outlawed_dissent"],
    }[route]
    state["country_has_voting_franchise"] = route == "local"
    if route == "conservative" and not bare:
        next(b for b in state["states"][0]["buildings"]
             if b["type"] == "building_government_administration")["occupancy"] = .5
    return state


def new_world(route="court", bare=False, *, states=None, movements=None):
    facts = current_facts(route, bare)
    if states is not None:
        facts["states"] = states
    if movements is not None:
        facts["movements"] = movements
    world = KorPublicWorld(countries={"KOR": facts, "CHI": {"states": [], "movements": [], "igs": []}})
    world.run("ywc_v03_initialize_country", world.tag)
    return world


def court_arc(catalog):
    return next(arc for arc in catalog["arcs"] if arc["slug"] == SLUG)


def actual_key(event, key):
    keys = [field(body, "name").rsplit(".", 1)[-1] for name, _, body in event if name == "option"]
    if key in keys:
        return key
    if key == "withdraw":
        matches = [name for name in keys if name.startswith("withdraw_at_")]
        if len(matches) == 1:
            return matches[0]
    assert key in keys, ("missing_actual_option", key, tuple(keys))
    return key


def choose(world, arc, event, key):
    return native_choose(world, arc, event, actual_key(event, key))


def force_option(world, event, key):
    return native_force(world, event, actual_key(event, key))


def option_legal(world, event, key):
    return native_legal(world, event, actual_key(event, key))


def play(world, arc, number, key):
    event = world.deliver(arc, f"ywc_kor.{number}")
    choose(world, arc, event, key)
    return event


def month(world, arc, count=1):
    for _ in range(count):
        world.advance_months(1)  # PartnerWorld owns the elapsed-month increment.
        world.pulse(arc)


def office(world, index=0):
    return next(b for b in world.countries[world.tag]["states"][index]["buildings"]
                if b["type"] == "building_government_administration")


def office_pop(world, index=0):
    return next(p for p in world.countries[world.tag]["states"][index]["pops"]
                if p["type"] == "bureaucrats")


def group(world, kind):
    return next(ig for ig in world.countries[world.tag]["igs"] if ig["type"] == kind)


def world_facts(world):
    keys = ("laws", "states", "igs", "movements", "institutions", "bureaucracy", "legitimacy",
            "authority", "net_fixed_income", "is_at_war", "in_default", "country_has_voting_franchise")
    return copy.deepcopy({key: world.countries[world.tag][key] for key in keys})


def snapshot(world, kind):
    state = world.countries[world.tag]
    prefix = {"handler": "petition", "signature": "sign"}.get(kind, kind)
    pilot = "handler_pilot" if kind == "handler" else prefix + "_pilot"
    for name in (prefix + "_mode", prefix + "_target", pilot):
        assert P + name in state, ("missing_actual_snapshot", kind, name)
    return state[P + prefix + "_mode"], state[P + prefix + "_target"], state[P + pilot]


def ready_for_review(world, route="court", limited=False, witness=None):
    """Real1120..1124 choices; no ready/payment/snapshot/clock is injected."""
    arc = court_arc(world.cat)
    play(world, arc, 1120, "finite_petition" if limited else ROUTES[route])
    play(world, arc, 1121, "pay_petition")
    witness = witness or ("finite_clerk_witness" if limited else
                          "conservative_clerk_witness" if route == "conservative" else "new_professional_witness")
    play(world, arc, 1122, witness)
    play(world, arc, 1123, "sign_responsibility")
    event = world.deliver(arc, "ywc_kor.1124")
    if option_legal(world, event, "record_sealed_case_reply"):
        choose(world, arc, event, "record_sealed_case_reply")
        event = world.deliver(arc, "ywc_kor.1124")
    choose(world, arc, event, "bounded_clerk_reply" if limited else CHANNELS[route])
    assert world.history[world.tag][JES[0]] == "complete"
    assert JES[1] in world.active[world.tag]
    return arc


def finish_review(world, arc, outcome=1):
    action = "advance_paid_review" if P + "review_paid" in world.countries[world.tag] else "pay_review"
    play(world, arc, 1125, action)
    suffix = {1: "full", 2: "finite"}[outcome]
    play(world, arc, 1126, "request_" + suffix)
    play(world, arc, 1127, "close_" + suffix)


class KorCourtPublic(unittest.TestCase):
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

    def assert_paid(self, world, petition, review):
        state = world.countries[world.tag]
        for bill, amount in (("petition", petition), ("review", review)):
            self.assertEqual(state[P + bill + "_paid"], 1)
            self.assertEqual(state[P + bill + "_paid_amount"], amount)
            self.assertGreater(amount, 0)

    def test_declared_court_card_contract(self):
        world = new_world()
        self.assertIn(SLUG, [arc["slug"] for arc in world.cat["arcs"]])
        arc = court_arc(world.cat)
        self.assertEqual([event["id"] for event in arc["events"]], [f"ywc_kor.{n}" for n in range(1120, 1128)])
        self.assertEqual([journal["id"] for journal in arc["journals"]], list(JES))

    def test_all_three_full_policies_pay_two_real_bills_and_preserve_current_world(self):
        for route, petition, review in (("court", 1000, 1000), ("local", 2000, 1500),
                                         ("conservative", 500, 500)):
            with self.subTest(route=route):
                world = new_world(route)
                original = world_facts(world)
                modifiers = copy.deepcopy(world.modifiers)
                arc = ready_for_review(world, route)
                state = world.countries[world.tag]
                self.assertEqual((state[P + "mode"], state[P + "target"], state[P + "phase"], state[P + "stage"]),
                                 (list(ROUTES).index(route) + 1, 1, 2, 1125))
                self.assertEqual(world.treasury[world.tag], -petition)
                month(world, arc, 6)
                finish_review(world, arc)
                self.assert_paid(world, petition, review)
                self.assertEqual(world.treasury[world.tag], -petition - review)
                self.assert_closed(world, 1)
                self.assertEqual(world_facts(world), original)
                self.assertEqual(world.modifiers, modifiers)

    def test_explicit_finite_is_any_regime_without_school_industry_or_sponsoring_group(self):
        for laws in (("law_monarchy", "law_autocracy", "law_outlawed_dissent"),
                     ("law_presidential_republic", "law_universal_suffrage", "law_protected_speech")):
            with self.subTest(laws=laws):
                world = new_world(bare=True)
                state = world.countries[world.tag]
                state["laws"] = list(laws) + ["law_no_schools", "law_land_based_taxation"]
                state["legitimacy"] = 20
                original = world_facts(world)
                arc = ready_for_review(world, limited=True)
                self.assertEqual((state[P + "mode"], state[P + "target"]), (3, 2))
                month(world, arc, 6)
                finish_review(world, arc, 2)
                self.assert_paid(world, 500, 500)
                self.assert_closed(world, 2)
                self.assertEqual(world_facts(world), original)

    def test_conservative_petition_is_full_even_without_a_school_or_industrial_building(self):
        world = new_world("conservative", bare=True)
        state = world.countries[world.tag]
        office(world)["occupancy"] = .5
        state["states"][0]["turmoil"] = .25
        group(world, "ig_landowners").update(in_government=True, clout=.10, approval=0)
        arc = ready_for_review(world, "conservative")
        month(world, arc, 6)
        finish_review(world, arc)
        self.assertEqual(len(state["states"][0]["buildings"]), 1)
        self.assertEqual(state[P + "target"], 1)
        self.assert_closed(world, 1)

    def test_current_power_speech_monarchy_and_office_laws_are_real_not_tax_proxies(self):
        cases = (("court", "law_monarchy", "law_presidential_republic"),
                 ("court", "law_appointed_bureaucrats", "law_elected_bureaucrats"),
                 ("court", "law_autocracy", "law_universal_suffrage"),
                 ("court", "law_censorship", "law_outlawed_dissent"),
                 ("local", "law_census_voting", "law_autocracy"),
                 ("local", "law_right_of_assembly", "law_censorship"),
                 ("conservative", "law_autocracy", "law_census_voting"),
                 ("conservative", "law_outlawed_dissent", "law_protected_speech"))
        for route, law, wrong in cases:
            with self.subTest(route=route, law=law):
                world = new_world(route)
                arc = court_arc(world.cat)
                event = world.deliver(arc, "ywc_kor.1120")
                self.assertTrue(option_legal(world, event, ROUTES[route]))
                state = world.countries[world.tag]
                state["laws"].remove(law)
                state["laws"].append(wrong)
                self.assertFalse(option_legal(world, event, ROUTES[route]))
                before = copy.deepcopy((state, world.treasury))
                force_option(world, event, ROUTES[route])
                self.assertEqual((state, world.treasury), before)

    def test_same_supporter_must_supply_government_clout_approval_and_alternatives_are_or(self):
        for route, kind in (("court", "ig_intelligentsia"), ("local", "ig_rural_folk"),
                            ("conservative", "ig_landowners")):
            with self.subTest(route=route):
                world = new_world(route)
                arc = court_arc(world.cat)
                event = world.deliver(arc, "ywc_kor.1120")
                state = world.countries[world.tag]
                for ig in state["igs"]:
                    ig["in_government"] = False
                first = group(world, kind)
                first.update(clout=.2, approval=1)
                second = {**first, "in_government": True, "clout": .099}
                state["igs"].append(second)
                self.assertFalse(option_legal(world, event, ROUTES[route]))
                second.update(clout=.1, approval=-1)
                self.assertFalse(option_legal(world, event, ROUTES[route]))
                second["approval"] = 0
                self.assertTrue(option_legal(world, event, ROUTES[route]))

    def test_first_owned_typed_pilot_is_claimed_once_and_never_reselected(self):
        template = current_facts()["states"][0]
        states = [copy.deepcopy(template) for _ in range(3)]
        states[0]["owner"] = "CHI"
        states[1]["region"] = "s:STATE_YANGHO"
        states[2]["region"] = "s:STATE_PYONGYANG"
        world = new_world(states=states)
        arc = court_arc(world.cat)
        play(world, arc, 1120, ROUTES["court"])
        state = world.countries[world.tag]
        selected = state[P + "pilot_state"]
        self.assertIsInstance(selected, StateRef)
        self.assertIs(world._state_dict(selected.sid), states[1])
        states[1]["owner"] = "CHI"
        event = world.deliver(arc, "ywc_kor.1121")
        self.assertFalse(option_legal(world, event, "pay_petition"))
        self.assertEqual(state[P + "pilot_state"], selected)
        choose(world, arc, event, "withdraw")
        self.assert_closed(world, 4)

    def test_employment_shortage_and_workplace_are_original_state_facts_without_culture_gate(self):
        for defect in ("unemployed", "workplace", "shortage"):
            with self.subTest(defect=defect):
                states = [copy.deepcopy(current_facts()["states"][0]) for _ in range(3)]
                states[1]["region"] = "s:STATE_YANGHO"
                states[2]["owner"] = "CHI"
                world = new_world(states=states)
                arc = court_arc(world.cat)
                event = world.deliver(arc, "ywc_kor.1120")
                self.assertTrue(option_legal(world, event, ROUTES["court"]))
                if defect == "unemployed": office_pop(world)["employed"] = False
                elif defect == "workplace": office_pop(world)["workplace"] = {"type": "building_rice_farm", "occupancy": 1, "shortage": False}
                else: office(world)["shortage"] = True
                self.assertFalse(option_legal(world, event, ROUTES["court"]))
        for primary, acceptance in ((True, 5), (False, 4)):
            world = new_world()
            office_pop(world).update(primary=primary, acceptance=acceptance)
            arc = ready_for_review(world)
            month(world, arc, 6)
            finish_review(world, arc)
            self.assert_closed(world, 1)

    def test_staged_witness_signature_and_acceptance_are_earned_without_future_cycles(self):
        world = new_world()
        arc = court_arc(world.cat)
        state = world.countries[world.tag]
        play(world, arc, 1120, ROUTES["court"])
        play(world, arc, 1121, "pay_petition")
        self.assertNotIn(P + "witness_mode", state)
        play(world, arc, 1122, "new_professional_witness")
        self.assertIn(JES[0], world.active[world.tag])
        self.assertNotIn(P + "sign_mode", state)
        self.assertNotIn(P + "accept_mode", state)
        for name in ("handler", "witness"):
            self.assertEqual(snapshot(world, name), (1, 1, state[P + "pilot_state"]))
        play(world, arc, 1123, "sign_responsibility")
        self.assertEqual(state[P + "phase"], 2)
        self.assertEqual(state[P + "stage"], 1124)
        self.assertEqual(state[P + "pending_event"], 1124)
        self.assertEqual(world.history[world.tag][JES[0]], "complete")
        self.assertNotIn(P + "accept_mode", state)
        play(world, arc, 1124, CHANNELS["court"])
        self.assertEqual((state[P + "accept_mode"], state[P + "accept_target"], state[P + "accept_pilot"]),
                         (1, 1, state[P + "pilot_state"]))
        self.assertEqual(state[P + "review_streak"], 0)

    def test_policy_bureaucracy_legitimacy_income_and_authority_are_current(self):
        cases = (("court", "bureaucracy", -1), ("court", "legitimacy", 29),
                 ("local", "legitimacy", 24), ("local", "net_fixed_income", -1),
                 ("conservative", "authority", 49), ("conservative", "legitimacy", 24))
        for route, key, bad in cases:
            with self.subTest(route=route, key=key):
                world = new_world(route)
                arc = court_arc(world.cat)
                event = world.deliver(arc, "ywc_kor.1120")
                self.assertTrue(option_legal(world, event, ROUTES[route]))
                world.countries[world.tag][key] = bad
                self.assertFalse(option_legal(world, event, ROUTES[route]))

    def test_real_opposition_is_recorded_without_granting_approval_and_new_opposition_needs_restart(self):
        for addition in ("ig", "movement"):
            with self.subTest(addition=addition):
                world = new_world()
                critic = group(world, "ig_trade_unions")
                critic.update(in_government=False, clout=.05, approval=-1)
                original = copy.deepcopy(critic)
                arc = ready_for_review(world)
                state = world.countries[world.tag]
                self.assertEqual(state[P + "opp_trade_unions"], 1)
                self.assertEqual(critic, original)
                month(world, arc, 2)
                new_critic = group(world, "ig_petty_bourgeoisie")
                if addition == "ig":
                    new_critic.update(in_government=False, clout=.05, approval=-1)
                else:
                    state["movements"].append({"is_being_suppressed": True, "political_movement_radicalism": .25})
                current = world_facts(world)
                month(world, arc)
                self.assertEqual(state[P + "review_interrupted"], 1)
                self.assertEqual(state[P + "review_streak"], 0)
                event = world.deliver(arc, "ywc_kor.1125")
                choose(world, arc, event, "restart_review")
                if addition == "ig":
                    self.assertEqual(state[P + "opp_petty_bourgeoisie"], 1)
                self.assertEqual(world_facts(world), current)
                month(world, arc, 6)
                finish_review(world, arc)
                self.assert_closed(world, 1)

    def test_suppressed_movement_is_same_object_and_requires_its_real_sealed_case_reply(self):
        for combined in (False, True):
            with self.subTest(combined=combined):
                movements = ([{"is_being_suppressed": True, "political_movement_radicalism": .25}] if combined else
                             [{"is_being_suppressed": True, "political_movement_radicalism": .1},
                              {"is_being_suppressed": False, "political_movement_radicalism": .9}])
                world = new_world(movements=movements)
                original = copy.deepcopy(movements)
                arc = court_arc(world.cat)
                for number, key in ((1120, ROUTES["court"]), (1121, "pay_petition"),
                                    (1122, "new_professional_witness"), (1123, "sign_responsibility")):
                    play(world, arc, number, key)
                event = world.deliver(arc, "ywc_kor.1124")
                self.assertEqual(option_legal(world, event, "record_sealed_case_reply"), combined)
                if combined:
                    self.assertFalse(option_legal(world, event, CHANNELS["court"]))
                    choose(world, arc, event, "record_sealed_case_reply")
                    event = world.deliver(arc, "ywc_kor.1124")
                state = world.countries[world.tag]
                state["laws"].remove("law_censorship")
                state["laws"].append("law_outlawed_dissent")
                self.assertFalse(option_legal(world, event, CHANNELS["court"]))
                before = copy.deepcopy((state, world.treasury))
                force_option(world, event, CHANNELS["court"])
                self.assertEqual((state, world.treasury), before)
                state["laws"].remove("law_outlawed_dissent")
                state["laws"].append("law_censorship")
                choose(world, arc, event, CHANNELS["court"])
                month(world, arc, 6)
                finish_review(world, arc)
                self.assertEqual(movements, original)
                self.assert_closed(world, 1)

    def test_two_fees_check_exact_cash_and_current_war_default_bankruptcy_law(self):
        for payment in (1121, 1125):
            for denial in ("cash", "war", "default", "bankruptcy", "law"):
                with self.subTest(payment=payment, denial=denial):
                    world = new_world()
                    arc = court_arc(world.cat)
                    if payment == 1121: play(world, arc, 1120, ROUTES["court"])
                    else:
                        arc = ready_for_review(world)
                        month(world, arc, 6)
                    event = world.deliver(arc, f"ywc_kor.{payment}")
                    key = "pay_petition" if payment == 1121 else "pay_review"
                    state = world.countries[world.tag]
                    state["gold_reserves"] = 1000 - world.treasury[world.tag]
                    self.assertTrue(option_legal(world, event, key))
                    if denial == "cash": state["gold_reserves"] -= .01
                    elif denial == "war": state["is_at_war"] = True
                    elif denial == "default": state["in_default"] = True
                    elif denial == "bankruptcy": world.modifiers.append((world.tag, {"modifier": "declared_bankruptcy"}))
                    else: state["laws"].remove("law_appointed_bureaucrats")
                    self.assertFalse(option_legal(world, event, key))
                    before = copy.deepcopy((state, world.treasury, world.active, world.history))
                    force_option(world, event, key)
                    self.assertEqual((state, world.treasury, world.active, world.history), before)

    def test_missing_or_zero_mode_target_phase_stage_receipt_never_pays(self):
        for payment in (1121, 1125):
            for name in (P + "mode", P + "target", P + "phase", P + "stage", R):
                for bad in (None, 0):
                    with self.subTest(payment=payment, name=name, bad=bad):
                        world = new_world()
                        arc = court_arc(world.cat)
                        if payment == 1121: play(world, arc, 1120, ROUTES["court"])
                        else:
                            arc = ready_for_review(world)
                            month(world, arc, 6)
                        event = world.deliver(arc, f"ywc_kor.{payment}")
                        key = "pay_petition" if payment == 1121 else "pay_review"
                        self.assertTrue(option_legal(world, event, key))
                        state = world.countries[world.tag]
                        self.assertIn(name, state)
                        if bad is None: del state[name]
                        else: state[name] = bad
                        self.assertFalse(option_legal(world, event, key))
                        before = copy.deepcopy((state, world.treasury, world.active, world.history))
                        force_option(world, event, key)
                        self.assertEqual((state, world.treasury, world.active, world.history), before)

    def test_native_immediate_is_exactly_two_nodes_with_ordinal_receipts_not_event_ids(self):
        world = new_world()
        arc = court_arc(world.cat)
        for ordinal, event in enumerate(arc["events"], 1):
            immediate = parse(event["immediate"].strip()[1:-1])
            self.assertEqual(immediate[0], ("ywc_v03_mark_major_delivered", "=", "yes"))
            self.assertEqual(len(immediate), 2)
            self.assertEqual(immediate[1][0:2], ("set_variable", "="))
            self.assertEqual(field(immediate[1][2], "name"), R)
            self.assertEqual(int(field(immediate[1][2], "value")), ordinal)
        play(world, arc, 1120, ROUTES["court"])
        event = world.deliver(arc, "ywc_kor.1121")
        state = world.countries[world.tag]
        self.assertEqual(state[R], 2)
        for bad in (1121, 1120, 1, 8):
            state[R] = bad
            self.assertFalse(option_legal(world, event, "pay_petition"))
            before = copy.deepcopy((state, world.treasury))
            force_option(world, event, "pay_petition")
            self.assertEqual((state, world.treasury), before)

    def test_claim_budget_is_captured_once_with_positive_hundred_minimum(self):
        for gross, expected in ((52000, 1000), (0, 100)):
            with self.subTest(gross=gross):
                world = new_world()
                state = world.countries[world.tag]
                state["yearly_gross_income"] = gross
                arc = court_arc(world.cat)
                play(world, arc, 1120, ROUTES["court"])
                state["yearly_gross_income"] = 520000
                play(world, arc, 1121, "pay_petition")
                self.assertEqual(state[P + "budget"], expected)
                self.assertEqual(state[P + "petition_paid_amount"], expected)
                self.assertEqual(world.treasury[world.tag], -expected)

    def test_all_policies_creation_day_duplicates_and_five_vs_six_months(self):
        for route, limited in (("court", False), ("local", False), ("conservative", False), ("court", True)):
            with self.subTest(route=route, limited=limited):
                world = new_world(route, bare=limited)
                arc = ready_for_review(world, route, limited)
                state = world.countries[world.tag]
                for _ in range(3): world.pulse(arc)
                self.assertEqual(state[P + "review_streak"], 0)
                month(world, arc, 5)
                self.assertEqual(state[P + "review_streak"], 5)
                self.assertNotIn(P + "review_mature", state)
                world.pulse(arc)
                self.assertEqual(state[P + "review_streak"], 5)
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 6)
                self.assertEqual(state[P + "review_mature"], 1)
                self.assertNotIn(P + "review_running", state)
                finish_review(world, arc, 2 if limited else 1)
                self.assert_closed(world, 2 if limited else 1)

    def test_current_losses_clear_observation_and_recovery_requires_explicit_fresh_restart(self):
        for loss in ("war", "default", "bankruptcy", "pilot", "law", "government", "clout", "approval", "employment", "shortage"):
            with self.subTest(loss=loss):
                world = new_world()
                arc = ready_for_review(world)
                state = world.countries[world.tag]
                month(world, arc, 2)
                facts = world_facts(world)
                modifiers = copy.deepcopy(world.modifiers)
                if loss == "war": state["is_at_war"] = True
                elif loss == "default": state["in_default"] = True
                elif loss == "bankruptcy": world.modifiers.append((world.tag, {"modifier": "declared_bankruptcy"}))
                elif loss == "pilot": state["states"][0]["owner"] = "CHI"
                elif loss == "law": state["laws"].remove("law_appointed_bureaucrats")
                elif loss in ("government", "clout", "approval"):
                    for kind in ("ig_intelligentsia", "ig_landowners"):
                        group(world, kind)[{"government": "in_government", "clout": "clout", "approval": "approval"}[loss]] = {"government": False, "clout": .09, "approval": -1}[loss]
                elif loss == "employment": office_pop(world)["employed"] = False
                else: office(world)["shortage"] = True
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 0)
                self.assertEqual(state[P + "review_interrupted"], 1)
                self.assertNotIn(P + "review_mature", state)
                self.assertNotIn(P + "review_running", state)
                # Restore literal facts in place, preserving every registered StateRef identity.
                original_state = state["states"][0]
                for key, value in facts.items():
                    if key != "states": state[key] = copy.deepcopy(value)
                original_state.clear(); original_state.update(copy.deepcopy(facts["states"][0]))
                world.modifiers = modifiers
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 0)
                event = world.deliver(arc, "ywc_kor.1125")
                choose(world, arc, event, "restart_review")
                month(world, arc, 5)
                self.assertNotIn(P + "review_mature", state)
                month(world, arc)
                finish_review(world, arc)
                self.assert_closed(world, 1)

    def test_both_late_recounts_observe_six_new_months_and_keep_zero_cash_paid_continuation(self):
        for late in (1126, 1127):
            with self.subTest(late=late):
                world = new_world()
                arc = ready_for_review(world)
                month(world, arc, 6)
                play(world, arc, 1125, "pay_review")
                if late == 1127: play(world, arc, 1126, "request_full")
                event = world.deliver(arc, f"ywc_kor.{late}")
                choose(world, arc, event, "recount")
                state = world.countries[world.tag]
                self.assertEqual((state[P + "stage"], state[P + "review_streak"]), (1125, 0))
                self.assertNotIn(P + "review_mature", state)
                self.assertNotIn(P + "requested", state)
                state["gold_reserves"] = -world.treasury[world.tag]
                month(world, arc, 5)
                self.assertNotIn(P + "review_mature", state)
                month(world, arc)
                finish_review(world, arc)
                self.assert_paid(world, 1000, 1000)
                self.assertEqual(world.treasury[world.tag], -2000)
                self.assert_closed(world, 1)

    def test_explicit_narrowing_really_resigns_all_duties_and_needs_six_new_months(self):
        world = new_world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1125, "pay_review")
        old = world.deliver(arc, "ywc_kor.1126")
        choose(world, arc, old, "recount")
        state = world.countries[world.tag]
        state["laws"].remove("law_appointed_bureaucrats")
        office(world)["occupancy"] = .25
        month(world, arc)
        event = world.deliver(arc, "ywc_kor.1125")
        original = world_facts(world)
        choose(world, arc, event, "narrow_and_resign")
        self.assertEqual((state[P + "mode"], state[P + "target"], state[P + "review_streak"]), (3, 2, 0))
        for kind in ("handler", "witness", "signature", "accept"):
            self.assertEqual(snapshot(world, kind), (3, 2, state[P + "pilot_state"]))
        self.assertEqual(world_facts(world), original)
        before = copy.deepcopy((state, world.treasury))
        force_option(world, old, "request_full")
        self.assertEqual((state, world.treasury), before)
        month(world, arc, 5)
        self.assertNotIn(P + "review_mature", state)
        month(world, arc)
        finish_review(world, arc, 2)
        self.assertEqual(world.treasury[world.tag], -2000)
        self.assert_closed(world, 2)

    def test_honest_setback_requires_real_paid_maturity_and_late_current_loss_not_recovery(self):
        for loss in ("war", "default", "pilot", "employment"):
            with self.subTest(loss=loss):
                world = new_world()
                arc = ready_for_review(world)
                state = world.countries[world.tag]
                self.assertFalse(option_legal(world, world.event_defs["ywc_kor.1126"], "request_setback"))
                month(world, arc, 6)
                play(world, arc, 1125, "pay_review")
                event = world.deliver(arc, "ywc_kor.1126")
                self.assertFalse(option_legal(world, event, "request_setback"))
                def change(lost):
                    if loss == "war": state["is_at_war"] = lost
                    elif loss == "default": state["in_default"] = lost
                    elif loss == "pilot": state["states"][0]["owner"] = "CHI" if lost else "KOR"
                    else: office_pop(world)["employed"] = not lost
                change(True)
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 6)
                self.assertEqual(state[P + "review_mature"], 1)
                self.assertFalse(option_legal(world, event, "request_full"))
                choose(world, arc, event, "request_setback")
                final = world.deliver(arc, "ywc_kor.1127")
                self.assertTrue(option_legal(world, final, "close_setback"))
                change(False)
                self.assertFalse(option_legal(world, final, "close_setback"))
                before = copy.deepcopy((state, world.treasury))
                force_option(world, final, "close_setback")
                self.assertEqual((state, world.treasury), before)
                change(True)
                choose(world, arc, final, "close_setback")
                self.assert_closed(world, 3)

    def test_cached_all_options_and_withdraw_are_inert_at_every_other_stage_or_bad_phase_receipt(self):
        world = new_world()
        arc = court_arc(world.cat)
        cached = []
        path = ((1120, ROUTES["court"]), (1121, "pay_petition"), (1122, "new_professional_witness"),
                (1123, "sign_responsibility"), (1124, CHANNELS["court"]),
                (1125, "pay_review"), (1126, "request_full"), (1127, "close_full"))
        for number, action in path:
            if number == 1125: month(world, arc, 6)
            event = world.deliver(arc, f"ywc_kor.{number}")
            for old_event, key in cached:
                before = copy.deepcopy((world.countries, world.treasury, world.active, world.history))
                force_option(world, old_event, key)
                self.assertEqual((world.countries, world.treasury, world.active, world.history), before)
            for name, _, option in event:
                if name != "option": continue
                key = field(option, "name").rsplit(".", 1)[-1]
                for guard in (P + "phase", R):
                    for bad in (None, 0):
                        clone = copy.deepcopy(world)
                        state = clone.countries[clone.tag]
                        self.assertIn(guard, state)
                        if bad is None: del state[guard]
                        else: state[guard] = bad
                        before = copy.deepcopy((clone.countries, clone.treasury, clone.active, clone.history))
                        force_option(clone, event, key)
                        self.assertEqual((clone.countries, clone.treasury, clone.active, clone.history), before)
                cached.append((event, key))
            choose(world, arc, event, action)
        for event, key in cached:
            before = copy.deepcopy((world.countries, world.treasury, world.active, world.history))
            force_option(world, event, key)
            self.assertEqual((world.countries, world.treasury, world.active, world.history), before)

    def test_signature_handoff_survives_immediate_pilot_loss_and_full_capacity(self):
        for capacity in (1, 3):
            with self.subTest(capacity=capacity):
                world = new_world()
                arc = court_arc(world.cat)
                for n, key in ((1120, ROUTES["court"]), (1121, "pay_petition"), (1122, "new_professional_witness")):
                    play(world, arc, n, key)
                event = world.deliver(arc, "ywc_kor.1123")
                state = world.countries[world.tag]
                # Literal external capacity pressure, not this arc's earned history.
                state["ywc_v03_active_arc_count"] = capacity
                state["ywc_v03_visible_task_count"] = capacity
                self.assertTrue(option_legal(world, event, "sign_responsibility"))
                native_force(world, event, "sign_responsibility")
                state["states"][0]["owner"] = "CHI"
                world.refresh(arc)
                self.assertEqual(world.history[world.tag][JES[0]], "complete")
                event = world.deliver(arc, "ywc_kor.1124")
                choose(world, arc, event, "withdraw")
                self.assert_closed(world, 4, capacity - 1)

    def test_final_close_rechecks_current_support_law_post_and_owner(self):
        for loss in ("law", "support", "employment", "pilot"):
            with self.subTest(loss=loss):
                world = new_world()
                arc = ready_for_review(world)
                month(world, arc, 6)
                play(world, arc, 1125, "pay_review")
                play(world, arc, 1126, "request_full")
                event = world.deliver(arc, "ywc_kor.1127")
                state = world.countries[world.tag]
                if loss == "law": state["laws"].remove("law_appointed_bureaucrats")
                elif loss == "support":
                    for kind in ("ig_intelligentsia", "ig_landowners"): group(world, kind)["in_government"] = False
                elif loss == "employment": office_pop(world)["employed"] = False
                else: state["states"][0]["owner"] = "CHI"
                self.assertFalse(option_legal(world, event, "close_full"))
                before = copy.deepcopy((state, world.treasury))
                force_option(world, event, "close_full")
                self.assertEqual((state, world.treasury), before)
                choose(world, arc, event, "withdraw")
                self.assert_closed(world, 4)

    def test_release_is_once_and_preserves_another_real_arc_queue_and_reservation(self):
        world = new_world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1125, "pay_review")
        play(world, arc, 1126, "request_full")
        event = world.deliver(arc, "ywc_kor.1127")
        old_arc = next(a for a in world.cat["arcs"] if a["slug"] == "v03_kor_military_accounts")
        world.refresh(old_arc)
        self.assert_capacity(world, 2)
        world.advance_days(91)
        world.pulse(old_arc)
        state = world.countries[world.tag]
        self.assertIn("ywc_kor_pending_event", state)
        other = {key: value for key, value in state.items() if key.startswith("ywc_kor_") and not key.startswith(P)}
        reservation = state.get("ywc_v03_kor_inline_reservation")
        self.assertIsNotNone(reservation)
        choose(world, arc, event, "close_full")
        self.assert_closed(world, 1, 1)
        self.assertEqual({key: value for key, value in state.items() if key in other}, other)
        self.assertEqual(state.get("ywc_v03_kor_inline_reservation"), reservation)
        for _ in range(3):
            world.run(RELEASE_EFFECT, world.tag)
            force_option(world, event, "close_full")
        self.assert_capacity(world, 1)
        self.assertEqual({key: value for key, value in state.items() if key in other}, other)

    def test_free_paid_advance_requires_real_positive_receipts_and_new_maturity(self):
        world = new_world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1125, "pay_review")
        event = world.deliver(arc, "ywc_kor.1126")
        choose(world, arc, event, "recount")
        state = world.countries[world.tag]
        self.assertFalse(option_legal(world, world.event_defs["ywc_kor.1125"], "advance_paid_review"))
        month(world, arc, 6)
        event = world.deliver(arc, "ywc_kor.1125")
        self.assertTrue(option_legal(world, event, "advance_paid_review"))
        for name in (P + "review_paid", P + "review_paid_amount", P + "petition_paid_amount"):
            for bad in (None, 0):
                clone = copy.deepcopy(world)
                altered = clone.countries[clone.tag]
                if bad is None: del altered[name]
                else: altered[name] = bad
                self.assertFalse(option_legal(clone, event, "advance_paid_review"))
                before = copy.deepcopy((altered, clone.treasury))
                force_option(clone, event, "advance_paid_review")
                self.assertEqual((altered, clone.treasury), before)
        state["gold_reserves"] = -world.treasury[world.tag]
        choose(world, arc, event, "advance_paid_review")
        self.assertEqual(world.treasury[world.tag], -2000)


if __name__ == "__main__":
    unittest.main()
