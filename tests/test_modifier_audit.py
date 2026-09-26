import pathlib
import subprocess
import sys
import tempfile
import unittest

from tools.modifier_audit import audit, collect_modifier_types
from tools.ywc_check import validate


ROOT = pathlib.Path(__file__).parents[1]
TOOL = ROOT / "tools/modifier_audit.py"
MOD_ROOT = ROOT / "yongchang_world"
GAME_ROOT = pathlib.Path(r"E:/SteamLibrary/steamapps/common/Victoria 3/game")

DEFINITIONS = (
    "country_authority_mult={\n\tdecimals=0\n}\n"
    "state_birth_rate_mult={\n\tdecimals=2\n}\n"
    "country_free_charters_add={\n\tdecimals=0\n}\n"
)


def build_fixture(base: pathlib.Path, modifier_text: str, extra: dict[str, str] | None = None) -> tuple[pathlib.Path, pathlib.Path]:
    mod = base / "mod"
    game = base / "game"
    definitions = game / "common/modifier_type_definitions"
    definitions.mkdir(parents=True)
    (definitions / "00_modifier_types.txt").write_text(DEFINITIONS, encoding="utf-8")
    statics = mod / "common/static_modifiers"
    statics.mkdir(parents=True)
    (statics / "ywc_test.txt").write_text(modifier_text, encoding="utf-8")
    for relative, text in (extra or {}).items():
        path = mod / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return mod, game


class ModifierAuditTest(unittest.TestCase):
    def test_collects_every_definition_not_just_the_first(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(pathlib.Path(directory) / "ok", "ywc_test = {\n\tcountry_authority_mult = 0.05\n}\n")
            valid, dlc_gated = collect_modifier_types(game)
            self.assertEqual(len(valid), 3)
            self.assertEqual(dlc_gated, set())

    def test_known_modifier_keys_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "ok",
                "ywc_test = {\n\tcountry_authority_mult = 0.05\n\tstate_birth_rate_mult = 0.10\n}\n",
            )
            report = audit(mod, game)
            self.assertEqual(report["unknown_modifier_types"], [])
            self.assertEqual(report["checked_keys"], 2)
            self.assertEqual(report["static_modifiers"], 1)

    def test_unknown_modifier_key_is_reported_with_its_line(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "bad",
                "ywc_test = {\n\tcountry_tax_capacity_mult = 0.05\n}\n",
            )
            report = audit(mod, game)
            self.assertEqual(len(report["unknown_modifier_types"]), 1)
            self.assertIn("country_tax_capacity_mult", report["unknown_modifier_types"][0])
            self.assertIn(":2:", report["unknown_modifier_types"][0])

    def test_metadata_keys_are_not_modifier_types(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "meta",
                "ywc_test = {\n\ticon = \"gfx/interface/icons/x.dds\"\n\tcolor = good\n\tcountry_authority_mult = 0.05\n}\n",
            )
            report = audit(mod, game)
            self.assertEqual(report["unknown_modifier_types"], [])
            self.assertEqual(report["checked_keys"], 1)

    def test_undeclared_add_modifier_reference_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "ref",
                "ywc_test = {\n\tcountry_authority_mult = 0.05\n}\n",
                {"events/ywc_test_events.txt": "ywc_test.1 = {\n\toption = { add_modifier = { name = ywc_missing months = 12 } }\n}\n"},
            )
            report = audit(mod, game)
            self.assertEqual(len(report["undeclared_modifier_references"]), 1)
            self.assertIn("ywc_missing", report["undeclared_modifier_references"][0])

    def test_declared_add_modifier_reference_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "ref-ok",
                "ywc_test = {\n\tcountry_authority_mult = 0.05\n}\n",
                {"events/ywc_test_events.txt": "ywc_test.1 = {\n\toption = { add_modifier = { name = ywc_test months = 12 } }\n}\n"},
            )
            report = audit(mod, game)
            self.assertEqual(report["undeclared_modifier_references"], [])

    def test_cli_reports_missing_definition_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--mod-root",
                    str(pathlib.Path(directory)),
                    "--game-root",
                    str(pathlib.Path(directory)),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("modifier_type_definitions", result.stdout)

    def test_ywc_check_runs_the_modifier_audit_when_a_game_root_is_given(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "wired",
                "ywc_test = {\n\tcountry_convoy_capacity_mult = 0.05\n}\n",
            )
            diagnostics = validate(mod, game)
            self.assertTrue(
                any("unknown modifier type country_convoy_capacity_mult" in item for item in diagnostics),
                diagnostics,
            )
            # Without a game root the audit cannot run, so it must not guess.
            self.assertFalse(
                any("unknown modifier type" in item for item in validate(mod))
            )

    def test_repository_modifiers_use_installed_modifier_types(self):
        if not (GAME_ROOT / "common/modifier_type_definitions").is_dir():
            self.skipTest(f"game root is unavailable: {GAME_ROOT}")
        report = audit(MOD_ROOT, GAME_ROOT)
        self.assertEqual(report["unknown_modifier_types"], [])
        self.assertEqual(report["undeclared_modifier_references"], [])
        self.assertGreater(report["checked_keys"], 100)


if __name__ == "__main__":
    unittest.main()
