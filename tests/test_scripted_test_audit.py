import pathlib
import subprocess
import sys
import tempfile
import unittest

from tools.scripted_test_audit import audit, build_vocabulary, suite_keys


ROOT = pathlib.Path(__file__).parents[1]
TOOL = ROOT / "tools/scripted_test_audit.py"
MOD_ROOT = ROOT / "yongchang_world"
GAME_ROOT = pathlib.Path(r"E:/SteamLibrary/steamapps/common/Victoria 3/game")

CLEAN_SUITE = (
    'last_date = "1836.2.1"\n'
    "\n"
    "tests = {\n"
    "    YWC_FIXTURE_CASE = {\n"
    "        acceptable_fail_rate = 0.0\n"
    "        success = {\n"
    "            exists = c:SHU\n"
    "            c:SHU ?= { has_variable = ywc_dlc_base_path }\n"
    "        }\n"
    "        fail = { game_date > \"1836.2.1\" }\n"
    "    }\n"
    "}\n"
)


def build_fixture(base: pathlib.Path, suite_text: str) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    mod = base / "mod"
    game = base / "game"
    suite = mod / "tools/scripted_tests/ywc_fixture.txt"
    suite.parent.mkdir(parents=True)
    suite.write_text(suite_text, encoding="utf-8")
    triggers = game / "common/scripted_triggers"
    triggers.mkdir(parents=True)
    (triggers / "vanilla.txt").write_text(
        "vanilla_only_trigger = {\n\talways = yes\n}\n", encoding="utf-8"
    )
    events = game / "events"
    events.mkdir(parents=True)
    (events / "vanilla_events.txt").write_text(
        "namespace = vanilla\nvanilla.1 = {\n\ttrigger = {\n\t\texists = c:ITA\n\t\thas_variable = x\n\t}\n}\n",
        encoding="utf-8",
    )
    return mod, game, suite


class ScriptedTestAuditTest(unittest.TestCase):
    def test_suite_keys_exclude_test_case_names(self):
        keys = suite_keys(CLEAN_SUITE)
        self.assertIn("tests", keys)
        self.assertIn("success", keys)
        self.assertNotIn("YWC_FIXTURE_CASE", keys)

    def test_format_keys_are_recognised(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game, _suite = build_fixture(pathlib.Path(directory) / "ok", CLEAN_SUITE)
            report = audit(mod, game)
            self.assertEqual(report["unknown_keys"], [])
            self.assertEqual(len(report["suites"]), 1)
            self.assertEqual(report["suites"]["ywc_fixture.txt"]["test_cases"], ["YWC_FIXTURE_CASE"])

    def test_vanilla_trigger_is_grounded_by_the_corpus(self):
        text = CLEAN_SUITE.replace("exists = c:SHU", "vanilla_only_trigger = yes")
        with tempfile.TemporaryDirectory() as directory:
            mod, game, _suite = build_fixture(pathlib.Path(directory) / "grounded", text)
            report = audit(mod, game)
            self.assertEqual(report["unknown_keys"], [])

    def test_unknown_trigger_is_reported_with_its_line(self):
        text = CLEAN_SUITE.replace("exists = c:SHU", "definitely_not_a_trigger = yes")
        with tempfile.TemporaryDirectory() as directory:
            mod, game, _suite = build_fixture(pathlib.Path(directory) / "bad", text)
            report = audit(mod, game)
            self.assertEqual(len(report["unknown_keys"]), 1)
            self.assertIn("definitely_not_a_trigger", report["unknown_keys"][0])
            self.assertIn(":7:", report["unknown_keys"][0])

    def test_mod_declared_names_count_as_grounded(self):
        text = CLEAN_SUITE.replace("exists = c:SHU", "ywc_fixture_helper = yes")
        with tempfile.TemporaryDirectory() as directory:
            mod, game, _suite = build_fixture(pathlib.Path(directory) / "mod", text)
            helper = mod / "common/scripted_triggers/ywc_fixture_triggers.txt"
            helper.parent.mkdir(parents=True, exist_ok=True)
            helper.write_text("ywc_fixture_helper = {\n\talways = yes\n}\n", encoding="utf-8")
            report = audit(mod, game)
            self.assertEqual(report["unknown_keys"], [])

    def test_full_corpus_widens_the_vocabulary(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game, _suite = build_fixture(pathlib.Path(directory) / "full", CLEAN_SUITE)
            extra = game / "common/buildings"
            extra.mkdir(parents=True)
            (extra / "vanilla_buildings.txt").write_text(
                "building_only_trigger = {\n\talways = yes\n}\n", encoding="utf-8"
            )
            self.assertNotIn("building_only_trigger", build_vocabulary(game))
            self.assertIn("building_only_trigger", build_vocabulary(game, full=True))

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game, _suite = build_fixture(pathlib.Path(directory) / "cli", CLEAN_SUITE)
            result = subprocess.run(
                [sys.executable, str(TOOL), "--mod-root", str(mod), "--game-root", str(game)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("grounded in the installed game", result.stdout)

    def test_repository_suites_use_grounded_vocabulary(self):
        if not GAME_ROOT.is_dir():
            self.skipTest(f"game root is unavailable: {GAME_ROOT}")
        report = audit(MOD_ROOT, GAME_ROOT)
        self.assertEqual(report["unknown_keys"], [], report["unknown_keys"])
        self.assertIn("ywc_startup_smoke.txt", report["suites"])
        self.assertIn("ywc_longrun_invariants.txt", report["suites"])
        self.assertLessEqual(
            {"tests", "last_date", "success", "fail"},
            set(report["used_keys"]),
        )


if __name__ == "__main__":
    unittest.main()
