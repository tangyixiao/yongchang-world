"""Offline contract checks for the NMG foundation arcs.

Three foundation arcs for New Ming (NMG), a Mexican protectorate on the Gulf of
California coast:
  v03_nmg_land_arbitration   (ywc_nmg.1000-1007, 2 journal entries)
  v03_nmg_bilingual_office   (ywc_nmg.1010-1015, 1 journal entry)
  v03_nmg_autonomy_revenue   (ywc_nmg.1020-1029, 3 journal entries, ordered)

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

CATALOG_PATH = ROOT / "data/content/v03/countries/nmg.json"
EFFECTS_PATH = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_nmg_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_nmg_triggers.txt"
REGISTRY_PATH = ROOT / "data/content/v03/id_registry.json"
MOD = ROOT / "yongchang_world"

LAND_SLUG = "v03_nmg_land_arbitration"
OFFICE_SLUG = "v03_nmg_bilingual_office"
REVENUE_SLUG = "v03_nmg_autonomy_revenue"

LAND_EVENTS = [f"ywc_nmg.{number}" for number in range(1000, 1008)]
OFFICE_EVENTS = [f"ywc_nmg.{number}" for number in range(1010, 1016)]
REVENUE_EVENTS = [f"ywc_nmg.{number}" for number in range(1020, 1030)]

LAND_JES = ["ywc_je_v03_nmg_land_arbitration", "ywc_je_v03_nmg_land_settlement"]
OFFICE_JES = ["ywc_je_v03_nmg_bilingual_office"]
REVENUE_JES = [
    "ywc_je_v03_nmg_revenue_opening",
    "ywc_je_v03_nmg_revenue_negotiation",
    "ywc_je_v03_nmg_revenue_settlement",
]

SHORT_SLOTS = {
    "land": "ywc_v03_nmg_v03_nmg_land_arbitration",
    "office": "ywc_v03_nmg_v03_nmg_bilingual_office",
    "revenue": "ywc_v03_nmg_v03_nmg_autonomy_revenue",
}

REQUIRED_EFFECTS = [
    "ywc_nmg_release_slot",
    "ywc_nmg_claim_land_arbitration",
    "ywc_nmg_claim_bilingual_office",
    "ywc_nmg_claim_autonomy_revenue",
    "ywc_nmg_open_land_once",
    "ywc_nmg_open_office_once",
    "ywc_nmg_open_revenue_once",
    "ywc_nmg_land_fee_snapshot",
    "ywc_nmg_land_pay_fee_once",
    "ywc_nmg_office_fee_snapshot",
    "ywc_nmg_office_pay_fee_once",
    "ywc_nmg_revenue_fee_snapshot",
    "ywc_nmg_revenue_pay_fee_once",
    "ywc_nmg_land_monthly_review",
    "ywc_nmg_office_monthly_review",
    "ywc_nmg_revenue_monthly_review",
    "ywc_nmg_land_note_blocked",
    "ywc_nmg_office_note_blocked",
    "ywc_nmg_revenue_note_blocked",
    "ywc_nmg_land_open_settlement",
    "ywc_nmg_revenue_open_negotiation",
    "ywc_nmg_revenue_open_settlement",
    "ywc_nmg_land_record_backlog",
    "ywc_nmg_office_record_parish",
    "ywc_nmg_choose_land_mixed",
    "ywc_nmg_choose_land_unified",
    "ywc_nmg_choose_land_old",
    "ywc_nmg_choose_office_bilingual",
    "ywc_nmg_choose_office_local",
    "ywc_nmg_choose_office_single",
    "ywc_nmg_choose_revenue_fixed",
    "ywc_nmg_choose_revenue_joint",
    "ywc_nmg_choose_revenue_arrears",
    "ywc_nmg_close_land_as_established",
    "ywc_nmg_close_land_as_compromise",
    "ywc_nmg_close_land_as_breach",
    "ywc_nmg_close_office_as_established",
    "ywc_nmg_close_office_as_compromise",
    "ywc_nmg_close_office_as_breach",
    "ywc_nmg_close_revenue_as_established",
    "ywc_nmg_close_revenue_as_compromise",
    "ywc_nmg_close_revenue_as_breach",
]

REQUIRED_TRIGGERS = [
    "ywc_nmg_v03_finance_safe",
    "ywc_nmg_v03_has_owned_state",
    "ywc_nmg_land_unsettled",
    "ywc_nmg_office_unsettled",
    "ywc_nmg_revenue_unsettled",
    "ywc_nmg_land_affordable",
    "ywc_nmg_office_affordable",
    "ywc_nmg_revenue_quota_affordable",
    "ywc_nmg_land_agriculture_present",
    "ywc_nmg_land_administration_present",
    "ywc_nmg_land_written_title",
    "ywc_nmg_land_migration_open",
    "ywc_nmg_land_mixed_ready",
    "ywc_nmg_land_unified_ready",
    "ywc_nmg_land_old_ready",
    "ywc_nmg_land_route_ready",
    "ywc_nmg_office_admin_present",
    "ywc_nmg_office_literacy_ready",
    "ywc_nmg_office_bilingual_ready",
    "ywc_nmg_office_local_ready",
    "ywc_nmg_office_single_ready",
    "ywc_nmg_office_route_ready",
    "ywc_nmg_office_ig_support",
    "ywc_nmg_office_school_investment",
    "ywc_nmg_revenue_real_subject",
    "ywc_nmg_revenue_overlord_present",
    "ywc_nmg_revenue_relations_ok",
    "ywc_nmg_revenue_defense_present",
    "ywc_nmg_revenue_tax_base",
    "ywc_nmg_revenue_fixed_ready",
    "ywc_nmg_revenue_joint_ready",
    "ywc_nmg_revenue_arrears_ready",
    "ywc_nmg_revenue_route_ready",
]

ROUTE_CHOICES = {
    "ywc_nmg_choose_land_mixed": ("land", "1"),
    "ywc_nmg_choose_land_unified": ("land", "2"),
    "ywc_nmg_choose_land_old": ("land", "3"),
    "ywc_nmg_choose_office_bilingual": ("office", "1"),
    "ywc_nmg_choose_office_local": ("office", "2"),
    "ywc_nmg_choose_office_single": ("office", "3"),
    "ywc_nmg_choose_revenue_fixed": ("revenue", "1"),
    "ywc_nmg_choose_revenue_joint": ("revenue", "2"),
    "ywc_nmg_choose_revenue_arrears": ("revenue", "3"),
}

FEE_VARIABLES = {
    "land": "ywc_nmg_land_fee",
    "office": "ywc_nmg_office_fee",
    "revenue": "ywc_nmg_revenue_quota",
}

FORBIDDEN_GRANTS = (
    "add_law",
    "set_state_owner",
    "set_state_type",
    "add_claim",
    "set_autonomy",
    "independence",
    "annex",
    "set_country_type",
    "change_technology",
    "add_technology",
)


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


class NmgFoundationContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        cls.triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        cls.land = _arc(cls.catalog, LAND_SLUG)
        cls.office = _arc(cls.catalog, OFFICE_SLUG)
        cls.revenue = _arc(cls.catalog, REVENUE_SLUG)

    # ------------------------------------------------------------------ shape
    def test_catalog_file_is_plain_utf8_and_ends_with_newline(self):
        raw = CATALOG_PATH.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "catalog must be UTF-8 without BOM")
        self.assertTrue(raw.endswith(b"\n"), "catalog must end with a newline")
        self.assertEqual(set(self.catalog), {"key", "layer", "runtime_tags", "arcs"})
        self.assertEqual(self.catalog["key"], "country_nmg")
        self.assertEqual(self.catalog["layer"], "country")
        self.assertEqual(self.catalog["runtime_tags"], ["NMG"])

    def test_arcs_are_registered_with_their_reserved_event_ranges(self):
        ranges = {
            (row["catalog_key"], row["slug"]): (row["start"], row["end"])
            for row in self.registry["arc_ranges"]
        }
        self.assertEqual(ranges[("country_nmg", LAND_SLUG)], (1000, 1009))
        self.assertEqual(ranges[("country_nmg", OFFICE_SLUG)], (1010, 1019))
        self.assertEqual(ranges[("country_nmg", REVENUE_SLUG)], (1020, 1029))
        self.assertEqual([row["id"] for row in self.land["events"]], LAND_EVENTS)
        self.assertEqual([row["id"] for row in self.office["events"]], OFFICE_EVENTS)
        self.assertEqual([row["id"] for row in self.revenue["events"]], REVENUE_EVENTS)
        self.assertEqual([row["id"] for row in self.land["journals"]], LAND_JES)
        self.assertEqual([row["id"] for row in self.office["journals"]], OFFICE_JES)
        self.assertEqual([row["id"] for row in self.revenue["journals"]], REVENUE_JES)

    def test_arc_split_is_exactly_eight_two_six_one_ten_three(self):
        self.assertEqual(self.catalog["arcs"][0]["slug"], LAND_SLUG)
        self.assertEqual(self.catalog["arcs"][1]["slug"], OFFICE_SLUG)
        self.assertEqual(self.catalog["arcs"][2]["slug"], REVENUE_SLUG)
        for arc, events, journals in (
            (self.land, 8, 2),
            (self.office, 6, 1),
            (self.revenue, 10, 3),
        ):
            self.assertEqual(len(arc["events"]), events, arc["slug"])
            self.assertEqual(len(arc["journals"]), journals, arc["slug"])
        total = sum(len(arc["events"]) for arc in self.catalog["arcs"])
        self.assertEqual(total, 24)
        self.assertEqual(sum(len(arc["journals"]) for arc in self.catalog["arcs"]), 6)

    def test_foundation_arcs_keep_the_locked_card_shape(self):
        for arc in (self.land, self.office, self.revenue):
            self.assertEqual(arc["era"], "foundation")
            self.assertEqual(arc["depends_on"], [])
            self.assertTrue(arc["outcomes"])
            self.assertTrue(arc["legacy_links"])
            self.assertEqual(
                set(arc["legacy_links"]),
                {"ywc_je_flavor_nmg_bargain_1", "ywc_campaign_nmg_c1_outcome"},
            )
            for event in arc["events"]:
                self.assertEqual(
                    set(event),
                    {"id", "title", "desc", "trigger", "immediate", "options",
                     "purpose", "reads", "writes"},
                    event["id"],
                )
                self.assertTrue(event["title"]["zh"] and event["title"]["en"], event["id"])
                self.assertTrue(event["desc"]["zh"] and event["desc"]["en"], event["id"])
                self.assertTrue(event["purpose"]["zh"] and event["purpose"]["en"], event["id"])
                self.assertGreaterEqual(len(event["options"]), 2, event["id"])
                keys = [option["key"] for option in event["options"]]
                self.assertEqual(len(keys), len(set(keys)), event["id"])
                for option in event["options"]:
                    self.assertRegex(option["key"], r"^[a-z0-9_]+$")
                    self.assertTrue(option["label"]["zh"] and option["label"]["en"])
                    self.assertEqual(set(option["cost_note"]), {"zh", "en"}, option["key"])
                    self.assertEqual(
                        set(option["consequence_note"]), {"zh", "en"}, option["key"]
                    )
                    self.assertRegex(option["ai_chance"], r"\bbase\s*=|\bmodifier\s*=")
            for journal in arc["journals"]:
                self.assertEqual(
                    set(journal),
                    {"id", "title", "desc", "script", "goal", "exit_conditions"},
                    journal["id"],
                )
                self.assertRegex(journal["id"], r"^ywc_je_v03_nmg_[a-z0-9_]+$")
                body = journal["script"].strip()[1:-1]
                self.assertIsNone(
                    re.search(r"(?<![a-z0-9_])(?:complete|fail)\s*=", body), journal["id"]
                )

    # ------------------------------------------------------------- resolution
    def test_required_foundation_scripts_are_defined(self):
        defined = _definitions()
        for name in REQUIRED_EFFECTS + REQUIRED_TRIGGERS:
            self.assertIn(name, defined, name)

    def test_every_scripted_call_in_the_foundation_arcs_resolves(self):
        defined = _definitions()
        for arc in (self.land, self.office, self.revenue):
            text = _arc_text(arc)
            calls = set(
                re.findall(r"(?<![A-Za-z0-9_.])(ywc_[a-z0-9_]+)\s*=\s*(?:yes|no|\{)", text)
            )
            self.assertEqual(sorted(calls - defined), [], arc["slug"])

    def test_every_foundation_event_has_a_dispatch_branch(self):
        for arc in (self.land, self.office, self.revenue):
            text = _arc_text(arc)
            dispatched = set(
                re.findall(r"trigger_event\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.]+)", text)
            )
            undelivered = [row["id"] for row in arc["events"] if row["id"] not in dispatched]
            self.assertEqual(undelivered, [], f"{arc['slug']} has undispatched events")

    def test_every_foundation_event_is_gated_on_real_delivery_state(self):
        for arc in (self.land, self.office, self.revenue):
            for event in arc["events"]:
                self.assertIn("c:NMG ?= this", event["trigger"], event["id"])
                self.assertIn("ywc_v03_can_deliver_major = yes", event["trigger"], event["id"])
                self.assertIn(
                    "ywc_v03_mark_major_delivered = yes", event["immediate"], event["id"]
                )

    # ---------------------------------------------------------------- routes
    def test_route_choices_record_route_one_two_three(self):
        for name, (short, route) in ROUTE_CHOICES.items():
            body = _helper_body(self.effects, name)
            self.assertIn("ywc_nmg_%s_route" % short, body, name)
            self.assertIn(f"value = {route}", body, name)

    def test_charges_are_real_and_guarded_and_never_double_billed(self):
        for short in SHORT_SLOTS:
            fee = FEE_VARIABLES[short]
            pay_once = _helper_body(self.effects, "ywc_nmg_%s_pay_fee_once" % short)
            self.assertIn(fee, pay_once, short)
            self.assertIn("gold_reserves >= var:" + fee, pay_once, short)
            self.assertIn("add_treasury", pay_once, short)
            self.assertIn("multiply = -1", pay_once, short)
            self.assertIn(f"{fee}_paid", pay_once, short)
            snapshot = _helper_body(self.effects, "ywc_nmg_%s_fee_snapshot" % short)
            self.assertIn("yearly_gross_income", snapshot, short)
            self.assertIn("divide = 52", snapshot, short)
            self.assertIn("clamp_variable", snapshot, short)
        for name, (short, _route) in ROUTE_CHOICES.items():
            body = _helper_body(self.effects, name)
            self.assertIn("ywc_nmg_%s_pay_fee_once = yes" % short, body, name)

    def test_affordability_triggers_read_the_same_fee_they_charge(self):
        for short, fee in FEE_VARIABLES.items():
            name = "ywc_nmg_%s_%s" % (
                short, "quota_affordable" if short == "revenue" else "affordable"
            )
            body = _helper_body(self.triggers, name)
            self.assertIn("ywc_nmg_v03_finance_safe = yes", body, name)
            self.assertIn("var:" + fee, body, name)

    # ---------------------------------------------------------------- slots
    def test_openers_claim_the_slot_once_and_seed_the_first_event(self):
        for short, slot in SHORT_SLOTS.items():
            claim = _helper_body(self.effects, "ywc_nmg_claim_%s_slot" % short)
            self.assertIn(slot + "_started", claim, short)
            self.assertIn("ywc_v03_initialize_country = yes", claim, short)
            self.assertIn("ywc_v03_active_arc_count", claim, short)
            self.assertIn("ywc_v03_visible_task_count", claim, short)
            opened = _helper_body(self.effects, "ywc_nmg_open_%s_once" % short)
            self.assertIn("NOT = { has_variable = ywc_nmg_%s_opened }" % short, opened, short)
            self.assertIn("ywc_nmg_%s_pending" % short, opened, short)

    def test_closers_write_outcome_and_release_the_slot(self):
        for short, slot in SHORT_SLOTS.items():
            for outcome, suffix in ((3, "established"), (2, "compromise"), (1, "breach")):
                name = "ywc_nmg_close_%s_as_%s" % (short, suffix)
                body = _helper_body(self.effects, name)
                self.assertIn(slot + "_started", body, name)
                self.assertIn(slot + "_settled", body, name)
                self.assertIn(f"{slot}_outcome value = {outcome}", body, name)
                self.assertIn("ywc_nmg_release_slot = yes", body, name)
        release = _helper_body(self.effects, "ywc_nmg_release_slot")
        self.assertIn("ywc_v03_active_arc_count add = -1", release)
        self.assertIn("ywc_v03_visible_task_count add = -1", release)
        self.assertEqual(release.count("clamp_variable"), 2)

    def test_observation_maturation_and_blockage_notices_exist(self):
        for short in SHORT_SLOTS:
            review = _helper_body(self.effects, "ywc_nmg_%s_monthly_review" % short)
            self.assertIn("ywc_nmg_%s_watch_started" % short, review, short)
            self.assertIn("ywc_nmg_%s_watch_timer" % short, review, short)
            self.assertIn("value = 1 months = 6", review, short)
            self.assertIn("ywc_nmg_%s_six_months_complete" % short, review, short)
            self.assertIn("ywc_nmg_%s_12_notice" % short, review, short)
            self.assertIn("months = 12", review, short)
            self.assertIn("ywc_nmg_%s_36_notice" % short, review, short)
            self.assertIn("months = 36", review, short)
            self.assertIn("ywc_nmg_%s_note_blocked = yes" % short, review, short)
            blocked = _helper_body(self.effects, "ywc_nmg_%s_note_blocked" % short)
            self.assertIn("_blocked_note value = 1 months = 12", blocked, short)
            self.assertIn("_blocked_long value = 1 months = 36", blocked, short)

    # -------------------------------------------------------------- revenue
    def test_revenue_arc_is_a_staged_opening_negotiation_settlement(self):
        negotiation = _helper_body(self.effects, "ywc_nmg_revenue_open_negotiation")
        self.assertIn("ywc_nmg_revenue_pending value = 1023", negotiation)
        settlement = _helper_body(self.effects, "ywc_nmg_revenue_open_settlement")
        self.assertIn("ywc_nmg_revenue_pending value = 1027", settlement)
        staged_land = _helper_body(self.effects, "ywc_nmg_land_open_settlement")
        self.assertIn("ywc_nmg_land_pending value = 1004", staged_land)
        opening_je = self.revenue["journals"][0]["script"]
        self.assertIn("ywc_nmg_open_revenue_once = yes", opening_je)
        self.assertIn("id = ywc_nmg.1020", opening_je)
        opener = _helper_body(self.effects, "ywc_nmg_open_revenue_once")
        self.assertIn("ywc_nmg_revenue_pending value = 1020", opener)
        self.assertIn("ywc_nmg_revenue_stage2", self.revenue["journals"][1]["script"])
        self.assertIn("ywc_nmg_revenue_stage3", self.revenue["journals"][2]["script"])

    def test_subject_relation_is_read_from_real_engine_state(self):
        body = _helper_body(self.triggers, "ywc_nmg_revenue_real_subject")
        self.assertIn("is_subject = yes", body)
        self.assertIn("is_subject_of = c:MEX", body)
        self.assertNotIn("has_variable", body)
        overlord = _helper_body(self.triggers, "ywc_nmg_revenue_overlord_present")
        self.assertIn("overlord ?= {", overlord)
        relations = _helper_body(self.triggers, "ywc_nmg_revenue_relations_ok")
        self.assertIn("relations:root", relations)
        self.assertIn("relations_threshold:", relations)

    def test_arrears_route_pays_in_diplomatic_standing(self):
        body = _helper_body(self.effects, "ywc_nmg_choose_revenue_arrears")
        self.assertIn("change_relations = { country = c:MEX value = { add = -25 } }", body)
        self.assertIn("ywc_nmg_revenue_arrears_strain", body)
        self.assertIn("ywc_nmg_revenue_arrears value = 1", body)
        breach = _helper_body(self.effects, "ywc_nmg_close_revenue_as_breach")
        self.assertIn("ywc_nmg_revenue_arrears", breach)
        established = _helper_body(self.effects, "ywc_nmg_close_revenue_as_established")
        self.assertNotIn("ywc_nmg_revenue_arrears", established)

    def test_no_route_hands_out_laws_territory_or_independence(self):
        haystack = "\n".join(
            [_arc_text(arc) for arc in (self.land, self.office, self.revenue)]
            + [self.effects, self.triggers]
        )
        for token in FORBIDDEN_GRANTS:
            self.assertNotIn(token, haystack, token)

    # -------------------------------------------------------------- render
    def test_rendered_outputs_exist_with_bom_and_lf(self):
        expected = [
            MOD / "events/ywc_v03_country_nmg_events.txt",
            MOD / "common/journal_entries/ywc_v03_country_nmg_journal.txt",
            MOD / "localization/simp_chinese/ywc_v03_country_nmg_l_simp_chinese.yml",
            MOD / "localization/english/ywc_v03_country_nmg_l_english.yml",
        ]
        for path in expected:
            self.assertTrue(path.is_file(), str(path))
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), str(path))
            self.assertNotIn(b"\r\n", raw, str(path))
        events_text = (MOD / "events/ywc_v03_country_nmg_events.txt").read_text(
            encoding="utf-8-sig"
        )
        rendered = re.findall(r"(?m)^ywc_nmg\.(\d{4}) = \{", events_text)
        self.assertEqual(len(rendered), 24)
        self.assertEqual(
            sorted("ywc_nmg." + number for number in rendered),
            sorted(LAND_EVENTS + OFFICE_EVENTS + REVENUE_EVENTS),
        )


if __name__ == "__main__":
    unittest.main()
