import contextlib
import io
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from test_v03_generator import write_fixture
from tools.build_v03_content import build
from tools.ywc_check import validate


class V03IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        write_fixture(self.root)
        self.mod_root = self.root / "yongchang_world"
        self.mod_root.mkdir()
        self.assertEqual([], build(self.root))

    def tearDown(self):
        self.temp.cleanup()

    def test_total_check_calls_v03_checker_for_real_manifest(self):
        with patch("tools.ywc_v03_check.check_root", return_value=["sentinel v03 failure"]) as check:
            diagnostics = validate(self.mod_root)
        check.assert_called_once_with(self.root, require_complete=False)
        self.assertTrue(any("sentinel v03 failure" in item for item in diagnostics), diagnostics)

    def test_missing_translation_fails_total_check(self):
        catalog_path = self.root / "data/content/v03/countries/shu.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        del catalog["arcs"][0]["events"][0]["title"]["en"]
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        diagnostics = validate(self.mod_root)
        self.assertTrue(any("title.en" in item for item in diagnostics), diagnostics)

    def test_dangling_journal_reference_fails_total_check(self):
        allowlist = self.root / "data/content/reachability_allowlist.json"
        allowlist.parent.mkdir(parents=True, exist_ok=True)
        allowlist.write_text(json.dumps({"unused_scripted_helpers": {}}), encoding="utf-8")
        script = self.mod_root / "common/on_actions/v03_integration.txt"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            "on_game_started = { add_journal_entry = { type = ywc_je_v03_missing_arc_main } }\n",
            encoding="utf-8",
        )
        diagnostics = validate(self.mod_root)
        self.assertTrue(any("dangling content reference ywc_je_v03_missing_arc_main" in item
                            for item in diagnostics), diagnostics)

    def test_stale_generated_output_fails_total_check(self):
        generated = self.mod_root / "events/ywc_v03_country_shu_events.txt"
        generated.write_text(generated.read_text(encoding="utf-8-sig") + "# changed\n", encoding="utf-8")
        diagnostics = validate(self.mod_root)
        self.assertTrue(any("stale generated output mismatch" in item for item in diagnostics), diagnostics)

    def test_incomplete_quota_is_development_valid_but_release_blocked(self):
        from tools.ywc_check import main

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(0, main(["--mod-root", str(self.mod_root)]))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, main(["--mod-root", str(self.mod_root), "--require-complete"]))


if __name__ == "__main__":
    unittest.main()
