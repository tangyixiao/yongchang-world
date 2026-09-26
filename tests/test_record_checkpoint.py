import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tools.record_checkpoint import (
    RecordCheckpointError,
    finalize_run,
    load_rows,
    merge_rows,
    missing_pairs,
    validate_rows,
)


ROOT = pathlib.Path(__file__).parents[1]
RECORDER = ROOT / "tools/record_checkpoint.py"
COUNTRIES = ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG")


def make_rows(year: int, population: int = 100000) -> list[dict]:
    return [
        {
            "year": year,
            "country": country,
            "rank": "major_power",
            "population": population,
            "market": country,
            "wars": 0,
            "subjects": 0,
            "error_count": 0,
        }
        for country in COUNTRIES
    ]


def write_csv(path: pathlib.Path, year: int, with_year_column: bool = True) -> None:
    header = ["country", "rank", "population", "market", "wars", "subjects", "error_count"]
    if with_year_column:
        header = ["year"] + header
    lines = [",".join(header)]
    for country in COUNTRIES:
        values = [country, "major_power", "100000", country, "0", "0", "0"]
        if with_year_column:
            values = [str(year)] + values
        lines.append(",".join(values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class RecordCheckpointTest(unittest.TestCase):
    def test_validate_rows_accepts_a_complete_year(self):
        rows = validate_rows(make_rows(1846), 1846)
        self.assertEqual(len(rows), 10)
        self.assertEqual([row["country"] for row in rows], sorted(COUNTRIES))

    def test_validate_rows_rejects_incomplete_country_coverage(self):
        rows = make_rows(1846)[:-1]
        with self.assertRaisesRegex(RecordCheckpointError, "missing countries"):
            validate_rows(rows, 1846)

    def test_validate_rows_rejects_unknown_country(self):
        rows = make_rows(1846)
        rows[0]["country"] = "SHN"
        with self.assertRaisesRegex(RecordCheckpointError, "unknown countries"):
            validate_rows(rows, 1846)

    def test_validate_rows_rejects_year_mismatch(self):
        with self.assertRaisesRegex(RecordCheckpointError, "do not match --year"):
            validate_rows(make_rows(1866), 1846)

    def test_validate_rows_rejects_script_errors(self):
        rows = make_rows(1846)
        rows[3]["error_count"] = 2
        with self.assertRaisesRegex(RecordCheckpointError, "error_count must be 0"):
            validate_rows(rows, 1846)

    def test_validate_rows_rejects_non_numeric_population(self):
        rows = make_rows(1846)
        rows[1]["population"] = "many"
        with self.assertRaisesRegex(RecordCheckpointError, "population must be an integer"):
            validate_rows(rows, 1846)

    def test_load_rows_reads_csv_with_and_without_year_column(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            with_year = base / "with-year.csv"
            without_year = base / "no-year.csv"
            write_csv(with_year, 1846, with_year_column=True)
            write_csv(without_year, 1846, with_year_column=False)
            self.assertEqual(len(load_rows(with_year, 1846)), 10)
            self.assertEqual(len(load_rows(without_year, 1846)), 10)

    def test_load_rows_rejects_unknown_csv_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "bad.csv"
            path.write_text("year,country,gdp\n1846,SHU,10\n", encoding="utf-8")
            with self.assertRaisesRegex(RecordCheckpointError, "unknown CSV columns"):
                load_rows(path, 1846)

    def test_merge_rows_keeps_existing_years(self):
        existing = make_rows(1846)
        merged = merge_rows(existing, make_rows(1866), replace=False)
        self.assertEqual(len(merged), 20)
        self.assertEqual(missing_pairs(merged)[0], (1900, "SHU"))

    def test_merge_rows_refuses_to_overwrite_without_replace(self):
        existing = make_rows(1846)
        with self.assertRaisesRegex(RecordCheckpointError, "already recorded"):
            merge_rows(existing, make_rows(1846), replace=False)

    def test_finalize_refuses_incomplete_checkpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            run_root = pathlib.Path(directory) / "none" / "11"
            run_root.mkdir(parents=True)
            checkpoint_path = run_root / "checkpoints.json"
            checkpoint_path.write_text(json.dumps(make_rows(1846)), encoding="utf-8")
            run_json = run_root / "run.json"
            run_json.write_text(json.dumps({"mod_mount": "mounted", "dlc_state_matches_config": "yes"}), encoding="utf-8")
            logs = run_root / "debug.log"
            logs.write_text("log\n", encoding="utf-8")
            with self.assertRaisesRegex(RecordCheckpointError, "still missing"):
                finalize_run(run_json, checkpoint_path, "campaign", logs, None, None)

    def test_finalize_refuses_malformed_complete_checkpoints(self):
        """Thirty expected pairs are insufficient when a measurement is invalid."""
        with tempfile.TemporaryDirectory() as directory:
            run_root = pathlib.Path(directory) / "none" / "11"
            run_root.mkdir(parents=True)
            rows = make_rows(1846) + make_rows(1866) + make_rows(1900)
            rows[0]["population"] = -1
            checkpoint_path = run_root / "checkpoints.json"
            checkpoint_path.write_text(json.dumps(rows), encoding="utf-8")
            run_json = run_root / "run.json"
            run_json.write_text(
                json.dumps(
                    {
                        "config": "none",
                        "run_id": "run-11",
                        "requested_seed": 11,
                        "observed_seed": None,
                        "status": "campaign_started",
                        "game_version": "1.13.11 (Matcha)",
                        "mod_mount": "mounted",
                        "version_match_evidence": "debug.log: version 1.13.11",
                        "expected_mounted_dlc": [],
                        "observed_mounted_dlc": [],
                        "dlc_state_matches_config": "yes",
                        "evidence": {},
                    }
                ),
                encoding="utf-8",
            )
            logs = run_root / "debug.log"
            logs.write_text("log\n", encoding="utf-8")

            with self.assertRaisesRegex(RecordCheckpointError, "negative population"):
                finalize_run(run_json, checkpoint_path, "campaign", logs, None, None)

    def test_finalize_refuses_incomplete_run_metadata(self):
        """A finalized checkpoint must remain consumable by the release summarizer."""
        with tempfile.TemporaryDirectory() as directory:
            run_root = pathlib.Path(directory) / "none" / "11"
            run_root.mkdir(parents=True)
            rows = make_rows(1846) + make_rows(1866) + make_rows(1900)
            checkpoint_path = run_root / "checkpoints.json"
            checkpoint_path.write_text(json.dumps(rows), encoding="utf-8")
            run_json = run_root / "run.json"
            run_json.write_text(
                json.dumps({"mod_mount": "mounted", "dlc_state_matches_config": "yes"}),
                encoding="utf-8",
            )
            logs = run_root / "debug.log"
            logs.write_text("log\n", encoding="utf-8")

            with self.assertRaisesRegex(RecordCheckpointError, "missing evidence fields"):
                finalize_run(run_json, checkpoint_path, "manual campaign", logs, None, None)

    def test_finalize_refuses_preload_only_mount_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            run_root = pathlib.Path(directory) / "none" / "11"
            run_root.mkdir(parents=True)
            rows = make_rows(1846) + make_rows(1866) + make_rows(1900)
            checkpoint_path = run_root / "checkpoints.json"
            checkpoint_path.write_text(json.dumps(rows), encoding="utf-8")
            run_json = run_root / "run.json"
            run_json.write_text(
                json.dumps({"mod_mount": "mounted", "dlc_state_matches_config": "no"}),
                encoding="utf-8",
            )
            logs = run_root / "debug.log"
            logs.write_text("log\n", encoding="utf-8")
            with self.assertRaisesRegex(RecordCheckpointError, "dlc_state_matches_config"):
                finalize_run(run_json, checkpoint_path, "campaign", logs, None, None)

    def test_finalize_writes_observed_status_and_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            run_root = pathlib.Path(directory) / "none" / "11"
            run_root.mkdir(parents=True)
            rows = make_rows(1846) + make_rows(1866) + make_rows(1900)
            checkpoint_path = run_root / "checkpoints.json"
            checkpoint_path.write_text(json.dumps(rows), encoding="utf-8")
            run_json = run_root / "run.json"
            run_json.write_text(
                json.dumps(
                    {
                        "config": "none",
                        "run_id": "run-11",
                        "requested_seed": 11,
                        "observed_seed": None,
                        "status": "campaign_started",
                        "game_version": "1.13.11 (Matcha)",
                        "mod_mount": "mounted",
                        "version_match_evidence": "debug.log: version 1.13.11",
                        "expected_mounted_dlc": [],
                        "observed_mounted_dlc": [],
                        "dlc_state_matches_config": "yes",
                        "evidence": {},
                    }
                ),
                encoding="utf-8",
            )
            logs = run_root / "debug.log"
            logs.write_text("log\n", encoding="utf-8")
            metadata = finalize_run(run_json, checkpoint_path, "manual campaign", logs, 11, None)
            self.assertEqual(metadata["status"], "observed_to_checkpoint")
            self.assertEqual(metadata["observed_seed"], 11)
            self.assertEqual(metadata["evidence"]["campaign"], "manual campaign")
            self.assertEqual(metadata["evidence"]["checkpoint_file"], str(checkpoint_path))

    def test_cli_records_two_years_and_reports_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "observe"
            (root / "none" / "11").mkdir(parents=True)
            first = pathlib.Path(directory) / "1846.csv"
            second = pathlib.Path(directory) / "1866.csv"
            write_csv(first, 1846)
            write_csv(second, 1866)
            for year, source in ((1846, first), (1866, second)):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(RECORDER),
                        "--root",
                        str(root),
                        "--config",
                        "none",
                        "--seed",
                        "11",
                        "--year",
                        str(year),
                        "--input",
                        str(source),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            checkpoints = json.loads((root / "none" / "11" / "checkpoints.json").read_text("utf-8"))
            self.assertEqual(len(checkpoints), 20)
            self.assertIn("missing=10", result.stdout)

    def test_cli_emits_a_blank_template_that_fails_until_filled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "observe"
            template = pathlib.Path(directory) / "1846.csv"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RECORDER),
                    "--root",
                    str(root),
                    "--config",
                    "none",
                    "--seed",
                    "11",
                    "--year",
                    "1846",
                    "--emit-template",
                    str(template),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            lines = template.read_text("utf-8").strip().splitlines()
            self.assertEqual(lines[0], "year,country,rank,population,market,wars,subjects,error_count")
            self.assertEqual(len(lines), 11)
            self.assertEqual(lines[1].split(",")[:2], ["1846", "SHU"])

            unfilled = subprocess.run(
                [
                    sys.executable,
                    str(RECORDER),
                    "--root",
                    str(root),
                    "--config",
                    "none",
                    "--seed",
                    "11",
                    "--year",
                    "1846",
                    "--input",
                    str(template),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(unfilled.returncode, 1)
            self.assertIn("must be an integer", unfilled.stdout)
            self.assertFalse((root / "none" / "11" / "checkpoints.json").exists())

    def test_cli_template_requires_a_year(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(RECORDER),
                    "--config",
                    "none",
                    "--seed",
                    "11",
                    "--emit-template",
                    str(pathlib.Path(directory) / "template.csv"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("requires --year", result.stdout)

    def test_cli_rejects_invalid_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "observe"
            source = pathlib.Path(directory) / "1846.csv"
            lines = ["year,country,rank,population,market,wars,subjects,error_count"]
            for country in COUNTRIES:
                lines.append(f"1846,{country},major_power,-5,{country},0,0,0")
            source.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(RECORDER),
                    "--root",
                    str(root),
                    "--config",
                    "none",
                    "--seed",
                    "11",
                    "--year",
                    "1846",
                    "--input",
                    str(source),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("negative population", result.stdout)
            self.assertFalse((root / "none" / "11" / "checkpoints.json").exists())

    def test_cli_finalize_requires_complete_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "observe"
            run_root = root / "none" / "11"
            run_root.mkdir(parents=True)
            (run_root / "checkpoints.json").write_text(json.dumps(make_rows(1846)), encoding="utf-8")
            (run_root / "run.json").write_text(json.dumps({"mod_mount": "mounted"}), encoding="utf-8")
            logs = run_root / "debug.log"
            logs.write_text("log\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(RECORDER),
                    "--root",
                    str(root),
                    "--config",
                    "none",
                    "--seed",
                    "11",
                    "--finalize",
                    "--campaign",
                    "manual campaign",
                    "--logs",
                    str(logs),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("still missing", result.stdout)


if __name__ == "__main__":
    unittest.main()
