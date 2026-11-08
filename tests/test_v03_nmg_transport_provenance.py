"""Permanent source-driven NMG inline transport provenance regressions.

All successful deliveries start at actual NMG admission and take a real
authored monthly-pulse -> event immediate -> legal-option path. The protocol
fields are inspected only as evidence after source execution; this file never
seeds a successful private proof.
"""
import copy
import json
import unittest
from pathlib import Path
from tests.test_v03_nmg_actual_fairness import actual_nmg_admission_world
from tests.clausewitz_harness import parse

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/content/v03/countries/nmg.json"
PREFIX = "ywc_v03_nmg_inline"
ARC_ORDER = tuple(arc["slug"] for arc in json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["arcs"])


def _field(nodes, key, default=None):
    return next((value for name, _, value in nodes if name == key), default)


def _walk_source_nodes(nodes):
    for node in nodes:
        yield node
        value = node[2]
        if isinstance(value, list):
            yield from _walk_source_nodes(value)


def _native_last_event_variable(immediate):
    writes = []
    for name, _, fields in _walk_source_nodes(immediate):
        if name != "set_variable":
            continue
        variable = _field(fields, "name", "")
        if variable.startswith("ywc_nmg_") and variable.endswith("_last_event"):
            writes.append(variable)
    if len(writes) != 1:
        raise AssertionError(("expected-one-native-business-last-event-write", writes))
    return writes[0]


def _catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _rows():
    result = []
    for arc in _catalog()["arcs"]:
        adapter = arc.get("inline_delivery_adapter")
        if not isinstance(adapter, dict):
            continue
        for branch in adapter.get("branches", []):
            candidates = branch.get("candidates", [])
            if len(candidates) != 1:
                raise AssertionError((arc["slug"], branch.get("event"), candidates))
            result.append({"arc": arc, "branch": branch, "candidate": candidates[0]})
    return result


def _require_adapter(test):
    arcs = _catalog()["arcs"]
    missing = [arc["slug"] for arc in arcs if not isinstance(arc.get("inline_delivery_adapter"), dict)]
    test.assertFalse(missing,
                     "NMG inline transport adapter is absent for " + ", ".join(missing))


def _event(world, event_id):
    try:
        return world.event_defs[event_id]
    except KeyError as exc:
        raise AssertionError(f"authored NMG event source is missing {event_id}") from exc


def _candidate(world, event_id):
    state = world.countries["NMG"]
    reservation = state.get(PREFIX + "_reservation")
    if isinstance(reservation, bool) or not isinstance(reservation, (int, float)) or int(reservation) != reservation:
        return None
    reservation = int(reservation)
    rows = _rows()
    if not 1 <= reservation <= len(rows):
        return None
    row = rows[reservation - 1]
    return row if row["branch"]["event"] == event_id else None


def _candidate_kind(candidate):
    kind = candidate["kind"]
    if kind in ("notice12", "notice36"):
        return kind
    if kind == "normal":
        return "normal"
    if kind == "notice":
        value = candidate.get("value")
        if value in (1006, 1014, 1028):
            return "notice12"
        if value in (1007, 1015, 1029):
            return "notice36"
    return kind


def _legal_option(world, event, suffix):
    for _, _, option in (node for node in event if node[0] == "option"):
        name = _field(option, "name", "")
        if not name.endswith("." + suffix):
            continue
        gate = _field(option, "trigger")
        if not gate or world.conditions(gate, "NMG"):
            return option
    return None


def _execute_option(world, option):
    ignored = {"name", "trigger", "ai_chance", "default_option", "custom_tooltip"}
    world.execute([node for node in option if node[0] not in ignored], "NMG")


def _start_real_popup(slug, kind="normal", max_months=6):
    """Pulse all three live JEs in authored order; execute incidental popups fully."""
    world, evidence, order = _first_popup_world(slug)
    catalog_arcs = {arc["slug"]: arc for arc in _catalog()["arcs"]}
    for _ in range(max_months):
        world.advance_months(1)
        _refresh_actual_phases(world)
        for source_slug in order:
            journal_id = world.nmg_phase_by_arc.get(source_slug)
            if journal_id is None:
                continue
            journal = world.journal_defs[journal_id]
            pulse = _field(_field(journal, "on_monthly_pulse"), "effect")
            before = len(world.events)
            world.active_journal = journal_id
            world.execute(pulse, "NMG")
            emitted = world.events[before:]
            del world.events[before:]
            for tag, event_id in emitted:
                if tag != "NMG":
                    raise AssertionError(("unexpected_popup_recipient", tag, event_id))
                event = _event(world, event_id)
                gate = _field(event, "trigger", [])
                if gate and not world.conditions(gate, "NMG"):
                    continue
                row = _candidate(world, event_id)
                if row is None:
                    raise AssertionError(("eligible_source_popup_without_bound_candidate", event_id,
                                          world.countries["NMG"]))
                actual_kind = _candidate_kind(row["candidate"])
                if row["arc"]["slug"] == slug and actual_kind == kind:
                    return world, evidence, event_id, row, order

                # Real incidental popup: complete the whole native immediate and
                # choose its source-authored defer option before another pulse.
                world.execute(_field(event, "immediate", []), "NMG")
                defer = _legal_option(world, event, "defer")
                if defer is None:
                    defer = _legal_option(world, event, "wait_retry")
                if defer is None:
                    raise AssertionError(("non_target_popup_has_no_legal_deferral", event_id))
                _execute_option(world, defer)
    raise AssertionError(("no_requested_real_source_popup", slug, kind,
                          world.countries["NMG"]))


def _first_popup_world(slug):
    order = (slug,) + tuple(item for item in ARC_ORDER if item != slug)
    world, evidence = actual_nmg_admission_world(admission_order=order)
    world.nmg_phase_by_arc = {
        arc["slug"]: arc["journals"][0]["id"] for arc in _catalog()["arcs"]
    }
    return world, evidence, order


def _refresh_actual_phases(world):
    """Reconcile terminal JEs and activate only the next authored live phase."""
    arcs = {arc["slug"]: arc for arc in _catalog()["arcs"]}
    for slug in ARC_ORDER:
        while world.nmg_phase_by_arc[slug] is not None:
            je_id = world.nmg_phase_by_arc[slug]
            entry = world.journal_defs[je_id]
            complete = world.conditions(_field(entry, "complete", []), "NMG")
            failed = world.conditions(_field(entry, "fail", []), "NMG")
            if not complete and not failed:
                break
            if complete and failed:
                raise AssertionError(("actual-je-both-complete-and-failed", je_id))
            if failed:
                world.execute(_field(entry, "on_fail", []), "NMG")
                world.failed_journals.append(je_id)
                world.active_journals.discard(je_id)
                world.nmg_phase_by_arc[slug] = None
                break
            world.execute(_field(entry, "on_complete", []), "NMG")
            world.completed_journals.append(je_id)
            world.active_journals.discard(je_id)
            position = next(index for index, item in enumerate(arcs[slug]["journals"])
                            if item["id"] == je_id)
            next_position = position + 1
            if next_position >= len(arcs[slug]["journals"]):
                world.nmg_phase_by_arc[slug] = None
                break
            next_id = arcs[slug]["journals"][next_position]["id"]
            next_entry = world.journal_defs[next_id]
            if not (world.conditions(_field(next_entry, "is_shown_when_inactive", []), "NMG")
                    and world.conditions(_field(next_entry, "possible", []), "NMG")):
                world.nmg_phase_by_arc[slug] = None
                break
            world.nmg_phase_by_arc[slug] = next_id
            world.active_journal = next_id
            world.active_journals.add(next_id)
            world.journals.append(("NMG", next_entry))
            world.execute(_field(next_entry, "immediate", []), "NMG")


def _receive(world, event_id, option_suffix):
    event = _event(world, event_id)
    gate = _field(event, "trigger", [])
    if gate and not world.conditions(gate, "NMG"):
        raise AssertionError(("source-dispatched-event-trigger-false", event_id,
                              world.countries["NMG"]))
    world.execute(_field(event, "immediate", []), "NMG")
    option = _legal_option(world, event, option_suffix)
    if option is None:
        raise AssertionError(("requested-source-option-not-legal", event_id, option_suffix,
                              world.countries["NMG"]))
    _execute_option(world, option)


def _default_source_choice(world, event):
    """Resolve a non-target popup through its actual body and a legal authored choice."""
    world.execute(_field(event, "immediate", []), "NMG")
    for suffix in ("defer", "wait_retry", "wait_for_funds", "hold_route", "keep_route"):
        option = _legal_option(world, event, suffix)
        if option is not None:
            _execute_option(world, option)
            return
    raise AssertionError(("incidental-popup-has-no-authored-defer-wait-option",
                          _field(event, "title"), [
                              _field(option, "name") for key, _, option in event if key == "option"
                          ]))


def _pulse_all_until(world, order, target_slug, target_event, target_kind,
                     max_months, pulse_counts=None):
    """Keep all three admitted JEs live and process every emitted native popup."""
    arcs = {arc["slug"]: arc for arc in _catalog()["arcs"]}
    for month_index in range(max_months):
        world.advance_months(1)
        _refresh_actual_phases(world)
        # Rotate the dispatch head each calendar window. A 90-day common
        # cooldown would otherwise let the same JE always win first at day 90.
        month_order = order[month_index % len(order):] + order[:month_index % len(order)]
        for source_slug in month_order:
            journal_id = world.nmg_phase_by_arc.get(source_slug)
            if journal_id is None:
                continue
            journal = world.journal_defs[journal_id]
            pulse = _field(_field(journal, "on_monthly_pulse"), "effect")
            if pulse_counts is not None:
                pulse_counts[source_slug] = pulse_counts.get(source_slug, 0) + 1
            world.active_journal = journal_id
            before = len(world.events)
            world.execute(pulse, "NMG")
            emitted = world.events[before:]
            del world.events[before:]
            for tag, event_id in emitted:
                if tag != "NMG":
                    raise AssertionError(("unexpected-pulse-recipient", tag, event_id))
                event = _event(world, event_id)
                gate = _field(event, "trigger", [])
                if gate and not world.conditions(gate, "NMG"):
                    continue
                row = _candidate(world, event_id)
                if row is None:
                    raise AssertionError(("eligible-real-popup-without-reservation", event_id,
                                          world.countries["NMG"]))
                if (source_slug == target_slug and event_id == target_event
                        and _candidate_kind(row["candidate"]) == target_kind):
                    return event_id, row
                _default_source_choice(world, event)
    raise AssertionError(("source-driven-target-popup-not-found", target_slug, target_event,
                          target_kind, world.countries["NMG"]))


def _natural_notice_world(slug, notice_kind):
    """Create a natural blocked clock using authored options and all live pulses."""
    world, evidence, order = _first_popup_world(slug)
    counts = {item: 0 for item in ARC_ORDER}
    if slug == ARC_ORDER[0]:
        # Land: real mixed route and fee, followed by an ordinary building loss.
        _pulse_all_until(world, order, slug, "ywc_nmg.1000", "normal", 3, counts)
        _receive(world, "ywc_nmg.1000", "mixed")
        world.countries["NMG"]["fixture_buildings"].pop("building_rye_farm", None)
        target_event = "ywc_nmg.1006" if notice_kind == "notice12" else "ywc_nmg.1007"
    elif slug == ARC_ORDER[1]:
        # Office: choose the authored bilingual route, then lose the ordinary
        # literacy condition. Existing paid/source history is retained.
        _pulse_all_until(world, order, slug, "ywc_nmg.1010", "normal", 3, counts)
        _receive(world, "ywc_nmg.1010", "bilingual")
        world.countries["NMG"]["literacy_rate"] = 0.2
        target_event = "ywc_nmg.1014" if notice_kind == "notice12" else "ywc_nmg.1015"
    else:
        # Revenue: authored fixed route/audit/account sequence first, then an
        # ordinary barracks loss while the paid route is open.
        for event_id, option in (("ywc_nmg.1020", "fixed"),
                                 ("ywc_nmg.1021", "audit_strict"),
                                 ("ywc_nmg.1022", "close_account")):
            _pulse_all_until(world, order, slug, event_id, "normal", 18, counts)
            _receive(world, event_id, option)
        world.countries["NMG"]["fixture_buildings"].pop("building_barrack", None)
        target_event = "ywc_nmg.1028" if notice_kind == "notice12" else "ywc_nmg.1029"

    # Wait on the complete, naturally aged 12/36-month source clock. Every
    # month includes all three admitted JE pulses and every incidental popup
    # is completed plus a legal authored option before the next one.
    max_wait = 20 if notice_kind == "notice12" else 50
    event_id, row = _pulse_all_until(world, order, slug, target_event, notice_kind, max_wait, counts)
    if not all(counts[item] for item in ARC_ORDER):
        raise AssertionError(("not-all-live-monthly-pulses-observed", counts))
    return world, evidence, event_id, row, order, counts


def _reservation(world, row, event_id):
    state = world.countries["NMG"]
    value = state.get(PREFIX + "_reservation")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value or value <= 0:
        raise AssertionError(("missing_real_reservation", event_id, value, state))
    reservation = int(value)
    epoch = state.get(PREFIX + "_reservation_epoch")
    if isinstance(epoch, bool) or not isinstance(epoch, (int, float)) or int(epoch) != epoch or epoch <= 0:
        raise AssertionError(("missing_positive_global_epoch", epoch, state))
    queue = row["candidate"]["queue"]
    candidate_epoch = state.get(f"{PREFIX}_candidate_epoch_{reservation}")
    if candidate_epoch != epoch:
        raise AssertionError(("candidate_epoch_not_bound", reservation, epoch, candidate_epoch))
    if queue not in state or state[queue] != row["candidate"]["value"]:
        raise AssertionError(("selected_source_queue_not_preserved", queue, row["candidate"], state))
    return reservation, epoch, queue


def _proof_names(reservation):
    return (f"{PREFIX}_callback_{reservation}",
            f"{PREFIX}_callback_candidate_{reservation}",
            f"{PREFIX}_callback_epoch_{reservation}",
            f"{PREFIX}_callback_queue_{reservation}")


def _assert_source_admission(test, world, evidence):
    test.assertEqual(len(evidence["root_admissions"]), 3)
    test.assertTrue(all(item["shown"] and item["possible"] for item in evidence["root_admissions"]))
    test.assertEqual(evidence["final_counts"], {"active": 3, "visible": 3})
    test.assertEqual(world.countries["NMG"].get("ywc_v03_active_arc_count"), 3)


class NmgTransportProvenanceRegression(unittest.TestCase):
    def test_notice_candidate_kind_uses_authored_shared_event_queue_values(self):
        """Derive notice/normal candidates from formal source AST, without adapter metadata."""
        source_candidates = []

        def flatten(nodes):
            for key, comparison, value in nodes:
                yield key, comparison, value
                if isinstance(value, list):
                    yield from flatten(value)

        def visit(nodes, limits=()):
            for key, _, value in nodes:
                if key in ("if", "else_if"):
                    limit = _field(value, "limit", [])
                    visit([node for node in value if node[0] != "limit"], limits + (limit,))
                elif key == "trigger_event":
                    event_id = _field(value, "id")
                    queue_checks = [
                        (condition_key[4:], int(condition_value))
                        for limit in limits
                        for condition_key, comparison, condition_value in flatten(limit)
                        if condition_key.startswith("var:ywc_nmg_")
                        and condition_key.endswith(("_pending", "_notice_pending"))
                        and comparison == "=" and str(condition_value).isdigit()
                    ]
                    for queue, queue_value in queue_checks:
                        if event_id == f"ywc_nmg.{queue_value}":
                            source_candidates.append({
                                "event": event_id,
                                "kind": "notice" if queue.endswith("_notice_pending") else "normal",
                                "queue": queue,
                                "value": queue_value,
                            })
                elif isinstance(value, list):
                    visit(value, limits)

        for arc in _catalog()["arcs"]:
            for journal in arc["journals"]:
                script = parse("wrapper = " + journal["script"])[0][2]
                for key, _, pulse in script:
                    if key == "on_monthly_pulse":
                        for pulse_key, _, body in pulse:
                            if pulse_key == "effect":
                                visit(body)

        expected_notices = {
            "ywc_nmg.1006": "notice12", "ywc_nmg.1007": "notice36",
            "ywc_nmg.1014": "notice12", "ywc_nmg.1015": "notice36",
            "ywc_nmg.1028": "notice12", "ywc_nmg.1029": "notice36",
        }
        derived_notices = {
            candidate["event"]: _candidate_kind(candidate)
            for candidate in source_candidates if candidate["kind"] == "notice"
        }
        self.assertEqual(expected_notices, derived_notices)
        self.assertTrue(any(candidate["event"] == "ywc_nmg.1006"
                            and candidate["kind"] == "normal"
                            for candidate in source_candidates),
                        "same-event normal queue control must be present in authored source AST")
        self.assertEqual("normal", _candidate_kind({"kind": "normal", "value": 1006}))

    def test_adapter_is_a_formal_per_arc_source_contract(self):
        """Check the feature at a real first-pulse boundary; absent imports are not used."""
        world, evidence = actual_nmg_admission_world(admission_order=ARC_ORDER)
        _assert_source_admission(self, world, evidence)
        arc = _catalog()["arcs"][0]
        journal = world.journal_defs[arc["journals"][0]["id"]]
        pulse = _field(_field(journal, "on_monthly_pulse"), "effect")
        world.advance_months(1)
        world.active_journal = arc["journals"][0]["id"]
        before = len(world.events)
        world.execute(pulse, "NMG")
        emitted = world.events[before:]
        self.assertEqual(len(emitted), 1, "real first source pulse did not emit its eligible first event")
        event_id = emitted[0][1]
        self.assertTrue(world.conditions(_field(_event(world, event_id), "trigger", []), "NMG"))
        state = world.countries["NMG"]
        self.assertIn(PREFIX + "_reservation", state,
                      f"real source popup {event_id} lacks a selected-candidate reservation")
        _require_adapter(self)
        for arc in _catalog()["arcs"]:
            adapter = arc["inline_delivery_adapter"]
            self.assertEqual(adapter.get("schema"), "v03.foundation_inline_adapter.v2")
            self.assertTrue(adapter.get("branches"), arc["slug"])

    def test_every_arc_real_normal_popup_runs_whole_immediate_and_source_ack(self):
        _require_adapter(self)
        for slug in ARC_ORDER:
            with self.subTest(arc=slug):
                world, evidence, event_id, row, _order = _start_real_popup(slug)
                _assert_source_admission(self, world, evidence)
                reservation, epoch, queue = _reservation(world, row, event_id)
                state = world.countries["NMG"]
                event = _event(world, event_id)
                self.assertTrue(world.conditions(_field(event, "trigger", []), "NMG"), event_id)
                before_ack = []
                original_run = world.run

                def observe_ack(name, tag="NMG"):
                    if name.startswith(PREFIX + "_ack_") and tag == "NMG":
                        before_ack.append(copy.deepcopy(state))
                    return original_run(name, tag)

                world.run = observe_ack
                world.execute(_field(event, "immediate", []), "NMG")
                self.assertEqual(len(before_ack), 1, (event_id, "whole immediate must invoke exactly one ACK"))
                at_ack = before_ack[0]
                self.assertEqual(at_ack.get(f"{PREFIX}_body_completed_{reservation}"), 1)
                self.assertEqual(at_ack.get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
                proof = _proof_names(reservation)
                self.assertEqual(tuple(at_ack.get(name) for name in proof),
                                 (1, reservation, epoch, row["candidate"]["value"]),
                                 "all four callback identity fields must come from the true whole-body ACK boundary")
                self.assertEqual(at_ack.get("ywc_v03_major_event_cooldown"), 1,
                                 "native body and cooldown must execute before ACK")
                self.assertNotIn(queue, state, "real ACK must consume the selected queue")
                self.assertNotIn(PREFIX + "_reservation", state)

    def test_callback_and_ack_without_real_body_or_old_last_event_cannot_mint_proof(self):
        _require_adapter(self)
        world, _evidence, event_id, row, _order = _start_real_popup(ARC_ORDER[0])
        reservation, epoch, queue = _reservation(world, row, event_id)
        state = world.countries["NMG"]
        arc = row["arc"]
        prefix = arc.get("inline_delivery_adapter", {}).get("prefix", PREFIX)
        last_event = row.get("last_event_variable")
        if not last_event:
            # Source native immediate identifies the historical receipt field.
            immediate = _field(_event(world, event_id), "immediate", [])
            last_event = _native_last_event_variable(immediate)
        before = copy.deepcopy(state)
        state[last_event] = float(event_id.rsplit(".", 1)[1])
        polluted_before = copy.deepcopy(state)
        proof_names = _proof_names(reservation)
        world.run(f"{prefix}_callback_{reservation}", "NMG")
        world.run(f"{prefix}_ack_{reservation}", "NMG")
        self.assertEqual(state, polluted_before, "old last_event plus bare helpers changed state")
        self.assertEqual(state[queue], row["candidate"]["value"])
        self.assertEqual(state.get(PREFIX + "_reservation_epoch"), epoch)
        self.assertFalse(set(proof_names).intersection(state))
        self.assertNotIn(f"{prefix}_body_completed_{reservation}", state)

    def test_native_immediate_fault_matrix_fails_closed_before_any_native_write(self):
        _require_adapter(self)
        faults = ("missing_global", "zero_global", "negative_global", "wrong_global",
                  "missing_candidate", "wrong_candidate", "missing_snapshot", "wrong_snapshot",
                  "missing_timer", "wrong_candidate_id", "lost_live_phase")
        for fault in faults:
            with self.subTest(fault=fault):
                world, _evidence, event_id, row, _order = _start_real_popup(ARC_ORDER[0])
                reservation, epoch, queue = _reservation(world, row, event_id)
                state = world.countries["NMG"]
                prefix = PREFIX
                snapshot = f"{prefix}_c{reservation}_{queue}"
                present_key, value_key = snapshot + "_present", snapshot + "_value"
                if fault == "missing_global": state.pop(prefix + "_reservation_epoch", None)
                elif fault == "zero_global": state[prefix + "_reservation_epoch"] = 0
                elif fault == "negative_global": state[prefix + "_reservation_epoch"] = -1
                elif fault == "wrong_global": state[prefix + "_reservation_epoch"] = epoch + 1
                elif fault == "missing_candidate": state.pop(f"{prefix}_candidate_epoch_{reservation}", None)
                elif fault == "wrong_candidate": state[f"{prefix}_candidate_epoch_{reservation}"] = epoch + 1
                elif fault == "missing_snapshot": state.pop(value_key, None)
                elif fault == "wrong_snapshot": state[value_key] = float(state[queue]) + 1
                elif fault == "missing_timer": state.pop(prefix + "_timer", None)
                elif fault == "wrong_candidate_id": state[prefix + "_reservation"] = reservation + 999
                elif fault == "lost_live_phase":
                    live = next(item["live_witness"] for item in row["arc"]["inline_delivery_adapter"]["live_phases"]
                                if item["journal"] == row["branch"]["journal"])
                    state.pop(live, None)
                before = copy.deepcopy(state)
                event = _event(world, event_id)
                self.assertFalse(world.conditions(_field(event, "trigger", []), "NMG"),
                                 f"{fault} admitted invalid actual source delivery")
                world.execute(_field(event, "immediate", []), "NMG")
                self.assertEqual(state, before, f"{fault} let real immediate mutate NMG state")

    def test_old_last_event_alone_is_not_a_delivery_proof(self):
        _require_adapter(self)
        world, _evidence, event_id, row, _order = _start_real_popup(ARC_ORDER[0])
        reservation, _epoch, queue = _reservation(world, row, event_id)
        state = world.countries["NMG"]
        native = _event(world, event_id)
        immediate = _field(native, "immediate", [])
        last_event = _native_last_event_variable(immediate)
        state[last_event] = float(event_id.rsplit(".", 1)[1])
        before = copy.deepcopy(state)
        world.run(f"{PREFIX}_callback_{reservation}", "NMG")
        world.run(f"{PREFIX}_ack_{reservation}", "NMG")
        self.assertEqual(state, before)
        self.assertIn(queue, state)

    def test_native_whole_body_ack_fault_retains_native_writes_and_cooldown(self):
        _require_adapter(self)
        world, _evidence, event_id, row, _order, _counts = _natural_notice_world(
            ARC_ORDER[0], "notice12")
        reservation, epoch, queue = _reservation(world, row, event_id)
        state = world.countries["NMG"]
        native = _event(world, event_id)
        immediate = _field(native, "immediate", [])
        short = "land"
        notice_kind = _candidate_kind(row["candidate"])
        native_names = [f"ywc_nmg_{short}_{notice_kind}_due",
                        f"ywc_nmg_{short}_{notice_kind}_delivered",
                        f"ywc_nmg_{short}_notice_response_context",
                        f"ywc_nmg_{short}_notice_return_event",
                        f"ywc_nmg_{short}_last_event",
                        "ywc_v03_major_event_cooldown", queue]
        ack = f"{PREFIX}_ack_{reservation}"
        original_run = world.run
        seen = []

        def fault_at_real_ack(name, tag="NMG"):
            if name == ack and tag == "NMG":
                seen.append(copy.deepcopy(state))
                state.pop(f"{PREFIX}_callback_{reservation}", None)
                state.pop(PREFIX + "_reservation_epoch", None)
            return original_run(name, tag)

        world.run = fault_at_real_ack
        world.execute(immediate, "NMG")
        self.assertEqual(len(seen), 1, "actual native notice immediate did not reach ACK boundary")
        at_ack = seen[0]
        self.assertEqual(at_ack.get(f"{PREFIX}_body_completed_{reservation}"), 1)
        self.assertEqual(at_ack.get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
        self.assertEqual({name: (name in state, state.get(name)) for name in native_names},
                         {name: (name in at_ack, at_ack.get(name)) for name in native_names},
                         "failed post-body ACK must preserve every native write at the true ACK boundary")
        self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1)
        self.assertEqual(state.get(queue), row["candidate"]["value"], "failed ACK consumed notice queue")

    def test_real_old_body_proof_replay_is_rejected_after_same_candidate_90_day_retry(self):
        _require_adapter(self)
        slug = ARC_ORDER[0]
        world, _evidence, first_event_id, first_row, order = _start_real_popup(slug, kind="normal")
        first_id, first_epoch, queue = _reservation(world, first_row, first_event_id)
        state = world.countries["NMG"]
        first_event = _event(world, first_event_id)
        first_proof_names = _proof_names(first_id)
        first_candidate_epoch = f"{PREFIX}_candidate_epoch_{first_id}"
        old_ack = f"{PREFIX}_ack_{first_id}"
        captured = []
        original_run = world.run

        def reject_first_real_ack(name, tag="NMG"):
            if name == old_ack and tag == "NMG":
                captured.append({key: state[key] for key in first_proof_names if key in state})
                self.assertEqual(len(captured[-1]), 4,
                                 "captured proof must be emitted by the actual completed first body")
                state[first_candidate_epoch] = first_epoch + 1
            return original_run(name, tag)

        world.run = reject_first_real_ack
        world.execute(_field(first_event, "immediate", []), "NMG")
        self.assertEqual(len(captured), 1)
        self.assertEqual(state.get(queue), first_row["candidate"]["value"])
        self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1)
        world.run = original_run
        # Restore only the controlled epoch mutation. Then take the real legal
        # wait route so the same authored source queue remains available.
        state[first_candidate_epoch] = first_epoch
        wait = _legal_option(world, first_event, "wait_for_funds")
        self.assertIsNotNone(wait, (first_event_id, state))
        _execute_option(world, wait)
        world.events.clear()

        elapsed = 0
        cooldown = []
        advance_days = world.advance_days

        def observe_actual_calendar(days=1):
            nonlocal elapsed
            advance_days(days)
            elapsed += days
            if days == 30:
                cooldown.append((elapsed, "ywc_v03_major_event_cooldown" in state))

        world.advance_days = observe_actual_calendar
        try:
            retry_event_id, retry_row = _pulse_all_until(
                world, order, slug, first_event_id, "normal", 9)
        finally:
            world.advance_days = advance_days
        self.assertEqual(cooldown[:3], [(30, True), (60, True), (90, False)],
                         "natural source retry must observe the actual 30/60/90-day cooldown")
        retry_id, retry_epoch, retry_queue = _reservation(world, retry_row, retry_event_id)
        self.assertEqual(retry_id, first_id, "same source branch should reuse its actual candidate id")
        self.assertGreater(retry_epoch, first_epoch)
        self.assertEqual(retry_queue, queue)
        self.assertEqual(state[retry_queue], retry_row["candidate"]["value"])

        # Replay only values captured at the first true world.run(ACK) boundary.
        state.update(captured[0])
        stale_snapshot = {name: state[name] for name in first_proof_names}
        before_replay = copy.deepcopy(state)
        world.run(f"{PREFIX}_callback_{first_id}", "NMG")
        self.assertEqual({name: state.get(name) for name in first_proof_names}, stale_snapshot,
                         "stale callback may not rewrite proof for the new epoch")
        world.run(old_ack, "NMG")
        self.assertEqual(state.get(PREFIX + "_reservation"), retry_id)
        self.assertEqual(state.get(retry_queue), retry_row["candidate"]["value"])
        arc_number = next(index for index, arc in enumerate(_catalog()["arcs"], 1) if arc["slug"] == slug)
        self.assertNotEqual(state.get(f"{PREFIX}_served_{arc_number}"),
                            state.get(PREFIX + "_round"),
                            "old same-ID proof must not serve the current round")

        fresh_event = _event(world, retry_event_id)
        world.execute(_field(fresh_event, "immediate", []), "NMG")
        self.assertNotIn(retry_queue, state, "fresh complete body proof should authorize the new ACK")
        self.assertNotIn(PREFIX + "_reservation", state)
        self.assertNotEqual(state, before_replay)

    def test_expired_known_bad_epochs_cleanup_and_unknown_slots_preserve_native_state(self):
        _require_adapter(self)
        for fault in ("missing_epoch", "zero_epoch", "negative_epoch", "wrong_epoch"):
            with self.subTest(fault=fault):
                world, _evidence, event_id, row, _order, _counts = _natural_notice_world(
                    ARC_ORDER[0], "notice12")
                reservation, epoch, queue = _reservation(world, row, event_id)
                state = world.countries["NMG"]
                event = _event(world, event_id)
                native = _field(event, "immediate", [])
                native_names = sorted({name for name in state if name.startswith("ywc_nmg_")}
                                      | {"ywc_v03_major_event_cooldown"})
                if fault == "missing_epoch": state.pop(PREFIX + "_reservation_epoch", None)
                elif fault == "zero_epoch": state[PREFIX + "_reservation_epoch"] = 0
                elif fault == "negative_epoch": state[PREFIX + "_reservation_epoch"] = -1
                else: state[PREFIX + "_reservation_epoch"] = epoch + 1
                before_native = {name: (name in state, state.get(name)) for name in native_names}
                timer_key = PREFIX + "_timer"
                day_remaining = world.days_until_expiry["NMG"].get(timer_key)
                month_remaining = world.months_until_expiry["NMG"].get(timer_key)
                self.assertTrue(day_remaining is not None or month_remaining is not None,
                                "reservation timer has no authored harness expiry")
                if day_remaining is not None:
                    world.advance_days(day_remaining)
                else:
                    world.advance_months(month_remaining)
                world.run(PREFIX + "_prepare", "NMG")
                self.assertNotIn(PREFIX + "_reservation", state)
                self.assertNotIn(PREFIX + "_timer", state)
                self.assertEqual({name: (name in state, state.get(name)) for name in native_names}, before_native)
                self.assertEqual(state.get(queue), row["candidate"]["value"])

        # Unknown 0/-1/999 identifiers are deliberately exercised only through
        # source cleanup; they must not own any source/native state.
        for unknown in (0, -1, 999):
            world, _evidence, event_id, row, _order, _counts = _natural_notice_world(
                ARC_ORDER[0], "notice12")
            state = world.countries["NMG"]
            queue = row["candidate"]["queue"]
            native_snapshot = {key: copy.deepcopy(value) for key, value in state.items()
                               if key.startswith("ywc_nmg_") or key == "ywc_v03_major_event_cooldown"}
            state[PREFIX + "_reservation"] = unknown
            state[PREFIX + "_timer"] = 1
            world.days_until_expiry.setdefault("NMG", {})[PREFIX + "_timer"] = 1
            world.advance_days(1)
            world.run(PREFIX + "_prepare", "NMG")
            self.assertEqual({key: value for key, value in state.items()
                              if key.startswith("ywc_nmg_") or key == "ywc_v03_major_event_cooldown"},
                             native_snapshot)
            self.assertIn(queue, state)

    def test_real_notice_and_natural_retry_matrix_is_source_pulsed(self):
        """Notice coverage is intentionally anchored to all admitted JEs, not a target-only pulse."""
        _require_adapter(self)
        for slug in ARC_ORDER:
            for kind, expected_due in (("notice12", "notice12_due"), ("notice36", "notice36_due")):
                with self.subTest(arc=slug, kind=kind):
                    world, evidence, event_id, row, order, pulse_counts = _natural_notice_world(slug, kind)
                    _assert_source_admission(self, world, evidence)
                    self.assertEqual(order, (slug,) + tuple(x for x in ARC_ORDER if x != slug))
                    self.assertTrue(all(pulse_counts[arc] > 0 for arc in ARC_ORDER))
                    reservation, _epoch, queue = _reservation(world, row, event_id)
                    state = world.countries["NMG"]
                    short = {ARC_ORDER[0]: "land", ARC_ORDER[1]: "office", ARC_ORDER[2]: "revenue"}[slug]
                    due = f"ywc_nmg_{short}_{expected_due}"
                    delivered = due.removesuffix("_due") + "_delivered"
                    context = f"ywc_nmg_{short}_notice_response_context"
                    return_event = f"ywc_nmg_{short}_notice_return_event"
                    last_event = f"ywc_nmg_{short}_last_event"
                    self.assertEqual(_candidate_kind(row["candidate"]), kind)
                    self.assertEqual(state.get(due), 1)
                    old_last_event = state.get(last_event)
                    native = _event(world, event_id)
                    world.execute(_field(native, "immediate", []), "NMG")
                    self.assertNotIn(queue, state, "notice ACK must consume its exact source queue")
                    self.assertNotIn(due, state, "native notice immediate must consume its due marker")
                    self.assertEqual(state.get(delivered), 1)
                    self.assertEqual(state.get(context), 1)
                    self.assertEqual(state.get(return_event), old_last_event,
                                     "notice body must retain native source last_event in return_event")
                    self.assertEqual(state.get(last_event), int(event_id.rsplit(".", 1)[1]))
                    self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1)
                    self.assertNotIn(PREFIX + "_reservation", state)
                    suffix = {
                        (ARC_ORDER[0], "notice12"): "renegotiate",
                        (ARC_ORDER[0], "notice36"): "settle_partial",
                        (ARC_ORDER[1], "notice12"): "keep_route",
                        (ARC_ORDER[1], "notice36"): "close_partial",
                        (ARC_ORDER[2], "notice12"): "own_arrears",
                        (ARC_ORDER[2], "notice36"): "wait_retry",
                    }[(slug, kind)]
                    option = _legal_option(world, native, suffix)
                    self.assertIsNotNone(option, (event_id, suffix, state))
                    _execute_option(world, option)

    def test_same_event_normal_control_has_no_notice_due_context(self):
        _require_adapter(self)
        # Reach the authored shared land event 1006 before the blocked-clock
        # notice is due; the candidate queue must distinguish normal from notice.
        slug = ARC_ORDER[0]
        world, _evidence, order = _first_popup_world(slug)
        counts = {item: 0 for item in ARC_ORDER}
        for event_id, option in (("ywc_nmg.1000", "mixed"),
                                 ("ywc_nmg.1001", "rule_register"),
                                 ("ywc_nmg.1002", "finish_survey"),
                                 ("ywc_nmg.1003", "keep_old"),
                                 ("ywc_nmg.1004", "keep_recording"),
                                 ("ywc_nmg.1005", "old_assessment")):
            _pulse_all_until(world, order, slug, event_id, "normal", 24, counts)
            _receive(world, event_id, option)
        event_id, row = _pulse_all_until(world, order, slug, "ywc_nmg.1006", "normal", 24, counts)
        reservation, _epoch, queue = _reservation(world, row, event_id)
        state = world.countries["NMG"]
        self.assertEqual(event_id, "ywc_nmg.1006")
        self.assertEqual(_candidate_kind(row["candidate"]), "normal")
        self.assertEqual(state[queue], row["candidate"]["value"])
        self.assertFalse(any(key.endswith(("notice12_due", "notice36_due")) for key in state))
        native = _event(world, event_id)
        old_last_event = state.get("ywc_nmg_land_last_event")
        world.execute(_field(native, "immediate", []), "NMG")
        self.assertNotIn(queue, state)
        self.assertNotIn(PREFIX + "_reservation", state)
        self.assertEqual(state.get("ywc_nmg_land_last_event"), 1006)
        self.assertNotIn("ywc_nmg_land_notice_response_context", state)
        self.assertEqual(state.get("ywc_nmg_land_notice_return_event"), old_last_event,
                         "native shared immediate unconditionally snapshots the previous last_event")
        self.assertNotEqual(old_last_event, 1006)


if __name__ == "__main__":
    unittest.main()
