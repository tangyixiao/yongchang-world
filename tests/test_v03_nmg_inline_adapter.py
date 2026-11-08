"""Permanent NMG source-bound inline adapter contract (deliberate feature RED)."""
import hashlib
import copy
import json
import re
import unittest
from pathlib import Path

from tools.v03_inline_delivery_adapter import (
    _kor_direct_adds, _kor_source_binding, children, direct_values, parse_block,
    render_inline_country_adapters, validate_inline_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/content/v03/countries/nmg.json"
JOURNAL_PATH = ROOT / "yongchang_world/common/journal_entries/ywc_v03_country_nmg_journal.txt"


def native_journals():
    from tests.clausewitz_harness import parse
    return {key: body for key, _, body in parse(JOURNAL_PATH.read_text(encoding="utf-8-sig"))}


def catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _sender_candidates(branch_source, owner=None):
    """Extract NMG queue + notice discriminator from one authentic source branch."""
    root = parse_block("{ " + branch_source + " }")
    if len(root) != 1 or root[0].key not in {"if", "else_if", "limit"}:
        raise ValueError("expected one NMG sender branch or limit")
    if root[0].key == "limit":
        limit = root[0]
    else:
        limits = direct_values(children(root[0]), "limit")
        if len(limits) != 1:
            raise ValueError("NMG sender must have one limit")
        limit = limits[0]
    all_nodes = []
    def walk(nodes, negative=False):
        for node in nodes:
            if node.key in {"OR", "XOR", "NOR"}:
                raise ValueError(f"unsupported NMG queue Boolean/container {node.key}")
            if isinstance(node.value, tuple) and node.key not in {"limit", "AND", "NOT"}:
                raise ValueError(f"unsupported NMG queue Boolean/container {node.key}")
            if node.key != "NOT" and not negative:
                all_nodes.append(node)
            if isinstance(node.value, tuple):
                walk(node.value, negative or node.key == "NOT")
    walk(children(limit))
    queues = [n for n in all_nodes if n.key.startswith("var:ywc_nmg_") and n.op == "="
              and isinstance(n.value, str) and n.value.isdigit()
              and n.key.endswith(("_pending", "_notice_pending"))]
    if len(queues) != 1:
        raise ValueError(f"expected exactly one positive NMG queue predicate, got {len(queues)}")
    q = queues[0]
    if owner is not None and q.key != f"var:ywc_nmg_{owner}_{'notice_pending' if q.key.endswith('_notice_pending') else 'pending'}":
        raise ValueError(f"candidate queue is not owned by {owner}")
    kind = "notice" if q.key.endswith("_notice_pending") else "normal"
    return [{"queue": q.key.removeprefix("var:"), "kind": kind,
             "mode": "exact", "value": int(q.value)}]


def _nmg_sender_binding(journal_id, script):
    """Project authentic sibling sender chains through the shared binding API.

    The parser currently accepts direct pulse chains. NMG places its normal chain
    under the native notice `else`; each projected source branch remains the
    original source text, while group/index information comes from AST siblings.
    """
    top = parse_block(script)
    monthly = direct_values(top, "on_monthly_pulse")
    if len(monthly) != 1:
        raise ValueError(f"{journal_id}: expected one monthly pulse")
    effects = direct_values(children(monthly[0]), "effect")
    if len(effects) != 1:
        raise ValueError(f"{journal_id}: expected one monthly effect")
    groups = []
    def walk(nodes, enclosing_else=None):
        sender_group = []
        for sibling_ordinal, node in enumerate(nodes):
            if node.key in {"if", "else_if"}:
                direct = direct_values(children(node), "trigger_event")
                if direct:
                    if len(direct) != 1:
                        raise ValueError(f"{journal_id}: sender has multiple trigger_event nodes")
                    sender_group.append((node, sibling_ordinal))
            elif node.key == "else":
                if sender_group:
                    groups.append((sender_group, enclosing_else))
                    sender_group = []
                walk(children(node), node)
            elif isinstance(node.value, tuple):
                if sender_group:
                    groups.append((sender_group, enclosing_else))
                    sender_group = []
                walk(children(node), enclosing_else)
        if sender_group:
            groups.append((sender_group, enclosing_else))
    walk(children(effects[0]))
    owner = ("land" if "land_" in journal_id else
             "office" if "office" in journal_id else "revenue")
    candidates = lambda branch: _sender_candidates(branch, owner=owner)
    rows, base_index = [], 0
    for chain_index, (group, enclosing_else) in enumerate(groups):
        fragments = [script[node.start:node.end] for node, _ in group]
        projected = "{ on_monthly_pulse = { effect = { " + " ".join(fragments) + " } } }"
        bound = _kor_source_binding(journal_id, projected, candidate_parser=candidates,
                                    exclusion_parser=_nmg_queue_exclusions)["branches"]
        if len(bound) != len(group):
            raise ValueError(f"{journal_id}: shared source binder lost a nested sender")
        for local, ((node, sibling_ordinal), source) in enumerate(zip(group, bound)):
            rows.append({**source, "branch_index": base_index + local,
                         "statement_ordinal": sibling_ordinal, "chain_index": chain_index,
                         "start": node.start, "end": node.end})
        base_index += len(group)
    # The ordinary sender chain is nested under the notice chain's `else`.
    # Bind both outer notice guards into every ordinary branch's exclusion proof.
    if len(groups) == 2 and groups[1][1] is not None:
        enclosing_else_source = script[groups[1][1].start:groups[1][1].end]
        outer_notice = [
            {"ordinal": row["statement_ordinal"], "sha256": row["sha256"],
             "limit_sha256": row["limit_sha256"], "limit_source": row["limit_source"]}
            for row in rows if row["chain_index"] == 0
        ]
        for row in rows:
            if row["chain_index"] != 1:
                continue
            row["chain_prior"] = outer_notice + row["chain_prior"]
            # The v2 fields have no separate ancestor field. Bind the full native
            # `else` AST alongside sibling priors into chain_sha256 so changes to
            # the enclosing notice-before-normal gate cannot be rebound away.
            row["chain_sha256"] = hashlib.sha256(repr({
                "chain_prior": row["chain_prior"],
                "enclosing_else_sha256": hashlib.sha256(enclosing_else_source.encode()).hexdigest(),
            }).encode()).hexdigest()
    return rows


def _nmg_queue_exclusions(branch_source):
    root = parse_block("{ " + branch_source + " }")
    if len(root) != 1 or root[0].key not in {"if", "else_if"}:
        raise ValueError("NMG exclusions require one source branch")
    limits = direct_values(children(root[0]), "limit")
    if len(limits) != 1:
        raise ValueError("NMG sender must have one limit")
    result = []
    def visit(nodes, negative=False):
        for node in nodes:
            neg = negative or node.key == "NOT"
            if node.key in {"OR", "XOR", "NOR"}:
                raise ValueError(f"unsupported NMG Boolean queue container {node.key}")
            if isinstance(node.value, tuple):
                visit(node.value, neg)
            elif neg and node.key.startswith("var:ywc_nmg_") and node.key.endswith(("_pending", "_notice_pending")):
                result.append({"queue": node.key.removeprefix("var:"), "op": node.op,
                               "mode": "exact", "value": node.value})
            elif neg and node.key == "has_variable" and isinstance(node.value, str) and node.value.startswith("ywc_nmg_") and node.value.endswith(("_pending", "_notice_pending")):
                result.append({"queue": node.value, "op": node.op, "mode": "presence"})
    visit(children(limits[0]))
    return result


def _v2_catalog_from_nmg_source():
    """Build complete v2 per-arc metadata using authentic source bindings."""
    result = copy.deepcopy(catalog())
    for arc in result["arcs"]:
        phases, branches = [], []
        for journal in arc["journals"]:
            script = journal["script"]
            slug = re.sub(r"[^a-z0-9_]+", "_", journal["id"].removeprefix("ywc_je_v03_nmg_"))
            phases.append({"journal": journal["id"],
                "live_witness": f"ywc_v03_nmg_inline_live_{slug}",
                "source_script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
                "goal_sha256": hashlib.sha256(journal["goal"].encode("utf-8")).hexdigest(),
                "exit_sha256": hashlib.sha256(journal["exit_conditions"].encode("utf-8")).hexdigest()})
            for source in _nmg_sender_binding(journal["id"], script):
                branches.append({"journal": journal["id"],
                    "branch_index": source["branch_index"],
                    "statement_ordinal": source["statement_ordinal"],
                    "chain_index": source["chain_index"],
                    "branch_kind": source["branch_kind"],
                    "event": source["event"],
                    "branch_sha256": source["sha256"],
                    "limit_sha256": source["limit_sha256"],
                    "chain_prior": source["chain_prior"],
                    "chain_sha256": source["chain_sha256"],
                    "candidates": source["candidates"],
                    "queue_exclusions": source["queue_exclusions"]})
        arc["inline_delivery_adapter"] = {
            "schema": "v03.foundation_inline_adapter.v2",
            "live_phases": phases,
            "branches": branches,
            "direct_adds": _kor_direct_adds(arc),
        }
    return result


def _rebind_v2_catalog_source(candidate):
    """Recompute every source pin/binding after a native in-memory mutation."""
    for arc in candidate["arcs"]:
        phases, branches = [], []
        for journal in arc["journals"]:
            script = journal["script"]
            slug = re.sub(r"[^a-z0-9_]+", "_", journal["id"].removeprefix("ywc_je_v03_nmg_"))
            phases.append({"journal": journal["id"],
                "live_witness": f"ywc_v03_nmg_inline_live_{slug}",
                "source_script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
                "goal_sha256": hashlib.sha256(journal["goal"].encode("utf-8")).hexdigest(),
                "exit_sha256": hashlib.sha256(journal["exit_conditions"].encode("utf-8")).hexdigest()})
            for source in _nmg_sender_binding(journal["id"], script):
                branches.append({"journal": journal["id"],
                    "branch_index": source["branch_index"],
                    "statement_ordinal": source["statement_ordinal"],
                    "chain_index": source["chain_index"],
                    "branch_kind": source["branch_kind"], "event": source["event"],
                    "branch_sha256": source["sha256"], "limit_sha256": source["limit_sha256"],
                    "chain_prior": source["chain_prior"], "chain_sha256": source["chain_sha256"],
                    "candidates": source["candidates"], "queue_exclusions": source["queue_exclusions"]})
        arc["inline_delivery_adapter"]["live_phases"] = phases
        arc["inline_delivery_adapter"]["branches"] = branches
        arc["inline_delivery_adapter"]["direct_adds"] = _kor_direct_adds(arc)
    return candidate


def _assert_exact_candidate_shape(candidate):
    if (set(candidate) != {"queue", "kind", "mode", "value"}
            or not isinstance(candidate["queue"], str)
            or candidate["kind"] not in {"normal", "notice"}
            or candidate["mode"] != "exact"
            or type(candidate["value"]) is not int):
        raise ValueError("invalid NMG exact queue candidate shape")


class NmgInlineAdapterContract(unittest.TestCase):
    def test_actual_nmg_source_has_36_sender_sites_and_exact_six_je_allocation(self):
        cat = catalog()
        ids = [j["id"] for arc in cat["arcs"] for j in arc["journals"]]
        native = native_journals()
        expected = {
            "ywc_je_v03_nmg_land_arbitration": 6,
            "ywc_je_v03_nmg_land_settlement": 6,
            "ywc_je_v03_nmg_bilingual_office": 8,
            "ywc_je_v03_nmg_revenue_opening": 5,
            "ywc_je_v03_nmg_revenue_negotiation": 6,
            "ywc_je_v03_nmg_revenue_settlement": 5,
        }
        self.assertEqual(set(ids), set(expected))
        counts, rows = {}, []
        for jid in ids:
            script = next(j["script"] for arc in cat["arcs"] for j in arc["journals"] if j["id"] == jid)
            binding = _nmg_sender_binding(jid, script)
            counts[jid] = len(binding)
            for b in binding:
                candidate = _sender_candidates(script[b["start"]:b["end"]])
                rows.append((jid, b["event"], candidate[0]))
            self.assertIn(jid, native)
        self.assertEqual(counts, expected)
        self.assertEqual(sum(counts.values()), 36)
        self.assertEqual(sum(c["kind"] == "normal" for _, _, c in rows), 24)
        self.assertEqual(sum(c["kind"] == "notice" for _, _, c in rows), 12)
        shared = {event for event in {r[1] for r in rows} if sum(x[1] == event for x in rows) > 1}
        self.assertEqual(shared, {"ywc_nmg.1006", "ywc_nmg.1007", "ywc_nmg.1014",
                                  "ywc_nmg.1015", "ywc_nmg.1028", "ywc_nmg.1029"})

    def test_valid_source_bound_v2_catalog_and_public_gate_then_rebound_mutants(self):
        valid = _v2_catalog_from_nmg_source()
        all_witnesses = []
        for arc in valid["arcs"]:
            adapter = arc["inline_delivery_adapter"]
            self.assertEqual(adapter["schema"], "v03.foundation_inline_adapter.v2")
            self.assertEqual({phase["journal"] for phase in adapter["live_phases"]},
                             {journal["id"] for journal in arc["journals"]})
            self.assertEqual(len(adapter["branches"]),
                             sum(len(_nmg_sender_binding(j["id"], j["script"]))
                                 for j in arc["journals"]))
            self.assertTrue(all(set(row) == {"journal", "branch_index", "statement_ordinal",
                "chain_index", "branch_kind", "event", "branch_sha256", "limit_sha256",
                "chain_prior", "chain_sha256", "candidates", "queue_exclusions"}
                for row in adapter["branches"]))
            self.assertEqual(adapter["direct_adds"], _kor_direct_adds(arc))
            for row in adapter["branches"]:
                self.assertEqual(row["candidates"][0]["value"], int(row["event"].rsplit(".", 1)[1]))
                if row["candidates"][0]["kind"] == "normal":
                    outer_notice_priors = [prior for prior in row["chain_prior"]
                                           if _sender_candidates(prior["limit_source"])[0]["kind"] == "notice"]
                    self.assertEqual(len(outer_notice_priors), 2,
                                     "normal branches must retain both enclosing notice guards")
                    self.assertEqual([prior["ordinal"] for prior in outer_notice_priors], [1, 2])
                    self.assertTrue(all(prior["sha256"] and prior["limit_sha256"]
                                        and prior["limit_source"] for prior in outer_notice_priors))
            for phase in adapter["live_phases"]:
                journal = next(j for j in arc["journals"] if j["id"] == phase["journal"])
                self.assertEqual(phase["source_script_sha256"],
                                 hashlib.sha256(journal["script"].encode("utf-8")).hexdigest())
                all_witnesses.append(phase["live_witness"])
        self.assertEqual(len(all_witnesses), len(set(all_witnesses)),
                         "live helper witnesses must not collide across NMG arcs")
        # This is the intentional feature RED today: NMG is not yet a registered
        # inline country. After implementation the valid source-bound oracle passes,
        # and every subsequent source/metadata mutant must fail the public gate.
        try:
            validate_inline_catalog(valid)
        except ValueError as exc:
            self.fail(f"public NMG validator rejected valid source-bound v2 metadata: {exc}")
        rendered = render_inline_country_adapters(valid)
        self.assertEqual(len(rendered["event_hooks"]), 24)

        cases = []
        wrong_queue = copy.deepcopy(valid)
        target = wrong_queue["arcs"][0]["inline_delivery_adapter"]["branches"][0]
        target["candidates"][0]["queue"] = "ywc_nmg_revenue_pending"
        cases.append(("foreign_queue", wrong_queue))
        wrong_hash = copy.deepcopy(valid)
        wrong_hash["arcs"][0]["inline_delivery_adapter"]["branches"][0]["branch_sha256"] = "0" * 64
        cases.append(("hash", wrong_hash))
        missing = copy.deepcopy(valid)
        missing["arcs"][0]["inline_delivery_adapter"]["branches"].pop()
        cases.append(("missing", missing))
        duplicate = copy.deepcopy(valid)
        duplicate["arcs"][0]["inline_delivery_adapter"]["branches"].append(
            copy.deepcopy(duplicate["arcs"][0]["inline_delivery_adapter"]["branches"][0]))
        cases.append(("duplicate", duplicate))
        metadata_alias = copy.deepcopy(valid)
        metadata_alias["arcs"][0]["inline_delivery_adapter"]["live_phases"][0]["live_witness"] = \
            metadata_alias["arcs"][0]["inline_delivery_adapter"]["live_phases"][1]["live_witness"]
        cases.append(("metadata_alias", metadata_alias))
        for label, mutant in cases:
            self.assertNotEqual(mutant, valid, label)
            with self.subTest(mutant=label, api="validator"), self.assertRaises(ValueError):
                validate_inline_catalog(mutant)
            with self.subTest(mutant=label, api="renderer"), self.assertRaises(ValueError):
                render_inline_country_adapters(mutant)

        # Rebind the full native source after introducing a source change. A
        # structurally valid but unmodeled timer argument must remain rejected.
        rebound = copy.deepcopy(valid)
        arc = rebound["arcs"][0]
        journal = arc["journals"][0]
        branch = next(row for row in _nmg_sender_binding(journal["id"], journal["script"])
                      if row["candidates"][0]["kind"] == "normal")
        old = journal["script"][branch["start"]:branch["end"]]
        queue = branch["candidates"][0]["queue"]
        self.assertIn(f"remove_variable = {queue}", old)
        journal["script"] = journal["script"].replace(
            f"remove_variable = {queue}",
            f"remove_variable = {{ name = {queue} days = 1 }}", 1)
        rebound = _rebind_v2_catalog_source(rebound)
        with self.assertRaises(ValueError):
            validate_inline_catalog(rebound)
        with self.assertRaises(ValueError):
            render_inline_country_adapters(rebound)

        # Preserve every sender and its own queue guard while changing the
        # enclosing native notice `else` AST. Rebinding must not legitimize it.
        outer_mutant = copy.deepcopy(valid)
        journal = outer_mutant["arcs"][0]["journals"][0]
        top = parse_block(journal["script"])
        monthly = direct_values(top, "on_monthly_pulse")
        self.assertEqual(len(monthly), 1)
        effects = direct_values(children(monthly[0]), "effect")
        self.assertEqual(len(effects), 1)
        outer_else = [node for node in children(effects[0]) if node.key == "else"]
        self.assertEqual(len(outer_else), 1)
        native_notice_fallback = outer_else[0]
        first_sender = children(native_notice_fallback)[0]
        self.assertEqual(first_sender.key, "if")
        self.assertTrue(direct_values(children(first_sender), "trigger_event"))
        insert_at = native_notice_fallback.value_start + 1
        journal["script"] = (journal["script"][:insert_at]
                             + " if = { limit = { always = yes } } "
                             + journal["script"][insert_at:])
        outer_mutant = _rebind_v2_catalog_source(outer_mutant)
        self.assertNotEqual(outer_mutant, valid)
        with self.assertRaises(ValueError):
            validate_inline_catalog(outer_mutant)
        with self.assertRaises(ValueError):
            render_inline_country_adapters(outer_mutant)

    def test_queue_candidate_oracle_rejects_missing_duplicate_negative_and_boolean_candidates(self):
        cat = catalog()
        journal = cat["arcs"][0]["journals"][0]
        branch = _nmg_sender_binding(journal["id"], journal["script"])[0]
        source = journal["script"][branch["start"]:branch["end"]]
        candidates = _sender_candidates(source)
        self.assertEqual(len(candidates), 1)
        _assert_exact_candidate_shape(candidates[0])
        self.assertIs(type(candidates[0]["value"]), int)
        bad_bool = dict(candidates[0], value=True)
        with self.assertRaisesRegex(ValueError, "candidate shape"):
            _assert_exact_candidate_shape(bad_bool)
        limit_match = re.search(r"limit\s*=\s*\{.*?\}", source, re.S)
        self.assertIsNotNone(limit_match)
        limit_source = limit_match.group(0)[limit_match.group(0).index("{") + 1:-1]
        with self.assertRaisesRegex(ValueError, "exactly one positive"):
            _sender_candidates("if = { limit = { " + limit_source.replace(
                re.search(r"var:ywc_nmg_[A-Za-z0-9_]+\s*=\s*[0-9]+", limit_source).group(0), "always = yes") +
                " } trigger_event = { id = ywc_nmg.1000 } }")
        positive = re.search(r"var:ywc_nmg_[A-Za-z0-9_]+\s*=\s*[0-9]+", limit_source)
        self.assertIsNotNone(positive)
        duplicated = limit_source + " " + positive.group(0)
        with self.assertRaisesRegex(ValueError, "exactly one positive"):
            _sender_candidates("if = { limit = { " + duplicated +
                                " } trigger_event = { id = ywc_nmg.1000 } }")
        for container in ("OR", "XOR", "NOR", "future_scope"):
            with self.subTest(container=container), self.assertRaises(ValueError):
                _sender_candidates("if = { limit = { " + container +
                    " = { " + positive.group(0) + " } } trigger_event = { id = ywc_nmg.1000 } }")
        negative = re.sub(r"(var:ywc_nmg_[A-Za-z0-9_]+\s*=\s*[0-9]+)", r"NOT = { \1 }",
                          limit_source, count=1)
        with self.assertRaisesRegex(ValueError, "exactly one positive"):
            _sender_candidates("if = { limit = { " + negative +
                                " } trigger_event = { id = ywc_nmg.1000 } }")

    def test_public_gate_rejects_each_rebound_native_notice_abi_mutant(self):
        """The valid authored catalog passes, while each altered immediate fails both APIs."""
        valid = catalog()
        validate_inline_catalog(valid)
        rendered = render_inline_country_adapters(valid)
        self.assertEqual(len(rendered["event_hooks"]), 24)

        mutations = (
            ("return_write_wrong_operator",
             "set_variable = { name = ywc_nmg_land_notice_return_event",
             "set_variable != { name = ywc_nmg_land_notice_return_event"),
            ("return_value_wrong_operator",
             "value = var:ywc_nmg_land_last_event",
             "value != var:ywc_nmg_land_last_event"),
            ("last_event_unmodeled_duration",
             "name = ywc_nmg_land_last_event value = 1006",
             "name = ywc_nmg_land_last_event value = 1006 days = 1"),
            ("return_unmodeled_duration",
             "name = ywc_nmg_land_notice_return_event value = var:ywc_nmg_land_last_event",
             "name = ywc_nmg_land_notice_return_event value = var:ywc_nmg_land_last_event days = 1"),
            ("notice_wrong_delivered_value",
             "name = ywc_nmg_land_notice12_delivered value = 1",
             "name = ywc_nmg_land_notice12_delivered value = 0"),
            ("notice_wrong_response_value",
             "name = ywc_nmg_land_notice_response_context value = 1",
             "name = ywc_nmg_land_notice_response_context value = 0"),
            ("notice_inverted_due_gate",
             "limit = { has_variable = ywc_nmg_land_notice12_due }",
             "limit = { NOT = { has_variable = ywc_nmg_land_notice12_due } }"),
            ("notice_due_remove_wrong_operator",
             "remove_variable = ywc_nmg_land_notice12_due",
             "remove_variable != ywc_nmg_land_notice12_due"),
        )
        for label, old, new in mutations:
            with self.subTest(mutant=label):
                mutant = copy.deepcopy(valid)
                event = next(event for arc in mutant["arcs"] for event in arc["events"]
                             if event["id"] == "ywc_nmg.1006")
                self.assertEqual(event["immediate"].count(old), 1, label)
                event["immediate"] = event["immediate"].replace(old, new, 1)
                self.assertNotEqual(event["immediate"],
                                    next(event["immediate"] for arc in valid["arcs"]
                                         for event in arc["events"]
                                         if event["id"] == "ywc_nmg.1006"), label)
                # Exercise each public boundary independently: a validator
                # rejection must not leave renderer coverage untested.
                with self.subTest(api="validator"), self.assertRaises(ValueError):
                    validate_inline_catalog(mutant)
                with self.subTest(api="renderer"), self.assertRaises(ValueError):
                    render_inline_country_adapters(mutant)

    def test_public_gate_and_all_rendered_helpers_are_invariant_to_legal_nmg_comments(self):
        """Comments before a native receipt are AST-neutral and must not alter rendered proofs or ACKs."""
        from tests.clausewitz_harness import parse

        base = catalog()
        validate_inline_catalog(base)
        baseline_render = render_inline_country_adapters(base)
        self.assertEqual(len(baseline_render["event_hooks"]), 24)
        def native_receipt_owner(immediate, event_id):
            roots = parse_block(immediate)
            matches = []

            def walk(nodes):
                for node in nodes:
                    if node.key == "set_variable" and isinstance(node.value, tuple):
                        names = direct_values(children(node), "name")
                        values = direct_values(children(node), "value")
                        if (len(names) == len(values) == 1 and names[0].op == "="
                                and values[0].op == "="
                                and isinstance(names[0].value, str)
                                and isinstance(values[0].value, str)
                                and re.fullmatch(r"ywc_nmg_([a-z0-9_]+)_last_event", names[0].value)
                                and values[0].value == event_id.rsplit(".", 1)[1]):
                            matches.append(re.fullmatch(
                                r"ywc_nmg_([a-z0-9_]+)_last_event", names[0].value
                            ).group(1))
                    if isinstance(node.value, tuple):
                        walk(node.value)

            walk(roots)
            self.assertEqual(len(matches), 1, event_id)
            return matches[0]

        source_events = []
        excluded_protocol_events = []
        for arc in base["arcs"]:
            for event in arc["events"]:
                if event["id"] in {"ywc_nmg.1030", "ywc_nmg.1031", "ywc_nmg.1032", "ywc_nmg.1033"}:
                    excluded_protocol_events.append(event["id"])
                    continue
                if event.get("immediate"):
                    source_events.append((native_receipt_owner(event["immediate"], event["id"]),
                                          event["id"]))
        self.assertEqual(excluded_protocol_events, ["ywc_nmg.1030", "ywc_nmg.1031", "ywc_nmg.1032", "ywc_nmg.1033"])
        self.assertEqual(len(source_events), 24)

        def comment_variants(source, comment):
            major = "ywc_v03_mark_major_delivered = yes"
            self.assertEqual(source.count(major), 1)
            return {
                # Leading comment inside the native block, before its body.
                "prefix": source.replace("{", "{\n" + comment + "\n", 1),
                # Comment between the cooldown marker and native receipt.
                "before_receipt": source.replace(major, major + "\n" + comment + "\n", 1),
                # A same-line comment ends at the newline before the true receipt.
                "same_line": source.replace(major, major + " " + comment + "\n", 1),
            }

        for owner, event_id in source_events:
            original = next(event["immediate"] for arc in base["arcs"]
                            for event in arc["events"] if event["id"] == event_id)
            comment = f"# name = ywc_nmg_{owner}_last_event value = 777"
            for layout, immediate in comment_variants(original, comment).items():
                with self.subTest(event=event_id, layout=layout):
                    mutant = copy.deepcopy(base)
                    event = next(event for arc in mutant["arcs"] for event in arc["events"]
                                 if event["id"] == event_id)
                    self.assertEqual(event["immediate"], original)
                    event["immediate"] = immediate
                    self.assertEqual(parse("immediate = " + original),
                                     parse("immediate = " + immediate),
                                     "comment-only mutation must preserve native Clausewitz AST")
                    validate_inline_catalog(mutant)
                    rendered = render_inline_country_adapters(mutant)
                    self.assertTrue(rendered == baseline_render,
                                    "legal comments must preserve every rendered helper and hook field")


if __name__ == "__main__":
    unittest.main()
