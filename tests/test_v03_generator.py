import json
import pathlib
import tempfile
import unittest

from test_v03_catalog import catalog
from tools.build_v03_content import build, render_all, validate_catalogs_at


def write_fixture(root):
    base = root / "data/content/v03"
    (base / "countries").mkdir(parents=True)
    (base / "countries/shu.json").write_text(json.dumps(catalog(), ensure_ascii=False), encoding="utf-8")
    outputs = [
        "events/ywc_v03_country_shu_events.txt",
        "common/journal_entries/ywc_v03_country_shu_journal.txt",
        "localization/simp_chinese/ywc_v03_country_shu_l_simp_chinese.yml",
        "localization/english/ywc_v03_country_shu_l_english.yml",
    ]
    manifest = {
        "schema_version": 1,
        "release": "0.3",
        "catalogs": ["data/content/v03/countries/shu.json"],
        "targets": {
            "country": {"events": 720, "journals": 180},
            "crisis": {"events": 96, "journals": 24},
            "regional": {"events": 378, "journals": 126},
            "theme": {"events": 96, "journals": 12},
        },
        "owned_outputs": outputs,
    }
    (base / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    registry = {
        "schema_version": 1,
        "namespace_limits": {
            "country": {"start": 1000, "end": 1999},
            "crisis": {"start": 1000, "end": 1799},
            "regional": {"start": 1000, "end": 7299},
            "theme": {"start": 1000, "end": 1599},
        },
        "reservations": [
            {"key": "country_shu", "layer": "country", "namespace": "ywc_shu"}
        ],
        "arc_ranges": [
            {"catalog_key": "country_shu", "slug": "shu_test_arc", "namespace": "ywc_shu", "start": 1000, "end": 1009}
        ],
    }
    (base / "id_registry.json").write_text(json.dumps(registry), encoding="utf-8")
    return outputs


class V03GeneratorTests(unittest.TestCase):
    def test_hidden_event_renders_country_event_without_options_or_inline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write_fixture(root)
            baseline = render_all(root)
            value = catalog()
            event = value["arcs"][0]["events"][0]
            event["hidden"] = True
            event["options"] = []
            path = root / "data/content/v03/countries/shu.json"
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            rendered = render_all(root)
            event_text = next(text for relative, text in rendered.items() if "_events.txt" in str(relative))
            self.assertIn("ywc_shu.1000 = {", event_text)
            self.assertIn("hidden = yes", event_text)
            self.assertIn("type = country_event", event_text)
            self.assertNotIn("option = {", event_text)
            for relative, text in baseline.items():
                if "journal.txt" in str(relative):
                    self.assertEqual(rendered[relative], text)
                if "localization" in str(relative):
                    self.assertIn('ywc_shu.1000.t:0 "测试事件"', rendered[relative])
                    self.assertIn('ywc_shu.1000.d:0 "测试说明"', rendered[relative])
                    self.assertNotIn("ywc_shu.1000.continue", rendered[relative])
            event.pop("hidden")
            event["options"] = catalog()["arcs"][0]["events"][0]["options"]
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(render_all(root), baseline)

    def test_rejects_registry_namespace_limit_expansion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write_fixture(root)
            path = root / "data/content/v03/id_registry.json"
            registry = json.loads(path.read_text(encoding="utf-8"))
            registry["namespace_limits"]["country"]["start"] = 1
            path.write_text(json.dumps(registry), encoding="utf-8")
            self.assertTrue(any("fixed" in e and "country" in e for e in validate_catalogs_at(root, {"country_shu": catalog()})))

    def test_empty_catalog_stale_output_prevents_all_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            active_outputs = write_fixture(root)
            base = root / "data/content/v03"
            empty = catalog()
            empty.update(key="country_dmg", runtime_tags=["DMG"])
            empty["arcs"] = []
            (base / "countries/dmg.json").write_text(json.dumps(empty), encoding="utf-8")
            manifest_path = base / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["catalogs"].append("data/content/v03/countries/dmg.json")
            stale_rel = "events/ywc_v03_country_dmg_events.txt"
            manifest["owned_outputs"].extend([
                stale_rel,
                "common/journal_entries/ywc_v03_country_dmg_journal.txt",
                "localization/simp_chinese/ywc_v03_country_dmg_l_simp_chinese.yml",
                "localization/english/ywc_v03_country_dmg_l_english.yml",
            ])
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            registry_path = base / "id_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["reservations"].append({"key": "country_dmg", "layer": "country", "namespace": "ywc_dmg"})
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            stale = root / "yongchang_world" / stale_rel
            stale.parent.mkdir(parents=True)
            stale.write_text("preserve me", encoding="utf-8")
            active = root / "yongchang_world" / active_outputs[0]
            errors = build(root)
            self.assertTrue(any(stale_rel in e and "stale" in e for e in errors), errors)
            self.assertFalse(active.exists())
            self.assertEqual(stale.read_text(encoding="utf-8"), "preserve me")

    def test_registered_non_country_packs_can_use_each_reserved_namespace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write_fixture(root)
            registry_path = root / "data/content/v03/id_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            catalog_by_layer = {}
            for index, layer in enumerate(("crisis", "regional", "theme")):
                key = f"{layer}_sample"
                namespace = {"crisis": "ywc_crisis", "regional": "ywc_regional", "theme": "ywc_society"}[layer]
                slug = f"{layer}_sample_arc"
                value = catalog()
                value.update(key=key, layer=layer, runtime_tags=["CHI"])
                value["arcs"][0].update(slug=slug, participants=["CHI"])
                owner = {"crisis": "C01", "regional": "CHI", "theme": "T01"}[layer]
                value["arcs"][0]["owner"] = owner
                value["arcs"][0]["journals"][0]["id"] = f"ywc_je_v03_{owner.lower()}_sample_main"
                value["arcs"][0]["events"][0]["id"] = f"{namespace}.{1000 + index:04d}"
                catalog_by_layer[key] = value
                registry["reservations"].append({"key": key, "layer": layer, "namespace": namespace})
                registry["arc_ranges"].append({
                    "catalog_key": key,
                    "slug": slug,
                    "namespace": namespace,
                    "start": 1000 + index,
                    "end": 1000 + index + 9,
                })
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            self.assertEqual([], validate_catalogs_at(root, catalog_by_layer))

    def test_output_is_deterministic_and_localization_has_utf8_bom(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write_fixture(root)
            first = render_all(root)
            second = render_all(root)
            self.assertEqual(first, second)
            zh = next(text for path, text in first.items() if "simp_chinese" in str(path))
            en = next(text for path, text in first.items() if "english" in str(path))
            self.assertFalse(zh.startswith("\ufeff"))
            self.assertFalse(en.startswith("\ufeff"))
            self.assertIn('ywc_shu.1000.t:0 "测试事件"', zh)
            self.assertIn('ywc_shu.1000.t:0 "测试事件"', en)
            self.assertEqual([], build(root))
            for relative in first:
                self.assertTrue((root / "yongchang_world" / relative).read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_option_notes_render_as_exact_bilingual_custom_tooltips(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write_fixture(root)
            value = catalog()
            option = value["arcs"][0]["events"][0]["options"][0]
            option["cost_note"] = {"zh": '花费\n“银两”', "en": 'Cost\n"silver"'}
            option["consequence_note"] = {"zh": "后果说明", "en": "Outcome note"}
            path = root / "data/content/v03/countries/shu.json"
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            rendered = render_all(root)
            event = next(text for relative, text in rendered.items() if "_events.txt" in str(relative))
            zh = next(text for relative, text in rendered.items() if "simp_chinese" in str(relative))
            en = next(text for relative, text in rendered.items() if "english" in str(relative))
            self.assertIn("custom_tooltip = { text = ywc_shu.1000.continue.cost_tooltip }", event)
            self.assertIn("custom_tooltip = { text = ywc_shu.1000.continue.consequence_tooltip }", event)
            self.assertIn('ywc_shu.1000.continue.cost_tooltip:0 "花费\\n“银两”"', zh)
            self.assertIn('ywc_shu.1000.continue.consequence_tooltip:0 "后果说明"', zh)
            self.assertIn('ywc_shu.1000.continue.cost_tooltip:0 "Cost\\n\\"silver\\""', en)
            self.assertIn('ywc_shu.1000.continue.consequence_tooltip:0 "Outcome note"', en)

    def test_option_trigger_is_preserved_in_event_and_absent_trigger_stays_unconditional(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write_fixture(root)
            value = catalog()
            event = value["arcs"][0]["events"][0]
            event["options"][0]["trigger"] = (
                "{\n    has_law = law_type:law_monarchy\n"
                "    has_technology_researched = tec:urban_planning\n}"
            )
            path = root / "data/content/v03/countries/shu.json"
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            rendered = render_all(root)
            script = next(text for relative, text in rendered.items() if "_events.txt" in str(relative))
            self.assertIn('event_image = { video = "unspecific_politicians_arguing" }', script)
            self.assertIn(
                "        trigger = {\n"
                "            has_law = law_type:law_monarchy\n"
                "            has_technology_researched = tec:urban_planning\n"
                "        }",
                script,
            )
            self.assertNotIn("trigger = { always = yes }", script)

            del event["options"][0]["trigger"]
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            rendered = render_all(root)
            script = next(text for relative, text in rendered.items() if "_events.txt" in str(relative))
            self.assertNotIn("        trigger =", script)

    def test_journal_goal_and_exit_are_rendered_as_complete_and_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write_fixture(root)
            outputs = render_all(root)
            journal = next(text for path, text in outputs.items() if "_journal.txt" in str(path))
            self.assertIn("complete = { has_law = law_type:law_traditionalism }", journal)
            self.assertIn("fail = { has_global_variable = ywc_v03_test_done }", journal)
            self.assertNotIn("\ufeff", journal)

    def test_refuses_unowned_outputs_and_does_not_overwrite_them(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            outputs = write_fixture(root)
            manifest_path = root / "data/content/v03/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["owned_outputs"].pop()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            from tools.ywc_v03_check import check_root

            errors = check_root(root)
            self.assertTrue(any("owned_outputs" in error for error in errors), errors)

    def test_build_check_detects_stale_output_without_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            outputs = write_fixture(root)
            rendered = render_all(root)
            for relative, text in rendered.items():
                path = root / "yongchang_world" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            stale = root / "yongchang_world" / outputs[0]
            stale.write_text("stale", encoding="utf-8")
            before = stale.read_bytes()
            from tools.build_v03_content import check_outputs

            errors = check_outputs(root)
            self.assertTrue(any("stale" in error.lower() or "mismatch" in error.lower() for error in errors), errors)
            self.assertEqual(stale.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
