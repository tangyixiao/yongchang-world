"""Consume genuine early DMG results through current generated school ASTs.

No positive outcome/settled/paid/source flag is injected. Earlier results are
earned by native event choices and pulses. Later factual changes are explicit
Luzon law, institution, employment, ownership or acceptance facts only.
"""
import copy
import unittest

from shu_kor_strict_review_runtime import Strict
from test_v03_dmg_school_languages import (
    JE, choose, finish_review, force_option, month, new_world, option_legal,
    play, ready_for_review, school_arc,
)


COMMON_ESTABLISHED = (
    (1000, "common_qualification"), (1001, "first"),
    (1002, "open_competition"), (1003, "joint_hearing"),
    (1004, "first"), (1005, "first"),
    (1006, "common_qualification"), (1007, "first"),
    (1008, "first"), (1009, "common_qualification"),
)
COMMON_TERRITORIAL = (
    (1000, "territorial_compact"), (1001, "second"),
    (1002, "open_competition"), (1003, "noble_guarantee"),
    (1004, "second"), (1005, "second"),
    (1006, "territorial_compact"), (1007, "second"),
    (1008, "first"), (1009, "territorial_compact"),
)
COURT_ESTABLISHED = (
    (1016, "royal_administration"), (1017, "central_audit_pays"),
    (1018, "authorize_staffed"), (1019, "royal_sole_review"),
    (1020, "office_charter_cosign"), (1021, "court_keeps_control"),
    (1022, "confirm_signed_terms"), (1023, "confirm_royal"),
)
COURT_LOCAL = (
    (1016, "local_compact"), (1017, "local_share_countersign"),
    (1018, "temporary_deputy"), (1019, "royal_sole_review"),
    (1020, "old_ledger_consultation"), (1021, "old_system_no_veto"),
    (1022, "confirm_signed_terms"), (1023, "confirm_local"),
)
LAND_MIXED = (
    (1010, "mixed_arbitration"), (1011, "joint_survey"),
    (1012, "local_joint_guarantee"), (1013, "pay_actual_cultivator"),
    (1014, "village_cosignature"), (1015, "confirm_mixed"),
)
P = "ywc_dmg_school_"


def early_arc(world, slug):
    return next(arc for arc in world.cat["arcs"] if arc["slug"] == slug)


def play_early(world, slug, plan):
    """Choose actual generated options; native helpers alone produce results."""
    arc = early_arc(world, slug)
    for number, key in plan:
        play(world, arc, number, key)
    return arc


def become_conservative_without_schools(world):
    """Change only present engine facts, preserving all earned early history."""
    bare = new_world(bare=True).countries[world.tag]
    world.countries[world.tag].update(copy.deepcopy({
        key: bare[key] for key in ("laws", "institutions", "states", "literacy_rate")
    }))


class DmgSchoolCrossEra(unittest.TestCase):
    def test_earned_discounts_reprice_at_execution_and_settled_payments_are_not_reclaimed(self):
        for source in ("common", "court"):
            with self.subTest(source=source):
                world = self.world()
                if source == "common":
                    play_early(world, "v03_dmg_common_subjects", COMMON_ESTABLISHED)
                    arc = school_arc(world.cat)
                    play(world, arc, 1120, "bilingual_public")
                    number, key = 1121, "pay_setup"
                else:
                    play_early(world, "v03_dmg_court_provinces", COURT_ESTABLISHED)
                    # Keep current full offices initially, but select an explicit
                    # limited goal so later 25% offices still support operation.
                    arc = ready_for_review(world, route="central", limited=True)
                    month(world, arc, 6)
                    number, key = 1124, "pay_next_term"
                state = world.countries[world.tag]
                event = world.deliver(arc, f"ywc_dmg.{number}")
                state["gold_reserves"] = -world.treasury[world.tag] + 500
                self.assertTrue(option_legal(world, event, key))
                if source == "common":
                    office_pop = next(p for p in state["states"][0]["pops"]
                                      if p["type"] == "bureaucrats")
                    office_pop["employed"] = False
                else:
                    office_pop = next(p for p in state["states"][0]["pops"]
                                      if p["type"] == "bureaucrats")
                    office_pop["workplace"]["occupancy"] = 0.25
                self.assertFalse(option_legal(world, event, key))
                before = copy.deepcopy((state, world.treasury))
                force_option(world, event, key)
                self.assertEqual((state, world.treasury), before)
                if source == "common":
                    office_pop["employed"] = True
                else:
                    office_pop["workplace"]["occupancy"] = 1
                before_cash = world.treasury[world.tag]
                choose(world, arc, event, key)
                self.assertEqual(world.treasury[world.tag] - before_cash, -500)
                if source == "common":
                    office_pop["employed"] = False
                else:
                    office_pop["workplace"]["occupancy"] = 0.25
                before = copy.deepcopy((state, world.treasury))
                force_option(world, event, key)
                self.assertEqual((state, world.treasury), before)
                self.assertEqual(state[P + ("setup_paid_amount" if source == "common"
                                            else "bill_paid_amount")], 500)

    def world(self):
        world = new_world()
        self.assertIsInstance(world, Strict)
        self.assertEqual(world.tag, "DMG")
        self.assertIn("ywc_v03_dmg_inline_candidate_49", world.trigger_defs,
                      "school source must be generated and loaded inline")
        self.assertIn(JE, world.journal_defs)
        state = world.countries[world.tag]
        self.assertNotIn("ywc_v03_dmg_v03_dmg_common_subjects_settled", state)
        self.assertNotIn(P + "setup_paid", state)
        self.assertEqual(state["states"][0]["region"], "s:STATE_LUZON")
        self.assertEqual(state["states"][0]["owner"], "DMG")
        # Strict represents native full acceptance (>=80) by tier 5.
        self.assertTrue(all(pop["acceptance"] == 5
                            for pop in state["states"][0]["pops"]))
        return world

    def assert_early_closed(self, world, slug):
        state = world.countries[world.tag]
        self.assertEqual(state[f"ywc_v03_dmg_{slug}_settled"], 1)
        arc = early_arc(world, slug)
        self.assertTrue(all(world.history[world.tag][j["id"]] == "complete"
                            for j in arc["journals"]))
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(state["ywc_v03_visible_task_count"], 0)

    def assert_school_closed(self, world, outcome):
        state = world.countries[world.tag]
        self.assertEqual(state[P + "review_streak"], 6)
        self.assertEqual(state[P + "outcome"], outcome)
        self.assertEqual(state["ywc_v03_dmg_v03_dmg_school_languages_outcome"], outcome)
        self.assertEqual(world.history[world.tag][JE], "complete")
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(state["ywc_v03_visible_task_count"], 0)

    def test_real_common_result_halves_setup_but_not_the_independent_later_bill(self):
        world = self.world()
        play_early(world, "v03_dmg_common_subjects", COMMON_ESTABLISHED)
        self.assert_early_closed(world, "v03_dmg_common_subjects")
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_v03_dmg_v03_dmg_common_subjects_outcome"], 1)
        self.assertEqual(state["ywc_dmg_outcome_common_qualification"], 1)
        self.assertEqual(state["ywc_dmg_public_language_mode"], 1)
        self.assertEqual(state["ywc_dmg_translation_duty"], 1)
        school_start = world.treasury[world.tag]
        arc = school_arc(world.cat)
        play(world, arc, 1120, "bilingual_public")
        before = world.treasury[world.tag]
        play(world, arc, 1121, "pay_setup")
        base = state[P + "budget"]
        self.assertEqual(world.treasury[world.tag] - before, -base * 0.5)
        self.assertEqual(state[P + "setup_paid_amount"], base * 0.5)
        self.assertEqual(state[P + "setup_source_common"], 1)
        play(world, arc, 1122, "confirm_supply")
        play(world, arc, 1123, "write_new_appeal")
        month(world, arc, 6)
        before = world.treasury[world.tag]
        finish_review(world, arc)
        self.assertEqual(world.treasury[world.tag] - before, -base)
        self.assertEqual(state[P + "bill_paid_amount"], base)
        self.assertNotIn(P + "bill_source_court", state)
        self.assertEqual(world.treasury[world.tag] - school_start, -base * 1.5)
        self.assert_school_closed(world, 1)

    def test_real_court_result_halves_the_bill_without_paying_school_setup(self):
        world = self.world()
        play_early(world, "v03_dmg_court_provinces", COURT_ESTABLISHED)
        self.assert_early_closed(world, "v03_dmg_court_provinces")
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_dmg_court_outcome"], 1)
        self.assertEqual(state["ywc_dmg_court_provinces_outcome"], 1)
        self.assertEqual(state["ywc_dmg_court_charter_paid"], 1)
        self.assertEqual(state["ywc_dmg_court_budget_paid"], 1)
        school_start = world.treasury[world.tag]
        arc = ready_for_review(world, route="central")
        base = state[P + "budget"]
        self.assertEqual(state[P + "setup_paid_amount"], base)
        self.assertEqual(world.treasury[world.tag] - school_start, -base)
        self.assertNotIn(P + "setup_source_common", state)
        month(world, arc, 6)
        before = world.treasury[world.tag]
        finish_review(world, arc)
        self.assertEqual(world.treasury[world.tag] - before, -base * 0.5)
        self.assertEqual(state[P + "bill_paid_amount"], base * 0.5)
        self.assertEqual(state[P + "bill_source_court"], 1)
        self.assertEqual(world.treasury[world.tag] - school_start, -base * 1.5)
        self.assert_school_closed(world, 1)

    def test_real_paid_mixed_land_result_supplies_the_village_clause(self):
        world = self.world()
        play_early(world, "v03_dmg_two_land_titles", LAND_MIXED)
        self.assert_early_closed(world, "v03_dmg_two_land_titles")
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_dmg_titles_outcome"], 1)
        self.assertEqual(state["ywc_dmg_two_land_titles_outcome"], 1)
        self.assertEqual(state["ywc_dmg_titles_newcomer_mode"], 2)
        self.assertEqual(state["ywc_dmg_titles_compensation_paid"], 1)
        school_start = world.treasury[world.tag]
        arc = school_arc(world.cat)
        for number, key in ((1120, "local_joint"), (1121, "pay_setup"),
                            (1122, "confirm_supply")):
            play(world, arc, number, key)
        event = world.deliver(arc, "ywc_dmg.1123")
        self.assertTrue(option_legal(world, event, "reuse_village_clause"))
        before = world.treasury[world.tag]
        choose(world, arc, event, "reuse_village_clause")
        self.assertEqual(world.treasury[world.tag], before)
        self.assertEqual(state[P + "terms_source_land"], 1)
        self.assertNotIn(P + "terms_new_appeal", state)
        self.assertEqual(state[P + "terms_pilot"], state[P + "pilot"])
        month(world, arc, 6)
        finish_review(world, arc, outcome=2)
        self.assertEqual(world.treasury[world.tag] - school_start, -state[P + "budget"])
        self.assertEqual(state["ywc_dmg_titles_compensation_paid"], 1)
        self.assertEqual(state["ywc_dmg_titles_newcomer_mode"], 2)
        self.assert_school_closed(world, 2)

    def test_real_land_outcome_without_village_terms_uses_a_new_appeal(self):
        world = self.world()
        plan = tuple((number, "individual_appeal" if number == 1014 else key)
                     for number, key in LAND_MIXED)
        play_early(world, "v03_dmg_two_land_titles", plan)
        self.assert_early_closed(world, "v03_dmg_two_land_titles")
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_dmg_two_land_titles_outcome"], 1)
        self.assertEqual(state["ywc_dmg_titles_compensation_paid"], 1)
        self.assertEqual(state["ywc_dmg_titles_newcomer_mode"], 1)
        arc = school_arc(world.cat)
        for number, key in ((1120, "local_joint"), (1121, "pay_setup"),
                            (1122, "confirm_supply")):
            play(world, arc, number, key)
        event = world.deliver(arc, "ywc_dmg.1123")
        self.assertFalse(option_legal(world, event, "reuse_village_clause"))
        self.assertTrue(option_legal(world, event, "write_new_appeal"))
        choose(world, arc, event, "write_new_appeal")
        self.assertEqual(state[P + "terms_new_appeal"], 1)
        self.assertNotIn(P + "terms_source_land", state)
        month(world, arc, 6)
        finish_review(world, arc, outcome=2)
        self.assert_school_closed(world, 2)

    def test_common_discount_needs_current_pilot_staff_after_real_early_success(self):
        world = self.world()
        play_early(world, "v03_dmg_common_subjects", COMMON_ESTABLISHED)
        self.assert_early_closed(world, "v03_dmg_common_subjects")
        state = world.countries[world.tag]
        arc = school_arc(world.cat)
        play(world, arc, 1120, "bilingual_public")
        for pop in state["states"][0]["pops"]:
            if pop["type"] == "bureaucrats":
                pop["employed"] = False
        # No early flag is removed: the price must read present employment.
        self.assertEqual(state["ywc_dmg_outcome_common_qualification"], 1)
        before = world.treasury[world.tag]
        play(world, arc, 1121, "pay_setup")
        self.assertEqual(state[P + "setup_paid_amount"], state[P + "budget"])
        self.assertEqual(world.treasury[world.tag] - before, -state[P + "budget"])
        self.assertNotIn(P + "setup_source_common", state)
        play(world, arc, 1122, "withdraw")
        self.assertEqual(state[P + "outcome"], 4)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)

    def test_court_discount_needs_current_full_offices_even_for_bounded_tuition(self):
        world = self.world()
        play_early(world, "v03_dmg_court_provinces", COURT_ESTABLISHED)
        self.assert_early_closed(world, "v03_dmg_court_provinces")
        become_conservative_without_schools(world)
        state = world.countries[world.tag]
        school_start = world.treasury[world.tag]
        arc = ready_for_review(world, route="central", limited=True)
        month(world, arc, 6)
        finish_review(world, arc, outcome=2)
        self.assertEqual(state["ywc_dmg_court_outcome"], 1)
        self.assertEqual(state["ywc_dmg_court_charter_paid"], 1)
        self.assertEqual(state["ywc_dmg_court_budget_paid"], 1)
        self.assertEqual(state[P + "bill_paid_amount"], state[P + "budget"])
        self.assertNotIn(P + "bill_source_court", state)
        self.assertEqual(world.treasury[world.tag] - school_start, -2 * state[P + "budget"])
        self.assert_school_closed(world, 2)

    def test_real_compromise_setback_and_nonparticipation_reach_conservative_bounded_end(self):
        for previous in ("territorial_compromise", "local_court", "qualification_setback",
                         "not_participated"):
            with self.subTest(previous=previous):
                world = self.world()
                state = world.countries[world.tag]
                if previous == "territorial_compromise":
                    play_early(world, "v03_dmg_common_subjects", COMMON_TERRITORIAL)
                    self.assert_early_closed(world, "v03_dmg_common_subjects")
                    self.assertEqual(state["ywc_v03_dmg_v03_dmg_common_subjects_outcome"], 2)
                elif previous == "local_court":
                    play_early(world, "v03_dmg_court_provinces", COURT_LOCAL)
                    self.assert_early_closed(world, "v03_dmg_court_provinces")
                    self.assertEqual(state["ywc_dmg_court_outcome"], 3)
                elif previous == "qualification_setback":
                    arc = play_early(world, "v03_dmg_common_subjects", COMMON_ESTABLISHED[:-1])
                    event = world.deliver(arc, "ywc_dmg.1009")
                    self.assertTrue(option_legal(world, event, "common_qualification"))
                    # A factual loss after opening, before choosing the close.
                    # Tier4 is native second-rate citizenship, not numeric80.
                    for pop in state["states"][0]["pops"]:
                        pop["acceptance"] = 4
                    self.assertFalse(option_legal(world, event, "common_qualification"))
                    self.assertTrue(option_legal(world, event, "limited_settlement"))
                    choose(world, arc, event, "limited_settlement")
                    self.assert_early_closed(world, "v03_dmg_common_subjects")
                    self.assertEqual(state["ywc_v03_dmg_v03_dmg_common_subjects_outcome"], 5)
                    self.assertEqual(state["ywc_dmg_outcome_limited_qualification"], 1)
                    self.assertNotIn("ywc_dmg_outcome_common_qualification", state)
                else:
                    for slug in ("v03_dmg_common_subjects", "v03_dmg_two_land_titles",
                                 "v03_dmg_court_provinces"):
                        self.assertNotIn(f"ywc_v03_dmg_{slug}_started", state)
                become_conservative_without_schools(world)
                facts_before = copy.deepcopy((state["laws"], state["institutions"],
                                              state["states"], state["literacy_rate"]))
                school_start = world.treasury[world.tag]
                arc = ready_for_review(world, route="bilingual", limited=True)
                month(world, arc, 6)
                finish_review(world, arc, outcome=2)
                self.assertEqual(state[P + "setup_paid_amount"], state[P + "budget"])
                self.assertEqual(state[P + "bill_paid_amount"], state[P + "budget"])
                self.assertNotIn(P + "setup_source_common", state)
                self.assertNotIn(P + "bill_source_court", state)
                self.assertEqual(world.treasury[world.tag] - school_start,
                                 -2 * state[P + "budget"])
                self.assertEqual((state["laws"], state["institutions"], state["states"],
                                  state["literacy_rate"]), facts_before)
                self.assert_school_closed(world, 2)

    def test_foreign_owned_pilot_cannot_spend_on_a_real_prior_common_result(self):
        world = self.world()
        play_early(world, "v03_dmg_common_subjects", COMMON_ESTABLISHED)
        self.assert_early_closed(world, "v03_dmg_common_subjects")
        state = world.countries[world.tag]
        arc = school_arc(world.cat)
        play(world, arc, 1120, "bilingual_public")
        state["states"][0]["owner"] = "PHI"
        event = world.deliver(arc, "ywc_dmg.1121")
        self.assertFalse(option_legal(world, event, "pay_setup"))
        self.assertTrue(option_legal(world, event, "wait_cash"))
        self.assertTrue(option_legal(world, event, "withdraw"))
        before = copy.deepcopy(state)
        treasury = world.treasury[world.tag]
        force_option(world, event, "pay_setup")
        self.assertEqual(state, before)
        self.assertEqual(world.treasury[world.tag], treasury)
        choose(world, arc, event, "withdraw")
        self.assertEqual(state[P + "outcome"], 4)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(state["ywc_v03_visible_task_count"], 0)


if __name__ == "__main__":
    unittest.main()
