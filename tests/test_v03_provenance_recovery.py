"""Permanent regressions for accepted4 cleanup and native-source recovery.

The fixtures and all lifecycle, dispatch, event, immediate, ACK, and pulse
logic come from the existing actual-source test modules.  The only injected
fault is removal of the callback proof flag at the actual ACK helper boundary.
"""
import copy
import unittest

from tests import test_v03_actual_immediate_provenance as provenance
from tests import test_v03_dmg_fair_delivery as dmg
from tests import test_v03_kor_fair_delivery as kor
from tests import test_v03_nqg_fair_delivery as nqg
from tests import test_v03_oir_foundation as oir
from tests.clausewitz_harness import PulseWorld
from tests.shu_kor_strict_review_runtime import field


class Accepted4CleanupAndRecovery(unittest.TestCase):
    """Exercise real authored helpers without inventing a provenance proof."""

    class DmgRunWorld(dmg.DmgInlineWorld):
        """Keep DMG's actual effects but route named effects through run()."""
        def execute(self, nodes, tag):
            return PulseWorld.execute(self, nodes, tag)

    @classmethod
    def _dmg_reserved(cls):
        dmg.DmgActualFairDelivery.setUpClass()
        world = cls.DmgRunWorld()
        provenance._strip_old_lifecycle(world.countries["DMG"])
        world.run("ywc_v03_initialize_country", "DMG")
        arc = dmg.DmgActualFairDelivery.ARCS[0]
        dmg._admit_real_je(world, arc)
        world.advance_months(1)
        dmg._pulse_real_je(world, arc)
        return world, arc, arc["events"][0]["id"]

    def test_unknown_reservations_remove_only_owned_state_and_keep_zero_queue(self):
        recipes = (
            ("OIR", provenance._oir_reserved, "ywc_v03_scheduler_prepare_country_oir",
             "ywc_v03_country_oir_reservation_candidate", "ywc_v03_country_oir_reservation_timer",
             "ywc_oir_pasture_pending_event"),
            ("DMG", Accepted4CleanupAndRecovery._dmg_reserved, "ywc_v03_dmg_inline_prepare",
             "ywc_v03_dmg_inline_reservation", "ywc_v03_dmg_inline_timer",
             "ywc_dmg_pending_event"),
            ("KOR", lambda: (lambda w, _e: (w, None, None))(
                *kor.KorFairDeliveryContract()._reserve_school_event()),
             "ywc_v03_kor_inline_prepare", "ywc_v03_kor_inline_reservation",
             "ywc_v03_kor_inline_timer", "ywc_kor_school_pending_event"),
            ("NQG", lambda: (lambda w, _j, _e, _c: (w, None, None))(
                *nqg._reserve_first_source_popup()),
             "ywc_v03_nqg_inline_prepare", "ywc_v03_nqg_inline_reservation",
             "ywc_v03_nqg_inline_timer", "ywc_nqg_winter_pending"),
        )
        for country, factory, helper, reservation, timer, queue in recipes:
            for unknown in (0, -1, 999):
                with self.subTest(country=country, reservation=unknown):
                    world, _, _ = factory()
                    state = world.countries[country]
                    state[queue] = 0
                    state[reservation] = unknown
                    before = copy.deepcopy(state)
                    world.run(helper, country)
                    native_before = {k: v for k, v in before.items() if not k.startswith("ywc_v03_")}
                    native_after = {k: v for k, v in state.items() if not k.startswith("ywc_v03_")}
                    self.assertEqual(native_after, native_before)
                    self.assertIn(queue, state)
                    self.assertEqual(state[queue], 0)
                    self.assertNotIn(reservation, state)
                    self.assertNotIn(timer, state)

    def test_nqg_unknown_reservation_preserves_native_intent_zero_and_seven(self):
        for intent in (0, 7):
            for unknown in (0, -1, 999):
                with self.subTest(intent=intent, reservation=unknown):
                    world, _, _, _ = nqg._reserve_first_source_popup(
                        extra={"ywc_nqg_winter_notice12_intent": intent})
                    state = world.countries["NQG"]
                    state["ywc_v03_nqg_inline_reservation"] = unknown
                    before = copy.deepcopy(state)
                    world.run("ywc_v03_nqg_inline_prepare", "NQG")
                    native_before = {k: v for k, v in before.items() if not k.startswith("ywc_v03_")}
                    native_after = {k: v for k, v in state.items() if not k.startswith("ywc_v03_")}
                    self.assertEqual(native_after, native_before)
                    self.assertNotIn("ywc_v03_nqg_inline_reservation", state)
                    self.assertNotIn("ywc_v03_nqg_inline_timer", state)
                    self.assertIn("ywc_nqg_winter_pending", state)
                    self.assertEqual(state["ywc_nqg_winter_pending"], 1000)
                    self.assertIn("ywc_nqg_winter_notice12_intent", state)
                    self.assertEqual(state["ywc_nqg_winter_notice12_intent"], intent)

    @staticmethod
    def _fault_ack(world, country, helper, proof_flag):
        """Delete one current proof precisely at actual ACK helper invocation."""
        boundaries = []
        original_run = world.run
        def run(name, tag=country):
            if name == helper and tag == country:
                state = world.countries[country]
                if state.get(proof_flag) != 1:
                    raise AssertionError(
                        f"{country}: expected current proof {proof_flag}=1 at actual ACK entry; "
                        f"found {state.get(proof_flag)!r}")
                state.pop(proof_flag, None)
                boundaries.append(copy.deepcopy(state))
            return original_run(name, tag)
        world.run = run
        return boundaries, lambda: setattr(world, "run", original_run)

    def _recover(self, country, world, recipe):
        """Real timer advancement and actual monthly source pulse; bounded 6m."""
        state = world.countries[country]
        world.events.clear()  # discard only the refused UI item
        for month in range(1, 4):
            if country in ("KOR", "NQG"):
                world.advance_months(1)
                world.elapsed_months += 1
            else:
                world.advance_days(30)
            if country == "OIR":
                oir.pulse_current(world, recipe)
            elif country == "DMG":
                dmg._pulse_real_je(world, recipe)
            elif country == "KOR":
                kor._pulse_active_kor_arcs(world)
            else:
                pulse = field(field(world.journal_defs[recipe], "on_monthly_pulse"), "effect")
                world.execute(pulse, "NQG")
            if month < 3:
                self.assertIn("ywc_v03_major_event_cooldown", state,
                              f"{country}: cooldown expired before 90 days (month {month})")
                self.assertEqual(world.events, [],
                                 f"{country}: source dispatched during the first {month * 30} days")
            else:
                self.assertNotIn("ywc_v03_major_event_cooldown", state,
                                 f"{country}: cooldown survived the real 90-day advance")
                self.assertGreater(len(world.events), 0,
                                   f"{country}: source pulse did not redispatch on day 90")
        if country == "OIR":
            arc = recipe
            actual_id = world.events[-1][1]
            recovered_candidate = int(state["ywc_v03_country_oir_reservation_candidate"])
            numeric_id = int(actual_id.rsplit(".", 1)[1])
            oir.fire(world, arc, numeric_id)
            proof_fields = (f"ywc_v03_scheduler_proof_{recovered_candidate}",
                            f"ywc_v03_scheduler_proof_candidate_{recovered_candidate}",
                            f"ywc_v03_scheduler_proof_epoch_{recovered_candidate}",
                            f"ywc_v03_scheduler_proof_queue_{recovered_candidate}")
            served = "ywc_v03_scheduler_served_v03_oir_pasture_boundaries"
            round_key = "ywc_v03_country_oir_delivery_round"
        elif country == "DMG":
            arc = recipe
            actual_id = world.events[-1][1]
            recovered_candidate = int(state["ywc_v03_dmg_inline_reservation"])
            dmg._receive_actual_event_and_wait(world, arc, actual_id)
            slot = next(i for i, row in enumerate(dmg.DmgActualFairDelivery.ARCS, 1)
                        if row["slug"] == arc["slug"])
            proof_fields = (f"ywc_v03_dmg_inline_callback_{recovered_candidate}",
                            f"ywc_v03_dmg_inline_callback_candidate_{recovered_candidate}",
                            f"ywc_v03_dmg_inline_callback_epoch_{recovered_candidate}",
                            f"ywc_v03_dmg_inline_callback_queue_{recovered_candidate}")
            served = f"ywc_v03_dmg_inline_served_{slot}"
            round_key = "ywc_v03_dmg_inline_round"
        elif country == "KOR":
            recovered_candidate = int(state["ywc_v03_kor_inline_reservation"])
            tag, actual_id = world.events[0]
            self.assertEqual(tag, "KOR")
            kor._receive_and_defer(world, actual_id)
            proof_fields = (f"ywc_v03_kor_inline_callback_{recovered_candidate}",
                            f"ywc_v03_kor_inline_callback_candidate_{recovered_candidate}",
                            f"ywc_v03_kor_inline_callback_epoch_{recovered_candidate}",
                            f"ywc_v03_kor_inline_callback_queue_{recovered_candidate}")
            served = "ywc_v03_kor_inline_served_2"
            round_key = "ywc_v03_kor_inline_round"
        else:
            journal_id = recipe
            actual_id = world.events[0][1]
            row = nqg._candidate_for_event(world, actual_id)
            cid = row["id"]
            nqg._deliver_reserved(world, actual_id)
            proof_fields = (f"ywc_v03_nqg_inline_callback_{cid}",
                            f"ywc_v03_nqg_inline_callback_candidate_{cid}",
                            f"ywc_v03_nqg_inline_callback_epoch_{cid}",
                            f"ywc_v03_nqg_inline_callback_queue_{cid}")
            arc_slot = next(index for index, arc in enumerate(
                [arc for arc in world.cat["arcs"] if arc.get("era") == "foundation"], 1)
                if arc["slug"] == row["arc"]["slug"])
            served = f"ywc_v03_nqg_inline_served_{arc_slot}"
            round_key = "ywc_v03_nqg_inline_round"
        self.assertNotIn("ywc_v03_dmg_inline_timer" if country == "DMG" else
                         "ywc_v03_kor_inline_timer" if country == "KOR" else
                         "ywc_v03_nqg_inline_timer" if country == "NQG" else
                         "ywc_v03_country_oir_reservation_timer", state)
        self.assertNotIn("ywc_v03_dmg_inline_reservation" if country == "DMG" else
                         "ywc_v03_kor_inline_reservation" if country == "KOR" else
                         "ywc_v03_nqg_inline_reservation" if country == "NQG" else
                         "ywc_v03_country_oir_reservation_candidate", state)
        self.assertEqual(state.get(served), state.get(round_key),
                         f"{country}: served arc must match current native delivery round")
        self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1)
        for name in proof_fields:
            self.assertNotIn(name, state)

    def test_real_ack_proofflag_loss_recovers_after_native_cooldown_for_all_four(self):
        # Independent fixtures ensure each refusal preserves its own native
        # cooldown and reservation while stale UI is discarded.
        factories = (
            ("OIR", provenance._oir_reserved, "ywc_v03_scheduler_ack_v03_oir_pasture_boundaries_event_1000",
             "ywc_v03_scheduler_proof_1", "ywc_v03_country_oir_reservation_candidate"),
            ("DMG", Accepted4CleanupAndRecovery._dmg_reserved, "ywc_v03_dmg_inline_ack_1",
             "ywc_v03_dmg_inline_callback_1", "ywc_v03_dmg_inline_reservation"),
            ("KOR", lambda: (lambda w, e: (w, None, "ywc_kor.1010"))(
                *kor.KorFairDeliveryContract()._reserve_school_event()),
             "ywc_v03_kor_inline_ack_15", "ywc_v03_kor_inline_callback_15",
             "ywc_v03_kor_inline_reservation"),
            ("NQG", lambda: (lambda w, j, e, c: (w, j, e))(
                *nqg._reserve_first_source_popup()),
             "ywc_v03_nqg_inline_ack_4", "ywc_v03_nqg_inline_callback_4",
             "ywc_v03_nqg_inline_reservation"),
        )
        for country, factory, helper, proof_flag, reservation in factories:
            with self.subTest(country=country):
                if country == "KOR":
                    world, _, event_id = factory()
                    arc = None
                else:
                    world, source, event_id = factory()
                    arc = source
                state = world.countries[country]
                boundaries, restore_ack = self._fault_ack(world, country, helper, proof_flag)
                if country == "OIR":
                    oir.fire(world, arc, 1000)
                elif country == "DMG":
                    generated = dmg._generated_event(event_id)
                    self.assertTrue(world.conditions(dmg._nodes_field(generated, "trigger"), "DMG"))
                    world.execute(dmg._nodes_field(generated, "immediate"), "DMG")
                elif country == "KOR":
                    tag, dispatched = world.events.pop(0)
                    self.assertEqual((tag, dispatched), ("KOR", event_id))
                    event = world.event_defs[event_id]
                    self.assertTrue(world.conditions(field(event, "trigger"), "KOR"))
                    world.execute(field(event, "immediate"), "KOR")
                else:
                    tag, dispatched = world.events.pop(0)
                    self.assertEqual((tag, dispatched), ("NQG", event_id))
                    event = world.event_defs[event_id]
                    self.assertTrue(world.conditions(field(event, "trigger"), "NQG"))
                    world.execute(field(event, "immediate"), "NQG")
                self.assertEqual(len(boundaries), 1, f"{country}: proof fault not injected at ACK")
                self.assertNotIn(proof_flag, boundaries[0])
                self.assertIn("ywc_v03_major_event_cooldown", state,
                              f"{country}: refused ACK must retain native cooldown")
                self.assertIn(reservation, state,
                              f"{country}: refused ACK must preserve current reservation")
                self.assertTrue(world.days_until_expiry[country].get(
                    "ywc_v03_major_event_cooldown", 0) >= 90,
                    f"{country}: actual immediate did not establish 90-day cooldown")
                restore_ack()
                # Recovery gets the actual source recipe. NQG's known reservation
                # expiry behavior is intentionally reported by its assertion.
                if country == "NQG":
                    recovery_recipe = source
                else:
                    recovery_recipe = arc
                self._recover(country, world, recovery_recipe)
