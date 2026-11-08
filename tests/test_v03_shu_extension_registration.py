"""Additional SHU content must be registered with its source-bound coordinator."""
import copy
import json
from pathlib import Path
import unittest

from tools.v03_inline_delivery_adapter import render_inline_country_adapters, validate_inline_catalog

ROOT = Path(__file__).resolve().parents[1]


def catalog_with_unregistered_arc():
    catalog = json.loads((ROOT / "data/content/v03/countries/shu.json").read_text(encoding="utf-8"))
    extra = copy.deepcopy(catalog["arcs"][0])
    extra["slug"] = "v03_shu_unregistered_extension"
    extra["era"] = "middle"
    catalog["arcs"].append(extra)
    return catalog, extra


class ShuExtensionRegistrationTests(unittest.TestCase):
    def test_unknown_extension_cannot_silently_bypass_source_registration(self):
        for metadata in (True, False):
            with self.subTest(metadata=metadata):
                catalog, extra = catalog_with_unregistered_arc()
                if not metadata:
                    extra.pop("inline_delivery_adapter")
                with self.assertRaisesRegex(ValueError, "unregistered SHU inline arc"):
                    validate_inline_catalog(catalog)

    def test_renderer_refuses_unknown_extension_before_retaining_its_raw_sender(self):
        catalog, extra = catalog_with_unregistered_arc()
        self.assertIn("trigger_event", extra["journals"][0]["script"])
        with self.assertRaisesRegex(ValueError, "unregistered SHU inline arc"):
            render_inline_country_adapters(catalog)
