"""Checks that Shun event-art references resolve to bundled assets."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "yongchang_world"


def event_block(path, event_id):
    text = (MOD / "events" / path).read_text(encoding="utf-8-sig")
    match = re.search(r"(?ms)^" + re.escape(event_id) + r" = \{.*?(?=^ywc_[a-z]+\.\d+ = \{|\Z)", text)
    if not match:
        raise AssertionError(f"missing event {event_id}")
    return match.group()


class ShunEventArtTests(unittest.TestCase):
    def test_aliases_point_to_bundled_bink_and_source_images(self):
        aliases = (MOD / "gfx/media_aliases/ywc_shu_opening_media.txt").read_text(encoding="utf-8-sig")
        names = re.findall(r"(?m)^(ywc_shu_\w+) = \{", aliases)
        self.assertCountEqual(names, ["ywc_shu_opening", "ywc_shu_frontier", "ywc_shu_customs"])
        for name in names:
            block = re.search(r"(?ms)^" + re.escape(name) + r" = \{(.*?)^\}", aliases).group(1)
            path = re.search(r'video = "([^"\r\n]+)"', block).group(1)
            video = MOD / path
            self.assertTrue(video.is_file(), path)
            self.assertEqual(video.read_bytes()[:3], b"KB2")
            source = ROOT / "assets/source/ywc_shu_opening" / f"{name}.png"
            self.assertTrue(source.is_file(), source)
            self.assertEqual(source.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertIn("fallback = unspecific_politicians_arguing", block)

    def test_shared_event_preserves_non_shun_fallback(self):
        block = event_block("ywc_shared_events.txt", "ywc_shared.1")
        self.assertRegex(block, r"(?s)event_image = \{\s*trigger = \{ c:SHU \?= THIS \}\s*video = \"ywc_shu_opening\"")
        self.assertRegex(block, r"(?s)event_image = \{\s*trigger = \{ NOT = \{ c:SHU \?= THIS \} \}\s*video = \"africa_diplomats_negotiating\"")
        self.assertEqual(len(re.findall(r"event_image = \{", block)), 2)

    def test_event_images_follow_narrative_areas(self):
        for event_id, image in {"ywc_shu.1": "customs", "ywc_shu.2": "frontier", "ywc_shu.5": "customs", "ywc_shu.6": "opening", "ywc_shu.8": "frontier"}.items():
            with self.subTest(event=event_id):
                self.assertIn(f'video = "ywc_shu_{image}"', event_block("ywc_shu_jhg_events.txt", event_id))
        for event_id, image in {"ywc_shu.1000": "opening", "ywc_shu.1010": "frontier", "ywc_shu.1018": "customs", "ywc_shu.1110": "opening"}.items():
            with self.subTest(event=event_id):
                self.assertIn(f'video = "ywc_shu_{image}"', event_block("ywc_v03_country_shu_events.txt", event_id))
        self.assertIn('video = "africa_diplomats_negotiating"', event_block("ywc_shu_jhg_events.txt", "ywc_jhg.1"))
        self.assertIn('video = "unspecific_politicians_arguing"', event_block("ywc_v03_country_tib_events.txt", "ywc_tib.1000"))


if __name__ == "__main__":
    unittest.main()
