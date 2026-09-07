import pathlib
import shutil
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / "tools/collect_smoke_logs.ps1"


class SmokeLogCollectorTest(unittest.TestCase):
    def run_collector(self, user_data_root, *extra_args):
        return subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-NoLaunch",
                "-UserDataRoot",
                str(user_data_root),
                *extra_args,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_clean_logs_return_zero_and_write_summary(self):
        result = self.run_collector(ROOT / "tests/fixtures/userdata-clean")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = (ROOT / "artifacts/smoke/latest-summary.txt").read_text("utf-8")
        self.assertIn("status=clean", summary)

    def test_mod_error_returns_one_and_prints_offending_line(self):
        result = self.run_collector(ROOT / "tests/fixtures/userdata-broken")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown trigger ywc_missing_trigger", result.stdout)

    def test_collector_uses_redirected_windows_documents_by_default(self):
        script = SCRIPT.read_text("utf-8")
        self.assertIn("[Environment]::GetFolderPath('MyDocuments')", script)
        self.assertNotIn("$env:USERPROFILE 'Documents", script)

    def test_collector_reports_unknown_mount_without_debug_log(self):
        result = self.run_collector(ROOT / "tests/fixtures/userdata-clean")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = (ROOT / "artifacts/smoke/latest-summary.txt").read_text("utf-8")
        self.assertIn("mod_mount=unknown_no_debug_log", summary)

    def test_collector_detects_mounted_mod_from_debug_log(self):
        result = self.run_collector(ROOT / "tests/fixtures/userdata-mounted")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = (ROOT / "artifacts/smoke/latest-summary.txt").read_text("utf-8")
        self.assertIn("mod_mount=mounted", summary)
        self.assertIn("Mounted Data: E:/Victoria3 Mod/yongchang_world", summary)

    def test_collector_reports_unmounted_mod_when_debug_log_lacks_yongchang(self):
        result = self.run_collector(ROOT / "tests/fixtures/userdata-mounted-none")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = (ROOT / "artifacts/smoke/latest-summary.txt").read_text("utf-8")
        self.assertIn("mod_mount=not_mounted", summary)

    def test_required_scripted_tests_reject_empty_engine_result(self):
        with tempfile.TemporaryDirectory() as temporary_root:
            user_data_root = pathlib.Path(temporary_root) / "userdata"
            shutil.copytree(ROOT / "tests/fixtures/userdata-clean", user_data_root)
            (user_data_root / "tests.txt").write_text("Tests:\n", encoding="utf-8")
            summary_path = ROOT / "artifacts/smoke/latest-summary.txt"
            if summary_path.exists():
                summary_path.unlink()
            result = self.run_collector(user_data_root, "-RequireScriptedTests")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(summary_path.is_file(), result.stderr)
        summary = (ROOT / "artifacts/smoke/latest-summary.txt").read_text("utf-8-sig")
        self.assertIn("scripted_tests=empty", summary)
        self.assertIn("scripted test results are empty", result.stdout)


if __name__ == "__main__":
    unittest.main()
