import json
import pathlib
import re
import unittest

from tools import build_hegemony_content as builder
from tools import ywc_hegemony_check as checker


ROOT = pathlib.Path(__file__).parents[1]
CATALOG = json.loads((ROOT / "data/content/hegemony_event_catalog.json").read_text(encoding="utf-8"))


class HegemonyCatalogTest(unittest.TestCase):
    def setUp(self):
        self.catalog = CATALOG
        self.events = {event["id"]: event for event in self.catalog["events"]}

    def test_catalog_holds_exactly_33_events(self):
        self.assertEqual(len(self.events), 33)
        hegemon = [event for event in self.catalog["events"] if event["kind"] == "hegemon"]
        participant = [event for event in self.catalog["events"] if event["kind"] == "participant"]
        self.assertEqual(len(hegemon), 6)
        self.assertEqual(len(participant), 27)

    def test_nine_candidates_get_summon_and_two_followups(self):
        shorts = {participant["short"] for participant in self.catalog["participants"]}
        self.assertEqual(len(shorts), 9)
        for short in shorts:
            for suffix in (200, 201, 202):
                self.assertIn(f"ywc_{short}.{suffix}", self.events)
        self.assertEqual(self.events["ywc_jhg.200"]["slot"], "summon")
        self.assertEqual(self.events["ywc_kor.201"]["slot"], "compliant")
        self.assertEqual(self.events["ywc_lan.202"]["slot"], "defiant")

    def test_every_summon_records_a_stance_answer(self):
        for event in self.catalog["events"]:
            if event.get("slot") != "summon":
                continue
            self.assertEqual(len(event["choices"]), 3, event["id"])
            stances = set()
            for choice in event["choices"]:
                stance_ops = [op for op in choice["ops"] if op["op"] == "stance"]
                self.assertEqual(len(stance_ops), 1, event["id"])
                stances.add(stance_ops[0]["value"])
            self.assertEqual(stances, {1, 2, 3}, event["id"])

    def test_followups_fire_only_from_the_hegemon_stage_machine(self):
        # The compliant/defiant followups are dispatched by the holder pulse,
        # so they must never be referenced from the summon events.
        for event in self.catalog["events"]:
            if event.get("slot") == "summon":
                text = json.dumps(event)
                self.assertNotIn(".201", text.replace("ywc_" + event["short"] + ".201", ""))

    def test_settlement_has_three_gated_outcomes(self):
        settle = self.events["ywc_hegemony.6"]
        self.assertEqual(len(settle["choices"]), 3)
        self.assertIn("ywc_hegemony_authority >= 55", settle["trigger"])
        outcomes = {choice["ops"][0]["value"] for choice in settle["choices"]}
        self.assertEqual(outcomes, {1, 2, 3})

    def test_every_event_is_bilingual(self):
        for event in self.catalog["events"]:
            for field in ("title_cn", "desc_cn", "title_en", "desc_en"):
                self.assertTrue(event[field].strip(), f"{event['id']} missing {field}")
            for choice in event["choices"]:
                self.assertTrue(choice["label_cn"].strip(), event["id"])
                self.assertTrue(choice["label_en"].strip(), event["id"])

    def test_participant_costs_scale_with_country_size(self):
        costs = {p["short"]: p["cost"] for p in self.catalog["participants"]}
        for short, cost in costs.items():
            summon = self.events[f"ywc_{short}.200"]
            paid = [op["amount"] for choice in summon["choices"] for op in choice["ops"]
                    if op["op"] == "treasury"]
            enroll = next(op["amount"] for choice in summon["choices"]
                          for op in choice["ops"] if op["op"] == "treasury")
            self.assertEqual(enroll, -cost, short)
            self.assertTrue(all(amount <= 0 for amount in paid), short)


class HegemonyGeneratorTest(unittest.TestCase):
    def test_generation_is_deterministic_and_fresh(self):
        self.assertEqual(builder.render_all(ROOT), builder.render_all(ROOT))
        for path, text in builder.render_all(ROOT).items():
            self.assertEqual(path.read_text(encoding="utf-8-sig"), text, str(path))

    def test_validator_rejects_duplicate_ids(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["events"].append(dict(catalog["events"][0]))
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_validator_rejects_missing_bilingual_copy(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["events"][0]["title_en"] = " "
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_validator_rejects_wrong_event_count(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["events"].pop()
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_validator_rejects_unknown_op(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["events"][0]["choices"][0]["ops"].append({"op": "annex_everything"})
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_validator_rejects_missing_participant_followup(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["events"] = [event for event in catalog["events"] if event["id"] != "ywc_tib.202"]
        with self.assertRaises(ValueError):
            builder.validate(catalog)


class HegemonyCheckerTest(unittest.TestCase):
    def test_checker_accepts_the_repository(self):
        catalog = builder.load_catalog(ROOT)
        events = builder.validate(catalog)
        problems: list[str] = []
        script = (ROOT / "yongchang_world/events/ywc_hegemony_events.txt").read_text(encoding="utf-8-sig")
        checker.check_events(events, script, problems)
        self.assertEqual(problems, [])

    def test_check_pulse_flags_a_missing_summon(self):
        catalog = builder.load_catalog(ROOT)
        effects = (ROOT / "yongchang_world/common/scripted_effects/ywc_hegemony_effects.txt").read_text(encoding="utf-8-sig")
        broken = effects.replace("trigger_event = { id = ywc_mgl.200 }", "trigger_event = { id = ywc_mgl.999 }")
        problems: list[str] = []
        checker.check_pulse(catalog, broken, problems)
        self.assertTrue(any("mgl" in problem for problem in problems), problems)

    def test_check_hooks_flags_a_missing_gate(self):
        campaign = (ROOT / "yongchang_world/events/ywc_large_campaign_events.txt").read_text(encoding="utf-8-sig")
        problems: list[str] = []
        checker.check_hooks(campaign.replace("var:ywc_campaign_crisis1_outcome = 1", "var:x = 1"), problems)
        self.assertTrue(any("crisis" in problem for problem in problems), problems)

    def test_check_modifiers_flags_undeclared_modifier(self):
        script = (ROOT / "yongchang_world/events/ywc_hegemony_events.txt").read_text(encoding="utf-8-sig")
        modifiers = (ROOT / "yongchang_world/common/static_modifiers/ywc_static_modifiers.txt").read_text(encoding="utf-8-sig")
        problems: list[str] = []
        checker.check_modifiers(script + "add_modifier = { name = ywc_hegemony_missing }", "", modifiers, problems)
        self.assertTrue(any("ywc_hegemony_missing" in problem for problem in problems), problems)


if __name__ == "__main__":
    unittest.main()
