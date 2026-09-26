import pathlib
import unittest

from tools.scenario_tag_audit import audit_references, audit_repository_tags


ROOT = pathlib.Path(__file__).parents[1]


class ScenarioTagAuditTest(unittest.TestCase):
    def test_current_scenario_and_history_tags_are_clean(self):
        self.assertEqual(audit_repository_tags(ROOT), [])

    def test_legacy_runtime_alias_is_rejected_with_replacement(self):
        diagnostics = audit_references(
            "country = c:SHN\nregion_state:MNG = { }\n",
            pathlib.Path("fixture.txt"),
            {"SHN", "MNG", "SHD", "MGL"},
        )
        self.assertEqual(len(diagnostics), 2)
        self.assertIn("SHN", diagnostics[0])
        self.assertIn("SHD", diagnostics[0])
        self.assertIn("MNG", diagnostics[1])
        self.assertIn("MGL", diagnostics[1])


if __name__ == "__main__":
    unittest.main()
