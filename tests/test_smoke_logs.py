import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / "tools/collect_smoke_logs.ps1"


class SmokeLogCollectorTest(unittest.TestCase):
    def run_collector(self, user_data_root):
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


if __name__ == "__main__":
    unittest.main()
