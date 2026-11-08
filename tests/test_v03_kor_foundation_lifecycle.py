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
            world.execute(review_pulse, "KOR")
            if len(world.events) > before:
                self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1016"))
                world.execute(parse(_event(self.school_arc, "ywc_kor.1016")["immediate"].strip()[1:-1]), "KOR")
                notices += 1
            world.advance_months(1)
        self.assertEqual(notices, 2)
        self.assertIn("ywc_kor_school_12_notice", country)
        self.assertIn("ywc_kor_school_36_notice", country)
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
            world.execute(self.pulse_effect, "KOR")
            if len(world.events) > before:
                self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1022"))
                world.execute(parse(arrears["immediate"].strip()[1:-1]), "KOR")
                delivered_notices += 1
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


if __name__ == "__main__":
    unittest.main()
