"""Permanent actual-source provenance contract for MGL inline transport.

The positive path starts with the real MGL history, legacy terminal, country
initializer and all three authored root admissions.  Reservation and receipt
fields are observed only after the source pulse and full native immediate run.
"""
from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from tests import test_v03_mgl_inline_actual_source as actual
from tests import test_v03_mgl_inline_adapter as binding
from tests import test_v03_mgl_actual_source as source
from tests.clausewitz_harness import parse
from tools.v03_inline_delivery_adapter import _queue_snapshot_name

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/content/v03/countries/mgl.json"
PREFIX = "ywc_v03_mgl_inline"
TAG = "MGL"
COOLDOWN = "ywc_v03_major_event_cooldown"
ARC_ORDER = tuple(arc["slug"] for arc in source.MGL_ARCS)


def _field(nodes, key, default=None):
    return next((value for name, _, value in nodes if name == key), default)


def _catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _event(world, event_id):
    try:
        return world.event_defs[event_id]
    except KeyError as exc:
        raise AssertionError(("missing-native-mgl-event", event_id)) from exc


def _all_rows():
    # The committed catalogue is intentionally pre-adapter. Expected rows come
    # from the formal JE scripts and source binder, not the R3 JSON artifact.
    source_catalog = binding._v2_catalog_from_formal_mgl_source()
    result = []
    for arc in source_catalog["arcs"]:
        adapter = arc.get("inline_delivery_adapter")
        if not isinstance(adapter, dict):
            continue
        for branch in adapter.get("branches", ()):
            candidates = branch.get("candidates", ())
            if len(candidates) != 1:
                raise AssertionError(("candidate-cardinality", arc["slug"], branch, candidates))
            result.append({"arc": arc, "branch": branch, "candidate": candidates[0]})
    return result


def _native_id(event_id):
    return int(event_id.rsplit(".", 1)[1])


def _canonical_candidate_id(reservation):
    """Return the exact positive integer ID used in authored helper names."""
    if (isinstance(reservation, bool) or not isinstance(reservation, (int, float))
            or not math.isfinite(reservation) or reservation <= 0
            or int(reservation) != reservation):
        raise ValueError(("invalid_candidate_id", reservation))
    return int(reservation)


def _selected_row(event_id, reservation):
    rows = _all_rows()
    try:
        candidate_id = _canonical_candidate_id(reservation)
    except ValueError:
        return None
    if candidate_id > len(rows):
        return None
    row = rows[candidate_id - 1]
    return row if row["branch"]["event"] == event_id else None


def _actual_unconsumed_popup(testcase, months=12):
    """Pulse real active MGL JEs until their real sender emits an event.

    Stop between native trigger_event and native event immediate so tests can
    inspect the reservation while the selected source queue is still present.
    """
    actual.assert_inline_supported(testcase)
    world, evidence = actual.actual_mgl_inline_world()
    testcase.assertEqual(evidence["counts"], {"active": 3, "visible": 3})
    testcase.assertEqual(len(evidence["legacy_trace"]), 6)
    testcase.assertEqual(len(evidence["root_admissions"]), 3)
    for _ in range(months):
        source._refresh_actual_journal_lifecycle(world)
        active = list(world.active_journals[TAG])
        testcase.assertTrue(active, "all three source roots should remain live before delivery")
        world.advance_months(1)
        emitted = []
        for journal_id in active:
            journal = world.journal_defs[journal_id]
            pulse = _field(_field(journal, "on_monthly_pulse", []), "effect", [])
            before = len(world.events)
            world.execute(pulse, TAG)
            emitted.extend(world.events[before:])
            del world.events[before:]
            if emitted:
                # Do not let a later JE pulse again until the event body has
                # run the authored common cooldown mark.
                world._mgl_inline_unpulsed_journals = active[active.index(journal_id) + 1:]
                world._mgl_inline_emitting_journal = journal_id
                break
        if emitted:
            testcase.assertEqual(len(emitted), 1, "shared 90-day gate permits one natural popup")
            tag, event_id = emitted[0]
            testcase.assertEqual(tag, TAG)
            event = _event(world, event_id)
            testcase.assertTrue(world.conditions(_field(event, "trigger", []), TAG),
                                "the full authored event trigger must still hold")
            state = world.countries[TAG]
            reservation = state.get(PREFIX + "_reservation")
            row = _selected_row(event_id, reservation)
            testcase.assertIsNotNone(row, "real sender must map to its exact source candidate")
            reservation = _canonical_candidate_id(reservation)
            candidate = row["candidate"]
            queue = candidate["queue"]
            testcase.assertIn(queue, state)
            testcase.assertEqual(state[queue], candidate["value"])
            epoch = state.get(PREFIX + "_reservation_epoch")
            testcase.assertIsInstance(epoch, (int, float))
            testcase.assertNotIsInstance(epoch, bool)
            testcase.assertGreater(epoch, 0)
            timer = state.get(PREFIX + "_timer")
            testcase.assertIsInstance(timer, (int, float))
            testcase.assertNotIsInstance(timer, bool)
            testcase.assertGreater(timer, 0)
            testcase.assertGreater(world.days_until_expiry[TAG][PREFIX + "_timer"], 0)
            testcase.assertTrue(world.has_journal_entry(row["branch"]["journal"], TAG))
            testcase.assertTrue(world.condition((f"{PREFIX}_dispatch_{reservation}", "=", "yes"), TAG),
                                "an authentic candidate and live source phase pass prebody dispatch")
            phase = next(p for p in row["arc"]["inline_delivery_adapter"]["live_phases"]
                         if p["journal"] == row["branch"]["journal"])
            testcase.assertEqual(state.get(phase["live_witness"]), 1)
            if queue.endswith("_pending_event"):
                stem = queue.removesuffix("_pending_event")
                siblings = (stem + "_blocked_12_notice_event", stem + "_blocked_36_notice_event")
            elif queue.endswith("_blocked_12_notice_event"):
                stem = queue.removesuffix("_blocked_12_notice_event")
                siblings = (stem + "_pending_event", stem + "_blocked_36_notice_event")
            elif queue.endswith("_blocked_36_notice_event"):
                stem = queue.removesuffix("_blocked_36_notice_event")
                siblings = (stem + "_pending_event", stem + "_blocked_12_notice_event")
            else:
                testcase.fail(("unrecognized-source-queue", queue))
            for tracked in (queue, *siblings):
                present = _queue_snapshot_name(int(reservation), tracked, "present", PREFIX)
                value = _queue_snapshot_name(int(reservation), tracked, "value", PREFIX)
                testcase.assertIn(present, state)
                testcase.assertIn(value, state)
                testcase.assertEqual(state[present], int(tracked in state))
                testcase.assertEqual(state[value], state.get(tracked, 0))
            return world, evidence, event_id, row, reservation, epoch, queue
    testcase.fail(("no-natural-source-popup-within-months", months))


def _natural_blocked_notice(testcase, notice_kind, months):
    """Reach a native 12/36-month blocked notice (365/1095 authored days) through ordinary world facts."""
    actual.assert_inline_supported(testcase)
    world, evidence = actual.actual_mgl_inline_world()
    testcase.assertEqual(evidence["counts"], {"active": 3, "visible": 3})
    testcase.assertEqual(len(evidence["legacy_trace"]), 6)
    testcase.assertEqual(len(evidence["root_admissions"]), 3)
    state = world.countries[TAG]
    # Ordinary market conditions deteriorate after authentic history/admission;
    # this does not inject any source queue, paid flag, due clock or adapter data.
    state["states"][0]["market_access"] = 0
    state["market"]["tea"]["exports"] = 0
    state["market"]["wool"]["exports"] = 0
    state["market"]["grain"]["pricier"] = 0.05
    suffix = f"_blocked_{notice_kind}_notice_event"
    for _ in range(months):
        source._refresh_actual_journal_lifecycle(world)
        active = list(world.active_journals[TAG])
        testcase.assertTrue(active)
        world.advance_months(1)
        emitted = []
        emitted_by = None
        for journal_id in active:
            pulse = _field(_field(world.journal_defs[journal_id], "on_monthly_pulse", []),
                           "effect", [])
            before = len(world.events)
            world.execute(pulse, TAG)
            emitted.extend(world.events[before:])
            del world.events[before:]
            if emitted:
                emitted_by = journal_id
                break
        if not emitted:
            continue
        testcase.assertEqual(len(emitted), 1)
        tag, event_id = emitted[0]
        testcase.assertEqual(tag, TAG)
        state = world.countries[TAG]
        reservation = state.get(PREFIX + "_reservation")
        row = _selected_row(event_id, reservation)
        testcase.assertIsNotNone(row, (event_id, reservation))
        reservation = _canonical_candidate_id(reservation)
        queue = row["candidate"]["queue"]
        if queue.endswith(suffix):
            testcase.assertEqual(queue.endswith("_blocked_12_notice_event"), notice_kind == "12")
            testcase.assertTrue(world.conditions(_field(_event(world, event_id), "trigger", []), TAG))
            testcase.assertEqual(state[queue], row["candidate"]["value"])
            testcase.assertGreater(world.days_until_expiry[TAG][PREFIX + "_timer"], 0)
            testcase.assertTrue(world.condition((f"{PREFIX}_dispatch_{reservation}", "=", "yes"), TAG),
                                "pretrigger last-delivered bookkeeping cannot revoke a selected live notice")
            return world, evidence, event_id, row, int(reservation), state[PREFIX + "_reservation_epoch"], queue

        # Complete each incidental source popup and take its authored defer;
        # the native shared mark then blocks all later JEs in that same month.
        event = _event(world, event_id)
        world.execute(_field(event, "immediate", []), TAG)
        actual.choose_inline_option(world, event_id, "defer")
        for journal_id in active[active.index(emitted_by) + 1:]:
            pulse = _field(_field(world.journal_defs[journal_id], "on_monthly_pulse", []),
                           "effect", [])
            before = len(world.events)
            world.execute(pulse, TAG)
            testcase.assertEqual(world.events[before:], [],
                                 "a completed event suppresses later JE senders in the shared window")
    testcase.fail(("no-natural-blocked-notice", notice_kind, months, state))


def _same_event_rows(event_id):
    return [row for row in _all_rows() if row["branch"]["event"] == event_id]


def _outside_adapter(state):
    """Retain every source-owned/shared/fact key and its presence exactly."""
    return {key: copy.deepcopy(value) for key, value in state.items()
            if not key.startswith(PREFIX + "_")}


class MglInlineCandidateIdControls(unittest.TestCase):
    def test_candidate_id_canonicalization_without_inline_feature(self):
        for raw in (4, 4.0):
            with self.subTest(raw=raw):
                candidate_id = _canonical_candidate_id(raw)
                self.assertIs(type(candidate_id), int)
                self.assertEqual(candidate_id, 4)
                self.assertEqual(f"{PREFIX}_dispatch_{candidate_id}", PREFIX + "_dispatch_4")
                self.assertEqual(f"{PREFIX}_ack_{candidate_id}", PREFIX + "_ack_4")
                self.assertEqual(f"{PREFIX}_body_completed_{candidate_id}", PREFIX + "_body_completed_4")
        for raw in (0, -1, 4.5, True, False, float("nan"), float("inf"), -float("inf"), None, "4"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    _canonical_candidate_id(raw)


class MglInlineProvenanceRegression(unittest.TestCase):
    def test_complete_native_immediate_precedes_receipt_and_ack(self):
        """No callback or early ACK can stand in for full authored event execution."""
        world, evidence, event_id, row, reservation, epoch, queue = _actual_unconsumed_popup(self)
        self.assertEqual(len(evidence["root_admissions"]), 3)
        event = _event(world, event_id)
        immediate = _field(event, "immediate", [])
        self.assertTrue(immediate, "real native event immediate must be nonempty")
        state = world.countries[TAG]
        catalog_event = next(item for item in row["arc"]["events"] if item["id"] == event_id)
        native_ast = parse("immediate = " + catalog_event["immediate"])[0][2]
        wrapper_ifs = [value for key, _, value in immediate if key == "if"]
        self.assertEqual(len(immediate), 1, "production builder emits one guarded outer immediate")
        self.assertEqual(len(wrapper_ifs), 1)
        wrapper_body = wrapper_ifs[0]
        limit_positions = [index for index, node in enumerate(wrapper_body) if node[0] == "limit"]
        self.assertEqual(len(limit_positions), 1)
        generated_body = wrapper_body[limit_positions[0] + 1:]
        self.assertEqual(generated_body[:len(native_ast)], native_ast,
                         "the complete authored immediate is the generated wrapper body prefix")
        native_keys = [key for key, _, _ in native_ast]
        self.assertEqual(native_keys.count("ywc_v03_mark_major_delivered"), 1)
        self.assertIn("ywc_v03_mark_major_delivered", native_keys)
        observation_for_event = {
            "ywc_mng.1005": "ywc_mgl_roads_observation_open",
            "ywc_mng.1015": "ywc_mgl_debt_observation_open",
            "ywc_mng.1025": "ywc_mgl_grain_observation_open",
        }.get(event_id)
        if observation_for_event:
            self.assertEqual(native_keys, ["ywc_v03_mark_major_delivered", "set_variable"])
            self.assertEqual(_field(native_ast[1][2], "name"), observation_for_event)
        boundaries = []
        original_run = world.run
        ack_name = f"{PREFIX}_ack_{reservation}"
        def observe(name, tag=TAG):
            if name == ack_name and tag == TAG:
                boundaries.append(copy.deepcopy(state))
            return original_run(name, tag)
        world.run = observe
        world.execute(immediate, TAG)
        self.assertEqual(len(boundaries), 1,
                         "one authentic full-body path must reach its exact candidate ACK once")
        boundary = boundaries[0]
        self.assertEqual(boundary.get(COOLDOWN), 1)
        self.assertEqual(boundary.get(f"{PREFIX}_body_completed_{reservation}"), 1)
        self.assertEqual(boundary.get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
        if observation_for_event:
            self.assertEqual(boundary.get(observation_for_event), 1,
                             "observation-open is a post-cooldown native body write")
        self.assertEqual(boundary.get(queue), row["candidate"]["value"])
        self.assertEqual(boundary.get(PREFIX + "_reservation"), reservation)
        self.assertIn(PREFIX + "_timer", boundary)
        self.assertEqual(boundary.get(f"{PREFIX}_callback_{reservation}"), 1,
                         "the inline proof must be minted only after the native body")
        self.assertEqual(boundary.get(f"{PREFIX}_callback_candidate_{reservation}"), reservation)
        self.assertEqual(boundary.get(f"{PREFIX}_callback_epoch_{reservation}"), epoch)
        self.assertEqual(boundary.get(f"{PREFIX}_callback_queue_{reservation}"),
                         row["candidate"]["value"])
        self.assertEqual(state.get(COOLDOWN), 1)
        # The later authored JEs in the same calendar pulse are allowed to run
        # only after this body has marked the shared 90-day cooldown.
        for journal_id in world._mgl_inline_unpulsed_journals:
            pulse = _field(_field(world.journal_defs[journal_id], "on_monthly_pulse", []),
                           "effect", [])
            before = len(world.events)
            world.execute(pulse, TAG)
            self.assertEqual(world.events[before:], [],
                             "one complete body must silence later JEs in this shared window")

    def test_callback_or_ack_before_body_cannot_mint_proof_or_consume_queue(self):
        """Calling public adapter helpers alone cannot create delivery evidence."""
        world, _evidence, event_id, row, reservation, epoch, queue = _actual_unconsumed_popup(self)
        state = world.countries[TAG]
        native_before = _outside_adapter(state)
        private_before = copy.deepcopy(state)
        # A callback invocation is permitted only after whole-body completion.
        world.run(f"{PREFIX}_callback_{reservation}", TAG)
        self.assertEqual(state, private_before,
                         "public callback before body cannot mint callback proof or receipt")
        world.run(f"{PREFIX}_ack_{reservation}", TAG)
        self.assertEqual(state, private_before,
                         "direct early ACK cannot consume candidate or mark a round served")
        self.assertEqual(_outside_adapter(state), native_before)
        self.assertEqual(state.get(PREFIX + "_reservation"), reservation)
        self.assertEqual(state.get(PREFIX + "_reservation_epoch"), epoch)
        self.assertEqual(state.get(queue), row["candidate"]["value"])
        trigger = _field(_event(world, event_id), "trigger", [])
        self.assertTrue(world.conditions(trigger, TAG),
                        "an early protocol call does not alter the authored dispatch gate")

    def test_ninety_day_natural_gate_and_selected_queue_kind_are_source_bound(self):
        """Candidate kind comes from the actual queue branch, not shared event ID."""
        world, evidence, event_id, row, _reservation, _epoch, queue = _actual_unconsumed_popup(self)
        self.assertEqual(row["branch"]["event"], event_id)
        self.assertEqual(row["candidate"]["queue"], queue)
        expected_kind = "normal" if queue.endswith("_pending_event") else "notice"
        self.assertEqual(row["candidate"]["kind"], expected_kind)
        self.assertEqual(row["candidate"]["kind"], expected_kind)

    def test_real_paid_story_reaches_all_three_observation_body_ack_boundaries(self):
        """All 1005/1015/1025 bodies run through real paid routes before inline ACK."""
        actual.assert_inline_supported(self)
        from unittest.mock import patch
        from tests import test_v03_mgl_inline_native_story as story

        captured = {}
        delayed = set()
        def instrumented_factory(order=None, ordinary_facts=None):
            world, evidence = actual.actual_mgl_inline_world(order, ordinary_facts)
            original_run = world.run
            captured["world"] = world
            captured["evidence"] = evidence
            captured["acks"] = []
            def capture_ack(name, tag=TAG):
                if name.startswith(PREFIX + "_ack_") and tag == TAG:
                    reservation = world.countries[TAG].get(PREFIX + "_reservation")
                    reservation = _canonical_candidate_id(reservation)
                    rows = _all_rows()
                    self.assertLessEqual(reservation, len(rows))
                    row = rows[reservation - 1]
                    epoch = world.countries[TAG].get(PREFIX + "_reservation_epoch")
                    captured["acks"].append((copy.deepcopy(world.countries[TAG]), reservation, epoch, row, name))
                return original_run(name, tag)
            world.run = capture_ack
            return world, evidence

        with patch.object(story, "actual_mgl_inline_world", instrumented_factory):
            original_choose = story.choose_inline_option
            def choose_with_ordinary_fact_transition(world, event_id, suffix):
                result = original_choose(world, event_id, suffix)
                state = world.countries[TAG]
                number = int(event_id.rsplit(".", 1)[1])
                arc = story._event_arc(event_id)[0]
                # Lose only this arc's ordinary qualification after the actual
                # second-reading choice. The already-open native observation
                # event remains eligible for fair shared service.
                if number in (1004, 1014, 1024) and arc not in delayed:
                    if arc == story.ARCS[0]:
                        state["states"][0]["market_access"] = 0.60
                    elif arc == story.ARCS[1]:
                        state["market"]["wool"]["exports"] = 0
                    else:
                        state["market"]["grain"]["pricier"] = 0.30
                    delayed.add(arc)
                # Restore the same ordinary fact only after the genuine
                # observation option has executed its complete native body.
                if number in (1005, 1015, 1025) and arc in delayed:
                    if arc == story.ARCS[0]:
                        state["states"][0]["market_access"] = 0.80
                    elif arc == story.ARCS[1]:
                        state["market"]["wool"]["exports"] = 2
                    else:
                        state["market"]["grain"]["pricier"] = 0.10
                return result
            with patch.object(story, "choose_inline_option", choose_with_ordinary_fact_transition):
                world, evidence, ledger, notices, unknown, paid = story._drive_route(story.ARCS, 1, None)
        self.assertEqual(len(evidence["root_admissions"]), 3)
        self.assertEqual(paid, {slug: 200 for slug in story.ARCS})
        self.assertEqual(notices, [])
        self.assertEqual(unknown, [])
        observation_ids = ("ywc_mng.1005", "ywc_mng.1015", "ywc_mng.1025")
        self.assertTrue(set(observation_ids).issubset({row["event"] for row in ledger}))
        observation_boundaries = {}
        for state, reservation, epoch, row, name in captured["acks"]:
            self.assertIsNotNone(row, (reservation, name))
            event_id = row["branch"]["event"]
            if event_id in observation_ids:
                self.assertNotIn(event_id, observation_boundaries,
                                 "each observation body must reach its exact ACK boundary once")
                observation_boundaries[event_id] = (state, reservation, epoch, row, name)
        self.assertEqual(set(observation_boundaries), set(observation_ids))
        self.assertEqual(delayed, set(story.ARCS))
        for event_id, open_variable in {
            "ywc_mng.1005": "ywc_mgl_roads_observation_open",
            "ywc_mng.1015": "ywc_mgl_debt_observation_open",
            "ywc_mng.1025": "ywc_mgl_grain_observation_open",
        }.items():
            with self.subTest(event=event_id):
                state, reservation, epoch, row, name = observation_boundaries[event_id]
                self.assertIsNotNone(row)
                self.assertIsInstance(reservation, (int, float))
                self.assertNotIsInstance(reservation, bool)
                self.assertEqual(int(reservation), reservation)
                self.assertGreater(reservation, 0)
                self.assertLessEqual(reservation, len(_all_rows()))
                self.assertEqual(row, _all_rows()[int(reservation) - 1])
                self.assertEqual(row["branch"]["event"], event_id)
                self.assertEqual(name, f"{PREFIX}_ack_{reservation}")
                self.assertIsInstance(epoch, (int, float))
                self.assertNotIsInstance(epoch, bool)
                self.assertGreater(epoch, 0)
                self.assertEqual(state.get(f"{PREFIX}_body_completed_{reservation}"), 1)
                self.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
                self.assertEqual(state.get(f"{PREFIX}_callback_{reservation}"), 1)
                self.assertEqual(state.get(f"{PREFIX}_callback_candidate_{reservation}"), reservation)
                self.assertEqual(state.get(f"{PREFIX}_callback_epoch_{reservation}"), epoch)
                self.assertEqual(state.get(f"{PREFIX}_callback_queue_{reservation}"),
                                 row["candidate"]["value"])
                self.assertEqual(state.get(COOLDOWN), 1)
                self.assertEqual(state.get(open_variable), 1)
        self.assertEqual(len(world.completed_journals), 7)
        story._assert_terminal(self, world, 1)

    def test_real_notice12_and_notice36_marker_is_not_body_proof(self):
        """Pretrigger last-delivered writes do not replace the real notice body or ACK."""
        for notice_kind, max_months in (("12", 18), ("36", 42)):
            with self.subTest(notice=notice_kind):
                world, evidence, event_id, row, reservation, epoch, queue = _natural_blocked_notice(
                    self, notice_kind, max_months)
                self.assertEqual(len(evidence["root_admissions"]), 3)
                self.assertTrue(queue.endswith(f"_blocked_{notice_kind}_notice_event"))
                self.assertEqual(row["candidate"]["kind"], "notice")
                same_id = _same_event_rows(event_id)
                self.assertIn("notice", {item["candidate"]["kind"] for item in same_id})
                self.assertIn("normal", {item["candidate"]["kind"] for item in same_id},
                              "shared 1006/1007 event identities retain a separate normal queue branch")
                event = _event(world, event_id)
                immediate = _field(event, "immediate", [])
                catalog_event = next(item for item in row["arc"]["events"] if item["id"] == event_id)
                native_ast = parse("immediate = " + catalog_event["immediate"])[0][2]
                self.assertEqual(native_ast, [("ywc_v03_mark_major_delivered", "=", "yes")])

                # The JE writes last_delivered before trigger_event. It is source
                # priority bookkeeping only; no generated body/callback evidence
                # exists at this point, even though native queue removal is pending.
                marker = queue.split("_blocked_", 1)[0] + "_blocked_notice_last_delivered"
                state = world.countries[TAG]
                self.assertEqual(state.get(marker), 1 if notice_kind == "12" else 2)
                self.assertEqual(state.get(queue), row["candidate"]["value"])
                proof_fields = (f"{PREFIX}_callback_{reservation}",
                                f"{PREFIX}_callback_candidate_{reservation}",
                                f"{PREFIX}_callback_epoch_{reservation}",
                                f"{PREFIX}_callback_queue_{reservation}")
                self.assertTrue(all(name not in state for name in proof_fields))
                before = copy.deepcopy(state)
                world.run(f"{PREFIX}_callback_{reservation}", TAG)
                world.run(f"{PREFIX}_ack_{reservation}", TAG)
                self.assertEqual(state, before,
                                 "the pretrigger marker cannot authorize callback or early ACK")
                self.assertEqual(state.get(marker), 1 if notice_kind == "12" else 2)

                boundaries = []
                original_run = world.run
                def observe_ack(name, tag=TAG):
                    if name == f"{PREFIX}_ack_{reservation}" and tag == TAG:
                        boundaries.append(copy.deepcopy(state))
                    return original_run(name, tag)
                world.run = observe_ack
                world.execute(immediate, TAG)
                self.assertEqual(len(boundaries), 1,
                                 "the genuine complete notice immediate must reach one ACK")
                self.assertEqual(boundaries[0].get(COOLDOWN), 1)
                self.assertEqual(boundaries[0].get(marker), 1 if notice_kind == "12" else 2)
                self.assertEqual(boundaries[0].get(f"{PREFIX}_callback_{reservation}"), 1)


if __name__ == "__main__":
    unittest.main()
