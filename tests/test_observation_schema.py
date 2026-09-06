import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SUMMARIZER = ROOT / "tools/summarize_observation.py"
REQUIRED_FIELDS = {
    "year",
    "country",
    "rank",
    "population",
    "market",
    "wars",
    "subjects",
    "error_count",
}


class ObservationSchemaTest(unittest.TestCase):
    def test_runner_isolates_user_data_and_does_not_claim_checkpoints(self):
        text = (ROOT / "tools/run_observation_matrix.ps1").read_text("utf-8")
        self.assertIn("-userdir", text)
        self.assertIn("isolatedUserDataRoot", text)
        self.assertIn("writes_to_user_data = $false", text)
        self.assertIn("hidden_preload_only", text)

    def test_runner_writes_content_load_json_without_bom(self):
        """The game fails to parse a UTF-8 BOM content_load.json and silently
        falls back to 'all DLC enabled, no mods' (see artifacts/observe probes)."""
        text = (ROOT / "tools/run_observation_matrix.ps1").read_text("utf-8")
        self.assertNotIn("Set-Content", text)
        self.assertIn("-Compress", text)
        self.assertIn("UTF8Encoding", text)
        self.assertIn("$false", text.split("UTF8Encoding", 1)[1][:40])

    def test_runner_records_mount_evidence_after_launch(self):
        text = (ROOT / "tools/run_observation_matrix.ps1").read_text("utf-8")
        self.assertIn("mod_mount", text)
        self.assertIn("Mounted Data", text)
        self.assertIn("successfully matched game version", text)
        self.assertIn("dlc_state_matches_config", text)
        self.assertIn("dlc_ownership_backend", text)
        self.assertIn("store backend", text)

    def test_runner_preserves_live_evidence_on_nolaunch_rerun(self):
        """A -NoLaunch rerun over an already-verified config/seed must not
        overwrite the recorded live evidence with a not_evaluated stub."""
        text = (ROOT / "tools/run_observation_matrix.ps1").read_text("utf-8")
        self.assertIn("existing.status -eq 'hidden_preload_only'", text)
        self.assertIn("existing.mod_mount -eq 'mounted'", text)
        self.assertIn("preserved existing live run evidence", text)

    def test_checkpoint_schema(self):
        row = {
            "year": 1846,
            "country": "SHU",
            "rank": "great_power",
            "population": 1000000,
            "market": "SHU",
            "wars": 0,
            "subjects": 1,
            "error_count": 0,
        }
        self.assertEqual(set(row), REQUIRED_FIELDS)

    def test_summarizer_accepts_valid_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "summary.json"
            result = subprocess.run(
                [sys.executable, str(SUMMARIZER), "--input", str(ROOT / "tests/fixtures/observation-valid"), "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            summary = json.loads(output.read_text("utf-8"))
            self.assertEqual(summary["checkpoint_count"], 3)
            self.assertEqual(summary["years"], [1846, 1866, 1900])

    def test_summarizer_rejects_negative_population(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = pathlib.Path(directory) / "checkpoints.json"
            output = pathlib.Path(directory) / "summary.json"
            row = {
                "year": 1846,
                "country": "SHU",
                "rank": "minor_power",
                "population": -1,
                "market": "SHU",
                "wars": 0,
                "subjects": 0,
                "error_count": 0,
            }
            input_path.write_text(json.dumps([row]), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SUMMARIZER), "--input", str(input_path), "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("negative population", result.stdout)


if __name__ == "__main__":
    unittest.main()
