"""Extra accepted4 epoch recovery and renderer-boundary regressions."""
import copy
import json
import unittest

from tests import test_v03_actual_immediate_provenance as provenance
from tests import test_v03_dmg_fair_delivery as dmg
from tests import test_v03_kor_fair_delivery as kor
from tests import test_v03_nqg_fair_delivery as nqg
from tests import test_v03_oir_foundation as oir
from tests.shu_kor_strict_review_runtime import field
from tools.v03_delivery_scheduler import validate_catalogue_adapters


class ProvenanceRenderValidation(unittest.TestCase):
    def _cases(self):
        world, arc, event_id = provenance._oir_reserved()
        yield ("OIR", world, arc, event_id,
               "ywc_v03_scheduler_prepare_country_oir", "ywc_v03_scheduler_provenance_epoch",
               lambda w, a: oir.pulse_current(w, a),
               lambda w, a, e: oir.fire(w, a, int(e.split(".")[-1])))

        world, arc, event_id = provenance._dmg_reserved()
        yield ("DMG", world, arc, event_id, "ywc_v03_dmg_inline_prepare",
               "ywc_v03_dmg_inline_reservation_epoch", dmg._pulse_real_je,
               lambda w, a, e: dmg._receive_actual_event_and_wait(w, a, e))

        world, event = kor.KorFairDeliveryContract()._reserve_school_event()
        arc = None
        yield ("KOR", world, arc, "ywc_kor.1010", "ywc_v03_kor_inline_prepare",
               "ywc_v03_kor_inline_reservation_epoch",
               lambda w, a: w.execute(field(field(w.journal_defs["ywc_je_v03_kor_school_funding"], "on_monthly_pulse"), "effect"), "KOR"),
               lambda w, a, e: kor._receive_and_defer(w, e))

        world, journal_id, event_id, _candidate = nqg._reserve_first_source_popup()
        yield ("NQG", world, journal_id, event_id, "ywc_v03_nqg_inline_prepare",
               "ywc_v03_nqg_inline_reservation_epoch",
               lambda w, jid: w.execute(field(field(w.journal_defs[jid], "on_monthly_pulse"), "effect"), "NQG"),
               lambda w, _jid, e: nqg._deliver_reserved(w, e))

    def test_zero_and_negative_global_epoch_recover_after_real_expiry(self):
        for value in (0, -1):
            for country, world, source, event_id, prepare, epoch, pulse, deliver in self._cases():
                with self.subTest(country=country, invalid_epoch=value):
                    state = world.countries[country]
                    state[epoch] = value
                    world.events.clear()
                    world.advance_days(2)
                    world.advance_months(1)
                    if country in {"KOR", "NQG"}:
                        world.elapsed_months += 1
                    world.run(prepare, country)
                    reservation = ("ywc_v03_country_oir_reservation_candidate" if country == "OIR" else
                                   f"ywc_v03_{country.lower()}_inline_reservation")
                    timer = ("ywc_v03_country_oir_reservation_timer" if country == "OIR" else
                             f"ywc_v03_{country.lower()}_inline_timer")
                    self.assertNotIn(reservation, state)
                    self.assertNotIn(timer, state)
                    pulse(world, source)
                    self.assertEqual(len(world.events), 1,
                                     f"{country}: fresh native monthly pulse must queue exactly one popup")
                    self.assertEqual(world.events[0], (country, event_id),
                                     f"{country}: emitted popup must match the source reservation")
                    self.assertGreater(state[epoch], 0)
                    cid = int(state[reservation])
                    candidate_epoch = (f"ywc_v03_scheduler_candidate_epoch_{cid}" if country == "OIR" else
                                       f"ywc_v03_{country.lower()}_inline_candidate_epoch_{cid}")
                    self.assertEqual(state[candidate_epoch], state[epoch])
                    event = (provenance._authored_event(country, event_id)
                             if country in {"OIR", "DMG"} else world.event_defs[event_id])
                    self.assertTrue(world.conditions(field(event, "trigger"), country),
                                    f"{country}: replacement source popup trigger rejected its live reservation")
                    deliver(world, source, event_id)
                    self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1)
                    self.assertNotIn(reservation, state)

    def test_both_epochs_zero_or_negative_fail_before_native_body(self):
        recipes = (
            ("OIR", lambda: (lambda w, _a, e: (w, e))(*provenance._oir_reserved()), "ywc_v03_scheduler_provenance_epoch", "ywc_v03_scheduler_candidate_epoch_1"),
            ("DMG", lambda: (lambda w, _a, e: (w, e))(*provenance._dmg_reserved()), "ywc_v03_dmg_inline_reservation_epoch", "ywc_v03_dmg_inline_candidate_epoch_1"),
            ("KOR", lambda: (lambda w, e: (w, "ywc_kor.1010"))(*kor.KorFairDeliveryContract()._reserve_school_event()), "ywc_v03_kor_inline_reservation_epoch", "ywc_v03_kor_inline_candidate_epoch_11"),
            ("NQG", lambda: (lambda w, _j, e, _c: (w, e))(*nqg._reserve_first_source_popup()), "ywc_v03_nqg_inline_reservation_epoch", "ywc_v03_nqg_inline_candidate_epoch_4"),
        )
        for invalid in (0, -1):
            for country, factory, global_epoch, candidate_epoch in recipes:
                with self.subTest(country=country, both_epochs=invalid):
                    world, event_id = factory()
                    event = (provenance._authored_event(country, event_id)
                             if country in {"OIR", "DMG"} else world.event_defs[event_id])
                    state = world.countries[country]
                    self.assertTrue(world.conditions(field(event, "trigger"), country),
                                    f"{country}: source factory must start with a legal popup")
                    state[global_epoch] = state[candidate_epoch] = invalid
                    before = copy.deepcopy(state)
                    world.execute(field(event, "immediate"), country)
                    self.assertEqual(state, before)

    def test_scheduler_prescan_malformed_shapes_are_value_error_and_receipt_zero_is_valid(self):
        base = json.loads(provenance.oir.CAT.read_text(encoding="utf-8"))
        for target, value in (("adapter", None), ("adapter", []),
                              ("queues", None), ("queues", 1),
                              ("candidates", None), ("candidates", 1)):
            with self.subTest(target=target, value=value):
                catalog = copy.deepcopy(base)
                adapter = catalog["arcs"][0]["delivery_adapter"]
                if target == "adapter":
                    catalog["arcs"][0]["delivery_adapter"] = value
                elif target == "queues":
                    adapter["queues"] = value
                else:
                    adapter["queues"][0]["candidates"] = value
                with self.assertRaises(ValueError):
                    validate_catalogue_adapters(catalog)

        catalog = copy.deepcopy(base)
        candidate = catalog["arcs"][0]["delivery_adapter"]["queues"][0]["candidates"][0]
        candidate["receipt_variable"] = "ywc_oir_pasture_last_event"
        candidate["receipt_value"] = 0
        validate_catalogue_adapters(catalog)

    def test_new_scheduler_namespace_malformed_ack_metadata_is_value_error(self):
        catalog = json.loads(provenance.oir.CAT.read_text(encoding="utf-8"))
        candidate = catalog["arcs"][0]["delivery_adapter"]["queues"][0]["candidates"][0]
        candidate["acknowledgement"] = [{"op": "set", "variable": [], "value": 1}]
        with self.assertRaises(ValueError):
            validate_catalogue_adapters(catalog)
