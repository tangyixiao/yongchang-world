"""Drive bay loan through authored events and monthly hooks, without seeded business state."""
import copy
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nmg_bay_runtime import NmgBayWorld
from kor_partner_protocol_runtime import StateRef
from test_v03_nmg_parish_school import deliver, play, set_cash
from test_v03_nmg_school_runtime import literal_countries

BENEFITS = {1: "ywc_nmg_bay_public_port", 2: "ywc_nmg_bay_supervised_port", 3: "ywc_nmg_bay_reduced_port"}


def countries():
    world = literal_countries()
    nmg = world["NMG"]
    state = nmg["states"][0]
    state["market_access"] = .9
    office = next(b for b in state["buildings"] if b["type"] == "building_government_administration")
    office["occupancy"] = .8
    # Keep exactly one real port object so fixture mutations affect the same
    # workplace that the employed dockworker actually occupies.
    state["buildings"] = [building for building in state["buildings"] if building["type"] != "building_port"]
    port = copy.deepcopy(office)
    port.update(type="building_port", occupancy=.8, shortage=False)
    state["buildings"].append(port)
    dockworker = copy.deepcopy(state["pops"][0])
    dockworker.update(type="laborers", employed=True, workplace=port)
    state["pops"].append(dockworker)
    return world


def three_partner_countries():
    fixture = countries()
    for tag in ("USA", "JHG"):
        fixture[tag] = copy.deepcopy(fixture["MEX"])
        fixture[tag]["states"][0]["owner"] = tag
        fixture[tag]["market"] = "m_" + tag.lower()
        fixture[tag]["relations"] = {"NMG": 50}
        fixture["NMG"]["relations"][tag] = 50
    return fixture


def world_and_arc(fixture=None):
    world = NmgBayWorld(countries() if fixture is None else fixture)
    world.assert_bay_hook_loaded_once()
    world.run("ywc_v03_initialize_country", "NMG")
    world._school_handled_jobs = {job.serial for job in world.jobs}
    world._school_country_month = None
    arc = next((a for a in world.cat["arcs"] if a.get("slug") == "v03_nmg_bay_ports"), None)
    assert arc is not None, "authored bay arc missing"
    return world, arc


def ask_mexico(world, arc):
    play(world, arc, 1100, "limited_operation")
    play(world, arc, 1101, "request_mexico")
    event = deliver(world, arc, 1108)
    job = world._school_event_jobs[id(event)]
    assert job.recipient == world.country_ref("MEX")
    return job


def real_month(world, arc):
    world.advance_months(1)
    world.run_country_monthly("NMG")
    world._school_country_month = world.date
    world.pulse(arc)


def assert_no_early_advance(test, world):
    for job in world.jobs:
        if job.event_id == "ywc_nmg.1105" and world.display_job(job):
            test.assertFalse(world.job_options(job).get("advance_review", False),
                             "unmatured observation was offered as complete")


def finish_public(world, arc):
    for number, key in ((1100, "public_port"), (1101, "local_terms"),
                        (1102, "pay_charter"), (1103, "sign_duties"),
                        (1104, "pay_maintenance")):
        play(world, arc, number, key)
    for _ in range(12):
        real_month(world, arc)
    play(world, arc, 1105, "advance_review")
    play(world, arc, 1106, "request_full")
    return play(world, arc, 1107, "close_full")


class NmgBayActualProtocol(unittest.TestCase):
    def test_damaged_history_blocks_advance_or_request_but_keeps_withdrawal(self):
        for stage, choice in ((1105, "advance_review"), (1106, "request_full")):
            for proof in ("signed", "accepted", "review_mature"):
                for damaged in ("zero", "missing"):
                    with self.subTest(stage=stage, proof=proof, damaged=damaged):
                        world, arc = world_and_arc()
                        for number, key in ((1100, "public_port"), (1101, "local_terms"),
                                            (1102, "pay_charter"), (1103, "sign_duties"),
                                            (1104, "pay_maintenance")):
                            play(world, arc, number, key)
                        for _ in range(12):
                            real_month(world, arc)
                        if stage == 1106:
                            play(world, arc, 1105, "advance_review")
                        event = deliver(world, arc, stage)
                        job = world._school_event_jobs[id(event)]
                        self.assertTrue(world.job_options(job)[choice])
                        state = world.countries["NMG"]
                        name = "ywc_nmg_bay_" + proof
                        self.assertEqual(state[name], 1)
                        if damaged == "zero":
                            state[name] = 0
                        else:
                            del state[name]
                        before = copy.deepcopy((world.countries, world.treasury, world.jobs))
                        self.assertFalse(world.job_options(job)[choice])
                        world.choose_job(job, choice)
                        self.assertEqual((world.countries, world.treasury, world.jobs), before)
                        self.assertTrue(world.job_options(job)["withdraw"])
                        world.choose_job(job, "withdraw")
                        self.assertEqual(state["ywc_nmg_bay_outcome"], 4)

    def test_earned_history_requires_positive_proofs_for_each_settlement(self):
        for route, mode, months, request, close in (
            ("full", "public_port", 12, "request_full", "close_full"),
            ("limited", "limited_preparation", 6, "request_limited", "close_limited"),
            ("setback", "public_port", 12, "request_setback", "close_setback"),
        ):
            for proof in ("signed", "accepted", "review_mature"):
                for damaged in ("zero", "missing"):
                    with self.subTest(route=route, proof=proof, damaged=damaged):
                        world, arc = world_and_arc()
                        for number, key in ((1100, mode), (1101, "local_terms"),
                                            (1102, "pay_charter"), (1103, "sign_duties"),
                                            (1104, "pay_maintenance")):
                            play(world, arc, number, key)
                        for _ in range(months):
                            real_month(world, arc)
                        play(world, arc, 1105, "advance_review")
                        if route == "setback":
                            port = next(b for b in world.countries["NMG"]["states"][0]["buildings"]
                                        if b["type"] == "building_port")
                            port["shortage"] = True
                        play(world, arc, 1106, request)
                        event = deliver(world, arc, 1107)
                        job = world._school_event_jobs[id(event)]
                        self.assertTrue(world.job_options(job)[close])
                        state = world.countries["NMG"]
                        name = "ywc_nmg_bay_" + proof
                        self.assertEqual(state[name], 1)
                        if damaged == "zero":
                            state[name] = 0
                        else:
                            del state[name]
                        before = copy.deepcopy((world.countries, world.treasury, world.jobs, world.state_modifiers))
                        self.assertFalse(world.job_options(job)[close])
                        world.choose_job(job, close)
                        self.assertEqual((world.countries, world.treasury, world.jobs, world.state_modifiers), before)

    def test_maintenance_charge_rejects_missing_or_zero_actual_signature(self):
        for damaged in ("zero", "missing"):
            with self.subTest(damaged=damaged):
                world, arc = world_and_arc()
                for number, key in ((1100, "public_port"), (1101, "local_terms"),
                                    (1102, "pay_charter"), (1103, "sign_duties")):
                    play(world, arc, number, key)
                event = deliver(world, arc, 1104)
                job = world._school_event_jobs[id(event)]
                self.assertTrue(world.job_options(job)["pay_maintenance"])
                state = world.countries["NMG"]
                self.assertEqual(state["ywc_nmg_bay_signed"], 1)
                if damaged == "zero":
                    state["ywc_nmg_bay_signed"] = 0
                else:
                    del state["ywc_nmg_bay_signed"]
                before = copy.deepcopy((world.countries, world.treasury, world.jobs))
                self.assertFalse(world.job_options(job)["pay_maintenance"])
                world.choose_job(job, "pay_maintenance")
                self.assertEqual((world.countries, world.treasury, world.jobs), before)

    def test_refused_foreign_popup_cannot_accept_the_next_real_offer(self):
        world, arc = world_and_arc()
        old = ask_mexico(world, arc)
        world.choose_job(old, "refuse")
        play(world, arc, 1101, "request_mexico")
        event = deliver(world, arc, 1108)
        current = world._school_event_jobs[id(event)]
        self.assertNotEqual(old.serial, current.serial)
        self.assertTrue(world.job_options(current)["accept_advance"])
        before = copy.deepcopy((world.countries, world.treasury, world.jobs))
        world.choose_job(old, "accept_advance")
        self.assertEqual((world.countries, world.treasury, world.jobs), before)
        world.choose_job(current, "accept_advance")
        self.assertIn("ywc_nmg_bay_debt_generation", world.countries["NMG"])
        self.assertGreater(world.treasury["NMG"], 0)
        self.assertAlmostEqual(sum(world.treasury.values()), 0)

    def test_wait_invalidates_each_real_popup_before_and_after_redispatch(self):
        steps = ((1100, "public_port"), (1101, "local_terms"),
                 (1102, "pay_charter"), (1103, "sign_duties"),
                 (1104, "pay_maintenance"), (1105, "advance_review"),
                 (1106, "request_full"), (1107, "close_full"))
        for index, (stage, choice) in enumerate(steps):
            with self.subTest(stage=stage):
                world, arc = world_and_arc()
                for previous, key in steps[:index]:
                    if previous == 1105:
                        for _ in range(12):
                            real_month(world, arc)
                    play(world, arc, previous, key)
                if stage == 1105:
                    for _ in range(12):
                        real_month(world, arc)
                event = deliver(world, arc, stage)
                old = world._school_event_jobs[id(event)]
                self.assertTrue(world.job_options(old)[choice])
                world.choose_job(old, "wait")
                before = copy.deepcopy((world.countries, world.treasury, world.jobs, world.state_modifiers))
                world.choose_job(old, choice)
                self.assertEqual((world.countries, world.treasury, world.jobs, world.state_modifiers), before)
                world.refresh(arc)
                event = deliver(world, arc, stage)
                current = world._school_event_jobs[id(event)]
                self.assertNotEqual(old.serial, current.serial)
                self.assertNotEqual(dict(world._displayed[old])["ywc_nmg_bay_popup_epoch"],
                                    dict(world._displayed[current])["ywc_nmg_bay_popup_epoch"])
                self.assertTrue(world.job_options(current)[choice])
                before = copy.deepcopy((world.countries, world.treasury, world.jobs, world.state_modifiers))
                world.choose_job(old, choice)
                self.assertEqual((world.countries, world.treasury, world.jobs, world.state_modifiers), before)
                world.choose_job(current, choice)
                self.assertNotEqual((world.countries, world.treasury, world.jobs, world.state_modifiers), before)

    def test_completed_benefit_expires_and_cannot_be_refreshed_by_replayed_close(self):
        world, arc = world_and_arc()
        closed_event = finish_public(world, arc)
        state = world.countries["NMG"]; pilot = state["ywc_nmg_bay_pilot"]
        key = (pilot, BENEFITS[1])
        self.assertIn(key, world.state_modifiers)
        expiry = world.state_modifiers[key]["expires"]
        old_job = world._school_event_jobs[id(closed_event)]
        world.choose_job(old_job, "close_full")
        self.assertEqual(world.state_modifiers[key]["expires"], expiry)
        world.advance_months(24)
        world.run_country_monthly("NMG")
        self.assertNotIn(key, world.state_modifiers)
        self.assertNotIn("ywc_nmg_bay_benefit_active", state)

    def test_completed_benefit_stops_when_pilot_changes_owner_or_loses_port_input(self):
        for loss in ("ownership", "shortage"):
            with self.subTest(loss=loss):
                world, arc = world_and_arc()
                finish_public(world, arc)
                state = world.countries["NMG"]; pilot = state["ywc_nmg_bay_pilot"]
                key = (pilot, BENEFITS[1])
                self.assertIn(key, world.state_modifiers)
                province = state["states"][0]
                if loss == "ownership":
                    province["owner"] = "MEX"
                    world.run_state_owner_change(pilot)
                else:
                    next(b for b in province["buildings"] if b["type"] == "building_port")["shortage"] = True
                    world.advance_months(1)
                    world.run_country_monthly("NMG")
                self.assertNotIn(key, world.state_modifiers)

    def test_cached_public_selection_rechecks_live_port_employment_before_effect(self):
        world, arc = world_and_arc()
        event = deliver(world, arc, 1100)
        job = world._school_event_jobs[id(event)]
        self.assertTrue(world.job_options(job)["public_port"])
        state = world.countries["NMG"]["states"][0]
        worker = next(p for p in state["pops"] if p["type"] == "laborers")
        worker["workplace"]["occupancy"] = .79
        before = copy.deepcopy((world.countries, world.treasury, world.jobs))
        world.choose_job(job, "public_port")
        self.assertEqual((world.countries, world.treasury, world.jobs), before)

    def test_replaying_an_old_choice_cannot_replace_captured_policy_or_queue(self):
        world, arc = world_and_arc()
        event = deliver(world, arc, 1100)
        job = world._school_event_jobs[id(event)]
        self.assertTrue(world.job_options(job)["public_port"])
        world.choose_job(job, "public_port")
        world.refresh(arc)
        before = copy.deepcopy((world.countries, world.treasury, world.jobs))
        world.choose_job(job, "refuse_capital")
        self.assertEqual((world.countries, world.treasury, world.jobs), before)

    def test_subject_cannot_request_a_third_party_even_if_choice_was_cached(self):
        fixture = three_partner_countries()
        world, arc = world_and_arc(fixture)
        play(world, arc, 1100, "limited_operation")
        event = deliver(world, arc, 1101)
        job = world._school_event_jobs[id(event)]
        options = world.job_options(job)
        self.assertTrue(options["request_mexico"])
        self.assertFalse(options["request_usa"])
        self.assertFalse(options["request_jhg"])
        before = copy.deepcopy((world.countries, world.treasury, world.jobs))
        world.choose_job(job, "request_usa")
        self.assertEqual((world.countries, world.treasury, world.jobs), before)

    def test_independent_country_can_request_each_real_eligible_partner(self):
        for tag, choice in (("MEX", "request_mexico"), ("USA", "request_usa"), ("JHG", "request_jhg")):
            with self.subTest(partner=tag):
                fixture = three_partner_countries()
                fixture["NMG"].update(is_subject=False, overlord=None)
                world, arc = world_and_arc(fixture)
                play(world, arc, 1100, "limited_operation")
                event = deliver(world, arc, 1101)
                job = world._school_event_jobs[id(event)]
                self.assertTrue(world.job_options(job)[choice])
                world.choose_job(job, choice)
                replies = [candidate for candidate in world.jobs if candidate.event_id == "ywc_nmg.1108"]
                self.assertEqual(len(replies), 1)
                self.assertEqual(replies[0].recipient, world.country_ref(tag))
                self.assertTrue(all(amount == 0 for amount in world.treasury.values()))

    def test_public_and_refused_capital_paths_pay_two_real_fees(self):
        for mode, ratio in (("public_port", 1), ("refuse_capital", .5)):
            with self.subTest(mode=mode):
                world, arc = world_and_arc()
                play(world, arc, 1100, mode)
                play(world, arc, 1101, "local_terms")
                before = world.treasury["NMG"]
                play(world, arc, 1102, "pay_charter")
                self.assertEqual(before - world.treasury["NMG"], 1000 * ratio)
                self.assertEqual(world.countries["NMG"]["ywc_nmg_bay_charter_paid"], 1)
                self.assertEqual(world.countries["NMG"]["ywc_nmg_bay_charter_paid_amount"], 1000 * ratio)
                play(world, arc, 1103, "sign_duties")
                before = world.treasury["NMG"]
                play(world, arc, 1104, "pay_maintenance")
                self.assertEqual(before - world.treasury["NMG"], 1000 * ratio)
                self.assertEqual(world.countries["NMG"]["ywc_nmg_bay_maintenance_paid"], 1)
                self.assertEqual(world.countries["NMG"]["ywc_nmg_bay_maintenance_paid_amount"], 1000 * ratio)
                self.assertEqual(world.treasury["MEX"], 0)

    def test_limited_preparation_works_with_no_port_and_uses_real_office(self):
        fixture = countries()
        state = fixture["NMG"]["states"][0]
        state["buildings"] = [b for b in state["buildings"] if b["type"] != "building_port"]
        state["pops"] = [p for p in state["pops"] if p["type"] != "laborers"]
        world = NmgBayWorld(fixture)
        world.assert_bay_hook_loaded_once()
        world.run("ywc_v03_initialize_country", "NMG")
        world._school_handled_jobs = {job.serial for job in world.jobs}
        world._school_country_month = None
        arc = next(a for a in world.cat["arcs"] if a.get("slug") == "v03_nmg_bay_ports")
        play(world, arc, 1100, "limited_preparation")
        play(world, arc, 1101, "local_terms")
        play(world, arc, 1102, "pay_charter")
        self.assertEqual(world.treasury["NMG"], -250)
        play(world, arc, 1103, "sign_duties")
        play(world, arc, 1104, "pay_maintenance")
        self.assertEqual(world.treasury["NMG"], -500)
        for _ in range(5):
            real_month(world, arc)
            assert_no_early_advance(self, world)
        real_month(world, arc)
        play(world, arc, 1105, "advance_review")
        play(world, arc, 1106, "request_limited")
        play(world, arc, 1107, "close_limited")
        self.assertEqual(world.treasury["NMG"], -500)
        self.assertEqual(world.countries["NMG"]["ywc_v03_nmg_v03_nmg_bay_ports_outcome"], 2)
        self.assertFalse(any(name in BENEFITS.values() for _, name in world.state_modifiers))
        self.assertTrue(all(world.history["NMG"].get(j["id"]) == "complete" for j in arc["journals"]))

    def test_public_observation_requires_twelve_new_months_then_reaches_full_outcome(self):
        world, arc = world_and_arc()
        for number, key in ((1100, "public_port"), (1101, "local_terms"),
                            (1102, "pay_charter"), (1103, "sign_duties"),
                            (1104, "pay_maintenance")):
            play(world, arc, number, key)
        state = world.countries["NMG"]
        self.assertEqual(state["ywc_nmg_bay_review_streak"], 0)
        world.run_country_monthly("NMG")
        self.assertEqual(state["ywc_nmg_bay_review_streak"], 0, "creation month cannot count")
        for expected in range(1, 12):
            real_month(world, arc)
            self.assertEqual(state["ywc_nmg_bay_review_streak"], expected)
            world.run_country_monthly("NMG")
            self.assertEqual(state["ywc_nmg_bay_review_streak"], expected, "month counted twice")
            assert_no_early_advance(self, world)
        real_month(world, arc)
        self.assertEqual(state["ywc_nmg_bay_review_streak"], 12)
        self.assertNotIn((state["ywc_nmg_bay_pilot"], BENEFITS[1]), world.state_modifiers)
        play(world, arc, 1105, "advance_review")
        play(world, arc, 1106, "request_full")
        play(world, arc, 1107, "close_full")
        self.assertEqual(world.treasury["NMG"], -2000)
        self.assertEqual(state["ywc_v03_nmg_v03_nmg_bay_ports_outcome"], 1)
        self.assertIn((state["ywc_nmg_bay_pilot"], BENEFITS[1]), world.state_modifiers)
        self.assertTrue(all(world.history["NMG"].get(j["id"]) == "complete" for j in arc["journals"]))

    def test_refusing_capital_is_a_full_route_when_actual_duties_are_met(self):
        world, arc = world_and_arc()
        for number, key in ((1100, "refuse_capital"), (1101, "local_terms"),
                            (1102, "pay_charter"), (1103, "sign_duties"),
                            (1104, "pay_maintenance")):
            play(world, arc, number, key)
        for _ in range(12):
            real_month(world, arc)
        play(world, arc, 1105, "advance_review")
        play(world, arc, 1106, "request_full")
        play(world, arc, 1107, "close_full")
        self.assertEqual(world.treasury["NMG"], -1000)
        self.assertEqual(world.treasury["MEX"], 0)
        self.assertEqual(world.countries["NMG"]["ywc_v03_nmg_v03_nmg_bay_ports_outcome"], 1)
        self.assertIn((world.countries["NMG"]["ywc_nmg_bay_pilot"], BENEFITS[3]), world.state_modifiers)
        self.assertTrue(all(world.history["NMG"].get(j["id"]) == "complete" for j in arc["journals"]))

    def test_interrupted_public_observation_requires_explicit_twelve_fresh_months(self):
        world, arc = world_and_arc()
        for number, key in ((1100, "public_port"), (1101, "local_terms"),
                            (1102, "pay_charter"), (1103, "sign_duties"),
                            (1104, "pay_maintenance")):
            play(world, arc, number, key)
        state = world.countries["NMG"]
        for _ in range(2):
            real_month(world, arc)
        self.assertEqual(state["ywc_nmg_bay_review_streak"], 2)
        worker = next(p for p in state["states"][0]["pops"] if p["type"] == "laborers")
        worker["workplace"]["occupancy"] = .79
        real_month(world, arc)
        self.assertEqual(state["ywc_nmg_bay_review_streak"], 0)
        self.assertIn("ywc_nmg_bay_review_interrupted", state)
        worker["workplace"]["occupancy"] = .8
        real_month(world, arc)
        self.assertEqual(state["ywc_nmg_bay_review_streak"], 0, "restoring eligibility cannot silently resume")
        play(world, arc, 1105, "restart_review")
        self.assertEqual(state["ywc_nmg_bay_review_streak"], 0)
        for expected in range(1, 12):
            real_month(world, arc)
            self.assertEqual(state["ywc_nmg_bay_review_streak"], expected)
            assert_no_early_advance(self, world)
        real_month(world, arc)
        play(world, arc, 1105, "advance_review")
        play(world, arc, 1106, "request_full")
        play(world, arc, 1107, "close_full")
        self.assertEqual(world.treasury["NMG"], -2000, "recount must not charge either fee again")

    def test_narrowing_requires_real_matching_earned_responsibility_before_display(self):
        world, arc = world_and_arc()
        for number, key in ((1100, "public_port"), (1101, "local_terms"),
                            (1102, "pay_charter"), (1103, "sign_duties"),
                            (1104, "pay_maintenance")):
            play(world, arc, number, key)
        for _ in range(12):
            real_month(world, arc)
        event = deliver(world, arc, 1105)
        job = world._school_event_jobs[id(event)]
        self.assertTrue(world.job_options(job)["narrow_and_recount"])
        world.countries["NMG"]["ywc_nmg_bay_signed_mode"] = 3
        self.assertFalse(world.job_options(job)["narrow_and_recount"])
        before = copy.deepcopy((world.countries, world.treasury, world.jobs))
        world.choose_job(job, "narrow_and_recount")
        self.assertEqual((world.countries, world.treasury, world.jobs), before)

    def test_loan_months_before_operations_do_not_count_and_full_remains_reachable(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        world.choose_job(reply, "accept_advance")
        for _ in range(6):
            real_month(world, arc)
        for number, key in ((1102, "pay_charter"), (1103, "sign_duties"),
                            (1104, "pay_maintenance")):
            play(world, arc, number, key)
        state = world.countries["NMG"]
        self.assertEqual(state["ywc_nmg_bay_review_streak"], 0)
        world.run_country_monthly("NMG")
        self.assertEqual(state["ywc_nmg_bay_review_streak"], 0)
        for expected in range(1, 12):
            real_month(world, arc)
            self.assertEqual(state["ywc_nmg_bay_review_streak"], expected)
            world.run_country_monthly("NMG")
            self.assertEqual(state["ywc_nmg_bay_review_streak"], expected)
            assert_no_early_advance(self, world)
        real_month(world, arc)
        self.assertEqual(state["ywc_nmg_bay_review_streak"], 12)
        self.assertAlmostEqual(state["ywc_nmg_bay_principal"], state["ywc_nmg_bay_repaid_total"])
        play(world, arc, 1105, "advance_review")
        play(world, arc, 1106, "request_full")
        play(world, arc, 1107, "close_full")
        self.assertAlmostEqual(world.treasury["NMG"], -2000)
        self.assertAlmostEqual(world.treasury["MEX"], 0)
        self.assertEqual(state["ywc_v03_nmg_v03_nmg_bay_ports_outcome"], 1)
        self.assertIn((state["ywc_nmg_bay_pilot"], BENEFITS[2]), world.state_modifiers)
        # The advance has been repaid; the subsequent local benefit is not an
        # indefinite foreign operating permission or a new partner veto.
        state["is_subject"] = False
        state["overlord"] = None
        world.countries["MEX"]["relations"]["NMG"] = -50
        world.advance_months(1)
        world.run_country_monthly("NMG")
        self.assertIn((state["ywc_nmg_bay_pilot"], BENEFITS[2]), world.state_modifiers)
        self.assertTrue(all(world.history["NMG"].get(j["id"]) == "complete" for j in arc["journals"]))

    def test_stale_payment_option_after_pilot_ownership_loss_cannot_charge(self):
        world, arc = world_and_arc()
        play(world, arc, 1100, "public_port")
        play(world, arc, 1101, "local_terms")
        event = deliver(world, arc, 1102)
        job = world._school_event_jobs[id(event)]
        self.assertTrue(world.job_options(job)["pay_charter"])
        world.countries["NMG"]["states"][0]["owner"] = "MEX"
        world.choose_job(job, "pay_charter")
        self.assertEqual(world.treasury, {"NMG": 0, "MEX": 0})
        self.assertNotIn("ywc_nmg_bay_charter_paid", world.countries["NMG"])

    def test_recovered_facts_invalidate_a_cached_honest_setback(self):
        world, arc = world_and_arc()
        for number, key in ((1100, "public_port"), (1101, "local_terms"),
                            (1102, "pay_charter"), (1103, "sign_duties"),
                            (1104, "pay_maintenance")):
            play(world, arc, number, key)
        for _ in range(12):
            real_month(world, arc)
        play(world, arc, 1105, "advance_review")
        event = deliver(world, arc, 1106)
        job = world._school_event_jobs[id(event)]
        worker = next(p for p in world.countries["NMG"]["states"][0]["pops"] if p["type"] == "laborers")
        worker["workplace"]["occupancy"] = .79
        self.assertTrue(world.job_options(job)["request_setback"])
        world.choose_job(job, "request_setback")
        world.refresh(arc)
        final = deliver(world, arc, 1107)
        final_job = world._school_event_jobs[id(final)]
        worker["workplace"]["occupancy"] = .8
        before = copy.deepcopy((world.countries, world.treasury, world.jobs))
        world.choose_job(final_job, "close_setback")
        self.assertEqual((world.countries, world.treasury, world.jobs), before)

    def test_real_reply_is_required_and_refusal_moves_no_principal(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        self.assertEqual(world.treasury, {"NMG": 0, "MEX": 0})
        self.assertTrue(world.job_options(reply)["refuse"])
        world.choose_job(reply, "refuse")
        self.assertEqual(world.treasury, {"NMG": 0, "MEX": 0})
        self.assertNotIn("ywc_nmg_bay_debt_generation", world.countries["NMG"])

    def test_acceptance_and_twelve_monthly_payments_conserve_both_treasuries(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        self.assertTrue(world.job_options(reply)["accept_advance"])
        before_cooldown = world.days_until_expiry["NMG"].get("ywc_v03_major_event_cooldown")
        world.choose_job(reply, "accept_advance")
        self.assertEqual(world.days_until_expiry["NMG"].get("ywc_v03_major_event_cooldown"), before_cooldown)
        self.assertNotIn("ywc_v03_major_event_cooldown", world.countries["MEX"])
        principal = world.countries["NMG"]["ywc_nmg_bay_principal"]
        self.assertGreater(principal, 0)
        self.assertEqual((world.treasury["NMG"], world.treasury["MEX"]), (principal, -principal))
        self.assertNotIn("ywc_nmg_bay_charter_paid", world.countries["NMG"])
        self.assertNotIn("ywc_nmg_bay_maintenance_paid", world.countries["NMG"])
        world.choose_job(reply, "accept_advance")  # replay must not create money
        self.assertEqual((world.treasury["NMG"], world.treasury["MEX"]), (principal, -principal))
        for _ in range(12):
            world.advance_months(1)
            world.run_country_monthly("NMG")
            after = dict(world.treasury)
            world.run_country_monthly("NMG")
            world.run_country_monthly("MEX")
            self.assertEqual(world.treasury, after, "duplicate callback paid twice")
            self.assertAlmostEqual(sum(world.treasury.values()), 0)
        self.assertAlmostEqual(world.treasury["NMG"], 0)
        self.assertAlmostEqual(world.treasury["MEX"], 0)
        self.assertAlmostEqual(world.countries["NMG"]["ywc_nmg_bay_repaid_total"], principal)

    def test_cached_foreign_answer_after_overlord_change_cannot_pay(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        world.countries["NMG"]["overlord"] = "USA"
        self.assertTrue(world.job_options(reply)["stale"], "an invalidated open foreign popup must be dismissible")
        world.choose_job(reply, "stale")
        world.choose_job(reply, "accept_advance")
        self.assertEqual(world.treasury, {"NMG": 0, "MEX": 0})
        self.assertNotIn("ywc_nmg_bay_debt_generation", world.countries["NMG"])

    def test_cached_accept_after_creditor_loses_cash_cannot_partially_disburse(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        self.assertTrue(world.job_options(reply)["accept_advance"])
        world.countries["MEX"]["gold_reserves"] = 0
        world.choose_job(reply, "accept_advance")
        self.assertEqual(world.treasury, {"NMG": 0, "MEX": 0})
        self.assertNotIn("ywc_nmg_bay_debt_generation", world.countries["NMG"])
        self.assertNotIn("ywc_nmg_bay_creditor_generation", world.countries["MEX"])

    def test_each_changed_captured_offer_term_blocks_foreign_acceptance(self):
        for name in ("generation", "serial", "quote_principal", "quote_term", "quote_scope_kind", "mode", "target", "pilot"):
            with self.subTest(term=name):
                world, arc = world_and_arc()
                reply = ask_mexico(world, arc)
                state = world.countries["NMG"]
                key = "ywc_nmg_bay_" + name
                if name == "pilot":
                    state[key] = StateRef(world.countries["MEX"]["states"][0]["_sid"])
                else:
                    state[key] += 1
                world.choose_job(reply, "accept_advance")
                self.assertEqual(world.treasury, {"NMG": 0, "MEX": 0})
                self.assertNotIn("ywc_nmg_bay_debt_generation", state)

    def test_mismatched_creditor_ledger_cannot_pay_one_side(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        world.choose_job(reply, "accept_advance")
        principal = world.countries["NMG"]["ywc_nmg_bay_principal"]
        world.countries["MEX"]["ywc_nmg_bay_creditor_generation"] += 1
        borrower = world.countries["NMG"]
        before_due = borrower["ywc_nmg_bay_scheduled_total"]
        before_month = borrower.get("ywc_nmg_bay_last_loan_month")
        world.advance_months(1)
        world.run_country_monthly("NMG")
        self.assertEqual((world.treasury["NMG"], world.treasury["MEX"]), (principal, -principal))
        self.assertEqual(borrower["ywc_nmg_bay_repaid_total"], 0)
        self.assertEqual(borrower["ywc_nmg_bay_scheduled_total"], before_due)
        self.assertEqual(borrower.get("ywc_nmg_bay_last_loan_month"), before_month)

    def test_mismatched_captured_contract_terms_never_release_payment(self):
        for suffix in ("offer_serial", "term", "mode", "target", "scope_kind", "start_month"):
            with self.subTest(term=suffix):
                world, arc = world_and_arc()
                reply = ask_mexico(world, arc)
                world.choose_job(reply, "accept_advance")
                state = world.countries["NMG"]
                creditor = world.countries["MEX"]
                principal = state["ywc_nmg_bay_principal"]
                creditor["ywc_nmg_bay_creditor_" + suffix] += 1
                world.advance_months(1)
                world.run_country_monthly("NMG")
                self.assertEqual((world.treasury["NMG"], world.treasury["MEX"]), (principal, -principal))
                self.assertEqual(state["ywc_nmg_bay_repaid_total"], 0)
                self.assertEqual(state["ywc_nmg_bay_scheduled_total"], 0)

    def test_signed_loan_can_resign_finite_at_each_preaccept_stage_without_erasing_debt(self):
        for stage in (1102, 1103, 1104):
            with self.subTest(stage=stage):
                world, arc = world_and_arc()
                reply = ask_mexico(world, arc)
                world.choose_job(reply, "accept_advance")
                state = world.countries["NMG"]
                principal = state["ywc_nmg_bay_principal"]
                generation = state["ywc_nmg_bay_debt_generation"]
                if stage >= 1103:
                    play(world, arc, 1102, "pay_charter")
                if stage >= 1104:
                    play(world, arc, 1103, "sign_duties")
                current = deliver(world, arc, stage)
                job = world._school_event_jobs[id(current)]
                state["overlord"] = "USA"  # Real subject relationship changes, not a story flag.
                self.assertTrue(world.job_options(job)["narrow_to_finite"])
                world.choose_job(job, "narrow_to_finite")
                world.refresh(arc)
                self.assertEqual((state["ywc_nmg_bay_mode"], state["ywc_nmg_bay_target"]), (3, 2))
                self.assertEqual((state["ywc_nmg_bay_principal"], state["ywc_nmg_bay_debt_generation"]), (principal, generation))
                if stage == 1102:
                    play(world, arc, 1102, "pay_charter")
                if stage <= 1103:
                    play(world, arc, 1103, "sign_duties")
                play(world, arc, 1104, "pay_maintenance")
                self.assertEqual(state["ywc_nmg_bay_charter_paid_amount"], 250 if stage == 1102 else 1000)
                self.assertEqual(state["ywc_nmg_bay_maintenance_paid_amount"], 250)
                self.assertEqual((state["ywc_nmg_bay_principal"], state["ywc_nmg_bay_debt_generation"]), (principal, generation))

    def test_expired_unanswered_offer_cannot_be_accepted_from_cached_popup(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        world.advance_months(4)
        world.run_country_monthly("NMG")
        world.choose_job(reply, "accept_advance")
        self.assertEqual(world.treasury, {"NMG": 0, "MEX": 0})
        self.assertNotIn("ywc_nmg_bay_debt_generation", world.countries["NMG"])

    def test_withdrawal_after_disbursement_leaves_debt_and_monthly_payments(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        world.choose_job(reply, "accept_advance")
        state = world.countries["NMG"]
        principal = state["ywc_nmg_bay_principal"]
        play(world, arc, 1102, "withdraw")
        self.assertEqual(state["ywc_v03_nmg_v03_nmg_bay_ports_outcome"], 4)
        self.assertEqual(state["ywc_nmg_bay_principal"], principal)
        world.advance_months(1)
        world.run_country_monthly("NMG")
        self.assertGreater(state["ywc_nmg_bay_repaid_total"], 0)
        self.assertEqual(state["ywc_nmg_bay_principal"], principal)
        self.assertAlmostEqual(sum(world.treasury.values()), 0)

    def test_new_loan_and_withdrawal_preserve_a_genuinely_signed_old_contract(self):
        from test_v03_nmg_partner_response import run_live_month

        world = NmgBayWorld(countries())
        world.assert_bay_hook_loaded_once()
        world.run("ywc_v03_initialize_country", "NMG")
        old = next(a for a in world.cat["arcs"] if a["slug"] == "v03_nmg_autonomy_revenue")
        bay = next(a for a in world.cat["arcs"] if a["slug"] == "v03_nmg_bay_ports")
        world.activate_entry(old, old["journals"][0]["id"])
        handled = set()
        choices = {"1020": "fixed", "1030": "accept", "1021": "audit_strict",
                   "1022": "close_account", "1023": "press_quota", "1024": "use_temperature",
                   "1025": "carry_heavy", "1026": "conclude"}
        def old_choice(_world, job, options):
            number = job.event_id.rsplit(".", 1)[-1]
            if number == "1027":
                return "settle_full" if options.get("settle_full") else "wait_retry"
            return choices[number]
        for _ in range(50):
            run_live_month(world, old, handled, old_choice)
            if world.countries["NMG"].get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"):
                break
        state = world.countries["NMG"]
        self.assertIn("ywc_nmg_mexshare_contract_generation", state, "old revenue contract was not earned through its real response")
        self.assertEqual(state.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"), 1)
        names = ("ywc_nmg_mexshare_contract_generation", "ywc_nmg_mexshare_contract_partner",
                 "ywc_nmg_mexshare_contract_monthly", "ywc_nmg_mexshare_contract_term")
        old_identity = {name: state[name] for name in names}
        already_paid = state["ywc_nmg_mexshare_paid_total"]
        world._school_handled_jobs = set(handled)
        world._school_country_month = world.date
        reply = ask_mexico(world, bay)
        world.choose_job(reply, "accept_advance")
        play(world, bay, 1102, "withdraw")
        self.assertEqual({name: state[name] for name in names}, old_identity)
        self.assertGreaterEqual(state["ywc_nmg_mexshare_paid_total"], already_paid)
        self.assertIn("ywc_nmg_bay_debt_generation", state)

    def test_default_preserves_debt_and_accrues_elapsed_periods(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        self.assertTrue(world.job_options(reply)["accept_advance"])
        world.choose_job(reply, "accept_advance")
        principal = world.countries["NMG"]["ywc_nmg_bay_principal"]
        world.countries["NMG"]["in_default"] = True
        for _ in range(3):
            world.advance_months(1)
            world.run_country_monthly("NMG")
        self.assertEqual((world.treasury["NMG"], world.treasury["MEX"]), (principal, -principal))
        self.assertEqual(world.countries["NMG"]["ywc_nmg_bay_repaid_total"], 0)
        world.countries["NMG"]["in_default"] = False
        world.advance_months(1)
        world.run_country_monthly("NMG")
        self.assertAlmostEqual(world.countries["NMG"]["ywc_nmg_bay_repaid_total"], principal / 3)
        self.assertAlmostEqual(sum(world.treasury.values()), 0)
        self.assertEqual(world.countries["NMG"]["ywc_nmg_bay_principal"], principal)

    def test_missed_callbacks_accrue_real_elapsed_loan_periods_without_double_payment(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        world.choose_job(reply, "accept_advance")
        state = world.countries["NMG"]
        principal = state["ywc_nmg_bay_principal"]
        # No observation credit is claimed: intentionally omit only debt
        # callbacks, then run the actual source on the fifth calendar month.
        world.advance_months(5)
        world.run_country_monthly("NMG")
        self.assertAlmostEqual(state["ywc_nmg_bay_repaid_total"], principal * 5 / 12)
        before = dict(world.treasury)
        world.run_country_monthly("NMG")
        self.assertEqual(world.treasury, before)
        self.assertAlmostEqual(sum(world.treasury.values()), 0)

    def test_insufficient_funds_pay_at_most_one_period_then_catch_up(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        world.choose_job(reply, "accept_advance")
        state = world.countries["NMG"]
        principal = state["ywc_nmg_bay_principal"]
        world.advance_months(3)
        # set_cash changes only the harness's present reserves; all debt and
        # payment records are still earned by actual source and callbacks.
        set_cash(world, principal / 12)
        world.run_country_monthly("NMG")
        self.assertAlmostEqual(state["ywc_nmg_bay_repaid_total"], principal / 12)
        self.assertAlmostEqual(sum(world.treasury.values()), 0)
        world.advance_months(1)
        set_cash(world, principal * 2)
        world.run_country_monthly("NMG")
        self.assertAlmostEqual(state["ywc_nmg_bay_repaid_total"], principal * 4 / 12)
        self.assertAlmostEqual(sum(world.treasury.values()), 0)

    def test_destroyed_creditor_keeps_outstanding_debt_without_paying_recreated_country(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        world.choose_job(reply, "accept_advance")
        state = world.countries["NMG"]
        principal = state["ywc_nmg_bay_principal"]
        old_creditor = world.country_ref("MEX")
        replacement = copy.deepcopy(countries()["MEX"])
        world.remove_country("MEX")
        world.advance_months(1)
        world.run_country_monthly("NMG")
        self.assertEqual(state["ywc_nmg_bay_principal"], principal)
        self.assertEqual(state["ywc_nmg_bay_repaid_total"], 0)
        self.assertAlmostEqual(state["ywc_nmg_bay_scheduled_total"], principal / 12)
        world.add_country("MEX", replacement)
        self.assertNotEqual(world.country_ref("MEX"), old_creditor)
        world.advance_months(1)
        world.run_country_monthly("NMG")
        self.assertEqual(state["ywc_nmg_bay_repaid_total"], 0)
        self.assertEqual(state["ywc_nmg_bay_principal"], principal)

    def test_loss_of_pilot_does_not_erase_signed_debt_or_prevent_repayment(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        world.choose_job(reply, "accept_advance")
        state = world.countries["NMG"]
        principal = state["ywc_nmg_bay_principal"]
        state["states"][0]["owner"] = "MEX"
        world.advance_months(1)
        world.run_country_monthly("NMG")
        self.assertEqual(state["ywc_nmg_bay_principal"], principal)
        self.assertAlmostEqual(state["ywc_nmg_bay_repaid_total"], principal / 12)
        self.assertAlmostEqual(sum(world.treasury.values()), 0)

    def test_pilot_object_disappearing_does_not_stop_signed_debt_repayment(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        world.choose_job(reply, "accept_advance")
        state = world.countries["NMG"]
        principal = state["ywc_nmg_bay_principal"]
        state["states"].clear()
        world.advance_months(1)
        world.run_country_monthly("NMG")
        self.assertAlmostEqual(state["ywc_nmg_bay_repaid_total"], principal / 12)
        self.assertAlmostEqual(sum(world.treasury.values()), 0)

    def test_different_live_pilot_in_creditor_mirror_blocks_payment(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        world.choose_job(reply, "accept_advance")
        state = world.countries["NMG"]
        principal = state["ywc_nmg_bay_principal"]
        other = StateRef(world.countries["MEX"]["states"][0]["_sid"])
        self.assertNotEqual(other, state["ywc_nmg_bay_debt_pilot"])
        world.countries["MEX"]["ywc_nmg_bay_creditor_pilot"] = other
        world.advance_months(1)
        world.run_country_monthly("NMG")
        self.assertEqual((world.treasury["NMG"], world.treasury["MEX"]), (principal, -principal))
        self.assertEqual(state["ywc_nmg_bay_repaid_total"], 0)

    def test_missing_pilot_never_excuses_a_mismatched_contract_serial(self):
        world, arc = world_and_arc()
        reply = ask_mexico(world, arc)
        world.choose_job(reply, "accept_advance")
        state = world.countries["NMG"]
        principal = state["ywc_nmg_bay_principal"]
        state["states"].clear()
        world.countries["MEX"]["ywc_nmg_bay_creditor_offer_serial"] += 1
        world.advance_months(1)
        world.run_country_monthly("NMG")
        self.assertEqual((world.treasury["NMG"], world.treasury["MEX"]), (principal, -principal))
        self.assertEqual(state["ywc_nmg_bay_repaid_total"], 0)

    def test_deleted_pilot_receipt_is_not_the_same_as_a_disappeared_state(self):
        for owner, name in (("NMG", "ywc_nmg_bay_debt_pilot"), ("MEX", "ywc_nmg_bay_creditor_pilot")):
            with self.subTest(owner=owner):
                world, arc = world_and_arc()
                reply = ask_mexico(world, arc)
                world.choose_job(reply, "accept_advance")
                state = world.countries["NMG"]
                principal = state["ywc_nmg_bay_principal"]
                state["states"].clear()
                del world.countries[owner][name]
                world.advance_months(1)
                world.run_country_monthly("NMG")
                self.assertEqual((world.treasury["NMG"], world.treasury["MEX"]), (principal, -principal))
                self.assertEqual(state["ywc_nmg_bay_repaid_total"], 0)


if __name__ == "__main__":
    unittest.main()
