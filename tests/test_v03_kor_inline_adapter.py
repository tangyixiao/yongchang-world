"""KOR source-binding and adapter schema regression tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from tools.v03_inline_delivery_adapter import parse_block, validate_inline_catalog


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/content/v03/countries/kor.json"


def _catalog():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


class KorInlineAdapterTests(unittest.TestCase):
    def test_relational_comparators_are_parsed_as_real_clausewitz_operators(self):
        nodes = parse_block("{ check = { var:amount < 1.5 var:other > 0 } }")
        check = nodes[0].value
        self.assertEqual([node.op for node in check], ["<", ">"])
        self.assertEqual([node.value for node in check], ["1.5", "0"])

    def test_complete_native_sender_inventory_and_ports_1022_chain(self):
        catalog = _catalog()
        validate_inline_catalog(catalog)
        ports = next(arc for arc in catalog["arcs"] if arc["slug"] == "v03_kor_controlled_ports")
        bindings = ports["inline_delivery_adapter"]["branches"]
        sites = [row for row in bindings if row["event"] == "ywc_kor.1022"]
        self.assertEqual([(row["branch_index"], row["statement_ordinal"], row["branch_kind"])
                          for row in sites], [(0, 2, "if"), (5, 7, "else_if"), (6, 8, "else_if")])
        self.assertEqual(sites[0]["candidates"], sites[1]["candidates"])
        self.assertTrue(sites[1]["chain_prior"])
        self.assertNotEqual(sites[2]["candidates"], sites[0]["candidates"])

    def test_direct_add_site_ordinal_rejects_bool_even_though_bool_is_int_subclass(self):
        catalog = _catalog()
        adapter = next(arc["inline_delivery_adapter"] for arc in catalog["arcs"]
                       if arc["slug"] == "v03_kor_school_factions")
        record = adapter["direct_adds"][0]
        forged = copy.deepcopy(catalog)
        target = next(arc for arc in forged["arcs"] if arc["slug"] == "v03_kor_school_factions")
        target["inline_delivery_adapter"]["direct_adds"][0]["site_ordinal"] = False
        with self.assertRaisesRegex(ValueError, "direct-add ordinal must be an integer"):
            validate_inline_catalog(forged)
        self.assertIs(type(record["site_ordinal"]), int)

    def test_direct_add_schema_and_hashes_are_exact(self):
        for change, message in (
            (lambda row: row.update(unreviewed=True), "malformed direct-add source binding"),
            (lambda row: row.update(effect_sha256="x"), "direct-add source hashes are malformed"),
        ):
            forged = _catalog()
            arc = next(row for row in forged["arcs"] if row["slug"] == "v03_kor_school_factions")
            change(arc["inline_delivery_adapter"]["direct_adds"][0])
            with self.assertRaisesRegex(ValueError, message):
                validate_inline_catalog(forged)

    def test_adapter_and_witness_metadata_fail_closed_on_unknown_fields_and_aliases(self):
        forged = _catalog()
        arc = next(row for row in forged["arcs"] if row["slug"] == "v03_kor_school_factions")
        arc["inline_delivery_adapter"]["unreviewed"] = True
        with self.assertRaisesRegex(ValueError, "v2 inline adapter schema"):
            validate_inline_catalog(forged)

        forged = _catalog()
        arc = next(row for row in forged["arcs"] if row["slug"] == "v03_kor_school_factions")
        other = next(row for row in forged["arcs"] if row["slug"] == "v03_kor_controlled_ports")
        arc["inline_delivery_adapter"]["live_phases"][0]["live_witness"] = other["inline_delivery_adapter"]["live_phases"][0]["live_witness"]
        with self.assertRaisesRegex(ValueError, "invalid live witness name"):
            validate_inline_catalog(forged)


if __name__ == "__main__":
    unittest.main()
