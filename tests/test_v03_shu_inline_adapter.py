from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import unittest

from tools.build_v03_content import _adapter_event_immediate
from tools.v03_inline_delivery_adapter import (
    _branch_node,
    _kor_source_binding,
    _shu_queue_candidates,
    children,
    direct_values,
    parse_block,
    render_inline_country_adapters,
    validate_inline_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/content/v03/countries/shu.json"


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def effects_by_name(text: str) -> dict[str, object]:
    return {node.key: node for node in parse_block("{\n" + text + "\n}")}


def trigger_names(text: str) -> set[str]:
    return {node.key for node in parse_block("{\n" + text + "\n}")}


def node_shape(node: object) -> tuple:
    value = tuple(node_shape(child) for child in node.value) if isinstance(node.value, tuple) else node.value
    return node.key, node.op, value


class ShuInlineAdapterTests(unittest.TestCase):
    def test_catalog_covers_all_native_sites_and_journal_phases(self) -> None:
        catalog = load_catalog()
        validate_inline_catalog(catalog)
        foundation = [arc for arc in catalog["arcs"] if arc["era"] == "foundation"]
        adapters = [arc["inline_delivery_adapter"] for arc in foundation]
        self.assertEqual(31, sum(len(item["branches"]) for item in adapters))
        self.assertEqual(6, sum(len(item["live_phases"]) for item in adapters))
        self.assertEqual(26, sum(len(arc["events"]) for arc in foundation))

    def test_foreign_queue_auxiliary_or_bad_ordinal_is_rejected(self) -> None:
        catalog = load_catalog()
        catalog["arcs"][0]["inline_delivery_adapter"]["branches"][0]["candidates"][0]["queue"] = "ywc_nqg_foreign_pending"
        with self.assertRaisesRegex(ValueError, "queue semantics|exact source chain/site"):
            validate_inline_catalog(catalog)

        catalog = load_catalog()
        catalog["arcs"][0]["inline_delivery_adapter"]["branches"][1]["source_ops"][0]["value"] = "ywc_shu_not_the_auxiliary_queue"
        with self.assertRaisesRegex(ValueError, "auxiliary/queue operations"):
            validate_inline_catalog(catalog)

        catalog = load_catalog()
        catalog["arcs"][0]["inline_delivery_adapter"]["branches"][0]["branch_index"] = True
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            validate_inline_catalog(catalog)

    def test_service_and_port_notice_presence_exclusions_survive_render(self) -> None:
        adapter = render_inline_country_adapters(load_catalog())
        text = adapter["triggers"]
        self.assertIn("NOT = { has_variable = ywc_shu_service_notice_pending_event }", text)
        self.assertIn("NOT = { has_variable = ywc_shu_port_notice_pending_event }", text)
        self.assertNotIn("ywc_shu_service_notice_pending_event = no", text)

    def test_expired_stale_epoch_cleanup_is_candidate_owned_and_preserves_new_aux(self) -> None:
        adapter = render_inline_country_adapters(load_catalog())
        prepare = effects_by_name(adapter["effects"])["ywc_v03_shu_inline_prepare"]
        source = adapter["effects"][prepare.start:prepare.end]
        self.assertIn("var:ywc_v03_shu_inline_reservation = 2 NOT = { has_variable = ywc_v03_shu_inline_timer }", source)
        self.assertIn("has_variable = ywc_v03_shu_inline_timer var:ywc_v03_shu_inline_reservation = 2 ywc_v03_shu_inline_candidate_2 = no", source)
        self.assertNotIn("var:ywc_v03_shu_inline_candidate_epoch_2 = var:ywc_v03_shu_inline_reservation_epoch", source)
        self.assertIn("has_variable = ywc_v03_shu_inline_aux_waiting_present_2 has_variable = ywc_v03_shu_inline_aux_waiting_value_2 NOT = { has_variable = ywc_shu_waiting_for_capacity }", source)
        self.assertIn("name = ywc_shu_waiting_for_capacity value = var:ywc_v03_shu_inline_aux_waiting_value_2", source)
        self.assertGreaterEqual(source.count("has_variable = ywc_v03_shu_inline_reservation NOT = { OR = { var:ywc_v03_shu_inline_reservation = 1"), 2)

    def test_epoch_and_callback_proof_fields_fail_closed_when_missing(self) -> None:
        adapter = render_inline_country_adapters(load_catalog())
        names = effects_by_name(adapter["effects"])
        triggers = effects_by_name(adapter["triggers"])
        for candidate in range(1, 32):
            prefix = f"ywc_v03_shu_inline_"
            epoch = f"{prefix}reservation_epoch"
            candidate_epoch = f"{prefix}candidate_epoch_{candidate}"
            dispatch = triggers[f"{prefix}dispatch_{candidate}"]
            dispatch_text = adapter["triggers"][dispatch.start:dispatch.end]
            self.assertIn(f"has_variable = {epoch}", dispatch_text)
            self.assertIn(f"has_variable = {candidate_epoch}", dispatch_text)
            self.assertIn(f"var:{epoch} > 0", dispatch_text)

            callback = names[f"{prefix}callback_{candidate}"]
            callback_text = adapter["effects"][callback.start:callback.end]
            for field in (epoch, candidate_epoch, f"{prefix}callback_{candidate}",
                          f"{prefix}callback_candidate_{candidate}",
                          f"{prefix}callback_epoch_{candidate}",
                          f"{prefix}callback_queue_{candidate}"):
                self.assertIn(f"has_variable = {field}", callback_text)
            self.assertIn(f"var:{epoch} > 0", callback_text)
            self.assertIn(f"var:{prefix}callback_{candidate} = 1", callback_text)

            ack = names[f"{prefix}ack_{candidate}"]
            ack_text = adapter["effects"][ack.start:ack.end]
            for field in (epoch, candidate_epoch, f"{prefix}callback_{candidate}",
                          f"{prefix}callback_candidate_{candidate}",
                          f"{prefix}callback_epoch_{candidate}",
                          f"{prefix}callback_queue_{candidate}"):
                self.assertIn(f"has_variable = {field}", ack_text)
            self.assertIn(f"var:{epoch} > 0", ack_text)
            self.assertIn(f"var:{prefix}callback_{candidate} = 1", ack_text)

        for event_proofs in adapter["inline_proofs"].values():
            for proof in event_proofs:
                self.assertIn(f"has_variable = {prefix}reservation_epoch", proof)
                self.assertIn(f"var:{prefix}reservation_epoch > 0", proof)
                self.assertRegex(proof, r"has_variable = ywc_v03_shu_inline_candidate_epoch_[0-9]+")

    def test_native_transaction_and_ack_are_bound_to_current_receipt(self) -> None:
        adapter = render_inline_country_adapters(load_catalog())
        names = effects_by_name(adapter["effects"])
        triggers = trigger_names(adapter["triggers"])
        for candidate in range(1, 32):
            self.assertIn(f"ywc_v03_shu_inline_candidate_{candidate}", triggers)
            self.assertIn(f"ywc_v03_shu_inline_turn_{candidate}", triggers)
            self.assertIn(f"ywc_v03_shu_inline_dispatch_{candidate}", triggers)
            self.assertIn(f"ywc_v03_shu_inline_callback_{candidate}", names)
            self.assertIn(f"ywc_v03_shu_inline_ack_{candidate}", names)
        for callback_name, callback in names.items():
            if not callback_name.startswith("ywc_v03_shu_inline_callback_"):
                continue
            source = adapter["effects"][callback.start:callback.end]
            self.assertTrue("ywc_v03_shu_event_dispatch" in source or "_last_event" in source)
            self.assertNotIn("ywc_v03_can_deliver_major", source)
            self.assertRegex(source, r"ywc_v03_shu_inline_candidate_epoch_[0-9]+ = var:ywc_v03_shu_inline_reservation_epoch")

        for arc in load_catalog()["arcs"]:
            for event in arc["events"]:
                if event["id"] not in adapter["guarded_immediate_events"]:
                    continue
                generated = parse_block(_adapter_event_immediate(event, adapter))
                wrapper = generated[0]
                body = [node for node in children(wrapper) if node.key != "limit"]
                callbacks = adapter["ack_hooks"][event["id"]]
                self.assertEqual(callbacks, [node.key for node in body[-len(callbacks):]])
                source_nodes = parse_block(event["immediate"])
                proofs = adapter["inline_proofs"][event["id"]]
                proof_nodes = body[-len(callbacks)-len(proofs):-len(callbacks)]
                self.assertEqual(len(proof_nodes), len(proofs))
                self.assertTrue(all(node.key == "if" for node in proof_nodes))
                self.assertEqual([node_shape(node) for node in source_nodes], [node_shape(node) for node in body[:-len(callbacks)-len(proofs)]])
                for callback in callbacks:
                    generated_callback = names[callback]
                    callback_text = adapter["effects"][generated_callback.start:generated_callback.end]
                    self.assertNotIn("set_variable = { name = ywc_v03_shu_inline_callback_", callback_text)

    def test_withheld_sender_gates_auxiliary_cleanup_and_claim(self) -> None:
        adapter = render_inline_country_adapters(load_catalog())
        catalog = load_catalog()
        journals = {journal["id"]: journal for arc in catalog["arcs"] for journal in arc["journals"]}
        for journal_id, event_id, retained_op, removed_queue in (
            ("ywc_je_v03_shu_register_pilot", "ywc_shu.1001", "ywc_shu_waiting_for_capacity", "ywc_shu_pending_event"),
            ("ywc_je_v03_shu_service_contract", "ywc_shu.1010", "ywc_v03_claim_arc_shu_v03_shu_service_compact", "ywc_shu_service_pending_event"),
            ("ywc_je_v03_shu_port_customs", "ywc_shu.1018", "ywc_v03_claim_arc_shu_v03_shu_port_treasury", "ywc_shu_port_pending_event"),
        ):
            script = adapter["journal_scripts"][journal_id]
            binding = _kor_source_binding(journal_id, script, candidate_parser=_shu_queue_candidates)
            branch = next(row for row in binding["branches"] if row["event"] == event_id)
            node = _branch_node(script, branch)[0]
            limit = direct_values(children(node), "limit")[0]
            limit_text = script[limit.start:limit.end]
            self.assertIn("ywc_v03_shu_inline_turn_", limit_text)
            direct_ops = children(node)
            self.assertTrue(any(op.key == "remove_variable" and op.value == retained_op for op in direct_ops) or any(op.key == retained_op for op in direct_ops))
            self.assertFalse(any(op.key == "remove_variable" and op.value == removed_queue for op in direct_ops))
            trigger = next(op for op in direct_ops if op.key == "trigger_event")
            self.assertGreater(trigger.start, next(op.start for op in direct_ops if op.key == retained_op or (op.key == "remove_variable" and op.value == retained_op)))

    def test_renderer_rejects_source_or_phase_drift_before_emitting(self) -> None:
        catalog = load_catalog()
        journal = catalog["arcs"][0]["journals"][0]
        journal["script"] += "\n"
        with self.assertRaisesRegex(ValueError, "frozen native source script changed"):
            render_inline_country_adapters(catalog)

        catalog = load_catalog()
        phase = catalog["arcs"][0]["inline_delivery_adapter"]["live_phases"][0]
        phase["live_witness"] = None
        with self.assertRaisesRegex(ValueError, "invalid or duplicate live witness"):
            render_inline_country_adapters(catalog)


if __name__ == "__main__":
    unittest.main()
