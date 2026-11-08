"""Offline contract checks for the SHU foundation arcs.

Two foundation arcs extend the accepted M1 fiscal-register prototype:
  v03_shu_service_compact  (ywc_shu.1010-1017, 3 journal entries)
  v03_shu_port_treasury    (ywc_shu.1018-1025, 1 journal entry)

These checks are static/repository-level only: no engine, no save games, no UI.
"""
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

from clausewitz_harness import PulseWorld, parse

CATALOG_PATH = ROOT / "data/content/v03/countries/shu.json"
EFFECTS_PATH = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_shu_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_shu_triggers.txt"
REGISTRY_PATH = ROOT / "data/content/v03/id_registry.json"
MOD = ROOT / "yongchang_world"

SERVICE_SLUG = "v03_shu_service_compact"
PORT_SLUG = "v03_shu_port_treasury"
SERVICE_EVENTS = [f"ywc_shu.{number}" for number in range(1010, 1018)]
PORT_EVENTS = [f"ywc_shu.{number}" for number in range(1018, 1026)]
SERVICE_JES = [
    "ywc_je_v03_shu_service_contract",
    "ywc_je_v03_shu_service_appointments",
    "ywc_je_v03_shu_service_successor",
]
PORT_JES = ["ywc_je_v03_shu_port_customs"]

REQUIRED_EFFECTS = [
    "ywc_v03_claim_arc_shu_v03_shu_service_compact",
    "ywc_v03_claim_arc_shu_v03_shu_port_treasury",
    "ywc_shu_choose_service_route",
    "ywc_shu_pay_service_cost",
    "ywc_shu_pay_service_local_once",
    "ywc_shu_service_start_review",
    "ywc_shu_port_start_review",
    "ywc_shu_service_withdraw",
    "ywc_shu_service_close_success",
    "ywc_shu_service_close_withdrawn",
    "ywc_shu_accept_port_advance",
    "ywc_shu_pay_port_fee",
    "ywc_shu_port_close_unified",
    "ywc_shu_port_close_shared",
    "ywc_shu_port_close_legacy",
    "ywc_shu_port_close_withdrawn",
]

REQUIRED_TRIGGERS = [
    "ywc_shu_v03_service_professional_ready",
    "ywc_shu_v03_service_route_ready",
    "ywc_shu_service_route_ready",
    "ywc_shu_v03_has_port",
    "ywc_shu_v03_inland_office_ready",
    "ywc_shu_v03_customs_law_ready",
    "ywc_shu_v03_port_execution_ready",
]

OUTCOME_SETS = {
    SERVICE_SLUG: ["ywc_shu_service_outcome", "ywc_v03_shu_v03_shu_service_compact_settled"],
    PORT_SLUG: ["ywc_shu_port_outcome", "ywc_v03_shu_v03_shu_port_treasury_settled"],
}


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

def _replace_lifecycle_facts(nodes):
    facts = {
        "ywc_shu_service_route_ready": "test_service_ready",
        "ywc_shu_service_block_target_ready": "test_service_ready",
        "ywc_shu_port_block_target_ready": "test_port_ready",
        "ywc_shu_v03_port_execution_ready": "test_port_ready",
        "ywc_v03_can_deliver_major": "test_cooldown_clear",
        "ywc_v03_has_capacity": "test_capacity",
    }
    result = []
    for key, comparison, value in nodes:
        if key in facts:
            result.append(("has_variable", "=", facts[key]))
        elif isinstance(value, list):
            result.append((key, comparison, _replace_lifecycle_facts(value)))
        else:
            result.append((key, comparison, value))
    return result



class ShuFoundationContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        cls.triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        cls.service = _arc(cls.catalog, SERVICE_SLUG)
        cls.port = _arc(cls.catalog, PORT_SLUG)

    def test_arcs_are_registered_with_their_reserved_event_ranges(self):
        ranges = {
            (row["catalog_key"], row["slug"]): (row["start"], row["end"])
            for row in self.registry["arc_ranges"]
        }
        self.assertEqual(ranges[("country_shu", SERVICE_SLUG)], (1010, 1017))
        self.assertEqual(ranges[("country_shu", PORT_SLUG)], (1018, 1025))
        self.assertEqual([row["id"] for row in self.service["events"]], SERVICE_EVENTS)
        self.assertEqual([row["id"] for row in self.port["events"]], PORT_EVENTS)
        self.assertEqual([row["id"] for row in self.service["journals"]], SERVICE_JES)
        self.assertEqual([row["id"] for row in self.port["journals"]], PORT_JES)

    def test_foundation_arcs_keep_the_locked_card_shape(self):
        for arc in (self.service, self.port):
            self.assertEqual(arc["era"], "foundation")
            self.assertTrue(arc["participants"])
            self.assertEqual(arc["depends_on"], ["v03_shu_fiscal_register"])
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
                    self.assertTrue(option["consequence_note"]["zh"] and option["consequence_note"]["en"])
            for journal in arc["journals"]:
                body = journal["script"].strip()[1:-1]
                self.assertIsNone(
                    re.search(r"(?<![a-z0-9_])(?:complete|fail)\s*=", body), journal["id"]
                )
                self.assertTrue(journal["goal"].strip("{ }"))

    def test_required_foundation_scripts_are_defined(self):
        defined = _definitions()
        for name in REQUIRED_EFFECTS + REQUIRED_TRIGGERS:
            self.assertIn(name, defined, name)

    def test_every_scripted_call_in_the_foundation_arcs_resolves(self):
        defined = _definitions()
        for arc in (self.service, self.port):
            text = _arc_text(arc)
            calls = set(re.findall(r"(?<![A-Za-z0-9_.])(ywc_[a-z0-9_]+)\s*=\s*(?:yes|no|\{)", text))
            missing = sorted(calls - defined)
            self.assertEqual(missing, [], f"{arc['slug']}: {missing}")

    def test_every_foundation_event_has_a_dispatch_branch(self):
        for arc in (self.service, self.port):
            text = _arc_text(arc)
            dispatched = set(re.findall(r"trigger_event\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.]+)", text))
            undelivered = [row["id"] for row in arc["events"] if row["id"] not in dispatched]
            self.assertEqual(undelivered, [], f"{arc['slug']} has undispatched events")

    def test_claim_helpers_are_idempotent_and_free_a_slot(self):
        for name in ("ywc_v03_claim_arc_shu_v03_shu_service_compact",
                     "ywc_v03_claim_arc_shu_v03_shu_port_treasury"):
            body = _helper_body(self.effects, name)
            self.assertIn("ywc_v03_active_arc_count", body, name)
            self.assertIn("ywc_v03_visible_task_count", body, name)
            self.assertIn("change_variable", body, name)
            self.assertRegex(body, r"NOT = \{\s*has_variable = ywc_v03_shu_v03_shu_\w+_started")
            self.assertRegex(body, r"NOT = \{\s*has_variable = ywc_v03_shu_v03_shu_\w+_settled")

    def test_service_route_and_review_helpers_record_real_state(self):
        choose = _helper_body(self.effects, "ywc_shu_choose_service_route")
        self.assertIn("ywc_shu_service_route", choose)
        start_review = _helper_body(self.effects, "ywc_shu_service_start_review")
        self.assertIn("ywc_shu_service_review_due", start_review)
        self.assertIn("ywc_shu_service_review", start_review)
        self.assertIn("days = 180", start_review)
        withdraw = _helper_body(self.effects, "ywc_shu_service_withdraw")
        self.assertIn("ywc_shu_service_withdrawn", withdraw)
        self.assertIn("ywc_shu_service_close_withdrawn", withdraw)

    def test_service_fee_waiver_and_professional_qualification_are_route_scoped(self):
        choose = _helper_body(self.effects, "ywc_shu_choose_service_route")
        self.assertRegex(choose, r"var:ywc_shu_service_route_candidate = 2[\s\S]*ywc_shu_service_compact_fee_waived")
        professional_trigger = _helper_body(self.triggers, "ywc_shu_service_professional_qualifies")
        self.assertIn("has_law_or_variant = law_type:law_professional_army", professional_trigger)
        self.assertIn("ywc_shu_v03_service_professional_ready = yes", professional_trigger)
        payment = _helper_body(self.effects, "ywc_shu_pay_service_cost")
        professional_branch = re.search(r"limit = \{ var:ywc_shu_service_route_candidate = 1 \}([\s\S]*?)\n\t\t}", payment)
        self.assertIsNotNone(professional_branch)
        self.assertIn("ywc_shu_service_professional_qualifies = yes", professional_branch.group(1))
        self.assertNotIn("else_if", professional_branch.group(1))
        event = next(row for row in self.service["events"] if row["id"] == "ywc_shu.1013")
        option = next(row for row in event["options"] if row["key"] == "professional")
        self.assertIn("ywc_shu_service_professional_qualifies = yes", option["trigger"])
        self.assertNotIn("has_variable = ywc_shu_service_compact_fee_waived", option["effect"])
        self.assertIn("value = 1013", option["effect"])
        waiver = _helper_body(self.triggers, "ywc_shu_service_compact_waiver_eligible")
        for fact in ("ywc_shu_service_provincial_report", "ywc_shu_service_joint_review", "ywc_shu_service_local_voice"):
            self.assertIn(f"has_variable = {fact}", waiver)
        provincial = next(row for row in self.service["events"][3]["options"] if row["key"] == "provincial_compact")
        self.assertIn("ywc_shu_service_compact_waiver_eligible = yes", provincial["trigger"])
        self.assertIn("ywc_shu_service_compact_waiver_eligible = yes", choose)
        payroll = next(row for row in self.service["events"][1]["options"] if row["key"] == "verify_payroll")
        self.assertIn("value = 1011", payroll["effect"])
        self.assertIn("ywc_shu_pay_service_cost = yes", payroll["effect"])
        port_fee = _helper_body(self.effects, "ywc_shu_pay_port_fee")
        self.assertIn("ywc_shu_port_fee_half_mode", port_fee)
        self.assertIn("gold_reserves >= { value = var:ywc_shu_port_cost }", port_fee)
        port = _arc(self.catalog, PORT_SLUG)
        verify = next(row for row in port["events"] if row["id"] == "ywc_shu.1022")
        verification = next(row for row in verify["options"] if row["key"] == "pay_verification")
        self.assertIn("gold_reserves >= { value = var:ywc_shu_port_cost }", verification["trigger"])
        self.assertIn("One-time fee equals weekly income", verification["cost_note"]["en"])

    def test_charges_are_real_guarded_and_never_double_billed(self):
        expectations = {
            "ywc_shu_pay_service_cost": "ywc_shu_service_cost_paid",
            "ywc_shu_pay_service_local_once": "ywc_shu_service_local_paid",
            "ywc_shu_pay_port_fee": "ywc_shu_port_fee_paid",
        }
        for name, flag in expectations.items():
            body = _helper_body(self.effects, name)
            self.assertIn(f"NOT = {{ has_variable = {flag} }}", body, name)
            self.assertIn("in_default = no", body, name)
            self.assertIn("has_modifier = declared_bankruptcy", body, name)
            self.assertIn("gold_reserves >=", body, name)
            self.assertRegex(body, r"add_treasury\s*=\s*\{\s*value\s*=\s*var:ywc_shu_\w+[\s\S]*?multiply\s*=\s*-\d")
            self.assertIn(f"name = {flag}", body, name)
        advance = _helper_body(self.effects, "ywc_shu_accept_port_advance")
        self.assertIn("ywc_shu_port_advance_accepted", advance)
        self.assertIn("ywc_shu_port_advance_unpaid", advance)

    def test_closers_release_the_slot_once_and_write_the_outcome(self):
        closers = {
            SERVICE_SLUG: ["ywc_shu_service_close_success", "ywc_shu_service_close_withdrawn"],
            PORT_SLUG: [
                "ywc_shu_port_close_unified",
                "ywc_shu_port_close_shared",
                "ywc_shu_port_close_legacy",
                "ywc_shu_port_close_withdrawn",
            ],
        }
        for slug, names in closers.items():
            settled, outcome = OUTCOME_SETS[slug]
            for name in names:
                body = _helper_body(self.effects, name)
                self.assertIn(settled, body, name)
                self.assertIn(outcome, body, name)
                self.assertIn("clamp_variable", body, name)
                self.assertIn("max = 3", body, name)
                self.assertIn("max = 6", body, name)
                self.assertIn("change_variable", body, name)

    def test_withdrawal_never_erases_a_paid_debt_and_never_allows_negative_cash(self):
        withdraw = _helper_body(self.effects, "ywc_shu_service_withdraw")
        # Withdrawal records a setback and frees the slot; it must not un-pay or refund a signed promise.
        self.assertNotRegex(withdraw, r"remove_variable[^\n]*ywc_shu_service_cost_paid")
        self.assertNotRegex(withdraw, r"remove_variable[^\n]*ywc_shu_port_fee_paid")
        for name in ("ywc_shu_pay_service_cost", "ywc_shu_pay_service_local_once", "ywc_shu_pay_port_fee"):
            body = _helper_body(self.effects, name)
            self.assertNotRegex(body, r"gold_reserves >= -")

    def test_blockage_and_observation_clocks_are_armed(self):
        service_text = _arc_text(self.service)
        self.assertIn("ywc_shu_track_service_block = yes", service_text)
        self.assertIn("ywc_shu_track_port_block = yes", _arc_text(self.port))
        self.assertIn("ywc_shu_service_block_12_due", self.effects)
        self.assertIn("ywc_shu_service_block_36_due", self.effects)
        self.assertIn("ywc_shu_port_block_12_due", self.effects)
        self.assertIn("ywc_shu_port_block_36_due", self.effects)
        self.assertIn("ywc_shu_service_review_mature", service_text)
        self.assertIn("ywc_shu_port_review_mature", _arc_text(self.port))

    def test_added_arc_admission_does_not_cancel_its_own_predecessor(self):
        for arc, own_slug in ((self.service, SERVICE_SLUG), (self.port, PORT_SLUG)):
            script = arc["journals"][0]["script"]
            settled = f"ywc_v03_shu_{own_slug}_settled"
            started = f"ywc_v03_shu_{own_slug}_started"
            self.assertNotIn("ywc_shu_v03_unsettled", script)
            self.assertIn(f"NOT = {{ has_variable = {settled} }}", script)
            self.assertIn(f"NOT = {{ has_variable = {started} }}", script)
            self.assertIn("ywc_v03_shu_v03_shu_fiscal_register_settled", script)

    def test_real_entry_predicates_accept_completed_prototype_and_block_replay(self):
        facts = {"ywc_v03_initialized": 1, "test_capacity": 1,
                 "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 1,
                 "ywc_v03_shu_v03_shu_fiscal_register_settled": 1}
        for arc in (self.service, self.port):
            script = parse(arc["journals"][0]["script"])
            possible = next(body for key, _, body in script if key == "possible")
            self.assertTrue(PulseWorld(self.effects, {"SHU": facts}).conditions(
                _replace_lifecycle_facts(possible), "SHU"), arc["slug"])
            own = f"ywc_v03_shu_{arc['slug']}_started"
            self.assertFalse(PulseWorld(self.effects, {"SHU": {**facts, own: 1}}).conditions(
                _replace_lifecycle_facts(possible), "SHU"), arc["slug"])

    def test_terminal_predicates_are_named_and_exclusive(self):
        for arc in (self.service, self.port):
            for journal in arc["journals"]:
                self.assertNotRegex(journal["exit_conditions"], r"\{\s*\{")
                self.assertIn("has_variable =", journal["exit_conditions"])
            journal = arc["journals"][-1]
            self.assertRegex(journal["goal"], r"var:ywc_shu_(?:service|port)_outcome = 1")
            self.assertNotRegex(journal["goal"], r"var:ywc_shu_(?:service|port)_outcome = 4")

    def test_review_matures_before_restart_and_real_loss_resets_it(self):
        journal = self.service["journals"][-1]
        script = journal["script"]
        maturity = script.index("set_variable = { name = ywc_shu_service_review_mature")
        restart = script.index("ywc_shu_service_start_review = yes", script.index("on_monthly_pulse"))
        self.assertLess(maturity, restart)
        self.assertIn("remove_variable = ywc_shu_service_review_mature", script)

    def test_blockage_notices_wait_for_elapsed_clocks_and_use_notice_queue(self):
        for arc, prefix in ((self.service, "service"), (self.port, "port")):
            script = arc["journals"][0]["script"]
            helper = _helper_body(self.effects, f"ywc_shu_track_{prefix}_block")
            self.assertIn(f"NOT = {{ has_variable = ywc_shu_{prefix}_block_12_due }}", helper)
            self.assertIn(f"NOT = {{ has_variable = ywc_shu_{prefix}_block_36_due }}", helper)
            self.assertIn(f"ywc_shu_{prefix}_notice_pending_event", helper)
            self.assertIn(f"ywc_shu_{prefix}_block_12_started", helper)
            self.assertNotIn(f"set_variable = {{ name = ywc_shu_{prefix}_block_12_due days = 365 }}", script)

    def test_service_paid_routes_advance_only_after_effect_time_charge(self):
        for option in self.service["events"][3]["options"][:2]:
            effect = option["effect"]
            self.assertIn("has_variable = ywc_shu_service_cost_paid", effect)
            self.assertIn("set_variable = { name = ywc_shu_service_route", effect)
            self.assertLess(effect.index("set_variable = { name = ywc_shu_service_route_candidate"), effect.index("ywc_shu_pay_service_cost = yes"))
            self.assertLess(effect.index("ywc_shu_pay_service_cost = yes"), effect.index("set_variable = { name = ywc_shu_service_route value"))
            self.assertIn("remove_variable = ywc_shu_service_route_candidate", effect)

    def test_authored_service_review_pulse_matures_on_day_180_without_restart(self):
        journal = self.service["journals"][-1]
        pulse = next(body for key, _, body in parse(journal["script"]) if key == "on_monthly_pulse")
        effect = next(body for key, _, body in pulse if key == "effect")
        world = PulseWorld(self.effects, {"SHU": {"test_service_ready": 1, "test_cooldown_clear": 1}})
        world.run("ywc_shu_service_start_review")
        world.advance_days(179)
        pulse_without_block_tracking = [node for node in effect if node[0] != "ywc_shu_track_service_block"]
        world.execute(_replace_lifecycle_facts(pulse_without_block_tracking), "SHU")
        self.assertNotIn("ywc_shu_service_review_mature", world.countries["SHU"])
        world.advance_days(1)
        pulse_without_block_tracking = [node for node in effect if node[0] != "ywc_shu_track_service_block"]
        world.execute(_replace_lifecycle_facts(pulse_without_block_tracking), "SHU")
        self.assertEqual(world.countries["SHU"].get("ywc_shu_service_review_mature"), 1)
        self.assertNotIn("ywc_shu_service_review_due", world.countries["SHU"])
        self.assertIn(("SHU", "ywc_shu.1017"), world.events)

    def test_authored_port_review_pulse_waits_for_180_continuous_days(self):
        journal = self.port["journals"][0]
        pulse = next(body for key, _, body in parse(journal["script"]) if key == "on_monthly_pulse")
        effect = next(body for key, _, body in pulse if key == "effect")
        world = PulseWorld(self.effects, {"SHU": {"test_port_ready": 1, "test_cooldown_clear": 1}})
        world.run("ywc_shu_port_start_review")
        world.advance_days(179)
        pulse_without_block_tracking = [node for node in effect if node[0] != "ywc_shu_track_port_block"]
        world.execute(_replace_lifecycle_facts(pulse_without_block_tracking), "SHU")
        self.assertNotIn("ywc_shu_port_review_mature", world.countries["SHU"])
        world.advance_days(1)
        world.execute(_replace_lifecycle_facts(pulse_without_block_tracking), "SHU")
        self.assertEqual(world.countries["SHU"].get("ywc_shu_port_review_mature"), 1)
        self.assertNotIn("ywc_shu_port_review_due", world.countries["SHU"])
        world.execute(_replace_lifecycle_facts(pulse_without_block_tracking), "SHU")
        self.assertIn(("SHU", "ywc_shu.1025"), world.events)

    def test_port_route_readiness_is_route_dependent(self):
        body = _helper_body(self.triggers, "ywc_shu_v03_port_execution_ready")
        self.assertIn("ywc_shu_port_route", body)
        self.assertIn("ywc_shu_v03_has_port", body)
        self.assertIn("ywc_shu_v03_finance_safe", body)
        self.assertIn("ywc_shu_v03_inland_office_ready", body)
        customs = _helper_body(self.triggers, "ywc_shu_v03_customs_law_ready")
        for law in ("law_mercantilism", "law_protectionism", "law_free_trade"):
            self.assertIn(law, customs)
        narrow = _helper_body(self.triggers, "ywc_shu_v03_port_narrow_ready")
        self.assertIn("ywc_shu_v03_inland_office_ready", narrow)
        self.assertNotIn("ywc_shu_v03_has_port", narrow)


if __name__ == "__main__":
    unittest.main()
