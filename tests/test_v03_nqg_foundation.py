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
            for journal in arc["journals"]:
                self.assertRegex(journal["id"], r"^ywc_je_v03_nqg_[a-z0-9_]+$")
                self.assertIsNone(re.search(r"(?m)^\s*(?:complete|fail)\s*=", journal["script"]),
                                  journal["id"])
                self.assertIn("var:ywc_v03_active_arc_count < 3", journal["script"])
                self.assertIn("var:ywc_v03_visible_task_count < 6", journal["script"])
                self.assertIn("ywc_v03_has_capacity = yes", journal["script"])
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
                      "has_diplomatic_pact", "relations_threshold"):
            self.assertIn(token, joined, token)


class NqgObservationTest(unittest.TestCase):
    def test_six_month_observation_restarts_after_a_relapse(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        for _, _, _, _, short in ARCS.values():
            body = _helper_body(effects, f"ywc_nqg_{short}_monthly_review")
            for token in ("months = 6", "six_months_complete", "ywc_nqg_" + short + "_observation_timer",
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


if __name__ == "__main__":
    unittest.main()
