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
            evidence_root = pathlib.Path(directory) / "evidence"
            runs = []
            for config in sorted(CONFIGS):
                for seed in (11, 23, 47):
                    run_evidence = evidence_root / config / str(seed)
                    run_evidence.mkdir(parents=True)
                    logs_path = run_evidence / "debug.log"
                    checkpoint_path = run_evidence / "checkpoints.json"
                    metadata_path = run_evidence / "run.json"
                    logs_path.write_text("evidence\n", encoding="utf-8")
                    checkpoint_path.write_text(
                        json.dumps(
                            [
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
                        ),
                        encoding="utf-8",
                    )
                    dlc = {
                        "none": [],
                        "sphere": ["dlc010_ep1"],
                        "charters": ["dlc013_mp1"],
                        "wave": ["dlc018_ep2"],
                        "all": ["dlc010_ep1", "dlc013_mp1", "dlc018_ep2"],
                    }[config]
                    metadata_path.write_text(
                        json.dumps(
                            {
                                "config": config,
                                "run_id": f"run-{seed}",
                                "requested_seed": seed,
                                "observed_seed": None,
                                "game_version": "1.13.11 (Matcha)",
                                "mod_mount": "mounted",
                                "version_match_evidence": ["debug.log: successfully matched game version"],
                                "expected_mounted_dlc": dlc,
                                "observed_mounted_dlc": dlc,
                                "dlc_state_matches_config": "yes",
                                "status": "observed_to_checkpoint",
                            }
                        ),
                        encoding="utf-8",
                    )
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
                            "source": str(checkpoint_path),
                            "evidence": {
                                "campaign": "checkpoint export",
                                "logs": str(logs_path),
                                "checkpoint_file": str(checkpoint_path),
                                "run_metadata": str(metadata_path),
                            },
                            "version_match_evidence": ["debug.log: successfully matched game version"],
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

            mismatch = json.loads(matrix_path.read_text(encoding="utf-8"))
            first_metadata = pathlib.Path(mismatch["runs"][0]["evidence"]["run_metadata"])
            first_metadata.write_text(
                json.dumps(
                    {
                        "config": "wrong-config",
                        "run_id": mismatch["runs"][0]["run_id"],
                        "requested_seed": mismatch["runs"][0]["requested_seed"],
                    }
                ),
                encoding="utf-8",
            )
            mismatch_path = pathlib.Path(directory) / "mismatched-metadata.json"
            mismatch_path.write_text(json.dumps(mismatch), encoding="utf-8")
            errors = check(mismatch_path, ROOT / "yongchang_world")
            self.assertTrue(
                any("run metadata config does not match" in error for error in errors),
                errors,
            )
            first_metadata.write_text(
                json.dumps(
                    {
                        "config": mismatch["runs"][0]["config"],
                        "run_id": mismatch["runs"][0]["run_id"],
                        "requested_seed": mismatch["runs"][0]["requested_seed"],
                        "version_match_evidence": ["debug.log: successfully matched game version"],
                        "status": "observed_to_checkpoint",
                    }
                ),
                encoding="utf-8",
            )

            corrupt = json.loads(matrix_path.read_text(encoding="utf-8"))
            first_checkpoint = pathlib.Path(corrupt["runs"][0]["evidence"]["checkpoint_file"])
            first_checkpoint.write_text("not-json", encoding="utf-8")
            corrupt_path = pathlib.Path(directory) / "corrupt-checkpoints.json"
            corrupt_path.write_text(json.dumps(corrupt), encoding="utf-8")
            errors = check(corrupt_path, ROOT / "yongchang_world")
            self.assertTrue(any("checkpoint evidence" in error for error in errors), errors)

            broken = json.loads(matrix_path.read_text(encoding="utf-8"))
            broken["runs"][0]["evidence"]["logs"] = str(evidence_root / "missing.log")
            broken_path = pathlib.Path(directory) / "missing-evidence.json"
            broken_path.write_text(json.dumps(broken), encoding="utf-8")
            errors = check(broken_path, ROOT / "yongchang_world")
            self.assertTrue(
                any("evidence path does not exist" in error for error in errors),
                errors,
            )

            malformed = json.loads(matrix_path.read_text(encoding="utf-8"))
            malformed["runs"][0]["observed_seed"] = 11
            malformed["runs"][0]["evidence"] = "not-an-object"
            malformed_path = pathlib.Path(directory) / "malformed-evidence.json"
            malformed_path.write_text(json.dumps(malformed), encoding="utf-8")
            errors = check(malformed_path, ROOT / "yongchang_world")
            self.assertTrue(any("missing evidence" in error for error in errors), errors)

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
                    checkpoint_path = run_root / "checkpoints.json"
                    logs_path = run_root / "debug.log"
                    metadata_path = run_root / "run.json"
                    checkpoint_path.write_text(json.dumps(rows), encoding="utf-8")
                    logs_path.write_text("Mounted Data: yongchang_world\n", encoding="utf-8")
                    dlc = EXPECTED_DLC[config]
                    metadata_path.write_text(
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
                                "evidence": {
                                    "campaign": "manual",
                                    "logs": str(logs_path),
                                    "checkpoint_file": str(checkpoint_path),
                                    "run_metadata": str(metadata_path),
                                },
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
            invalid_checkpoint = json.loads(json.dumps(summary))
            invalid_checkpoint_path = pathlib.Path(
                invalid_checkpoint["runs"][0]["evidence"]["checkpoint_file"]
            )
            invalid_rows = json.loads(invalid_checkpoint_path.read_text(encoding="utf-8"))
            invalid_rows[0]["population"] = "100000"
            invalid_checkpoint_path.write_text(json.dumps(invalid_rows), encoding="utf-8")
            invalid_checkpoint_matrix = pathlib.Path(directory) / "invalid-checkpoint-values.json"
            invalid_checkpoint_matrix.write_text(json.dumps(invalid_checkpoint), encoding="utf-8")
            errors = check(invalid_checkpoint_matrix, ROOT / "yongchang_world")
            self.assertTrue(any("population" in error for error in errors), errors)

            missing_checkpoint_field = json.loads(json.dumps(summary))
            missing_checkpoint_path = pathlib.Path(
                missing_checkpoint_field["runs"][0]["evidence"]["checkpoint_file"]
            )
            missing_rows = json.loads(missing_checkpoint_path.read_text(encoding="utf-8"))
            missing_rows[0]["population"] = 100000
            missing_rows[0].pop("market")
            missing_checkpoint_path.write_text(json.dumps(missing_rows), encoding="utf-8")
            missing_checkpoint_matrix = pathlib.Path(directory) / "missing-checkpoint-field.json"
            missing_checkpoint_matrix.write_text(json.dumps(missing_checkpoint_field), encoding="utf-8")
            errors = check(missing_checkpoint_matrix, ROOT / "yongchang_world")
            self.assertTrue(any("missing market" in error for error in errors), errors)
            missing_rows[0]["market"] = COUNTRIES[0]
            missing_checkpoint_path.write_text(json.dumps(missing_rows), encoding="utf-8")

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

            missing_version_evidence = json.loads(json.dumps(summary))
            missing_version_evidence["runs"][0]["version_match_evidence"] = []
            missing_version_path = pathlib.Path(directory) / "missing-version-evidence.json"
            missing_version_path.write_text(json.dumps(missing_version_evidence), encoding="utf-8")
            errors = check(missing_version_path, ROOT / "yongchang_world")
            self.assertTrue(any("version-match evidence" in error for error in errors), errors)

            mismatched_version_metadata = json.loads(json.dumps(summary))
            mismatched_metadata_path = pathlib.Path(
                mismatched_version_metadata["runs"][0]["evidence"]["run_metadata"]
            )
            mismatched_metadata = json.loads(mismatched_metadata_path.read_text(encoding="utf-8"))
            mismatched_metadata["version_match_evidence"] = []
            mismatched_metadata_path.write_text(json.dumps(mismatched_metadata), encoding="utf-8")
            mismatched_version_path = pathlib.Path(directory) / "mismatched-version-evidence.json"
            mismatched_version_path.write_text(json.dumps(mismatched_version_metadata), encoding="utf-8")
            errors = check(mismatched_version_path, ROOT / "yongchang_world")
            self.assertTrue(any("run metadata version_match_evidence" in error for error in errors), errors)

            mismatched_runtime_metadata = json.loads(json.dumps(summary))
            mismatched_runtime_metadata_path = pathlib.Path(
                mismatched_runtime_metadata["runs"][0]["evidence"]["run_metadata"]
            )
            runtime_metadata = json.loads(mismatched_runtime_metadata_path.read_text(encoding="utf-8"))
            runtime_metadata["version_match_evidence"] = summary["runs"][0]["version_match_evidence"]
            runtime_metadata["game_version"] = "1.13.10"
            mismatched_runtime_metadata_path.write_text(json.dumps(runtime_metadata), encoding="utf-8")
            mismatched_runtime_path = pathlib.Path(directory) / "mismatched-runtime-metadata.json"
            mismatched_runtime_path.write_text(json.dumps(mismatched_runtime_metadata), encoding="utf-8")
            errors = check(mismatched_runtime_path, ROOT / "yongchang_world")
            self.assertTrue(any("run metadata game_version" in error for error in errors), errors)

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
