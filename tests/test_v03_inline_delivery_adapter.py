import json
import subprocess
import unittest
from pathlib import Path

from tools.v03_inline_delivery_adapter import inject_limit_guard, parse_block, queue_candidates, render_inline_country_adapters, source_binding, trigger_event_ids

ROOT = Path(__file__).resolve().parents[1]


class InlineSourceParserTests(unittest.TestCase):
    def test_rejects_incomplete_and_unsupported_structure(self):
        for source in ('{ if = {', '{ a = }', '{ a b }', '{ a = { b = 1 } } trailing', '{ a = @ }', '{ a = = }', '{ >= = x }'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse_block(source)

    def test_parses_nested_operator_nodes_and_exact_event_ids(self):
        source = '{ if = { limit = { c:DMG ?= this var:x >= 0 } trigger_event = { id = ywc_dmg.1000 } } }'
        node = parse_block(source)[0]
        self.assertEqual(node.key, "if")
        self.assertEqual(trigger_event_ids((node,)), ["ywc_dmg.1000"])
        self.assertEqual(parse_block("{ c:DMG ?= this }")[0].op, "?=")

    def test_rejects_unsupported_sender_ownership_and_duplicate_branches(self):
        cases = {
            "duplicate identical sender": "{ on_monthly_pulse = { effect = { if = { limit = { var:q = 1 } trigger_event = { id = ywc_dmg.1000 } } if = { limit = { var:q = 1 } trigger_event = { id = ywc_dmg.1000 } } } } }",
            "effect-level trigger": "{ on_monthly_pulse = { effect = { trigger_event = { id = ywc_dmg.1000 } } } }",
            "arbitrary nested sender": "{ on_monthly_pulse = { effect = { scope:foo = { if = { limit = { var:q = 1 } trigger_event = { id = ywc_dmg.1000 } } } } }",
            "orphan else_if": "{ on_monthly_pulse = { effect = { else_if = { limit = { var:q = 1 } trigger_event = { id = ywc_dmg.1000 } } } } }",
        }
        for label, source in cases.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                source_binding("strict-fixture", source)

    def test_preserves_non_sender_helper_with_no_trigger_event(self):
        source = "{ on_monthly_pulse = { effect = { custom_effect = { value = 1 } if = { limit = { var:q = 1 } trigger_event = { id = ywc_dmg.1000 } } } } }"
        self.assertEqual(len(source_binding("helper-fixture", source)["branches"]), 1)

    def test_queue_candidate_extraction_ignores_negative_notice_conditions(self):
        source = "limit = { var:ywc_dmg_pending_event = 1009 NOT = { has_variable = ywc_dmg_review_blocked_12_notice } OR = { has_variable = ywc_dmg_review_blocked_36_notice has_variable = ywc_dmg_review_state_lost_notice } }"
        candidates = queue_candidates(source)
        self.assertEqual({(c["queue"], c["kind"]) for c in candidates}, {
            ("ywc_dmg_pending_event", "normal"),
            ("ywc_dmg_review_blocked_36_notice", "notice36"),
            ("ywc_dmg_review_state_lost_notice", "notice12"),
        })

    def test_splice_changes_only_bound_limit_span_and_rejects_drift(self):
        script = "{ on_monthly_pulse = { effect = { if = { limit = { var:q = 1 } remove_variable = q trigger_event = { id = ywc_dmg.1000 } } set_variable = { name = untouched value = 1 } } } }"
        binding = source_binding("je", script)["branches"][0]
        changed = inject_limit_guard(script, binding, "ywc_v03_dispatch = yes")
        self.assertIn("var:q = 1 ywc_v03_dispatch = yes", changed)
        self.assertIn("set_variable = { name = untouched value = 1 }", changed)
        stale = dict(binding, sha256="0" * 64)
        with self.assertRaises(ValueError):
            inject_limit_guard(script, stale, "ywc_v03_dispatch = yes")

    def test_binds_all_real_dmg_inline_sender_nodes(self):
        catalog = json.loads((ROOT / "data/content/v03/countries/dmg.json").read_text(encoding="utf-8-sig"))
        bindings = [source_binding(j["id"], j["script"]) for a in catalog["arcs"] for j in a["journals"]]
        foundation = [source_binding(j["id"], j["script"]) for a in catalog["arcs"]
                      if a["era"] == "foundation" for j in a["journals"]]
        self.assertEqual(sum(len(item["branches"]) for item in foundation), 29)
        self.assertEqual(len({item["journal"] for item in foundation}), 6)
        old_arcs = [a for a in catalog["arcs"] if a["slug"] != "v03_dmg_representative_crown"]
        previous = json.loads(subprocess.run(
            ["git", "show", "9980153ba0edb9c48f141df84c11b2f530ab39b6:data/content/v03/countries/dmg.json"],
            cwd=ROOT, check=True, capture_output=True).stdout.decode("utf-8-sig"))
        self.assertEqual(old_arcs, previous["arcs"], "all five old cards and exact source proofs are preserved")
        old_bindings = [source_binding(j["id"], j["script"]) for a in old_arcs for j in a["journals"]]
        self.assertEqual(sum(len(item["branches"]) for item in old_bindings), 43)
        self.assertEqual(len(old_bindings), 9)
        crown = next(a for a in catalog["arcs"] if a["slug"] == "v03_dmg_representative_crown")
        self.assertEqual(len(crown["journals"]), 3)
        self.assertEqual({e["id"] for e in crown["events"]}, {f"ywc_dmg.{n}" for n in range(1110, 1120)})
        self.assertEqual(sum(len(item["branches"]) for item in bindings), 53)
        self.assertEqual(len({item["journal"] for item in bindings}), 12)
        self.assertEqual(sum(b["event"] == "ywc_dmg.1015" for item in bindings for b in item["branches"]), 3)
        self.assertTrue(all(len(b["sha256"]) == 64 and b["end"] > b["start"] for item in bindings for b in item["branches"]))
        candidates = [queue_candidates(b["limit_source"]) for item in bindings for b in item["branches"]]
        self.assertEqual(sum(map(len, candidates)), 72)
        self.assertTrue(all(candidates), "every actual sender branch has a source-backed queue"); self.assertTrue(any(c["kind"] == "notice12" for group in candidates for c in group)); self.assertTrue(any(c["kind"] == "notice36" for group in candidates for c in group)); self.assertTrue(any(c["mode"] == "presence" for group in candidates for c in group)); self.assertTrue(any(c["mode"] == "exact" for group in candidates for c in group))

    def test_rendered_dispatch_rechecks_exact_captured_queue_before_native_immediate(self):
        catalog = json.loads((ROOT / "data/content/v03/countries/dmg.json").read_text(encoding="utf-8-sig"))
        rendered = render_inline_country_adapters(catalog)
        self.assertEqual(len(rendered["journal_scripts"]), 12)
        number = 0
        for arc in catalog["arcs"]:
            if arc.get("era") != "foundation":
                continue
            arc_queues = {
                candidate["queue"]
                for branch in arc["inline_delivery_adapter"]["branches"]
                for candidate in branch["candidates"]
                if candidate["kind"].startswith("notice")
            }
            tracked = set(arc_queues)
            tracked.update(queue.replace("_notice", "_delivered") for queue in arc_queues
                           if queue.endswith("_blocked_12_notice") or queue.endswith("_blocked_36_notice"))
            for proof in arc["inline_delivery_adapter"]["branches"]:
                for candidate in proof["candidates"]:
                    number += 1
                    queue = candidate["queue"]
                    value_name = f"ywc_v03_dmg_inline_c{number}_{queue.removeprefix('ywc_dmg_')}_value"
                    present_name = f"ywc_v03_dmg_inline_c{number}_{queue.removeprefix('ywc_dmg_')}_present"
                    dispatch = next(line for line in rendered["triggers"].splitlines()
                                    if line.startswith(f"ywc_v03_dmg_inline_dispatch_{number} = {{"))
                    self.assertIn(f"ywc_v03_dmg_inline_candidate_{number} = yes", dispatch)
                    self.assertIn(f"has_variable = {present_name}", dispatch)
                    self.assertIn(f"has_variable = {value_name}", dispatch)
                    self.assertIn(f"has_variable = {queue}", dispatch)
                    self.assertIn(f"var:{queue} = var:{value_name}", dispatch)
                    self.assertIn("NOT = { var:ywc_v03_dmg_inline_served_", dispatch)
                    self.assertIn("= var:ywc_v03_dmg_inline_round }", dispatch)
                    for sibling in tracked:
                        sibling_present = f"ywc_v03_dmg_inline_c{number}_{sibling.removeprefix('ywc_dmg_')}_present"
                        sibling_value = f"ywc_v03_dmg_inline_c{number}_{sibling.removeprefix('ywc_dmg_')}_value"
                        self.assertIn(f"has_variable = {sibling_present}", dispatch)
                        self.assertIn(f"has_variable = {sibling_value}", dispatch)
                        self.assertIn(f"var:{sibling} = var:{sibling_value}", dispatch)
                        self.assertIn(f"NOT = {{ has_variable = {sibling} }}", dispatch)
        self.assertEqual(number, 48)
        # The original foundation snapshot remains exactly48; registered
        # school/market/crown queues append after it without renumbering.
        middle = ([(n, "ywc_dmg_school_pending_event", eid) for n, eid in zip(range(49, 55), range(1120, 1126))]
                  + [(n, "ywc_dmg_market_pending_event", eid) for n, eid in zip(range(55, 63), range(1100, 1108))]
                  + [(n, "ywc_dmg_crown_pending_event", eid) for n, eid in zip(range(63, 73), range(1110, 1120))])
        for ident, queue, event_number in middle:
            value_name = f"ywc_v03_dmg_inline_c{ident}_{queue.removeprefix('ywc_dmg_')}_value"
            present_name = f"ywc_v03_dmg_inline_c{ident}_{queue.removeprefix('ywc_dmg_')}_present"
            dispatch = next(line for line in rendered["triggers"].splitlines()
                            if line.startswith(f"ywc_v03_dmg_inline_dispatch_{ident} = {{"))
            candidate = next(line for line in rendered["triggers"].splitlines()
                             if line.startswith(f"ywc_v03_dmg_inline_candidate_{ident} = {{"))
            self.assertIn(f"has_variable = {present_name}", dispatch)
            self.assertIn(f"has_variable = {value_name}", dispatch)
            self.assertIn(f"var:{queue} = var:{value_name}", dispatch)
            self.assertIn(f"var:{queue} = {event_number}", candidate)


if __name__ == "__main__":
    unittest.main()
