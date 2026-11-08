"""The first middle arc shares SHU's existing source-bound scheduler."""
import copy
import json
from pathlib import Path
import unittest

from tools.v03_inline_delivery_adapter import (
    _shu_expected_receipt,
    render_inline_country_adapters,
    validate_inline_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
SLUG = "v03_shu_provincial_contract"


def catalog():
    return json.loads((ROOT / "data/content/v03/countries/shu.json").read_text(encoding="utf-8"))


class ShuMiddleAdapterTests(unittest.TestCase):
    def test_middle_and_two_foundation_arcs_share_actual_source_turns_in_both_orders(self):
        from collections import Counter
        from shu_kor_strict_review_runtime import facts
        from shu_provincial_runtime import ProvincialWorld
        from test_v03_shu_actual_fairness import (
            LEGACY_RESULT, ROOTS, _install_real_shu_render, _render_real_shu,
            _native_admission, _pulse_actual_active_arc,
        )
        participants = list(ROOTS[1:]) + [
            (SLUG, "ywc_je_v03_shu_provincial_charter")]
        choices = {
            "ywc_shu.1100": "pilot_sichuan",
            "ywc_shu.1101": "keep_old_office",
            "ywc_shu.1102": "push_old_quota",
            "ywc_shu.1105": "confirm_old_quota",
            "ywc_shu.1106": "settle_on_time",
            "ywc_shu.1107": "close_compromise",
        }
        for order in (participants, list(reversed(participants))):
            with self.subTest(order=[row[0] for row in order]):
                world = ProvincialWorld("shu", load_inline=False)
                state = facts()
                state.pop("ywc_v03_initialized", None)
                state.pop("ywc_v03_release_version", None)
                state[LEGACY_RESULT] = 1
                world.countries[world.tag] = state
                _install_real_shu_render(world, _render_real_shu())
                world.run("ywc_v03_initialize_country", world.tag)
                for slug, journal in order:
                    _native_admission(world, slug, journal)
                self.assertEqual(state["ywc_v03_active_arc_count"], 3)
                deliveries = []
                for month in range(1, 61):
                    world.advance_months(1)
                    world.elapsed_months += 1
                    for slug, _ in order:
                        for row in _pulse_actual_active_arc(world, slug, month * 30, choices):
                            deliveries.append((slug, row["day"], row["event"]))
                first = deliveries[:9]
                self.assertEqual(len(first), 9)
                self.assertEqual(Counter(row[0] for row in first),
                                 Counter({slug: 3 for slug, _ in participants}))
                self.assertTrue(all(b[1] - a[1] >= 90
                                    for a, b in zip(deliveries, deliveries[1:])))
                proofs = [row for row in world.trace
                          if row.get("op") == "actual_candidate_ack_proof"
                          and row["arc"] == SLUG]
                self.assertEqual({row["event"] for row in proofs}, set(choices))
                self.assertTrue(all(32 <= row["candidate"] <= 39 for row in proofs))
                self.assertEqual(state["ywc_shu_prov_outcome"], 2)

    def test_new_receipts_are_explicit_and_do_not_change_early_receipts(self):
        self.assertEqual(_shu_expected_receipt("ywc_shu.1000"),
                         ("ywc_v03_shu_v03_shu_fiscal_register_last_event", 1))
        self.assertEqual(_shu_expected_receipt("ywc_shu.1025"),
                         ("ywc_v03_shu_event_dispatch", 1025))
        for event in range(1100, 1108):
            with self.subTest(event=event):
                try:
                    receipt = _shu_expected_receipt(f"ywc_shu.{event}")
                except ValueError as error:
                    self.fail(str(error))
                self.assertEqual(receipt, ("ywc_v03_shu_event_dispatch", event))
        for event in (1026, 1099, 1108, 1109, 1110):
            with self.subTest(unimplemented=event), self.assertRaises(ValueError):
                _shu_expected_receipt(f"ywc_shu.{event}")

    def test_fourth_arc_has_eight_bound_senders_in_the_same_coordinator(self):
        current = catalog()
        arcs = [arc for arc in current["arcs"] if arc["slug"] == SLUG]
        self.assertEqual(len(arcs), 1, "the approved middle arc is not registered")
        arc = arcs[0]
        self.assertEqual(arc["era"], "middle")
        self.assertEqual({event["id"] for event in arc["events"]},
                         {f"ywc_shu.{event}" for event in range(1100, 1108)})
        metadata = arc["inline_delivery_adapter"]
        self.assertEqual(metadata["schema"], "v03.foundation_inline_adapter.v3")
        self.assertEqual(len(metadata["live_phases"]), 2)
        self.assertEqual(len(metadata["branches"]), 8)
        validate_inline_catalog(current)
        adapter = render_inline_country_adapters(current)
        self.assertIn("ywc_v03_shu_inline_served_4", adapter["effects"])
        for candidate in range(32, 40):
            self.assertIn(f"ywc_v03_shu_inline_candidate_{candidate} =", adapter["triggers"])
        self.assertNotIn("ywc_v03_shu_prov_inline_reservation", adapter["effects"])

    def test_new_authored_source_still_rejects_rehashed_foreign_sender(self):
        current = catalog()
        arcs = [arc for arc in current["arcs"] if arc["slug"] == SLUG]
        self.assertEqual(len(arcs), 1, "the approved middle arc is not registered")
        forged = copy.deepcopy(current)
        arc = next(arc for arc in forged["arcs"] if arc["slug"] == SLUG)
        journal = arc["journals"][0]
        self.assertIn("ywc_shu_prov_pending_event", journal["script"])
        journal["script"] = journal["script"].replace("ywc_shu_prov_pending_event",
                                                    "ywc_shu_port_pending_event")
        # Rehashing mutable metadata cannot authorize a different source queue.
        import hashlib
        arc["inline_delivery_adapter"]["live_phases"][0]["source_script_sha256"] = (
            hashlib.sha256(journal["script"].encode("utf-8")).hexdigest())
        with self.assertRaisesRegex(ValueError, "frozen native source script changed"):
            validate_inline_catalog(forged)
