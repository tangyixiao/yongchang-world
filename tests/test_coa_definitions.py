import pathlib
import re
import unittest
import json


ROOT = pathlib.Path(__file__).parents[1]
COA_DIR = ROOT / "yongchang_world/common/coat_of_arms/coat_of_arms"
TEXTURES = ROOT / "yongchang_world/gfx/coat_of_arms/textured_emblems"


class CoADefinitionsTest(unittest.TestCase):
    def test_custom_coas_use_vanilla_geometric_patterns(self):
        definitions = []
        for path in COA_DIR.glob("*.txt"):
            text = path.read_text("utf-8-sig")
            definitions.extend(re.findall(r"(?m)^(YWC_[A-Z]+(?:_MARITIME)?)\s*=\s*\{([^}]*)\}", text))
        allowed_patterns = {
            "pattern_circle.dds",
            "pattern_cross.dds",
             "pattern_gironny_8.dds",
             "pattern_gironny_12.dds",
             "pattern_gironny_16.dds",
             "pattern_lozengy_bend.dds",
            "pattern_per_bend.dds",
            "pattern_per_saltire.dds",
            "pattern_border_of_3.dds",
            "pattern_border_of_4.dds",
        }
        for name, body in definitions:
            match = re.search(r'pattern\s*=\s*"([^"]+)"', body)
            self.assertIsNotNone(match, name)
            if match.group(1) == "pattern_solid.tga":
                texture = re.search(r'textured_emblem\s*=\s*\{\s*texture\s*=\s*"([^"]+\.dds)"', body)
                self.assertIsNotNone(texture, name)
                self.assertTrue((TEXTURES / texture.group(1)).is_file(), name)
            else:
                self.assertIn(match.group(1), allowed_patterns, name)


if __name__ == "__main__":
    unittest.main()
