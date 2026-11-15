"""NMG school literal facts and genuine old-office producer compatibility."""
import copy
from datetime import date
from pathlib import Path
import unittest

from clausewitz_harness import parse
from kor_partner_protocol_runtime import StateRef, UnsupportedSubset
from lan_public_runtime import LanPublicWorld
from nmg_school_runtime import NmgSchoolWorld
from shu_kor_strict_review_runtime import Strict, facts, field
from test_v03_nmg_partner_response import NmgPartnerWorld


ROOT = Path(__file__).resolve().parents[1]


def literal_countries():
    """Only ordinary current engine facts; no initialized/paid/story flags."""
    state = {key: copy.deepcopy(value) for key, value in facts().items()
             if not key.startswith("ywc_")}
    state.update(literacy_rate=.40, is_subject=True, overlord="MEX",
                 relations={"MEX": 50}, market="m_nmg")
    state["laws"].extend(("law_freedom_of_conscience", "law_monarchy"))
    state["igs"] = [
        {"type": kind, "in_government": True, "clout": .15, "approval": 1}
        for kind in ("ig_intelligentsia", "ig_devout", "ig_rural_folk")
    ]
    province = state["states"][0]
    province.update(owner="NMG", region="s:STATE_BAJA_CALIFORNIA")
    province["pops"][0]["workplace"] = next(building for building in province["buildings"]
        if building["type"] == "building_government_administration")
    academic = copy.deepcopy(province["pops"][0])
    academic.update(type="academics", workplace=next(building for building in province["buildings"]
        if building["type"] == "building_university"))
    province["pops"].append(academic)
    foreign = copy.deepcopy(state)
    foreign.update(is_subject=False, overlord=None, relations={"NMG": 50}, market="m_mex")
    foreign["states"][0].update(owner="MEX", region="s:STATE_CALIFORNIA")
    foreign["institutions"]["institution_schools"] = 4
    return {"NMG": state, "MEX": foreign}


def new_world(*, start_date=date(1836, 1, 1)):
    return NmgSchoolWorld(literal_countries(), start_date=start_date)


def capture_literal_pilot(world):
    world.run_script("""
        every_scope_state = {
            limit = { owner = ROOT state_region = s:STATE_BAJA_CALIFORNIA }
            save_scope_as = literal_nmg_school_state
        }
        set_variable = { name = literal_nmg_school_pilot value = scope:literal_nmg_school_state }
    """, "NMG")
    return world.countries["NMG"]["literal_nmg_school_pilot"]


IG_QUERY = """any_interest_group = {
    is_interest_group_type = ig_intelligentsia
    is_in_government = yes ig_clout >= .10 ig_approval >= 0
}"""
POST_QUERY = """any_scope_state = { owner = ROOT
    any_scope_pop = {
        is_pop_type = academics is_employed = yes pop_has_primary_culture = no
        pop_acceptance >= acceptance_status_5
        workplace ?= { is_building_type = building_university
                       occupancy >= .5 building_has_goods_shortage = no }
    }
}"""
EDUCATION_QUERY = """institution_investment_level = {
    institution = institution_schools value >= 1
}"""

OLD_JE = "ywc_je_flavor_nmg_bargain_1"
OFFICE = "v03_nmg_bilingual_office"
OLD_PREFIX = "ywc_v03_nmg_v03_nmg_bilingual_office_"
LEGACY_EVENTS = ("ywc_nmg.6", "ywc_nmg.100", "ywc_nmg.101", "ywc_nmg.102", "ywc_nmg.103", "ywc_nmg.104")


def load_native_legacy_sources(world):
    """Load real old declarations; no replacement business ASTs or predicates."""
    for filename in ("ywc_campaign_effects.txt", "ywc_flavor_effects.txt", "ywc_shared_effects.txt"):
        path = ROOT / "yongchang_world/common/scripted_effects" / filename
        for name, _, nodes in parse(path.read_text(encoding="utf-8-sig")):
            if name in world.effects and world.effects[name] != nodes:
                raise AssertionError(("legacy_effect_conflict", path, name))
            world.effects[name] = nodes
    for filename in ("ywc_kor_lan_nmg_events.txt", "ywc_large_campaign_events.txt"):
        path = ROOT / "yongchang_world/events" / filename
        for name, _, nodes in parse(path.read_text(encoding="utf-8-sig")):
            if name == "namespace":
                continue
            if name in world.event_defs and world.event_defs[name] != nodes:
                raise AssertionError(("legacy_event_conflict", path, name))
            world.event_defs[name] = nodes
    journals = parse((ROOT / "yongchang_world/common/journal_entries/ywc_nmg.txt").read_text(encoding="utf-8-sig"))
    # The bounded old-producer proof pulses this original admission chapter;
    # unrelated legacy chapters remain outside this test's admitted scope.
    world.journal_defs[OLD_JE] = next(nodes for name, _, nodes in journals if name == OLD_JE)


def native_deliver(world, arc, wanted, handled, max_months=48):
    """Run source on_actions/JE pulses and real Gregorian months, then display."""
    world.refresh(arc)
    for _ in range(max_months):
        # Each callback belongs to a newly reached actual calendar month.
        # Calling this helper for the next popup cannot pulse the prior month
        # again and advance the legacy .6/.100 sequence twice on one day.
        world.advance_months(1)
        world.run_country_monthly("NMG")
        world.pulse(arc)
        for job in world.jobs:
            if job.serial in handled or not world.display_job(job):
                continue
            if field(world.event_defs[job.event_id], "hidden") == "yes":
                raise AssertionError(("unexpected_hidden_old_office_job", job.event_id))
            if job.event_id != wanted:
                raise AssertionError(("unexpected_native_office_delivery", wanted, job.event_id))
            handled.add(job.serial)
            return job
    raise AssertionError(("no_native_old_office_event", wanted, world.date))


def native_choose(world, arc, job, choice):
    legal = world.job_options(job)
    if not legal.get(choice):
        raise AssertionError(("illegal_native_old_office_choice", job.event_id, choice, legal))
    before = world.treasury["NMG"]
    world.choose_job(job, choice)
    world.refresh(arc)
    world.__dict__.setdefault("native_producer_cash_trace", []).append(
        (job.event_id, choice, world.date, world.treasury["NMG"] - before))


def earn_old_office(world, outcome=3):
    """Same-world original country history, six legacy choices and office JE."""
    state = world.countries["NMG"]
    if any(name.startswith((OLD_PREFIX, "ywc_nmg_office_", "ywc_campaign_nmg_c1")) for name in state):
        raise AssertionError("old office history must start genuinely absent")
    load_native_legacy_sources(world)
    history = parse((ROOT / "yongchang_world/common/history/countries/ywc_content_starts.txt").read_text(encoding="utf-8-sig"))
    countries = field(history, "COUNTRIES")
    source_scope = next(node for node in countries if node[0] == "c:NMG")
    world.execute([source_scope], "NMG")
    legacy_arc = {"journals": [{"id": OLD_JE}]}
    handled = set()
    provenance = []
    for expected in LEGACY_EVENTS:
        job = native_deliver(world, legacy_arc, expected, handled)
        native_choose(world, legacy_arc, job, "b")
        provenance.append((job.event_id, "b", world.date))
    if world.history["NMG"][OLD_JE] != "complete":
        raise AssertionError(("original_legacy_did_not_complete", world.history["NMG"]))
    world.run("ywc_v03_initialize_country", "NMG")
    arc = next(row for row in world.cat["arcs"] if row["slug"] == OFFICE)
    before = world.treasury["NMG"]
    plan = ((1010, "local" if outcome == 2 else "bilingual"),
            (1011, "hire_thin" if outcome == 2 else "hire_full"),
            (1012, "court_parish"), (1013, "fund_schools"), (1014, "keep_route"))
    for number, choice in plan:
        job = native_deliver(world, arc, f"ywc_nmg.{number}", handled)
        native_choose(world, arc, job, choice)
        provenance.append((job.event_id, choice, world.date))
    terminal = {3: "close_full", 2: "close_partial", 1: "withdraw"}[outcome]
    for _ in range(6):
        job = native_deliver(world, arc, "ywc_nmg.1015", handled)
        if outcome == 1 or state.get("ywc_nmg_office_six_months_complete") == 1:
            native_choose(world, arc, job, terminal)
            provenance.append((job.event_id, terminal, world.date))
            break
        native_choose(world, arc, job, "wait_retry")
        provenance.append((job.event_id, "wait_retry", world.date))
    else:
        raise AssertionError("original old office never earned real six-month proof")
    return arc, provenance, world.treasury["NMG"] - before


class NmgSchoolLiteralFacts(unittest.TestCase):
    def test_native_mro_keeps_both_literal_group_and_typed_country_state_layers(self):
        world = new_world()
        self.assertIsInstance(world, LanPublicWorld)
        self.assertIsInstance(world, NmgPartnerWorld)
        chain = type(world).__mro__
        self.assertLess(chain.index(LanPublicWorld), chain.index(NmgPartnerWorld))
        self.assertLess(chain.index(NmgPartnerWorld), chain.index(Strict))
        self.assertEqual(world.tag, "NMG")
        self.assertTrue(world.check_script("is_subject_of = c:MEX", "NMG"))
        self.assertTrue(world.check_script(IG_QUERY, "NMG"))
        self.assertTrue(world.check_script(POST_QUERY, "NMG"))
        self.assertFalse(any(key.startswith("ywc_") for key in world.countries["NMG"]))

    def test_saved_state_identity_reads_live_owner_and_cannot_borrow_a_foreign_school(self):
        world = new_world()
        reference = capture_literal_pilot(world)
        self.assertIsInstance(reference, StateRef)
        query = """exists = var:literal_nmg_school_pilot
            var:literal_nmg_school_pilot = { owner = ROOT
                any_scope_pop = { is_pop_type = academics is_employed = yes
                    workplace ?= { is_building_type = building_university occupancy >= .5 }
                }
            }"""
        self.assertTrue(world.check_script(query, "NMG"))
        selected = world.countries["NMG"]["states"][0]
        selected["owner"] = "MEX"
        self.assertFalse(world.check_script(query, "NMG"))
        self.assertEqual(world.countries["NMG"]["literal_nmg_school_pilot"], reference)
        self.assertTrue(world.check_script(POST_QUERY, "MEX"))
        self.assertFalse(world.check_script(POST_QUERY, "NMG"))
        selected["owner"] = "NMG"
        self.assertTrue(world.check_script(query, "NMG"))

    def test_saved_state_vanishes_without_reselection_or_numeric_business_defaults(self):
        world = new_world()
        reference = capture_literal_pilot(world)
        world.countries["NMG"]["states"].clear()
        self.assertFalse(world.check_script("exists = var:literal_nmg_school_pilot", "NMG"))
        self.assertFalse(world.check_script(
            "exists = var:literal_nmg_school_pilot var:literal_nmg_school_pilot = { owner = ROOT }", "NMG"))
        self.assertEqual(world.countries["NMG"]["literal_nmg_school_pilot"], reference)
        with self.assertRaises(UnsupportedSubset):
            world.run_script("set_variable = { name = literal_copy value = var:ywc_nmg_school_paid }", "NMG")
        with self.assertRaises(UnsupportedSubset):
            world.run_script("change_variable = { name = ywc_nmg_school_streak add = 1 }", "NMG")
        with self.assertRaises(UnsupportedSubset):
            world.check_script("var:ywc_nmg_school_paid_amount > 0", "NMG")
        self.assertFalse(world.check_script("var:ywc_nmg_school_streak = 0", "NMG"))
        self.assertNotIn("ywc_nmg_school_paid", world.countries["NMG"])
        self.assertNotIn("ywc_nmg_school_streak", world.countries["NMG"])

    def test_group_type_government_clout_and_approval_must_match_one_group(self):
        world = new_world()
        state = world.countries["NMG"]
        candidate = state["igs"][0]
        candidate.update(in_government=False, clout=.2, approval=1)
        split = copy.deepcopy(candidate)
        split.update(in_government=True, clout=.09, approval=1)
        state["igs"].append(split)
        self.assertFalse(world.check_script(IG_QUERY, "NMG"))
        split.update(clout=.10, approval=-1)
        self.assertFalse(world.check_script(IG_QUERY, "NMG"))
        split["approval"] = 0
        self.assertTrue(world.check_script(IG_QUERY, "NMG"))
        self.assertIsNone(world.scope_ig)

    def test_employment_acceptance_and_workplace_belong_to_the_same_real_pop(self):
        world = new_world()
        state = world.countries["NMG"]["states"][0]
        academic = next(pop for pop in state["pops"] if pop["type"] == "academics")
        self.assertTrue(world.check_script(POST_QUERY, "NMG"))
        for field_name, bad_value in (("employed", False), ("acceptance", 4), ("type", "bureaucrats")):
            before = academic[field_name]
            academic[field_name] = bad_value
            self.assertFalse(world.check_script(POST_QUERY, "NMG"))
            academic[field_name] = before
        academic["workplace"]["occupancy"] = .49
        self.assertFalse(world.check_script(POST_QUERY, "NMG"))
        academic["workplace"]["occupancy"] = .5
        self.assertTrue(world.check_script(POST_QUERY, "NMG"))
        academic["workplace"]["shortage"] = True
        self.assertFalse(world.check_script(POST_QUERY, "NMG"))
        self.assertIsNone(world.state_scope)
        self.assertIsNone(world.pop_scope)
        self.assertIsNone(world.building_scope)
        academic["workplace"]["shortage"] = False
        for bad in ("no", 0, 1):
            academic["employed"] = bad
            with self.subTest(employed=bad), self.assertRaises(AssertionError):
                world.check_script(POST_QUERY, "NMG")
        academic["employed"] = True
        for bad in (True, "1", float("nan"), -1):
            academic["workplace"]["occupancy"] = bad
            with self.subTest(occupancy=bad), self.assertRaises(AssertionError):
                world.check_script(POST_QUERY, "NMG")

    def test_school_institution_is_current_country_fact_and_cannot_borrow_foreign_investment(self):
        world = new_world()
        self.assertTrue(world.check_script(EDUCATION_QUERY, "NMG"))
        world.countries["NMG"]["institutions"]["institution_schools"] = 0
        self.assertFalse(world.check_script(EDUCATION_QUERY, "NMG"))
        self.assertTrue(world.check_script(EDUCATION_QUERY, "MEX"))
        for bad in (True, "2", float("nan"), float("inf"), -1):
            world.countries["NMG"]["institutions"]["institution_schools"] = bad
            with self.subTest(bad=bad), self.assertRaises(AssertionError):
                world.check_script(EDUCATION_QUERY, "NMG")

    def test_unknown_or_malformed_literal_queries_fail_without_business_fallbacks(self):
        world = new_world()
        before = copy.deepcopy(world.countries)
        bad_queries = (
            "ywc_nmg_school_runtime_unknown_predicate = yes",
            "any_interest_group = { is_interest_group_type = ig_devout is_in_government = maybe }",
            "institution_investment_level = { institution = institution_schools value >= 1 fake = yes }",
            "institution_investment_level = { institution = institution_schools value >= 1 value >= 2 }",
        )
        for query in bad_queries:
            with self.subTest(query=query), self.assertRaises(AssertionError):
                world.check_script(query, "NMG")
        self.assertEqual(world.countries, before)

    def test_gregorian_calendar_has_one_elapsed_month_owner(self):
        world = new_world(start_date=date(1836, 1, 31))
        world.advance_months(1)
        self.assertEqual((world.date, world.elapsed_months), (date(1836, 2, 29), 1))
        world.advance_months(1)
        self.assertEqual((world.date, world.elapsed_months), (date(1836, 3, 29), 2))
        self.assertEqual(world.day, 58)

    def test_original_history_and_old_office_native_produce_actual_3_2_1_outcomes_in_same_world(self):
        for outcome, fee in ((3, 2000), (2, 1000), (1, 2000)):
            with self.subTest(outcome=outcome):
                world = new_world()
                reference = capture_literal_pilot(world)
                arc, provenance, paid = earn_old_office(world, outcome)
                state = world.countries["NMG"]
                self.assertEqual(state[OLD_PREFIX + "outcome"], outcome)
                self.assertEqual(state[OLD_PREFIX + "settled"], 1)
                self.assertEqual(state["ywc_campaign_nmg_c1_outcome"], 2)
                self.assertEqual(state["ywc_je_flavor_nmg_bargain_1_resolved"], 1)
                self.assertEqual([event for event, _, _ in provenance[:6]], list(LEGACY_EVENTS))
                legacy_dates = [day for _, _, day in provenance[:6]]
                self.assertTrue(all(later > earlier for earlier, later in zip(legacy_dates, legacy_dates[1:])))
                self.assertEqual(legacy_dates, [date(1836, 2, 1), date(1836, 3, 1),
                    date(1836, 7, 1), date(1836, 11, 1), date(1837, 3, 1), date(1837, 7, 1)])
                self.assertEqual(paid, -fee)
                office_cash = [(event, change) for event, _, _, change in world.native_producer_cash_trace
                               if int(event.split(".")[1]) >= 1000 and change]
                self.assertEqual(office_cash, [("ywc_nmg.1010", -1000)] +
                                 ([] if outcome == 2 else [("ywc_nmg.1011", -1000)]))
                self.assertEqual(next(change for event, choice, _, change in world.native_producer_cash_trace
                                      if event == "ywc_nmg.1013" and choice == "fund_schools"), 0)
                self.assertEqual(world.history["NMG"][arc["journals"][0]["id"]],
                                 "failed" if outcome == 1 else "complete")
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
                self.assertEqual(state["literal_nmg_school_pilot"], reference)
                self.assertTrue(world.check_script(IG_QUERY, "NMG"))
                self.assertTrue(world.check_script(POST_QUERY, "NMG"))
                self.assertTrue(world.check_script(EDUCATION_QUERY, "NMG"))
                if outcome != 1:
                    self.assertEqual(state["ywc_nmg_office_six_months_complete"], 1)
                    major_dates = [day for event, _, day in provenance if int(event.split(".")[1]) >= 1000]
                    self.assertTrue(all((later - earlier).days >= 90 for earlier, later in zip(major_dates, major_dates[1:])))

    def test_earned_old_contract_does_not_override_current_school_group_or_pilot_facts(self):
        world = new_world()
        reference = capture_literal_pilot(world)
        earn_old_office(world)
        state = world.countries["NMG"]
        state["institutions"]["institution_schools"] = 0
        self.assertFalse(world.check_script(EDUCATION_QUERY, "NMG"))
        state["igs"][0]["in_government"] = False
        self.assertFalse(world.check_script(IG_QUERY, "NMG"))
        state["states"][0]["owner"] = "MEX"
        self.assertFalse(world.check_script(
            "exists = var:literal_nmg_school_pilot var:literal_nmg_school_pilot = { owner = ROOT }", "NMG"))
        self.assertEqual(state["literal_nmg_school_pilot"], reference)
        self.assertEqual(state[OLD_PREFIX + "outcome"], 3)
        self.assertEqual(state["ywc_nmg_office_fee_paid"], 1)


if __name__ == "__main__":
    unittest.main()
