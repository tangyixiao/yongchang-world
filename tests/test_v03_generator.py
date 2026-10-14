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
                value["arcs"][0]["journals"][0]["id"] = f"ywc_je_v03_{layer}_sample_main"
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
