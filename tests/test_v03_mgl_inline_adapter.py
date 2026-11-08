"""Permanent MGL inline adapter source contract (feature RED until registered)."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

from tests.clausewitz_harness import parse
from tools.v03_inline_delivery_adapter import (
    _kor_direct_adds, _kor_source_binding, children, direct_values, parse_block,
    render_inline_country_adapters, validate_inline_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/content/v03/countries/mgl.json"
EVENT_PATH = ROOT / "yongchang_world/events/ywc_v03_country_mgl_events.txt"
JOURNAL_PATH = ROOT / "yongchang_world/common/journal_entries/ywc_v03_country_mgl_journal.txt"
TRIGGER_PATH = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_mgl_triggers.txt"
EXPECTED_JES = {
    "ywc_je_v03_mgl_roads_register", "ywc_je_v03_mgl_roads_review",
    "ywc_je_v03_mgl_debt_register", "ywc_je_v03_mgl_debt_review",
    "ywc_je_v03_mgl_grain_register", "ywc_je_v03_mgl_grain_review",
}
EXPECTED_ARCS = {"v03_mgl_two_trade_roads", "v03_mgl_pastoral_debt",
                 "v03_mgl_princes_monasteries"}


def _catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _native_journals():
    return {k: b for k, _, b in parse(JOURNAL_PATH.read_text(encoding="utf-8-sig"))}


def _queue_kind(queue: str) -> str:
    if queue.endswith("_notice_event"):
        return "notice"
    if queue.endswith("_pending_event"):
        return "normal"
    raise ValueError(f"MGL sender queue has an unsupported name: {queue}")


def _mgl_candidates(branch_source: str):
    root = parse_block("{ " + branch_source + " }")
    if len(root) != 1 or root[0].key not in {"if", "else_if"}:
        raise ValueError("MGL candidate input must be one source sender branch")
    limits = direct_values(children(root[0]), "limit")
    events = direct_values(children(root[0]), "trigger_event")
    if len(limits) != 1 or len(events) != 1 or not isinstance(events[0].value, tuple):
        raise ValueError("MGL sender must bind one direct limit and one event")
    event_ids = direct_values(children(events[0]), "id")
    if len(event_ids) != 1 or not isinstance(event_ids[0].value, str):
        raise ValueError("MGL trigger_event must carry one literal id")
    found = []
    def walk(nodes, negative=False):
        for node in nodes:
            if node.key in {"OR", "XOR", "NOR"}:
                raise ValueError(f"unsupported MGL queue Boolean/container {node.key}")
            if node.key == "NOT":
                walk(children(node), True)
            elif isinstance(node.value, tuple):
                walk(node.value, negative)
            elif (not negative and node.key.startswith("var:ywc_mgl_")
                  and node.op == "=" and isinstance(node.value, str)
                  and node.value.isdigit()):
                queue = node.key.removeprefix("var:")
                kind = _queue_kind(queue)
                found.append({"queue": queue, "kind": kind, "mode": "exact",
                              "value": int(node.value)})
    walk(children(limits[0]))
    if len(found) != 1:
        raise ValueError(f"MGL sender must have one positive queue candidate, got {found!r}")
    return found


def _binding(journal_id, script):
    """Use the shared source binder, then retain MGL's authored chain context."""
    bound = _kor_source_binding(journal_id, script, candidate_parser=_mgl_candidates,
                                exclusion_parser=lambda _src: [])
    # MGL's preferred notice branch is followed by native fallback and normal
    # branches in the same source chain. The common binder records full sibling
    # predecessors and source hashes; this projection adds the concrete source
    # ordinal and queue-derived kind without inferring kind from event identity.
    root = parse_block(script)
    monthly = direct_values(root, "on_monthly_pulse")
    if len(monthly) != 1:
        raise ValueError(f"{journal_id}: expected one monthly pulse")
    effects = direct_values(children(monthly[0]), "effect")
    if len(effects) != 1:
        raise ValueError(f"{journal_id}: expected one pulse effect")
    nodes = children(effects[0])
    result = []
    for source in bound["branches"]:
        node = next((n for n in nodes if n.start == source["start"] and n.end == source["end"]), None)
        if node is None:
            raise ValueError(f"{journal_id}: source binder lost a sender AST")
        candidates = _mgl_candidates(script[node.start:node.end])
        result.append({**source, "statement_ordinal": nodes.index(node), "chain_index": 0,
                       "branch_kind": node.key, "candidates": candidates,
                       "queue_exclusions": []})
    return result


def _v2_catalog_from_formal_mgl_source():
    """Build complete candidate metadata from real MGL source, never R3 JSON."""
    result = copy.deepcopy(_catalog())
    for arc in result["arcs"]:
        phases, branches = [], []
        for journal in arc["journals"]:
            slug = re.sub(r"[^a-z0-9_]+", "_", journal["id"].removeprefix("ywc_je_v03_mgl_"))
            phases.append({"journal": journal["id"],
                "live_witness": f"ywc_v03_mgl_inline_live_{slug}",
                "source_script_sha256": hashlib.sha256(journal["script"].encode()).hexdigest(),
                "goal_sha256": hashlib.sha256(journal["goal"].encode()).hexdigest(),
                "exit_sha256": hashlib.sha256(journal["exit_conditions"].encode()).hexdigest()})
            for source in _binding(journal["id"], journal["script"]):
                branches.append({"journal": journal["id"], "branch_index": source["branch_index"],
                    "statement_ordinal": source["statement_ordinal"], "chain_index": source["chain_index"],
                    "branch_kind": source["branch_kind"], "event": source["event"],
                    "branch_sha256": source["sha256"], "limit_sha256": source["limit_sha256"],
                    "chain_prior": source["chain_prior"], "chain_sha256": source["chain_sha256"],
                    "candidates": source["candidates"], "queue_exclusions": source["queue_exclusions"]})
        arc["inline_delivery_adapter"] = {"schema": "v03.foundation_inline_adapter.v2",
            "live_phases": phases, "branches": branches, "direct_adds": _kor_direct_adds(arc)}
    return result


def _rebind_v2_catalog(candidate):
    """Recompute source hashes/bindings after an in-memory native mutation."""
    for arc in candidate["arcs"]:
        phases, branches = [], []
        for journal in arc["journals"]:
            slug = re.sub(r"[^a-z0-9_]+", "_", journal["id"].removeprefix("ywc_je_v03_mgl_"))
            phases.append({"journal": journal["id"],
                "live_witness": f"ywc_v03_mgl_inline_live_{slug}",
                "source_script_sha256": hashlib.sha256(journal["script"].encode()).hexdigest(),
                "goal_sha256": hashlib.sha256(journal["goal"].encode()).hexdigest(),
                "exit_sha256": hashlib.sha256(journal["exit_conditions"].encode()).hexdigest()})
            for source in _binding(journal["id"], journal["script"]):
                branches.append({"journal": journal["id"], "branch_index": source["branch_index"],
                    "statement_ordinal": source["statement_ordinal"], "chain_index": source["chain_index"],
                    "branch_kind": source["branch_kind"], "event": source["event"],
                    "branch_sha256": source["sha256"], "limit_sha256": source["limit_sha256"],
                    "chain_prior": source["chain_prior"], "chain_sha256": source["chain_sha256"],
                    "candidates": source["candidates"], "queue_exclusions": source["queue_exclusions"]})
        arc["inline_delivery_adapter"]["live_phases"] = phases
        arc["inline_delivery_adapter"]["branches"] = branches
        arc["inline_delivery_adapter"]["direct_adds"] = _kor_direct_adds(arc)
    return candidate


def _definitions_no_duplicates(source, label):
    result = {}
    for key, _, body in parse(source):
        if key in result:
            raise AssertionError(("duplicate_definition", label, key))
        result[key] = body
    return result


def _wrapped_definitions(source):
    """Parse a registry's full top-level definitions, detecting duplicate names."""
    wrapped = "{\n" + source + "\n}"
    nodes = parse_block(wrapped)
    result = {}
    for node in nodes:
        if node.key in result:
            raise AssertionError(("duplicate_definition", node.key))
        result[node.key] = node.value
    return result


def _ast_value(value):
    if isinstance(value, tuple):
        return tuple((node.key, node.op, _ast_value(node.value)) for node in value)
    return value


def _helper_mutants(source):
    """Return nine real helper mutants with only the intended AST changed."""
    original = {key: _ast_value(value) for key, value in _wrapped_definitions(source).items()}
    names = [f"ywc_mgl_{arc}_{helper}" for arc in ("roads", "debt", "grain")
             for helper in ("any_affordable_entry_offer", "selected_current_obligation",
                            "current_obligation_ready")]
    wrapped = "{\n" + source + "\n}"
    nodes = parse_block(wrapped)
    results = []
    for name in names:
        matches = [node for node in nodes if node.key == name]
        if len(matches) != 1:
            raise AssertionError(("helper_definition_count", name, len(matches)))
        node = matches[0]
        definition = wrapped[node.start:node.end]
        if name.endswith("selected_current_obligation"):
            arc = name.removeprefix("ywc_mgl_").removesuffix("_selected_current_obligation")
            pattern = r"(var:ywc_mgl_" + re.escape(arc) + r"_route\s*=\s*)1\b"
            mutated, count = re.subn(pattern, r"\g<1>9", definition, count=1)
        else:
            mutated, count = re.subn(r"(=\s*)yes\b", r"\1no", definition, count=1)
        if count != 1:
            raise AssertionError(("helper_mutant_source_site_missing", name, count))
        full = wrapped[:node.start] + mutated + wrapped[node.end:]
        mutant_defs = {n.key: _ast_value(n.value) for n in parse_block(full)}
        changed = {key for key in original if mutant_defs[key] != original[key]}
        if changed != {name}:
            raise AssertionError(("helper_mutant_ast_scope", name, changed))
        results.append((name, full[2:-2], original[name], mutant_defs[name]))
    return results


def _walk_rows(nodes):
    for key, op, value in nodes:
        yield key, op, value
        if isinstance(value, list):
            yield from _walk_rows(value)


def _scalar_pairs(nodes):
    """Yield only scalar key/value pairs from a nested Clausewitz tuple AST."""
    for key, _op, value in nodes:
        if isinstance(value, str):
            yield key, value
        elif isinstance(value, list):
            yield from _scalar_pairs(value)


def _set_variable_names(nodes):
    return [name for key, _op, value in _walk_rows(nodes) if key == "set_variable"
            and isinstance(value, list) for child_key, _child_op, name in value
            if child_key == "name" and isinstance(name, str)]


def _rows(nodes):
    return [(node.key, node.op, _rows(node.value) if isinstance(node.value, tuple)
             else node.value) for node in nodes]


def _formal_generated_projection(catalog):
    """Use public registration and the real builder for committed output ASTs."""
    from tools import build_v03_content
    enabled = ["inline_delivery_adapter" in arc for arc in catalog["arcs"]]
    adapter = None
    if any(enabled):
        if not all(enabled):
            raise AssertionError("partial MGL inline metadata")
        validate_inline_catalog(catalog)
        adapter = render_inline_country_adapters(catalog)
    journals = _definitions_no_duplicates(build_v03_content._render_journal_file(catalog, adapter), "expected JE")
    events = _definitions_no_duplicates(build_v03_content._render_event_file(catalog, ROOT, adapter), "expected event")
    events.pop("namespace", None)
    return adapter, journals, events


class MglInlineAdapterStaticContract(unittest.TestCase):
    def test_formal_catalogue_and_source_inventory_are_complete(self):
        cat = _catalog()
        self.assertEqual(cat["key"], "country_mgl")
        self.assertEqual({a["slug"] for a in cat["arcs"]}, EXPECTED_ARCS)
        native = _native_journals()
        adapter, expected_journals, _ = _formal_generated_projection(cat)
        self.assertEqual(native, expected_journals)
        counts, kinds, events = {}, {"normal": 0, "notice": 0}, []
        for arc in cat["arcs"]:
            for je in arc["journals"]:
                self.assertIn(je["id"], EXPECTED_JES)
                self.assertIn(je["id"], native)
                native_fields = native[je["id"]]
                script_nodes = [row for row in parse(je["script"]) if row[0] != "{"]
                self.assertTrue(script_nodes)
                for key, op, value in script_nodes:
                    matches = [(native_op, native_value) for native_key, native_op, native_value
                               in native_fields if native_key == key]
                    self.assertEqual(len(matches), 1, (je["id"], key))
                    if adapter is None or key not in {"immediate", "on_complete", "on_fail", "on_monthly_pulse"}:
                        self.assertEqual((op, value), matches[0], (je["id"], key))
                    elif key in {"immediate", "on_complete", "on_fail"}:
                        # Lifecycle augmentation appends one witness operation;
                        # the entire authored business body remains its prefix.
                        self.assertEqual(matches[0][0], op)
                        self.assertEqual(matches[0][1][:len(value)], value, (je["id"], key))
                for key, value in (("complete", je["goal"]), ("fail", je["exit_conditions"])):
                    matches = [body for native_key, _, body in native_fields if native_key == key]
                    self.assertEqual(len(matches), 1, (je["id"], key))
                    self.assertEqual(parse(f"{key} = {value}")[0][2], matches[0], (je["id"], key))
                branches = _binding(je["id"], je["script"])
                counts[je["id"]] = len(branches)
                for row in branches:
                    candidate = row["candidates"][0]
                    kinds[candidate["kind"]] += 1
                    events.append(row["event"])
        self.assertEqual(set(counts), EXPECTED_JES)
        self.assertEqual(counts, {jid: 11 for jid in EXPECTED_JES})
        self.assertEqual(kinds, {"normal": 48, "notice": 18})
        for arc in cat["arcs"]:
            for je in arc["journals"]:
                rows = _binding(je["id"], je["script"])
                self.assertEqual([row["candidates"][0]["kind"] for row in rows],
                                 ["notice", "notice", "notice"] + ["normal"] * 8)
                base_event = {"roads": 1000, "debt": 1010, "grain": 1020}[
                    next(name for name in ("roads", "debt", "grain") if name in je["id"])]
                self.assertEqual([row["candidates"][0]["value"] for row in rows],
                                 [base_event + 6, base_event + 7, base_event + 6,
                                  *range(base_event, base_event + 8)])
                self.assertEqual([int(row["event"].rsplit(".", 1)[1]) for row in rows],
                                 [row["candidates"][0]["value"] for row in rows])
        self.assertEqual(len(events), 66)
        self.assertEqual(len(set(events)), 24)
        native_events = {k for k, _, _ in parse(EVENT_PATH.read_text(encoding="utf-8-sig")) if k != "namespace"}
        self.assertEqual(set(events), native_events)
        # Same native notice event has independent notice and normal senders.
        for event_id in events:
            if event_id.rsplit(".", 1)[-1] in {"1006", "1007", "1016", "1017", "1026", "1027"}:
                kinds_for_event = {row["candidates"][0]["kind"] for a in cat["arcs"]
                    for je in a["journals"] for row in _binding(je["id"], je["script"])
                    if row["event"] == event_id}
                self.assertEqual(kinds_for_event, {"normal", "notice"})

    def test_all_24_full_native_event_and_helper_asts_are_bound(self):
        cat = _catalog()
        native_events = {k: b for k, _, b in parse(EVENT_PATH.read_text(encoding="utf-8-sig"))
                         if k != "namespace"}
        adapter, _, expected_events = _formal_generated_projection(cat)
        self.assertEqual(native_events, expected_events)
        catalog_events = {event["id"]: event for arc in cat["arcs"] for event in arc["events"]}
        self.assertEqual(set(catalog_events), set(native_events))
        for event_id, event in catalog_events.items():
            with self.subTest(event=event_id):
                body = native_events[event_id]
                native_immediate = [v for k, _, v in body if k == "immediate"]
                self.assertEqual(len(native_immediate), 1)
                authored_immediate = parse("immediate = " + event["immediate"])[0][2]
                if adapter is None:
                    self.assertEqual(authored_immediate, native_immediate[0])
                else:
                    self.assertIn(event_id, adapter["guarded_immediate_events"])
                    guards = adapter["event_hooks"][event_id]
                    self.assertTrue(guards)
                    gate = [("OR", "=", [(name, "=", "yes") for name in guards])]
                    self.assertEqual(len(native_immediate[0]), 1)
                    self.assertEqual(native_immediate[0][0][:2], ("if", "="))
                    guarded_body = native_immediate[0][0][2]
                    self.assertEqual(guarded_body[0], ("limit", "=", gate))
                    self.assertEqual(guarded_body[1:1 + len(authored_immediate)], authored_immediate)
                    proofs = adapter["inline_proofs"][event_id]
                    acks = adapter["ack_hooks"][event_id]
                    self.assertTrue(proofs)
                    self.assertTrue(acks)
                    suffix = parse(" ".join(proofs) + " " + " ".join(f"{name} = yes" for name in acks))
                    self.assertEqual(guarded_body[1 + len(authored_immediate):], suffix)
                # Retain full authored condition and immediate AST, including
                # the three observation events' post-cooldown open write.
                native_trigger = [v for k, _, v in body if k == "trigger"]
                self.assertEqual(len(native_trigger), 1)
                authored_trigger = parse("trigger = " + event["trigger"])[0][2]
                if adapter is None:
                    self.assertEqual(authored_trigger, native_trigger[0])
                else:
                    self.assertEqual(native_trigger[0], [("AND", "=", authored_trigger + gate)])
        observation_events = {"ywc_mng.1005", "ywc_mng.1015", "ywc_mng.1025"}
        for event_id in observation_events:
            nodes = parse("immediate = " + catalog_events[event_id]["immediate"])[0][2]
            self.assertEqual([key for key, _, _ in nodes],
                             ["ywc_v03_mark_major_delivered", "set_variable"]
                             if event_id == "ywc_mng.1005" else
                             ["ywc_v03_mark_major_delivered", "set_variable"]
                             if event_id == "ywc_mng.1015" else
                             ["ywc_v03_mark_major_delivered", "set_variable"])
            observation = nodes[1][2]
            self.assertEqual({key: value for key, _, value in observation},
                             {"name": {"ywc_mng.1005": "ywc_mgl_roads_observation_open",
                                       "ywc_mng.1015": "ywc_mgl_debt_observation_open",
                                       "ywc_mng.1025": "ywc_mgl_grain_observation_open"}[event_id],
                              "value": "1"})
        # Every helper invoked by a native sender or event exists in the real
        # scripted-trigger registry and its full AST is available for gates.
        helpers = {k: b for k, _, b in parse(TRIGGER_PATH.read_text(encoding="utf-8-sig"))}
        invoked = set()
        def walk(nodes):
            for key, op, value in nodes:
                if key in helpers and op == "=" and value in ("yes", "no"):
                    invoked.add(key)
                if isinstance(value, list):
                    walk(value)
        for arc in cat["arcs"]:
            for je in arc["journals"]:
                walk(parse(je["script"]))
            for event in arc["events"]:
                walk(parse("trigger = " + event["trigger"]))
        self.assertGreaterEqual(len(invoked), 2)
        obligation_predicates = {
            f"ywc_mgl_{arc}_{name}" for arc in ("roads", "debt", "grain")
            for name in ("any_affordable_entry_offer", "selected_current_obligation",
                         "current_obligation_ready")
        }
        self.assertTrue(obligation_predicates <= set(helpers))
        self.assertTrue(all(helpers[name] for name in obligation_predicates))

    def test_source_bound_v2_candidate_reaches_both_public_apis_before_mutants(self):
        valid = _v2_catalog_from_formal_mgl_source()
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["branches"]) for a in valid["arcs"]), 66)
        self.assertTrue(all(a["inline_delivery_adapter"]["schema"] == "v03.foundation_inline_adapter.v2"
                            for a in valid["arcs"]))
        # Intended ordinary feature RED on baseline: first source candidate is
        # validated by the public API, then both renderers run before mutants.
        from tests.test_v03_mgl_inline_actual_source import assert_inline_supported
        rendered = assert_inline_supported(self)
        self.assertEqual(len(rendered["event_hooks"]), 24)
        mutations = []
        missing = copy.deepcopy(valid)
        missing["arcs"][0]["inline_delivery_adapter"]["branches"].pop()
        mutations.append(missing)
        bad_hash = copy.deepcopy(valid)
        bad_hash["arcs"][0]["inline_delivery_adapter"]["branches"][0]["branch_sha256"] = "0" * 64
        mutations.append(bad_hash)
        foreign_queue = copy.deepcopy(valid)
        foreign_queue["arcs"][0]["inline_delivery_adapter"]["branches"][0]["candidates"][0]["queue"] = \
            "ywc_mgl_roads_route"
        mutations.append(foreign_queue)
        alias = copy.deepcopy(valid)
        alias["arcs"][0]["inline_delivery_adapter"]["live_phases"][0]["live_witness"] = \
            alias["arcs"][0]["inline_delivery_adapter"]["live_phases"][1]["live_witness"]
        mutations.append(alias)
        protected_alias = copy.deepcopy(valid)
        protected_alias["arcs"][0]["inline_delivery_adapter"]["live_phases"][0]["live_witness"] = \
            "ywc_mgl_roads_route"
        mutations.append(protected_alias)
        for mutant in mutations:
            with self.assertRaises(ValueError):
                validate_inline_catalog(mutant)
            with self.assertRaises(ValueError):
                render_inline_country_adapters(mutant)

    def test_full_native_body_prefix_proof_ack_and_ack_helper_guards(self):
        from tests.test_v03_mgl_inline_actual_source import assert_inline_supported
        from tools import build_v03_content

        catalog = _v2_catalog_from_formal_mgl_source()
        rendered = assert_inline_supported(self)
        generated = _definitions_no_duplicates(
            build_v03_content._render_event_file(catalog, ROOT, rendered), "generated_events")
        source_events = {event["id"]: event for arc in catalog["arcs"] for event in arc["events"]}
        effect_defs = _definitions_no_duplicates(rendered["effects"], "generated_effects")
        for event_id in sorted(source_events):
            with self.subTest(event=event_id):
                source = source_events[event_id]
                actual = generated[event_id]
                source_immediate = parse("immediate = " + source["immediate"])[0][2]
                actual_immediate = next(value for key, _, value in actual if key == "immediate")
                outer = [value for key, _, value in actual_immediate if key == "if"]
                self.assertEqual(len(outer), 1, "builder wrapper must guard the whole immediate")
                gated = outer[0]
                limit = next(value for key, _, value in gated if key == "limit")
                self.assertEqual(limit[0][0], "OR")
                self.assertEqual({key for key, _, key_value in limit[0][2]
                                  if key_value == "yes"}, set(rendered["event_hooks"][event_id]))
                body = [node for node in gated if node[0] != "limit"]
                self.assertEqual(body[:len(source_immediate)], source_immediate,
                                 "complete native event body must be the first guarded effect prefix")
                cursor = len(source_immediate)
                proofs = [node for text in rendered["inline_proofs"].get(event_id, [])
                          for node in parse("proof = { " + text + " }")[0][2]]
                self.assertEqual(body[cursor:cursor + len(proofs)], proofs)
                proof_nodes = list(_walk_rows(proofs))
                receipt_names = [value for key, _, value in proof_nodes if key == "name"
                                 and isinstance(value, str) and "_body_completed_" in value]
                self.assertTrue(receipt_names,
                                "post-body proof writes body-completion receipt only after native AST")
                cursor += len(proofs)
                expected_ack = [(name, "=", "yes") for name in rendered["ack_hooks"][event_id]]
                self.assertEqual(body[cursor:], expected_ack,
                                 "ACK callbacks must follow the complete body and inline proof")
                self.assertTrue(expected_ack)
                generated_trigger = next(value for key, _, value in actual if key == "trigger")
                self.assertEqual(generated_trigger[0][0], "AND")
                gate_parts = generated_trigger[0][2]
                self.assertEqual(gate_parts[-1][0], "OR")
                self.assertEqual({key for key, _, value in gate_parts[-1][2] if value == "yes"},
                                 set(rendered["event_hooks"][event_id]))

        for event_id, callbacks in rendered["ack_hooks"].items():
            for callback in callbacks:
                with self.subTest(event=event_id, callback=callback):
                    self.assertIn(callback, effect_defs)
                    callback_nodes = list(_walk_rows(effect_defs[callback]))
                    ack_calls = [key for key, op, value in callback_nodes
                                 if op == "=" and value == "yes" and "_ack_" in key]
                    self.assertEqual(len(ack_calls), 1)
                    ack = ack_calls[0]
                    self.assertIn(ack, effect_defs)
                    ack_nodes = list(_walk_rows(effect_defs[ack]))
                    scalar_pairs = list(_scalar_pairs(effect_defs[ack]))
                    self.assertTrue(any(key.startswith("has_variable") and "_body_completed_" in value
                                         for key, value in scalar_pairs))
                    self.assertTrue(any(key.startswith("var:") and "_body_completed_" in key
                                         for key, _ in scalar_pairs))
                    self.assertTrue(any(key.startswith("var:") and key.endswith("_reservation_epoch")
                                         for key, _ in scalar_pairs))
                    ack_writes = _set_variable_names(effect_defs[ack])
                    self.assertFalse(any("_body_completed_" in name for name in ack_writes),
                                     "callback/ACK must inspect, never mint body-completion proof")

    def test_native_event_comments_and_whitespace_preserve_rendered_helpers_and_ack_ast(self):
        from tests.test_v03_mgl_inline_actual_source import assert_inline_supported
        from tools import build_v03_content

        valid = _v2_catalog_from_formal_mgl_source()
        baseline = assert_inline_supported(self)
        baseline_event_file = build_v03_content._render_event_file(valid, ROOT, baseline)
        source_events = {event["id"]: event for arc in valid["arcs"] for event in arc["events"]}
        observations = {"ywc_mng.1005", "ywc_mng.1015", "ywc_mng.1025"}
        for event_id, event in source_events.items():
            original = event["immediate"]
            variants = {
                "comment_before_body": original.replace("{", "{ # legal metadata-looking comment\n", 1),
                "comment_after_major": original.replace(
                    "ywc_v03_mark_major_delivered = yes",
                    "ywc_v03_mark_major_delivered = yes # ywc_mgl_roads_route = 999\n", 1),
                "whitespace_only": "{\n    " + original.strip()[1:-1].strip().replace(" ", "\n    ") + "\n}",
            }
            for layout, variant in variants.items():
                with self.subTest(event=event_id, layout=layout):
                    self.assertEqual(parse("immediate = " + original),
                                     parse("immediate = " + variant),
                                     "comment/whitespace variant must preserve native AST")
                    mutated = copy.deepcopy(valid)
                    next(e for arc in mutated["arcs"] for e in arc["events"]
                         if e["id"] == event_id)["immediate"] = variant
                    validate_inline_catalog(mutated)
                    rendered = render_inline_country_adapters(mutated)
                    self.assertEqual(rendered, baseline,
                                     "legal formatting cannot alter any generated helper, guard or ACK")
                    rendered_event_file = build_v03_content._render_event_file(mutated, ROOT, rendered)
                    if event_id in observations:
                        before = _definitions_no_duplicates(baseline_event_file, "baseline_events")[event_id]
                        after = _definitions_no_duplicates(rendered_event_file, "formatted_events")[event_id]
                        before_immediate = next(v for k, _, v in before if k == "immediate")
                        after_immediate = next(v for k, _, v in after if k == "immediate")
                        self.assertEqual(before_immediate, after_immediate,
                                         "observation event runtime body/ACK AST must be unchanged")

    def test_all_nine_native_obligation_helper_ast_mutants_are_rejected(self):
        from tests.test_v03_mgl_inline_actual_source import assert_inline_supported
        from tools import v03_inline_delivery_adapter as public

        candidate = _v2_catalog_from_formal_mgl_source()
        rendered = assert_inline_supported(self)
        self.assertEqual(len(rendered["event_hooks"]), 24)
        validate_helpers = getattr(public, "validate_mgl_native_helper_source", None)
        self.assertTrue(callable(validate_helpers),
                        "MGL source helper ABI must have a public fail-closed source validator")
        source = TRIGGER_PATH.read_text(encoding="utf-8-sig")
        validate_helpers(source)
        mutants = _helper_mutants(source)
        self.assertEqual(len(mutants), 9)
        for name, mutant_source, original_ast, mutant_ast in mutants:
            with self.subTest(helper=name):
                self.assertNotEqual(original_ast, mutant_ast)
                with self.assertRaises(ValueError):
                    validate_helpers(mutant_source)

    def test_nine_helper_mutation_controls_are_feature_independent(self):
        """Exercise source-site and AST-scope assertions even while API is RED."""
        mutants = _helper_mutants(TRIGGER_PATH.read_text(encoding="utf-8-sig"))
        self.assertEqual(len(mutants), 9)
        self.assertEqual({name for name, *_ in mutants}, {
            f"ywc_mgl_{arc}_{helper}" for arc in ("roads", "debt", "grain")
            for helper in ("any_affordable_entry_offer", "selected_current_obligation",
                           "current_obligation_ready")})
        for name, _, original_ast, mutant_ast in mutants:
            with self.subTest(helper=name):
                self.assertNotEqual(original_ast, mutant_ast)

    def test_nested_ack_ast_extractors_handle_blocks_without_hashing(self):
        """Pin the proof/ACK extraction helpers independently of MGL renderer support."""
        nodes = parse_block("""{
            has_variable = ywc_mgl_roads_body_completed
            var:ywc_mgl_roads_body_completed = 1
            var:ywc_mgl_roads_reservation_epoch = 4
            set_variable = { name = ywc_mgl_roads_ack_marker value = 1 }
        }""")
        rows = _rows(nodes)
        scalar = list(_scalar_pairs(rows))
        self.assertIn(("has_variable", "ywc_mgl_roads_body_completed"), scalar)
        self.assertIn(("var:ywc_mgl_roads_reservation_epoch", "4"), scalar)
        self.assertEqual(_set_variable_names(rows), ["ywc_mgl_roads_ack_marker"])
        self.assertFalse(any("_body_completed_" in name
                             for name in _set_variable_names(rows)))

    def test_sender_limit_chain_ordinal_auxwrite_and_exclusion_mutants_are_rejected(self):
        from tests.test_v03_mgl_inline_actual_source import assert_inline_supported

        valid = _v2_catalog_from_formal_mgl_source()
        rendered = assert_inline_supported(self)
        self.assertEqual(len(rendered["event_hooks"]), 24)

        cases = []
        limit_mutant = copy.deepcopy(valid)
        arc = limit_mutant["arcs"][0]
        journal = arc["journals"][0]
        branch = next(row for row in _binding(journal["id"], journal["script"])
                      if row["candidates"][0]["kind"] == "notice")
        old_limit = journal["script"][branch["start"]:branch["end"]]
        candidate = branch["candidates"][0]
        self.assertIn(f"var:{candidate['queue']} = {candidate['value']}", old_limit)
        journal["script"] = journal["script"].replace(
            f"var:{candidate['queue']} = {candidate['value']}",
            f"var:{candidate['queue']} = {candidate['value'] + 1}", 1)
        cases.append(("limit candidate rebound", _rebind_v2_catalog(limit_mutant)))

        prior_mutant = copy.deepcopy(valid)
        branch_row = prior_mutant["arcs"][0]["inline_delivery_adapter"]["branches"][1]
        self.assertTrue(branch_row["chain_prior"])
        branch_row["chain_prior"][0]["ordinal"] += 1
        cases.append(("chain prior ordinal", prior_mutant))

        ordinal_mutant = copy.deepcopy(valid)
        ordinal_mutant["arcs"][0]["inline_delivery_adapter"]["branches"][0]["statement_ordinal"] += 1
        cases.append(("sender statement ordinal", ordinal_mutant))

        auxwrite_mutant = copy.deepcopy(valid)
        arc = auxwrite_mutant["arcs"][0]
        journal = arc["journals"][0]
        branch = _binding(journal["id"], journal["script"])[0]
        queue = branch["candidates"][0]["queue"]
        source_branch = journal["script"][branch["start"]:branch["end"]]
        statement = f"remove_variable = {queue}"
        self.assertEqual(source_branch.count(statement), 1)
        journal["script"] = journal["script"].replace(
            statement, f"remove_variable = {{ name = {queue} days = 1 }}", 1)
        cases.append(("native queue auxiliary write", _rebind_v2_catalog(auxwrite_mutant)))

        exclusion_mutant = copy.deepcopy(valid)
        exclusion_mutant["arcs"][0]["inline_delivery_adapter"]["branches"][0]["queue_exclusions"] = [
            {"queue": "ywc_mgl_roads_pending_event", "op": "=", "mode": "exact", "value": 0}]
        cases.append(("queue exclusion context", exclusion_mutant))

        for label, mutant in cases:
            with self.subTest(context_mutation=label):
                self.assertNotEqual(mutant, valid)
                with self.assertRaises(ValueError):
                    validate_inline_catalog(mutant)
                with self.assertRaises(ValueError):
                    render_inline_country_adapters(mutant)


if __name__ == "__main__":
    unittest.main()
