"""Actual-source delivery regressions for the DMG inline scheduler.

The offline Clausewitz harness supplies only facts the game engine normally
owns. Admissions, monthly JE effects, sender branches, event gates/immediates,
and wait choices are loaded from the repository's real generated source.
"""
import copy
import hashlib
import json
import re
import itertools
import unittest
from pathlib import Path

from tools.v03_inline_delivery_adapter import (
    queue_candidates,
    render_inline_country_adapters,
    source_binding,
    validate_inline_catalog,
)
from tests.test_v03_dmg_foundation_lifecycle import (
    DmgWorld,
    DMG_TRIGGER_MAP,
    EFFECTS as DMG_EFFECT_SOURCE,
    SHARED_EFFECTS,
    SHARED_TRIGGERS,
    _actual_option,
    _actual_option_effect,
    _field,
    _generated_event,
    _generated_je,
    _nodes_field,
)
from tests.clausewitz_harness import parse

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/content/v03/countries/dmg.json"
JE_PATH = ROOT / "yongchang_world/common/journal_entries/ywc_v03_country_dmg_journal.txt"
EVENT_PATH = ROOT / "yongchang_world/events/ywc_v03_country_dmg_events.txt"
TRIGGER_PATH = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_delivery_dmg_triggers.txt"
EFFECT_PATH = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_delivery_dmg_effects.txt"
def _read(path):
    return path.read_text(encoding="utf-8-sig")


SHARED_TRIGGER_MAP = {key: body for key, _, body in parse(_read(ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt"))}
DELIVERY_TRIGGER_MAP = {key: body for key, _, body in parse(_read(TRIGGER_PATH))}
DELIVERY_EFFECT_SOURCE = _read(EFFECT_PATH)
ENGINE_FACTS = {
    # These predicates require Clausewitz country/state/pop/building objects.
    # The fixture supplies those facts while every surrounding script gate,
    # scheduler decision and event/option AST still runs through the harness.
    "ywc_dmg_v03_has_owned_state": "fixture_owned_state",
    "ywc_dmg_v03_has_multiple_identity_groups": "fixture_multiple_identity_groups",
    "ywc_dmg_v03_has_low_acceptance_pop": "fixture_low_acceptance_pop",
    "ywc_dmg_v03_has_fully_accepted_secondary_pop": "fixture_fully_accepted_pop",
    "ywc_dmg_v03_government_appointment_ready": "fixture_government_appointment_ready",
    "ywc_dmg_v03_military_appointment_ready": "fixture_military_appointment_ready",
    "ywc_dmg_v03_electoral_representative_ready": "fixture_electoral_representative_ready",
    "ywc_dmg_v03_common_political_qualification_ready": "fixture_political_qualification_ready",
    "ywc_dmg_v03_secondary_local_office_ready": "fixture_secondary_office_ready",
    "ywc_dmg_foundation_agriculture_employment": "fixture_agriculture_employment",
}


class DmgInlineWorld(DmgWorld):
    """Execute actual DMG/core/delivery scripts; stub only engine owned-state facts."""
    def __init__(self):
        facts = {
            "ywc_v03_initialized": 1,
            "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0,
            "ywc_v03_visible_task_count": 0,
            "fixture_owned_state": 1,
            "net_fixed_income": 100,
            "yearly_gross_income": 5200,
            "bureaucracy": 100,
            "fixture_multiple_identity_groups": 1,
            "fixture_low_acceptance_pop": 1,
            "fixture_fully_accepted_pop": 1,
            "fixture_government_appointment_ready": 1,
            "fixture_military_appointment_ready": 1,
            "fixture_electoral_representative_ready": 1,
            "fixture_political_qualification_ready": 1,
            "fixture_secondary_office_ready": 1,
            "fixture_agriculture_employment": 1,
        }
        super().__init__(DMG_EFFECT_SOURCE + "\n" + SHARED_EFFECTS + "\n" + DELIVERY_EFFECT_SOURCE,
                         {"DMG": facts})
        self.scripted_triggers = {**SHARED_TRIGGER_MAP, **DMG_TRIGGER_MAP, **DELIVERY_TRIGGER_MAP}
        self.arc_by_journal = {}

    def condition(self, node, tag):
        key, comparison, value = node
        if key in ENGINE_FACTS:
            actual = bool(self.countries[tag].get(ENGINE_FACTS[key], 0))
            return actual == (value == "yes")
        if key in self.scripted_triggers and value == "yes":
            return self.conditions(self.scripted_triggers[key], tag)
        if key == "any_scope_state":
            # Only the country-owned-state fact is represented here; deeper
            # population/building facts remain unknown and fail in the parent.
            if all(child in (("owner", "=", "ROOT"), ("is_owned_by", "=", "ROOT")) for child in value):
                return bool(self.countries[tag].get("fixture_owned_state", 0))
        if key == "ywc_dmg_v03_government_appointment_ready":
            return bool(self.countries[tag].get("fixture_government_appointment_ready", 0)) == (value == "yes")
        return super().condition(node, tag)


def _admit_real_je(world, arc):
    journal = arc["journals"][0]
    generated = _generated_je(journal["id"])
    possible = _nodes_field(generated, "possible")
    if not world.conditions(possible, "DMG"):
        raise AssertionError(f"real JE admission rejected {journal['id']}: {world.countries['DMG']}")
    world.execute(_nodes_field(generated, "immediate"), "DMG")
    world.journals.append(("DMG", [("type", "=", journal["id"])]))
    world.arc_by_journal[journal["id"]] = arc


def _pulse_real_je(world, arc):
    journal = arc["journals"][0]
    generated = _generated_je(journal["id"])
    world.execute(_nodes_field(_nodes_field(generated, "on_monthly_pulse"), "effect"), "DMG")


def _receive_actual_event_and_wait(world, arc, event_id, *, run_wait=True):
    event = next(e for e in arc["events"] if e["id"] == event_id)
    generated = _generated_event(event_id)
    reservation = world.countries["DMG"].get("ywc_v03_dmg_inline_reservation")
    if isinstance(reservation, (int, float)):
        reservation = int(reservation)
    self = DmgActualFairDelivery
    candidate = self.CANDIDATES.get(reservation)
    if candidate is None or candidate["arc"]["slug"] != arc["slug"] or candidate["proof"]["event"] != event_id:
        raise AssertionError(f"sender did not reserve this actual event/class: {reservation}, {event_id}")
    ack_name = f"ywc_v03_dmg_inline_ack_{reservation}"
    if ack_name not in self.RENDERED["ack_hooks"].get(event_id, []):
        raise AssertionError(f"event {event_id} is not wired to selected-class receipt {ack_name}")
    state = world.countries["DMG"]
    sibling_queues = {
        q["queue"]: state[q["queue"]]
        for proof in arc["inline_delivery_adapter"]["branches"]
        if proof["event"] == event_id
        for q in proof["candidates"]
        if q["queue"] != candidate["queue"]["queue"] and q["queue"] in state
    }
    trigger = _nodes_field(generated, "trigger")
    if not world.conditions(trigger, "DMG"):
        raise AssertionError(f"real event trigger rejected {event_id}; state={world.countries['DMG']}")
    world.execute(_nodes_field(generated, "immediate"), "DMG")
    state = world.countries["DMG"]
    if "ywc_v03_dmg_inline_reservation" in state or "ywc_v03_dmg_inline_timer" in state:
        raise AssertionError(f"actual immediate ACK did not consume reservation {reservation}")
    slot = next(i for i, item in enumerate(self.ARCS, 1) if item["slug"] == arc["slug"])
    served = f"ywc_v03_dmg_inline_served_{slot}"
    if state.get(served) != state.get("ywc_v03_dmg_inline_round"):
        raise AssertionError(f"actual immediate did not record served arc {arc['slug']}")
    if candidate["queue"]["queue"] in state:
        raise AssertionError(f"selected authored queue survived its valid ACK: {candidate['queue']['queue']}")
    for queue, value in sibling_queues.items():
        if state.get(queue) != value:
            raise AssertionError(f"ACK consumed or mutated sibling authored queue {queue}: {value} -> {state.get(queue)}")
    receipt = re.search(r"name\s*=\s*(ywc_v03_dmg_[a-z0-9_]*_last_event)\s+value\s*=\s*([0-9]+)", event["immediate"])
    if receipt is None or state.get(receipt.group(1)) != int(receipt.group(2)):
        raise AssertionError(f"actual event immediate did not write the selected receipt for {event_id}")
    if not run_wait:
        return
    wait_key = next((key for key in ("defer", "wait_for_posting", "renegotiate")
                     if any(o["key"] == key for o in event["options"])), None)
    if wait_key is None:
        raise AssertionError(f"{event_id} has no legal nonterminal wait option")
    option = _actual_option(event_id, wait_key)
    option_trigger = _nodes_field(option, "trigger") if any(k == "trigger" for k, _, _ in option) else []
    if option_trigger and not world.conditions(option_trigger, "DMG"):
        raise AssertionError(f"authored wait option unavailable: {event_id}.{wait_key}")
    world.execute(_actual_option_effect(event_id, wait_key), "DMG")


def _block(source, name):
    """Extract one top-level generated Clausewitz definition."""
    match = re.search(r"(?m)^" + re.escape(name) + r"\s*=\s*\{", source)
    if not match:
        raise AssertionError(f"missing generated definition {name}")
    depth = 0
    for pos in range(match.start(), len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():pos + 1]
    raise AssertionError(f"unclosed generated definition {name}")


class DmgActualFairDelivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(_read(CATALOG_PATH))
        cls.rendered = render_inline_country_adapters(cls.catalog)
        cls.ARCS = [a for a in cls.catalog["arcs"] if a.get("era") == "foundation"]
        cls.CANDIDATES = {}
        candidate_id = 0
        for arc in cls.ARCS:
            for proof in arc["inline_delivery_adapter"]["branches"]:
                for candidate in proof["candidates"]:
                    candidate_id += 1
                    cls.CANDIDATES[candidate_id] = {"arc": arc, "proof": proof, "queue": candidate}
        cls.RENDERED = cls.rendered
        cls.generated_jes = _read(JE_PATH)
        cls.generated_events = _read(EVENT_PATH)
        cls.triggers = _read(TRIGGER_PATH)
        cls.effects = _read(EFFECT_PATH)

    def test_all_real_sender_branches_are_source_bound_and_generated(self):
        validate_inline_catalog(self.catalog)
        arcs = [a for a in self.catalog["arcs"] if a.get("era") == "foundation"]
        self.assertEqual(len(arcs), 3)
        branch_total = 0
        classes = set()
        for arc in arcs:
            adapter = arc["inline_delivery_adapter"]
            for phase in adapter["live_phases"]:
                journal = next(j for j in arc["journals"] if j["id"] == phase["journal"])
                binding = source_binding(journal["id"], journal["script"])
                self.assertEqual(
                    hashlib.sha256(journal["script"].encode()).hexdigest(),
                    phase["source_script_sha256"],
                )
                expected_script = self.rendered["journal_scripts"][journal["id"]]
                self.assertIn("ywc_v03_dmg_inline_prepare = yes", expected_script)
                generated = _block(self.generated_jes, journal["id"])
                # The generated JE adds catalog goal/fail fields; compare each
                # source-script field directly, including the complete pulse AST.
                actual_fields = dict((key, body) for key, _, body in parse(generated)[0][2])
                expected_fields = dict((key, body) for key, _, body in parse(journal["id"] + " = " + expected_script)[0][2])
                for field in ("possible", "on_monthly_pulse"):
                    self.assertEqual(actual_fields[field], expected_fields[field], (journal["id"], field))
                actual_immediate = actual_fields["immediate"]
                self.assertEqual(actual_immediate[:-1], expected_fields["immediate"], journal["id"])
                self.assertEqual(actual_immediate[-1][0], "set_variable", journal["id"])
                self.assertEqual(actual_immediate[-1][2][0][2], self.rendered["live_witnesses"][journal["id"]])
                for branch in binding["branches"]:
                    self.assertIn(f"OR = {{ ywc_v03_dmg_inline_turn_", generated)
                    self.assertIn(f"id = {branch['event']}", generated)
                branch_total += len(binding["branches"])
                for proof in adapter["branches"]:
                    classes.update(c["kind"] for c in proof["candidates"])
        self.assertEqual(branch_total, 29)
        self.assertTrue({"normal", "notice12", "notice36"} <= classes)
        self.assertIn("ywc_v03_dmg_inline_candidate_", self.triggers)
        self.assertIn("ywc_v03_dmg_inline_reserve_", self.effects)

    def test_real_event_immediates_are_the_only_ack_receipt_path(self):
        for event_id, hooks in self.rendered["ack_hooks"].items():
            generated = _block(self.generated_events, event_id)
            immediate = generated.split("immediate =", 1)[1].split("\n    option =", 1)[0]
            for hook in hooks:
                self.assertIn(hook, immediate, (event_id, hook))
                self.assertRegex(immediate, r"ywc_v03_dmg_v03_dmg_[a-z_]+_last_event")
        # Every selected-class ACK checks reservation, expiry, receipt presence
        # and receipt value before it can remove the authored source queue.
        effects = self.effects
        for candidate in range(1, 50):
            name = f"ywc_v03_dmg_inline_ack_{candidate}"
            if name not in effects:
                continue
            block = _block(effects, name)
            self.assertIn("has_variable = ywc_v03_dmg_inline_timer", block)
            self.assertRegex(block, r"has_variable = ywc_v03_dmg_v03_dmg_[a-z_]+_last_event")
            self.assertIn("remove_variable = ywc_v03_dmg_inline_reservation", block)
        self.assertIn("has_variable = ywc_v03_dmg_inline_timer", effects)

    def test_real_admissions_and_source_pulses_are_fair_in_every_order(self):
        arcs = [a for a in self.catalog["arcs"] if a.get("era") == "foundation"]
        event_to_arc = {event["id"]: arc for arc in arcs for event in arc["events"]}
        self.assertEqual(len(arcs), 3)
        for order in itertools.permutations(arcs):
            with self.subTest(order=tuple(a["slug"] for a in order)):
                world = DmgInlineWorld()
                for arc in arcs:
                    _admit_real_je(world, arc)
                counts = {arc["slug"]: 0 for arc in arcs}
                for opportunity in range(15):
                    if opportunity:
                        # Advance the real calendar and run all three authored
                        # monthly business pulses at 30 and 60 days. Then check
                        # the exact day-89/90 gate on a copy before day-90's
                        # third monthly pulse is run in the live world.
                        for _month in (1, 2):
                            world.advance_months(1)
                            for driver in order:
                                previous = len(world.events)
                                _pulse_real_je(world, driver)
                                self.assertEqual(len(world.events), previous,
                                                 "shared major-event cooldown expired before day 90")
                        boundary = copy.deepcopy(world)
                        boundary.advance_days(29)
                        can_deliver = ("ywc_v03_can_deliver_major", "=", "yes")
                        self.assertFalse(boundary.condition(can_deliver, "DMG"),
                                         "shared cooldown must remain active at day 89")
                        boundary.advance_days(1)
                        self.assertTrue(boundary.condition(can_deliver, "DMG"),
                                        "shared cooldown must expire at day 90")
                        world.advance_months(1)
                    for driver in order:
                        previous = len(world.events)
                        _pulse_real_je(world, driver)
                        new_events = world.events[previous:]
                        self.assertLessEqual(len(new_events), 1, (driver["slug"], new_events))
                        if not new_events:
                            continue
                        tag, event_id = new_events[-1]
                        self.assertEqual(tag, "DMG")
                        recipient = event_to_arc.get(event_id)
                        self.assertIsNotNone(recipient, f"unexpected event {event_id}; state={world.countries['DMG']}")
                        _receive_actual_event_and_wait(world, recipient, event_id)
                        counts[recipient["slug"]] += 1
                self.assertEqual(sum(counts.values()), 15, counts)
                self.assertEqual(counts, {arc["slug"]: 5 for arc in arcs}, counts)

    def test_real_presence_candidate_distinguishes_zero_from_absence(self):
        arc = next(a for a in self.catalog["arcs"] if a.get("slug") == "v03_dmg_two_land_titles")
        journal = arc["journals"][0]
        proof = next(
            item for item in arc["inline_delivery_adapter"]["branches"]
            if any(c["queue"] == "ywc_dmg_titles_emergency_notice" and c["mode"] == "presence"
                   for c in item["candidates"])
        )
        candidate_meta = next(c for c in proof["candidates"] if c["queue"] == "ywc_dmg_titles_emergency_notice")
        candidate_id = 0
        found_id = None
        for current_arc in self.catalog["arcs"]:
            if current_arc.get("era") != "foundation":
                continue
            for current_proof in current_arc["inline_delivery_adapter"]["branches"]:
                for current_candidate in current_proof["candidates"]:
                    candidate_id += 1
                    if (current_arc["slug"] == arc["slug"] and current_proof == proof
                            and current_candidate == candidate_meta):
                        found_id = candidate_id
        self.assertIsNotNone(found_id, proof)
        trigger_name = f"ywc_v03_dmg_inline_candidate_{found_id}"
        world = DmgInlineWorld()
        _admit_real_je(world, arc)
        world.countries["DMG"]["ywc_dmg_titles_emergency_notice"] = 0
        self.assertTrue(world.condition((trigger_name, "=", "yes"), "DMG"),
                        "Clausewitz has_variable must treat literal zero as present")
        world.countries["DMG"].pop("ywc_dmg_titles_emergency_notice")
        self.assertFalse(world.condition((trigger_name, "=", "yes"), "DMG"),
                         "actual candidate must fail when the presence queue is absent")

    def test_real_monthly_block_clock_sends_notice12_then_notice36_and_keeps_ordinary_queue(self):
        arc = next(a for a in self.ARCS if a["slug"] == "v03_dmg_two_land_titles")
        world = DmgInlineWorld()
        _admit_real_je(world, arc)
        notice_deliveries = []
        for month in range(1, 43):
            world.advance_months(1)
            before = len(world.events)
            _pulse_real_je(world, arc)
            if len(world.events) == before:
                continue
            tag, event_id = world.events[-1]
            self.assertEqual(tag, "DMG")
            reservation = int(world.countries["DMG"]["ywc_v03_dmg_inline_reservation"])
            selected = self.CANDIDATES[reservation]
            if event_id == "ywc_dmg.1015":
                notice_deliveries.append((month, selected["queue"]["kind"]))
            _receive_actual_event_and_wait(world, arc, event_id)
        kinds = [kind for _, kind in notice_deliveries]
        self.assertIn("notice12", kinds, notice_deliveries)
        self.assertIn("notice36", kinds, notice_deliveries)
        first12 = next(month for month, kind in notice_deliveries if kind == "notice12")
        first36 = next(month for month, kind in notice_deliveries if kind == "notice36")
        self.assertLess(first12, first36, notice_deliveries)
        self.assertIn("ywc_dmg_titles_pending_event", world.countries["DMG"])

    def test_real_unselected_notice_snapshot_mutation_rejects_and_recovers(self):
        """Both naturally-created notices are snapshotted by a real dispatch.

        Change only the unselected 36-month marker after reserving the 12-month
        notice and before popup-trigger reevaluation. The failed gate must not
        run the event immediate; after expiry the next native pulse should
        capture current state and ACK only the selected marker.
        """
        arc = next(a for a in self.ARCS if a["slug"] == "v03_dmg_two_land_titles")
        event_id = "ywc_dmg.1015"
        event = _generated_event(event_id)
        queue12 = "ywc_dmg_titles_blocked_12_notice"
        queue36 = "ywc_dmg_titles_blocked_36_notice"

        for mutation, replacement in (("absent", None), ("present_zero", 0)):
            with self.subTest(mutation=mutation):
                world = DmgInlineWorld()
                _admit_real_je(world, arc)
                _pulse_real_je(world, arc)
                self.assertEqual(world.events[-1], ("DMG", "ywc_dmg.1010"))
                self.assertTrue(world.conditions(_nodes_field(_generated_event("ywc_dmg.1010"), "trigger"), "DMG"))
                _receive_actual_event_and_wait(world, arc, "ywc_dmg.1010")

                world.advance_months(36)
                before = len(world.events)
                _pulse_real_je(world, arc)
                self.assertEqual(world.events[before:], [("DMG", event_id)])
                state = world.countries["DMG"]
                self.assertIn(queue12, state)
                self.assertIn(queue36, state)
                reservation = int(state["ywc_v03_dmg_inline_reservation"])
                self.assertEqual(reservation, 14, "selected reservation must represent the 12-month notice")
                self.assertEqual(state[queue12], 1)
                self.assertEqual(state[queue36], 1)

                # Mutate only the unselected, already-present 36-month marker.
                if replacement is None:
                    state.pop(queue36)
                else:
                    state[queue36] = replacement
                mutated_presence = queue36 in state
                mutated_value = state.get(queue36)
                before_gate = copy.deepcopy(state)
                self.assertFalse(world.conditions(_nodes_field(event, "trigger"), "DMG"),
                                 f"reservation must reject changed unselected snapshot ({mutation})")
                self.assertEqual(state, before_gate, "trigger re-evaluation must not execute native effects")
                self.assertEqual(state[queue12], 1, "selected notice must remain untouched before immediate")
                self.assertEqual(queue36 in state, mutated_presence)
                self.assertEqual(state.get(queue36), mutated_value)
                # A rejected event never reaches immediate/ACK. Let the real
                # reservation expire, then let the source monthly pulse retry.
                world.advance_days(1)
                world.events.clear()
                _pulse_real_je(world, arc)
                self.assertEqual(world.events[-1], ("DMG", event_id))
                state = world.countries["DMG"]
                fresh_reservation = int(state["ywc_v03_dmg_inline_reservation"])
                self.assertEqual(fresh_reservation, 14)
                # The source monthly business logic can naturally recreate a
                # due 36-month notice before dispatch. Compare ACK against the
                # live state after that pulse, never against the earlier
                # deliberate mutation.
                current_presence = queue36 in state
                current_value = state.get(queue36)
                c14_prefix = "ywc_v03_dmg_inline_c14_titles_blocked_36_notice_"
                self.assertEqual(state.get(c14_prefix + "present"), 1 if current_presence else None)
                self.assertEqual(state.get(c14_prefix + "value"), current_value)
                self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"),
                                "fresh reservation should match current unselected marker")
                _receive_actual_event_and_wait(world, arc, event_id)
                state = world.countries["DMG"]
                self.assertNotIn(queue12, state, "valid retry ACK should consume selected 12-month marker")
                self.assertEqual(queue36 in state, current_presence,
                                 "valid retry ACK must preserve current unselected marker presence")
                self.assertEqual(state.get(queue36), current_value,
                                 "valid retry ACK must preserve current unselected marker value")

    def test_real_dispatch_rejects_arc_already_served_in_current_epoch(self):
        """A reservation cannot reopen after the arc acquires its served marker."""
        arc = next(a for a in self.ARCS if a["slug"] == "v03_dmg_two_land_titles")
        event = _generated_event("ywc_dmg.1015")
        world = DmgInlineWorld()
        _admit_real_je(world, arc)
        _pulse_real_je(world, arc)
        _receive_actual_event_and_wait(world, arc, "ywc_dmg.1010")
        world.advance_months(36)
        _pulse_real_je(world, arc)
        state = world.countries["DMG"]
        self.assertEqual(world.events[-1], ("DMG", "ywc_dmg.1015"))
        self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"))
        slot = next(i for i, item in enumerate(self.ARCS, 1) if item["slug"] == arc["slug"])
        served = f"ywc_v03_dmg_inline_served_{slot}"
        round_key = "ywc_v03_dmg_inline_round"
        state[served] = state[round_key]
        before = copy.deepcopy(state)
        self.assertFalse(world.conditions(_nodes_field(event, "trigger"), "DMG"),
                         "actual popup trigger must reject an arc already served this epoch")
        self.assertEqual(state, before, "rejected popup trigger must not run immediate effects")

    def test_expired_real_reservation_closes_gate_and_recovers_on_native_pulse(self):
        arc = next(a for a in self.ARCS if a["slug"] == "v03_dmg_common_subjects")
        event_id = "ywc_dmg.1000"

        expired = DmgInlineWorld()
        _admit_real_je(expired, arc)
        _pulse_real_je(expired, arc)
        self.assertEqual(expired.events[-1], ("DMG", event_id))
        event = _generated_event(event_id)
        self.assertTrue(expired.conditions(_nodes_field(event, "trigger"), "DMG"))
        expired.advance_days(1)
        self.assertFalse(expired.conditions(_nodes_field(event, "trigger"), "DMG"),
                         "expired reservation must close the actual event gate")
        self.assertEqual(expired.countries["DMG"].get("ywc_dmg_pending_event"), 1000)
        expired.events.clear()
        _pulse_real_je(expired, arc)
        self.assertEqual(expired.events[-1], ("DMG", event_id), "source queue must recover after expiry")
        self.assertTrue(expired.conditions(_nodes_field(event, "trigger"), "DMG"))
        _receive_actual_event_and_wait(expired, arc, event_id)

    def test_real_queue_replacement_revalidates_before_popup_and_recovers(self):
        arc = next(a for a in self.ARCS if a["slug"] == "v03_dmg_common_subjects")
        event = _generated_event("ywc_dmg.1000")
        world = DmgInlineWorld()
        _admit_real_je(world, arc)
        _pulse_real_je(world, arc)
        self.assertEqual(world.events[-1], ("DMG", "ywc_dmg.1000"))
        # Another authored effect changes the queue before the engine opens
        # the popup. The generated event trigger must be re-evaluated now.
        world.countries["DMG"]["ywc_dmg_pending_event"] = 1001
        self.assertFalse(world.conditions(_nodes_field(event, "trigger"), "DMG"),
                         "replaced candidate must fail the actual popup trigger")
        # Do not execute the immediate: rejected popups do not reach it.
        world.advance_days(1)
        world.events.clear()
        _pulse_real_je(world, arc)
        self.assertEqual(world.events[-1], ("DMG", "ywc_dmg.1001"),
                         "native pulse should reserve the replacement after expiry")
        replacement = _generated_event("ywc_dmg.1001")
        self.assertTrue(world.conditions(_nodes_field(replacement, "trigger"), "DMG"))
        _receive_actual_event_and_wait(world, arc, "ywc_dmg.1001", run_wait=False)

    def test_defensive_ack_probe_preserves_replaced_queue_after_stale_open_popup(self):
        """Force an already-open popup through an ACK after authored state changes.

        This models stale UI or other asynchronous interleaving. Normal game
        opening reevaluates the trigger first; the previous test covers that
        native path. This probe tests ACK defensiveness only.
        """
        arc = next(a for a in self.ARCS if a["slug"] == "v03_dmg_common_subjects")
        event_id = "ywc_dmg.1000"
        event = _generated_event(event_id)
        replaced = DmgInlineWorld()
        _admit_real_je(replaced, arc)
        _pulse_real_je(replaced, arc)
        self.assertEqual(replaced.events[-1], ("DMG", event_id))
        self.assertTrue(replaced.conditions(_nodes_field(event, "trigger"), "DMG"),
                        "the source popup must be genuinely eligible before mutation")
        # Model another authored effect replacing the queue after the game has
        # opened the actual popup but before its immediate ACK executes.
        replaced.countries["DMG"]["ywc_dmg_pending_event"] = 1001
        replaced.execute(_nodes_field(event, "immediate"), "DMG")
        self.assertEqual(replaced.countries["DMG"].get("ywc_dmg_pending_event"), 1001,
                         "stale popup ACK must preserve the replacement queue")

    def test_popup_ack_after_real_je_phase_completion_keeps_its_queue(self):
        arc = next(a for a in self.ARCS if a["slug"] == "v03_dmg_common_subjects")
        journal_id = arc["journals"][0]["id"]
        world = DmgInlineWorld()
        _admit_real_je(world, arc)
        _pulse_real_je(world, arc)
        event = _generated_event("ywc_dmg.1000")
        self.assertTrue(world.conditions(_nodes_field(event, "trigger"), "DMG"))
        # The actual popup was eligible when opened. The JE then completes
        # before its immediate acknowledgement runs.
        world.journals = [entry for entry in world.journals
                          if dict((k, v) for k, _, v in entry[1]).get("type") != journal_id]
        world.countries["DMG"].pop("ywc_v03_dmg_live_public_qualification", None)
        world.execute(_nodes_field(event, "immediate"), "DMG")
        self.assertEqual(world.countries["DMG"].get("ywc_dmg_pending_event"), 1000,
                         "completed-phase ACK must leave authored queue available to its owner")
        self.assertNotIn("ywc_v03_dmg_inline_served_1", world.countries["DMG"])

    def test_source_extraction_does_not_promote_negated_or_unrelated_queues(self):
        for arc in self.catalog["arcs"]:
            if arc.get("era") != "foundation":
                continue
            for journal in arc["journals"]:
                for branch in source_binding(journal["id"], journal["script"])["branches"]:
                    candidates = queue_candidates(branch["limit_source"])
                    self.assertTrue(candidates, (journal["id"], branch["event"]))
                    self.assertTrue(all(c["queue"].startswith("ywc_dmg_") for c in candidates))
                    self.assertTrue(all(c["kind"] in {"normal", "notice12", "notice36"} for c in candidates))
        # A presence-valued marker set to literal zero is still present in
        # Clausewitz. The parser must preserve that distinction as metadata.
        fixture = "limit = { has_variable = ywc_dmg_titles_emergency_notice }"
        self.assertEqual(queue_candidates(fixture), [{
            "queue": "ywc_dmg_titles_emergency_notice", "mode": "presence", "kind": "notice12",
        }])
        # `NOT`-guarded variables are conditions excluding delivery; they are
        # not positive queue evidence and cannot become candidates.
        source = "{ on_monthly_pulse = { effect = { if = { limit = { NOT = { has_variable = ywc_dmg_titles_emergency_notice } } trigger_event = { id = ywc_dmg.1015 } } } } }"
        extracted = source_binding("negative", source)["branches"][0]
        self.assertEqual(queue_candidates(extracted["limit_source"]), [])

    def test_catalog_rejects_source_drift_without_weakening_live_binding(self):
        altered = copy.deepcopy(self.catalog)
        arc = next(a for a in altered["arcs"] if a.get("era") == "foundation")
        arc["journals"][0]["script"] += " "
        with self.assertRaisesRegex(ValueError, "source JE/goal/fail drift"):
            validate_inline_catalog(altered)


if __name__ == "__main__":
    unittest.main()
