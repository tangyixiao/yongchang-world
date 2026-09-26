import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tools.summarize_observation import _load_run


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

    def test_runner_records_run_specific_smoke_summary_after_launch(self):
        text = (ROOT / "tools/run_observation_matrix.ps1").read_text("utf-8")
        self.assertIn("smoke-summary.txt", text)
        self.assertIn("smoke_status", text)
        self.assertIn("collect_smoke_logs.ps1", text)
        self.assertIn("-SummaryPath", text)

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
            run_root = pathlib.Path(directory) / "none" / "run-11"
            run_root.mkdir(parents=True)
            rows = []
            for year in (1846, 1866, 1900):
                for country in ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG"):
                    rows.append(
                        {
                            "year": year,
                            "country": country,
                            "rank": "major_power",
                            "population": 100000,
                            "market": country,
                            "wars": 0,
                            "subjects": 0,
                            "error_count": 0,
                        }
                    )
            (run_root / "checkpoints.json").write_text(json.dumps(rows), encoding="utf-8")
            (run_root / "run.json").write_text(
                json.dumps(
                    {
                        "config": "none",
                        "run_id": "run-11",
                        "requested_seed": 11,
                        "observed_seed": None,
                        "status": "observed_to_checkpoint",
                        "game_version": "1.13.11 (Matcha)",
                        "mod_mount": "mounted",
                        "version_match_evidence": ["matched"],
                        "expected_mounted_dlc": [],
                        "observed_mounted_dlc": [],
                        "dlc_state_matches_config": "yes",
                        "evidence": {
                            "campaign": "manual campaign checkpoint export",
                            "logs": "debug.log",
                        },
                    }
                ),
                encoding="utf-8",
            )
            output = pathlib.Path(directory) / "summary.json"
            result = subprocess.run(
                [sys.executable, str(SUMMARIZER), "--input", str(pathlib.Path(directory)), "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            summary = json.loads(output.read_text("utf-8"))
            self.assertEqual(summary["schema_version"], 1)
            self.assertEqual(summary["run_ids"], ["none/run-11"])
            self.assertEqual(len(summary["runs"]), 1)
            run = summary["runs"][0]
            self.assertEqual(run["checkpoint_count"], 30)
            self.assertEqual(run["checkpoint_years"], [1846, 1866, 1900])
            self.assertEqual(run["countries"], sorted({"SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG"}))
            self.assertEqual(run["status"], "verified")
            self.assertIn("source", run)
            self.assertIn("evidence", run)

    def test_summarizer_rejects_incomplete_or_duplicate_run(self):
        with tempfile.TemporaryDirectory() as directory:
            run_root = pathlib.Path(directory) / "none" / "run-11"
            run_root.mkdir(parents=True)
            row = {
                "year": 1846,
                "country": "SHU",
                "rank": "major_power",
                "population": 100000,
                "market": "SHU",
                "wars": 0,
                "subjects": 0,
                "error_count": 0,
            }
            (run_root / "checkpoints.json").write_text(json.dumps([row, row]), encoding="utf-8")
            (run_root / "run.json").write_text(
                json.dumps({"config": "none", "run_id": "run-11", "requested_seed": 11}),
                encoding="utf-8",
            )
            output = pathlib.Path(directory) / "summary.json"
            result = subprocess.run(
                [sys.executable, str(SUMMARIZER), "--input", str(pathlib.Path(directory)), "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertRegex(result.stdout, "30 unique")

    def test_summarizer_rejects_negative_population(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = pathlib.Path(directory) / "checkpoints.json"
            output = pathlib.Path(directory) / "summary.json"
            rows = []
            for year in (1846, 1866, 1900):
                for country in ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG"):
                    rows.append(
                        {
                            "year": year,
                            "country": country,
                            "rank": "minor_power",
                            "population": -1 if country == "SHU" else 100000,
                            "market": country,
                            "wars": 0,
                            "subjects": 0,
                            "error_count": 0,
                        }
                    )
            input_path.write_text(json.dumps(rows), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SUMMARIZER), "--input", str(input_path), "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("negative population", result.stdout)

    def test_summarizer_rejects_non_numeric_checkpoint_values(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = pathlib.Path(directory) / "checkpoints.json"
            output = pathlib.Path(directory) / "summary.json"
            rows = [
                {
                    "year": year,
                    "country": country,
                    "rank": "minor_power",
                    "population": 100000,
                    "market": country,
                    "wars": 0,
                    "subjects": 0,
                    "error_count": 0,
                }
                for year in (1846, 1866, 1900)
                for country in ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG")
            ]
            rows[0]["population"] = "100000"
            input_path.write_text(json.dumps(rows), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SUMMARIZER), "--input", str(input_path), "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("population must be a non-negative integer", result.stdout)

    def test_run_evidence_rejects_empty_campaign_description(self):
        with tempfile.TemporaryDirectory() as directory:
            run_root = pathlib.Path(directory) / "none" / "run-11"
            run_root.mkdir(parents=True)
            (run_root / "run.json").write_text(
                json.dumps(
                    {
                        "config": "none",
                        "run_id": "run-11",
                        "requested_seed": 11,
                        "observed_seed": None,
                        "status": "observed_to_checkpoint",
                        "game_version": "1.13.11 (Matcha)",
                        "mod_mount": "mounted",
                        "version_match_evidence": ["matched"],
                        "expected_mounted_dlc": [],
                        "observed_mounted_dlc": [],
                        "dlc_state_matches_config": "yes",
                        "evidence": {"campaign": "", "logs": "debug.log"},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "campaign evidence must be non-empty"):
                _load_run(run_root / "checkpoints.json")


if __name__ == "__main__":
    unittest.main()
