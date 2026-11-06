"""The isolated JHG public renderer must validate its shared cooldown ABI."""

import unittest

from tests.test_v03_jhg_inline_adapter import _isolated_build_root, _v2_catalog_from_formal_jhg_source
from tools import build_v03_country
from tools.v03_inline_delivery_adapter import parse_block


class JhgInlineHelperAbi(unittest.TestCase):
    def test_isolated_jhg_renderer_accepts_exact_shared_cooldown_helper(self):
        candidate = _v2_catalog_from_formal_jhg_source()
        with _isolated_build_root(candidate) as root:
            rendered = build_v03_country.render_country(root, "country_jhg")
        self.assertEqual(len(rendered), 6)

    def test_isolated_jhg_renderer_rejects_altered_shared_cooldown_helper(self):
        candidate = _v2_catalog_from_formal_jhg_source()
        with _isolated_build_root(candidate) as root:
            path = root / "yongchang_world/common/scripted_effects/ywc_v03_effects.txt"
            source = path.read_text(encoding="utf-8-sig")
            path.write_text(source.replace("days = 90", "days = 91", 1), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "shared.*definition|cooldown helper"):
                build_v03_country.render_country(root, "country_jhg")

    def test_isolated_jhg_renderer_rejects_duplicate_shared_cooldown_definition(self):
        candidate = _v2_catalog_from_formal_jhg_source()
        with _isolated_build_root(candidate) as root:
            path = root / "yongchang_world/common/scripted_effects/ywc_v03_effects.txt"
            source = path.read_text(encoding="utf-8-sig")
            definition = "ywc_v03_mark_major_delivered = { if = { limit = { NOT = { has_variable = ywc_v03_major_event_cooldown } } set_variable = { name = ywc_v03_major_event_cooldown value = 1 days = 90 } } }"
            path.write_text(source + "\n" + definition + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "shared.*definition|cooldown helper"):
                build_v03_country.render_country(root, "country_jhg")

    def test_isolated_jhg_renderer_rejects_missing_shared_cooldown_definition(self):
        candidate = _v2_catalog_from_formal_jhg_source()
        with _isolated_build_root(candidate) as root:
            path = root / "yongchang_world/common/scripted_effects/ywc_v03_effects.txt"
            source = path.read_text(encoding="utf-8-sig")
            wrapped = "{\n" + source + "\n}"
            definition = next(node for node in parse_block(wrapped)
                              if node.key == "ywc_v03_mark_major_delivered")
            start, end = definition.start - 2, definition.end - 2
            path.write_text(source[:start] + source[end:], encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "shared.*definition|cooldown helper"):
                build_v03_country.render_country(root, "country_jhg")


if __name__ == "__main__":
    unittest.main()
