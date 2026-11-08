"""LAN foundation gate: 24 events / 6 journals / 3 arcs of 8+2, and the honesty rules that
keep the arc from handing out mines, laws or free legitimacy."""

import json
import copy
import operator
import re
import unittest
from pathlib import Path
from tests.clausewitz_harness import PulseWorld, parse

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "content" / "v03" / "countries" / "lan.json"
EFFECTS_PATH = ROOT / "yongchang_world" / "common" / "scripted_effects" / "ywc_v03_lan_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world" / "common" / "scripted_triggers" / "ywc_v03_lan_triggers.txt"
SHARED_TRIGGERS_PATH = ROOT / "yongchang_world" / "common" / "scripted_triggers" / "ywc_v03_triggers.txt"
SHARED_EFFECTS_PATH = ROOT / "yongchang_world" / "common" / "scripted_effects" / "ywc_v03_effects.txt"
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


def _script_condition(world, block, tag):
    return world.conditions(parse("condition = " + block)[0][2], tag)


class LanRuntimeWorld(PulseWorld):
    """Execute LAN scripts and the shared capacity/cooldown trigger definitions."""
    def __init__(self, effects, triggers, countries):
        super().__init__(effects, countries)
        self.trigger_defs = {key: body for key, _, body in parse(triggers)}

    def execute(self, nodes, tag):
        i = 0
        while i < len(nodes):
            key, _, body = nodes[i]
            if key == "if":
                chosen = False
                branch_start = i
                while i < len(nodes) and (i == branch_start or nodes[i][0] in ("else_if", "else")):
                    branch_key, _, branch = nodes[i]
                    limit = next((v for n, _, v in branch if n == "limit"), [])
                    if not chosen and (branch_key == "else" or self.conditions(limit, tag)):
                        self.execute([n for n in branch if n[0] != "limit"], tag)
                        chosen = True
                    i += 1
                continue
            if key in ("else_if", "else"):
                raise AssertionError("orphan branch in authored LAN script")
            if key == "add_treasury":
                before = self.treasury[tag]
                super().execute([nodes[i]], tag)
                self.countries[tag]["gold_reserves"] = self.countries[tag].get("gold_reserves", 0) + self.treasury[tag] - before
            else:
                super().execute([nodes[i]], tag)
            i += 1

    def condition(self, node, tag):
        key, comparison, value = node
        if key in self.trigger_defs and comparison == "=":
            return self.conditions(self.trigger_defs[key], tag)
        if key == "has_modifier":
            return any(modifier_tag == tag and fields.get("name", fields.get("modifier")) == value
                       for modifier_tag, fields in self.modifiers)
        if key == "any_scope_building":
            buildings = self.countries[tag].get("test_buildings", [])
            fields = {name: child for name, _, child in value}
            building_type = fields.get("is_building_type")
            group = fields.get("is_building_group")
            for building in buildings:
                if building_type and building.get("type") != building_type:
                    continue
                if group and group not in building.get("groups", set()):
                    continue
                matched = True
                for field, operator, expected in value:
                    if field in ("is_building_type", "is_building_group"):
                        continue
                    if field == "level":
                        matched &= float(building.get("level", 0)) >= float(expected)
                    elif field == "occupancy":
                        matched &= float(building.get("occupancy", 0)) >= float(expected)
                    elif field == "building_has_goods_shortage":
                        matched &= bool(building.get("shortage", False)) == (expected == "yes")
                    else:
                        raise AssertionError(f"unprovided LAN building predicate: {field}")
                if matched:
                    return True
            return False
        if key == "has_law_or_variant":
            law_id = value.removeprefix("law_type:")
            return law_id in self.countries[tag].get("test_laws", set())
        return super().condition(node, tag)


class StrictLanRuntimeWorld(LanRuntimeWorld):
    """Fail closed on every LAN condition, including short-circuited children."""

    _numeric_conditions = {
        "net_fixed_income", "bureaucracy", "gold_reserves", "yearly_gross_income",
        "scaled_debt", "in_default", "is_at_war",
    }
    _comparators = {
        "=": operator.eq, ">=": operator.ge, "<=": operator.le,
        ">": operator.gt, "<": operator.lt, "!=": operator.ne,
    }

    def validate_condition(self, node, seen=frozenset()):
        key, comparison, value = node
        if key in {"AND", "OR", "NOT", "NOR"}:
            assert comparison == "=" and isinstance(value, list), node
            for child in value:
                self.validate_condition(child, seen)
        elif key in self.trigger_defs:
            assert comparison == "=" and value == "yes" and key not in seen, node
            for child in self.trigger_defs[key]:
                self.validate_condition(child, seen | {key})
        elif key == "any_scope_building":
            assert comparison == "=" and isinstance(value, list), node
            for field, op, expected in value:
                if field in ("level", "occupancy"):
                    assert op in self._comparators, (field, op, expected)
                elif field in ("is_building_type", "is_building_group", "building_has_goods_shortage"):
                    assert op == "=", (field, op, expected)
                    if field == "building_has_goods_shortage":
                        assert expected in ("yes", "no"), (field, op, expected)
                else:
                    raise AssertionError(("unsupported LAN building condition", field, op, expected))
        elif key in ("has_variable", "has_modifier", "has_law_or_variant", "exists", "always"):
            assert comparison == "=" and isinstance(value, str), node
            if key == "has_variable":
                assert value not in ("yes", "no"), node
            elif key == "always":
                assert value in ("yes", "no"), node
        elif key.startswith("c:"):
            assert comparison == "?=", node
            if isinstance(value, list):
                for child in value:
                    self.validate_condition(child, seen)
            else:
                assert value == "this", node
        elif key.startswith("var:") or key in self._numeric_conditions:
            if key in ("in_default", "is_at_war"):
                assert comparison in ("=", "!=") and value in ("yes", "no"), node
            elif comparison == "?=":
                # PulseWorld already implements safe optional variable equality;
                # retain the stricter numeric/building operator vocabulary.
                assert key.startswith("var:") and isinstance(value, str), node
            else:
                assert comparison in self._comparators, node
            if isinstance(value, list):
                fields = {name: child for name, op, child in value if op == "="}
                assert len(fields) == len(value) and set(fields) <= {"value", "multiply"}, node
                assert "value" in fields, node
        else:
            raise AssertionError(("unsupported LAN condition", node))

    def conditions(self, nodes, tag):
        for node in nodes:
            self.validate_condition(node)
        return super().conditions(nodes, tag)

    def condition(self, node, tag):
        self.validate_condition(node)
        key, comparison, value = node
        if key == "any_scope_building":
            def matches(building):
                for field, op, expected in value:
                    if field == "is_building_type":
                        matched = building.get("type") == expected
                    elif field == "is_building_group":
                        matched = expected in building.get("groups", set())
                    elif field == "building_has_goods_shortage":
                        matched = bool(building.get("shortage", False)) == (expected == "yes")
                    else:
                        matched = self._comparators[op](float(building.get(field, 0)), float(expected))
                    if not matched:
                        return False
                return True
            return any(matches(building) for building in self.countries[tag].get("test_buildings", []))
        return super().condition(node, tag)


def _catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _foundation_catalog():
    catalog = _catalog()
    catalog["arcs"] = [arc for arc in catalog["arcs"] if arc["era"] == "foundation"]
    return catalog


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
        catalog = _foundation_catalog()
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
        catalog = _foundation_catalog()
        for arc in catalog["arcs"]:
            for journal in arc["journals"]:
                self.assertRegex(journal["id"], r"^ywc_je_v03_lan_[a-z0-9_]+$")
                self.assertIsNone(re.search(r"(?m)^\s*(?:complete|fail)\s*=", journal["script"]),
                                  journal["id"])
                if journal is arc["journals"][0]:
                    self.assertIn("var:ywc_v03_active_arc_count < 3", journal["script"])
                    self.assertIn("var:ywc_v03_visible_task_count < 6", journal["script"])
                    self.assertIn("ywc_v03_has_capacity = yes", journal["script"])
                else:
                    self.assertNotIn("ywc_v03_has_capacity = yes", journal["script"])

    def test_every_event_has_a_free_idempotent_exit(self):
        """A player must always be able to walk away without paying: every event carries a
        free `withdraw`, and every non-terminal event also carries a free `defer`."""
        catalog = _foundation_catalog()
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


class LanContextContractRegressionTest(unittest.TestCase):
    def test_context_claims_match_recorded_flags_and_one_time_costs(self):
        events = {event["id"]: event for arc in _foundation_catalog()["arcs"] for event in arc["events"]}
        self.assertEqual(len(events), 24)

        def option(event_id, key):
            return next(item for item in events[event_id]["options"] if item["key"] == key)

        unsupported = (
            "monthly contribution", "monthly contributions", "living standard", "living standards",
            "tax base", "tax-base", "月缴", "生活水平", "税基",
            "lowest administrative cost", "cheapest", "public revenue grows", "revenue gain",
            "unrest falls", "unrest stays", "output is forgone", "output rises", "low public spending",
            "payout gap", "行政成本最低", "成本最低", "公共收入增长", "动荡下降", "产出上升",
            "放弃部分产出", "公共支出低",
        )
        for event in events.values():
            for language in ("en", "zh"):
                self.assertTrue(event["title"].get(language), (event["id"], "title", language))
                self.assertTrue(event["desc"].get(language), (event["id"], "desc", language))
            narrative = " ".join(event.get("title", {}).values()) + " " + " ".join(
                event.get("desc", {}).values()
            )
            self.assertIsNone(re.search(r"\b(?:flags?|markers?|variables?|AST)\b|变量|标记|程序标记", narrative, re.I),
                              f"implementation wording in {event['id']}")
            for claim in unsupported:
                self.assertNotIn(claim, narrative.lower(), f"unsupported narrative in {event['id']}")
            for item in event["options"]:
                for language in ("en", "zh"):
                    for field in ("label", "cost_note", "consequence_note"):
                        self.assertTrue(item[field].get(language), (event["id"], item["key"], field, language))
                text = " ".join(item.get("label", {}).values()) + " " + " ".join(
                    item.get("cost_note", {}).values()
                ) + " " + " ".join(item.get("consequence_note", {}).values())
                self.assertIsNone(re.search(r"\b(?:flags?|markers?|variables?|AST)\b|变量|标记|程序标记", text, re.I),
                                  f"implementation wording in {event['id']}.{item['key']}")
                for claim in unsupported:
                    self.assertNotIn(claim, text.lower(), f"unsupported claim in {event['id']}.{item['key']}")

        self.assertIn("charter for reconciling shipping accounts", events["ywc_lan.1003"]["desc"]["en"])
        self.assertIn("combined or separate books", events["ywc_lan.1004"]["desc"]["en"])
        self.assertIn("third one-time reserve charge", events["ywc_lan.1025"]["desc"]["en"])
        self.assertIn("checks no live diplomatic relation", events["ywc_lan.1012"]["desc"]["en"])
        self.assertNotIn("current revenue", events["ywc_lan.1007"]["desc"]["en"])
        self.assertNotIn("unrest", events["ywc_lan.1016"]["desc"]["en"].lower())
        self.assertNotIn("output", events["ywc_lan.1017"]["desc"]["en"].lower())
        self.assertNotIn("administration costs are read", events["ywc_lan.1025"]["desc"]["en"].lower())
        self.assertNotIn("payout", events["ywc_lan.1027"]["title"]["en"].lower())

        notice = option("ywc_lan.1012", "notify_neighbour")
        notice_text = " ".join(notice["cost_note"].values()) + " " + " ".join(notice["consequence_note"].values())
        self.assertIn("deed was checked", notice_text)
        self.assertIn("does not check diplomatic relations", notice_text)
        self.assertIn("不检查外交关系", notice_text)
        self.assertIn("不代表对方同意", notice_text)
        river_card = events["ywc_lan.1012"]["desc"]
        self.assertIn("checks no live diplomatic relation", river_card["en"])
        self.assertIn("不检查现实外交关系", river_card["zh"])

    def test_strict_fixture_validates_all_children_and_building_comparators(self):
        triggers = (TRIGGERS_PATH.read_text(encoding="utf-8-sig") + "\n"
                    + SHARED_TRIGGERS_PATH.read_text(encoding="utf-8-sig"))
        world = StrictLanRuntimeWorld(EFFECTS_PATH.read_text(encoding="utf-8-sig"), triggers, {"LAN": {
            "present_but_zero": 0,
            "test_buildings": [{"type": "building_government_administration", "groups": set(),
                                "level": 2, "occupancy": 0.75, "shortage": False}],
        }})
        self.assertTrue(world.conditions(parse("condition = { has_variable = present_but_zero }")[0][2], "LAN"))
        below = parse("condition = { any_scope_building = { is_building_type = building_government_administration occupancy < 0.8 } }")[0][2]
        self.assertTrue(world.conditions(below, "LAN"), "the authored < comparator must remain a true less-than check")
        self.assertFalse(world.conditions(parse("condition = { any_scope_building = { is_building_type = building_government_administration occupancy < 0.7 } }")[0][2], "LAN"))
        for block in (
            "{ always = no unknown_lan_condition = yes }",
            "{ OR = { always = no unknown_lan_condition = yes } }",
            "{ OR = { AND = { always = no unknown_lan_condition = yes } always = yes } }",
            "{ has_variable > present_but_zero }",
            "{ ywc_lan_mine_can_pay > yes }",
            "{ any_scope_building = { building_has_goods_shortage > no } }",
        ):
            with self.subTest(block=block), self.assertRaises(AssertionError):
                world.conditions(parse("condition = " + block)[0][2], "LAN")

    def test_optional_queue_equality_keeps_absence_zero_and_later_stage_distinct(self):
        world = StrictLanRuntimeWorld("", "", {"LAN": {}})
        state = world.countries["LAN"]
        queue = "ywc_lan_river_pending_event"
        for present, value, expected in ((False, None, False), (True, 0, False),
                                         (True, 1014, True), (True, 1015, False)):
            with self.subTest(present=present, value=value):
                state.clear()
                if present:
                    state[queue] = value
                self.assertEqual(world.conditions(parse(f"var:{queue} ?= 1014"), "LAN"), expected)
        state.clear()
        self.assertFalse(world.conditions(parse(f"var:{queue} ?= 0"), "LAN"))
        state[queue] = 0
        self.assertTrue(world.conditions(parse(f"var:{queue} ?= 0"), "LAN"))
        for source in ("bureaucracy ?= 0", "any_scope_building = { occupancy ?= 0.8 }"):
            with self.subTest(invalid=source), self.assertRaises(AssertionError):
                world.conditions(parse(source), "LAN")

    def test_opening_paid_options_require_fee_or_receipt_and_keep_free_choices(self):
        expected = {
            ("ywc_lan.1000", "public_audit"): ("ywc_lan_mine", "ywc_lan_mine_fee", 1.0, 1000),
            ("ywc_lan.1000", "shareholder_farm"): ("ywc_lan_mine", "ywc_lan_mine_fee", 0.7, 700),
            ("ywc_lan.1000", "limited_liability"): ("ywc_lan_mine", "ywc_lan_mine_fee", 0.5, 500),
            ("ywc_lan.1010", "compensate"): ("ywc_lan_river", "ywc_lan_river_fee", 1.0, 1000),
            ("ywc_lan.1010", "restrict"): ("ywc_lan_river", "ywc_lan_river_fee", 0.5, 500),
            ("ywc_lan.1010", "guards"): ("ywc_lan_river", "ywc_lan_river_fee", 0.4, 400),
            ("ywc_lan.1020", "mutual_fund"): ("ywc_lan_fund", "ywc_lan_fund_fee", 1.0, 1000),
            ("ywc_lan.1020", "company_insurance"): ("ywc_lan_fund", "ywc_lan_fund_fee", 0.7, 700),
        }
        events = {event["id"]: event for arc in _catalog()["arcs"] for event in arc["events"]}
        triggers = (TRIGGERS_PATH.read_text(encoding="utf-8-sig") + "\n"
                    + SHARED_TRIGGERS_PATH.read_text(encoding="utf-8-sig"))
        for (event_id, key), (prefix, fee, rate, amount) in expected.items():
            item = next(option for option in events[event_id]["options"] if option["key"] == key)
            ast = parse("condition = " + item["trigger"])[0][2]
            gate = next((body for name, _, body in ast if name == "OR"), None)
            self.assertIsNotNone(gate, f"{event_id}.{key} has no paid-or-affordable gate")
            receipt = prefix + "_filing_fee_paid"
            self.assertIn(("has_variable", "=", receipt), gate)
            self.assertIn((prefix + "_can_pay", "=", "yes"), ast)
            affordability = next(node for node in gate if node[0] == "AND") if rate < 1 else None
            if rate < 1:
                self.assertIn(("gold_reserves", ">=", "100"), affordability[2])
                self.assertIn(("gold_reserves", ">=", [("value", "=", "var:" + fee),
                                                        ("multiply", "=", str(rate))]), affordability[2])
            else:
                self.assertIn(("gold_reserves", ">=", "var:" + fee), gate)

            # Exercise every actual option gate at fee-1, exact fee and default.
            for cash, in_default, legal in (
                (amount - 1, False, False),
                (amount, False, True),
                (amount, True, False),
            ):
                country = {
                    fee: 1000,
                    "gold_reserves": cash,
                    "in_default": in_default,
                    "test_buildings": LanLifecycleRegressionTest._buildings(),
                    "test_laws": {"law_poor_laws"},
                }
                world = StrictLanRuntimeWorld(EFFECTS_PATH.read_text(encoding="utf-8-sig"), triggers, {"LAN": country})
                with self.subTest(event=event_id, option=key, cash=cash, default=in_default):
                    self.assertEqual(world.conditions(ast, "LAN"), legal)
            if rate < 1:
                for cash, legal in ((99, False), (100, True)):
                    country = {
                        fee: 100,
                        "gold_reserves": cash,
                        "test_buildings": LanLifecycleRegressionTest._buildings(),
                        "test_laws": {"law_poor_laws"},
                    }
                    world = StrictLanRuntimeWorld(EFFECTS_PATH.read_text(encoding="utf-8-sig"), triggers, {"LAN": country})
                    with self.subTest(event=event_id, option=key, base_fee=100, cash=cash):
                        self.assertEqual(world.conditions(ast, "LAN"), legal)

        for event_id, free_keys in {
            "ywc_lan.1000": ("defer", "withdraw"),
            "ywc_lan.1010": ("defer", "withdraw"),
            "ywc_lan.1020": ("private_relief", "defer", "withdraw"),
        }.items():
            for key in free_keys:
                item = next(option for option in events[event_id]["options"] if option["key"] == key)
                self.assertIn("always = yes", item.get("trigger", ""))
                self.assertNotIn("gold_reserves", item.get("trigger", ""))

    def test_all_eight_paid_opening_effects_use_real_entry_and_payment_receipt(self):
        cases = (
            ("v03_lan_mine_accounts", "ywc_lan.1000", "public_audit", "ywc_lan_mine", "ywc_lan_mine_fee", "ywc_lan_mine_route", 1, 1000),
            ("v03_lan_mine_accounts", "ywc_lan.1000", "shareholder_farm", "ywc_lan_mine", "ywc_lan_mine_fee", "ywc_lan_mine_route", 2, 700),
            ("v03_lan_mine_accounts", "ywc_lan.1000", "limited_liability", "ywc_lan_mine", "ywc_lan_mine_fee", "ywc_lan_mine_route", 3, 500),
            ("v03_lan_river_compacts", "ywc_lan.1010", "compensate", "ywc_lan_river", "ywc_lan_river_fee", "ywc_lan_river_route", 1, 1000),
            ("v03_lan_river_compacts", "ywc_lan.1010", "restrict", "ywc_lan_river", "ywc_lan_river_fee", "ywc_lan_river_route", 2, 500),
            ("v03_lan_river_compacts", "ywc_lan.1010", "guards", "ywc_lan_river", "ywc_lan_river_fee", "ywc_lan_river_route", 3, 400),
            ("v03_lan_work_accident_fund", "ywc_lan.1020", "mutual_fund", "ywc_lan_fund", "ywc_lan_fund_fee", "ywc_lan_fund_route", 1, 1000),
            ("v03_lan_work_accident_fund", "ywc_lan.1020", "company_insurance", "ywc_lan_fund", "ywc_lan_fund_fee", "ywc_lan_fund_route", 2, 700),
        )
        lifecycle = LanLifecycleRegressionTest()
        lifecycle.catalog = _catalog()
        for slug, event_id, key, prefix, fee_var, route_var, route, amount in cases:
            arc = _arc(lifecycle.catalog, slug)
            world = lifecycle._world(amount, strict=True)
            world.active_journals = {"LAN": None}
            world.journal_states = {"LAN": {}}
            world.journal_add_cursor = {"LAN": 0}
            country = world.countries["LAN"]
            country["test_laws"] = {"law_poor_laws", "law_commercialized_agriculture"}
            lifecycle._admit_entry(world, arc["journals"][0])
            self.assertEqual(country[fee_var], 1000)
            self.assertEqual(lifecycle._dispatch_queued_event(world, arc), _number(event_id))
            lifecycle._take_event_option(world, arc, _number(event_id), key)
            receipt = prefix + "_filing_fee_paid"
            opening = next(e for e in arc["events"] if e["id"] == event_id)
            option = next(o for o in opening["options"] if o["key"] == key)
            trigger = parse("condition = " + option["trigger"])[0][2]
            with self.subTest(event=event_id, option=key):
                self.assertEqual(country[route_var], route)
                self.assertEqual(country[receipt], 1)
                self.assertEqual(country["gold_reserves"], 0)
                self.assertEqual(world.treasury["LAN"], -amount)
                self.assertTrue(world.conditions(trigger, "LAN"), "earned receipt keeps the opening option legal at cash zero")
                before_replay = copy.deepcopy(country)
                world.execute(parse("effect = " + option["effect"])[0][2], "LAN")
                self.assertEqual(country, before_replay, "the complete option effect cannot charge twice or alter the chosen route")
                self.assertEqual(world.treasury["LAN"], -amount)


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


class LanLifecycleRegressionTest(unittest.TestCase):
    def setUp(self):
        self.catalog = _catalog()
        self.effects = EFFECTS_PATH.read_text(encoding="utf-8-sig") + "\n" + SHARED_EFFECTS_PATH.read_text(encoding="utf-8-sig")
        triggers = (TRIGGERS_PATH.read_text(encoding="utf-8-sig")
                    + "\n" + SHARED_TRIGGERS_PATH.read_text(encoding="utf-8-sig"))
        self.world = LanRuntimeWorld(self.effects, triggers, {"LAN": {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0,
            "ywc_v03_visible_task_count": 0,
            "ywc_campaign_lan_c1_outcome": 3,
            "ywc_je_flavor_lan_charter_1_resolved": 1,
            "yearly_gross_income": 52000,
            "gold_reserves": 0,
            "test_buildings": self._buildings(),
        }})

    @staticmethod
    def _buildings(office=True, mine=True, port=True):
        buildings = []
        if office:
            buildings.append({"type": "building_government_administration", "groups": set(),
                             "level": 2, "occupancy": 0.9, "shortage": False})
        if mine:
            buildings.append({"type": "building_mine", "groups": {"bg_mining"},
                             "level": 3, "occupancy": 0.75, "shortage": False})
        if port:
            buildings.append({"type": "building_port", "groups": set(),
                             "level": 1, "occupancy": 0.7, "shortage": False})
        return buildings

    @staticmethod
    def _set_building_fact(country, building_type, **changes):
        building = next(b for b in country["test_buildings"] if b["type"] == building_type)
        building.update(changes)

    def _world(self, cash=0, strict=False):
        triggers = (TRIGGERS_PATH.read_text(encoding="utf-8-sig")
                    + "\n" + SHARED_TRIGGERS_PATH.read_text(encoding="utf-8-sig"))
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig") + "\n" + SHARED_EFFECTS_PATH.read_text(encoding="utf-8-sig")
        world_class = StrictLanRuntimeWorld if strict else LanRuntimeWorld
        return world_class(effects, triggers, {"LAN": {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "ywc_campaign_lan_c1_outcome": 3,
            "ywc_je_flavor_lan_charter_1_resolved": 1,
            "yearly_gross_income": 52000, "gold_reserves": cash,
            "test_buildings": self._buildings(),
        }})

    def _activate_arc(self, world, slug):
        # Low-level unit fixtures only; full-route evidence uses _admit_entry below.
        first = _arc(self.catalog, slug)["journals"][0]
        immediate = next(value for key, _, value in parse(first["script"]) if key == "immediate")
        world.execute(immediate, "LAN")

    def _journal(self, slug, suffix):
        return next(j for j in _arc(self.catalog, slug)["journals"] if j["id"].endswith(suffix))

    def _journal_block(self, journal, name):
        if name in {"goal", "exit_conditions"}:
            return parse("condition = " + journal[name])[0][2]
        return next(value for key, _, value in parse(journal["script"]) if key == name)

    def _possible(self, journal):
        return self.world.conditions(self._journal_block(journal, "possible"), "LAN")

    def _shown(self, journal, world):
        return world.conditions(self._journal_block(journal, "is_shown_when_inactive"), "LAN")

    def _admit_entry(self, world, journal):
        self.assertIsNone(world.active_journals.get("LAN"), "only one LAN entry may run in this linear arc")
        self.assertTrue(self._shown(journal, world), f"not displayed while inactive: {journal['id']}")
        self.assertTrue(world.conditions(self._journal_block(journal, "possible"), "LAN"),
                        f"entry is not actually possible: {journal['id']}")
        world.execute(self._journal_block(journal, "immediate"), "LAN")
        world.active_journals["LAN"] = journal["id"]
        world.journal_states["LAN"][journal["id"]] = "active"

    def _refresh_journal_lifecycle(self, world, arc):
        tag = "LAN"
        active_id = world.active_journals.get(tag)
        if active_id:
            active = next(j for j in arc["journals"] if j["id"] == active_id)
            goal = world.conditions(self._journal_block(active, "goal"), tag)
            failed = world.conditions(self._journal_block(active, "exit_conditions"), tag)
            self.assertFalse(goal and failed, f"goal and fail cannot both complete {active_id}")
            if failed:
                world.journal_states[tag][active_id] = "failed"
                world.active_journals[tag] = None
            elif goal:
                world.journal_states[tag][active_id] = "completed"
                world.active_journals[tag] = None
        while world.journal_add_cursor[tag] < len(world.journals):
            entry_tag, body = world.journals[world.journal_add_cursor[tag]]
            world.journal_add_cursor[tag] += 1
            if entry_tag != tag:
                continue
            fields = {name: value for name, _, value in body}
            entry_id = fields.get("type")
            journal = next((j for j in arc["journals"] if j["id"] == entry_id), None)
            self.assertIsNotNone(journal, f"add_journal_entry referenced unknown entry {entry_id}")
            self.assertIsNone(world.active_journals.get(tag), "handoff tried to activate before prior JE settled")
            self._admit_entry(world, journal)

    def _take_event_option(self, world, arc, event_number, key):
        active_id = world.active_journals.get("LAN")
        self.assertIsNotNone(active_id, "events require an active, nonterminal journal entry")
        active = next(j for j in arc["journals"] if j["id"] == active_id)
        self.assertEqual(world.journal_states["LAN"][active_id], "active")
        self.assertFalse(world.conditions(self._journal_block(active, "goal"), "LAN"), active_id)
        self.assertFalse(world.conditions(self._journal_block(active, "exit_conditions"), "LAN"), active_id)
        event = next(e for e in arc["events"] if _number(e["id"]) == event_number)
        self.assertTrue(_script_condition(world, event["trigger"], "LAN"), event["id"])
        world.execute(parse("immediate = " + event["immediate"])[0][2], "LAN")
        option = next(o for o in event["options"] if o["key"] == key)
        self.assertTrue(_script_condition(world, option.get("trigger", "{ always = yes }"), "LAN"), (event["id"], key))
        world.execute(parse("effect = " + option["effect"])[0][2], "LAN")
        self._refresh_journal_lifecycle(world, arc)

    def _pulse_active(self, world, arc):
        active_id = world.active_journals.get("LAN")
        self.assertIsNotNone(active_id, "cannot pulse a journal after completion/failure")
        active = next(j for j in arc["journals"] if j["id"] == active_id)
        self.assertEqual(world.journal_states["LAN"][active_id], "active")
        self.assertFalse(world.conditions(self._journal_block(active, "goal"), "LAN"),
                         f"terminal journal received a later pulse: {active_id}")
        self.assertFalse(world.conditions(self._journal_block(active, "exit_conditions"), "LAN"),
                         f"failed journal received a later pulse: {active_id}")
        world.advance_months(1)
        pulse = self._journal_block(active, "on_monthly_pulse")
        world.execute(next(value for key, _, value in pulse if key == "effect"), "LAN")
        self._refresh_journal_lifecycle(world, arc)
        if world.events:
            tag, event_id = world.events.pop(0)
            self.assertEqual(tag, "LAN")
            self.assertTrue(world.active_journals.get("LAN"), "event emitted without a live JE")
            return int(event_id.rsplit(".", 1)[1])
        return None

    def _dispatch_queued_event(self, world, arc, max_months=15):
        for _ in range(max_months):
            event_number = self._pulse_active(world, arc)
            if event_number is not None:
                return event_number
        self.fail(("production JE pulses did not dispatch a queued event", world.countries["LAN"]))

    def _elapse_blocked_months(self, world, arc, short, months, review_event, notice_event):
        vars = world.countries["LAN"]
        twelve_key = f"reconsider_{short}_12"
        for _ in range(months):
            event_number = self._pulse_active(world, arc)
            if event_number is None:
                continue
            self.assertIn(event_number, (review_event, notice_event))
            notice = vars.get(f"ywc_lan_{short}_notice_current")
            if notice == 12:
                if months == 12:
                    return
                pending_before_ack = vars.get(f"ywc_lan_{short}_pending_event")
                self.assertIsNotNone(pending_before_ack, "the normal review must remain queued behind notice 12")
                self._take_event_option(world, arc, review_event, twelve_key)
                self.assertEqual(vars.get(f"ywc_lan_{short}_pending_event"), pending_before_ack,
                                 "safe 12-month acknowledgement must preserve the ordinary event")
            elif notice == 36:
                self.assertEqual(event_number, notice_event)
                self.assertGreaterEqual(vars.get(f"ywc_lan_{short}_blocked_months", 0), 36)
                self.assertEqual(vars.get(f"ywc_lan_{short}_notice12_sent"), 1)
                self.assertEqual(vars.get(f"ywc_lan_{short}_notice36_sent"), 1)
                self.assertIsNotNone(vars.get(f"ywc_lan_{short}_pending_event"))
                return
            else:
                self._take_event_option(world, arc, review_event, "defer")
        self.fail(f"notice {notice_event} was not delivered after {months} real pulses")

    def _assert_terminal_history(self, world, arc, short, outcome):
        vars = world.countries["LAN"]
        expected_status = "failed" if outcome == 0 else "completed"
        self.assertEqual(vars.get(f"ywc_lan_{short}_settled"), 1)
        self.assertEqual(vars.get("ywc_v03_active_arc_count"), 0)
        self.assertEqual(vars.get("ywc_v03_visible_task_count"), 0)
        self.assertEqual(vars.get("ywc_campaign_lan_c1_outcome"), 3)
        owner = f"ywc_v03_lan_v03_lan_{arc['slug'].removeprefix('v03_lan_')}"
        self.assertEqual(vars.get(owner + "_outcome"), outcome)
        self.assertEqual(world.active_journals.get("LAN"), None)
        self.assertEqual(world.journal_states["LAN"], {j["id"]: ("failed" if outcome == 0 and i == 1 else "completed")
                                                       for i, j in enumerate(arc["journals"])})
        for journal in arc["journals"]:
            self.assertFalse(self._shown(journal, world), f"completed entry was shown again: {journal['id']}")
            self.assertFalse(world.conditions(self._journal_block(journal, "possible"), "LAN"),
                             f"completed entry was still possible: {journal['id']}")

    def _run_route(self, slug, picks, cash=100000, watch=True):
        arc = _arc(self.catalog, slug)
        world = self._world(cash)
        vars = world.countries["LAN"]
        vars.update({"test_buildings": self._buildings(),
                     "test_laws": {"law_commercialized_agriculture", "law_poor_laws"}})
        world.active_journals = {"LAN": None}
        world.journal_states = {"LAN": {j["id"]: "inactive" for j in arc["journals"]}}
        world.journal_add_cursor = {"LAN": 0}
        first, second = arc["journals"]
        self._admit_entry(world, first)
        short = {"v03_lan_mine_accounts": "mine", "v03_lan_river_compacts": "river",
                 "v03_lan_work_accident_fund": "fund"}[slug]
        for event_id, key in picks:
            selected = self._dispatch_queued_event(world, arc)
            self.assertEqual(selected, event_id, vars)
            self._take_event_option(world, arc, event_id, key)
            if not vars.get(f"ywc_lan_{short}_implementation_complete"):
                for premature in (f"ywc_lan_{short}_blocked_months", f"ywc_lan_{short}_notice_event",
                                  f"ywc_lan_{short}_notice_current", f"ywc_lan_{short}_notice12_sent",
                                  f"ywc_lan_{short}_notice36_sent"):
                    self.assertNotIn(premature, vars, f"normal route progress must not accrue blocked time: {premature}")
        self.assertEqual(world.active_journals.get("LAN"), second["id"],
                         "only the authored add_journal_entry handoff may activate the continuation")
        self.assertEqual(world.journal_states["LAN"][first["id"]], "completed")
        if not watch:
            return world, arc, second
        review_event = {"v03_lan_mine_accounts": 1006,
                        "v03_lan_river_compacts": 1016,
                        "v03_lan_work_accident_fund": 1026}[slug]
        dispatch_count = 0
        while True:
            self.assertEqual(self._dispatch_queued_event(world, arc), review_event)
            dispatch_count += 1
            if vars.get({"v03_lan_mine_accounts": "ywc_lan_mine_six_months_complete",
                         "v03_lan_river_compacts": "ywc_lan_river_six_months_complete",
                         "v03_lan_work_accident_fund": "ywc_lan_fund_six_months_complete"}[slug]):
                break
            self._take_event_option(world, arc, review_event, "defer")
            self.assertLessEqual(dispatch_count, 4, "deferred watch should reach six observed months")
        self._take_event_option(world, arc, review_event, "begin_review")
        terminal_event = self._dispatch_queued_event(world, arc)
        self.assertEqual(terminal_event, review_event + 1)
        return world, arc, terminal_event

    def test_real_shareholder_farm_route_reaches_compromise_terminal(self):
        world, arc, terminal_event = self._run_route("v03_lan_mine_accounts", [
            (1000, "shareholder_farm"), (1001, "staff_audit"),
            (1002, "dividend_first"), (1003, "internal_only"),
            (1004, "separate_books"), (1005, "cap_public_claim")])
        self.assertEqual(terminal_event, 1007)
        self._take_event_option(world, arc, terminal_event, "settle_compromise")
        self.assertTrue(world.countries["LAN"].get("ywc_lan_mine_compromise"))
        self._assert_terminal_history(world, arc, "mine", 2)

    def test_real_public_audit_full_mine_chain_without_port_laws_or_foreign_countries(self):
        arc = _arc(self.catalog, "v03_lan_mine_accounts")
        world = self._world(cash=2000, strict=True)
        country = world.countries["LAN"]
        country["test_laws"] = set()
        country["test_buildings"] = self._buildings(port=False)
        self.assertEqual(set(world.countries), {"LAN"})
        self.assertFalse(any(b["type"] == "building_port" for b in country["test_buildings"]))
        self.assertEqual(country["test_laws"], set())
        self.assertNotIn("ywc_lan_mine_route", country)
        self.assertNotIn("ywc_lan_mine_filing_fee_paid", country)
        self.assertNotIn("ywc_lan_mine_six_months_complete", country)
        self.assertNotIn("ywc_v03_lan_v03_lan_mine_accounts_outcome", country)

        world.active_journals = {"LAN": None}
        world.journal_states = {"LAN": {j["id"]: "inactive" for j in arc["journals"]}}
        world.journal_add_cursor = {"LAN": 0}
        first, second = arc["journals"]
        self.assertTrue(self._shown(first, world))
        self.assertTrue(world.conditions(self._journal_block(first, "possible"), "LAN"))
        self._admit_entry(world, first)

        choices = [(1000, "public_audit"), (1001, "staff_audit"),
                   (1002, "public_share_first"), (1003, "use_shipping"),
                   (1004, "merge_customs")]
        for event_id, key in choices:
            self.assertEqual(self._dispatch_queued_event(world, arc), event_id)
            reserves_before = world.countries["LAN"]["gold_reserves"]
            self._take_event_option(world, arc, event_id, key)
            if event_id == 1000:
                self.assertEqual(reserves_before, 2000)
                self.assertEqual(country["gold_reserves"], 1000)
                self.assertEqual(country["ywc_lan_mine_filing_fee_paid"], 1)
                self.assertEqual(world.treasury["LAN"], -1000)
        self.assertEqual(world.active_journals["LAN"], second["id"])
        self.assertEqual(self._dispatch_queued_event(world, arc), 1005)
        self._take_event_option(world, arc, 1005, "fund_audit")
        self.assertEqual(country["ywc_lan_mine_reserve_paid"], 1)
        self.assertEqual(country["gold_reserves"], 0)
        self.assertEqual(world.treasury["LAN"], -2000)

        for _ in range(8):
            self.assertEqual(self._dispatch_queued_event(world, arc), 1006)
            if country.get("ywc_lan_mine_six_months_complete"):
                break
            self._take_event_option(world, arc, 1006, "defer")
        self.assertTrue(country.get("ywc_lan_mine_six_months_complete"))
        self._take_event_option(world, arc, 1006, "begin_review")
        self.assertEqual(self._dispatch_queued_event(world, arc), 1007)
        self.assertTrue(_script_condition(world, next(o for o in arc["events"][-1]["options"]
                                                      if o["key"] == "settle_full")["trigger"], "LAN"))
        self._take_event_option(world, arc, 1007, "settle_full")
        self.assertTrue(country.get("ywc_lan_mine_established"))
        self._assert_terminal_history(world, arc, "mine", 1)

    def test_real_mine_public_route_reaches_full_terminal(self):
        world, arc, terminal_event = self._run_route("v03_lan_mine_accounts", [
            (1000, "public_audit"), (1001, "staff_audit"), (1002, "public_share_first"),
            (1003, "use_shipping"), (1004, "merge_customs"), (1005, "fund_audit")])
        self.assertEqual(terminal_event, 1007)
        self._take_event_option(world, arc, terminal_event, "settle_full")
        self.assertTrue(world.countries["LAN"].get("ywc_lan_mine_established"))
        self._assert_terminal_history(world, arc, "mine", 1)

    def test_real_river_guards_route_reaches_compromise_terminal(self):
        world, arc, terminal_event = self._run_route("v03_lan_river_compacts", [
            (1010, "guards"), (1011, "deed_review"), (1012, "notify_neighbour"),
            (1013, "restrict_blocks"), (1014, "hire_guards"), (1015, "hold_scale")])
        self.assertEqual(terminal_event, 1017)
        self._take_event_option(world, arc, terminal_event, "settle_compromise")
        self.assertTrue(world.countries["LAN"].get("ywc_lan_river_compromise"))
        self._assert_terminal_history(world, arc, "river", 2)

    def test_real_river_co_management_route_reaches_full_terminal(self):
        world, arc, terminal_event = self._run_route("v03_lan_river_compacts", [
            (1010, "compensate"), (1011, "deed_review"), (1012, "notify_neighbour"),
            (1013, "fund_board"), (1014, "keep_restricted"), (1015, "expand_blocks")])
        vars = world.countries["LAN"]
        self.assertEqual(terminal_event, 1017)
        self._take_event_option(world, arc, terminal_event, "settle_full")
        self.assertEqual(world.treasury["LAN"], -2000)
        self.assertTrue(vars.get("ywc_lan_river_board_chosen"))
        self.assertTrue(vars.get("ywc_lan_river_board_funded"))
        self.assertTrue(vars.get("ywc_lan_river_established"))
        self._assert_terminal_history(world, arc, "river", 1)

    def test_real_loss_restarts_a_fresh_six_month_observation(self):
        world, arc, second = self._run_route("v03_lan_mine_accounts", [
            (1000, "public_audit"), (1001, "staff_audit"), (1002, "public_share_first"),
            (1003, "use_shipping"), (1004, "merge_customs"), (1005, "fund_audit")], watch=False)
        vars = world.countries["LAN"]
        event_number = self._dispatch_queued_event(world, arc)
        self.assertEqual(event_number, 1006)
        self._take_event_option(world, arc, 1006, "defer")
        self.assertIn("ywc_lan_mine_observation_timer", vars)
        for _ in range(3):
            event_number = self._pulse_active(world, arc)
            if event_number is not None:
                self.assertEqual(event_number, 1006)
                self._take_event_option(world, arc, 1006, "defer")
        self._set_building_fact(vars, "building_mine", occupancy=0.2, shortage=True)
        event_number = self._pulse_active(world, arc)
        if event_number is not None:
            self.assertEqual(event_number, 1006)
            self._take_event_option(world, arc, 1006, "defer")
        for stale in ("ywc_lan_mine_observation_timer", "ywc_lan_mine_observation_started",
                      "ywc_lan_mine_six_months_complete"):
            self.assertNotIn(stale, vars)
        self._set_building_fact(vars, "building_mine", occupancy=0.75, shortage=False)
        event_number = self._pulse_active(world, arc)
        if event_number is not None:
            self.assertEqual(event_number, 1006)
            self._take_event_option(world, arc, 1006, "defer")
        self.assertEqual(world.months_until_expiry["LAN"]["ywc_lan_mine_observation_timer"], 6)
        for _ in range(5):
            event_number = self._pulse_active(world, arc)
            if event_number is not None:
                self.assertEqual(event_number, 1006)
                self._take_event_option(world, arc, 1006, "defer")
        self.assertNotIn("ywc_lan_mine_six_months_complete", vars)
        event_number = self._pulse_active(world, arc)
        if event_number is not None:
            self.assertEqual(event_number, 1006)
            self._take_event_option(world, arc, 1006, "defer")
        self.assertTrue(vars.get("ywc_lan_mine_six_months_complete"))
        # The matured observation makes the next real delivery actionable.
        for _ in range(4):
            event_number = self._pulse_active(world, arc)
            if event_number is not None:
                self.assertEqual(event_number, 1006)
                self._take_event_option(world, arc, 1006, "begin_review")
                break
        else:
            self.fail("mature observation did not deliver a real review event")
        self.assertEqual(self._dispatch_queued_event(world, arc), 1007)
        self._take_event_option(world, arc, 1007, "settle_full")
        self._assert_terminal_history(world, arc, "mine", 1)

    def test_real_recovery_clears_notice_epoch_and_a_later_loss_restarts_it(self):
        world, arc, _ = self._run_route("v03_lan_mine_accounts", [
            (1000, "public_audit"), (1001, "staff_audit"), (1002, "public_share_first"),
            (1003, "use_shipping"), (1004, "merge_customs"), (1005, "fund_audit")], watch=False)
        vars = world.countries["LAN"]
        self._set_building_fact(vars, "building_mine", occupancy=0.2, shortage=True)
        self._elapse_blocked_months(world, arc, "mine", 12, 1006, 1006)
        self.assertEqual(vars.get("ywc_lan_mine_notice_current"), 12)
        self.assertEqual(vars.get("ywc_lan_mine_notice12_sent"), 1)
        self._take_event_option(world, arc, 1006, "reconsider_mine_12")
        self._set_building_fact(vars, "building_mine", occupancy=0.75, shortage=False)
        event_number = self._pulse_active(world, arc)
        if event_number is not None:
            self.assertEqual(event_number, 1006)
            self._take_event_option(world, arc, 1006, "defer")
        for stale in ("ywc_lan_mine_blocked_months", "ywc_lan_mine_notice_event",
                      "ywc_lan_mine_notice12_sent", "ywc_lan_mine_notice36_sent",
                      "ywc_lan_mine_notice_current", "ywc_lan_mine_six_months_complete"):
            self.assertNotIn(stale, vars, stale)
        self.assertIn("ywc_lan_mine_observation_timer", vars)
        self._set_building_fact(vars, "building_mine", occupancy=0.2, shortage=True)
        self._pulse_active(world, arc)
        self.assertEqual(vars.get("ywc_lan_mine_blocked_months"), 1)
        self.assertNotIn("ywc_lan_mine_notice12_sent", vars)
        for _ in range(10):
            event_number = self._pulse_active(world, arc)
            if event_number is not None:
                self.assertEqual(event_number, 1006)
                self._take_event_option(world, arc, 1006, "defer")
        self.assertNotIn("ywc_lan_mine_notice_current", vars)
        event_number = self._dispatch_queued_event(world, arc)
        self.assertEqual(event_number, 1006)
        self.assertEqual(vars.get("ywc_lan_mine_notice_current"), 12)

    def test_review_defer_atomically_invalidates_mature_observation_when_target_is_lost(self):
        world, arc, _ = self._run_route("v03_lan_mine_accounts", [
            (1000, "public_audit"), (1001, "staff_audit"), (1002, "public_share_first"),
            (1003, "use_shipping"), (1004, "merge_customs"), (1005, "fund_audit")], watch=False)
        vars = world.countries["LAN"]
        for _ in range(4):
            self.assertEqual(self._dispatch_queued_event(world, arc), 1006)
            if vars.get("ywc_lan_mine_six_months_complete"):
                break
            self._take_event_option(world, arc, 1006, "defer")
        self.assertTrue(vars.get("ywc_lan_mine_six_months_complete"))
        self._set_building_fact(vars, "building_mine", occupancy=0.2, shortage=True)
        self._take_event_option(world, arc, 1006, "defer")
        for stale in ("ywc_lan_mine_observation_timer", "ywc_lan_mine_observation_started",
                      "ywc_lan_mine_six_months_complete"):
            self.assertNotIn(stale, vars, stale)
        self._set_building_fact(vars, "building_mine", occupancy=0.75, shortage=False)
        self._pulse_active(world, arc)
        self.assertIn("ywc_lan_mine_observation_timer", vars)
        self.assertNotIn("ywc_lan_mine_six_months_complete", vars)

    def test_real_36_month_withdrawal_closes_the_active_journal_once(self):
        world, arc, _ = self._run_route("v03_lan_mine_accounts", [
            (1000, "public_audit"), (1001, "staff_audit"), (1002, "public_share_first"),
            (1003, "use_shipping"), (1004, "merge_customs"), (1005, "fund_audit")], watch=False)
        vars = world.countries["LAN"]
        self._set_building_fact(vars, "building_mine", occupancy=0.2, shortage=True)
        self._elapse_blocked_months(world, arc, "mine", 36, 1006, 1007)
        self.assertEqual(vars.get("ywc_lan_mine_notice_current"), 36)
        self._take_event_option(world, arc, 1007, "withdraw_mine_36")
        self.assertEqual(vars.get("ywc_lan_mine_breach"), 1)
        self._assert_terminal_history(world, arc, "mine", 0)

    def test_real_paid_early_defer_reaches_same_epoch_notices_in_all_three_arcs(self):
        cases = (
            ("v03_lan_mine_accounts", 1000, "public_audit", 1001, 1006, 1007, "mine"),
            ("v03_lan_river_compacts", 1010, "compensate", 1011, 1016, 1017, "river"),
            ("v03_lan_work_accident_fund", 1020, "mutual_fund", 1021, 1026, 1027, "fund"),
        )
        for slug, first_event, paid_choice, deferred_event, notice12, notice36, short in cases:
            with self.subTest(arc=slug):
                world = self._world(1000)
                vars = world.countries["LAN"]
                vars.update({"test_laws": {"law_commercialized_agriculture", "law_poor_laws"}})
                arc = _arc(self.catalog, slug)
                world.active_journals = {"LAN": None}
                world.journal_states = {"LAN": {j["id"]: "inactive" for j in arc["journals"]}}
                world.journal_add_cursor = {"LAN": 0}
                self._admit_entry(world, arc["journals"][0])
                self.assertEqual(self._dispatch_queued_event(world, arc), first_event)
                self._take_event_option(world, arc, first_event, paid_choice)
                self.assertEqual(world.treasury["LAN"], -1000)
                self.assertEqual(vars.get(f"ywc_lan_{short}_filing_fee_paid"), 1)
                self.assertNotIn(f"ywc_lan_{short}_implementation_complete", vars)
                vars["in_default"] = True
                safe_ack = f"reconsider_{short}_12"
                notice_seen = []
                for month in range(1, 41):
                    event_number = self._pulse_active(world, arc)
                    if event_number is None:
                        continue
                    if event_number == notice12 and vars.get(f"ywc_lan_{short}_notice_current") == 12:
                        notice_seen.append(12)
                        self._take_event_option(world, arc, notice12, safe_ack)
                        self.assertEqual(vars.get(f"ywc_lan_{short}_blocked_months"), 12)
                        self.assertEqual(vars.get(f"ywc_lan_{short}_notice12_sent"), 1)
                        self.assertEqual(vars.get(f"ywc_lan_{short}_pending_event"), deferred_event)
                    elif event_number == notice36 and vars.get(f"ywc_lan_{short}_notice_current") == 36:
                        notice_seen.append(36)
                        self.assertEqual(vars.get(f"ywc_lan_{short}_blocked_months"), 36)
                        self.assertEqual(vars.get(f"ywc_lan_{short}_notice12_sent"), 1)
                        self.assertEqual(vars.get(f"ywc_lan_{short}_notice36_sent"), 1)
                        self.assertEqual(vars.get(f"ywc_lan_{short}_pending_event"), deferred_event)
                        break
                    else:
                        self.assertEqual(event_number, deferred_event)
                        self._take_event_option(world, arc, deferred_event, "defer")
                self.assertEqual(notice_seen, [12, 36])
                vars["in_default"] = False
                event_number = self._pulse_active(world, arc)
                if event_number is not None:
                    self.assertEqual(event_number, deferred_event)
                    self._take_event_option(world, arc, deferred_event, "defer")
                for stale in (f"ywc_lan_{short}_blocked_months", f"ywc_lan_{short}_notice_event",
                              f"ywc_lan_{short}_notice12_sent", f"ywc_lan_{short}_notice36_sent",
                              f"ywc_lan_{short}_notice_current"):
                    self.assertNotIn(stale, vars, stale)
                vars["in_default"] = True
                self._pulse_active(world, arc)
                self.assertEqual(vars.get(f"ywc_lan_{short}_blocked_months"), 1)
                self.assertNotIn(f"ywc_lan_{short}_notice12_sent", vars)
                for _ in range(10):
                    event_number = self._pulse_active(world, arc)
                    if event_number is not None:
                        self.assertEqual(event_number, deferred_event)
                        self._take_event_option(world, arc, deferred_event, "defer")
                self.assertEqual(self._dispatch_queued_event(world, arc), notice12)
                self.assertEqual(vars.get(f"ywc_lan_{short}_notice_current"), 12)
                self.assertEqual(vars.get(f"ywc_lan_{short}_notice12_sent"), 1)

    def test_real_36_month_notice_dispatches_in_all_three_owned_queues(self):
        paths = {
            "v03_lan_mine_accounts": ([(1000, "public_audit"), (1001, "staff_audit"),
                (1002, "public_share_first"), (1003, "use_shipping"), (1004, "merge_customs"),
                (1005, "fund_audit")], "mine", 1007, "narrow_mine_36"),
            "v03_lan_river_compacts": ([(1010, "guards"), (1011, "deed_review"),
                (1012, "notify_neighbour"), (1013, "restrict_blocks"),
                (1014, "hire_guards"), (1015, "hold_scale")], "river", 1017, "narrow_river_36"),
            "v03_lan_work_accident_fund": ([(1020, "mutual_fund"), (1021, "enrol_mine"),
                (1022, "assume_debt"), (1023, "fund"), (1024, "borrow_practice"),
                (1025, "pay_both")], "fund", 1027, "narrow_fund_36"),
        }
        for slug, (picks, short, notice_id, choice) in paths.items():
            with self.subTest(arc=slug):
                world, arc, second = self._run_route(slug, picks, watch=False)
                vars = world.countries["LAN"]
                if short == "mine": self._set_building_fact(vars, "building_mine", occupancy=0.2, shortage=True)
                elif short == "river": self._set_building_fact(vars, "building_port", level=0)
                else: self._set_building_fact(vars, "building_mine", occupancy=0.2, shortage=True)
                review_event = {"mine":1006,"river":1016,"fund":1026}[short]
                self._elapse_blocked_months(world, arc, short, 36, review_event, notice_id)
                self.assertEqual(vars[f"ywc_lan_{short}_notice_current"], 36)
                self._take_event_option(world, arc, notice_id, choice)
                self.assertEqual(vars.get(f"ywc_lan_{short}_narrowed"), 1)
                self.assertNotIn(f"ywc_lan_{short}_six_months_complete", vars)
                if short == "mine":
                    self.assertFalse(_script_condition(world, "{ ywc_lan_mine_target_ready = yes }", "LAN"))
                    self._set_building_fact(vars, "building_mine", level=1, occupancy=0.7, shortage=False)
                    self.assertTrue(_script_condition(world, "{ ywc_lan_mine_target_ready = yes }", "LAN"))
                    for _ in range(7):
                        event_number = self._pulse_active(world, arc)
                        if event_number is not None:
                            self.assertEqual(event_number, 1006)
                            self._take_event_option(world, arc, event_number, "defer")
                    self.assertTrue(vars.get("ywc_lan_mine_six_months_complete"))
                    self.assertGreaterEqual(vars.get("ywc_lan_mine_blocked_months", 0), 0)

    def test_real_12_month_notice_dispatches_and_resets_all_three_arcs(self):
        paths = {
            "v03_lan_mine_accounts": ([(1000, "public_audit"), (1001, "staff_audit"),
                (1002, "public_share_first"), (1003, "use_shipping"), (1004, "merge_customs"),
                (1005, "fund_audit")], "mine", 1006, "reconsider_mine_12"),
            "v03_lan_river_compacts": ([(1010, "guards"), (1011, "deed_review"),
                (1012, "notify_neighbour"), (1013, "restrict_blocks"),
                (1014, "hire_guards"), (1015, "hold_scale")], "river", 1016, "reconsider_river_12"),
            "v03_lan_work_accident_fund": ([(1020, "mutual_fund"), (1021, "enrol_mine"),
                (1022, "assume_debt"), (1023, "fund"), (1024, "borrow_practice"),
                (1025, "pay_both")], "fund", 1026, "reconsider_fund_12"),
        }
        for slug, (picks, short, notice_id, choice) in paths.items():
            with self.subTest(arc=slug):
                world, arc, second = self._run_route(slug, picks, watch=False)
                vars = world.countries["LAN"]
                if short == "mine": self._set_building_fact(vars, "building_mine", occupancy=0.2, shortage=True)
                elif short == "river": self._set_building_fact(vars, "building_port", level=0)
                else: self._set_building_fact(vars, "building_mine", occupancy=0.2, shortage=True)
                review_event = {"mine":1006,"river":1016,"fund":1026}[short]
                self._elapse_blocked_months(world, arc, short, 12, review_event, notice_id)
                self.assertEqual(vars[f"ywc_lan_{short}_notice_current"], 12)
                self._take_event_option(world, arc, notice_id, choice)
                self.assertNotIn(f"ywc_lan_{short}_notice_current", vars)
                self.assertEqual(vars.get(f"ywc_lan_{short}_blocked_months"), 12)
                self.assertEqual(vars.get(f"ywc_lan_{short}_notice12_sent"), 1)

    def test_real_mutual_fund_route_reaches_fully_funded_terminal(self):
        world, arc, terminal_event = self._run_route("v03_lan_work_accident_fund", [
            (1020, "mutual_fund"), (1021, "enrol_mine"), (1022, "assume_debt"),
            (1023, "fund"), (1024, "borrow_practice"), (1025, "pay_both")])
        self.assertEqual(terminal_event, 1027)
        vars = world.countries["LAN"]
        self.assertEqual(world.treasury["LAN"], -4000)
        self._take_event_option(world, arc, terminal_event, "settle_full")
        self.assertTrue(vars.get("ywc_lan_fund_established"))
        self._assert_terminal_history(world, arc, "fund", 1)

    def test_real_private_relief_route_reaches_compromise_without_filing_fee(self):
        world, arc, terminal_event = self._run_route("v03_lan_work_accident_fund", [
            (1020, "private_relief"), (1021, "small_roll"), (1022, "company_holds"),
            (1023, "firm_reserve"), (1024, "decline_practice"), (1025, "pay_wages_first")])
        self.assertEqual(terminal_event, 1027)
        vars = world.countries["LAN"]
        self.assertNotIn("ywc_lan_fund_filing_fee_paid", vars)
        self.assertEqual(world.treasury["LAN"], 0)
        self._take_event_option(world, arc, terminal_event, "settle_compromise")
        self.assertTrue(vars.get("ywc_lan_fund_compromise"))
        self._assert_terminal_history(world, arc, "fund", 2)

    def test_office_and_mine_gates_read_occupancy_and_supply(self):
        world = self._world(1000)
        office = world.trigger_defs["ywc_v03_lan_has_staffed_office"]
        mine = world.trigger_defs["ywc_v03_lan_has_mine_employment"]
        self.assertTrue(world.conditions(office, "LAN"))
        self.assertTrue(world.conditions(mine, "LAN"))
        vars = world.countries["LAN"]
        self._set_building_fact(vars, "building_government_administration", occupancy=0.79)
        self.assertFalse(world.conditions(office, "LAN"), "a high-level but mostly vacant office is not staffed")
        self._set_building_fact(vars, "building_government_administration", occupancy=0.9, shortage=True)
        self.assertFalse(world.conditions(office, "LAN"), "an input-starved office does not count as staffed")
        self._set_building_fact(vars, "building_government_administration", shortage=False)
        self._set_building_fact(vars, "building_mine", occupancy=0.59)
        self.assertFalse(world.conditions(mine, "LAN"), "a mine level without real employment is not mine employment")
        self._set_building_fact(vars, "building_mine", occupancy=0.75, shortage=True)
        self.assertFalse(world.conditions(mine, "LAN"), "an input-starved mine does not count as working employment")
        catalog_text = CATALOG_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("80%", catalog_text)
        self.assertIn("60%", catalog_text)

    def test_three_legal_claims_keep_independent_normal_queues(self):
        expected = {
            "v03_lan_mine_accounts": ("ywc_je_v03_lan_mine_ledger", 1000, "ywc_lan_mine_pending_event"),
            "v03_lan_river_compacts": ("ywc_je_v03_lan_river_compacts", 1010, "ywc_lan_river_pending_event"),
            "v03_lan_work_accident_fund": ("ywc_je_v03_lan_accident_fund", 1020, "ywc_lan_fund_pending_event"),
        }
        for slug, (journal_id, event_id, queue) in expected.items():
            journal = next(j for j in _arc(self.catalog, slug)["journals"] if j["id"] == journal_id)
            self.assertTrue(self._possible(journal), journal_id)
            nodes = parse(journal["script"])
            immediate = next(value for key, _, value in nodes if key == "immediate")
            self.world.execute(immediate, "LAN")
        variables = self.world.countries["LAN"]
        self.assertEqual(variables["ywc_lan_mine_pending_event"], 1000)
        self.assertEqual(variables["ywc_lan_river_pending_event"], 1010)
        self.assertEqual(variables["ywc_lan_fund_pending_event"], 1020)
        self.assertNotIn("ywc_lan_pending_event", variables)

    def test_owned_continuation_needs_completed_phase_and_ignores_entry_capacity(self):
        variables = self.world.countries["LAN"]
        variables.update({
            "ywc_v03_lan_v03_lan_mine_accounts_started": 1,
            "ywc_v03_active_arc_count": 3,
            "ywc_v03_visible_task_count": 6,
        })
        journal = self._journal("v03_lan_mine_accounts", "mine_settlement")
        self.assertFalse(self._possible(journal), "settlement cannot be offered before actual first-phase completion")
        variables["ywc_lan_mine_phase_one_complete"] = 1
        self.assertTrue(self._possible(journal), "an owned continuation must not consume new entry capacity")

    def test_claim_preserves_preexisting_public_legacy_outcome(self):
        self.world.run("ywc_lan_claim_mine_arc", "LAN")
        self.assertEqual(self.world.countries["LAN"]["ywc_campaign_lan_c1_outcome"], 3)

    def test_unaffordable_stale_paid_choice_does_not_charge_or_select_route(self):
        variables = self.world.countries["LAN"]
        journal = next(j for j in _arc(self.catalog, "v03_lan_mine_accounts")["journals"]
                       if j["id"] == "ywc_je_v03_lan_mine_ledger")
        immediate = next(value for key, _, value in parse(journal["script"]) if key == "immediate")
        self.world.execute(immediate, "LAN")
        variables.update({"ywc_lan_mine_fee": 1000, "gold_reserves": 0})
        self.world.run("ywc_lan_choose_mine_audit", "LAN")
        self.assertNotIn("ywc_lan_mine_filing_fee_paid", variables)
        self.assertNotIn("ywc_lan_mine_route", variables)
        self.assertEqual(self.world.treasury["LAN"], 0)

    def test_every_initial_paid_route_uses_its_advertised_cash_amount(self):
        cases = (
            ("v03_lan_mine_accounts", "ywc_lan_choose_mine_audit", "ywc_lan_mine_route", 1, 1000),
            ("v03_lan_mine_accounts", "ywc_lan_choose_mine_farm", "ywc_lan_mine_route", 2, 700),
            ("v03_lan_mine_accounts", "ywc_lan_choose_mine_limited", "ywc_lan_mine_route", 3, 500),
            ("v03_lan_river_compacts", "ywc_lan_choose_river_compensate", "ywc_lan_river_route", 1, 1000),
            ("v03_lan_river_compacts", "ywc_lan_choose_river_restrict", "ywc_lan_river_route", 2, 500),
            ("v03_lan_river_compacts", "ywc_lan_choose_river_guards", "ywc_lan_river_route", 3, 400),
            ("v03_lan_work_accident_fund", "ywc_lan_choose_fund_mutual", "ywc_lan_fund_route", 1, 1000),
            ("v03_lan_work_accident_fund", "ywc_lan_choose_fund_company", "ywc_lan_fund_route", 2, 700),
        )
        for slug, helper, route_var, route, cost in cases:
            with self.subTest(helper=helper):
                world = self._world(cost - 1)
                self._activate_arc(world, slug)
                world.run(helper, "LAN")
                country = world.countries["LAN"]
                self.assertNotIn(route_var, country)
                self.assertEqual(world.treasury["LAN"], 0)
                country["gold_reserves"] = cost
                world.run(helper, "LAN")
                self.assertEqual(country[route_var], route)
                self.assertEqual(world.treasury["LAN"], -cost)
                self.assertEqual(country["gold_reserves"], 0)

    def test_every_later_paid_reserve_fails_cleanly_at_cash_zero(self):
        cases = (
            ("v03_lan_mine_accounts", "ywc_lan_choose_mine_audit", "ywc_lan_mine_route", 1,
             "ywc_lan_mine_fund_audit", "ywc_lan_mine_reserve_paid"),
            ("v03_lan_river_compacts", "ywc_lan_choose_river_compensate", "ywc_lan_river_route", 1,
             "ywc_lan_river_fund_board", "ywc_lan_river_board_reserve_paid"),
            ("v03_lan_river_compacts", "ywc_lan_choose_river_guards", "ywc_lan_river_route", 3,
             "ywc_lan_river_hire_guards", "ywc_lan_river_guard_fee_paid"),
            ("v03_lan_river_compacts", "ywc_lan_choose_river_guards", "ywc_lan_river_route", 3,
             "ywc_lan_river_convert_board", "ywc_lan_river_board_conversion_paid"),
            ("v03_lan_work_accident_fund", "ywc_lan_choose_fund_mutual", "ywc_lan_fund_route", 1,
             "ywc_lan_fund_assume_debt", "ywc_lan_fund_assumption_fee_paid"),
            ("v03_lan_work_accident_fund", "ywc_lan_choose_fund_mutual", "ywc_lan_fund_route", 1,
             "ywc_lan_fund_open_mutual", "ywc_lan_fund_mutual_reserve_paid"),
            ("v03_lan_work_accident_fund", "ywc_lan_choose_fund_mutual", "ywc_lan_fund_route", 1,
             "ywc_lan_fund_pay_both", "ywc_lan_fund_pay_both_reserve_paid"),
        )
        for slug, opening, route_var, route, helper, paid in cases:
            with self.subTest(helper=helper):
                world = self._world(1000)
                self._activate_arc(world, slug)
                world.run(opening, "LAN")
                self.assertEqual(world.countries["LAN"][route_var], route)
                initial_debit = world.treasury["LAN"]
                world.countries["LAN"]["gold_reserves"] = 0
                world.run(helper, "LAN")
                self.assertNotIn(paid, world.countries["LAN"])
                self.assertEqual(world.treasury["LAN"], initial_debit)

    def test_unresolved_outcome_callback_is_not_silently_removed(self):
        names = {name for name, _, _ in parse(self.effects)}
        for name in ("ywc_lan_mark_established_outcome", "ywc_lan_mark_compromise_outcome",
                     "ywc_lan_mark_breach_outcome"):
            self.assertIn(name, names)


class LanPaymentTest(unittest.TestCase):
    def test_fees_are_captured_snapshot_and_actually_charged(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for arc in ("mine", "river", "fund"):
            claim = _helper_body(effects, f"ywc_lan_claim_{arc}_arc")
            self.assertIn("yearly_gross_income", claim)
            self.assertIn("divide = 52", claim)
            self.assertIn("clamp_variable", claim)
            chargers = [h for h in re.findall(rf"(?m)^(ywc_lan_choose_{arc}_[a-z0-9_]+)\s*=\s*\{{", effects)
                        if "add_treasury" in _helper_body(effects, h)]
            self.assertTrue(chargers, f"{arc} has no charging route helper")
            for helper in chargers:
                pay = _helper_body(effects, helper)
                for token in ("add_treasury", "multiply = -1", "in_default = no",
                              "declared_bankruptcy"):
                    self.assertIn(token, pay, f"{arc} {helper}")

    def test_no_route_helper_can_charge_twice(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for helper in re.findall(r"(?m)^(ywc_lan_choose_[a-z0-9_]+)\s*=\s*\{", effects):
            body = _helper_body(effects, helper)
            self.assertLessEqual(body.count("add_treasury"), 1, helper)
            if "add_treasury" in body:
                self.assertIn("NOT = { has_variable = ywc_lan_", body, helper)
                self.assertIn("_filing_fee_paid", body, helper)


class LanHonestyTest(unittest.TestCase):
    @staticmethod
    def _buildings():
        return [
            {"type": "building_government_administration", "groups": set(), "level": 2, "occupancy": 0.9, "shortage": False},
            {"type": "building_mine", "groups": {"bg_mining"}, "level": 3, "occupancy": 0.75, "shortage": False},
            {"type": "building_port", "groups": set(), "level": 1, "occupancy": 0.7, "shortage": False},
        ]
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

    def test_real_closers_keep_breach_distinct_and_journal_exit_exclusive(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        short_for = {"mine_accounts": "mine", "river_compacts": "river", "work_accident_fund": "fund"}
        for slug, short in SLOTS.items():
            item = _arc(_catalog(), slug)
            state_slot = "ywc_v03_lan_v03_lan_" + short + "_started"
            outcome = "ywc_v03_lan_v03_lan_" + short + "_outcome"
            for terminal, closer, expected in (
                ("established", f"ywc_lan_close_{short_for[short]}_as_established", 1),
                ("compromise", f"ywc_lan_close_{short_for[short]}_as_compromise", 2),
                ("breach", f"ywc_lan_close_{short_for[short]}_as_breach", 0),
            ):
                with self.subTest(arc=short, terminal=terminal):
                    tag = "LAN"
                    triggers = (TRIGGERS_PATH.read_text(encoding="utf-8-sig")
                                + "\n" + SHARED_TRIGGERS_PATH.read_text(encoding="utf-8-sig"))
                    world = LanRuntimeWorld(effects, triggers, {tag: {
                        state_slot: 1, "ywc_v03_active_arc_count": 1,
                        "ywc_v03_visible_task_count": 1, f"ywc_lan_{short_for[short]}_route": 1 if terminal == "established" else 2,
                        f"ywc_lan_{short_for[short]}_six_months_complete": 1,
                        f"ywc_lan_{short_for[short]}_implementation_complete": 1,
                        "test_buildings": self._buildings(),
                        "test_laws": {"law_commercialized_agriculture", "law_poor_laws"},
                    }})
                    country = world.countries[tag]
                    country[f"ywc_lan_{short_for[short]}_phase_one_complete"] = 1
                    if terminal == "established":
                        country[f"ywc_lan_{short_for[short]}_reserve_paid"] = 1
                    if short == "mine_accounts":
                        country.update({
                            "ywc_lan_mine_audit_chosen": 1, "ywc_lan_mine_clerks_kept": 1,
                            "ywc_lan_mine_share_choice": 1, "ywc_lan_mine_freight_checked": 1,
                            "ywc_lan_mine_customs_merged": 1, "ywc_lan_mine_farm_chosen": 1,
                            "ywc_lan_mine_customs_separate": 1,
                            "ywc_lan_mine_freight_internal": 1,
                        })
                    elif short == "river_compacts":
                        country.update({
                            "ywc_lan_river_board_chosen": 1, "ywc_lan_river_deed_checked": 1,
                            "ywc_lan_river_neighbour_notified": 1, "ywc_lan_river_restrict_chosen": 1,
                            "ywc_lan_river_blocks_restricted": 1,
                            "ywc_lan_river_board_funded": 1,
                        })
                    else:
                        country.update({
                            "ywc_lan_fund_mutual_chosen": 1, "ywc_lan_fund_mutual_opened": 1,
                            "ywc_lan_fund_both_paid": 1, "ywc_lan_fund_practice_adopted": 1,
                            "ywc_lan_fund_company_chosen": 1, "ywc_lan_fund_debt_choice": 1,
                            "ywc_lan_fund_firm_reserved": 1,
                        })
                    world.run(closer, tag)
                    self.assertEqual(country[outcome], expected)
                    self.assertTrue(country[f"ywc_lan_{short_for[short]}_settled"])
                    if terminal == "breach":
                        self.assertTrue(country[f"ywc_lan_{short_for[short]}_breach"])
                    else:
                        self.assertFalse(country.get(f"ywc_lan_{short_for[short]}_breach", False))
                    self.assertEqual((country["ywc_v03_active_arc_count"], country["ywc_v03_visible_task_count"]), (0, 0))
                    first, settlement = item["journals"]
                    self.assertEqual((_script_condition(world, first["goal"], tag), _script_condition(world, first["exit_conditions"], tag)), (terminal != "breach", terminal == "breach"))
                    self.assertEqual((_script_condition(world, settlement["goal"], tag), _script_condition(world, settlement["exit_conditions"], tag)), (terminal != "breach", terminal == "breach"))
                    # Replaying an actual breach closer cannot write a new result or release twice.
                    world.run(closer, tag)
                    self.assertEqual(country[outcome], expected)
                    self.assertEqual((country["ywc_v03_active_arc_count"], country["ywc_v03_visible_task_count"]), (0, 0))
        self.assertIn("ywc_lan_relief_gap", _helper_body(effects, "ywc_lan_choose_fund_private"))
        modifiers = MODIFIERS_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("country_legitimacy_base_add = -10", modifiers)
        self.assertIn("state_lower_strata_expected_sol_add = 1", modifiers)


class LanObservationTest(unittest.TestCase):
    def test_stale_terminal_recovery_is_owned_by_phase_and_nonterminal_state(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for short, review in (("mine", 1006), ("river", 1016), ("fund", 1026)):
            body = _helper_body(effects, f"ywc_lan_{short}_reject_stale_terminal")
            self.assertIn(f"has_variable = ywc_lan_{short}_phase_two_started", body)
            self.assertIn(f"NOT = {{ ywc_lan_{short}_target_ready = yes }}", body)
            self.assertNotIn(f"has_variable = ywc_lan_{short}_six_months_complete", body)
            self.assertIn(f"var:ywc_lan_{short}_pending_event = {review}", body)
            self.assertIn(f"NOT = {{ has_variable = ywc_lan_{short}_settled }}", body)

    def test_stale_terminal_rejection_recovers_after_real_loss_pulse_clears_maturity(self):
        helper = LanLifecycleRegressionTest()
        helper.setUp()
        picks = [(1000, "public_audit"), (1001, "staff_audit"), (1002, "public_share_first"),
                 (1003, "use_shipping"), (1004, "merge_customs"), (1005, "fund_audit")]
        world, arc, _ = helper._run_route("v03_lan_mine_accounts", picks, watch=False)
        vars = world.countries["LAN"]
        for _ in range(8):
            self.assertEqual(helper._dispatch_queued_event(world, arc), 1006)
            if vars.get("ywc_lan_mine_six_months_complete"):
                break
            helper._take_event_option(world, arc, 1006, "defer")
        self.assertTrue(vars.get("ywc_lan_mine_six_months_complete"))
        helper._take_event_option(world, arc, 1006, "begin_review")
        self.assertEqual(helper._dispatch_queued_event(world, arc), 1007)
        terminal = next(e for e in arc["events"] if _number(e["id"]) == 1007)
        world.execute(parse("immediate = " + terminal["immediate"])[0][2], "LAN")
        self.assertTrue(_script_condition(world, next(o for o in terminal["options"] if o["key"] == "settle_full")["trigger"], "LAN"))

        helper._set_building_fact(vars, "building_mine", level=0, occupancy=0, shortage=True)
        helper._pulse_active(world, arc)
        self.assertNotIn("ywc_lan_mine_six_months_complete", vars)
        stale = next(o for o in terminal["options"] if o["key"] == "settle_full")
        world.execute(parse("effect = " + stale["effect"])[0][2], "LAN")
        self.assertNotIn("ywc_lan_mine_settled", vars)
        self.assertEqual(vars.get("ywc_lan_mine_pending_event"), 1006)
        self.assertEqual(world.active_journals.get("LAN"), arc["journals"][1]["id"])
        self.assertEqual(vars.get("ywc_v03_active_arc_count"), 1)

        helper._set_building_fact(vars, "building_mine", level=3, occupancy=0.75, shortage=False)
        watch_pulses = 0
        terminal_popup = False
        for _ in range(20):
            event_number = helper._pulse_active(world, arc)
            if "ywc_lan_mine_observation_timer" in vars or vars.get("ywc_lan_mine_six_months_complete"):
                watch_pulses += 1
            if event_number is not None:
                self.assertEqual(event_number, 1006)
                if vars.get("ywc_lan_mine_six_months_complete"):
                    terminal_popup = True
                    break
                helper._take_event_option(world, arc, 1006, "defer")
            if vars.get("ywc_lan_mine_six_months_complete"):
                break
        self.assertTrue(vars.get("ywc_lan_mine_six_months_complete"))
        self.assertGreaterEqual(watch_pulses, 6)
        if not terminal_popup:
            self.assertEqual(helper._dispatch_queued_event(world, arc), 1006)
        helper._take_event_option(world, arc, 1006, "begin_review")
        self.assertEqual(helper._dispatch_queued_event(world, arc), 1007)
        helper._take_event_option(world, arc, 1007, "settle_full")
        self.assertEqual(vars.get("ywc_v03_lan_v03_lan_mine_accounts_outcome"), 1)
        helper._assert_terminal_history(world, arc, "mine", 1)

    def test_full_result_contract_excludes_mine_narrowing_and_fund_mutual_keeps_law(self):
        triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        mine_full = _helper_body(triggers, "ywc_lan_mine_full_ready")
        self.assertIn("NOT = { has_variable = ywc_lan_mine_narrowed }", mine_full)
        for arc in ("river", "fund"):
            full = _helper_body(triggers, f"ywc_lan_{arc}_full_ready")
            compromise = _helper_body(triggers, f"ywc_lan_{arc}_compromise_ready")
            self.assertIn(f"NOT = {{ has_variable = ywc_lan_{arc}_narrowed }}", full)
            self.assertIn(f"AND = {{ var:ywc_lan_{arc}_route = 1 has_variable = ywc_lan_{arc}_narrowed }}", compromise)
        fund_target = _helper_body(triggers, "ywc_lan_fund_target_ready")
        mutual = fund_target[fund_target.index("var:ywc_lan_fund_route = 1"):]
        mutual = mutual[:mutual.index("\n\t\tAND =")]
        self.assertIn("has_law_or_variant = law_type:law_poor_laws", mutual)

    def test_mature_review_submission_rechecks_real_target_on_all_six_contracts(self):
        helper = LanLifecycleRegressionTest()
        helper.setUp()
        paths = (
            ("v03_lan_mine_accounts", [(1000, "public_audit"), (1001, "staff_audit"),
             (1002, "public_share_first"), (1003, "use_shipping"), (1004, "merge_customs"),
             (1005, "fund_audit")], "mine", 1006, "building", "building_mine"),
            ("v03_lan_mine_accounts", [(1000, "shareholder_farm"), (1001, "staff_audit"),
             (1002, "dividend_first"), (1003, "internal_only"), (1004, "separate_books"),
             (1005, "cap_public_claim")], "mine", 1006, "building", "building_mine"),
            ("v03_lan_river_compacts", [(1010, "compensate"), (1011, "deed_review"),
             (1012, "notify_neighbour"), (1013, "fund_board"), (1014, "keep_restricted"),
             (1015, "expand_blocks")], "river", 1016, "building", "building_port"),
            ("v03_lan_river_compacts", [(1010, "guards"), (1011, "deed_review"),
             (1012, "notify_neighbour"), (1013, "restrict_blocks"), (1014, "hire_guards"),
             (1015, "hold_scale")], "river", 1016, "building", "building_port"),
            ("v03_lan_work_accident_fund", [(1020, "mutual_fund"), (1021, "enrol_mine"),
             (1022, "assume_debt"), (1023, "fund"), (1024, "borrow_practice"),
             (1025, "pay_both")], "fund", 1026, "law", "law_poor_laws"),
            ("v03_lan_work_accident_fund", [(1020, "private_relief"), (1021, "small_roll"),
             (1022, "company_holds"), (1023, "firm_reserve"), (1024, "decline_practice"),
             (1025, "pay_wages_first")], "fund", 1026, "modifier", "ywc_lan_relief_gap"),
        )
        for slug, picks, short, review, loss_kind, fact in paths:
            with self.subTest(slug=slug, first=picks[0][1]):
                world, arc, _ = helper._run_route(slug, picks, watch=False)
                vars = world.countries["LAN"]
                for _ in range(5):
                    self.assertEqual(helper._dispatch_queued_event(world, arc), review)
                    if vars.get(f"ywc_lan_{short}_six_months_complete"):
                        break
                    helper._take_event_option(world, arc, review, "defer")
                self.assertTrue(vars.get(f"ywc_lan_{short}_six_months_complete"))
                if loss_kind == "law":
                    vars["test_laws"].discard(fact)
                elif loss_kind == "modifier":
                    world.modifiers = [(tag, fields) for tag, fields in world.modifiers
                                       if tag != "LAN" or fields.get("name", fields.get("modifier")) != fact]
                else:
                    helper._set_building_fact(vars, fact, level=0, occupancy=0.2, shortage=True)
                helper._take_event_option(world, arc, review, "begin_review")
                for stale in (f"ywc_lan_{short}_observation_timer", f"ywc_lan_{short}_observation_started",
                              f"ywc_lan_{short}_six_months_complete"):
                    self.assertNotIn(stale, vars)
                self.assertEqual(vars.get(f"ywc_lan_{short}_pending_event"), review)
                if loss_kind == "law":
                    vars["test_laws"].add(fact)
                elif loss_kind == "modifier":
                    world.modifiers.append(("LAN", {"modifier": fact}))
                else:
                    helper._set_building_fact(vars, fact, level=1 if short == "river" else 3,
                                              occupancy=0.75, shortage=False)
                self.assertEqual(helper._dispatch_queued_event(world, arc), review)
                helper._take_event_option(world, arc, review, "defer")
                self.assertIn(f"ywc_lan_{short}_observation_timer", vars)
                self.assertNotIn(f"ywc_lan_{short}_six_months_complete", vars)

    def test_stale_terminal_submission_requeues_owned_review_for_all_six_contracts(self):
        helper = LanLifecycleRegressionTest()
        helper.setUp()
        paths = (
            ("v03_lan_mine_accounts", [(1000, "public_audit"), (1001, "staff_audit"), (1002, "public_share_first"), (1003, "use_shipping"), (1004, "merge_customs"), (1005, "fund_audit")], "mine", 1006, 1007, "mine", "building_mine", "ywc_lan_close_mine_as_established"),
            ("v03_lan_mine_accounts", [(1000, "shareholder_farm"), (1001, "staff_audit"), (1002, "dividend_first"), (1003, "internal_only"), (1004, "separate_books"), (1005, "cap_public_claim")], "mine", 1006, 1007, "mine", "building_mine", "ywc_lan_close_mine_as_compromise"),
            ("v03_lan_river_compacts", [(1010, "compensate"), (1011, "deed_review"), (1012, "notify_neighbour"), (1013, "fund_board"), (1014, "keep_restricted"), (1015, "expand_blocks")], "river", 1016, 1017, "river", "building_port", "ywc_lan_close_river_as_established"),
            ("v03_lan_river_compacts", [(1010, "guards"), (1011, "deed_review"), (1012, "notify_neighbour"), (1013, "restrict_blocks"), (1014, "hire_guards"), (1015, "hold_scale")], "river", 1016, 1017, "river", "building_port", "ywc_lan_close_river_as_compromise"),
            ("v03_lan_work_accident_fund", [(1020, "mutual_fund"), (1021, "enrol_mine"), (1022, "assume_debt"), (1023, "fund"), (1024, "borrow_practice"), (1025, "pay_both")], "fund", 1026, 1027, "law", "law_poor_laws", "ywc_lan_close_fund_as_established"),
            ("v03_lan_work_accident_fund", [(1020, "private_relief"), (1021, "small_roll"), (1022, "company_holds"), (1023, "firm_reserve"), (1024, "decline_practice"), (1025, "pay_wages_first")], "fund", 1026, 1027, "modifier", "ywc_lan_relief_gap", "ywc_lan_close_fund_as_compromise"),
        )
        for slug, picks, short, review, terminal, loss_kind, fact, closer in paths:
            with self.subTest(slug=slug, first=picks[0][1]):
                world, arc, _ = helper._run_route(slug, picks, watch=False)
                vars = world.countries["LAN"]
                for _ in range(5):
                    self.assertEqual(helper._dispatch_queued_event(world, arc), review)
                    if vars.get(f"ywc_lan_{short}_six_months_complete"):
                        break
                    helper._take_event_option(world, arc, review, "defer")
                self.assertTrue(vars.get(f"ywc_lan_{short}_six_months_complete"))
                helper._take_event_option(world, arc, review, "begin_review")
                self.assertEqual(helper._dispatch_queued_event(world, arc), terminal)
                if loss_kind == "law":
                    vars["test_laws"].discard(fact)
                elif loss_kind == "modifier":
                    world.modifiers = [(tag, fields) for tag, fields in world.modifiers
                                       if tag != "LAN" or fields.get("name", fields.get("modifier")) != fact]
                else:
                    helper._set_building_fact(vars, fact, level=0, occupancy=0.2, shortage=True)
                active = world.active_journals.get("LAN")
                event = next(e for e in arc["events"] if _number(e["id"]) == terminal)
                world.execute(parse("immediate = " + event["immediate"])[0][2], "LAN")
                world.run(closer, "LAN")
                self.assertEqual(world.active_journals.get("LAN"), active)
                slot = {"mine": "mine_accounts", "river": "river_compacts",
                        "fund": "work_accident_fund"}[short]
                self.assertNotIn(f"ywc_v03_lan_v03_lan_{slot}_outcome", vars)
                self.assertNotIn(f"ywc_lan_{short}_settled", vars)
                self.assertEqual(vars.get(f"ywc_lan_{short}_pending_event"), review)
                self.assertNotIn(f"ywc_lan_{short}_six_months_complete", vars)
                if loss_kind == "law":
                    vars["test_laws"].add(fact)
                elif loss_kind == "modifier":
                    world.modifiers.append(("LAN", {"modifier": fact}))
                else:
                    helper._set_building_fact(vars, fact, level=3 if short == "mine" else 1,
                                              occupancy=0.75, shortage=False)
                self.assertEqual(helper._dispatch_queued_event(world, arc), review)
                helper._take_event_option(world, arc, review, "defer")
                self.assertIn(f"ywc_lan_{short}_observation_timer", vars)
                self.assertNotIn(f"ywc_lan_{short}_six_months_complete", vars)

    def test_real_mine_full_contract_can_only_close_limited_after_narrowing_and_fresh_watch(self):
        helper = LanLifecycleRegressionTest()
        helper.setUp()
        picks = [(1000, "public_audit"), (1001, "staff_audit"), (1002, "public_share_first"),
                 (1003, "use_shipping"), (1004, "merge_customs"), (1005, "fund_audit")]
        world, arc, _ = helper._run_route("v03_lan_mine_accounts", picks, watch=False)
        vars = world.countries["LAN"]
        helper._set_building_fact(vars, "building_mine", level=2, occupancy=0.2, shortage=True)
        helper._elapse_blocked_months(world, arc, "mine", 36, 1006, 1007)
        self.assertEqual(vars.get("ywc_lan_mine_notice_current"), 36)
        helper._take_event_option(world, arc, 1007, "narrow_mine_36")
        self.assertTrue(vars.get("ywc_lan_mine_narrowed"))
        helper._set_building_fact(vars, "building_mine", level=1, occupancy=0.65, shortage=False)
        self.assertTrue(_script_condition(world, "{ ywc_lan_mine_target_ready = yes }", "LAN"))
        self.assertFalse(_script_condition(world, "{ ywc_lan_mine_full_ready = yes }", "LAN"))
        terminal = None
        for _ in range(8):
            self.assertEqual(helper._dispatch_queued_event(world, arc), 1006)
            if vars.get("ywc_lan_mine_six_months_complete"):
                break
            helper._take_event_option(world, arc, 1006, "defer")
        else:
            self.fail("narrowed mine standard did not mature after a fresh 180-day watch")
        terminal = 1007
        event = next(e for e in arc["events"] if _number(e["id"]) == terminal)
        options = {o["key"]: o for o in event["options"]}
        self.assertFalse(_script_condition(world, options["settle_full"]["trigger"], "LAN"))
        self.assertTrue(_script_condition(world, options["settle_compromise"]["trigger"], "LAN"))
        world.run("ywc_lan_close_mine_as_established", "LAN")
        self.assertFalse(vars.get("ywc_lan_mine_established"))
        self.assertNotIn("ywc_v03_lan_v03_lan_mine_accounts_outcome", vars)
        self.assertEqual(world.active_journals.get("LAN"), arc["journals"][1]["id"])
        helper._take_event_option(world, arc, 1006, "begin_review")
        self.assertEqual(helper._dispatch_queued_event(world, arc), terminal)
        helper._take_event_option(world, arc, terminal, "settle_compromise")
        self.assertTrue(vars.get("ywc_lan_mine_compromise"))
        self.assertEqual(vars.get("ywc_v03_lan_v03_lan_mine_accounts_outcome"), 2)
        helper._assert_terminal_history(world, arc, "mine", 2)

    def test_river_and_fund_full_routes_narrow_only_to_compromise_after_fresh_watch(self):
        helper = LanLifecycleRegressionTest()
        helper.setUp()
        cases = (
            ("v03_lan_river_compacts", [(1010, "compensate"), (1011, "deed_review"),
             (1012, "notify_neighbour"), (1013, "fund_board"), (1014, "keep_restricted"),
             (1015, "expand_blocks")], "river", 1016, 1017, "narrow_river_36", "building_port",
             "ywc_lan_close_river_as_established", "ywc_lan_close_river_as_compromise"),
            ("v03_lan_work_accident_fund", [(1020, "mutual_fund"), (1021, "enrol_mine"),
             (1022, "assume_debt"), (1023, "fund"), (1024, "borrow_practice"), (1025, "pay_both")],
             "fund", 1026, 1027, "narrow_fund_36", "law_poor_laws",
             "ywc_lan_close_fund_as_established", "ywc_lan_close_fund_as_compromise"),
        )
        for slug, picks, short, review, terminal, narrow_key, loss_fact, full_closer, compromise_closer in cases:
            with self.subTest(arc=short):
                world, arc, _ = helper._run_route(slug, picks, watch=False)
                vars = world.countries["LAN"]
                if short == "river":
                    helper._set_building_fact(vars, loss_fact, level=0, occupancy=0.1, shortage=True)
                else:
                    vars["test_laws"].discard(loss_fact)
                helper._elapse_blocked_months(world, arc, short, 36, review, terminal)
                self.assertEqual(vars.get(f"ywc_lan_{short}_notice_current"), 36)
                helper._take_event_option(world, arc, terminal, narrow_key)
                self.assertTrue(vars.get(f"ywc_lan_{short}_narrowed"))
                if short == "river":
                    helper._set_building_fact(vars, loss_fact, level=1, occupancy=0.65, shortage=False)
                else:
                    helper._set_building_fact(vars, "building_mine", level=1, occupancy=0.65, shortage=False)
                    self.assertNotIn(loss_fact, vars["test_laws"], "narrow mutual target must not promise full poor-laws coverage")
                self.assertTrue(_script_condition(world, f"{{ ywc_lan_{short}_target_ready = yes }}", "LAN"))
                self.assertFalse(_script_condition(world, f"{{ ywc_lan_{short}_full_ready = yes }}", "LAN"))
                self.assertFalse(_script_condition(world, f"{{ ywc_lan_{short}_compromise_ready = yes }}", "LAN"))
                self.assertNotIn(f"ywc_lan_{short}_six_months_complete", vars)
                watched_pulses = 0
                review_popup = False
                for _ in range(15):
                    event_number = helper._pulse_active(world, arc)
                    if f"ywc_lan_{short}_observation_timer" in vars or vars.get(f"ywc_lan_{short}_six_months_complete"):
                        watched_pulses += 1
                    if event_number is not None:
                        self.assertEqual(event_number, review)
                        if vars.get(f"ywc_lan_{short}_six_months_complete"):
                            review_popup = True
                            break
                        helper._take_event_option(world, arc, review, "defer")
                    if vars.get(f"ywc_lan_{short}_six_months_complete"):
                        break
                self.assertGreaterEqual(watched_pulses, 6, "fresh observation must span six live monthly pulses")
                self.assertTrue(vars.get(f"ywc_lan_{short}_six_months_complete"))
                if not review_popup:
                    self.assertEqual(helper._dispatch_queued_event(world, arc), review)
                terminal_event = next(e for e in arc["events"] if _number(e["id"]) == terminal)
                options = {o["key"]: o for o in terminal_event["options"]}
                self.assertFalse(_script_condition(world, options["settle_full"]["trigger"], "LAN"))
                self.assertTrue(_script_condition(world, options["settle_compromise"]["trigger"], "LAN"))
                world.run(full_closer, "LAN")
                self.assertNotIn(f"ywc_lan_{short}_settled", vars)
                self.assertEqual(world.active_journals.get("LAN"), arc["journals"][1]["id"])
                helper._take_event_option(world, arc, review, "begin_review")
                self.assertEqual(helper._dispatch_queued_event(world, arc), terminal)
                helper._take_event_option(world, arc, terminal, "settle_compromise")
                self.assertEqual(vars.get({"river": "ywc_v03_lan_v03_lan_river_compacts_outcome",
                                          "fund": "ywc_v03_lan_v03_lan_work_accident_fund_outcome"}[short]), 2)
                helper._assert_terminal_history(world, arc, short, 2)

    def test_early_paid_current_obligation_loss_gets_12_and_36_month_notices(self):
        helper = LanLifecycleRegressionTest()
        helper.setUp()
        cases = (
            ("v03_lan_mine_accounts", 1000, "public_audit", 1001, "mine", "ywc_lan_mine", 1006, 1007),
            ("v03_lan_river_compacts", 1010, "compensate", 1011, "river", "ywc_lan_river", 1016, 1017),
            ("v03_lan_work_accident_fund", 1020, "mutual_fund", 1021, "fund", "ywc_lan_fund", 1026, 1027),
        )
        for slug, first, paid, current, short, prefix, notice12, notice36 in cases:
            with self.subTest(slug=slug):
                arc = _arc(helper.catalog, slug)
                world = helper._world(10000)
                vars = world.countries["LAN"]
                vars.update({"test_buildings": helper._buildings(),
                             "test_laws": {"law_commercialized_agriculture", "law_poor_laws"}})
                world.active_journals = {"LAN": None}
                world.journal_states = {"LAN": {j["id"]: "inactive" for j in arc["journals"]}}
                world.journal_add_cursor = {"LAN": 0}
                helper._admit_entry(world, arc["journals"][0])
                self.assertEqual(helper._dispatch_queued_event(world, arc), first)
                helper._take_event_option(world, arc, first, paid)
                paid_key = {"mine": "ywc_lan_mine_filing_fee_paid", "river": "ywc_lan_river_filing_fee_paid",
                            "fund": "ywc_lan_fund_filing_fee_paid"}[short]
                self.assertTrue(vars.get(paid_key))
                if short == "mine":
                    helper._set_building_fact(vars, "building_government_administration", occupancy=0)
                elif short == "river":
                    vars["test_laws"].discard("law_commercialized_agriculture")
                else:
                    helper._set_building_fact(vars, "building_mine", occupancy=0)
                    helper._set_building_fact(vars, "building_government_administration", occupancy=0)
                self.assertEqual(helper._dispatch_queued_event(world, arc), current)
                helper._take_event_option(world, arc, current, "defer")
                self.assertTrue(vars.get(f"ywc_lan_{short}_current_deferred"))
                for month in range(1, 41):
                    event_number = helper._pulse_active(world, arc)
                    if event_number == notice12 and vars.get(f"ywc_lan_{short}_notice_current") == 12:
                        helper._take_event_option(world, arc, notice12, f"reconsider_{short}_12")
                    elif event_number == notice36 and vars.get(f"ywc_lan_{short}_notice_current") == 36:
                        break
                    elif event_number is not None:
                        self.assertEqual(event_number, current, (month, vars))
                        helper._take_event_option(world, arc, current, "defer")
                else:
                    self.fail(f"{slug} did not deliver a 36-month current-obligation notice")
                self.assertEqual(vars.get(f"ywc_lan_{short}_notice12_sent"), 1)
                self.assertEqual(vars.get(f"ywc_lan_{short}_notice36_sent"), 1)
                self.assertGreaterEqual(vars.get(f"ywc_lan_{short}_blocked_months", 0), 36)
                self.assertTrue(vars.get(f"ywc_lan_{short}_pending_event"))

    def test_early_current_obligation_recovery_clears_the_notice_epoch(self):
        helper = LanLifecycleRegressionTest()
        helper.setUp()
        cases = (
            ("v03_lan_mine_accounts", 1000, "public_audit", 1001, 1006, "mine", "office"),
            ("v03_lan_river_compacts", 1010, "compensate", 1011, 1016, "river", "law"),
            ("v03_lan_work_accident_fund", 1020, "mutual_fund", 1021, 1026, "fund", "mine_office"),
        )
        for slug, first, paid, current, notice12, short, loss in cases:
            with self.subTest(slug=slug):
                arc = _arc(helper.catalog, slug)
                world = helper._world(10000)
                vars = world.countries["LAN"]
                vars.update({"test_buildings": helper._buildings(),
                             "test_laws": {"law_commercialized_agriculture", "law_poor_laws"}})
                world.active_journals = {"LAN": None}
                world.journal_states = {"LAN": {j["id"]: "inactive" for j in arc["journals"]}}
                world.journal_add_cursor = {"LAN": 0}
                helper._admit_entry(world, arc["journals"][0])
                self.assertEqual(helper._dispatch_queued_event(world, arc), first)
                helper._take_event_option(world, arc, first, paid)
                if loss == "office":
                    helper._set_building_fact(vars, "building_government_administration", occupancy=0)
                elif loss == "law":
                    vars["test_laws"].discard("law_commercialized_agriculture")
                else:
                    helper._set_building_fact(vars, "building_mine", occupancy=0)
                    helper._set_building_fact(vars, "building_government_administration", occupancy=0)
                self.assertEqual(helper._dispatch_queued_event(world, arc), current)
                helper._take_event_option(world, arc, current, "defer")
                event = None
                for _ in range(18):
                    event = helper._pulse_active(world, arc)
                    if event == notice12:
                        self.assertEqual(vars.get(f"ywc_lan_{short}_notice_current"), 12)
                        break
                    if event is not None:
                        self.assertEqual(event, current)
                        helper._take_event_option(world, arc, current, "defer")
                else:
                    self.fail(f"{slug} did not send the real 12-month notice")
                helper._take_event_option(world, arc, notice12, f"reconsider_{short}_12")
                if loss == "office":
                    helper._set_building_fact(vars, "building_government_administration", occupancy=0.9)
                elif loss == "law":
                    vars["test_laws"].add("law_commercialized_agriculture")
                else:
                    helper._set_building_fact(vars, "building_mine", occupancy=0.75)
                    helper._set_building_fact(vars, "building_government_administration", occupancy=0.9)
                helper._pulse_active(world, arc)
                for stale in (f"ywc_lan_{short}_current_deferred", f"ywc_lan_{short}_blocked_months",
                              f"ywc_lan_{short}_notice_event", f"ywc_lan_{short}_notice_current",
                              f"ywc_lan_{short}_notice12_sent", f"ywc_lan_{short}_notice36_sent"):
                    self.assertNotIn(stale, vars, stale)

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
        catalog = _foundation_catalog()
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
