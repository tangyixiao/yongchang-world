import json
import pathlib
import unittest

from tools.build_frontier_polity_content import assign_frontier_event_ids


ROOT = pathlib.Path(__file__).parents[1]
SNAPSHOT = ROOT / "data/content/v03/legacy_ids.json"


class LegacyFrontierIdContractTest(unittest.TestCase):
    def test_legacy_frontier_ids_survive_added_tag(self):
        frozen = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        old_ids = frozen["frontier_event_ids"]
        self.assertEqual(len(old_ids), 56)
        tags = sorted([*old_ids, "AAA"])
        with self.assertRaisesRegex(ValueError, "AAA.*missing.*legacy|missing.*AAA"):
            assign_frontier_event_ids(tags, old_ids)

        resolved = assign_frontier_event_ids(list(old_ids), old_ids)
        self.assertEqual(resolved, old_ids)
        self.assertEqual(assign_frontier_event_ids(tags[1:], old_ids), old_ids)

    def test_duplicate_frontier_ids_are_rejected(self):
        frozen = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["frontier_event_ids"]
        frozen["AAA"] = list(frozen["ABN"])
        with self.assertRaisesRegex(ValueError, "duplicate.*ywc_frontier\\.1|ywc_frontier\\.1.*duplicate"):
            assign_frontier_event_ids(["AAA", "ABN"], frozen)

    def test_snapshot_records_current_definition_inventory(self):
        frozen = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(len(frozen["events"]), 491)
        self.assertEqual(len(frozen["journals"]), 142)
        self.assertEqual(len(frozen["routes"]), 20)
        self.assertTrue(frozen["baseline_revision"])


if __name__ == "__main__":
    unittest.main()
