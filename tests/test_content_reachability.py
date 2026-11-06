import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tools.content_reachability import audit
from tools.build_v03_content import load_catalogs


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

    def test_country_filtered_auto_journal_is_a_valid_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            files = dict(CLEAN_FIXTURE)
            files["common/journal_entries/ywc_test_journal.txt"] = (
                "ywc_je_auto = {\n"
                "  is_shown_when_inactive = { c:SHU ?= this }\n"
                "  possible = { c:SHU ?= this }\n"
                "  complete = { always = yes }\n"
                "}\n"
            )
            base = build_fixture(pathlib.Path(directory) / "mod", files)
            report = audit(base, pathlib.Path(directory) / "missing-allowlist.json")
            self.assertEqual(report["unreferenced_journals"], [])

    def test_auto_journal_without_country_filter_stays_unreferenced(self):
        with tempfile.TemporaryDirectory() as directory:
            files = dict(CLEAN_FIXTURE)
            files["common/journal_entries/ywc_test_journal.txt"] = (
                "ywc_je_auto = {\n"
                "  is_shown_when_inactive = { always = yes }\n"
                "  possible = { always = yes }\n"
                "  complete = { always = yes }\n"
                "}\n"
            )
            base = build_fixture(pathlib.Path(directory) / "mod", files)
            report = audit(base, pathlib.Path(directory) / "missing-allowlist.json")
            self.assertEqual(report["unreferenced_journals"], ["ywc_je_auto"])

    def test_auto_journal_requires_the_same_current_country_in_both_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            files = dict(CLEAN_FIXTURE)
            files["common/journal_entries/ywc_test_journal.txt"] = (
                "ywc_je_auto = {\n"
                "  is_shown_when_inactive = { c:SHU = this }\n"
                "  possible = { c:DMG = this }\n"
                "  immediate = { is_shown_when_inactive = { c:SHU = this } }\n"
                "}\n"
            )
            base = build_fixture(pathlib.Path(directory) / "mod", files)
            report = audit(base, pathlib.Path(directory) / "missing-allowlist.json")
            self.assertEqual(report["unreferenced_journals"], ["ywc_je_auto"])

    def test_route_reference_is_counted_and_dangling_route_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            files = dict(CLEAN_FIXTURE)
            files["common/journal_entries/ywc_test_journal.txt"] += (
                "ywc_route_test = { complete = { always = yes } }\n"
            )
            files["common/history/countries/ywc_test_start.txt"] += (
                "c:SHU = { effect = { add_journal_entry = { type = ywc_route_test } } }\n"
            )
            base = build_fixture(pathlib.Path(directory) / "mod", files)
            report = audit(base, pathlib.Path(directory) / "missing-allowlist.json")
            self.assertEqual(report["journal_count"], 2)
            self.assertEqual(report["dangling_references"], [])
            self.assertEqual(report["unreferenced_journals"], [])

            route_file = base / "common/journal_entries/ywc_test_journal.txt"
            route_file.write_text(
                route_file.read_text(encoding="utf-8").replace(
                    "ywc_route_test = { complete = { always = yes } }\n", ""
                ), encoding="utf-8"
            )
            report = audit(base, pathlib.Path(directory) / "missing-allowlist.json")
            self.assertEqual(report["dangling_references"], ["ywc_route_test"])

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
        legacy = json.loads((ROOT / "data/content/v03/legacy_ids.json").read_text(encoding="utf-8"))
        old_events = set(legacy["events"])
        old_journals = set(legacy["journals"])
        old_routes = set(legacy["routes"])
        self.assertEqual(len(old_events), len(legacy["events"]))
        self.assertEqual(len(old_journals), len(legacy["journals"]))
        self.assertEqual(len(old_routes), len(legacy["routes"]))

        catalogs = load_catalogs(ROOT)
        new_events = {
            event["id"]
            for catalog in catalogs.values()
            for arc in catalog["arcs"]
            for event in arc["events"]
        }
        new_journals = {
            journal["id"]
            for catalog in catalogs.values()
            for arc in catalog["arcs"]
            for journal in arc["journals"]
        }
        catalog_event_count = sum(
            len(arc["events"]) for catalog in catalogs.values() for arc in catalog["arcs"]
        )
        catalog_journal_count = sum(
            len(arc["journals"]) for catalog in catalogs.values() for arc in catalog["arcs"]
        )
        self.assertEqual(len(new_events), catalog_event_count)
        self.assertEqual(len(new_journals), catalog_journal_count)
        old_ids = old_events | old_journals | old_routes
        new_ids = new_events | new_journals
        self.assertTrue(old_ids.isdisjoint(new_ids), sorted(old_ids & new_ids))
        self.assertTrue(new_events.isdisjoint(new_journals), sorted(new_events & new_journals))

        # Keep the frozen pre-catalog identity set; count the new side from the
        # source catalogs. The audit count comes independently from generated scripts.
        self.assertEqual(report["event_count"], len(old_events | new_events))
        self.assertEqual(report["journal_count"], len(old_journals | old_routes | new_journals))
        self.assertEqual(report["route_count"], len(old_routes))


if __name__ == "__main__":
    unittest.main()
