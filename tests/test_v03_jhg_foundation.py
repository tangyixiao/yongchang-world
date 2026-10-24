"""Guard rails for the JHG foundation arcs (the three country paths)."""

import json
import re
import unittest
from collections import Counter
from pathlib import Path
from tests.clausewitz_harness import PulseWorld, parse

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "data" / "content" / "v03" / "countries" / "jhg.json"
REGISTRY_PATH = ROOT / "data" / "content" / "v03" / "id_registry.json"
EFFECTS_PATH = ROOT / "yongchang_world" / "common" / "scripted_effects" / "ywc_v03_jhg_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world" / "common" / "scripted_triggers" / "ywc_v03_jhg_triggers.txt"
MOD = ROOT / "yongchang_world"
SHARED_EFFECTS_PATH = MOD / "common" / "scripted_effects" / "ywc_v03_effects.txt"
SHARED_TRIGGERS_PATH = MOD / "common" / "scripted_triggers" / "ywc_v03_triggers.txt"

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
    "ywc_jhg_court_can_advance",
    "ywc_jhg_court_current_target_ready",
    "ywc_jhg_court_limited_route_execution_ready",
    "ywc_jhg_convoy_navy_ready",
    "ywc_jhg_convoy_port_ready",
    "ywc_jhg_convoy_partner_ready",
    "ywc_jhg_convoy_route_execution_ready",
    "ywc_jhg_convoy_full_sea_lane_covered",
    "ywc_jhg_convoy_can_pay",
    "ywc_jhg_convoy_can_advance",
    "ywc_jhg_convoy_current_target_ready",
    "ywc_jhg_convoy_limited_route_execution_ready",
    "ywc_jhg_tribute_relationship_open",
    "ywc_jhg_tribute_partner_ready",
    "ywc_jhg_tribute_route_execution_ready",
    "ywc_jhg_tribute_can_pay",
    "ywc_jhg_tribute_can_advance",
    "ywc_jhg_tribute_current_target_ready",
    "ywc_jhg_tribute_limited_route_execution_ready",
]

PREFIX = {COURT: "ywc_jhg_court", CONVOY: "ywc_jhg_convoy", TRIBUTE: "ywc_jhg_tribute"}
CLOSERS = {COURT: 1007, CONVOY: 1018, TRIBUTE: 1025}


class JhgTerminalWorld(PulseWorld):
    """Run actual JHG helpers and triggers while fixture-driving engine world facts."""
    def __init__(self, effects, countries):
        shared=SHARED_EFFECTS_PATH.read_text(encoding="utf-8-sig")
        super().__init__(effects + "\n" + shared, countries)
        trigger_text=(SHARED_TRIGGERS_PATH.read_text(encoding="utf-8-sig") + "\n"
                      + TRIGGERS_PATH.read_text(encoding="utf-8-sig"))
        self.triggers={key:body for key,_,body in parse(trigger_text)}
        self.finished_journals = set()

    def journal_is_active(self, tag, journal_id):
        for entry_tag, body in self.journals:
            if entry_tag != tag:
                continue
            if body == journal_id:
                return True
            if isinstance(body, list) and dict((name, field) for name, _, field in body).get("type") == journal_id:
                return True
        return False

    def execute(self, nodes, tag):
        # `add_journal_entry = { type = ... }` is an explicit engine request;
        # `possible` gates player selection of inactive entries, not this effect.
        # Full-chain auto-activation below still evaluates the actual `possible`.
        for node in nodes:
            key, _, value = node
            requested = (dict((name, field) for name, _, field in value).get("type")
                         if key == "add_journal_entry" and isinstance(value, list) else value)
            if key == "add_journal_entry" and not any(
                    j["id"] == requested for item in catalog()["arcs"] for j in item["journals"]):
                raise AssertionError(f"unknown JHG journal entry: {requested}")
        return super().execute(nodes, tag)

    def journal_contract(self, journal):
        nodes=parse("wrapper = "+journal["script"])[0][2]
        shown=next((value for name,_,value in nodes if name=="is_shown_when_inactive"), [])
        possible=next((value for name,_,value in nodes if name=="possible"), [])
        return shown, possible

    def is_finished(self, tag, journal_id):
        return (tag,journal_id) in self.finished_journals

    def finish_journal(self, tag, journal):
        self.finished_journals.add((tag,journal["id"]))
        self.journals=[(entry_tag,body) for entry_tag,body in self.journals
                       if not (entry_tag==tag and (body==journal["id"] or
                           (isinstance(body,list) and dict((name,field) for name,_,field in body).get("type")==journal["id"]))) ]

    def reconcile_journals(self, item, tag="JHG"):
        for journal in item["journals"]:
            if not self.journal_is_active(tag, journal["id"]):
                continue
            if (_script_condition(self, journal["goal"], tag) or
                    _script_condition(self, journal["exit_conditions"], tag)):
                self.finish_journal(tag, journal)

    def run_live_journal_pulse(self, item, tag="JHG"):
        """Reconcile real JE handoffs before each scheduler pulse."""
        self.reconcile_journals(item, tag)
        for candidate in item["journals"]:
            if self.journal_is_active(tag, candidate["id"]) or self.is_finished(tag, candidate["id"]):
                continue
            shown, possible = self.journal_contract(candidate)
            if self.conditions(shown, tag) and self.conditions(possible, tag):
                self.journals.append((tag, candidate["id"]))
        active = [candidate for candidate in item["journals"]
                  if self.journal_is_active(tag, candidate["id"])
                  and not _script_condition(self, candidate["goal"], tag)
                  and not _script_condition(self, candidate["exit_conditions"], tag)]
        if len(active) != 1:
            raise AssertionError(f"expected one live JHG JE before pulse, found {[j['id'] for j in active]}")
        journal = active[0]
        self.run_journal_pulse(journal, tag)
        self.reconcile_journals(item, tag)
        return journal
    def run_journal_pulse(self, journal, tag="JHG"):
        """Pulse only a genuine currently active, unfinished journal entry."""
        if not self.journal_is_active(tag, journal["id"]):
            raise AssertionError(f"journal is not active before pulse: {journal['id']}")
        if _script_condition(self, journal["goal"], tag):
            raise AssertionError(f"journal goal already complete before pulse: {journal['id']}")
        if _script_condition(self, journal["exit_conditions"], tag):
            raise AssertionError(f"journal exit condition already true before pulse: {journal['id']}")
        self._execute_pulse_body_for_unit(journal, tag)

    def _execute_pulse_body_for_unit(self, journal, tag="JHG"):
        """Execute a pulse body for isolated effect tests; not scheduler evidence."""
        nodes=parse("wrapper = "+journal["script"])[0][2]
        pulse=next(value for name,_,value in nodes if name=="on_monthly_pulse")
        body=next(value for name,_,value in pulse if name=="effect")
        before=len(self.events)
        self.execute(body,tag)
        for event_tag,event_id in self.events[before:]:
            event=next((event for item in catalog()["arcs"] for event in item["events"]
                        if event["id"]==event_id),None)
            if event is not None:
                if not _script_condition(self, event["trigger"], event_tag):
                    raise AssertionError(f"actual dispatched event trigger failed: {event_id}")
                immediate=parse("wrapper = "+event["immediate"])[0][2]
                self.execute(immediate,event_tag)

    @staticmethod
    def _compare(left, comparison, right):
        return {"=":lambda a,b:a==b,">=":lambda a,b:a>=b,"<=":lambda a,b:a<=b,
                ">":lambda a,b:a>b,"<":lambda a,b:a<b,"!=":lambda a,b:a!=b}[comparison](left,right)

    def _state_matches(self, nodes, state):
        for key, comparison, value in nodes:
            if key == "is_owned_by":
                if not self._compare(state.get("owned_by_root", False), comparison, value == "ROOT"):
                    return False
            elif key == "any_scope_building":
                if not any(self._building_matches(value, b) for b in state.get("buildings", [])):
                    return False
            else:
                raise AssertionError(f"unsupported JHG state trigger: {(key, comparison, value)}")
        return True

    def _building_matches(self, nodes, building):
        for key, comparison, value in nodes:
            if key == "is_building_type":
                if not self._compare(building.get("type"), comparison, value):
                    return False
            elif key == "occupancy":
                if not self._compare(float(building.get("occupancy", 0)), comparison, float(value)):
                    return False
            elif key == "building_has_goods_shortage":
                expected = value == "yes"
                if not self._compare(bool(building.get("goods_shortage", False)), comparison, expected):
                    return False
            else:
                raise AssertionError(f"unsupported JHG building trigger: {(key, comparison, value)}")
        return True

    def condition(self,node,tag):
        key,comparison,value=node
        country = self.countries[tag]
        if key in self.triggers and value=="yes":
            return self.conditions(self.triggers[key],tag)
        if key=="any_scope_state":
            return any(self._state_matches(value, state) for state in country.get("engine_states", []))
        if key=="any_country":
            return any(self._partner_matches(value, partner) for partner in country.get("engine_partners", []))
        if key=="exists" and value=="overlord":
            return bool(country.get("engine_overlord"))
        if key=="is_subject":
            return country.get("engine_is_subject",False)==(value=="yes")
        if key in ("government_legitimacy","navy_size"):
            return self._compare(country.get(key,0),comparison,float(value))
        if key.startswith("ig:"):
            fact=key.split(":",1)[1].removeprefix("ig_")
            return bool(country.get("engine_interest_groups",{}).get(fact,
                              country.get("engine_powerful_"+fact,False)))
        if key=="has_law_or_variant":
            law=value.removeprefix("law_type:")
            return law in country.get("engine_laws", []) or bool(country.get("engine_law_"+law,False))
        if key=="relations:root":
            return self._compare(country.get("engine_overlord",{}).get("relations",0),comparison,
                                 float(value) if value.replace('.','',1).isdigit() else country.get("engine_relation_thresholds",{}).get(value.split(':')[-1],50))
        if key=="relations_threshold:cordial":
            return self._compare(50,comparison,float(value) if value.replace('.','',1).isdigit() else 50)
        if key in ("has_diplomatic_pact",):
            fields={k:v for k,_,v in value}
            return fields.get("type") in country.get("engine_diplomatic_pacts", [])
        if key=="army_size":
            return self._compare(float(country.get("_partner_army_size",0)),comparison,float(value))
        if key.startswith("c:") and comparison=="?=":
            return super().condition(node,tag)
        if comparison=="?=":
            if isinstance(value,list):
                raise AssertionError(f"unsupported optional-scope equality trigger: {node}")
            actual=bool(country.get(key,False))
            return actual==(value=="yes")
        return super().condition(node,tag)

    @staticmethod
    def _partner_matches(nodes, partner):
        for key, comparison, value in nodes:
            if key == "has_diplomatic_pact":
                pact = {name: field for name, _, field in value}
                if pact.get("type") not in partner.get("diplomatic_pacts", []):
                    return False
            elif key == "relations:root":
                threshold = 50 if value == "relations_threshold:cordial" else float(value)
                if not JhgTerminalWorld._compare(float(partner.get("relations_to_root",0)),comparison,threshold):
                    return False
            elif key == "army_size":
                if not JhgTerminalWorld._compare(float(partner.get("army_size",0)),comparison,float(value)):
                    return False
            elif key == "gold_reserves":
                if not JhgTerminalWorld._compare(float(partner.get("gold_reserves",0)),comparison,float(value)):
                    return False
            else:
                raise AssertionError(f"unsupported JHG partner trigger: {(key, comparison, value)}")
        return True

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
            (COURT, "ywc_jhg_court_close_as_established", "established"),
            (COURT, "ywc_jhg_court_close_as_compromise", "compromise"),
            (COURT, "ywc_jhg_court_close_as_breach", "withdrawn"),
            (CONVOY, "ywc_jhg_convoy_close_as_established", "established"),
            (CONVOY, "ywc_jhg_convoy_close_as_compromise", "compromise"),
            (CONVOY, "ywc_jhg_convoy_close_as_breach", "withdrawn"),
            (TRIBUTE, "ywc_jhg_tribute_close_as_established", "established"),
            (TRIBUTE, "ywc_jhg_tribute_close_as_compromise", "compromise"),
            (TRIBUTE, "ywc_jhg_tribute_close_as_breach", "withdrawn"),
        ]
        for slug, closer, terminal in cases:
            with self.subTest(slug=slug, terminal=terminal):
                tag = "JHG"
                prefix = PREFIX[slug]
                start_var = "ywc_jhg_v03_" + slug[4:] + "_started"
                route = 3
                world = JhgTerminalWorld(effects, {tag: {
                    start_var: 1, "ywc_v03_active_arc_count": 1,
                    "ywc_v03_visible_task_count": 1, prefix + "_route": route,
                    prefix + "_shared_fund": 1 if slug == CONVOY and route == 2 else 0,
                    "bureaucracy": 50, "net_fixed_income": 1000,
                    "government_legitimacy": 60, "engine_powerful_industrialists": True,
                    "engine_is_subject": True,
                    "ywc_jhg_tribute_relationship_open": 1,
                    prefix + "_six_months_complete": 1,
                }})
                world.run(closer, tag)
                item = arc(slug)
                for journal in item["journals"]:
                    complete = _script_condition(world, journal["goal"], tag)
                    fail = _script_condition(world, journal["exit_conditions"], tag)
                    self.assertFalse(complete and fail, journal["id"])
                    if journal["id"].endswith("_settlement") or slug == TRIBUTE:
                        self.assertEqual((complete, fail), (terminal != "withdrawn", terminal == "withdrawn"))

    def test_arcs_are_registered_with_their_reserved_event_ranges(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
        ranges = [r for r in registry["arc_ranges"] if r["catalog_key"] == "country_jhg"]
        foundation_ranges = [r for r in ranges if r["slug"] in SLUGS]
        self.assertEqual(3, len(foundation_ranges))
        self.assertEqual(9, len(ranges))
        for item in catalog()["arcs"]:
            reserved = [r for r in foundation_ranges if r["slug"] == item["slug"]][0]
            numbers = sorted(int(e["id"].split(".")[1]) for e in item["events"])
            self.assertGreaterEqual(numbers[0], reserved["start"], item["slug"])
            self.assertLessEqual(numbers[-1], reserved["end"], item["slug"])
        found = sorted(int(e["id"].split(".")[1]) for i in catalog()["arcs"] for e in i["events"])
        self.assertEqual(found, sorted(EVENT_IDS))

    def test_foundation_arcs_keep_the_locked_card_shape(self):
        self.assertEqual({"key", "layer", "runtime_tags", "arcs"}, set(catalog()))
        expected = {"slug", "era", "participants", "depends_on", "journals", "events",
                    "outcomes", "legacy_links", "inline_delivery_adapter"}
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

    def test_reviewfix_trigger_helpers_have_unique_top_level_definitions(self):
        nodes = parse(TRIGGERS_PATH.read_text(encoding="utf-8-sig"))
        counts = Counter(name for name, _, _ in nodes)
        reviewed_helpers = [
            "ywc_jhg_court_current_target_ready",
            "ywc_jhg_convoy_current_target_ready",
            "ywc_jhg_tribute_current_target_ready",
            "ywc_jhg_court_can_advance",
            "ywc_jhg_convoy_can_advance",
            "ywc_jhg_tribute_can_advance",
        ]
        duplicates = {name: counts[name] for name in reviewed_helpers if counts[name] != 1}
        self.assertEqual({}, duplicates, "review-fix helpers must each have one source definition")

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
                prefix = PREFIX[slug]
                self.assertIn("var:%s_pending_event = %s" % (prefix, number), text)
                self.assertIn("trigger_event = { id = ywc_jhg.%s }" % number, text)
                self.assertIn("remove_variable = %s_pending_event" % prefix, text)

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
            self.assertIn("days = 180", review)
            self.assertIn("%s_six_months_complete" % prefix, review)
            self.assertIn("%s_limited_six_months_complete" % prefix, review)
            self.assertIn("%s_12_notice" % prefix, review)
            self.assertIn("%s_36_notice" % prefix, review)
            self.assertIn("days = 365", review)
            self.assertIn("days = 1095", review)
            reset = re.search(r"%s_reset_observation = \{(.*?)\n\}" % prefix, body, re.S).group(1)
            self.assertIn("%s_observation_timer" % prefix, reset)
            self.assertNotIn("%s_blocked_months" % prefix, reset)
            self.assertNotIn("%s_six_months_complete" % prefix, reset)
            self.assertIn("remove_variable = %s_six_months_complete" % prefix, review)

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


    def test_legacy_bridges_preserve_existing_public_values_when_closers_run(self):
        cases = [
            ("court", "court_assembly", "ywc_jhg_court_close_as_established", "ywc_campaign_jhg_c1_outcome", "ywc_jhg_court_prior_campaign_outcome", 1),
            ("convoy", "convoy_capacity", "ywc_jhg_convoy_close_as_breach", "ywc_campaign_jhg_c1_outcome", "ywc_jhg_convoy_prior_campaign_outcome", 4),
            ("tribute", "tribute_autonomy", "ywc_jhg_tribute_close_as_established", "ywc_je_flavor_jhg_convoy_1", "ywc_jhg_tribute_prior_flavor_outcome", 1),
        ]
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for name, slot, closer, public_key, prior_key, new_outcome in cases:
            with self.subTest(arc=name):
                start = "ywc_jhg_v03_jhg_" + slot + "_started"
                route_key = "ywc_jhg_" + name + "_route"
                world = JhgTerminalWorld(effects, {"JHG": {
                    start: 1, "ywc_v03_active_arc_count": 1,
                    "ywc_v03_visible_task_count": 1, route_key: 1,
                    "ywc_jhg_" + name + "_six_months_complete": 1,
                    public_key: 3,
                    "ywc_jhg_tribute_relationship_open": 1,
                    "ywc_jhg_court_bureaucracy_ready": 1,
                    "bureaucracy":50,"net_fixed_income":1000,
                    "government_legitimacy":60,"engine_powerful_industrialists":True,
                    "engine_is_subject":True,
                    "engine_states":[{"owned_by_root":True,"buildings":[
                        {"type":"building_government_administration","occupancy":0.9,"goods_shortage":False}]}],
                }})
                world.run(closer, "JHG")
                world.run(closer, "JHG")
                state = world.countries["JHG"]
                self.assertEqual(3, state[public_key])
                self.assertEqual(3, state[prior_key])
                self.assertEqual(0, state["ywc_v03_active_arc_count"])
                own = "ywc_jhg_v03_jhg_" + slot + "_outcome"
                self.assertEqual(new_outcome, state[own])


    def test_all_legacy_result_values_are_read_only_and_missing_values_bridge_once(self):
        cases = [
            ("court", "court_bridge_legacy", "ywc_campaign_jhg_c1_outcome", "ywc_jhg_court_prior_campaign_outcome", "ywc_jhg_v03_jhg_court_assembly_outcome"),
            ("convoy", "convoy_bridge_legacy", "ywc_campaign_jhg_c1_outcome", "ywc_jhg_convoy_prior_campaign_outcome", "ywc_jhg_v03_jhg_convoy_capacity_outcome"),
            ("tribute", "tribute_bridge_legacy", "ywc_je_flavor_jhg_convoy_1", "ywc_jhg_tribute_prior_flavor_outcome", "ywc_jhg_v03_jhg_tribute_autonomy_outcome"),
        ]
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for prefix, bridge_suffix, public, prior, own in cases:
            for old_result in (1, 2, 3, 4):
                with self.subTest(arc=prefix, old_result=old_result):
                    state = {public: old_result, own: 2}
                    world = JhgTerminalWorld(effects, {"JHG": state})
                    world.run("ywc_jhg_" + bridge_suffix, "JHG")
                    world.run("ywc_jhg_" + bridge_suffix, "JHG")
                    self.assertEqual(old_result, state[public])
                    self.assertEqual(old_result, state[prior])
                    self.assertEqual(2, state[own])
            with self.subTest(arc=prefix, old_result="missing"):
                state = {own: 4}
                JhgTerminalWorld(effects, {"JHG": state}).run("ywc_jhg_" + bridge_suffix, "JHG")
                self.assertEqual(4, state[public])


    def test_blocked_clock_survives_loss_of_observation_for_37_months(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        slots = {"court": "court_assembly", "convoy": "convoy_capacity", "tribute": "tribute_autonomy"}
        for prefix, slot in slots.items():
            with self.subTest(arc=prefix):
                state = {"ywc_v03_active_arc_count": 1,
                         "ywc_v03_visible_task_count": 1,
                         "ywc_jhg_v03_jhg_" + slot + "_started": 1,
                         "ywc_jhg_" + prefix + "_route": 0,
                         "engine_is_subject": True,
                         "bureaucracy": 50, "net_fixed_income": 1000,
                         "government_legitimacy": 60}
                world = JhgTerminalWorld(effects, {"JHG": state})
                for _ in range(37):
                    world.run("ywc_jhg_" + prefix + "_monthly_review", "JHG")
                self.assertEqual(37, state.get("ywc_jhg_" + prefix + "_blocked_months"))
                self.assertIn("ywc_jhg_" + prefix + "_12_notice", state)
                self.assertIn("ywc_jhg_" + prefix + "_36_notice", state)



    def test_stale_unaffordable_options_keep_the_current_event_retryable(self):
        for slug in SLUGS:
            prefix = PREFIX[slug]
            item = arc(slug)
            opening = item["events"][0]
            route_option = next(option for option in opening["options"] if "_choose_" in option["effect"])
            event_number = int(opening["id"].split(".")[1])
            state = {prefix + "_filing_fee": 1000,
                     "gold_reserves": 0,
                     "ywc_v03_active_arc_count": 1,
                     "ywc_v03_visible_task_count": 1,
                     "in_default": False,
                     "bureaucracy": 60, "government_legitimacy": 70, "navy_size": 10,
                     "net_fixed_income": 1000, "engine_laws": ["law_merchant_navy", "law_landed_voting"],
                     "engine_interest_groups": {"industrialists": True, "landowners": True},
                     "engine_is_subject": True, "engine_diplomatic_pacts": ["alliance"],
                     "engine_partners": [{"diplomatic_pacts": ["alliance"], "relations_to_root": 70, "army_size": 12, "gold_reserves": 10000}],
                     "engine_states": [{"owned_by_root": True, "buildings": [{"type": "building_government_administration", "occupancy": 0.95}, {"type": "building_port", "occupancy": 0.95}]}]}
            world = JhgTerminalWorld(EFFECTS_PATH.read_text(encoding="utf-8-sig"), {"JHG": state})
            world.execute(parse("wrapper = " + route_option["effect"])[0][2], "JHG")
            self.assertNotIn(prefix + "_filing_fee_paid", state, slug)
            self.assertNotIn(prefix + "_route", state, slug)
            self.assertEqual(event_number, state.get(prefix + "_pending_event"), slug)
            self.assertEqual(0, world.treasury["JHG"], slug)
            world.treasury["JHG"] = 1000
            state["gold_reserves"] = 1000
            world.execute(parse("wrapper = " + route_option["effect"])[0][2], "JHG")
            self.assertEqual(1, state[prefix + "_filing_fee_paid"], slug)
            self.assertIn(prefix + "_route", state, slug)
            self.assertEqual(int(item["events"][1]["id"].split(".")[1]), state[prefix + "_pending_event"], slug)
            stage_index = 1 if slug == CONVOY else (0 if slug == TRIBUTE else -1)
            stage_id = item["journals"][stage_index]["id"]
            if slug != TRIBUTE:
                self.assertTrue(world.journal_is_active("JHG", stage_id), slug)



    def test_three_catalog_entry_immediates_keep_independent_queues_and_capacity(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        state = {"ywc_v03_active_arc_count": 0,
                 "ywc_v03_visible_task_count": 0,
                 "yearly_gross_income": 52000,
                 "engine_is_subject": True,
                 "bureaucracy": 50, "net_fixed_income": 1000,
                 "government_legitimacy": 60}
        world = JhgTerminalWorld(effects, {"JHG": state})
        for slug in SLUGS:
            entry = arc(slug)["journals"][0]
            entry_nodes = parse("wrapper = " + entry["script"])[0][2]
            immediate = next(value for name, _, value in entry_nodes if name == "immediate")
            world.execute(immediate, "JHG")
        self.assertEqual(3, state["ywc_v03_active_arc_count"])
        self.assertEqual(3, state["ywc_v03_visible_task_count"])
        self.assertEqual(1000, state["ywc_jhg_court_pending_event"])
        self.assertEqual(1010, state["ywc_jhg_convoy_pending_event"])
        self.assertEqual(1020, state["ywc_jhg_tribute_pending_event"])



    def test_unmatured_selected_routes_cannot_be_closed_as_full_results(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        cases = [
            ("ywc_jhg_court_close_as_established", "ywc_jhg_v03_jhg_court_assembly_started", "ywc_jhg_court_route"),
            ("ywc_jhg_convoy_close_as_established", "ywc_jhg_v03_jhg_convoy_capacity_started", "ywc_jhg_convoy_route"),
            ("ywc_jhg_tribute_close_as_established", "ywc_jhg_v03_jhg_tribute_autonomy_started", "ywc_jhg_tribute_route"),
        ]
        for closer, started, route in cases:
            state={started:1,route:1,"ywc_v03_active_arc_count":1,"ywc_v03_visible_task_count":1,
                   "engine_powerful_industrialists":True,"engine_is_subject":True,
                   "bureaucracy":50,"net_fixed_income":1000,"government_legitimacy":60}
            world=JhgTerminalWorld(effects,{"JHG":state})
            world.run(closer,"JHG")
            self.assertNotIn("ywc_jhg_"+route.split("_")[2]+"_established",state)
            self.assertNotIn(started.replace("_started","_settled"),state)



    def test_successful_route_transaction_hands_off_to_a_live_stage_journal(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        expected = {COURT: "ywc_je_v03_jhg_court_settlement",
                    CONVOY: "ywc_je_v03_jhg_convoy_partner_watch"}
        for slug, journal_id in expected.items():
            with self.subTest(arc=slug):
                item = arc(slug)
                option = next(op for op in item["events"][0]["options"] if "_choose_" in op["effect"])
                prefix = PREFIX[slug]
                state = {prefix+"_filing_fee":100, prefix+"_route":0,
                         "gold_reserves":1000, "bureaucracy":50,
                         "ywc_v03_active_arc_count":1,"ywc_v03_visible_task_count":1,
                         "yearly_gross_income":52000,"net_fixed_income":1000,
                         "government_legitimacy":60,"engine_is_subject":True,
                         "engine_powerful_industrialists":True,"navy_size":10,"engine_laws":["law_merchant_navy"],
                         "engine_states":[{"owned_by_root":True,"buildings":[{"type":"building_port","occupancy":0.95}]}],
                         "engine_diplomatic_pacts":["alliance"],"engine_partners":[{"diplomatic_pacts":["alliance"],"relations_to_root":70,"army_size":12,"gold_reserves":10000}]}
                world=JhgTerminalWorld(effects,{"JHG":state})
                world.execute(parse("wrapper = "+option["effect"])[0][2],"JHG")
                self.assertEqual(1,state[prefix+"_route"])
                self.assertEqual(1,state[prefix+"_filing_fee_paid"])
                self.assertEqual(int(item["events"][1]["id"].split(".")[1]),state[prefix+"_pending_event"])
                self.assertTrue(world.journal_is_active("JHG", journal_id))
                stages=[j for j in item["journals"] if j["id"]==journal_id]
                self.assertTrue(stages)
                self.assertIn("on_monthly_pulse",stages[0]["script"])


    def test_two_distinct_routes_per_arc_run_from_real_admission_to_mature_terminal(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        route_keys = {
            COURT: [(1, "audit_contract", "settle_full"),
                    (2, "prince_guarantee", "settle_partial"),
                    (3, "merchant_pool", "withdraw")],
            CONVOY: [(1, "main_lane", "settle_full"),
                     (2, "shared_escort", "settle_partial"),
                     (3, "insurance", "withdraw")],
            TRIBUTE: [(1, "fixed_share", "settle_full"),
                      (2, "project_share", "settle_partial"),
                      (3, "ambiguity", "withdraw")],
        }
        terminal_id = {COURT: 1007, CONVOY: 1018, TRIBUTE: 1025}
        terminal_closer = {COURT: "ywc_jhg_court_close_as_established",
                           CONVOY: "ywc_jhg_convoy_close_as_established",
                           TRIBUTE: "ywc_jhg_tribute_close_as_established"}
        actual_paths = {slug: set() for slug in SLUGS}
        successful_targets = {slug: set() for slug in SLUGS}
        for slug in SLUGS:
            item = arc(slug)
            prefix = PREFIX[slug]
            start_var = "ywc_jhg_v03_" + slug[4:] + "_started"
            for route, route_option_key, terminal_choice in route_keys[slug]:
                with self.subTest(arc=slug, route=route, terminal=terminal_choice):
                    state = {
                        "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                        "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
                        "yearly_gross_income": 52000, "gold_reserves": 10000,
                        "bureaucracy": 60, "net_fixed_income": 1000,
                        "government_legitimacy": 70, "navy_size": 10,
                        "engine_laws": ["law_landed_voting", "law_merchant_navy"],
                        "engine_interest_groups": {"industrialists": True, "landowners": True},
                        "engine_is_subject": True,
                        "engine_overlord": {"relations": 70},
                        "engine_diplomatic_pacts": ["alliance"],
                        "engine_partners": [{"diplomatic_pacts": ["alliance"],
                                             "relations_to_root": 70, "army_size": 12,
                                             "gold_reserves": 10000}],
                        "engine_states": [{"owned_by_root": True, "buildings": [
                            {"type": "building_government_administration", "occupancy": 0.95,
                             "goods_shortage": False},
                            {"type": "building_port", "occupancy": 0.95,
                             "goods_shortage": False}]}],
                        # Existing campaign context required by the approved entries.
                        "ywc_campaign_jhg_c1_outcome": 1,
                        "ywc_je_flavor_jhg_convoy_1_resolved": 1,
                    }
                    world = JhgTerminalWorld(effects, {"JHG": state})
                    entry = item["journals"][0]
                    entry_nodes = parse("wrapper = " + entry["script"])[0][2]
                    possible = next(value for name, _, value in entry_nodes if name == "possible")
                    shown = next(value for name, _, value in entry_nodes if name == "is_shown_when_inactive")
                    self.assertTrue(world.conditions(shown, "JHG"), "entry must actually be shown")
                    self.assertTrue(world.conditions(possible, "JHG"), "entry must be possible from actual prior context")
                    immediate = next(value for name, _, value in entry_nodes if name == "immediate")
                    world.execute(immediate, "JHG")
                    self.assertIn(start_var, state)
                    # Model the game's accepted JE activation; the immediate above is production code.
                    world.journals.append(("JHG", entry["id"]))
                    opening_number = int(item["events"][0]["id"].split(".")[1])
                    self.assertEqual(opening_number, state[prefix + "_pending_event"])
                    seen = []
                    actual_route_trace = []
                    route_was_selected = False
                    terminal_closed = False
                    stale_mature_rejected = False
                    retry_popup_seen = False
                    recovered_from_partner_loss = False
                    settlement_partner_loss_checked = False
                    pulse_limit = 60 if route == 1 and terminal_choice == "settle_full" else 30
                    for _ in range(pulse_limit):
                        rejected_this_popup = False
                        world.reconcile_journals(item)
                        # Model the engine checking inactive JEs after their true
                        # prerequisite phase completes; never select a completed JE.
                        for candidate in item["journals"]:
                            if world.journal_is_active("JHG", candidate["id"]) or world.is_finished("JHG", candidate["id"]):
                                continue
                            candidate_shown, candidate_possible = world.journal_contract(candidate)
                            if world.conditions(candidate_shown, "JHG") and world.conditions(candidate_possible, "JHG"):
                                world.journals.append(("JHG", candidate["id"]))
                        active_journals = [j for j in item["journals"]
                                           if world.journal_is_active("JHG", j["id"])
                                           and not _script_condition(world, j["goal"], "JHG")
                                           and not _script_condition(world, j["exit_conditions"], "JHG")]
                        self.assertEqual(1, len(active_journals),
                                         (slug, state, [j["id"] for j in active_journals]))
                        selected_journal = active_journals[0]
                        self.assertFalse(_script_condition(world, selected_journal["goal"], "JHG"))
                        self.assertFalse(_script_condition(world, selected_journal["exit_conditions"], "JHG"))
                        if (slug == CONVOY and route == 2 and
                                selected_journal["id"] == "ywc_je_v03_jhg_convoy_settlement" and
                                not settlement_partner_loss_checked):
                            state["engine_partners"] = []
                            world.run_live_journal_pulse(item)
                            world.reconcile_journals(item)
                            self.assertFalse(world.is_finished("JHG", selected_journal["id"]),
                                             "a recoverable partner loss must not terminate the settlement owner")
                            self.assertTrue(world.journal_is_active("JHG", selected_journal["id"]))
                            self.assertFalse(_script_condition(world, selected_journal["goal"], "JHG"))
                            self.assertFalse(_script_condition(world, selected_journal["exit_conditions"], "JHG"))
                            state["engine_partners"] = [{"diplomatic_pacts": ["alliance"],
                                                         "relations_to_root": 70, "army_size": 12,
                                                         "gold_reserves": 10000}]
                            settlement_partner_loss_checked = True
                        dispatched = len(world.events)
                        world.run_live_journal_pulse(item)
                        world.reconcile_journals(item)
                        if recovered_from_partner_loss:
                            self.assertNotIn(prefix + "_blocked_months", state)
                            self.assertNotIn(prefix + "_six_months_complete", state)
                            recovered_from_partner_loss = False
                        if len(world.events) == dispatched:
                            world.advance_months(1)
                            continue
                        event_id = world.events[-1][1]
                        number = int(event_id.split(".")[1])
                        seen.append(number)
                        event = next(e for e in item["events"] if e["id"] == event_id)
                        if number == terminal_id[slug]:
                            if stale_mature_rejected and prefix + "_six_months_complete" not in state:
                                retry_popup_seen = True
                            if terminal_choice == "withdraw":
                                option = option_by_key(event, "withdraw")
                                option_trigger = parse("wrapper = " + option["trigger"])[0][2]
                                self.assertTrue(world.conditions(option_trigger, "JHG"), "withdraw must remain available")
                            elif prefix + "_six_months_complete" not in state:
                                option = option_by_key(event, "defer")
                            else:
                                option = option_by_key(event, terminal_choice)
                                option_trigger = parse("wrapper = " + option["trigger"])[0][2]
                                self.assertTrue(world.conditions(option_trigger, "JHG"), "terminal choice must be legal now")
                        elif not route_was_selected:
                            option = option_by_key(event, route_option_key)
                            option_trigger = parse("wrapper = " + option["trigger"])[0][2]
                            self.assertTrue(world.conditions(option_trigger, "JHG"), "chosen opening option must be legal")
                        else:
                            # After entry, keep the selected route fixed while
                            # progressing the arc. Never silently choose the
                            # first eligible alternative route and label it as
                            # the original route under test.
                            choices = [o for o in event["options"]
                                       if o["key"] not in ("defer", "withdraw")]
                            preferred = next((o for o in choices if o["key"] == route_option_key), None)
                            if preferred is None:
                                preferred = next((o for o in choices if o["key"] == "hold_course"), None)
                            if preferred is None:
                                preferred = next((o for o in choices
                                                  if prefix + "_choose_" not in o["effect"]), None)
                            if preferred is None and len(choices) == 1:
                                # This event exposes one legal progress branch
                                # for the current phase; record its actual route
                                # effect below instead of silently assuming the
                                # scenario's opening route remains selected.
                                preferred = choices[0]
                            self.assertIsNotNone(preferred, f"no non-route-changing progress choice at {event_id}")
                            option = preferred
                            option_trigger = parse("wrapper = " + option["trigger"])[0][2]
                            self.assertTrue(world.conditions(option_trigger, "JHG"),
                                            f"production option {event_id}/{option['key']} must be legal")
                        old_route = state.get(prefix + "_route", 0)
                        if (number == terminal_id[slug] and route == 1 and
                                terminal_choice == "settle_full" and not stale_mature_rejected):
                            # An actual qualified full popup becomes stale after opening,
                            # while its six-month maturity is still present.
                            self.assertIn(prefix + "_six_months_complete", state)
                            state["in_default"] = True
                            world.execute(parse("wrapper = " + option["effect"])[0][2], "JHG")
                            self.assertNotIn("ywc_jhg_v03_" + slug[4:] + "_outcome", state)
                            self.assertNotIn(prefix + "_six_months_complete", state)
                            self.assertNotIn(prefix + "_limited_six_months_complete", state)
                            self.assertEqual(terminal_id[slug], state[prefix + "_pending_event"])
                            self.assertEqual(1, state[prefix + "_filing_fee_paid"])
                            self.assertEqual(route, state[prefix + "_route"])
                            state.pop("in_default")
                            stale_mature_rejected = True
                            rejected_this_popup = True
                            event_count = len(world.events)
                            world.advance_days(8)
                            world.run_live_journal_pulse(item)
                            self.assertEqual(event_count, len(world.events),
                                             "stale popup must wait for the real 90-day retry gate")
                            self.assertNotIn(prefix + "_six_months_complete", state)
                            self.assertNotIn("ywc_jhg_v03_" + slug[4:] + "_outcome", state)
                            self.assertEqual(180, world.days_until_expiry["JHG"][prefix + "_observation_timer"])
                            self.assertEqual(terminal_id[slug], state[prefix + "_pending_event"])
                        else:
                            world.execute(parse("wrapper = " + option["effect"])[0][2], "JHG")
                        new_route = state.get(prefix + "_route", 0)
                        if new_route != old_route:
                            actual_route_trace.append((event_id, option["key"], old_route, new_route))
                        route_was_selected = route_was_selected or state.get(prefix + "_route", 0) == route
                        if slug == CONVOY and route == 2 and option["key"] == route_option_key:
                            state["engine_partners"] = []
                            for _ in range(2):
                                world.advance_months(1)
                                world.run_live_journal_pulse(item)
                            self.assertGreaterEqual(state[prefix + "_blocked_months"], 2)
                            self.assertNotIn(prefix + "_six_months_complete", state)
                            state["engine_partners"] = [{"diplomatic_pacts": ["alliance"],
                                                         "relations_to_root": 70, "army_size": 12,
                                                         "gold_reserves": 10000}]
                            recovered_from_partner_loss = True
                        if (number == terminal_id[slug] and option["key"] == terminal_choice
                                and not rejected_this_popup):
                            terminal_closed = True
                            break
                        world.advance_months(1)
                    self.assertTrue(route_was_selected, (slug, route, seen))
                    self.assertTrue(terminal_closed, (slug, route, seen, state))
                    if route == 1 and terminal_choice == "settle_full":
                        self.assertTrue(stale_mature_rejected)
                        self.assertTrue(retry_popup_seen, (slug, "missing actual retry popup after cooldown", seen))
                    self.assertEqual(route, state[prefix + "_route"],
                                     "later event must not silently replace the selected target")
                    self.assertIn(opening_number, seen)
                    self.assertIn(terminal_id[slug], seen)
                    if slug == CONVOY and route == 2:
                        self.assertFalse(recovered_from_partner_loss)
                    self.assertEqual(1, state[prefix + "_filing_fee_paid"])
                    if terminal_choice in ("settle_full", "settle_partial"):
                        self.assertIn(prefix + "_six_months_complete", state)
                        self.assertEqual(state[prefix + "_route"], state[prefix + "_observation_route"],
                                         (slug, actual_route_trace, state))
                    own_outcome = "ywc_jhg_v03_" + slug[4:] + "_outcome"
                    outcome = {"settle_full": 1, "settle_partial": 2, "withdraw": 4}[terminal_choice]
                    self.assertEqual(outcome, state[own_outcome])
                    self.assertEqual(1, state["ywc_jhg_v03_" + slug[4:] + "_settled"])
                    self.assertEqual(0, state["ywc_v03_active_arc_count"])
                    world.reconcile_journals(item)
                    self.assertEqual(set(j["id"] for j in item["journals"]),
                                     {entry_id for entry_tag, entry_id in world.finished_journals
                                      if entry_tag == "JHG"},
                                     "every actually started JE must end once and stay terminal")
                    for candidate in item["journals"]:
                        if (not world.journal_is_active("JHG", candidate["id"]) and
                                not world.is_finished("JHG", candidate["id"])):
                            candidate_shown, candidate_possible = world.journal_contract(candidate)
                            if world.conditions(candidate_shown, "JHG") and world.conditions(candidate_possible, "JHG"):
                                self.fail("a terminal phase was eligible for reactivation: " + candidate["id"])
                    actual_paths[slug].add((route_option_key, tuple(seen),
                                            state[prefix + "_route"], terminal_choice))
                    if terminal_choice in ("settle_full", "settle_partial"):
                        ready_key = ("ywc_jhg_court_route_execution_ready" if slug == COURT else
                                     "ywc_jhg_convoy_route_execution_ready" if slug == CONVOY else
                                     "ywc_jhg_tribute_route_execution_ready")
                        self.assertTrue(world.conditions(world.triggers[ready_key], "JHG"))
                        successful_targets[slug].add(state[prefix + "_route"])
                    self.assertTrue(state[prefix + "_route"] in (1, 2, 3),
                                    (slug, actual_route_trace, state))
        for slug, paths in actual_paths.items():
            self.assertGreaterEqual(len(paths), 2, (slug, paths))
            self.assertGreaterEqual(len(successful_targets[slug]), 2,
                                    (slug, "distinct actual successful targets", successful_targets[slug]))
        self.actual_route_summary = {
            slug: sorted({path[2] for path in paths}) for slug, paths in actual_paths.items()
        }



    def test_actual_admission_12_ack_36_limited_fresh_180_and_close(self):
        setups={
            COURT:{"opening":1000,"choice":"audit_contract","lower":lambda s: s.update({"bureaucracy":50,"government_legitimacy":60,"engine_states":[{"owned_by_root":True,"buildings":[{"type":"building_government_administration","occupancy":.75,"goods_shortage":False}]}]}),
                   "loss":lambda s: s.update({"engine_states":[{"owned_by_root":True,"buildings":[{"type":"building_government_administration","occupancy":.5,"goods_shortage":False}]}]}),"event":1007},
            CONVOY:{"opening":1010,"choice":"main_lane","lower":lambda s: s.update({"navy_size":4,"engine_laws":["law_merchant_navy"],"engine_states":[{"owned_by_root":True,"buildings":[{"type":"building_port","occupancy":.7,"goods_shortage":False}]}]}),
                    "loss":lambda s: s.update({"navy_size":2,"engine_states":[{"owned_by_root":True,"buildings":[{"type":"building_port","occupancy":.4,"goods_shortage":False}]}]}),"event":1018},
            TRIBUTE:{"opening":1020,"choice":"fixed_share","lower":lambda s: s.update({"engine_is_subject":True,"bureaucracy":15}),
                     "loss":lambda s: s.update({"engine_is_subject":True,"bureaucracy":5}),"event":1025},
        }
        for slug,config in setups.items():
            with self.subTest(arc=slug):
                prefix=PREFIX[slug]
                state={"ywc_v03_initialized":1,"ywc_v03_active_arc_count":0,
                       "ywc_v03_visible_task_count":0,"yearly_gross_income":52000,
                       "gold_reserves":1000,"net_fixed_income":1000,"bureaucracy":60,
                       "government_legitimacy":70,"navy_size":10,"engine_is_subject":True,
                       "engine_laws":["law_landed_voting","law_merchant_navy"],
                       "engine_interest_groups":{"industrialists":True,"landowners":True},
                       "engine_powerful_industrialists":True,"engine_powerful_landowners":True,
                       "engine_overlord":{"relations":70},"engine_diplomatic_pacts":["alliance"],
                       "engine_partners":[{"diplomatic_pacts":["alliance"],"relations_to_root":70,
                                            "army_size":12,"gold_reserves":12000}],
                       "engine_states":[{"owned_by_root":True,"buildings":[
                           {"type":"building_government_administration","occupancy":.95,"goods_shortage":False},
                           {"type":"building_port","occupancy":.95,"goods_shortage":False}]}],
                       "ywc_campaign_jhg_c1_outcome":1,"ywc_je_flavor_jhg_convoy_1_resolved":1}
                world=JhgTerminalWorld(EFFECTS_PATH.read_text(encoding="utf-8-sig"),{"JHG":state})
                item=arc(slug); entry=item["journals"][0]
                entry_nodes=parse("wrapper = "+entry["script"])[0][2]
                shown=next(v for n,_,v in entry_nodes if n=="is_shown_when_inactive")
                possible=next(v for n,_,v in entry_nodes if n=="possible")
                self.assertTrue(world.conditions(shown,"JHG")); self.assertTrue(world.conditions(possible,"JHG"))
                immediate=next(v for n,_,v in entry_nodes if n=="immediate")
                world.execute(immediate,"JHG")
                with self.assertRaisesRegex(AssertionError, "not active before pulse"):
                    world.run_journal_pulse(entry)
                world.journals.append(("JHG",entry["id"]))
                self.assertEqual(1,state["ywc_v03_active_arc_count"])
                self.assertFalse(state.get(prefix+"_route"))

                # Real opening dispatch and route option produce the fee receipt and next phase.
                world.run_live_journal_pulse(item)
                opening_event=next(e for e in item["events"] if int(e["id"].split(".")[-1])==config["opening"])
                self.assertEqual("ywc_jhg."+str(config["opening"]),world.events[-1][1])
                opening_option=option_by_key(opening_event,config["choice"])
                self.assertTrue(world.conditions(parse("wrapper = "+opening_option["trigger"])[0][2],"JHG"))
                before_treasury=world.treasury["JHG"]
                world.execute(parse("wrapper = "+opening_option["effect"])[0][2],"JHG")
                fee_delta=world.treasury["JHG"]-before_treasury
                self.assertEqual(-1000,fee_delta)
                state["gold_reserves"]+=fee_delta
                self.assertEqual(1,state[prefix+"_filing_fee_paid"])
                self.assertEqual(1,state[prefix+"_route"])
                stage_number=config["opening"]+1
                stage_event=next(e for e in item["events"] if int(e["id"].split(".")[-1])==stage_number)
                delivered_stage=False
                for _ in range(5):
                    world.advance_months(1)
                    prior=len(world.events)
                    world.run_live_journal_pulse(item)
                    if len(world.events)>prior and world.events[-1][1]=="ywc_jhg."+str(stage_number):
                        delivered_stage=True
                        break
                self.assertTrue(delivered_stage,(slug,"ordinary stage not dispatched",state))
                stage_option=option_by_key(stage_event,config["choice"])
                self.assertTrue(world.conditions(parse("wrapper = "+stage_option["trigger"])[0][2],"JHG"))
                after_opening_treasury=world.treasury["JHG"]
                world.execute(parse("wrapper = "+stage_option["effect"])[0][2],"JHG")
                self.assertEqual(after_opening_treasury,world.treasury["JHG"],
                                 "later stage must reuse the actual receipt without replay debit")
                ordinary_pending=state.get(prefix+"_pending_event")
                self.assertIsNotNone(ordinary_pending)
                self.assertNotEqual(stage_number,ordinary_pending)

                # Make the selected full target genuinely unqualified; keep the earned route and receipt.
                config["loss"](state)
                full_ready=prefix+"_route_execution_ready"
                self.assertFalse(world.conditions(world.triggers[full_ready],"JHG"))
                self.assertFalse(world.conditions(world.triggers[prefix+"_current_target_ready"],"JHG"))
                ordinary_counts=Counter()
                delivered_12=False; delivered_36=False
                limit=90
                for _ in range(limit):
                    prior=len(world.events)
                    world.run_live_journal_pulse(item)
                    if len(world.events)>prior:
                        event_id=world.events[-1][1]
                        event=next(e for e in item["events"] if e["id"]==event_id)
                        number=int(event_id.split(".")[-1])
                        if number==config["event"]:
                            if prefix+"_notice_delivery_12" in state and not delivered_12:
                                self.assertIn(prefix+"_12_notice_delivered",state)
                                ack=option_by_key(event,"acknowledge_12_notice")
                                self.assertTrue(world.conditions(parse("wrapper = "+ack["trigger"])[0][2],"JHG"))
                                world.execute(parse("wrapper = "+ack["effect"])[0][2],"JHG")
                                delivered_12=True
                                blocked_at_12_ack=state[prefix+"_blocked_months"]
                            elif prefix+"_notice_delivery_36" in state:
                                self.assertIn(prefix+"_36_notice_delivered",state)
                                self.assertTrue(delivered_12,"36 notice must follow acknowledged 12 notice")
                                self.assertGreaterEqual(state[prefix+"_blocked_months"],blocked_at_12_ack)
                                self.assertGreaterEqual(state[prefix+"_blocked_months"],36)
                                config["lower"](state)
                                limited=option_by_key(event,"limited_36_settlement")
                                self.assertTrue(world.conditions(parse("wrapper = "+limited["trigger"])[0][2],"JHG"),state)
                                world.execute(parse("wrapper = "+limited["effect"])[0][2],"JHG")
                                self.assertTrue(world.conditions(world.triggers[prefix+"_current_target_ready"],"JHG"))
                                self.assertFalse(world.conditions(world.triggers[full_ready],"JHG"),
                                                 "limited target must remain below the full threshold")
                                delivered_36=True
                                break
                            else:
                                defer=option_by_key(event,"defer")
                                world.execute(parse("wrapper = "+defer["effect"])[0][2],"JHG")
                        else:
                            ordinary_counts[number]=ordinary_counts.get(number,0)+1
                            defer=option_by_key(event,"defer")
                            world.execute(parse("wrapper = "+defer["effect"])[0][2],"JHG")
                    world.advance_months(1)
                self.assertTrue(delivered_12, (slug,"missing actual 12 notice",state))
                self.assertTrue(delivered_36, (slug,"missing actual 36 notice",state))
                self.assertGreaterEqual(state[prefix+"_blocked_months"],36)
                self.assertIn(prefix+"_limited_target_selected",state)
                self.assertNotIn(prefix+"_limited_six_months_complete",state)
                self.assertTrue(state[prefix+"_filing_fee_paid"])
                self.assertEqual(1,state[prefix+"_route"])
                self.assertEqual(ordinary_pending,state[prefix+"_pending_event"],
                                 "real ordinary queue remains intact across notice delivery")

                # The target is now qualified; earn a fresh 180-day watch on the actual JE clock.
                world.run_live_journal_pulse(item)  # starts the new observation timer
                timer=prefix+"_observation_timer"
                self.assertEqual(180,world.days_until_expiry["JHG"][timer])
                world.advance_days(179)
                world.run_live_journal_pulse(item)
                self.assertNotIn(prefix+"_limited_six_months_complete",state)
                self.assertEqual(1,world.days_until_expiry["JHG"][timer])
                world.advance_days(1)
                for _ in range(4):
                    prior=len(world.events)
                    world.run_live_journal_pulse(item)
                    if len(world.events)>prior and world.events[-1][1]=="ywc_jhg."+str(config["event"]):
                        break
                    if len(world.events)>prior:
                        event=next(e for e in item["events"] if e["id"]==world.events[-1][1])
                        world.execute(parse("wrapper = "+option_by_key(event,"defer")["effect"])[0][2],"JHG")
                    world.advance_months(1)
                self.assertIn(prefix+"_limited_six_months_complete",state)
                endpoint=next(e for e in item["events"] if int(e["id"].split(".")[-1])==config["event"])
                close=option_by_key(endpoint,"settle_partial")
                self.assertTrue(world.conditions(parse("wrapper = "+close["trigger"])[0][2],"JHG"))
                world.execute(parse("wrapper = "+close["effect"])[0][2],"JHG")
                outcome="ywc_jhg_v03_"+slug[4:]+"_outcome"
                self.assertEqual(2,state[outcome])
                self.assertEqual(1,state["ywc_jhg_v03_"+slug[4:]+"_settled"])
                self.assertEqual(0,state["ywc_v03_active_arc_count"])

    def test_unit_pulse_body_blocked_12_and_36_logic(self):
        endpoints = {COURT: 1007, CONVOY: 1018, TRIBUTE: 1025}
        ordinary = {COURT: 1001, CONVOY: 1011, TRIBUTE: 1021}
        closers = {COURT:"ywc_jhg_court_close_as_compromise",
                   CONVOY:"ywc_jhg_convoy_close_as_compromise",
                   TRIBUTE:"ywc_jhg_tribute_close_as_compromise"}
        for slug, endpoint in endpoints.items():
            for months, marker in ((12, "12_notice_delivered"), (36, "36_notice_delivered")):
                with self.subTest(arc=slug, months=months):
                    prefix=PREFIX[slug]
                    state={"ywc_v03_active_arc_count":1,"ywc_v03_visible_task_count":1,
                           "ywc_jhg_v03_"+slug[4:]+"_started":1,
                           prefix+"_route":1,prefix+"_pending_event":ordinary[slug],
                           "engine_is_subject":slug != TRIBUTE,"bureaucracy":50,
                           "net_fixed_income":1000,"government_legitimacy":60}
                    world=JhgTerminalWorld(EFFECTS_PATH.read_text(encoding="utf-8-sig"),{"JHG":state})
                    journal=arc(slug)["journals"][0]
                    for _ in range(months - 1):
                        before=len(world.events)
                        world._execute_pulse_body_for_unit(journal)
                        if len(world.events) > before:
                            delivered=next(e for e in arc(slug)["events"] if e["id"]==world.events[-1][1])
                            defer=option_by_key(delivered,"defer")
                            world.execute(parse("wrapper = "+defer["effect"])[0][2],"JHG")
                        world.advance_months(1)
                    state[prefix+"_pending_event"] = ordinary[slug]
                    for _ in range(4):
                        before=len(world.events)
                        world._execute_pulse_body_for_unit(journal)
                        if len(world.events) > before and world.events[-1][1] == "ywc_jhg."+str(endpoint):
                            break
                        if len(world.events) > before:
                            delivered=next(e for e in arc(slug)["events"] if e["id"]==world.events[-1][1])
                            world.execute(parse("wrapper = "+option_by_key(delivered,"defer")["effect"])[0][2],"JHG")
                        world.advance_months(1)
                    key=prefix+"_"+marker
                    self.assertIn(key,state)
                    self.assertEqual("ywc_jhg."+str(endpoint),world.events[-1][1],state)
                    self.assertIn(prefix+"_notice_delivery_active",state)
                    self.assertEqual(ordinary[slug], state[prefix+"_pending_event"])
                    self.assertGreaterEqual(sum(event_id == "ywc_jhg."+str(ordinary[slug])
                                                for _,event_id in world.events),
                                            3 if months == 12 else 10)
                    notice_event=next(e for e in arc(slug)["events"] if int(e["id"].split(".")[1])==endpoint)
                    if months == 12:
                        action=option_by_key(notice_event,"acknowledge_12_notice")
                        self.assertTrue(world.conditions(parse("wrapper = "+action["trigger"])[0][2],"JHG"))
                        world.execute(parse("wrapper = "+action["effect"])[0][2],"JHG")
                        self.assertNotIn(prefix+"_notice_delivery_active",state)
                    else:
                        state[prefix+"_route"]=1
                        state["bureaucracy"]=50
                        state["government_legitimacy"]=60
                        state["engine_is_subject"]=True
                        state["navy_size"]=10
                        state["engine_laws"]=["law_merchant_navy"]
                        state["engine_states"]=[{"owned_by_root":True,"buildings":[
                            {"type":"building_port","occupancy":0.9,"goods_shortage":False},
                            {"type":"building_government_administration","occupancy":0.9,"goods_shortage":False}]}]
                        limited=option_by_key(notice_event,"limited_36_settlement")
                        self.assertTrue(world.conditions(parse("wrapper = "+limited["trigger"])[0][2],"JHG"),state)
                        world.execute(parse("wrapper = "+limited["effect"])[0][2],"JHG")
                        self.assertNotIn(prefix+"_compromise",state)
                        self.assertIn(prefix+"_limited_target_selected",state)
                        self.assertNotIn(prefix+"_limited_six_months_complete",state)
                        for _ in range(7):
                            world.advance_months(1)
                            world._execute_pulse_body_for_unit(journal)
                        self.assertIn(prefix+"_limited_six_months_complete",state)
                        self.assertEqual("ywc_jhg."+str(endpoint),world.events[-1][1])
                        self.assertTrue(world.conditions(parse("wrapper = "+limited["trigger"])[0][2],"JHG"))
                        world.execute(parse("wrapper = "+limited["effect"])[0][2],"JHG")
                        self.assertIn(prefix+"_compromise",state)
                        self.assertEqual(2,state["ywc_jhg_v03_"+slug[4:]+"_outcome"])


    def test_notice_context_has_separate_12_month_ack_and_36_month_limited_remedy(self):
        expected = {COURT: (1007, "ywc_jhg_court"),
                    CONVOY: (1018, "ywc_jhg_convoy"),
                    TRIBUTE: (1025, "ywc_jhg_tribute")}
        for slug, (event_number, prefix) in expected.items():
            endpoint = next(e for e in arc(slug)["events"] if int(e["id"].split(".")[1]) == event_number)
            options = {option["key"]: option for option in endpoint["options"]}
            keys = set(options)
            self.assertIn("acknowledge_12_notice", keys, slug)
            self.assertIn("limited_36_settlement", keys, slug)
            self.assertIn("has_variable = " + prefix + "_notice_delivery_12",
                          options["acknowledge_12_notice"]["trigger"], slug)
            self.assertIn("has_variable = " + prefix + "_notice_delivery_36",
                          options["limited_36_settlement"]["trigger"], slug)



    def test_changing_selected_route_restarts_the_six_month_watch(self):
        state={"ywc_jhg_v03_jhg_court_assembly_started":1,
               "ywc_jhg_court_route":3,"bureaucracy":50,"net_fixed_income":1000,
               "government_legitimacy":60,"engine_powerful_industrialists":True,
               "engine_law_law_landed_voting":True,
               "ywc_v03_active_arc_count":1,"ywc_v03_visible_task_count":1}
        world=JhgTerminalWorld(EFFECTS_PATH.read_text(encoding="utf-8-sig"),{"JHG":state})
        world.run("ywc_jhg_court_monthly_review","JHG")
        world.advance_months(6)
        world.run("ywc_jhg_court_monthly_review","JHG")
        self.assertIn("ywc_jhg_court_six_months_complete",state)
        state["ywc_jhg_court_route"]=2
        world.run("ywc_jhg_court_monthly_review","JHG")
        self.assertNotIn("ywc_jhg_court_six_months_complete",state)
        self.assertEqual(180,world.days_until_expiry["JHG"]["ywc_jhg_court_observation_timer"])


class JhgBlockageLifecycleRegression(unittest.TestCase):
    def test_blocked_calendar_never_matures_limited_terminal(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for prefix in ("ywc_jhg_court", "ywc_jhg_convoy", "ywc_jhg_tribute"):
            match = re.search(r"(?ms)^" + re.escape(prefix + "_monthly_review") +
                              r"\s*=\s*\{(.*?)(?=^[a-z_0-9]+\s*=\s*\{|\Z)", effects)
            self.assertIsNotNone(match, prefix)
            body = match.group(1)
            state = {prefix + "_route": 1, "ywc_v03_active_arc_count": 1,
                     "ywc_v03_visible_task_count": 1, "in_default": True}
            world = JhgTerminalWorld(effects, {"JHG": state})
            for _ in range(36):
                world.run(prefix + "_monthly_review", "JHG")
                world.advance_months(1)
            self.assertIn(prefix + "_36_notice", state)
            self.assertNotIn(prefix + "_limited_six_months_complete", state)
            self.assertNotIn(prefix + "_limited_six_months_complete", state)

    def test_recovery_cancels_queued_notice_and_latches_only_after_real_dispatch(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for prefix in ("ywc_jhg_court", "ywc_jhg_convoy", "ywc_jhg_tribute"):
            match = re.search(r"(?ms)^" + re.escape(prefix + "_monthly_review") +
                              r"\s*=\s*\{(.*?)(?=^[a-z_0-9]+\s*=\s*\{|\Z)", effects)
            self.assertIsNotNone(match, prefix)
            body = match.group(1)
            self.assertIn("remove_variable = " + prefix + "_notice_pending_event", body)
            self.assertIn("remove_variable = " + prefix + "_12_notice_delivered", body)
            self.assertIn("remove_variable = " + prefix + "_36_notice_delivered", body)
            self.assertNotIn("set_variable = { name = " + prefix + "_12_notice_delivered", body)
            self.assertNotIn("set_variable = { name = " + prefix + "_36_notice_delivered", body)

    def test_full_chain_asserts_only_live_unfinished_journal_before_each_pulse(self):
        self.assertIn("and not _script_condition(world, j[\"goal\"]", Path(__file__).read_text(encoding="utf-8-sig"))
        self.assertIn("and not _script_condition(world, j[\"exit_conditions\"]", Path(__file__).read_text(encoding="utf-8-sig"))

    def test_exact_cash_fee_receipt_allows_zero_cash_replay_but_stale_finance_cannot_advance(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        setups = [
            (COURT, 1000, 1001, "audit_contract", {"bureaucracy": 60, "government_legitimacy": 70,
             "engine_laws": ["law_landed_voting"], "engine_states": [{"owned_by_root": True, "buildings": [{"type": "building_government_administration", "occupancy": .95}]}]}),
            (CONVOY, 1010, 1011, "main_lane", {"navy_size": 10, "engine_laws": ["law_merchant_navy"],
             "engine_states": [{"owned_by_root": True, "buildings": [{"type": "building_port", "occupancy": .95}]}]}),
            (TRIBUTE, 1020, 1021, "fixed_share", {"bureaucracy": 60, "engine_is_subject": True}),
        ]
        for slug, opening_id, stage_id, opening_key, facts in setups:
            with self.subTest(arc=slug):
                item=arc(slug); prefix=PREFIX[slug]
                state={"ywc_v03_initialized":1,"ywc_v03_active_arc_count":0,
                       "ywc_v03_visible_task_count":0,"yearly_gross_income":52000,
                       "gold_reserves":1000,"net_fixed_income":1000,
                       "government_legitimacy":70,"engine_powerful_industrialists":True,
                       "ywc_campaign_jhg_c1_outcome":1,"ywc_je_flavor_jhg_convoy_1_resolved":1,
                       "engine_diplomatic_pacts":["alliance"],
                       "engine_partners":[{"diplomatic_pacts":["alliance"],"relations_to_root":70,
                                            "army_size":12,"gold_reserves":10000}],**facts}
                world=JhgTerminalWorld(effects,{"JHG":state})
                entry=item["journals"][0]
                entry_nodes=parse("wrapper = "+entry["script"])[0][2]
                shown=next(v for n,_,v in entry_nodes if n=="is_shown_when_inactive")
                possible=next(v for n,_,v in entry_nodes if n=="possible")
                self.assertTrue(world.conditions(shown,"JHG")); self.assertTrue(world.conditions(possible,"JHG"))
                immediate=next(v for n,_,v in entry_nodes if n=="immediate")
                world.execute(immediate,"JHG"); world.journals.append(("JHG",entry["id"]))
                opening=next(e for e in item["events"] if int(e["id"].split(".")[-1])==opening_id)
                option=option_by_key(opening,opening_key)
                self.assertTrue(world.conditions(parse("wrapper = "+option["trigger"])[0][2],"JHG"))
                opening_treasury = world.treasury["JHG"]
                opening_cash = state["gold_reserves"]
                world.execute(parse("wrapper = "+option["effect"])[0][2],"JHG")
                self.assertEqual(1,state[prefix+"_filing_fee_paid"])
                actual_fee_delta = world.treasury["JHG"] - opening_treasury
                self.assertEqual(-1000, actual_fee_delta, "opening option must debit the real quoted fee")
                state["gold_reserves"] = opening_cash + actual_fee_delta
                self.assertEqual(0, state["gold_reserves"], "engine cash follows the actual fee delta")
                stage=next(e for e in item["events"] if int(e["id"].split(".")[-1])==stage_id)
                stage_option=option_by_key(stage,opening_key)
                self.assertTrue(world.conditions(parse("wrapper = "+stage_option["trigger"])[0][2],"JHG"),
                                "paid receipt must permit replay at zero cash")
                state["in_default"]=True
                self.assertFalse(world.conditions(parse("wrapper = "+stage_option["trigger"])[0][2],"JHG"),
                                 "a stale paid popup must still require current financial safety")
                before=state.get(prefix+"_pending_event")
                world.execute(parse("wrapper = "+stage_option["effect"])[0][2],"JHG")
                self.assertEqual(stage_id,state.get(prefix+"_pending_event",before))
                self.assertEqual(1,state[prefix+"_route"])
                self.assertNotIn(prefix+"_negotiated_"+opening_key,state)

    def test_terminal_popup_requeues_when_current_status_or_maturity_fails(self):
        effects=EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for slug, event_id, route, readiness in ((COURT,1007,2,{"engine_law_law_landed_voting":True}),
                                                  (CONVOY,1018,1,{"navy_size":10,"engine_laws":["law_merchant_navy"],"engine_states":[{"owned_by_root":True,"buildings":[{"type":"building_port","occupancy":.95}]}]}),
                                                  (TRIBUTE,1025,3,{"engine_is_subject":True})):
            with self.subTest(arc=slug):
                prefix=PREFIX[slug]
                slot="court_assembly" if slug==COURT else "convoy_capacity" if slug==CONVOY else "tribute_autonomy"
                state={"ywc_jhg_v03_jhg_"+slot+"_started":1,"ywc_v03_active_arc_count":1,
                       "ywc_v03_visible_task_count":1,prefix+"_route":route,
                       prefix+"_six_months_complete":1,"net_fixed_income":1000,
                       "government_legitimacy":70,"bureaucracy":60,"engine_powerful_industrialists":True,
                       "ywc_jhg_tribute_relationship_open":1,**readiness}
                world=JhgTerminalWorld(effects,{"JHG":state})
                option=option_by_key(next(e for e in arc(slug)["events"] if int(e["id"].split(".")[-1])==event_id),"settle_full")
                self.assertTrue(world.conditions(parse("wrapper = "+option["trigger"])[0][2],"JHG"))
                state["in_default"]=True
                self.assertFalse(world.conditions(parse("wrapper = "+option["trigger"])[0][2],"JHG"))
                world.execute(parse("wrapper = "+option["effect"])[0][2],"JHG")
                self.assertNotIn("ywc_jhg_v03_jhg_"+slot+"_settled",state)
                self.assertEqual(event_id,state.get(prefix+"_pending_event"))
                state.pop("in_default")
                self.assertNotIn(prefix+"_six_months_complete",state,
                                 "the production closer must invalidate stale maturity")
                self.assertFalse(world.conditions(parse("wrapper = "+option["trigger"])[0][2],"JHG"),
                                 "current popup must also require earned maturity")

    def test_terminal_closer_preserves_unmatured_watch_when_target_remains_ready(self):
        setups=((COURT,"court_assembly",{"bureaucracy":60,"government_legitimacy":70,
                  "engine_laws":["law_landed_voting"],"engine_states":[{"owned_by_root":True,"buildings":[
                      {"type":"building_government_administration","occupancy":.95,"goods_shortage":False}]}]}),
                (CONVOY,"convoy_capacity",{"navy_size":10,"engine_laws":["law_merchant_navy"],
                  "engine_states":[{"owned_by_root":True,"buildings":[{"type":"building_port","occupancy":.95,"goods_shortage":False}]}]}),
                (TRIBUTE,"tribute_autonomy",{"bureaucracy":60,"engine_is_subject":True,
                  "engine_overlord":{"relations":70},"engine_diplomatic_pacts":["alliance"],
                  "engine_partners":[{"diplomatic_pacts":["alliance"],"relations_to_root":70,"gold_reserves":12000}]}))
        for slug,slot,facts in setups:
            prefix=PREFIX[slug]
            started="ywc_jhg_v03_"+slug[4:]+"_started"
            timer=prefix+"_observation_timer"
            with self.subTest(arc=slug):
                state={started:1,"ywc_v03_active_arc_count":1,
                       "ywc_v03_visible_task_count":1,prefix+"_route":1,prefix+"_filing_fee_paid":1,
                       prefix+"_pending_event":1,prefix+"_observation_armed":1,
                       timer:1,"net_fixed_income":1000,**facts}
                world=JhgTerminalWorld(EFFECTS_PATH.read_text(encoding="utf-8-sig"),{"JHG":state})
                world.days_until_expiry["JHG"][timer]=173
                self.assertIn(started,state,"the actual arc started guard must be active")
                self.assertTrue(world.conditions(world.triggers[prefix+"_current_target_ready"],"JHG"))
                self.assertNotIn(prefix+"_six_months_complete",state,
                                 "the watch must remain unmatured before the closer")
                self.assertIn(timer,world.days_until_expiry["JHG"])
                self.assertEqual(173,world.days_until_expiry["JHG"][timer],
                                 "the fixture must carry an actual nonempty countdown")
                world.run(prefix+"_close_as_compromise","JHG")
                self.assertIn(prefix+"_observation_armed",state)
                self.assertIn(timer,state)
                self.assertEqual(173,world.days_until_expiry["JHG"][timer],
                                 "a still-qualified unmatured watch must keep its countdown")
                self.assertNotIn(prefix+"_six_months_complete",state)
                self.assertNotIn(prefix+"_limited_six_months_complete",state)
                self.assertNotIn("ywc_jhg_v03_"+slug[4:]+"_outcome",state)

    def test_every_terminal_alias_invalidates_only_when_current_target_is_lost(self):
        effects=EFFECTS_PATH.read_text(encoding="utf-8-sig")
        setup=((COURT,1007,"court_assembly"),(CONVOY,1018,"convoy_capacity"),
               (TRIBUTE,1025,"tribute_autonomy"))
        for slug,event_id,slot in setup:
            prefix=PREFIX[slug]
            aliases=(prefix+"_close_as_established",prefix+"_close_as_compromise",
                     "limited_36_settlement")
            for alias in aliases:
                with self.subTest(arc=slug,alias=alias):
                    state={"ywc_jhg_v03_"+slug[4:]+"_started":1,"ywc_v03_active_arc_count":1,
                           "ywc_v03_visible_task_count":1,prefix+"_route":1,
                           prefix+"_filing_fee_paid":1,prefix+"_pending_event":event_id,
                           prefix+"_six_months_complete":1,prefix+"_limited_six_months_complete":1,
                           prefix+"_limited_target_selected":1,prefix+"_observation_armed":1,
                           prefix+"_observation_timer":0,"in_default":True,
                           "bureaucracy":60,"government_legitimacy":70,"net_fixed_income":1000,
                           "engine_is_subject":True}
                    world=JhgTerminalWorld(effects,{"JHG":state})
                    if alias=="limited_36_settlement":
                        state[prefix+"_notice_delivery_active"]=1
                        state[prefix+"_notice_delivery_36"]=1
                        option=option_by_key(next(e for e in arc(slug)["events"]
                                                 if int(e["id"].split(".")[-1])==event_id),alias)
                        world.execute(parse("wrapper = "+option["effect"])[0][2],"JHG")
                    else:
                        world.run(alias,"JHG")
                    self.assertNotIn(prefix+"_six_months_complete",state)
                    self.assertNotIn(prefix+"_limited_six_months_complete",state)
                    self.assertNotIn(prefix+"_observation_armed",state)
                    self.assertNotIn(prefix+"_observation_timer",state)
                    self.assertEqual(1,state[prefix+"_filing_fee_paid"])
                    self.assertEqual(1,state[prefix+"_route"])
                    self.assertEqual(event_id,state[prefix+"_pending_event"])
                    self.assertNotIn("ywc_jhg_v03_"+slug[4:]+"_outcome",state)
                    self.assertEqual(1,state["ywc_v03_active_arc_count"])

    def test_terminal_defer_invalidates_maturity_before_recovery_without_a_pulse(self):
        effects=EFFECTS_PATH.read_text(encoding="utf-8-sig")
        setups=((COURT,1007,2,"court_assembly",{"engine_law_law_landed_voting":True}),
                (CONVOY,1018,1,"convoy_capacity",{"navy_size":10,"engine_laws":["law_merchant_navy"],
                  "engine_states":[{"owned_by_root":True,"buildings":[{"type":"building_port","occupancy":.95}]}]}),
                (TRIBUTE,1025,3,"tribute_autonomy",{"engine_is_subject":True}))
        for slug,event_id,route,slot,facts in setups:
            with self.subTest(arc=slug):
                prefix=PREFIX[slug]
                state={"ywc_jhg_v03_jhg_"+slot+"_started":1,"ywc_v03_active_arc_count":1,
                       "ywc_v03_visible_task_count":1,prefix+"_route":route,
                       prefix+"_filing_fee_paid":1,prefix+"_limited_target_selected":1,
                       prefix+"_six_months_complete":1,prefix+"_limited_six_months_complete":1,
                       prefix+"_observation_armed":1,prefix+"_observation_timer":0,
                       prefix+"_observation_route":route,prefix+"_pending_event":event_id,
                       "net_fixed_income":1000,"government_legitimacy":70,"bureaucracy":60,
                       "engine_powerful_industrialists":True,**facts}
                world=JhgTerminalWorld(effects,{"JHG":state})
                event=next(e for e in arc(slug)["events"] if int(e["id"].split(".")[-1])==event_id)
                defer=option_by_key(event,"defer")
                state["in_default"]=True
                world.execute(parse("wrapper = "+defer["effect"])[0][2],"JHG")
                self.assertNotIn(prefix+"_six_months_complete",state)
                self.assertNotIn(prefix+"_limited_six_months_complete",state)
                self.assertNotIn(prefix+"_observation_armed",state)
                self.assertNotIn(prefix+"_observation_timer",state)
                self.assertEqual(event_id,state[prefix+"_pending_event"])
                self.assertEqual(1,state[prefix+"_filing_fee_paid"])
                self.assertEqual(route,state[prefix+"_route"])
                state.pop("in_default")
                closer= {COURT:"ywc_jhg_court_close_as_compromise",
                         CONVOY:"ywc_jhg_convoy_close_as_compromise",
                         TRIBUTE:"ywc_jhg_tribute_close_as_compromise"}[slug]
                world.run(closer,"JHG")
                self.assertNotIn("ywc_jhg_v03_"+slug[4:]+"_settled",state)
                self.assertNotIn("ywc_jhg_v03_"+slug[4:]+"_outcome",state)

    def test_limited_target_uses_a_lower_real_threshold_and_fresh_180_day_watch(self):
        state={"ywc_jhg_v03_jhg_court_assembly_started":1,"ywc_jhg_court_route":1,
               "ywc_v03_active_arc_count":1,"ywc_v03_visible_task_count":1,
               "bureaucracy":50,"government_legitimacy":60,"net_fixed_income":1000,
               "ywc_jhg_court_notice_delivery_active":1,"ywc_jhg_court_notice_delivery_36":1,
               "engine_states":[{"owned_by_root":True,"buildings":[
                   {"type":"building_government_administration","occupancy":.75}]}]}
        world=JhgTerminalWorld(EFFECTS_PATH.read_text(encoding="utf-8-sig"),{"JHG":state})
        notice=next(e for e in arc(COURT)["events"] if e["id"]=="ywc_jhg.1007")
        select=option_by_key(notice,"limited_36_settlement")
        self.assertTrue(world.conditions(parse("wrapper = "+select["trigger"])[0][2],"JHG"))
        world.execute(parse("wrapper = "+select["effect"])[0][2],"JHG")
        self.assertEqual(1,state["ywc_jhg_court_limited_target_selected"])
        self.assertNotIn("ywc_jhg_court_notice_delivery_36",state)
        world.run("ywc_jhg_court_monthly_review","JHG")
        self.assertIn("ywc_jhg_court_observation_timer",state)
        world.advance_days(179)
        world.run("ywc_jhg_court_monthly_review","JHG")
        self.assertNotIn("ywc_jhg_court_limited_six_months_complete",state)
        world.advance_days(1)
        world.run("ywc_jhg_court_monthly_review","JHG")
        self.assertIn("ywc_jhg_court_limited_six_months_complete",state)
        settle=option_by_key(notice,"limited_36_settlement")
        self.assertTrue(world.conditions(parse("wrapper = "+settle["trigger"])[0][2],"JHG"))
        world.execute(parse("wrapper = "+settle["effect"])[0][2],"JHG")
        self.assertEqual(2,state["ywc_jhg_v03_jhg_court_assembly_outcome"])
        self.assertEqual(1,state["ywc_jhg_v03_jhg_court_assembly_settled"])

    def test_recovery_removes_old_notice_popup_context(self):
        for short, slot, route, facts in (("court","court_assembly",1,{"bureaucracy":50,"government_legitimacy":60,"engine_states":[{"owned_by_root":True,"buildings":[{"type":"building_government_administration","occupancy":.95}]}]}),
                                          ("convoy","convoy_capacity",1,{"navy_size":10,"engine_laws":["law_merchant_navy"],"engine_states":[{"owned_by_root":True,"buildings":[{"type":"building_port","occupancy":.95}]}]}),
                                          ("tribute","tribute_autonomy",1,{"engine_is_subject":True,"bureaucracy":50})):
            with self.subTest(arc=short):
                prefix="ywc_jhg_"+short
                state={"ywc_jhg_v03_jhg_"+slot+"_started":1,prefix+"_route":route,
                       "net_fixed_income":1000,"government_legitimacy":60,"ywc_v03_active_arc_count":1,
                       prefix+"_blocked_months":36,prefix+"_12_notice":1,prefix+"_36_notice":1,
                       prefix+"_notice_pending_event":1007,prefix+"_12_notice_delivered":1,
                       prefix+"_36_notice_delivered":1,prefix+"_notice_delivery_active":1,
                       prefix+"_notice_delivery_12":1,prefix+"_notice_delivery_36":1,**facts}
                world=JhgTerminalWorld(EFFECTS_PATH.read_text(encoding="utf-8-sig"),{"JHG":state})
                world.run(prefix+"_monthly_review","JHG")
                for suffix in ("notice_delivery_active","notice_delivery_12","notice_delivery_36","notice_pending_event","12_notice_delivered","36_notice_delivered"):
                    self.assertNotIn(prefix+"_"+suffix,state)
                self.assertNotIn(prefix+"_36_notice",state)



if __name__ == "__main__":
    unittest.main()
