"""Permanent source-driven NMG story contracts on the real admission world.

The authored-source harness is not the Clausewitz engine. These checks begin at
real NMG country history, execute the six legacy events, initialization, and all
three root JEs; only the ordinary engine-owned fixture facts are supplied by
the actual-admission factory.
"""
from __future__ import annotations

import hashlib
import itertools
import unittest
from pathlib import Path

from tests.test_v03_nmg_actual_fairness import actual_nmg_admission_world
from tests import test_v03_nmg_foundation_lifecycle as base
from tests.test_v03_nmg_inline_adapter import catalog as nmg_inline_catalog
from tools.v03_inline_delivery_adapter import _queue_snapshot_name

ROOT = Path(__file__).resolve().parents[1]
ARCS = ("land", "office", "revenue")
ADMISSION_SLUG = {"land": "v03_nmg_land_arbitration",
                  "office": "v03_nmg_bilingual_office",
                  "revenue": "v03_nmg_autonomy_revenue"}
ARC_JES = {
    "land": ("ywc_je_v03_nmg_land_arbitration", "ywc_je_v03_nmg_land_settlement"),
    "office": ("ywc_je_v03_nmg_bilingual_office",),
    "revenue": ("ywc_je_v03_nmg_revenue_opening", "ywc_je_v03_nmg_revenue_negotiation",
                "ywc_je_v03_nmg_revenue_settlement"),
}
ROUTES = {
    "land": ("mixed", "rule_register", "finish_survey", "keep_old", "keep_recording",
             "old_assessment", "renegotiate", "settle_partial"),
    "office": ("bilingual", "hire_full", "court_parish", "fund_schools", "keep_route",
               "wait_retry", "close_full"),
    "revenue": ("fixed", "audit_strict", "close_account", "press_quota", "use_temperature",
                "carry_heavy", "conclude", "wait_retry", "wait_retry", "settle_full"),
}
NOTICE_OPTIONS = {
    ("land", 1006): "renegotiate", ("land", 1007): "settle_partial",
    ("office", 1014): "keep_route", ("office", 1015): "wait_retry",
    ("revenue", 1028): "own_arrears", ("revenue", 1029): "wait_retry",
}
PULSE_ORDERS = tuple(itertools.permutations(ARCS))
NOTICE_EVENT_THRESHOLD = {
    ("land", 1006): 12, ("land", 1007): 36,
    ("office", 1014): 12, ("office", 1015): 36,
    ("revenue", 1028): 12, ("revenue", 1029): 36,
}
PAID_EVENT = {"land": 1000, "office": 1010, "revenue": 1020}
SOURCE_PATHS = (
    "data/content/v03/countries/nmg.json",
    "yongchang_world/common/history/countries/ywc_content_starts.txt",
    "yongchang_world/common/journal_entries/ywc_nmg.txt",
    "yongchang_world/common/journal_entries/ywc_v03_country_nmg_journal.txt",
    "yongchang_world/common/scripted_effects/ywc_v03_nmg_effects.txt",
    "yongchang_world/common/scripted_effects/ywc_v03_effects.txt",
    "yongchang_world/common/scripted_effects/ywc_campaign_effects.txt",
    "yongchang_world/common/scripted_effects/ywc_flavor_effects.txt",
    "yongchang_world/common/scripted_effects/ywc_shared_effects.txt",
    "yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt",
    "yongchang_world/common/scripted_triggers/ywc_v03_nmg_triggers.txt",
    "yongchang_world/events/ywc_kor_lan_nmg_events.txt",
    "yongchang_world/events/ywc_large_campaign_events.txt",
    "yongchang_world/events/ywc_v03_country_nmg_events.txt",
)
OPTIONAL_SOURCE_PATHS = (
    "yongchang_world/common/scripted_effects/ywc_v03_delivery_nmg_effects.txt",
    "yongchang_world/common/scripted_triggers/ywc_v03_delivery_nmg_triggers.txt",
    "yongchang_world/events/ywc_v03_delivery_nmg_events.txt",
)


def _pins():
    paths = SOURCE_PATHS + tuple(path for path in OPTIONAL_SOURCE_PATHS if (ROOT / path).is_file())
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}


def _candidate_metadata(candidate_id):
    candidates = [candidate for arc_row in nmg_inline_catalog()["arcs"]
                  for branch in arc_row.get("inline_delivery_adapter", {}).get("branches", [])
                  for candidate in branch.get("candidates", [])]
    if candidate_id < 1 or candidate_id > len(candidates):
        raise AssertionError(("candidate_id_out_of_catalog_range", candidate_id, len(candidates)))
    return candidates[candidate_id - 1]


def _classify_notice(arc, event_id, country, require_transport, source_queue=None):
    number = int(event_id.rsplit(".", 1)[1])
    expected_threshold = NOTICE_EVENT_THRESHOLD.get((arc, number))
    candidate = country.get("ywc_v03_nmg_inline_reservation")
    if require_transport and candidate is not None:
        metadata = _candidate_metadata(int(candidate))
        queue = metadata["queue"]
        if not queue.startswith(f"ywc_nmg_{arc}_"):
            raise AssertionError(("reserved_candidate_wrong_arc", arc, event_id, candidate, metadata))
        is_notice = metadata.get("kind") == "notice" or queue.endswith("_notice_pending")
        if is_notice and expected_threshold is None:
            raise AssertionError(("reserved_candidate_kind_disagrees_with_popup", arc, event_id,
                                  candidate, metadata, expected_threshold))
        return is_notice

    # The authored source consumes its queue before the popup. Observe the real
    # queue removal that led to trigger_event, which disambiguates IDs also used
    # by normal routes (notably office 1014/1015).
    if source_queue is None or not source_queue.startswith(f"ywc_nmg_{arc}_"):
        raise AssertionError(("source_popup_lacks_observed_queue_branch", arc, event_id, source_queue))
    is_notice = source_queue.endswith("_notice_pending")
    if is_notice and expected_threshold is None:
        raise AssertionError(("notice_queue_emitted_non_notice_event", arc, event_id, source_queue))
    return is_notice


def _execute_pulse_observing_queue(world, pulse, arc):
    """Capture the native queue removed for each emitted event during this pulse."""
    country = world.countries["NMG"]
    queue_names = (f"ywc_nmg_{arc}_pending", f"ywc_nmg_{arc}_notice_pending")
    removals = []
    event_queues = {}
    original_execute = world.execute

    def observing_execute(nodes, tag):
        before_events = len(world.events)
        before_queues = {name: country[name] for name in queue_names if name in country}
        result = original_execute(nodes, tag)
        for name, value in before_queues.items():
            if name not in country:
                removals.append((name, value))
        for _event_tag, event_id in world.events[before_events:]:
            number = int(event_id.rsplit(".", 1)[1])
            match_index = next((i for i in range(len(removals) - 1, -1, -1)
                                if removals[i][1] == number), None)
            if match_index is not None:
                queue, _value = removals.pop(match_index)
                event_queues.setdefault(event_id, queue)
        return result

    try:
        world.execute = observing_execute
        world.execute(pulse, "NMG")
    finally:
        world.execute = original_execute
    return event_queues


def _field(nodes, name):
    return base.field(nodes, name)


def _pulse(entry):
    return _field(_field(entry, "on_monthly_pulse"), "effect")


def _event_arc(event_id):
    number = int(event_id.rsplit(".", 1)[1])
    return "land" if 1000 <= number <= 1007 else "office" if 1010 <= number <= 1015 else "revenue"


def _option_nodes(event):
    return [body for key, _, body in event if key == "option"]


def _option_name(option):
    return _field(option, "name").rsplit(".", 1)[-1]


def _event_choices(world, event_id, arc, index, notice, choice_override=None):
    event = world.event_defs[event_id]
    options = _option_nodes(event)
    legal = []
    for option in options:
        trigger = next((body for key, _, body in option if key == "trigger"), [])
        if not trigger or world.conditions(trigger, "NMG"):
            legal.append(_option_name(option))
    wanted = choice_override
    if wanted is None:
        wanted = NOTICE_OPTIONS.get((arc, int(event_id.rsplit(".", 1)[1]))) if notice else None
    if wanted is None:
        if index >= len(ROUTES[arc]):
            raise AssertionError(("authored_story_route_exhausted", arc, event_id, index, legal))
        wanted = ROUTES[arc][index]
    if wanted not in legal:
        raise AssertionError(("planned_route_option_not_legal", arc, event_id, wanted, legal, index))
    return event, options, legal, wanted


def _dispatch(world, event_id, arc, day, route_index, *, notice=False, choice_override=None,
              require_transport=True):
    """Execute the complete real event body, require source ACK, then choose a legal option."""
    event = world.event_defs[event_id]
    country = world.countries["NMG"]
    trigger = next((body for key, _, body in event if key == "trigger"), [])
    if trigger and not world.conditions(trigger, "NMG"):
        raise AssertionError(("source_event_trigger_false", event_id, day))

    prefix = "ywc_v03_nmg_inline"
    reservation_name = prefix + "_reservation"
    reservation = country.get(reservation_name)
    candidate = int(reservation) if reservation is not None else None
    ack_name = f"{prefix}_ack_{candidate}" if candidate is not None else None
    round_prefix = prefix + "_round"
    arc_number = ARCS.index(arc) + 1
    served_name = f"{prefix}_served_{arc_number}"
    lane = f"ywc_nmg_{arc}"
    queue_name = lane + ("_notice_pending" if notice else "_pending")
    snapshot_present = _queue_snapshot_name(candidate, queue_name, "present", prefix) if candidate else None
    snapshot_value = _queue_snapshot_name(candidate, queue_name, "value", prefix) if candidate else None
    captured_epoch = country.get(prefix + "_reservation_epoch")
    captured_round = country.get(round_prefix)
    captured_queue = country.get(queue_name)
    captured_snapshot = {
        "present": country.get(snapshot_present) if snapshot_present else None,
        "value": country.get(snapshot_value) if snapshot_value else None,
        "candidate_epoch": country.get(prefix + f"_candidate_epoch_{candidate}"),
    }
    number = int(event_id.rsplit(".", 1)[1])
    before_body = dict(country)
    ack_witnesses = []
    named_calls_before = len(world.named_effect_calls)
    original_run = world.run

    def witness_run(name, tag="NMG"):
        if name == ack_name:
            state = dict(country)
            # The callback must be reached from the whole authored immediate;
            # notice ACK is valid only after its real due marker was consumed.
            if state.get(lane + "_last_event") != number:
                raise AssertionError(("ack_before_full_event_body", event_id, candidate, state))
            if notice:
                threshold = 12 if number in (1006, 1014, 1028) else 36
                if (state.get(lane + f"_notice{threshold}_delivered") != 1
                        or state.get(lane + "_notice_response_context") != 1
                        or lane + f"_notice{threshold}_due" in state):
                    raise AssertionError(("notice_ack_not_after_delivery_body", event_id, state))
            if require_transport:
                expected_snapshot = {
                    "present": 1,
                    "value": number,
                    "candidate_epoch": captured_epoch,
                }
                if captured_queue != number or captured_epoch is None or captured_round is None:
                    raise AssertionError(("FEATURE_RED: reservation_snapshot_or_round_missing_before_ack",
                                          event_id, captured_queue, captured_epoch, captured_round,
                                          captured_snapshot))
                if captured_snapshot != expected_snapshot:
                    raise AssertionError(("FEATURE_RED: candidate_queue_snapshot_mismatch_before_ack",
                                          event_id, captured_snapshot, expected_snapshot))
                if state.get("ywc_v03_nmg_inline_reservation_epoch") != captured_epoch:
                    raise AssertionError(("FEATURE_RED: reservation_epoch_changed_before_ack",
                                          event_id, captured_epoch, state))
                if state.get(prefix + f"_candidate_epoch_{candidate}") != captured_epoch:
                    raise AssertionError(("FEATURE_RED: candidate_epoch_mismatch_at_ack",
                                          event_id, captured_epoch, state))
                if state.get(queue_name) != number:
                    raise AssertionError(("FEATURE_RED: selected_queue_not_retained_through_body",
                                          event_id, queue_name, state.get(queue_name), number))
                if state.get(round_prefix) != captured_round:
                    raise AssertionError(("FEATURE_RED: dispatch_round_changed_during_body",
                                          event_id, captured_round, state))
            ack_witnesses.append((name, state))
        return original_run(name, tag)

    immediate = next((body for key, _, body in event if key == "immediate"), [])
    if not immediate:
        raise AssertionError(("native_event_missing_immediate", event_id))
    try:
        world.run = witness_run
        world.execute(immediate, "NMG")
    finally:
        world.run = original_run
    after_body = dict(country)
    if country.get(lane + "_last_event") != number:
        raise AssertionError(("whole_immediate_did_not_record_last_event", event_id, after_body))
    event, options, legal, wanted = _event_choices(world, event_id, arc, route_index, notice, choice_override)
    if not legal:
        raise AssertionError(("native_popup_has_no_legal_option", event_id, day))
    if require_transport and candidate is None:
        raise AssertionError(("FEATURE_RED: native_story_popup_has_no_source_reservation",
                              event_id, arc, day, after_body, legal))
    if require_transport and not any(name == ack_name for name, _ in ack_witnesses):
        raise AssertionError(("FEATURE_RED: actual_whole_immediate_did_not_call_candidate_ack",
                              event_id, candidate, before_body, after_body))
    named_calls = world.named_effect_calls[named_calls_before:]
    if require_transport:
        if reservation_name in after_body:
            raise AssertionError(("ack_did_not_release_native_reservation", event_id, candidate, after_body))
        if queue_name in after_body:
            raise AssertionError(("ack_did_not_consume_selected_queue_before_option",
                                  event_id, queue_name, after_body))
        if after_body.get(served_name) != captured_round:
            raise AssertionError(("FEATURE_RED: served_round_not_recorded_by_ack", event_id,
                                  served_name, captured_round, after_body.get(served_name)))
        if ack_name not in named_calls:
            raise AssertionError(("FEATURE_RED: whole_body_ack_absent_from_named_effect_calls",
                                  event_id, ack_name, named_calls))
        if any(key.startswith(prefix + "_timer") for key in after_body):
            raise AssertionError(("ack_did_not_release_native_timer", event_id, after_body))
        candidate_snapshot_names = {
            _queue_snapshot_name(candidate, queue_name, "present", prefix),
            _queue_snapshot_name(candidate, queue_name, "value", prefix),
            prefix + f"_candidate_epoch_{candidate}",
        }
        candidate_state = sorted(candidate_snapshot_names.intersection(after_body))
        if candidate_state:
            raise AssertionError(("ack_did_not_release_candidate_snapshot_or_proof_state",
                                  event_id, candidate_state, after_body))

    option = next(option for option in options if _option_name(option) == wanted)
    gate = next((body for key, _, body in option if key == "trigger"), [])
    if gate and not world.conditions(gate, "NMG"):
        raise AssertionError(("chosen_option_not_legal", event_id, wanted, legal))
    effects = [node for node in option if node[0] not in
               ("name", "trigger", "ai_chance", "default_option", "custom_tooltip")]
    world.execute(effects, "NMG")
    return {"day": day, "event": event_id, "arc": arc, "candidate": candidate,
            "notice": notice, "transport_contract": "required" if require_transport else "source_only_no_transport_claim",
            "complete_immediate": True, "last_event_after_body": country[lane + "_last_event"],
            "ack_calls": len(ack_witnesses), "ack_named_calls": named_calls,
            "captured_round": captured_round, "captured_epoch": captured_epoch,
            "legal_options": legal, "selected_option": wanted,
            "notice_return_event": (int(after_body[lane + "_notice_return_event"])
                                     if notice and lane + "_notice_return_event" in after_body else None),
            "after_body": after_body, "after_option": dict(country)}


def _refresh_handoff(world, arc, current, seen, terminal_status, terminal_hooks, handoffs):
    jid = current[arc]
    if jid is None:
        return
    je = world.journal_defs[jid]
    complete = world.conditions(_field(je, "complete"), "NMG")
    failed = world.conditions(_field(je, "fail"), "NMG")
    if complete and failed:
        raise AssertionError(("journal_both_complete_and_failed", jid))
    if not (complete or failed):
        return
    terminal_status[arc][jid] = "complete" if complete else "failed"
    terminal = "on_complete" if complete else "on_fail"
    hook = next((body for key, _, body in je if key == terminal), None)
    if hook is not None:
        country = world.countries["NMG"]
        witnesses = tuple(sorted(value for key, _, value in hook
                                 if key == "remove_variable"
                                 and isinstance(value, str)
                                 and value.startswith("ywc_v03_nmg_inline_live_")))
        before = {name: name in country for name in witnesses}
        world.execute(hook, "NMG")
        after = {name: name in country for name in witnesses}
        terminal_hooks[arc].setdefault(jid, []).append({
            "hook": terminal, "witnesses_before": before, "witnesses_after": after,
        })
    world.active_journals.discard(jid)
    sequence = ARC_JES[arc]
    next_id = sequence[sequence.index(jid) + 1] if complete and sequence.index(jid) + 1 < len(sequence) else None
    if next_id is None:
        current[arc] = None
        return
    next_je = world.journal_defs[next_id]
    if not (world.conditions(_field(next_je, "is_shown_when_inactive"), "NMG")
            and world.conditions(_field(next_je, "possible"), "NMG")):
        raise AssertionError(("authored_handoff_not_legal", jid, next_id))
    world.execute(_field(next_je, "immediate"), "NMG")
    world.active_journals.add(next_id)
    current[arc] = next_id
    seen[arc].add(next_id)
    handoffs[arc].append((jid, next_id))


def run_nmg_story(order=ARCS, max_months=600, *, stop_at_five=False, block_facts=False,
                  require_transport=True):
    world, admission = actual_nmg_admission_world(admission_order=tuple(ADMISSION_SLUG[arc] for arc in order))
    country = world.countries["NMG"]
    current = {arc: ARC_JES[arc][0] for arc in ARCS}
    route_index = {arc: 0 for arc in ARCS}
    normal_choices = {arc: {} for arc in ARCS}
    replay_choices = {arc: {} for arc in ARCS}
    seen = {arc: {current[arc]} for arc in ARCS}
    terminal_status = {arc: {} for arc in ARCS}
    terminal_hooks = {arc: {} for arc in ARCS}
    handoffs = {arc: [] for arc in ARCS}
    counts = {arc: 0 for arc in ARCS}
    paid_days = {}
    event_days = {arc: [] for arc in ARCS}
    recipients = []
    trace = []
    monthly_pulse_audit = []
    blocked = set()
    notices = {arc: {} for arc in ARCS}
    recovery_day = None
    helper_clean = set()
    recovery_popups = set()
    for month in range(1, max_months + 1):
        world.advance_months(1)
        day = month * 30
        if require_transport:
            pulse_order = tuple(order)
        else:
            pulse_order = PULSE_ORDERS[(PULSE_ORDERS.index(tuple(order)) + (month - 1) // 3) % len(PULSE_ORDERS)]
        active_at_start = {arc: jid for arc, jid in current.items() if jid is not None}
        pulsed_this_month = []
        fairness_reached = False
        for arc in pulse_order:
            jid = current[arc]
            if jid is None:
                continue
            pulse = _pulse(world.journal_defs[jid])
            pulsed_this_month.append((arc, jid))
            start = len(world.events)
            world.active_journal = jid
            source_queues = _execute_pulse_observing_queue(world, pulse, arc)
            after_pulse = dict(country)
            emitted = world.events[start:]
            if len(emitted) > 1:
                raise AssertionError(("source_je_emitted_multiple_events", month, arc, emitted))
            row = {"month": month, "day": day, "arc": arc, "je": jid, "events": [x[1] for x in emitted]}
            row["source_queues"] = source_queues
            trace.append(row)
            if not emitted:
                continue
            tag, event_id = emitted[0]
            if tag != "NMG" or _event_arc(event_id) != arc:
                raise AssertionError(("popup_wrong_recipient_or_arc", arc, tag, event_id, month))
            del world.events[start:]
            number = int(event_id.rsplit(".", 1)[1])
            notice = _classify_notice(arc, event_id, country, require_transport,
                                      source_queue=source_queues.get(event_id))
            replay = not notice and number in replay_choices[arc]
            choice_override = replay_choices[arc].pop(number, None) if replay else None
            observation = _dispatch(world, event_id, arc, day, route_index[arc], notice=notice,
                                    choice_override=choice_override, require_transport=require_transport)
            row["observation"] = observation
            if notice:
                threshold = NOTICE_EVENT_THRESHOLD[(arc, number)]
                notices[arc][threshold] = observation
            counts[arc] += 1
            event_days[arc].append(day)
            recipients.append(day)
            if number == PAID_EVENT[arc] and arc not in paid_days:
                paid_days[arc] = day
            if notice:
                return_event = observation["notice_return_event"]
                if return_event is not None and return_event in normal_choices[arc]:
                    replay_choices[arc][return_event] = normal_choices[arc][return_event]
            else:
                normal_choices[arc][number] = observation["selected_option"]
                if not replay:
                    route_index[arc] += 1
            block_event = {"land": 1000, "office": 1010, "revenue": 1022}[arc]
            if block_facts and number == block_event and arc not in blocked:
                if arc == "land":
                    country["fixture_buildings"].pop("building_rye_farm", None)
                elif arc == "office":
                    country["fixture_buildings"].pop("building_government_administration", None)
                elif arc == "revenue":
                    # `1022 close_account` must be selected before removing barracks;
                    # this routine waits for that real source node to do so.
                    country["fixture_buildings"].pop("building_barrack", None)
                blocked.add(arc)
            if recovery_day is not None and day > recovery_day:
                recovery_popups.add(arc)
            _refresh_handoff(world, arc, current, seen, terminal_status, terminal_hooks, handoffs)
            if block_facts and recovery_day is None and all(36 in notices[other] for other in ARCS):
                # Restore only ordinary world facts after all three authored
                # 36-month notices have been dispatched and legally answered.
                country["fixture_buildings"].update({
                    "building_rye_farm": 0.8,
                    "building_government_administration": 0.8,
                    "building_barrack": 0.8,
                })
                recovery_day = day
            if stop_at_five and min(counts.values()) >= 5:
                fairness_reached = True
        monthly_pulse_audit.append({"month": month, "pulse_order": pulse_order,
                                    "active_at_start": active_at_start,
                                    "pulsed": tuple(pulsed_this_month)})
        if set(active_at_start.items()) != set(pulsed_this_month):
            raise AssertionError(("monthly_active_je_pulse_coverage_mismatch", month,
                                  active_at_start, pulsed_this_month))
        if fairness_reached:
            ordered = sorted(recipients)
            if any(b - a < 90 for a, b in zip(ordered, ordered[1:])):
                raise AssertionError(("global_recipient_cooldown_under_90_days", ordered))
            return {"world": world, "admission": admission, "trace": trace, "counts": counts,
                    "paid_days": paid_days, "event_days": event_days, "recipients": recipients,
                    "current": current, "seen": seen, "route_index": route_index,
                    "terminal_status": terminal_status, "handoffs": handoffs,
                    "terminal_hooks": terminal_hooks,
                    "notices": notices, "recovery_day": recovery_day,
                    "helper_clean": helper_clean, "recovery_popups": recovery_popups,
                    "monthly_pulse_audit": monthly_pulse_audit,
                    "pulse_policy": "fixed_input_order" if require_transport else "rotating_source_only_diagnostic"}
        if recovery_day is not None:
            for arc in ARCS:
                lane = f"ywc_nmg_{arc}"
                cleanup_fields = ("_blocked_clock_started", "_blocked_months", "_notice12_due",
                                  "_notice36_due", "_notice_pending", "_notice12_delivered",
                                  "_notice36_delivered", "_notice_response_context", "_notice_return_event")
                if all(lane + field not in country for field in cleanup_fields):
                    helper_clean.add(arc)
        if all(value is None for value in current.values()) and (not block_facts or len(helper_clean) == 3):
            break
    return {"world": world, "admission": admission, "trace": trace, "counts": counts,
            "paid_days": paid_days, "event_days": event_days, "recipients": recipients,
            "current": current, "seen": seen, "route_index": route_index, "blocked": blocked,
            "terminal_status": terminal_status, "handoffs": handoffs,
            "terminal_hooks": terminal_hooks,
            "notices": notices, "recovery_day": recovery_day,
            "helper_clean": helper_clean, "recovery_popups": recovery_popups,
            "monthly_pulse_audit": monthly_pulse_audit,
            "pulse_policy": "fixed_input_order" if require_transport else "rotating_source_only_diagnostic"}


class NmgNativeStoryContract(unittest.TestCase):
    def setUp(self):
        source_pins_before = _pins()
        self.addCleanup(lambda: self.assertEqual(source_pins_before, _pins(),
                                                 "formal NMG source input changed during story contract"))

    def test_six_admission_and_pulse_orders_have_five_whole_body_popups_per_arc(self):
        for order in itertools.permutations(ARCS):
            with self.subTest(admission_and_pulse_order=order):
                result = run_nmg_story(order, stop_at_five=True)
                self.assertTrue(all(result["counts"][arc] >= 5 for arc in ARCS),
                                {"order": order, "counts": result["counts"], "trace": result["trace"]})
                self.assertEqual(set(result["paid_days"]), set(ARCS))
                for arc, paid_day in result["paid_days"].items():
                    later = [day for day in result["event_days"][arc] if day >= paid_day + 180]
                    self.assertGreaterEqual(len(later), 2, (order, arc, paid_day, result["event_days"][arc]))
                ordered = sorted(result["recipients"])
                self.assertTrue(all(b - a >= 90 for a, b in zip(ordered, ordered[1:])),
                                (order, "global recipient spacing", ordered))
                self.assertTrue(all(len([row for row in result["trace"] if row["arc"] == arc]) > 0
                                    for arc in ARCS), (order, "non-target JEs were not pulsed"))
                self.assertTrue(result["monthly_pulse_audit"])
                for audit in result["monthly_pulse_audit"]:
                    self.assertEqual(set(audit["active_at_start"].items()), set(audit["pulsed"]),
                                     (order, audit))

    def test_all_six_journal_entries_handoff_and_finish_with_no_visible_or_active_arc(self):
        result = run_nmg_story(ARCS, max_months=600)
        world, final = result["world"], result["world"].countries["NMG"]
        self.assertEqual(result["current"], {arc: None for arc in ARCS},
                         {"counts": result["counts"], "trace": result["trace"]})
        self.assertEqual(result["seen"], {arc: set(ARC_JES[arc]) for arc in ARCS})
        self.assertEqual({arc: set(row) for arc, row in result["terminal_status"].items()},
                         {arc: set(ARC_JES[arc]) for arc in ARCS})
        self.assertTrue(all(status == "complete"
                            for row in result["terminal_status"].values() for status in row.values()),
                        result["terminal_status"])
        for arc in ARCS:
            for jid in ARC_JES[arc]:
                je = world.journal_defs[jid]
                source_hook = _field(je, "on_complete")
                records = result["terminal_hooks"].get(arc, {}).get(jid, [])
                source_witnesses = tuple(sorted(value for key, _, value in source_hook or []
                                                 if key == "remove_variable"
                                                 and isinstance(value, str)
                                                 and value.startswith("ywc_v03_nmg_inline_live_")))
                if source_hook is None:
                    self.assertEqual(records, [], (jid, "native source has no completion hook"))
                else:
                    self.assertTrue(source_witnesses,
                                    (jid, source_hook, "generated completion hook must name its live witness"))
                    self.assertEqual(len(records), 1, (jid, records))
                    self.assertEqual(records[0]["hook"], "on_complete")
                    self.assertEqual(set(records[0]["witnesses_before"]), set(source_witnesses))
                    self.assertTrue(all(records[0]["witnesses_before"].values()),
                                    (jid, records[0], "generated witness must be live before hook"))
                    self.assertEqual(set(records[0]["witnesses_after"]), set(source_witnesses))
                    self.assertFalse(any(records[0]["witnesses_after"].values()),
                                     (jid, records[0], "completion hook must clear its generated witness"))
                    self.assertTrue(all(name not in final for name in source_witnesses),
                                    (jid, source_witnesses, final))
        self.assertEqual(result["handoffs"], {
            "land": [(ARC_JES["land"][0], ARC_JES["land"][1])],
            "office": [],
            "revenue": [(ARC_JES["revenue"][0], ARC_JES["revenue"][1]),
                        (ARC_JES["revenue"][1], ARC_JES["revenue"][2])],
        })
        self.assertEqual(final.get("ywc_v03_active_arc_count"), 0)
        self.assertEqual(final.get("ywc_v03_visible_task_count"), 0)
        self.assertFalse(world.active_journals.intersection(set().union(*map(set, ARC_JES.values()))))

    def test_all_three_native_notice_epochs_dispatch_ack_and_recover_on_normal_helper(self):
        result = run_nmg_story(ARCS, max_months=420, block_facts=True)
        # Deliberately checks actual source-driven 12/36 delivery, legal ACK options,
        # ordinary-fact restoration, and subsequent source helper cleanup.
        world = result["world"]
        for arc in ARCS:
            self.assertEqual(set(result["notices"][arc]), {12, 36},
                             (arc, result["notices"][arc], result["trace"]))
            for threshold, row in result["notices"][arc].items():
                self.assertTrue(row["complete_immediate"])
                self.assertGreater(row["ack_calls"], 0, (arc, threshold, row))
                self.assertIn(row["selected_option"], row["legal_options"])
                self.assertEqual(row["after_body"][f"ywc_nmg_{arc}_notice{threshold}_delivered"], 1)
                self.assertEqual(row["after_body"][f"ywc_nmg_{arc}_notice_response_context"], 1)
        self.assertIsNotNone(result["recovery_day"])
        self.assertEqual(result["helper_clean"], set(ARCS),
                         (result["helper_clean"], result["trace"][-12:]))
        self.assertEqual(result["recovery_popups"], set(ARCS),
                         (result["recovery_popups"], result["trace"][-12:]))
        self.assertTrue(world.events == [] or all(tag == "NMG" for tag, _ in world.events))


if __name__ == "__main__":
    unittest.main()
