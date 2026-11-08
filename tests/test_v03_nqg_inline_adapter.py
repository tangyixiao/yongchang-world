"""Static source and schema contracts for the staged NQG inline adapter."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest

from tools.build_v03_country import render_country
from tools.v03_inline_delivery_adapter import (
    _kor_source_binding,
    children,
    direct_values,
    parse_block,
    render_inline_country_adapters,
    validate_inline_catalog,
    validate_nqg_native_helper_source,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/content/v03/countries/nqg.json"
LATE_EVENTS = {"ywc_nqg.1009", "ywc_nqg.1015", "ywc_nqg.1027"}
EXPECTED_CLASSES = {"normal_queued_event", "notice12", "notice36", "remedy_final"}


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def monthly_sender_nodes(script: str):
    top = parse_block(script)
    monthly = direct_values(top, "on_monthly_pulse")
    effect = direct_values(children(monthly[0]), "effect")
    return [node for node in children(effect[0]) if node.key in {"if", "else_if"} and any(n.key == "trigger_event" for n in children(node))]


def has_reserve_call(node) -> bool:
    if node.key.startswith("ywc_v03_nqg_inline_reserve_"):
        return True
    return isinstance(node.value, tuple) and any(has_reserve_call(child) for child in node.value)


def ast_shape(node):
    value = tuple(ast_shape(child) for child in node.value) if isinstance(node.value, tuple) else node.value
    return node.key, node.op, value


def refresh_source_pins(arc: dict) -> None:
    adapter = arc["inline_delivery_adapter"]
    for journal in arc["journals"]:
        phase = next(row for row in adapter["live_phases"] if row["journal"] == journal["id"])
        phase["source_script_sha256"] = hashlib.sha256(journal["script"].encode("utf-8")).hexdigest()
        binding = _kor_source_binding(journal["id"], journal["script"])["branches"]
        proofs = [row for row in adapter["branches"] if row["journal"] == journal["id"]]
        assert len(binding) == len(proofs)
        for proof, source in zip(proofs, binding):
            for key in ("branch_index", "statement_ordinal", "chain_index", "branch_kind", "event", "chain_prior", "chain_sha256", "queue_exclusions"):
                proof[key] = source[key]
            proof["branch_sha256"] = source["sha256"]
            proof["limit_sha256"] = source["limit_sha256"]
            proof["candidates"] = source["candidates"]


def mutate_native_sender(catalog: dict, slug: str, event: str, kind: str, old: str, new: str) -> None:
    arc = next(row for row in catalog["arcs"] if row.get("slug") == slug)
    for journal in arc["journals"]:
        binding = _kor_source_binding(journal["id"], journal["script"])["branches"]
        target = next((row for row in binding if row["event"] == event and any(item["kind"] == kind for item in row["candidates"])), None)
        if target is None:
            continue
        source = journal["script"][target["start"]:target["end"]]
        if old not in source:
            continue
        journal["script"] = journal["script"][:target["start"]] + source.replace(old, new) + journal["script"][target["end"]:]
        refresh_source_pins(arc)
        return
    raise AssertionError(f"native sender not found: {slug}/{event}/{kind}/{old}")


class NqgInlineAdapterTests(unittest.TestCase):
    def test_source_inventory_is_exact_and_late_classes_are_all_present(self) -> None:
        catalog = load_catalog()
        validate_inline_catalog(catalog)
        arcs = [arc for arc in catalog["arcs"] if arc.get("era") == "foundation"]
        self.assertEqual(len(arcs), 3)
        self.assertEqual(sum(len(arc["inline_delivery_adapter"]["live_phases"]) for arc in arcs), 6)
        self.assertEqual(sum(len(arc["inline_delivery_adapter"]["branches"]) for arc in arcs), 70)
        records = [record for arc in arcs for record in arc["inline_delivery_adapter"]["branches"] if record["event"] in LATE_EVENTS]
        self.assertEqual(len(records), 24)
        by_phase: dict[str, set[str]] = {}
        for record in records:
            by_phase.setdefault(record["journal"], set()).update(candidate["kind"] for candidate in record["candidates"])
        self.assertEqual(len(by_phase), 6)
        self.assertTrue(all(classes == EXPECTED_CLASSES for classes in by_phase.values()))

    def test_boolean_branch_ordinal_is_rejected(self) -> None:
        catalog = load_catalog()
        bad = copy.deepcopy(catalog)
        bad["arcs"][0]["inline_delivery_adapter"]["branches"][0]["branch_index"] = True
        with self.assertRaisesRegex(ValueError, "branch_index must be an integer"):
            validate_inline_catalog(bad)

    def test_source_script_hash_drift_is_rejected(self) -> None:
        catalog = load_catalog()
        bad = copy.deepcopy(catalog)
        bad["arcs"][0]["journals"][0]["script"] += " "
        with self.assertRaisesRegex(ValueError, "source script drift"):
            validate_inline_catalog(bad)

    def test_rehashed_foreign_queue_and_wrong_intent_sender_mutants_are_rejected(self) -> None:
        foreign_queue = load_catalog()
        mutate_native_sender(foreign_queue, "v03_nqg_winter_court", "ywc_nqg.1009", "notice12",
                             "ywc_nqg_winter_notice12_pending", "ywc_nqg_port_notice12_pending")
        with self.assertRaisesRegex(ValueError, "candidate queue is not owned"):
            validate_inline_catalog(foreign_queue)

        wrong_intent = load_catalog()
        mutate_native_sender(wrong_intent, "v03_nqg_winter_court", "ywc_nqg.1009", "notice12",
                             "ywc_nqg_winter_notice12_intent", "ywc_nqg_winter_notice36_intent")
        with self.assertRaisesRegex(ValueError, "must set its own class intent"):
            validate_inline_catalog(wrong_intent)

    def test_native_helper_receipt_and_event_arc_mutants_are_rejected(self) -> None:
        catalog = load_catalog()
        effects_path = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_nqg_effects.txt"
        effects_source = effects_path.read_text(encoding="utf-8-sig")
        helper_start = effects_source.index("ywc_nqg_winter_mark_notice_delivery = {")
        helper_end = effects_source.index("\nywc_nqg_hunting_mark_notice_delivery =", helper_start)
        winter_helper = effects_source[helper_start:helper_end]
        bad_helper = effects_source[:helper_start] + winter_helper.replace(
            "ywc_nqg_winter_blocked_12_delivered", "ywc_nqg_hunting_blocked_12_delivered", 1
        ) + effects_source[helper_end:]
        with self.assertRaisesRegex(ValueError, "intent/receipt/open mapping drift"):
            validate_nqg_native_helper_source(catalog, bad_helper)

        bad_event = copy.deepcopy(catalog)
        winter = next(arc for arc in bad_event["arcs"] if arc.get("slug") == "v03_nqg_winter_court")
        settlement = next(event for event in winter["events"] if event.get("id") == "ywc_nqg.1009")
        settlement["immediate"] = settlement["immediate"].replace(
            "ywc_nqg_winter_mark_notice_delivery", "ywc_nqg_port_mark_notice_delivery"
        )
        with self.assertRaisesRegex(ValueError, "own direct notice helper"):
            validate_nqg_native_helper_source(bad_event, effects_source)

        nested_foreign = copy.deepcopy(catalog)
        winter = next(arc for arc in nested_foreign["arcs"] if arc.get("slug") == "v03_nqg_winter_court")
        settlement = next(event for event in winter["events"] if event.get("id") == "ywc_nqg.1009")
        settlement["immediate"] = settlement["immediate"][:-1] + " if = { limit = { always = yes } ywc_nqg_port_mark_notice_delivery = yes } }"
        with self.assertRaisesRegex(ValueError, "own direct notice helper"):
            validate_nqg_native_helper_source(nested_foreign, effects_source)

    def test_native_nonqueue_dispatch_effects_keep_order_at_all_70_sites(self) -> None:
        catalog = load_catalog()
        adapter = render_inline_country_adapters(catalog)
        checked = 0
        for arc in (arc for arc in catalog["arcs"] if arc.get("era") == "foundation"):
            metadata = arc["inline_delivery_adapter"]
            for journal in arc["journals"]:
                original = monthly_sender_nodes(journal["script"])
                generated = monthly_sender_nodes(adapter["journal_scripts"][journal["id"]])
                self.assertEqual(len(generated), len(original), journal["id"])
                proofs = [row for row in metadata["branches"] if row["journal"] == journal["id"]]
                for old, new, proof in zip(original, generated, proofs):
                    self.assertEqual(old.key, new.key)
                    old_effects = [node for node in children(old) if node.key != "limit"]
                    queue_removals = {candidate["queue"] for candidate in proof["candidates"]}
                    old_effects = [node for node in old_effects if not (node.key == "remove_variable" and node.value in queue_removals)]
                    new_effects = [node for node in children(new) if node.key != "limit"]
                    new_effects = [node for node in new_effects if not (node.key == "if" and has_reserve_call(node))]
                    self.assertEqual([ast_shape(n) for n in new_effects], [ast_shape(n) for n in old_effects], f"{journal['id']} branch {proof['branch_index']}")
                    checked += 1
        self.assertEqual(checked, 70)

    def test_pre_and_post_send_intent_conditions_preserve_native_if_else_if_rules(self) -> None:
        catalog = load_catalog()
        adapter = render_inline_country_adapters(catalog)
        by_kind: dict[str, tuple[dict, dict, str]] = {}
        indexed = []
        for arc in (arc for arc in catalog["arcs"] if arc.get("era") == "foundation"):
            for proof in arc["inline_delivery_adapter"]["branches"]:
                for candidate in proof["candidates"]:
                    indexed.append((arc, proof, candidate))
                    if proof["event"] in LATE_EVENTS:
                        by_kind.setdefault(candidate["kind"], (proof, candidate, arc["slug"]))
        for kind in EXPECTED_CLASSES:
            self.assertIn(kind, by_kind)
        # The current-state candidate predicates retain same-class preexisting
        # intent for notices, while later classes cannot consume an earlier 12m intent.
        trigger_rows = adapter["triggers"].splitlines()
        def row_for(kind: str) -> str:
            proof, candidate, slug = by_kind[kind]
            ordinal = next(i for i, (_arc, row, item) in enumerate(indexed, start=1)
                           if row is proof and item is candidate)
            return next(line for line in trigger_rows if line.startswith(f"ywc_v03_nqg_inline_candidate_{ordinal} ="))
        notice12 = row_for("notice12")
        notice36 = row_for("notice36")
        normal = row_for("normal_queued_event")
        remedy = row_for("remedy_final")
        self.assertNotIn("NOT = { has_variable = ywc_nqg_winter_notice12_intent }", notice12)
        self.assertNotIn("NOT = { has_variable = ywc_nqg_winter_notice36_intent }", notice12)
        self.assertIn("NOT = { has_variable = ywc_nqg_winter_notice12_intent }", notice36)
        self.assertNotIn("NOT = { has_variable = ywc_nqg_winter_notice36_intent }", notice36)
        for row in (normal, remedy):
            self.assertIn("NOT = { has_variable = ywc_nqg_winter_notice12_intent }", row)
            self.assertIn("NOT = { has_variable = ywc_nqg_winter_notice36_intent }", row)
        self.assertIn("ywc_v03_nqg_inline_reservation_epoch", adapter["effects"])
        # Event callbacks run after the native late-event immediate and require
        # the class helper to have consumed the selected intent and written receipt.
        self.assertIn("NOT = { has_variable = ywc_nqg_winter_notice12_intent }", adapter["effects"])
        self.assertIn("var:ywc_nqg_winter_blocked_12_delivered = 1", adapter["effects"])
        self.assertIn("var:ywc_nqg_winter_notice12_open = 1", adapter["effects"])
        self.assertIn("NOT = { has_variable = ywc_nqg_winter_notice36_intent }", adapter["effects"])
        # Ordinary event 1000 only runs mark-major; its callback keeps both
        # notice intent snapshots intact while still acknowledging the queue.
        rows = adapter["effects"].splitlines()
        def callback_id(event_id: str) -> int:
            index = 0
            for arc in (arc for arc in catalog["arcs"] if arc.get("era") == "foundation"):
                for proof in arc["inline_delivery_adapter"]["branches"]:
                    for candidate in proof["candidates"]:
                        index += 1
                        if (arc["slug"] == "v03_nqg_winter_court" and proof["event"] == event_id
                                and candidate["kind"] == "normal_queued_event"):
                            return index
            raise AssertionError(f"normal candidate missing for {event_id}")
        ordinary_id = callback_id("ywc_nqg.1000")
        callback_ordinary = next(row for row in rows if row.startswith(f"ywc_v03_nqg_inline_callback_{ordinary_id} ="))
        self.assertIn(f"ywc_v03_nqg_inline_c{ordinary_id}_winter_notice12_intent_present", callback_ordinary)
        self.assertIn(f"ywc_v03_nqg_inline_c{ordinary_id}_winter_notice36_intent_value", callback_ordinary)
        def direct_intent_absence(callback: str, intent: str) -> bool:
            effect = parse_block("{ " + callback + " }")[0]
            guard_if = direct_values(children(effect), "if")[0]
            guard = direct_values(children(guard_if), "limit")[0]
            for node in children(guard):
                if node.key != "NOT" or not isinstance(node.value, tuple):
                    continue
                terms = children(node)
                if len(terms) == 1 and terms[0].key == "has_variable" and terms[0].op == "=" and terms[0].value == intent:
                    return True
            return False
        # Ordinary event 1000 only runs mark-major: both intents are compared
        # to snapshots, but neither is a bare class exclusion in its callback.
        self.assertFalse(direct_intent_absence(callback_ordinary, "ywc_nqg_winter_notice12_intent"))
        self.assertFalse(direct_intent_absence(callback_ordinary, "ywc_nqg_winter_notice36_intent"))
        # Late event 1009 runs mark_notice_delivery, so its normal candidate
        # must reject both still-live notice intents after the native helper.
        callback_late_id = callback_id("ywc_nqg.1009")
        callback_late = next(row for row in rows if row.startswith(f"ywc_v03_nqg_inline_callback_{callback_late_id} ="))
        self.assertTrue(direct_intent_absence(callback_late, "ywc_nqg_winter_notice12_intent"))
        self.assertTrue(direct_intent_absence(callback_late, "ywc_nqg_winter_notice36_intent"))

    def test_dispatch_source_guards_are_candidate_local_across_arcs(self) -> None:
        adapter = render_inline_country_adapters(load_catalog())
        rows = adapter["triggers"].splitlines()
        winter = next(row for row in rows if row.startswith("ywc_v03_nqg_inline_dispatch_4 ="))
        port = next(row for row in rows if row.startswith("ywc_v03_nqg_inline_dispatch_59 ="))
        self.assertIn("var:ywc_nqg_winter_pending = 1000", winter)
        self.assertNotIn("var:ywc_nqg_port_pending = 1027", winter)
        self.assertIn("var:ywc_nqg_port_pending = 1027", port)
        self.assertNotIn("var:ywc_nqg_winter_pending = 1000", port)

    def test_bounded_render_owns_only_nqg_delivery_paths_and_hooks_after_native_immediate(self) -> None:
        outputs = render_country(ROOT, "country_nqg")
        self.assertEqual(len(outputs), 6)
        effects_path = Path("common/scripted_effects/ywc_v03_delivery_nqg_effects.txt")
        triggers_path = Path("common/scripted_triggers/ywc_v03_delivery_nqg_triggers.txt")
        self.assertIn(effects_path, outputs)
        self.assertIn(triggers_path, outputs)
        event_file = outputs[Path("events/ywc_v03_country_nqg_events.txt")]
        self.assertIn("ywc_v03_nqg_inline_callback_", outputs[effects_path])
        event1009 = event_file[event_file.index("ywc_nqg.1009 = {"):]
        self.assertLess(event1009.index("ywc_nqg_winter_mark_notice_delivery = yes"), event1009.index("ywc_v03_nqg_inline_callback_"))
        for class_name in EXPECTED_CLASSES:
            self.assertIn(f'"kind": "{class_name}"', json.dumps([b["candidates"] for a in load_catalog()["arcs"] if a.get("era") == "foundation" for b in a["inline_delivery_adapter"]["branches"]], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
