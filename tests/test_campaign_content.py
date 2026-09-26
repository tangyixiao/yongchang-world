import json
import pathlib
import re
import unittest

from tools import build_campaign_content as builder
from tools import ywc_campaign_check as checker


ROOT = pathlib.Path(__file__).parents[1]
CATALOG = json.loads((ROOT / "data/content/large_campaign_event_catalog.json").read_text(encoding="utf-8"))


class CampaignCatalogTest(unittest.TestCase):
    def setUp(self):
        self.catalog = CATALOG
        self.events = {event["id"]: event for event in self.catalog["events"]}

    def test_catalog_holds_exactly_180_unique_events(self):
        self.assertEqual(len(self.events), 180)
        national = [event for event in self.catalog["events"] if event["kind"] == "national"]
        crisis = [event for event in self.catalog["events"] if event["kind"] == "crisis"]
        self.assertEqual(len(national), 150)
        self.assertEqual(len(crisis), 30)

    def test_ten_countries_have_three_chapters_of_five(self):
        for short in self.catalog["countries"]:
            ids = [event["id"] for event in self.catalog["events"]
                   if event.get("short") == short]
            self.assertEqual(ids, [f"ywc_{short}.{100 + index}" for index in range(15)], short)
            for event in self.catalog["events"]:
                if event.get("short") == short and event["position"] == 5:
                    self.assertTrue(event["final"], event["id"])
                    self.assertTrue(
                        self.catalog["countries"][short]["gates"][str(event["chapter"])],
                        f"{event['id']} needs an establishment gate",
                    )

    def test_crises_cover_six_stages_each(self):
        for crisis in self.catalog["crises"]:
            stages = sorted(
                event["stage"] for event in self.catalog["events"]
                if event.get("crisis") == int(crisis)
            )
            self.assertEqual(stages, [1, 2, 3, 4, 5, 6], crisis)
            final = self.events[f"ywc_crisis.{(int(crisis) - 1) * 6 + 6}"]
            self.assertEqual(len(final["choices"]), 3, crisis)

    def test_every_event_is_bilingual_with_two_choices(self):
        for event in self.catalog["events"]:
            minimum = 3 if event.get("stage") == 6 else 2
            self.assertGreaterEqual(len(event["choices"]), minimum, event["id"])
            for field in ("title_cn", "desc_cn", "title_en", "desc_en"):
                self.assertTrue(event[field].strip(), f"{event['id']} missing {field}")
            for choice in event["choices"]:
                self.assertTrue(choice["label_cn"].strip(), event["id"])
                self.assertTrue(choice["label_en"].strip(), event["id"])

    def test_crisis_answers_are_recorded_on_the_design_countries(self):
        for event in self.catalog["events"]:
            if event["kind"] != "crisis":
                continue
            self.assertTrue(event["answerer"], event["id"])

    def test_chapter_settlements_never_grant_territory_or_subject_freedoms(self):
        forbidden = ("set_key = ", "annex", "release_subject", "add_claim", "own_manila")
        script = (ROOT / "yongchang_world/events/ywc_large_campaign_events.txt").read_text(encoding="utf-8-sig")
        for word in forbidden:
            self.assertNotIn(word, script)


class CampaignGeneratorTest(unittest.TestCase):
    def test_generation_is_deterministic_and_fresh(self):
        first = builder.render_all(ROOT)
        second = builder.render_all(ROOT)
        self.assertEqual(first, second)
        for path, text in first.items():
            self.assertEqual(path.read_text(encoding="utf-8-sig"), text, str(path))

    def test_validator_rejects_duplicate_ids(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["events"].append(dict(catalog["events"][0]))
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_validator_rejects_out_of_order_national_ids(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["events"][0]["id"] = "ywc_shu.120"
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_validator_rejects_missing_bilingual_copy(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["events"][0]["title_en"] = "  "
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_validator_rejects_thin_options(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["events"][0]["choices"] = catalog["events"][0]["choices"][:1]
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_validator_rejects_incomplete_crisis_stage(self):
        catalog = json.loads(json.dumps(CATALOG))
        event = next(event for event in catalog["events"] if event["id"] == "ywc_crisis.6")
        catalog["events"].remove(event)
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_generated_options_cost_treasury_only_when_priced(self):
        script = (ROOT / "yongchang_world/events/ywc_large_campaign_events.txt").read_text(encoding="utf-8-sig")
        option_pattern = re.compile(r"(?ms)^    option = \{(.*?)(?=^    option = \{|\Z)")
        for event in CATALOG["events"]:
            block = script.split(f"{event['id']} = {{", 1)[1].split("\nywc_", 1)[0]
            options = option_pattern.findall(block)
            self.assertEqual(len(options), len(event["choices"]), event["id"])
            for index, (option, choice) in enumerate(zip(options, event["choices"])):
                letter = chr(ord("a") + index)
                self.assertIn(f"name = {event['id']}.{letter}", option, event["id"])
                if choice["cost"]:
                    self.assertIn(f"add_treasury = -{choice['cost']}", option, event["id"])
                else:
                    self.assertNotRegex(option, r"add_treasury = -\d+", event["id"])


class CampaignCheckerTest(unittest.TestCase):
    def test_checker_accepts_the_repository(self):
        # The repo-level check is the acceptance command itself; here we only
        # assert its pure functions agree on the committed content.
        catalog = builder.load_catalog(ROOT)
        events = builder.validate(catalog)
        problems: list[str] = []
        script = (ROOT / "yongchang_world/events/ywc_large_campaign_events.txt").read_text(encoding="utf-8-sig")
        checker.check_events(events, catalog["countries"], catalog["crises"], script, problems)
        self.assertEqual(problems, [])

    def test_check_events_flags_a_missing_settlement_marker(self):
        catalog = builder.load_catalog(ROOT)
        events = builder.validate(catalog)
        script = (ROOT / "yongchang_world/events/ywc_large_campaign_events.txt").read_text(encoding="utf-8-sig")
        broken = script.replace(
            "set_variable = { name = ywc_je_flavor_shu_court_1_resolved value = 1 }",
            "set_variable = { name = ywc_je_flavor_shu_court_2_resolved value = 1 }",
        )
        self.assertNotEqual(script, broken, "mutation must change the script")
        problems: list[str] = []
        checker.check_events(events, catalog["countries"], catalog["crises"], broken, problems)
        self.assertTrue(any("ywc_shu.104" in problem for problem in problems), problems)

    def test_check_crisis_journals_flags_a_missing_stage(self):
        catalog = builder.load_catalog(ROOT)
        effects = (ROOT / "yongchang_world/common/scripted_effects/ywc_campaign_effects.txt").read_text(encoding="utf-8-sig")
        broken = effects.replace("trigger_event = { id = ywc_crisis.6 }", "trigger_event = { id = ywc_crisis.99 }")
        problems: list[str] = []
        checker.check_crisis_journals(
            catalog["crises"],
            (ROOT / "yongchang_world/common/journal_entries/ywc_large_campaign_crises.txt").read_text(encoding="utf-8-sig"),
            broken,
            problems,
        )
        self.assertTrue(any("ywc_crisis.6" in problem for problem in problems), problems)

    def test_check_modifiers_flags_undeclared_modifier(self):
        script = (ROOT / "yongchang_world/events/ywc_large_campaign_events.txt").read_text(encoding="utf-8-sig")
        effects = (ROOT / "yongchang_world/common/scripted_effects/ywc_campaign_effects.txt").read_text(encoding="utf-8-sig")
        problems: list[str] = []
        checker.check_modifiers(script + "add_modifier = { name = ywc_campaign_missing }", effects, "", problems)
        self.assertTrue(any("ywc_campaign_missing" in problem for problem in problems), problems)


if __name__ == "__main__":
    unittest.main()
