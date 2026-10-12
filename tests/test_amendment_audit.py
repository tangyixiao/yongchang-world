import pathlib
import subprocess
import sys
import tempfile
import unittest

from tools.amendment_audit import audit


ROOT = pathlib.Path(__file__).parents[1]
TOOL = ROOT / "tools/amendment_audit.py"
MOD_ROOT = ROOT / "yongchang_world"
GAME_ROOT = pathlib.Path(r"E:/SteamLibrary/steamapps/common/Victoria 3/game")

LAWS = {
    "vanilla/common/laws/00_test_laws.txt": (
        "law_land_based_taxation = {\n\tgroup = lawgroup_taxation\n}\n"
        "law_appointed_bureaucrats = {\n\tgroup = lawgroup_bureaucracy\n}\n"
    ),
    "vanilla/common/country_definitions/00_test_countries.txt": "TST = {\n\tcultures = { han }\n}\n",
    "vanilla/common/interest_groups/00_test_igs.txt": (
        "ig_landowners = {\n}\nig_intelligentsia = {\n}\n"
    ),
    "vanilla/common/modifier_type_definitions/00_test_modifiers.txt": (
        "country_bureaucracy_add = {\n\tdecimals = 0\n}\n"
        "country_authority_add = {\n\tdecimals = 0\n}\n"
    ),
    "vanilla/common/history/countries/tst - test.txt": (
        "COUNTRIES = {\n\tc:TST ?= {\n"
        "\t\tactivate_law = law_type:law_land_based_taxation\n"
        "\t\tactivate_law = law_type:law_appointed_bureaucrats\n"
        "\t}\n}\n"
    ),
}

AMENDMENT = (
    "amendment_tst_exam_bureaucracy = {\n"
    "\tparent = law_appointed_bureaucrats\n"
    "\tallowed_laws = { law_appointed_bureaucrats }\n"
    "\tmodifier = { country_bureaucracy_add = 25 }\n"
    "\tpossible = { this = c:TST }\n"
    "\twould_sponsor = { OR = { is_interest_group_type = ig_intelligentsia } }\n"
    "\tai_will_revoke = { always = no }\n"
    "\tcan_repeal = { legitimacy >= legitimacy_to_repeal_amendment }\n"
    "}\n"
)

ATTACHMENT = (
    "COUNTRIES = {\n"
    "\tc:TST ?= {\n"
    "\t\tactive_law:lawgroup_bureaucracy ?= {\n"
    "\t\t\tadd_amendment = { type = amendment_tst_exam_bureaucracy "
    "sponsor = PREV.ig:ig_intelligentsia }\n"
    "\t\t}\n"
    "\t}\n"
    "}\n"
)

def localization_file(language: str) -> str:
    """Return a two-line amendment localization file for one language."""

    return (
        f"{language}:\n"
        ' amendment_tst_exam_bureaucracy:0 "Exam"\n'
        ' amendment_tst_exam_bureaucracy_desc:0 "Detail"\n'
    )


LOCALIZATION = {
    "english": localization_file("l_english"),
    "simp_chinese": localization_file("l_simp_chinese"),
}


def build_fixture(base, *, amendment=AMENDMENT, attachment=ATTACHMENT, laws=None, localization=None):
    mod = base / "mod"
    game = base / "game"
    for relative, text in (laws if laws is not None else LAWS).items():
        path = game / relative.split("/", 1)[1]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    amendments = mod / "common/amendments"
    amendments.mkdir(parents=True, exist_ok=True)
    (amendments / "ywc_test_amendments.txt").write_text(amendment, encoding="utf-8")
    history = mod / "common/history/countries"
    history.mkdir(parents=True, exist_ok=True)
    (history / "zzz_test.txt").write_text(attachment, encoding="utf-8")
    for language, text in (localization if localization is not None else LOCALIZATION).items():
        path = mod / "localization" / language / "ywc_test_l.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return mod, game


class AmendmentAuditTest(unittest.TestCase):
    def test_consistent_fixture_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(pathlib.Path(directory) / "ok")
            report = audit(mod, game)
            self.assertEqual(report["problems"], [])
            self.assertEqual(report["amendments"], 1)
            self.assertEqual(report["attachments"], 1)

    def test_nested_blocks_are_not_read_as_database_entries(self):
        # A law file has nested ``can_impose``/``modifier`` blocks; treating one
        # as a top-level entry used to collapse the whole law list to a single
        # law and produce bogus "unknown law" reports.
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(pathlib.Path(directory) / "nested")
            report = audit(mod, game)
            self.assertGreaterEqual(report["laws"], 2)
            self.assertFalse(
                any("unknown law" in problem for problem in report["problems"]), report["problems"]
            )

    def test_parent_not_in_allowed_laws_is_reported(self):
        amendment = AMENDMENT.replace(
            "allowed_laws = { law_appointed_bureaucrats }",
            "allowed_laws = { law_land_based_taxation }",
        )
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(pathlib.Path(directory) / "allowed", amendment=amendment)
            report = audit(mod, game)
            self.assertTrue(
                any("is not listed in allowed_laws" in problem for problem in report["problems"]),
                report["problems"],
            )

    def test_amendment_attached_to_the_wrong_law_group_is_reported(self):
        # The opening law in lawgroup_bureaucracy is law_appointed_bureaucrats,
        # but this country activates law_land_based_taxation there instead: the
        # amendment would then have no parent in game.
        laws = dict(LAWS)
        laws["vanilla/common/history/countries/tst - test.txt"] = (
            "COUNTRIES = {\n\tc:TST ?= {\n"
            "\t\tactivate_law = law_type:law_land_based_taxation\n\t}\n}\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(pathlib.Path(directory) / "shifted", laws=laws)
            report = audit(mod, game)
            self.assertTrue(
                any("whose opening law is none" in problem for problem in report["problems"]),
                report["problems"],
            )

    def test_unknown_modifier_key_is_reported(self):
        amendment = AMENDMENT.replace("country_bureaucracy_add", "country_tax_capacity_mult")
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(pathlib.Path(directory) / "modifier", amendment=amendment)
            report = audit(mod, game)
            self.assertTrue(
                any("unknown modifier type" in problem for problem in report["problems"]),
                report["problems"],
            )

    def test_unattached_amendment_is_reported(self):
        attachment = ATTACHMENT.replace(
            "add_amendment = { type = amendment_tst_exam_bureaucracy "
            "sponsor = PREV.ig:ig_intelligentsia }",
            "add_amendment = { type = amendment_tst_unused sponsor = PREV.ig:ig_intelligentsia }",
        )
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(pathlib.Path(directory) / "unattached", attachment=attachment)
            report = audit(mod, game)
            self.assertTrue(
                any("is never attached" in problem for problem in report["problems"]),
                report["problems"],
            )

    def test_missing_localization_is_reported(self):
        localization = {"english": LOCALIZATION["english"]}
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(pathlib.Path(directory) / "loc", localization=localization)
            report = audit(mod, game)
            self.assertTrue(
                any("simp_chinese" in problem and "missing localization" in problem for problem in report["problems"]),
                report["problems"],
            )

    def test_undefined_country_in_possible_is_reported(self):
        amendment = AMENDMENT.replace("this = c:TST", "this = c:ZZZ")
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(pathlib.Path(directory) / "tag", amendment=amendment)
            report = audit(mod, game)
            self.assertTrue(
                any("names undefined country c:ZZZ" in problem for problem in report["problems"]),
                report["problems"],
            )

    def test_unknown_interest_group_is_reported(self):
        amendment = AMENDMENT.replace("ig_intelligentsia", "ig_nonexistent")
        with tempfile.TemporaryDirectory() as directory:
            mod, game = build_fixture(pathlib.Path(directory) / "ig", amendment=amendment)
            report = audit(mod, game)
            self.assertTrue(
                any("names unknown ig_nonexistent" in problem for problem in report["problems"]),
                report["problems"],
            )

    def test_cli_reports_missing_amendment_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(TOOL), "--mod-root", str(pathlib.Path(directory))],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("common/amendments", result.stdout)

    def test_repository_amendments_are_consistent(self):
        if not (GAME_ROOT / "common/modifier_type_definitions").is_dir():
            self.skipTest(f"game root is unavailable: {GAME_ROOT}")
        report = audit(MOD_ROOT, GAME_ROOT)
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["amendments"], 10)
        self.assertEqual(report["attachments"], 10)
        self.assertGreater(report["modifier_types"], 2000)


if __name__ == "__main__":
    unittest.main()
