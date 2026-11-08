"""NMG lifecycle paths through the authored JE/event scripts and shared pulse."""
import json
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from clausewitz_harness import PulseWorld, parse
from tests.nmg_foundation_projection import foundation_catalog

# This legacy fixture admits exactly its three original foundation arcs.
CATALOG = foundation_catalog()
MOD = ROOT / "yongchang_world"
EFFECTS = (MOD / "common/scripted_effects/ywc_v03_nmg_effects.txt").read_text(encoding="utf-8-sig")
SHARED_EFFECTS = (MOD / "common/scripted_effects/ywc_v03_effects.txt").read_text(encoding="utf-8-sig")
DELIVERY_EFFECTS_PATH = MOD / "common/scripted_effects/ywc_v03_delivery_nmg_effects.txt"
DELIVERY_TRIGGERS_PATH = MOD / "common/scripted_triggers/ywc_v03_delivery_nmg_triggers.txt"
DELIVERY_EFFECTS = DELIVERY_EFFECTS_PATH.read_text(encoding="utf-8-sig") if DELIVERY_EFFECTS_PATH.exists() else ""
DELIVERY_TRIGGERS = DELIVERY_TRIGGERS_PATH.read_text(encoding="utf-8-sig") if DELIVERY_TRIGGERS_PATH.exists() else ""
TRIGGERS = (MOD / "common/scripted_triggers/ywc_v03_nmg_triggers.txt").read_text(encoding="utf-8-sig")
SHARED_TRIGGERS = (MOD / "common/scripted_triggers/ywc_v03_triggers.txt").read_text(encoding="utf-8-sig")
SOURCE_TRIGGER_DEFS = {k: b for k, _, b in parse(TRIGGERS + "\n" + SHARED_TRIGGERS + "\n" + DELIVERY_TRIGGERS)}
GENERATED_JES = {k: b for k, _, b in parse((MOD / "common/journal_entries/ywc_v03_country_nmg_journal.txt").read_text(encoding="utf-8-sig"))}
GENERATED_EVENTS = {k: b for k, _, b in parse((MOD / "events/ywc_v03_country_nmg_events.txt").read_text(encoding="utf-8-sig"))}


def field(nodes, name):
    return next(body for key, _, body in nodes if key == name)


def event_option(event_id, key):
    event = GENERATED_EVENTS[event_id]
    return next(body for name, _, body in event if name == "option"
                and field(body, "name") == f"{event_id}.{key}")


class NmgWorld(PulseWorld):
    """Interpret authored scripts; fixture only the engine-owned world facts."""
    # This older single-country interpreter cannot represent foreign event
    # recipients or incarnation-bound country scopes.  It must fail closed
    # at that boundary; test_v03_nmg_partner_response exercises the real
    # protocol with a multi-country interpreter and no fabricated acceptance.
    FOREIGN_PROTOCOL_BOUNDARIES = {"ywc_nmg_mexshare_can_offer", "ywc_nmg_mexshare_agreement_current",
                                   "ywc_nmg_jointproject_mex_eligible", "ywc_nmg_jointproject_jhg_eligible",
                                   "ywc_nmg_jointproject_agreement_current", "ywc_nmg_partner_renewal_available",
                                   "ywc_nmg_partner_renewal_menu_current"}
    SUPPORTED_CONDITION_PRIMITIVES = {
        "has_variable", "has_modifier", "exists", "always", "net_fixed_income",
        "bureaucracy", "gold_reserves", "yearly_gross_income", "scaled_debt",
        "in_default", "is_at_war", "trigger_if", "calc_true_if", "ywc_nmg_v03_has_owned_state",
        "owner", "is_owned_by", "any_scope_state", "any_scope_building", "is_building_type",
        "occupancy", "building_has_goods_shortage", "has_law_or_variant", "radical_fraction",
        "literacy_rate", "institution_investment_level", "is_subject", "is_subject_of",
        "overlord", "relations:root", "relations_threshold:poor", "any_interest_group",
        "is_interest_group_type", "ig_approval",
    }

    def __init__(self, countries):
        super().__init__(EFFECTS + "\n" + SHARED_EFFECTS + "\n" + DELIVERY_EFFECTS, countries)
        self.trigger_defs = copy.deepcopy(SOURCE_TRIGGER_DEFS)
        self._trigger_stack = set()
        self.events = []
        self.completed_journals = []
        self.failed_journals = []
        self.active_journal = None
        self.active_journals = set()
        self.current_building = None
        self.calendar_month = 0

    def advance_months(self, months=1):
        self.calendar_month += months
        return super().advance_months(months)

    def _validate_condition_tree(self, nodes):
        """Reject malformed supported primitives even beneath false branches."""
        comparisons = {"=", "!=", ">", ">=", "<", "<="}
        for key, comparison, value in nodes:
            if key == "owner" and (comparison, value) != ("=", "ROOT"):
                raise AssertionError(("unsupported NMG ownership shape", (key, comparison, value)))
            if isinstance(value, list):
                self._validate_condition_tree(value)
            if key == "institution_investment_level":
                if comparison != "=" or not isinstance(value, list):
                    raise ValueError("institution_investment_level requires a child block")
                names = [child for child, _, _ in value]
                if sorted(names) != ["institution", "value"]:
                    raise ValueError("institution_investment_level requires one institution and one value")
                institution_cmp, institution = next((cmp, body) for child, cmp, body in value if child == "institution")
                target = next((cmp, body) for child, cmp, body in value if child == "value")
                if institution_cmp != "=" or institution not in ("institution_schools",):
                    raise ValueError(f"unsupported institution {institution!r}")
                if target[0] not in comparisons or not isinstance(target[1], str):
                    raise ValueError("institution investment value requires a supported numeric comparison")
                try:
                    float(target[1])
                except ValueError as exc:
                    raise ValueError("institution investment threshold must be numeric") from exc
            elif key == "radical_fraction":
                if comparison != "=" or not isinstance(value, list):
                    raise ValueError("radical_fraction requires a value child block")
                if len(value) != 1 or value[0][0] != "value":
                    raise ValueError("radical_fraction requires exactly one value child")
                _, child_cmp, child_value = value[0]
                if child_cmp not in comparisons or not isinstance(child_value, str):
                    raise ValueError("radical_fraction requires a supported numeric comparison")
                try:
                    float(child_value)
                except ValueError as exc:
                    raise ValueError("radical_fraction threshold must be numeric") from exc
            elif key == "ig_approval":
                if comparison not in comparisons or not isinstance(value, str):
                    raise ValueError("ig_approval requires a supported numeric comparison")
                try:
                    float(value)
                except ValueError as exc:
                    raise ValueError("ig_approval threshold must be numeric") from exc

    def validate_condition(self, node, seen=frozenset()):
        """Validate all actual condition branches, including branches not taken."""
        key, comparison, value = node
        if key in self.FOREIGN_PROTOCOL_BOUNDARIES:
            if comparison != "=" or value not in ("yes", "no"):
                raise AssertionError(("invalid_foreign_protocol_boundary", node))
            return
        if key in {"AND", "OR", "NOT", "NOR"}:
            if comparison != "=" or not isinstance(value, list):
                raise AssertionError(("invalid_boolean_condition", node))
            for child in value:
                self.validate_condition(child, seen)
            return
        if key in self.trigger_defs:
            if comparison != "=" or value not in ("yes", "no") or key in seen:
                raise AssertionError(("invalid_or_recursive_scripted_trigger", node))
            body = self.trigger_defs[key]
            self._validate_condition_tree(body)
            for child in body:
                self.validate_condition(child, seen | {key})
            return
        if key == "has_journal_entry":
            if (comparison != "=" or not isinstance(value, str) or not value.startswith("ywc_je_")
                    or not value.removeprefix("ywc_je_").replace("_", "").isalnum()):
                raise AssertionError(("invalid_journal_entry_query", node))
            return
        if key == "trigger_if":
            if comparison != "=" or not isinstance(value, list):
                raise AssertionError(("invalid_trigger_if_condition", node))
            limits = [(cmp, body) for child, cmp, body in value if child == "limit"]
            if len(limits) != 1 or limits[0][0] != "=" or not isinstance(limits[0][1], list):
                raise AssertionError(("invalid_trigger_if_limit", node))
            for child, cmp, body in value:
                if child in ("limit", "trigger_else"):
                    if cmp != "=" or not isinstance(body, list):
                        raise AssertionError(("invalid_trigger_if_branch", (child, cmp, body)))
                    for nested in body:
                        self.validate_condition(nested, seen)
                else:
                    self.validate_condition((child, cmp, body), seen)
            return
        if key == "calc_true_if":
            if comparison != "=" or not isinstance(value, list):
                raise AssertionError(("invalid_calc_true_if_condition", node))
            amounts = [(cmp, body) for child, cmp, body in value if child == "amount"]
            if len(amounts) != 1 or amounts[0][0] not in ("=", ">="):
                raise AssertionError(("invalid_calc_true_if_amount", node))
            try:
                float(amounts[0][1])
            except (TypeError, ValueError) as exc:
                raise AssertionError(("invalid_calc_true_if_amount", node)) from exc
            for child in value:
                if child[0] != "amount":
                    self.validate_condition(child, seen)
            return
        if key.startswith("c:"):
            if isinstance(value, list):
                for child in value:
                    self.validate_condition(child, seen)
            return
        if key in {"any_scope_state", "any_scope_building", "overlord", "any_interest_group"}:
            if not isinstance(value, list):
                raise AssertionError(("invalid_scoped_condition", node))
            for child in value:
                self.validate_condition(child, seen)
            return
        if key not in self.SUPPORTED_CONDITION_PRIMITIVES and not key.startswith("var:"):
            raise AssertionError(("unsupported_test_condition", node))
        if key in {"institution_investment_level", "radical_fraction"}:
            self._validate_condition_tree([node])

    def conditions(self, nodes, tag):
        self._validate_condition_tree(nodes)
        for node in nodes:
            self.validate_condition(node)
        return super().conditions(nodes, tag)

    def condition(self, node, tag):
        self._validate_condition_tree([node])
        self.validate_condition(node)
        key, comparison, value = node
        v = self.countries[tag]
        if key in self.FOREIGN_PROTOCOL_BOUNDARIES:
            return value == "no"
        if key in self.trigger_defs:
            if key in self._trigger_stack:
                raise AssertionError(("invalid_or_recursive_scripted_trigger", node))
            self._trigger_stack.add(key)
            try:
                result = self.conditions(self.trigger_defs[key], tag)
            finally:
                self._trigger_stack.remove(key)
            return result == (value == "yes")
        if key == "has_journal_entry":
            return comparison == "=" and tag == "NMG" and value in self.active_journals
        if key == "owner" and (comparison, value) != ("=", "ROOT"):
            raise AssertionError(("unsupported NMG ownership shape", node))
        if key in ("ywc_nmg_v03_has_owned_state", "owner", "is_owned_by"):
            return bool(v.get("fixture_owned_state", 0)) and v.get("fixture_state_owner", "NMG") == tag
        if key == "any_scope_state":
            if not v.get("fixture_owned_state", 0) or v.get("fixture_state_owner", "NMG") != tag:
                return False
            previous = self.current_building
            buildings = v.get("fixture_buildings", {})
            state_predicates = [(child, cmp, body) for child, cmp, body in value
                                if child != "any_scope_building"]
            result = self.conditions(state_predicates, tag)
            building_scopes = [body for child, _, body in value if child == "any_scope_building"]
            if result and building_scopes:
                result = False
                for building, occupancy in buildings.items():
                    self.current_building = (building, occupancy)
                    if any(self.conditions(scope, tag) for scope in building_scopes):
                        result = True
                        break
            self.current_building = previous
            return result
        if key == "any_scope_building":
            return False
        if key == "is_building_type":
            return bool(self.current_building and self.current_building[0] == value)
        if key == "occupancy":
            left = self.current_building[1] if self.current_building else 0
            return {"=": lambda a,b:a==b, ">=":lambda a,b:a>=b, "<=":lambda a,b:a<=b}[comparison](left, float(value))
        if key == "building_has_goods_shortage":
            if not self.current_building:
                return False
            shortages = v.get("fixture_shortages", set())
            actual = self.current_building[0] in shortages
            return actual == (value == "yes")
        if key == "has_law_or_variant":
            return value.removeprefix("law_type:") in v.get("fixture_laws", set())
        if key == "radical_fraction":
            child = value[0]
            return {"=": lambda a,b:a==b, ">=":lambda a,b:a>=b, "<=":lambda a,b:a<=b,
                    ">":lambda a,b:a>b, "<":lambda a,b:a<b, "!=":lambda a,b:a!=b}[child[1]](
                v.get("radical_fraction", 0), float(child[2]))
        if key == "literacy_rate":
            return {"=":lambda a,b:a==b, ">=":lambda a,b:a>=b, "<=":lambda a,b:a<=b}[comparison](v.get(key, 0), float(value))
        if key == "institution_investment_level":
            child = next(node for node in value if node[0] == "value")
            left = v.get("fixture_institutions", {}).get(
                next(body for name, _, body in value if name == "institution"),
                v.get("fixture_schools_invested", 0))
            return {"=":lambda a,b:a==b, ">=":lambda a,b:a>=b, "<=":lambda a,b:a<=b,
                    ">":lambda a,b:a>b, "<":lambda a,b:a<b, "!=":lambda a,b:a!=b}[child[1]](
                left, float(child[2]))
        if key == "is_subject":
            return bool(v.get("fixture_subject", 0)) == (value == "yes")
        if key == "is_subject_of":
            return value == "c:MEX" and bool(v.get("fixture_mex_overlord", 0))
        if key == "overlord":
            return bool(v.get("fixture_mex_overlord", 0)) and self.conditions(value, "MEX")
        if key == "relations:root":
            right = -20 if value == "relations_threshold:poor" else float(value)
            return {">=": lambda a, b: a >= b, "=": lambda a, b: a == b,
                    ">": lambda a, b: a > b}[comparison](v.get("fixture_relations", 0), right)
        if key == "relations_threshold:poor":
            return -20
        if key == "any_interest_group":
            return bool(v.get("fixture_ig_support", 0)) and self.conditions(value, tag)
        if key == "is_interest_group_type":
            return value == "ig_intelligentsia"
        if key == "ig_approval":
            return {"=":lambda a,b:a==b, ">=":lambda a,b:a>=b, "<=":lambda a,b:a<=b,
                    ">":lambda a,b:a>b, "<":lambda a,b:a<b, "!=":lambda a,b:a!=b}[comparison](
                v.get("fixture_ig_approval", 1), float(value))
        return super().condition(node, tag)

    def execute(self, nodes, tag):
        has_direct_treasury = any(key == "add_treasury" for key, _, _ in nodes)
        treasury_before = self.treasury[tag]
        # Political cost is an authored engine effect, recorded as a country fact.
        filtered = []
        for key, comparison, body in nodes:
            if key == "change_relations":
                amount = float(field(field(body, "value"), "add"))
                self.countries[tag]["fixture_relations"] = self.countries[tag].get("fixture_relations", 0) + amount
            else:
                filtered.append((key, comparison, body))
        result = super().execute(filtered, tag)
        debit = self.treasury[tag] - treasury_before
        if has_direct_treasury and debit < 0:
            self.countries[tag]["gold_reserves"] = self.countries[tag].get("gold_reserves", 0) + debit
        return result


def fixture():
    return {
        "NMG": {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "bureaucracy": 100, "net_fixed_income": 500, "yearly_gross_income": 52000,
            "gold_reserves": 100000, "fixture_owned_state": 1,
            "fixture_state_owner": "NMG", "fixture_shortages": set(),
            "fixture_buildings": {"building_rye_farm": 0.8,
                                   "building_government_administration": 0.8,
                                   "building_barrack": 0.8},
            # These laws share a law group in the official game data.
            "fixture_laws": {"law_commercialized_agriculture"},
            "literacy_rate": 0.6, "fixture_schools_invested": 1,
            "fixture_subject": 1, "fixture_mex_overlord": 1, "fixture_relations": 50,
            # Existing campaign outcomes and progress are public legacy state.
            "ywc_campaign_nmg_c1_outcome": 4, "ywc_campaign_nmg_c2_outcome": 3,
            "ywc_campaign_nmg_c3_outcome": 2, "ywc_campaign_nmg_c1_e100_done": 1,
            "ywc_campaign_nmg_c1_e101_done": 1, "ywc_campaign_nmg_c1_e102_done": 1,
            "ywc_campaign_nmg_c1_e103_done": 1, "ywc_campaign_nmg_c1_e104_done": 1,
            "is_at_war": False,
        },
        "MEX": {"fixture_relations": 50},
    }


class NmgLifecycleTest(unittest.TestCase):
    def test_world_fact_fixture_rejects_missing_state_shortage_and_unknown_primitives(self):
        world = NmgWorld(fixture())
        v = world.countries["NMG"]
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nmg_land_administration_present"], "NMG"))
        v["fixture_shortages"].add("building_government_administration")
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_land_administration_present"], "NMG"))
        v["fixture_shortages"].clear()
        v["fixture_state_owner"] = "MEX"
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_v03_has_owned_state"], "NMG"))
        with self.assertRaises(AssertionError):
            world.condition(("not_a_real_game_primitive", "=", "yes"), "NMG")
        laws = v["fixture_laws"]
        self.assertFalse({"law_commercialized_agriculture", "law_tenant_farmers"} <= laws)

    def test_world_fact_fixture_validates_nmg_comparison_schemas_and_values(self):
        world = NmgWorld(fixture())
        school_level = ("institution_investment_level", "=", [
            ("institution", "=", "institution_schools"), ("value", ">=", "1")])
        self.assertTrue(world.condition(school_level, "NMG"))
        too_high = ("institution_investment_level", "=", [
            ("institution", "=", "institution_schools"), ("value", ">=", "99")])
        self.assertFalse(world.condition(too_high, "NMG"))
        v = world.countries["NMG"]
        v["fixture_relations"] = -20
        self.assertTrue(world.condition(("relations:root", ">=", "relations_threshold:poor"), "NMG"))
        v["fixture_relations"] = -21
        self.assertFalse(world.condition(("relations:root", ">=", "relations_threshold:poor"), "NMG"))
        v["radical_fraction"] = 0.2
        radical = ("radical_fraction", "=", [("value", ">=", "0.25")])
        self.assertFalse(world.condition(radical, "NMG"))
        self.assertTrue(world.condition(("ig_approval", ">=", "1"), "NMG"))
        self.assertFalse(world.condition(("ig_approval", ">=", "100"), "NMG"))

        malformed = (
            ("institution_investment_level", "=", [
                ("institution", "=", "institution_schools"), ("value", ">=", "1"),
                ("future_child", None, "yes")]),
            ("institution_investment_level", "=", [
                ("institution", "=", "institution_schools"), ("institution", "=", "institution_schools"),
                ("value", ">=", "1")]),
            ("institution_investment_level", "=", [
                ("institution", "=", "institution_schools"), ("value", "~", "1")]),
            ("institution_investment_level", "=", [
                ("institution", "=", "institution_unknown"), ("value", ">=", "1")]),
            ("institution_investment_level", "=", [
                ("institution", ">", "institution_schools"), ("value", ">=", "1")]),
            ("radical_fraction", "=", [("value", ">=", "0.2"), ("future_child", None, "1")]),
            ("radical_fraction", "=", [("value", "~", "0.2")]),
            ("ig_approval", "~", "1"),
        )
        for node in malformed:
            with self.subTest(node=node), self.assertRaises(ValueError):
                world.condition(node, "NMG")

        # Schema validation precedes Boolean short-circuiting and empty-scope evaluation.
        bad_nested = ("OR", None, [("always", None, "no"), malformed[0]])
        with self.assertRaises(ValueError):
            world.condition(bad_nested, "NMG")
        empty_scope = ("any_scope_state", None, [malformed[1]])
        world.countries["NMG"]["fixture_owned_state"] = 0
        with self.assertRaises(ValueError):
            world.condition(empty_scope, "NMG")

    def test_each_paid_arc_can_ack_12_choose_lower_at_36_and_close_limited_after_fresh_watch(self):
        cases = (
            (0, "land", ["mixed", "rule_register", "finish_survey", "keep_old", "keep_recording", "old_assessment", "renegotiate"],
             "ywc_nmg.1006", "ywc_nmg.1007", "renegotiate", "settle_partial",
             lambda v: v["fixture_buildings"].pop("building_rye_farm"),
             lambda v: v["fixture_buildings"].update(building_rye_farm=0.8), 3),
            (1, "office", ["bilingual", "hire_full", "court_parish", "fund_schools", "keep_route", "wait_retry"],
             "ywc_nmg.1014", "ywc_nmg.1015", "keep_route", "close_partial",
             lambda v: v.update(literacy_rate=0.2), lambda v: v.update(literacy_rate=0.6), 3),
            (2, "revenue", ["domestic", "audit_strict", "close_account_domestic", "local_plan", "local_record", "retain_local_budget", "conclude", "wait_retry"],
             "ywc_nmg.1028", "ywc_nmg.1029", "own_arrears", "select_arrears_limited",
             lambda v: v["fixture_buildings"].pop("building_barrack"),
             lambda v: v["fixture_buildings"].update(building_barrack=0.8), 3),
        )
        for arc_i, lane, prefix, notice12, notice36, ack, lower, lose_fact, restore_fact, lower_route in cases:
            with self.subTest(lane=lane):
                world = NmgWorld(fixture())
                arc = CATALOG["arcs"][arc_i]
                order = [j["id"] for j in arc["journals"]]
                self.activate(world, order[0])
                for choice_index, key in enumerate(prefix):
                    active = world.active_journal
                    eid = self.pulse_until_event(world, active)
                    self.choose(world, eid, key)
                    if self.reconcile_active_je(world) == "complete" and choice_index + 1 < len(prefix):
                        self.activate(world, order[len(world.completed_journals)])
                if world.active_journal is None:
                    self.activate(world, order[len(world.completed_journals)])
                lane_name = {"land": "land", "office": "office", "revenue": "revenue"}[lane]
                v = world.countries["NMG"]
                self.assertEqual(v.get(f"ywc_nmg_{lane_name}_fee_paid") or v.get("ywc_nmg_revenue_quota_paid"), 1)
                paid_treasury = world.treasury["NMG"]
                lose_fact(v)

                def deliver(target, choose_key=None):
                    for _ in range(48):
                        eid = self.pulse_until_event(world, world.active_journal)
                        if eid == target:
                            notice_month = 12 if target == notice12 else 36
                            is_due_notice = v.get(f"ywc_nmg_{lane_name}_notice{notice_month}_due") == 1
                            pending_before_notice = v.get(f"ywc_nmg_{lane_name}_pending")
                            if is_due_notice:
                                action = choose_key
                            else:
                                keys = {o["key"] for item in arc["events"] if item["id"] == eid for o in item["options"]}
                                action = "defer" if "defer" in keys else "wait_retry" if "wait_retry" in keys else None
                            if action:
                                option = event_option(eid, action)
                                self.assertTrue(world.conditions(field(option, "trigger"), "NMG"), (eid, action))
                            world.execute(field(GENERATED_EVENTS[eid], "immediate"), "NMG")
                            return_event = v.get(f"ywc_nmg_{lane_name}_notice_return_event")
                            delivered = v.get(f"ywc_nmg_{lane_name}_notice{notice_month}_delivered") == 1
                            if delivered:
                                if target == notice36:
                                    self.assertGreaterEqual(v.get(f"ywc_nmg_{lane_name}_blocked_months", 0), 36,
                                                            "36 notice must follow 36 real blocked monthly pulses")
                                effect = [n for n in option if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
                                world.execute(effect, "NMG")
                                if target == notice12:
                                    expected_pending = pending_before_notice if pending_before_notice is not None else return_event
                                    self.assertEqual(v.get(f"ywc_nmg_{lane_name}_pending"), expected_pending,
                                                     "notice acknowledgement must preserve or restore the phase-correct queue")
                                self.assertNotIn(f"ywc_nmg_{lane_name}_notice_response_context", v)
                                world.events.clear()
                                if not (target == notice36 and choose_key == lower):
                                    world.advance_months(1)
                                return
                            # Same event ID can also be an ordinary narrative item.
                            if action:
                                effect = [n for n in option if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
                                world.execute(effect, "NMG")
                                world.events.clear()
                                world.advance_months(1)
                            continue
                        e = GENERATED_EVENTS[eid]
                        keys = {o["key"] for item in arc["events"] if item["id"] == eid for o in item["options"]}
                        fallback = "defer" if "defer" in keys else "wait_retry" if "wait_retry" in keys else None
                        if fallback:
                            self.choose(world, eid, fallback)
                    self.fail(f"did not deliver {target} through live monthly driver")

                # A real loss begins the continuous blocked clock; ordinary events are legally deferred.
                deliver(notice12, ack)
                self.assertEqual(v.get(f"ywc_nmg_{lane_name}_notice12_delivered"), 1)
                # Wait at 36, recover the real selected contract, then lose it again.
                # Recovery must clear the first epoch's delivery latch and queued notice.
                deliver(notice36, "wait_retry")
                restore_fact(v)
                recovered_event = self.pulse_until_event(world, world.active_journal)
                self.assertNotIn(f"ywc_nmg_{lane_name}_notice12_delivered", v)
                self.assertNotIn(f"ywc_nmg_{lane_name}_notice36_delivered", v)
                self.assertNotIn(f"ywc_nmg_{lane_name}_notice_pending", v)
                self.assertNotIn(f"ywc_nmg_{lane_name}_notice_response_context", v)
                options = [body for key, _, body in GENERATED_EVENTS[recovered_event] if key == "option"]
                keys = [field(item, "name").split(".")[-1] for item in options]
                fallback = "defer" if "defer" in keys else "wait_retry"
                self.choose(world, recovered_event, fallback)
                lose_fact(v)
                deliver(notice12, ack)
                self.assertEqual(v.get(f"ywc_nmg_{lane_name}_notice12_delivered"), 1)
                deliver(notice36, lower)
                self.assertEqual(v.get(f"ywc_nmg_{lane_name}_notice36_delivered"), 1)
                self.assertEqual(v.get(f"ywc_nmg_{lane_name}_route"), lower_route)
                self.assertEqual(v.get(f"ywc_nmg_{lane_name}_limited_selected"), 1)
                full_ready = ("ywc_nmg_land_mixed_ready", "ywc_nmg_office_bilingual_ready",
                              "ywc_nmg_revenue_fixed_ready")[arc_i]
                limited_ready = ("ywc_nmg_land_old_ready", "ywc_nmg_office_single_ready",
                                 "ywc_nmg_revenue_arrears_ready")[arc_i]
                self.assertFalse(world.conditions(world.trigger_defs[full_ready], "NMG"), "higher obligation must remain unmet")
                self.assertTrue(world.conditions(world.trigger_defs[limited_ready], "NMG"), "lower target must be currently feasible")
                self.assertEqual(world.treasury["NMG"], paid_treasury, "renegotiation preserves sunk fee without second debit")
                for suffix in ("watch_started", "watch_timer", "six_months_complete"):
                    self.assertNotIn(f"ywc_nmg_{lane_name}_{suffix}", v)

                # First lower-target selection starts a new native six-month watch.
                # Drive each monthly review and calendar month separately; 90-day
                # delivery waits remain ordinary queue time, not failed observation.
                entry = GENERATED_JES[world.active_journal]
                pulse = field(field(entry, "on_monthly_pulse"), "effect")
                timer = f"ywc_nmg_{lane_name}_watch_timer"
                def one_pulse():
                    world.execute(pulse, "NMG")
                    if not world.events:
                        return
                    pulse_event = world.events[-1][1]
                    event = GENERATED_EVENTS[pulse_event]
                    world.execute(field(event, "immediate"), "NMG")
                    opts = [body for key, _, body in event if key == "option"]
                    keys = [field(body, "name").split(".")[-1] for body in opts]
                    fallback = "wait_retry" if "wait_retry" in keys else "defer" if "defer" in keys else None
                    if fallback:
                        option = event_option(pulse_event, fallback)
                        effect = [n for n in option if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
                        world.execute(effect, "NMG")
                    world.events.clear()

                one_pulse()
                self.assertEqual(world.months_until_expiry["NMG"].get(timer), 6)
                self.assertNotIn(f"ywc_nmg_{lane_name}_six_months_complete", v)
                for elapsed_month in range(1, 6):
                    world.advance_months(1)
                    one_pulse()
                    self.assertNotIn(f"ywc_nmg_{lane_name}_six_months_complete", v,
                                     "the native six-month timer must not mature before its sixth calendar month")
                    self.assertEqual(world.months_until_expiry["NMG"].get(timer), 6 - elapsed_month)
                world.advance_months(1)
                one_pulse()
                self.assertEqual(v.get(f"ywc_nmg_{lane_name}_six_months_complete"), 1,
                                 "the selected target matures only after six calendar months")
                eid = self.pulse_until_event(world, world.active_journal)
                allowed = "settle_partial" if lane == "land" else "close_partial"
                partial_option = event_option(eid, allowed)
                self.assertTrue(world.conditions(field(partial_option, "trigger"), "NMG"),
                                (lane, eid, allowed, v))
                self.choose(world, eid, allowed)
                self.assertEqual(v.get(f"ywc_v03_nmg_v03_nmg_{('land_arbitration','bilingual_office','autonomy_revenue')[arc_i]}_outcome"), 2, v)
                self.assertNotIn(f"ywc_nmg_{lane_name}_established", v, "limited outcome must not report full success")
                self.assertEqual(v.get("ywc_v03_active_arc_count"), 0)
                self.assertEqual(v.get("ywc_v03_visible_task_count"), 0)
                self.assertEqual({key: v.get(key) for key in (
                    "ywc_campaign_nmg_c1_outcome", "ywc_campaign_nmg_c2_outcome",
                    "ywc_campaign_nmg_c3_outcome", "ywc_campaign_nmg_c1_e100_done",
                    "ywc_campaign_nmg_c1_e101_done", "ywc_campaign_nmg_c1_e102_done",
                    "ywc_campaign_nmg_c1_e103_done", "ywc_campaign_nmg_c1_e104_done")}, {
                    "ywc_campaign_nmg_c1_outcome": 4, "ywc_campaign_nmg_c2_outcome": 3,
                    "ywc_campaign_nmg_c3_outcome": 2, "ywc_campaign_nmg_c1_e100_done": 1,
                    "ywc_campaign_nmg_c1_e101_done": 1, "ywc_campaign_nmg_c1_e102_done": 1,
                    "ywc_campaign_nmg_c1_e103_done": 1, "ywc_campaign_nmg_c1_e104_done": 1})

    def test_early_recovery_clears_old_notice_epoch_and_delivers_fresh_12_in_all_arcs(self):
        cases = (
            (0,"land","ywc_nmg.1000","unified","ywc_nmg.1006","renegotiate",
             lambda v:v["fixture_laws"].clear(),lambda v:v["fixture_laws"].add("law_commercialized_agriculture"),
             "ywc_nmg_land_fee_paid"),
            (1,"office","ywc_nmg.1010","local","ywc_nmg.1014","keep_route",
             lambda v:v["fixture_buildings"].pop("building_government_administration"),
             lambda v:v["fixture_buildings"].update(building_government_administration=0.8),
             "ywc_nmg_office_fee_paid"),
            (2,"revenue","ywc_nmg.1020","domestic","ywc_nmg.1028","own_arrears",
             lambda v:v["fixture_buildings"].pop("building_barrack"),
             lambda v:v["fixture_buildings"].update(building_barrack=0.8),
             "ywc_nmg_revenue_quota_paid"),
        )
        replay_choices={1001:"rule_register",1002:"half_survey",1003:"keep_old",1004:"keep_recording",1005:"old_assessment",
                        1011:"hire_thin",1012:"court_parish",1013:"borrow_staff",1014:"keep_route",
                        1020:"domestic",1021:"audit_strict",1022:"reopen",1023:"local_plan",1024:"defer",
                        1025:"defer",1026:"defer"}
        for arc_index,lane,opening,first_choice,notice,ack,lose,restore,paid_var in cases:
            with self.subTest(lane=lane):
                world=NmgWorld(fixture()); v=world.countries["NMG"]
                order=[j["id"] for j in CATALOG["arcs"][arc_index]["journals"]]
                self.activate(world,order[0])
                def active_pulse_once():
                    status=self.reconcile_active_je(world)
                    self.assertNotEqual(status,"fail")
                    if status=="complete":
                        self.activate(world,order[len(world.completed_journals)])
                    active=world.active_journal
                    self.assertIn(active,world.active_journals)
                    entry=GENERATED_JES[active]
                    self.assertFalse(world.conditions(field(entry,"complete"),"NMG"))
                    self.assertFalse(world.conditions(field(entry,"fail"),"NMG"))
                    world.execute(field(field(entry,"on_monthly_pulse"),"effect"),"NMG")
                    return world.events[-1][1] if world.events else None
                def active_pulse_event():
                    for _ in range(48):
                        eid=active_pulse_once()
                        if eid is not None:
                            return eid
                        world.advance_months(1)
                    self.fail(f"no event from active {lane} JE: {v}")
                def choose_normal(eid,key):
                    self.choose(world,eid,key)
                    status=self.reconcile_active_je(world)
                    self.assertNotEqual(status,"fail")
                    if status=="complete":
                        self.activate(world,order[len(world.completed_journals)])
                eid=active_pulse_event()
                self.assertEqual(eid,opening)
                choose_normal(eid,first_choice)
                if lane=="revenue":
                    for next_id,key in (("ywc_nmg.1021","audit_strict"),("ywc_nmg.1022","reopen")):
                        eid=active_pulse_event()
                        self.assertEqual(eid,next_id)
                        choose_normal(eid,key)
                self.assertEqual(v.get(paid_var),1)
                self.assertFalse(world.conditions(world.trigger_defs[f"ywc_nmg_{lane}_route_ready"],"NMG"))
                cash_after_fee=world.treasury["NMG"]

                lose(v); acknowledged=False
                for _ in range(18):
                    eid=active_pulse_event()
                    if eid==notice and v.get(f"ywc_nmg_{lane}_notice12_due")==1:
                        event=GENERATED_EVENTS[eid]; world.execute(field(event,"immediate"),"NMG")
                        self.assertEqual(v.get(f"ywc_nmg_{lane}_notice12_delivered"),1)
                        option=event_option(eid,ack)
                        self.assertTrue(world.conditions(field(option,"trigger"),"NMG"))
                        effect=[n for n in option if n[0] not in ("name","trigger","ai_chance","custom_tooltip")]
                        world.execute(effect,"NMG"); world.events.clear(); world.advance_months(1)
                        acknowledged=True; break
                    event=GENERATED_EVENTS[eid]
                    options=[body for key,_,body in event if key=="option"]
                    keys=[field(body,"name").split(".")[-1] for body in options]
                    fallback=("wait_for_funds" if "wait_for_funds" in keys else "defer" if "defer" in keys
                              else "wait_retry" if "wait_retry" in keys else "reopen" if "reopen" in keys
                              else "hold_route" if "hold_route" in keys else "keep_route" if "keep_route" in keys
                              else "own_arrears" if "own_arrears" in keys else None)
                    self.assertIsNotNone(fallback,(lane,eid,keys))
                    choose_normal(eid,fallback)
                self.assertTrue(acknowledged,f"{lane}: actual first 12-month notice was not acknowledged")
                self.assertNotIn(f"ywc_nmg_{lane}_notice_response_context",v)
                ordinary_pending=v.get(f"ywc_nmg_{lane}_pending")
                self.assertIsNotNone(ordinary_pending,f"{lane}: notice reply lost the ordinary phase queue")
                restore(v)

                # Recovery clears only stale notice-epoch state. The live JE then emits its real queued node.
                eid=active_pulse_event()
                self.assertEqual(eid,f"ywc_nmg.{int(ordinary_pending)}")
                for suffix in ("notice12_delivered","notice36_delivered","notice_pending","notice_response_context","notice_return_event"):
                    self.assertNotIn(f"ywc_nmg_{lane}_{suffix}",v)
                self.assertEqual(world.treasury["NMG"],cash_after_fee)
                self.assertTrue(world.conditions(world.trigger_defs[f"ywc_nmg_{lane}_selected_target_ready"],"NMG"))
                self.assertFalse(world.conditions(world.trigger_defs[f"ywc_nmg_{lane}_route_ready"],"NMG"))
                key=replay_choices.get(int(ordinary_pending))
                self.assertIsNotNone(key,(lane,ordinary_pending))
                option=event_option(eid,key)
                self.assertTrue(world.conditions(field(option,"trigger"),"NMG"),(lane,eid,key))
                choose_normal(eid,key)
                self.assertEqual(world.treasury["NMG"],cash_after_fee,"legal replay cannot charge sunk route fee again")

                lose(v); fresh_notice=False
                for _ in range(15):
                    eid=active_pulse_once()
                    if eid is None:
                        world.advance_months(1); continue
                    if eid==notice and v.get(f"ywc_nmg_{lane}_notice12_due")==1:
                        event=GENERATED_EVENTS[eid]; world.execute(field(event,"immediate"),"NMG")
                        self.assertEqual(v.get(f"ywc_nmg_{lane}_notice12_delivered"),1)
                        fresh_notice=True; world.events.clear(); break
                    event=GENERATED_EVENTS[eid]
                    options=[body for key,_,body in event if key=="option"]
                    keys=[field(body,"name").split(".")[-1] for body in options]
                    fallback=("wait_for_funds" if "wait_for_funds" in keys else "defer" if "defer" in keys
                              else "wait_retry" if "wait_retry" in keys else "reopen" if "reopen" in keys
                              else "hold_route" if "hold_route" in keys else "keep_route" if "keep_route" in keys
                              else "own_arrears" if "own_arrears" in keys else None)
                    self.assertIsNotNone(fallback,(lane,eid,keys))
                    choose_normal(eid,fallback)
                self.assertTrue(fresh_notice,f"{lane}: second failure epoch did not deliver a fresh 12-month notice")

    def test_partial_consequence_notes_are_canonical_and_rendered(self):
        cases={
            "ywc_nmg.1007":("settle_partial","fresh six-month observation","after it matures, confirm","\u65b0\u7684\u516d\u4e2a\u6708\u89c2\u5bdf","\u89c2\u5bdf\u6210\u719f\u540e\u518d\u6b21\u786e\u8ba4"),
            "ywc_nmg.1015":("close_partial","fresh six-month observation","after it matures, confirm","\u65b0\u7684\u516d\u4e2a\u6708\u89c2\u5bdf","\u89c2\u5bdf\u6210\u719f\u540e\u518d\u6b21\u786e\u8ba4"),
            "ywc_nmg.1029":("select_arrears_limited","fresh six-month observation","after it matures, confirm","\u65b0\u7684\u516d\u4e2a\u6708\u89c2\u5bdf","\u89c2\u5bdf\u6210\u719f\u540e\u518d\u6b21\u786e\u8ba4")}
        eng=(MOD/"localization/english/ywc_v03_country_nmg_l_english.yml").read_text(encoding="utf-8-sig")
        zho=(MOD/"localization/simp_chinese/ywc_v03_country_nmg_l_simp_chinese.yml").read_text(encoding="utf-8-sig")
        for event_id,(option_key,first_phrase,mature_phrase,zh_first,zh_mature) in cases.items():
            event=next(e for a in CATALOG["arcs"] for e in a["events"] if e["id"]==event_id)
            option=next(o for o in event["options"] if o["key"]==option_key)
            note=option["consequence_note"]
            english_note=note["en"].casefold()
            self.assertIn(first_phrase,english_note); self.assertIn(mature_phrase,english_note)
            self.assertIn(zh_first,note["zh"]); self.assertIn(zh_mature,note["zh"])
            key=f"{event_id}.{option_key}.consequence_tooltip:0"
            self.assertIn(f'{key} "{note["en"]}"',eng)
            self.assertIn(f'{key} "{note["zh"]}"',zho)

        event_id="ywc_nmg.1027"; option_key="settle_partial"
        event=next(e for a in CATALOG["arcs"] for e in a["events"] if e["id"]==event_id)
        option=next(o for o in event["options"] if o["key"]==option_key)
        note=option["consequence_note"]
        self.assertIn("observation already mature",note["en"].casefold())
        self.assertIn("conditions met",note["en"].casefold())
        self.assertIn("no new payment",note["en"].casefold())
        self.assertIn("\u89c2\u5bdf\u671f\u5df2\u6210\u719f",note["zh"])
        self.assertIn("\u8def\u7ebf\u6761\u4ef6\u7b26\u5408",note["zh"])
        self.assertIn("\u4e0d\u65b0\u4ed8\u6b3e",note["zh"])
        key=f"{event_id}.{option_key}.consequence_tooltip:0"
        self.assertIn(f'{key} "{note["en"]}"',eng)
        self.assertIn(f'{key} "{note["zh"]}"',zho)

    def test_real_revenue_1027_compromise_uses_matured_paid_contract_and_retries_after_popup_loss(self):
        prefix=["domestic","audit_strict","close_account_domestic","local_plan","local_record","retain_local_budget","conclude","wait_retry"]
        def real_mature_popup():
            world=self.finish_path(2,4,prefix)
            v=world.countries["NMG"]
            self.assertEqual(v.get("ywc_nmg_revenue_quota_paid"),1)
            for _ in range(20):
                eid=self.pulse_until_event(world,world.active_journal)
                self.assertEqual(eid,"ywc_nmg.1027")
                event=GENERATED_EVENTS[eid]
                self.assertTrue(world.conditions(field(event,"trigger"),"NMG"))
                world.execute(field(event,"immediate"),"NMG")
                option=event_option(eid,"settle_partial")
                if world.conditions(field(option,"trigger"),"NMG"):
                    self.assertEqual(v.get("ywc_nmg_revenue_six_months_complete"),1)
                    self.assertTrue(world.conditions(world.trigger_defs["ywc_nmg_revenue_route_ready"],"NMG"))
                    return world,eid,v
                wait=event_option(eid,"wait_retry")
                self.assertTrue(world.conditions(field(wait,"trigger"),"NMG"))
                effects=[n for n in wait if n[0] not in ("name","trigger","ai_chance","custom_tooltip")]
                world.execute(effects,"NMG")
                world.events.clear()
                world.advance_months(1)
            self.fail("the actual six-month NMG revenue watch did not mature")

        world,eid,v=real_mature_popup()
        option=event_option(eid,"settle_partial")
        self.assertTrue(world.conditions(field(option,"trigger"),"NMG"))
        treasury_before=world.treasury["NMG"]
        nmg_relations_before=v["fixture_relations"]
        mex_relations_before=world.countries["MEX"]["fixture_relations"]
        effects=[n for n in option if n[0] not in ("name","trigger","ai_chance","custom_tooltip")]
        world.execute(effects,"NMG")
        self.assertEqual(v.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_outcome"),2)
        self.assertEqual(v.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"),1)
        self.assertEqual(v.get("ywc_v03_active_arc_count"),0)
        self.assertEqual(v.get("ywc_v03_visible_task_count"),0)
        self.assertEqual(world.treasury["NMG"],treasury_before,"1027 compromise does not charge again")
        self.assertEqual(v["fixture_relations"],nmg_relations_before)
        self.assertEqual(world.countries["MEX"]["fixture_relations"],mex_relations_before)
        timer="ywc_nmg_revenue_watch_timer"
        self.assertNotIn(timer,v)
        self.assertNotIn(timer,world.months_until_expiry["NMG"],"mature 1027 does not restart the watch")

        world,eid,v=real_mature_popup()
        option=event_option(eid,"settle_partial")
        v["fixture_buildings"].pop("building_barrack")
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_revenue_route_ready"],"NMG"))
        self.assertFalse(world.conditions(field(option,"trigger"),"NMG"),"stale matured popup cannot close after target loss")
        wait=event_option(eid,"wait_retry")
        self.assertTrue(world.conditions(field(wait,"trigger"),"NMG"))
        effects=[n for n in wait if n[0] not in ("name","trigger","ai_chance","custom_tooltip")]
        world.execute(effects,"NMG")
        self.assertEqual(v.get("ywc_nmg_revenue_pending"),1027)
        self.assertEqual(v.get("ywc_nmg_revenue_route"),4)
        self.assertEqual(v.get("ywc_nmg_revenue_quota_paid"),1)
        self.assertNotIn("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled",v)
        self.assertEqual(v.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_outcome"),0)
        for suffix in ("watch_started","watch_timer","six_months_complete"):
            self.assertNotIn(f"ywc_nmg_revenue_{suffix}",v)

    def test_revenue_12_notice_ack_preserves_real_opening_queue_and_resumes_after_recovery(self):
        world = NmgWorld(fixture())
        arc = CATALOG["arcs"][2]
        order = [j["id"] for j in arc["journals"]]
        self.activate(world, order[0])
        for choice_index, key in enumerate(("domestic", "audit_strict", "reopen")):
            active = world.active_journal
            eid = self.pulse_until_event(world, active)
            self.assertEqual(eid, f"ywc_nmg.{1020 + choice_index}")
            self.choose(world, eid, key)
            if self.reconcile_active_je(world) == "complete" and choice_index < 2:
                self.activate(world, order[len(world.completed_journals)])
        v = world.countries["NMG"]
        self.assertEqual(v.get("ywc_nmg_revenue_pending"), 1020)
        self.assertEqual(v.get("ywc_nmg_revenue_route"), 4)
        self.assertNotIn("ywc_nmg_revenue_stage2", v)
        self.assertEqual(v.get("ywc_nmg_revenue_quota_paid"), 1)
        paid_cash = v.get("gold_reserves")
        self.assertLess(paid_cash, 100000)

        # Trigger a real early loss and keep advancing the active JE through its
        # ordinary wait choices until its 12-month notice is due and delivered.
        v["fixture_buildings"].pop("building_barrack")
        noticed = False
        for _ in range(48):
            eid = self.pulse_until_event(world, world.active_journal)
            if eid == "ywc_nmg.1028" and v.get("ywc_nmg_revenue_notice12_due") == 1:
                event = GENERATED_EVENTS[eid]
                world.execute(field(event, "immediate"), "NMG")
                option = event_option(eid, "own_arrears")
                self.assertTrue(world.conditions(field(option, "trigger"), "NMG"))
                effect = [n for n in option if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
                world.execute(effect, "NMG")
                world.events.clear()
                self.assertEqual(v.get("ywc_nmg_revenue_pending"), 1020,
                                 "notice response must not replace the opening JE's ordinary node")
                self.assertNotIn("ywc_nmg_revenue_stage2", v)
                self.assertNotIn("ywc_nmg_revenue_notice_response_context", v)
                noticed = True
                break
            options = [body for key, _, body in GENERATED_EVENTS[eid] if key == "option"]
            keys = [field(body, "name").split(".")[-1] for body in options]
            fallback = "wait_for_funds" if "wait_for_funds" in keys else "wait_retry" if "wait_retry" in keys else "defer" if "defer" in keys else None
            self.assertIsNotNone(fallback, (eid, keys))
            self.choose(world, eid, fallback)
        self.assertTrue(noticed, "a real 12-month notice must arrive through active-JE pulses")

        v["fixture_buildings"]["building_barrack"] = 0.8
        eid = self.pulse_until_event(world, world.active_journal)
        self.assertEqual(eid, "ywc_nmg.1020", "restoration must resume the phase-correct opening queue")
        self.assertEqual(v.get("ywc_nmg_revenue_pending"), 1020,
                         "the selected opening queue remains intact until the event body is acknowledged")
        self.assertEqual(v.get("ywc_v03_nmg_inline_reservation"), 23)
        self.assertEqual(v.get("ywc_v03_nmg_inline_c23_ywc_nmg_revenue_pending_value"), 1020)
        self.assertEqual(v.get("gold_reserves"), paid_cash, "ack and recovery do not charge the sunk fee again")
        self.assertTrue(world.conditions(field(GENERATED_EVENTS[eid], "trigger"), "NMG"))
        self.choose(world, eid, "wait_for_funds")

    def activate(self, world, je_id):
        entry = GENERATED_JES[je_id]
        self.assertNotIn(je_id, world.completed_journals, "completed JE must never revive")
        self.assertNotIn(je_id, world.failed_journals, "failed JE must never revive")
        self.assertTrue(world.conditions(field(entry, "is_shown_when_inactive"), "NMG"), (je_id, "shown"))
        self.assertTrue(world.conditions(field(entry, "possible"), "NMG"), je_id)
        world.active_journal = je_id
        world.active_journals.add(je_id)
        world.journals.append(("NMG", entry))
        world.execute(field(entry, "immediate"), "NMG")

    def reconcile_active_je(self, world):
        je_id = world.active_journal
        self.assertIsNotNone(je_id)
        entry = GENERATED_JES[je_id]
        complete = world.conditions(field(entry, "complete"), "NMG")
        failed = world.conditions(field(entry, "fail"), "NMG")
        self.assertFalse(complete and failed, f"JE has mutually exclusive terminal predicates: {je_id}")
        if complete:
            world.execute(field(entry, "on_complete"), "NMG")
            world.completed_journals.append(je_id)
            world.active_journals.discard(je_id)
            world.active_journal = None
            return "complete"
        if failed:
            world.execute(field(entry, "on_fail"), "NMG")
            world.failed_journals.append(je_id)
            world.active_journals.discard(je_id)
            world.active_journal = None
            return "fail"
        return None

    def pulse_until_event(self, world, je_id):
        entry = GENERATED_JES[je_id]
        pulse = field(field(entry, "on_monthly_pulse"), "effect")
        for _ in range(48):
            self.assertIn(je_id, world.active_journals, "only an actually admitted JE may pulse")
            world.active_journal = je_id
            self.assertFalse(world.conditions(field(entry, "complete"), "NMG"), "goal must be reconciled before pulse")
            self.assertFalse(world.conditions(field(entry, "fail"), "NMG"), "fail must be reconciled before pulse")
            world.execute(pulse, "NMG")
            if world.events:
                break
            world.advance_months(1)
        self.assertTrue(world.events, f"no event from live journal {je_id}: {world.countries['NMG']}")
        return world.events[-1][1]

    def choose(self, world, event_id, option_key):
        event = GENERATED_EVENTS[event_id]
        self.assertTrue(world.conditions(field(event, "trigger"), "NMG"), event_id)
        world.execute(field(event, "immediate"), "NMG")
        option = event_option(event_id, option_key)
        self.assertTrue(world.conditions(field(option, "trigger"), "NMG"),
                        (event_id, option_key, world.countries["NMG"], field(option, "trigger")))
        effect = [n for n in option if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
        world.execute(effect, "NMG")
        world.events.clear()
        world.advance_months(1)

    def finish_path(self, arc_index, route, choices):
        world = NmgWorld(fixture())
        arc = CATALOG["arcs"][arc_index]
        first_je = arc["journals"][0]["id"]
        order = [j["id"] for j in arc["journals"]]
        self.activate(world, first_je)
        selected = 0
        while selected < len(choices):
            active = world.active_journal
            event_id = self.pulse_until_event(world, active)
            self.choose(world, event_id, choices[selected])
            selected += 1
            entry = GENERATED_JES[active]
            status = self.reconcile_active_je(world) if world.active_journal == active else None
            if status == "complete":
                if selected < len(choices):
                    next_je = order[len(world.completed_journals)]
                    self.activate(world, next_je)
        return world

    def test_three_arcs_each_have_two_real_queue_to_terminal_paths(self):
        paths = (
            (0, 1, ["mixed", "rule_register", "finish_survey", "keep_old", "keep_recording", "old_assessment", "renegotiate", "settle_full"]),
            (0, 2, ["unified", "rule_custom", "finish_survey", "keep_old", "keep_recording", "new_assessment", "renegotiate", "wait_retry", "settle_full"]),
            (1, 1, ["bilingual", "hire_full", "court_parish", "fund_schools", "keep_route", "wait_retry", "close_full"]),
            (1, 2, ["local", "hire_thin", "court_parish", "fund_schools", "switch_local", "wait_retry", "wait_retry", "close_full"]),
            (2, 4, ["domestic", "audit_strict", "close_account_domestic", "local_plan", "local_record", "retain_local_budget", "conclude", "wait_retry", "wait_retry", "settle_full"]),
            (2, 3, ["arrears", "audit_strict", "close_account_arrears", "accept_floor", "escalate", "share_even", "conclude", "defer", "own_arrears", "wait_retry", "wait_retry", "close_partial"]),
        )
        terminal = ("ywc_v03_nmg_v03_nmg_land_arbitration_settled",
                    "ywc_v03_nmg_v03_nmg_bilingual_office_settled",
                    "ywc_v03_nmg_v03_nmg_autonomy_revenue_settled")
        for arc, route, choices in paths:
            with self.subTest(arc=arc, route=route):
                world = self.finish_path(arc, route, choices)
                v = world.countries["NMG"]
                self.assertEqual(v.get(terminal[arc]), 1, v)
                self.assertEqual(v.get("ywc_v03_active_arc_count"), 0)
                self.assertEqual(v.get("ywc_v03_visible_task_count"), 0)
                self.assertEqual(v.get(f"ywc_nmg_{('land','office','revenue')[arc]}_route"), route)
                self.assertEqual(world.completed_journals, [j["id"] for j in CATALOG["arcs"][arc]["journals"]])
                self.assertEqual(world.failed_journals, [])
                self.assertEqual(world.active_journal, None)
                expected_paid = {(0, 1): -2000, (0, 2): -2000,
                                 (1, 1): -2000, (1, 2): -1000,
                                 (2, 4): -1000, (2, 3): -1000}[(arc, route)]
                self.assertEqual(world.treasury["NMG"], expected_paid)
                self.assertEqual(v["gold_reserves"], 100000 + world.treasury["NMG"])

    def test_paid_arrears_route_has_an_explicit_opening_handoff(self):
        world = self.finish_path(2, 3, ["arrears", "audit_strict", "close_account_arrears"])
        state = world.countries["NMG"]
        self.assertEqual(state.get("ywc_nmg_revenue_route"), 3)
        self.assertEqual(state.get("ywc_nmg_revenue_stage2"), 1)
        self.assertEqual(state.get("ywc_nmg_revenue_pending"), 1023)
        self.assertEqual(world.treasury["NMG"], -1000)

    def test_paid_arrears_route_can_complete_all_three_authored_stages(self):
        choices = ["arrears", "audit_strict", "close_account_arrears", "accept_floor", "escalate",
                   "share_even", "conclude", "defer", "own_arrears", "wait_retry", "wait_retry", "close_partial"]
        world = self.finish_path(2, 3, choices)
        state = world.countries["NMG"]
        self.assertEqual(state.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_outcome"), 2)
        self.assertEqual(state.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"), 1)
        self.assertEqual(world.completed_journals, [j["id"] for j in CATALOG["arcs"][2]["journals"]])
        self.assertEqual(world.treasury["NMG"], -1000)

    def test_paid_contract_completes_after_exact_cash_is_spent(self):
        world = NmgWorld(fixture())
        world.countries["NMG"]["gold_reserves"] = 1000
        arc = CATALOG["arcs"][1]
        order = [j["id"] for j in arc["journals"]]
        self.activate(world, order[0])
        for index, key in enumerate(("local", "hire_thin", "court_parish", "fund_schools", "switch_local", "wait_retry", "wait_retry", "close_full")):
            active = world.active_journal
            eid = self.pulse_until_event(world, active)
            self.choose(world, eid, key)
            self.reconcile_active_je(world)
            if world.active_journal is None and index < 7:
                self.activate(world, order[len(world.completed_journals)])
        v = world.countries["NMG"]
        self.assertEqual(world.treasury["NMG"], -1000)
        self.assertEqual(v["gold_reserves"], 0)
        self.assertEqual(v.get("ywc_v03_nmg_v03_nmg_bilingual_office_settled"), 1)

    def test_real_withdraw_is_failure_only_releases_once_and_cannot_revive(self):
        paths = (
            (0, ["mixed", "rule_register", "finish_survey", "keep_old", "keep_recording", "old_assessment", "renegotiate", "withdraw"]),
            (1, ["bilingual", "hire_full", "court_parish", "fund_schools", "keep_route", "wait_retry", "withdraw"]),
        )
        for arc_i, choices in paths:
            with self.subTest(arc=arc_i):
                world = self.finish_path(arc_i, 1, choices)
                v = world.countries["NMG"]
                final_je = CATALOG["arcs"][arc_i]["journals"][-1]["id"]
                entry = GENERATED_JES[final_je]
                self.assertIn(final_je, world.failed_journals)
                self.assertNotIn(final_je, world.completed_journals)
                self.assertTrue(world.conditions(field(entry, "fail"), "NMG"))
                self.assertFalse(world.conditions(field(entry, "complete"), "NMG"))
                self.assertFalse(world.conditions(field(entry, "is_shown_when_inactive"), "NMG"))
                self.assertEqual(v.get("ywc_v03_active_arc_count"), 0)
                self.assertEqual(v.get("ywc_v03_visible_task_count"), 0)

    def test_three_live_arc_admissions_keep_independent_queues_under_shared_90_day_gate(self):
        world = NmgWorld(fixture())
        openings = [arc["journals"][0]["id"] for arc in CATALOG["arcs"]]
        expected = (1000, 1010, 1020)
        for je_id in openings:
            self.activate(world, je_id)
        v = world.countries["NMG"]
        self.assertEqual(v.get("ywc_v03_active_arc_count"), 3)
        self.assertEqual(v.get("ywc_v03_visible_task_count"), 3)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_v03_has_capacity"], "NMG"))
        delivery_months = []
        for je_id, event_num in zip(openings, expected):
            eid = self.pulse_until_event(world, je_id)
            self.assertEqual(eid, f"ywc_nmg.{event_num}")
            delivery_months.append(world.calendar_month)
            self.choose(world, eid, "wait_for_funds")
            self.assertIn(je_id, world.active_journals)
        self.assertGreaterEqual(delivery_months[1] - delivery_months[0], 3)
        self.assertGreaterEqual(delivery_months[2] - delivery_months[1], 3)
        self.assertEqual([v.get(f"ywc_nmg_{name}_pending") for name in ("land", "office", "revenue")],
                         [1000, 1010, 1020])
        self.assertEqual(v.get("ywc_v03_active_arc_count"), 3)
        self.assertEqual(v.get("ywc_v03_visible_task_count"), 3)

    def test_real_paid_revenue_route_withdraws_after_live_12_and_36_month_notices(self):
        # The domestic route is admitted and paid through the actual opening and two real JE handoffs.
        world = self.finish_path(2, 4, ["domestic", "audit_strict", "close_account_domestic",
                                        "local_plan", "local_record", "retain_local_budget", "conclude"])
        self.assertEqual(world.completed_journals, [
            "ywc_je_v03_nmg_revenue_opening", "ywc_je_v03_nmg_revenue_negotiation"])
        settlement = "ywc_je_v03_nmg_revenue_settlement"
        self.activate(world, settlement)
        v = world.countries["NMG"]
        self.assertEqual(v.get("ywc_nmg_revenue_route"), 4)
        self.assertEqual(v.get("ywc_nmg_revenue_quota_paid"), 1)
        self.assertEqual(world.treasury["NMG"], -1000)
        paid = world.treasury["NMG"]
        # Lose the selected contract's real defense building after payment.
        v["fixture_buildings"].pop("building_barrack")
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_revenue_route_ready"], "NMG"))
        relation_before_notice = v["fixture_relations"]

        def deliver_notice(target, due_variable, delivered_variable, chosen_option):
            for _ in range(60):
                event_id = self.pulse_until_event(world, settlement)
                if event_id == target:
                    was_due = v.get(due_variable) == 1
                    event = GENERATED_EVENTS[event_id]
                    world.execute(field(event, "immediate"), "NMG")
                    if v.get(delivered_variable) == 1:
                        self.assertTrue(was_due, f"{target} must come from its elapsed live clock")
                        if target == "ywc_nmg.1029":
                            self.assertGreaterEqual(v.get("ywc_nmg_revenue_blocked_months", 0), 36)
                        option = event_option(event_id, chosen_option)
                    else:
                        options = [body for key, _, body in event if key == "option"]
                        keys = [field(item, "name") for item in options]
                        fallback = "defer" if "defer" in keys else "wait_retry"
                        option = event_option(event_id, fallback)
                    self.assertTrue(world.conditions(field(option, "trigger"), "NMG"),
                                    (event_id, field(option, "name"), v))
                    effects = [n for n in option if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
                    world.execute(effects, "NMG")
                    was_delivered = v.get(delivered_variable) == 1
                    world.events.clear()
                    world.advance_months(1)
                    if was_delivered:
                        return
                else:
                    options = [body for key, _, body in GENERATED_EVENTS[event_id] if key == "option"]
                    keys = [field(item, "name") for item in options]
                    fallback = "defer" if "defer" in keys else "wait_retry"
                    self.choose(world, event_id, fallback)
            self.fail(f"live queue did not deliver {target}")

        deliver_notice("ywc_nmg.1028", "ywc_nmg_revenue_notice12_due",
                       "ywc_nmg_revenue_notice12_delivered", "own_arrears")
        self.assertEqual(v.get("ywc_nmg_revenue_notice12_delivered"), 1)
        self.assertEqual(v.get("ywc_nmg_revenue_arrears_owned"), 1)
        self.assertEqual(v["fixture_relations"], relation_before_notice - 5)
        self.assertEqual(world.treasury["NMG"], paid, "acknowledgement does not refund or recharge the sunk fee")

        relation_before_withdraw = v["fixture_relations"]
        deliver_notice("ywc_nmg.1029", "ywc_nmg_revenue_notice36_due",
                       "ywc_nmg_revenue_notice36_delivered", "withdraw")
        self.assertEqual(v.get("ywc_nmg_revenue_notice36_delivered"), 1)
        self.assertEqual(self.reconcile_active_je(world), "fail")
        self.assertEqual(v.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"), 1)
        self.assertEqual(v.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_outcome"), 1)
        self.assertEqual(v.get("ywc_nmg_revenue_withdrawn"), 1)
        self.assertNotIn("ywc_nmg_revenue_established", v)
        self.assertNotIn("ywc_nmg_revenue_compromise", v)
        self.assertEqual(v["fixture_relations"], relation_before_withdraw - 25,
                         "the generic withdrawal penalty is applied once; arrears-only exit cost is in the callee")
        self.assertEqual(world.treasury["NMG"], paid, "withdrawal preserves sunk opening payment")
        self.assertEqual(world.failed_journals, [settlement])
        self.assertEqual(world.completed_journals, [
            "ywc_je_v03_nmg_revenue_opening", "ywc_je_v03_nmg_revenue_negotiation"])
        entry = GENERATED_JES[settlement]
        self.assertTrue(world.conditions(field(entry, "fail"), "NMG"))
        self.assertFalse(world.conditions(field(entry, "complete"), "NMG"))
        self.assertEqual(v.get("ywc_v03_active_arc_count"), 0)
        self.assertEqual(v.get("ywc_v03_visible_task_count"), 0)
        self.assertEqual({key: v.get(key) for key in (
            "ywc_campaign_nmg_c1_outcome", "ywc_campaign_nmg_c2_outcome",
            "ywc_campaign_nmg_c3_outcome", "ywc_campaign_nmg_c1_e100_done",
            "ywc_campaign_nmg_c1_e101_done", "ywc_campaign_nmg_c1_e102_done",
            "ywc_campaign_nmg_c1_e103_done", "ywc_campaign_nmg_c1_e104_done")}, {
            "ywc_campaign_nmg_c1_outcome": 4, "ywc_campaign_nmg_c2_outcome": 3,
            "ywc_campaign_nmg_c3_outcome": 2, "ywc_campaign_nmg_c1_e100_done": 1,
            "ywc_campaign_nmg_c1_e101_done": 1, "ywc_campaign_nmg_c1_e102_done": 1,
            "ywc_campaign_nmg_c1_e103_done": 1, "ywc_campaign_nmg_c1_e104_done": 1})

    def test_revenue_notice_withdraw_guard_is_failure_only(self):
        world = NmgWorld(fixture())
        v = world.countries["NMG"]
        v.update({
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1,
            "ywc_v03_nmg_v03_nmg_autonomy_revenue_started": 1,
            "ywc_nmg_revenue_opened": 1, "ywc_nmg_revenue_stage3": 1,
            "ywc_nmg_revenue_route": 1, "ywc_nmg_revenue_quota_paid": 1,
            "ywc_nmg_revenue_audit_strict": 1, "ywc_nmg_revenue_share": 3,
            "ywc_nmg_revenue_notice36_due": 1, "ywc_nmg_revenue_notice_pending": 1029,
        })
        self.activate(world, "ywc_je_v03_nmg_revenue_settlement")
        eid = self.pulse_until_event(world, world.active_journal)
        self.assertEqual(eid, "ywc_nmg.1029")
        self.choose(world, eid, "withdraw")
        self.assertEqual(v.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"), 1)
        self.assertTrue(world.conditions(field(GENERATED_JES[world.active_journal], "fail"), "NMG"))
        self.assertFalse(world.conditions(field(GENERATED_JES[world.active_journal], "complete"), "NMG"))

        self.assertEqual(v["fixture_relations"], 25, "ordinary route pays one generic withdrawal hit")

        # Unit guard: on an arrears contract the closer's arrears exit cost replaces
        # the generic caller hit, so the same withdrawal does not debit relations twice.
        arrears_world = NmgWorld(fixture())
        arrears = arrears_world.countries["NMG"]
        arrears.update({
            "fixture_subject": 0,
            "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1,
            "ywc_v03_nmg_v03_nmg_autonomy_revenue_started": 1,
            "ywc_nmg_revenue_opened": 1, "ywc_nmg_revenue_stage3": 1,
            "ywc_nmg_revenue_route": 3, "ywc_nmg_revenue_arrears": 1,
            "ywc_nmg_revenue_quota_paid": 1, "ywc_nmg_revenue_audit_strict": 1,
            "ywc_nmg_revenue_share": 3, "ywc_nmg_revenue_notice36_due": 1,
            "ywc_nmg_revenue_notice_pending": 1029,
        })
        self.activate(arrears_world, "ywc_je_v03_nmg_revenue_settlement")
        eid = self.pulse_until_event(arrears_world, arrears_world.active_journal)
        self.assertEqual(eid, "ywc_nmg.1029")
        self.choose(arrears_world, eid, "withdraw")
        self.assertEqual(arrears["fixture_relations"], 25,
                         "arrears-specific exit cost remains one -25 penalty")
        self.assertEqual(arrears.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"), 1)

    def test_real_unified_land_chain_rejects_stale_confirm_after_law_loss_and_rewatches(self):
        world = NmgWorld(fixture())
        arc = CATALOG["arcs"][0]
        order = [j["id"] for j in arc["journals"]]
        self.activate(world, order[0])
        for key in ("unified", "rule_custom", "finish_survey", "keep_old",
                    "keep_recording", "new_assessment", "renegotiate"):
            active = world.active_journal
            eid = self.pulse_until_event(world, active)
            self.choose(world, eid, key)
            goal = arc["journals"][order.index(active)]["goal"]
            if world.conditions(parse(goal.strip()[1:-1]), "NMG"):
                world.completed_journals.append(active)
                self.activate(world, order[len(world.completed_journals)])

        event_id = self.pulse_until_event(world, world.active_journal)
        self.assertEqual(event_id, "ywc_nmg.1007")
        for _ in range(3):
            world.execute(field(GENERATED_EVENTS[event_id], "immediate"), "NMG")
            if world.countries["NMG"].get("ywc_nmg_land_six_months_complete"):
                break
            wait = event_option(event_id, "wait_retry")
            wait_effect = [n for n in wait if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
            world.execute(wait_effect, "NMG")
            world.events.clear()
            world.advance_months(3)
            event_id = self.pulse_until_event(world, world.active_journal)
            self.assertEqual(event_id, "ywc_nmg.1007")
        terminal = event_option(event_id, "settle_full")
        self.assertTrue(world.conditions(field(terminal, "trigger"), "NMG"))
        v = world.countries["NMG"]
        old_laws = set(v["fixture_laws"])
        v["fixture_laws"].clear()  # The selected route loses its actual title law after popup delivery.
        effect = [n for n in terminal if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
        before_treasury = world.treasury["NMG"]
        world.execute(effect, "NMG")
        self.assertNotIn("ywc_nmg_land_established", v)
        self.assertNotIn("ywc_v03_nmg_v03_nmg_land_arbitration_settled", v)
        self.assertEqual(v.get("ywc_nmg_land_pending"), 1007)
        self.assertEqual(v.get("ywc_nmg_land_route"), 2)
        self.assertEqual(v.get("ywc_nmg_land_fee_paid"), 1)
        self.assertEqual(world.treasury["NMG"], before_treasury)
        for suffix in ("watch_started", "watch_timer", "six_months_complete"):
            self.assertNotIn(f"ywc_nmg_land_{suffix}", v)

        world.events.clear()  # The stale popup was consumed; the authored queue owns retry.
        v["fixture_laws"] = old_laws
        for _ in range(4):
            eid = self.pulse_until_event(world, world.active_journal)
            if v.get("ywc_nmg_land_six_months_complete"):
                self.assertTrue(world.conditions(field(event_option(eid, "settle_full"), "trigger"), "NMG"))
                self.choose(world, eid, "settle_full")
                break
            self.choose(world, eid, "wait_retry")
        self.assertEqual(v.get("ywc_v03_nmg_v03_nmg_land_arbitration_settled"), 1)
        self.assertEqual(v.get("ywc_nmg_land_route"), 2)
        self.assertEqual(world.treasury["NMG"], -2000)

    def test_real_target_loss_delivers_12_and_36_month_notices_during_defer(self):
        world = NmgWorld(fixture())
        arc = CATALOG["arcs"][0]
        order = [journal["id"] for journal in arc["journals"]]
        self.activate(world, order[0])
        event_id = self.pulse_until_event(world, world.active_journal)
        self.choose(world, event_id, "mixed")
        v = world.countries["NMG"]
        # Actual selected-route readiness is lost after commitment; the normal
        # narrative queue continues to be deferred while notice delivery ages.
        v["fixture_buildings"] = {}
        delivered = set()

        def reconcile_and_handoff():
            if world.active_journal is None:
                return None
            status = self.reconcile_active_je(world)
            if status == "complete":
                next_index = len(world.completed_journals)
                if next_index < len(order):
                    self.activate(world, order[next_index])
            return status

        for _ in range(40):
            reconcile_and_handoff()
            if world.active_journal is None:
                break
            active = world.active_journal
            entry = GENERATED_JES[active]
            pulse = field(field(entry, "on_monthly_pulse"), "effect")
            world.execute(pulse, "NMG")
            if world.events:
                actual_id = world.events[-1][1]
                ev = GENERATED_EVENTS[actual_id]
                self.assertTrue(world.conditions(field(ev, "trigger"), "NMG"), actual_id)
                notice12_was_due = actual_id == "ywc_nmg.1006" and v.get("ywc_nmg_land_notice12_due") == 1
                notice36_was_due = actual_id == "ywc_nmg.1007" and v.get("ywc_nmg_land_notice36_due") == 1
                world.execute(field(ev, "immediate"), "NMG")
                delivered_this_event = False
                if notice12_was_due and v.get("ywc_nmg_land_notice12_delivered") == 1:
                    delivered.add(12)
                    delivered_this_event = True
                if notice36_was_due and v.get("ywc_nmg_land_notice36_delivered") == 1:
                    delivered.add(36)
                    delivered_this_event = True
                is_notice = delivered_this_event
                option_key = ("renegotiate" if actual_id == "ywc_nmg.1006" else "wait_retry") if is_notice else None
                option_names = []
                if option_key is None:
                    option_names = [field(body, "name").split(".")[-1]
                                    for key, _, body in ev if key == "option"]
                    option_key = "defer" if "defer" in option_names else "wait_retry" if "wait_retry" in option_names else None
                self.assertIsNotNone(option_key, (actual_id, option_names))
                option = event_option(actual_id, option_key)
                self.assertTrue(world.conditions(field(option, "trigger"), "NMG"),
                                (actual_id, option_key, v))
                effect = [n for n in option if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
                world.execute(effect, "NMG")
                world.events.clear()
            reconcile_and_handoff()
            world.advance_months(1)
            reconcile_and_handoff()
        self.assertEqual(delivered, {12, 36})
        self.assertEqual(v.get("ywc_nmg_land_route"), 1)
        self.assertEqual(v.get("ywc_nmg_land_fee_paid"), 1)
        self.assertNotIn("ywc_v03_nmg_v03_nmg_land_arbitration_settled", v)

    def test_stale_route_choice_and_failed_cash_leave_contract_retryable(self):
        for changed in ({"in_default": True}, {"gold_reserves": 0}):
            with self.subTest(changed=changed):
                world = NmgWorld(fixture())
                self.activate(world, "ywc_je_v03_nmg_land_arbitration")
                event_id = self.pulse_until_event(world, world.active_journal)
                self.assertEqual(event_id, "ywc_nmg.1000")
                world.execute(field(GENERATED_EVENTS[event_id], "immediate"), "NMG")
                v = world.countries["NMG"]
                v.update(changed)  # Popup arrived before finance changed.
                option = event_option(event_id, "mixed")
                effect = [n for n in option if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
                world.execute(effect, "NMG")
                self.assertEqual(v.get("ywc_nmg_land_route"), 0)
                self.assertNotIn("ywc_nmg_land_fee_paid", v)
                self.assertEqual(v.get("ywc_nmg_land_pending"), 1000)
                self.assertEqual(world.treasury["NMG"], 0)

    def test_wait_after_popup_loss_requeues_and_clears_stale_maturity(self):
        for short, event_id in (("land", "ywc_nmg.1007"), ("office", "ywc_nmg.1015"), ("revenue", "ywc_nmg.1027")):
            with self.subTest(lane=short):
                world = NmgWorld(fixture())
                v = world.countries["NMG"]
                v.update({f"ywc_nmg_{short}_route": 1, f"ywc_nmg_{short}_watch_started": 1,
                          f"ywc_nmg_{short}_watch_timer": 1, f"ywc_nmg_{short}_six_months_complete": 1,
                          f"ywc_nmg_{short}_fee_paid": 1, f"ywc_nmg_{short}_last_event": int(event_id.split('.')[1]),
                          "in_default": True, "ywc_v03_major_event_cooldown": 1,
                          "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1})
                e = GENERATED_EVENTS[event_id]
                wait = event_option(event_id, "wait_retry")
                effect = [n for n in wait if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
                world.execute(effect, "NMG")
                self.assertEqual(v.get(f"ywc_nmg_{short}_pending"), int(event_id.split('.')[1]))
                for suffix in ("watch_started", "watch_timer", "six_months_complete"):
                    self.assertNotIn(f"ywc_nmg_{short}_{suffix}", v)
                self.assertEqual(v.get(f"ywc_nmg_{short}_route"), 1)


if __name__ == "__main__":
    unittest.main()
