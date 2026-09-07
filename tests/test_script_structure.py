import pathlib
import re
import tempfile
import unittest

from tools.ywc_check import (
    collect_declared_keys,
    collect_localization_keys,
    find_duplicate_keys,
    scan_braces,
    validate,
)
from tools.build_state_history import balanced_end


ROOT = pathlib.Path(__file__).parents[1]


class ScriptStructureTest(unittest.TestCase):
    def test_state_history_files_have_states_wrapper(self):
        state_dir = ROOT / "yongchang_world/common/history/states"
        for path in sorted(state_dir.glob("*.txt")):
            text = path.read_text("utf-8-sig")
            self.assertRegex(text, r"(?m)^\s*STATES\s*=\s*\{", path.name)
            self.assertRegex(text.rstrip(), r"\}\s*$", path.name)

    def test_building_history_uses_vanilla_level_forms(self):
        building_dir = ROOT / "yongchang_world/common/history/buildings"
        offenders = []
        for path in sorted(building_dir.glob("*.txt")):
            text = path.read_text("utf-8-sig")
            if "create_building = { building =" in text and " levels =" in text:
                offenders.append(path.name)
            for match in re.finditer(r"create_building\s*=\s*\{", text):
                opening = text.find("{", match.start(), match.end())
                block_end = balanced_end(text, opening)
                block = text[opening + 1 : block_end]
                depth = 0
                for line in block.splitlines():
                    depth += line.count("{") - line.count("}")
                    if depth == 0:
                        self.assertNotRegex(
                            line,
                            r"^\s*levels\s*=\s*\d+\s*$",
                            f"top-level create_building levels in {path.name}",
                        )
        self.assertEqual(offenders, [])

    def test_set_variable_names_do_not_contain_event_dots(self):
        event_dir = ROOT / "yongchang_world/events"
        offenders = []
        for path in sorted(event_dir.glob("*.txt")):
            text = path.read_text("utf-8-sig")
            for match in re.finditer(
                r"set_variable\s*=\s*\{\s*name\s*=\s*([^\s}]+)", text
            ):
                name = match.group(1)
                if "." in name:
                    line_number = text.count("\n", 0, match.start()) + 1
                    offenders.append(f"{path}:{line_number}:{name}")
        self.assertEqual(offenders, [])

    def test_journal_entries_do_not_use_unsupported_visible_clause(self):
        journal_dir = ROOT / "yongchang_world/common/journal_entries"
        offenders = []
        for path in sorted(journal_dir.glob("*.txt")):
            for line_number, line in enumerate(path.read_text("utf-8-sig").splitlines(), 1):
                if line.strip().startswith("visible ="):
                    offenders.append(f"{path}:{line_number}")
        self.assertEqual(offenders, [])

    def test_country_identity_uses_supported_this_comparison(self):
        # Runtime evidence (user campaign, 2026-09-06 16:31): plain
        # `this = c:TAG` raises "comparison were of different types
        # (country vs country_definition)" when evaluated in journal and
        # flag contexts. The supported idiom is `c:TAG ?= this`, which the
        # mod's own dynamic map colors already use successfully.
        path = ROOT / "yongchang_world/common/scripted_triggers/ywc_shared_triggers.txt"
        text = path.read_text("utf-8-sig")
        self.assertNotIn("is_country =", text)
        self.assertNotIn("visible =", text)
        self.assertEqual(text.count("this = c:"), 0)
        # Ten supported country identity comparisons remain; the former
        # four-country maritime whitelist is now a numeric shared-variable
        # trigger and must not contribute extra tag comparisons.
        self.assertEqual(text.count("?= this"), 10)

    def test_event_ids_are_unique_across_mod_events(self):
        event_dir = ROOT / "yongchang_world/events"
        ids = []
        for path in sorted(event_dir.glob("*.txt")):
            ids.extend(
                line.split("=", 1)[0].strip()
                for line in path.read_text("utf-8-sig").splitlines()
                if line.strip().startswith("ywc_") and line.rstrip().endswith("= {")
            )
        self.assertEqual(len(ids), len(set(ids)), ids)

    def test_reports_unclosed_brace(self):
        self.assertIn("unclosed brace", scan_braces("SHU = { color = { 1 2 3 }"))

    def test_ignores_comments_and_quoted_braces(self):
        text = 'key = { value = "}" } # comment with {\n'
        self.assertEqual(scan_braces(text), [])
        self.assertEqual(scan_braces('key = { value = "}" } # { }'), [])

    def test_ywc_keys_are_localized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "common").mkdir()
            (root / "localization/simp_chinese").mkdir(parents=True)
            (root / "common/example.txt").write_text(
                "ywc_example = { value = 1 }\n", encoding="utf-8"
            )
            (root / "localization/simp_chinese/example.yml").write_text(
                'l_simp_chinese:\n ywc_example:0 "示例"\n', encoding="utf-8"
            )
            self.assertEqual(
                collect_declared_keys(root) - collect_localization_keys(root), set()
            )

    def test_validate_accepts_vanilla_localization_for_overridden_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            mod = root / "mod"
            game = root / "game"
            (mod / "common/country_definitions").mkdir(parents=True)
            (game / "localization/english").mkdir(parents=True)
            (mod / "common/country_definitions/country.txt").write_text(
                "MNG = { country_type = unrecognized }\n", encoding="utf-8"
            )
            (game / "localization/english/countries.yml").write_text(
                'l_english:\n MNG:0 "Minas Gerais"\n', encoding="utf-8"
            )
            self.assertEqual(validate(mod, game), [])

    def test_reports_duplicate_declared_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "common").mkdir()
            (root / "common/one.txt").write_text("ywc_same = {}\n", encoding="utf-8")
            (root / "common/two.txt").write_text("ywc_same = {}\n", encoding="utf-8")
            duplicates = find_duplicate_keys(root)
            self.assertIn("ywc_same", duplicates)

    def test_nested_scripted_effect_calls_are_not_declarations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "common").mkdir()
            (root / "common/example.txt").write_text(
                "ywc_example = {\n    ywc_example = yes\n}\n", encoding="utf-8"
            )
            self.assertEqual(collect_declared_keys(root), {"ywc_example"})

    def test_on_action_ids_do_not_require_localization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "common/on_actions").mkdir(parents=True)
            (root / "common/on_actions/example.txt").write_text(
                "ywc_on_action = { effect = {} }\n", encoding="utf-8"
            )
            self.assertEqual(collect_declared_keys(root), set())

    def test_visual_database_tags_do_not_collide_with_country_definitions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "common/country_definitions").mkdir(parents=True)
            (root / "common/flag_definitions").mkdir(parents=True)
            (root / "localization/simp_chinese").mkdir(parents=True)
            (root / "common/country_definitions/country.txt").write_text(
                "SHU = {}\n", encoding="utf-8"
            )
            (root / "common/flag_definitions/flag.txt").write_text(
                "SHU = {}\n", encoding="utf-8"
            )
            (root / "localization/simp_chinese/country.yml").write_text(
                'l_simp_chinese:\n SHU:0 "蜀"\n', encoding="utf-8"
            )
            self.assertEqual(find_duplicate_keys(root), set())
            self.assertEqual(collect_declared_keys(root), {"SHU"})

    def test_repo_fixtures_are_available(self):
        self.assertTrue((ROOT / "tests/fixtures/broken_brace.txt").exists())
        self.assertTrue((ROOT / "tests/fixtures/missing_localization.txt").exists())


if __name__ == "__main__":
    unittest.main()
