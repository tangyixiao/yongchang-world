import json
import pathlib
import tempfile
import unittest

from tools.build_v03_content import load_catalogs, validate_catalogs


ROOT = pathlib.Path(__file__).parents[1]


def localized(text):
    return {"zh": text, "en": text}


def catalog():
    return {
        "key": "country_shu",
        "layer": "country",
        "runtime_tags": ["SHU"],
        "arcs": [
            {
                "slug": "shu_test_arc",
                "era": "1836-1870",
                "participants": ["SHU"],
                "depends_on": [],
                "journals": [
                    {
                        "id": "ywc_je_v03_shu_test_arc_main",
                        "title": localized("测试日志"),
                        "desc": localized("测试说明"),
                        "script": "{ is_shu = yes }",
                        "goal": "{ has_law = law_type:law_traditionalism }",
                        "exit_conditions": "{ has_global_variable = ywc_v03_test_done }",
                    }
                ],
                "events": [
                    {
                        "id": "ywc_shu.1000",
                        "title": localized("测试事件"),
                        "desc": localized("测试说明"),
                        "trigger": "{ c:SHU ?= this }",
                        "immediate": "{ set_global_variable = ywc_v03_test_seen }",
                        "options": [
                            {
                                "key": "continue",
                                "label": localized("继续"),
                                "effect": "{ set_global_variable = ywc_v03_test_done }",
                                "ai_chance": "{ base = 1 modifier = { factor = 0 } }",
                                "cost_note": localized("无直接成本"),
                                "consequence_note": localized("记录决定"),
                            }
                        ],
                        "purpose": localized("检查确定性渲染"),
                        "reads": [],
                        "writes": ["ywc_v03_test_seen", "ywc_v03_test_done"],
                    }
                ],
                "outcomes": ["settled", "compromise", "failed"],
                "legacy_links": [],
            }
        ],
    }


class V03CatalogTests(unittest.TestCase):
    def test_load_catalogs_reads_only_manifest_entries(self):
        catalogs = load_catalogs(ROOT)
        self.assertEqual(set(catalogs), {"country_shu", "country_dmg", "country_kor"})

    def test_rejects_duplicate_ids_across_catalogs(self):
        first = catalog()
        second = catalog()
        second["key"] = "country_dmg"
        second["layer"] = "country"
        second["runtime_tags"] = ["DMG"]
        second["arcs"][0]["slug"] = "dmg_test_arc"
        errors = validate_catalogs({first["key"]: first, second["key"]: second})
        self.assertTrue(any("duplicate" in error.lower() for error in errors), errors)

    def test_rejects_missing_translation(self):
        value = catalog()
        del value["arcs"][0]["events"][0]["title"]["en"]
        errors = validate_catalogs({value["key"]: value})
        self.assertTrue(any("title" in error and "en" in error for error in errors), errors)

    def test_rejects_unregistered_event_id(self):
        value = catalog()
        value["arcs"][0]["events"][0]["id"] = "ywc_shu.0999"
        errors = validate_catalogs({value["key"]: value})
        self.assertTrue(any("id" in error.lower() and "outside registered" in error for error in errors), errors)

    def test_rejects_event_outside_its_arc_reservation(self):
        value = catalog()
        value["arcs"][0]["slug"] = "v03_shu_fiscal_register"
        value["arcs"][0]["events"][0]["id"] = "ywc_shu.1010"
        errors = validate_catalogs({value["key"]: value})
        self.assertTrue(any("outside explicit arc range" in error for error in errors), errors)

    def test_rejects_journal_body_that_redefines_complete_or_fail(self):
        value = catalog()
        value["arcs"][0]["journals"][0]["script"] = "{ icon = test complete = { always = yes } }"
        errors = validate_catalogs({value["key"]: value})
        self.assertTrue(any("must not define complete or fail" in error for error in errors), errors)

    def test_option_trigger_is_optional_and_must_be_a_clausewitz_block(self):
        value = catalog()
        errors = validate_catalogs({value["key"]: value})
        self.assertFalse(any("options[0].trigger" in error for error in errors), errors)

        value["arcs"][0]["events"][0]["options"][0]["trigger"] = (
            "{ has_law = law_type:law_monarchy }"
        )
        errors = validate_catalogs({value["key"]: value})
        self.assertFalse(any("options[0].trigger" in error for error in errors), errors)

        value["arcs"][0]["events"][0]["options"][0]["trigger"] = (
            "has_law = law_type:law_monarchy"
        )
        errors = validate_catalogs({value["key"]: value})
        self.assertTrue(any("trigger" in error and "wrapped" in error for error in errors), errors)

        value["arcs"][0]["events"][0]["options"][0]["trigger"] = "{ always = yes }}"
        errors = validate_catalogs({value["key"]: value})
        self.assertTrue(any("trigger" in error and "unbalanced" in error for error in errors), errors)

    def test_script_blocks_require_clausewitz_logic_operator_blocks(self):
        value = catalog()
        value["arcs"][0]["journals"][0]["goal"] = (
            "{ has_variable = ywc_ready OR has_variable = ywc_failed }"
        )
        errors = validate_catalogs({value["key"]: value})
        self.assertTrue(
            any("journals[0].goal" in error and "OR" in error and "block" in error for error in errors),
            errors,
        )

        value["arcs"][0]["journals"][0]["goal"] = "{ OR = yes }"
        errors = validate_catalogs({value["key"]: value})
        self.assertTrue(
            any("journals[0].goal" in error and "OR" in error and "block" in error for error in errors),
            errors,
        )

    def test_script_blocks_accept_nested_logic_and_ignore_quotes_and_comments(self):
        value = catalog()
        value["arcs"][0]["journals"][0]["goal"] = (
            '{ AND = { OR = { always = yes } NOT = { always = no } } '
            'custom_tooltip = { text = "OR AND NOT NOR" } # NOR = invalid }\n}'
        )
        errors = validate_catalogs({value["key"]: value})
        self.assertFalse(any("journals[0].goal" in error for error in errors), errors)

    def test_rejects_missing_journal_goal_and_exit_conditions(self):
        value = catalog()
        del value["arcs"][0]["journals"][0]["goal"]
        del value["arcs"][0]["journals"][0]["exit_conditions"]
        errors = validate_catalogs({value["key"]: value})
        self.assertTrue(any("goal" in error for error in errors), errors)
        self.assertTrue(any("exit_conditions" in error for error in errors), errors)

    def test_rejects_unknown_dependency_and_cycles(self):
        value = catalog()
        value["arcs"][0]["depends_on"] = ["missing_arc"]
        errors = validate_catalogs({value["key"]: value})
        self.assertTrue(any("missing_arc" in error for error in errors), errors)

        value["arcs"][0]["depends_on"] = ["shu_test_arc"]
        errors = validate_catalogs({value["key"]: value})
        self.assertTrue(any("cycle" in error.lower() for error in errors), errors)

    def test_rejects_unsafe_manifest_catalog_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "data/content/v03").mkdir(parents=True)
            (root / "data/content/v03/manifest.json").write_text(
                json.dumps({"schema_version": 1, "release": "0.3", "catalogs": ["../../outside.json"], "targets": {}, "owned_outputs": []}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unsafe|outside|path"):
                load_catalogs(root)

    def test_rejects_unsafe_owned_output_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            base = root / "data/content/v03"
            base.mkdir(parents=True)
            manifest = {
                "schema_version": 1,
                "release": "0.3",
                "catalogs": [],
                "targets": {
                    "country": {"events": 720, "journals": 180},
                    "crisis": {"events": 96, "journals": 24},
                    "regional": {"events": 378, "journals": 126},
                    "theme": {"events": 96, "journals": 12},
                },
                "owned_outputs": ["../outside.txt"],
            }
            (base / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsafe|outside|path"):
                load_catalogs(root)

    def test_partial_catalog_is_valid_but_release_reports_layer_quotas(self):
        errors = validate_catalogs({})
        self.assertEqual(errors, [])
        from tools.ywc_v03_check import check_root

        errors = check_root(ROOT, require_complete=True)
        self.assertTrue(any("country owner" in error and "72" in error for error in errors), errors)
        self.assertTrue(any("crisis owner" in error and "12" in error for error in errors), errors)
        self.assertTrue(any("regional owner" in error and "6" in error for error in errors), errors)
        self.assertTrue(any("theme owner" in error and "8" in error for error in errors), errors)

    def test_complete_quota_is_per_owner_not_aggregate(self):
        from tools.v03_owners import REGIONAL_TAGS
        from tools.ywc_v03_check import check_complete_quotas

        arcs = []
        for tag in REGIONAL_TAGS[:-1]:
            events, journals = 6, 2
            if tag == "CHI":
                events += 6
                journals += 2
            arcs.append({"slug": f"arc_{tag.lower()}", "owner": tag, "era": "1836-1870",
                         "events": [{}] * events, "journals": [{}] * journals})
        errors = check_complete_quotas({"regional_pack": {"layer": "regional", "runtime_tags": list(REGIONAL_TAGS), "arcs": arcs}})
        self.assertTrue(any("owner MHG event quota" in error for error in errors), errors)

    def test_one_catalog_can_cover_multiple_crisis_owners(self):
        from tools.v03_owners import CRISIS_OWNERS
        from tools.ywc_v03_check import check_complete_quotas

        arcs = [{"slug": f"crisis_{owner.lower()}", "owner": owner, "era": "1836-1870",
                 "events": [{}] * 12, "journals": [{}] * 3} for owner in CRISIS_OWNERS]
        errors = check_complete_quotas({"crisis_pack": {"layer": "crisis", "runtime_tags": ["CHI"], "arcs": arcs}})
        self.assertFalse(any(error.startswith("crisis owner ") for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
