"""Permanent source-driven regressions for LAN inline provenance and cleanup.

Positive cases use the frozen real-history fixture in
``test_v03_lan_actual_fairness``.  Adversarial state changes in this module are
limited to explicit boundary faults; they are not presented as engine history.
"""
import copy
import json
import unittest
from pathlib import Path

from tests.clausewitz_harness import parse
from tests.test_v03_lan_actual_fairness import (
    ARC_ORDER,
    _fresh_three_arcs,
    _fields,
)

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "ywc_v03_lan_inline"
CATALOG = ROOT / "data/content/v03/countries/lan.json"


def _field(nodes, key, default=None):
    return next((value for name, _, value in nodes if name == key), default)


def _rows(catalog):
    result = []
    for arc in catalog["arcs"]:
        adapter = arc.get("inline_delivery_adapter")
        if not isinstance(adapter, dict):
            raise AssertionError(f"{arc['slug']} has no formal inline adapter")
        for branch in adapter.get("branches", []):
            candidates = branch.get("candidates", [])
            if len(candidates) != 1:
                raise AssertionError((arc["slug"], branch.get("event"), candidates))
            result.append({"arc": arc, "branch": branch, "candidate": candidates[0]})
    return result


def _integer_value(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and float(value).is_integer())


def _reservation_row(world, rows, event_id):
    reservation = world.countries["LAN"].get(PREFIX + "_reservation")
    if not _integer_value(reservation):
        return None
    reservation = int(reservation)
    if not 1 <= reservation <= len(rows):
        return None
    row = rows[reservation - 1]
    return row if row["branch"]["event"] == event_id else None


def _source_option(world, event, suffix):
    options = [body for key, _, body in event if key == "option"]
    return next((option for option in options
                 if (_field(option, "name") or "").endswith("." + suffix)
                 and (not _field(option, "trigger")
                      or world.conditions(_field(option, "trigger"), "LAN"))), None)


def _execute_option(world, option):
    ignored = {"name", "ai_chance", "trigger", "default_option", "custom_tooltip"}
    world.execute([node for node in option if node[0] not in ignored], "LAN")


def _candidate_kind(candidate):
    if candidate["kind"] in ("notice12", "notice36"):
        return candidate["kind"]
    if candidate["kind"] == "notice" and candidate["value"] in (12, 36):
        return f"notice{candidate['value']}"
    return candidate["kind"]


def _notice_short(slug):
    return {"v03_lan_mine_accounts": "mine",
            "v03_lan_river_compacts": "river",
            "v03_lan_work_accident_fund": "fund"}[slug]


def _start_real_popup(world, native, slug, order=ARC_ORDER, desired_kind="normal", max_months=18,
                      reserve_boundary=None):
    """Pulse every admitted real JE in calendar order, deferring other popups."""
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = _rows(catalog)
    original_run = world.run
    observed_reserve_ids = set()

    def observe_reserve(name, tag="LAN"):
        if reserve_boundary is not None and tag == "LAN" and name.startswith(PREFIX + "_reserve_"):
            try:
                reservation_number = int(name.rsplit("_", 1)[1])
            except ValueError:
                reservation_number = -1
            bound_row = rows[reservation_number - 1] if 1 <= reservation_number <= len(rows) else None
            if (bound_row is not None and bound_row["branch"]["event"]
                    == next((item["branch"]["event"] for item in rows
                             if item["arc"]["slug"] == slug
                             and _candidate_kind(item["candidate"]) == desired_kind), None)
                    and name not in observed_reserve_ids):
                observed_reserve_ids.add(name)
                reserve_boundary(world, bound_row, name)
        return original_run(name, tag)

    if reserve_boundary is not None:
        world.run = observe_reserve
    for _month in range(max_months):
        world.advance_days(30)
        for source_slug in order:
            effect = _field(_field(native[source_slug], "on_monthly_pulse"), "effect")
            before = len(world.events)
            world.execute(effect, "LAN")
            emitted_count = len(world.events) - before
            for _ in range(emitted_count):
                tag, event_id = world.events.pop(before)
                if tag != "LAN":
                    raise AssertionError(("unexpected_popup_recipient", tag, event_id))
                event = _event(world, event_id)
                if not world.conditions(_field(event, "trigger", []), "LAN"):
                    continue  # source event item is not an eligible popup while cooldown is active
                row = _reservation_row(world, rows, event_id)
                if row is None:
                    raise AssertionError(("eligible_real_popup_without_bound_candidate", event_id,
                                          world.countries["LAN"]))
                actual_kind = _candidate_kind(row["candidate"])
                if row["arc"]["slug"] == slug and actual_kind == desired_kind:
                    world.run = original_run
                    if reserve_boundary is not None and not observed_reserve_ids:
                        raise AssertionError(("requested_real_reserve_boundary_not_observed", slug,
                                              desired_kind, world.countries["LAN"]))
                    return event_id, row

                # Every other eligible source popup runs its complete body and
                # the actual legal defer option before the driver advances.
                world.execute(_field(event, "immediate"), "LAN")
                defer = _source_option(world, event, "defer")
                if defer is not None:
                    _execute_option(world, defer)
                    continue
                if actual_kind == "notice12":
                    short = _notice_short(row["arc"]["slug"])
                    acknowledge = _source_option(world, event, f"reconsider_{short}_12")
                    if acknowledge is not None:
                        _execute_option(world, acknowledge)
                        continue
                raise AssertionError(("non_target_popup_has_no_legal_defer", event_id,
                                      actual_kind, row["arc"]["slug"]))
    raise AssertionError(("no_source_popup_of_requested_kind", slug, desired_kind,
                          world.countries["LAN"]))


def _notice_world(slug):
    world, _, native, _ = _fresh_three_arcs()
    state = world.countries["LAN"]
    state.update({
        "gold_reserves": 10000,
        "yearly_gross_income": 52000,
        "test_laws": {"law_commercialized_agriculture", "law_poor_laws"},
        "test_buildings": [
            {"type": "building_government_administration", "level": 2, "occupancy": 1.0,
             "shortage": False, "groups": []},
            {"type": "building_mine", "level": 3, "occupancy": 1.0,
             "shortage": False, "groups": ["bg_mining"]},
            {"type": "building_port", "level": 1, "occupancy": 1.0,
             "shortage": False, "groups": []},
        ],
    })
    order = (slug,) + tuple(item for item in ARC_ORDER if item != slug)
    event_id, _ = _start_real_popup(world, native, slug, order=order)
    event = _event(world, event_id)
    world.execute(_field(event, "immediate"), "LAN")
    paid_choice = {"v03_lan_mine_accounts": "public_audit",
                   "v03_lan_river_compacts": "compensate",
                   "v03_lan_work_accident_fund": "mutual_fund"}[slug]
    option = _source_option(world, event, paid_choice)
    if option is None:
        raise AssertionError(("required_source_paid_option_not_legal", event_id, paid_choice, state))
    _execute_option(world, option)
    state["in_default"] = True  # controlled engine-owned blocking fact, not a LAN protocol field
    return world, native, order


def _event(world, event_id):
    try:
        return world.event_defs[event_id]
    except KeyError as exc:
        raise AssertionError(f"formal event source is missing {event_id}") from exc


def _reservation(world, row, event_id):
    state = world.countries["LAN"]
    reservation = state.get(PREFIX + "_reservation")
    if not _integer_value(reservation) or reservation <= 0:
        raise AssertionError(("missing_real_reservation", event_id, reservation, state))
    reservation = int(reservation)
    selected = row["candidate"]
    queue = selected["queue"]
    epoch = state.get(PREFIX + "_reservation_epoch")
    if not _integer_value(epoch) or epoch <= 0:
        raise AssertionError(("missing_positive_global_epoch", epoch, state))
    if state.get(f"{PREFIX}_candidate_epoch_{reservation}") != epoch:
        raise AssertionError(("candidate_epoch_not_bound", reservation, epoch, state))
    if queue not in state or state[queue] != selected["value"]:
        raise AssertionError(("source_queue_not_snapshot", queue, selected, state))
    proof_fields = (f"{PREFIX}_callback_{reservation}",
                    f"{PREFIX}_callback_candidate_{reservation}",
                    f"{PREFIX}_callback_epoch_{reservation}",
                    f"{PREFIX}_callback_queue_{reservation}",
                    f"{PREFIX}_body_completed_{reservation}",
                    f"{PREFIX}_body_completed_epoch_{reservation}")
    if any(name in state for name in proof_fields):
        raise AssertionError(("reservation_started_with_private_positive_proof", proof_fields, state))
    return reservation, epoch, queue


class LanTransportProvenanceRegression(unittest.TestCase):
    def test_scripted_helper_yes_no_unknown_and_cycle_are_strict(self):
        world, _, _, _ = _fresh_three_arcs()
        helper = next((name for name in world.trigger_defs
                       if name.startswith("ywc_v03_lan_inline_candidate_")), None)
        self.assertIsNotNone(helper, "generated LAN candidate trigger is absent")
        yes = world.condition((helper, "=", "yes"), "LAN")
        no = world.condition((helper, "=", "no"), "LAN")
        self.assertNotEqual(yes, no, "scripted helper = no must be logical complement of = yes")
        with self.assertRaises(AssertionError):
            world.condition(("ywc_v03_lan_inline_unknown_helper", "=", "yes"), "LAN")

        cycle = "ywc_v03_lan_inline_test_cycle"
        world.trigger_defs[cycle] = [(cycle, "=", "yes")]
        try:
            with self.assertRaises(AssertionError):
                world.condition((cycle, "=", "yes"), "LAN")
        finally:
            world.trigger_defs.pop(cycle, None)

    def test_each_arc_real_normal_popup_full_native_body_and_legal_option_ack(self):
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        arcs = {arc["slug"]: arc for arc in catalog["arcs"]}
        for slug in ARC_ORDER:
            with self.subTest(arc=slug):
                world, _, native, _ = _fresh_three_arcs()
                event_id, row = _start_real_popup(world, native, slug)
                reservation, epoch, queue = _reservation(world, row, event_id)
                self.assertEqual(row["arc"]["slug"], slug)
                event = _event(world, event_id)
                self.assertTrue(world.conditions(_field(event, "trigger", []), "LAN"), event_id)
                immediate = _field(event, "immediate")
                self.assertTrue(immediate, (event_id, "native immediate missing"))
                self.assertEqual(arcs[slug]["slug"], row["arc"]["slug"])

                boundaries = []
                original_run = world.run

                def observe_ack(name, tag="LAN"):
                    if name.startswith(PREFIX + "_ack_") and tag == "LAN":
                        boundaries.append((name, copy.deepcopy(world.countries["LAN"])))
                    return original_run(name, tag)

                world.run = observe_ack
                world.execute(immediate, "LAN")
                self.assertEqual(len(boundaries), 1,
                                 (event_id, "actual immediate did not invoke exactly one ACK", boundaries))
                ack_name, at_ack = boundaries[0]
                self.assertEqual(ack_name, f"{PREFIX}_ack_{reservation}")
                self.assertEqual(at_ack.get(f"{PREFIX}_body_completed_{reservation}"), 1,
                                 "completion must be written after the complete native body and before ACK")
                self.assertEqual(at_ack.get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
                self.assertNotIn(f"{PREFIX}_rollback_armed_{reservation}", at_ack,
                                 "completed native body must disarm source-position rollback before ACK")
                self.assertEqual(at_ack.get("ywc_v03_major_event_cooldown"), 1,
                                 "the actual native immediate must execute before ACK")
                self.assertNotIn(queue, world.countries["LAN"], "real ACK did not consume selected queue")
                # Served markers are ordered numeric arc slots in the renderer.
                arc_index = next(i for i, item in enumerate(catalog["arcs"], 1)
                                 if item["slug"] == slug)
                served = f"{PREFIX}_served_{arc_index}"
                self.assertEqual(world.countries["LAN"].get(served),
                                 world.countries["LAN"].get(PREFIX + "_round"))
                self.assertIn(served, world.countries["LAN"], "successful ACK did not mark the native round served")
                after_ack = copy.deepcopy(world.countries["LAN"])
                world.run(ack_name, "LAN")
                world.run(ack_name, "LAN")
                self.assertEqual(world.countries["LAN"], after_ack,
                                 "duplicate public ACK changed an already completed delivery")

                options = [body for key, _, body in event if key == "option"]
                legal = [option for option in options
                         if not _field(option, "trigger") or world.conditions(_field(option, "trigger"), "LAN")]
                self.assertTrue(legal, (event_id, "native event has no legal source option after immediate"))
                chosen = legal[0]
                ignored = {"name", "ai_chance", "trigger", "default_option", "custom_tooltip"}
                world.execute([node for node in chosen if node[0] not in ignored], "LAN")

    def test_public_ack_without_body_cannot_consume_queue_serve_or_mint_proof(self):
        world, _, native, _ = _fresh_three_arcs()
        event_id, row = _start_real_popup(world, native, ARC_ORDER[0])
        reservation, epoch, queue = _reservation(world, row, event_id)
        state = world.countries["LAN"]
        before = copy.deepcopy(state)

        world.run(f"{PREFIX}_callback_{reservation}", "LAN")
        world.run(f"{PREFIX}_ack_{reservation}", "LAN")

        self.assertEqual(state.get(queue), before[queue], "public ACK consumed source queue without body")
        self.assertEqual(state.get(PREFIX + "_reservation"), reservation)
        self.assertEqual(state.get(PREFIX + "_reservation_epoch"), epoch)
        private_positive_fields = (
            f"{PREFIX}_body_completed_{reservation}",
            f"{PREFIX}_body_completed_epoch_{reservation}",
            f"{PREFIX}_callback_{reservation}",
            f"{PREFIX}_callback_candidate_{reservation}",
            f"{PREFIX}_callback_epoch_{reservation}",
            f"{PREFIX}_callback_queue_{reservation}",
        )
        self.assertFalse(set(private_positive_fields).intersection(state),
                         "public callback/ACK minted private body or callback proof")
        arc_index = next(index for index, arc in enumerate(
            json.loads(CATALOG.read_text(encoding="utf-8"))["arcs"], 1)
            if arc["slug"] == row["arc"]["slug"])
        self.assertNotEqual(state.get(f"{PREFIX}_served_{arc_index}"), state.get(PREFIX + "_round"),
                            "public callback/ACK served an arc without body")
        self.assertNotIn("ywc_v03_major_event_cooldown", state,
                         "public ACK fabricated native immediate effects")

    def test_actual_popup_rejects_bad_global_or_candidate_epoch_before_native_body(self):
        faults = ("missing_global", "zero_global", "negative_global", "wrong_global", "wrong_candidate")
        for fault in faults:
            with self.subTest(fault=fault):
                world, _, native, _ = _fresh_three_arcs()
                event_id, row = _start_real_popup(world, native, ARC_ORDER[0])
                reservation, epoch, queue = _reservation(world, row, event_id)
                state = world.countries["LAN"]
                if fault == "missing_global":
                    state.pop(PREFIX + "_reservation_epoch", None)
                elif fault == "zero_global":
                    state[PREFIX + "_reservation_epoch"] = 0.0
                elif fault == "negative_global":
                    state[PREFIX + "_reservation_epoch"] = -1.0
                elif fault == "wrong_global":
                    state[PREFIX + "_reservation_epoch"] = epoch + 1
                else:
                    state[f"{PREFIX}_candidate_epoch_{reservation}"] = epoch + 1
                before_queue = (queue in state, state.get(queue))

                event = _event(world, event_id)
                self.assertFalse(world.conditions(_field(event, "trigger", []), "LAN"),
                                 f"{fault} admitted a source popup")
                # Exercise the complete actual immediate behind its own event
                # guard; this is not a partial AST body witness.
                world.execute(_field(event, "immediate"), "LAN")
                world.run(f"{PREFIX}_callback_{reservation}", "LAN")
                world.run(f"{PREFIX}_ack_{reservation}", "LAN")

                self.assertEqual((queue in state, state.get(queue)), before_queue)
                self.assertNotIn("ywc_v03_major_event_cooldown", state)
                self.assertNotIn(f"{PREFIX}_body_completed_{reservation}", state)
                self.assertNotIn(f"{PREFIX}_callback_{reservation}", state)

    def test_actual_source_blocking_history_emits_12_then_36_notices_for_each_arc(self):
        for slug in ARC_ORDER:
            with self.subTest(arc=slug):
                world, native, order = _notice_world(slug)
                short = _notice_short(slug)
                event_id, row = _start_real_popup(world, native, slug, order=order,
                                                  desired_kind="notice12", max_months=72)
                state = world.countries["LAN"]
                reservation, _, queue = _reservation(world, row, event_id)
                self.assertEqual(_candidate_kind(row["candidate"]), "notice12")
                self.assertEqual(row["candidate"]["value"], 12)
                self.assertEqual(state[f"ywc_lan_{short}_notice_current"], 12.0)
                self.assertEqual(state[f"ywc_lan_{short}_notice12_sent"], 1.0)
                event = _event(world, event_id)
                self.assertTrue(world.conditions(_field(event, "trigger", []), "LAN"))
                world.execute(_field(event, "immediate"), "LAN")
                option = _source_option(world, event, f"reconsider_{short}_12")
                self.assertIsNotNone(option, (event_id, state))
                self.assertNotIn(queue, state, "real 12-month ACK did not consume selected notice queue")
                _execute_option(world, option)

                event_id, row = _start_real_popup(world, native, slug, order=order,
                                                  desired_kind="notice36", max_months=72)
                reservation, _, queue = _reservation(world, row, event_id)
                self.assertEqual(_candidate_kind(row["candidate"]), "notice36")
                self.assertEqual(row["candidate"]["value"], 36)
                self.assertEqual(state[f"ywc_lan_{short}_notice_current"], 36.0)
                self.assertEqual(state[f"ywc_lan_{short}_notice36_sent"], 1.0)
                event = _event(world, event_id)
                self.assertTrue(world.conditions(_field(event, "trigger", []), "LAN"))
                world.execute(_field(event, "immediate"), "LAN")
                option = _source_option(world, event, f"narrow_{short}_36")
                self.assertIsNotNone(option, (event_id, state))
                self.assertNotIn(queue, state, "real 36-month ACK did not consume selected notice queue")
                _execute_option(world, option)

    def test_real_notice12_ack_boundary_fault_cleanup_preserves_native_aux_and_cooldown(self):
        slug = "v03_lan_river_compacts"
        short = _notice_short(slug)
        world, native, order = _notice_world(slug)
        event_id, row = _start_real_popup(world, native, slug, order=order,
                                          desired_kind="notice12", max_months=72)
        reservation, epoch, queue = _reservation(world, row, event_id)
        state = world.countries["LAN"]
        current = f"ywc_lan_{short}_notice_current"
        sent = f"ywc_lan_{short}_notice12_sent"
        sibling_sent = f"ywc_lan_{short}_notice36_sent"
        before_native = {name: (name in state, state.get(name))
                         for name in (current, sent, sibling_sent)}
        callback_proof = f"{PREFIX}_callback_{reservation}"
        candidate_epoch = f"{PREFIX}_candidate_epoch_{reservation}"
        timer = PREFIX + "_timer"
        ack_name = f"{PREFIX}_ack_{reservation}"
        boundaries = []
        original_run = world.run

        def corrupt_at_actual_ack(name, tag="LAN"):
            if name == ack_name and tag == "LAN":
                self.assertEqual(state.get(callback_proof), 1)
                state.pop(callback_proof, None)
                state.pop(timer, None)
                state.pop(PREFIX + "_reservation_epoch", None)
                state.pop(candidate_epoch, None)
                boundaries.append(copy.deepcopy(state))
            return original_run(name, tag)

        world.run = corrupt_at_actual_ack
        event = _event(world, event_id)
        self.assertTrue(world.conditions(_field(event, "trigger", []), "LAN"))
        world.execute(_field(event, "immediate"), "LAN")
        self.assertEqual(len(boundaries), 1, "notice delivery missed the actual ACK invocation")
        at_ack = boundaries[0]
        self.assertEqual(at_ack.get(f"{PREFIX}_body_completed_{reservation}"), 1)
        self.assertEqual(at_ack.get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
        self.assertNotIn(f"{PREFIX}_rollback_armed_{reservation}", at_ack)
        self.assertEqual({name: (name in at_ack, at_ack.get(name))
                          for name in (current, sent, sibling_sent)}, before_native)
        self.assertEqual(at_ack.get("ywc_v03_major_event_cooldown"), 1)
        self.assertEqual(state.get(queue), 12.0, "failed ACK consumed source notice queue")
        arc_index = next(index for index, arc in enumerate(
            json.loads(CATALOG.read_text(encoding="utf-8"))["arcs"], 1)
            if arc["slug"] == slug)
        self.assertNotEqual(state.get(f"{PREFIX}_served_{arc_index}"), state.get(PREFIX + "_round"),
                            "failed ACK served river in the current round")

        world.run = original_run
        world.run(PREFIX + "_prepare", "LAN")
        self.assertNotIn(PREFIX + "_reservation", state, "known notice slot remained stranded")
        self.assertNotIn(timer, state)
        self.assertEqual(state.get(queue), 12.0)
        self.assertEqual({name: (name in state, state.get(name))
                          for name in (current, sent, sibling_sent)}, before_native,
                         "post-body cleanup rolled back source-position current/sent writes")
        self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1)
        self.assertNotIn(f"{PREFIX}_body_completed_{reservation}", state)

    def test_actual_ack_boundary_proof_fault_then_known_missing_epoch_cleanup_keeps_body(self):
        world, _, native, _ = _fresh_three_arcs()
        event_id, row = _start_real_popup(world, native, ARC_ORDER[0])
        reservation, epoch, queue = _reservation(world, row, event_id)
        state = world.countries["LAN"]
        callback_proof = f"{PREFIX}_callback_{reservation}"
        ack_name = f"{PREFIX}_ack_{reservation}"
        boundary = []
        original_run = world.run

        def corrupt_proof_at_actual_ack(name, tag="LAN"):
            if name == ack_name and tag == "LAN":
                self.assertEqual(state.get(callback_proof), 1,
                                 "real body did not produce callback proof before ACK invocation")
                state.pop(callback_proof, None)  # controlled fault at the actual world.run boundary
                boundary.append(copy.deepcopy(state))
            return original_run(name, tag)

        world.run = corrupt_proof_at_actual_ack
        event = _event(world, event_id)
        self.assertTrue(world.conditions(_field(event, "trigger", []), "LAN"))
        world.execute(_field(event, "immediate"), "LAN")
        self.assertEqual(len(boundary), 1, "ACK fault was not injected at the actual helper call")
        at_ack = boundary[0]
        self.assertEqual(at_ack.get(f"{PREFIX}_body_completed_{reservation}"), 1)
        self.assertEqual(at_ack.get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
        self.assertNotIn(f"{PREFIX}_rollback_armed_{reservation}", at_ack)
        self.assertEqual(at_ack.get("ywc_v03_major_event_cooldown"), 1)
        self.assertEqual(state.get(queue), row["candidate"]["value"],
                         "failed ACK must leave selected source queue available")
        self.assertIn(PREFIX + "_reservation", state)

        world.run = original_run
        state.pop(PREFIX + "_reservation_epoch", None)  # known-ID cleanup without a usable global epoch
        world.run(PREFIX + "_prepare", "LAN")
        self.assertNotIn(PREFIX + "_reservation", state, "known invalid slot was stranded")
        self.assertNotIn(PREFIX + "_timer", state)
        self.assertEqual(state.get(queue), row["candidate"]["value"])
        self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1,
                         "post-body cleanup rolled back completed native delivery")
        self.assertNotIn(f"{PREFIX}_body_completed_{reservation}", state)

    def test_unknown_reservation_ids_clear_private_state_only_on_natural_notice(self):
        """An unrecognized ID must never authorize rollback of native notice state."""
        slug = "v03_lan_river_compacts"
        short = _notice_short(slug)
        for unknown_id in (0, -1, 999):
            with self.subTest(reservation=unknown_id):
                world, native, order = _notice_world(slug)
                event_id, row = _start_real_popup(
                    world, native, slug, order=order,
                    desired_kind="notice12", max_months=72)
                reservation, _, queue = _reservation(world, row, event_id)
                state = world.countries["LAN"]
                current = f"ywc_lan_{short}_notice_current"
                sent12 = f"ywc_lan_{short}_notice12_sent"
                sent36 = f"ywc_lan_{short}_notice36_sent"
                native_before = {
                    name: (name in state, state.get(name))
                    for name in (queue, current, sent12, sent36,
                                 "ywc_v03_major_event_cooldown")
                }
                round_before = state[PREFIX + "_round"]
                epoch_before = state[PREFIX + "_reservation_epoch"]
                # Controlled ID corruption of the source-created positive reservation.
                # No positive reservation, proof, queue, or epoch is seeded here.
                state[PREFIX + "_reservation"] = float(unknown_id)
                world.run(PREFIX + "_prepare", "LAN")

                self.assertNotIn(PREFIX + "_reservation", state)
                self.assertNotIn(PREFIX + "_timer", state)
                self.assertNotIn(f"{PREFIX}_candidate_epoch_{reservation}", state)
                self.assertEqual(
                    {name: (name in state, state.get(name)) for name in native_before},
                    native_before,
                    "unknown ID cleanup mutated the actual source queue/current/sent/cooldown")
                self.assertEqual(state[PREFIX + "_round"], round_before)
                self.assertEqual(state[PREFIX + "_reservation_epoch"], epoch_before)

    def test_natural_notice_prebody_cleanup_cas_restores_original_absent_zero_and_seven(self):
        """Source writes are rolled back only while each field still has our post-value."""
        for slug in ARC_ORDER:
            short = _notice_short(slug)
            for original in (None, 0, 7):
                with self.subTest(arc=slug, original=original):
                    world, native, order = _notice_world(slug)
                    current = f"ywc_lan_{short}_notice_current"
                    sent12 = f"ywc_lan_{short}_notice12_sent"

                    def set_original_at_real_reserve(active_world, bound_row, reserve_name):
                        self.assertEqual(bound_row["arc"]["slug"], slug)
                        state = active_world.countries["LAN"]
                        for field in (current, sent12):
                            if original is None:
                                state.pop(field, None)
                            else:
                                state[field] = float(original)

                    event_id, row = _start_real_popup(
                        world, native, slug, order=order, desired_kind="notice12",
                        max_months=72, reserve_boundary=set_original_at_real_reserve)
                    reservation, _, queue = _reservation(world, row, event_id)
                    state = world.countries["LAN"]
                    self.assertEqual(row["candidate"]["value"], 12)
                    self.assertEqual(state[current], 12.0)
                    self.assertEqual(state[sent12], 1.0)
                    self.assertEqual(state[queue], 12.0)

                    # A known pre-body fault at the real notice popup boundary.
                    # The queue and source-position writes came from native history.
                    state.pop(PREFIX + "_timer", None)
                    event = _event(world, event_id)
                    self.assertFalse(world.conditions(_field(event, "trigger", []), "LAN"))
                    world.execute(_field(event, "immediate"), "LAN")
                    self.assertNotIn(f"{PREFIX}_body_completed_{reservation}", state)
                    self.assertNotIn(f"{PREFIX}_callback_{reservation}", state)
                    world.run(PREFIX + "_prepare", "LAN")

                    for field in (current, sent12):
                        expected = (False, None) if original is None else (True, float(original))
                        self.assertEqual((field in state, state.get(field)), expected,
                                         (slug, original, field, state))
                    self.assertEqual(state[queue], 12.0,
                                     "source queue is not an auxiliary field owned by rollback")
                    self.assertNotIn(PREFIX + "_reservation", state)
                    self.assertNotIn(PREFIX + "_timer", state)
                    self.assertNotIn(f"{PREFIX}_rollback_armed_{reservation}", state)

    def test_natural_notice_prebody_cleanup_preserves_fresh_live_absent_zero_and_seven(self):
        """CAS rollback leaves live values changed by another native writer untouched."""
        slug = "v03_lan_work_accident_fund"
        short = _notice_short(slug)
        for original, fresh in ((None, 7), (0, None), (7, 0)):
            with self.subTest(original=original, fresh=fresh):
                world, native, order = _notice_world(slug)
                current = f"ywc_lan_{short}_notice_current"
                sent12 = f"ywc_lan_{short}_notice12_sent"

                def set_original_at_real_reserve(active_world, bound_row, reserve_name):
                    state = active_world.countries["LAN"]
                    for field in (current, sent12):
                        if original is None:
                            state.pop(field, None)
                        else:
                            state[field] = float(original)

                event_id, row = _start_real_popup(
                    world, native, slug, order=order, desired_kind="notice12",
                    max_months=72, reserve_boundary=set_original_at_real_reserve)
                reservation, _, queue = _reservation(world, row, event_id)
                state = world.countries["LAN"]
                self.assertEqual(state[current], 12.0)
                self.assertEqual(state[sent12], 1.0)

                # Controlled later native writes distinguish CAS cleanup from a
                # blind restore; source queue remains the naturally queued 12.
                for field in (current, sent12):
                    if fresh is None:
                        state.pop(field, None)
                    else:
                        state[field] = float(fresh)
                state.pop(PREFIX + "_reservation_epoch", None)
                event = _event(world, event_id)
                self.assertFalse(world.conditions(_field(event, "trigger", []), "LAN"))
                world.execute(_field(event, "immediate"), "LAN")
                self.assertNotIn(f"{PREFIX}_body_completed_{reservation}", state)
                world.run(PREFIX + "_prepare", "LAN")

                for field in (current, sent12):
                    expected = (False, None) if fresh is None else (True, float(fresh))
                    self.assertEqual((field in state, state.get(field)), expected,
                                     (original, fresh, field, state))
                self.assertEqual(state[queue], 12.0)
                self.assertNotIn(PREFIX + "_reservation", state)
                self.assertNotIn(PREFIX + "_timer", state)

    def test_natural_notice_missing_or_mismatched_candidate_epoch_cannot_complete_or_strand(self):
        slug = "v03_lan_mine_accounts"
        short = _notice_short(slug)
        current = f"ywc_lan_{short}_notice_current"
        sent12 = f"ywc_lan_{short}_notice12_sent"
        sent36 = f"ywc_lan_{short}_notice36_sent"
        for original in (None, 0, 7):
            for mutation in ("missing_global", "missing_candidate", "mismatch_candidate"):
                with self.subTest(original=original, fault=mutation):
                    world, native, order = _notice_world(slug)
                    original_native = {}

                    def set_pre_reserve_values(active_world, bound_row, reserve_name):
                        state = active_world.countries["LAN"]
                        self.assertEqual(bound_row["arc"]["slug"], slug)
                        for field in (current, sent12, sent36):
                            if original is None:
                                state.pop(field, None)
                            else:
                                state[field] = float(original)
                            original_native[field] = (field in state, state.get(field))

                    event_id, row = _start_real_popup(
                        world, native, slug, order=order,
                        desired_kind="notice12", max_months=72,
                        reserve_boundary=set_pre_reserve_values)
                    reservation, epoch, queue = _reservation(world, row, event_id)
                    state = world.countries["LAN"]
                    # The source position writes these before the popup. The expected
                    # rollback owner values come only from the observed real reserve call.
                    self.assertEqual(state[current], 12.0)
                    self.assertEqual(state[sent12], 1.0)
                    self.assertEqual((sent36 in state, state.get(sent36)), original_native[sent36])
                    self.assertEqual(state[queue], 12.0)

                    candidate_epoch = f"{PREFIX}_candidate_epoch_{reservation}"
                    if mutation == "missing_global":
                        state.pop(PREFIX + "_reservation_epoch", None)
                    elif mutation == "missing_candidate":
                        state.pop(candidate_epoch, None)
                    else:
                        state[candidate_epoch] = float(epoch + 1)

                    event = _event(world, event_id)
                    self.assertFalse(world.conditions(_field(event, "trigger", []), "LAN"))
                    # Execute the complete event immediate anyway. Its own guard must
                    # reject the body and leave rollback ownership available to prepare.
                    world.execute(_field(event, "immediate"), "LAN")
                    self.assertNotIn(f"{PREFIX}_body_completed_{reservation}", state)
                    self.assertNotIn(f"{PREFIX}_callback_{reservation}", state)
                    world.run(PREFIX + "_prepare", "LAN")

                    self.assertNotIn(PREFIX + "_reservation", state)
                    self.assertNotIn(PREFIX + "_timer", state)
                    self.assertNotIn(f"{PREFIX}_rollback_armed_{reservation}", state)
                    self.assertEqual((current in state, state.get(current)), original_native[current])
                    self.assertEqual((sent12 in state, state.get(sent12)), original_native[sent12])
                    self.assertEqual((sent36 in state, state.get(sent36)), original_native[sent36],
                                     "untouched sibling sent36 must remain at its pre-reserve value")
                    self.assertEqual(state[queue], 12.0,
                                     "unserved source queue must remain after rejected notice body")

    def test_real_notice_delivery_cooldown_expires_after_three_real_monthly_pulses(self):
        """Cooldown time advances with calendar days while every live JE still pulses."""
        slug = "v03_lan_river_compacts"
        short = _notice_short(slug)
        world, native, order = _notice_world(slug)
        event_id, row = _start_real_popup(
            world, native, slug, order=order, desired_kind="notice12", max_months=72)
        reservation, _, _ = _reservation(world, row, event_id)
        event = _event(world, event_id)
        world.execute(_field(event, "immediate"), "LAN")
        option = _source_option(world, event, f"reconsider_{short}_12")
        self.assertIsNotNone(option)
        _execute_option(world, option)
        state = world.countries["LAN"]
        cooldown = "ywc_v03_major_event_cooldown"
        self.assertIn(cooldown, state)

        for month in range(1, 4):
            world.advance_days(30)
            if month < 3:
                self.assertIn(cooldown, state,
                              f"native 90-day cooldown expired before day {month * 30}")
            else:
                self.assertNotIn(cooldown, state,
                                 "native 90-day cooldown did not expire at day 90")
            for source_slug in order:
                effect = _field(_field(native[source_slug], "on_monthly_pulse"), "effect")
                before = len(world.events)
                world.execute(effect, "LAN")
                emitted = len(world.events) - before
                for _ in range(emitted):
                    tag, next_event_id = world.events.pop(before)
                    self.assertEqual(tag, "LAN")
                    popup = _event(world, next_event_id)
                    if world.conditions(_field(popup, "trigger", []), "LAN"):
                        # Maintain source-driven progression for a popup released at the
                        # expiry boundary, including complete body and a legal option.
                        world.execute(_field(popup, "immediate"), "LAN")
                        legal = _source_option(world, popup, "defer")
                        if legal is not None:
                            _execute_option(world, legal)

    def test_natural_notice_expired_timer_after_owner_snapshot_loss_preserves_live_postwrite(self):
        slug = "v03_lan_river_compacts"
        short = _notice_short(slug)
        world, native, order = _notice_world(slug)
        current = f"ywc_lan_{short}_notice_current"
        sent12 = f"ywc_lan_{short}_notice12_sent"

        def original_seven_at_actual_reserve(active_world, bound_row, reserve_name):
            state = active_world.countries["LAN"]
            state[current] = 7.0
            state[sent12] = 7.0

        event_id, row = _start_real_popup(
            world, native, slug, order=order, desired_kind="notice12",
            max_months=72, reserve_boundary=original_seven_at_actual_reserve)
        reservation, _, queue = _reservation(world, row, event_id)
        state = world.countries["LAN"]
        self.assertEqual((state[current], state[sent12]), (12.0, 1.0))
        current_snapshot = (f"{PREFIX}_c{reservation}_{current}_present",
                           f"{PREFIX}_c{reservation}_{current}_value")
        self.assertEqual(state.get(current_snapshot[0]), 1.0)
        self.assertEqual(state.get(current_snapshot[1]), 7.0)

        # Controlled loss of this one ownership record simulates a paired-snapshot
        # fault; the source's current post-write remains a live value and must fail closed.
        state.pop(current_snapshot[0])
        state.pop(current_snapshot[1])
        world.advance_days(2)
        self.assertNotIn(PREFIX + "_timer", state,
                         "the real one-day delivery timer did not expire")
        world.run(PREFIX + "_prepare", "LAN")

        self.assertNotIn(PREFIX + "_reservation", state,
                         "expired delivery lease did not release private reservation")
        self.assertNotIn(PREFIX + "_timer", state)
        self.assertIn(current, state,
                      "missing paired snapshot erased the live source post-write")
        self.assertEqual(state.get(current), 12.0,
                         "missing paired snapshot must preserve live source post-write, not erase it")
        self.assertEqual(state.get(sent12), 7.0,
                         "undamaged sibling snapshot should restore its exact original value")
        self.assertEqual(state[queue], 12.0)

    def test_same_candidate_id_rejects_captured_stale_body_proof_after_natural_retry(self):
        slug = ARC_ORDER[0]
        world, _, native, _ = _fresh_three_arcs()
        first_event_id, first_row = _start_real_popup(world, native, slug)
        first_reservation, first_epoch, queue = _reservation(world, first_row, first_event_id)
        self.assertEqual(first_row["arc"]["slug"], slug)
        first_state = world.countries["LAN"]
        first_ack = f"{PREFIX}_ack_{first_reservation}"
        first_callback = f"{PREFIX}_callback_{first_reservation}"
        proof_names = (
            first_callback,
            f"{PREFIX}_callback_candidate_{first_reservation}",
            f"{PREFIX}_callback_epoch_{first_reservation}",
            f"{PREFIX}_callback_queue_{first_reservation}",
            f"{PREFIX}_body_completed_{first_reservation}",
            f"{PREFIX}_body_completed_epoch_{first_reservation}",
        )
        captured_old_proof = []
        original_run = world.run

        def reject_first_ack_after_real_body(name, tag="LAN"):
            if name == first_ack and tag == "LAN":
                captured_old_proof.append({key: first_state[key] for key in proof_names
                                           if key in first_state})
                self.assertEqual(len(captured_old_proof[-1]), len(proof_names),
                                 "first complete real body did not emit its entire callback tuple")
                # Controlled post-body identity fault makes the actual ACK reject while
                # leaving the captured old proof material from the real body intact.
                first_state[f"{PREFIX}_candidate_epoch_{first_reservation}"] = float(first_epoch + 1)
            return original_run(name, tag)

        world.run = reject_first_ack_after_real_body
        first_event = _event(world, first_event_id)
        self.assertTrue(world.conditions(_field(first_event, "trigger", []), "LAN"))
        world.execute(_field(first_event, "immediate"), "LAN")
        self.assertEqual(len(captured_old_proof), 1)
        self.assertEqual(first_state.get(queue), first_row["candidate"]["value"],
                         "rejected actual ACK consumed its natural source queue")
        self.assertIn("ywc_v03_major_event_cooldown", first_state)
        world.run = original_run
        # Restore only the controlled identity mutation. The failed proof remains
        # real old material; expiry/cleanup must now occur on natural monthly pulses.
        first_state[f"{PREFIX}_candidate_epoch_{first_reservation}"] = float(first_epoch)

        # Retry only by source calendar progression; _start_real_popup pulses every
        # admitted JE and executes full bodies/legal defer options for non-target events.
        elapsed = 0
        cooldown_observations = []
        advance_days = world.advance_days

        def observe_calendar(days=1):
            nonlocal elapsed
            advance_days(days)
            elapsed += days
            if days == 30:
                cooldown_observations.append((elapsed,
                                              "ywc_v03_major_event_cooldown" in first_state))

        world.advance_days = observe_calendar
        try:
            retry_event_id, retry_row = _start_real_popup(
                world, native, slug, order=ARC_ORDER, desired_kind="normal", max_months=6)
        finally:
            world.advance_days = advance_days
        self.assertEqual(cooldown_observations[:3], [(30, True), (60, True), (90, False)],
                         "natural mine-first source retry did not wait for the actual 90-day cooldown")
        retry_reservation, retry_epoch, retry_queue = _reservation(world, retry_row, retry_event_id)
        self.assertEqual(retry_reservation, first_reservation,
                         "same candidate should be selected again after its natural 90-day cooldown")
        self.assertGreater(retry_epoch, first_epoch)
        self.assertEqual(retry_queue, queue)
        self.assertEqual(first_state.get(retry_queue), retry_row["candidate"]["value"])

        before_bare_replay = copy.deepcopy(first_state)
        world.run(first_callback, "LAN")
        world.run(first_ack, "LAN")
        self.assertEqual(first_state, before_bare_replay,
                         "old public callback/ACK without captured proof changed the fresh slot")

        # Replay proof values captured from the prior actual body. These are not fake
        # positives: every copied value came from the real first immediate boundary.
        first_state.update(captured_old_proof[0])
        old_callback_snapshot = {key: first_state[key] for key in proof_names}
        world.run(first_callback, "LAN")
        self.assertEqual({key: first_state.get(key) for key in proof_names}, old_callback_snapshot,
                         "old public callback rewrote its stale proof for the new epoch")
        world.run(first_ack, "LAN")
        self.assertEqual(first_state.get(PREFIX + "_reservation"), float(retry_reservation),
                         "stale same-ID ACK consumed a fresh reservation")
        self.assertEqual(first_state.get(retry_queue), retry_row["candidate"]["value"])
        self.assertNotEqual(first_state.get(f"{PREFIX}_served_1"),
                            first_state.get(PREFIX + "_round"),
                            "stale proof served the current round")

        # Remove the stale slot with the real cleanup helper and source-reserve again;
        # then prove a fresh complete body at the current epoch can ACK normally.
        world.advance_days(2)
        world.run(PREFIX + "_prepare", "LAN")
        self.assertNotIn(PREFIX + "_reservation", first_state)
        final_event_id, final_row = _start_real_popup(
            world, native, slug, order=ARC_ORDER, desired_kind="normal", max_months=2)
        final_reservation, final_epoch, final_queue = _reservation(world, final_row, final_event_id)
        self.assertEqual(final_reservation, first_reservation)
        self.assertGreater(final_epoch, retry_epoch)
        final_event = _event(world, final_event_id)
        world.execute(_field(final_event, "immediate"), "LAN")
        self.assertNotIn(final_queue, first_state)
        self.assertNotIn(PREFIX + "_reservation", first_state)
        self.assertIn(f"{PREFIX}_served_1", first_state)


if __name__ == "__main__":
    unittest.main()
