"""Drive the SHU foundation authored JE/event scripts through the offline Clausewitz subset."""
import json
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from clausewitz_harness import PulseWorld, parse

CATALOG = json.loads((ROOT / "data/content/v03/countries/shu.json").read_text(encoding="utf-8"))
EFFECTS = "\n".join(p.read_text(encoding="utf-8-sig") for p in sorted((ROOT / "yongchang_world/common/scripted_effects").glob("*.txt")))
TRIGGER_TEXT = "\n".join(p.read_text(encoding="utf-8-sig") for p in sorted((ROOT / "yongchang_world/common/scripted_triggers").glob("*.txt")))
TRIGGERS = {key: body for key, _, body in parse(TRIGGER_TEXT)}


def arc(slug):
    return next(row for row in CATALOG["arcs"] if row["slug"] == slug)


def facts_only(nodes):
    """Resolve authored scripted triggers; substitute only engine/world leaves with explicit fixture facts."""
    result = []
    world_leaf_names = {
        "any_scope_state": "test_owned_state",
        "any_scope_building": "test_real_building",
        "has_law_or_variant": None,
        "has_technology_researched": None,
        "has_technology": None,
    }
    for key, comparison, value in nodes:
        if key in TRIGGERS:
            body = facts_only(TRIGGERS[key])
            if value == "no":
                result.append(("NOT", "=", body))
            else:
                result.append(("AND", "=", body))
        elif key == "any_scope_state":
            building = next((str(bv).split(":")[-1] for k, _, v in value if k == "any_scope_building" for bk, _, bv in v if bk == "is_building_type"), None)
            fact = "test_owned_building_" + building if building else "test_owned_state"
            result.append(("has_variable", "=", fact))
        elif key == "any_scope_building":
            building = next((str(v).split(":")[-1] for k, _, v in value if k == "is_building_type"), None)
            result.append(("has_variable", "=", "test_owned_building_" + building if building else "test_real_building"))
        elif key in world_leaf_names:
            fact = world_leaf_names[key]
            if fact is None:
                token = str(value).split(":")[-1]
                fact = "test_law_" + token
            result.append(("has_variable", "=", fact))
        elif isinstance(value, list):
            result.append((key, comparison, facts_only(value)))
        else:
            result.append((key, comparison, value))
    return result


class ShuPulseWorld(PulseWorld):
    def run(self, name, tag="SHU"):
        self.execute(facts_only(self.effects[name]), tag)


class ShuRuntime:
    def __init__(self, slug, seed=None):
        self.arc = arc(slug)
        start = {
            "yearly_gross_income": 52_000,
            "gold_reserves": 100_000,
            "net_fixed_income": 100,
            "bureaucracy": 1000,
            "test_owned_state": 1,
            "test_real_building": 1,
            "test_owned_building_building_barrack": 1,
            "test_owned_building_building_government_administration": 1,
            "test_owned_building_building_port": 1,
            "test_law_law_professional_army": 1,
            "test_law_law_mercantilism": 1,
            "test_law_law_protectionism": 1,
            "test_law_law_free_trade": 1,
            "test_law_law_land_based_taxation": 1,
            "test_law_law_per_capita_taxation": 1,
            "test_law_law_per_capita_based_taxation": 1,
            "test_law_law_consumption_based_taxation": 1,
            "test_ready": 1,
            "test_limited_ready": 1,
            "test_has_pilot": 1,
            "test_has_candidate": 1,
            "test_finance_safe": 1,
            "test_cooldown_clear": 1,
            "test_service_ready": 1,
            "test_port_ready": 1,
        }
        if seed:
            start.update(seed)
        self.state = {"SHU": start}
        self.world = ShuPulseWorld(EFFECTS, self.state)
        self.active = None
        self.delivered = []
        self.event_map = {row["id"]: row for row in self.arc["events"]}
        self.journal_map = {row["id"]: row for row in self.arc["journals"]}

    def cond(self, source):
        nodes = parse(source[1:-1])
        nodes = self._resolve_active_journal(nodes)
        return self.world.conditions(facts_only(nodes), "SHU")

    def _resolve_active_journal(self, nodes):
        result=[]
        for key, comparison, value in nodes:
            if key == "has_journal_entry":
                result.append(("has_variable", "=", "test_active_" + str(value)))
            elif isinstance(value, list):
                result.append((key, comparison, self._resolve_active_journal(value)))
            else:
                result.append((key, comparison, value))
        return result

    def invoke_event(self, event_id):
        event = self.event_map[event_id]
        if not self.cond(event["trigger"]):
            return False
        self.world.execute(parse(event["immediate"][1:-1]), "SHU")
        self.delivered.append(event_id)
        return True

    def activate(self, journal):
        self.world.journals = [("SHU", [("type", "=", journal["id"])])]
        for other in self.arc["journals"]:
            self.state["SHU"].pop("test_active_" + other["id"], None)
        self.state["SHU"]["test_active_" + journal["id"]] = 1
        self.active = journal
        top = parse(journal["script"][1:-1])
        immediate = next(body for key, _, body in top if key == "immediate")
        self.world.execute(immediate, "SHU")

    def handoff(self):
        moved = True
        while moved:
            moved = False
            for journal in self.arc["journals"]:
                if journal is self.active:
                    continue
                possible = next(body for key, _, body in parse(journal["script"][1:-1]) if key == "possible")
                eligible = self.world.conditions(facts_only(possible), "SHU")
                if eligible:
                    # Candidate JE must be inactive-possible and its predecessor must already have reached its authored goal.
                    if self.active and self.cond(self.active["goal"]):
                        self.activate(journal)
                        moved = True
                        break

    def pulse(self):
        assert self.active is not None
        assert not self.cond(self.active["goal"]), f"attempted to pulse completed JE: {self.active['id']}"
        assert not self.cond(self.active["exit_conditions"]), f"attempted to pulse exited JE: {self.active['id']}"
        top = parse(self.active["script"][1:-1])
        row = next(body for key, _, body in top if key == "on_monthly_pulse")
        effect = next(body for key, _, body in row if key == "effect")
        self.world.execute(facts_only(effect), "SHU")
        queued = [event for tag, event in self.world.events if tag == "SHU"]
        self.world.events = [(tag, event) for tag, event in self.world.events if tag != "SHU"]
        fired = [event for event in queued if self.invoke_event(event)]
        self.handoff()
        return fired

    def open(self):
        je = self.arc["journals"][0]
        self.assert_entry_eligible(je)
        self.activate(je)

    def assert_entry_eligible(self, journal):
        top = parse(journal["script"][1:-1])
        possible = next(body for key, _, body in top if key == "possible")
        assert self.world.conditions(facts_only(possible), "SHU"), f"not eligible: {journal['id']}"

    def choose(self, event_id, key):
        event = self.event_map[event_id]
        option = next(row for row in event["options"] if row["key"] == key)
        if option.get("trigger"):
            assert self.cond(option["trigger"]), f"option not legal: {event_id}/{key}"
        self.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
        self.handoff()

    def dispatch_until(self, event_id, max_days=200):
        for _ in range(max_days + 1):
            fired = self.pulse()
            if event_id in fired:
                return
            self.world.advance_days(1)
        raise AssertionError(f"queued {event_id} did not dispatch; state={self.state['SHU']}")

    def advance_review(self, day_count):
        for _ in range(day_count):
            self.world.advance_days(1)
            # Monthly callbacks, not daily: use day 30/60/.. pulse cadence.
            if _ % 30 == 29:
                self.pulse()


class ShuFoundationRuntimeTest(unittest.TestCase):
    def test_service_full_route_one_and_three_actual_event_lifecycle(self):
        for route, start, expected in ((1, "professional", 1), (3, "legacy_cap", 3)):
            with self.subTest(route=route):
                runtime = ShuRuntime("v03_shu_service_compact", {
                    "ywc_v03_initialized": 1,
                    "ywc_v03_release_version": 3,
                    "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
                    "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
                    "ywc_v03_active_arc_count": 1,
                    "ywc_v03_visible_task_count": 2,
                    "ywc_shu_v03_pilot_state": 1,
                })
                runtime.open()
                self.assertEqual(runtime.state["SHU"].get("ywc_v03_shu_v03_shu_service_compact_started"), 1)
                runtime.dispatch_until("ywc_shu.1010")
                runtime.choose("ywc_shu.1010", "court_seal")
                self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"), 1011)
                self.assertEqual(runtime.pulse(), [])
                self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"), 1011)
                runtime.world.advance_days(89)
                self.assertEqual(runtime.pulse(), [])
                runtime.world.advance_days(1)
                self.assertIn("ywc_shu.1011", runtime.pulse())
                runtime.choose("ywc_shu.1011", "cap_arrears" if route == 1 else "local_ledger")
                runtime.dispatch_until("ywc_shu.1012")
                runtime.choose("ywc_shu.1012", "professional_list" if route == 1 else "joint_list")
                runtime.dispatch_until("ywc_shu.1013")
                runtime.choose("ywc_shu.1013", start)
                self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_route"), route)
                if route == 1:
                    self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_cost_paid"), 1)
                    self.assertEqual(runtime.world.treasury["SHU"], -500)
                runtime.dispatch_until("ywc_shu.1014")
                runtime.choose("ywc_shu.1014", "check_supply")
                runtime.dispatch_until("ywc_shu.1015")
                runtime.choose("ywc_shu.1015", "accept_appointments")
                runtime.handoff()
                self.assertEqual(runtime.active["id"], "ywc_je_v03_shu_service_successor")
                runtime.advance_review(179)
                self.assertNotIn("ywc_shu_service_review_mature", runtime.state["SHU"])
                runtime.advance_review(1)
                runtime.dispatch_until("ywc_shu.1017")
                final = next(o for o in runtime.event_map["ywc_shu.1017"]["options"] if o["key"] == "settle_service")
                self.assertTrue(runtime.cond(final["trigger"]))
                runtime.choose("ywc_shu.1017", "settle_service")
                self.assertTrue(runtime.cond(runtime.active["goal"]))
                self.assertFalse(runtime.cond(runtime.active["exit_conditions"]))
                self.assertEqual(runtime.state["SHU"].get("ywc_v03_shu_v03_shu_service_compact_outcome"), expected)

    def test_stale_service_payment_option_cannot_mark_route_or_advance(self):
        runtime = ShuRuntime("v03_shu_service_compact", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
            "ywc_shu_v03_pilot_state": 1,
        })
        runtime.open()
        runtime.dispatch_until("ywc_shu.1010"); runtime.choose("ywc_shu.1010", "court_seal")
        runtime.dispatch_until("ywc_shu.1011"); runtime.choose("ywc_shu.1011", "cap_arrears")
        runtime.dispatch_until("ywc_shu.1012"); runtime.choose("ywc_shu.1012", "professional_list")
        runtime.dispatch_until("ywc_shu.1013")
        option = next(o for o in runtime.event_map["ywc_shu.1013"]["options"] if o["key"] == "professional")
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.state["SHU"]["gold_reserves"] = 0  # funds change after the displayed trigger
        runtime.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
        self.assertNotIn("ywc_shu_service_cost_paid", runtime.state["SHU"])
        self.assertNotIn("ywc_shu_service_route", runtime.state["SHU"])
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"), 1013)
        self.assertEqual(runtime.world.treasury["SHU"], 0)

    def test_1011_verify_payroll_uses_full_price_without_route_candidate(self):
        runtime = ShuRuntime("v03_shu_service_compact", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
            "ywc_shu_v03_pilot_state": 1,
        })
        runtime.open()
        runtime.dispatch_until("ywc_shu.1010"); runtime.choose("ywc_shu.1010", "court_seal")
        runtime.dispatch_until("ywc_shu.1011")
        option = next(o for o in runtime.event_map["ywc_shu.1011"]["options"] if o["key"] == "verify_payroll")
        self.assertNotIn("ywc_shu_service_route_candidate", runtime.state["SHU"])
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.choose("ywc_shu.1011", "verify_payroll")
        self.assertEqual(runtime.world.treasury["SHU"], -1000)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_cost_paid"), 1)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_payroll_checked"), 1)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"), 1012)

    def test_1011_full_payment_fulfills_later_professional_fee_without_recharge(self):
        runtime = ShuRuntime("v03_shu_service_compact", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
            "ywc_shu_v03_pilot_state": 1,
        })
        runtime.open()
        runtime.dispatch_until("ywc_shu.1010"); runtime.choose("ywc_shu.1010", "court_seal")
        runtime.dispatch_until("ywc_shu.1011"); runtime.choose("ywc_shu.1011", "verify_payroll")
        runtime.dispatch_until("ywc_shu.1012"); runtime.choose("ywc_shu.1012", "professional_list")
        runtime.dispatch_until("ywc_shu.1013")
        runtime.state["SHU"]["gold_reserves"] = 0
        option = next(o for o in runtime.event_map["ywc_shu.1013"]["options"] if o["key"] == "professional")
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.choose("ywc_shu.1013", "professional")
        self.assertEqual(runtime.world.treasury["SHU"], -1000)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_route"), 1)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"), 1014)

    def test_prepaid_professional_rechecks_current_choice_eligibility_after_popup(self):
        for invalidation in ("default", "bankruptcy", "negative_income", "professional_qualification"):
            with self.subTest(invalidation=invalidation):
                runtime = ShuRuntime("v03_shu_service_compact", {
                    "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                    "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
                    "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
                    "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
                    "ywc_shu_v03_pilot_state": 1,
                })
                runtime.open()
                runtime.dispatch_until("ywc_shu.1010"); runtime.choose("ywc_shu.1010", "court_seal")
                runtime.dispatch_until("ywc_shu.1011"); runtime.choose("ywc_shu.1011", "verify_payroll")
                runtime.dispatch_until("ywc_shu.1012"); runtime.choose("ywc_shu.1012", "professional_list")
                runtime.dispatch_until("ywc_shu.1013")
                runtime.state["SHU"]["gold_reserves"] = 0
                option = next(o for o in runtime.event_map["ywc_shu.1013"]["options"] if o["key"] == "professional")
                self.assertTrue(runtime.cond(option["trigger"]))
                self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_cost_paid"), 1)
                if invalidation == "default": runtime.state["SHU"]["in_default"] = 1
                elif invalidation == "bankruptcy": runtime.world.modifiers.append(("SHU", {"modifier": "declared_bankruptcy"}))
                elif invalidation == "negative_income": runtime.state["SHU"]["net_fixed_income"] = -1
                else:
                    runtime.state["SHU"].pop("test_law_law_professional_army", None)
                    runtime.state["SHU"].pop("test_owned_building_building_barrack", None)
                runtime.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
                self.assertNotIn("ywc_shu_service_route", runtime.state["SHU"])
                self.assertNotIn("ywc_shu_service_route_candidate", runtime.state["SHU"])
                self.assertNotEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"), 1014)
                self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"), 1013)
                self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_cost_paid"), 1)
                self.assertEqual(runtime.world.treasury["SHU"], -1000)

    def test_full_register_share_returns_to_real_fee_payment_before_observation(self):
        runtime = ShuRuntime("v03_shu_port_treasury", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
        })
        runtime.open()
        for event, option in (("ywc_shu.1018", "unified_customs"), ("ywc_shu.1019", "publish_books"),
                              ("ywc_shu.1020", "refuse_credit"), ("ywc_shu.1021", "current_law_review")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1022")
        self.assertTrue(runtime.cond(next(o["trigger"] for o in runtime.event_map["ywc_shu.1022"]["options"] if o["key"] == "register_share")))
        runtime.choose("ywc_shu.1022", "register_share")
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_pending_event"), 1022)
        self.assertNotIn("ywc_shu_port_receipts_checked", runtime.state["SHU"])
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_arrears_open"), 1)
        self.assertNotIn("ywc_shu_port_fee_paid", runtime.state["SHU"])
        runtime.dispatch_until("ywc_shu.1022")
        runtime.choose("ywc_shu.1022", "pay_verification")
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_fee_paid"), 1)
        self.assertEqual(runtime.world.treasury["SHU"], -1000)
        runtime.dispatch_until("ywc_shu.1023"); runtime.choose("ywc_shu.1023", "central_form")
        runtime.dispatch_until("ywc_shu.1024"); runtime.choose("ywc_shu.1024", "central_burden")
        self.assertNotIn("ywc_shu_port_review_mature", runtime.state["SHU"])
        runtime.advance_review(179)
        self.assertNotIn("ywc_shu_port_review_mature", runtime.state["SHU"])
        runtime.advance_review(1); runtime.pulse()
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_review_mature"), 1)
        runtime.dispatch_until("ywc_shu.1025")
        option = next(o for o in runtime.event_map["ywc_shu.1025"]["options"] if o["key"] == "settle_unified")
        self.assertTrue(runtime.cond(option["trigger"]))
        for key, helper in (("settle_unified", "ywc_shu_port_terminal_unified_ready"),
                            ("settle_share", "ywc_shu_port_terminal_shared_ready"),
                            ("settle_legacy", "ywc_shu_port_terminal_limited_ready")):
            terminal = next(o for o in runtime.event_map["ywc_shu.1025"]["options"] if o["key"] == key)
            self.assertEqual(terminal["trigger"].strip(), "{\n" + helper + " = yes\n}")
        runtime.choose("ywc_shu.1025", "settle_unified")
        self.assertEqual(runtime.state["SHU"].get("ywc_v03_shu_v03_shu_port_treasury_outcome"), 1)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_arrears_open"), 1)

    def test_waived_compact_is_eligible_at_zero_cash_from_existing_report(self):
        runtime = ShuRuntime("v03_shu_service_compact", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
            "ywc_shu_v03_pilot_state": 1,
        })
        runtime.open()
        for event, option in (("ywc_shu.1010", "garrison_seal"), ("ywc_shu.1011", "local_ledger"),
                              ("ywc_shu.1012", "professional_list")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1013")
        runtime.state["SHU"]["gold_reserves"] = 0
        option = next(o for o in runtime.event_map["ywc_shu.1013"]["options"] if o["key"] == "provincial_compact")
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.choose("ywc_shu.1013", "provincial_compact")
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_compact_fee_waived"), 1)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_route"), 2)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"), 1014)
        self.assertNotIn("ywc_shu_service_cost_paid", runtime.state["SHU"])
        self.assertEqual(runtime.world.treasury["SHU"], 0)

    def test_waiver_effect_time_default_requeues_without_new_route_markers(self):
        runtime = ShuRuntime("v03_shu_service_compact", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
            "ywc_shu_v03_pilot_state": 1,
        })
        runtime.open()
        for event, option in (("ywc_shu.1010", "garrison_seal"), ("ywc_shu.1011", "local_ledger"),
                              ("ywc_shu.1012", "professional_list")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1013")
        option = next(o for o in runtime.event_map["ywc_shu.1013"]["options"] if o["key"] == "provincial_compact")
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.state["SHU"]["in_default"] = True
        runtime.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
        self.assertNotIn("ywc_shu_service_route", runtime.state["SHU"])
        self.assertNotIn("ywc_shu_service_compact_fee_waived", runtime.state["SHU"])
        self.assertNotIn("ywc_shu_service_cost_paid", runtime.state["SHU"])
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"), 1013)
        self.assertEqual(runtime.world.treasury["SHU"], 0)

    def test_waiver_effect_time_bankruptcy_and_negative_income_do_not_progress(self):
        for failure in ("bankruptcy", "negative_income"):
            with self.subTest(failure=failure):
                runtime = ShuRuntime("v03_shu_service_compact", {
                    "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                    "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
                    "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
                    "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
                    "ywc_shu_v03_pilot_state": 1,
                })
                runtime.open()
                for event, option in (("ywc_shu.1010", "garrison_seal"), ("ywc_shu.1011", "local_ledger"),
                                      ("ywc_shu.1012", "professional_list")):
                    runtime.dispatch_until(event); runtime.choose(event, option)
                runtime.dispatch_until("ywc_shu.1013")
                option = next(o for o in runtime.event_map["ywc_shu.1013"]["options"] if o["key"] == "provincial_compact")
                self.assertTrue(runtime.cond(option["trigger"]))
                if failure == "bankruptcy": runtime.world.modifiers.append(("SHU", {"modifier": "declared_bankruptcy"}))
                else: runtime.state["SHU"]["net_fixed_income"] = -1
                runtime.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
                self.assertNotIn("ywc_shu_service_route", runtime.state["SHU"])
                self.assertNotIn("ywc_shu_service_compact_fee_waived", runtime.state["SHU"])
                self.assertNotIn("ywc_shu_service_cost_paid", runtime.state["SHU"])
                self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"), 1013)
                self.assertEqual(runtime.world.treasury["SHU"], 0)

    def test_stale_port_payment_option_cannot_mark_receipts_or_advance(self):
        runtime = ShuRuntime("v03_shu_port_treasury", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
        })
        runtime.open()
        runtime.dispatch_until("ywc_shu.1018"); runtime.choose("ywc_shu.1018", "unified_customs")
        runtime.dispatch_until("ywc_shu.1019"); runtime.choose("ywc_shu.1019", "publish_books")
        runtime.dispatch_until("ywc_shu.1020"); runtime.choose("ywc_shu.1020", "refuse_credit")
        runtime.dispatch_until("ywc_shu.1021"); runtime.choose("ywc_shu.1021", "current_law_review")
        runtime.dispatch_until("ywc_shu.1022")
        option=next(o for o in runtime.event_map["ywc_shu.1022"]["options"] if o["key"]=="pay_verification")
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.state["SHU"]["gold_reserves"] = 0
        runtime.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
        self.assertNotIn("ywc_shu_port_fee_paid", runtime.state["SHU"])
        self.assertNotIn("ywc_shu_port_receipts_checked", runtime.state["SHU"])
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_pending_event"), 1022)
        self.assertEqual(runtime.world.treasury["SHU"], 0)

    def test_service_loss_restarts_real_180_day_clock_and_withdrawal_exits_as_failure(self):
        runtime=ShuRuntime("v03_shu_service_compact", {
            "ywc_v03_initialized":1,"ywc_v03_release_version":3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled":1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome":2,
            "ywc_v03_active_arc_count":1,"ywc_v03_visible_task_count":2,
            "ywc_shu_v03_pilot_state":1,
        })
        runtime.open()
        for event,option in (("ywc_shu.1010","court_seal"),
                             ("ywc_shu.1011","local_ledger"),
                             ("ywc_shu.1012","joint_list"),
                             ("ywc_shu.1013","legacy_cap"),
                             ("ywc_shu.1014","reduce_target"),
                             ("ywc_shu.1015","accept_appointments")):
            runtime.dispatch_until(event);runtime.choose(event,option)
        self.assertEqual(runtime.active["id"],"ywc_je_v03_shu_service_successor")
        runtime.advance_review(90)
        runtime.state["SHU"]["in_default"]=True
        runtime.pulse()
        self.assertNotIn("ywc_shu_service_review_due",runtime.state["SHU"])
        self.assertNotIn("ywc_shu_service_review_mature",runtime.state["SHU"])
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_review_interrupted"),1)
        runtime.dispatch_until("ywc_shu.1016")
        runtime.state["SHU"]["in_default"]=False
        runtime.choose("ywc_shu.1016","retry_after_repair")
        runtime.advance_review(179)
        self.assertNotIn("ywc_shu_service_review_mature",runtime.state["SHU"])
        runtime.advance_review(1)
        runtime.pulse()
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_review_mature"),1)
        runtime.dispatch_until("ywc_shu.1017")
        runtime.choose("ywc_shu.1017","withdraw_at_close")
        self.assertFalse(runtime.cond(runtime.active["goal"]))
        self.assertTrue(runtime.cond(runtime.active["exit_conditions"]))
        self.assertEqual(runtime.state["SHU"].get("ywc_v03_shu_v03_shu_service_compact_outcome"),4)

    def test_port_withdrawal_is_terminal_failure_and_never_a_success_goal(self):
        runtime = ShuRuntime("v03_shu_port_treasury", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
        })
        runtime.open()
        for event, option in (("ywc_shu.1018", "unified_customs"),
                              ("ywc_shu.1019", "publish_books"),
                              ("ywc_shu.1020", "refuse_credit"),
                              ("ywc_shu.1021", "books_only"),
                              ("ywc_shu.1022", "pay_verification"),
                              ("ywc_shu.1023", "central_form")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1024")
        runtime.choose("ywc_shu.1024", "withdraw_port")
        je=runtime.active
        self.assertFalse(runtime.cond(je["goal"]))
        self.assertTrue(runtime.cond(je["exit_conditions"]))
        self.assertEqual(runtime.state["SHU"].get("ywc_v03_shu_v03_shu_port_treasury_outcome"), 5)

    def test_service_12_and_36_month_notices_are_elapsed_and_recover_through_real_queue(self):
        runtime=ShuRuntime("v03_shu_service_compact",{
            "ywc_v03_initialized":1,"ywc_v03_release_version":3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled":1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome":2,
            "ywc_v03_active_arc_count":1,"ywc_v03_visible_task_count":2,
        })
        runtime.open()
        runtime.dispatch_until("ywc_shu.1010")
        self.assertNotIn("ywc_shu_service_block_12_prompted",runtime.state["SHU"])
        runtime.world.advance_days(364);runtime.pulse()
        self.assertNotIn("ywc_shu_service_block_12_prompted",runtime.state["SHU"])
        runtime.world.advance_days(1)
        self.assertIn("ywc_shu.1016",runtime.pulse())
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_block_12_prompted"),1)
        option=next(o for o in runtime.event_map["ywc_shu.1016"]["options"] if o["key"]=="resume_service_contract")
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.choose("ywc_shu.1016","resume_service_contract")
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"),1010)
        runtime.world.advance_days(729);runtime.pulse()
        self.assertNotIn("ywc_shu_service_block_36_prompted",runtime.state["SHU"])
        runtime.world.advance_days(1)
        # The overdue notice queues while the resumed normal story is delivered;
        # it must survive that event's real 90-day shared delivery cooldown.
        self.assertEqual(runtime.pulse(), [])
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_notice_pending_event"),1016)
        runtime.world.advance_days(88)
        self.assertEqual(runtime.pulse(), [])
        runtime.world.advance_days(1)
        self.assertIn("ywc_shu.1016",runtime.pulse())
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_block_36_prompted"),1)

    def test_port_stale_success_effect_rechecks_owned_port_target(self):
        runtime = ShuRuntime("v03_shu_port_treasury", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
        })
        runtime.open()
        for event, option in (("ywc_shu.1018", "unified_customs"), ("ywc_shu.1019", "publish_books"),
                              ("ywc_shu.1020", "refuse_credit"), ("ywc_shu.1021", "current_law_review"),
                              ("ywc_shu.1022", "pay_verification"), ("ywc_shu.1023", "central_form"),
                              ("ywc_shu.1024", "central_burden")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.advance_review(180); runtime.dispatch_until("ywc_shu.1025")
        option = next(o for o in runtime.event_map["ywc_shu.1025"]["options"] if o["key"] == "settle_unified")
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.state["SHU"].pop("test_owned_building_building_port", None)
        self.assertFalse(runtime.cond(option["trigger"]))
        runtime.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
        self.assertNotIn("ywc_v03_shu_v03_shu_port_treasury_outcome", runtime.state["SHU"])
        self.assertNotIn("ywc_v03_shu_v03_shu_port_treasury_settled", runtime.state["SHU"])

    def test_port_reduced_target_uses_real_inland_office_after_port_loss(self):
        runtime = ShuRuntime("v03_shu_port_treasury", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
        })
        runtime.open()
        for event, option in (("ywc_shu.1018", "unified_customs"), ("ywc_shu.1019", "publish_books"),
                              ("ywc_shu.1020", "refuse_credit"), ("ywc_shu.1021", "current_law_review"),
                              ("ywc_shu.1022", "pay_verification"), ("ywc_shu.1023", "central_form")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1024")
        runtime.state["SHU"].pop("test_owned_building_building_port", None)
        self.assertTrue(runtime.cond(next(o["trigger"] for o in runtime.event_map["ywc_shu.1024"]["options"] if o["key"]=="reduce_burden")))
        runtime.choose("ywc_shu.1024", "reduce_burden")
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_route"), 4)
        self.assertNotIn("ywc_shu_port_review_mature", runtime.state["SHU"])
        self.assertNotIn("ywc_shu_port_review_interrupted", runtime.state["SHU"])
        runtime.advance_review(179)
        self.assertNotIn("ywc_shu_port_review_mature", runtime.state["SHU"])
        runtime.advance_review(1); runtime.pulse()
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_review_mature"), 1)
        self.assertTrue(runtime.cond("{ ywc_shu_v03_port_execution_ready = yes }"))
        runtime.dispatch_until("ywc_shu.1025")
        runtime.choose("ywc_shu.1025", "settle_legacy")
        self.assertEqual(runtime.state["SHU"].get("ywc_v03_shu_v03_shu_port_treasury_outcome"), 3)

    def test_register_share_lower_target_reaches_real_limited_terminal(self):
        runtime = ShuRuntime("v03_shu_port_treasury", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
        })
        runtime.open()
        for event, option in (("ywc_shu.1018", "legacy_collection"), ("ywc_shu.1019", "publish_books"),
                              ("ywc_shu.1020", "refuse_credit"), ("ywc_shu.1021", "current_law_review")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1022")
        runtime.choose("ywc_shu.1022", "register_share")
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_arrears_open"), 1)
        self.assertNotIn("ywc_shu_port_fee_paid", runtime.state["SHU"])
        self.assertEqual(runtime.world.treasury["SHU"], 0)
        runtime.dispatch_until("ywc_shu.1023"); runtime.choose("ywc_shu.1023", "legacy_form")
        runtime.dispatch_until("ywc_shu.1024"); runtime.choose("ywc_shu.1024", "central_burden")
        runtime.advance_review(180); runtime.dispatch_until("ywc_shu.1025")
        option = next(o for o in runtime.event_map["ywc_shu.1025"]["options"] if o["key"] == "settle_legacy")
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.choose("ywc_shu.1025", "settle_legacy")
        self.assertEqual(runtime.state["SHU"].get("ywc_v03_shu_v03_shu_port_treasury_outcome"), 3)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_arrears_open"), 1)

    def test_recovered_port_does_not_break_paid_inland_narrow_watch(self):
        runtime = ShuRuntime("v03_shu_port_treasury", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
        })
        runtime.open()
        for event, option in (("ywc_shu.1018", "unified_customs"), ("ywc_shu.1019", "publish_books"),
                              ("ywc_shu.1020", "refuse_credit"), ("ywc_shu.1021", "current_law_review"),
                              ("ywc_shu.1022", "pay_verification"), ("ywc_shu.1023", "central_form")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1024")
        runtime.state["SHU"].pop("test_owned_building_building_port", None)
        runtime.choose("ywc_shu.1024", "reduce_burden")
        runtime.advance_review(90)
        runtime.state["SHU"]["test_owned_building_building_port"] = 1
        runtime.pulse()
        self.assertNotIn("ywc_shu_port_review_interrupted", runtime.state["SHU"])
        self.assertNotIn("ywc_shu_port_review_mature", runtime.state["SHU"])
        runtime.advance_review(89)
        self.assertNotIn("ywc_shu_port_review_mature", runtime.state["SHU"])
        runtime.advance_review(1); runtime.pulse()
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_review_mature"), 1)
        runtime.dispatch_until("ywc_shu.1025"); runtime.choose("ywc_shu.1025", "settle_legacy")
        self.assertEqual(runtime.state["SHU"].get("ywc_v03_shu_v03_shu_port_treasury_outcome"), 3)

    def test_losing_inland_office_clears_narrow_maturity_without_upgrading_route(self):
        runtime = ShuRuntime("v03_shu_port_treasury", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
        })
        runtime.open()
        for event, option in (("ywc_shu.1018", "unified_customs"), ("ywc_shu.1019", "publish_books"),
                              ("ywc_shu.1020", "refuse_credit"), ("ywc_shu.1021", "current_law_review"),
                              ("ywc_shu.1022", "pay_verification"), ("ywc_shu.1023", "central_form")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1024")
        runtime.state["SHU"].pop("test_owned_building_building_port", None)
        runtime.choose("ywc_shu.1024", "reduce_burden")
        runtime.advance_review(180); runtime.pulse()
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_review_mature"), 1)
        runtime.state["SHU"].pop("test_owned_building_building_government_administration", None)
        runtime.pulse()
        self.assertNotIn("ywc_shu_port_review_mature", runtime.state["SHU"])
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_review_interrupted"), 1)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_route"), 4)

    def test_1011_stale_full_price_finance_failure_retries_without_payment_markers(self):
        for failure in ("cash", "default", "negative_income"):
            with self.subTest(failure=failure):
                runtime = ShuRuntime("v03_shu_service_compact", {
                    "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                    "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
                    "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
                    "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
                    "ywc_shu_v03_pilot_state": 1,
                })
                runtime.open()
                runtime.dispatch_until("ywc_shu.1010"); runtime.choose("ywc_shu.1010", "court_seal")
                runtime.dispatch_until("ywc_shu.1011")
                option = next(o for o in runtime.event_map["ywc_shu.1011"]["options"] if o["key"] == "verify_payroll")
                self.assertTrue(runtime.cond(option["trigger"]))
                if failure == "cash": runtime.state["SHU"]["gold_reserves"] = 0
                elif failure == "default": runtime.state["SHU"]["in_default"] = True
                else: runtime.state["SHU"]["net_fixed_income"] = -1
                runtime.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
                self.assertNotIn("ywc_shu_service_cost_paid", runtime.state["SHU"])
                self.assertNotIn("ywc_shu_service_payroll_checked", runtime.state["SHU"])
                self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"), 1011)
                self.assertEqual(runtime.world.treasury["SHU"], 0)

    def test_1022_verification_uses_full_fee_when_no_prior_fee_paid(self):
        runtime = ShuRuntime("v03_shu_port_treasury", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
        })
        runtime.open()
        for event, option in (("ywc_shu.1018", "unified_customs"), ("ywc_shu.1019", "publish_books"),
                              ("ywc_shu.1020", "refuse_credit"), ("ywc_shu.1021", "current_law_review")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1022")
        option = next(o for o in runtime.event_map["ywc_shu.1022"]["options"] if o["key"] == "pay_verification")
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.choose("ywc_shu.1022", "pay_verification")
        self.assertEqual(runtime.world.treasury["SHU"], -1000)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_fee_amount"), 1000)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_receipts_checked"), 1)
        runtime.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
        self.assertEqual(runtime.world.treasury["SHU"], -1000)

    def test_1020_consult_half_fee_fulfills_same_obligation_without_second_charge(self):
        runtime = ShuRuntime("v03_shu_port_treasury", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
        })
        runtime.open()
        for event, option in (("ywc_shu.1018", "unified_customs"), ("ywc_shu.1019", "publish_books")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1020"); runtime.choose("ywc_shu.1020", "consult_only")
        self.assertEqual(runtime.world.treasury["SHU"], -500)
        runtime.dispatch_until("ywc_shu.1021"); runtime.choose("ywc_shu.1021", "current_law_review")
        runtime.dispatch_until("ywc_shu.1022"); runtime.choose("ywc_shu.1022", "pay_verification")
        self.assertEqual(runtime.world.treasury["SHU"], -500)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_fee_amount"), 500)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_receipts_checked"), 1)

    def test_1020_consult_half_fee_stale_finance_failure_retries(self):
        for failure in ("cash", "default", "negative_income"):
            with self.subTest(failure=failure):
                runtime = ShuRuntime("v03_shu_port_treasury", {
                    "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                    "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
                    "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
                    "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
                })
                runtime.open()
                runtime.dispatch_until("ywc_shu.1018"); runtime.choose("ywc_shu.1018", "unified_customs")
                runtime.dispatch_until("ywc_shu.1019"); runtime.choose("ywc_shu.1019", "publish_books")
                runtime.dispatch_until("ywc_shu.1020")
                option = next(o for o in runtime.event_map["ywc_shu.1020"]["options"] if o["key"] == "consult_only")
                self.assertTrue(runtime.cond(option["trigger"]))
                if failure == "cash": runtime.state["SHU"]["gold_reserves"] = 0
                elif failure == "default": runtime.state["SHU"]["in_default"] = True
                else: runtime.state["SHU"]["net_fixed_income"] = -1
                runtime.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
                self.assertNotIn("ywc_shu_port_fee_paid", runtime.state["SHU"])
                self.assertNotIn("ywc_shu_port_fee_amount", runtime.state["SHU"])
                self.assertNotIn("ywc_shu_port_merchant_review", runtime.state["SHU"])
                self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_pending_event"), 1020)
                self.assertEqual(runtime.world.treasury["SHU"], 0)

    def test_1022_full_fee_stale_default_retries_without_receipt_flag(self):
        runtime = ShuRuntime("v03_shu_port_treasury", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
        })
        runtime.open()
        for event, option in (("ywc_shu.1018", "unified_customs"), ("ywc_shu.1019", "publish_books"),
                              ("ywc_shu.1020", "refuse_credit"), ("ywc_shu.1021", "current_law_review")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1022")
        option = next(o for o in runtime.event_map["ywc_shu.1022"]["options"] if o["key"] == "pay_verification")
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.state["SHU"]["in_default"] = True
        runtime.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
        self.assertNotIn("ywc_shu_port_fee_paid", runtime.state["SHU"])
        self.assertNotIn("ywc_shu_port_receipts_checked", runtime.state["SHU"])
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_pending_event"), 1022)
        self.assertEqual(runtime.world.treasury["SHU"], 0)

    def test_service_nonwaived_provincial_route_pays_quarter_fee(self):
        runtime = ShuRuntime("v03_shu_service_compact", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
            "ywc_shu_v03_pilot_state": 1,
        })
        runtime.open()
        for event, option in (("ywc_shu.1010", "court_seal"), ("ywc_shu.1011", "cap_arrears"),
                              ("ywc_shu.1012", "professional_list")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1013")
        runtime.choose("ywc_shu.1013", "provincial_compact")
        self.assertEqual(runtime.world.treasury["SHU"], -250)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_paid_amount"), 250)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_route"), 2)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_cost_paid"), 1)

    def test_local_review_waives_only_provincial_route_not_professional(self):
        runtime = ShuRuntime("v03_shu_service_compact", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
            "ywc_shu_v03_pilot_state": 1,
        })
        runtime.open()
        for event, option in (("ywc_shu.1010", "garrison_seal"), ("ywc_shu.1011", "local_ledger"),
                              ("ywc_shu.1012", "professional_list")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1013")
        runtime.choose("ywc_shu.1013", "professional")
        self.assertEqual(runtime.world.treasury["SHU"], -500)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_route"), 1)
        self.assertNotIn("ywc_shu_service_compact_fee_waived", runtime.state["SHU"])

    def test_stale_professional_qualification_cannot_buy_full_price_and_can_retry(self):
        runtime = ShuRuntime("v03_shu_service_compact", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
            "ywc_shu_v03_pilot_state": 1,
        })
        runtime.open()
        for event, option in (("ywc_shu.1010", "court_seal"), ("ywc_shu.1011", "cap_arrears"),
                              ("ywc_shu.1012", "professional_list")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1013")
        option = next(o for o in runtime.event_map["ywc_shu.1013"]["options"] if o["key"] == "professional")
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.state["SHU"].pop("test_law_law_professional_army", None)
        runtime.state["SHU"].pop("test_owned_building_building_barrack", None)
        runtime.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
        self.assertNotIn("ywc_shu_service_cost_paid", runtime.state["SHU"])
        self.assertNotIn("ywc_shu_service_route", runtime.state["SHU"])
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_pending_event"), 1013)
        self.assertEqual(runtime.world.treasury["SHU"], 0)

    def test_service_waived_provincial_route_does_not_debit(self):
        runtime = ShuRuntime("v03_shu_service_compact", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
            "ywc_shu_v03_pilot_state": 1,
        })
        runtime.open()
        for event, option in (("ywc_shu.1010", "garrison_seal"), ("ywc_shu.1011", "local_ledger"),
                              ("ywc_shu.1012", "professional_list")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1013")
        runtime.choose("ywc_shu.1013", "provincial_compact")
        self.assertEqual(runtime.world.treasury["SHU"], 0)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_compact_fee_waived"), 1)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_route"), 2)

    def test_m1_fiscal_catalog_arc_matches_reviewfix_before_snapshot(self):
        current_arc = next(a for a in CATALOG["arcs"] if a["slug"] == "v03_shu_fiscal_register")
        canonical = json.dumps(current_arc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), "c9d2097f2d67b9a1ad0781cac6f047ab07372db905c0fcf83fe860f5ed75da92")

    def test_service_healthy_over_36_months_then_loss_starts_fresh_clock(self):
        runtime = ShuRuntime("v03_shu_service_compact", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
            "ywc_shu_v03_pilot_state": 1,
        })
        runtime.open()
        for event, option in (("ywc_shu.1010", "court_seal"), ("ywc_shu.1011", "cap_arrears"),
                              ("ywc_shu.1012", "professional_list"), ("ywc_shu.1013", "professional"),
                              ("ywc_shu.1014", "check_supply"), ("ywc_shu.1015", "accept_appointments")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        for day in range(1200):
            runtime.world.advance_days(1)
            if day % 30 == 29:
                runtime.pulse()
        self.assertNotIn("ywc_shu_service_block_36_started", runtime.state["SHU"])
        self.assertNotIn("ywc_shu_service_block_36_prompted", runtime.state["SHU"])
        runtime.state["SHU"].pop("test_owned_building_building_government_administration", None)
        runtime.pulse()
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_block_12_started"), 1)
        self.assertNotIn("ywc_shu_service_block_12_prompted", runtime.state["SHU"])
        for day in range(364):
            runtime.world.advance_days(1)
            if day % 30 == 29: runtime.pulse()
        self.assertNotIn("ywc_shu_service_block_12_prompted", runtime.state["SHU"])
        runtime.world.advance_days(1); runtime.pulse()
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_service_block_12_prompted"), 1)

    def test_parallel_service_and_port_entries_keep_independent_queues_and_shared_slots(self):
        runtime=ShuRuntime("v03_shu_service_compact",{
            "ywc_v03_initialized":1,"ywc_v03_release_version":3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled":1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome":2,
            "ywc_v03_active_arc_count":1,"ywc_v03_visible_task_count":2,
        })
        runtime.open()
        port=arc("v03_shu_port_treasury")["journals"][0]
        port_top=parse(port["script"][1:-1])
        port_possible=next(body for key,_,body in port_top if key=="possible")
        self.assertTrue(runtime.world.conditions(facts_only(port_possible),"SHU"))
        runtime.world.journals.append(("SHU",[("type","=",port["id"])]))
        runtime.state["SHU"]["test_active_"+port["id"]]=1
        port_immediate=next(body for key,_,body in port_top if key=="immediate")
        runtime.world.execute(port_immediate,"SHU")
        self.assertEqual(runtime.state["SHU"].get("ywc_v03_active_arc_count"),3)
        self.assertEqual(runtime.state["SHU"].get("ywc_v03_visible_task_count"),4)

        # Run both authored monthly callbacks in a stable order against the
        # same country and shared 90-day delivery effect.
        fired=[]
        for journal in (runtime.arc["journals"][0],port):
            top=parse(journal["script"][1:-1])
            pulse=next(body for key,_,body in top if key=="on_monthly_pulse")
            effect=next(body for key,_,body in pulse if key=="effect")
            runtime.world.execute(facts_only(effect),"SHU")
            queued=[event for tag,event in runtime.world.events if tag=="SHU"]
            runtime.world.events=[(tag,event) for tag,event in runtime.world.events if tag!="SHU"]
            for event_id in queued:
                event=next(row for source_arc in (runtime.arc,arc("v03_shu_port_treasury")) for row in source_arc["events"] if row["id"]==event_id)
                if runtime.cond(event["trigger"]):
                    runtime.world.execute(parse(event["immediate"][1:-1]),"SHU")
                    fired.append(event_id)
        self.assertIn("ywc_shu.1010",fired)
        self.assertNotIn("ywc_shu.1018",fired)
        self.assertEqual(runtime.state["SHU"].get("ywc_shu_port_pending_event"),1018)
        self.assertNotIn("ywc_shu_service_pending_event",runtime.state["SHU"])
        self.assertEqual(runtime.state["SHU"].get("ywc_v03_active_arc_count"),3)

    def test_port_actual_event_chain_routes_one_and_three_to_distinct_terminals(self):
        for first, expected in (("unified_customs", 1), ("legacy_collection", 3)):
            with self.subTest(first=first):
                runtime = ShuRuntime("v03_shu_port_treasury", {
                    "ywc_v03_initialized": 1,
                    "ywc_v03_release_version": 3,
                    "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
                    "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
                    "ywc_v03_active_arc_count": 1,
                    "ywc_v03_visible_task_count": 2,
                })
                runtime.open()
                runtime.dispatch_until("ywc_shu.1018")
                runtime.choose("ywc_shu.1018", first)
                runtime.dispatch_until("ywc_shu.1019")
                runtime.choose("ywc_shu.1019", "publish_books")
                runtime.dispatch_until("ywc_shu.1020")
                runtime.choose("ywc_shu.1020", "refuse_credit")
                runtime.dispatch_until("ywc_shu.1021")
                runtime.choose("ywc_shu.1021", "current_law_review")
                runtime.dispatch_until("ywc_shu.1022")
                runtime.choose("ywc_shu.1022", "pay_verification")
                self.assertEqual(runtime.world.treasury["SHU"], -1000)
                runtime.dispatch_until("ywc_shu.1023")
                runtime.choose("ywc_shu.1023", "central_form")
                runtime.dispatch_until("ywc_shu.1024")
                runtime.choose("ywc_shu.1024", "central_burden")
                runtime.advance_review(180)
                runtime.dispatch_until("ywc_shu.1025")
                option = "settle_unified" if expected == 1 else "settle_legacy"
                runtime.choose("ywc_shu.1025", option)
                self.assertTrue(runtime.cond(runtime.active["goal"]))
                self.assertFalse(runtime.cond(runtime.active["exit_conditions"]))
                self.assertEqual(runtime.state["SHU"].get("ywc_v03_shu_v03_shu_port_treasury_outcome"), expected)

    def test_service_stale_success_effect_rechecks_terminal_eligibility(self):
        runtime = ShuRuntime("v03_shu_service_compact", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
            "ywc_shu_v03_pilot_state": 1,
        })
        runtime.open()
        for event, option in (("ywc_shu.1010", "court_seal"), ("ywc_shu.1011", "cap_arrears"),
                              ("ywc_shu.1012", "professional_list"), ("ywc_shu.1013", "professional"),
                              ("ywc_shu.1014", "check_supply"), ("ywc_shu.1015", "accept_appointments")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.advance_review(180); runtime.dispatch_until("ywc_shu.1017")
        option = next(o for o in runtime.event_map["ywc_shu.1017"]["options"] if o["key"] == "settle_service")
        self.assertTrue(runtime.cond(option["trigger"]))
        runtime.state["SHU"]["in_default"] = True
        self.assertFalse(runtime.cond(option["trigger"]))
        runtime.world.execute(facts_only(parse(option["effect"][1:-1])), "SHU")
        self.assertNotIn("ywc_v03_shu_v03_shu_service_compact_outcome", runtime.state["SHU"])
        self.assertNotIn("ywc_v03_shu_v03_shu_service_compact_settled", runtime.state["SHU"])

    def test_port_narrow_target_is_real_inland_route_and_resets_watch(self):
        trigger = TRIGGERS["ywc_shu_v03_port_execution_ready"]
        rendered = str(trigger)
        self.assertIn("ywc_shu_v03_inland_office_ready", rendered)
        self.assertIn("ywc_shu_v03_port_narrow_ready", rendered)
        helper = TRIGGERS["ywc_shu_v03_inland_office_ready"]
        self.assertIn("building_government_administration", str(helper))
        self.assertIn("occupancy", str(helper))

    def test_overdue_notice_preempts_repeated_normal_defer(self):
        runtime = ShuRuntime("v03_shu_port_treasury", {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_shu_v03_shu_fiscal_register_settled": 1,
            "ywc_v03_shu_v03_shu_fiscal_register_outcome": 2,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 2,
        })
        runtime.open()
        for event, option in (("ywc_shu.1018", "unified_customs"), ("ywc_shu.1019", "publish_books"),
                              ("ywc_shu.1020", "refuse_credit")):
            runtime.dispatch_until(event); runtime.choose(event, option)
        runtime.dispatch_until("ywc_shu.1021")
        runtime.state["SHU"].pop("test_law_law_mercantilism", None)
        runtime.state["SHU"].pop("test_law_law_protectionism", None)
        runtime.state["SHU"].pop("test_law_law_free_trade", None)
        runtime.choose("ywc_shu.1021", "wait_law")
        for day in range(1200):
            runtime.world.advance_days(1)
            if day % 30 == 29:
                fired = runtime.pulse()
                if "ywc_shu.1021" in fired:
                    runtime.choose("ywc_shu.1021", "wait_law")
        self.assertGreaterEqual(runtime.delivered.count("ywc_shu.1024"), 2)


if __name__ == "__main__":
    unittest.main()
