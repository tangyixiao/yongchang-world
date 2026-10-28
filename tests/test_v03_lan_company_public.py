"""Actual generated LAN public-mandate source with concrete political facts."""
import copy
from pathlib import Path
import unittest

from clausewitz_harness import parse
from lan_public_runtime import LanPublicWorld
from shu_kor_strict_review_runtime import facts, field
from test_v03_shu_provincial_contract import _option_effect, option_nodes, option_legal

ROOT = Path(__file__).resolve().parents[1]
SLUG = "v03_lan_company_public"
JES = ("ywc_je_v03_lan_public_mandate", "ywc_je_v03_lan_public_budget",
       "ywc_je_v03_lan_public_succession")
P = "ywc_lan_public_"
ROUTES = {"term": "term_company_republic", "resident": "resident_representation",
          "shareholders": "bounded_shareholders"}


def force_option(world, event, key):
    # Legacy events have native UI metadata in addition to the shared fields.
    # Keep tooltip business children, excluding only default-option UI markup.
    nodes = [node for node in _option_effect(option_nodes(event, key))
             if node[0] != "default_option"]
    world.execute(nodes, world.tag)


def choose(world, arc, event, key):
    assert option_legal(world, event, key), ("illegal_option", key)
    force_option(world, event, key)
    world.refresh(arc)


def public_arc(catalog):
    return next(arc for arc in catalog["arcs"] if arc["slug"] == SLUG)


def new_world(route="term", bare=False, legacy=False):
    world = LanPublicWorld("lan", load_inline=True)
    state = facts()
    state["is_subject"] = legacy
    state["literacy_rate"] = .35
    state["country_has_voting_franchise"] = True
    state["laws"] = ["law_presidential_republic", "law_poor_laws", "law_tenant_farmers",
                     "law_multicultural", "law_universal_suffrage" if route == "resident"
                     else "law_oligarchy" if route == "shareholders" else "law_census_voting",
                     "law_proportional_taxation" if route == "resident" else "law_per_capita_based_taxation"]
    state.update({"modifier:country_voting_power_base_add": 1,
                  "modifier:country_voting_power_wealth_threshold_add": 0,
                  "modifier:country_allow_voting_full_acceptance_bool": True})
    province = state["states"][0]
    province.update(owner="LAN", region="s:STATE_WEST_BORNEO")
    for building in province["buildings"]:
        building["level"] = 2 if building["type"] == "building_government_administration" else 1
    mine = {"type": "building_gold_mine", "groups": ["bg_mining"], "level": 3,
            "occupancy": .75, "shortage": False}
    province["buildings"].append(mine)
    laborer = copy.deepcopy(province["pops"][0])
    laborer.update(type="laborers", workplace=mine)
    farm = next(b for b in province["buildings"] if b["type"] == "building_maize_farm")
    farmer = copy.deepcopy(province["pops"][0])
    farmer.update(type="farmers", workplace=farm)
    province["pops"].extend((laborer, farmer))
    state["igs"] = [
        {"type": kind, "clout": clout, "in_government": True, "approval": 2}
        for kind, clout in (
            ("ig_industrialists", .20), ("ig_petty_bourgeoisie", .15),
            ("ig_rural_folk", .15), ("ig_intelligentsia", .15), ("ig_trade_unions", .15),
            ("ig_landowners", .08), ("ig_devout", .07), ("ig_armed_forces", .05))
    ]
    if bare:
        state["laws"] = ["law_monarchy", "law_autocracy", "law_land_based_taxation",
                         "law_serfdom", "law_no_schools", "law_state_religion"]
        state["country_has_voting_franchise"] = False
        state["institutions"] = {}
        state["modifier:country_voting_power_base_add"] = 0
        state["modifier:country_allow_voting_full_acceptance_bool"] = False
        province["pops"] = [province["pops"][0]]
        province["pops"][0]["workplace"]["occupancy"] = .25
        province["buildings"] = [province["pops"][0]["workplace"]]
        for group in state["igs"]:
            group["in_government"] = group["type"] in ("ig_landowners", "ig_devout")
    world.countries[world.tag] = state
    world.run("ywc_v03_initialize_country", world.tag)
    if legacy:
        run_actual_legacy_prelude(world)
    return world


def play(world, arc, number, key):
    event = world.deliver(arc, f"ywc_lan.{number}")
    choose(world, arc, event, key)
    return event


def month(world, arc, count=1):
    for _ in range(count):
        world.advance_months(1)
        world.elapsed_months += 1
        world.pulse(arc)


def run_actual_legacy_prelude(world):
    """Earn old foundation admission through shipped country history and events."""
    for relative in ("common/scripted_effects/ywc_campaign_effects.txt",
                     "common/scripted_effects/ywc_flavor_effects.txt",
                     "common/scripted_effects/ywc_shared_effects.txt"):
        for key, _, body in parse((ROOT / "yongchang_world" / relative).read_text("utf-8-sig")):
            if isinstance(body, list):
                assert key not in world.effects, ("duplicate_legacy_effect", key)
                world.effects[key] = body
    for relative in ("events/ywc_kor_lan_nmg_events.txt", "events/ywc_large_campaign_events.txt"):
        for key, _, body in parse((ROOT / "yongchang_world" / relative).read_text("utf-8-sig")):
            if key.startswith("ywc_lan.") and isinstance(body, list):
                assert key not in world.event_defs
                world.event_defs[key] = body
    jid = "ywc_je_flavor_lan_charter_1"
    legacy = next(body for key, _, body in parse(
        (ROOT / "yongchang_world/common/journal_entries/ywc_lan.txt").read_text("utf-8-sig"))
                  if key == jid)
    world.journal_defs[jid] = legacy
    countries = next(body for key, _, body in parse(
        (ROOT / "yongchang_world/common/history/countries/ywc_content_starts.txt").read_text("utf-8-sig"))
                     if key == "COUNTRIES")
    initial = next(body for key, _, body in countries if key == "c:LAN")
    world.execute(initial, world.tag)
    bounded_legacy = {"journals": []}
    world.refresh(bounded_legacy)
    assert jid in world.active[world.tag]
    expected = [(7, "a", 30), (100, "a", 60), (101, "a", 180),
                (102, "a", 300), (103, "a", 420), (104, "b", 540)]
    world.legacy_provenance = []
    # Legacy counters predate the new one-day gates. Execute their monthly
    # source exactly once per calendar month, rather than using the focused
    # deliver pump which may retry an unchanged day.
    for observation in range(1, 19):
        world.advance_days(30)
        world.elapsed_months += 1
        world.pulse(bounded_legacy)
        while world.events:
            _, event_id = world.events.pop(0)
            number, key, day = expected[len(world.legacy_provenance)]
            assert event_id == f"ywc_lan.{number}"
            assert observation * 30 == day, (event_id, observation, day)
            event = world.event_defs[event_id]
            assert world.conditions(field(event, "trigger"), world.tag)
            world.execute(field(event, "immediate"), world.tag)
            choose(world, bounded_legacy, event, key)
            world.legacy_provenance.append((event_id, key, day))
    assert len(world.legacy_provenance) == 6
    assert world.history[world.tag][jid] == "complete"
    assert world.countries[world.tag]["ywc_campaign_lan_c1_outcome"] == 2
    assert world.countries[world.tag]["ywc_je_flavor_lan_charter_1_resolved"] == 1
    assert world.countries[world.tag]["ywc_v03_active_arc_count"] == 0


def ready_for_review(world, route="term", limited=False):
    arc = public_arc(world.cat)
    for number, key in (
        (1100, ROUTES[route]), (1101, "pay_charter"),
        (1102, "bounded_petitions" if limited else "verify_constituency"),
        (1103, "sign_bounded_mandate"), (1104, "write_public_appeal"),
        (1105, "confirm_bounded_accounts" if limited else "confirm_current_tax_base"),
        (1106, "pay_public_review"),
    ):
        play(world, arc, number, key)
    assert world.history[world.tag][JES[0]] == "complete"
    assert JES[1] in world.active[world.tag]
    return arc


def finish_review(world, arc, outcome=1):
    play(world, arc, 1107, "accept_six_reviews")
    assert world.history[world.tag][JES[1]] == "complete"
    assert JES[2] in world.active[world.tag]
    play(world, arc, 1108, "confirm_current_mandate")
    play(world, arc, 1109, "close_established" if outcome == 1 else "close_compromise")


class LanCompanyPublic(unittest.TestCase):
    def test_same_issue_reoffered_after_cooldown_cannot_pay_twice_or_restore_old_stage(self):
        world = new_world()
        arc = public_arc(world.cat)
        play(world, arc, 1100, ROUTES["term"])
        first = world.deliver(arc, "ywc_lan.1101")
        state = world.countries[world.tag]
        self.assertTrue(option_legal(world, first, "pay_charter"))
        # Model an unresolved player choice across the existing 90-day cooldown.
        # This proves source reoffer/idempotence, not the engine's popup UI.
        month(world, arc, 3)
        second = world.deliver(arc, "ywc_lan.1101")
        self.assertTrue(option_legal(world, second, "pay_charter"))
        choose(world, arc, first, "pay_charter")
        self.assertEqual(world.treasury[world.tag], -1000)
        self.assertEqual(state[P + "stage"], 1102)
        self.assertEqual(state[P + "pending_event"], 1102)
        before = copy.deepcopy((state, world.treasury))
        for event in (first, second):
            for key in ("pay_charter", "wait_cash", "withdraw"):
                force_option(world, event, key)
        self.assertEqual((state, world.treasury), before)

    def test_final_mandate_keeps_the_actual_named_sponsor_instead_of_substituting_another_group(self):
        world = new_world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1107, "accept_six_reviews")
        play(world, arc, 1108, "confirm_current_mandate")
        state = world.countries[world.tag]
        self.assertEqual(state[P + "term_sponsor"], 1)
        event = world.deliver(arc, "ywc_lan.1109")
        self.assertTrue(option_legal(world, event, "close_established"))
        next(group for group in state["igs"] if group["type"] == "ig_industrialists")["in_government"] = False
        self.assertTrue(next(g for g in state["igs"] if g["type"] == "ig_petty_bourgeoisie")["in_government"])
        self.assertFalse(option_legal(world, event, "close_established"))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, event, "close_established")
        self.assertEqual((state, world.treasury), before)
        choose(world, arc, event, "close_setback")
        self.assertEqual(state[P + "outcome"], 3)
        self.assertEqual(world.treasury[world.tag], -2250)

    def test_current_dispute_after_real_observation_keeps_an_honest_unfunded_term_exit(self):
        world = new_world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1107, "accept_six_reviews")
        state = world.countries[world.tag]
        state["is_at_war"] = True
        event = world.deliver(arc, "ywc_lan.1108")
        self.assertFalse(option_legal(world, event, "confirm_current_mandate"))
        self.assertTrue(option_legal(world, event, "record_dispute"))
        choose(world, arc, event, "record_dispute")
        self.assertNotIn(P + "term_due", state)
        final = world.deliver(arc, "ywc_lan.1109")
        self.assertTrue(option_legal(world, final, "close_setback"))
        self.assertFalse(option_legal(world, final, "close_established"))
        choose(world, arc, final, "close_setback")
        self.assertEqual(state[P + "outcome"], 3)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)

    def test_legacy_source_earns_foundation_entry_via_country_history_and_six_actual_events(self):
        world = new_world(legacy=True)
        state = world.countries[world.tag]
        self.assertEqual(world.history[world.tag]["ywc_je_flavor_lan_charter_1"], "complete")
        self.assertEqual(state["ywc_campaign_lan_c1_outcome"], 2)
        self.assertEqual(world.elapsed_months, 18)
        self.assertEqual([day for _, _, day in world.legacy_provenance],
                         [30, 60, 180, 300, 420, 540])
        self.assertTrue(all(state[f"ywc_campaign_lan_c1_e{n}_done"] == 1 for n in range(100, 105)))
        self.assertNotIn("ywc_v03_lan_v03_lan_mine_accounts_started", state)
        self.assertNotIn("ywc_v03_lan_v03_lan_work_accident_fund_started", state)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)

    def test_war_pilot_default_and_governing_support_loss_need_explicit_six_month_restart(self):
        for loss in ("war", "pilot", "default", "government"):
            with self.subTest(loss=loss):
                world = new_world()
                arc = ready_for_review(world)
                state = world.countries[world.tag]
                month(world, arc, 4)
                if loss == "war": state["is_at_war"] = True
                elif loss == "pilot": state["states"][0]["owner"] = "DEI"
                elif loss == "default": state["in_default"] = True
                else:
                    for group in state["igs"]:
                        if group["type"] in ("ig_industrialists", "ig_petty_bourgeoisie"):
                            group["in_government"] = False
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 0)
                self.assertNotIn(P + "review_running", state)
                event = world.deliver(arc, "ywc_lan.1107")
                self.assertFalse(option_legal(world, event, "accept_six_reviews"))
                state["is_at_war"] = state["in_default"] = False
                state["states"][0]["owner"] = "LAN"
                for group in state["igs"]:
                    group["in_government"] = True
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 0)
                choose(world, arc, event, "defer_recount")
                before = copy.deepcopy(state)
                for stale in ("defer_recount", "wait_review", "withdraw"):
                    force_option(world, event, stale)
                self.assertEqual(state, before)
                month(world, arc, 5)
                self.assertNotIn(P + "review_mature", state)
                month(world, arc)
                finish_review(world, arc)
                self.assertEqual(state[P + "outcome"], 1)

    def test_resident_route_requires_actual_current_franchise_and_qualified_employed_resident(self):
        for loss in ("franchise", "acceptance", "employment", "wealth", "law"):
            with self.subTest(loss=loss):
                world = new_world("resident")
                arc = public_arc(world.cat)
                play(world, arc, 1100, ROUTES["resident"])
                play(world, arc, 1101, "pay_charter")
                event = world.deliver(arc, "ywc_lan.1102")
                self.assertTrue(option_legal(world, event, "verify_constituency"))
                state = world.countries[world.tag]
                if loss == "franchise": state["country_has_voting_franchise"] = False
                elif loss == "law": state["laws"].remove("law_universal_suffrage")
                elif loss == "wealth": state["modifier:country_voting_power_wealth_threshold_add"] = 100
                else:
                    for pop in state["states"][0]["pops"]:
                        if loss == "acceptance": pop["acceptance"] = 4
                        else: pop["employed"] = False
                self.assertFalse(option_legal(world, event, "verify_constituency"))
                before = copy.deepcopy(state)
                force_option(world, event, "verify_constituency")
                self.assertEqual(state, before)

    def test_foreign_split_state_cannot_supply_owned_other_province(self):
        world = new_world()
        state = world.countries[world.tag]
        foreign = copy.deepcopy(state["states"][0])
        foreign["owner"] = "DEI"
        state["states"][0].update(region="s:STATE_SICHUAN", pops=[])
        state["states"].append(foreign)
        world.refresh(public_arc(world.cat))
        self.assertNotIn(JES[0], world.active[world.tag])
        self.assertNotIn(P + "pilot", state)

    def test_capacity_limits_and_final_repeat_release_preserve_other_arc_slots(self):
        for counter, value in (("ywc_v03_active_arc_count", 3), ("ywc_v03_visible_task_count", 6)):
            with self.subTest(counter=counter):
                world = new_world()
                state = world.countries[world.tag]
                state[counter] = value
                world.refresh(public_arc(world.cat))
                self.assertNotIn(JES[0], world.active[world.tag])
                self.assertEqual(state[counter], value)
        world = new_world()
        state = world.countries[world.tag]
        # These are two independently existing undertakings, not success flags.
        state["ywc_v03_active_arc_count"] = state["ywc_v03_visible_task_count"] = 2
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1107, "accept_six_reviews")
        play(world, arc, 1108, "confirm_current_mandate")
        final = play(world, arc, 1109, "close_established")
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (2, 2))
        before = copy.deepcopy((state, world.treasury))
        for key in ("close_established", "close_compromise", "close_setback", "withdraw"):
            force_option(world, final, key)
        self.assertEqual((state, world.treasury), before)

    def test_three_complete_routes_pay_distinct_actual_amounts_and_handoff_three_journals(self):
        for route, charge, outcome in (("term", 2250, 1), ("resident", 2750, 1),
                                       ("shareholders", 1750, 2)):
            with self.subTest(route=route):
                world = new_world(route)
                state = world.countries[world.tag]
                before = copy.deepcopy((state["laws"], state["institutions"], state["states"], state["igs"]))
                arc = ready_for_review(world, route)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]),
                                 (1, 1))
                self.assertEqual(world.treasury[world.tag], -charge)
                month(world, arc, 6)
                finish_review(world, arc, outcome)
                self.assertEqual(state[P + "outcome"], outcome)
                self.assertEqual(world.treasury[world.tag], -charge)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]),
                                 (0, 0))
                self.assertTrue(all(world.history[world.tag][j] == "complete" for j in JES))
                self.assertEqual((state["laws"], state["institutions"], state["states"], state["igs"]), before)

    def test_conservative_no_mine_no_school_no_franchise_can_choose_explicit_bounded_goal(self):
        for route, charge in (("term", 2250), ("resident", 2750), ("shareholders", 1750)):
            with self.subTest(route=route):
                world = new_world(route, bare=True)
                arc = ready_for_review(world, route, limited=True)
                month(world, arc, 6)
                finish_review(world, arc, 2)
                state = world.countries[world.tag]
                self.assertEqual(state[P + "outcome"], 2)
                self.assertEqual(world.treasury[world.tag], -charge)
                self.assertIn("law_monarchy", state["laws"])
                self.assertFalse(state["country_has_voting_franchise"])

    def test_creation_day_five_months_and_duplicate_callbacks_are_not_six_observations(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        world.pulse(arc)
        self.assertEqual(state[P + "review_streak"], 0)
        for count in range(1, 6):
            month(world, arc)
            world.pulse(arc)
            self.assertEqual(state[P + "review_streak"], count)
            self.assertNotIn(P + "review_mature", state)
            self.assertFalse(world.events)
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 6)
        self.assertEqual(state[P + "review_mature"], 1)
        finish_review(world, arc)
        self.assertEqual(state[P + "outcome"], 1)

    def test_opening_pilot_loss_after_admission_preserves_wait_and_exit(self):
        world = new_world()
        arc = public_arc(world.cat)
        world.refresh(arc)
        state = world.countries[world.tag]
        state["states"][0]["owner"] = "DEI"
        opening = world.deliver(arc, "ywc_lan.1100")
        self.assertFalse(option_legal(world, opening, ROUTES["term"]))
        self.assertTrue(option_legal(world, opening, "wait_pilot"))
        choose(world, arc, opening, "withdraw")
        self.assertEqual(state[P + "outcome"], 4)
        self.assertEqual(world.history[world.tag][JES[0]], "failed")
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)

    def test_current_constituency_reads_same_governing_group_clout_and_approval(self):
        for loss in ("opposition", "clout", "approval", "no_republic", "foreign_state"):
            with self.subTest(loss=loss):
                world = new_world()
                arc = public_arc(world.cat)
                play(world, arc, 1100, ROUTES["term"])
                play(world, arc, 1101, "pay_charter")
                event = world.deliver(arc, "ywc_lan.1102")
                self.assertTrue(option_legal(world, event, "verify_constituency"))
                state = world.countries[world.tag]
                for group in state["igs"]:
                    if group["type"] not in ("ig_industrialists", "ig_petty_bourgeoisie"):
                        continue
                    if loss == "opposition": group["in_government"] = False
                    elif loss == "clout": group["clout"] = .099
                    elif loss == "approval": group["approval"] = -1
                if loss == "no_republic":
                    state["laws"].remove("law_presidential_republic")
                    state["laws"].append("law_monarchy")
                elif loss == "foreign_state":
                    state["states"][0]["owner"] = "DEI"
                self.assertFalse(option_legal(world, event, "verify_constituency"))
                before = copy.deepcopy(state)
                force_option(world, event, "verify_constituency")
                self.assertEqual(state, before)
                self.assertTrue(option_legal(world, event, "withdraw"))

    def test_live_cash_and_all_old_fee_options_are_rechecked_before_mutation(self):
        for number, key in ((1101, "pay_charter"), (1104, "write_public_appeal"),
                             (1106, "pay_public_review")):
            with self.subTest(number=number):
                world = new_world()
                state = world.countries[world.tag]
                arc = public_arc(world.cat)
                sequence = ((1100, ROUTES["term"]), (1101, "pay_charter"),
                            (1102, "verify_constituency"), (1103, "sign_bounded_mandate"),
                            (1104, "write_public_appeal"), (1105, "confirm_current_tax_base"))
                for event_number, choice in sequence:
                    if event_number >= number:
                        break
                    play(world, arc, event_number, choice)
                event = world.deliver(arc, f"ywc_lan.{number}")
                state["gold_reserves"] = -world.treasury[world.tag]
                self.assertFalse(option_legal(world, event, key))
                before = copy.deepcopy((state, world.treasury))
                force_option(world, event, key)
                self.assertEqual((state, world.treasury), before)
                state["gold_reserves"] += 1000
                choose(world, arc, event, key)
                before = copy.deepcopy((state, world.treasury))
                for stale in (key, "withdraw"):
                    force_option(world, event, stale)
                self.assertEqual((state, world.treasury), before)

    def test_actual_twelve_month_public_mandate_expiry_cannot_close_as_permanent_success(self):
        world = new_world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        play(world, arc, 1107, "accept_six_reviews")
        play(world, arc, 1108, "confirm_current_mandate")
        state = world.countries[world.tag]
        self.assertIn(P + "term_due", state)
        month(world, arc, 12)
        final = world.deliver(arc, "ywc_lan.1109")
        self.assertFalse(option_legal(world, final, "close_established"))
        self.assertFalse(option_legal(world, final, "close_compromise"))
        self.assertTrue(option_legal(world, final, "close_setback"))
        choose(world, arc, final, "close_setback")
        self.assertEqual(state[P + "outcome"], 3)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)


if __name__ == "__main__":
    unittest.main()
