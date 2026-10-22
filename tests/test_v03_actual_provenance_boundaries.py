"""Actual-source edge boundaries for zero-valued notice queues.

The controlled zero is introduced only after a native DMG helper has created
its queue, or as the explicit NQG fixture input. It is not a claim about game
state generation.
"""
import sys
import copy
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests import test_v03_dmg_fair_delivery as dmg
from tests import test_v03_nqg_fair_delivery as nqg
from tests import test_v03_kor_fair_delivery as kor
from tests import test_v03_oir_foundation as oir
from tests.shu_kor_strict_review_runtime import field
from tests.clausewitz_harness import PulseWorld, parse


def _strip_old_lifecycle(state):
    for key in ("ywc_v03_initialized", "ywc_v03_release_version",
                "ywc_v03_active_arc_count", "ywc_v03_visible_task_count"):
        state.pop(key, None)


class _DmgInterposeAtNativeHelperReturn(dmg.DmgInlineWorld):
    """Set the source queue to zero between its native writer and sender."""
    def __init__(self):
        super().__init__()
        self.arm_zero = False
        self.observed = []

    def execute(self, nodes, tag):
        helper = "ywc_dmg_foundation_update_titles_blocked_clock"
        index = next((i for i, (key, _, value) in enumerate(nodes)
                      if self.arm_zero and key == helper and value == "yes"), None)
        if index is None:
            return PulseWorld.execute(self, nodes, tag)
        PulseWorld.execute(self, nodes[:index + 1], tag)
        state = self.countries[tag]
        self.observed.append(("ywc_dmg_titles_emergency_notice" in state,
                              state.get("ywc_dmg_titles_emergency_notice")))
        if self.observed[-1] != (True, 1):
            raise AssertionError(("native helper did not create queue=1", self.observed[-1]))
        state["ywc_dmg_titles_emergency_notice"] = 0
        return PulseWorld.execute(self, nodes[index + 1:], tag)


class _DmgSourceWorld(dmg.DmgInlineWorld):
    """Retain DMG source effects/conditions but use native helper dispatch."""
    def execute(self, nodes, tag):
        return PulseWorld.execute(self, nodes, tag)


class ActualSourceProvenanceBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dmg.DmgActualFairDelivery.setUpClass()

    def _dmg_setup(self, world):
        state = world.countries["DMG"]
        _strip_old_lifecycle(state)
        world.run("ywc_v03_initialize_country", "DMG")
        arc = next(a for a in dmg.DmgActualFairDelivery.ARCS
                   if a["slug"] == "v03_dmg_two_land_titles")
        dmg._admit_real_je(world, arc)
        return arc

    def _actual_dmg_receive(self, world, arc, event_id, expected_candidate):
        state = world.countries["DMG"]
        self.assertTrue(world.conditions(dmg._nodes_field(
            dmg._generated_event(event_id), "trigger"), "DMG"))
        rid = int(state["ywc_v03_dmg_inline_reservation"])
        self.assertEqual(rid, expected_candidate)
        # This runs the complete authored immediate, including its real ACK.
        dmg._receive_actual_event_and_wait(world, arc, event_id, run_wait=False)
        # The selected candidate is a source class; served is indexed by arc.
        self.assertEqual(state.get("ywc_v03_dmg_inline_served_2"),
                         state.get("ywc_v03_dmg_inline_round"))
        self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1)
        self.assertNotIn("ywc_v03_dmg_inline_reservation", state)

    def test_dmg_real_helper_then_controlled_zero_dispatch_and_ack(self):
        world = _DmgInterposeAtNativeHelperReturn()
        arc = self._dmg_setup(world)
        state = world.countries["DMG"]
        # fixture-owned fact causes the actual source clock helper to produce
        # its normal emergency queue before the pulse is interposed.
        state["fixture_owned_state"] = 0
        world.advance_months(1)
        world.arm_zero = True
        dmg._pulse_real_je(world, arc)
        world.arm_zero = False
        self.assertEqual(world.observed, [(True, 1)])
        self.assertTrue(world.events)
        _, event_id = world.events[-1]
        row = dmg.DmgActualFairDelivery.CANDIDATES[
            int(state["ywc_v03_dmg_inline_reservation"])]
        self.assertEqual((event_id, row["queue"]["queue"],
                          state.get("ywc_dmg_titles_emergency_notice")),
                         ("ywc_dmg.1015", "ywc_dmg_titles_emergency_notice", 0))
        self._actual_dmg_receive(world, arc, event_id, 15)
        self.assertNotIn("ywc_dmg_titles_emergency_notice", state)

    def test_dmg_absent_queue_uses_ordinary_source_candidate_and_ack(self):
        world = _DmgSourceWorld()
        arc = self._dmg_setup(world)
        world.advance_months(1)
        dmg._pulse_real_je(world, arc)
        self.assertTrue(world.events)
        _, event_id = world.events[-1]
        state = world.countries["DMG"]
        row = dmg.DmgActualFairDelivery.CANDIDATES[
            int(state["ywc_v03_dmg_inline_reservation"])]
        self.assertEqual((event_id, int(state["ywc_v03_dmg_inline_reservation"]), row["queue"]["queue"]),
                         ("ywc_dmg.1010", 20, "ywc_dmg_titles_pending_event"))
        self.assertNotIn("ywc_dmg_titles_emergency_notice", state)
        self._actual_dmg_receive(world, arc, event_id, 20)

    def test_dmg_named_helper_fixture_matches_legacy_source_positive(self):
        worlds = []
        for world in (_DmgSourceWorld(), dmg.DmgInlineWorld()):
            arc = self._dmg_setup(world)
            world.advance_months(1)
            dmg._pulse_real_je(world, arc)
            event_id = world.events[-1][1]
            cid = int(world.countries["DMG"]["ywc_v03_dmg_inline_reservation"])
            self.assertEqual(event_id, "ywc_dmg.1010")
            worlds.append((world, arc, event_id, cid))
        self.assertEqual([(e, c) for _, _, e, c in worlds],
                         [("ywc_dmg.1010", 20), ("ywc_dmg.1010", 20)])
        for world, arc, event_id, cid in worlds:
            self.assertTrue(world.conditions(dmg._nodes_field(
                dmg._generated_event(event_id), "trigger"), "DMG"))
            dmg._receive_actual_event_and_wait(world, arc, event_id, run_wait=False)
        compared = ("ywc_v03_dmg_inline_served_2", "ywc_v03_major_event_cooldown",
                    "ywc_dmg_v03_titles_last_event", "ywc_v03_dmg_inline_reservation")
        self.assertEqual([{k: w.countries["DMG"].get(k) for k in compared} for w, *_ in worlds][0],
                         [{k: w.countries["DMG"].get(k) for k in compared} for w, *_ in worlds][1])

    def test_nqg_zero_notice_actual_pulse_ack_and_intent_rollback(self):
        world, journal, event_id, row = nqg._reserve_first_source_popup(
            extra={"ywc_nqg_winter_notice12_pending": 0})
        state = world.countries["NQG"]
        cid = row["id"]
        self.assertEqual((event_id, cid, row["candidate"]["kind"],
                          state.get("ywc_nqg_winter_notice12_pending")),
                         ("ywc_nqg.1009", 2, "notice12", 0))
        # ACK observer is the real helper invocation reached by whole immediate.
        cursor = len(world.ack_boundaries)
        nqg._deliver_reserved(world, event_id)
        boundary = next((snapshot for name, snapshot in world.ack_boundaries[cursor:]
                         if name == f"ywc_v03_nqg_inline_ack_{cid}"), None)
        self.assertIsNotNone(boundary, "real NQG ACK helper was not observed")
        for key, value in ((f"ywc_v03_nqg_inline_callback_{cid}", 1),
                           (f"ywc_v03_nqg_inline_callback_candidate_{cid}", cid),
                           (f"ywc_v03_nqg_inline_callback_epoch_{cid}",
                            state.get("ywc_v03_nqg_inline_reservation_epoch"))):
            self.assertEqual(boundary.get(key), value, (key, boundary))
        self.assertNotIn("ywc_nqg_winter_notice12_pending", state)
        self.assertEqual(boundary.get("ywc_nqg_winter_blocked_12_delivered"), 1)
        self.assertEqual(boundary.get("ywc_nqg_winter_notice12_open"), 1)
        self.assertNotIn("ywc_nqg_winter_notice12_intent", boundary)

    def test_nqg_absent_notice12_selects_ordinary_candidate_and_ack(self):
        world, _, event_id, row = nqg._reserve_first_source_popup()
        state = world.countries["NQG"]
        self.assertEqual((event_id, row["id"], row["candidate"]["kind"]),
                         ("ywc_nqg.1000", 4, "normal_queued_event"))
        self.assertNotIn("ywc_nqg_winter_notice12_pending", state)
        cursor = len(world.ack_boundaries)
        nqg._deliver_reserved(world, event_id)
        self.assertTrue(any(name == "ywc_v03_nqg_inline_ack_4"
                            for name, _ in world.ack_boundaries[cursor:]))
        self.assertEqual(state.get("ywc_v03_nqg_inline_served_1"),
                         state.get("ywc_v03_nqg_inline_round"))
        self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1)

    def _make_dmg_case(self):
        world = _DmgSourceWorld(); arc = self._dmg_setup(world)
        world.advance_months(1); dmg._pulse_real_je(world, arc)
        eid = world.events[-1][1]
        cid = int(world.countries["DMG"]["ywc_v03_dmg_inline_reservation"])
        immediate = dmg._nodes_field(dmg._generated_event(eid), "immediate")
        trigger = dmg._nodes_field(dmg._generated_event(eid), "trigger")
        return world, "DMG", cid, f"ywc_v03_dmg_inline_ack_{cid}", trigger, immediate

    def _make_kor_case(self):
        world, _ = kor.KorFairDeliveryContract()._reserve_school_event()
        cid = int(world.countries["KOR"]["ywc_v03_kor_inline_reservation"])
        immediate = field(world.event_defs["ywc_kor.1010"], "immediate")
        trigger = field(world.event_defs["ywc_kor.1010"], "trigger")
        return world, "KOR", cid, f"ywc_v03_kor_inline_ack_{cid}", trigger, immediate

    def _make_nqg_case(self):
        world, _, eid, row = nqg._reserve_first_source_popup()
        cid = int(row["id"])
        immediate = field(world.event_defs[eid], "immediate")
        trigger = field(world.event_defs[eid], "trigger")
        return world, "NQG", cid, f"ywc_v03_nqg_inline_ack_{cid}", trigger, immediate

    def _make_oir_case(self):
        import json
        world = oir.world(); _strip_old_lifecycle(world.countries["OIR"])
        world.run("ywc_v03_initialize_country", "OIR")
        arc = json.loads(oir.CAT.read_text(encoding="utf-8"))["arcs"][0]
        oir.start(world, arc); oir.pulse_current(world, arc)
        cid = int(world.countries["OIR"]["ywc_v03_country_oir_reservation_candidate"])
        eid = arc["events"][0]["id"]
        name = "ywc_v03_scheduler_ack_v03_oir_pasture_boundaries_event_1000"
        source = parse((oir.MOD / "events/ywc_v03_country_oir_events.txt").read_text(encoding="utf-8-sig"))
        event = next(body for key, _, body in source if key == eid)
        immediate = field(event, "immediate")
        trigger = field(event, "trigger")
        return world, "OIR", cid, name, trigger, immediate

    def test_four_countries_reject_each_damaged_inline_proof_at_actual_ack(self):
        """Mutate inline witnesses at actual ACK dispatch after validating the positive callback."""
        builders = {
            "DMG": lambda: self._make_dmg_case(),
            "KOR": lambda: self._make_kor_case(),
            "NQG": lambda: self._make_nqg_case(),
            "OIR": lambda: self._make_oir_case(),
        }
        proof_prefix = {"DMG": "ywc_v03_dmg_inline_callback", "KOR": "ywc_v03_kor_inline_callback",
                        "NQG": "ywc_v03_nqg_inline_callback", "OIR": "ywc_v03_scheduler_proof"}
        epoch_names = {"DMG": ("ywc_v03_dmg_inline_reservation_epoch", "ywc_v03_dmg_inline_candidate_epoch_{}"),
                       "KOR": ("ywc_v03_kor_inline_reservation_epoch", "ywc_v03_kor_inline_candidate_epoch_{}"),
                       "NQG": ("ywc_v03_nqg_inline_reservation_epoch", "ywc_v03_nqg_inline_candidate_epoch_{}"),
                       "OIR": ("ywc_v03_scheduler_provenance_epoch", "ywc_v03_scheduler_candidate_epoch_{}")}
        for country, builder in builders.items():
            pfx = proof_prefix[country]
            global_epoch, candidate_epoch_fmt = epoch_names[country]
            # Every proof role is tested missing and corrupt; both epoch
            # bindings are tested missing, zero and mismatched at the ACK.
            for proof_index, (kind, value) in enumerate([
                    ("proof", None), ("proof", 0), ("candidate", None), ("candidate", -1),
                    ("epoch", None), ("epoch", -1), ("queue", None), ("queue", -1),
                    ("global", None), ("global", 0), ("global", "mismatch"),
                    ("candidate_epoch", None), ("candidate_epoch", 0), ("candidate_epoch", "mismatch")]):
                world, tag, cid, callname, trigger, immediate = builder()
                proof_key = (f"{pfx}_{cid}" if kind == "proof" else
                             f"{pfx}_candidate_{cid}" if kind == "candidate" else
                             f"{pfx}_epoch_{cid}" if kind == "epoch" else
                             f"{pfx}_queue_{cid}" if kind == "queue" else
                             global_epoch if kind == "global" else candidate_epoch_fmt.format(cid))
                captured = []
                original_run = world.run
                def interposed(name, current_tag=tag, *, _key=proof_key, _kind=kind,
                               _value=value, _callname=callname, _original=original_run,
                               _country=country, _cid=cid, _pfx=pfx, _global=global_epoch,
                               _candidate_epoch=candidate_epoch_fmt.format(cid)):
                    if name == _callname:
                        state = world.countries[current_tag]
                        # Prove the unmodified complete inline witness at the
                        # actual helper entry before applying this case's fault.
                        proof_fields = [f"{_pfx}_{_cid}", f"{_pfx}_candidate_{_cid}",
                                        f"{_pfx}_epoch_{_cid}", f"{_pfx}_queue_{_cid}"]
                        self.assertTrue(all(key in state for key in proof_fields), (name, proof_fields, state))
                        self.assertEqual(state[proof_fields[0]], 1)
                        self.assertEqual(state[proof_fields[1]], _cid)
                        self.assertEqual(state[proof_fields[2]], state[_global])
                        self.assertGreater(state[_global], 0)
                        self.assertEqual(state[_candidate_epoch], state[_global])
                        captured_queue_values = [v for k, v in state.items()
                                                 if f"_c{_cid}_" in k and k.endswith("_value")]
                        if _country != "OIR":
                            self.assertIn(state[proof_fields[3]], captured_queue_values,
                                          (name, proof_fields, captured_queue_values, state))
                        else:
                            self.assertEqual(state[proof_fields[3]],
                                             state[f"ywc_v03_scheduler_snapshot_{_cid}_value"])
                        self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1, (name, state))
                        if _kind in ("global", "candidate_epoch"):
                            expected = state[_key]
                            if _value is None: state.pop(_key)
                            elif _value == "mismatch": state[_key] = expected + 1
                            else: state[_key] = _value
                        elif _value is None: state.pop(_key)
                        else: state[_key] = _value
                        before = copy.deepcopy(state)
                        try: return _original(name, current_tag)
                        finally: captured.append((before, copy.deepcopy(state)))
                    return _original(name, current_tag)
                world.run = interposed
                try:
                    self.assertTrue(world.conditions(trigger, tag), (country, "source event trigger rejected"))
                    world.execute(immediate, tag)
                finally:
                    world.run = original_run
                with self.subTest(country=country, proof=proof_key):
                    self.assertEqual(len(captured), 1,
                                     f"{country}: actual ACK helper invocation was not observed")
                    self.assertEqual(captured[0][1], captured[0][0],
                                     f"{country}: damaged proof let ACK mutate country state")


if __name__ == "__main__":
    unittest.main()
