"""SHU rural-workshop contracts, prepared from the frozen implementation plan.

Imports/construction are gated by root until the StateRef runtime is terminal.
Business qualification, fees, histories and clocks are always original source ASTs.
"""
import copy
import unittest

from shu_rural_state_runtime import ShuRuralStateWorld, StateRef
from test_v03_shu_rural_runtime import rural_facts, HOME_PM, RICE
from test_v03_shu_provincial_contract import (
    choose, force_option, option_legal, field,
)
from test_v03_shu_content import shu_monthly_effect


SLUG = "v03_shu_rural_workshop"
P = "ywc_shu_workshop_"
L = "ywc_v03_shu_v03_shu_rural_workshop_"
JES = ("ywc_je_v03_shu_workshop_ground", "ywc_je_v03_shu_workshop_yields")
ROUTES = {"rural": "rural_processing", "urban": "urban_concentration",
          "home": "protect_home_workshops"}
DUTIES = {"rural": "record_rural_duties", "urban": "record_urban_duties",
          "home": "record_home_duties"}
# Source-terminal bindings: actual authored fields, not additional requirements.
IDENTITIES = {role: tuple(P + role + "_" + item for item in ("mode", "target", "pilot"))
              for role in ("handler", "witness", "sign", "accept", "review")}
PAID = {bill: (P + bill + "_paid", P + bill + "_paid_amount")
        for bill in ("admin", "survey")}
KIND_FIELDS = (P + "handler_kind", P + "witness_source", P + "accept_kind", P + "review_kind")


def building(kind, occupancy=1, *, groups=(), methods=(), level=1):
    return {"type": kind, "occupancy": occupancy, "shortage": False,
            "groups": list(groups), "active_production_methods": list(methods), "level": level}


def population(kind, workplace, sol):
    return {"type": kind, "employed": True, "workplace": workplace,
            "standard_of_living": sol, "wealth": 12, "literacy": .4,
            "primary": True, "acceptance": 5}


def current_facts(route="rural", bare=False):
    if route not in ROUTES:
        raise ValueError(route)
    state = rural_facts()
    own = state["states"][0]
    own.update(owner="SHU", owned=True, region="s:STATE_SICHUAN",
               market_access=1, average_sol=30, turmoil=.1)
    farm = building("building_rice_farm", groups=("bg_agriculture",))
    food = building("building_food_industry")
    city = building("building_urban_center", level=3)
    own["buildings"].extend((farm, food, city))
    own["pops"].extend((population("farmers", farm, 12), population("machinists", food, 12)))
    for b in own["buildings"]:
        b.setdefault("active_production_methods", [])
        b.setdefault("level", 1)
    for pop in own["pops"]:
        pop.setdefault("standard_of_living", 12)
    state["laws"] = [law for law in state["laws"] if law not in (
        "law_serfdom", "law_tenant_farmers", "law_homesteading", "law_commercialized_agriculture")]
    state["laws"].append("law_tenant_farmers")
    for kind in ("ig_rural_folk", "ig_landowners", "ig_industrialists", "ig_intelligentsia"):
        existing = next((ig for ig in state["igs"] if ig["type"] == kind), None)
        if existing is None:
            existing = {"type": kind}
            state["igs"].append(existing)
        existing.update(in_government=True, clout=.15, approval=1)
    state.update(legitimacy=50, bureaucracy=100, net_fixed_income=100,
                 is_at_war=False, in_default=False, gold_reserves=100000,
                 yearly_gross_income=52000, market={"grain": {"pricier": .25}})
    if bare:
        office = next(b for b in own["buildings"] if b["type"] == "building_government_administration")
        office["occupancy"] = .25
        farm["occupancy"] = .25
        own["buildings"] = [office, farm]
        own["pops"] = [population("bureaucrats", office, 5), population("farmers", farm, 5)]
        own["market_access"] = .25
        state.update(igs=[], institutions={}, legitimacy=15,
                     laws=["law_no_schools", "law_serfdom"], market={"grain": {"pricier": .75}})
    return state


def new_world(route="rural", bare=False, *, states=None):
    facts = current_facts(route, bare)
    if states is not None:
        facts["states"] = states
    world = ShuRuralStateWorld()
    world.countries["SHU"] = facts
    # Shared native initialization compares actual c:DMG/c:KOR identities even
    # in a SHU world. Supply explicit country objects, never relax unknown scopes.
    for tag in ("CHI", "DMG", "KOR", "JHG", "LAN", "NMG", "MGL", "NQG", "TIB", "OIR"):
        world.countries[tag] = {"states": [], "igs": [], "market": {"grain": {"pricier": 0}}}
    world.run("ywc_v03_initialize_country", "SHU")
    return world


def workshop_arc(catalog):
    return next(a for a in catalog["arcs"] if a["slug"] == SLUG)


def state(world):
    return world.countries[world.tag]


def pilot(world):
    ref = state(world)[P + "pilot"]
    assert isinstance(ref, StateRef), ("pilot_is_actual_state_object", ref)
    return world._state_object(ref)


def office(world, province=None):
    province = state(world)["states"][0] if province is None else province
    return next(b for b in province["buildings"] if b["type"] == "building_government_administration")


def pop(world, kind, province=None):
    province = state(world)["states"][0] if province is None else province
    return next(p for p in province["pops"] if p["type"] == kind)


def group(world, kind):
    return next(ig for ig in state(world)["igs"] if ig["type"] == kind)


def cash(world):
    return state(world)["gold_reserves"] + world.treasury[world.tag]


def set_cash(world, amount):
    state(world)["gold_reserves"] = amount - world.treasury[world.tag]


def world_facts(world):
    return copy.deepcopy({k: v for k, v in state(world).items()
                          if not k.startswith("ywc_") and k != "gold_reserves"})


def restore_facts(world, original):
    """Restore ordinary facts without replacing any registered state object."""
    s = state(world)
    assert len(s["states"]) == len(original["states"])
    for actual, saved in zip(s["states"], original["states"]):
        actual.clear(); actual.update(copy.deepcopy(saved))
    for key, value in original.items():
        if key != "states": s[key] = copy.deepcopy(value)


def month(world, arc, count=1):
    """One inherited calendar owner, actual country accounts and native JE pulse."""
    for _ in range(count):
        before = world.elapsed_months
        world.advance_months(1)
        if world.elapsed_months == before:
            world.elapsed_months += 1
        else:
            assert world.elapsed_months == before + 1
        world.execute(shu_monthly_effect(), world.tag)
        world.pulse(arc)


def deliver(world, arc, number):
    """Receive actual queued callback; waiting months also service old accounts."""
    expected = "ywc_shu." + str(number)
    for _ in range(120):
        world.pulse(arc)
        while world.events:
            tag, actual = world.events.pop(0)
            event = world.event_defs[actual]
            if not world.conditions(field(event, "trigger"), tag):
                continue
            assert (tag, actual) == (world.tag, expected), ("unexpected_native_event", actual, expected)
            world.execute(field(event, "immediate"), tag)
            return event
        month(world, arc)
    raise AssertionError(("no_actual_event", expected, world.trace[-8:]))


def play(world, arc, number, key):
    event = deliver(world, arc, number)
    choose(world, arc, event, key)
    return event


def auxiliary(event, kind):
    """Unfrozen wait/withdraw spelling: select the unique REAL source UI key."""
    keys = [field(body, "name").rsplit(".", 1)[-1]
            for name, _, body in event if name == "option"]
    matches = [key for key in keys if key == kind or key.startswith(kind + "_")]
    assert len(matches) == 1, ("expected_one_actual_auxiliary", kind, keys)
    return matches[0]


def through_witness(world, route="rural", *, limited=False, witness=None):
    arc = workshop_arc(world.cat)
    play(world, arc, 1110, "limited_local_preparation" if limited else ROUTES[route])
    play(world, arc, 1111, "pay_admin")
    play(world, arc, 1112, witness or ("local_witness" if limited else "new_witness"))
    return arc


def ready_for_review(world, route="rural", limited=False, witness=None):
    arc = through_witness(world, route, limited=limited, witness=witness)
    play(world, arc, 1113, "sign_responsibility")
    play(world, arc, 1114, "record_local_duties" if limited else DUTIES[route])
    return arc


def finish_review(world, arc, outcome=1):
    action = "advance_paid_review" if PAID["survey"][0] in state(world) else "pay_survey"
    play(world, arc, 1115, action)
    suffix = {1: "full", 2: "limited", 3: "setback"}[outcome]
    play(world, arc, 1116, "request_" + suffix)
    play(world, arc, 1117, "close_" + suffix)


def reached(world, number, route="rural"):
    arc = workshop_arc(world.cat)
    if number == 1110:
        return arc, deliver(world, arc, 1110)
    play(world, arc, 1110, ROUTES[route])
    if number == 1111:
        return arc, deliver(world, arc, 1111)
    play(world, arc, 1111, "pay_admin")
    if number == 1112:
        return arc, deliver(world, arc, 1112)
    play(world, arc, 1112, "new_witness")
    if number == 1113:
        return arc, deliver(world, arc, 1113)
    play(world, arc, 1113, "sign_responsibility")
    if number == 1114:
        return arc, deliver(world, arc, 1114)
    play(world, arc, 1114, DUTIES[route])
    if number == 1115:
        return arc, deliver(world, arc, 1115)
    month(world, arc, 6)
    play(world, arc, 1115, "pay_survey")
    if number == 1116:
        return arc, deliver(world, arc, 1116)
    play(world, arc, 1116, "request_full")
    return arc, deliver(world, arc, 1117)


class ShuRuralWorkshop(unittest.TestCase):
    def assert_closed(self, w, outcome):
        s = state(w)
        self.assertEqual((s[P + "outcome"], s[L + "outcome"], s[L + "settled"]), (outcome, outcome, 1))
        self.assertEqual((s["ywc_v03_active_arc_count"], s["ywc_v03_visible_task_count"]), (0, 0))
        self.assertTrue(all(j not in w.active[w.tag] for j in JES))

    def test_declared_eight_events_two_native_journals_and_actual_id_receipts(self):
        w = new_world()
        self.assertIn(SLUG, [a["slug"] for a in w.cat["arcs"]])
        arc = workshop_arc(w.cat)
        self.assertEqual([e["id"] for e in arc["events"]], ["ywc_shu." + str(n) for n in range(1110, 1118)])
        self.assertEqual([j["id"] for j in arc["journals"]], list(JES))
        e = deliver(w, arc, 1110)
        self.assertEqual(state(w)[P + "last_event"], 1110)
        self.assertIs(pilot(w), state(w)["states"][0])

    def test_three_full_policies_pay_both_real_bills_and_preserve_actual_world(self):
        for route in ROUTES:
            with self.subTest(route=route):
                w = new_world(route); original = world_facts(w); before = cash(w)
                a = ready_for_review(w, route)
                self.assertEqual(before - cash(w), 1000)
                month(w, a, 6); finish_review(w, a)
                self.assertEqual(before - cash(w), 2000)
                for paid, amount in PAID.values():
                    self.assertEqual((state(w)[paid], state(w)[amount]), (1, 1000))
                self.assert_closed(w, 1)
                self.assertEqual(world_facts(w), original)

    def test_explicit_finite_has_real_agriculture_but_no_industry_school_ig_or_land_requirement(self):
        for laws in (["law_serfdom", "law_no_schools"], ["law_commercialized_agriculture", "law_universal_suffrage"]):
            with self.subTest(laws=laws):
                w = new_world(bare=True); state(w)["laws"] = laws
                before = cash(w); a = ready_for_review(w, limited=True)
                month(w, a, 6); finish_review(w, a, 2)
                self.assertEqual(before - cash(w), 1000)
                self.assertEqual((state(w)[P + "mode"], state(w)[P + "target"]), (3, 2))
                self.assert_closed(w, 2)
        w = new_world(bare=True); pop(w, "farmers")["employed"] = False
        a = workshop_arc(w.cat); e = deliver(w, a, 1110)
        self.assertFalse(option_legal(w, e, "limited_local_preparation"))

    def test_same_current_ig_must_jointly_supply_government_clout_and_approval(self):
        for route, kinds in (("rural", ("ig_rural_folk", "ig_landowners")),
                             ("urban", ("ig_industrialists", "ig_intelligentsia")),
                             ("home", ("ig_landowners", "ig_rural_folk"))):
            with self.subTest(route=route):
                w = new_world(route); a = workshop_arc(w.cat); e = deliver(w, a, 1110)
                self.assertTrue(option_legal(w, e, ROUTES[route]))
                for kind in kinds: group(w, kind).update(in_government=False)
                split = copy.deepcopy(group(w, kinds[0])); split.update(in_government=True, clout=.099)
                state(w)["igs"].append(split)
                self.assertFalse(option_legal(w, e, ROUTES[route]))
                split.update(clout=.10, approval=-1)
                self.assertFalse(option_legal(w, e, ROUTES[route]))
                split["approval"] = 0
                self.assertTrue(option_legal(w, e, ROUTES[route]))

    def test_land_laws_are_read_as_current_policy_facts_and_urban_needs_no_specific_land_law(self):
        for route in ROUTES:
            w = new_world(route); a = workshop_arc(w.cat); e = deliver(w, a, 1110)
            state(w)["laws"] = ["law_serfdom"]
            self.assertEqual(option_legal(w, e, ROUTES[route]), route != "rural")
            state(w)["laws"] = ["law_commercialized_agriculture"]
            self.assertEqual(option_legal(w, e, ROUTES[route]), route != "home")

    def test_rural_requires_both_real_farm_and_processing_jobs_at_exact_workplace_boundary(self):
        for role in ("farmers", "machinists"):
            for loss in ("employed", "workplace", "occupancy", "shortage"):
                with self.subTest(role=role, loss=loss):
                    w = new_world(); a = workshop_arc(w.cat); e = deliver(w, a, 1110)
                    p = pop(w, role); p["workplace"]["occupancy"] = .5
                    self.assertTrue(option_legal(w, e, ROUTES["rural"]))
                    if loss == "employed": p["employed"] = False
                    elif loss == "workplace": p["workplace"] = office(w)
                    elif loss == "occupancy": p["workplace"]["occupancy"] = .499
                    else: p["workplace"]["shortage"] = True
                    self.assertFalse(option_legal(w, e, ROUTES["rural"]))

    def test_urban_requires_actual_industrial_employee_and_same_state_city_level_three(self):
        w = new_world("urban"); a = workshop_arc(w.cat); e = deliver(w, a, 1110)
        city = next(b for b in state(w)["states"][0]["buildings"] if b["type"] == "building_urban_center")
        self.assertTrue(option_legal(w, e, ROUTES["urban"]))
        city["level"] = 2
        self.assertFalse(option_legal(w, e, ROUTES["urban"]))
        city["level"] = 3; pop(w, "machinists")["employed"] = False
        self.assertFalse(option_legal(w, e, ROUTES["urban"]))

    def test_home_full_requires_peasant_actual_matching_subsistence_workshop_pm(self):
        w = new_world("home"); a = workshop_arc(w.cat); e = deliver(w, a, 1110)
        p = pop(w, "peasants"); self.assertTrue(option_legal(w, e, ROUTES["home"]))
        p["workplace"]["active_production_methods"] = []
        self.assertFalse(option_legal(w, e, ROUTES["home"]))
        p["workplace"]["active_production_methods"] = ["pm_home_workshops_building_subsistence_farm"]
        self.assertFalse(option_legal(w, e, ROUTES["home"]))
        p["workplace"]["active_production_methods"] = [HOME_PM]
        p["workplace"] = office(w)
        self.assertFalse(option_legal(w, e, ROUTES["home"]))

    def test_each_target_pop_sol_threshold_is_not_replaced_by_state_average(self):
        for route, role, threshold in (("rural", "farmers", 10), ("rural", "machinists", 10),
                                       ("urban", "machinists", 12), ("home", "peasants", 8)):
            with self.subTest(route=route, role=role):
                w = new_world(route); a = workshop_arc(w.cat); e = deliver(w, a, 1110)
                p = pop(w, role); p["standard_of_living"] = threshold
                self.assertTrue(option_legal(w, e, ROUTES[route]))
                p["standard_of_living"] = threshold - .01
                self.assertFalse(option_legal(w, e, ROUTES[route]))

    def test_native_grain_threshold_and_missing_price_never_borrow_country_or_state_price(self):
        for route, threshold in (("rural", .25), ("urban", .40), ("home", .50)):
            with self.subTest(route=route):
                w = new_world(route); a = workshop_arc(w.cat); e = deliver(w, a, 1110)
                state(w)["market"]["grain"]["pricier"] = threshold
                self.assertTrue(option_legal(w, e, ROUTES[route]))
                state(w)["states"][0]["market"] = {"grain": {"pricier": 0}}
                state(w)["market"]["grain"]["pricier"] = threshold + .001
                self.assertFalse(option_legal(w, e, ROUTES[route]))
                del state(w)["market"]["grain"]["pricier"]
                with self.assertRaises(AssertionError): option_legal(w, e, ROUTES[route])

    def test_access_legitimacy_and_finance_boundaries_are_current_at_selection(self):
        for route, access, legitimacy in (("rural", .5, 20), ("urban", .75, 25), ("home", .3, 20)):
            for loss in ("access", "legitimacy", "bureaucracy", "net_fixed_income", "war", "default", "bankruptcy"):
                with self.subTest(route=route, loss=loss):
                    w = new_world(route); a = workshop_arc(w.cat); e = deliver(w, a, 1110)
                    s = state(w); s["states"][0]["market_access"] = access; s["legitimacy"] = legitimacy
                    self.assertTrue(option_legal(w, e, ROUTES[route]))
                    if loss == "access": s["states"][0]["market_access"] -= .001
                    elif loss == "legitimacy": s["legitimacy"] -= 1
                    elif loss in ("bureaucracy", "net_fixed_income"): s[loss] = -1
                    elif loss == "war": s["is_at_war"] = True
                    elif loss == "default": s["in_default"] = True
                    else: w.modifiers.append((w.tag, {"modifier": "declared_bankruptcy"}))
                    self.assertFalse(option_legal(w, e, ROUTES[route]))

    def test_first_state_object_is_captured_once_and_owner_loss_or_disappearance_cannot_repick(self):
        for loss in ("foreign_owner", "remove", "equal_replacement"):
            with self.subTest(loss=loss):
                facts = current_facts(); first = facts["states"][0]; other = copy.deepcopy(first)
                w = new_world(states=[first, other]); a = workshop_arc(w.cat); e = deliver(w, a, 1110)
                ref = state(w)[P + "pilot"]; self.assertIs(pilot(w), first)
                if loss == "foreign_owner": first["owner"] = "CHI"
                elif loss == "remove": state(w)["states"].remove(first)
                else: state(w)["states"][0] = copy.deepcopy(first)
                self.assertFalse(option_legal(w, e, ROUTES["rural"]))
                w.pulse(a); self.assertEqual(state(w)[P + "pilot"], ref)

    def test_jobs_cannot_be_assembled_across_owned_states_or_foreign_same_region_splits(self):
        for foreign in (False, True):
            with self.subTest(foreign=foreign):
                first = current_facts()["states"][0]; other = copy.deepcopy(first)
                next(p for p in first["pops"] if p["type"] == "machinists")["employed"] = False
                if foreign: other["owner"] = "CHI"
                w = new_world(states=[first, other]); a = workshop_arc(w.cat); e = deliver(w, a, 1110)
                self.assertFalse(option_legal(w, e, ROUTES["rural"]))

    def test_both_fees_exact_cash_atomicity_duplicates_and_late_current_loss(self):
        for limited, price in ((False, 1000), (True, 500)):
            for node, key in ((1111, "pay_admin"), (1115, "pay_survey")):
                with self.subTest(limited=limited, node=node):
                    w = new_world(bare=limited); a = workshop_arc(w.cat)
                    if node == 1111:
                        play(w, a, 1110, "limited_local_preparation" if limited else ROUTES["rural"])
                    else:
                        a = ready_for_review(w, limited=limited); month(w, a, 6)
                    e = deliver(w, a, node); set_cash(w, price - 1)
                    self.assertFalse(option_legal(w, e, key)); before = copy.deepcopy((state(w), w.treasury))
                    force_option(w, e, key); self.assertEqual((state(w), w.treasury), before)
                    set_cash(w, price); self.assertTrue(option_legal(w, e, key))
                    pop(w, "farmers")["employed"] = False
                    self.assertFalse(option_legal(w, e, key)); before = copy.deepcopy((state(w), w.treasury))
                    force_option(w, e, key); self.assertEqual((state(w), w.treasury), before)
                    pop(w, "farmers")["employed"] = True
                    before = cash(w); choose(w, a, e, key); self.assertEqual(before - cash(w), price)
                    before = copy.deepcopy((state(w), w.treasury)); force_option(w, e, key)
                    self.assertEqual((state(w), w.treasury), before)

    def test_budget_is_captured_once_clamped_and_both_fees_keep_that_quote(self):
        for income, quote in ((0, 100), (52000, 1000), (104000, 2000), (52 * 2e9, 1e9)):
            with self.subTest(income=income):
                w = new_world(); state(w)["yearly_gross_income"] = income; set_cash(w, 3e9)
                a = workshop_arc(w.cat); play(w, a, 1110, ROUTES["rural"])
                state(w)["yearly_gross_income"] = 5200000
                before = cash(w); play(w, a, 1111, "pay_admin")
                self.assertEqual(before - cash(w), quote)
                play(w, a, 1112, "new_witness"); play(w, a, 1113, "sign_responsibility")
                play(w, a, 1114, DUTIES["rural"]); month(w, a, 6)
                before = cash(w); play(w, a, 1115, "pay_survey")
                self.assertEqual(before - cash(w), quote)

    def test_cached_wrong_receipts_phase_and_stage_make_action_wait_withdraw_inert(self):
        for node in range(1110, 1118):
            with self.subTest(node=node):
                w = new_world(); a, e = reached(w, node)
                wait, withdraw = auxiliary(e, "wait"), auxiliary(e, "withdraw")
                for field_name, bad in ((P + "last_event", None), (P + "last_event", 0),
                                        (P + "last_event", node - 1), (P + "phase", 0),
                                        (P + "stage", node + 1)):
                    v = copy.deepcopy(w); s = state(v)
                    if bad is None: del s[field_name]
                    else: s[field_name] = bad
                    for key in (wait, withdraw):
                        self.assertFalse(option_legal(v, e, key))
                        before = copy.deepcopy((s, v.treasury)); force_option(v, e, key)
                        self.assertEqual((s, v.treasury), before)

    def test_signature_handoff_uses_only_earned_snapshots_and_survives_occupied_capacity(self):
        w = new_world(); a = through_witness(w); s = state(w)
        self.assertNotIn(IDENTITIES["accept"][0], s)
        self.assertNotIn(IDENTITIES["review"][0], s)
        e = deliver(w, a, 1113); self.assertTrue(option_legal(w, e, "sign_responsibility"))
        for name in (*IDENTITIES["handler"], *IDENTITIES["witness"]):
            v = copy.deepcopy(w); del state(v)[name]
            self.assertFalse(option_legal(v, e, "sign_responsibility"))
        s["ywc_v03_active_arc_count"] = 3; s["ywc_v03_visible_task_count"] = 3
        choose(w, a, e, "sign_responsibility")
        self.assertEqual((s[P + "phase"], s[P + "stage"]), (2, 1114))
        self.assertEqual(w.history[w.tag][JES[0]], "complete")
        self.assertIn(JES[1], w.active[w.tag])

    def test_creation_day_duplicate_pulses_and_five_vs_six_real_months(self):
        w = new_world(); a = ready_for_review(w); s = state(w)
        self.assertEqual(s[P + "review_streak"], 0)
        for _ in range(4): w.pulse(a)
        self.assertEqual(s[P + "review_streak"], 0)
        for count in range(1, 7):
            month(w, a); self.assertEqual(s[P + "review_streak"], count)
            w.pulse(a); self.assertEqual(s[P + "review_streak"], count)
            self.assertEqual(P + "review_mature" in s, count == 6)
        self.assertNotIn(P + "review_running", s)

    def test_unpaid_mature_current_loss_interrupts_and_recovery_needs_explicit_six_fresh_restart(self):
        w = new_world(); a = ready_for_review(w); month(w, a, 6); s = state(w)
        pop(w, "machinists")["standard_of_living"] = 9
        month(w, a); self.assertEqual(s[P + "review_streak"], 0)
        self.assertIn(P + "review_interrupted", s); self.assertNotIn(P + "review_mature", s)
        pop(w, "machinists")["standard_of_living"] = 12; month(w, a)
        self.assertEqual(s[P + "review_streak"], 0)
        play(w, a, 1115, "restart_review"); month(w, a, 5)
        self.assertNotIn(P + "review_mature", s); month(w, a)
        finish_review(w, a); self.assert_closed(w, 1)

    def test_paid_late_each_current_family_allows_honest_setback_and_restoration_invalidates_cache(self):
        for route, loss in (*(("rural", name) for name in (
                "farm_job", "processing_job", "farm_sol", "processing_sol", "grain", "land", "ig",
                "access", "legitimacy", "bureaucracy", "net_fixed_income", "default", "bankruptcy",
                "shortage", "office", "war")), ("urban", "city"), ("home", "pm"), ("home", "owner")):
            with self.subTest(route=route, loss=loss):
                w = new_world(route); a = ready_for_review(w, route); month(w, a, 6)
                play(w, a, 1115, "pay_survey"); s = state(w); original = world_facts(w)
                original_modifiers = copy.deepcopy(w.modifiers)
                e = deliver(w, a, 1116); before = cash(w)
                if loss in ("farm_job", "processing_job"):
                    pop(w, "farmers" if loss == "farm_job" else "machinists")["employed"] = False
                elif loss in ("farm_sol", "processing_sol"):
                    pop(w, "farmers" if loss == "farm_sol" else "machinists")["standard_of_living"] = 9
                elif loss == "grain": s["market"]["grain"]["pricier"] = .9
                elif loss == "land": s["laws"] = ["law_serfdom"]
                elif loss == "ig":
                    for ig in s["igs"]: ig["in_government"] = False
                elif loss == "city": next(b for b in s["states"][0]["buildings"] if b["type"] == "building_urban_center")["level"] = 2
                elif loss == "pm": pop(w, "peasants")["workplace"]["active_production_methods"] = []
                elif loss == "owner": pilot(w)["owner"] = "CHI"
                elif loss == "access": pilot(w)["market_access"] = .49
                elif loss == "legitimacy": s["legitimacy"] = 19
                elif loss in ("bureaucracy", "net_fixed_income"): s[loss] = -1
                elif loss == "default": s["in_default"] = True
                elif loss == "bankruptcy": w.modifiers.append((w.tag, {"modifier": "declared_bankruptcy"}))
                elif loss == "shortage": pop(w, "farmers")["workplace"]["shortage"] = True
                elif loss == "office": office(w)["occupancy"] = .49
                else: s["is_at_war"] = True
                month(w, a)
                self.assertEqual(s[P + "stage"], 1116)
                self.assertFalse(option_legal(w, e, "request_full")); self.assertTrue(option_legal(w, e, "request_setback"))
                choose(w, a, e, "request_setback"); close = deliver(w, a, 1117)
                # Restore ordinary facts IN PLACE, preserving all historical snapshots and pilot identity.
                restore_facts(w, original); w.modifiers[:] = original_modifiers
                self.assertFalse(option_legal(w, close, "close_setback")); self.assertEqual(cash(w), before)
                choose(w, a, close, "recount_1115"); month(w, a, 6); finish_review(w, a)
                self.assert_closed(w, 1)

    def test_actual_paid_recount_requires_six_new_months_and_advances_without_cash_or_recharge(self):
        w = new_world(); a = ready_for_review(w); month(w, a, 6)
        play(w, a, 1115, "pay_survey"); paid = {k: state(w)[k] for pair in PAID.values() for k in pair}
        play(w, a, 1116, "recount_1115"); s = state(w)
        self.assertEqual(s[P + "review_streak"], 0); month(w, a, 5)
        self.assertNotIn(P + "review_mature", s); month(w, a)
        set_cash(w, 0); before = cash(w); finish_review(w, a)
        self.assertEqual(cash(w), before); self.assertEqual({k: s[k] for k in paid}, paid)
        self.assert_closed(w, 1)

    def test_explicit_finite_resign_rewrites_all_roles_and_triples_preserves_paid_and_recounts(self):
        w = new_world(); a = ready_for_review(w); month(w, a, 6); play(w, a, 1115, "pay_survey")
        play(w, a, 1116, "recount_1115"); office(w)["occupancy"] = .25
        paid = {k: state(w)[k] for pair in PAID.values() for k in pair}
        play(w, a, 1115, "narrow_and_recount"); s = state(w)
        self.assertEqual((s[P + "mode"], s[P + "target"], s[P + "review_streak"]), (3, 2, 0))
        for triple in IDENTITIES.values(): self.assertEqual(tuple(s[k] for k in triple), (3, 2, s[P + "pilot"]))
        month(w, a, 5); self.assertNotIn(P + "review_mature", s); month(w, a)
        finish_review(w, a, 2); self.assertEqual({k: s[k] for k in paid}, paid); self.assert_closed(w, 2)

    def test_each_stage_real_withdraw_releases_only_this_arc_once_and_cached_buttons_are_inert(self):
        for number in range(1110, 1118):
            with self.subTest(number=number):
                w = new_world(); a, e = reached(w, number); s = state(w)
                unrelated = {"ywc_shu_prov_pending_event": 1102, "ywc_shu_delib_pending_event": 1123}
                s.update(unrelated)  # Negative isolation sentinels, not admission/history evidence.
                key = auxiliary(e, "withdraw"); before = cash(w); choose(w, a, e, key)
                self.assert_closed(w, 4); self.assertEqual(cash(w), before)
                self.assertEqual({k: s[k] for k in unrelated}, unrelated)
                frozen = copy.deepcopy((s, w.treasury)); force_option(w, e, key)
                self.assertEqual((s, w.treasury), frozen)

    def test_full_and_finite_requests_reject_each_missing_or_zero_paid_proof_and_earned_identity(self):
        for limited in (False, True):
            w = new_world(bare=limited); a = ready_for_review(w, limited=limited); month(w, a, 6)
            play(w, a, 1115, "pay_survey"); e = deliver(w, a, 1116)
            key = "request_limited" if limited else "request_full"
            self.assertTrue(option_legal(w, e, key))
            for field_name in (k for pair in PAID.values() for k in pair):
                for value in (None, 0):
                    v = copy.deepcopy(w)
                    if value is None: del state(v)[field_name]
                    else: state(v)[field_name] = value
                    self.assertFalse(option_legal(v, e, key), (limited, field_name, value))
            for triple in IDENTITIES.values():
                for field_name in triple:
                    v = copy.deepcopy(w); del state(v)[field_name]
                    self.assertFalse(option_legal(v, e, key), (limited, field_name))
            for field_name in KIND_FIELDS:
                self.assertIn(field_name, state(w))
                for bad in (None, 99):
                    v = copy.deepcopy(w)
                    if bad is None: del state(v)[field_name]
                    else: state(v)[field_name] = bad
                    self.assertFalse(option_legal(v, e, key), (limited, field_name, bad))
            choose(w, a, e, key); play(w, a, 1117, "close_limited" if limited else "close_full")
            self.assert_closed(w, 2 if limited else 1)


if __name__ == "__main__":
    unittest.main()
