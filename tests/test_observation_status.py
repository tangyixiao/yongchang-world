import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tools.observation_status import inspect_matrix, inspect_run


ROOT = pathlib.Path(__file__).parents[1]
STATUS = ROOT / "tools/observation_status.py"
COUNTRIES = ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG")


def rows_for(year: int) -> list[dict]:
    return [
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
        for country in COUNTRIES
    ]


def complete_run_metadata() -> dict:
    return {
        "config": "none",
        "run_id": "run-11",
        "requested_seed": 11,
        "observed_seed": None,
        "status": "observed_to_checkpoint",
        "game_version": "1.13.11 (Matcha)",
        "mod_mount": "mounted",
        "version_match_evidence": "debug.log: version 1.13.11",
        "expected_mounted_dlc": [],
        "observed_mounted_dlc": [],
        "dlc_state_matches_config": "yes",
        "evidence": {"campaign": "manual campaign"},
    }


class ObservationStatusTest(unittest.TestCase):
    def test_empty_root_reports_no_ready_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "observe"
            root.mkdir()
            report = inspect_matrix(root)
            self.assertEqual(report["expected_runs"], 15)
            self.assertEqual(report["recorded_rows"], 0)
            self.assertEqual(report["ready_runs"], [])
            self.assertEqual(report["runs"][0]["status"], "no_run_metadata")

    def test_partial_run_counts_recorded_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            run_root = root / "none" / "11"
            run_root.mkdir(parents=True)
            (run_root / "checkpoints.json").write_text(json.dumps(rows_for(1846)), encoding="utf-8")
            run = inspect_run(root, "none", 11)
            self.assertEqual(run["recorded"], 10)
            self.assertEqual(run["expected"], 30)
            self.assertEqual(len(run["missing"]), 20)
            self.assertFalse(run["ready_for_summary"])

    def test_complete_run_with_mount_evidence_is_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            run_root = root / "none" / "11"
            run_root.mkdir(parents=True)
            rows = rows_for(1846) + rows_for(1866) + rows_for(1900)
            (run_root / "checkpoints.json").write_text(json.dumps(rows), encoding="utf-8")
            (run_root / "run.json").write_text(
                json.dumps(complete_run_metadata()),
                encoding="utf-8",
            )
            run = inspect_run(root, "none", 11)
            self.assertTrue(run["ready_for_summary"])
            self.assertEqual(run["missing"], [])

    def test_complete_run_with_malformed_checkpoint_row_is_not_ready(self):
        """A complete pair set must not hide rows the summarizer will reject."""
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            run_root = root / "none" / "11"
            run_root.mkdir(parents=True)
            rows = rows_for(1846) + rows_for(1866) + rows_for(1900)
            rows[0]["population"] = -1
            (run_root / "checkpoints.json").write_text(json.dumps(rows), encoding="utf-8")
            (run_root / "run.json").write_text(
                json.dumps(
                    {
                        "status": "observed_to_checkpoint",
                        "mod_mount": "mounted",
                        "dlc_state_matches_config": "yes",
                    }
                ),
                encoding="utf-8",
            )

            run = inspect_run(root, "none", 11)

            self.assertFalse(run["ready_for_summary"])
            self.assertTrue(run["validation_errors"])

    def test_preload_status_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            run_root = root / "none" / "11"
            run_root.mkdir(parents=True)
            rows = rows_for(1846) + rows_for(1866) + rows_for(1900)
            (run_root / "checkpoints.json").write_text(json.dumps(rows), encoding="utf-8")
            (run_root / "run.json").write_text(
                json.dumps(
                    {
                        "status": "hidden_preload_only",
                        "mod_mount": "mounted",
                        "dlc_state_matches_config": "yes",
                    }
                ),
                encoding="utf-8",
            )
            self.assertFalse(inspect_run(root, "none", 11)["ready_for_summary"])

    def test_complete_rows_with_incomplete_run_metadata_are_not_ready(self):
        """Status/mount flags alone are not enough for the summarizer."""
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            run_root = root / "none" / "11"
            run_root.mkdir(parents=True)
            rows = rows_for(1846) + rows_for(1866) + rows_for(1900)
            (run_root / "checkpoints.json").write_text(json.dumps(rows), encoding="utf-8")
            (run_root / "run.json").write_text(
                json.dumps(
                    {
                        "status": "observed_to_checkpoint",
                        "mod_mount": "mounted",
                        "dlc_state_matches_config": "yes",
                    }
                ),
                encoding="utf-8",
            )

            run = inspect_run(root, "none", 11)

            self.assertFalse(run["ready_for_summary"])
            self.assertTrue(run["validation_errors"])

    def test_cli_prints_progress_table(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "observe"
            (root / "none" / "11").mkdir(parents=True)
            (root / "none" / "11" / "checkpoints.json").write_text(
                json.dumps(rows_for(1846)), encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(STATUS), "--root", str(root)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("none/11", result.stdout)
            self.assertIn("10/30", result.stdout)
            self.assertIn("0/15", result.stdout)

    def test_cli_json_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "observe"
            root.mkdir()
            result = subprocess.run(
                [sys.executable, str(STATUS), "--root", str(root), "--json"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(len(report["runs"]), 15)
            self.assertEqual(report["expected_rows"], 450)


if __name__ == "__main__":
    unittest.main()
