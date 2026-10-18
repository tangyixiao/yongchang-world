"""Guard rails for the JHG foundation arcs (the three country paths)."""

import json
import re
import unittest
from pathlib import Path
from tests.clausewitz_harness import PulseWorld, parse

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "data" / "content" / "v03" / "countries" / "jhg.json"
REGISTRY_PATH = ROOT / "data" / "content" / "v03" / "id_registry.json"
EFFECTS_PATH = ROOT / "yongchang_world" / "common" / "scripted_effects" / "ywc_v03_jhg_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world" / "common" / "scripted_triggers" / "ywc_v03_jhg_triggers.txt"
MOD = ROOT / "yongchang_world"

SLUGS = ["v03_jhg_court_assembly", "v03_jhg_convoy_capacity", "v03_jhg_tribute_autonomy"]
COURT, CONVOY, TRIBUTE = SLUGS
EVENT_IDS = [1000 + n for n in range(8)] + [1010 + n for n in range(10)] + [1020 + n for n in range(6)]
JE_IDS = [
    "ywc_je_v03_jhg_court_assembly",
    "ywc_je_v03_jhg_court_settlement",
    "ywc_je_v03_jhg_convoy_capacity",
    "ywc_je_v03_jhg_convoy_partner_watch",
    "ywc_je_v03_jhg_convoy_settlement",
    "ywc_je_v03_jhg_tribute_autonomy",
]

REQUIRED_EFFECTS = [
    "ywc_jhg_court_capture_cost_base",
    "ywc_jhg_court_choose_audit_contract",
    "ywc_jhg_court_choose_prince_guarantee",
    "ywc_jhg_court_choose_merchant_pool",
    "ywc_jhg_court_close_as_established",
    "ywc_jhg_court_close_as_compromise",
    "ywc_jhg_court_close_as_breach",
    "ywc_jhg_court_finalize",
    "ywc_jhg_court_reset_observation",
    "ywc_jhg_court_monthly_review",
    "ywc_jhg_court_bridge_legacy",
    "ywc_jhg_court_pay_filing_fee_once",
    "ywc_jhg_convoy_capture_cost_base",
    "ywc_jhg_convoy_choose_main_lane",
    "ywc_jhg_convoy_choose_shared_escort",
    "ywc_jhg_convoy_choose_insurance",
    "ywc_jhg_convoy_close_as_established",
    "ywc_jhg_convoy_close_as_compromise",
    "ywc_jhg_convoy_close_as_breach",
    "ywc_jhg_convoy_finalize",
    "ywc_jhg_convoy_reset_observation",
    "ywc_jhg_convoy_monthly_review",
    "ywc_jhg_convoy_bridge_legacy",
    "ywc_jhg_convoy_pay_filing_fee_once",
    "ywc_jhg_tribute_capture_cost_base",
    "ywc_jhg_tribute_choose_fixed_share",
    "ywc_jhg_tribute_choose_project_share",
    "ywc_jhg_tribute_choose_ambiguity",
    "ywc_jhg_tribute_close_as_established",
    "ywc_jhg_tribute_close_as_compromise",
    "ywc_jhg_tribute_close_as_breach",
    "ywc_jhg_tribute_finalize",
    "ywc_jhg_tribute_reset_observation",
    "ywc_jhg_tribute_monthly_review",
    "ywc_jhg_tribute_bridge_legacy",
    "ywc_jhg_tribute_pay_filing_fee_once",
]

REQUIRED_TRIGGERS = [
    "ywc_jhg_finance_safe",
    "ywc_jhg_court_bureaucracy_ready",
    "ywc_jhg_court_administration_staffed",
    "ywc_jhg_court_property_rep",
    "ywc_jhg_court_route_execution_ready",
    "ywc_jhg_court_can_pay",
    "ywc_jhg_convoy_navy_ready",
    "ywc_jhg_convoy_port_ready",
    "ywc_jhg_convoy_partner_ready",
    "ywc_jhg_convoy_route_execution_ready",
    "ywc_jhg_convoy_full_sea_lane_covered",
    "ywc_jhg_convoy_can_pay",
    "ywc_jhg_tribute_relationship_open",
    "ywc_jhg_tribute_partner_ready",
    "ywc_jhg_tribute_route_execution_ready",
    "ywc_jhg_tribute_can_pay",
]

PREFIX = {COURT: "ywc_jhg_court", CONVOY: "ywc_jhg_convoy", TRIBUTE: "ywc_jhg_tribute"}
CLOSERS = {COURT: 1007, CONVOY: 1018, TRIBUTE: 1025}


class JhgTerminalWorld(PulseWorld):
    """Run real JHG closers while fixture-driving only engine readiness predicates."""
    def condition(self, node, tag):
        key, comparison, value = node
        if key.endswith(("_route_execution_ready", "_full_ready", "_compromise_ready")) and value == "yes":
            return True
        if comparison == "?=":
            actual = bool(self.countries[tag].get(key, False))
            return actual == (value == "yes")
        if key in ("ywc_jhg_court_route", "ywc_jhg_convoy_route", "ywc_jhg_tribute_route"):
            return {"=": lambda a, b: a == b, ">": lambda a, b: a > b, "<": lambda a, b: a < b,
                    ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, "!=": lambda a, b: a != b}[comparison](self.countries[tag].get(key, 0), float(value))
        if key == "ywc_jhg_convoy_full_sea_lane_covered":
            return False
        return super().condition(node, tag)


def _script_condition(world, block, tag):
    return world.conditions(parse("condition = " + block)[0][2], tag)


def catalog():
    with CATALOG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def arc(slug):
    matches = [item for item in catalog()["arcs"] if item["slug"] == slug]
    assert len(matches) == 1, "expected exactly one arc named %s" % slug
    return matches[0]


def arc_text(item):
    parts = []
    for journal in item["journals"]:
        parts.extend([journal["script"], journal["goal"], journal["exit_conditions"]])
    for event in item["events"]:
        parts.extend([event["trigger"], event["immediate"]])
        for option in event["options"]:
            parts.append(option["effect"])
            parts.append(option.get("trigger", ""))
    return "\n".join(parts)


def definitions():
    names = set()
    for folder in ("scripted_effects", "scripted_triggers"):
        for path in sorted((MOD / "common" / folder).glob("*.txt")):
            text = path.read_text(encoding="utf-8-sig")
            names.update(re.findall(r"(?m)^([a-z_0-9]+)\s*=\s*\{", text))
    return names


def option_by_key(event, key):
    matches = [item for item in event["options"] if item["key"] == key]
    assert len(matches) == 1, "expected exactly one option %s" % key
    return matches[0]


class JhgFoundationTest(unittest.TestCase):
    def test_real_terminal_closers_make_journal_goal_and_exit_exclusive(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        cases = [
            (COURT, "court_assembly", "ywc_jhg_court_close_as_established", "established"),
            (COURT, "court_assembly", "ywc_jhg_court_close_as_compromise", "compromise"),
            (COURT, "court_assembly", "ywc_jhg_court_close_as_breach", "withdrawn"),
            (CONVOY, "convoy_capacity", "ywc_jhg_convoy_close_as_established", "established"),
            (CONVOY, "convoy_capacity", "ywc_jhg_convoy_close_as_compromise", "compromise"),
            (CONVOY, "convoy_capacity", "ywc_jhg_convoy_close_as_breach", "withdrawn"),
        ]
        for slug, slot, closer, terminal in cases:
            with self.subTest(slug=slug, terminal=terminal):
                tag = "JHG"
                prefix = "ywc_jhg_" + ("court" if slot == "court_assembly" else "convoy")
                start_var = "ywc_jhg_v03_jhg_" + slot + "_started"
                route = 2 if slot == "convoy_capacity" else 1
                world = JhgTerminalWorld(effects, {tag: {
                    start_var: 1, "ywc_v03_active_arc_count": 1,
                    "ywc_v03_visible_task_count": 1, prefix + "_route": route,
                    prefix + "_shared_fund": 1 if slot == "convoy_capacity" and route == 2 else 0,
                }})
                world.run(closer, tag)
                item = arc(slug)
                for journal in item["journals"]:
                    complete = _script_condition(world, journal["goal"], tag)
                    fail = _script_condition(world, journal["exit_conditions"], tag)
                    self.assertFalse(complete and fail, journal["id"])
                    if journal["id"].endswith("_settlement"):
                        self.assertEqual((complete, fail), (terminal != "withdrawn", terminal == "withdrawn"))
                    if journal["id"].endswith("_partner_watch"):
                        self.assertEqual((complete, fail), (terminal != "withdrawn", terminal == "withdrawn"))

    def test_arcs_are_registered_with_their_reserved_event_ranges(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
        ranges = [r for r in registry["arc_ranges"] if r["catalog_key"] == "country_jhg"]
        self.assertEqual(3, len(ranges))
        for item in catalog()["arcs"]:
            reserved = [r for r in ranges if r["slug"] == item["slug"]][0]
            numbers = sorted(int(e["id"].split(".")[1]) for e in item["events"])
            self.assertGreaterEqual(numbers[0], reserved["start"], item["slug"])
            self.assertLessEqual(numbers[-1], reserved["end"], item["slug"])
        found = sorted(int(e["id"].split(".")[1]) for i in catalog()["arcs"] for e in i["events"])
        self.assertEqual(found, sorted(EVENT_IDS))

    def test_foundation_arcs_keep_the_locked_card_shape(self):
        self.assertEqual({"key", "layer", "runtime_tags", "arcs"}, set(catalog()))
        expected = {"slug", "era", "participants", "depends_on", "journals", "events",
                    "outcomes", "legacy_links"}
        counts = {COURT: (8, 2), CONVOY: (10, 3), TRIBUTE: (6, 1)}
        for item in catalog()["arcs"]:
            self.assertEqual(expected, set(item), item["slug"])
            self.assertEqual("foundation", item["era"])
            self.assertEqual([], item["depends_on"])
            self.assertGreaterEqual(len(item["outcomes"]), 4)
            self.assertGreaterEqual(len(item["legacy_links"]), 2)
            self.assertEqual(counts[item["slug"]], (len(item["events"]), len(item["journals"])))
            for journal in item["journals"]:
                self.assertEqual({"id", "title", "desc", "script", "goal", "exit_conditions"},
                                 set(journal))
                self.assertTrue(journal["id"].startswith("ywc_je_v03_jhg_"))
                self.assertIsNone(
                    re.search(r"(?<![a-z0-9_])(?:complete|fail)\s*=", journal["script"]),
                    journal["id"])
            for event in item["events"]:
                self.assertEqual({"id", "title", "desc", "trigger", "immediate", "options",
                                  "purpose", "reads", "writes"}, set(event), event["id"])
                self.assertIn("ywc_v03_can_deliver_major = yes", event["trigger"])
                self.assertIn("ywc_v03_mark_major_delivered = yes", event["immediate"])
                keys = {option["key"] for option in event["options"]}
                self.assertIn("defer", keys, event["id"])
                self.assertIn("withdraw", keys, event["id"])
                for option in event["options"]:
                    self.assertEqual({"key", "label", "effect", "ai_chance", "cost_note",
                                      "consequence_note"}, set(option) - {"trigger"})
                    self.assertEqual({"zh", "en"}, set(option["cost_note"]))
                    self.assertEqual({"zh", "en"}, set(option["consequence_note"]))
                    self.assertTrue(option["ai_chance"].lstrip("{ ").startswith("base ="))
        ids = sorted(j["id"] for i in catalog()["arcs"] for j in i["journals"])
        self.assertEqual(sorted(JE_IDS), ids)

    def test_required_foundation_scripts_are_defined(self):
        names = definitions()
        missing = [n for n in REQUIRED_EFFECTS + REQUIRED_TRIGGERS if n not in names]
        self.assertEqual([], missing)

    def test_every_scripted_call_in_the_foundation_arcs_resolves(self):
        names = definitions()
        allowed = set(names)
        called = set()
        for slug in SLUGS:
            called.update(re.findall(r"\b(ywc_[a-z_0-9]+)\s*=\s*(?:yes|no)\b", arc_text(arc(slug))))
        unresolved = sorted(c for c in called if c not in allowed)
        self.assertEqual([], unresolved)

    def test_every_foundation_event_has_a_dispatch_branch(self):
        for slug in SLUGS:
            text = arc_text(arc(slug))
            for event in arc(slug)["events"]:
                number = event["id"].split(".")[1]
                self.assertIn("var:ywc_jhg_pending_event = %s" % number, text)
                self.assertIn("trigger_event = { id = ywc_jhg.%s }" % number, text)
                self.assertIn("remove_variable = ywc_jhg_pending_event", text)

    def test_route_choices_record_route_one_two_three(self):
        names = definitions()
        for slug in SLUGS:
            prefix = PREFIX[slug]
            chosen = re.findall(r"(%s_choose_[a-z_]+) = yes" % prefix, arc_text(arc(slug)))
            self.assertGreaterEqual(len(set(chosen)), 3, slug)
            for name in set(chosen):
                self.assertIn(name, names)
                body = EFFECTS_PATH.read_text(encoding="utf-8-sig")
                block = re.search(r"%s = \{(.*?)\n\}" % name, body, re.S)
                self.assertIsNotNone(block, name)
                self.assertRegex(block.group(1), r"set_variable = \{ name = %s_route value = [123] \}" % prefix)

    def test_charges_are_real_and_guarded_and_never_double_billed(self):
        body = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for slug in SLUGS:
            prefix = PREFIX[slug]
            payer = "%s_pay_filing_fee_once" % prefix
            block = re.search(r"%s = \{(.*?)\n\}" % payer, body, re.S).group(1)
            self.assertIn("add_treasury", block)
            self.assertRegex(block, r"multiply\s*=\s*-1")
            self.assertIn("%s_filing_fee_paid" % prefix, block)
            self.assertIn("%s_can_pay = yes" % prefix, block)
            self.assertIn("NOT = { has_variable = %s_filing_fee_paid }" % prefix, block)
            captured = "%s_capture_cost_base" % prefix
            cap = re.search(r"%s = \{(.*?)\n\}" % captured, body, re.S).group(1)
            self.assertIn("yearly_gross_income", cap)
            self.assertIn("divide = 52", cap)
            self.assertRegex(cap, r"clamp_variable = \{ name = %s_captured_income min = 100 max = 1000000000 \}" % prefix)
            for event in arc(slug)["events"]:
                for option in event["options"]:
                    if "_choose_" not in option["effect"]:
                        self.assertNotIn("add_treasury", option["effect"])
                        continue
                    self.assertIn("%s_filing_fee_paid" % prefix, option["effect"])
        finance = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("NOT = { in_default = yes }", finance)
        self.assertIn("NOT = { has_modifier = declared_bankruptcy }", finance)

    def test_closers_write_outcome_and_release_the_slot(self):
        body = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for slug in SLUGS:
            prefix = PREFIX[slug]
            slot = "ywc_jhg_v03_" + slug[4:]
            closer = re.search(r"%s_close_as_established = \{(.*?)\n\}" % prefix, body, re.S).group(1)
            self.assertIn("%s_outcome value = 1" % slot, closer)
            self.assertIn("%s_established" % prefix, closer)
            finalize = re.search(r"%s_finalize = \{(.*?)\n\}" % prefix, body, re.S).group(1)
            self.assertIn("ywc_v03_active_arc_count", finalize)
            self.assertIn("ywc_v03_visible_task_count", finalize)
            self.assertIn("change_variable", finalize)
            self.assertIn("clamp_variable", finalize)
            self.assertIn("%s_settled value = 1" % slot, finalize)
            breach = re.search(r"%s_close_as_breach = \{(.*?)\n\}" % prefix, body, re.S).group(1)
            self.assertIn("%s_outcome value = 4" % slot, breach)
            closer_event = [e for e in arc(slug)["events"]
                            if int(e["id"].split(".")[1]) == CLOSERS[slug]][0]
            effects = " ".join(o["effect"] for o in closer_event["options"])
            self.assertIn("%s_close_as_established = yes" % prefix, effects)
            self.assertIn("%s_close_as_breach = yes" % prefix, effects)
            entry = arc(slug)["journals"][0]
            self.assertIn("is_shown_when_inactive", entry["script"])
            self.assertIn("possible", entry["script"])
            self.assertIn("on_monthly_pulse", entry["script"])

    def test_observation_maturation_and_blockage_notices_exist(self):
        body = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for slug in SLUGS:
            prefix = PREFIX[slug]
            review = re.search(r"%s_monthly_review = \{(.*?)\n\}" % prefix, body, re.S).group(1)
            self.assertIn("months = 6", review)
            self.assertIn("%s_six_months_complete" % prefix, review)
            self.assertIn("%s_limited_six_months_complete" % prefix, review)
            self.assertIn("%s_12_notice" % prefix, review)
            self.assertIn("%s_36_notice" % prefix, review)
            self.assertIn("days = 365", review)
            self.assertIn("days = 1095", review)
            reset = re.search(r"%s_reset_observation = \{(.*?)\n\}" % prefix, body, re.S).group(1)
            self.assertIn("%s_observation_timer" % prefix, reset)
            self.assertIn("%s_six_months_complete" % prefix, reset)

    def test_full_sea_lane_cover_is_unreachable(self):
        triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        body = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        full = re.search(r"ywc_jhg_convoy_full_sea_lane_covered = \{(.*?)\n\}", triggers, re.S).group(1)
        self.assertIn("ywc_jhg_convoy_full_fleet_fee", full)
        self.assertIn("ywc_jhg_convoy_lane_coverage >= 7", full)
        self.assertNotIn("full_fleet_fee =", body)
        self.assertNotIn("set_variable = { name = ywc_jhg_convoy_full_fleet_fee", body)
        established = re.search(r"ywc_jhg_convoy_close_as_established = \{(.*?)\n\}", body, re.S).group(1)
        self.assertIn("NOT = { ywc_jhg_convoy_full_sea_lane_covered = yes }", established)
        goal = arc(CONVOY)["journals"][0]["goal"]
        self.assertIn("NOT = { ywc_jhg_convoy_full_sea_lane_covered = yes }", goal)

    def test_tribute_and_convoy_write_the_fixed_legacy_variables(self):
        body = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("ywc_campaign_jhg_c1_outcome", body)
        self.assertIn("ywc_je_flavor_jhg_convoy_1", body)
        legacy = [link for i in catalog()["arcs"] for link in i["legacy_links"]]
        self.assertIn("ywc_campaign_jhg_c1_outcome", legacy)
        self.assertIn("ywc_je_flavor_jhg_convoy_1", legacy)


if __name__ == "__main__":
    unittest.main()
