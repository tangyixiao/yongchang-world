"""LAN foundation gate: 24 events / 6 journals / 3 arcs of 8+2, and the honesty rules that
keep the arc from handing out mines, laws or free legitimacy."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "content" / "v03" / "countries" / "lan.json"
EFFECTS_PATH = ROOT / "yongchang_world" / "common" / "scripted_effects" / "ywc_v03_lan_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world" / "common" / "scripted_triggers" / "ywc_v03_lan_triggers.txt"
MODIFIERS_PATH = ROOT / "yongchang_world" / "common" / "static_modifiers" / "ywc_v03_lan_modifiers.txt"

ARCS = {
    "v03_lan_mine_accounts": (1000, 1007),
    "v03_lan_river_compacts": (1010, 1017),
    "v03_lan_work_accident_fund": (1020, 1027),
}
SLOTS = {
    "v03_lan_mine_accounts": "mine_accounts",
    "v03_lan_river_compacts": "river_compacts",
    "v03_lan_work_accident_fund": "work_accident_fund",
}


def _catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _arc(catalog, slug):
    for arc in catalog["arcs"]:
        if arc["slug"] == slug:
            return arc
    raise AssertionError(f"arc {slug} missing")


def _arc_text(arc):
    parts = []
    for journal in arc["journals"]:
        parts += [journal["script"], journal["goal"], journal["exit_conditions"]]
    for event in arc["events"]:
        parts += [event["trigger"], event["immediate"]]
        for option in event["options"]:
            parts += [option["effect"], option.get("trigger", "")]
    return "\n".join(parts)


def _number(event_id):
    return int(event_id.rsplit(".", 1)[-1])


def _definitions():
    found = set()
    for folder in ("scripted_effects", "scripted_triggers"):
        for path in (ROOT / "yongchang_world" / "common" / folder).glob("*.txt"):
            text = path.read_text(encoding="utf-8-sig")
            found |= set(re.findall(r"(?m)^([a-z_0-9]+)\s*=\s*\{", text))
    return found


def _helper_body(text, name):
    start = text.index(f"\n{name} = {{")
    return text[start:text.find("\n}", start)]


class LanCatalogShapeTest(unittest.TestCase):
    def test_three_arcs_with_eight_events_and_two_journals_each(self):
        catalog = _catalog()
        self.assertEqual(catalog["key"], "country_lan")
        self.assertEqual(catalog["runtime_tags"], ["LAN"])
        self.assertEqual(len(catalog["arcs"]), 3)
        seen = set()
        total = 0
        for arc in catalog["arcs"]:
            self.assertIn(arc["slug"], ARCS)
            seen.add(arc["slug"])
            self.assertEqual(arc["era"], "foundation")
            self.assertEqual(arc["depends_on"], [])
            self.assertEqual(len(arc["events"]), 8, arc["slug"])
            self.assertEqual(len(arc["journals"]), 2, arc["slug"])
            self.assertGreaterEqual(len(arc["outcomes"]), 4)
            self.assertGreaterEqual(len(arc["legacy_links"]), 2)
            total += len(arc["events"])
        self.assertEqual(seen, set(ARCS))
        self.assertEqual(total, 24)

    def test_event_numbers_are_in_their_own_partition(self):
        catalog = _catalog()
        for slug, (low, high) in ARCS.items():
            numbers = sorted(_number(e["id"]) for e in _arc(catalog, slug)["events"])
            self.assertEqual(len(set(numbers)), 8, slug)
            self.assertEqual(numbers[0], low, slug)
            self.assertEqual(numbers[-1], high, slug)
            for value in numbers:
                self.assertTrue(low <= value <= high, f"{slug} {value}")
            for event in _arc(catalog, slug)["events"]:
                self.assertTrue(event["id"].startswith("ywc_lan."), event["id"])

    def test_journal_ids_use_the_lan_namespace(self):
        catalog = _catalog()
        for arc in catalog["arcs"]:
            for journal in arc["journals"]:
                self.assertRegex(journal["id"], r"^ywc_je_v03_lan_[a-z0-9_]+$")
                self.assertIsNone(re.search(r"(?m)^\s*(?:complete|fail)\s*=", journal["script"]),
                                  journal["id"])
                self.assertIn("var:ywc_v03_active_arc_count < 3", journal["script"])
                self.assertIn("var:ywc_v03_visible_task_count < 6", journal["script"])
                self.assertIn("ywc_v03_has_capacity = yes", journal["script"])

    def test_every_event_has_a_free_idempotent_exit(self):
        """A player must always be able to walk away without paying: every event carries a
        free `withdraw`, and every non-terminal event also carries a free `defer`."""
        catalog = _catalog()
        for arc in catalog["arcs"]:
            terminal = max(_number(e["id"]) for e in arc["events"])
            for event in arc["events"]:
                keys = [o["key"] for o in event["options"]]
                self.assertEqual(len(keys), len(set(keys)), f"{event['id']} duplicate option keys")
                self.assertIn("withdraw", keys, event["id"])
                if _number(event["id"]) != terminal:
                    self.assertIn("defer", keys, event["id"])
                for option in event["options"]:
                    self.assertIn("base =", option["ai_chance"])
                    self.assertTrue(option["cost_note"]["zh"])
                    self.assertTrue(option["consequence_note"]["en"])
                for option in event["options"]:
                    if option["key"] in ("defer", "withdraw"):
                        self.assertNotIn("add_treasury", option["effect"])
                        self.assertNotIn("_paid", option["effect"])

    def test_major_events_never_double_fire(self):
        catalog = _catalog()
        for arc in catalog["arcs"]:
            for event in arc["events"]:
                self.assertIn("ywc_v03_can_deliver_major = yes", event["trigger"])
                self.assertIn("ywc_v03_mark_major_delivered = yes", event["immediate"])
                self.assertIn("c:LAN ?= this", event["trigger"])


class LanScriptResolutionTest(unittest.TestCase):
    def test_every_called_helper_is_defined(self):
        catalog = _catalog()
        blob = "\n".join(_arc_text(arc) for arc in catalog["arcs"])
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        defined = _definitions()
        for shared in ("ywc_v03_has_capacity", "ywc_v03_can_deliver_major",
                       "ywc_v03_initialize_country", "ywc_v03_mark_major_delivered"):
            self.assertIn(shared, defined, shared)
        called = set(re.findall(r"(?<![a-z0-9_])(ywc_[a-z0-9_]+)\s*=\s*yes", blob))
        missing = sorted(c for c in called if c not in defined)
        self.assertEqual(missing, [])
        local = set(re.findall(r"(?m)^([a-z_0-9]+)\s*=\s*\{", effects + "\n" + triggers))
        for name in sorted(called):
            if not name.startswith("ywc_v03_"):
                self.assertIn(name, local, name)

    def test_every_event_is_dispatched(self):
        catalog = _catalog()
        for arc in catalog["arcs"]:
            script = "\n".join(j["script"] for j in arc["journals"])
            for event in arc["events"]:
                self.assertIn(f"trigger_event = {{ id = {event['id']} }}", script,
                              f"{event['id']} unreachable")

    def test_every_arc_can_close_as_all_three_tiers(self):
        catalog = _catalog()
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for slug in ARCS:
            body = _arc_text(_arc(catalog, slug))
            for tier in ("established", "compromise", "breach"):
                self.assertIn(f"_{tier} = yes", body, f"{slug} {tier}")
            self.assertIn("close_", body)

    def test_each_arc_offers_all_three_routes(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for arc in ("mine", "river", "fund"):
            recorded = set()
            helpers = re.findall(rf"(?m)^(ywc_lan_choose_{arc}_[a-z0-9_]+)\s*=\s*\{{", effects)
            self.assertEqual(len(helpers), 3, f"{arc} {helpers}")
            for helper in helpers:
                body = _helper_body(effects, helper)
                recorded |= set(re.findall(rf"name = ywc_lan_{arc}_route value = (\d)", body))
            self.assertEqual(recorded, {"1", "2", "3"}, f"{arc} routes {recorded}")


class LanPaymentTest(unittest.TestCase):
    def test_fees_are_captured_snapshot_and_actually_charged(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for arc in ("mine", "river", "fund"):
            claim = _helper_body(effects, f"ywc_lan_claim_{arc}_arc")
            self.assertIn("yearly_gross_income", claim)
            self.assertIn("divide = 52", claim)
            self.assertIn("clamp_variable", claim)
            pay = _helper_body(effects, f"ywc_lan_{arc}_pay_fee")
            for token in ("add_treasury", "multiply = -1", "in_default = yes",
                          "declared_bankruptcy"):
                self.assertIn(token, pay, arc)

    def test_no_route_helper_can_charge_twice(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for helper in re.findall(r"(?m)^(ywc_lan_choose_[a-z0-9_]+)\s*=\s*\{", effects):
            body = _helper_body(effects, helper)
            self.assertLessEqual(body.count("add_treasury"), 1, helper)
            if "add_treasury" in body:
                self.assertIn("NOT = { has_variable = ywc_lan_", body, helper)
                self.assertIn("_filing_fee_paid", body, helper)


class LanHonestyTest(unittest.TestCase):
    """The three rules the brief calls out as unbreakable."""

    GRANT_PATTERNS = (
        "add_law", "set_law", "activate_law", "change_law", "add_law_variant",
        "set_state_owner", "add_state", "add_core", "add_claim", "add_homeland",
        "add_building", "build_building", "create_building", "add_technology",
        "set_country_type", "make_independent", "add_resource", "add_mine",
    )

    def test_no_arc_gifts_law_territory_industry_or_independence(self):
        catalog = _catalog()
        blob = "\n".join(_arc_text(arc) for arc in catalog["arcs"])
        blob += EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for pattern in self.GRANT_PATTERNS:
            self.assertIsNone(re.search(rf"(?<![a-z0-9_]){pattern}\s*=", blob),
                              f"found a prohibited grant: {pattern}")

    def test_mines_are_read_never_created(self):
        catalog = _catalog()
        blob = "\n".join(_arc_text(arc) for arc in catalog["arcs"])
        blob += TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        blob += EFFECTS_PATH.read_text(encoding="utf-8-sig")
        self.assertNotRegex(blob, r"(?<![a-z0-9_])(add|create|build)_building\s*=")
        self.assertNotRegex(blob, r"building_(coal|iron|lead|sulfur)_mine")
        self.assertIn("is_building_group = bg_mining", blob)

    def test_no_single_support_score(self):
        catalog = _catalog()
        blob = "\n".join(_arc_text(arc) for arc in catalog["arcs"]).lower()
        for forbidden in ("chinese_support", "hua_support", "support_score", "loyalty_score",
                          "lan_support", "chinese support"):
            self.assertNotIn(forbidden, blob)

    def test_responsibility_always_costs_money_or_unrest(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for helper in re.findall(r"(?m)^(ywc_lan_choose_[a-z0-9_]+)\s*=\s*\{", effects):
            body = _helper_body(effects, helper)
            pays = "add_treasury" in body or "_filing_fee_paid value = 1" in body
            burdens = "add_radicals" in body or "add_modifier" in body
            self.assertTrue(pays or burdens, f"{helper} neither pays nor bears unrest")

    def test_cheap_routes_carry_a_visible_burden(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("ywc_lan_guard_backlash",
                      _helper_body(effects, "ywc_lan_river_hire_guards"))
        self.assertIn("ywc_lan_relief_gap",
                      _helper_body(effects, "ywc_lan_choose_fund_private"))
        modifiers = MODIFIERS_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("country_legitimacy_base_add = -10", modifiers)
        self.assertIn("state_lower_strata_expected_sol_add = 1", modifiers)


class LanObservationTest(unittest.TestCase):
    def test_six_month_observation_can_restart(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for arc in ("mine", "river", "fund"):
            body = _helper_body(effects, f"ywc_lan_{arc}_monthly_review")
            for token in ("months = 6", "six_months_complete", "else = {",
                          f"remove_variable = ywc_lan_{arc}_observation_timer"):
                self.assertIn(token, body, f"{arc} {token}")

    def test_low_tier_outcomes_cannot_jump_to_the_high_tier_result(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for arc, slot in (("mine", "mine_accounts"), ("river", "river_compacts"),
                          ("fund", "work_accident_fund")):
            established = _helper_body(effects, f"ywc_lan_close_{arc}_as_established")
            self.assertIn("_full_ready = yes", established)
            self.assertIn(f"name = ywc_v03_lan_v03_lan_{slot}_outcome value = 1", established)
            compromise = _helper_body(effects, f"ywc_lan_close_{arc}_as_compromise")
            self.assertIn(f"name = ywc_v03_lan_v03_lan_{slot}_outcome value = 2", compromise)
            self.assertNotIn("_full_ready", compromise)


class LanLegacyTest(unittest.TestCase):
    def test_arcs_read_the_old_campaign_variable(self):
        catalog = _catalog()
        for arc in catalog["arcs"]:
            text = _arc_text(arc)
            self.assertIn("ywc_campaign_lan_c1_outcome", text, arc["slug"])
            self.assertIn("ywc_je_flavor_lan_charter_1", text, arc["slug"])
            self.assertIn("ywc_v03_initialized", text, arc["slug"])

    def test_closers_release_the_shared_slots(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for slot in SLOTS.values():
            self.assertIn(f"ywc_v03_lan_v03_lan_{slot}_settled", effects)
            self.assertIn(f"ywc_v03_lan_v03_lan_{slot}_started", effects)
            self.assertIn(f"ywc_v03_lan_v03_lan_{slot}_outcome", effects)
        self.assertIn("name = ywc_v03_active_arc_count add = -1", effects)
        self.assertIn("name = ywc_v03_visible_task_count add = -1", effects)
        self.assertIn("clamp_variable", effects)


if __name__ == "__main__":
    unittest.main()
