import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tools.content_reachability import audit


ROOT = pathlib.Path(__file__).parents[1]
TOOL = ROOT / "tools/content_reachability.py"
MOD_ROOT = ROOT / "yongchang_world"

CLEAN_FIXTURE = {
    "events/ywc_test_events.txt": (
        "namespace = ywc_test\n"
        "ywc_test.1 = { type = country_event title = ywc_test.1.t desc = ywc_test.1.d "
        "option = { name = ywc_test.1.a } }\n"
    ),
    "common/journal_entries/ywc_test_journal.txt": (
        "ywc_je_test = { on_monthly_pulse = { effect = { trigger_event = { id = ywc_test.1 } } } }\n"
    ),
    "common/history/countries/ywc_test_start.txt": (
        "c:SHU = { effect = { add_journal_entry = { type = ywc_je_test } } }\n"
    ),
}


def build_fixture(base: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    for relative, text in files.items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return base


class ContentReachabilityTest(unittest.TestCase):
    def test_clean_fixture_has_no_problems(self):
        with tempfile.TemporaryDirectory() as directory:
            base = build_fixture(pathlib.Path(directory) / "mod", CLEAN_FIXTURE)
            report = audit(base, pathlib.Path(directory) / "missing-allowlist.json")
            self.assertEqual(report["event_count"], 1)
            self.assertEqual(report["journal_count"], 1)
            self.assertEqual(report["dangling_references"], [])
            self.assertEqual(report["unreferenced_events"], [])
            self.assertEqual(report["unreferenced_journals"], [])
            self.assertEqual(report["unused_scripted_helpers"], [])

    def test_dangling_event_reference_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            files = dict(CLEAN_FIXTURE)
            files["common/journal_entries/ywc_test_journal.txt"] = (
                "ywc_je_test = { on_monthly_pulse = { effect = { trigger_event = { id = ywc_test.99 } } } }\n"
            )
            base = build_fixture(pathlib.Path(directory) / "mod", files)
            report = audit(base, pathlib.Path(directory) / "missing-allowlist.json")
            self.assertEqual(report["dangling_references"], ["ywc_test.99"])

    def test_unreferenced_event_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            files = dict(CLEAN_FIXTURE)
            files["events/ywc_test_events.txt"] += (
                "ywc_test.2 = { type = country_event title = ywc_test.2.t desc = ywc_test.2.d "
                "option = { name = ywc_test.2.a } }\n"
            )
            base = build_fixture(pathlib.Path(directory) / "mod", files)
            report = audit(base, pathlib.Path(directory) / "missing-allowlist.json")
            self.assertEqual(report["unreferenced_events"], ["ywc_test.2"])

    def test_unreferenced_journal_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            files = dict(CLEAN_FIXTURE)
            files["common/journal_entries/ywc_test_journal.txt"] += "ywc_je_orphan = { complete = { always = yes } }\n"
            base = build_fixture(pathlib.Path(directory) / "mod", files)
            report = audit(base, pathlib.Path(directory) / "missing-allowlist.json")
            self.assertEqual(report["unreferenced_journals"], ["ywc_je_orphan"])

    def test_unused_helper_requires_an_allowlist_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory) / "mod"
            files = dict(CLEAN_FIXTURE)
            files["common/scripted_triggers/ywc_test_triggers.txt"] = "ywc_test_unused = { always = yes }\n"
            build_fixture(base, files)
            report = audit(base, pathlib.Path(directory) / "missing-allowlist.json")
            self.assertEqual(report["unused_scripted_helpers"], ["ywc_test_unused"])

            allowlist = pathlib.Path(directory) / "allowlist.json"
            allowlist.write_text(
                json.dumps({"unused_scripted_helpers": {"ywc_test_unused": "kept as a readable alias"}}),
                encoding="utf-8",
            )
            report = audit(base, allowlist)
            self.assertEqual(report["unused_scripted_helpers"], [])
            self.assertEqual(report["allowlisted_helpers"], ["ywc_test_unused"])

    def test_cli_exit_codes_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            base = build_fixture(pathlib.Path(directory) / "mod", CLEAN_FIXTURE)
            allowlist = pathlib.Path(directory) / "allowlist.json"
            allowlist.write_text(json.dumps({"unused_scripted_helpers": {}}), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(TOOL), "--root", str(base), "--allowlist", str(allowlist)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Content reachability is clean", result.stdout)

            files = dict(CLEAN_FIXTURE)
            files["events/ywc_test_events.txt"] += "ywc_test.3 = { }\n"
            bad = build_fixture(pathlib.Path(directory) / "bad", files)
            result = subprocess.run(
                [sys.executable, str(TOOL), "--root", str(bad), "--allowlist", str(allowlist)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("unreferenced event: ywc_test.3", result.stdout)

    def test_repository_content_is_fully_reachable(self):
        """Every shipped event and journal entry must have a trigger or a setter."""

        report = audit(MOD_ROOT, ROOT / "data/content/reachability_allowlist.json")
        self.assertEqual(report["dangling_references"], [])
        self.assertEqual(report["unreferenced_events"], [])
        self.assertEqual(report["unreferenced_journals"], [])
        self.assertEqual(report["unused_scripted_helpers"], [])
        # 92 pre-campaign events + 150 national chapter events + 30 crisis
        # events; 74 pre-campaign journals + 5 cross-country crisis journals.
        self.assertEqual(report["event_count"], 272)
        self.assertEqual(report["journal_count"], 79)


if __name__ == "__main__":
    unittest.main()
