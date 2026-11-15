"""Earn old DMG results through native source, then consume them in the market.

No positive outcome, settled, paid or source flag is injected. The only later
fixture changes are current-world laws, institutions, staff, cash and ownership.
"""
import copy
import unittest

from dmg_market_runtime import DmgMarketWorld
from test_v03_dmg_luzon_market import (
    JES, P, choose, finish_review, force_option, market_arc, month, new_world,
    option_legal, play, ready_for_review,
)
from test_v03_dmg_school_cross_era import (
    COMMON_ESTABLISHED, COMMON_TERRITORIAL, COURT_ESTABLISHED, COURT_LOCAL,
    LAND_MIXED,
)


COMMON = "v03_dmg_common_subjects"
LAND = "v03_dmg_two_land_titles"
COURT = "v03_dmg_court_provinces"
L = "ywc_v03_dmg_v03_dmg_luzon_border_market_"


def early_arc(world, slug):
    return next(arc for arc in world.cat["arcs"] if arc["slug"] == slug)


def earn(world, slug, plan):
    arc = early_arc(world, slug)
    for number, key in plan:
        play(world, arc, number, key)
    return arc


def local_office(world):
    return next(building for building in world.countries[world.tag]["states"][0]["buildings"]
                if building["type"] == "building_government_administration")


def office_pop(world):
    return next(pop for pop in world.countries[world.tag]["states"][0]["pops"]
                if pop["type"] == "bureaucrats")


def become_conservative(world):
    """Copy only present-world facts; earned story state stays in the same dict."""
    bare = new_world(bare=True, access="none").countries[world.tag]
    world.countries[world.tag].update(copy.deepcopy({
        key: bare[key] for key in ("laws", "institutions", "states", "literacy_rate")
    }))


class DmgMarketCrossEra(unittest.TestCase):
    def world(self):
        world = new_world()
        self.assertIsInstance(world, DmgMarketWorld)
        self.assertIn("ywc_v03_dmg_inline_candidate_55", world.trigger_defs)
        self.assertTrue(all(jid in world.journal_defs for jid in JES))
        state = world.countries[world.tag]
        for slug in (COMMON, LAND, COURT):
            self.assertNotIn(f"ywc_v03_dmg_{slug}_settled", state)
        self.assertNotIn(P + "setup_paid", state)
        return world

    def assert_old_closed(self, world, slug, outcome, failed=False):
        state = world.countries[world.tag]
        self.assertEqual(state[f"ywc_v03_dmg_{slug}_settled"], 1)
        if slug == COMMON:
            self.assertEqual(state[f"ywc_v03_dmg_{slug}_outcome"], outcome)
        else:
            key = "ywc_dmg_titles_outcome" if slug == LAND else "ywc_dmg_court_outcome"
            self.assertEqual(state[key], outcome)
        statuses = [world.history[world.tag].get(journal["id"])
                    for journal in early_arc(world, slug)["journals"]]
        if failed:
            self.assertIn("failed", statuses)
        else:
            self.assertTrue(all(status == "complete" for status in statuses), statuses)
        self.assertEqual((state["ywc_v03_active_arc_count"],
                          state["ywc_v03_visible_task_count"]), (0, 0))

    def assert_market_closed(self, world, outcome):
        state = world.countries[world.tag]
        self.assertEqual(state[P + "outcome"], outcome)
        self.assertEqual(state[L + "outcome"], outcome)
        self.assertEqual(state[L + "settled"], 1)
        self.assertEqual(state[P + "review_streak"], 6)
        self.assertTrue(all(world.history[world.tag][jid] == "complete" for jid in JES))
        self.assertEqual((state["ywc_v03_active_arc_count"],
                          state["ywc_v03_visible_task_count"]), (0, 0))

    def test_real_common_result_halves_controlled_setup_but_absence_or_territorial_result_does_not(self):
        for previous, expected in (("common", 500), ("territorial", 1000), ("absent", 1000)):
            with self.subTest(previous=previous):
                world = self.world()
                if previous != "absent":
                    earn(world, COMMON, COMMON_ESTABLISHED if previous == "common"
                         else COMMON_TERRITORIAL)
                    self.assert_old_closed(world, COMMON, 1 if previous == "common" else 2)
                state = world.countries[world.tag]
                before = world.treasury[world.tag]
                arc = market_arc(world.cat)
                play(world, arc, 1100, "controlled_market")
                play(world, arc, 1101, "pay_setup")
                self.assertEqual(state[P + "budget"], 1000)
                self.assertEqual(state[P + "setup_paid_amount"], expected)
                self.assertEqual(world.treasury[world.tag] - before, -expected)
                self.assertEqual(P + "setup_source_common" in state, previous == "common")

    def test_earned_common_discount_rechecks_cash_and_current_employee_at_execution(self):
        world = self.world()
        earn(world, COMMON, COMMON_ESTABLISHED)
        self.assert_old_closed(world, COMMON, 1)
        state = world.countries[world.tag]
        arc = market_arc(world.cat)
        play(world, arc, 1100, "controlled_market")
        event = world.deliver(arc, "ywc_dmg.1101")
        state["gold_reserves"] = -world.treasury[world.tag] + 500
        self.assertTrue(option_legal(world, event, "pay_setup"))
        office_pop(world)["employed"] = False
        self.assertFalse(option_legal(world, event, "pay_setup"))
        self.assertEqual(state["ywc_dmg_outcome_common_qualification"], 1)
        before = copy.deepcopy((state, world.treasury))
        force_option(world, event, "pay_setup")
        self.assertEqual((state, world.treasury), before)
        office_pop(world)["employed"] = True
        cash = world.treasury[world.tag]
        choose(world, arc, event, "pay_setup")
        self.assertEqual(world.treasury[world.tag] - cash, -500)
        office_pop(world)["employed"] = False
        before = copy.deepcopy((state, world.treasury))
        force_option(world, event, "pay_setup")
        self.assertEqual((state, world.treasury), before)
        self.assertEqual(state[P + "setup_paid_amount"], 500)

    def test_real_paid_mixed_land_and_village_terms_allow_hearing_at_quarter_staffing(self):
        world = self.world()
        before_land = world.treasury[world.tag]
        earn(world, LAND, LAND_MIXED)
        self.assert_old_closed(world, LAND, 1)
        state = world.countries[world.tag]
        self.assertLess(world.treasury[world.tag], before_land)
        self.assertEqual(state["ywc_dmg_titles_compensation_paid"], 1)
        self.assertEqual(state["ywc_dmg_titles_newcomer_mode"], 2)
        local_office(world)["occupancy"] = .25
        arc = market_arc(world.cat)
        for n, key in ((1100, "controlled_market"), (1101, "pay_setup"),
                       (1102, "limit_local_livelihood")):
            play(world, arc, n, key)
        hearing = world.deliver(arc, "ywc_dmg.1103")
        self.assertTrue(option_legal(world, hearing, "reuse_village_clause"))
        self.assertFalse(option_legal(world, hearing, "write_new_hearing"))
        cash = world.treasury[world.tag]
        choose(world, arc, hearing, "reuse_village_clause")
        self.assertEqual(world.treasury[world.tag], cash)
        self.assertEqual(state[P + "hearing"], 1)
        play(world, arc, 1104, "sign_six_month_terms")
        month(world, arc, 6)
        finish_review(world, arc, limited=True)
        self.assert_market_closed(world, 2)

    def test_two_earned_policy_bundles_change_setup_and_hearing_under_the_same_current_facts(self):
        worlds = [self.world(), self.world()]
        individual = tuple((n, "individual_appeal" if n == 1014 else key)
                           for n, key in LAND_MIXED)
        for world, common_plan, land_plan in (
            (worlds[0], COMMON_ESTABLISHED, LAND_MIXED),
            (worlds[1], COMMON_TERRITORIAL, individual),
        ):
            earn(world, COMMON, common_plan)
            earn(world, LAND, land_plan)
            self.assert_old_closed(world, LAND, 1)
            # Match current available cash without changing any earned result.
            world.countries[world.tag]["gold_reserves"] = -world.treasury[world.tag] + 10000
        fact_keys = ("laws", "institutions", "states", "bureaucracy", "net_fixed_income",
                     "is_at_war", "yearly_gross_income", "authority")
        left, right = [world.countries[world.tag] for world in worlds]
        self.assertEqual({k: left[k] for k in fact_keys}, {k: right[k] for k in fact_keys})
        self.assertEqual(worlds[0].markets, worlds[1].markets)
        self.assertEqual(worlds[0].treaties, worlds[1].treaties)
        arcs = []
        for world, expected in zip(worlds, (500, 1000)):
            arc = market_arc(world.cat)
            arcs.append(arc)
            before = world.treasury[world.tag]
            play(world, arc, 1100, "controlled_market")
            play(world, arc, 1101, "pay_setup")
            self.assertEqual(world.treasury[world.tag] - before, -expected)
            local_office(world)["occupancy"] = .25
            play(world, arc, 1102, "limit_local_livelihood")
        hearings = [world.deliver(arc, "ywc_dmg.1103") for world, arc in zip(worlds, arcs)]
        self.assertEqual({k: left[k] for k in fact_keys}, {k: right[k] for k in fact_keys})
        self.assertTrue(option_legal(worlds[0], hearings[0], "reuse_village_clause"))
        self.assertFalse(option_legal(worlds[0], hearings[0], "write_new_hearing"))
        self.assertFalse(option_legal(worlds[1], hearings[1], "reuse_village_clause"))
        self.assertFalse(option_legal(worlds[1], hearings[1], "write_new_hearing"))
        local_office(worlds[1])["occupancy"] = .5
        self.assertTrue(option_legal(worlds[1], hearings[1], "write_new_hearing"))
        for world, arc, event, key in (
            (worlds[0], arcs[0], hearings[0], "reuse_village_clause"),
            (worlds[1], arcs[1], hearings[1], "write_new_hearing"),
        ):
            cash = world.treasury[world.tag]
            choose(world, arc, event, key)
            self.assertEqual(world.treasury[world.tag], cash)
            play(world, arc, 1104, "sign_six_month_terms")
            month(world, arc, 6)
            finish_review(world, arc, limited=True)
            self.assert_market_closed(world, 2)
        self.assertEqual((left[P + "setup_paid_amount"], right[P + "setup_paid_amount"]), (500, 1000))
        self.assertEqual((left[P + "bill_paid_amount"], right[P + "bill_paid_amount"]), (1000, 1000))

    def test_real_court_cosign_and_budget_halve_the_multilateral_bill_but_not_setup(self):
        for previous, expected_bill in (("central", 1000), ("absent", 2000)):
            with self.subTest(previous=previous):
                world = self.world()
                if previous == "central":
                    earn(world, COURT, COURT_ESTABLISHED)
                    self.assert_old_closed(world, COURT, 1)
                    state = world.countries[world.tag]
                    for flag in ("ywc_dmg_court_charter_paid", "ywc_dmg_court_budget_paid",
                                 "ywc_dmg_joint_appointment_clause", "ywc_dmg_court_successor_terms"):
                        self.assertEqual(state[flag], 1)
                    self.assertEqual(state["ywc_dmg_court_representation"], 2)
                    self.assertEqual(state["ywc_dmg_court_defence_veto"], 1)
                state = world.countries[world.tag]
                before = world.treasury[world.tag]
                arc = ready_for_review(world, route="multilateral")
                self.assertEqual(state[P + "setup_paid_amount"], 2000)
                self.assertEqual(world.treasury[world.tag] - before, -2000)
                month(world, arc, 6)
                finish_review(world, arc, route="multilateral")
                self.assertEqual(state[P + "bill_paid_amount"], expected_bill)
                self.assertEqual(P + "bill_source_court" in state, previous == "central")
                self.assertEqual(world.treasury[world.tag] - before, -2000 - expected_bill)
                self.assert_market_closed(world, 1)

    def test_earned_court_discount_reprices_on_current_office_loss_and_paid_bill_is_not_reclaimed(self):
        world = self.world()
        earn(world, COURT, COURT_ESTABLISHED)
        self.assert_old_closed(world, COURT, 1)
        state = world.countries[world.tag]
        arc = ready_for_review(world, route="multilateral", limited=True)
        month(world, arc, 6)
        bill = world.deliver(arc, "ywc_dmg.1105")
        state["gold_reserves"] = -world.treasury[world.tag] + 1000
        self.assertTrue(option_legal(world, bill, "pay_review_bill"))
        # Half staffing retains the new hearing and local target, but loses
        # the full-office qualification for the old budget discount.
        local_office(world)["occupancy"] = .5
        self.assertTrue(world.conditions(world.trigger_defs[P + "operating_conditions"], world.tag))
        self.assertFalse(option_legal(world, bill, "pay_review_bill"))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, bill, "pay_review_bill")
        self.assertEqual((state, world.treasury), before)
        local_office(world)["occupancy"] = 1
        cash = world.treasury[world.tag]
        choose(world, arc, bill, "pay_review_bill")
        self.assertEqual(world.treasury[world.tag] - cash, -1000)
        self.assertEqual(state[P + "bill_source_court"], 1)
        local_office(world)["occupancy"] = .5
        before = copy.deepcopy((state, world.treasury))
        force_option(world, bill, "pay_review_bill")
        self.assertEqual((state, world.treasury), before)
        play(world, arc, 1106, "retain_limited")
        play(world, arc, 1107, "close_compromise")
        self.assertEqual(state[P + "bill_paid_amount"], 1000)
        self.assert_market_closed(world, 2)

    def test_real_court_history_without_current_full_office_pays_the_normal_limited_bill(self):
        world = self.world()
        earn(world, COURT, COURT_ESTABLISHED)
        self.assert_old_closed(world, COURT, 1)
        become_conservative(world)
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_dmg_court_budget_paid"], 1)
        self.assertEqual(local_office(world)["occupancy"], .5)
        before = world.treasury[world.tag]
        arc = ready_for_review(world, route="multilateral", limited=True)
        month(world, arc, 6)
        finish_review(world, arc, route="multilateral", limited=True)
        self.assertEqual(state[P + "setup_paid_amount"], 2000)
        self.assertEqual(state[P + "bill_paid_amount"], 2000)
        self.assertNotIn(P + "bill_source_court", state)
        self.assertEqual(world.treasury[world.tag] - before, -4000)
        self.assert_market_closed(world, 2)

    def test_real_prior_2_3_4_5_and_nonparticipation_reach_a_conservative_limited_end(self):
        for previous in ("territorial_2", "local_court_3", "withdrawn_4", "limited_5", "absent"):
            with self.subTest(previous=previous):
                world = self.world()
                state = world.countries[world.tag]
                if previous == "territorial_2":
                    earn(world, COMMON, COMMON_TERRITORIAL)
                    self.assert_old_closed(world, COMMON, 2)
                elif previous == "local_court_3":
                    earn(world, COURT, COURT_LOCAL)
                    self.assert_old_closed(world, COURT, 3)
                elif previous == "withdrawn_4":
                    arc = early_arc(world, COMMON)
                    play(world, arc, 1000, "withdraw")
                    self.assert_old_closed(world, COMMON, 4, failed=True)
                elif previous == "limited_5":
                    arc = earn(world, COMMON, COMMON_ESTABLISHED[:-1])
                    final = world.deliver(arc, "ywc_dmg.1009")
                    self.assertTrue(option_legal(world, final, "common_qualification"))
                    for pop in state["states"][0]["pops"]:
                        pop["acceptance"] = 4
                    self.assertFalse(option_legal(world, final, "common_qualification"))
                    self.assertTrue(option_legal(world, final, "limited_settlement"))
                    choose(world, arc, final, "limited_settlement")
                    self.assert_old_closed(world, COMMON, 5)
                else:
                    self.assertTrue(all(f"ywc_v03_dmg_{slug}_started" not in state
                                        for slug in (COMMON, LAND, COURT)))
                become_conservative(world)
                facts_before = copy.deepcopy({key: state[key] for key in
                    ("laws", "institutions", "states", "literacy_rate")})
                before = world.treasury[world.tag]
                arc = ready_for_review(world, limited=True)
                month(world, arc, 6)
                finish_review(world, arc, limited=True)
                self.assertEqual(state[P + "setup_paid_amount"], 1000)
                self.assertEqual(state[P + "bill_paid_amount"], 1000)
                self.assertNotIn(P + "setup_source_common", state)
                self.assertNotIn(P + "bill_source_court", state)
                self.assertEqual(world.treasury[world.tag] - before, -2000)
                self.assertEqual({key: state[key] for key in facts_before}, facts_before)
                self.assert_market_closed(world, 2)

    def test_genuine_common_history_cannot_pay_through_a_foreign_owned_pilot(self):
        world = self.world()
        earn(world, COMMON, COMMON_ESTABLISHED)
        self.assert_old_closed(world, COMMON, 1)
        state = world.countries[world.tag]
        arc = market_arc(world.cat)
        play(world, arc, 1100, "controlled_market")
        state["states"][0]["owner"] = "PHI"
        event = world.deliver(arc, "ywc_dmg.1101")
        self.assertFalse(option_legal(world, event, "pay_setup"))
        self.assertTrue(option_legal(world, event, "wait_cash"))
        self.assertTrue(option_legal(world, event, "withdraw"))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, event, "pay_setup")
        self.assertEqual((state, world.treasury), before)
        choose(world, arc, event, "withdraw")
        self.assertEqual(state[P + "outcome"], 4)
        self.assertEqual(world.history[world.tag][JES[0]], "failed")
        self.assertEqual((state["ywc_v03_active_arc_count"],
                          state["ywc_v03_visible_task_count"]), (0, 0))
    def test_real_land_without_village_cosignature_needs_a_better_staffed_new_hearing(self):
        world = self.world()
        individual = tuple((n, "individual_appeal" if n == 1014 else key)
                           for n, key in LAND_MIXED)
        earn(world, LAND, individual)
        self.assert_old_closed(world, LAND, 1)
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_dmg_titles_compensation_paid"], 1)
        self.assertEqual(state["ywc_dmg_titles_newcomer_mode"], 1)
        local_office(world)["occupancy"] = .25
        arc = market_arc(world.cat)
        for n, key in ((1100, "controlled_market"), (1101, "pay_setup"),
                       (1102, "limit_local_livelihood")):
            play(world, arc, n, key)
        hearing = world.deliver(arc, "ywc_dmg.1103")
        self.assertFalse(option_legal(world, hearing, "reuse_village_clause"))
        self.assertFalse(option_legal(world, hearing, "write_new_hearing"))
        local_office(world)["occupancy"] = .5
        self.assertTrue(option_legal(world, hearing, "write_new_hearing"))
        choose(world, arc, hearing, "write_new_hearing")
        self.assertEqual(state[P + "hearing"], 2)
        play(world, arc, 1104, "sign_six_month_terms")
        month(world, arc, 6)
        finish_review(world, arc, limited=True)
        self.assert_market_closed(world, 2)


if __name__ == "__main__":
    unittest.main()
