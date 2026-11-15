"""Player-facing KOR partner names must match the actual dispatched countries."""
import json
import unittest
from pathlib import Path

from test_v03_kor_instructor_lifecycle import signed_world
from test_v03_kor_procurement_protocol import procurement_world, send_quote
from clausewitz_harness import parse

ROOT = Path(__file__).resolve().parents[1]


class KorPartnerLabelTests(unittest.TestCase):
    def test_visible_names_match_registered_tags_and_real_recipients(self):
        registry = json.loads((ROOT / "data/scenario/tag_registry.json").read_text(encoding="utf-8"))
        names = {country["tag"]: country["name_zh"] for country in registry["countries"]}
        self.assertEqual(names["SHU"], "大顺")
        self.assertEqual(names["JHG"], "靖海国")
        for tag in ("SHU", "JHG"):
            with self.subTest(tag=tag, protocol="instructor"):
                world, _ = signed_world(partner=tag)
                job = next(job for job in world.jobs if job.event_id == "ywc_kor.1030")
                self.assertEqual(job.recipient, world.country_ref(tag))
            with self.subTest(tag=tag, protocol="procurement"):
                world, _ = procurement_world()
                job = send_quote(world, partner=tag)
                self.assertEqual(job.recipient, world.country_ref(tag))

        catalog = json.loads((ROOT / "data/content/v03/countries/kor.json").read_text(encoding="utf-8"))
        events = {event["id"]: event for arc in catalog["arcs"] for event in arc["events"]}
        intro = events["ywc_kor.1004"]["desc"]
        for expected in ("大顺", "靖海"): self.assertIn(expected, intro["zh"])
        for expected in ("Great Shun", "Jinghai"): self.assertIn(expected, intro["en"])
        generated_zh = (ROOT / "yongchang_world/localization/simp_chinese/ywc_v03_country_kor_l_simp_chinese.yml").read_text(encoding="utf-8-sig")
        generated_en = (ROOT / "yongchang_world/localization/english/ywc_v03_country_kor_l_english.yml").read_text(encoding="utf-8-sig")
        for event_id, prefix in (("ywc_kor.1004", "offer"), ("ywc_kor.1007", "quote"),
                                 ("ywc_kor.1031", "retry"), ("ywc_kor.1034", "retry")):
            for suffix, zh, en in (("shu", "大顺", "Great Shun"), ("jhg", "靖海", "Jinghai")):
                option = next(o for o in events[event_id]["options"] if o["key"] == f"{prefix}_{suffix}")
                with self.subTest(event=event_id, partner=suffix):
                    self.assertIn(zh, option["label"]["zh"])
                    self.assertIn(en, option["label"]["en"])
                    self.assertNotIn("准噶尔", option["label"]["zh"])
                    self.assertNotIn("蜀", option["label"]["zh"])
                    self.assertIn(f'{event_id}.{prefix}_{suffix}:0 "{option["label"]["zh"]}"', generated_zh)
                    self.assertIn(f'{event_id}.{prefix}_{suffix}:0 "{option["label"]["en"]}"', generated_en)
                    if prefix == "quote":
                        self.assertIn(zh, option["consequence_note"]["zh"])
                        self.assertIn(en, option["consequence_note"]["en"])


class NqgPartnerLabelTests(unittest.TestCase):
    def test_grain_aid_retry_names_the_actual_shu_recipient(self):
        catalog = json.loads((ROOT / "data/content/v03/countries/nqg.json").read_text(encoding="utf-8"))
        event = next(e for arc in catalog["arcs"] for e in arc["events"] if e["id"] == "ywc_nqg.1031")
        option = next(o for o in event["options"] if o["key"] == "retry_shu")
        self.assertIn("大顺", option["label"]["zh"])
        self.assertIn("Great Shun", option["label"]["en"])
        self.assertIn("ywc_nqg_aid_choose_retry_shu", option["effect"])
        effects = parse((ROOT / "yongchang_world/common/scripted_effects/ywc_v03_nqg_effects.txt").read_text(encoding="utf-8-sig"))
        by_name = {key: body for key, _, body in effects}
        def keys(body):
            for key, _, value in body:
                yield key
                if isinstance(value, list): yield from keys(value)
        self.assertIn("ywc_nqg_aid_send_shu", list(keys(by_name["ywc_nqg_aid_choose_retry_shu"])))
        self.assertIn("c:SHU", list(keys(by_name["ywc_nqg_aid_send_shu"])))
        for language, name in (("simp_chinese", "zh"), ("english", "en")):
            generated = (ROOT / f"yongchang_world/localization/{language}/ywc_v03_country_nqg_l_{language}.yml").read_text(encoding="utf-8-sig")
            self.assertIn(f'ywc_nqg.1031.retry_shu:0 "{option["label"][name]}"', generated)


if __name__ == "__main__":
    unittest.main()
