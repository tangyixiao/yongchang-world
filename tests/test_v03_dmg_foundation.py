"""Offline contract checks for the DMG foundation arcs.

Two foundation arcs extend the accepted M1 common-subjects prototype:
  v03_dmg_two_land_titles  (ywc_dmg.1010-1015, 1 journal entry)
  v03_dmg_court_provinces  (ywc_dmg.1016-1023, 3 journal entries)

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

CATALOG_PATH = ROOT / "data/content/v03/countries/dmg.json"
EFFECTS_PATH = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_dmg_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_dmg_triggers.txt"
MODIFIER_PATH = ROOT / "yongchang_world/common/static_modifiers/ywc_v03_dmg_modifiers.txt"
REGISTRY_PATH = ROOT / "data/content/v03/id_registry.json"
MOD = ROOT / "yongchang_world"

TITLES_SLUG = "v03_dmg_two_land_titles"
COURT_SLUG = "v03_dmg_court_provinces"
TITLES_EVENTS = [f"ywc_dmg.{number}" for number in range(1010, 1016)]
COURT_EVENTS = [f"ywc_dmg.{number}" for number in range(1016, 1024)]
JOURNAL_ID = re.compile(r"^ywc_je_v03_dmg_[a-z0-9_]+$")

REQUIRED_HELPERS = [
    "ywc_dmg_foundation_snapshot_costs",
    "ywc_dmg_foundation_claim_titles",
    "ywc_dmg_foundation_claim_court",
    "ywc_dmg_foundation_pay_titles_registry",
    "ywc_dmg_foundation_pay_titles_compensation",
    "ywc_dmg_foundation_pay_court_charter",
    "ywc_dmg_foundation_pay_court_budget",
    "ywc_dmg_foundation_close_titles",
    "ywc_dmg_foundation_close_court",
    "ywc_dmg_foundation_limit_titles",
    "ywc_dmg_foundation_withdraw_titles",
    "ywc_dmg_foundation_limit_court",
    "ywc_dmg_foundation_withdraw_court",
]

REQUIRED_TRIGGERS = [
    "ywc_dmg_foundation_agriculture_employment",
    "ywc_dmg_foundation_titles_route_ready",
    "ywc_dmg_foundation_court_route_ready",
]

FOUNDATION_MODIFIERS = [
    "ywc_dmg_foundation_titles_mixed",
    "ywc_dmg_foundation_titles_contract",
    "ywc_dmg_foundation_titles_legacy",
    "ywc_dmg_foundation_court_central",
    "ywc_dmg_foundation_court_joint",
    "ywc_dmg_foundation_court_local",
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


class DmgFoundationContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        cls.triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        cls.modifiers = MODIFIER_PATH.read_text(encoding="utf-8-sig")
        cls.titles = _arc(cls.catalog, TITLES_SLUG)
        cls.court = _arc(cls.catalog, COURT_SLUG)

    def test_arcs_are_registered_with_their_reserved_event_ranges(self):
        ranges = {
            (row["catalog_key"], row["slug"]): (row["start"], row["end"])
            for row in self.registry["arc_ranges"]
        }
        self.assertEqual(ranges[("country_dmg", TITLES_SLUG)], (1010, 1015))
        self.assertEqual(ranges[("country_dmg", COURT_SLUG)], (1016, 1023))
        self.assertEqual([row["id"] for row in self.titles["events"]], TITLES_EVENTS)
        self.assertEqual([row["id"] for row in self.court["events"]], COURT_EVENTS)
        self.assertEqual(len(self.titles["journals"]), 1)
        self.assertEqual(len(self.court["journals"]), 3)
        seen = []
        for arc in (self.titles, self.court):
            for journal in arc["journals"]:
                self.assertRegex(journal["id"], JOURNAL_ID)
                seen.append(journal["id"])
        self.assertEqual(len(set(seen)), len(seen), seen)

    def test_foundation_arcs_keep_the_locked_card_shape(self):
        for arc in (self.titles, self.court):
            self.assertEqual(arc["depends_on"], ["v03_dmg_common_subjects"])
            self.assertTrue(arc["participants"])
            self.assertTrue(arc["outcomes"])
            self.assertTrue(arc["legacy_links"])
            for event in arc["events"]:
                self.assertTrue(event["title"]["zh"] and event["title"]["en"], event["id"])
                self.assertTrue(event["desc"]["zh"] and event["desc"]["en"], event["id"])
                self.assertGreaterEqual(len(event["options"]), 2, event["id"])
                for option in event["options"]:
                    self.assertEqual(set(option["cost_note"]), {"zh", "en"}, option["key"])
                    self.assertEqual(set(option["consequence_note"]), {"zh", "en"}, option["key"])
                    self.assertTrue(option["cost_note"]["zh"] and option["cost_note"]["en"])
            for journal in arc["journals"]:
                self.assertEqual(journal["id"][:11], "ywc_je_v03_")
                body = journal["script"].strip()[1:-1]
                self.assertIsNone(
                    re.search(r"(?<![a-z0-9_])(?:complete|fail)\s*=", body), journal["id"]
                )

    def test_required_foundation_scripts_are_defined(self):
        defined = _definitions()
        for name in REQUIRED_HELPERS + REQUIRED_TRIGGERS:
            self.assertIn(name, defined, name)

    def test_every_scripted_call_in_the_foundation_arcs_resolves(self):
        defined = _definitions()
        for arc in (self.titles, self.court):
            text = _arc_text(arc)
            calls = set(re.findall(r"(?<![A-Za-z0-9_.])(ywc_[a-z0-9_]+)\s*=\s*(?:yes|no|\{)", text))
            self.assertEqual(sorted(calls - defined), [], arc["slug"])

    def test_every_foundation_event_has_a_dispatch_branch(self):
        for arc in (self.titles, self.court):
            text = _arc_text(arc)
            dispatched = set(re.findall(r"trigger_event\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.]+)", text))
            undelivered = [row["id"] for row in arc["events"] if row["id"] not in dispatched]
            self.assertEqual(undelivered, [], f"{arc['slug']} has undispatched events")

    def test_claim_helpers_respect_the_shared_arc_and_task_caps(self):
        for name in ("ywc_dmg_foundation_claim_titles", "ywc_dmg_foundation_claim_court"):
            body = _helper_body(self.effects, name)
            self.assertIn("ywc_v03_active_arc_count", body, name)
            self.assertIn("ywc_v03_visible_task_count", body, name)
            self.assertIn("ywc_dmg_v03_has_owned_state", body, name)
            self.assertRegex(body, r"< 3")
            self.assertRegex(body, r"< 6")
            self.assertRegex(body, r"NOT = \{\s*has_variable = ywc_v03_dmg_v03_dmg_\w+_settled")

    def test_costs_snapshot_once_from_official_income_and_floors_at_hundred(self):
        body = _helper_body(self.effects, "ywc_dmg_foundation_snapshot_costs")
        self.assertIn("yearly_gross_income", body)
        self.assertIn("divide = 52", body)
        self.assertIn("min = 100", body)
        self.assertIn("ywc_dmg_foundation_costs_snapshotted", body)
        self.assertRegex(body, r"NOT = \{\s*has_variable = ywc_dmg_foundation_costs_snapshotted")

    def test_charges_are_real_guarded_and_never_double_billed(self):
        expectations = {
            "ywc_dmg_foundation_pay_titles_registry": "ywc_dmg_titles_registry_paid",
            "ywc_dmg_foundation_pay_titles_compensation": "ywc_dmg_titles_compensation_paid",
            "ywc_dmg_foundation_pay_court_charter": "ywc_dmg_court_charter_paid",
            "ywc_dmg_foundation_pay_court_budget": "ywc_dmg_court_budget_paid",
        }
        for name, flag in expectations.items():
            body = _helper_body(self.effects, name)
            self.assertIn(f"NOT = {{ has_variable = {flag} }}", body, name)
            self.assertIn("gold_reserves >=", body, name)
            self.assertIn("in_default = no", body, name)
            self.assertIn("has_modifier = declared_bankruptcy", body, name)
            self.assertRegex(body, r"add_treasury\s*=\s*\{\s*value\s*=\s*var:ywc_dmg_\w+[\s\S]*?multiply\s*=\s*-1")
            self.assertIn(f"name = {flag}", body, name)

    def test_closers_pick_the_route_outcome_and_release_the_slot_once(self):
        config = (
            ("ywc_dmg_foundation_close_titles", "ywc_dmg_titles", "ywc_dmg_two_land_titles",
             "ywc_dmg_foundation_titles_"),
            ("ywc_dmg_foundation_close_court", "ywc_dmg_court", "ywc_dmg_court_provinces",
             "ywc_dmg_foundation_court_"),
        )
        for name, prefix, slug, modifier_prefix in config:
            body = _helper_body(self.effects, name)
            self.assertIn(f"{prefix}_review_matured", body, name)
            self.assertIn(f"{prefix}_route_ready", body, name)
            self.assertIn("ywc_v03_release_arc_dmg_foundation_", body, name)
            self.assertIn("months = 36", body, name)
            for route in ("1", "2", "3"):
                self.assertRegex(body, rf"var:{prefix}_route = {route}")
            expected = [mod for mod in FOUNDATION_MODIFIERS if mod.startswith(modifier_prefix)]
            self.assertEqual(len(expected), 3, modifier_prefix)
            for modifier in expected:
                self.assertIn(modifier, body, name)

    def test_withdrawal_and_limit_release_without_erasing_signed_debt(self):
        for name, outcome, slug in (
            ("ywc_dmg_foundation_limit_titles", "ywc_dmg_titles_outcome", TITLES_SLUG),
            ("ywc_dmg_foundation_withdraw_titles", "ywc_dmg_titles_outcome", TITLES_SLUG),
            ("ywc_dmg_foundation_limit_court", "ywc_dmg_court_outcome", COURT_SLUG),
            ("ywc_dmg_foundation_withdraw_court", "ywc_dmg_court_outcome", COURT_SLUG),
        ):
            body = _helper_body(self.effects, name)
            self.assertIn(outcome, body, name)
            self.assertIn("ywc_v03_release_arc_dmg_foundation_", body, name)
            self.assertNotRegex(body, r"remove_variable[^\n]*_paid")

    def test_release_helpers_free_exactly_one_slot_and_clamp_the_counters(self):
        for name, slug in (("ywc_v03_release_arc_dmg_foundation_titles", TITLES_SLUG),
                           ("ywc_v03_release_arc_dmg_foundation_court", COURT_SLUG)):
            body = _helper_body(self.effects, name)
            self.assertIn(f"ywc_v03_dmg_{slug}_started", body, name)
            self.assertIn(f"ywc_v03_dmg_{slug}_settled", body, name)
            self.assertIn("add = -1", body, name)
            self.assertIn("min = 0 max = 3", body, name)
            self.assertIn("min = 0 max = 6", body, name)

    def test_agriculture_employment_uses_real_staffed_buildings(self):
        body = _helper_body(self.triggers, "ywc_dmg_foundation_agriculture_employment")
        self.assertIn("any_scope_state", body)
        self.assertIn("is_owned_by = ROOT", body)
        self.assertIn("is_building_group = bg_agriculture", body)
        self.assertIn("occupancy >= 0.5", body)
        self.assertIn("building_has_goods_shortage = no", body)

    def test_land_route_readiness_requires_land_law_and_agriculture(self):
        body = _helper_body(self.triggers, "ywc_dmg_foundation_titles_route_ready")
        self.assertIn("net_fixed_income >= 0", body)
        self.assertIn("ywc_dmg_foundation_agriculture_employment", body)
        for law in ("law_tenant_farmers", "law_manorialism", "law_peasant_proprietorship",
                    "law_commercialized_agriculture", "law_homesteading"):
            self.assertIn(law, body)

    def test_court_route_readiness_branches_on_real_franchise(self):
        body = _helper_body(self.triggers, "ywc_dmg_foundation_court_route_ready")
        self.assertIn("ywc_dmg_court_charter_paid", body)
        self.assertIn("ywc_dmg_court_budget_paid", body)
        self.assertRegex(body, r"country_has_voting_franchise = (yes|no)")
        self.assertIn("ywc_dmg_v03_government_appointment_ready", body)
        self.assertIn("ywc_dmg_v03_electoral_representative_ready", body)
        self.assertIn("ywc_dmg_joint_appointment_clause", body)

    def test_six_foundation_modifiers_are_declared_and_localized(self):
        declared = set(re.findall(r"(?m)^([A-Za-z0-9_]+)\s*=\s*\{", self.modifiers))
        for name in FOUNDATION_MODIFIERS:
            self.assertIn(name, declared, name)
        for language in ("simp_chinese", "english"):
            text = (ROOT / f"yongchang_world/localization/{language}"
                           / f"ywc_v03_dmg_modifiers_l_{language}.yml").read_text(encoding="utf-8-sig")
            for name in FOUNDATION_MODIFIERS:
                self.assertIn(f"{name}:", text, f"{language}:{name}")

    def test_bilingual_localization_covers_every_new_option(self):
        for language in ("simp_chinese", "english"):
            text = (ROOT / f"yongchang_world/localization/{language}"
                           / f"ywc_v03_country_dmg_l_{language}.yml").read_text(encoding="utf-8-sig")
            for arc in (self.titles, self.court):
                for event in arc["events"]:
                    self.assertIn(f"{event['id']}.t:", text)
                    self.assertIn(f"{event['id']}.d:", text)
                    for option in event["options"]:
                        self.assertIn(f"{event['id']}.{option['key']}:", text, option["key"])

    def test_court_arc_reads_the_land_titles_outcome_in_executable_code(self):
        # The report promises cross-arc reads at the local-budget and re-signing beats.
        readers = [event for event in self.court["events"] if event["id"] in ("ywc_dmg.1017", "ywc_dmg.1022")]
        self.assertEqual(len(readers), 2)
        for event in readers:
            text = event["trigger"] + event["immediate"] + "".join(
                option["effect"] + (option.get("trigger") or "") for option in event["options"])
            self.assertRegex(
                text,
                r"ywc_dmg_(?:two_land_titles|titles)_outcome",
                f"{event['id']} must branch on the land-titles outcome",
            )


if __name__ == "__main__":
    unittest.main()