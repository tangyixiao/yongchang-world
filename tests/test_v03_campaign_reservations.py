"""B0 reservations and complete-campaign era contract."""
import json
import copy
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from test_v03_catalog import catalog
from test_v03_generator import write_fixture
from tools.build_v03_content import COUNTRY_NAMESPACES, load_catalogs, validate_catalogs_at
from tools.v03_owners import COUNTRY_TAGS
from tools.ywc_v03_check import check_complete_quotas


ROOT = Path(__file__).resolve().parents[1]
FOUNDATION_REGISTRY_PATH = ROOT / "tests/fixtures/v03_foundation_id_registry.json"
REGISTRY_PATH = ROOT / "data/content/v03/id_registry.json"
SPEC_PATH = ROOT / "docs/superpowers/specs/2026-10-14-v0.3-十国长线内容目录.md"
CANONICAL_ERAS = ("foundation", "middle", "late")


def markdown_country_reservations():
    rows = []
    for line in SPEC_PATH.read_text(encoding="utf-8-sig").splitlines():
        match = re.match(r"\|\s*(扩展|韧性)\s*\|\s*`(v03_[a-z0-9_]+)`", line)
        if match:
            era = {"扩展": "middle", "韧性": "late"}[match.group(1)]
            slug = match.group(2)
            country = slug.split("_")[1]
            rows.append((country, era, slug))
    return rows


def registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def write_registry(root, value):
    path = root / "data/content/v03/id_registry.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def era_fixture(eras_by_country=None):
    eras_by_country = eras_by_country or {
        tag: tuple(era for era in CANONICAL_ERAS for _ in range(3)) for tag in COUNTRY_TAGS
    }
    catalogs = {}
    for tag in COUNTRY_TAGS:
        eras = eras_by_country[tag]
        arcs = []
        for index, era in enumerate(eras):
            arcs.append({"era": era, "events": [VISIBLE_EVENT_SLOT] * 8, "journals": [None] * 2})
        catalogs[f"country_{tag.lower()}"] = {
            "key": f"country_{tag.lower()}", "layer": "country", "runtime_tags": [tag], "arcs": arcs,
        }
    return catalogs


# Placeholder events counted as visible (non-hidden) by the substantive quota.
VISIBLE_EVENT_SLOT = {"hidden": False}


def registry_probe_catalog(slug):
    return {
        "country_shu": {
            "key": "country_shu", "layer": "country", "runtime_tags": ["SHU"],
            "arcs": [{
                "slug": slug, "era": "middle", "participants": ["SHU"], "depends_on": [],
                "journals": [], "outcomes": [], "legacy_links": [],
                "events": [{
                    "id": "ywc_shu.1100", "title": {"zh": "测试", "en": "Probe"},
                    "desc": {"zh": "测试", "en": "Probe"}, "purpose": {"zh": "测试", "en": "Probe"},
                    "trigger": "{ c:SHU ?= this }", "immediate": "{}",
                    "options": [{
                        "key": "continue", "label": {"zh": "继续", "en": "Continue"},
                        "effect": "{}", "ai_chance": "{ base = 1 }",
                        "cost_note": {"zh": "无", "en": "None"},
                        "consequence_note": {"zh": "记录", "en": "Record"},
                    }],
                    "reads": [], "writes": [],
                }],
            }],
        }
    }


class V03CampaignReservationTests(unittest.TestCase):
    def test_registry_preserves_foundation_and_matches_all_sixty_approved_middle_late_slots(self):
        current = registry()
        before = json.loads(FOUNDATION_REGISTRY_PATH.read_text(encoding="utf-8"))
        foundation = copy.deepcopy(current["arc_ranges"][:len(before["arc_ranges"])])
        expected_extensions = {
            ("country_kor", "v03_kor_military_accounts"): [{"start": 1030, "end": 1039}],
            ("country_nqg", "v03_nqg_winter_court"): [{"start": 1030, "end": 1039}],
            ("country_jhg", "v03_jhg_convoy_capacity"): [{"start": 1030, "end": 1032}],
            ("country_nmg", "v03_nmg_autonomy_revenue"): [{"start": 1030, "end": 1032}],
        }
        seen_extensions = set()
        for row in foundation:
            key = (row["catalog_key"], row["slug"])
            if key in expected_extensions:
                self.assertEqual(row.pop("additional_ranges"), expected_extensions[key])
                seen_extensions.add(key)
        self.assertEqual(seen_extensions, set(expected_extensions))
        self.assertEqual(foundation, before["arc_ranges"])
        self.assertEqual(len(before["arc_ranges"]), 30)
        self.assertEqual(current["reservations"], before["reservations"])
        self.assertEqual(current["namespace_limits"], before["namespace_limits"])
        self.assertEqual(len(current["reservations"]), 10)

        additions = current["arc_ranges"][len(before["arc_ranges"]):]
        expected_rows = markdown_country_reservations()
        self.assertEqual(len(expected_rows), 60)
        self.assertEqual(len({slug for _, _, slug in expected_rows}), 60)
        self.assertEqual(len(additions), 60)
        self.assertEqual(len({row["slug"] for row in current["arc_ranges"]}), 90)
        self.assertEqual(len({(row["catalog_key"], row["slug"]) for row in current["arc_ranges"]}), 90)
        self.assertEqual({row["slug"] for row in current["arc_ranges"]},
                         {row["slug"] for row in before["arc_ranges"]}
                         | {slug for _, _, slug in expected_rows})
        self.assertEqual(Counter(row["catalog_key"] for row in current["arc_ranges"]),
                         {f"country_{tag.lower()}": 9 for tag in COUNTRY_TAGS})

        expected = []
        for country in sorted({country for country, _, _ in expected_rows}):
            for era, start in (("middle", 1100), ("late", 1200)):
                slugs = [slug for row_country, row_era, slug in expected_rows
                         if row_country == country and row_era == era]
                self.assertEqual(len(slugs), 3, (country, era))
                for index, slug in enumerate(slugs):
                    tag = {value.lower(): value for value in COUNTRY_TAGS}[country]
                    expected.append({
                        "catalog_key": f"country_{country}", "slug": slug,
                        "namespace": COUNTRY_NAMESPACES[tag], "start": start + index * 10,
                        "end": start + index * 10 + 9,
                    })
        self.assertEqual(additions, expected)
        self.assertEqual(COUNTRY_NAMESPACES["MGL"], "ywc_mng")
        self.assertEqual(COUNTRY_NAMESPACES["NMG"], "ywc_nmg")

        authored = load_catalogs(ROOT)
        foundation_arcs = [arc for c in authored.values() for arc in c["arcs"]
                           if arc.get("era") == "foundation"]
        self.assertEqual(len(foundation_arcs), 30)
        self.assertEqual(sum(len(arc["events"]) for arc in foundation_arcs), 260)
        self.assertEqual(sum(sum(not event.get("hidden", False) for event in arc["events"])
                             for arc in foundation_arcs), 253)
        self.assertEqual(sum(len(arc["journals"]) for arc in foundation_arcs), 60)
        self.assertEqual(validate_catalogs_at(ROOT, authored), [])

    def test_registry_validator_rejects_missing_middle_slot_when_referenced(self):
        value = registry()
        self.assertEqual(validate_catalogs_at(ROOT, load_catalogs(ROOT)), [])
        slug = "v03_shu_provincial_contract"
        value["arc_ranges"] = [row for row in value["arc_ranges"] if row["slug"] != slug]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_registry(root, value)
            errors = validate_catalogs_at(root, registry_probe_catalog(slug))
        self.assertEqual(errors, [
            f"catalog[country_shu].arcs[0].events[0].id has no explicit arc ID range for country_shu/{slug}"
        ])

    def test_registry_validator_rejects_overlapping_reserved_slots(self):
        value = registry()
        self.assertEqual(validate_catalogs_at(ROOT, load_catalogs(ROOT)), [])
        first = next(row for row in value["arc_ranges"] if row["slug"] == "v03_shu_provincial_contract")
        second = next(row for row in value["arc_ranges"] if row["slug"] == "v03_shu_rural_workshop")
        second["start"], second["end"] = first["start"], first["end"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_registry(root, value)
            errors = validate_catalogs_at(root, {})
        self.assertEqual(errors, [
            "overlapping ID arc ranges in ywc_shu: country_shu/v03_shu_provincial_contract and "
            "v03_shu_rural_workshop"
        ])

    def test_registry_validator_rejects_wrong_middle_slot_namespace(self):
        value = registry()
        self.assertEqual(validate_catalogs_at(ROOT, load_catalogs(ROOT)), [])
        target = next(row for row in value["arc_ranges"] if row["slug"] == "v03_mgl_mobile_offices")
        target["namespace"] = "ywc_mgl"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_registry(root, value)
            errors = validate_catalogs_at(root, {})
        self.assertEqual(errors, [
            "ID arc range namespace does not match catalog reservation for country_mgl/v03_mgl_mobile_offices"
        ])

    def test_canonical_three_country_eras_pass_country_gate_and_other_layer_gaps_remain_visible(self):
        errors = check_complete_quotas(era_fixture())
        country_errors = [error for error in errors if error.startswith("country owner ")]
        self.assertEqual(country_errors, [])
        self.assertIn("crisis owner C01 event quota: 0/12", errors)
        self.assertIn("regional owner CHI event quota: 0/6", errors)
        self.assertIn("theme owner T01 event quota: 0/8", errors)

    def test_hidden_events_do_not_fulfill_country_event_quota(self):
        catalogs = era_fixture()
        catalogs["country_shu"]["arcs"][0]["events"] = [VISIBLE_EVENT_SLOT] * 7 + [{"hidden": True}] * 2
        errors = check_complete_quotas(catalogs)
        self.assertTrue(any(error == "country owner SHU event quota: 71/72" for error in errors), errors)
        surplus = era_fixture()
        surplus["country_shu"]["arcs"][0]["events"] = [VISIBLE_EVENT_SLOT] * 8 + [{"hidden": True}] * 3
        surplus_errors = check_complete_quotas(surplus)
        self.assertFalse(any(error.startswith("country owner SHU ") for error in surplus_errors), surplus_errors)

    def test_arbitrary_three_era_names_do_not_pass_complete_country_era_gate(self):
        era_order = ("early",) * 3 + ("present",) * 3 + ("after",) * 3
        eras = {tag: era_order for tag in COUNTRY_TAGS}
        errors = check_complete_quotas(era_fixture(eras))
        self.assertTrue(any("country owner SHU must cover canonical eras" in error for error in errors), errors)
        self.assertTrue(any(error.startswith("crisis owner ") for error in errors), errors)

    def test_extra_unrecognized_era_cannot_repair_missing_canonical_era(self):
        eras = {tag: ("foundation", "foundation", "foundation", "middle", "middle", "middle",
                      "bonus", "bonus", "bonus") for tag in COUNTRY_TAGS}
        errors = check_complete_quotas(era_fixture(eras))
        self.assertTrue(any("country owner SHU has unrecognized era bonus" in error for error in errors), errors)
        self.assertTrue(any("country owner SHU must cover canonical eras" in error for error in errors), errors)

    def test_each_canonical_era_requires_at_least_three_country_arcs(self):
        eras = {tag: ("foundation", "foundation", "middle", "middle", "middle",
                      "middle", "late", "late", "late") for tag in COUNTRY_TAGS}
        errors = check_complete_quotas(era_fixture(eras))
        self.assertTrue(any("country owner SHU era foundation arc quota: 2/3" in error for error in errors), errors)

    def test_historical_noncanonical_development_era_remains_schema_compatible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_fixture(root)
            errors = validate_catalogs_at(root, {"country_shu": catalog()})
        self.assertFalse(any("era" in error.lower() for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
