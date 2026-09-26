import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from tools.inspect_playsets import evaluate, load_playsets


ROOT = pathlib.Path(__file__).parents[1]
INSPECTOR = ROOT / "tools/inspect_playsets.py"
GATE_DLCS = ("dlc010_ep1", "dlc013_mp1", "dlc018_ep2")

SCHEMA = """
CREATE TABLE playsets (id TEXT, name TEXT, isActive INTEGER, isRemoved INTEGER);
CREATE TABLE mods (id TEXT, name TEXT, displayName TEXT, dirPath TEXT);
CREATE TABLE playsets_mods (playsetId TEXT, modId TEXT, enabled INTEGER, position INTEGER);
CREATE TABLE playsets_dlcs (playsetId TEXT, dlcId TEXT, enabled INTEGER);
"""


def build_database(path: pathlib.Path, config: dict) -> None:
    """config maps a playset name to {'dlc': iterable, 'mods': [(name, enabled)], 'other': [(name, enabled)]}."""

    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA)
        for index, (name, spec) in enumerate(config.items()):
            playset_id = f"playset-{index}"
            connection.execute(
                "INSERT INTO playsets VALUES (?, ?, ?, 0)",
                (playset_id, name, 1 if spec.get("active") else 0),
            )
            mod_index = 0
            for mod_name, enabled in spec.get("mods", []) + spec.get("other", []):
                mod_id = f"mod-{index}-{mod_index}"
                mod_index += 1
                connection.execute(
                    "INSERT INTO mods VALUES (?, ?, ?, ?)",
                    (mod_id, mod_name, mod_name, f"D:/mods/{mod_name}"),
                )
                connection.execute(
                    "INSERT INTO playsets_mods VALUES (?, ?, ?, ?)",
                    (playset_id, mod_id, 1 if enabled else 0, mod_index),
                )
            for dlc_id, enabled in spec.get("dlc", {}).items():
                connection.execute(
                    "INSERT INTO playsets_dlcs VALUES (?, ?, ?)",
                    (playset_id, dlc_id, 1 if enabled else 0),
                )
        connection.commit()
    finally:
        connection.close()


def complete_config() -> dict:
    return {
        "none": {"mods": [("yongchang_world", True)], "dlc": {dlc: False for dlc in GATE_DLCS}},
        "sphere": {"mods": [("yongchang_world", True)], "dlc": {"dlc010_ep1": True, "dlc013_mp1": False, "dlc018_ep2": False}},
        "charters": {"mods": [("yongchang_world", True)], "dlc": {"dlc013_mp1": True, "dlc010_ep1": False, "dlc018_ep2": False}},
        "wave": {"mods": [("yongchang_world", True)], "dlc": {"dlc018_ep2": True, "dlc010_ep1": False, "dlc013_mp1": False}},
        "all": {"mods": [("yongchang_world", True)], "dlc": {dlc: True for dlc in GATE_DLCS}},
    }


class InspectPlaysetsTest(unittest.TestCase):
    def test_complete_configuration_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "launcher-v2.sqlite"
            build_database(path, complete_config())
            report = evaluate(load_playsets(path))
            self.assertEqual(len(report), 5)
            self.assertTrue(all(row["matches"] for row in report), report)

    def test_missing_playset_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "launcher-v2.sqlite"
            config = complete_config()
            del config["wave"]
            build_database(path, config)
            report = {row["config"]: row for row in evaluate(load_playsets(path))}
            self.assertFalse(report["wave"]["matches"])
            self.assertIn("does not exist", report["wave"]["reasons"][0])

    def test_wrong_dlc_set_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "launcher-v2.sqlite"
            config = complete_config()
            config["sphere"]["dlc"] = {dlc: True for dlc in GATE_DLCS}
            build_database(path, config)
            report = {row["config"]: row for row in evaluate(load_playsets(path))}
            self.assertFalse(report["sphere"]["matches"])
            self.assertTrue(any("DLC set" in reason for reason in report["sphere"]["reasons"]))

    def test_unrecorded_dlc_is_not_assumed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "launcher-v2.sqlite"
            config = complete_config()
            config["none"]["dlc"] = {"dlc010_ep1": False}
            build_database(path, config)
            report = {row["config"]: row for row in evaluate(load_playsets(path))}
            self.assertFalse(report["none"]["matches"])
            self.assertEqual(report["none"]["unknown_dlc"], ["dlc013_mp1", "dlc018_ep2"])

    def test_other_enabled_mods_are_flagged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "launcher-v2.sqlite"
            config = complete_config()
            config["all"]["other"] = [("Daoyu Cheat", True)]
            build_database(path, config)
            report = {row["config"]: row for row in evaluate(load_playsets(path))}
            self.assertFalse(report["all"]["matches"])
            self.assertTrue(any("contaminate" in reason for reason in report["all"]["reasons"]))

    def test_disabled_target_mod_is_flagged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "launcher-v2.sqlite"
            config = complete_config()
            config["none"]["mods"] = [("yongchang_world", False)]
            build_database(path, config)
            report = {row["config"]: row for row in evaluate(load_playsets(path))}
            self.assertFalse(report["none"]["mod_enabled"])

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            good = base / "good"
            good.mkdir()
            build_database(good / "launcher-v2.sqlite", complete_config())
            result = subprocess.run(
                [sys.executable, str(INSPECTOR), "--user-data-dir", str(good)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("active playset", result.stdout)

            bad = base / "bad"
            bad.mkdir()
            build_database(bad / "launcher-v2.sqlite", {"none": {"mods": [], "dlc": {}}})
            result = subprocess.run(
                [sys.executable, str(INSPECTOR), "--user-data-dir", str(bad)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not exist", result.stdout)

    def test_cli_writes_json_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            good = base / "good"
            good.mkdir()
            build_database(good / "launcher-v2.sqlite", complete_config())
            output = base / "launcher-evidence.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(INSPECTOR),
                    "--user-data-dir",
                    str(good),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text("utf-8"))
            self.assertTrue(payload["all_match"])
            self.assertEqual(len(payload["configs"]), 5)

    def test_cli_reports_missing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(INSPECTOR), "--user-data-dir", directory],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not exist", result.stdout)


if __name__ == "__main__":
    unittest.main()
