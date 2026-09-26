"""Guard the ``common/history`` root-key contract.

Vanilla loads each history folder through one fixed root key (``DIPLOMACY``,
``COUNTRIES``, ...).  A file whose root key is not that exact token is discarded
without an error, so typo'd or invented keys produce a mod that satisfies every
content assertion while doing nothing in game.  These tests pin the contract and
make the failure loud.
"""

import pathlib
import re
import tempfile
import unittest

from tools.ywc_check import (
    VANILLA_HISTORY_ROOT_KEYS,
    _history_root_key_diagnostics,
    find_top_level_keys,
    scan_braces,
    validate,
)


ROOT = pathlib.Path(__file__).parents[1]
HISTORY_ROOT = ROOT / "yongchang_world/common/history"
DIPLOMACY_FILES = (
    "ywc_core_relations.txt",
    "ywc_core_subjects.txt",
    "ywc_inner_asia_diplomacy.txt",
    "ywc_ocean_diplomacy.txt",
    "ywc_southwest_diplomacy.txt",
)


class HistoryRootKeyTest(unittest.TestCase):
    def test_find_top_level_keys_reads_only_root_keys(self):
        text = (
            "# DIPLOMACY = { commented out }\n"
            'name = "a { brace inside a string" \n'
            "COUNTRIES = {\n"
            "\tc:SHU ?= {\n"
            "\t\tadd_journal_entry = { type = ywc_test }\n"
            "\t}\n"
            "}\n"
        )
        self.assertEqual(find_top_level_keys(text), ["COUNTRIES"])

    def test_every_history_file_uses_its_vanilla_root_key(self):
        diagnostics = _history_root_key_diagnostics(ROOT / "yongchang_world")
        self.assertEqual(diagnostics, [], "\n".join(diagnostics))

    def test_history_files_cover_only_known_folders(self):
        for path in sorted(HISTORY_ROOT.rglob("*.txt")):
            self.assertIn(path.parent.name, VANILLA_HISTORY_ROOT_KEYS, path.name)

    def test_diplomacy_files_declare_the_diplomacy_root_key(self):
        """Regression: these five files shipped RELATIONS / DIPLOMATIC_PACTS."""

        for name in DIPLOMACY_FILES:
            path = HISTORY_ROOT / "diplomacy" / name
            self.assertTrue(path.is_file(), name)
            self.assertEqual(find_top_level_keys(path.read_text("utf-8-sig")), ["DIPLOMACY"], name)

    def test_diplomacy_files_keep_one_root_block(self):
        """Merging the two legacy root blocks must not nest or duplicate them."""

        for name in DIPLOMACY_FILES:
            path = HISTORY_ROOT / "diplomacy" / name
            text = path.read_text("utf-8-sig")
            self.assertEqual(len(re.findall(r"(?m)^DIPLOMACY\s*=\s*\{", text)), 1, name)
            self.assertEqual(scan_braces(text), [], name)
            self.assertRegex(text.rstrip(), r"\}\s*$", name)

    def test_validate_reports_an_unaccepted_root_key(self):
        with tempfile.TemporaryDirectory() as directory:
            mod_root = pathlib.Path(directory) / "mod"
            diplomacy = mod_root / "common/history/diplomacy"
            diplomacy.mkdir(parents=True)
            (diplomacy / "bad.txt").write_text(
                "DIPLOMATIC_PACTS = {\n\tc:SHU ?= { }\n}\n", encoding="utf-8"
            )
            diagnostics = _history_root_key_diagnostics(mod_root)
            self.assertEqual(len(diagnostics), 1)
            self.assertIn("DIPLOMATIC_PACTS", diagnostics[0])
            self.assertIn("DIPLOMACY", diagnostics[0])

    def test_validate_reports_an_unknown_history_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            mod_root = pathlib.Path(directory) / "mod"
            wrong = mod_root / "common/history/statse"
            wrong.mkdir(parents=True)
            (wrong / "typo.txt").write_text("STATES = {\n\t0 = { }\n}\n", encoding="utf-8")
            diagnostics = _history_root_key_diagnostics(mod_root)
            self.assertEqual(len(diagnostics), 1)
            self.assertIn("statse", diagnostics[0])

    def test_validate_reports_a_history_file_without_a_root_key(self):
        with tempfile.TemporaryDirectory() as directory:
            mod_root = pathlib.Path(directory) / "mod"
            countries = mod_root / "common/history/countries"
            countries.mkdir(parents=True)
            (countries / "comment_only.txt").write_text("# nothing here\n", encoding="utf-8")
            diagnostics = _history_root_key_diagnostics(mod_root)
            self.assertEqual(len(diagnostics), 1)
            self.assertIn("no top-level key", diagnostics[0])

    def test_validate_surfaces_root_key_problems(self):
        with tempfile.TemporaryDirectory() as directory:
            mod_root = pathlib.Path(directory) / "mod"
            diplomacy = mod_root / "common/history/diplomacy"
            diplomacy.mkdir(parents=True)
            (diplomacy / "bad.txt").write_text(
                "RELATIONS = {\n\tc:SHU ?= { }\n}\n", encoding="utf-8"
            )
            reported = [line for line in validate(mod_root) if "root key" in line]
            self.assertEqual(len(reported), 1, reported)


if __name__ == "__main__":
    unittest.main()
