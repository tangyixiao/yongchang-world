import json
import pathlib
import unittest

from tools import build_southwest_content as builder
from tools import ywc_southwest_check as checker


ROOT = pathlib.Path(__file__).parents[1]
CATALOG = json.loads((ROOT / "data/content/southwest_event_catalog.json").read_text(encoding="utf-8"))


class SouthwestCatalogTest(unittest.TestCase):
    def setUp(self):
        self.catalog = CATALOG
        self.events = {event["id"]: event for line in self.catalog["lines"] for event in line["events"]}

    def test_six_lines_with_three_events_each(self):
        self.assertEqual(len(self.catalog["lines"]), 6)
        for line in self.catalog["lines"]:
            self.assertEqual([event["slot"] for event in line["events"]], [1, 2, 3], line["short"])
            self.assertEqual(line["journal"], f"ywc_je_sw_{line['short']}")
        self.assertEqual(len(self.events), 18)

    def test_every_event_is_bilingual_with_two_choices(self):
        for event in self.events.values():
            for field in ("title_cn", "desc_cn", "title_en", "desc_en"):
                self.assertTrue(event[field].strip(), f"{event['id']} missing {field}")
            self.assertEqual(len(event["choices"]), 2, event["id"])
            for choice in event["choices"]:
                self.assertTrue(choice["label_cn"].strip(), event["id"])
                self.assertTrue(choice["label_en"].strip(), event["id"])

    def test_final_events_settle_their_line_both_ways(self):
        for line in self.catalog["lines"]:
            final = line["events"][-1]
            markers = {op["name"] for choice in final["choices"] for op in choice["ops"]
                       if op["op"] == "marker"}
            self.assertIn(f"ywc_sw_{line['short']}_resolved", markers, line["short"])
            self.assertIn(f"ywc_sw_{line['short']}_failed", markers, line["short"])

    def test_relations_targets_exist_in_the_scenario(self):
        known = {"SHU", "GBR", "TIB", "DER", "BUR"}
        for event in self.events.values():
            for choice in event["choices"]:
                for op in choice["ops"]:
                    if op["op"] == "relations":
                        self.assertIn(op["tag"], known, event["id"])

    def test_no_forbidden_effects_in_the_southwest_layer(self):
        script = (ROOT / "yongchang_world/events/ywc_southwest_events.txt").read_text(encoding="utf-8-sig")
        for word in ("annex", "add_claim", "release_subject", "set_key = ", "own_manila",
                     "ywc_route_", "change_variable = { name = ywc_heritage_legitimacy"):
            self.assertNotIn(word, script)

    def test_regionals_never_touch_shared_direction_effects(self):
        script = (ROOT / "yongchang_world/events/ywc_southwest_events.txt").read_text(encoding="utf-8-sig")
        for name in ("ywc_add_heritage_legitimacy", "ywc_lower_heritage_legitimacy",
                     "ywc_add_maritime_network", "ywc_raise_autonomy_pressure"):
            self.assertNotIn(name, script)


class SouthwestGeneratorTest(unittest.TestCase):
    def test_generation_is_deterministic_and_fresh(self):
        self.assertEqual(builder.render_all(ROOT), builder.render_all(ROOT))
        for path, text in builder.render_all(ROOT).items():
            self.assertEqual(path.read_text(encoding="utf-8-sig"), text, str(path))

    def test_validator_rejects_duplicate_ids(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["lines"][0]["events"].append(dict(catalog["lines"][0]["events"][0]))
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_validator_rejects_missing_bilingual_copy(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["lines"][0]["events"][0]["title_en"] = " "
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_validator_rejects_wrong_line_size(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["lines"][0]["events"].pop()
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_validator_rejects_unknown_op(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["lines"][0]["events"][0]["choices"][0]["ops"].append({"op": "annex"})
        with self.assertRaises(ValueError):
            builder.validate(catalog)

    def test_validator_rejects_unsettled_line(self):
        catalog = json.loads(json.dumps(CATALOG))
        event = catalog["lines"][0]["events"][2]
        for choice in event["choices"]:
            choice["ops"] = [op for op in choice["ops"] if op.get("name") != "ywc_sw_ljg_resolved"]
        with self.assertRaises(ValueError):
            builder.validate(catalog)


class SouthwestCheckerTest(unittest.TestCase):
    def test_checker_accepts_the_repository(self):
        catalog = builder.load_catalog(ROOT)
        events = builder.validate(catalog)
        problems: list[str] = []
        script = (ROOT / "yongchang_world/events/ywc_southwest_events.txt").read_text(encoding="utf-8-sig")
        checker.check_events(events, script, problems)
        self.assertEqual(problems, [])

    def test_check_journals_flags_a_missing_mount(self):
        catalog = builder.load_catalog(ROOT)
        starts = (ROOT / "yongchang_world/common/history/countries/ywc_regional_countries.txt").read_text(encoding="utf-8-sig")
        problems: list[str] = []
        checker.check_journals(
            catalog,
            (ROOT / "yongchang_world/common/journal_entries/ywc_southwest_journal.txt").read_text(encoding="utf-8-sig"),
            (ROOT / "yongchang_world/events/ywc_southwest_events.txt").read_text(encoding="utf-8-sig"),
            starts.replace("add_journal_entry = { type = ywc_je_sw_shd }", ""),
            problems,
        )
        self.assertTrue(any("SHD" in problem for problem in problems), problems)

    def test_check_modifiers_flags_undeclared_modifier(self):
        script = (ROOT / "yongchang_world/events/ywc_southwest_events.txt").read_text(encoding="utf-8-sig")
        modifiers = (ROOT / "yongchang_world/common/static_modifiers/ywc_static_modifiers.txt").read_text(encoding="utf-8-sig")
        problems: list[str] = []
        checker.check_modifiers(script + "add_modifier = { name = ywc_sw_missing }", modifiers, problems)
        self.assertTrue(any("ywc_sw_missing" in problem for problem in problems), problems)


if __name__ == "__main__":
    unittest.main()
