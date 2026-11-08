"""Actual-source SHU scheduler fairness baseline; static evidence only.

The strict interpreter executes authored startup registration, native first-JE
admission/immediate, monthly pulses, event triggers/immediates and legal
options. Only the documented old-result flag and owned Sichuan world facts are
scenario inputs. This does not emulate the Victoria 3 engine.
"""
import unittest
import copy
import hashlib
import json
from pathlib import Path

from tools.build_v03_country import render_country
from tools import v03_inline_delivery_adapter as inline_adapter
from tools.v03_inline_delivery_adapter import render_inline_country_adapters, validate_inline_catalog
from tests.shu_kor_strict_review_runtime import Strict, facts, field
from tests.clausewitz_harness import parse


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/content/v03/countries/shu.json"


def _definitions(text):
    rows = parse(text)
    names = [key for key, _, _ in rows]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise AssertionError(("duplicate_generated_script_definitions", duplicates))
    return {key: body for key, _, body in rows}


def _render_real_shu():
    """Render SHU entirely in memory; permanent tests never touch PLANWS/build outputs."""
    return render_country(ROOT, "country_shu")


def _install_real_shu_render(world, outputs):
    """Load the current renderer's real generated SHU helpers and native scripts."""
    by_name = {path.name: text for path, text in outputs.items()}
    event_name = "ywc_v03_country_shu_events.txt"
    journal_name = "ywc_v03_country_shu_journal.txt"
    effects_name = "ywc_v03_delivery_shu_effects.txt"
    triggers_name = "ywc_v03_delivery_shu_triggers.txt"
    missing = {event_name, journal_name, effects_name, triggers_name} - set(by_name)
    if missing:
        raise AssertionError(("real_generated_shu_adapter_outputs_missing", sorted(missing)))
    helper_effects = _definitions(by_name[effects_name])
    helper_triggers = _definitions(by_name[triggers_name])
    duplicate_effects = set(helper_effects) & set(world.effects)
    duplicate_triggers = set(helper_triggers) & set(world.trigger_defs)
    if duplicate_effects or duplicate_triggers:
        raise AssertionError(("generated_shu_helper_collision", sorted(duplicate_effects),
                              sorted(duplicate_triggers)))
    world.effects.update(helper_effects)
    world.trigger_defs.update(helper_triggers)
    world.event_defs = {key: body for key, _, body in parse(by_name[event_name])
                        if isinstance(body, list)}
    world.journal_defs = _definitions(by_name[journal_name])
    world._shu_outputs = outputs
    world._shu_rendered = render_inline_country_adapters(world.cat)
    world._shu_candidates = {}
    candidate_id = 0
    branch_count = 0
    world._shu_slot_by_arc = {}
    for arc in world.cat["arcs"]:
        adapter = arc.get("inline_delivery_adapter")
        if not adapter:
            continue
        world._shu_slot_by_arc[arc["slug"]] = len(world._shu_slot_by_arc) + 1
        for proof in adapter["branches"]:
            branch_count += 1
            for candidate in proof["candidates"]:
                candidate_id += 1
                world._shu_candidates[candidate_id] = {
                    "arc": arc, "proof": proof, "candidate": candidate}
    if branch_count != 31 or candidate_id != 31:
        raise AssertionError(("unexpected_shu_source_branch_or_candidate_count",
                              branch_count, candidate_id))
    world.trace.append({"op": "load_real_rendered_shu_helpers",
                        "effects": sorted(helper_effects),
                        "triggers": sorted(helper_triggers),
                        "events": len(world.event_defs),
                        "journals": len(world.journal_defs)})


def _actual_rendered_option(world, event_id, key):
    event = world.event_defs[event_id]
    option = next(value for name, _, value in event
                  if name == "option" and field(value, "name").endswith("." + key))
    trigger = field(option, "trigger", None)
    if trigger and not world.conditions(trigger, world.tag):
        raise AssertionError(("actual_source_option_rejected", event_id, key,
                              dict(world.countries[world.tag])))
    return option


def _execute_actual_event(world, event_id, option_key, day):
    event = world.event_defs[event_id]
    trigger = field(event, "trigger")
    if not world.conditions(trigger, world.tag):
        raise AssertionError(("actual_generated_event_trigger_rejected", event_id, day,
                              dict(world.countries[world.tag])))
    before = dict(world.countries[world.tag])
    immediate = field(event, "immediate")
    world.execute(immediate, world.tag)
    after_immediate = dict(world.countries[world.tag])
    option = _actual_rendered_option(world, event_id, option_key)
    effect = [node for node in option if node[0] not in
              ("name", "trigger", "ai_chance", "custom_tooltip")]
    world.execute(effect, world.tag)
    row = {"event": event_id, "day": day, "option": option_key,
           "immediate_delta": {k: v for k, v in after_immediate.items()
                                if before.get(k) != v},
           "option_delta": {k: v for k, v in world.countries[world.tag].items()
                            if after_immediate.get(k) != v}}
    world.trace.append({"op": "actual_generated_event_and_option", **row})
    return row


ROOTS = (
    ("v03_shu_fiscal_register", "ywc_je_v03_shu_register_pilot"),
    ("v03_shu_service_compact", "ywc_je_v03_shu_service_contract"),
    ("v03_shu_port_treasury", "ywc_je_v03_shu_port_customs"),
)
FRESH_M1_EVENT = "ywc_shu.1000"
LEGACY_RESULT = "ywc_campaign_shu_c1_outcome"
CALENDAR_MONTHS = 30
EXPECTED_OPPORTUNITY_DAYS = tuple(range(30, 841, 90))
KNOWN_NONDEFER_CHOICES = {
    "ywc_shu.1000": "pilot_state_sichuan",
    "ywc_shu.1001": "wait_for_office",
    "ywc_shu.1010": "garrison_seal",
    "ywc_shu.1011": "local_ledger",
    "ywc_shu.1012": "incumbents_only",
    "ywc_shu.1013": "legacy_cap",
    "ywc_shu.1014": "reduce_target",
    "ywc_shu.1015": "vacant_cap",
    "ywc_shu.1018": "unified_customs",
    "ywc_shu.1019": "publish_books",
    "ywc_shu.1020": "consult_only",
    "ywc_shu.1021": "current_law_review",
    "ywc_shu.1022": "wait_receipts",
    "ywc_shu.1023": "central_form",
    "ywc_shu.1024": "reduce_burden",
    "ywc_shu.1025": "retry_port",
    "ywc_shu.1016": "resume_service_appointments",
    "ywc_shu.1017": "restart_service_review",
}


def _new_world(legacy_result=None):
    # This harness renders and loads its own current in-memory helper set;
    # disable the runtime's default on-disk load to keep collision checks real.
    world = Strict("shu", load_inline=False)
    # The strict runtime resolves ownership, region and authored scripted
    # triggers against this actual engine-world fixture. It starts queue-free.
    world.countries[world.tag] = facts()
    state = world.countries[world.tag]
    # `facts()` is also used by older initialized-state tests. Strip its two
    # preloaded lifecycle fields so this baseline exercises real initialize +
    # legacy registration. Do not seed any new-arc or scheduler-owned state.
    state.pop("ywc_v03_initialized", None)
    state.pop("ywc_v03_release_version", None)
    private_seed = [key for key in state
                    if key.startswith("ywc_v03_") or "pending_event" in key]
    if private_seed:
        raise AssertionError(("unexpected_initial_lifecycle_or_queue_seed", private_seed))
    if legacy_result is not None:
        state[LEGACY_RESULT] = legacy_result
    if any("pending_event" in key for key in state):
        raise AssertionError(("unexpected_initial_source_queue", state))
    world.trace.append({"op": "scenario_seed", "owned_state": "s:STATE_SICHUAN",
                        "legacy_result": legacy_result, "initial_queues": []})
    return world


def _journal(world, journal_id):
    return world.journal_defs[journal_id]


def _root_arc(world, slug):
    return next(arc for arc in world.cat["arcs"] if arc["slug"] == slug)


def _refresh_actual_journal_history(world):
    """Apply authored completion/admission checks without pulsing terminal JEs."""
    for arc in world.cat["arcs"]:
        world.refresh(arc)


def _native_admission(world, slug, journal_id):
    journal = _journal(world, journal_id)
    shown = world.conditions(field(journal, "is_shown_when_inactive"), world.tag)
    possible = world.conditions(field(journal, "possible"), world.tag)
    if not shown or not possible:
        raise AssertionError(("native_entry_not_shown_and_possible", slug, shown, possible,
                              dict(world.countries[world.tag])))
    before = dict(world.countries[world.tag])
    world.activate_entry(_root_arc(world, slug), journal_id)
    after = world.countries[world.tag]
    world.trace.append({"op": "native_first_je_admission", "arc": slug,
                        "journal": journal_id, "shown": shown, "possible": possible,
                        "immediate_delta": {k: v for k, v in after.items()
                                            if before.get(k) != v},
                        "active": list(world.active[world.tag]),
                        "active_count": after.get("ywc_v03_active_arc_count"),
                        "visible_count": after.get("ywc_v03_visible_task_count"),
                        "source_queues": {k: v for k, v in after.items()
                                          if "pending_event" in k}})


def _option_rows(world, event):
    return [(option, field(option, "name").rsplit(".", 1)[-1])
            for key, _, option in event if key == "option"]


def _is_notice_ack(name):
    return name.endswith(("acknowledge_12_month_notice", "acknowledge_36_month_notice"))


def _select_legal_option(world, event, event_id, day, overrides=None):
    rows = _option_rows(world, event)
    legal = [(option, name) for option, name in rows
             if world.conditions(field(option, "trigger"), world.tag)]
    if not legal:
        raise AssertionError(("native_event_has_no_legal_option", event_id, day,
                              dict(world.countries[world.tag])))
    override = (overrides or {}).get(event_id)
    if override is not None:
        matches = [(option, name) for option, name in legal if name == override]
        if len(matches) != 1:
            raise AssertionError(("requested_source_option_not_legal", event_id, day,
                                  override, [name for _, name in legal]))
        chosen, name = matches[0]
    else:
        chosen = name = None

    # The source's opening choice establishes the actual route and has no
    # defer on the port card. Record that native route choice before applying
    # the normal defer/notice policy to subsequent cards.
    if chosen is not None:
        pass
    elif event_id in ("ywc_shu.1010", "ywc_shu.1018"):
        wanted = KNOWN_NONDEFER_CHOICES[event_id]
        starters = [(option, name) for option, name in legal if name == wanted]
        if len(starters) != 1:
            raise AssertionError(("native_route_starter_not_legal", event_id, day,
                                  wanted, [name for _, name in legal]))
        chosen, name = starters[0]
    else:
        chosen = name = None

    # Prefer a real authored defer/wait/retry. Notices in these sources have
    # authored acknowledgements instead of a defer option; execute that actual
    # acknowledgement only if its own trigger is legal.
    deferrers = [(option, name) for option, name in legal
                 if name == "defer" or name.startswith(("delay_", "wait_", "retry_"))]
    if chosen is not None:
        pass
    elif len(deferrers) == 1:
        chosen, name = deferrers[0]
    elif event_id == "ywc_shu.1016":
        # SHU notice 1016 has no synthetic defer/receipt option. Continue only
        # through the one source-authored acknowledgement legal for the live
        # native phase; the exact key differs by JE stage.
        acknowledgements = [(option, name) for option, name in legal
                            if name.startswith(("resume_", "retry_after_repair"))]
        if len(acknowledgements) != 1:
            raise AssertionError(("ambiguous_or_missing_source_1016_ack", event_id,
                                  day, [name for _, name in legal]))
        chosen, name = acknowledgements[0]
    else:
        acknowledgements = [(option, name) for option, name in legal if _is_notice_ack(name)]
        if acknowledgements:
            if len(acknowledgements) != 1:
                raise AssertionError(("ambiguous_native_notice_ack", event_id, day,
                                      [name for _, name in acknowledgements]))
            chosen, name = acknowledgements[0]
        else:
            wanted = KNOWN_NONDEFER_CHOICES.get(event_id)
            matches = [(option, name) for option, name in legal if name == wanted]
            if len(matches) != 1:
                raise AssertionError(("unsupported_or_illegal_native_choice", event_id, day,
                                      wanted, [name for _, name in legal]))
            chosen, name = matches[0]

    effect = [node for node in chosen
              if node[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
    before = dict(world.countries[world.tag])
    world.execute(effect, world.tag)
    world.trace.append({"op": "native_legal_option", "event": event_id, "option": name,
                        "day": day, "legal_option_names": [item for _, item in legal],
                        "state_delta": {k: v for k, v in world.countries[world.tag].items()
                                        if before.get(k) != v},
                        "source_queues": {k: v for k, v in world.countries[world.tag].items()
                                          if "pending_event" in k}})
    return name


def _deliver_actual_event(world, event_id, day, overrides=None):
    if event_id not in world.event_defs:
        raise AssertionError(("unknown_native_event", event_id, day))
    event = world.event_defs[event_id]
    trigger = field(event, "trigger")
    if not world.conditions(trigger, world.tag):
        world.trace.append({"op": "native_event_rejected", "event": event_id, "day": day,
                            "trigger": trigger,
                            "state": dict(world.countries[world.tag])})
        raise AssertionError(("native_event_trigger_rejected", event_id, day,
                              dict(world.countries[world.tag])))
    before = dict(world.countries[world.tag])
    reservation = before.get("ywc_v03_shu_inline_reservation")
    if not isinstance(reservation, (int, float)) or isinstance(reservation, bool):
        raise AssertionError(("actual_event_without_candidate_reservation", event_id, day,
                              reservation, before))
    candidate_id = int(reservation)
    row = world._shu_candidates.get(candidate_id)
    if row is None or row["proof"]["event"] != event_id:
        raise AssertionError(("reservation_does_not_match_actual_sender", candidate_id,
                              event_id, row))
    candidate = row["candidate"]
    queue_name = candidate["queue"]
    if queue_name not in before:
        raise AssertionError(("actual_source_queue_missing_before_native_immediate",
                              candidate_id, queue_name, before))
    if candidate.get("mode") == "exact" and before[queue_name] != candidate.get("value"):
        raise AssertionError(("actual_source_queue_value_drift", candidate_id, queue_name,
                              before[queue_name], candidate.get("value")))
    epoch = before.get("ywc_v03_shu_inline_reservation_epoch")
    round_value = before.get("ywc_v03_shu_inline_round")
    served_name = "ywc_v03_shu_inline_served_" + str(
        world._shu_slot_by_arc[row["arc"]["slug"]])
    siblings = {item["candidate"]["queue"]: before[item["candidate"]["queue"]]
                for item in world._shu_candidates.values()
                if item["arc"]["slug"] == row["arc"]["slug"]
                and item["candidate"]["queue"] != queue_name
                and item["candidate"]["queue"] in before}
    world.execute(field(event, "immediate"), world.tag)
    after = world.countries[world.tag]
    if (after.get(served_name) != round_value
            or "ywc_v03_shu_inline_reservation" in after
            or "ywc_v03_shu_inline_timer" in after
            or queue_name in after):
        raise AssertionError(("actual_native_immediate_did_not_ack_selected_candidate",
                              candidate_id, event_id, day, dict(after)))
    changed_siblings = {name: (value, after.get(name)) for name, value in siblings.items()
                        if after.get(name) != value}
    if changed_siblings:
        raise AssertionError(("ack_mutated_sibling_source_queue", candidate_id,
                              changed_siblings, dict(after)))
    world.trace.append({"op": "actual_candidate_ack_proof", "candidate": candidate_id,
                        "arc": row["arc"]["slug"], "journal": row["proof"]["journal"],
                        "event": event_id, "queue": queue_name,
                        "queue_value_before": before[queue_name], "epoch": epoch,
                        "round": round_value, "served_variable": served_name,
                        "served": after.get(served_name),
                        "sibling_queues_before": siblings,
                        "sibling_queues_after": {name: after.get(name) for name in siblings}})
    world.trace.append({"op": "native_event_trigger_and_immediate", "event": event_id,
                        "day": day, "trigger": trigger,
                        "state_delta": {k: v for k, v in world.countries[world.tag].items()
                                        if before.get(k) != v}})
    option = _select_legal_option(world, event, event_id, day, overrides)
    return {"event": event_id, "day": day, "option": option}


def _terminal_check(world, journal_id, day):
    journal = _journal(world, journal_id)
    complete = world.conditions(field(journal, "complete"), world.tag)
    fail = world.conditions(field(journal, "fail"), world.tag)
    if complete or fail:
        raise AssertionError(("terminal_native_je_was_not_supposed_to_be_driven",
                              journal_id, day, complete, fail,
                              dict(world.countries[world.tag])))


def _source_queues(world):
    state = world.countries[world.tag]
    # The generated adapter has helper booleans named `*_pending_event_*`;
    # those are not authored source queues and must not be counted as such.
    queue_names = {item["candidate"]["queue"]
                   for item in world._shu_candidates.values()}
    return {key: state[key] for key in sorted(queue_names) if key in state}


def _pulse_actual_active_arc(world, arc_slug, day, overrides=None):
    """Run the authored pulse for the live source JE and deliver its real popup."""
    arc = _root_arc(world, arc_slug)
    owner_by_journal = {row["id"]: owner["slug"] for owner in world.cat["arcs"]
                        for row in owner["journals"]}
    active = [row["id"] for row in arc["journals"]
              if row["id"] in world.active[world.tag]
              and owner_by_journal.get(row["id"]) == arc_slug]
    delivered = []
    for journal_id in active:
        if journal_id not in world.active[world.tag]:
            continue
        _terminal_check(world, journal_id, day)
        journal = _journal(world, journal_id)
        pulse = field(field(journal, "on_monthly_pulse"), "effect")
        before_state = dict(world.countries[world.tag])
        before_events = len(world.events)
        before_queues = _source_queues(world)
        world.execute(pulse, world.tag)
        emitted = list(world.events[before_events:])
        sender_state = dict(world.countries[world.tag])
        if len(emitted) > 1:
            raise AssertionError(("authored_shu_pulse_emitted_multiple_events",
                                  journal_id, day, emitted))
        event_delivery = None
        if emitted:
            recipient, event_id = emitted[0]
            if recipient != world.tag:
                raise AssertionError(("actual_source_event_wrong_recipient", recipient,
                                      event_id, day))
            world.events.pop(before_events)
            event_delivery = _deliver_actual_event(world, event_id, day, overrides)
            delivered.append(event_delivery)
        world.trace.append({"op": "focused_actual_source_pulse", "journal": journal_id,
                            "arc": arc_slug, "day": day, "source_events": emitted,
                            "delivered": event_delivery,
                            "queues_before": before_queues,
                            "queues_after": _source_queues(world),
                            "sender_state_before_actual_immediate": sender_state,
                            "state_delta": {key: value for key, value in
                                            world.countries[world.tag].items()
                                            if before_state.get(key) != value}})
        _refresh_actual_journal_history(world)
    return delivered


def _run_monthly_fairness_order(order, option_overrides=None):
    world = _new_world(legacy_result=1)
    _install_real_shu_render(world, _render_real_shu())
    # Actual initializer calls the actual legacy continuation registration.
    world.run("ywc_v03_initialize_country", world.tag)
    state = world.countries[world.tag]
    m1 = _journal(world, ROOTS[0][1])
    if world.conditions(field(m1, "possible"), world.tag):
        raise AssertionError(("legacy_registration_did_not_close_m1", dict(state)))
    if state.get("ywc_v03_shu_v03_shu_fiscal_register_settled") != 1:
        raise AssertionError(("legacy_registration_missing_m1_settlement",
                              dict(state)))
    if state.get("ywc_v03_active_arc_count") != 0 or state.get("ywc_v03_visible_task_count") != 0:
        raise AssertionError(("initialization_changed_active_counts", dict(state)))
    world.trace.append({"op": "actual_startup_initialize_and_legacy_registration",
                        "legacy_result": state.get(LEGACY_RESULT),
                        "m1_possible": world.conditions(field(m1, "possible"), world.tag),
                        "m1_settled": state.get("ywc_v03_shu_v03_shu_fiscal_register_settled"),
                        "active_count": state.get("ywc_v03_active_arc_count"),
                        "visible_count": state.get("ywc_v03_visible_task_count")})

    for slug, journal_id in order:
        journal = _journal(world, journal_id)
        shown = world.conditions(field(journal, "is_shown_when_inactive"), world.tag)
        possible = world.conditions(field(journal, "possible"), world.tag)
        if not (shown and possible):
            raise AssertionError(("service_or_port_not_natively_admissible", slug,
                                  shown, possible, dict(state)))
        _native_admission(world, slug, journal_id)
    if state.get("ywc_v03_active_arc_count") != 2 or state.get("ywc_v03_visible_task_count") != 2:
        raise AssertionError(("native_two_root_counter_mismatch", dict(state)))
    if len(world.active[world.tag]) != 2:
        raise AssertionError(("native_active_root_count_mismatch", world.active[world.tag]))

    counts = {slug: 0 for slug, _ in order}
    delivery_days = {slug: [] for slug, _ in order}
    delivery_events = {slug: [] for slug, _ in order}
    day = 0
    owner_by_journal = {
        row["id"]: arc["slug"]
        for arc in world.cat["arcs"] for row in arc["journals"]
    }
    for month in range(1, CALENDAR_MONTHS + 1):
        world.advance_days(30)
        world.elapsed_months += 1
        day += 30
        _refresh_actual_journal_history(world)
        for slug, journal_id in order:
            arc = _root_arc(world, slug)
            # Pulse every currently active native JE owned by this source arc,
            # in the same stable order the authored catalog declares them.
            active_for_arc = [row["id"] for row in arc["journals"]
                              if row["id"] in world.active[world.tag]
                              and owner_by_journal.get(row["id"]) == slug]
            for active_journal_id in active_for_arc:
                if active_journal_id not in world.active[world.tag]:
                    continue
                _terminal_check(world, active_journal_id, day)
                journal = _journal(world, active_journal_id)
                pulse = field(field(journal, "on_monthly_pulse"), "effect")
                before = len(world.events)
                queues_before = _source_queues(world)
                state_before = dict(world.countries[world.tag])
                world.execute(pulse, world.tag)
                emitted = list(world.events[before:])
                if len(emitted) > 1:
                    raise AssertionError(("one_native_pulse_emitted_multiple_events",
                                          active_journal_id, day, emitted))
                delivered = None
                if emitted:
                    tag, event_id = emitted[0]
                    if tag != world.tag:
                        raise AssertionError(("native_event_wrong_recipient", tag, event_id, day))
                    world.events.pop(before)
                    delivered = _deliver_actual_event(world, event_id, day,
                                                      option_overrides)
                    counts[slug] += 1
                    delivery_days[slug].append(day)
                    delivery_events[slug].append(delivered)
                world.trace.append({"op": "real_monthly_je_pulse", "month": month, "day": day,
                                    "order_index": [arc_slug for arc_slug, _ in order].index(slug),
                                    "arc": slug, "journal": active_journal_id,
                                    "source_events": [event for _, event in emitted],
                                    "delivered": delivered,
                                    "queues_before": queues_before,
                                    "queues_after": _source_queues(world),
                                    "reservation": world.countries[world.tag].get("ywc_v03_shu_inline_reservation"),
                                    "state_delta": {k: v for k, v in world.countries[world.tag].items()
                                                    if state_before.get(k) != v},
                                    "active": list(world.active[world.tag]),
                                    "active_count": world.countries[world.tag].get("ywc_v03_active_arc_count"),
                                    "visible_count": world.countries[world.tag].get("ywc_v03_visible_task_count")})
                # Let authored completion/release/request handlers run now.
                # The next pulse uses the actual active history, never a
                # completed JE's on_monthly_pulse.
                _refresh_actual_journal_history(world)

    # Do not use end-state/counter caps as evidence of eligible service.
    expected_calendar = list(EXPECTED_OPPORTUNITY_DAYS)
    actual_days = sorted(day for days in delivery_days.values() for day in days)
    summary = {"order": [slug for slug, _ in order], "counts": counts,
               "delivery_days": delivery_days, "delivery_events": delivery_events,
               "all_delivery_days": actual_days,
               "source_queues_after_30_months": _source_queues(world),
               "active": list(world.active[world.tag]),
               "history": dict(world.history[world.tag]),
               "active_count": world.countries[world.tag].get("ywc_v03_active_arc_count"),
               "visible_count": world.countries[world.tag].get("ywc_v03_visible_task_count"),
               "expected_opportunity_days": expected_calendar,
               "final_state": dict(world.countries[world.tag])}
    world.trace.append({"op": "summary", **summary})
    if actual_days != expected_calendar:
        raise AssertionError(("actual_native_callback_calendar_mismatch", summary))
    active_arc_slugs = {owner_by_journal.get(journal_id)
                        for journal_id in world.active[world.tag]}
    if (len(world.active[world.tag]) != 2
            or active_arc_slugs != {slug for slug, _ in order}):
        raise AssertionError(("native_history_active_state_mismatch", summary))
    return world, summary


def _run_fresh_m1_first_callback():
    world = _new_world()
    _install_real_shu_render(world, _render_real_shu())
    world.run("ywc_v03_initialize_country", world.tag)
    state = world.countries[world.tag]
    entries = [_journal(world, journal_id) for _, journal_id in ROOTS]
    admissibility = [{"arc": slug,
                     "shown": world.conditions(field(journal, "is_shown_when_inactive"), world.tag),
                     "possible": world.conditions(field(journal, "possible"), world.tag)}
                    for (slug, _), journal in zip(ROOTS, entries)]
    if admissibility != [
            {"arc": ROOTS[0][0], "shown": True, "possible": True},
            {"arc": ROOTS[1][0], "shown": False, "possible": False},
            {"arc": ROOTS[2][0], "shown": False, "possible": False}]:
        raise AssertionError(("fresh_native_admissibility_mismatch", admissibility,
                              dict(state)))
    _native_admission(world, *ROOTS[0])
    if state.get("ywc_v03_active_arc_count") != 1 or state.get("ywc_v03_visible_task_count") != 1:
        raise AssertionError(("fresh_m1_counter_mismatch", dict(state)))
    if state.get("ywc_shu_pending_event") != 1000:
        raise AssertionError(("fresh_m1_immediate_did_not_open_actual_1000", dict(state)))

    world.advance_days(30)
    world.elapsed_months += 1
    journal = _journal(world, ROOTS[0][1])
    pulse = field(field(journal, "on_monthly_pulse"), "effect")
    before = len(world.events)
    world.execute(pulse, world.tag)
    emitted = world.events[before:]
    if emitted != [(world.tag, FRESH_M1_EVENT)]:
        raise AssertionError(("fresh_m1_first_real_callback_mismatch", emitted,
                              dict(state)))
    world.events.pop(before)
    delivered = _deliver_actual_event(world, FRESH_M1_EVENT, 30)
    if delivered["option"] != "pilot_state_sichuan":
        raise AssertionError(("fresh_m1_did_not_choose_actual_owned_candidate", delivered,
                              dict(state)))
    return {"admissibility": admissibility, "active_count": state.get("ywc_v03_active_arc_count"),
            "visible_count": state.get("ywc_v03_visible_task_count"),
            "first_callback": delivered, "initial_immediate": 1000,
            "trace": list(world.trace), "final_state": dict(state)}


def _run_fresh_m1_capacity_auxiliary_flow():
    world = _new_world()
    _install_real_shu_render(world, _render_real_shu())
    world.run("ywc_v03_initialize_country", world.tag)
    _native_admission(world, *ROOTS[0])
    rows = []
    for day in (30, 60, 90, 120, 150, 180, 210):
        world.advance_days(30)
        world.elapsed_months += 1
        deliveries = _pulse_actual_active_arc(world, ROOTS[0][0], day)
        expected_event = {30: "ywc_shu.1000", 120: "ywc_shu.1001",
                          210: "ywc_shu.1001"}.get(day)
        if ((expected_event is None and deliveries)
                or (expected_event is not None
                    and (len(deliveries) != 1 or deliveries[0]["event"] != expected_event))):
            raise AssertionError(("fresh_m1_capacity_actual_callback_mismatch", day,
                                  expected_event, deliveries, dict(world.countries[world.tag])))
        if deliveries:
            rows.append(deliveries[0])
        state = world.countries[world.tag]
        if day == 120 and state.get("ywc_shu_waiting_for_capacity") != 1:
            raise AssertionError(("actual_1001_wait_choice_missing_capacity_aux", dict(state)))
        if day == 210:
            send = next(row for row in reversed(world.trace)
                        if row.get("op") == "focused_actual_source_pulse")
            before_popup = send["sender_state_before_actual_immediate"]
            if "ywc_shu_waiting_for_capacity" in before_popup:
                raise AssertionError(("actual_1001_sender_did_not_cleanup_aux_after_selection",
                                      before_popup))
            if before_popup.get("ywc_shu_pending_event") != 1001:
                raise AssertionError(("actual_1001_sender_consumed_queue_before_ack",
                                      before_popup))
    return {"deliveries": rows, "trace": list(world.trace),
            "final_state": dict(world.countries[world.tag])}


def _run_m1_expired_stale_epoch(snapshot_value, newer_value=None,
                                snapshot_missing=False, reservation_fault="epoch_mismatch"):
    world = _new_world()
    _install_real_shu_render(world, _render_real_shu())
    world.run("ywc_v03_initialize_country", world.tag)
    _native_admission(world, *ROOTS[0])
    choices = {"ywc_shu.1000": "pilot_state_sichuan",
               "ywc_shu.1001": "wait_for_office"}
    for day in (30, 60, 90, 120, 150, 180):
        world.advance_days(30)
        world.elapsed_months += 1
        rows = _pulse_actual_active_arc(world, ROOTS[0][0], day, choices)
        expected = {30: "ywc_shu.1000", 120: "ywc_shu.1001"}.get(day)
        if ((expected is None and rows)
                or (expected is not None
                    and (len(rows) != 1 or rows[0]["event"] != expected))):
            raise AssertionError(("actual_m1_setup_path_mismatch", day, expected,
                                  rows, dict(world.countries[world.tag])))

    state = world.countries[world.tag]
    state["ywc_shu_waiting_for_capacity"] = snapshot_value
    world.advance_days(30)
    world.elapsed_months += 1
    journal = _journal(world, ROOTS[0][1])
    pulse = field(field(journal, "on_monthly_pulse"), "effect")
    before = len(world.events)
    world.execute(pulse, world.tag)
    emitted = list(world.events[before:])
    if emitted != [(world.tag, "ywc_shu.1001")]:
        raise AssertionError(("actual_m1_retry_reservation_not_sent", emitted,
                              dict(state)))
    world.events.pop(before)  # Withhold the rejected popup; do not run its immediate/options.
    original_epoch = state["ywc_v03_shu_inline_reservation_epoch"]
    candidate_epoch = state["ywc_v03_shu_inline_candidate_epoch_2"]
    if (state.get("ywc_v03_shu_inline_reservation") != 2
            or candidate_epoch != original_epoch):
        raise AssertionError(("actual_m1_candidate2_reservation_mismatch", dict(state)))
    if "ywc_shu_waiting_for_capacity" in state:
        raise AssertionError(("native_1001_sender_did_not_remove_aux", dict(state)))
    present_name = "ywc_v03_shu_inline_aux_waiting_present_2"
    value_name = "ywc_v03_shu_inline_aux_waiting_value_2"
    if state.get(present_name) != 1 or state.get(value_name) != snapshot_value:
        raise AssertionError(("actual_1001_aux_snapshot_capture_mismatch", dict(state)))

    state["ywc_v03_shu_inline_reservation_epoch"] = original_epoch + 1
    if reservation_fault == "candidate_epoch_missing":
        state.pop("ywc_v03_shu_inline_candidate_epoch_2", None)
    elif reservation_fault in ("invalid_reservation_id",
                                "invalid_reservation_id_zero",
                                "invalid_reservation_id_negative"):
        invalid_id = {"invalid_reservation_id": 999,
                      "invalid_reservation_id_zero": 0,
                      "invalid_reservation_id_negative": -1}[reservation_fault]
        state["ywc_v03_shu_inline_reservation"] = invalid_id
        # Unknown reservation IDs have no owned aux snapshot. Do not restore
        # candidate 2's snapshot into a reservation whose ownership is unknown.
        snapshot_missing = True
        state.pop(present_name, None)
        state.pop(value_name, None)
    elif reservation_fault != "epoch_mismatch":
        raise AssertionError(("unknown_reservation_fault", reservation_fault))
    if newer_value is not None:
        state["ywc_shu_waiting_for_capacity"] = newer_value
    if snapshot_missing:
        state.pop(present_name, None)
        state.pop(value_name, None)
    world.trace.append({"op": "controlled_stale_reservation_epoch_before_expiry",
                        "day": 210, "candidate": 2,
                        "candidate_epoch": candidate_epoch,
                        "global_epoch": state["ywc_v03_shu_inline_reservation_epoch"],
                        "snapshot_aux_value": snapshot_value,
                        "newer_aux_value": newer_value,
                        "snapshot_missing": snapshot_missing,
                        "reservation_fault": reservation_fault,
                        "popup_immediate_executed": False,
                        "popup_option_executed": False})
    world.advance_days(1)
    world.run("ywc_v03_shu_inline_prepare", world.tag)
    after_expiry = dict(state)
    if "ywc_v03_shu_inline_reservation" in state or "ywc_v03_shu_inline_timer" in state:
        raise AssertionError(("stale_epoch_expiry_left_candidate_reserved", after_expiry))
    if present_name in state or value_name in state:
        raise AssertionError(("stale_epoch_expiry_left_aux_snapshot", after_expiry))
    if state.get("ywc_shu_pending_event") != 1001:
        raise AssertionError(("stale_epoch_expiry_consumed_native_source_queue", after_expiry))
    if snapshot_missing:
        if "ywc_shu_waiting_for_capacity" in state:
            raise AssertionError(("missing_aux_snapshot_invented_aux_value", after_expiry))
    elif newer_value is not None:
        if state.get("ywc_shu_waiting_for_capacity") != newer_value:
            raise AssertionError(("expiry_overwrote_newer_aux_value", after_expiry))
    elif state.get("ywc_shu_waiting_for_capacity") != snapshot_value:
        raise AssertionError(("stale_epoch_expiry_failed_to_restore_aux", after_expiry))

    retry = []
    retry_day = None
    prior_day = 211
    for retry_day_candidate in (240, 270, 300):
        gap = retry_day_candidate - prior_day
        world.advance_days(gap)
        world.elapsed_months += 1
        retry = _pulse_actual_active_arc(world, ROOTS[0][0],
                                         retry_day_candidate, choices)
        if retry:
            retry_day = retry_day_candidate
            break
        prior_day = retry_day_candidate
    if len(retry) != 1 or retry[0]["event"] != "ywc_shu.1001":
        raise AssertionError(("actual_m1_did_not_retry_within_three_source_months",
                              retry, dict(state), list(world.trace)))
    proof = next(row for row in reversed(world.trace)
                 if row.get("op") == "actual_candidate_ack_proof"
                 and row.get("event") == "ywc_shu.1001")
    if proof["epoch"] == candidate_epoch:
        raise AssertionError(("actual_m1_retry_reused_expired_candidate_epoch", proof))
    if state.get("ywc_shu_waiting_for_capacity") != 1:
        raise AssertionError(("actual_m1_wait_option_did_not_establish_new_aux",
                              dict(state)))
    return {"snapshot_value": snapshot_value, "newer_value": newer_value,
            "snapshot_missing": snapshot_missing,
            "reservation_fault": reservation_fault,
            "after_expiry": after_expiry,
            "candidate_epoch": candidate_epoch, "retry": retry[0],
            "retry_day": retry_day, "proof": proof, "trace": list(world.trace)}



def _run_m1_missing_epoch_guard_and_source_retry(missing_fields):
    world = _new_world()
    _install_real_shu_render(world, _render_real_shu())
    world.run("ywc_v03_initialize_country", world.tag)
    _native_admission(world, *ROOTS[0])
    world.advance_days(30)
    world.elapsed_months += 1
    journal = _journal(world, ROOTS[0][1])
    pulse = field(field(journal, "on_monthly_pulse"), "effect")
    before = len(world.events)
    world.execute(pulse, world.tag)
    emitted = list(world.events[before:])
    if emitted != [(world.tag, "ywc_shu.1000")]:
        raise AssertionError(("actual_m1_initial_1000_reservation_not_emitted",
                              emitted, dict(world.countries[world.tag])))
    world.events.pop(before)  # Keep the authored popup pending; do not select an option.
    event = world.event_defs["ywc_shu.1000"]
    event_trigger = field(event, "trigger")
    event_immediate = field(event, "immediate")
    state = world.countries[world.tag]
    candidate_epoch_name = "ywc_v03_shu_inline_candidate_epoch_1"
    original_candidate_epoch = state.get(candidate_epoch_name)
    original_global_epoch = state.get("ywc_v03_shu_inline_reservation_epoch")
    if not (world.conditions(event_trigger, world.tag)
            and original_candidate_epoch is not None and original_global_epoch is not None):
        raise AssertionError(("fresh_native_1000_should_initially_be_eligible", dict(state)))
    for name in missing_fields:
        state.pop(name, None)
    if world.conditions(event_trigger, world.tag):
        raise AssertionError(("native_event_trigger_accepted_missing_epoch", missing_fields,
                              dict(state)))

    # Evaluate only a cloned world's full guarded immediate as a negative
    # no-op probe. The withheld popup is never executed on the actual world.
    probe = copy.deepcopy(world)
    probe_state = probe.countries[probe.tag]
    probe_before = dict(probe_state)
    expiry_before = dict(probe.days_until_expiry[probe.tag])
    probe.execute(copy.deepcopy(event_immediate), probe.tag)
    if probe_state != probe_before or probe.days_until_expiry[probe.tag] != expiry_before:
        raise AssertionError(("missing_epoch_guarded_immediate_was_not_noop",
                              missing_fields, probe_before, dict(probe_state)))
    for key in ("ywc_v03_shu_v03_shu_fiscal_register_last_event",
                "ywc_v03_major_event_cooldown", "ywc_v03_shu_inline_served_1"):
        if key not in probe_state and key in probe_before:
            raise AssertionError(("guard_probe_removed_existing_fact", key, probe_before))

    retry = []
    retry_day = None
    for day in (60, 90, 120, 150):
        world.advance_days(30)
        world.elapsed_months += 1
        retry = _pulse_actual_active_arc(world, ROOTS[0][0], day)
        if retry:
            retry_day = day
            break
    if len(retry) != 1 or retry[0]["event"] != "ywc_shu.1000":
        raise AssertionError(("actual_source_did_not_retry_after_missing_epoch_expiry",
                              missing_fields, retry, dict(state), list(world.trace)))
    proof = next(row for row in reversed(world.trace)
                 if row.get("op") == "actual_candidate_ack_proof"
                 and row.get("event") == "ywc_shu.1000")
    retry_pulse = next(row for row in reversed(world.trace)
                       if row.get("op") == "focused_actual_source_pulse"
                       and row.get("delivered", {}).get("event") == "ywc_shu.1000")
    reserved_state = retry_pulse["sender_state_before_actual_immediate"]
    new_global_epoch = reserved_state.get("ywc_v03_shu_inline_reservation_epoch")
    new_candidate_epoch = reserved_state.get(candidate_epoch_name)
    if (new_global_epoch is None or new_candidate_epoch is None
            or new_candidate_epoch != new_global_epoch
            or proof.get("epoch") != new_global_epoch):
        raise AssertionError(("native_retry_did_not_establish_current_candidate_epoch",
                              reserved_state, proof))
    return {"missing_fields": list(missing_fields),
            "old_global_epoch": original_global_epoch,
            "old_candidate_epoch": original_candidate_epoch,
            "rejected_trigger": True,
            "guarded_immediate_noop": True,
            "retry_day": retry_day, "retry": retry[0],
            "reserved_state": reserved_state,
            "proof": proof, "trace": list(world.trace)}



def _run_m1_nonpositive_epoch_proof_mutants():
    world = _new_world()
    _install_real_shu_render(world, _render_real_shu())
    world.run("ywc_v03_initialize_country", world.tag)
    _native_admission(world, *ROOTS[0])
    world.advance_days(30)
    world.elapsed_months += 1
    journal = _journal(world, ROOTS[0][1])
    pulse = field(field(journal, "on_monthly_pulse"), "effect")
    before = len(world.events)
    world.execute(pulse, world.tag)
    if world.events[before:] != [(world.tag, "ywc_shu.1000")]:
        raise AssertionError(("actual_m1_1000_popup_not_pending", dict(world.countries[world.tag])))
    world.events.pop(before)
    event = world.event_defs["ywc_shu.1000"]
    event_trigger = field(event, "trigger")
    immediate = field(event, "immediate")
    results = []
    for invalid_epoch in (0, -1):
        mutant = copy.deepcopy(world)
        state = mutant.countries[mutant.tag]
        state["ywc_v03_shu_inline_reservation_epoch"] = invalid_epoch
        state["ywc_v03_shu_inline_candidate_epoch_1"] = invalid_epoch
        if mutant.conditions(event_trigger, mutant.tag):
            raise AssertionError(("dispatch_accepted_nonpositive_current_epochs",
                                  invalid_epoch, dict(state)))
        before_state = dict(state)
        before_expiry = dict(mutant.days_until_expiry[mutant.tag])
        mutant.execute(copy.deepcopy(immediate), mutant.tag)
        if state != before_state or mutant.days_until_expiry[mutant.tag] != before_expiry:
            raise AssertionError(("nonpositive_epoch_guarded_immediate_was_not_noop",
                                  invalid_epoch, before_state, dict(state)))
        results.append({"epoch": invalid_epoch, "dispatch_rejected": True,
                        "guarded_immediate_noop": True,
                        "source_queue": state.get("ywc_shu_pending_event")})
    return {"mutants": results, "trace": list(world.trace)}


def _run_m1_callback_proof_presence_guards():
    world = _new_world()
    _install_real_shu_render(world, _render_real_shu())
    world.run("ywc_v03_initialize_country", world.tag)
    _native_admission(world, *ROOTS[0])
    world.advance_days(30)
    world.elapsed_months += 1
    journal = _journal(world, ROOTS[0][1])
    pulse = field(field(journal, "on_monthly_pulse"), "effect")
    before = len(world.events)
    world.execute(pulse, world.tag)
    if world.events[before:] != [(world.tag, "ywc_shu.1000")]:
        raise AssertionError(("actual_m1_1000_popup_not_pending", dict(world.countries[world.tag])))
    world.events.pop(before)

    event_immediate = copy.deepcopy(field(world.event_defs["ywc_shu.1000"], "immediate"))
    if len(event_immediate) != 1 or event_immediate[0][0] != "if":
        raise AssertionError(("unexpected_generated_guarded_immediate_shape", event_immediate))
    guarded = event_immediate[0]
    guarded_body = list(guarded[2])
    callback_call = ("ywc_v03_shu_inline_callback_1", "=", "yes")
    if not guarded_body or guarded_body[-1] != callback_call:
        raise AssertionError(("callback_not_last_guarded_immediate_hook", guarded_body[-3:]))
    # Preserve the actual native immediate and generated proof writer, while
    # pausing before the callback consumer so its proof facts can be checked.
    proof_world = copy.deepcopy(world)
    proof_world.execute([(guarded[0], guarded[1], guarded_body[:-1])], proof_world.tag)
    proof_state = proof_world.countries[proof_world.tag]
    proof_names = ("ywc_v03_shu_inline_callback_1",
                   "ywc_v03_shu_inline_callback_candidate_1",
                   "ywc_v03_shu_inline_callback_epoch_1",
                   "ywc_v03_shu_inline_callback_queue_1")
    if any(name not in proof_state for name in proof_names):
        raise AssertionError(("actual_inlineproof_did_not_write_all_presence_facts",
                              {name: proof_state.get(name) for name in proof_names},
                              dict(proof_state)))
    if (proof_state[proof_names[0]] != 1
            or proof_state[proof_names[1]] != 1
            or proof_state[proof_names[2]] != proof_state.get("ywc_v03_shu_inline_reservation_epoch")
            or proof_state[proof_names[3]] != 1000):
        raise AssertionError(("actual_inlineproof_fields_do_not_match_native_candidate",
                              {name: proof_state.get(name) for name in proof_names},
                              dict(proof_state)))

    mutants = []
    for missing_name in proof_names:
        mutant = copy.deepcopy(proof_world)
        mutant_state = mutant.countries[mutant.tag]
        mutant_state.pop(missing_name, None)
        before_state = dict(mutant_state)
        mutant.run("ywc_v03_shu_inline_callback_1", mutant.tag)
        if mutant_state != before_state:
            raise AssertionError(("callback_accepted_missing_inlineproof_field",
                                  missing_name, before_state, dict(mutant_state)))
        mutants.append({"missing_field": missing_name, "callback_noop": True})

    # A real callback-queue proof value of zero is not synthesized by source.
    # This controlled absence mutant checks that a missing callback queue
    # cannot compare equal to a zero-valued live queue/snapshot in Strict.
    zero_queue = copy.deepcopy(proof_world)
    zero_state = zero_queue.countries[zero_queue.tag]
    zero_state["ywc_shu_pending_event"] = 0
    zero_state["ywc_v03_shu_inline_c1_pending_event_value"] = 0
    zero_state.pop("ywc_v03_shu_inline_callback_queue_1", None)
    before_zero = dict(zero_state)
    zero_queue.run("ywc_v03_shu_inline_callback_1", zero_queue.tag)
    if zero_state != before_zero:
        raise AssertionError(("missing_callback_queue_was_treated_as_zero_proof",
                              before_zero, dict(zero_state)))
    mutants.append({"missing_field": "callback_queue_with_zero_live_queue",
                    "callback_noop": True})
    return {"proof_fields": {name: proof_state[name] for name in proof_names},
            "missing_field_mutants": mutants,
            "trace": list(proof_world.trace)}


def _run_actual_full_shu_native_handoffs():
    """Run all six native JEs from fresh M1 admission through source pulses."""
    choices = {
        "ywc_shu.1000": "pilot_state_sichuan",
        "ywc_shu.1001": "central_register",
        "ywc_shu.1002": "time_limited_exemption",
        "ywc_shu.1003": "budget_queue",
        "ywc_shu.1004": "central_appeal",
        "ywc_shu.1005": "refuse_private_advance",
        "ywc_shu.1006": "publish_central_difference",
        "ywc_shu.1007": "central_public_duties",
        "ywc_shu.1008": "review_in_peace",
        "ywc_shu.1009": "establish_central",
        "ywc_shu.1010": "court_seal",
        "ywc_shu.1011": "cap_arrears",
        "ywc_shu.1012": "professional_list",
        "ywc_shu.1013": "professional",
        "ywc_shu.1014": "check_supply",
        "ywc_shu.1015": "accept_appointments",
        "ywc_shu.1017": "settle_service",
        "ywc_shu.1018": "unified_customs",
        "ywc_shu.1019": "publish_books",
        "ywc_shu.1020": "consult_only",
        "ywc_shu.1021": "current_law_review",
        "ywc_shu.1022": "pay_verification",
        "ywc_shu.1023": "central_form",
        "ywc_shu.1024": "retry_after_repair",
        "ywc_shu.1025": "settle_unified",
    }
    world = _new_world()
    _install_real_shu_render(world, _render_real_shu())
    initial_state = dict(world.countries[world.tag])
    world.run("ywc_v03_initialize_country", world.tag)
    _native_admission(world, *ROOTS[0])
    state = world.countries[world.tag]
    if state.get("ywc_v03_active_arc_count") != 1:
        raise AssertionError(("fresh_m1_did_not_start_as_one_native_arc", dict(state)))
    m1_handoff_state = None

    for month in range(1, 101):
        day = month * 30
        world.advance_days(30)
        world.elapsed_months += 1
        _refresh_actual_journal_history(world)
        for slug, _ in ROOTS:
            _pulse_actual_active_arc(world, slug, day, choices)
        _refresh_actual_journal_history(world)
        if (m1_handoff_state is None
                and state.get("ywc_v03_shu_v03_shu_fiscal_register_settled") == 1
                and state.get("ywc_v03_active_arc_count") == 2.0
                and state.get("ywc_v03_visible_task_count") == 2.0):
            m1_handoff_state = dict(state)

    acknowledgements = [row for row in world.trace
                        if row.get("op") == "actual_candidate_ack_proof"]
    by_arc = {slug: [row["event"] for row in acknowledgements if row["arc"] == slug]
              for slug, _ in ROOTS}
    expected_by_arc = {
        ROOTS[0][0]: [f"ywc_shu.{event}" for event in range(1000, 1010)],
        ROOTS[1][0]: [f"ywc_shu.{event}" for event in
                      (1010, 1011, 1012, 1013, 1014, 1015, 1017)],
        ROOTS[2][0]: [f"ywc_shu.{event}" for event in range(1018, 1026)],
    }
    if by_arc != expected_by_arc:
        raise AssertionError(("full_native_source_event_handoffs_mismatch", by_arc,
                              expected_by_arc, dict(state)))
    for proof in acknowledgements:
        candidate = world._shu_candidates[proof["candidate"]]
        if candidate["proof"]["event"] != proof["event"] or proof["epoch"] is None:
            raise AssertionError(("handoff_ack_missing_candidate_or_epoch_proof", proof))
    after_m1 = m1_handoff_state
    if after_m1 is None:
        raise AssertionError(("real_m1_handoff_not_observed", dict(state)))
    for name in ("ywc_v03_active_arc_count", "ywc_v03_visible_task_count"):
        if after_m1.get(name) != 2.0:
            raise AssertionError(("real_m1_handoff_counter_mismatch", name,
                                  after_m1))
    expected_history = {
        "ywc_je_v03_shu_register_pilot": "complete",
        "ywc_je_v03_shu_fiscal_settlement": "complete",
        "ywc_je_v03_shu_service_contract": "complete",
        "ywc_je_v03_shu_port_customs": "complete",
        "ywc_je_v03_shu_service_appointments": "complete",
        "ywc_je_v03_shu_service_successor": "complete",
    }
    if world.history[world.tag] != expected_history:
        raise AssertionError(("six_native_je_lifecycle_handoff_mismatch",
                              world.history[world.tag], dict(state)))
    if (state.get("ywc_v03_active_arc_count") != 0
            or state.get("ywc_v03_visible_task_count") != 0
            or _source_queues(world)):
        raise AssertionError(("native_handoffs_did_not_release_source_slots",
                              dict(state), _source_queues(world)))
    source_event_days = {
        row["delivered"]["event"]: row["day"]
        for row in world.trace
        if row.get("op") == "focused_actual_source_pulse" and row.get("delivered")
    }
    return {"initial_state": initial_state, "by_arc": by_arc,
            "acknowledgements": acknowledgements,
            "m1_handoff_state_delta": after_m1,
            "history": dict(world.history[world.tag]),
            "source_event_days": source_event_days,
            "final_state": dict(state), "trace": list(world.trace)}


def _run_port_notice_presence_and_same_id_priority():
    choices = {"ywc_shu.1010": "garrison_seal",
               "ywc_shu.1011": "local_ledger",
               "ywc_shu.1012": "incumbents_only",
               "ywc_shu.1013": "legacy_cap",
               "ywc_shu.1014": "reduce_target",
               "ywc_shu.1015": "vacant_cap",
               "ywc_shu.1016": "resume_service_contract",
               "ywc_shu.1021": "current_law_review",
               "ywc_shu.1022": "pay_verification",
               "ywc_shu.1023": "share_form",
               "ywc_shu.1024": "retry_after_repair"}
    world, _ = _run_monthly_fairness_order((ROOTS[1], ROOTS[2]), choices)
    state = world.countries[world.tag]
    deliveries = []
    queue_name = "ywc_shu_port_notice_pending_event"
    for month in range(31, 47):
        day = month * 30
        world.advance_days(30)
        world.elapsed_months += 1
        _refresh_actual_journal_history(world)
        if day == 990:
            # Controlled business fact for the authored in-default notice path.
            state["in_default"] = True
        service_rows = _pulse_actual_active_arc(world, ROOTS[1][0], day, choices)
        if day == 1230:
            port_rows = _pulse_actual_active_arc(world, ROOTS[2][0], day, choices)
            if port_rows or state.get(queue_name) != 1024:
                raise AssertionError(("native_port_notice_sender_not_observed", day,
                                      port_rows, dict(state)))
            probe = copy.deepcopy(world)
            probe_state = probe.countries[probe.tag]
            probe_state.pop("ywc_v03_major_event_cooldown", None)
            probe.days_until_expiry[probe.tag].pop("ywc_v03_major_event_cooldown", None)
            # The authored normal queue was ACKed just before the notice was
            # created. Add it only on this copy to compare same-ID priority.
            probe_state["ywc_shu_port_pending_event"] = 1024
            self_name = "ywc_v03_shu_inline_candidate_31"
            ordinary_name = "ywc_v03_shu_inline_candidate_29"
            if not probe.conditions([[self_name, "=", "yes"]], probe.tag):
                raise AssertionError(("present_zero_notice_was_not_a_candidate",
                                      dict(probe_state)))
            if probe.conditions([[ordinary_name, "=", "yes"]], probe.tag):
                raise AssertionError(("ordinary_same_id_ignored_present_notice_priority",
                                      dict(probe_state)))
            absent = copy.deepcopy(probe)
            absent.countries[absent.tag].pop(queue_name, None)
            if absent.conditions([[self_name, "=", "yes"]], absent.tag):
                raise AssertionError(("absent_notice_queue_accepted_as_presence",
                                      dict(absent.countries[absent.tag])))
            if not absent.conditions([[ordinary_name, "=", "yes"]], absent.tag):
                raise AssertionError(("absence_did_not_reenable_exact_ordinary_1024",
                                      dict(absent.countries[absent.tag])))
            world.trace.append({"op": "controlled_port_notice_presence_zero_priority",
                                "day": day, "notice_queue_value": 1024,
                                "same_id_ordinary_queue_value": 1024,
                                "notice_candidate": True, "ordinary_candidate": False,
                                "absent_notice_candidate": False,
                                "absence_reenables_ordinary_candidate": True,
                                "natural_same_id_coexistence": False,
                                "controlled_zero_variant": False})
        else:
            if day == 1380:
                if not world.conditions([["ywc_v03_shu_inline_candidate_31", "=", "yes"]],
                                        world.tag):
                    raise AssertionError(("port_notice_candidate_not_eligible_after_cooldown",
                                          dict(state)))
                if not world.conditions([["ywc_v03_shu_inline_turn_31", "=", "yes"]],
                                        world.tag):
                    raise AssertionError(("port_notice_turn_not_selected_by_authored_fairness",
                                          dict(state)))
                if world.conditions([["ywc_v03_shu_inline_candidate_29", "=", "yes"]],
                                    world.tag):
                    raise AssertionError(("ordinary_same_id_candidate_bypassed_notice",
                                          dict(state)))
            port_rows = _pulse_actual_active_arc(world, ROOTS[2][0], day, choices)
        if day == 1350:
            # The authored tracker may refresh the notice queue during its
            # pulse; set the presence-mode-zero variant only after that real
            # source work, one opportunity before the actual retry.
            state[queue_name] = 0
            state["ywc_shu_port_pending_event"] = 1024
            probe = copy.deepcopy(world)
            probe_state = probe.countries[probe.tag]
            probe_state.pop("ywc_v03_major_event_cooldown", None)
            probe.days_until_expiry[probe.tag].pop("ywc_v03_major_event_cooldown", None)
            if not probe.conditions([["ywc_v03_shu_inline_candidate_31", "=", "yes"]],
                                    probe.tag):
                raise AssertionError(("present_zero_notice_was_not_a_candidate",
                                      dict(probe_state)))
            if probe.conditions([["ywc_v03_shu_inline_candidate_29", "=", "yes"]],
                                probe.tag):
                raise AssertionError(("ordinary_same_id_ignored_present_notice_priority",
                                      dict(probe_state)))
            absent = copy.deepcopy(probe)
            absent.countries[absent.tag].pop(queue_name, None)
            if absent.conditions([["ywc_v03_shu_inline_candidate_31", "=", "yes"]],
                                 absent.tag):
                raise AssertionError(("absent_notice_queue_accepted_as_presence",
                                      dict(absent.countries[absent.tag])))
            if not absent.conditions([["ywc_v03_shu_inline_candidate_29", "=", "yes"]],
                                     absent.tag):
                raise AssertionError(("absence_did_not_reenable_exact_ordinary_1024",
                                      dict(absent.countries[absent.tag])))
            world.trace.append({"op": "controlled_port_notice_presence_zero_priority",
                                "day": day, "notice_queue_value": 0,
                                "same_id_ordinary_queue_value": 1024,
                                "notice_candidate": True, "ordinary_candidate": False,
                                "absent_notice_candidate": False,
                                "absence_reenables_ordinary_candidate": True,
                                "natural_same_id_coexistence": False,
                                "controlled_zero_variant": True})
        deliveries.extend(service_rows)
        deliveries.extend(port_rows)
    actual_notice = [row for row in deliveries
                     if row.get("event") == "ywc_shu.1024" and row.get("day") == 1380]
    if len(actual_notice) != 1 or actual_notice[0].get("option") != "retry_after_repair":
        raise AssertionError(("actual_port_notice_ack_mismatch", deliveries,
                              dict(state)))
    proof = next(row for row in reversed(world.trace)
                 if row.get("op") == "actual_candidate_ack_proof"
                 and row.get("event") == "ywc_shu.1024")
    if proof["candidate"] != 31 or proof["queue"] != queue_name:
        raise AssertionError(("port_notice_used_wrong_candidate_or_queue", proof))
    if proof["queue_value_before"] != 1024:
        raise AssertionError(("actual_source_notice_queue_value_mismatch", proof))
    if proof["sibling_queues_before"] != {"ywc_shu_port_pending_event": 1024}:
        raise AssertionError(("same_id_ordinary_sibling_not_snapshotted", proof))
    if proof["sibling_queues_after"] != proof["sibling_queues_before"]:
        raise AssertionError(("notice_ack_changed_ordinary_sibling", proof))
    if queue_name in state or state.get("ywc_shu_port_pending_event") != 1024:
        raise AssertionError(("notice_ack_did_not_preserve_selected_sibling_only",
                              dict(state)))
    return {"delivery": actual_notice[0], "proof": proof,
            "final_state": dict(state), "trace": list(world.trace)}


class ShuActualFairnessBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
        validate_inline_catalog(cls.catalog)
        cls.adapter = render_inline_country_adapters(cls.catalog)
        cls.outputs = _render_real_shu()

    def test_real_renderer_loads_source_bound_helpers_and_rejects_collisions(self):
        arcs = [arc for arc in self.catalog["arcs"]
                if arc.get("era") == "foundation"]
        self.assertEqual(len(arcs), 3)
        branches = [branch for arc in arcs
                    for branch in arc["inline_delivery_adapter"]["branches"]]
        self.assertEqual(len(branches), 31)
        self.assertEqual({branch["journal"] for branch in branches},
                         {journal_id for arc in arcs for journal_id in
                          [journal["id"] for journal in arc["journals"]
                           if journal["id"] in self.adapter["journal_scripts"]]})
        outputs_by_name = {path.name: text for path, text in self.outputs.items()}
        self.assertIn("ywc_v03_delivery_shu_effects.txt", outputs_by_name)
        self.assertIn("ywc_v03_delivery_shu_triggers.txt", outputs_by_name)
        world = _new_world()
        _install_real_shu_render(world, self.outputs)
        with self.assertRaisesRegex(AssertionError, "generated_shu_helper_collision"):
            _install_real_shu_render(world, self.outputs)
        effects = _definitions(outputs_by_name["ywc_v03_delivery_shu_effects.txt"])
        triggers = _definitions(outputs_by_name["ywc_v03_delivery_shu_triggers.txt"])
        self.assertTrue(effects and triggers)
        for journal_id, generated_script in self.adapter["journal_scripts"].items():
            source_fields = _definitions(journal_id + " = " + generated_script)[journal_id]
            rendered_fields = _definitions(outputs_by_name[
                "ywc_v03_country_shu_journal.txt"])[journal_id]
            self.assertEqual(field(source_fields, "on_monthly_pulse"),
                             field(rendered_fields, "on_monthly_pulse"), journal_id)

    def test_shu_validator_rejects_foreign_and_nested_native_receipt_mutants(self):
        event_id = "ywc_shu.1000"
        for mutant in ("foreign_helper", "nested_receipt"):
            catalog = copy.deepcopy(self.catalog)
            event = next(event for arc in catalog["arcs"]
                         for event in arc.get("events", [])
                         if event.get("id") == event_id)
            immediate = event["immediate"]
            if mutant == "foreign_helper":
                event["immediate"] = (immediate[:-1] +
                                      " ywc_v03_shu_inline_foreign_probe = yes }")
            else:
                receipt = "ywc_v03_shu_v03_shu_fiscal_register_last_event"
                event["immediate"] = (immediate[:-1] +
                    " if = { limit = { always = yes } set_variable = { name = " +
                    receipt + " value = 1000 } } }")
            with self.subTest(mutant=mutant), self.assertRaises(ValueError):
                validate_inline_catalog(catalog)

    def test_shu_validator_binds_direct_add_successor_identity(self):
        catalog = copy.deepcopy(self.catalog)
        arc = next(arc for arc in catalog["arcs"]
                   if arc.get("slug") == ROOTS[1][0])
        event = next(event for event in arc["events"]
                     if event.get("id") == "ywc_shu.1015")
        option = next(option for option in event["options"]
                      if option.get("key") == "accept_appointments")
        self.assertIn("ywc_je_v03_shu_service_successor", option["effect"])
        option["effect"] = option["effect"].replace(
            "ywc_je_v03_shu_service_successor", "ywc_je_v03_shu_port_customs")
        # Recompute the ordinary metadata projection as an attacker would;
        # only a binding to the frozen source successor should reject this.
        arc["inline_delivery_adapter"]["direct_adds"] = inline_adapter._kor_direct_adds(arc)
        with self.assertRaises(ValueError):
            validate_inline_catalog(catalog)

    def test_fresh_m1_alone_is_natively_admitted_and_drives_real_first_1000_callback(self):
        result = _run_fresh_m1_first_callback()
        self.assertEqual(result["active_count"], 1)
        self.assertEqual(result["visible_count"], 1)
        self.assertEqual(result["first_callback"],
                         {"event": FRESH_M1_EVENT, "day": 30,
                          "option": "pilot_state_sichuan"})

    def test_fresh_initialize_drives_all_six_native_je_handoffs_and_actual_ack_epochs(self):
        result = _run_actual_full_shu_native_handoffs()
        self.assertEqual(result["initial_state"].get("ywc_v03_initialized"), None)
        self.assertEqual(result["initial_state"].get("ywc_v03_release_version"), None)
        self.assertEqual(result["by_arc"][ROOTS[0][0]],
                         [f"ywc_shu.{event}" for event in range(1000, 1010)])
        self.assertEqual(result["by_arc"][ROOTS[1][0]],
                         [f"ywc_shu.{event}" for event in
                          (1010, 1011, 1012, 1013, 1014, 1015, 1017)])
        self.assertEqual(result["by_arc"][ROOTS[2][0]],
                         [f"ywc_shu.{event}" for event in range(1018, 1026)])
        self.assertEqual(len(result["acknowledgements"]), 25)
        self.assertEqual(result["m1_handoff_state_delta"]["ywc_v03_active_arc_count"], 2.0)
        self.assertEqual(result["m1_handoff_state_delta"]["ywc_v03_visible_task_count"], 2.0)
        self.assertTrue(all(row["epoch"] is not None
                            for row in result["acknowledgements"]))
        self.assertEqual(set(result["history"].values()), {"complete"})
        self.assertEqual(result["source_event_days"]["ywc_shu.1017"] -
                         result["source_event_days"]["ywc_shu.1015"], 180)
        paid_state = result["final_state"]
        self.assertEqual(paid_state["ywc_shu_service_cost_paid"], 1.0)
        self.assertEqual(paid_state["ywc_shu_service_paid_amount"], 500.0)
        self.assertEqual(paid_state["ywc_shu_port_fee_paid"], 1.0)
        self.assertEqual(paid_state["ywc_shu_port_fee_amount"], 500.0)
        self.assertEqual(result["final_state"]["ywc_v03_active_arc_count"], 0.0)
        self.assertEqual(result["final_state"]["ywc_v03_visible_task_count"], 0.0)

    def test_fresh_m1_actual_1001_capacity_auxiliary_retries_without_invented_queue(self):
        result = _run_fresh_m1_capacity_auxiliary_flow()
        self.assertEqual([row["event"] for row in result["deliveries"]],
                         ["ywc_shu.1000", "ywc_shu.1001", "ywc_shu.1001"])
        self.assertEqual([row["option"] for row in result["deliveries"]],
                         ["pilot_state_sichuan", "wait_for_office", "wait_for_office"])
        self.assertEqual(result["final_state"].get("ywc_shu_waiting_for_capacity"), 1)

    def test_actual_legacy_registration_admits_service_and_port_as_two_roots(self):
        world = _new_world(legacy_result=1)
        world.run("ywc_v03_initialize_country", world.tag)
        state = world.countries[world.tag]
        self.assertEqual(state.get("ywc_v03_shu_v03_shu_fiscal_register_settled"), 1)
        self.assertFalse(world.conditions(field(_journal(world, ROOTS[0][1]), "possible"), world.tag))
        self.assertEqual((state.get("ywc_v03_active_arc_count"),
                          state.get("ywc_v03_visible_task_count")), (0, 0))
        for slug, journal_id in ROOTS[1:]:
            _native_admission(world, slug, journal_id)
        self.assertEqual((state.get("ywc_v03_active_arc_count"),
                          state.get("ywc_v03_visible_task_count")), (2, 2))
        self.assertEqual(set(world.active[world.tag]), {journal_id for _, journal_id in ROOTS[1:]})

    def test_two_real_source_orders_have_equal_ten_callback_fairness(self):
        orders = (
            (ROOTS[1], ROOTS[2]),
            (ROOTS[2], ROOTS[1]),
        )
        summaries = []
        for order in orders:
            with self.subTest(order=[slug for slug, _ in order]):
                world, summary = _run_monthly_fairness_order(order)
                summaries.append(summary)
                counts = summary["counts"]
                self.assertEqual(sum(counts.values()), 10, world.trace[-1])
                self.assertEqual(sorted(counts.values()), [5, 5],
                                 {"order": summary["order"], "counts": counts,
                                  "delivery_days": summary["delivery_days"],
                                  "source_queues_after_30_months":
                                      summary["source_queues_after_30_months"]})
        self.assertEqual([summary["expected_opportunity_days"] for summary in summaries],
                         [list(EXPECTED_OPPORTUNITY_DAYS)] * 2)

    def test_actual_service_notice_rejects_absence_and_zero_snapshot_without_touching_siblings(self):
        # Observe a real 1016 sent by the authored monthly source. Probe stale
        # queue states on copies so the real popup can still take its actual
        # source ACK and prove sibling retention in the original world.
        actual_delivery = _deliver_actual_event
        probes = []

        def probe_before_actual_delivery(world, event_id, day, overrides=None):
            if event_id == "ywc_shu.1016":
                state = world.countries[world.tag]
                queue_name = "ywc_shu_service_notice_pending_event"
                self.assertIn(queue_name, state)
                original_value = state[queue_name]
                self.assertEqual(original_value, 1016)
                event = world.event_defs[event_id]
                trigger = field(event, "trigger")
                candidate_id = int(state["ywc_v03_shu_inline_reservation"])
                arc = world._shu_candidates[candidate_id]["arc"]
                slot = world._shu_slot_by_arc[arc["slug"]]
                faults = ("absent", "zero", "epoch", "callback_queue",
                          "phase", "expiry", "served")
                for fault in faults:
                    probe = copy.deepcopy(world)
                    probe_state = probe.countries[probe.tag]
                    if fault == "absent":
                        probe_state.pop(queue_name, None)
                    else:
                        if fault == "zero":
                            probe_state[queue_name] = 0
                        elif fault == "epoch":
                            probe_state["ywc_v03_shu_inline_reservation_epoch"] += 1
                        elif fault == "callback_queue":
                            probe_state["ywc_v03_shu_inline_c" + str(candidate_id) +
                                        "_service_notice_pending_event_value"] = 0
                        elif fault == "phase":
                            probe_state.pop("ywc_v03_shu_inline_live_service_contract", None)
                        elif fault == "expiry":
                            probe_state.pop("ywc_v03_shu_inline_timer", None)
                        elif fault == "served":
                            probe_state["ywc_v03_shu_inline_served_" + str(slot)] = \
                                probe_state["ywc_v03_shu_inline_round"]
                    before = dict(probe_state)
                    legal = probe.conditions(trigger, probe.tag)
                    self.assertFalse(legal, (fault, event_id, day, before))
                    self.assertEqual(probe.countries[probe.tag], before,
                                     "a rejected stale trigger must not mutate source facts")
                    world.trace.append({"op": "rejected_stale_callback_probe",
                                        "fault": fault, "event": event_id, "day": day,
                                        "candidate": candidate_id,
                                        "arc": arc["slug"], "source_queue": queue_name,
                                        "trigger_accepted": legal,
                                        "facts_unchanged": True})
                    probes.append(fault)
                delivered = actual_delivery(world, event_id, day, overrides)
                ack = next(row for row in reversed(world.trace)
                           if row.get("op") == "actual_candidate_ack_proof"
                           and row.get("event") == event_id)
                self.assertNotIn(queue_name, ack["sibling_queues_before"])
                self.assertEqual(ack["sibling_queues_after"],
                                 ack["sibling_queues_before"])
                return delivered
            return actual_delivery(world, event_id, day, overrides)

        globals()["_deliver_actual_event"] = probe_before_actual_delivery
        try:
            world, summary = _run_monthly_fairness_order((ROOTS[1], ROOTS[2]))
        finally:
            globals()["_deliver_actual_event"] = actual_delivery
        self.assertEqual(probes, ["absent", "zero", "epoch", "callback_queue",
                                  "phase", "expiry", "served"])
        self.assertEqual(summary["counts"], {ROOTS[1][0]: 5, ROOTS[2][0]: 5})
        self.assertTrue(any(row.get("op") == "actual_candidate_ack_proof"
                            and row.get("event") == "ywc_shu.1016"
                            for row in world.trace))

    def test_port_paid_option_runs_native_request_handoff(self):
        # Keep the 30-month fairness schedule intact, but select source-authored
        # port options that enter receipt verification and leave its actual
        # next-stage request in the source queue.
        choices = {"ywc_shu.1021": "current_law_review",
                   "ywc_shu.1022": "pay_verification"}
        world, summary = _run_monthly_fairness_order((ROOTS[1], ROOTS[2]), choices)
        port = world.countries[world.tag]
        delivery = summary["delivery_events"][ROOTS[2][0]]
        self.assertIn({"event": "ywc_shu.1021", "day": 570,
                       "option": "current_law_review"}, delivery)
        self.assertIn({"event": "ywc_shu.1022", "day": 840,
                       "option": "pay_verification"}, delivery)
        self.assertEqual(port.get("ywc_shu_port_receipts_checked"), 1)
        self.assertEqual(port.get("ywc_shu_port_pending_event"), 1023)
        self.assertEqual(summary["counts"], {ROOTS[1][0]: 5, ROOTS[2][0]: 5})

    def test_port_1024_notice_recovers_after_cooldown_and_preserves_same_id_sibling(self):
        result = _run_port_notice_presence_and_same_id_priority()
        self.assertEqual(result["delivery"],
                         {"event": "ywc_shu.1024", "day": 1380,
                          "option": "retry_after_repair"})
        proof = result["proof"]
        self.assertEqual((proof["candidate"], proof["queue"], proof["epoch"]),
                         (31, "ywc_shu_port_notice_pending_event", 16.0))
        self.assertEqual(proof["sibling_queues_before"],
                         {"ywc_shu_port_pending_event": 1024})
        self.assertEqual(proof["sibling_queues_after"],
                         proof["sibling_queues_before"])
        probes = [row for row in result["trace"]
                  if row.get("op") == "controlled_port_notice_presence_zero_priority"]
        self.assertEqual([row["day"] for row in probes], [1230, 1350])
        self.assertFalse(probes[0]["natural_same_id_coexistence"])
        self.assertTrue(probes[1]["controlled_zero_variant"])

    def test_m1_1001_expired_rejection_restores_capacity_aux_then_real_retry_acks(self):
        # Obtain the auxiliary only through the real 1000 -> pilot option ->
        # 1001 wait path. The three values below are controlled state variants
        # after that native wait has established the fact.
        for aux_value in (0, 1, 7):
            with self.subTest(aux_value=aux_value):
                world = _new_world()
                _install_real_shu_render(world, _render_real_shu())
                world.run("ywc_v03_initialize_country", world.tag)
                _native_admission(world, *ROOTS[0])
                for day in (30, 60, 90, 120):
                    world.advance_days(30)
                    world.elapsed_months += 1
                    deliveries = _pulse_actual_active_arc(world, ROOTS[0][0], day)
                    expected = {30: "ywc_shu.1000", 120: "ywc_shu.1001"}.get(day)
                    self.assertEqual([row["event"] for row in deliveries],
                                     [expected] if expected else [])
                state = world.countries[world.tag]
                self.assertEqual(state.get("ywc_shu_waiting_for_capacity"), 1)
                state["ywc_shu_waiting_for_capacity"] = aux_value

                for day in (150, 180):
                    world.advance_days(30)
                    world.elapsed_months += 1
                    self.assertEqual(_pulse_actual_active_arc(world, ROOTS[0][0], day), [])

                world.advance_days(30)
                world.elapsed_months += 1
                journal = _journal(world, ROOTS[0][1])
                pulse = field(field(journal, "on_monthly_pulse"), "effect")
                before = len(world.events)
                world.execute(pulse, world.tag)
                emitted = list(world.events[before:])
                self.assertEqual(emitted, [(world.tag, "ywc_shu.1001")])
                world.events.pop(before)
                self.assertNotIn("ywc_shu_waiting_for_capacity", state,
                                 "native sender consumes the auxiliary before popup dispatch")

                # Invalidate the authored pilot-state trigger while the actual
                # popup is pending. Do not run its immediate or any option.
                state.pop("ywc_shu_v03_pilot_state", None)
                trigger = field(world.event_defs["ywc_shu.1001"], "trigger")
                rejected_state = dict(state)
                self.assertFalse(world.conditions(trigger, world.tag))
                self.assertEqual(state, rejected_state)
                world.trace.append({"op": "rejected_m1_pilot_state_popup",
                                    "day": 210, "aux_value_before_sender": aux_value,
                                    "trigger_accepted": False, "facts_unchanged": True})

                world.advance_days(1)
                world.run("ywc_v03_shu_inline_prepare", world.tag)
                self.assertIn("ywc_shu_waiting_for_capacity", state,
                              "expired failed popup must restore the sender-owned auxiliary")
                self.assertEqual(state["ywc_shu_waiting_for_capacity"], aux_value)
                self.assertNotIn("ywc_v03_shu_inline_reservation", state)

                # Restore the actual pilot fact and allow a fresh native source
                # pulse to reserve and deliver the still-pending 1001 queue.
                state["ywc_shu_v03_pilot_state"] = 1
                world.advance_days(29)
                world.elapsed_months += 1
                before = len(world.events)
                world.execute(pulse, world.tag)
                retry = list(world.events[before:])
                self.assertEqual(retry, [(world.tag, "ywc_shu.1001")])
                world.events.pop(before)
                delivered = _deliver_actual_event(world, "ywc_shu.1001", 240)
                self.assertEqual(delivered["option"], "wait_for_office")
                ack = next(row for row in reversed(world.trace)
                           if row.get("op") == "actual_candidate_ack_proof"
                           and row.get("event") == "ywc_shu.1001")
                self.assertEqual(ack["queue_value_before"], 1001)
                self.assertNotIn("ywc_shu_pending_event", state)
                self.assertEqual(state.get("ywc_shu_waiting_for_capacity"), 1,
                                 "native wait option may establish a new auxiliary value")

    def test_m1_stale_epoch_expiry_cleans_candidate_restores_only_owned_aux_and_retries(self):
        cases = ((0, None, False, "epoch_mismatch"),
                 (1, None, False, "epoch_mismatch"),
                 (7, None, False, "epoch_mismatch"),
                 (0, 7, False, "epoch_mismatch"),
                 (7, 0, False, "epoch_mismatch"),
                 (1, None, True, "epoch_mismatch"),
                 (0, None, False, "candidate_epoch_missing"),
                 (1, None, False, "invalid_reservation_id"),
                 (1, None, False, "invalid_reservation_id_zero"),
                 (1, None, False, "invalid_reservation_id_negative"))
        for snapshot_value, newer_value, missing, fault in cases:
            with self.subTest(snapshot_value=snapshot_value,
                              newer_value=newer_value, snapshot_missing=missing,
                              reservation_fault=fault):
                result = _run_m1_expired_stale_epoch(snapshot_value, newer_value,
                                                      missing, fault)
                expired = result["after_expiry"]
                if result["snapshot_missing"]:
                    self.assertNotIn("ywc_shu_waiting_for_capacity", expired)
                elif newer_value is not None:
                    self.assertEqual(expired.get("ywc_shu_waiting_for_capacity"),
                                     newer_value)
                else:
                    self.assertEqual(expired.get("ywc_shu_waiting_for_capacity"),
                                     snapshot_value)
                self.assertEqual(result["retry"]["event"], "ywc_shu.1001")
                self.assertEqual(result["retry"]["option"], "wait_for_office")
                self.assertIn(result["retry_day"], (240, 270, 300))
                self.assertNotEqual(result["proof"]["epoch"],
                                    result["candidate_epoch"])

    def test_native_1000_rejects_single_or_double_missing_epochs_then_retries_from_source(self):
        faults = (("global_epoch_missing", ("ywc_v03_shu_inline_reservation_epoch",)),
                  ("candidate_epoch_missing", ("ywc_v03_shu_inline_candidate_epoch_1",)),
                  ("both_epochs_missing", ("ywc_v03_shu_inline_reservation_epoch",
                                            "ywc_v03_shu_inline_candidate_epoch_1")))
        for name, missing_fields in faults:
            with self.subTest(fault=name):
                result = _run_m1_missing_epoch_guard_and_source_retry(missing_fields)
                self.assertTrue(result["rejected_trigger"])
                self.assertTrue(result["guarded_immediate_noop"])
                self.assertIn(result["retry_day"], (60, 90, 120, 150))
                self.assertEqual(result["retry"]["event"], "ywc_shu.1000")
                self.assertIsNotNone(result["proof"]["epoch"])

    def test_actual_dispatch_rejects_present_zero_or_negative_epoch_proofs(self):
        result = _run_m1_nonpositive_epoch_proof_mutants()
        self.assertEqual([row["epoch"] for row in result["mutants"]], [0, -1])
        self.assertTrue(all(row["dispatch_rejected"] and row["guarded_immediate_noop"]
                            for row in result["mutants"]))
        self.assertTrue(all(row["source_queue"] == 1000 for row in result["mutants"]))

    def test_actual_inlineproof_presence_fields_gate_callback_including_zero_queue_mutant(self):
        result = _run_m1_callback_proof_presence_guards()
        self.assertEqual(len(result["proof_fields"]), 4)
        self.assertEqual(len(result["missing_field_mutants"]), 5)
        self.assertTrue(all(row["callback_noop"]
                            for row in result["missing_field_mutants"]))

    def test_callback_alone_cannot_ack_without_native_event_immediate(self):
        world = _new_world()
        _install_real_shu_render(world, _render_real_shu())
        world.run("ywc_v03_initialize_country", world.tag)
        _native_admission(world, *ROOTS[0])
        world.advance_days(30)
        world.elapsed_months += 1
        journal = _journal(world, ROOTS[0][1])
        pulse = field(field(journal, "on_monthly_pulse"), "effect")
        before_events = len(world.events)
        world.execute(pulse, world.tag)
        self.assertEqual(world.events[before_events:], [(world.tag, "ywc_shu.1000")])
        event = world.events.pop(before_events)[1]
        candidate_id = int(world.countries[world.tag]["ywc_v03_shu_inline_reservation"])
        before_callback = copy.deepcopy(world.countries[world.tag])
        # This generated helper is intentionally callable in isolation by the
        # interpreter; it must not consume the source queue or mark the arc.
        world.run(f"ywc_v03_shu_inline_callback_{candidate_id}", world.tag)
        self.assertEqual(world.countries[world.tag], before_callback)
        self.assertEqual(world.countries[world.tag].get("ywc_shu_pending_event"), 1000)
        self.assertNotIn("ywc_v03_shu_inline_served_1", world.countries[world.tag])
        self.assertNotIn("ywc_v03_major_event_cooldown", world.days_until_expiry[world.tag])

        # Only the actual event immediate writes its native receipt, runs the
        # post-immediate callback for this candidate/epoch, and acknowledges.
        delivered = _deliver_actual_event(world, event, 30)
        self.assertEqual(delivered["option"], "pilot_state_sichuan")
        proof = next(row for row in reversed(world.trace)
                     if row.get("op") == "actual_candidate_ack_proof")
        self.assertEqual((proof["candidate"], proof["event"]), (candidate_id, event))
        self.assertEqual(world.countries[world.tag].get("ywc_shu_pending_event"), 1001,
                         "the authored option may enqueue the next native M1 stage after ACK")
        self.assertIn("ywc_v03_major_event_cooldown", world.days_until_expiry[world.tag])

    def test_historical_dispatch_receipt_cannot_ack_fresh_service_reservation(self):
        world = _new_world(legacy_result=1)
        _install_real_shu_render(world, _render_real_shu())
        world.run("ywc_v03_initialize_country", world.tag)
        _native_admission(world, *ROOTS[1])
        state = world.countries[world.tag]
        # Controlled historical native receipt only. There is no current 1010
        # immediate in this execution yet.
        state["ywc_v03_shu_event_dispatch"] = 1010
        world.advance_days(30)
        world.elapsed_months += 1
        journal = _journal(world, ROOTS[1][1])
        pulse = field(field(journal, "on_monthly_pulse"), "effect")
        before = len(world.events)
        world.execute(pulse, world.tag)
        emitted = list(world.events[before:])
        self.assertEqual(emitted, [(world.tag, "ywc_shu.1010")])
        candidate_id = int(state["ywc_v03_shu_inline_reservation"])
        self.assertEqual(candidate_id, 11)
        self.assertEqual(state.get("ywc_v03_shu_event_dispatch"), 1010)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1010)

        probe = copy.deepcopy(world)
        probe_state = probe.countries[probe.tag]
        before_callback = copy.deepcopy(probe_state)
        probe.run(f"ywc_v03_shu_inline_callback_{candidate_id}", probe.tag)
        self.assertEqual(probe_state, before_callback,
                         "historical dispatch id must not count as this popup's immediate receipt")
        self.assertEqual(probe_state.get("ywc_v03_shu_inline_served_2"),
                         before_callback.get("ywc_v03_shu_inline_served_2"))
        self.assertEqual(probe_state.get("ywc_shu_service_pending_event"), 1010)
        self.assertEqual(probe_state.get("ywc_v03_shu_inline_reservation"), candidate_id)
        world.trace.append({"op": "historical_dispatch_callback_negative",
                            "event": "ywc_shu.1010", "candidate": candidate_id,
                            "historical_dispatch": 1010,
                            "callback_alone_changed_facts": False})

        world.events.pop(before)
        delivered = _deliver_actual_event(world, "ywc_shu.1010", 30)
        proof = next(row for row in reversed(world.trace)
                     if row.get("op") == "actual_candidate_ack_proof"
                     and row.get("event") == "ywc_shu.1010")
        self.assertEqual(delivered["option"], "garrison_seal")
        self.assertEqual(proof["candidate"], candidate_id)
        # The acknowledged 1010 queue is cleared by its native option, which
        # immediately schedules the source's legitimate successor 1011.
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1011)
        self.assertIn("ywc_v03_major_event_cooldown", world.days_until_expiry[world.tag])


if __name__ == "__main__":
    unittest.main()
