"""NQG foundation gate: 24 events / 6 journals / 3 arcs of 10+6+8, and the honesty rules
that keep a small island court from inventing famine, treasure or mainland restoration."""

import json
import re
import unittest
from pathlib import Path
from tests.clausewitz_harness import PulseWorld, parse

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "content" / "v03" / "countries" / "nqg.json"
EFFECTS_PATH = ROOT / "yongchang_world" / "common" / "scripted_effects" / "ywc_v03_nqg_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world" / "common" / "scripted_triggers" / "ywc_v03_nqg_triggers.txt"
JOURNAL_PATH = ROOT / "yongchang_world" / "common" / "journal_entries" / "ywc_v03_country_nqg_journal.txt"

ARCS = {
    "v03_nqg_winter_court": (1000, 1009, 10, 3, "winter"),
    "v03_nqg_hunting_rights": (1010, 1015, 6, 1, "hunting"),
    "v03_nqg_northern_port": (1020, 1027, 8, 2, "port"),
}


class NqgTerminalWorld(PulseWorld):
    """Run real NQG route closers with readiness triggers fixture-driven."""
    def condition(self, node, tag):
        key, comparison, value = node
        if key.endswith(("_full_ready", "_compromise_ready")) and value == "yes":
            return True
        return super().condition(node, tag)


def _script_condition(world, block, tag):
    return world.conditions(parse("condition = " + block)[0][2], tag)


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
            found |= set(re.findall(r"(?m)^([a-z_0-9]+)\s*=\s*\{", path.read_text(encoding="utf-8-sig")))
    return found


def _helper_body(text, name):
    """Return one helper's own block. Helpers are emitted one per line, but this also
    copes with multi-line helpers by matching braces."""
    match = re.search(r"(?m)^" + re.escape(name) + r" = \{", text)
    if match is None:
        raise AssertionError(f"helper {name} missing")
    depth = 0
    for index in range(match.end() - 1, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[match.start():index + 1]
    raise AssertionError(f"helper {name} unbalanced")


class NqgCatalogShapeTest(unittest.TestCase):
    def test_three_arcs_with_the_catalogue_counts(self):
        catalog = _catalog()
        self.assertEqual(catalog["key"], "country_nqg")
        self.assertEqual(catalog["runtime_tags"], ["NQG"])
        self.assertEqual(len(catalog["arcs"]), 3)
        seen = set()
        events = journals = 0
        for arc in catalog["arcs"]:
            slug = arc["slug"]
            self.assertIn(slug, ARCS)
            seen.add(slug)
            low, high, count, jcount, _ = ARCS[slug]
            self.assertEqual(arc["era"], "foundation")
            self.assertEqual(arc["depends_on"], [])
            self.assertEqual(len(arc["events"]), count, slug)
            self.assertEqual(len(arc["journals"]), jcount, slug)
            self.assertGreaterEqual(len(arc["outcomes"]), 4)
            self.assertGreaterEqual(len(arc["legacy_links"]), 2)
            numbers = sorted(_number(e["id"]) for e in arc["events"])
            self.assertEqual(numbers[0], low)
            self.assertEqual(numbers[-1], high)
            events += len(arc["events"])
            journals += len(arc["journals"])
        self.assertEqual(seen, set(ARCS))
        self.assertEqual(events, 24)
        self.assertEqual(journals, 6)

    def test_event_ids_use_the_nqg_namespace(self):
        for arc in _catalog()["arcs"]:
            for event in arc["events"]:
                self.assertTrue(event["id"].startswith("ywc_nqg."), event["id"])

    def test_journal_ids_use_the_nqg_namespace(self):
        for arc in _catalog()["arcs"]:
            for index, journal in enumerate(arc["journals"]):
                self.assertRegex(journal["id"], r"^ywc_je_v03_nqg_[a-z0-9_]+$")
                self.assertIsNone(re.search(r"(?m)^\s*(?:complete|fail)\s*=", journal["script"]),
                                  journal["id"])
                if index == 0:
                    self.assertIn("var:ywc_v03_active_arc_count < 3", journal["script"])
                    self.assertIn("var:ywc_v03_visible_task_count < 6", journal["script"])
                    self.assertIn("ywc_v03_has_capacity = yes", journal["script"])
                else:
                    self.assertNotIn("ywc_v03_has_capacity = yes", journal["script"])
                    self.assertNotIn("var:ywc_v03_active_arc_count < 3", journal["script"])
                    self.assertNotIn("var:ywc_v03_visible_task_count < 6", journal["script"])
                self.assertIn("c:NQG ?= this", journal["script"])

    def test_every_event_offers_a_free_exit(self):
        for arc in _catalog()["arcs"]:
            terminal = max(_number(e["id"]) for e in arc["events"])
            for event in arc["events"]:
                keys = [o["key"] for o in event["options"]]
                self.assertEqual(len(keys), len(set(keys)), f"{event['id']} duplicate keys")
                self.assertIn("withdraw", keys, event["id"])
                if _number(event["id"]) != terminal:
                    self.assertIn("defer", keys, event["id"])
                for option in event["options"]:
                    self.assertIn("base =", option["ai_chance"])
                    self.assertTrue(option["cost_note"]["zh"])
                    self.assertTrue(option["consequence_note"]["en"])
                    if option["key"] in ("defer", "withdraw"):
                        self.assertNotIn("add_treasury", option["effect"])

    def test_major_events_never_double_fire(self):
        for arc in _catalog()["arcs"]:
            for event in arc["events"]:
                self.assertIn("ywc_v03_can_deliver_major = yes", event["trigger"])
                self.assertIn("ywc_v03_mark_major_delivered = yes", event["immediate"])
                self.assertIn("c:NQG ?= this", event["trigger"])


class NqgProgressTest(unittest.TestCase):
    """An arc that cannot hand the player the next event is dead content."""

    def test_every_non_terminal_event_advances_its_own_pending_event(self):
        for arc in _catalog()["arcs"]:
            short = ARCS[arc["slug"]][4]
            pending = f"ywc_nqg_{short}_pending"
            numbers = [_number(e["id"]) for e in arc["events"]]
            for event in arc["events"]:
                n = _number(event["id"])
                if n == numbers[-1]:
                    continue
                moved = set()
                for option in event["options"]:
                    if option["key"] == "defer":
                        continue
                    moved |= {int(v) for v in re.findall(rf"name = {pending} value = (\d+)",
                                                          option["effect"])}
                self.assertIn(n + 1, moved, f"{event['id']} cannot reach {n + 1}")

    def test_defer_re_queues_the_same_event(self):
        for arc in _catalog()["arcs"]:
            short = ARCS[arc["slug"]][4]
            pending = f"ywc_nqg_{short}_pending"
            for event in arc["events"]:
                for option in event["options"]:
                    if option["key"] != "defer":
                        continue
                    self.assertIn(f"name = {pending} value = {_number(event['id'])}",
                                  option["effect"], event["id"])


class NqgScriptResolutionTest(unittest.TestCase):
    def test_every_called_helper_is_defined(self):
        catalog = _catalog()
        blob = "\n".join(_arc_text(arc) for arc in catalog["arcs"])
        defined = _definitions()
        for shared in ("ywc_v03_has_capacity", "ywc_v03_can_deliver_major",
                       "ywc_v03_initialize_country", "ywc_v03_mark_major_delivered"):
            self.assertIn(shared, defined, shared)
        called = set(re.findall(r"(?<![A-Za-z0-9_.])(ywc_[a-z0-9_]+)\s*=\s*yes", blob))
        missing = sorted(c for c in called if c not in defined)
        self.assertEqual(missing, [])

    def test_every_event_is_dispatched_from_a_journal(self):
        for arc in _catalog()["arcs"]:
            script = "\n".join(j["script"] for j in arc["journals"])
            for event in arc["events"]:
                self.assertIn(f"trigger_event = {{ id = {event['id']} }}", script,
                              f"{event['id']} unreachable")

    def test_every_journal_is_present_in_the_rendered_file(self):
        rendered = JOURNAL_PATH.read_text(encoding="utf-8-sig")
        for arc in _catalog()["arcs"]:
            for journal in arc["journals"]:
                self.assertIn(journal["id"] + " = {", rendered, journal["id"])


class NqgPaymentTest(unittest.TestCase):
    def test_fees_are_snapshotted_and_actually_charged(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for _, _, _, _, short in ARCS.values():
            claim = _helper_body(effects, f"ywc_nqg_{short}_claim_arc")
            capture = _helper_body(effects, f"ywc_nqg_{short}_capture_cost_base")
            self.assertIn(f"ywc_nqg_{short}_capture_cost_base = yes", claim)
            self.assertIn("yearly_gross_income", capture)
            self.assertIn("divide = 52", capture)
            self.assertIn("clamp_variable", capture)
            pay = _helper_body(effects, f"ywc_nqg_{short}_pay_filing_fee_once")
            for token in ("add_treasury", "multiply = -1", "in_default = yes",
                          "declared_bankruptcy", "gold_reserves >= var:"):
                self.assertIn(token, pay, short)

    def test_a_route_can_never_be_recorded_without_payment(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for _, _, _, _, short in ARCS.values():
            for match in re.finditer(rf"(?m)^(ywc_nqg_{short}_choose_[a-z0-9_]+)\s*=\s*\{{", effects):
                body = _helper_body(effects, match.group(1))
                self.assertIn(f"ywc_nqg_{short}_pay_filing_fee_once = yes", body)
                self.assertIn("has_variable = ywc_nqg_" + short + "_fee_paid", body)
                self.assertLessEqual(body.count("add_treasury"), 1, match.group(1))


class NqgHonestyTest(unittest.TestCase):
    GRANT_PATTERNS = (
        "add_law", "set_law", "activate_law", "change_law", "add_law_variant",
        "set_state_owner", "add_state", "add_core", "add_claim", "add_homeland",
        "add_building", "build_building", "create_building", "add_technology",
        "set_country_type", "make_independent", "add_resource", "add_mine",
        "add_manpower", "set_population",
    )

    def test_no_arc_gifts_law_territory_industry_or_independence(self):
        catalog = _catalog()
        blob = "\n".join(_arc_text(arc) for arc in catalog["arcs"])
        blob += EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for pattern in self.GRANT_PATTERNS:
            self.assertIsNone(re.search(rf"(?<![a-z0-9_]){pattern}\s*=", blob),
                              f"found a prohibited grant: {pattern}")

    def test_winter_never_invents_famine_or_casualty(self):
        catalog = _catalog()
        blob = "\n".join(_arc_text(arc) for arc in catalog["arcs"])
        blob += EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for forbidden in ("famine", "starvation", "mass_die_off", "kill_population",
                          "add_population = {", "change_population"):
            self.assertNotIn(forbidden, blob.lower())

    def test_the_old_mainland_is_never_restored_for_free(self):
        catalog = _catalog()
        blob = "\n".join(_arc_text(arc) for arc in catalog["arcs"])
        blob += JOURNAL_PATH.read_text(encoding="utf-8-sig")
        for forbidden in ("add_state = ", "set_state_owner = ", "add_core = ",
                          "restore_qing", "recover_mainland", "reconquer"):
            self.assertNotIn(forbidden, blob)
        self.assertNotRegex(blob, r"c:CHI\s*\?=\s*this")

    def test_no_single_support_score_stands_in_for_governance(self):
        catalog = _catalog()
        blob = "\n".join(_arc_text(arc) for arc in catalog["arcs"]).lower()
        for forbidden in ("support_score", "loyalty_score", "island_support",
                          "court_support", "legitimacy_score", "nqg_support"):
            self.assertNotIn(forbidden, blob)

    def test_real_conditions_are_read_from_the_world(self):
        triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        joined = " ".join(triggers.split())
        for token in ("market_access", "government_legitimacy", "gold_reserves",
                      "is_building_type = building_government_administration",
                      "is_building_type = building_port", "has_law_or_variant",
                      "has_diplomatic_pact", "relations:root >= 20"):
            self.assertIn(token, joined, token)
        self.assertNotIn("relations_threshold:", joined)

    def test_opening_choices_disclose_the_real_one_time_fee(self):
        catalog = _catalog()
        for arc in catalog["arcs"]:
            opening = arc["events"][0]
            for option in opening["options"]:
                if option["key"] in ("defer", "withdraw"):
                    continue
                for lang, terms in (("en", ("filing fee", "annual gross income", "52", "100")),
                                    ("zh", ("立案费", "年总收入", "52", "100"))):
                    note = option["cost_note"][lang]
                    for term in terms:
                        self.assertIn(term, note, f"{opening['id']} {option['key']} {lang}")

    def test_winter_grain_choice_is_only_an_unanswered_request(self):
        catalog = _catalog()
        winter = _arc(catalog, "v03_nqg_winter_court")
        opening = winter["events"][0]
        request = next(o for o in opening["options"] if o["key"] == "grain_loan")
        for phrase in ("no grain", "or money", "no debt", "cannot settle"):
            self.assertIn(phrase, request["consequence_note"]["en"].lower())
        triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        winter_execution = _helper_body(triggers, "ywc_nqg_winter_route_execution_ready")
        self.assertNotIn("ywc_nqg_winter_loan_ready", winter_execution)
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        self.assertNotIn("add_goods", effects)
        self.assertNotIn("change_goods", effects)
        self.assertNotIn("add_treasury", _helper_body(effects, "ywc_nqg_winter_e1005_take_loan_terms"))
        for locale in ("english", "simp_chinese"):
            path = ROOT / "yongchang_world" / "localization" / locale / f"ywc_v03_country_nqg_l_{'english' if locale == 'english' else 'simp_chinese'}.yml"
            text = path.read_text(encoding="utf-8-sig")
            self.assertIn(".1000.grain_loan.consequence_tooltip", text)
            self.assertIn(".1005.take_loan_terms.consequence_tooltip", text)


class NqgObservationTest(unittest.TestCase):
    def test_six_month_observation_restarts_after_a_relapse(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for _, _, _, _, short in ARCS.values():
            body = _helper_body(effects, f"ywc_nqg_{short}_monthly_review")
            for token in ("days = 180", "six_months_complete", "ywc_nqg_" + short + "_observation_timer",
                          "ywc_nqg_" + short + "_reset_observation = yes"):
                self.assertIn(token, body, f"{short} {token}")

    def test_twelve_and_thirty_six_month_notices_exist(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for _, _, _, _, short in ARCS.values():
            body = _helper_body(effects, f"ywc_nqg_{short}_monthly_review")
            self.assertIn("days = 365", body, short)
            self.assertIn("days = 1095", body, short)

    def test_a_compromise_cannot_claim_the_established_result(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for slug, (_, _, _, _, short) in ARCS.items():
            slot = slug.replace("v03_nqg_", "")
            established = _helper_body(effects, f"ywc_nqg_{short}_close_as_established")
            self.assertIn(f"ywc_nqg_{short}_full_ready = yes", established)
            self.assertIn(f"ywc_v03_nqg_v03_nqg_{slot}_outcome value = 3", established)
            compromise = _helper_body(effects, f"ywc_nqg_{short}_close_as_compromise")
            self.assertIn(f"ywc_nqg_{short}_compromise_ready = yes", compromise)
            self.assertNotIn("_full_ready", compromise)
            self.assertIn(f"ywc_v03_nqg_v03_nqg_{slot}_outcome value = 2", compromise)

    def test_actual_route_closers_classify_settlement_and_withdrawal_exclusively(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for slug, (_, _, _, _, short) in ARCS.items():
            if short not in ("winter", "port"):
                continue
            item = _arc(_catalog(), slug)
            slot_name = "winter_court" if short == "winter" else "northern_port"
            slot = f"ywc_v03_nqg_v03_nqg_{slot_name}_outcome"
            start_var = f"ywc_v03_nqg_v03_nqg_{slot_name}_started"
            settlement = item["journals"][-1]
            first = item["journals"][0]
            for terminal, helper, expected in (("established", "established", 3), ("compromise", "compromise", 2), ("withdrawn", "breach", 1)):
                with self.subTest(arc=short, terminal=terminal):
                    tag = "NQG"
                    prefix = f"ywc_nqg_{short}"
                    vars = {start_var: 1, "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1,
                            f"{prefix}_route": 2, f"{prefix}_six_months_complete": 1}
                    vars[f"{prefix}_implementation_started"] = 1
                    if short == "winter": vars["ywc_nqg_winter_stage"] = 1008
                    if short == "port": vars["ywc_nqg_port_stage"] = 1025
                    world = NqgTerminalWorld(effects, {tag: vars})
                    world.run(f"{prefix}_close_as_{helper}", tag)
                    country = world.countries[tag]
                    self.assertEqual(country[slot], expected)
                    complete = _script_condition(world, settlement["goal"], tag)
                    fail = _script_condition(world, settlement["exit_conditions"], tag)
                    self.assertEqual((complete, fail), (terminal != "withdrawn", terminal == "withdrawn"))
                    self.assertFalse(complete and fail)
                    self.assertEqual((_script_condition(world, first["goal"], tag), _script_condition(world, first["exit_conditions"], tag)), (terminal != "withdrawn", terminal == "withdrawn"))
                    if short == "winter":
                        review = item["journals"][1]
                        self.assertEqual((_script_condition(world, review["goal"], tag), _script_condition(world, review["exit_conditions"], tag)), (terminal != "withdrawn", terminal == "withdrawn"))
                    self.assertEqual((country["ywc_v03_active_arc_count"], country["ywc_v03_visible_task_count"]), (0, 0))
                    world.run(f"{prefix}_close_as_breach", tag)
                    self.assertEqual(country[slot], expected)
                    self.assertEqual((country["ywc_v03_active_arc_count"], country["ywc_v03_visible_task_count"]), (0, 0))


class NqgLegacyTest(unittest.TestCase):
    def test_arcs_read_the_old_campaign_and_flavour_state(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for arc in _catalog()["arcs"]:
            short = ARCS[arc["slug"]][4]
            self.assertIn("ywc_campaign_nqg_c1_outcome", arc["legacy_links"], arc["slug"])
            self.assertIn("ywc_je_flavor_nqg_supply_1", arc["legacy_links"], arc["slug"])
            claim = _helper_body(effects, f"ywc_nqg_{short}_claim_arc")
            self.assertIn("ywc_campaign_nqg_c1_outcome", claim)
            self.assertIn("ywc_je_flavor_nqg_supply_1_resolved", claim)
            self.assertIn("ywc_v03_initialized", _arc_text(arc))

    def test_closers_release_the_shared_slots(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for slug in ARCS:
            slot = slug.replace("v03_nqg_", "")
            for marker in ("started", "settled", "outcome"):
                self.assertIn(f"ywc_v03_nqg_v03_nqg_{slot}_{marker}", effects)
        self.assertIn("name = ywc_v03_active_arc_count add = -1", effects)
        self.assertIn("name = ywc_v03_visible_task_count add = -1", effects)
        self.assertIn("clamp_variable", effects)


class NqgLifecycleRepairTest(unittest.TestCase):
    def test_legacy_bridge_is_absent_only_and_truthful_when_missing(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for short, slot in (("winter", "winter_court"), ("hunting", "hunting_rights"), ("port", "northern_port")):
            bridge = f"ywc_nqg_{short}_bridge_legacy"
            output = f"ywc_v03_nqg_v03_nqg_{slot}_outcome"
            for old in (1, 2, 3, 4):
                for new in (1, 2, 3):
                    world = PulseWorld(effects, {"NQG": {"ywc_campaign_nqg_c1_outcome": old, output: new}})
                    world.run(bridge, "NQG")
                    self.assertEqual(world.countries["NQG"]["ywc_campaign_nqg_c1_outcome"], old)
            world = PulseWorld(effects, {"NQG": {output: 2}})
            world.run(bridge, "NQG")
            self.assertEqual(world.countries["NQG"]["ywc_campaign_nqg_c1_outcome"], 2)

    def test_failed_stale_opening_choice_remains_retryable_and_does_not_advance(self):
        catalog = _catalog()
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for slug, event_id, short, option_key in (("v03_nqg_winter_court", 1000, "winter", "cap_stipend"),
                                                   ("v03_nqg_hunting_rights", 1010, "hunting", "co_manage"),
                                                   ("v03_nqg_northern_port", 1020, "port", "open_berths")):
            event = next(e for a in catalog["arcs"] if a["slug"] == slug for e in a["events"] if _number(e["id"]) == event_id)
            option = next(o for o in event["options"] if o["key"] == option_key)
            vars = {f"ywc_nqg_{short}_fee": 1000, "gold_reserves": 0}
            world = PulseWorld(effects, {"NQG": vars})
            world.execute(parse("effect = " + option["effect"])[0][2], "NQG")
            c = world.countries["NQG"]
            self.assertNotIn(f"ywc_nqg_{short}_fee_paid", c)
            self.assertNotIn(f"ywc_nqg_{short}_route", c)
            self.assertNotIn(f"ywc_nqg_{short}_st{event_id}_{option_key}", c)
            self.assertEqual(c[f"ywc_nqg_{short}_pending"], event_id)
            self.assertNotIn(f"ywc_nqg_{short}_stage", c)
            world.countries["NQG"]["gold_reserves"] = 100000
            world.execute(parse("effect = " + option["effect"])[0][2], "NQG")
            self.assertEqual(c[f"ywc_nqg_{short}_route"], {"winter": 1, "hunting": 1, "port": 1}[short])
            self.assertEqual(c[f"ywc_nqg_{short}_stage"], event_id + 1)
            self.assertEqual(world.treasury["NQG"], -1000)


class NqgWorldFactsRuntime(PulseWorld):
    """Run NQG authored predicates against explicit owned-state/building/law facts."""
    def __init__(self, countries):
        shared_fx = (ROOT / "yongchang_world/common/scripted_effects/ywc_v03_effects.txt").read_text(encoding="utf-8-sig")
        local_fx = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        super().__init__(shared_fx + "\n" + local_fx, countries)
        shared_tr = (ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt").read_text(encoding="utf-8-sig")
        local_tr = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        self.triggers = {key: body for key, _, body in parse(shared_tr + "\n" + local_tr)}
        self.states = None
        self.building = None
        self.partners = None
        self.active_journals = {tag:set() for tag in countries}
        self.terminal_journals = {tag:set() for tag in countries}
        self.completed_journals = {tag:set() for tag in countries}
        self.failed_journals = {tag:set() for tag in countries}
        self._execution_depth = 0
        self.journal_index = {j["id"]:j for arc in _catalog()["arcs"] for j in arc["journals"]}
        self.journal_started = {}
        for arc in _catalog()["arcs"]:
            short = ARCS[arc["slug"]][4]
            started = {"winter":"ywc_v03_nqg_v03_nqg_winter_court_started",
                       "hunting":"ywc_v03_nqg_v03_nqg_hunting_rights_started",
                       "port":"ywc_v03_nqg_v03_nqg_northern_port_started"}[short]
            for journal in arc["journals"]:
                self.journal_started[journal["id"]] = started

    def condition(self, node, tag):
        key, op, value = node
        variables = self.countries[tag]
        if key in self.triggers and value == "yes":
            return self.conditions(self.triggers[key], tag)
        if key == "any_scope_state":
            previous = self.states
            try:
                for state in variables.get("states", []):
                    self.states = state
                    if self.conditions(value, tag): return True
                return False
            finally: self.states = previous
        if key == "any_scope_building":
            if self.states is None: return False
            previous = self.building
            try:
                for building in self.states.get("buildings", []):
                    self.building = building
                    if self.conditions(value, tag): return True
                return False
            finally: self.building = previous
        if key == "any_country":
            previous = self.partners
            try:
                for partner, facts in self.countries.items():
                    if partner == tag: continue
                    self.partners = (partner, facts)
                    if self.conditions(value, tag): return True
                return False
            finally: self.partners = previous
        if key in ("owner", "is_owned_by"):
            if self.states is None: return False
            target = value if isinstance(value, str) else next((v for k, _, v in value if k == "who"), "ROOT")
            return self.states.get("owner") == (tag if target.lower() == "root" else target.removeprefix("c:"))
        if key == "is_building_type": return self.building is not None and self.building.get("type") == value
        if key == "is_building_group": return self.building is not None and self.building.get("group") == value
        if key == "occupancy":
            if self.building is None: return False
            return {">=": lambda a,b:a>=b, "=":lambda a,b:a==b, "<=":lambda a,b:a<=b}[op](float(self.building.get("occupancy",0)),float(value))
        if key == "building_has_goods_shortage":
            if self.building is None: return False
            return self.building.get("goods_shortage", False) == (value == "yes")
        if key == "market_access":
            if self.states is None: return False
            return {">=":lambda a,b:a>=b, "=":lambda a,b:a==b, "<=":lambda a,b:a<=b}[op](float(self.states.get("market_access",0)),float(value))
        if key == "government_legitimacy":
            left=float(variables.get(key,0));right=float(value)
            return {">=":lambda:left>=right, "=":lambda:left==right, "<=":lambda:left<=right}[op]()
        if key == "has_law_or_variant":
            law=value.removeprefix("law_type:")
            return law in variables.get("laws", [])
        if key == "has_diplomatic_pact":
            if self.partners is None:return False
            fields={name:field for name,_,field in value}
            target=fields.get("who","ROOT"); typ=fields.get("type")
            return typ in self.partners[1].get("diplomatic_pacts",[]) and target in ("ROOT",tag)
        if key == "gold_reserves" and self.partners is not None:
            left=float(self.partners[1].get("gold_reserves",0)); right=float(value)
            return {">=":lambda:left>=right, "=":lambda:left==right, "<=":lambda:left<=right}[op]()
        if key.startswith("relations:"):
            if self.partners is None: raise AssertionError("relations must be read inside any_country scope")
            left=float(self.partners[1].get("relations_to_root",self.partners[1].get("relations",0)))
            try: right=float(value)
            except ValueError: raise AssertionError("unsupported symbolic relation threshold: "+value)
            return {">=":lambda:left>=right, "=":lambda:left==right, "<=":lambda:left<=right}[op]()
        return super().condition(node, tag)

    def execute(self, nodes, tag):
        outer=self._execution_depth==0
        before={country:self.treasury[country] for country in self.treasury} if outer else None
        self._execution_depth+=1
        try:
            super().execute(nodes,tag)
        finally:
            self._execution_depth-=1
        if outer:
            for country,old in before.items():
                self.countries[country]["gold_reserves"] = float(self.countries[country].get("gold_reserves",0)) + self.treasury[country] - old

    def current_driver(self, arc, tag="NQG"):
        active=[journal for journal in arc["journals"] if journal["id"] in self.active_journals[tag]]
        self.assert_world(len(active)==1,"expected exactly one live driver for "+arc["slug"])
        return active[0]

    def enter(self, journal, tag="NQG"):
        self.assert_world(journal["id"] not in self.active_journals[tag] and journal["id"] not in self.terminal_journals[tag],
                          "journal cannot be activated twice: "+journal["id"])
        script=parse("root = "+journal["script"])[0][2]
        shown=next((body for key,_,body in script if key=="is_shown_when_inactive"),None)
        if shown is not None:
            self.assert_world(self.conditions(shown,tag), "journal is not actually shown: "+journal["id"])
        possible=next(body for key,_,body in script if key=="possible")
        self.assert_world(self.conditions(possible,tag), "journal not currently admissible: "+journal["id"])
        immediate=next((body for key,_,body in script if key=="immediate"),[])
        if immediate: self.execute(immediate,tag)
        self.active_journals[tag].add(journal["id"])

    def _refresh_journals(self, tag):
        for jid in tuple(self.active_journals[tag]):
            journal=self.journal_index[jid]
            goal=parse("condition = "+journal["goal"])[0][2]
            failure=parse("condition = "+journal["exit_conditions"])[0][2]
            is_goal=self.conditions(goal,tag); is_failure=self.conditions(failure,tag)
            self.assert_world(not (is_goal and is_failure),"JE goal and failure overlap: "+jid)
            if is_goal or is_failure:
                self.active_journals[tag].remove(jid)
                self.terminal_journals[tag].add(jid)
                (self.completed_journals if is_goal else self.failed_journals)[tag].add(jid)
        for _ in range(len(self.journal_index)):
            activated=False
            for jid,journal in self.journal_index.items():
                if jid in self.active_journals[tag] or jid in self.terminal_journals[tag]: continue
                if self.journal_started[jid] not in self.countries[tag]: continue
                script=parse("root = "+journal["script"])[0][2]
                shown=next((body for key,_,body in script if key=="is_shown_when_inactive"),None)
                possible=next(body for key,_,body in script if key=="possible")
                if shown is not None and self.conditions(shown,tag) and self.conditions(possible,tag):
                    immediate=next((body for key,_,body in script if key=="immediate"),[])
                    if immediate: self.execute(immediate,tag)
                    self.active_journals[tag].add(jid); activated=True
            if not activated: break


    @staticmethod
    def assert_world(value, message):
        if not value: raise AssertionError(message)

    def pulse(self, journal, tag="NQG"):
        self.assert_world(journal["id"] in self.active_journals[tag], "monthly pulse requires an actually active journal: "+journal["id"])
        goal=parse("condition = "+journal["goal"])[0][2]
        failure=parse("condition = "+journal["exit_conditions"])[0][2]
        self.assert_world(not self.conditions(goal,tag) and not self.conditions(failure,tag),
                          "completed/failed journals cannot pulse: "+journal["id"])
        pulse=next(body for key,_,body in parse("root = "+journal["script"])[0][2] if key=="on_monthly_pulse")
        effect=next(body for key,_,body in pulse if key=="effect")
        before=len(self.events)
        self.execute(effect,tag)
        delivered=self.events[before:]
        catalog=_catalog(); event_map={event["id"]:event for arc in catalog["arcs"] for event in arc["events"]}
        for event_tag,event_id in delivered:
            event=event_map[event_id]
            trigger=parse("condition = "+event["trigger"])[0][2]
            self.assert_world(self.conditions(trigger,event_tag),"authored event trigger failed: "+event_id)
            immediate=parse("effect = "+event["immediate"])[0][2]
            self.execute(immediate,event_tag)
        self._refresh_journals(tag)
        return [event_id for _,event_id in delivered]

    def choose(self,event_id,option_key,tag="NQG"):
        event=next(e for a in _catalog()["arcs"] for e in a["events"] if e["id"]==event_id)
        option=next(o for o in event["options"] if o["key"]==option_key)
        trigger=parse("condition = "+option.get("trigger","{ always = yes }") )[0][2]
        self.assert_world(self.conditions(trigger,tag),"option not currently legal: "+event_id+"/"+option_key)
        self.execute(parse("effect = "+option["effect"])[0][2],tag)
        self._refresh_journals(tag)


class NqgNoticeLaneTest(unittest.TestCase):
    def test_all_three_arcs_are_concurrently_admitted_under_recipient_cooldown(self):
        catalog=_catalog()
        facts={"ywc_v03_initialized":1,"ywc_v03_release_version":3,
               "ywc_v03_active_arc_count":0,"ywc_v03_visible_task_count":0,
               "yearly_gross_income":52000,"gold_reserves":20000,"bureaucracy":10,
               "net_fixed_income":1,"government_legitimacy":30,"laws":["law_mercantilism"],
               "states":[{"owner":"NQG","market_access":1.0,
                           "buildings":[{"group":"bg_logging","type":"building_port",
                                         "occupancy":0.8,"goods_shortage":False}]}]}
        world=NqgWorldFactsRuntime({"NQG":facts})
        firsts=[arc["journals"][0] for arc in catalog["arcs"]]
        for journal in firsts: world.enter(journal)
        c=world.countries["NQG"]
        self.assertEqual((c["ywc_v03_active_arc_count"],c["ywc_v03_visible_task_count"]),(3,3))
        deliveries=[]
        for index,journal in enumerate(firsts):
            if index: world.advance_months(3)
            deliveries.extend(world.pulse(journal))
        self.assertEqual(deliveries,["ywc_nqg.1000","ywc_nqg.1010","ywc_nqg.1020"])
        self.assertEqual((c["ywc_v03_active_arc_count"],c["ywc_v03_visible_task_count"]),(3,3))
        self.assertTrue(all(c.get(f"ywc_v03_nqg_v03_nqg_{name}_{suffix}")
                            for name,suffix in (("winter_court","started"),
                                                ("hunting_rights","started"),
                                                ("northern_port","started"))))

    def test_winter_and_port_full_routes_complete_through_actual_phases(self):
        catalog=_catalog()
        def world_for(arc_slug):
            facts={"ywc_v03_initialized":1,"ywc_v03_release_version":3,
                   "ywc_v03_active_arc_count":0,"ywc_v03_visible_task_count":0,
                   "yearly_gross_income":52000,"gold_reserves":20000,"bureaucracy":100,
                   "net_fixed_income":1,"government_legitimacy":35,"laws":["law_mercantilism"],
                   "states":[{"owner":"NQG","market_access":1.0,
                               "buildings":[{"group":"bg_logging","occupancy":0.8,"goods_shortage":False},
                                             {"type":"building_government_administration","occupancy":0.9,"goods_shortage":False},
                                             {"type":"building_barrack","occupancy":0.9,"goods_shortage":False},
                                             {"type":"building_port","occupancy":0.8,"goods_shortage":False},
                                             {"group":"bg_agriculture","occupancy":0.7,"goods_shortage":False}]}]}
            w=NqgWorldFactsRuntime({"NQG":facts}); arc=_arc(catalog,arc_slug); first=arc["journals"][0]; w.enter(first)
            def await_event(event_id):
                for _ in range(8):
                    w.advance_months(1)
                    if event_id in w.pulse(w.current_driver(arc)): return
                raise AssertionError("authored event not delivered: "+event_id)
            return w,arc,first,await_event
        w,arc,first,await_event=world_for("v03_nqg_winter_court")
        for event,choice in [(1000,"cap_stipend"),(1001,"cap_household"),(1002,"audit_districts"),(1003,"cap_soldiers")]:
            event_id=f"ywc_nqg.{event}"; await_event(event_id); w.choose(event_id,choice)
        self.assertIn("ywc_nqg_winter_stage",w.countries["NQG"])
        self.assertIn(arc["journals"][0]["id"], w.completed_journals["NQG"])
        self.assertEqual(w.current_driver(arc)["id"], arc["journals"][1]["id"])
        with self.assertRaises(AssertionError): w.pulse(arc["journals"][0])
        for event,choice in [(1004,"cap_market"),(1005,"refuse_loan_terms"),(1006,"publish_count"),(1007,"make_standing_rule")]:
            event_id=f"ywc_nqg.{event}"; await_event(event_id); w.choose(event_id,choice)
        self.assertIn(arc["journals"][1]["id"], w.completed_journals["NQG"])
        self.assertIn(arc["journals"][2]["id"], w.active_journals["NQG"])
        await_event("ywc_nqg.1008"); w.choose("ywc_nqg.1008","hold_buffer")
        self.assertIn(arc["journals"][2]["id"], w.active_journals["NQG"])
        self.assertIn(arc["journals"][2]["id"], w.active_journals["NQG"])
        await_event("ywc_nqg.1009"); w.choose("ywc_nqg.1009","settle_full")
        self.assertEqual(w.countries["NQG"]["ywc_v03_nqg_v03_nqg_winter_court_outcome"],3)
        self.assertTrue(_script_condition(w,arc["journals"][-1]["goal"],"NQG"))
        self.assertFalse(_script_condition(w,arc["journals"][-1]["exit_conditions"],"NQG"))
        w,arc,first,await_event=world_for("v03_nqg_northern_port")
        for event,choice in [(1020,"open_berths"),(1021,"by_tonnage"),(1022,"from_customs"),(1023,"renegotiate"),(1024,"recognise_duties")]:
            event_id=f"ywc_nqg.{event}"; await_event(event_id); w.choose(event_id,choice)
        for event,choice in [(1025,"keep_watch"),(1026,"renew")]:
            event_id=f"ywc_nqg.{event}"; await_event(event_id); w.choose(event_id,choice)
        self.assertIn(arc["journals"][0]["id"], w.completed_journals["NQG"])
        self.assertIn(arc["journals"][1]["id"], w.active_journals["NQG"])
        with self.assertRaises(AssertionError): w.pulse(arc["journals"][0])
        await_event("ywc_nqg.1027"); w.choose("ywc_nqg.1027","settle_full")
        self.assertEqual(w.countries["NQG"]["ywc_v03_nqg_v03_nqg_northern_port_outcome"],3)
        self.assertTrue(_script_condition(w,arc["journals"][-1]["goal"],"NQG"))
        self.assertFalse(_script_condition(w,arc["journals"][-1]["exit_conditions"],"NQG"))

        # Independent domestic winter route: district apportionment is a second real full strategy.
        w,arc,first,await_event=world_for("v03_nqg_winter_court")
        w.countries["NQG"]["states"][0]["buildings"].append({"group":"bg_agriculture","occupancy":0.7,"goods_shortage":False})
        for event,choice in [(1000,"local_share"),(1001,"cap_household"),(1002,"audit_districts"),(1003,"cap_soldiers")]:
            event_id=f"ywc_nqg.{event}"; await_event(event_id); w.choose(event_id,choice)
        for event,choice in [(1004,"cap_market"),(1005,"refuse_loan_terms"),(1006,"publish_count"),(1007,"make_standing_rule")]:
            event_id=f"ywc_nqg.{event}"; await_event(event_id); w.choose(event_id,choice)
        await_event("ywc_nqg.1008"); w.choose("ywc_nqg.1008","hold_buffer")
        await_event("ywc_nqg.1009"); w.choose("ywc_nqg.1009","settle_full")
        self.assertEqual(w.countries["NQG"]["ywc_v03_nqg_v03_nqg_winter_court_outcome"],3)

        # Hunting lease route requires current owned logging employment and produces a real full result.
        w=NqgWorldFactsRuntime({"NQG":{"ywc_v03_initialized":1,"ywc_v03_release_version":3,
          "ywc_v03_active_arc_count":0,"ywc_v03_visible_task_count":0,"yearly_gross_income":52000,
          "gold_reserves":20000,"bureaucracy":100,"net_fixed_income":1,"government_legitimacy":30,
          "laws":["law_mercantilism"],"states":[{"owner":"NQG","market_access":1.0,
          "buildings":[{"group":"bg_logging","occupancy":0.8,"goods_shortage":False},
                        {"type":"building_government_administration","occupancy":0.9,"goods_shortage":False}]}]}})
        arc=_arc(catalog,"v03_nqg_hunting_rights"); first=arc["journals"][0]; w.enter(first)
        def wait_hunting(event_id):
            for _ in range(8):
                w.advance_months(1)
                if event_id in w.pulse(w.current_driver(arc)): return
            raise AssertionError("authored event not delivered: "+event_id)
        wait_hunting("ywc_nqg.1010"); w.choose("ywc_nqg.1010","lease_dues")
        for event,choice in [(1011,"community_calendar"),(1012,"joint_assessment"),(1013,"favour_cutters"),(1014,"honour_old_marks")]:
            event_id=f"ywc_nqg.{event}"; wait_hunting(event_id); w.choose(event_id,choice)
        wait_hunting("ywc_nqg.1015"); w.choose("ywc_nqg.1015","settle_full")
        self.assertEqual(w.countries["NQG"]["ywc_v03_nqg_v03_nqg_hunting_rights_outcome"],3)

        # The port lease path checks a real foreign trade pact plus owned port capacity.
        pf={"ywc_v03_initialized":1,"ywc_v03_release_version":3,"ywc_v03_active_arc_count":0,
            "ywc_v03_visible_task_count":0,"yearly_gross_income":52000,"gold_reserves":20000,
            "bureaucracy":100,"net_fixed_income":1,"government_legitimacy":30,
            "laws":["law_mercantilism"],"states":[{"owner":"NQG","market_access":1.0,
            "buildings":[{"type":"building_port","occupancy":0.8,"goods_shortage":False}]}]}
        w=NqgWorldFactsRuntime({"NQG":pf,"ALLY":{"diplomatic_pacts":["trade_agreement"],"relations":50}})
        arc=_arc(catalog,"v03_nqg_northern_port"); first=arc["journals"][0]; w.enter(first)
        def wait_port(event_id):
            for _ in range(8):
                w.advance_months(1)
                if event_id in w.pulse(w.current_driver(arc)): return
            raise AssertionError("authored event not delivered: "+event_id)
        wait_port("ywc_nqg.1020"); w.choose("ywc_nqg.1020","exclusive_lease")
        for event,choice in [(1021,"by_call"),(1022,"levy_users"),(1023,"renegotiate"),(1024,"recognise_duties")]:
            event_id=f"ywc_nqg.{event}"; wait_port(event_id); w.choose(event_id,choice)
        for event,choice in [(1025,"keep_watch"),(1026,"renew")]:
            event_id=f"ywc_nqg.{event}"; wait_port(f"ywc_nqg.{event}"); w.choose(f"ywc_nqg.{event}",choice)
        wait_port("ywc_nqg.1027"); w.choose("ywc_nqg.1027","settle_full")
        self.assertEqual(w.countries["NQG"]["ywc_v03_nqg_v03_nqg_northern_port_outcome"],3)

    def test_stale_full_popup_rejects_and_reopens_after_fresh_whole_target_watch(self):
        catalog=_catalog(); arc=_arc(catalog,"v03_nqg_hunting_rights"); first=arc["journals"][0]
        facts={"ywc_v03_initialized":1,"ywc_v03_release_version":3,
               "ywc_v03_active_arc_count":0,"ywc_v03_visible_task_count":0,
               "yearly_gross_income":52000,"gold_reserves":20000,"bureaucracy":10,
               "net_fixed_income":1,"government_legitimacy":30,"laws":["law_mercantilism"],
               "states":[{"owner":"NQG","market_access":1.0,
                           "buildings":[{"group":"bg_logging","occupancy":0.8,"goods_shortage":False},
                                         {"type":"building_government_administration","occupancy":0.9,"goods_shortage":False}]}]}
        world=NqgWorldFactsRuntime({"NQG":facts}); world.enter(first); c=world.countries["NQG"]
        def wait_for(event_id,limit=8):
            for _ in range(limit):
                world.advance_months(1)
                if event_id in world.pulse(world.current_driver(arc)): return
            self.fail("authored event did not arrive: "+event_id)
        wait_for("ywc_nqg.1010"); world.choose("ywc_nqg.1010","co_manage")
        wait_for("ywc_nqg.1011"); world.choose("ywc_nqg.1011","rotation_rule")
        wait_for("ywc_nqg.1012"); world.choose("ywc_nqg.1012","joint_assessment")
        wait_for("ywc_nqg.1013"); world.choose("ywc_nqg.1013","favour_cutters")
        wait_for("ywc_nqg.1014"); world.choose("ywc_nqg.1014","honour_old_marks")
        wait_for("ywc_nqg.1015")
        self.assertIn("ywc_nqg_hunting_six_months_complete",c)
        # The popup is already consumed. The direct production callee sees a real route loss.
        c["states"][0]["buildings"][0]["occupancy"]=0.2
        world.run("ywc_nqg_hunting_close_as_established","NQG")
        self.assertNotIn("ywc_nqg_hunting_six_months_complete",c)
        self.assertEqual(c.get("ywc_nqg_hunting_pending"),1015)
        self.assertNotIn("ywc_nqg_hunting_any_outcome",c)
        # Recovery does not recover old maturity: keep the selected full target and earn a new 180d.
        c["states"][0]["buildings"][0]["occupancy"]=0.8
        for _ in range(7): world.advance_months(1); world.pulse(world.current_driver(arc))
        self.assertIn("ywc_nqg_hunting_six_months_complete",c)
        self.assertEqual(c.get("ywc_nqg_hunting_limited_target",0),0)
        world.choose("ywc_nqg.1015","settle_full")
        self.assertEqual(c["ywc_v03_nqg_v03_nqg_hunting_rights_outcome"],3)
        self.assertTrue(_script_condition(world,arc["journals"][-1]["goal"],"NQG"))
        self.assertFalse(_script_condition(world,arc["journals"][-1]["exit_conditions"],"NQG"))
        with self.assertRaises(AssertionError): world.pulse(first)

    def test_recovery_clears_old_notice_epoch_and_a_later_loss_gets_a_new_12_month_notice(self):
        arc=_arc(_catalog(),"v03_nqg_hunting_rights"); first=arc["journals"][0]
        facts={"ywc_v03_initialized":1,"ywc_v03_release_version":3,
               "ywc_v03_active_arc_count":0,"ywc_v03_visible_task_count":0,
               "yearly_gross_income":52000,"gold_reserves":10000,"bureaucracy":10,
               "net_fixed_income":1,"government_legitimacy":30,"laws":["law_mercantilism"],
               "states":[{"owner":"NQG","market_access":1.0,
                           "buildings":[{"group":"bg_logging","occupancy":0.7,"goods_shortage":False}]}]}
        world=NqgWorldFactsRuntime({"NQG":facts}); world.enter(first)
        self.assertEqual(world.pulse(world.current_driver(arc)),["ywc_nqg.1010"])
        world.choose("ywc_nqg.1010","co_manage")
        c=world.countries["NQG"]; c["states"][0]["buildings"][0]["occupancy"]=0.2
        world.advance_months(1); world.pulse(world.current_driver(arc))
        self.assertIn("ywc_nqg_hunting_blocked_timer_started",c)
        first_notice=False
        for _ in range(14):
            world.advance_months(1); delivered=world.pulse(world.current_driver(arc))
            if "ywc_nqg.1015" in delivered and "ywc_nqg_hunting_notice12_open" in c:
                first_notice=True; world.choose("ywc_nqg.1015","acknowledge_12_month_notice"); break
            if "ywc_nqg.1011" in delivered: world.choose("ywc_nqg.1011","defer")
        self.assertTrue(first_notice)
        self.assertIn("ywc_nqg_hunting_blocked_12_delivered",c)
        c["states"][0]["buildings"][0]["occupancy"]=0.7
        delivered=[]
        for _ in range(4):
            world.advance_months(1); delivered=world.pulse(world.current_driver(arc))
            if "ywc_nqg.1011" in delivered: world.choose("ywc_nqg.1011","rotation_rule"); break
        self.assertNotIn("ywc_nqg_hunting_blocked_12_delivered",c)
        self.assertNotIn("ywc_nqg_hunting_notice12_open",c)
        c["states"][0]["buildings"][0]["occupancy"]=0.2
        world.advance_months(1); world.pulse(world.current_driver(arc))
        self.assertIn("ywc_nqg_hunting_blocked_timer_started",c)
        second_notice=False
        for _ in range(14):
            world.advance_months(1); delivered=world.pulse(world.current_driver(arc))
            if "ywc_nqg.1015" in delivered and "ywc_nqg_hunting_notice12_open" in c:
                second_notice=True
                self.assertIn("ywc_nqg_hunting_blocked_12_delivered",c)
                world.choose("ywc_nqg.1015","acknowledge_12_month_notice")
                break
            if "ywc_nqg.1012" in delivered: world.choose("ywc_nqg.1012","defer")
        self.assertTrue(second_notice)
        self.assertEqual(c.get("ywc_nqg_hunting_pending"),1012)

    def test_hunting_real_defer_queue_does_not_starve_12_and_36_month_notices(self):
        catalog=_catalog(); arc=_arc(catalog,"v03_nqg_hunting_rights"); first=arc["journals"][0]
        facts={"ywc_v03_initialized":1,"ywc_v03_release_version":3,
               "ywc_v03_active_arc_count":0,"ywc_v03_visible_task_count":0,
               "yearly_gross_income":52000,"gold_reserves":10000,"bureaucracy":10,
               "net_fixed_income":1,"government_legitimacy":30,
               "laws":["law_mercantilism"],
               "states":[{"owner":"NQG","market_access":1.0,
                           "buildings":[{"group":"bg_logging","occupancy":0.7,"goods_shortage":False}]}]}
        world=NqgWorldFactsRuntime({"NQG":facts})
        world.enter(first)
        self.assertEqual(world.countries["NQG"]["ywc_v03_active_arc_count"],1)
        # The entry, fee and route are earned through the actual JE, event pulse and option effect.
        self.assertEqual(world.pulse(world.current_driver(arc)),["ywc_nqg.1010"])
        world.choose("ywc_nqg.1010","co_manage")
        self.assertEqual(world.treasury["NQG"],-1000)
        self.assertEqual(world.countries["NQG"]["ywc_nqg_hunting_route"],1)
        # Reach the actual next phase, then defer the current ordinary event repeatedly.
        for _ in range(3): world.advance_months(1); world.pulse(world.current_driver(arc))
        self.assertEqual(world.events[-1][1],"ywc_nqg.1011")
        world.choose("ywc_nqg.1011","rotation_rule")
        for _ in range(3): world.advance_months(1); world.pulse(world.current_driver(arc))
        self.assertEqual(world.events[-1][1],"ywc_nqg.1012")
        world.choose("ywc_nqg.1012","defer")
        c=world.countries["NQG"]
        self.assertEqual(c["ywc_nqg_hunting_pending"],1012)
        # Actual staffed logging occupancy is lost after payment; no synthetic readiness flag is used.
        c["states"][0]["buildings"][0]["occupancy"]=0.2
        world.advance_months(1); world.pulse(world.current_driver(arc))
        self.assertIn("ywc_nqg_hunting_blocked_timer_started",c)
        seen=[]
        for _ in range(43):
            world.advance_months(1)
            delivered=world.pulse(world.current_driver(arc))
            seen.extend(delivered)
            if delivered==["ywc_nqg.1015"] and "ywc_nqg_hunting_notice12_open" in c:
                self.assertIn("ywc_nqg_hunting_blocked_12_delivered",c)
                world.choose("ywc_nqg.1015","acknowledge_12_month_notice")
                self.assertEqual(c.get("ywc_nqg_hunting_pending"),1012,repr(c))
            elif delivered==["ywc_nqg.1015"] and "ywc_nqg_hunting_notice36_open" in c:
                # Choose the real lower target only after its current world facts qualify.
                c["states"][0]["buildings"][0]["occupancy"]=0.4
                world.choose("ywc_nqg.1015","start_36_month_limited_remedy")
                self.assertEqual(c.get("ywc_nqg_hunting_pending"),1012)
                break
            elif delivered==["ywc_nqg.1012"]:
                world.choose("ywc_nqg.1012","defer")
        self.assertEqual(seen.count("ywc_nqg.1015"),2)
        self.assertLess(seen.index("ywc_nqg.1015"),len(seen)-1)
        self.assertIn("ywc_nqg_hunting_limited_target",c)
        self.assertNotIn("ywc_nqg_hunting_six_months_complete",c)
        final_event=next(e for e in arc["events"] if e["id"]=="ywc_nqg.1015")
        full_option=next(o for o in final_event["options"] if o["key"]=="settle_full")
        limited_option=next(o for o in final_event["options"] if o["key"]=="settle_compromise")
        self.assertFalse(_script_condition(world,full_option["trigger"],"NQG"))
        self.assertFalse(_script_condition(world,limited_option["trigger"],"NQG"))
        # The limited action earns a fresh watch; only actual elapsed pulses mature it.
        final=[]
        for _ in range(10):
            world.advance_months(1)
            final.extend(world.pulse(world.current_driver(arc)))
            if "ywc_nqg.1015" in final and "ywc_nqg_hunting_six_months_complete" in c:
                break
        self.assertIn("ywc_nqg.1015",final)
        self.assertIn("ywc_nqg_hunting_six_months_complete",c)
        self.assertFalse(_script_condition(world,full_option["trigger"],"NQG"))
        self.assertTrue(_script_condition(world,limited_option["trigger"],"NQG"))
        world.choose("ywc_nqg.1015","settle_compromise")
        self.assertEqual(c["ywc_v03_nqg_v03_nqg_hunting_rights_outcome"],2)
        self.assertEqual(c["ywc_v03_active_arc_count"],0)
        self.assertNotIn("ywc_nqg_hunting_pending",c)
        self.assertNotIn("ywc_nqg_hunting_blocked_12_delivered",c)  # recovery clears the completed failure epoch


class NqgReviewFixTest(unittest.TestCase):
    def _world(self, country_overrides=None):
        facts={"ywc_v03_initialized":1,"ywc_v03_release_version":3,
               "ywc_v03_active_arc_count":0,"ywc_v03_visible_task_count":0,
               "yearly_gross_income":52000,"gold_reserves":20000,"bureaucracy":100,
               "net_fixed_income":1,"government_legitimacy":35,"laws":["law_mercantilism"],
               "states":[{"owner":"NQG","market_access":1.0,"buildings":[
                   {"group":"bg_logging","occupancy":0.8,"goods_shortage":False},
                   {"type":"building_government_administration","occupancy":0.9,"goods_shortage":False},
                   {"type":"building_port","occupancy":0.8,"goods_shortage":False},
                   {"group":"bg_agriculture","occupancy":0.7,"goods_shortage":False}]}]}
        facts.update(country_overrides or {})
        return NqgWorldFactsRuntime({"NQG":facts})

    def _await(self, world, arc, event_id):
        for _ in range(8):
            world.advance_months(1)
            if event_id in world.pulse(world.current_driver(arc)):
                return
        self.fail("actual event was not dispatched: "+event_id)

    def test_followup_fees_are_atomic_and_retryable_at_actual_cash(self):
        catalog=_catalog(); winter=_arc(catalog,"v03_nqg_winter_court")
        world=self._world(); world.enter(winter["journals"][0])
        self._await(world,winter,"ywc_nqg.1000"); world.choose("ywc_nqg.1000","cap_stipend")
        self._await(world,winter,"ywc_nqg.1001"); world.choose("ywc_nqg.1001","cap_household")
        self._await(world,winter,"ywc_nqg.1002"); world.choose("ywc_nqg.1002","audit_districts")
        self._await(world,winter,"ywc_nqg.1003")
        option=next(o for o in next(e for e in winter["events"] if e["id"]=="ywc_nqg.1003")["options"] if o["key"]=="keep_full_guard")
        self.assertEqual(world.countries["NQG"]["ywc_nqg_winter_half_fee"],500)
        world.countries["NQG"]["gold_reserves"]=0
        world.execute(parse("effect = "+option["effect"])[0][2],"NQG")
        c=world.countries["NQG"]
        self.assertNotIn("ywc_nqg_winter_st1003_keep_full_guard",c)
        self.assertEqual(c["ywc_nqg_winter_stage"],1003)
        self.assertEqual(c["ywc_nqg_winter_pending"],1003)
        self.assertEqual(world.treasury["NQG"],-1000)
        c["gold_reserves"]=20000
        world.execute(parse("effect = "+option["effect"])[0][2],"NQG")
        self.assertEqual(c["ywc_nqg_winter_stage"],1004)
        self.assertEqual(c["ywc_nqg_winter_pending"],1004)
        self.assertEqual(c["gold_reserves"],19500)
        self.assertEqual(world.treasury["NQG"],-1500)

        port=_arc(catalog,"v03_nqg_northern_port")
        world=self._world(); world.enter(port["journals"][0])
        for event_id,choice in [("ywc_nqg.1020","open_berths"),("ywc_nqg.1021","by_tonnage")]:
            self._await(world,port,event_id); world.choose(event_id,choice)
        for event_id,choice in [("ywc_nqg.1022","from_customs")]:
            self._await(world,port,event_id)
            option=next(o for o in next(e for e in port["events"] if e["id"]==event_id)["options"] if o["key"]==choice)
            c=world.countries["NQG"]; c["gold_reserves"]=0
            world.execute(parse("effect = "+option["effect"])[0][2],"NQG")
            marker="ywc_nqg_port_st1022_from_customs"
            self.assertNotIn(marker,c); self.assertEqual(c["ywc_nqg_port_stage"],1022)
            self.assertEqual(c["ywc_nqg_port_pending"],1022); self.assertEqual(world.treasury["NQG"],-1000)
            c["gold_reserves"]=20000; world.execute(parse("effect = "+option["effect"])[0][2],"NQG")
            self.assertIn(marker,c); self.assertEqual(c["ywc_nqg_port_stage"],1023)
            self.assertEqual(c["gold_reserves"],19000); self.assertEqual(world.treasury["NQG"],-2000)
        self._await(world,port,"ywc_nqg.1023"); world.choose("ywc_nqg.1023","renegotiate")
        self._await(world,port,"ywc_nqg.1024"); world.choose("ywc_nqg.1024","recognise_duties")
        self._await(world,port,"ywc_nqg.1025")
        option=next(o for o in next(e for e in port["events"] if e["id"]=="ywc_nqg.1025")["options"] if o["key"]=="keep_watch")
        c=world.countries["NQG"]; c["gold_reserves"]=0
        world.execute(parse("effect = "+option["effect"])[0][2],"NQG")
        marker="ywc_nqg_port_st1025_keep_watch"
        self.assertNotIn(marker,c); self.assertEqual(c["ywc_nqg_port_stage"],1025)
        self.assertEqual(c["ywc_nqg_port_pending"],1025); self.assertEqual(world.treasury["NQG"],-2000)
        c["gold_reserves"]=20000; world.execute(parse("effect = "+option["effect"])[0][2],"NQG")
        self.assertIn(marker,c); self.assertEqual(c["ywc_nqg_port_stage"],1026)
        self.assertEqual(c["gold_reserves"],19000); self.assertEqual(world.treasury["NQG"],-3000)

    def test_delivered_defer_keeps_12_36_epoch_and_observation_unearned_for_all_arcs(self):
        cases=(
            ("v03_nqg_winter_court","ywc_nqg.1000","cap_stipend","ywc_nqg.1001","acknowledge_12_month_notice","ywc_nqg_winter"),
            ("v03_nqg_hunting_rights","ywc_nqg.1010","co_manage","ywc_nqg.1011","acknowledge_12_month_notice","ywc_nqg_hunting"),
            ("v03_nqg_northern_port","ywc_nqg.1020","open_berths","ywc_nqg.1021","acknowledge_12_month_notice","ywc_nqg_port"),
        )
        for slug,opening,choice,deferred,ack,prefix in cases:
            with self.subTest(arc=slug):
                arc=_arc(_catalog(),slug); world=self._world(); world.enter(arc["journals"][0])
                self.assertEqual(world.pulse(world.current_driver(arc)),[opening]); world.choose(opening,choice)
                self._await(world,arc,deferred); world.choose(deferred,"defer")
                c=world.countries["NQG"]; stage=f"{prefix}_stage"; marker=f"{prefix}_deferred_event"
                self.assertEqual(c[marker],_number(deferred)); self.assertEqual(c[stage],_number(deferred))
                ordinary=0; saw12=saw36=False
                for _ in range(43):
                    world.advance_months(1); delivered=world.pulse(world.current_driver(arc))
                    if delivered==[deferred]:
                        ordinary+=1; world.choose(deferred,"defer")
                    elif delivered and delivered[-1].endswith((".1009",".1015",".1027")):
                        if c.get(f"{prefix}_notice12_open"):
                            saw12=True; world.choose(delivered[-1],ack)
                        elif c.get(f"{prefix}_notice36_open"):
                            saw36=True; break
                self.assertTrue(saw12,"12-month notice was not actually delivered")
                self.assertTrue(saw36,"36-month notice was not actually delivered")
                self.assertGreaterEqual(ordinary,8)
                self.assertEqual(c[stage],_number(deferred))
                self.assertEqual(c.get(f"{prefix}_deferred_event"),_number(deferred))
                self.assertNotIn(f"{prefix}_six_months_complete",c)

    def _earn_limited_watch(self, slug):
        spec={
            "v03_nqg_winter_court":("ywc_nqg.1000","cap_stipend","ywc_nqg.1001","ywc_nqg.1009","ywc_nqg_winter","building_government_administration",0.65),
            "v03_nqg_hunting_rights":("ywc_nqg.1010","co_manage","ywc_nqg.1011","ywc_nqg.1015","ywc_nqg_hunting","bg_logging",0.4),
            "v03_nqg_northern_port":("ywc_nqg.1020","open_berths","ywc_nqg.1021","ywc_nqg.1027","ywc_nqg_port","building_port",0.45),
        }
        opening,choice,deferred,final,prefix,building,lower=spec[slug]
        arc=_arc(_catalog(),slug); world=self._world(); world.enter(arc["journals"][0])
        self.assertEqual(world.pulse(world.current_driver(arc)),[opening]); world.choose(opening,choice)
        self._await(world,arc,deferred); world.choose(deferred,"defer")
        c=world.countries["NQG"]
        for _ in range(50):
            world.advance_months(1); delivered=world.pulse(world.current_driver(arc))
            if delivered==[deferred]:
                world.choose(deferred,"defer")
            elif delivered==[final] and c.get(prefix+"_notice12_open"):
                world.choose(final,"acknowledge_12_month_notice")
            elif delivered==[final] and c.get(prefix+"_notice36_open"):
                for state in c["states"]:
                    for b in state.get("buildings",[]):
                        if b.get("type")==building or b.get("group")==building: b["occupancy"]=lower
                world.choose(final,"start_36_month_limited_remedy")
                self.assertIn(prefix+"_limited_target",c)
                return world,arc,prefix,deferred,final,building,lower
        self.fail("actual 36-month lower remedy was not delivered: "+slug)

    def test_actual_limited_terminal_closes_only_the_admitted_phase(self):
        for slug,steps,terminal_stage,unadmitted in (
            ("v03_nqg_winter_court",(("ywc_nqg.1001","cap_exempt_clan"),("ywc_nqg.1002","pay_by_register")),1003,"ywc_je_v03_nqg_winter_review"),
            ("v03_nqg_northern_port",(("ywc_nqg.1021","by_tonnage"),("ywc_nqg.1022","levy_users")),1023,"ywc_je_v03_nqg_northern_port_settlement"),
        ):
            with self.subTest(arc=slug):
                world,arc,prefix,deferred,final,building,lower=self._earn_limited_watch(slug)
                c=world.countries["NQG"]
                self._await(world,arc,deferred)
                world.choose(deferred,steps[0][1])
                self._await(world,arc,steps[1][0]); world.choose(steps[1][0],steps[1][1])
                self.assertEqual(c[prefix+"_stage"],terminal_stage)
                for _ in range(10):
                    world.advance_months(1); delivered=world.pulse(world.current_driver(arc))
                    if final in delivered: break
                self.assertIn(final,delivered,"fresh limited watch did not dispatch real terminal event")
                world.choose(final,"settle_compromise")
                start=arc["journals"][0]["id"]
                self.assertIn(start,world.completed_journals["NQG"])
                self.assertNotIn(start,world.active_journals["NQG"])
                self.assertNotIn(start,world.failed_journals["NQG"])
                self.assertNotIn(unadmitted,world.active_journals["NQG"])
                self.assertNotIn(unadmitted,world.completed_journals["NQG"])
                self.assertEqual(c["ywc_v03_active_arc_count"],0)

    def test_superseded_old_defer_keeps_lower_watch_and_real_loss_restarts_remedy_clock(self):
        specs=(
            ("v03_nqg_winter_court","ywc_nqg.1001","ywc_nqg.1009","ywc_nqg_winter","building_government_administration",0.2),
            ("v03_nqg_hunting_rights","ywc_nqg.1011","ywc_nqg.1015","ywc_nqg_hunting","bg_logging",0.2),
            ("v03_nqg_northern_port","ywc_nqg.1021","ywc_nqg.1027","ywc_nqg_port","building_port",0.2),
        )
        for slug,deferred,final,prefix,building,lost in specs:
            with self.subTest(arc=slug):
                world,arc,prefix,deferred,final,building,lower=self._earn_limited_watch(slug)
                c=world.countries["NQG"]
                # The same ordinary popup remains queued, but its pre-remedy defer is superseded.
                self._await(world,arc,deferred); world.choose(deferred,"defer")
                self.assertEqual(c.get(prefix+"_deferred_event_is_superseded"),1)
                for _ in range(15):
                    world.advance_months(1); delivered=world.pulse(world.current_driver(arc))
                    if delivered==[deferred]: world.choose(deferred,"defer")
                    self.assertNotIn(prefix+"_blocked_timer_started",c)
                self.assertIn(prefix+"_six_months_complete",c)
                arc_suffix={"v03_nqg_winter_court":"v03_nqg_winter_court","v03_nqg_hunting_rights":"v03_nqg_hunting_rights","v03_nqg_northern_port":"v03_nqg_northern_port"}[slug]
                self.assertNotIn("ywc_v03_nqg_"+arc_suffix+"_settled",c)
                # Actual loss of the new lower target overrides the superseded-defer exemption.
                for state in c["states"]:
                    for b in state.get("buildings",[]):
                        if b.get("type")==building or b.get("group")==building: b["occupancy"]=lost
                world.advance_months(1); world.pulse(world.current_driver(arc))
                self.assertIn(prefix+"_blocked_timer_started",c)
                self.assertNotIn(prefix+"_six_months_complete",c)
                self.assertNotIn(prefix+"_observation_timer",c)
                saw12=saw36=False
                for _ in range(45):
                    world.advance_months(1); delivered=world.pulse(world.current_driver(arc))
                    if delivered==[final] and c.get(prefix+"_notice12_open"):
                        saw12=True; world.choose(final,"acknowledge_12_month_notice")
                    elif delivered==[final] and c.get(prefix+"_notice36_open"):
                        saw36=True
                        for state in c["states"]:
                            for b in state.get("buildings",[]):
                                if b.get("type")==building or b.get("group")==building: b["occupancy"]=lower
                        world.choose(final,"start_36_month_limited_remedy")
                        break
                self.assertTrue(saw12,"lower-target loss did not deliver 12-month remedy notice")
                self.assertTrue(saw36,"lower-target loss did not deliver 36-month remedy notice")
                world.advance_months(1); world.pulse(world.current_driver(arc))
                self.assertIn(prefix+"_observation_started",c)
                self.assertIn(prefix+"_observation_timer",c)
                self.assertNotIn(prefix+"_blocked_timer_started",c)

    def test_partner_reserves_relations_and_player_treasury_are_scoped_facts(self):
        world=self._world()
        world.countries["ALLY"]={"diplomatic_pacts":["alliance"],"relations_to_root":19,"gold_reserves":0}
        trigger=parse("condition = { ywc_nqg_winter_loan_ready = yes }")[0][2]
        self.assertFalse(world.conditions(trigger,"NQG"))
        world.countries["ALLY"]["gold_reserves"]=12000
        self.assertFalse(world.conditions(trigger,"NQG"))
        world.countries["ALLY"]["relations_to_root"]=20
        self.assertTrue(world.conditions(trigger,"NQG"))
        with self.assertRaises(AssertionError):
            world.conditions(parse("condition = { relations:root >= relations_threshold:cordial }")[0][2],"NQG")
        self.assertEqual(world.countries["NQG"]["gold_reserves"],20000)
        world.execute(parse("effect = { add_treasury = { value = 1000 multiply = -1 } }")[0][2],"NQG")
        self.assertEqual(world.treasury["NQG"],-1000)
        self.assertEqual(world.countries["NQG"]["gold_reserves"],19000)


if __name__ == "__main__":
    unittest.main()
