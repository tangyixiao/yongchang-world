import pathlib
import subprocess
import sys
import tempfile
import unittest

from tools.startup_data_audit import audit


ROOT = pathlib.Path(__file__).parents[1]
TOOL = ROOT / "tools/startup_data_audit.py"
MOD_ROOT = ROOT / "yongchang_world"
GAME_ROOT = pathlib.Path(r"E:/SteamLibrary/steamapps/common/Victoria 3/game")

GAME_FILES = {
    "map_data/state_regions/00_fixture.txt": (
        "STATE_TESTA = {\n"
        "    arable_land = 30\n"
        '    arable_resources = { "building_rye_farm" }\n'
        "    capped_resources = {\n        building_logging_camp = 20\n    }\n"
        "}\n"
        # No arable or capped capacity at all: a farm here has zero capacity.
        "STATE_TESTB = {\n    arable_land = 0\n    arable_resources = { }\n}\n"
    ),
    "common/buildings/00_fixture.txt": (
        "building_rye_farm = { }\nbuilding_logging_camp = { }\n"
        "building_government_administration = { }\n"
    ),
    "common/cultures/00_cultures.txt": "han = { }\ntibetan = { }\n",
    "common/religions/religion.txt": "buddhist = { }\n",
    "common/pop_types/laborers.txt": "laborers = { }\n",
    # Vanilla itself places the administration building without a capacity
    # entry, which is how the tool learns which buildings are urban.
    "common/history/buildings/00_fixture.txt": (
        "BUILDINGS = {\n"
        "    s:STATE_TESTA = {\n"
        "        region_state:TST = {\n"
        "            create_building = {\n"
        '                building = "building_government_administration"\n'
        "                add_ownership = { country = { country = \"c:TST\" levels = 1 } }\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "}\n"
    ),
}

VALID_BUILDINGS = (
    "BUILDINGS = {\n"
    "    s:STATE_TESTA = {\n"
    "        region_state:TST = {\n"
    "            create_building = {\n"
    '                building = "building_rye_farm"\n'
    "                add_ownership = { country = { country = \"c:TST\" levels = 2 } }\n"
    "            }\n"
    "            create_building = {\n"
    '                building = "building_government_administration"\n'
    "                level = 1\n"
    "            }\n"
    "        }\n"
    "    }\n"
    "}\n"
)

VALID_POPS = (
    "POPS = {\n"
    "    s:STATE_TESTA = {\n"
    "        region_state:TST = {\n"
    "            create_pop = { culture = han size = 1000 religion = buddhist pop_type = laborers }\n"
    "        }\n"
    "    }\n"
    "}\n"
)


def build_fixture(base: pathlib.Path, files: dict[str, str]) -> tuple[pathlib.Path, pathlib.Path]:
    mod = base / "mod"
    game = base / "game"
    for relative, text in GAME_FILES.items():
        path = game / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    for relative, text in files.items():
        path = mod / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return mod, game


class StartupDataAuditTest(unittest.TestCase):
    def test_valid_startup_data_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "ok",
                {
                    "common/history/buildings/ywc_test.txt": VALID_BUILDINGS,
                    "common/history/pops/ywc_test.txt": VALID_POPS,
                },
            )
            report = audit(mod, game)
            self.assertEqual(report["problems"], [])
            self.assertEqual(report["checked_buildings"], 2)
            self.assertEqual(report["checked_pops"], 3)

    def test_unknown_building_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "unknown",
                {
                    "common/history/buildings/ywc_test.txt": VALID_BUILDINGS.replace(
                        "building_rye_farm", "building_rye_castle"
                    )
                },
            )
            report = audit(mod, game)
            self.assertTrue(
                any("unknown building building_rye_castle" in item for item in report["problems"]),
                report["problems"],
            )

    def test_zero_capacity_building_is_reported(self):
        """The KUC logging camp / wheat farm / fishing wharf class of mistake."""

        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "capacity",
                {
                    "common/history/buildings/ywc_test.txt": VALID_BUILDINGS.replace(
                        "STATE_TESTA", "STATE_TESTB"
                    )
                },
            )
            report = audit(mod, game)
            self.assertTrue(
                any("zero capacity" in item and "building_rye_farm" in item for item in report["problems"]),
                report["problems"],
            )

    def test_negative_level_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "level",
                {
                    "common/history/buildings/ywc_test.txt": VALID_BUILDINGS.replace(
                        "levels = 2", "levels = 0"
                    )
                },
            )
            report = audit(mod, game)
            self.assertTrue(
                any("non-positive level 0" in item for item in report["problems"]), report["problems"]
            )

    def test_missing_level_is_not_an_error(self):
        """Vanilla omits `level` for some entries, so absence must stay legal."""

        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "no-level",
                {
                    "common/history/buildings/ywc_test.txt": (
                        "BUILDINGS = {\n    s:STATE_TESTA = {\n        region_state:TST = {\n"
                        '            create_building = { building = "building_rye_farm" }\n'
                        "        }\n    }\n}\n"
                    )
                },
            )
            report = audit(mod, game)
            self.assertEqual(report["problems"], [])

    def test_mod_defined_building_is_not_checked_against_vanilla_capacity(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "custom",
                {
                    "common/buildings/ywc_custom.txt": "building_ywc_south_sea_station = { }\n",
                    "common/history/buildings/ywc_test.txt": VALID_BUILDINGS.replace(
                        "building_rye_farm", "building_ywc_south_sea_station"
                    ),
                },
            )
            report = audit(mod, game)
            self.assertEqual(report["problems"], [])

    def test_unknown_culture_religion_and_pop_type_are_reported(self):
        for field, value in (("culture", "atlantean"), ("religion", "cthulhu"), ("pop_type", "wizards")):
            with tempfile.TemporaryDirectory() as directory:
                mod, game = build_fixture(
                    pathlib.Path(directory) / f"pop-{field}",
                    {
                        "common/history/pops/ywc_test.txt": (
                            "POPS = {\n    s:STATE_TESTA = {\n        region_state:TST = {\n"
                            f"            create_pop = {{ culture = han {field} = {value} }}\n"
                            "        }\n    }\n}\n"
                        )
                    },
                )
                report = audit(mod, game)
                self.assertTrue(
                    any(f"unknown {field} {value}" in item for item in report["problems"]),
                    report["problems"],
                )

    def test_unknown_state_region_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "state",
                {
                    "common/history/pops/ywc_test.txt": VALID_POPS.replace(
                        "STATE_TESTA", "STATE_NOWHERE"
                    )
                },
            )
            report = audit(mod, game)
            self.assertTrue(
                any("unknown state region STATE_NOWHERE" in item for item in report["problems"]),
                report["problems"],
            )

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(
                pathlib.Path(directory) / "cli",
                {"common/history/buildings/ywc_test.txt": VALID_BUILDINGS},
            )
            result = subprocess.run(
                [sys.executable, str(TOOL), "--mod-root", str(mod), "--game-root", str(game)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Startup data is valid", result.stdout)

    def test_repository_startup_data_is_valid(self):
        if not GAME_ROOT.is_dir():
            self.skipTest(f"game root is unavailable: {GAME_ROOT}")
        report = audit(MOD_ROOT, GAME_ROOT)
        self.assertEqual(report["problems"], [], report["problems"])
        self.assertGreater(report["checked_buildings"], 1000)
        self.assertGreater(report["checked_pops"], 1000)


if __name__ == "__main__":
    unittest.main()
