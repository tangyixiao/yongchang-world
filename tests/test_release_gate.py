import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tools.check_release import check


ROOT = pathlib.Path(__file__).parents[1]
CONFIGS = {"none", "sphere", "charters", "wave", "all"}
COUNTRIES = ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG")
EXPECTED_DLC = {
    "none": [],
    "sphere": ["dlc010_ep1"],
    "charters": ["dlc013_mp1"],
    "wave": ["dlc018_ep2"],
    "all": ["dlc010_ep1", "dlc013_mp1", "dlc018_ep2"],
}


class ReleaseMatrixTest(unittest.TestCase):
    def test_matrix_has_fifteen_runs(self):
        data = json.loads((ROOT / "artifacts/observe/matrix-summary.json").read_text("utf-8"))
        self.assertEqual(len(data["runs"]), 15)
        self.assertEqual(set(data["configs"]), CONFIGS)
        self.assertEqual(set(data["seeds"]), {11, 23, 47})

    def test_each_matrix_run_has_three_checkpoints(self):
        data = json.loads((ROOT / "artifacts/observe/matrix-summary.json").read_text("utf-8"))
        for run in data["runs"]:
            self.assertEqual(run["checkpoint_years"], [1846, 1866, 1900])

    def test_release_gate_requires_matching_evidence_for_every_run(self):
        with tempfile.TemporaryDirectory() as directory:
            matrix_path = pathlib.Path(directory) / "matrix.json"
            runs = []
            for config in sorted(CONFIGS):
                for seed in (11, 23, 47):
                    runs.append(
                        {
                            "config": config,
                            "run_id": f"run-{seed}",
                            "requested_seed": seed,
                            "observed_seed": None,
                            "status": "verified",
                            "checkpoint_years": [1846, 1866, 1900],
                            "checkpoint_count": 30,
                            "countries": ["SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG"],
                            "source": "artifacts/observe",
                            "evidence": {"campaign": "checkpoint export", "logs": "debug.log"},
                            "mod_mount": "mounted",
                            "game_version": "1.13.11 (Matcha)",
                            "dlc_state_matches_config": "yes",
                            "expected_mounted_dlc": {
                                "none": [],
                                "sphere": ["dlc010_ep1"],
                                "charters": ["dlc013_mp1"],
                                "wave": ["dlc018_ep2"],
                                "all": ["dlc010_ep1", "dlc013_mp1", "dlc018_ep2"],
                            }[config],
                            "observed_mounted_dlc": {
                                "none": [],
                                "sphere": ["dlc010_ep1"],
                                "charters": ["dlc013_mp1"],
                                "wave": ["dlc018_ep2"],
                                "all": ["dlc010_ep1", "dlc013_mp1", "dlc018_ep2"],
                            }[config],
                        }
                    )
            matrix_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "configs": sorted(CONFIGS),
                        "run_ids": [f"{run['config']}/{run['run_id']}" for run in runs],
                        "runs": runs,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(check(matrix_path, ROOT / "yongchang_world"), [])

    def test_release_gate_rejects_forged_verified_status(self):
        data = json.loads((ROOT / "artifacts/observe/matrix-summary.json").read_text("utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            matrix_path = pathlib.Path(directory) / "matrix.json"
            for run in data["runs"]:
                run["status"] = "verified"
            data["schema_version"] = 1
            matrix_path.write_text(json.dumps(data), encoding="utf-8")
            errors = check(matrix_path, ROOT / "yongchang_world")
            self.assertTrue(any("evidence" in error for error in errors))

    def test_machine_summary_passes_gate_only_with_complete_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            observe_root = pathlib.Path(directory) / "observe"
            for config in sorted(CONFIGS):
                for seed in (11, 23, 47):
                    run_root = observe_root / config / f"run-{seed}"
                    run_root.mkdir(parents=True)
                    rows = [
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
                        for year in (1846, 1866, 1900)
                        for country in COUNTRIES
                    ]
                    (run_root / "checkpoints.json").write_text(json.dumps(rows), encoding="utf-8")
                    dlc = EXPECTED_DLC[config]
                    (run_root / "run.json").write_text(
                        json.dumps(
                            {
                                "config": config,
                                "run_id": f"run-{seed}",
                                "requested_seed": seed,
                                "observed_seed": None,
                                "status": "observed_to_checkpoint",
                                "game_version": "1.13.11 (Matcha)",
                                "mod_mount": "mounted",
                                "version_match_evidence": ["debug.log"],
                                "expected_mounted_dlc": dlc,
                                "observed_mounted_dlc": dlc,
                                "dlc_state_matches_config": "yes",
                                "evidence": {"campaign": "manual", "logs": "debug.log"},
                            }
                        ),
                        encoding="utf-8",
                    )
            matrix_path = observe_root / "matrix-summary.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/summarize_observation.py"),
                    "--input",
                    str(observe_root),
                    "--output",
                    str(matrix_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(check(matrix_path, ROOT / "yongchang_world"), [])

            summary = json.loads(matrix_path.read_text("utf-8"))
            for field, value, fragment in (
                ("mod_mount", "not_mounted", "mounted"),
                ("game_version", "1.13.10", "version"),
                ("dlc_state_matches_config", "no", "DLC"),
                ("status", "hidden_preload_only", "verified"),
            ):
                broken = json.loads(json.dumps(summary))
                broken["runs"][0][field] = value
                broken_path = pathlib.Path(directory) / f"broken-{field}.json"
                broken_path.write_text(json.dumps(broken), encoding="utf-8")
                self.assertTrue(
                    any(fragment in error for error in check(broken_path, ROOT / "yongchang_world")),
                    f"release gate accepted broken {field}",
                )
            forged_seed = json.loads(json.dumps(summary))
            forged_seed["runs"][0]["observed_seed"] = 11
            forged_seed_path = pathlib.Path(directory) / "broken-observed-seed.json"
            forged_seed_path.write_text(json.dumps(forged_seed), encoding="utf-8")
            self.assertTrue(any("observed_seed" in error for error in check(forged_seed_path, ROOT / "yongchang_world")))

            missing_run = json.loads(json.dumps(summary))
            missing_run["runs"].pop()
            missing_run["run_ids"].pop()
            missing_run_path = pathlib.Path(directory) / "broken-missing-run.json"
            missing_run_path.write_text(json.dumps(missing_run), encoding="utf-8")
            self.assertTrue(any("15 runs" in error or "every config/requested_seed" in error for error in check(missing_run_path, ROOT / "yongchang_world")))

            duplicate_run = json.loads(json.dumps(summary))
            duplicate_run["runs"][1]["run_id"] = duplicate_run["runs"][0]["run_id"]
            duplicate_run["run_ids"][1] = duplicate_run["run_ids"][0]
            duplicate_run_path = pathlib.Path(directory) / "broken-duplicate-run.json"
            duplicate_run_path.write_text(json.dumps(duplicate_run), encoding="utf-8")
            self.assertTrue(any("duplicate" in error for error in check(duplicate_run_path, ROOT / "yongchang_world")))


class ReleaseDocsTest(unittest.TestCase):
    def test_release_docs_name_exact_baseline(self):
        text = (ROOT / "docs/release/v0.1-acceptance.md").read_text("utf-8")
        self.assertIn("1.13.11 (Matcha)", text)
        self.assertIn("没有预定1900—1950政治结局", text)
        self.assertIn("NMG", text)


if __name__ == "__main__":
    unittest.main()
