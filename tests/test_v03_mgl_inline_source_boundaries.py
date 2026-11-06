"""Permanent MGL source formatting and typed metadata boundary contracts."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import test_v03_mgl_inline_adapter as source
from tests.clausewitz_harness import parse
from tools import build_v03_content as global_builder
from tools import build_v03_country as country_builder
from tools.v03_inline_delivery_adapter import validate_inline_catalog, render_inline_country_adapters

ROOT = Path(__file__).resolve().parents[1]


def _definitions(text):
    return source._definitions_no_duplicates(text, "source boundary")


def _numeric_leaves(value, path):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _numeric_leaves(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _numeric_leaves(child, path + (index,))
    elif type(value) is int:
        yield path, value


def _category(path):
    if "chain_prior" in path:
        return "chain_prior." + path[-1]
    if "candidates" in path:
        return "candidate." + path[-1]
    return "branch." + path[-1]


def _final_outputs(catalog):
    # Supply one in-memory catalogue to each real public builder. File reads
    # for manifests, native registries and all builder logic remain real.
    with patch.object(global_builder, "load_catalogs", return_value={"country_mgl": catalog}):
        global_outputs = global_builder.render_all(ROOT)
    original_read = Path.read_text
    target = ROOT / "data/content/v03/countries/mgl.json"
    def read(path, *args, **kwargs):
        return json.dumps(catalog) if path == target else original_read(path, *args, **kwargs)
    with patch.object(Path, "read_text", read):
        country_outputs = country_builder.render_country(ROOT, "country_mgl")
    return global_outputs, country_outputs


class MglInlineSourceBoundaryContracts(unittest.TestCase):
    def _positive(self):
        catalog = source._v2_catalog_from_formal_mgl_source()
        validate_inline_catalog(catalog)
        rendered = render_inline_country_adapters(catalog)
        self.assertEqual(len(rendered["event_hooks"]), 24)
        return catalog, rendered

    def test_positive_public_helpers_and_both_final_builders_parse(self):
        catalog, rendered = self._positive()
        self.assertTrue(_definitions(rendered["effects"]))
        self.assertTrue(_definitions(rendered["triggers"]))
        global_outputs, country_outputs = _final_outputs(catalog)
        self.assertEqual(global_outputs, country_outputs)
        self.assertEqual(len(global_outputs), 6)
        for path, text in global_outputs.items():
            if str(path).endswith(".txt"):
                self.assertTrue(parse(text), str(path))

    def _comments(self, field):
        catalog, baseline = self._positive()
        native_events = [event for arc in catalog["arcs"] for event in arc["events"]]
        self.assertEqual(len(native_events), 24)
        baseline_events = _definitions(global_builder._render_event_file(catalog, ROOT, baseline))
        baseline_helpers = {key: _definitions(baseline[key]) for key in ("effects", "triggers")}
        for event in native_events:
            with self.subTest(event=event["id"], field=field):
                mutated = copy.deepcopy(catalog)
                chosen = next(e for arc in mutated["arcs"] for e in arc["events"] if e["id"] == event["id"])
                text = chosen[field]
                closing = text.rfind("}")
                self.assertGreaterEqual(closing, 0)
                chosen[field] = text[:closing] + " # trailing comment\n" + text[closing:]
                self.assertEqual(parse(field + " = " + text), parse(field + " = " + chosen[field]))
                validate_inline_catalog(mutated)
                rendered = render_inline_country_adapters(mutated)
                faults = []
                # Continue independent checks after a failure, so helper faults
                # cannot hide final wrapper parse or native-body regressions.
                def check(label, action):
                    try:
                        action()
                    except Exception as exc:
                        faults.append(f"{label}: {type(exc).__name__}: {exc}")
                for key in ("effects", "triggers"):
                    check("raw helper bytes " + key, lambda key=key: self.assertTrue(
                        rendered[key] == baseline[key], "helper text changed: " + key))
                    check("full helper " + key, lambda key=key: self.assertEqual(_definitions(rendered[key]), baseline_helpers[key]))
                def event_body():
                    events = _definitions(global_builder._render_event_file(mutated, ROOT, rendered))
                    self.assertEqual(events, baseline_events)
                    body = next(v for k, _, v in events[event["id"]] if k == "immediate")
                    self.assertEqual(len(body), 1)
                    self.assertEqual(body[0][:2], ("if", "="))
                    guarded = body[0][2]
                    native = parse("immediate = " + event["immediate"])[0][2]
                    self.assertEqual(guarded[0][0], "limit")
                    self.assertEqual(guarded[1:1 + len(native)], native)
                    suffix = parse(" ".join(rendered["inline_proofs"][event["id"]]) + " " +
                                   " ".join(f"{name} = yes" for name in rendered["ack_hooks"][event["id"]]))
                    self.assertTrue(suffix)
                    self.assertEqual(guarded[1 + len(native):], suffix)
                check("full event native prefix/proof/ACK", event_body)
                def final_wrappers():
                    global_outputs, country_outputs = _final_outputs(mutated)
                    self.assertEqual(global_outputs, country_outputs)
                    parse_faults = []
                    for builder, outputs in (("global", global_outputs), ("country", country_outputs)):
                        for path, output in outputs.items():
                            if str(path).endswith(".txt"):
                                try:
                                    parse(output)
                                except Exception as exc:
                                    parse_faults.append(f"{builder}/{path}: {type(exc).__name__}: {exc}")
                    self.assertEqual(parse_faults, [])
                check("both final wrappers", final_wrappers)
                self.assertEqual(faults, [], "\n".join(faults))

    def test_all_24_native_trigger_trailing_comments_preserve_asts(self):
        self._comments("trigger")

    def test_all_24_native_immediate_trailing_comments_preserve_full_body_and_ack(self):
        self._comments("immediate")

    def test_actual_nested_integer_metadata_rejects_numeric_aliases(self):
        catalog, _ = self._positive()
        leaves = [row for index, arc in enumerate(catalog["arcs"])
                  for row in _numeric_leaves(arc["inline_delivery_adapter"], ("arcs", index, "inline_delivery_adapter"))]
        self.assertEqual(len(leaves), 594)
        cases = [(path, value, alias) for path, value in leaves
                 for alias in ([float(value), bool(value)] if value in (0, 1) else [float(value)])]
        self.assertEqual(len(cases), 738)
        representatives = {}
        for path, value, alias in cases:
            representatives.setdefault((_category(path), type(alias)), (path, value, alias))
        self.assertEqual({key[0] for key in representatives}, {"branch.branch_index", "branch.statement_ordinal",
                         "branch.chain_index", "candidate.value", "chain_prior.ordinal"})
        def reject(api, path, value, alias):
            mutated = copy.deepcopy(catalog)
            parent = mutated
            for step in path[:-1]:
                parent = parent[step]
            self.assertIs(type(parent[path[-1]]), int)
            self.assertEqual(parent[path[-1]], value)
            parent[path[-1]] = alias
            try:
                api(mutated)
            except ValueError:
                return
            except Exception as exc:
                self.fail(f"unexpected rejection at {path}: {type(exc).__name__}: {exc}")
            self.fail(f"accepted source metadata alias at {path}: {value!r} -> {alias!r} ({type(alias).__name__})")
        for path, value, alias in cases:
            with self.subTest(api="validate", path=path, alias_type=type(alias).__name__):
                reject(validate_inline_catalog, path, value, alias)
        # Renderer invokes the same validator; cover each actual category/type
        # once rather than regenerating all helpers for every metadata leaf.
        self.assertEqual(len(representatives), 9)
        for path, value, alias in representatives.values():
            with self.subTest(api="render", path=path, alias_type=type(alias).__name__):
                reject(render_inline_country_adapters, path, value, alias)


if __name__ == "__main__":
    unittest.main()
