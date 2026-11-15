"""Real OIR source-to-scheduler projection contract.

This checks queue/value/event identity and JE call reachability against authored
source and generated files. It does not claim that the scheduler reproduces the
native dispatcher's full behavior, nor does it establish engine/gameplay acceptance.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.build_v03_content import _render_journal_file
from tools.v03_delivery_scheduler import render_country_adapters
from tools.v03_inline_delivery_adapter import Node, parse_block


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/content/v03/countries/oir.json"
NATIVE = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_oir_effects.txt"
EFFECTS = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_delivery_oir_effects.txt"
JOURNALS = ROOT / "yongchang_world/common/journal_entries/ywc_v03_country_oir_journal.txt"
ALLOWLIST = ROOT / "data/content/reachability_allowlist.json"
ANCHORS = {
    "ywc_oir_dispatch_pasture",
    "ywc_oir_dispatch_supply",
    "ywc_oir_dispatch_tolls",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _block(text: str) -> str:
    return "{\n" + text + "\n}"


def _children(node: Node, context: str) -> tuple[Node, ...]:
    _require(isinstance(node.value, tuple), f"{context}: expected block")
    return node.value


def _direct(nodes: tuple[Node, ...], key: str) -> list[Node]:
    return [node for node in nodes if node.key == key]


def _walk(nodes: tuple[Node, ...]):
    for node in nodes:
        yield node
        if isinstance(node.value, tuple):
            yield from _walk(node.value)


def _one(nodes: tuple[Node, ...], key: str, context: str) -> Node:
    found = _direct(nodes, key)
    _require(len(found) == 1, f"{context}: expected one {key}, got {len(found)}")
    return found[0]


def _definitions(source: str, context: str) -> dict[str, Node]:
    nodes = parse_block(source)
    names = [node.key for node in nodes]
    _require(len(names) == len(set(names)), f"{context}: duplicate top-level definition")
    return {node.key: node for node in nodes}


def _native_cases(anchor: Node, queue_names: set[str]) -> list[tuple[str, str, str, Node, Node]]:
    cases = []
    for branch in _children(anchor, anchor.key):
        _require(branch.key in {"if", "else_if"}, f"{anchor.key}: unexpected branch {branch.key}")
        body = _children(branch, anchor.key)
        limit = _one(body, "limit", anchor.key)
        event = _one(body, "trigger_event", anchor.key)
        _require(len([node for node in _walk(body) if node.key == "trigger_event"]) == 1,
                 f"{anchor.key}: expected exactly one branch event")
        predicates = [node for node in _children(limit, anchor.key)
                      if node.key in {"var:" + name for name in queue_names}]
        _require(len(predicates) == 1, f"{anchor.key}: expected one queue predicate")
        queue = predicates[0]
        _require(queue.op == "=" and isinstance(queue.value, str),
                 f"{anchor.key}: malformed queue predicate")
        event_id = _one(_children(event, anchor.key), "id", anchor.key)
        _require(event_id.op == "=" and isinstance(event_id.value, str),
                 f"{anchor.key}: malformed event ID")
        cases.append((queue.key.removeprefix("var:"), queue.value, event_id.value,
                      queue, event_id))
    return cases


def _caller_pairs(caller: Node) -> list[tuple[str, str]]:
    pairs = []
    for branch in _children(caller, caller.key):
        if branch.key != "if":
            continue
        body = _children(branch, caller.key)
        events = _direct(body, "trigger_event")
        if not events:
            continue
        _require(len(events) == 1, f"{caller.key}: duplicate event in branch")
        limit = _one(body, "limit", caller.key)
        guards = _children(limit, caller.key)
        _require(len(guards) == 1 and guards[0].op == "=" and guards[0].value == "yes",
                 f"{caller.key}: malformed dispatch guard")
        eid = _one(_children(events[0], caller.key), "id", caller.key)
        _require(eid.op == "=" and isinstance(eid.value, str),
                 f"{caller.key}: malformed event ID")
        pairs.append((guards[0].key, eid.value))
    _require(len([n for n in _walk(_children(caller, caller.key)) if n.key == "trigger_event"])
             == len(pairs), f"{caller.key}: nested or unaccounted event")
    return pairs


def _assert_projection(catalog: dict, native_block: str, generated_journal_block: str,
                       generated_effect_block: str) -> dict:
    arcs = [arc for arc in catalog["arcs"] if arc.get("era") == "foundation"]
    _require(len(arcs) == 3, "OIR requires exactly three foundation arcs")
    anchors = [arc["delivery_adapter"]["source_dispatch_effect"] for arc in arcs]
    _require(len(set(anchors)) == 3 and set(anchors) == ANCHORS,
             "OIR source anchor set drifted")
    native = _definitions(native_block, "native OIR effects")
    _require({name for name in native if name.startswith("ywc_oir_dispatch_")} == ANCHORS,
             "native OIR anchor set drifted")
    _require(all(name in native for name in anchors), "native OIR anchor missing")
    generated_journals = _definitions(generated_journal_block, "generated OIR JEs")
    generated_effects = _definitions(generated_effect_block, "generated OIR effects")
    adapter = render_country_adapters(catalog)
    expected_pairs = []
    source_journals = []
    mappings = 0
    for arc in arcs:
        slug = arc["slug"]
        queues = arc["delivery_adapter"]["queues"]
        expected = [(queue["variable"], str(candidate["value"]), candidate["event_id"])
                    for queue in queues for candidate in queue["candidates"]]
        _require(len(expected) == len(set(expected)), f"{slug}: duplicate catalog mapping")
        native_cases = _native_cases(native[arc["delivery_adapter"]["source_dispatch_effect"]],
                                     {queue["variable"] for queue in queues})
        actual = [row[:3] for row in native_cases]
        _require(len(actual) == len(set(actual)), f"{slug}: duplicate native mapping")
        _require(len(actual) == len(expected) and sorted(actual) == sorted(expected),
                 f"{slug}: native queue/value/event projection differs from catalog")
        mappings += len(actual)
        expected_pairs.extend((f"ywc_v03_scheduler_dispatch_{slug}_{candidate['key']}",
                               candidate["event_id"])
                              for queue in queues for candidate in queue["candidates"])
        anchor = arc["delivery_adapter"]["source_dispatch_effect"]
        for journal in arc["journals"]:
            jid = journal["id"]
            source_journals.append(jid)
            source_calls = [node for node in _walk(parse_block(journal["script"]))
                            if node.key in ANCHORS]
            _require(len(source_calls) == 1 and source_calls[0].key == anchor
                     and source_calls[0].value == "yes", f"{jid}: source anchor binding differs")
    _require(mappings == 24 and len(expected_pairs) == 24,
             "OIR requires 24 queue/value/event mappings")
    _require(len(source_journals) == 6 and len(set(source_journals)) == 6,
             "OIR requires six distinct source JEs")
    _require(len(expected_pairs) == len(set(expected_pairs)), "duplicate guard/event pair")
    for jid in source_journals:
        _require(jid in generated_journals, f"{jid}: generated JE missing")
        caller = f"ywc_v03_scheduler_dispatch_from_{jid.removeprefix('ywc_je_v03_')}"
        _require(adapter["journal_calls"].get(jid) == caller,
                 f"{jid}: adapter caller identity differs")
        calls = [node for node in _walk(_children(generated_journals[jid], jid))
                 if node.key.startswith("ywc_v03_scheduler_dispatch_from_") or node.key in ANCHORS]
        _require(len(calls) == 1 and calls[0].key == caller and calls[0].value == "yes",
                 f"{jid}: generated caller binding differs")
        _require(caller in generated_effects, f"{jid}: generated caller missing")
        _require(_caller_pairs(generated_effects[caller]) == expected_pairs,
                 f"{jid}: ordered guard/event projection differs")
    return {"anchors": len(anchors), "mappings": mappings, "journals": len(source_journals),
            "guard_event_pairs": len(source_journals) * len(expected_pairs)}


class OirSourceProjectionContract(unittest.TestCase):
    def _actual(self):
        catalog = json.loads(CATALOG.read_text(encoding="utf-8-sig"))
        native = _block(NATIVE.read_text(encoding="utf-8-sig"))
        journal = _block(JOURNALS.read_text(encoding="utf-8-sig"))
        effects = _block(EFFECTS.read_text(encoding="utf-8-sig"))
        return catalog, native, journal, effects

    def test_actual_source_projection_and_physical_render_parity(self):
        catalog, native, journal, effects = self._actual()
        self.assertEqual(_assert_projection(catalog, native, journal, effects),
                         {"anchors": 3, "mappings": 24, "journals": 6, "guard_event_pairs": 144})
        adapter = render_country_adapters(catalog)
        self.assertEqual(JOURNALS.read_text(encoding="utf-8-sig"),
                         _render_journal_file(catalog, adapter))
        self.assertEqual(EFFECTS.read_text(encoding="utf-8-sig"),
                         "# Generated OIR scheduler scripted effects.\n\n" + adapter["effects"])

    def test_projection_rejects_57_independent_source_mutations(self):
        catalog, native, journal, effects = self._actual()
        _assert_projection(catalog, native, journal, effects)
        native_defs = _definitions(native, "native OIR effects")
        count = 0
        for arc in catalog["arcs"]:
            anchor = arc["delivery_adapter"]["source_dispatch_effect"]
            queue_names = {queue["variable"] for queue in arc["delivery_adapter"]["queues"]}
            for index, (_, value, eid, queue_node, event_node) in enumerate(
                    _native_cases(native_defs[anchor], queue_names)):
                for kind, node, replacement in (("queue", queue_node, str(int(value) + 100000)),
                                                ("event", event_node, eid + "9")):
                    with self.subTest(anchor=anchor, case=index, kind=kind):
                        changed = native[:node.value_start] + replacement + native[node.value_end:]
                        with self.assertRaisesRegex(AssertionError, "projection differs"):
                            _assert_projection(catalog, changed, journal, effects)
                    count += 1
            anchor_node = native_defs[anchor]
            renamed = (native[:anchor_node.start] + anchor + "_mutation"
                       + native[anchor_node.start + len(anchor):])
            with self.subTest(anchor=anchor, kind="renamed anchor"):
                with self.assertRaisesRegex(AssertionError, "anchor set drifted"):
                    _assert_projection(catalog, renamed, journal, effects)
            count += 1
        generated = _definitions(journal, "generated OIR JEs")
        for arc in catalog["arcs"]:
            for source_je in arc["journals"]:
                jid = source_je["id"]
                caller = f"ywc_v03_scheduler_dispatch_from_{jid.removeprefix('ywc_je_v03_')}"
                calls = [node for node in _walk(_children(generated[jid], jid)) if node.key == caller]
                self.assertEqual(len(calls), 1, jid)
                node = calls[0]
                changed = journal[:node.start] + caller + "_mutation" + journal[node.start + len(caller):]
                with self.subTest(journal=jid, kind="caller substitution"):
                    with self.assertRaisesRegex(AssertionError, "caller binding differs"):
                        _assert_projection(catalog, native, changed, effects)
                count += 1
        self.assertEqual(count, 57)

    def test_native_source_anchors_have_documented_intentional_retention(self):
        catalog, native, journal, effects = self._actual()
        _assert_projection(catalog, native, journal, effects)
        allowlist = json.loads(ALLOWLIST.read_text(encoding="utf-8-sig"))["unused_scripted_helpers"]
        for anchor in ANCHORS:
            with self.subTest(anchor=anchor):
                reason = allowlist.get(anchor, "")
                self.assertTrue(reason.strip(), f"{anchor}: missing intentional-retention reason")
                self.assertIn("tests/test_v03_oir_source_projection.py", reason)
                self.assertIn("source", reason.lower())
        self.assertFalse(any(f"ywc_v03_scheduler_turn_{arc['slug']}" in allowlist
                             for arc in catalog["arcs"] if arc.get("era") == "foundation"),
                         "OIR aggregate turn helper allowlisted")


if __name__ == "__main__":
    unittest.main()
