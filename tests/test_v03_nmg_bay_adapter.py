"""Bay source-bound sender and foreign-response isolation contract."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools import v03_inline_delivery_adapter as adapter
from test_v03_nmg_school_adapter import bind_sources


ROOT = Path(__file__).resolve().parents[1]
SLUG = "v03_nmg_bay_ports"
QUEUE = "ywc_nmg_bay_pending_event"
RECEIPT = "ywc_v03_nmg_v03_nmg_bay_ports_last_event"
JES = ("ywc_je_v03_nmg_bay_charter", "ywc_je_v03_nmg_bay_operations")


def synthetic_catalog():
    result = subprocess.run(["git", "show", "2595db93ba5a4f213f7c52210d311d5aa11a23cc:data/content/v03/countries/nmg.json"],
                            cwd=ROOT, check=True, capture_output=True)
    catalog = json.loads(result.stdout.decode("utf-8-sig"))
    arc = {"slug": SLUG, "era": "middle", "journals": [], "events": []}
    for jid, numbers in zip(JES, (range(1100, 1104), range(1104, 1108))):
        sends = []
        for number in numbers:
            sends.append(f"if = {{ limit = {{ var:{QUEUE} = {number} }} "
                         f"remove_variable = {QUEUE} trigger_event = {{ id = ywc_nmg.{number} }} }}")
            arc["events"].append({"id": f"ywc_nmg.{number}", "trigger": "{ always = yes }", "options": [],
                                  "immediate": "{ ywc_v03_mark_major_delivered = yes "
                                  f"set_variable = {{ name = {RECEIPT} value = {number - 1099} }} "
                                  "change_variable = { name = ywc_nmg_bay_popup_epoch add = 1 } "
                                  "save_scope_value_as = { name = ywc_nmg_bay_popup_epoch value = var:ywc_nmg_bay_popup_epoch } }"})
        arc["journals"].append({"id": jid, "script": "{ possible = { always = yes } immediate = {} "
                                "on_monthly_pulse = { effect = { " + " ".join(sends) + " } } }",
                                "goal": "{ var:synthetic_closed = 1 }",
                                "exit_conditions": "{ var:synthetic_withdrawn = 1 }"})
    arc["events"].append({"id": "ywc_nmg.1108", "trigger": "{ ywc_nmg_bay_reply_current = yes }",
                          "immediate": "{}", "options": [
                              {"key": "accept_advance", "trigger": "{ ywc_nmg_bay_reply_current = yes }",
                               "effect": "{ if = { limit = { ywc_nmg_bay_reply_current = yes } ywc_nmg_bay_accept_advance = yes } }"},
                              {"key": "refuse", "trigger": "{ ywc_nmg_bay_reply_current = yes }",
                               "effect": "{ if = { limit = { ywc_nmg_bay_reply_current = yes } ywc_nmg_bay_refuse = yes } }"}]})
    bind_sources(arc)
    # Witness names are distinct from the school phases and bound to these JEs.
    for i, phase in enumerate(arc["inline_delivery_adapter"]["live_phases"]):
        phase["live_witness"] = f"ywc_v03_nmg_inline_live_bay_{i + 1}"
    catalog["arcs"].append(arc)
    return catalog


class NmgBayAdapterContract(unittest.TestCase):
    def test_legacy_projection_rejects_unknown_arc_and_broken_bay_proofs(self):
        from nmg_foundation_projection import _validated_projection
        source = json.loads((ROOT / "data/content/v03/countries/nmg.json").read_text(encoding="utf-8-sig"))
        _validated_projection(json.dumps(source).encode())
        mutants = []
        unknown = copy.deepcopy(source)
        unknown["arcs"].append({"slug": "unregistered_middle", "era": "middle"})
        mutants.append(unknown)
        bad_receipt = copy.deepcopy(source)
        bad_receipt["arcs"][-1]["events"][0]["immediate"] = "{}"
        mutants.append(bad_receipt)
        bad_proof = copy.deepcopy(source)
        bad_proof["arcs"][-1]["inline_delivery_adapter"]["branches"][0]["event"] = "ywc_nmg.1101"
        mutants.append(bad_proof)
        for mutant in mutants:
            with self.subTest(mutant=mutants.index(mutant)), self.assertRaises((ValueError, AssertionError)):
                _validated_projection(json.dumps(mutant).encode())

    def test_shared_capacity_gate_retains_three_active_and_six_visible_limits(self):
        from clausewitz_harness import PulseWorld, parse
        path = "yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt"
        original = subprocess.run(["git", "show", "2595db93ba5a4f213f7c52210d311d5aa11a23cc:" + path],
                                  cwd=ROOT, check=True, capture_output=True).stdout.decode("utf-8-sig")
        current = (ROOT / path).read_text(encoding="utf-8-sig")
        self.assertEqual(current.replace("\r\n", "\n"), original.replace("\r\n", "\n"))
        gate = next(body for key, _, body in parse(current) if key == "ywc_v03_has_capacity")
        for active, visible, expected in ((2, 5, True), (3, 5, False), (2, 6, False), (3, 6, False)):
            with self.subTest(active=active, visible=visible):
                state = {"ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                         "ywc_v03_active_arc_count": active, "ywc_v03_visible_task_count": visible}
                self.assertEqual(PulseWorld("", {"NMG": state}).conditions(gate, "NMG"), expected)

    def test_binder_preserves_existing_catalog_prefix_and_refuses_rebinding(self):
        import nmg_bay_bind as binder
        catalog = synthetic_catalog()
        del catalog["arcs"][-1]["inline_delivery_adapter"]
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=repr(newline)):
                original = (json.dumps(catalog, ensure_ascii=False, indent=2) + "\n").replace("\n", newline)
                result = binder.bind_text(original)
                slug_at = original.index('"v03_nmg_bay_ports"')
                self.assertEqual(result[:slug_at], original[:slug_at])
                # The binder must perform exactly one insertion, with no old byte lost.
                prefix = 0
                while prefix < len(original) and original[prefix] == result[prefix]:
                    prefix += 1
                suffix = 0
                while suffix < len(original) - prefix and original[-1 - suffix] == result[-1 - suffix]:
                    suffix += 1
                self.assertEqual(prefix + suffix, len(original))
                self.assertEqual(len(json.loads(result)["arcs"][-1]["inline_delivery_adapter"]["branches"]), 8)
                with self.assertRaisesRegex(ValueError, "refuse overwrite"):
                    binder.bind_text(result)

    def test_binder_refuses_to_overwrite_a_concurrently_changed_catalog(self):
        import nmg_bay_bind as binder
        catalog = synthetic_catalog()
        del catalog["arcs"][-1]["inline_delivery_adapter"]
        original = (json.dumps(catalog, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nmg.json"
            path.write_bytes(original)
            bind = binder.bind_text
            def other_writer(text):
                result = bind(text)
                path.write_bytes(b"another writer's content")
                return result
            with mock.patch.object(binder, "PATH", path), mock.patch.object(binder, "bind_text", other_writer):
                with self.assertRaisesRegex(RuntimeError, "catalog changed"):
                    binder.main()
            self.assertEqual(path.read_bytes(), b"another writer's content")
            self.assertEqual([item.name for item in Path(directory).iterdir()], ["nmg.json"])

    def test_all_receipts_are_exact_ordinal_and_reject_altered_immediate(self):
        for number in range(1100, 1108):
            ordinal = number - 1099
            immediate = ("{ ywc_v03_mark_major_delivered = yes "
                         f"set_variable = {{ name = {RECEIPT} value = {ordinal} }} "
                         "change_variable = { name = ywc_nmg_bay_popup_epoch add = 1 } "
                         "save_scope_value_as = { name = ywc_nmg_bay_popup_epoch value = var:ywc_nmg_bay_popup_epoch } }")
            event = {"id": f"ywc_nmg.{number}", "immediate": immediate}
            self.assertEqual(adapter._nmg_native_receipt(event, "bay"), (RECEIPT, ordinal))
            for bad in (immediate.replace(RECEIPT, "ywc_nmg_school_last_event"),
                        immediate.replace(f"value = {ordinal}", f"value = {number}"),
                        immediate.replace("mark_major_delivered = yes", "mark_major_delivered = no"),
                        immediate.replace("add = 1", "add = 2"),
                        immediate.replace("value = var:ywc_nmg_bay_popup_epoch", "value = 1"),
                        immediate.replace("save_scope_value_as", "save_scope_as"),
                        immediate.replace("name = ywc_nmg_bay_popup_epoch", "name = other_epoch", 1),
                        immediate[:-1] + " add_treasury = 1 }"):
                with self.subTest(number=number, bad=bad), self.assertRaises(ValueError):
                    adapter._nmg_native_receipt({**event, "immediate": bad}, "bay")

    def test_preexisting_nmg_renderer_matches_original_baseline(self):
        ref = "2595db93ba5a4f213f7c52210d311d5aa11a23cc"
        def frozen(path):
            return subprocess.run(["git", "show", ref + ":" + path], cwd=ROOT,
                                  check=True, capture_output=True).stdout.decode("utf-8-sig")
        original = types.ModuleType("nmg_bay_baseline_adapter")
        sys.modules[original.__name__] = original
        try:
            exec(compile(frozen("tools/v03_inline_delivery_adapter.py"), original.__name__, "exec"), original.__dict__)
            catalog = json.loads(frozen("data/content/v03/countries/nmg.json"))
            self.assertEqual(adapter.render_inline_country_adapters(catalog),
                             original.render_inline_country_adapters(catalog))
            for country in ("dmg", "jhg", "kor", "lan", "mgl", "nqg", "shu", "tib"):
                with self.subTest(country=country):
                    other = json.loads(frozen(f"data/content/v03/countries/{country}.json"))
                    self.assertEqual(adapter.render_inline_country_adapters(other),
                                     original.render_inline_country_adapters(other))
        finally:
            sys.modules.pop(original.__name__, None)

    def test_private_queue_parser_requires_exact_registered_name(self):
        source = f"if = {{ limit = {{ var:{QUEUE} = 1100 }} trigger_event = {{ id = ywc_nmg.1100 }} }}"
        self.assertEqual(adapter._nmg_queue_candidates(source),
                         [{"queue": QUEUE, "kind": "normal", "mode": "exact", "value": 1100}])
        with self.assertRaises(ValueError):
            adapter._nmg_queue_candidates(source.replace(QUEUE, "ywc_nmg_other_pending_event"))

    def test_eight_local_senders_and_foreign_reply_are_distinct(self):
        catalog = synthetic_catalog()
        adapter.validate_inline_catalog(catalog)
        rendered = adapter.render_inline_country_adapters(catalog)
        self.assertEqual(len(rendered["journal_scripts"]), 10)
        self.assertIn("ywc_v03_nmg_inline_served_5", rendered["effects"])
        for number in range(45, 53):
            self.assertIn(f"ywc_v03_nmg_inline_candidate_{number} =", rendered["triggers"])
        self.assertNotIn("ywc_nmg.1108", rendered.get("event_hooks", {}))
        self.assertNotIn("ywc_nmg.1108", rendered.get("ack_hooks", {}))
        reordered = copy.deepcopy(catalog)
        reordered["arcs"].reverse()
        self.assertEqual(adapter.render_inline_country_adapters(reordered), rendered)

    def test_first_bay_ack_rejects_wrong_receipt_even_with_all_other_proofs(self):
        from clausewitz_harness import PulseWorld
        rendered = adapter.render_inline_country_adapters(synthetic_catalog())
        state = {"ywc_v03_nmg_inline_reservation": 45, "ywc_v03_nmg_inline_timer": 1,
                 "ywc_v03_nmg_inline_reservation_epoch": 7, "ywc_v03_nmg_inline_candidate_epoch_45": 7,
                 "ywc_v03_nmg_inline_c45_ywc_nmg_bay_pending_event_present": 1,
                 "ywc_v03_nmg_inline_c45_ywc_nmg_bay_pending_event_value": 1100,
                 "ywc_v03_nmg_inline_live_bay_1": 1, "ywc_v03_nmg_inline_round": 1,
                 "ywc_v03_nmg_inline_callback_45": 1, "ywc_v03_nmg_inline_callback_candidate_45": 45,
                 "ywc_v03_nmg_inline_callback_epoch_45": 7, "ywc_v03_nmg_inline_callback_queue_45": 1100,
                 "ywc_v03_nmg_inline_body_completed_45": 1, "ywc_v03_nmg_inline_body_completed_epoch_45": 7,
                 QUEUE: 1100, RECEIPT: 0}
        world = PulseWorld(rendered["effects"], {"NMG": state})
        world.journals = [("NMG", [("type", "=", JES[0])])]
        before = copy.deepcopy(state)
        world.run("ywc_v03_nmg_inline_ack_45", "NMG")
        self.assertEqual(state, before)
        state[RECEIPT] = 1
        world.run("ywc_v03_nmg_inline_ack_45", "NMG")
        self.assertNotIn(QUEUE, state)
        self.assertNotIn("ywc_v03_nmg_inline_reservation", state)

    def test_rehashed_foreign_and_local_sender_mutants_are_rejected(self):
        original = synthetic_catalog()
        for fault in ("wrong_receipt", "extra_foreign_major", "foreign_unchecked_effect", "foreign_sender", "partition", "hidden_direct_add", "school_queue", "land_queue"):
            catalog = copy.deepcopy(original)
            arc = catalog["arcs"][-1]
            if fault == "wrong_receipt":
                arc["events"][0]["immediate"] = arc["events"][0]["immediate"].replace("value = 1", "value = 1100")
            elif fault == "extra_foreign_major":
                arc["events"][-1]["immediate"] = "{ ywc_v03_mark_major_delivered = yes }"
            elif fault == "foreign_unchecked_effect":
                arc["events"][-1]["options"][0]["effect"] = "{ ywc_nmg_bay_accept_advance = yes }"
            elif fault == "foreign_sender":
                arc["journals"][1]["script"] = arc["journals"][1]["script"].replace("1107", "1108")
            elif fault == "hidden_direct_add":
                arc["journals"][0]["script"] = arc["journals"][0]["script"].replace(
                    "immediate = {}", "immediate = { add_journal_entry = { type = " + JES[1] + " } }")
            elif fault in ("school_queue", "land_queue"):
                other = "ywc_nmg_school_pending_event" if fault == "school_queue" else "ywc_nmg_land_pending"
                for journal in arc["journals"]:
                    journal["script"] = journal["script"].replace(QUEUE, other)
            else:
                arc["journals"][0]["script"] = arc["journals"][0]["script"].replace("1103", "1104")
                arc["journals"][1]["script"] = arc["journals"][1]["script"].replace("1104", "1103")
            bind_sources(arc)
            for i, phase in enumerate(arc["inline_delivery_adapter"]["live_phases"]):
                phase["live_witness"] = f"ywc_v03_nmg_inline_live_bay_{i + 1}"
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                adapter.validate_inline_catalog(catalog)


if __name__ == "__main__":
    unittest.main()
