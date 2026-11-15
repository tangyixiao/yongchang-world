"""Genuine legacy/foundation LAN choices consumed by the generated middle arc.

No positive story outcome/settled/paid/source flag is seeded. Cash and other
world-fact counterfactuals are explicit, while actual treasury history remains.
"""
import copy
import unittest

from lan_public_runtime import LanPublicWorld
from test_v03_lan_company_public import (
    JES, P, choose, finish_review, force_option, month, new_world, option_legal,
    play, public_arc, ready_for_review,
)


MINE_PUBLIC = ((1000, "public_audit"), (1001, "staff_audit"),
               (1002, "public_share_first"), (1003, "use_shipping"),
               (1004, "merge_customs"), (1005, "fund_audit"))
MINE_FARM = ((1000, "shareholder_farm"), (1001, "staff_audit"),
             (1002, "dividend_first"), (1003, "internal_only"),
             (1004, "separate_books"), (1005, "cap_public_claim"))
RIVER_BOARD = ((1010, "compensate"), (1011, "deed_review"),
               (1012, "notify_neighbour"), (1013, "fund_board"),
               (1014, "keep_restricted"), (1015, "expand_blocks"))
RIVER_RESTRICTED = ((1010, "restrict"), (1011, "deed_review"),
                    (1012, "notify_neighbour"), (1013, "restrict_blocks"),
                    (1014, "keep_restricted"), (1015, "hold_scale"))
FUND_MUTUAL = ((1020, "mutual_fund"), (1021, "enrol_mine"),
               (1022, "assume_debt"), (1023, "fund"),
               (1024, "borrow_practice"), (1025, "pay_both"))
FUND_PRIVATE = ((1020, "private_relief"), (1021, "small_roll"),
                (1022, "company_holds"), (1023, "firm_reserve"),
                (1024, "decline_practice"), (1025, "pay_wages_first"))
SLUGS = {"mine": "v03_lan_mine_accounts", "river": "v03_lan_river_compacts",
         "fund": "v03_lan_work_accident_fund"}
REVIEW = {"mine": 1006, "river": 1016, "fund": 1026}
WORLD_KEYS = (
    "laws", "institutions", "states", "igs", "is_subject", "literacy_rate",
    "country_has_voting_franchise", "net_fixed_income", "bureaucracy",
    "legitimacy", "authority", "yearly_gross_income",
    "modifier:country_voting_power_base_add",
    "modifier:country_voting_power_wealth_threshold_add",
    "modifier:country_allow_voting_full_acceptance_bool",
)


def foundation_arc(world, name):
    return next(a for a in world.cat["arcs"] if a["slug"] == SLUGS[name])


def use_commercial_land_law(world):
    """An actual current-law fixture change, never two laws in one land group."""
    state = world.countries[world.tag]
    land_laws = {"law_serfdom", "law_manorialism", "law_tenant_farmers",
                 "law_peasant_proprietorship", "law_commercialized_agriculture",
                 "law_homesteading"}
    state["laws"] = [law for law in state["laws"] if law not in land_laws]
    state["laws"].append("law_commercialized_agriculture")


def earn_foundation(world, name, plan, terminal="settle_full"):
    """Run native source, including its initially immature observation popup."""
    if name == "river":
        use_commercial_land_law(world)
    arc = foundation_arc(world, name)
    for number, key in plan:
        play(world, arc, number, key)
    deferrals = 0
    for attempt in range(5):
        event = world.deliver(arc, f"ywc_lan.{REVIEW[name]}")
        if option_legal(world, event, "begin_review"):
            choose(world, arc, event, "begin_review")
            break
        if not option_legal(world, event, "defer"):
            raise AssertionError(("immature_native_review_has_no_defer", name, attempt))
        choose(world, arc, event, "defer")
        deferrals += 1
    else:
        raise AssertionError(("native_review_not_mature_after_five_deliveries", name))
    if deferrals < 1:
        raise AssertionError(("expected_real_first_immature_popup", name))
    play(world, arc, REVIEW[name] + 1, terminal)
    return deferrals


def current_cash(world):
    return world.countries[world.tag]["gold_reserves"] + world.treasury[world.tag]


def set_current_cash(world, amount):
    """Set the present engine-owned cash fact; retain all real debit history."""
    world.countries[world.tag]["gold_reserves"] = amount - world.treasury[world.tag]


def become_bounded_conservative(world):
    bare = new_world(bare=True).countries[world.tag]
    keys = ("laws", "institutions", "states", "igs", "country_has_voting_franchise",
            "modifier:country_voting_power_base_add",
            "modifier:country_voting_power_wealth_threshold_add",
            "modifier:country_allow_voting_full_acceptance_bool")
    world.countries[world.tag].update(copy.deepcopy({key: bare[key] for key in keys}))


class LanCompanyCrossEra(unittest.TestCase):
    def world(self, route="term"):
        world = new_world(route=route, legacy=True)
        self.assertIsInstance(world, LanPublicWorld)
        self.assertEqual(world.tag, "LAN")
        self.assertEqual(world.elapsed_months, 18)
        self.assertEqual([day for _, _, day in world.legacy_provenance],
                         [30, 60, 180, 300, 420, 540])
        self.assertEqual(world.history[world.tag]["ywc_je_flavor_lan_charter_1"], "complete")
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_campaign_lan_c1_outcome"], 2)
        self.assertEqual(state["ywc_je_flavor_lan_charter_1_resolved"], 1)
        self.assertEqual(state["states"][0]["owner"], "LAN")
        self.assertEqual(state["states"][0]["region"], "s:STATE_WEST_BORNEO")
        self.assertIn("ywc_v03_lan_inline_candidate_37", world.trigger_defs)
        for slug in SLUGS.values():
            self.assertNotIn(f"ywc_v03_lan_{slug}_started", state)
        self.assertNotIn(P + "charter_paid", state)
        return world

    def assert_old_result(self, world, name, outcome):
        state = world.countries[world.tag]
        key = f"ywc_v03_lan_{SLUGS[name]}"
        self.assertIn(key + "_outcome", state)
        self.assertEqual(state[key + "_outcome"], outcome)
        self.assertEqual(state[key + "_settled"], 1)
        self.assertEqual(state[f"ywc_lan_{name}_settled"], 1)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(state["ywc_v03_visible_task_count"], 0)
        arc = foundation_arc(world, name)
        if outcome == 0:
            self.assertEqual(state[f"ywc_lan_{name}_breach"], 1)
            self.assertEqual(world.history[world.tag][arc["journals"][0]["id"]], "failed")
        else:
            for journal in arc["journals"]:
                self.assertEqual(world.history[world.tag][journal["id"]], "complete")

    def assert_public_closed(self, world, outcome):
        state = world.countries[world.tag]
        self.assertEqual(state[P + "outcome"], outcome)
        self.assertEqual(state[P + "review_streak"], 6)
        self.assertEqual(state["ywc_v03_lan_v03_lan_company_public_outcome"], outcome)
        self.assertEqual(state["ywc_v03_lan_v03_lan_company_public_settled"], 1)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(state["ywc_v03_visible_task_count"], 0)
        for jid in JES:
            self.assertEqual(world.history[world.tag][jid], "complete")

    def start_public_to_appeal(self, world, route="term"):
        arc = public_arc(world.cat)
        key = {"term": "term_company_republic", "resident": "resident_representation",
               "shareholders": "bounded_shareholders"}[route]
        for number, choice in ((1100, key), (1101, "pay_charter"),
                               (1102, "verify_constituency"),
                               (1103, "sign_bounded_mandate")):
            play(world, arc, number, choice)
        return arc

    def finish_after_appeal(self, world, arc, limited=False, outcome=1):
        play(world, arc, 1105, "confirm_bounded_accounts" if limited else "confirm_current_tax_base")
        play(world, arc, 1106, "pay_public_review")
        month(world, arc, 6)
        finish_review(world, arc, outcome)

    def test_real_public_share_audit_halves_company_charter_after_earned_legacy_admission(self):
        world = self.world()
        before = world.treasury[world.tag]
        earn_foundation(world, "mine", MINE_PUBLIC)
        self.assertEqual(world.treasury[world.tag] - before, -2000)
        self.assert_old_result(world, "mine", 1)
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_lan_mine_public_share_taken"], 1)
        self.assertEqual(state["ywc_lan_mine_reserve_paid"], 1)
        start = world.treasury[world.tag]
        arc = ready_for_review(world, route="term")
        self.assertEqual(state[P + "charter_paid_amount"], 500)
        self.assertEqual(state[P + "charter_source_mine"], 1)
        self.assertEqual(state[P + "appeal_paid_amount"], 250)
        self.assertEqual(state[P + "review_paid_amount"], 1000)
        month(world, arc, 6)
        finish_review(world, arc)
        self.assertEqual(world.treasury[world.tag] - start, -1750)
        self.assert_public_closed(world, 1)

    def test_real_outcome_one_with_dividend_does_not_turn_share_choice_into_public_money(self):
        world = self.world()
        plan = tuple((n, "dividend_first" if n == 1002 else key) for n, key in MINE_PUBLIC)
        earn_foundation(world, "mine", plan)
        self.assert_old_result(world, "mine", 1)
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_lan_mine_share_choice"], 1)
        self.assertEqual(state["ywc_lan_mine_dividend_taken"], 1)
        self.assertNotIn("ywc_lan_mine_public_share_taken", state)
        start = world.treasury[world.tag]
        arc = ready_for_review(world)
        self.assertEqual(state[P + "charter_paid_amount"], 1000)
        self.assertNotIn(P + "charter_source_mine", state)
        month(world, arc, 6)
        finish_review(world, arc)
        self.assertEqual(world.treasury[world.tag] - start, -2250)
        self.assert_public_closed(world, 1)

    def test_real_mutual_fund_halves_resident_review_as_a_separate_actual_payment(self):
        world = self.world(route="resident")
        before = world.treasury[world.tag]
        earn_foundation(world, "fund", FUND_MUTUAL)
        self.assert_old_result(world, "fund", 1)
        self.assertEqual(world.treasury[world.tag] - before, -4000)
        state = world.countries[world.tag]
        for suffix in ("filing_fee_paid", "assumption_fee_paid", "mutual_reserve_paid",
                       "pay_both_reserve_paid", "mutual_opened", "both_paid", "practice_adopted"):
            self.assertEqual(state["ywc_lan_fund_" + suffix], 1)
        start = world.treasury[world.tag]
        arc = ready_for_review(world, route="resident")
        self.assertEqual(state[P + "charter_paid_amount"], 1500)
        self.assertEqual(state[P + "review_paid_amount"], 500)
        self.assertEqual(state[P + "review_source_fund"], 1)
        self.assertEqual(world.treasury[world.tag] - start, -2250)
        month(world, arc, 6)
        finish_review(world, arc)
        self.assert_public_closed(world, 1)

    def test_real_private_relief_reservation_is_not_a_cash_funded_public_discount(self):
        world = self.world(route="resident")
        before = world.treasury[world.tag]
        earn_foundation(world, "fund", FUND_PRIVATE, "settle_compromise")
        self.assert_old_result(world, "fund", 2)
        self.assertEqual(world.treasury[world.tag], before)
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_lan_fund_firm_reserved"], 1)
        self.assertNotIn("ywc_lan_fund_mutual_reserve_paid", state)
        self.assertNotIn("ywc_lan_fund_pay_both_reserve_paid", state)
        start = world.treasury[world.tag]
        arc = ready_for_review(world, route="resident")
        self.assertEqual(state[P + "review_paid_amount"], 1000)
        self.assertNotIn(P + "review_source_fund", state)
        month(world, arc, 6)
        finish_review(world, arc)
        self.assertEqual(world.treasury[world.tag] - start, -2750)
        self.assert_public_closed(world, 1)

    def test_real_river_board_waives_appeal_without_fake_payment_or_stale_clawback(self):
        world = self.world()
        before = world.treasury[world.tag]
        earn_foundation(world, "river", RIVER_BOARD)
        self.assert_old_result(world, "river", 1)
        self.assertEqual(world.treasury[world.tag] - before, -2000)
        state = world.countries[world.tag]
        for suffix in ("board_chosen", "board_funded", "deed_checked", "neighbour_notified"):
            self.assertEqual(state["ywc_lan_river_" + suffix], 1)
        start = world.treasury[world.tag]
        arc = self.start_public_to_appeal(world)
        event = world.deliver(arc, "ywc_lan.1104")
        set_current_cash(world, 0)
        self.assertTrue(option_legal(world, event, "reuse_river_board"))
        self.assertFalse(option_legal(world, event, "write_public_appeal"))
        cash_before = world.treasury[world.tag]
        choose(world, arc, event, "reuse_river_board")
        self.assertEqual(world.treasury[world.tag], cash_before)
        self.assertEqual(state[P + "appeal_waived"], 1)
        self.assertEqual(state[P + "appeal_source_river"], 1)
        self.assertNotIn(P + "appeal_paid", state)
        self.assertNotIn(P + "appeal_paid_amount", state)
        self.assertEqual(state[P + "appeal_pilot"], state[P + "pilot"])
        # Temporary real ownership loss invalidates the source's present office.
        # A paid old option still cannot charge a completed waiver at a new stage.
        state["states"][0]["owner"] = "DEI"
        frozen = copy.deepcopy((state, world.treasury))
        force_option(world, event, "write_public_appeal")
        force_option(world, event, "reuse_river_board")
        self.assertEqual((state, world.treasury), frozen)
        state["states"][0]["owner"] = "LAN"
        set_current_cash(world, 100000)
        self.finish_after_appeal(world, arc)
        self.assertEqual(world.treasury[world.tag] - start, -2000)
        self.assertNotIn(P + "appeal_paid", state)
        self.assert_public_closed(world, 1)

    def test_two_real_policy_bundles_change_two_nodes_on_the_same_current_company_route(self):
        worlds = []
        for policy in ("public_board", "farmed_restricted"):
            world = self.world()
            if policy == "public_board":
                earn_foundation(world, "mine", MINE_PUBLIC)
                earn_foundation(world, "river", RIVER_BOARD)
                self.assert_old_result(world, "mine", 1)
                self.assert_old_result(world, "river", 1)
            else:
                earn_foundation(world, "mine", MINE_FARM, "settle_compromise")
                earn_foundation(world, "river", RIVER_RESTRICTED, "settle_compromise")
                self.assert_old_result(world, "mine", 2)
                self.assert_old_result(world, "river", 2)
            # Equal present cash is an explicit engine-fact counterfactual, not a
            # story payment: old treasury debits and paid producers stay intact.
            set_current_cash(world, 100000)
            worlds.append(world)
        left, right = worlds
        ls, rs = (w.countries[w.tag] for w in worlds)
        self.assertEqual({k: ls[k] for k in WORLD_KEYS}, {k: rs[k] for k in WORLD_KEYS})
        self.assertEqual(current_cash(left), current_cash(right))
        self.assertEqual(ls["ywc_campaign_lan_c1_outcome"], rs["ywc_campaign_lan_c1_outcome"])
        observed = []
        for world, expected_charter, expected_appeal in ((left, 500, 0), (right, 1000, 250)):
            state = world.countries[world.tag]
            start = world.treasury[world.tag]
            arc = public_arc(world.cat)
            play(world, arc, 1100, "term_company_republic")
            before = world.treasury[world.tag]
            play(world, arc, 1101, "pay_charter")
            charter = before - world.treasury[world.tag]
            self.assertEqual(charter, expected_charter)
            self.assertEqual(state[P + "charter_paid_amount"], expected_charter)
            play(world, arc, 1102, "verify_constituency")
            play(world, arc, 1103, "sign_bounded_mandate")
            event = world.deliver(arc, "ywc_lan.1104")
            before = world.treasury[world.tag]
            reusable = option_legal(world, event, "reuse_river_board")
            self.assertEqual(reusable, expected_appeal == 0)
            choose(world, arc, event, "reuse_river_board" if reusable else "write_public_appeal")
            appeal = before - world.treasury[world.tag]
            self.assertEqual(appeal, expected_appeal)
            self.assertEqual(state[P + "mode"], 1)
            self.finish_after_appeal(world, arc)
            self.assertEqual(state[P + "review_paid_amount"], 1000)
            self.assertEqual(world.treasury[world.tag] - start,
                             -expected_charter - expected_appeal - 1000)
            self.assert_public_closed(world, 1)
            observed.append((charter, appeal))
        self.assertEqual(observed, [(500, 0), (1000, 250)])

    def test_current_source_loss_and_half_only_cash_cannot_reuse_a_real_old_discount(self):
        world = self.world()
        earn_foundation(world, "mine", MINE_PUBLIC)
        self.assert_old_result(world, "mine", 1)
        state = world.countries[world.tag]
        arc = public_arc(world.cat)
        play(world, arc, 1100, "term_company_republic")
        event = world.deliver(arc, "ywc_lan.1101")
        office = next(b for b in state["states"][0]["buildings"]
                      if b["type"] == "building_government_administration")
        office["occupancy"] = .5
        set_current_cash(world, 500)
        self.assertEqual(state["ywc_lan_mine_established"], 1)
        self.assertEqual(state["ywc_lan_mine_public_share_taken"], 1)
        self.assertFalse(option_legal(world, event, "pay_charter"))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, event, "pay_charter")
        self.assertEqual((state, world.treasury), before)
        self.assertNotIn(P + "charter_paid", state)
        set_current_cash(world, 1000)
        cash_before = world.treasury[world.tag]
        choose(world, arc, event, "pay_charter")
        self.assertEqual(world.treasury[world.tag] - cash_before, -1000)
        self.assertEqual(state[P + "charter_paid_amount"], 1000)
        self.assertNotIn(P + "charter_source_mine", state)
        play(world, arc, 1102, "withdraw")
        self.assertEqual(state[P + "outcome"], 4)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(state["ywc_v03_visible_task_count"], 0)

    def test_real_compromises_withdrawal_zero_and_nonparticipation_reach_bounded_conservative_end(self):
        for history in ("mine_compromise", "river_compromise", "fund_compromise",
                        "mine_withdrawn", "not_participated"):
            with self.subTest(history=history):
                world = self.world()
                state = world.countries[world.tag]
                if history == "mine_compromise":
                    earn_foundation(world, "mine", MINE_FARM, "settle_compromise")
                    self.assert_old_result(world, "mine", 2)
                elif history == "river_compromise":
                    earn_foundation(world, "river", RIVER_RESTRICTED, "settle_compromise")
                    self.assert_old_result(world, "river", 2)
                elif history == "fund_compromise":
                    earn_foundation(world, "fund", FUND_PRIVATE, "settle_compromise")
                    self.assert_old_result(world, "fund", 2)
                elif history == "mine_withdrawn":
                    play(world, foundation_arc(world, "mine"), 1000, "withdraw")
                    self.assert_old_result(world, "mine", 0)
                else:
                    for slug in SLUGS.values():
                        self.assertNotIn(f"ywc_v03_lan_{slug}_outcome", state)
                become_bounded_conservative(world)
                before_facts = copy.deepcopy({key: state[key] for key in WORLD_KEYS})
                start = world.treasury[world.tag]
                arc = ready_for_review(world, route="term", limited=True)
                self.assertEqual(state[P + "charter_paid_amount"], 1000)
                self.assertEqual(state[P + "appeal_paid_amount"], 250)
                self.assertEqual(state[P + "review_paid_amount"], 1000)
                self.assertNotIn(P + "charter_source_mine", state)
                self.assertNotIn(P + "appeal_source_river", state)
                self.assertNotIn(P + "review_source_fund", state)
                month(world, arc, 6)
                finish_review(world, arc, outcome=2)
                self.assertEqual(world.treasury[world.tag] - start, -2250)
                self.assertEqual({key: state[key] for key in WORLD_KEYS}, before_facts)
                self.assertIn("law_monarchy", state["laws"])
                self.assertIn("law_no_schools", state["laws"])
                self.assertEqual(state["institutions"], {})
                self.assert_public_closed(world, 2)


if __name__ == "__main__":
    unittest.main()
