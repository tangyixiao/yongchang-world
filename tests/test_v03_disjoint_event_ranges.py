"""Disjoint address reservations; no partner-response content is implemented here."""
import copy
import json
import pathlib
import tempfile
import unittest

from test_v03_catalog import catalog
from test_v03_generator import write_fixture
from tools.build_v03_content import build, render_all, validate_catalogs_at


ROOT = pathlib.Path(__file__).resolve().parents[1]


def read_registry(root):
    return json.loads((root / "data/content/v03/id_registry.json").read_text(encoding="utf-8"))


def write_registry(root, registry):
    (root / "data/content/v03/id_registry.json").write_text(json.dumps(registry), encoding="utf-8")


class V03DisjointEventRangeTests(unittest.TestCase):
    def test_old_shape_remains_valid_and_extra_capacity_does_not_change_rendering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write_fixture(root)
            self.assertEqual(validate_catalogs_at(root, {"country_shu": catalog()}), [])
            before = render_all(root)
            registry = read_registry(root)
            registry["arc_ranges"][0]["additional_ranges"] = [{"start": 1030, "end": 1039}]
            write_registry(root, registry)
            self.assertEqual(validate_catalogs_at(root, {"country_shu": catalog()}), [])
            self.assertEqual(render_all(root), before)

    def test_new_kor_nqg_and_jhg_segment_boundaries_are_accepted_and_built(self):
        segments = (("KOR", "v03_kor_military_accounts", 1000, 1009, 1030, 1039),
                    ("NQG", "v03_nqg_winter_court", 1000, 1009, 1030, 1039),
                    ("JHG", "v03_jhg_convoy_capacity", 1010, 1019, 1030, 1032))
        for tag, slug, primary_start, primary_end, extra_start, extra_end in segments:
            for number in (primary_start, primary_end, extra_start, extra_end):
                with self.subTest(tag=tag, number=number), tempfile.TemporaryDirectory() as temp:
                    root = pathlib.Path(temp)
                    write_fixture(root)
                    key, namespace = f"country_{tag.lower()}", f"ywc_{tag.lower()}"
                    value = catalog()
                    value.update(key=key, runtime_tags=[tag])
                    arc = value["arcs"][0]
                    arc.update(slug=slug, participants=[tag])
                    arc["journals"][0]["id"] = f"ywc_je_v03_{tag.lower()}_probe_main"
                    identifier = f"{namespace}.{number}"
                    arc["events"][0]["id"] = identifier
                    registry = read_registry(root)
                    registry["reservations"][0].update(key=key, namespace=namespace)
                    registry["arc_ranges"][0].update(catalog_key=key, slug=slug, namespace=namespace,
                                                    start=primary_start, end=primary_end,
                                                    additional_ranges=[{"start": extra_start, "end": extra_end}])
                    write_registry(root, registry)
                    # The existing fixture manifest deliberately still points at shu.json.
                    (root / "data/content/v03/countries/shu.json").write_text(json.dumps(value), encoding="utf-8")
                    manifest_path = root / "data/content/v03/manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["owned_outputs"] = [path.replace("country_shu", key) for path in manifest["owned_outputs"]]
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                    self.assertEqual(validate_catalogs_at(root, {key: value}), [])
                    self.assertEqual(build(root), [])
                    script = (root / f"yongchang_world/events/ywc_v03_{key}_events.txt").read_text(encoding="utf-8-sig")
                    self.assertIn(f"{identifier} = {{", script)
                    localization = (root / f"yongchang_world/localization/english/ywc_v03_{key}_l_english.yml").read_text(encoding="utf-8-sig")
                    self.assertIn(f'{identifier}.t:0 "测试事件"', localization)

    def test_live_allocations_preserve_all_original_foundation_fields(self):
        registry = read_registry(ROOT)
        historical = json.loads((ROOT / "tests/fixtures/v03_foundation_id_registry.json").read_text(encoding="utf-8"))
        foundation = copy.deepcopy(registry["arc_ranges"][:30])
        expected = {("country_kor", "v03_kor_military_accounts"): ("ywc_kor", 1039),
                    ("country_nqg", "v03_nqg_winter_court"): ("ywc_nqg", 1039),
                    ("country_jhg", "v03_jhg_convoy_capacity"): ("ywc_jhg", 1032)}
        actual = {(row["catalog_key"], row["slug"]): row for row in registry["arc_ranges"] if "additional_ranges" in row}
        self.assertEqual(set(actual), set(expected))
        for row in foundation:
            pair = (row["catalog_key"], row["slug"])
            if pair in expected:
                namespace, end = expected[pair]
                self.assertEqual(row["namespace"], namespace)
                self.assertEqual(row.pop("additional_ranges"), [{"start": 1030, "end": end}])
        self.assertEqual(foundation, historical["arc_ranges"])
        self.assertEqual(registry["namespace_limits"], historical["namespace_limits"])
        self.assertEqual(registry["reservations"], historical["reservations"])
        self.assertEqual(len(registry["arc_ranges"]), 90)

    def test_malformed_segments_collect_diagnostics(self):
        cases = {
            "null_list": None, "object_list": {}, "string_list": "1030-1039", "empty_list": [],
            "null_item": [None], "array_item": [[1030, 1039]], "string_item": ["1030"],
            "missing_start": [{"end": 1039}], "missing_end": [{"start": 1030}],
            "unknown_field": [{"start": 1030, "end": 1039, "extra": 1}],
            "namespace_override": [{"start": 1030, "end": 1039, "namespace": "ywc_nqg"}],
            "catalog_override": [{"start": 1030, "end": 1039, "catalog_key": "country_nqg"}],
            "owner_override": [{"start": 1030, "end": 1039, "owner": "NQG"}],
            "bool_start": [{"start": True, "end": 1039}], "bool_end": [{"start": 1030, "end": False}],
            "float_start": [{"start": 1030.0, "end": 1039}], "string_end": [{"start": 1030, "end": "1039"}],
            "reversed": [{"start": 1039, "end": 1030}],
            "below_namespace": [{"start": 999, "end": 999}], "above_namespace": [{"start": 2000, "end": 2009}],
            "mixed_valid_invalid": [{"start": 1030, "end": 1039}, None, {"start": 1040, "end": False}],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write_fixture(root)
            baseline = read_registry(root)
            for name, extras in cases.items():
                with self.subTest(case=name):
                    registry = copy.deepcopy(baseline)
                    registry["arc_ranges"][0]["additional_ranges"] = extras
                    write_registry(root, registry)
                    errors = validate_catalogs_at(root, {"country_shu": catalog()})
                    self.assertTrue(errors, errors)
                    self.assertTrue(any("additional_ranges" in error for error in errors), errors)
                    if name == "mixed_valid_invalid":
                        self.assertGreaterEqual(len(errors), 2, errors)

    def test_all_segments_participate_in_inclusive_overlap_checks(self):
        cases = (
            ("own_primary", [{"start": 1009, "end": 1019}], None, True),
            ("duplicate_extra", [{"start": 1030, "end": 1039}] * 2, None, True),
            ("extra_endpoint", [{"start": 1030, "end": 1039}, {"start": 1039, "end": 1049}], None, True),
            ("other_primary", [{"start": 1030, "end": 1039}], (1039, 1049, None, "ywc_shu"), True),
            ("other_extra", [{"start": 1030, "end": 1039}], (1050, 1059, [{"start": 1035, "end": 1040}], "ywc_shu"), True),
            ("other_extra_own_primary", [{"start": 1030, "end": 1039}], (1050, 1059, [{"start": 1000, "end": 1001}], "ywc_shu"), True),
            ("adjacent_primary", [{"start": 1010, "end": 1019}], None, False),
            ("adjacent_extras", [{"start": 1030, "end": 1039}, {"start": 1040, "end": 1049}], None, False),
            ("adjacent_other_arc", [{"start": 1030, "end": 1039}], (1040, 1049, None, "ywc_shu"), False),
            ("different_namespace", [{"start": 1030, "end": 1039}], (1000, 1009, [{"start": 1030, "end": 1039}], "ywc_nqg"), False),
        )
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write_fixture(root)
            baseline = read_registry(root)
            for name, extras, other, overlap in cases:
                with self.subTest(case=name):
                    registry = copy.deepcopy(baseline)
                    registry["arc_ranges"][0]["additional_ranges"] = extras
                    if other:
                        start, end, additional, namespace = other
                        key = "country_nqg" if namespace == "ywc_nqg" else "country_shu"
                        if key == "country_nqg":
                            registry["reservations"].append({"key": key, "layer": "country", "namespace": namespace})
                        row = {"catalog_key": key, "slug": "other_arc", "namespace": namespace, "start": start, "end": end}
                        if additional is not None:
                            row["additional_ranges"] = additional
                        registry["arc_ranges"].append(row)
                    write_registry(root, registry)
                    errors = validate_catalogs_at(root, {"country_shu": catalog()})
                    if overlap:
                        self.assertTrue(any("overlapping ID arc ranges" in error for error in errors), errors)
                    else:
                        self.assertEqual(errors, [])

    def test_membership_rejects_gaps_borrowing_wrong_namespace_and_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write_fixture(root)
            registry = read_registry(root)
            registry["arc_ranges"][0]["additional_ranges"] = [{"start": 1030, "end": 1039}]
            registry["arc_ranges"].append({"catalog_key": "country_shu", "slug": "other_arc", "namespace": "ywc_shu",
                                            "start": 1020, "end": 1029, "additional_ranges": [{"start": 1040, "end": 1049}]})
            write_registry(root, registry)
            for name, identifier, diagnostic in (
                ("gap", "ywc_shu.1010", "outside explicit arc range"),
                ("borrow_primary", "ywc_shu.1020", "outside explicit arc range"),
                ("borrow_extra", "ywc_shu.1040", "outside explicit arc range"),
                ("wrong_namespace", "ywc_nqg.1030", "registered event namespace"),
            ):
                with self.subTest(case=name):
                    value = catalog()
                    value["arcs"][0]["events"][0]["id"] = identifier
                    errors = validate_catalogs_at(root, {"country_shu": value})
                    self.assertTrue(any(diagnostic in error for error in errors), errors)
            value = catalog()
            event = value["arcs"][0]["events"][0]
            event["id"] = "ywc_shu.1030"
            value["arcs"][0]["events"].append(copy.deepcopy(event))
            self.assertTrue(any("duplicate ID ywc_shu.1030" in error for error in validate_catalogs_at(root, {"country_shu": value})))
            for name, mutate, diagnostic in (
                ("duplicate_row", lambda rows: rows.append(copy.deepcopy(rows[0])), "duplicate ID range for arc"),
                ("parent_unknown_field", lambda rows: rows[0].update(extra=True), "invalid ID arc range fields"),
                ("parent_missing_start", lambda rows: rows[0].pop("start"), "invalid ID arc range"),
                ("parent_namespace", lambda rows: rows[0].update(namespace="ywc_nqg"), "does not match catalog reservation"),
            ):
                with self.subTest(case=name):
                    changed = copy.deepcopy(registry)
                    mutate(changed["arc_ranges"])
                    write_registry(root, changed)
                    errors = validate_catalogs_at(root, {"country_shu": catalog()})
                    self.assertTrue(any(diagnostic in error for error in errors), errors)

    def test_authored_non_country_extras_cannot_escape_fixed_owner_slot(self):
        for layer, owner, namespace, escape in (("crisis", "C01", "ywc_crisis", 1100),
                                                 ("regional", "CHI", "ywc_regional", 1100),
                                                 ("theme", "T01", "ywc_society", 1050)):
            with self.subTest(layer=layer), tempfile.TemporaryDirectory() as temp:
                root = pathlib.Path(temp)
                write_fixture(root)
                value = catalog()
                key, slug = f"{layer}_sample", f"{layer}_sample_arc"
                value.update(key=key, layer=layer, runtime_tags=["CHI"])
                value["arcs"][0].update(slug=slug, owner=owner, participants=["CHI"])
                value["arcs"][0]["journals"][0]["id"] = f"ywc_je_v03_{owner.lower()}_sample_main"
                value["arcs"][0]["events"][0]["id"] = f"{namespace}.1030"
                registry = read_registry(root)
                registry["reservations"] = [{"key": key, "layer": layer, "namespace": namespace}]
                registry["arc_ranges"] = [{"catalog_key": key, "slug": slug, "namespace": namespace,
                                            "start": 1000, "end": 1009, "additional_ranges": [{"start": 1030, "end": 1039}]}]
                write_registry(root, registry)
                self.assertEqual(validate_catalogs_at(root, {key: value}), [])
                registry["arc_ranges"][0]["additional_ranges"] = [{"start": escape, "end": escape + 9}]
                value["arcs"][0]["events"][0]["id"] = f"{namespace}.{escape}"
                write_registry(root, registry)
                errors = validate_catalogs_at(root, {key: value})
                self.assertTrue(any(f"fixed {layer} owner {owner} slot" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
