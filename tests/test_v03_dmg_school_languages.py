"""DMG school behavior through actual generated source and concrete Luzon facts."""
import copy
import unittest

from shu_kor_strict_review_runtime import Strict, facts
from test_v03_shu_provincial_contract import choose, force_option, option_legal

SLUG = "v03_dmg_school_languages"
JE = "ywc_je_v03_dmg_school_languages"


def school_arc(catalog):
    return next(arc for arc in catalog["arcs"] if arc["slug"] == SLUG)


def new_world(bare=False):
    world = Strict("dmg", load_inline=True)
    state = facts()
    state["literacy_rate"] = 0.35
    state["laws"].append("law_total_separation")
    province = state["states"][0]
    province["region"] = "s:STATE_LUZON"
    province["owner"] = "DMG"
    university = next(b for b in province["buildings"] if b["type"] == "building_university")
    # This existing Strict adapter represents native acceptance_status_5 (>=80)
    # as tier 5, not a raw 0..100 acceptance number.
    academic = copy.deepcopy(province["pops"][0])
    academic.update(type="academics", workplace=university)
    province["pops"].append(academic)
    if bare:
        state["laws"] = ["law_tenant_farmers", "law_no_schools", "law_state_religion"]
        state["institutions"] = {}
        province["pops"] = [province["pops"][0]]
        province["buildings"].remove(university)
        province["pops"][0]["workplace"]["occupancy"] = 0.25
    world.countries[world.tag] = state
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


def ready_for_review(world, route="bilingual", limited=False):
    arc = school_arc(world.cat)
    play(world, arc, 1120, {"bilingual": "bilingual_public", "local": "local_joint",
                          "central": "central_curriculum"}[route])
    play(world, arc, 1121, "pay_setup")
    play(world, arc, 1122, "limit_existing_tuition" if limited else "confirm_supply")
    play(world, arc, 1123, "write_new_appeal")
    return arc


def finish_review(world, arc, outcome=1):
    play(world, arc, 1124, "pay_next_term")
    play(world, arc, 1125, "close_established" if outcome == 1 else "close_compromise")


class DmgSchoolLanguages(unittest.TestCase):
    def test_three_full_routes_pay_both_real_bills_without_granting_world_facts(self):
        for route, charge, outcome in (("bilingual", 2000, 1), ("local", 1000, 2),
                                       ("central", 2000, 1)):
            with self.subTest(route=route):
                world = new_world()
                state = world.countries[world.tag]
                original = copy.deepcopy((state["laws"], state["institutions"], state["states"],
                                          state["literacy_rate"]))
                arc = ready_for_review(world, route)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]),
                                 (1, 1))
                self.assertEqual(state["ywc_dmg_school_review_streak"], 0)
                month(world, arc, 6)
                finish_review(world, arc, outcome)
                self.assertEqual(world.treasury[world.tag], -charge)
                self.assertEqual(state["ywc_dmg_school_outcome"], outcome)
                self.assertEqual(world.history[world.tag][JE], "complete")
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]),
                                 (0, 0))
                self.assertEqual((state["laws"], state["institutions"], state["states"],
                                  state["literacy_rate"]), original)

    def test_no_school_or_new_law_is_needed_for_explicit_bounded_tuition(self):
        for route, charge in (("bilingual", 2000), ("local", 1000), ("central", 2000)):
            with self.subTest(route=route):
                world = new_world(bare=True)
                arc = ready_for_review(world, route, limited=True)
                month(world, arc, 6)
                event = world.deliver(arc, "ywc_dmg.1124")
                self.assertTrue(option_legal(world, event, "pay_next_term"))
                choose(world, arc, event, "pay_next_term")
                final = world.deliver(arc, "ywc_dmg.1125")
                self.assertFalse(option_legal(world, final, "close_established"))
                self.assertTrue(option_legal(world, final, "close_compromise"))
                choose(world, arc, final, "close_compromise")
                state = world.countries[world.tag]
                self.assertEqual(state["ywc_dmg_school_outcome"], 2)
                self.assertEqual(state["institutions"], {})
                self.assertIn("law_no_schools", state["laws"])
                self.assertEqual(world.treasury[world.tag], -charge)

    def test_creation_day_and_duplicate_pulses_do_not_count_as_months(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        world.pulse(arc)
        self.assertEqual(state["ywc_dmg_school_review_streak"], 0)
        for count in range(1, 6):
            month(world, arc)
            self.assertEqual(state["ywc_dmg_school_review_streak"], count)
            world.pulse(arc)
            self.assertEqual(state["ywc_dmg_school_review_streak"], count)
            self.assertNotIn("ywc_dmg_school_review_mature", state)
            self.assertFalse(world.events)
        month(world, arc)
        self.assertEqual(state["ywc_dmg_school_review_streak"], 6)
        self.assertEqual(state["ywc_dmg_school_review_mature"], 1)
        event = world.deliver(arc, "ywc_dmg.1124")
        self.assertTrue(option_legal(world, event, "pay_next_term"))

    def test_war_pilot_loss_default_and_teacher_loss_require_six_fresh_observations(self):
        for reason in ("war", "pilot", "default", "teacher"):
            with self.subTest(reason=reason):
                world = new_world()
                arc = ready_for_review(world)
                state = world.countries[world.tag]
                province = state["states"][0]
                month(world, arc, 4)
                if reason == "war":
                    state["is_at_war"] = True
                elif reason == "pilot":
                    province["owner"] = "PHI"
                elif reason == "default":
                    state["in_default"] = True
                else:
                    province["pops"][1]["employed"] = False
                month(world, arc)
                self.assertEqual(state["ywc_dmg_school_review_streak"], 0)
                self.assertNotIn("ywc_dmg_school_review_running", state)
                event = world.deliver(arc, "ywc_dmg.1124")
                self.assertFalse(option_legal(world, event, "pay_next_term"))
                state["is_at_war"] = state["in_default"] = False
                province["owner"] = "DMG"
                province["pops"][1]["employed"] = True
                month(world, arc)
                self.assertEqual(state["ywc_dmg_school_review_streak"], 0)
                choose(world, arc, event, "defer_recount")
                frozen = copy.deepcopy(state)
                force_option(world, event, "defer_recount")
                force_option(world, event, "wait_bill")
                force_option(world, event, "withdraw")
                self.assertEqual(state, frozen, "an old receipt must not reset a new audit")
                month(world, arc, 5)
                self.assertNotIn("ywc_dmg_school_review_mature", state)
                month(world, arc)
                finish_review(world, arc)
                self.assertEqual(state["ywc_dmg_school_outcome"], 1)

    def test_opening_admission_then_pilot_loss_still_allows_exit(self):
        world = new_world()
        arc = school_arc(world.cat)
        world.refresh(arc)
        state = world.countries[world.tag]
        state["states"][0]["owner"] = "PHI"
        event = world.deliver(arc, "ywc_dmg.1120")
        self.assertFalse(option_legal(world, event, "bilingual_public"))
        self.assertTrue(option_legal(world, event, "wait_pilot"))
        self.assertTrue(option_legal(world, event, "withdraw"))
        choose(world, arc, event, "withdraw")
        self.assertEqual(world.history[world.tag][JE], "failed")
        self.assertEqual(state["ywc_dmg_school_outcome"], 4)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))

    def test_actual_cash_is_rechecked_at_both_payments_and_stale_effects_do_nothing(self):
        for number in (1121, 1124):
            with self.subTest(number=number):
                world = new_world()
                state = world.countries[world.tag]
                arc = school_arc(world.cat)
                if number == 1121:
                    play(world, arc, 1120, "bilingual_public")
                    key = "pay_setup"
                else:
                    arc = ready_for_review(world)
                    month(world, arc, 6)
                    key = "pay_next_term"
                event = world.deliver(arc, f"ywc_dmg.{number}")
                self.assertTrue(option_legal(world, event, key))
                state["gold_reserves"] = -world.treasury[world.tag] + 999
                self.assertFalse(option_legal(world, event, key))
                before = copy.deepcopy((state, world.treasury))
                force_option(world, event, key)
                self.assertEqual((state, world.treasury), before)
                state["gold_reserves"] += 1
                choose(world, arc, event, key)
                before = copy.deepcopy((state, world.treasury))
                for stale in (key, "wait_cash" if number == 1121 else "wait_bill", "withdraw"):
                    force_option(world, event, stale)
                self.assertEqual((state, world.treasury), before)

    def test_supply_requires_actual_same_owned_pilot_employment_acceptance_and_workplace(self):
        for missing in ("foreign_owner", "wrong_state", "unemployed", "acceptance_tier4",
                        "primary_only", "wrong_job", "wrong_workplace", "shortage", "occupancy",
                        "no_institution", "no_public_school", "bureaucracy"):
            with self.subTest(missing=missing):
                world = new_world()
                arc = school_arc(world.cat)
                play(world, arc, 1120, "bilingual_public")
                play(world, arc, 1121, "pay_setup")
                event = world.deliver(arc, "ywc_dmg.1122")
                self.assertTrue(option_legal(world, event, "confirm_supply"))
                state = world.countries[world.tag]
                province = state["states"][0]
                pop = province["pops"][1]
                if missing == "foreign_owner": province["owner"] = "PHI"
                elif missing == "wrong_state": province["region"] = "s:STATE_SICHUAN"
                elif missing == "unemployed": pop["employed"] = False
                elif missing == "acceptance_tier4": pop["acceptance"] = 4
                elif missing == "primary_only": pop["primary"] = True
                elif missing == "wrong_job": pop["type"] = "bureaucrats"
                elif missing == "wrong_workplace": pop["workplace"] = province["buildings"][0]
                elif missing == "shortage": pop["workplace"]["shortage"] = True
                elif missing == "occupancy": pop["workplace"]["occupancy"] = 0.79
                elif missing == "no_institution": state["institutions"] = {}
                elif missing == "no_public_school": state["laws"].remove("law_public_schools")
                elif missing == "bureaucracy": state["bureaucracy"] = -1
                self.assertFalse(option_legal(world, event, "confirm_supply"))
                before = copy.deepcopy(state)
                force_option(world, event, "confirm_supply")
                self.assertEqual(state, before)

    def test_foreign_luzon_cannot_supply_owned_other_region(self):
        world = new_world()
        state = world.countries[world.tag]
        foreign = copy.deepcopy(state["states"][0])
        foreign["owner"] = "PHI"
        state["states"][0].update(region="s:STATE_SICHUAN", pops=[])
        state["states"].append(foreign)
        arc = school_arc(world.cat)
        world.refresh(arc)
        self.assertNotIn(JE, world.active[world.tag])
        self.assertNotIn("ywc_dmg_school_pilot", state)

    def test_local_clergy_supply_reads_current_religious_policy(self):
        world = new_world()
        state = world.countries[world.tag]
        state["laws"] = ["law_religious_schools", "law_state_religion"]
        state["states"][0]["pops"][1]["type"] = "clergymen"
        state["states"][0]["pops"][1]["workplace"]["occupancy"] = 0.5
        arc = school_arc(world.cat)
        play(world, arc, 1120, "local_joint")
        play(world, arc, 1121, "pay_setup")
        event = world.deliver(arc, "ywc_dmg.1122")
        self.assertTrue(option_legal(world, event, "confirm_supply"))
        for incompatible in ("law_total_separation", "law_state_atheism"):
            state["laws"] = ["law_religious_schools", incompatible]
            self.assertFalse(option_legal(world, event, "confirm_supply"))
        state["laws"] = ["law_religious_schools", "law_freedom_of_conscience"]
        choose(world, arc, event, "confirm_supply")
        play(world, arc, 1123, "write_new_appeal")
        month(world, arc, 6)
        finish_review(world, arc, 2)
        self.assertEqual(state["ywc_dmg_school_outcome"], 2)

    def test_only_early_flags_cannot_fake_discount_or_reused_land_terms(self):
        world = new_world()
        state = world.countries[world.tag]
        state.update(ywc_dmg_public_language_mode=1, ywc_dmg_translation_duty=1,
                     ywc_dmg_court_charter_paid=1, ywc_dmg_court_budget_paid=1,
                     ywc_dmg_titles_newcomer_mode=2, ywc_dmg_titles_compensation_paid=1)
        arc = school_arc(world.cat)
        play(world, arc, 1120, "bilingual_public")
        play(world, arc, 1121, "pay_setup")
        self.assertEqual(world.treasury[world.tag], -1000)
        play(world, arc, 1122, "confirm_supply")
        event = world.deliver(arc, "ywc_dmg.1123")
        self.assertFalse(option_legal(world, event, "reuse_village_clause"))
        choose(world, arc, event, "write_new_appeal")
        month(world, arc, 6)
        finish_review(world, arc)
        self.assertEqual(world.treasury[world.tag], -2000)

    def test_current_final_condition_loss_closes_honest_setback_without_refund(self):
        world = new_world()
        arc = ready_for_review(world)
        month(world, arc, 6)
        bill = play(world, arc, 1124, "pay_next_term")
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_dmg_school_stage"], 1125)
        month(world, arc)
        self.assertEqual(state["ywc_dmg_school_stage"], 1125)
        self.assertEqual(state["ywc_dmg_school_review_streak"], 6)
        final = world.deliver(arc, "ywc_dmg.1125")
        self.assertTrue(option_legal(world, final, "close_established"))
        state["states"][0]["owner"] = "PHI"
        self.assertFalse(option_legal(world, final, "close_established"))
        before = copy.deepcopy((state, world.treasury))
        force_option(world, final, "close_established")
        force_option(world, bill, "pay_next_term")
        self.assertEqual((state, world.treasury), before)
        choose(world, arc, final, "close_setback")
        self.assertEqual(state["ywc_dmg_school_outcome"], 3)
        self.assertEqual(world.treasury[world.tag], -2000)
        before = copy.deepcopy((state, world.treasury))
        for key in ("close_setback", "withdraw", "wait_final"):
            force_option(world, final, key)
        world.execute([("ywc_dmg_school_release_once", "=", "yes")], world.tag)
        self.assertEqual((state, world.treasury), before)

    def test_capacity_limits_and_minimum_budget_are_real_admission_constraints(self):
        for counter, maximum in (("ywc_v03_active_arc_count", 3), ("ywc_v03_visible_task_count", 6)):
            with self.subTest(counter=counter):
                world = new_world()
                state = world.countries[world.tag]
                state[counter] = maximum
                world.refresh(school_arc(world.cat))
                self.assertNotIn(JE, world.active[world.tag])
                self.assertNotIn("ywc_v03_dmg_v03_dmg_school_languages_started", state)
                self.assertEqual(state[counter], maximum)
        world = new_world(bare=True)
        state = world.countries[world.tag]
        state["yearly_gross_income"] = 0
        arc = ready_for_review(world, "local", limited=True)
        self.assertEqual(state["ywc_dmg_school_budget"], 100)
        month(world, arc, 6)
        finish_review(world, arc, 2)
        self.assertEqual(world.treasury[world.tag], -100)


if __name__ == "__main__":
    unittest.main()
