"""Permanent source-bound LAN inline adapter contract checks."""
import hashlib
import copy
import json
import re
import unittest
from pathlib import Path

from tests.clausewitz_harness import parse
from tools.v03_inline_delivery_adapter import (
    _kor_direct_adds,
    _kor_source_binding,
    children,
    direct_values,
    parse_block,
    render_node,
    source_binding,
    validate_inline_catalog,
    render_inline_country_adapters,
    validate_lan_native_helper_source,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/content/v03/countries/lan.json"
NATIVE_JOURNAL_PATH = ROOT / "yongchang_world/common/journal_entries/ywc_v03_country_lan_journal.txt"
COUNTS = {
    "ywc_je_v03_lan_mine_ledger": 7,
    "ywc_je_v03_lan_mine_settlement": 5,
    "ywc_je_v03_lan_river_compacts": 8,
    "ywc_je_v03_lan_river_settlement": 4,
    "ywc_je_v03_lan_accident_fund": 7,
    "ywc_je_v03_lan_fund_settlement": 5,
}
ARC_SLUGS = {"v03_lan_mine_accounts", "v03_lan_river_compacts", "v03_lan_work_accident_fund"}


def _catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _native_journals():
    return {key: body for key, _, body in parse(NATIVE_JOURNAL_PATH.read_text(encoding="utf-8-sig"))}


def _catalog_journals():
    return {journal["id"]: journal for arc in _catalog()["arcs"] for journal in arc["journals"]}


def _lan_queue_candidates(branch_source):
    """Derive exact LAN queue predicates from a sender or its limit source."""
    roots = parse_block("{ " + branch_source + " }")
    if len(roots) != 1:
        raise ValueError("LAN candidate input must contain exactly one source node")
    node = roots[0]
    if node.key in {"if", "else_if"}:
        limits = direct_values(children(node), "limit")
        if len(limits) != 1:
            raise ValueError("LAN sender branch must have exactly one limit")
        limit_nodes = children(limits[0])
    elif node.key == "limit":
        limit_nodes = children(node)
    else:
        raise ValueError("LAN candidates require one sender branch or one limit block")
    found = []
    for leaf in _walk_positive_ast(limit_nodes):
        if (leaf.key.startswith("var:ywc_lan_") and leaf.op == "="
                and isinstance(leaf.value, str) and leaf.value.isdigit()):
            queue = leaf.key.removeprefix("var:")
            if queue.endswith("_pending_event"):
                kind = "normal"
            elif queue.endswith("_notice_event"):
                kind = "notice"
            else:
                continue
            found.append({"queue": queue, "kind": kind, "mode": "exact",
                          "value": int(leaf.value)})
    if len(found) != 1:
        raise ValueError(f"each LAN sender must bind exactly one positive queue candidate; got {found!r}")
    return found


def _walk_ast(nodes):
    for node in nodes:
        yield node
        if isinstance(node.value, tuple):
            yield from _walk_ast(node.value)


def _walk_positive_ast(nodes):
    for node in nodes:
        if node.key == "NOT":
            continue
        yield node
        if isinstance(node.value, tuple):
            yield from _walk_positive_ast(node.value)


def _v2_catalog_from_formal_lan_source():
    """Build a valid-shaped v2 candidate solely from the formal LAN catalog source."""
    catalog = copy.deepcopy(_catalog())
    for arc in catalog["arcs"]:
        phases, branches = [], []
        for journal in arc["journals"]:
            phase_slug = re.sub(r"[^a-z0-9_]+", "_", journal["id"].removeprefix("ywc_je_v03_lan_"))
            phases.append({
                "journal": journal["id"],
                "live_witness": f"ywc_v03_lan_inline_live_{phase_slug}",
                "source_script_sha256": hashlib.sha256(journal["script"].encode()).hexdigest(),
                "goal_sha256": hashlib.sha256(journal["goal"].encode()).hexdigest(),
                "exit_sha256": hashlib.sha256(journal["exit_conditions"].encode()).hexdigest(),
            })
            binding = _kor_source_binding(journal["id"], journal["script"],
                                          candidate_parser=_lan_queue_candidates)
            for source in binding["branches"]:
                branches.append({
                    "journal": journal["id"],
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
                    "queue_exclusions": source["queue_exclusions"],
                })
        arc["inline_delivery_adapter"] = {
            "schema": "v03.foundation_inline_adapter.v2",
            "live_phases": phases,
            "branches": branches,
            "direct_adds": _kor_direct_adds(arc),
        }
    return catalog


def _rebind_v2_catalog_source(catalog):
    """Rebuild every source binding after an in-memory native source mutation."""
    for arc in catalog["arcs"]:
        adapter = arc["inline_delivery_adapter"]
        phases, branches = [], []
        for journal in arc["journals"]:
            phase_slug = re.sub(r"[^a-z0-9_]+", "_", journal["id"].removeprefix("ywc_je_v03_lan_"))
            phases.append({
                "journal": journal["id"],
                "live_witness": f"ywc_v03_lan_inline_live_{phase_slug}",
                "source_script_sha256": hashlib.sha256(journal["script"].encode()).hexdigest(),
                "goal_sha256": hashlib.sha256(journal["goal"].encode()).hexdigest(),
                "exit_sha256": hashlib.sha256(journal["exit_conditions"].encode()).hexdigest(),
            })
            binding = _kor_source_binding(journal["id"], journal["script"],
                                          candidate_parser=_lan_queue_candidates)
            for source in binding["branches"]:
                branches.append({
                    "journal": journal["id"], "branch_index": source["branch_index"],
                    "statement_ordinal": source["statement_ordinal"],
                    "chain_index": source["chain_index"], "branch_kind": source["branch_kind"],
                    "event": source["event"], "branch_sha256": source["sha256"],
                    "limit_sha256": source["limit_sha256"], "chain_prior": source["chain_prior"],
                    "chain_sha256": source["chain_sha256"], "candidates": source["candidates"],
                    "queue_exclusions": source["queue_exclusions"],
                })
        adapter["live_phases"] = phases
        adapter["branches"] = branches
        adapter["direct_adds"] = _kor_direct_adds(arc)
    return catalog


class LanInlineAdapterStaticContractTest(unittest.TestCase):
    def test_exact_six_je_sender_inventory_and_shared_ids(self):
        native = _native_journals()
        sources = _catalog_journals()
        counts = {}
        ids = []
        for journal_id in COUNTS:
            binding = source_binding(journal_id, sources[journal_id]["script"])
            counts[journal_id] = len(binding["branches"])
            ids.extend(branch["event"] for branch in binding["branches"])
        self.assertEqual(counts, COUNTS)
        self.assertEqual(sum(counts.values()), 36)
        shared = {event for event in set(ids) if ids.count(event) > 1}
        self.assertEqual(shared, {"ywc_lan.1006", "ywc_lan.1007", "ywc_lan.1016",
                                  "ywc_lan.1017", "ywc_lan.1026", "ywc_lan.1027"})
        self.assertEqual(len(set(native) & set(COUNTS)), 6)
        self.assertEqual(len(native), 9)

    def test_three_arc_v2_per_arc_metadata_binds_all_live_phases_and_sender_spans(self):
        catalog = _catalog()
        foundation = [arc for arc in catalog["arcs"] if arc["era"] == "foundation"]
        self.assertEqual(len(catalog["arcs"]), 4)
        self.assertEqual(len(foundation), 3)
        self.assertEqual({arc["slug"] for arc in foundation}, ARC_SLUGS)
        for arc in foundation:
            with self.subTest(arc=arc["slug"]):
                adapter = arc.get("inline_delivery_adapter")
                self.assertIsInstance(adapter, dict,
                                      f"{arc['slug']} lacks per-arc inline_delivery_adapter metadata")
                self.assertEqual(adapter.get("schema"), "v03.foundation_inline_adapter.v2")
                self.assertEqual(len(adapter.get("live_phases", [])), 2)
                self.assertEqual(len(adapter.get("branches", [])),
                                 sum(COUNTS.get(journal["id"], 0) for journal in arc["journals"]))
                self.assertTrue(adapter.get("branches"), "source-bound branch records are required")
                journal_ids = {journal["id"] for journal in arc["journals"]}
                self.assertEqual({phase.get("journal") for phase in adapter["live_phases"]}, journal_ids)
                for phase in adapter["live_phases"]:
                    journal = next(j for j in arc["journals"] if j["id"] == phase["journal"])
                    for field, source in (("source_script_sha256", journal["script"]),
                                          ("goal_sha256", journal["goal"]),
                                          ("exit_sha256", journal["exit_conditions"])):
                        expected = hashlib.sha256(source.encode("utf-8")).hexdigest()
                        self.assertEqual(phase.get(field), expected, (arc["slug"], phase["journal"], field))
                by_journal = {}
                for branch in adapter["branches"]:
                    by_journal.setdefault(branch.get("journal"), []).append(branch)
                self.assertEqual(set(by_journal), journal_ids)
                for journal in arc["journals"]:
                    binding = _kor_source_binding(journal["id"], journal["script"],
                                                  candidate_parser=_lan_queue_candidates)
                    records = sorted(by_journal[journal["id"]], key=lambda row: row["branch_index"])
                    self.assertEqual(len(records), len(binding["branches"]))
                    for record, source in zip(records, binding["branches"]):
                        self.assertEqual(record.get("branch_index"), source["branch_index"])
                        self.assertEqual(record.get("statement_ordinal"), source["statement_ordinal"])
                        self.assertEqual(record.get("journal"), journal["id"])
                        self.assertEqual(record.get("event"), source["event"])
                        self.assertIn(record.get("event"), {event["id"] for event in arc["events"]})
                        self.assertIn(record.get("branch_kind"), {"if", "else_if"})
                        self.assertEqual(record.get("branch_sha256"), source["sha256"])
                        self.assertEqual(record.get("limit_sha256"), source["limit_sha256"])
                        self.assertEqual(record.get("candidates"),
                                         _lan_queue_candidates(source["limit_source"]),
                                         "native positive queue candidate bindings must match sender guards")

    def test_formal_v2_metadata_oracle_has_all_36_exact_source_candidates(self):
        catalog = _v2_catalog_from_formal_lan_source()
        arcs = catalog["arcs"]
        metadata = [branch for arc in arcs
                    for branch in arc["inline_delivery_adapter"]["branches"]]
        self.assertEqual(len(metadata), 46)
        self.assertEqual(sum(len(arc["inline_delivery_adapter"]["branches"]) for arc in arcs
                             if arc["era"] == "foundation"), 36)
        self.assertTrue(all(row["candidates"] for row in metadata),
                        "every native sender needs a positive queue candidate")
        self.assertEqual(sum(candidate["kind"] == "notice"
                             for row in metadata for candidate in row["candidates"]), 12)
        self.assertEqual(sum(candidate["kind"] == "normal"
                             for row in metadata for candidate in row["candidates"]), 34)
        notices = [candidate["value"] for row in metadata for candidate in row["candidates"]
                   if candidate["kind"] == "notice"]
        self.assertEqual(notices.count(12), 6)
        self.assertEqual(notices.count(36), 6)
        for arc in arcs:
            for journal in arc["journals"]:
                binding = _kor_source_binding(journal["id"], journal["script"],
                                              candidate_parser=_lan_queue_candidates)
                for source in binding["branches"]:
                    branch_source = journal["script"][source["start"]:source["end"]]
                    self.assertEqual(_lan_queue_candidates(branch_source),
                                     _lan_queue_candidates(source["limit_source"]),
                                     (journal["id"], source["branch_index"]))
                    candidate = _lan_queue_candidates(source["limit_source"])
                    self.assertEqual(len(candidate), 1)
                    self.assertEqual(candidate[0]["mode"], "exact")
                    self.assertIs(type(candidate[0]["value"]), int)

    def test_formal_source_v2_candidate_and_mutant_probes_reach_official_gate(self):
        catalog = _v2_catalog_from_formal_lan_source()
        total = sum(len(arc["inline_delivery_adapter"]["branches"]) for arc in catalog["arcs"])
        self.assertEqual(total, 46)
        validate_inline_catalog(catalog)
        self.assertEqual(len(render_inline_country_adapters(catalog)["event_hooks"]), 34)

        mutants = []
        wrong_queue = copy.deepcopy(catalog)
        wrong_queue["arcs"][0]["inline_delivery_adapter"]["branches"][0]["candidates"][0]["queue"] = "ywc_lan_wrong_queue"
        mutants.append(("wrong_queue", wrong_queue))
        wrong_hash = copy.deepcopy(catalog)
        wrong_hash["arcs"][0]["inline_delivery_adapter"]["branches"][0]["branch_sha256"] = "0" * 64
        mutants.append(("wrong_branch_hash", wrong_hash))
        missing = copy.deepcopy(catalog)
        missing["arcs"][0]["inline_delivery_adapter"]["branches"].pop(0)
        mutants.append(("missing_sender", missing))
        duplicate = copy.deepcopy(catalog)
        duplicate["arcs"][0]["inline_delivery_adapter"]["branches"].append(
            copy.deepcopy(duplicate["arcs"][0]["inline_delivery_adapter"]["branches"][0]))
        mutants.append(("duplicate_sender", duplicate))
        for label, mutant in mutants:
            with self.subTest(mutant=label):
                with self.assertRaises(ValueError) as validation:
                    validate_inline_catalog(mutant)
                with self.assertRaises(ValueError) as rendering:
                    render_inline_country_adapters(mutant)

    def test_native_helper_is_an_exact_single_definition_ast(self):
        helper = ("ywc_v03_mark_major_delivered = { if = { limit = { NOT = { "
                  "has_variable = ywc_v03_major_event_cooldown } } set_variable = { "
                  "name = ywc_v03_major_event_cooldown value = 1 days = 90 } } }")
        validate_lan_native_helper_source(helper)
        mutants = (
            helper.replace("has_variable = ywc_v03_major_event_cooldown",
                           "has_variable = ywc_v03_major_event_cooldown always = no", 1),
            helper.replace("days = 90", "days = 90 months = 1", 1),
            helper + "\nywc_v03_mark_major_delivered = { }",
        )
        for index, mutant in enumerate(mutants):
            with self.subTest(mutant=index):
                with self.assertRaises(ValueError):
                    validate_lan_native_helper_source(mutant)

    def test_rebound_notice_writes_reject_unmodeled_duration_fields(self):
        base = _v2_catalog_from_formal_lan_source()
        validate_inline_catalog(base)
        render_inline_country_adapters(base)
        cases = (
            ("name = ywc_lan_mine_notice_current value = 12", "days = 1"),
            ("name = ywc_lan_mine_notice12_sent value = 1", "months = 1"),
        )
        for source_fragment, extra_field in cases:
            with self.subTest(extra_field=extra_field):
                mutant = copy.deepcopy(base)
                journal = mutant["arcs"][0]["journals"][0]
                self.assertIn(source_fragment, journal["script"])
                journal["script"] = journal["script"].replace(
                    source_fragment, source_fragment + " " + extra_field, 1)
                rebound = _rebind_v2_catalog_source(mutant)
                with self.assertRaises(ValueError):
                    validate_inline_catalog(rebound)
                with self.assertRaises(ValueError):
                    render_inline_country_adapters(rebound)

    def test_rebound_nor_wrapped_notice_queue_is_rejected(self):
        base = _v2_catalog_from_formal_lan_source()
        validate_inline_catalog(base)
        render_inline_country_adapters(base)
        mutant = copy.deepcopy(base)
        journal = mutant["arcs"][0]["journals"][0]
        queue_predicate = "var:ywc_lan_mine_notice_event = 12"
        self.assertIn(queue_predicate, journal["script"])
        journal["script"] = journal["script"].replace(
            queue_predicate, f"NOR = {{ {queue_predicate} }}", 1)
        rebound = _rebind_v2_catalog_source(mutant)
        for api, validate in (("validator", validate_inline_catalog),
                              ("renderer", render_inline_country_adapters)):
            with self.subTest(api=api):
                with self.assertRaises(ValueError):
                    validate(rebound)

    def test_native_helper_full_file_layout_and_comment_controls(self):
        def assert_valid(source, label):
            try:
                validate_lan_native_helper_source(source)
            except ValueError as exc:
                self.fail(f"valid helper layout {label} was rejected: {exc}")

        formal_source = (ROOT / "yongchang_world/common/scripted_effects/ywc_v03_effects.txt").read_text(
            encoding="utf-8-sig")
        wrapped = "{\n" + formal_source + "\n}"
        top_level = parse_block(wrapped)
        helper_nodes = [node for node in top_level if node.key == "ywc_v03_mark_major_delivered"]
        self.assertEqual(len(helper_nodes), 1)
        helper_source = render_node(helper_nodes[0], wrapped)

        # A legal unrelated definition before the real helper on the same line
        # must not hide the unique target definition from source inventory.
        unrelated = "ywc_v03_layout_probe = { set_variable = { name = layout_probe value = 1 } }"
        same_line_helper = unrelated + " " + helper_source

        # Clausewitz comments are ignored by the parser, including braces in
        # comments inside the authentic helper body.
        commented_helper = helper_source.replace(
            "if = {", "if = { # harmless comment containing } brace\n", 1)
        self.assertNotEqual(commented_helper, helper_source)
        for label, valid_source in (("full formal file", formal_source),
                                    ("unrelated definition on preceding same line", same_line_helper),
                                    ("inline comment with a closing brace", commented_helper)):
            with self.subTest(valid_layout=label):
                assert_valid(valid_source, label)

        duplicate_layouts = (
            ("same_line", formal_source.rstrip() + " " + helper_source),
            ("adjacent", formal_source.rstrip() + "\n" + helper_source),
            ("comment_separated", formal_source.rstrip() + "\n# duplicate follows comment\n" + helper_source),
        )
        for layout, mutant in duplicate_layouts:
            with self.subTest(layout=layout):
                mutant_top_level = parse_block("{\n" + mutant + "\n}")
                self.assertEqual(sum(node.key == "ywc_v03_mark_major_delivered"
                                     for node in mutant_top_level), 2)
                with self.assertRaises(ValueError):
                    validate_lan_native_helper_source(mutant)

    def test_manifest_registers_formal_lan_helper_output_pair(self):
        manifest = json.loads((ROOT / "data/content/v03/manifest.json").read_text(encoding="utf-8"))
        owned = set(manifest.get("owned_outputs", []))
        self.assertIn("common/scripted_effects/ywc_v03_delivery_lan_effects.txt", owned,
                      "manifest must own the generated LAN delivery effects output")
        self.assertIn("common/scripted_triggers/ywc_v03_delivery_lan_triggers.txt", owned,
                      "manifest must own the generated LAN delivery triggers output")


if __name__ == "__main__":
    unittest.main()
