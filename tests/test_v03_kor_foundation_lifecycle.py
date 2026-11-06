"""Execute KOR's authored JE and event scripts through the offline harness."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

from clausewitz_harness import PulseWorld, parse

CATALOG = ROOT / "data/content/v03/countries/kor.json"
EFFECTS = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_kor_effects.txt"
SHARED_EFFECTS = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_effects.txt"
TRIGGERS = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_kor_triggers.txt"
SHARED_TRIGGERS = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt"


class KorLifecycleWorld(PulseWorld):
    """Execute authored KOR logic; only engine-owned leaf facts are fixture-backed."""

    def __init__(self, state):
        effects = EFFECTS.read_text(encoding="utf-8-sig") + "\n" + SHARED_EFFECTS.read_text(encoding="utf-8-sig")
        super().__init__(effects, {"KOR": state})
        trigger_text = TRIGGERS.read_text(encoding="utf-8-sig") + "\n" + SHARED_TRIGGERS.read_text(encoding="utf-8-sig")
        self.trigger_defs = {key: body for key, _, body in parse(trigger_text)}

    def condition(self, node, tag):
        key, comparison, value = node
        if key == "ywc_v03_can_deliver_major":
            return "ywc_v03_major_event_cooldown" not in self.countries[tag]
        if key in self.trigger_defs:
            return self.conditions(self.trigger_defs[key], tag)
        if key == "has_law_or_variant":
            return value.split(":", 1)[-1] in self.countries[tag].get("laws", set())
        if key == "institution_investment_level":
            return self.countries[tag].get("school_investment", False)
        if key == "any_scope_state":
            variables = self.countries[tag]
            building_query = next((body for name, _, body in value if name == "any_scope_building"), None)
            if building_query is None:
                return bool(variables.get("owns_state", True))
            building_type = next((field for name, _, field in building_query if name == "is_building_type"), None)
            if building_type is None:
                return False
            fact = {
                "building_port": "staffed_port",
                "building_government_administration": "staffed_office",
                "building_university": "staffed_university",
            }.get(building_type)
            return bool(variables.get("owns_state", True) and fact and variables.get(fact, False))
        return super().condition(node, tag)


def _one(nodes, key):
    return next(body for name, _, body in nodes if name == key)


def _journal(arc, journal_id):
    return next(row for row in arc["journals"] if row["id"] == journal_id)


def _event(arc, event_id):
    return next(row for row in arc["events"] if row["id"] == event_id)


def _typed_journal(je):
    return [("type", "=", je["id"])]


class KorPortsLifecycleRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.arc = next(row for row in cls.catalog["arcs"] if row["slug"] == "v03_kor_controlled_ports")
        cls.school_arc = next(row for row in cls.catalog["arcs"] if row["slug"] == "v03_kor_school_factions")
        cls.journal = _journal(cls.arc, "ywc_je_v03_kor_controlled_ports")
        cls.journal_nodes = parse(cls.journal["script"])
        cls.pulse_effect = _one(_one(cls.journal_nodes, "on_monthly_pulse"), "effect")

    def activate_entry(self, world, arc, je):
        nodes = parse(je["script"])
        self.assertTrue(world.conditions(_one(nodes, "possible"), "KOR"), je["id"])
        world.execute(_one(nodes, "immediate"), "KOR")
        world.journals.append(("KOR", _typed_journal(je)))
        self.assertFalse(world.conditions(parse(je["goal"].strip()[1:-1]), "KOR"), je["id"])
        return je

    def activate_requested_entries(self, world, arc, start_at):
        active = []
        for tag, request in world.journals[start_at:]:
            self.assertEqual(tag, "KOR")
            fields = {name: value for name, _, value in request}
            je = _journal(arc, fields["type"])
            nodes = parse(je["script"])
            if any(name == "possible" for name, _, _ in nodes):
                self.assertTrue(world.conditions(_one(nodes, "possible"), "KOR"), je["id"])
            world.execute(_one(nodes, "immediate"), "KOR")
            self.assertFalse(world.conditions(parse(je["goal"].strip()[1:-1]), "KOR"), je["id"])
            active.append(je)
        return active

    def deliver(self, world, arc, active_je, event_id):
        nodes = parse(active_je["script"])
        pulse = _one(_one(nodes, "on_monthly_pulse"), "effect")
        for _ in range(4):
            self.assertTrue(any(tag == "KOR" and dict((name, value) for name, _, value in body).get("type") == active_je["id"]
                                for tag, body in world.journals),
                            f"monthly pulse requires active JE {active_je['id']}")
            self.assertFalse(world.conditions(parse(active_je["goal"].strip()[1:-1]), "KOR"),
                             f"completed JE {active_je['id']} must not pulse")
            self.assertFalse(world.conditions(parse(active_je["exit_conditions"].strip()[1:-1]), "KOR"),
                             f"failed JE {active_je['id']} must not pulse")
            before = len(world.events)
            world.execute(pulse, "KOR")
            if len(world.events) > before:
                break
            world.advance_months(1)
        self.assertEqual(world.events[-1], ("KOR", event_id))
        event = _event(arc, event_id)
        self.assertTrue(world.conditions(parse(event["trigger"].strip()[1:-1]), "KOR"), event_id)
        world.execute(parse(event["immediate"].strip()[1:-1]), "KOR")
        return event

    def choose(self, world, event, key, arc):
        option = next(row for row in event["options"] if row["key"] == key)
        self.assertTrue(world.conditions(parse(option["trigger"].strip()[1:-1]), "KOR"), (event["id"], key))
        before = len(world.journals)
        world.execute(parse(option["effect"].strip()[1:-1]), "KOR")
        return self.activate_requested_entries(world, arc, before)

    def finish_if_terminal(self, world, je):
        goal = world.conditions(parse(je["goal"].strip()[1:-1]), "KOR")
        failed = world.conditions(parse(je["exit_conditions"].strip()[1:-1]), "KOR")
        self.assertFalse(goal and failed, (je["id"], "success and failure overlap"))
        return goal or failed

    def start_school_review(self, country, route="limited", employer_choice=None):
        world = KorLifecycleWorld(country)
        funding = _journal(self.school_arc, "ywc_je_v03_kor_school_funding")
        appointments = _journal(self.school_arc, "ywc_je_v03_kor_school_appointments")
        review = _journal(self.school_arc, "ywc_je_v03_kor_school_review")
        active = self.activate_entry(world, self.school_arc, funding)
        first = {"full": "co_manage", "office": "court_office", "limited": "limited_lessons"}[route]
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1010")
        self.choose(world, event, first, self.school_arc)
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1011")
        self.choose(world, event, "record_old_invoice", self.school_arc)
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1012")
        self.choose(world, event, "narrow_to_clerk" if route == "limited" else "share_review", self.school_arc)
        active = appointments
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1013")
        self.choose(world, event, employer_choice or ("office_post" if route in ("office", "limited") else "university_post"), self.school_arc)
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1014")
        self.choose(world, event, "narrow_to_clerk" if route == "limited" else "keep_docket", self.school_arc)
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1015")
        requested = self.choose(world, event, "start_review", self.school_arc)
        self.assertEqual([entry["id"] for entry in requested], [review["id"]])
        self.assertTrue(self.finish_if_terminal(world, appointments))
        return world, review

    def test_port_full_and_shore_strategies_reach_distinct_actual_closures(self):
        for strategy, state, route_choices, option1022, final_key, expected_outcome in (
            ("designated", {"staffed_port": 1, "laws": {"law_protectionism"}},
             ("licensed_port", "record_exception", "assign_auditors", "verify_full"),
             "repair", "settle_full", 1),
            ("shore", {"staffed_port": 0, "laws": set()},
             ("shore_ledger", "narrow", "shore_only", "shore_only"),
             "narrow", "settle_shore", 3),
        ):
            with self.subTest(strategy=strategy):
                country = {
                    "ywc_v03_initialized": 1,
                    "ywc_v03_release_version": 3,
                    "ywc_v03_active_arc_count": 0,
                    "ywc_v03_visible_task_count": 0,
                    "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
                    "yearly_gross_income": 52000,
                    "net_fixed_income": 0,
                    "bureaucracy": 100,
                    "gold_reserves": 10000,
                    "owns_state": 1,
                    "staffed_office": 1,
                    **state,
                }
                world = KorLifecycleWorld(country)
                active = self.activate_entry(world, self.arc, self.journal)

                event = self.deliver(world, self.arc, active, "ywc_kor.1018")
                self.choose(world, event, route_choices[0], self.arc)
                for event_id, key in zip(("ywc_kor.1019", "ywc_kor.1020", "ywc_kor.1021"), route_choices[1:]):
                    event = self.deliver(world, self.arc, active, event_id)
                    self.choose(world, event, key, self.arc)

                event = self.deliver(world, self.arc, active, "ywc_kor.1022")
                self.choose(world, event, option1022, self.arc)
                event = self.deliver(world, self.arc, active, "ywc_kor.1023")
                final_option = next(row for row in event["options"] if row["key"] == final_key)
                if not world.conditions(parse(final_option["trigger"].strip()[1:-1]), "KOR"):
                    self.choose(world, event, "wait_for_observation", self.arc)
                    for _ in range(8):
                        before = len(world.events)
                        world.execute(self.pulse_effect, "KOR")
                        if len(world.events) > before:
                            break
                        world.advance_months(1)
                    self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1023"))
                    event = _event(self.arc, "ywc_kor.1023")
                self.assertTrue(world.conditions(parse(final_option["trigger"].strip()[1:-1]), "KOR"), country)
                self.choose(world, event, final_key, self.arc)

                self.assertEqual(country.get("ywc_v03_kor_v03_kor_controlled_ports_outcome"), expected_outcome)
                self.assertEqual(country.get("ywc_v03_active_arc_count"), 0)
                self.assertEqual(country.get("ywc_v03_visible_task_count"), 0)
                self.assertTrue(self.finish_if_terminal(world, active))

    def test_school_full_and_limited_paths_keep_review_dispatcher_until_event_1017_closes(self):
        for strategy, first_choice, review_choice, employer_choice, docket_choice, final_key, expected_outcome in (
            ("cooperative-full", "co_manage", "share_review", "university_post", "keep_docket", "establish", 1),
            ("limited-office", "limited_lessons", "narrow_to_clerk", "office_post", "narrow_to_clerk", "compromise", 3),
        ):
            with self.subTest(strategy=strategy):
                country = {
                    "ywc_v03_initialized": 1,
                    "ywc_v03_release_version": 3,
                    "ywc_v03_active_arc_count": 0,
                    "ywc_v03_visible_task_count": 0,
                    "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
                    "yearly_gross_income": 52000,
                    "net_fixed_income": 0,
                    "bureaucracy": 100,
                    "gold_reserves": 10000,
                    "owns_state": 1,
                    "staffed_office": 1,
                    "staffed_university": 1,
                    "school_investment": 1,
                    "army_size": 0,
                    "laws": {"law_public_schools"},
                }
                world = KorLifecycleWorld(country)
                funding = _journal(self.school_arc, "ywc_je_v03_kor_school_funding")
                appointments = _journal(self.school_arc, "ywc_je_v03_kor_school_appointments")
                review = _journal(self.school_arc, "ywc_je_v03_kor_school_review")
                active = self.activate_entry(world, self.school_arc, funding)

                event = self.deliver(world, self.school_arc, active, "ywc_kor.1010")
                self.choose(world, event, first_choice, self.school_arc)
                event = self.deliver(world, self.school_arc, active, "ywc_kor.1011")
                self.choose(world, event, "record_old_invoice", self.school_arc)
                event = self.deliver(world, self.school_arc, active, "ywc_kor.1012")
                requested = self.choose(world, event, review_choice, self.school_arc)
                self.assertTrue(self.finish_if_terminal(world, funding))
                self.assertEqual([row["id"] for row in requested], [appointments["id"]])
                active = appointments

                event = self.deliver(world, self.school_arc, active, "ywc_kor.1013")
                self.choose(world, event, employer_choice, self.school_arc)
                event = self.deliver(world, self.school_arc, active, "ywc_kor.1014")
                self.choose(world, event, docket_choice, self.school_arc)
                event = self.deliver(world, self.school_arc, active, "ywc_kor.1015")
                requested = self.choose(world, event, "start_review", self.school_arc)
                self.assertTrue(self.finish_if_terminal(world, appointments))
                self.assertEqual([row["id"] for row in requested], [review["id"]])
                active = review

                event = self.deliver(world, self.school_arc, active, "ywc_kor.1016")
                final = next(row for row in event["options"] if row["key"] == final_key)
                if not world.conditions(parse(final["trigger"].strip()[1:-1]), "KOR"):
                    self.choose(world, event, "wait_for_observation", self.school_arc)
                    for _ in range(8):
                        before = len(world.events)
                        world.execute(_one(_one(parse(active["script"]), "on_monthly_pulse"), "effect"), "KOR")
                        if len(world.events) > before:
                            break
                        world.advance_months(1)
                    self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1016"))
                    event = _event(self.school_arc, "ywc_kor.1016")
                self.choose(world, event, final_key, self.school_arc)
                self.assertNotIn("ywc_v03_kor_v03_kor_school_factions_settled", country)
                self.assertFalse(self.finish_if_terminal(world, active), "JE must stay active for terminal story event 1017")

                event = self.deliver(world, self.school_arc, active, "ywc_kor.1017")
                close_key = "settle_established" if final_key == "establish" else "settle_compromise"
                self.choose(world, event, close_key, self.school_arc)
                self.assertEqual(country.get("ywc_v03_kor_v03_kor_school_factions_outcome"), expected_outcome)
                self.assertEqual(country.get("ywc_v03_active_arc_count"), 0)
                self.assertEqual(country.get("ywc_v03_visible_task_count"), 0)
                self.assertTrue(self.finish_if_terminal(world, active))

    def test_school_watch_requires_both_route_and_selected_employer_continuously(self):
        for route, employer, missing_fact, expected_outcome in (
            ("full", "office_post", "staffed_office", 1),
            ("office", "university_post", "staffed_university", 2),
        ):
            with self.subTest(route=route, employer=employer):
                country = {
                    "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                    "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
                    "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
                    "yearly_gross_income": 52000, "net_fixed_income": 0,
                    "bureaucracy": 100, "gold_reserves": 10000,
                    "owns_state": 1, "staffed_office": 1, "staffed_university": 1,
                    "school_investment": 1, "army_size": 0, "laws": {"law_public_schools"},
                }
                world, review = self.start_school_review(country, route=route, employer_choice=employer)
                pulse = _one(_one(parse(review["script"]), "on_monthly_pulse"), "effect")
                self.assertEqual(country.get("ywc_kor_school_employer_confirmed"), 1)
                self.assertEqual(country.get("ywc_kor_school_employer"), 2 if employer == "office_post" else 1)
                country[missing_fact] = 0
                for _ in range(8):
                    world.execute(pulse, "KOR"); world.advance_months(1)
                self.assertFalse(world.conditions(world.trigger_defs["ywc_kor_school_observation_target_ready"], "KOR"))
                self.assertNotIn("ywc_kor_school_six_months_complete", country)
                country[missing_fact] = 1
                for month in range(6):
                    world.execute(pulse, "KOR")
                    self.assertNotIn("ywc_kor_school_six_months_complete", country, f"must be fresh before month {month + 1}")
                    world.advance_months(1)
                world.execute(pulse, "KOR")
                self.assertIn("ywc_kor_school_six_months_complete", country)
                event = self.deliver(world, self.school_arc, review, "ywc_kor.1016")
                self.choose(world, event, "establish", self.school_arc)
                event = self.deliver(world, self.school_arc, review, "ywc_kor.1017")
                self.choose(world, event, "settle_established", self.school_arc)
                self.assertEqual(country.get("ywc_v03_kor_v03_kor_school_factions_outcome"), expected_outcome)
                self.assertTrue(self.finish_if_terminal(world, review))

    def test_full_paid_port_can_narrow_to_shore_without_new_charge(self):
        for narrow_event in ("ywc_kor.1019", "ywc_kor.1020", "ywc_kor.1021", "ywc_kor.1022"):
            with self.subTest(narrow_event=narrow_event):
                country = {
                    "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                    "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
                    "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
                    "yearly_gross_income": 52000, "net_fixed_income": 0,
                    "bureaucracy": 100, "gold_reserves": 10000,
                    "owns_state": 1, "staffed_port": 1, "staffed_office": 1,
                    "laws": {"law_protectionism"},
                }
                world = KorLifecycleWorld(country)
                active = self.activate_entry(world, self.arc, self.journal)
                event = self.deliver(world, self.arc, active, "ywc_kor.1018")
                self.choose(world, event, "licensed_port", self.arc)
                if narrow_event == "ywc_kor.1019":
                    event = self.deliver(world, self.arc, active, "ywc_kor.1019")
                    self.choose(world, event, "narrow", self.arc)
                    event = self.deliver(world, self.arc, active, "ywc_kor.1020")
                    self.choose(world, event, "shore_only", self.arc)
                    event = self.deliver(world, self.arc, active, "ywc_kor.1021")
                    self.choose(world, event, "shore_only", self.arc)
                else:
                    event = self.deliver(world, self.arc, active, "ywc_kor.1019")
                    self.choose(world, event, "record_exception", self.arc)
                    event = self.deliver(world, self.arc, active, "ywc_kor.1020")
                    if narrow_event == "ywc_kor.1020":
                        self.choose(world, event, "shore_only", self.arc)
                        event = self.deliver(world, self.arc, active, "ywc_kor.1021")
                        self.choose(world, event, "shore_only", self.arc)
                    else:
                        self.choose(world, event, "assign_auditors", self.arc)
                        event = self.deliver(world, self.arc, active, "ywc_kor.1021")
                        self.choose(world, event, "shore_only" if narrow_event == "ywc_kor.1021" else "verify_full", self.arc)
                self.assertEqual(country.get("ywc_kor_ports_filing_fee_paid"), 1)
                self.assertEqual(country.get("ywc_kor_ports_designated_paid"), 1)
                self.assertEqual(world.treasury["KOR"], -1000)
                country["gold_reserves"] = 0
                event = self.deliver(world, self.arc, active, "ywc_kor.1022")
                if narrow_event == "ywc_kor.1022":
                    self.choose(world, event, "narrow", self.arc)
                else:
                    self.choose(world, event, "repair", self.arc)
                self.assertEqual(country.get("ywc_kor_ports_route"), 3)
                self.assertEqual(country.get("ywc_kor_ports_prior_contracts_checked"), 1)
                self.assertEqual(country.get("ywc_kor_ports_filing_fee_paid"), 1)
                self.assertNotIn("ywc_kor_ports_shore_paid", country, "credit records earlier real funding, not a fictional shore debit")
                self.assertEqual(world.treasury["KOR"], -1000)
                pulse = self.pulse_effect
                for month in range(6):
                    world.execute(pulse, "KOR")
                    self.assertNotIn("ywc_kor_ports_limited_six_months_complete", country, f"fresh watch before month {month + 1}")
                    world.advance_months(1)
                world.execute(pulse, "KOR")
                self.assertIn("ywc_kor_ports_limited_six_months_complete", country)
                event = self.deliver(world, self.arc, active, "ywc_kor.1023")
                self.choose(world, event, "settle_shore", self.arc)
                self.assertEqual(country.get("ywc_v03_kor_v03_kor_controlled_ports_outcome"), 3)
                self.assertEqual(world.treasury["KOR"], -1000)

    def test_completed_school_arrangement_loss_interrupts_port_watch_and_recovery_is_fresh(self):
        country = {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000, "net_fixed_income": 0,
            "bureaucracy": 100, "gold_reserves": 10000,
            "owns_state": 1, "staffed_office": 1, "staffed_university": 1,
            "staffed_port": 1, "school_investment": 1, "army_size": 0,
            "laws": {"law_public_schools", "law_protectionism"},
        }
        world, school_review = self.start_school_review(country, route="office", employer_choice="university_post")
        school_pulse = _one(_one(parse(school_review["script"]), "on_monthly_pulse"), "effect")
        for _ in range(7):
            world.execute(school_pulse, "KOR"); world.advance_months(1)
        event = self.deliver(world, self.school_arc, school_review, "ywc_kor.1016")
        self.choose(world, event, "establish", self.school_arc)
        event = self.deliver(world, self.school_arc, school_review, "ywc_kor.1017")
        self.choose(world, event, "settle_established", self.school_arc)
        self.assertEqual(country.get("ywc_v03_kor_v03_kor_school_factions_outcome"), 2)
        self.assertEqual(country.get("ywc_kor_school_route"), 2)
        self.assertEqual(country.get("ywc_kor_school_employer"), 1)

        active = self.activate_entry(world, self.arc, self.journal)
        for event_id, key in (("ywc_kor.1018", "licensed_port"),
                              ("ywc_kor.1019", "record_exception"),
                              ("ywc_kor.1020", "assign_auditors"),
                              ("ywc_kor.1021", "verify_full"),
                              ("ywc_kor.1022", "repair")):
            event = self.deliver(world, self.arc, active, event_id)
            self.choose(world, event, key, self.arc)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_kor_ports_auditor_ready"], "KOR"))
        country["school_investment"] = 0
        country["laws"].remove("law_public_schools")
        for _ in range(8):
            world.execute(self.pulse_effect, "KOR"); world.advance_months(1)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_kor_ports_auditor_ready"], "KOR"))
        self.assertFalse(world.conditions(world.trigger_defs["ywc_kor_ports_observation_target_ready"], "KOR"))
        self.assertNotIn("ywc_kor_ports_six_months_complete", country)
        self.assertNotIn("ywc_v03_kor_v03_kor_controlled_ports_outcome", country)

        country["school_investment"] = 1
        country["laws"].add("law_public_schools")
        for month in range(6):
            world.execute(self.pulse_effect, "KOR")
            self.assertNotIn("ywc_kor_ports_six_months_complete", country, f"fresh partner watch before month {month + 1}")
            world.advance_months(1)
        world.execute(self.pulse_effect, "KOR")
        self.assertIn("ywc_kor_ports_six_months_complete", country)
        event = self.deliver(world, self.arc, active, "ywc_kor.1023")
        self.choose(world, event, "settle_full", self.arc)
        self.assertEqual(country.get("ywc_v03_kor_v03_kor_controlled_ports_outcome"), 1)
        self.assertEqual(world.treasury["KOR"], -2500)

    def test_completed_full_school_route1_keeps_university_required_for_paid_port(self):
        country = {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000, "net_fixed_income": 0,
            "bureaucracy": 100, "gold_reserves": 10000,
            "owns_state": 1, "staffed_office": 1, "staffed_university": 1,
            "staffed_port": 1, "school_investment": 1, "army_size": 0,
            "laws": {"law_public_schools", "law_protectionism"},
        }
        world, school_review = self.start_school_review(country, route="full", employer_choice="office_post")
        school_pulse = _one(_one(parse(school_review["script"]), "on_monthly_pulse"), "effect")
        for _ in range(7):
            world.execute(school_pulse, "KOR"); world.advance_months(1)
        event = self.deliver(world, self.school_arc, school_review, "ywc_kor.1016")
        self.choose(world, event, "establish", self.school_arc)
        event = self.deliver(world, self.school_arc, school_review, "ywc_kor.1017")
        self.choose(world, event, "settle_established", self.school_arc)
        self.assertEqual(country.get("ywc_v03_kor_v03_kor_school_factions_outcome"), 1)
        self.assertEqual(country.get("ywc_kor_school_route"), 1)
        self.assertEqual(country.get("ywc_kor_school_employer"), 2)

        active = self.activate_entry(world, self.arc, self.journal)
        for event_id, key in (("ywc_kor.1018", "licensed_port"),
                              ("ywc_kor.1019", "record_exception"),
                              ("ywc_kor.1020", "assign_auditors"),
                              ("ywc_kor.1021", "verify_full"),
                              ("ywc_kor.1022", "repair")):
            event = self.deliver(world, self.arc, active, event_id)
            self.choose(world, event, key, self.arc)
        port_debit = world.treasury["KOR"]
        self.assertTrue(world.conditions(world.trigger_defs["ywc_kor_ports_auditor_ready"], "KOR"))
        self.assertTrue(world.conditions(world.trigger_defs["ywc_kor_ports_observation_target_ready"], "KOR"))
        for month in range(6):
            world.execute(self.pulse_effect, "KOR")
            self.assertNotIn("ywc_kor_ports_six_months_complete", country,
                             f"full route1 watch must be fresh before month {month + 1}")
            world.advance_months(1)
        world.execute(self.pulse_effect, "KOR")
        self.assertIn("ywc_kor_ports_six_months_complete", country)
        event = self.deliver(world, self.arc, active, "ywc_kor.1023")
        settle = next(row for row in event["options"] if row["key"] == "settle_full")

        country["staffed_university"] = 0
        for _ in range(8):
            world.execute(self.pulse_effect, "KOR"); world.advance_months(1)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_kor_ports_auditor_ready"], "KOR"))
        self.assertFalse(world.conditions(world.trigger_defs["ywc_kor_ports_observation_target_ready"], "KOR"))
        self.assertNotIn("ywc_kor_ports_six_months_complete", country)
        self.assertFalse(world.conditions(parse(settle["trigger"].strip()[1:-1]), "KOR"))
        world.execute(parse(settle["effect"].strip()[1:-1]), "KOR")
        self.assertNotIn("ywc_v03_kor_v03_kor_controlled_ports_settled", country)
        self.assertNotIn("ywc_v03_kor_v03_kor_controlled_ports_outcome", country)
        self.assertEqual(country.get("ywc_v03_active_arc_count"), 1)

        country["staffed_university"] = 1
        self.choose(world, event, "wait_for_observation", self.arc)
        for month in range(6):
            world.execute(self.pulse_effect, "KOR")
            self.assertNotIn("ywc_kor_ports_six_months_complete", country,
                             f"recovered route1 watch must be fresh before month {month + 1}")
            world.advance_months(1)
        world.execute(self.pulse_effect, "KOR")
        self.assertIn("ywc_kor_ports_six_months_complete", country)
        event = self.deliver(world, self.arc, active, "ywc_kor.1023")
        self.choose(world, event, "settle_full", self.arc)
        self.assertEqual(country.get("ywc_v03_kor_v03_kor_controlled_ports_outcome"), 1)
        self.assertEqual(world.treasury["KOR"], port_debit)

    def test_ports_twelve_and_thirty_six_month_notices_interrupt_early_defer_without_skipping_steps(self):
        country = {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000, "net_fixed_income": 0,
            "bureaucracy": 100, "gold_reserves": 10000,
            "owns_state": 1, "staffed_port": 1, "staffed_office": 1,
            "laws": {"law_protectionism"},
        }
        world = KorLifecycleWorld(country)
        active = self.activate_entry(world, self.arc, self.journal)
        event = self.deliver(world, self.arc, active, "ywc_kor.1018")
        self.choose(world, event, "licensed_port", self.arc)
        pulse = self.pulse_effect
        delivered_notices = []
        for month in range(41):
            previous = len(world.events)
            world.execute(pulse, "KOR")
            if len(world.events) > previous:
                event_id = world.events[-1][1]
                self.assertIn(event_id, ("ywc_kor.1019", "ywc_kor.1022"))
                event = _event(self.arc, event_id)
                world.execute(parse(event["immediate"].strip()[1:-1]), "KOR")
                if event_id == "ywc_kor.1019":
                    self.choose(world, event, "defer", self.arc)
                else:
                    self.assertTrue(country.get("ywc_kor_ports_12_notice") or country.get("ywc_kor_ports_36_notice"))
                    delivered_notices.append((month, country.get("ywc_kor_ports_12_notice"), country.get("ywc_kor_ports_36_notice")))
                    if country.get("ywc_kor_ports_36_notice"):
                        self.choose(world, event, "record_prior_contracts", self.arc)
                    else:
                        self.choose(world, event, "defer", self.arc)
            world.advance_months(1)
        self.assertEqual(len(delivered_notices), 2, (delivered_notices, country, world.events))
        self.assertTrue(country.get("ywc_kor_ports_12_notice"))
        self.assertTrue(country.get("ywc_kor_ports_36_notice"))
        self.assertEqual(country.get("ywc_kor_ports_prior_outcome_read"), 1)
        self.assertEqual(country.get("ywc_kor_ports_pending_event"), 1020)

        for event_id, key in (("ywc_kor.1020", "assign_auditors"), ("ywc_kor.1021", "verify_full"), ("ywc_kor.1022", "repair")):
            event = self.deliver(world, self.arc, active, event_id)
            self.choose(world, event, key, self.arc)
        self.assertEqual(country.get("ywc_kor_ports_prior_contracts_checked"), 1)
        for month in range(6):
            world.execute(pulse, "KOR")
            self.assertNotIn("ywc_kor_ports_six_months_complete", country)
            world.advance_months(1)
        world.execute(pulse, "KOR")
        self.assertIn("ywc_kor_ports_six_months_complete", country)
        event = self.deliver(world, self.arc, active, "ywc_kor.1023")
        self.choose(world, event, "settle_full", self.arc)
        self.assertEqual(country.get("ywc_v03_kor_v03_kor_controlled_ports_outcome"), 1)
        self.assertEqual(world.treasury["KOR"], -1000)

    def test_ports_recovery_clears_notice_epoch_and_later_loss_can_notify_again(self):
        country = {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000, "net_fixed_income": 0,
            "bureaucracy": 100, "gold_reserves": 10000,
            "owns_state": 1, "staffed_port": 1, "staffed_office": 1,
            "laws": {"law_protectionism"},
        }
        world = KorLifecycleWorld(country)
        active = self.activate_entry(world, self.arc, self.journal)
        for event_id, key in (("ywc_kor.1018", "licensed_port"),
                              ("ywc_kor.1019", "record_exception"),
                              ("ywc_kor.1020", "assign_auditors"),
                              ("ywc_kor.1021", "verify_full"),
                              ("ywc_kor.1022", "repair")):
            event = self.deliver(world, self.arc, active, event_id)
            self.choose(world, event, key, self.arc)
        self.assertEqual(country.get("ywc_kor_ports_prior_contracts_checked"), 1)
        pulse = self.pulse_effect
        delivered12 = 0
        country["staffed_port"] = 0
        for _ in range(14):
            previous = len(world.events)
            world.execute(pulse, "KOR")
            if len(world.events) > previous:
                event_id = world.events[-1][1]
                event = _event(self.arc, event_id)
                world.execute(parse(event["immediate"].strip()[1:-1]), "KOR")
                if event_id == "ywc_kor.1022" and country.get("ywc_kor_ports_12_notice"):
                    delivered12 += 1
                    self.choose(world, event, "defer", self.arc)
                elif event_id == "ywc_kor.1023":
                    self.choose(world, event, "wait_for_observation", self.arc)
            world.advance_months(1)
        self.assertEqual(delivered12, 1, world.events)
        self.assertIn("ywc_kor_ports_12_notice", country)
        country["staffed_port"] = 1
        world.execute(pulse, "KOR")
        self.assertNotIn("ywc_kor_ports_12_notice", country)
        self.assertNotIn("ywc_kor_ports_36_notice", country)
        self.assertNotIn("ywc_kor_ports_notice_event", country)
        self.assertNotIn("ywc_kor_ports_blocked_timer_started", country)

        country["staffed_port"] = 0
        world.execute(pulse, "KOR")
        self.assertEqual(country.get("ywc_kor_ports_blocked_timer_started"), 1)
        delivered_again = 0
        for _ in range(14):
            previous = len(world.events)
            world.execute(pulse, "KOR")
            if len(world.events) > previous:
                event_id = world.events[-1][1]
                event = _event(self.arc, event_id)
                world.execute(parse(event["immediate"].strip()[1:-1]), "KOR")
                if event_id == "ywc_kor.1022" and country.get("ywc_kor_ports_12_notice"):
                    delivered_again += 1
                    self.choose(world, event, "defer", self.arc)
                elif event_id == "ywc_kor.1023":
                    self.choose(world, event, "wait_for_observation", self.arc)
            world.advance_months(1)
        self.assertEqual(delivered_again, 1, world.events)
        self.assertIn("ywc_kor_ports_12_notice", country)
        self.assertEqual(country.get("ywc_kor_ports_36_notice", 0), 0)

    def test_school_final_phase_loss_delivers_separate_12_and_36_month_remedies(self):
        country = {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0,
            "ywc_v03_visible_task_count": 0,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000,
            "net_fixed_income": 0,
            "bureaucracy": 100,
            "gold_reserves": 10000,
            "owns_state": 1,
            "staffed_office": 1,
            "school_investment": 1,
            "army_size": 0,
            "laws": {"law_public_schools"},
        }
        world = KorLifecycleWorld(country)
        funding = _journal(self.school_arc, "ywc_je_v03_kor_school_funding")
        appointments = _journal(self.school_arc, "ywc_je_v03_kor_school_appointments")
        review = _journal(self.school_arc, "ywc_je_v03_kor_school_review")
        active = self.activate_entry(world, self.school_arc, funding)
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1010")
        self.choose(world, event, "limited_lessons", self.school_arc)
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1011")
        self.choose(world, event, "record_old_invoice", self.school_arc)
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1012")
        requested = self.choose(world, event, "narrow_to_clerk", self.school_arc)
        self.assertEqual([row["id"] for row in requested], [appointments["id"]])
        active = appointments
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1013")
        self.choose(world, event, "office_post", self.school_arc)
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1014")
        self.choose(world, event, "narrow_to_clerk", self.school_arc)
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1015")
        requested = self.choose(world, event, "start_review", self.school_arc)
        self.assertEqual([row["id"] for row in requested], [review["id"]])
        active = review

        country["staffed_office"] = 0
        event = self.deliver(world, self.school_arc, active, "ywc_kor.1016")
        self.choose(world, event, "wait_for_observation", self.school_arc)
        notices = 0
        review_pulse = _one(_one(parse(active["script"]), "on_monthly_pulse"), "effect")
        for _ in range(40):
            before = len(world.events)
            notice_due_now = (
                ("ywc_kor_school_blocked_12_due" not in country and "ywc_kor_school_12_notice" not in country)
                or ("ywc_kor_school_blocked_36_due" not in country and "ywc_kor_school_36_notice" not in country)
            )
            world.execute(review_pulse, "KOR")
            if len(world.events) > before:
                if notice_due_now:
                    notices += 1
                self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1016"))
                event = _event(self.school_arc, "ywc_kor.1016")
                world.execute(parse(event["immediate"].strip()[1:-1]), "KOR")
                options = {row["key"]: row for row in event["options"]}
                if world.conditions(parse(options["defer"]["trigger"].strip()[1:-1]), "KOR"):
                    self.choose(world, event, "defer", self.school_arc)
            world.advance_months(1)
        self.assertEqual(notices, 2, (country, world.events))
        self.assertIn("ywc_kor_school_12_notice", country)
        self.assertIn("ywc_kor_school_36_notice", country)
        self.assertNotIn("ywc_kor_school_notice_event", country,
                         "repeated legal defer must not starve the overdue 36-month notice")
        event = _event(self.school_arc, "ywc_kor.1016")
        options = {row["key"]: row for row in event["options"]}
        self.assertTrue(world.conditions(parse(options["defer"]["trigger"].strip()[1:-1]), "KOR"))
        self.assertTrue(world.conditions(parse(options["withdraw"]["trigger"].strip()[1:-1]), "KOR"))
        country["staffed_office"] = 1
        world.execute(review_pulse, "KOR")
        self.assertNotIn("ywc_kor_school_12_notice", country)
        self.assertNotIn("ywc_kor_school_36_notice", country)
        self.assertNotIn("ywc_kor_school_notice_event", country)

    def test_1022_retains_a_safe_exit_after_losing_office_qualification_during_90_day_cooldown(self):
        state = {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 1,
            "ywc_v03_visible_task_count": 1,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000,
            "net_fixed_income": 0,
            "bureaucracy": 100,
            "gold_reserves": 10000,
            "owns_state": 1,
            "staffed_port": 1,
            "staffed_office": 1,
            "laws": {"law_protectionism"},
        }
        world = KorLifecycleWorld(state)

        possible = _one(self.journal_nodes, "possible")
        immediate = _one(self.journal_nodes, "immediate")
        self.assertTrue(world.conditions(possible, "KOR"))
        world.execute(immediate, "KOR")
        self.assertEqual(state.get("ywc_v03_active_arc_count"), 2)
        self.assertEqual(state.get("ywc_kor_ports_pending_event"), 1018)

        # Run the actual JE dispatcher, event immediate, and legal option effects.
        chosen = []
        for event_id, option_key in (("ywc_kor.1018", "licensed_port"),
                                     ("ywc_kor.1019", "record_exception"),
                                     ("ywc_kor.1020", "assign_auditors")):
            world.execute(self.pulse_effect, "KOR")
            self.assertEqual(world.events[-1], ("KOR", event_id))
            event = _event(self.arc, event_id)
            world.execute(parse(event["immediate"].strip()[1:-1]), "KOR")
            option = next(row for row in event["options"] if row["key"] == option_key)
            self.assertTrue(world.conditions(parse(option["trigger"].strip()[1:-1]), "KOR"), (event_id, option_key))
            world.execute(parse(option["effect"].strip()[1:-1]), "KOR")
            chosen.append(option_key)
            for _ in range(3):
                world.execute(self.pulse_effect, "KOR")
                world.advance_months(1)

        world.execute(self.pulse_effect, "KOR")
        self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1021"))
        request = _event(self.arc, "ywc_kor.1021")
        world.execute(parse(request["immediate"].strip()[1:-1]), "KOR")
        verify = next(row for row in request["options"] if row["key"] == "verify_full")
        self.assertTrue(world.conditions(parse(verify["trigger"].strip()[1:-1]), "KOR"))
        world.execute(parse(verify["effect"].strip()[1:-1]), "KOR")
        self.assertEqual(state.get("ywc_kor_ports_pending_event"), 1022)

        for month in range(3):
            world.execute(self.pulse_effect, "KOR")
            world.advance_months(1)
            if month == 0:
                state["staffed_office"] = 0
        world.execute(self.pulse_effect, "KOR")
        self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1022"))
        arrears = _event(self.arc, "ywc_kor.1022")
        options = {row["key"]: row for row in arrears["options"]}
        eligible = [key for key, option in options.items()
                    if world.conditions(parse(option["trigger"].strip()[1:-1]), "KOR")]
        self.assertTrue(eligible, "qualification loss must leave a reachable safe exit")
        delivered_notices = 0
        for _ in range(40):
            before = len(world.events)
            notice_due_now = (
                ("ywc_kor_ports_blocked_12_due" not in state and "ywc_kor_ports_12_notice" not in state)
                or ("ywc_kor_ports_blocked_36_due" not in state and "ywc_kor_ports_36_notice" not in state)
            )
            world.execute(self.pulse_effect, "KOR")
            if len(world.events) > before:
                self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1022"))
                world.execute(parse(arrears["immediate"].strip()[1:-1]), "KOR")
                if notice_due_now:
                    delivered_notices += 1
                defer = options["defer"]
                if world.conditions(parse(defer["trigger"].strip()[1:-1]), "KOR"):
                    self.choose(world, arrears, "defer", self.arc)
            world.advance_months(1)
        self.assertEqual(delivered_notices, 2, "12- and 36-month notices must both deliver on their own queue")
        self.assertIn("ywc_kor_ports_12_notice", state)
        self.assertIn("ywc_kor_ports_36_notice", state)
        self.assertTrue(world.conditions(parse(options["defer"]["trigger"].strip()[1:-1]), "KOR"))
        self.assertTrue(world.conditions(parse(options["withdraw"]["trigger"].strip()[1:-1]), "KOR"))
        state["staffed_office"] = 1
        world.execute(self.pulse_effect, "KOR")
        self.assertNotIn("ywc_kor_ports_12_notice", state)
        self.assertNotIn("ywc_kor_ports_36_notice", state)
        self.assertNotIn("ywc_kor_ports_notice_event", state)
        withdraw = options["withdraw"]
        world.execute(parse(withdraw["effect"].strip()[1:-1]), "KOR")
        self.assertEqual(state.get("ywc_v03_kor_v03_kor_controlled_ports_outcome"), 4)
        self.assertEqual(state.get("ywc_v03_active_arc_count"), 1)
        self.assertEqual(state.get("ywc_v03_visible_task_count"), 1)
        self.assertFalse(world.conditions(parse(self.journal["goal"].strip()[1:-1]), "KOR"))
        self.assertTrue(world.conditions(parse(self.journal["exit_conditions"].strip()[1:-1]), "KOR"))

    def test_school_and_ports_claim_independent_queues_without_capturing_prototype_queue(self):
        state = {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 1,
            "ywc_v03_visible_task_count": 1,
            "ywc_v03_kor_v03_kor_military_accounts_started": 1,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "ywc_kor_pending_event": 1006,
            "yearly_gross_income": 52000,
            "net_fixed_income": 0,
            "bureaucracy": 100,
            "gold_reserves": 10000,
            "staffed_office": 1,
            "laws": {"law_public_schools"},
        }
        world = KorLifecycleWorld(state)
        for arc in (self.school_arc, self.arc):
            journal = arc["journals"][0]
            nodes = parse(journal["script"])
            self.assertTrue(world.conditions(_one(nodes, "possible"), "KOR"), arc["slug"])
            world.execute(_one(nodes, "immediate"), "KOR")
        self.assertEqual(state.get("ywc_kor_pending_event"), 1006)
        self.assertEqual(state.get("ywc_kor_school_pending_event"), 1010)
        self.assertEqual(state.get("ywc_kor_ports_pending_event"), 1018)
        self.assertEqual(state.get("ywc_v03_active_arc_count"), 3)
        self.assertEqual(state.get("ywc_v03_visible_task_count"), 3)

        school_je = self.school_arc["journals"][0]
        school_pulse = _one(_one(parse(school_je["script"]), "on_monthly_pulse"), "effect")
        ports_pulse = _one(_one(parse(self.journal["script"]), "on_monthly_pulse"), "effect")
        world.execute(school_pulse, "KOR")
        self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1010"))
        school_event = _event(self.school_arc, "ywc_kor.1010")
        world.execute(parse(school_event["immediate"].strip()[1:-1]), "KOR")
        self.assertEqual(state.get("ywc_kor_pending_event"), 1006)
        event_count = len(world.events)
        world.execute(ports_pulse, "KOR")
        self.assertEqual(len(world.events), event_count, "the other new arc must respect the shared cooldown")
        for _ in range(3):
            world.execute(school_pulse, "KOR")
            world.execute(ports_pulse, "KOR")
            world.advance_months(1)
        world.execute(ports_pulse, "KOR")
        self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1018"))
        self.assertEqual(state.get("ywc_kor_pending_event"), 1006)

    def test_legacy_global_pending_event_is_rehomed_only_to_its_own_started_arc(self):
        state = {
            "ywc_v03_initialized": 1,
            "ywc_v03_active_arc_count": 2,
            "ywc_v03_visible_task_count": 2,
            "ywc_v03_major_event_cooldown": 1,
            "ywc_v03_kor_v03_kor_school_factions_started": 1,
            "ywc_v03_kor_v03_kor_controlled_ports_started": 1,
            "ywc_kor_pending_event": 1012,
        }
        world = KorLifecycleWorld(state)
        school_pulse = _one(_one(parse(self.school_arc["journals"][0]["script"]), "on_monthly_pulse"), "effect")
        ports_pulse = _one(_one(parse(self.journal["script"]), "on_monthly_pulse"), "effect")
        world.execute(school_pulse, "KOR")
        self.assertNotIn("ywc_kor_pending_event", state)
        self.assertEqual(state.get("ywc_kor_school_pending_event"), 1012)
        self.assertNotIn("ywc_kor_ports_pending_event", state)
        world.execute(school_pulse, "KOR")
        self.assertEqual(state.get("ywc_kor_school_pending_event"), 1012)

        state["ywc_kor_pending_event"] = 1021
        world.execute(school_pulse, "KOR")
        self.assertEqual(state.get("ywc_kor_pending_event"), 1021, "school must leave its sibling's old queue untouched")
        world.execute(ports_pulse, "KOR")
        self.assertNotIn("ywc_kor_pending_event", state)
        self.assertEqual(state.get("ywc_kor_ports_pending_event"), 1021)

    def test_school_entry_fee_failure_does_not_advance_the_actual_option_queue(self):
        state = {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0,
            "ywc_v03_visible_task_count": 0,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000,
            "net_fixed_income": 0,
            "bureaucracy": 100,
            "gold_reserves": 10000,
            "staffed_office": 1,
            "laws": {"law_public_schools"},
        }
        world = KorLifecycleWorld(state)
        journal = self.school_arc["journals"][0]
        journal_nodes = parse(journal["script"])
        self.assertTrue(world.conditions(_one(journal_nodes, "possible"), "KOR"))
        world.execute(_one(journal_nodes, "immediate"), "KOR")
        school_pulse = _one(_one(journal_nodes, "on_monthly_pulse"), "effect")
        world.execute(school_pulse, "KOR")
        self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1010"))
        event = _event(self.school_arc, "ywc_kor.1010")
        world.execute(parse(event["immediate"].strip()[1:-1]), "KOR")
        option = next(row for row in event["options"] if row["key"] == "co_manage")
        self.assertTrue(world.conditions(parse(option["trigger"].strip()[1:-1]), "KOR"))
        state["gold_reserves"] = 0
        world.execute(parse(option["effect"].strip()[1:-1]), "KOR")
        self.assertNotIn("ywc_kor_school_filing_fee_paid", state)
        self.assertEqual(state.get("ywc_kor_school_route"), 0)
        self.assertEqual(state.get("ywc_kor_school_pending_event"), 1010)

    def test_port_entry_fee_failure_does_not_advance_the_actual_option_queue(self):
        state = {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0,
            "ywc_v03_visible_task_count": 0,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000,
            "net_fixed_income": 0,
            "bureaucracy": 100,
            "gold_reserves": 10000,
            "staffed_port": 1,
            "staffed_office": 1,
            "laws": {"law_protectionism"},
        }
        world = KorLifecycleWorld(state)
        active = self.activate_entry(world, self.arc, self.journal)
        event = self.deliver(world, self.arc, active, "ywc_kor.1018")
        option = next(row for row in event["options"] if row["key"] == "licensed_port")
        self.assertTrue(world.conditions(parse(option["trigger"].strip()[1:-1]), "KOR"))
        state["gold_reserves"] = 0
        world.execute(parse(option["effect"].strip()[1:-1]), "KOR")
        self.assertNotIn("ywc_kor_ports_filing_fee_paid", state)
        self.assertNotIn("ywc_kor_ports_route", state)
        self.assertEqual(state.get("ywc_kor_ports_pending_event"), 1018)

    def test_school_second_invoice_reserve_failure_retries_the_same_actual_node(self):
        for loss in ("cash", "default", "bankruptcy"):
            with self.subTest(loss=loss):
                state = {
                    "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                    "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
                    "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
                    "ywc_v03_kor_v03_kor_military_accounts_outcome": 4,
                    "yearly_gross_income": 52000, "net_fixed_income": 0,
                    "bureaucracy": 100, "gold_reserves": 10000,
                    "staffed_office": 1, "laws": {"law_public_schools"},
                }
                world = KorLifecycleWorld(state)
                active = self.activate_entry(world, self.school_arc,
                                             _journal(self.school_arc, "ywc_je_v03_kor_school_funding"))
                event = self.deliver(world, self.school_arc, active, "ywc_kor.1010")
                self.choose(world, event, "limited_lessons", self.school_arc)
                event = self.deliver(world, self.school_arc, active, "ywc_kor.1011")
                option = next(row for row in event["options"] if row["key"] == "record_old_invoice")
                self.assertTrue(world.conditions(parse(option["trigger"].strip()[1:-1]), "KOR"))
                if loss == "cash":
                    state["gold_reserves"] = 0
                elif loss == "default":
                    state["in_default"] = 1
                else:
                    world.modifiers.append(("KOR", {"modifier": "declared_bankruptcy"}))
                world.execute(parse(option["effect"].strip()[1:-1]), "KOR")
                self.assertNotIn("ywc_kor_school_old_invoice_paid", state)
                self.assertNotIn("ywc_kor_school_old_account_recorded", state)
                self.assertEqual(state.get("ywc_kor_school_pending_event"), 1011)

    def test_school_actual_withdrawal_is_failure_not_review_goal(self):
        country = {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000, "net_fixed_income": 0,
            "bureaucracy": 100, "gold_reserves": 10000,
            "owns_state": 1, "staffed_office": 1,
            "school_investment": 1, "army_size": 0,
            "laws": {"law_public_schools"},
        }
        world, review = self.start_school_review(country)
        event = self.deliver(world, self.school_arc, review, "ywc_kor.1016")
        self.choose(world, event, "withdraw", self.school_arc)
        goal = world.conditions(parse(review["goal"].strip()[1:-1]), "KOR")
        failed = world.conditions(parse(review["exit_conditions"].strip()[1:-1]), "KOR")
        self.assertFalse(goal, "school withdrawal outcome 4 must fail, never satisfy success goal")
        self.assertTrue(failed, "withdrawal must stay on the explicit failure exit")
        self.assertFalse(goal and failed)

    def test_school_proposal_does_not_disable_loss_clock_or_real_withdrawal(self):
        country = {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000, "net_fixed_income": 0,
            "bureaucracy": 100, "gold_reserves": 10000,
            "owns_state": 1, "staffed_office": 1, "staffed_university": 1,
            "school_investment": 1, "army_size": 0, "laws": {"law_public_schools"},
        }
        world, review = self.start_school_review(country, route="full")
        pulse = _one(_one(parse(review["script"]), "on_monthly_pulse"), "effect")
        for _ in range(7):
            world.execute(pulse, "KOR")
            world.advance_months(1)
        event = self.deliver(world, self.school_arc, review, "ywc_kor.1016")
        self.choose(world, event, "establish", self.school_arc)
        self.assertNotIn("ywc_v03_kor_v03_kor_school_factions_settled", country)
        country["in_default"] = 1
        world.execute(pulse, "KOR")
        self.assertNotIn("ywc_kor_school_six_months_complete", country,
                         "proposal state must not freeze earned maturity after eligibility loss")
        self.assertIn("ywc_kor_school_blocked_timer_started", country)
        event = self.deliver(world, self.school_arc, review, "ywc_kor.1017")
        self.choose(world, event, "withdraw", self.school_arc)
        self.assertEqual(country.get("ywc_v03_kor_v03_kor_school_factions_outcome"), 4)
        self.assertEqual(country.get("ywc_v03_active_arc_count"), 0)

    def test_school_stale_terminal_event_cannot_settle_after_default_begins(self):
        country = {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000, "net_fixed_income": 0,
            "bureaucracy": 100, "gold_reserves": 10000,
            "owns_state": 1, "staffed_office": 1, "staffed_university": 1,
            "school_investment": 1, "army_size": 0, "laws": {"law_public_schools"},
        }
        world, review = self.start_school_review(country, route="full")
        pulse = _one(_one(parse(review["script"]), "on_monthly_pulse"), "effect")
        for _ in range(7):
            world.execute(pulse, "KOR")
            world.advance_months(1)
        event = self.deliver(world, self.school_arc, review, "ywc_kor.1016")
        self.choose(world, event, "establish", self.school_arc)
        event = self.deliver(world, self.school_arc, review, "ywc_kor.1017")
        option = next(row for row in event["options"] if row["key"] == "settle_established")
        country["in_default"] = 1
        self.assertFalse(world.conditions(parse(option["trigger"].strip()[1:-1]), "KOR"),
                         "terminal popup must lose success eligibility when default begins")
        world.execute(parse(option["effect"].strip()[1:-1]), "KOR")
        self.assertNotIn("ywc_v03_kor_v03_kor_school_factions_settled", country)
        self.assertNotIn("ywc_v03_kor_v03_kor_school_factions_outcome", country)
        self.assertEqual(country.get("ywc_v03_active_arc_count"), 1)
        country["in_default"] = 0
        country["is_at_war"] = 1
        self.assertFalse(world.conditions(parse(option["trigger"].strip()[1:-1]), "KOR"))
        world.execute(parse(option["effect"].strip()[1:-1]), "KOR")
        self.assertNotIn("ywc_v03_kor_v03_kor_school_factions_outcome", country)
        country["is_at_war"] = 0
        retry = next(row for row in event["options"] if row["key"] == "retry")
        world.execute(parse(retry["effect"].strip()[1:-1]), "KOR")
        country["in_default"] = 0
        for _ in range(7):
            world.execute(pulse, "KOR")
            world.advance_months(1)
        event = self.deliver(world, self.school_arc, review, "ywc_kor.1016")
        self.choose(world, event, "establish", self.school_arc)
        self.assertEqual(country.get("ywc_kor_school_pending_event"), 1017,
                         "recovered proposal must queue its real settlement event again")
        event = self.deliver(world, self.school_arc, review, "ywc_kor.1017")
        self.choose(world, event, "settle_established", self.school_arc)
        self.assertEqual(country.get("ywc_v03_kor_v03_kor_school_factions_outcome"), 1)
        self.assertEqual(country.get("ywc_v03_active_arc_count"), 0)

    def test_school_office_cannot_mature_the_selected_university_target(self):
        country = {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000, "net_fixed_income": 0,
            "bureaucracy": 100, "gold_reserves": 10000,
            "owns_state": 1, "staffed_office": 1, "staffed_university": 0,
            "school_investment": 1, "army_size": 0, "laws": {"law_public_schools"},
        }
        world, review = self.start_school_review(country, route="full", employer_choice="office_post")
        pulse = _one(_one(parse(review["script"]), "on_monthly_pulse"), "effect")
        for _ in range(8):
            world.execute(pulse, "KOR")
            world.advance_months(1)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_kor_school_route_execution_ready"], "KOR"))
        self.assertFalse(world.conditions(world.trigger_defs["ywc_kor_school_full_ready"], "KOR"))
        self.assertNotIn("ywc_kor_school_six_months_complete", country,
                         "office readiness cannot mature the full university target")

    def test_port_stale_popup_cannot_close_after_watch_loss_and_brief_recovery(self):
        country = {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "yearly_gross_income": 52000, "net_fixed_income": 0,
            "bureaucracy": 100, "gold_reserves": 10000,
            "owns_state": 1, "staffed_office": 1, "staffed_port": 1,
            "laws": {"law_protectionism"},
        }
        world = KorLifecycleWorld(country)
        active = self.activate_entry(world, self.arc, self.journal)
        for event_id, key in (("ywc_kor.1018", "licensed_port"),
                              ("ywc_kor.1019", "record_exception"),
                              ("ywc_kor.1020", "assign_auditors"),
                              ("ywc_kor.1021", "verify_full"),
                              ("ywc_kor.1022", "repair")):
            event = self.deliver(world, self.arc, active, event_id)
            self.choose(world, event, key, self.arc)
        event = self.deliver(world, self.arc, active, "ywc_kor.1023")
        option = next(row for row in event["options"] if row["key"] == "settle_full")
        pulse = self.pulse_effect
        country["in_default"] = 1
        world.execute(pulse, "KOR")
        self.assertNotIn("ywc_kor_ports_six_months_complete", country)
        country["in_default"] = 0
        world.execute(pulse, "KOR")
        self.assertFalse(world.conditions(parse(option["trigger"].strip()[1:-1]), "KOR"),
                         "brief solvency return cannot revive the stale matured popup")
        world.execute(parse(option["effect"].strip()[1:-1]), "KOR")
        self.assertNotIn("ywc_v03_kor_v03_kor_controlled_ports_settled", country)
        self.assertNotIn("ywc_v03_kor_v03_kor_controlled_ports_outcome", country)
        self.assertEqual(country.get("ywc_v03_active_arc_count"), 1)
        country["is_at_war"] = 1
        world.execute(pulse, "KOR")
        self.assertFalse(world.conditions(parse(option["trigger"].strip()[1:-1]), "KOR"))
        world.execute(parse(option["effect"].strip()[1:-1]), "KOR")
        self.assertNotIn("ywc_v03_kor_v03_kor_controlled_ports_outcome", country)
        country["is_at_war"] = 0
        self.choose(world, event, "wait_for_observation", self.arc)
        for _ in range(7):
            world.execute(pulse, "KOR")
            world.advance_months(1)
        event = self.deliver(world, self.arc, active, "ywc_kor.1023")
        option = next(row for row in event["options"] if row["key"] == "settle_full")
        self.assertTrue(world.conditions(parse(option["trigger"].strip()[1:-1]), "KOR"))
        self.choose(world, event, "settle_full", self.arc)
        self.assertEqual(country.get("ywc_v03_kor_v03_kor_controlled_ports_outcome"), 1)
        self.assertEqual(country.get("ywc_v03_active_arc_count"), 0)



if __name__ == "__main__":
    unittest.main()
