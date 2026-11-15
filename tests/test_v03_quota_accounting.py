"""Conservative exclusion of operational events from release quotas."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.v03_owners import REGIONAL_TAGS
from tools.ywc_v03_check import check_complete_quotas, check_root

ROOT = Path(__file__).resolve().parents[1]
REL = Path("data/content/v03/quota_exclusions.json")
KNOWN_PROTOCOLS = {
    "ywc_jhg.1030", "ywc_kor.1030", "ywc_kor.1031", "ywc_kor.1033", "ywc_kor.1034",
    "ywc_nmg.1030", "ywc_nmg.1032", "ywc_nmg.1033", "ywc_nqg.1028", "ywc_nqg.1030", "ywc_nqg.1031",
}


def fixture():
    owner = REGIONAL_TAGS[0]
    events = [{"id": f"ywc_regional.{1000 + i}"} for i in range(5)]
    events.extend(({"id": "ywc_regional.1100"}, {"id": "ywc_regional.1101", "hidden": True}))
    return {"regional_demo": {"layer": "regional", "runtime_tags": [owner], "arcs": [{
        "owner": owner, "events": events, "journals": [{}, {}],
    }]}}


def write_metadata(root, value):
    path = Path(root) / REL; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class QuotaAccountingTests(unittest.TestCase):
    def test_only_visible_nonexcluded_definitions_contribute_to_the_owner_gate(self):
        owner = REGIONAL_TAGS[0]; catalogs = fixture()
        without = check_complete_quotas(catalogs)
        self.assertFalse(any(f"regional owner {owner} event quota" in row for row in without), without)
        with_exclusion = check_complete_quotas(catalogs, {"ywc_regional.1100"})
        self.assertIn(f"regional owner {owner} event quota: 5/6", with_exclusion)
        catalogs["regional_demo"]["arcs"][0]["events"].append({"id": "ywc_regional.1102"})
        after = check_complete_quotas(catalogs, {"ywc_regional.1100"})
        self.assertFalse(any(f"regional owner {owner} event quota" in row for row in after), after)

    def test_missing_exclusions_file_blocks_complete_gate(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("tools.ywc_v03_check.read_manifest", return_value={}), \
             patch("tools.ywc_v03_check.load_catalogs", return_value=fixture()), \
             patch("tools.ywc_v03_check.validate_catalogs_at", return_value=[]), \
             patch("tools.ywc_v03_check.check_outputs", return_value=[]):
            errors = check_root(Path(directory), require_complete=True)
        self.assertTrue(any("quota_exclusions.json" in error and "missing" in error for error in errors), errors)

    def test_optional_file_is_checked_when_present_but_not_needed_for_basic_fixture(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("tools.ywc_v03_check.read_manifest", return_value={}), \
             patch("tools.ywc_v03_check.load_catalogs", return_value=fixture()), \
             patch("tools.ywc_v03_check.validate_catalogs_at", return_value=[]), \
             patch("tools.ywc_v03_check.check_outputs", return_value=[]):
            self.assertEqual(check_root(Path(directory)), [])
            write_metadata(directory, {"schema_version": 1, "exclusions": [{"event_id": "missing", "reason": "menu"}]})
            errors = check_root(Path(directory))
            self.assertTrue(any("quota_exclusions" in error and "unknown event" in error for error in errors), errors)

    def test_bad_metadata_never_allows_a_complete_gate_to_pass(self):
        cases = (
            {"schema_version": True, "exclusions": []},
            {"schema_version": 1, "exclusions": "not a list"},
            {"schema_version": 1, "exclusions": [{"event_id": "ywc_regional.1100", "reason": ""}]},
            {"schema_version": 1, "exclusions": [{"event_id": "ywc_regional.1100", "reason": "menu"}, {"event_id": "ywc_regional.1100", "reason": "duplicate"}]},
            {"schema_version": 1, "exclusions": [{"event_id": "ywc_regional.9999", "reason": "unknown"}]},
            {"schema_version": 1, "exclusions": [{"event_id": "ywc_regional.1101", "reason": "already hidden"}]},
        )
        for value in cases:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory, \
                 patch("tools.ywc_v03_check.read_manifest", return_value={}), \
                 patch("tools.ywc_v03_check.load_catalogs", return_value=fixture()), \
                 patch("tools.ywc_v03_check.validate_catalogs_at", return_value=[]), \
                 patch("tools.ywc_v03_check.check_outputs", return_value=[]):
                write_metadata(directory, value)
                errors = check_root(Path(directory), require_complete=True)
                self.assertTrue(any("quota_exclusions" in error for error in errors), errors)

    def test_duplicate_json_keys_and_invalid_json_are_reported(self):
        texts = (
            '{"schema_version":1,"exclusions":[{"event_id":"ywc_regional.1100","event_id":"ywc_regional.1000","reason":"menu"}]}',
            '{"schema_version":1,"exclusions": [',
        )
        for text in texts:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as directory, \
                 patch("tools.ywc_v03_check.read_manifest", return_value={}), \
                 patch("tools.ywc_v03_check.load_catalogs", return_value=fixture()), \
                 patch("tools.ywc_v03_check.validate_catalogs_at", return_value=[]), \
                 patch("tools.ywc_v03_check.check_outputs", return_value=[]):
                path = Path(directory) / REL; path.parent.mkdir(parents=True)
                path.write_text(text, encoding="utf-8")
                errors = check_root(Path(directory), require_complete=True)
                self.assertTrue(any("quota_exclusions" in error for error in errors), errors[:3])

    def test_malformed_event_id_does_not_crash_quota_diagnostics(self):
        catalogs = fixture()
        catalogs["regional_demo"]["arcs"][0]["events"][0]["id"] = ["not", "hashable"]
        errors = check_complete_quotas(catalogs, {"ywc_regional.1100"})
        self.assertTrue(any(f"regional owner {REGIONAL_TAGS[0]} event quota" in error for error in errors))

    def test_valid_metadata_is_used_by_complete_gate(self):
        catalogs = fixture()
        with tempfile.TemporaryDirectory() as directory, \
             patch("tools.ywc_v03_check.read_manifest", return_value={}), \
             patch("tools.ywc_v03_check.load_catalogs", return_value=catalogs), \
             patch("tools.ywc_v03_check.validate_catalogs_at", return_value=[]), \
             patch("tools.ywc_v03_check.check_outputs", return_value=[]):
            write_metadata(directory, {"schema_version": 1, "exclusions": [{"event_id": "ywc_regional.1100", "reason": "retry menu"}]})
            errors = check_root(Path(directory), require_complete=True)
        self.assertIn(f"regional owner {REGIONAL_TAGS[0]} event quota: 5/6", errors)
        self.assertFalse(any("quota_exclusions" in error for error in errors))

    def test_omitting_a_known_protocol_is_reported_but_empty_fixture_is_valid(self):
        for include_protocol in (False, True):
            catalogs = fixture()
            if include_protocol:
                catalogs["regional_demo"]["arcs"][0]["events"].append({"id": "ywc_nmg.1032"})
            with self.subTest(include_protocol=include_protocol), tempfile.TemporaryDirectory() as directory, \
                 patch("tools.ywc_v03_check.read_manifest", return_value={}), \
                 patch("tools.ywc_v03_check.load_catalogs", return_value=catalogs), \
                 patch("tools.ywc_v03_check.validate_catalogs_at", return_value=[]), \
                 patch("tools.ywc_v03_check.check_outputs", return_value=[]):
                write_metadata(directory, {"schema_version": 1, "exclusions": []})
                errors = check_root(Path(directory), require_complete=True)
                found = [error for error in errors if "quota_exclusions" in error and "ywc_nmg.1032" in error]
                self.assertEqual(bool(found), include_protocol, found)

    def test_current_protocol_events_are_explicitly_excluded_with_reasons(self):
        metadata = json.loads((ROOT / REL).read_text(encoding="utf-8"))
        rows = metadata["exclusions"]
        ids = [row["event_id"] for row in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(KNOWN_PROTOCOLS <= set(ids))
        self.assertTrue(all(row["reason"].strip() for row in rows))


if __name__ == "__main__":
    unittest.main()
