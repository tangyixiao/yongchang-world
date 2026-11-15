"""Actual-source KOR workshop contracts. No ready, paid or outcome flags injected.

Mode 1 is bounded public coordination, not a loan or a claim of borrower cash
receipt. The catalog's repayable firm-credit requirement remains unimplemented.
"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kor_partner_protocol_runtime import StateRef
from test_v03_kor_workshops_literal import world
from kor_partner_protocol_runtime import EventJob
from test_v03_kor_court_public import choose as _old_choose, force_option as _old_force, option_legal as _old_legal
from test_v03_kor_revenue_cross_era import earn_military, earn_school


SLUG = "v03_kor_workshops_credit"
P = "ywc_kor_workshops_"
L = "ywc_v03_kor_v03_kor_workshops_credit_"
MODIFIERS = {"office_service": "ywc_kor_workshops_office_service",
             "infrastructure": "ywc_kor_workshops_infrastructure",
             "home_workshops": "ywc_kor_workshops_home_workshops"}


def new_world():
    w = world()
    w.countries["KOR"]["literacy_rate"] = .5
    w.run("ywc_v03_initialize_country", "KOR")
    return w


def arc_for(w):
    arc = next((a for a in w.cat["arcs"] if a.get("slug") == SLUG), None)
    assert arc is not None, "actual KOR workshops card absent"
    return arc


def event(w, arc, number):
    for _ in range(150):
        w.pulse(arc)
        for job in w.jobs:
            if job.event_id == f"ywc_kor.{number}" and job not in w._displayed and w.display_job(job):
                return job
        w.advance_days(30)
    raise AssertionError(("actual_workshop_event_not_delivered", number, w.date))


def option_legal(w, e, key):
    return w.job_options(e).get(key, False) if isinstance(e, EventJob) else _old_legal(w, e, key)


def force_option(w, e, key):
    return w.choose_job(e, key) if isinstance(e, EventJob) else _old_force(w, e, key)


def choose(w, arc, e, key):
    if not isinstance(e, EventJob):
        return _old_choose(w, arc, e, key)
    assert option_legal(w, e, key), ("illegal_actual_workshop_choice", e.event_id, key)
    w.choose_job(e, key)
    w.refresh(arc)


def play(w, arc, number, key):
    e = event(w, arc, number)
    choose(w, arc, e, key)
    return e


def month(w, arc, count=1):
    for _ in range(count):
        w.advance_months(1)
        w.run_country_monthly("KOR")
        w.pulse(arc)


class KorWorkshopsBusiness(unittest.TestCase):
    def test_three_programs_debit_real_cost_and_add_distinct_real_state_effect(self):
        for choice, amount in (("office_service", 1000), ("infrastructure", 2000),
                               ("home_workshops", 500)):
            with self.subTest(choice=choice):
                w = new_world(); arc = arc_for(w)
                play(w, arc, 1110, choice)
                state = w.countries["KOR"]
                pilot = state[P + "pilot"]
                self.assertIsInstance(pilot, StateRef)
                before = w.treasury["KOR"]
                play(w, arc, 1111, "pay_program")
                self.assertEqual(before - w.treasury["KOR"], amount)
                self.assertEqual(state[P + "program_paid"], 1)
                self.assertEqual(state[P + "program_paid_amount"], amount)
                self.assertIn((pilot, MODIFIERS[choice]), w.state_modifiers)
                self.assertEqual(sum((pilot, name) in w.state_modifiers for name in MODIFIERS.values()), 1)
                self.assertFalse(any("principal_repaid" in name for name in state if name.startswith(P)))

    def test_no_deduction_or_effect_after_current_factory_loses_required_input(self):
        w = new_world(); arc = arc_for(w)
        play(w, arc, 1110, "office_service")
        e = event(w, arc, 1111)
        self.assertTrue(option_legal(w, e, "pay_program"))
        province = w.countries["KOR"]["states"][0]
        factory = next(b for b in province["buildings"] if b["type"] == "building_textile_mill")
        factory["shortage"] = True
        before = copy.deepcopy((w.countries, w.treasury, w.state_modifiers))
        force_option(w, e, "pay_program")
        self.assertEqual((w.countries, w.treasury, w.state_modifiers), before)

    def test_no_deduction_after_original_state_changes_owner(self):
        w = new_world(); arc = arc_for(w)
        play(w, arc, 1110, "office_service")
        e = event(w, arc, 1111)
        self.assertTrue(option_legal(w, e, "pay_program"))
        w.countries["KOR"]["states"][0]["owner"] = "CHI"
        before = copy.deepcopy((w.countries, w.treasury, w.state_modifiers))
        force_option(w, e, "pay_program")
        self.assertEqual((w.countries, w.treasury, w.state_modifiers), before)

    def test_old_school_and_military_are_genuine_sources_at_separate_nodes(self):
        w = new_world(); w.modifiers.append(("KOR", {"modifier": "military_wages_medium"}))
        earn_military(w, "provincial")
        earn_school(w, "cooperative")
        state = w.countries["KOR"]
        self.assertEqual(state["ywc_v03_kor_v03_kor_military_accounts_outcome"], 2)
        self.assertEqual(state["ywc_v03_kor_v03_kor_school_factions_outcome"], 1)
        arc = arc_for(w)
        play(w, arc, 1110, "office_service")
        play(w, arc, 1111, "pay_program")
        e = event(w, arc, 1112)
        self.assertTrue(option_legal(w, e, "reuse_school_mentor"))
        choose(w, arc, e, "reuse_school_mentor")
        play(w, arc, 1113, "sign_duties")
        play(w, arc, 1114, "accept_duties")
        month(w, arc, 6)
        e = event(w, arc, 1115)
        self.assertTrue(option_legal(w, e, "reuse_military_review"))
        before = w.treasury["KOR"]
        choose(w, arc, e, "reuse_military_review")
        self.assertEqual(before - w.treasury["KOR"], 500)
        self.assertEqual(state[P + "review_paid_amount"], 500)

    def test_state_transfer_removes_the_effect_even_after_story_closes(self):
        w = new_world(); arc = arc_for(w)
        play(w, arc, 1110, "infrastructure")
        play(w, arc, 1111, "pay_program")
        state = w.countries["KOR"]; pilot = state[P + "pilot"]
        self.assertIn((pilot, MODIFIERS["infrastructure"]), w.state_modifiers)
        province = state["states"][0]
        province["owner"] = "CHI"
        w.run_state_owner_change(pilot)
        self.assertNotIn((pilot, MODIFIERS["infrastructure"]), w.state_modifiers)


if __name__ == "__main__":
    unittest.main()
