"""Actual-source regressions for native immediate provenance."""
import json
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests import test_v03_dmg_fair_delivery as dmg
from tests import test_v03_kor_fair_delivery as kor
from tests import test_v03_nqg_fair_delivery as nqg
from tests import test_v03_oir_foundation as oir
from tests import test_v03_aggregate_scheduler as aggregate_scheduler
from tests.shu_kor_strict_review_runtime import field
from tests.clausewitz_harness import parse
from tools.v03_delivery_scheduler import validate_catalogue_adapters


def _strip_old_lifecycle(state):
    for key in ("ywc_v03_initialized", "ywc_v03_release_version",
                "ywc_v03_active_arc_count", "ywc_v03_visible_task_count"):
        state.pop(key, None)


def _dmg_reserved():
    dmg.DmgActualFairDelivery.setUpClass()
    world = dmg.DmgInlineWorld()
    _strip_old_lifecycle(world.countries["DMG"])
    world.run("ywc_v03_initialize_country", "DMG")
    arc = dmg.DmgActualFairDelivery.ARCS[0]
    dmg._admit_real_je(world, arc)
    world.advance_months(1)
    dmg._pulse_real_je(world, arc)
    return world, arc, arc["events"][0]["id"]


def _oir_reserved():
    world = oir.world()
    _strip_old_lifecycle(world.countries["OIR"])
    world.run("ywc_v03_initialize_country", "OIR")
    arc = json.loads(oir.CAT.read_text(encoding="utf-8"))["arcs"][0]
    oir.start(world, arc)
    oir.pulse_current(world, arc)
    return world, arc, arc["events"][0]["id"]


def _public_helper(world, country, helper):
    if country == "OIR":
        world.run(helper, country)
    else:
        world.execute([(helper, "=", "yes")], country)


def _authored_event(country, event_id):
    path = ROOT / f"yongchang_world/events/ywc_v03_country_{country.lower()}_events.txt"
    events = dict((name, body) for name, _, body in parse(path.read_text(encoding="utf-8-sig")))
    return events[event_id]


class ActualImmediateProvenanceContract(unittest.TestCase):
    """Old/currently unexecuted receipts cannot close a real reservation."""

    def test_oir_absent_receipt_preserves_current_reservation(self):
        world, arc, event_id = _oir_reserved()
        state = world.countries["OIR"]
        before = copy.deepcopy(state)
        _public_helper(world, "OIR", "ywc_v03_scheduler_ack_v03_oir_pasture_boundaries_event_1000")
        self.assertEqual(state, before, "OIR absent-receipt public ACK changed country state")
        self.assertIn("ywc_oir_pasture_pending_event", state)
        self.assertIn("ywc_v03_country_oir_reservation_arc", state)
        self.assertNotIn("ywc_v03_scheduler_served_v03_oir_pasture_boundaries", state)
        self.assertNotIn("ywc_v03_major_event_cooldown", state)

    def test_oir_controlled_historical_receipt_is_rejected(self):
        world, arc, event_id = _oir_reserved()
        state = world.countries["OIR"]
        state["ywc_oir_pasture_last_event"] = 1000
        before = copy.deepcopy(state)
        _public_helper(world, "OIR", "ywc_v03_scheduler_ack_v03_oir_pasture_boundaries_event_1000")
        self.assertEqual(state, before, "OIR historical-receipt public ACK changed country state")
        self.assertEqual(state.get("ywc_oir_pasture_pending_event"), 1000)
        self.assertIn("ywc_v03_country_oir_reservation_arc", state)
        self.assertNotIn("ywc_v03_scheduler_served_v03_oir_pasture_boundaries", state)
        self.assertNotIn("ywc_v03_major_event_cooldown", state)

    def test_dmg_absent_receipt_preserves_current_reservation(self):
        world, arc, event_id = _dmg_reserved()
        state = world.countries["DMG"]
        before = copy.deepcopy(state)
        _public_helper(world, "DMG", "ywc_v03_dmg_inline_ack_1")
        self.assertEqual(state, before, "DMG absent-receipt public ACK changed country state")
        self.assertEqual(state.get("ywc_dmg_pending_event"), 1000)
        self.assertIn("ywc_v03_dmg_inline_reservation", state)
        self.assertNotIn("ywc_v03_dmg_inline_served_1", state)
        self.assertNotIn("ywc_v03_major_event_cooldown", state)

    def test_dmg_controlled_historical_receipt_is_rejected(self):
        world, arc, event_id = _dmg_reserved()
        state = world.countries["DMG"]
        state["ywc_v03_dmg_v03_dmg_common_subjects_last_event"] = 1
        before = copy.deepcopy(state)
        _public_helper(world, "DMG", "ywc_v03_dmg_inline_ack_1")
        self.assertEqual(state, before, "DMG historical-receipt public ACK changed country state")
        self.assertEqual(state.get("ywc_dmg_pending_event"), 1000)
        self.assertIn("ywc_v03_dmg_inline_reservation", state)
        self.assertNotIn("ywc_v03_dmg_inline_served_1", state)
        self.assertNotIn("ywc_v03_major_event_cooldown", state)

    def test_kor_controlled_legacy_receipt_is_rejected(self):
        world, event = kor.KorFairDeliveryContract()._reserve_school_event()
        state = world.countries["KOR"]
        state["ywc_v03_kor_v03_kor_military_accounts_last_event"] = 10
        before = copy.deepcopy(state)
        _public_helper(world, "KOR", "ywc_v03_kor_inline_callback_11")
        self.assertEqual(state, before, "KOR historical-receipt public callback changed country state")
        self.assertEqual(state.get("ywc_kor_school_pending_event"), 1010)
        self.assertIn("ywc_v03_kor_inline_reservation", state)
        self.assertNotIn("ywc_v03_kor_inline_served_2", state)
        self.assertNotIn("ywc_v03_major_event_cooldown", state)

    def test_kor_absent_current_receipt_preserves_reservation(self):
        world, event = kor.KorFairDeliveryContract()._reserve_school_event()
        state = world.countries["KOR"]
        state.pop("ywc_v03_kor_v03_kor_military_accounts_last_event", None)
        before = copy.deepcopy(state)
        _public_helper(world, "KOR", "ywc_v03_kor_inline_callback_11")
        self.assertEqual(state, before, "KOR absent-receipt public callback changed country state")
        self.assertEqual(state.get("ywc_kor_school_pending_event"), 1010)
        self.assertIn("ywc_v03_kor_inline_reservation", state)
        self.assertNotIn("ywc_v03_kor_inline_served_2", state)
        self.assertNotIn("ywc_v03_major_event_cooldown", state)

    def test_nqg_controlled_old_receipt_is_rejected(self):
        world, journal, event_id, candidate = nqg._reserve_first_source_popup()
        state = world.countries["NQG"]
        state["ywc_v03_nqg_v03_nqg_winter_court_last_event"] = 1000
        before = copy.deepcopy(state)
        _public_helper(world, "NQG", "ywc_v03_nqg_inline_callback_4")
        self.assertEqual(state, before, "NQG historical-receipt public callback changed country state")
        self.assertEqual(state.get("ywc_nqg_winter_pending"), 1000)
        self.assertIn("ywc_v03_nqg_inline_reservation", state)
        self.assertNotIn("ywc_v03_nqg_inline_served_1", state)
        self.assertNotIn("ywc_v03_major_event_cooldown", state)

    def test_nqg_absent_current_receipt_preserves_reservation(self):
        world, journal, event_id, candidate = nqg._reserve_first_source_popup()
        state = world.countries["NQG"]
        state.pop("ywc_v03_nqg_v03_nqg_winter_court_last_event", None)
        before = copy.deepcopy(state)
        _public_helper(world, "NQG", "ywc_v03_nqg_inline_callback_4")
        self.assertEqual(state, before, "NQG absent-receipt public callback changed country state")
        self.assertEqual(state.get("ywc_nqg_winter_pending"), 1000)
        self.assertIn("ywc_v03_nqg_inline_reservation", state)
        self.assertNotIn("ywc_v03_nqg_inline_served_1", state)
        self.assertNotIn("ywc_v03_major_event_cooldown", state)

    def test_real_event_immediates_still_complete_native_ack_for_all_four(self):
        world, arc, event_id = _dmg_reserved()
        dmg._receive_actual_event_and_wait(world, arc, event_id, run_wait=False)
        self.assertEqual(world.countries["DMG"].get("ywc_v03_major_event_cooldown"), 1)

        world, event = kor.KorFairDeliveryContract()._reserve_school_event()
        kor._receive_and_defer(world, "ywc_kor.1010")
        self.assertEqual(world.countries["KOR"].get("ywc_v03_major_event_cooldown"), 1)

        world, journal, event_id, candidate = nqg._reserve_first_source_popup()
        nqg._deliver_reserved(world, event_id)
        self.assertEqual(world.countries["NQG"].get("ywc_v03_major_event_cooldown"), 1)

        world, arc, event_id = _oir_reserved()
        oir.fire(world, arc, 1000)
        self.assertEqual(world.countries["OIR"].get("ywc_v03_major_event_cooldown"), 1)

    def test_guarded_native_immediate_fails_closed_after_both_epochs_are_lost(self):
        """Controlled delayed-popup race after a genuinely accepted source dispatch."""
        cases = []
        world, arc, event_id = _oir_reserved()
        cases.append(("OIR", world, event_id, "ywc_v03_scheduler_provenance_epoch",
                      "ywc_v03_scheduler_candidate_epoch_1"))
        world, arc, event_id = _dmg_reserved()
        cases.append(("DMG", world, event_id, "ywc_v03_dmg_inline_reservation_epoch",
                      "ywc_v03_dmg_inline_candidate_epoch_1"))
        world, event = kor.KorFairDeliveryContract()._reserve_school_event()
        cases.append(("KOR", world, "ywc_kor.1010", "ywc_v03_kor_inline_reservation_epoch",
                      "ywc_v03_kor_inline_candidate_epoch_11"))
        world, journal, event_id, candidate = nqg._reserve_first_source_popup()
        cases.append(("NQG", world, event_id, "ywc_v03_nqg_inline_reservation_epoch",
                      "ywc_v03_nqg_inline_candidate_epoch_4"))
        for country, world, event_id, global_epoch, candidate_epoch in cases:
            with self.subTest(country=country, fault="delete_global_and_candidate_epoch"):
                event = _authored_event(country, event_id) if country in {"OIR", "DMG"} else world.event_defs[event_id]
                state = world.countries[country]
                self.assertTrue(world.conditions(field(event, "trigger"), country),
                                f"{country}: source-dispatched popup must initially be accepted")
                state.pop(global_epoch, None)
                state.pop(candidate_epoch, None)
                before = copy.deepcopy(state)
                trigger_after_fault = world.conditions(field(event, "trigger"), country)
                # Defensive execution of the real guarded immediate body after
                # a controlled race; no UI dispatch is fabricated here.
                world.execute(field(event, "immediate"), country)
                self.assertEqual(state, before,
                                 f"{country}: guarded immediate changed native state after epoch loss; trigger_after_fault={trigger_after_fault}")

    def test_guarded_native_immediate_fails_closed_for_current_provenance_fault_matrix(self):
        """AST fault injection against four genuinely source-dispatched events."""
        recipes = (
            ("OIR", _oir_reserved, "ywc_v03_scheduler_provenance_epoch", "ywc_v03_scheduler_candidate_epoch_1",
             "ywc_v03_scheduler_snapshot_1_present", "ywc_v03_scheduler_snapshot_1_value", "ywc_oir_pasture_pending_event", 1000,
             "ywc_v03_scheduler_served_v03_oir_pasture_boundaries"),
            ("DMG", _dmg_reserved, "ywc_v03_dmg_inline_reservation_epoch", "ywc_v03_dmg_inline_candidate_epoch_1",
             "ywc_v03_dmg_inline_c1_pending_event_present", "ywc_v03_dmg_inline_c1_pending_event_value", "ywc_dmg_pending_event", 1000,
             "ywc_v03_dmg_inline_served_1"),
            ("KOR", lambda: (lambda w,e: (w,None,"ywc_kor.1010"))(*kor.KorFairDeliveryContract()._reserve_school_event()), "ywc_v03_kor_inline_reservation_epoch", "ywc_v03_kor_inline_candidate_epoch_11",
             "ywc_v03_kor_inline_c11_school_pending_event_present", "ywc_v03_kor_inline_c11_school_pending_event_value", "ywc_kor_school_pending_event", 1010,
             "ywc_v03_kor_inline_served_2"),
            ("NQG", lambda: (lambda w,j,e,c: (w,None,e))(*nqg._reserve_first_source_popup()), "ywc_v03_nqg_inline_reservation_epoch", "ywc_v03_nqg_inline_candidate_epoch_4",
             "ywc_v03_nqg_inline_c4_winter_pending_present", "ywc_v03_nqg_inline_c4_winter_pending_value", "ywc_nqg_winter_pending", 1000,
             "ywc_v03_nqg_inline_served_1"),
        )
        faults = ("global_missing", "global_zero", "global_negative", "global_mismatch",
                  "candidate_missing", "candidate_zero", "candidate_negative", "candidate_mismatch",
                  "snapshot_missing", "snapshot_mismatch", "queue_missing", "queue_mismatch",
                  "phase_lost", "already_served", "reservation_candidate_mismatch")
        for country, factory, ge, ce, sp, sv, queue, expected, served in recipes:
            for fault in faults:
                with self.subTest(country=country, fault=fault):
                    world, _, event_id = factory()
                    state = world.countries[country]
                    event = _authored_event(country, event_id) if country in {"OIR", "DMG"} else world.event_defs[event_id]
                    self.assertTrue(world.conditions(field(event, "trigger"), country),
                                    f"{country}: fault must start from a legal source-dispatched popup")
                    if fault == "global_missing": state.pop(ge, None)
                    elif fault == "global_zero": state[ge] = 0
                    elif fault == "global_negative": state[ge] = -1
                    elif fault == "global_mismatch": state[ge] += 1
                    elif fault == "candidate_missing": state.pop(ce, None)
                    elif fault == "candidate_zero": state[ce] = 0
                    elif fault == "candidate_negative": state[ce] = -1
                    elif fault == "candidate_mismatch": state[ce] += 1
                    elif fault == "snapshot_missing": state.pop(sp, None)
                    elif fault == "snapshot_mismatch": state[sv] += 1
                    elif fault == "queue_missing": state.pop(queue, None)
                    elif fault == "queue_mismatch": state[queue] += 1
                    elif fault == "phase_lost":
                        phase_keys = [k for k in state if "live_" in k and "phase" not in k]
                        # Source fixtures identify phase witness by its catalog entry.
                        if country == "OIR": phase_keys = ["ywc_v03_sched_live_pasture_entry"]
                        elif country == "DMG": phase_keys = ["ywc_v03_dmg_live_public_qualification"]
                        elif country == "KOR": phase_keys = ["ywc_v03_kor_inline_live_school_funding"]
                        else: phase_keys = ["ywc_v03_nqg_inline_live_winter_court_1"]
                        state.pop(phase_keys[0], None)
                    elif fault == "already_served": state[served] = state.get("ywc_v03_major_event_round", 1)
                    elif fault == "reservation_candidate_mismatch":
                        reservation = {"OIR":"ywc_v03_country_oir_reservation_candidate", "DMG":"ywc_v03_dmg_inline_reservation", "KOR":"ywc_v03_kor_inline_reservation", "NQG":"ywc_v03_nqg_inline_reservation"}[country]
                        state[reservation] += 1
                    before = copy.deepcopy(state)
                    trigger_after_fault = world.conditions(field(event, "trigger"), country)
                    world.execute(field(event, "immediate"), country)
                    self.assertEqual(state, before,
                                     f"{country}: guarded immediate changed state for {fault}; trigger_after_fault={trigger_after_fault}")

    def test_nqg_real_expiry_cleans_reservation_when_epoch_is_invalid(self):
        """The real prepare boundary clears expired state before source redispatch."""
        for fault in ("missing_global", "missing_candidate", "mismatched_global"):
            with self.subTest(country="NQG", fault=fault):
                world, journal_id, event_id, candidate = nqg._reserve_first_source_popup()
                state = world.countries["NQG"]
                reservation = "ywc_v03_nqg_inline_reservation"
                global_epoch = "ywc_v03_nqg_inline_reservation_epoch"
                candidate_epoch = f"ywc_v03_nqg_inline_candidate_epoch_{int(state[reservation])}"
                original_reservation = state[reservation]
                original_epoch = state.get(global_epoch)
                if fault == "missing_global":
                    state.pop(global_epoch, None)
                elif fault == "missing_candidate":
                    state.pop(candidate_epoch, None)
                else:
                    state[global_epoch] += 1
                world.events.clear()  # discard stale UI dispatch only
                world.advance_days(30)
                world.elapsed_months += 1
                boundary_failures = []

                # Observe the authored cleanup helper exactly at its return,
                # before the source pulse can create a replacement reservation.
                world.run("ywc_v03_nqg_inline_prepare", "NQG")
                if reservation in state:
                    boundary_failures.append("expired reservation survived real prepare return")
                if "ywc_v03_nqg_inline_timer" in state:
                    boundary_failures.append("expired timer survived real prepare return")

                # The real monthly source pulse now gets to reserve and dispatch
                # a fresh popup. A candidate ID may be reused; epoch loss must
                # not be mistaken for a monotonically larger old value.
                pulse = field(field(world.journal_defs[journal_id], "on_monthly_pulse"), "effect")
                world.execute(pulse, "NQG")
                if len(world.events) != 1:
                    boundary_failures.append(
                        f"actual source pulse dispatched {len(world.events)} replacement popups, expected 1")
                else:
                    self.assertEqual(world.events[0][0], "NQG")
                    replacement_id = world.events[0][1]
                    self.assertIn(reservation, state,
                                  f"NQG/{fault}: replacement dispatch has no current reservation")
                    self.assertIn("ywc_v03_nqg_inline_timer", state,
                                  f"NQG/{fault}: replacement reservation has no live timer")
                    self.assertGreater(state.get(global_epoch, 0), 0,
                                       f"NQG/{fault}: replacement has no positive global epoch")
                    replacement = nqg._candidate_for_event(world, replacement_id)
                    cid = replacement["id"]
                    self.assertEqual(state[reservation], cid)
                    self.assertEqual(state.get(f"ywc_v03_nqg_inline_candidate_epoch_{cid}"),
                                     state[global_epoch],
                                     f"NQG/{fault}: replacement candidate epoch is not bound")
                    queue = replacement["candidate"]["queue"]
                    queue_value = state.get(queue)
                    self.assertIsNotNone(queue_value,
                                         f"NQG/{fault}: source queue disappeared before native delivery")
                    snapshot = f"ywc_v03_nqg_inline_c{cid}_{queue.removeprefix('ywc_nqg_')}"
                    self.assertEqual(state.get(snapshot + "_present"), 1)
                    self.assertEqual(state.get(snapshot + "_value"), queue_value,
                                     f"NQG/{fault}: replacement snapshot is not bound to source queue")
                    self.assertTrue(world.conditions(field(world.event_defs[replacement_id], "trigger"), "NQG"),
                                    f"NQG/{fault}: replacement native event trigger is false")

                    nqg._deliver_reserved(world, replacement_id)
                    self.assertNotIn(reservation, state,
                                     f"NQG/{fault}: native ACK left replacement reservation behind")
                    self.assertNotIn("ywc_v03_nqg_inline_timer", state,
                                     f"NQG/{fault}: native ACK left replacement timer behind")
                    self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1,
                                     f"NQG/{fault}: native ACK did not set cooldown")
                    for proof in (f"ywc_v03_nqg_inline_callback_{cid}",
                                  f"ywc_v03_nqg_inline_callback_candidate_{cid}",
                                  f"ywc_v03_nqg_inline_callback_epoch_{cid}",
                                  f"ywc_v03_nqg_inline_callback_queue_{cid}"):
                        self.assertNotIn(proof, state,
                                         f"NQG/{fault}: native ACK left proof {proof}")
                # Preserve the lost value only as context, never as a success
                # condition when missing_global removed the old counter.
                self.assertIsNotNone(original_reservation)
                if fault != "missing_global":
                    self.assertIsNotNone(original_epoch)
                if boundary_failures:
                    self.fail(f"NQG/{fault} at real prepare return / source retry: " +
                              "; ".join(boundary_failures))

    def test_scheduler_rejects_new_internal_aliases_in_every_source_role(self):
        """Synthetic catalogue metadata cannot claim scheduler-owned names."""
        reserved = (
            "ywc_v03_scheduler_provenance_epoch",
            "ywc_v03_scheduler_proof_1",
            "ywc_v03_scheduler_proof_candidate_1",
            "ywc_v03_scheduler_proof_epoch_1",
            "ywc_v03_scheduler_proof_queue_1",
            "ywc_v03_scheduler_candidate_epoch_1",
            "ywc_v03_scheduler_snapshot_1_present",
            "ywc_v03_scheduler_snapshot_1_value",
        )
        roles = ("queue.variable", "owner_started", "live_phases[0].live_witness",
                 "candidate.receipt_variable", "candidate.acknowledgement")

        for name in reserved:
            for role in roles:
                with self.subTest(reserved_name=name, source_role=role):
                    catalog = aggregate_scheduler.fixture_catalog()
                    adapter = catalog["arcs"][0]["delivery_adapter"]
                    candidate = adapter["queues"][0]["candidates"][0]
                    if role == "queue.variable":
                        adapter["queues"][0]["variable"] = name
                    elif role == "owner_started":
                        adapter["owner_started"] = name
                    elif role == "live_phases[0].live_witness":
                        adapter["live_phases"][0]["live_witness"] = name
                    elif role == "candidate.receipt_variable":
                        candidate["receipt_variable"] = name
                        candidate["receipt_value"] = 0
                    else:
                        candidate["acknowledgement"] = [
                            {"op": "set", "variable": name, "value": 1}
                        ]
                    with self.assertRaises(ValueError):
                        validate_catalogue_adapters(catalog)

    def test_scheduler_new_alias_matrix_positive_controls_remain_valid(self):
        ordinary = aggregate_scheduler.fixture_catalog()
        validate_catalogue_adapters(ordinary)

        zero_receipt = aggregate_scheduler.fixture_catalog()
        candidate = zero_receipt["arcs"][0]["delivery_adapter"]["queues"][0]["candidates"][0]
        candidate["receipt_variable"] = "alpha_receipt"
        candidate["receipt_value"] = 0
        validate_catalogue_adapters(zero_receipt)
