"""Offline contract checks for the KOR foundation arcs.

Two foundation arcs extend the accepted M1 military-accounts prototype:
  v03_kor_school_factions   (ywc_kor.1010-1017, 3 journal entries)
  v03_kor_controlled_ports  (ywc_kor.1018-1023, 1 journal entry)

Static/repository-level checks only: no engine, no save games, no UI.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

CATALOG_PATH = ROOT / "data/content/v03/countries/kor.json"
EFFECTS_PATH = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_kor_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_kor_triggers.txt"
REGISTRY_PATH = ROOT / "data/content/v03/id_registry.json"
MOD = ROOT / "yongchang_world"

SCHOOL_SLUG = "v03_kor_school_factions"
PORTS_SLUG = "v03_kor_controlled_ports"
SCHOOL_EVENTS = [f"ywc_kor.{number}" for number in range(1010, 1018)]
PORTS_EVENTS = [f"ywc_kor.{number}" for number in range(1018, 1024)]
SCHOOL_JES = [
    "ywc_je_v03_kor_school_funding",
    "ywc_je_v03_kor_school_appointments",
    "ywc_je_v03_kor_school_review",
]
PORTS_JES = ["ywc_je_v03_kor_controlled_ports"]

REQUIRED_EFFECTS = [
    "ywc_kor_choose_school_coop",
    "ywc_kor_choose_school_office",
    "ywc_kor_choose_school_limited",
    "ywc_kor_choose_school_employer_university",
    "ywc_kor_choose_school_employer_office",
    "ywc_kor_close_school_as_established",
    "ywc_kor_close_school_as_compromise",
    "ywc_kor_close_school_as_breach",
    "ywc_kor_school_finalize",
    "ywc_kor_school_record_old_account",
    "ywc_kor_school_reset_observation",
    "ywc_kor_school_monthly_review",
    "ywc_kor_choose_port_designated",
    "ywc_kor_choose_port_general",
    "ywc_kor_choose_port_shore",
    "ywc_kor_close_ports_as_established",
    "ywc_kor_close_ports_as_compromise",
    "ywc_kor_close_ports_as_breach",
    "ywc_kor_ports_authorize_review",
    "ywc_kor_ports_record_prior_outcomes",
    "ywc_kor_ports_record_school_route",
    "ywc_kor_ports_reset_observation",
    "ywc_kor_ports_monthly_review",
]

REQUIRED_TRIGGERS = [
    "ywc_kor_school_can_pay",
    "ywc_kor_school_coop_ready",
    "ywc_kor_school_office_ready",
    "ywc_kor_school_limited_ready",
    "ywc_kor_school_university_ready",
    "ywc_kor_school_route_execution_ready",
    "ywc_kor_school_full_ready",
    "ywc_kor_school_old_contracts_clear",
    "ywc_kor_ports_trade_permitted",
    "ywc_kor_ports_broad_trade_law",
    "ywc_kor_ports_has_staffed_port",
    "ywc_kor_ports_can_pay",
    "ywc_kor_ports_designated_ready",
    "ywc_kor_ports_general_ready",
    "ywc_kor_ports_shore_ready",
    "ywc_kor_ports_current_route_ready",
    "ywc_kor_ports_full_ready",
    "ywc_kor_ports_auditor_ready",
    "ywc_kor_ports_old_contracts_clear",
]


def _arc(catalog, slug):
    matches = [arc for arc in catalog["arcs"] if arc["slug"] == slug]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one arc {slug}, found {len(matches)}")
    return matches[0]


def _arc_text(arc):
    parts = []
    for journal in arc["journals"]:
        parts += [journal["script"], journal["goal"], journal["exit_conditions"]]
    for event in arc["events"]:
        parts += [event["trigger"], event["immediate"]]
        for option in event["options"]:
            parts.append(option["effect"])
            if option.get("trigger"):
                parts.append(option["trigger"])
    return "\n".join(parts)


def _definitions():
    defined = set()
    for folder in ("common/scripted_effects", "common/scripted_triggers"):
        for path in sorted((MOD / folder).rglob("*.txt")):
            text = path.read_text(encoding="utf-8-sig")
            defined.update(re.findall(r"(?m)^([a-z_0-9]+)\s*=\s*\{", text))
    return defined


def _helper_body(text, name):
    try:
        start = text.index(f"\n{name} = {{")
    except ValueError:
        raise AssertionError(f"scripted definition missing: {name}") from None
    end = text.find("\n}", start)
    return text[start:end if end != -1 else len(text)]


class KorFoundationContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        cls.triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        cls.school = _arc(cls.catalog, SCHOOL_SLUG)
        cls.ports = _arc(cls.catalog, PORTS_SLUG)

    def test_arcs_are_registered_with_their_reserved_event_ranges(self):
        ranges = {
            (row["catalog_key"], row["slug"]): (row["start"], row["end"])
            for row in self.registry["arc_ranges"]
        }
        self.assertEqual(ranges[("country_kor", SCHOOL_SLUG)], (1010, 1017))
        self.assertEqual(ranges[("country_kor", PORTS_SLUG)], (1018, 1023))
        self.assertEqual([row["id"] for row in self.school["events"]], SCHOOL_EVENTS)
        self.assertEqual([row["id"] for row in self.ports["events"]], PORTS_EVENTS)
        self.assertEqual([row["id"] for row in self.school["journals"]], SCHOOL_JES)
        self.assertEqual([row["id"] for row in self.ports["journals"]], PORTS_JES)

    def test_foundation_arcs_keep_the_locked_card_shape(self):
        for arc in (self.school, self.ports):
            self.assertEqual(arc["era"], "foundation")
            self.assertEqual(arc["depends_on"], ["v03_kor_military_accounts"])
            self.assertTrue(arc["outcomes"])
            self.assertTrue(arc["legacy_links"])
            for event in arc["events"]:
                self.assertTrue(event["title"]["zh"] and event["title"]["en"], event["id"])
                self.assertTrue(event["desc"]["zh"] and event["desc"]["en"], event["id"])
                self.assertGreaterEqual(len(event["options"]), 2, event["id"])
                for option in event["options"]:
                    self.assertEqual(set(option["cost_note"]), {"zh", "en"}, option["key"])
                    self.assertEqual(set(option["consequence_note"]), {"zh", "en"}, option["key"])
            for journal in arc["journals"]:
                body = journal["script"].strip()[1:-1]
                self.assertIsNone(
                    re.search(r"(?<![a-z0-9_])(?:complete|fail)\s*=", body), journal["id"]
                )

    def test_required_foundation_scripts_are_defined(self):
        defined = _definitions()
        for name in REQUIRED_EFFECTS + REQUIRED_TRIGGERS:
            self.assertIn(name, defined, name)

    def test_every_scripted_call_in_the_foundation_arcs_resolves(self):
        defined = _definitions()
        for arc in (self.school, self.ports):
            text = _arc_text(arc)
            calls = set(re.findall(r"(?<![A-Za-z0-9_.])(ywc_[a-z0-9_]+)\s*=\s*(?:yes|no|\{)", text))
            self.assertEqual(sorted(calls - defined), [], arc["slug"])

    def test_every_foundation_event_has_a_dispatch_branch(self):
        for arc in (self.school, self.ports):
            text = _arc_text(arc)
            dispatched = set(re.findall(r"trigger_event\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.]+)", text))
            undelivered = [row["id"] for row in arc["events"] if row["id"] not in dispatched]
            self.assertEqual(undelivered, [], f"{arc['slug']} has undispatched events")

    def test_route_choices_record_route_one_two_three(self):
        schools = {
            "ywc_kor_choose_school_coop": "1",
            "ywc_kor_choose_school_office": "2",
            "ywc_kor_choose_school_limited": "3",
        }
        ports = {
            "ywc_kor_choose_port_designated": "1",
            "ywc_kor_choose_port_general": "2",
            "ywc_kor_choose_port_shore": "3",
        }
        for name, route in schools.items():
            body = _helper_body(self.effects, name)
            self.assertIn("ywc_kor_school_route", body, name)
            self.assertIn(f"value = {route}", body, name)
        for name, route in ports.items():
            body = _helper_body(self.effects, name)
            self.assertIn("ywc_kor_ports_route", body, name)
            self.assertIn(f"value = {route}", body, name)

    def test_charges_are_real_and_guarded_and_never_double_billed(self):
        for name, cost in (("ywc_kor_choose_school_coop", "ywc_kor_school_archive_fee"),
                           ("ywc_kor_choose_school_office", "ywc_kor_school_archive_fee"),
                           ("ywc_kor_choose_school_limited", "ywc_kor_school_archive_fee"),
                           ("ywc_kor_school_record_old_account", "ywc_kor_school_archive_fee"),
                           ("ywc_kor_choose_port_designated", "ywc_kor_port_fee"),
                           ("ywc_kor_choose_port_general", "ywc_kor_port_fee"),
                           ("ywc_kor_choose_port_shore", "ywc_kor_port_fee")):
            body = _helper_body(self.effects, name)
            self.assertIn(cost, body, name)
            self.assertIn("add_treasury", body, name)
            self.assertRegex(body, r"multiply\s*=\s*-1")
            self.assertIn("_paid", body, name)

    def test_old_contracts_must_be_settled_before_full_settlement(self):
        body = _helper_body(self.triggers, "ywc_kor_school_old_contracts_clear")
        self.assertIn("ywc_kor_translation_contract_paid_months", body)
        self.assertIn("ywc_kor_veteran_contract_paid_months", body)
        self.assertIn(">= 12", body)

    def test_port_readiness_is_route_dependent(self):
        route = _helper_body(self.triggers, "ywc_kor_ports_current_route_ready")
        self.assertIn("ywc_kor_ports_route", route)
        for helper in ("ywc_kor_ports_designated_ready", "ywc_kor_ports_general_ready",
                       "ywc_kor_ports_shore_ready"):
            self.assertIn(helper, route)
        full = _helper_body(self.triggers, "ywc_kor_ports_full_ready")
        self.assertIn("ywc_kor_ports_designated_ready", full)
        self.assertIn("ywc_kor_ports_general_ready", full)
        auditor = _helper_body(self.triggers, "ywc_kor_ports_auditor_ready")
        self.assertIn("ywc_kor_school_route", auditor)
        self.assertIn("ywc_kor_ports_current_route_ready", auditor)

    def test_closers_write_outcome_and_release_the_slot(self):
        for arc, names in (
            (self.school, ["ywc_kor_close_school_as_established",
                           "ywc_kor_close_school_as_compromise",
                           "ywc_kor_close_school_as_breach"]),
            (self.ports, ["ywc_kor_close_ports_as_established",
                          "ywc_kor_close_ports_as_compromise",
                          "ywc_kor_close_ports_as_breach"]),
        ):
            for name in names:
                body = _helper_body(self.effects, name)
                self.assertIn("ywc_v03_active_arc_count", body, name)
                self.assertIn("ywc_v03_visible_task_count", body, name)
                self.assertIn("change_variable", body, name)
                self.assertIn("clamp_variable", body, name)
                expected_slot = arc["slug"].replace("v03_", "ywc_v03_kor_v03_", 1)
                self.assertIn(f"{expected_slot}_settled", body, name)

    def test_observation_maturation_and_blockage_notices_exist(self):
        school_text = _arc_text(self.school)
        self.assertIn("ywc_kor_school_monthly_review", school_text)
        self.assertIn("ywc_kor_school_six_months_complete", school_text)
        ports_text = _arc_text(self.ports)
        self.assertIn("ywc_kor_ports_monthly_review", ports_text)
        self.assertIn("ywc_kor_ports_six_months_complete", ports_text)
        review = _helper_body(self.effects, "ywc_kor_school_monthly_review")
        self.assertIn("months = 6", review)
        self.assertIn("ywc_kor_school_six_months_complete", review)
        self.assertIn("ywc_kor_school_limited_six_months_complete", review)
        ports_review = _helper_body(self.effects, "ywc_kor_ports_monthly_review")
        self.assertIn("ywc_kor_ports_six_months_complete", ports_review)
        self.assertIn("ywc_kor_ports_limited_six_months_complete", ports_review)
        self.assertIn("ywc_kor_ports_12_notice", ports_review)
        self.assertIn("ywc_kor_ports_36_notice", ports_review)


if __name__ == "__main__":
    unittest.main()