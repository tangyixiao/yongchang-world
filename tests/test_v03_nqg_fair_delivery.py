"""NQG actual-source fairness baseline for the unfixed native scheduler.

Only engine-owned country/world facts are fixtures. Startup initialization,
each first JE's possible/immediate, native monthly pulse, event trigger and
immediate, and the player's legal defer option are executed from source.
"""
import unittest
from pathlib import Path

from tests.shu_kor_strict_review_runtime import Strict, field
from tests.clausewitz_harness import parse


ARCS = (
    ("v03_nqg_winter_court", "ywc_je_v03_nqg_winter_court", "ywc_nqg_winter_pending", 1000),
    ("v03_nqg_hunting_rights", "ywc_je_v03_nqg_hunting_rights", "ywc_nqg_hunting_pending", 1010),
    ("v03_nqg_northern_port", "ywc_je_v03_nqg_northern_port", "ywc_nqg_port_pending", 1020),
)


def _facts():
    # All fixtures below are engine-owned country/state facts. Arc lifecycle,
    # queues, timers, notices, receipts and scheduler witnesses start absent.
    return {"NQG": {
        "yearly_gross_income": 52000,
        "gold_reserves": 100000,
        "bureaucracy": 100,
        "net_fixed_income": 100,
        "scaled_debt": 0,
        "government_legitimacy": 80,
        "states": [{"owned": True, "region": "s:STATE_SAKHALIN", "market_access": 1.0,
                    "buildings": [{"type": "building_government_administration",
                                   "occupancy": 1.0, "shortage": False, "groups": []}],
                    "pops": []}],
    }}


class NqgActualWorld(Strict):
    def __init__(self):
        super().__init__("nqg")
        root = Path(__file__).resolve().parents[1]
        for relative, destination in (
            ("yongchang_world/common/scripted_effects/ywc_v03_delivery_nqg_effects.txt", self.effects),
            ("yongchang_world/common/scripted_triggers/ywc_v03_delivery_nqg_triggers.txt", self.trigger_defs),
        ):
            path = root / relative
            if not path.is_file():
                raise AssertionError(("generated_nqg_adapter_missing", str(path)))
            definitions = {key: body for key, _, body in parse(path.read_text(encoding="utf-8-sig"))}
            collisions = set(definitions).intersection(destination)
            if collisions:
                raise AssertionError(("generated_helper_name_collision", str(path), sorted(collisions)))
            destination.update(definitions)
        self.countries = _facts()
        self.active = {"NQG": []}
        self.history = {"NQG": {}}
        self.trace = []
        self.ack_boundaries = []

    def run(self, name, tag="NQG"):
        if name.startswith("ywc_v03_nqg_inline_ack_"):
            self.ack_boundaries.append((name, dict(self.countries[tag])))
        return super().run(name, tag)

    def condition(self, node, tag):
        key, op, value = node
        if key == "c:NQG":
            return op == "?=" and value == "this" and tag == "NQG"
        if key == "is_owned_by":
            return self.state_scope is not None and self.state_scope.get("owned") is True and value == "ROOT"
        if key == "owner":
            return self.state_scope is not None and self.state_scope.get("owned") is True and value.lower() == "root"
        if key == "government_legitimacy":
            return self.compare(self.countries[tag].get(key, 0), op, float(value))
        return super().condition(node, tag)

    def start(self, journal_id):
        assert journal_id not in self.history["NQG"], journal_id
        journal = self.journal_defs[journal_id]
        if not self.conditions(field(journal, "is_shown_when_inactive"), "NQG") or not self.conditions(
                field(journal, "possible"), "NQG"):
            raise AssertionError(("actual_first_je_not_admissible", journal_id, self.countries["NQG"]))
        self.active["NQG"].append(journal_id)
        self.history["NQG"][journal_id] = "active"
        self.trace.append({"op": "admitted", "journal": journal_id, "day": 0})
        self.execute(field(journal, "immediate"), "NQG")

    def deliver_native_popup(self, day):
        if not self.events:
            return False
        tag, event_id = self.events.pop(0)
        if tag != "NQG":
            raise AssertionError(("wrong_recipient", tag, event_id))
        event = self.event_defs[event_id]
        if not self.conditions(field(event, "trigger"), "NQG"):
            self.trace.append({"op": "rejected_event_trigger", "event": event_id, "day": day,
                               "state": dict(self.countries["NQG"])})
            return False
        self.execute(field(event, "immediate"), "NQG")
        self.trace.append({"op": "native_event", "event": event_id, "day": day,
                           "state": dict(self.countries["NQG"])})
        options = [body for key, _, body in event if key == "option"]
        legal = [option for option in options
                 if field(option, "name").endswith(".defer")
                 and self.conditions(field(option, "trigger"), "NQG")]
        if not legal:
            legal = [option for option in options
                     if field(option, "name").endswith((".acknowledge_12_month_notice",
                                                         ".acknowledge_36_month_notice"))
                     and self.conditions(field(option, "trigger"), "NQG")]
        if len(legal) != 1:
            raise AssertionError(("no_unique_native_defer_or_notice_ack", event_id, options))
        choice = [node for node in legal[0] if node[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
        self.execute(choice, "NQG")
        self.trace.append({"op": "legal_option", "option": field(legal[0], "name"),
                           "event": event_id, "day": day,
                           "state": dict(self.countries["NQG"])})
        return True


def _arc(world, slug):
    return next(row for row in world.cat["arcs"] if row["slug"] == slug)


def _candidates(world):
    result = {}
    candidate_id = 0
    for arc in world.cat["arcs"]:
        adapter = arc.get("inline_delivery_adapter")
        if not adapter:
            continue
        phase_by_je = {phase["journal"]: phase for phase in adapter["live_phases"]}
        for branch in adapter["branches"]:
            for candidate in branch["candidates"]:
                candidate_id += 1
                result[candidate_id] = {"id": candidate_id, "arc": arc, "branch": branch,
                                        "candidate": candidate,
                                        "phase": phase_by_je[branch["journal"]]}
    return result


def _candidate_for_event(world, event_id):
    rows = _candidates(world)
    reservation = world.countries["NQG"].get("ywc_v03_nqg_inline_reservation")
    if reservation is None or int(reservation) not in rows:
        raise AssertionError(("missing_actual_reservation", event_id, reservation,
                              world.countries["NQG"], world.trace[-10:]))
    row = rows[int(reservation)]
    if row["branch"]["event"] != event_id:
        raise AssertionError(("reservation_event_mismatch", event_id, reservation, row))
    return row


def _queue_snapshot(state, names):
    return {name: (name in state, state.get(name)) for name in names}


def _deliver_reserved(world, event_id, choice_suffix=None, before_immediate=None):
    """Execute a true source popup and observe ACK at its real helper invocation."""
    if not world.events:
        raise AssertionError(("no_native_popup", event_id, world.trace[-12:]))
    tag, actual_id = world.events.pop(0)
    if (tag, actual_id) != ("NQG", event_id):
        raise AssertionError(("unexpected_native_dispatch", tag, actual_id, event_id))
    event = world.event_defs[event_id]
    if not world.conditions(field(event, "trigger"), "NQG"):
        raise AssertionError(("native_event_trigger_rejected", event_id, world.countries["NQG"]))
    row = _candidate_for_event(world, event_id)
    if before_immediate:
        choice_suffix = before_immediate(world, row)
    cid = row["id"]
    candidate = row["candidate"]
    state = world.countries["NQG"]
    queue = candidate["queue"]
    snapshot_base = f"ywc_v03_nqg_inline_c{cid}_{queue.removeprefix('ywc_nqg_')}"
    present_key, value_key = snapshot_base + "_present", snapshot_base + "_value"
    if state.get(present_key) != 1 or value_key not in state:
        raise AssertionError(("reservation_did_not_capture_selected_queue", cid, queue,
                              present_key, value_key, state))
    if candidate["mode"] == "exact" and state[value_key] != candidate["value"]:
        raise AssertionError(("reservation_selected_wrong_exact_queue_value", cid,
                              candidate["value"], state[value_key]))
    epoch = state.get("ywc_v03_nqg_inline_reservation_epoch")
    if epoch is None or state.get(f"ywc_v03_nqg_inline_candidate_epoch_{cid}") != epoch:
        raise AssertionError(("candidate_epoch_not_bound", cid, epoch, state))
    siblings = {item["candidate"]["queue"] for item in _candidates(world).values()
                if item["arc"]["slug"] == row["arc"]["slug"] and item["candidate"]["queue"] != queue}
    before = _queue_snapshot(state, siblings)
    cursor = len(world.ack_boundaries)
    world.execute(field(event, "immediate"), "NQG")
    hook = f"ywc_v03_nqg_inline_ack_{cid}"
    boundary = next((snapshot for name, snapshot in world.ack_boundaries[cursor:] if name == hook), None)
    if boundary is None:
        raise AssertionError(("actual_callback_did_not_reach_ack", cid, world.ack_boundaries[cursor:]))
    expected_proof = ((f"ywc_v03_nqg_inline_callback_{cid}", 1),
                      (f"ywc_v03_nqg_inline_callback_candidate_{cid}", cid),
                      (f"ywc_v03_nqg_inline_callback_epoch_{cid}", epoch))
    for name, value in expected_proof:
        if boundary.get(name) != value:
            raise AssertionError(("callback_proof_mismatch_at_ack", cid, name, value, boundary))
    kind = candidate["kind"]
    if kind in ("notice12", "notice36"):
        prefix = {"v03_nqg_winter_court": "winter", "v03_nqg_hunting_rights": "hunting",
                  "v03_nqg_northern_port": "port"}[row["arc"]["slug"]]
        notice = "12" if kind == "notice12" else "36"
        if boundary.get(f"ywc_nqg_{prefix}_blocked_{notice}_delivered") != 1:
            raise AssertionError(("native_notice_receipt_missing_at_ack", cid, boundary))
        if boundary.get(f"ywc_nqg_{prefix}_notice{notice}_open") != 1:
            raise AssertionError(("native_notice_open_missing_at_ack", cid, boundary))
        if f"ywc_nqg_{prefix}_notice{notice}_intent" in boundary:
            raise AssertionError(("native_notice_intent_not_consumed", cid, boundary))
    if queue in state or _queue_snapshot(state, siblings) != before:
        raise AssertionError(("ack_queue_mutation_mismatch", cid, queue, before, state))
    options = [body for key, _, body in event if key == "option"]
    if choice_suffix:
        suffixes = ((choice_suffix,) if isinstance(choice_suffix, str)
                    else tuple(choice_suffix))
        chosen = next((option for suffix in suffixes for option in options
                       if field(option, "name").endswith("." + suffix)
                       and world.conditions(field(option, "trigger"), "NQG")), None)
        if chosen is None:
            raise AssertionError(("requested_native_option_not_legal", event_id, choice_suffix, state))
    else:
        if kind == "notice12":
            chosen = next((option for option in options
                           if field(option, "name").endswith(".acknowledge_12_month_notice")
                           and world.conditions(field(option, "trigger"), "NQG")), None)
        elif kind == "notice36":
            chosen = next((option for option in options
                           if field(option, "name").endswith(".start_36_month_limited_remedy")
                           and world.conditions(field(option, "trigger"), "NQG")), None)
            if chosen is None:
                chosen = next((option for option in options
                               if field(option, "name").endswith(".withdraw_after_36_month_notice")
                               and world.conditions(field(option, "trigger"), "NQG")), None)
        elif kind == "remedy_final":
            chosen = next((option for option in options
                           if field(option, "name").endswith((".settle_full", ".settle_compromise"))
                           and world.conditions(field(option, "trigger"), "NQG")), None)
        else:
            chosen = next((option for option in options if field(option, "name").endswith(".defer")
                           and world.conditions(field(option, "trigger"), "NQG")), None)
    if chosen is None:
        raise AssertionError(("no_legal_native_option", event_id, options, state))
    choice = [node for node in chosen if node[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
    world.execute(choice, "NQG")
    world.trace.append({"op": "native_choice", "event": event_id,
                        "option": field(chosen, "name"), "day": world.elapsed_months * 30})
    return row, boundary

def _run_order(order):
    world = NqgActualWorld()
    # Real shared startup helper establishes actual v0.3 capacity/counters.
    world.run("ywc_v03_initialize_country", "NQG")
    if world.countries["NQG"].get("ywc_v03_active_arc_count") != 0:
        raise AssertionError(("startup_counter_not_zero", world.countries["NQG"]))
    for position, index in enumerate(order, 1):
        arc_slug, journal_id, pending, first_event = ARCS[index]
        world.start(journal_id)
        state = world.countries["NQG"]
        if state.get("ywc_v03_active_arc_count") != position:
            raise AssertionError(("native_claim_counter", arc_slug, state))
        if state.get("ywc_v03_visible_task_count") != position:
            raise AssertionError(("native_visible_counter", arc_slug, state))
        world.trace.append({"op": "arc_started", "arc": arc_slug, "pending": pending,
                           "first_event": first_event, "day": 0})

    counts = {slug: 0 for slug, *_ in ARCS}
    deliveries = {slug: [] for slug, *_ in ARCS}
    # Run 45 consecutive real 30-day pulse intervals. Date-based cooldowns
    # expire in the same calendar as each source monthly JE pulse.
    for month in range(45):
        world.advance_days(30)
        world.elapsed_months += 1
        day = (month + 1) * 30
        for index in order:
            arc_slug, journal_id, pending, first_event = ARCS[index]
            if journal_id not in world.active["NQG"]:
                continue
            journal = world.journal_defs[journal_id]
            pulse = field(field(journal, "on_monthly_pulse"), "effect")
            before = len(world.events)
            world.execute(pulse, "NQG")
            if len(world.events) > before:
                if len(world.events) != before + 1:
                    raise AssertionError(("multiple_native_events_from_one_pulse", journal_id,
                                          world.events[before:], day))
                event_id = world.events[before][1]
                event = world.event_defs[event_id]
                if world.conditions(field(event, "trigger"), "NQG"):
                    _deliver_reserved(world, event_id)
                    counts[arc_slug] += 1
                    deliveries[arc_slug].append(day)
                else:
                    # A refused native popup remains observable in trace but is
                    # never executed or counted as a delivery.
                    world.deliver_native_popup(day)
        # Observe, but do not synthesize lifecycle terminal transitions.
        for arc_slug, journal_id, _, _ in ARCS:
            if journal_id not in world.active["NQG"]:
                continue
            journal = world.journal_defs[journal_id]
            if (world.conditions(field(journal, "complete"), "NQG")
                    or world.conditions(field(journal, "fail"), "NQG")):
                raise AssertionError(("native_first_je_reached_terminal", arc_slug, journal_id, day,
                                     dict(world.countries["NQG"])))
    world.trace.append({"op": "summary", "order": list(order), "counts": counts,
                       "delivery_days": deliveries, "final": dict(world.countries["NQG"])})
    return world, counts, deliveries


def _advance_actual_month(world, journal_ids, before_event=None):
    world.advance_days(30)
    world.elapsed_months += 1
    day = world.elapsed_months * 30
    delivered = []
    for journal_id in journal_ids:
        if journal_id not in world.active["NQG"]:
            continue
        journal = world.journal_defs[journal_id]
        if (world.conditions(field(journal, "complete"), "NQG")
                or world.conditions(field(journal, "fail"), "NQG")):
            raise AssertionError(("unexpected_terminal_je_during_natural_delivery", journal_id,
                                  day, world.countries["NQG"], world.trace[-20:]))
        pulse = field(field(journal, "on_monthly_pulse"), "effect")
        cursor = len(world.events)
        world.execute(pulse, "NQG")
        if len(world.events) == cursor:
            continue
        if len(world.events) != cursor + 1:
            raise AssertionError(("multiple_events_from_one_natural_pulse", journal_id,
                                  world.events[cursor:], day))
        event_id = world.events[cursor][1]
        event = world.event_defs[event_id]
        if not world.conditions(field(event, "trigger"), "NQG"):
            # Keep the refusal visible and never execute the rejected popup.
            world.trace.append({"op": "native_trigger_refused", "event": event_id,
                                "day": day, "state": dict(world.countries["NQG"])})
            world.events.pop(cursor)
            continue
        row, boundary = _deliver_reserved(world, event_id,
                                          before_immediate=(lambda current, row:
                                                            before_event(current, event_id)
                                                            if before_event else None))
        delivered.append((row, boundary, day))
    # Let the actual country arc refresh lifecycle after native choices; this
    # performs only authored complete/fail transitions and possible checks.
    for arc in world.cat["arcs"]:
        if any(jid in {row["id"] for row in arc["journals"]} for jid in journal_ids):
            world.refresh(arc)
    return delivered


def _reserve_first_source_popup(extra=None):
    world = NqgActualWorld()
    world.run("ywc_v03_initialize_country", "NQG")
    journal_id = ARCS[0][1]
    world.start(journal_id)
    if extra:
        world.countries["NQG"].update(extra)
    world.advance_days(30)
    world.elapsed_months += 1
    pulse = field(field(world.journal_defs[journal_id], "on_monthly_pulse"), "effect")
    world.execute(pulse, "NQG")
    if len(world.events) != 1:
        raise AssertionError(("controlled_native_pulse_did_not_queue_one_popup", world.events,
                              world.countries["NQG"], world.trace[-20:]))
    event_id = world.events[0][1]
    if not world.conditions(field(world.event_defs[event_id], "trigger"), "NQG"):
        raise AssertionError(("controlled_popup_not_initially_legal", event_id,
                              world.countries["NQG"], world.trace[-20:]))
    return world, journal_id, event_id, _candidate_for_event(world, event_id)


def _retry_source_popup_after_fault(world, journal_id, old_epoch):
    # Never execute the refused popup. Expire its one-day reservation, then let
    # the real source JE pulse create a fresh reservation and popup.
    world.events.clear()
    world.advance_days(2)
    world.advance_days(30)
    world.elapsed_months += 1
    pulse = field(field(world.journal_defs[journal_id], "on_monthly_pulse"), "effect")
    world.execute(pulse, "NQG")
    if len(world.events) != 1:
        raise AssertionError(("native_pulse_did_not_re_reserve_after_fault", world.events,
                              world.countries["NQG"], world.trace[-20:]))
    event_id = world.events[0][1]
    if not world.conditions(field(world.event_defs[event_id], "trigger"), "NQG"):
        raise AssertionError(("recovered_native_popup_still_illegal", event_id,
                              world.countries["NQG"], world.trace[-20:]))
    candidate = _candidate_for_event(world, event_id)
    epoch = world.countries["NQG"]["ywc_v03_nqg_inline_reservation_epoch"]
    if epoch <= old_epoch:
        raise AssertionError(("retry_did_not_mint_new_epoch", old_epoch, epoch,
                              world.countries["NQG"]))
    _deliver_reserved(world, event_id)
    return candidate, epoch


class NqgActualFairDeliveryBaseline(unittest.TestCase):
    def test_catalog_distinguishes_candidate_senders_from_phase_class_records(self):
        world = NqgActualWorld()
        candidates = list(_candidates(world).values())
        self.assertEqual(len(candidates), 73)
        kinds = [candidate["candidate"]["kind"] for candidate in candidates]
        self.assertEqual(kinds.count("normal_queued_event"), 52)
        self.assertEqual(kinds.count("remedy_final"), 6)
        self.assertEqual(kinds.count("notice12"), 6)
        self.assertEqual(kinds.count("notice36"), 6)
        self.assertEqual(kinds.count("notice"), 3)
        first_phase = {arc_slug: journal_id for arc_slug, journal_id, _, _ in ARCS}
        first_classes = [row for row in candidates
                         if row["branch"]["journal"] in first_phase.values()
                         and row["candidate"]["kind"] in {"remedy_final", "notice12", "notice36"}]
        self.assertEqual(len(first_classes), 9)
        self.assertEqual({row["candidate"]["kind"] for row in first_classes},
                         {"remedy_final", "notice12", "notice36"})

    def test_three_real_native_arcs_share_fifteen_ninety_day_opportunities(self):
        orders = ((0, 1, 2), (2, 1, 0), (1, 2, 0), (0, 2, 1), (2, 0, 1), (1, 0, 2))
        rows = []
        failures = []
        for order in orders:
            world, counts, deliveries = _run_order(order)
            rows.append({"order": list(order), "counts": counts, "delivery_days": deliveries})
            self.assertEqual(sum(counts.values()), 15, world.trace)
            all_days = sorted(day for arc_days in deliveries.values() for day in arc_days)
            self.assertEqual(all_days[0], 30, world.trace)
            self.assertEqual(all_days[-1], 1290, world.trace)
            self.assertTrue(all(right - left == 90 for left, right in zip(all_days, all_days[1:])),
                            world.trace)
            if sorted(counts.values()) != [5, 5, 5]:
                failures.append({"order": list(order), "counts": counts})
            self.assertEqual(world.countries["NQG"].get("ywc_v03_active_arc_count"), 3, world.trace)
            self.assertEqual(world.countries["NQG"].get("ywc_v03_visible_task_count"), 3, world.trace)
        self.assertFalse(failures, failures)

    def test_natural_12_and_36_month_notices_preserve_ordinary_pending(self):
        world = NqgActualWorld()
        world.run("ywc_v03_initialize_country", "NQG")
        journal_id = ARCS[0][1]
        world.start(journal_id)
        world.advance_days(30)
        world.elapsed_months += 1
        first = field(field(world.journal_defs[journal_id], "on_monthly_pulse"), "effect")
        world.execute(first, "NQG")
        self.assertEqual(world.events, [("NQG", "ywc_nqg.1000")], world.trace)
        first_row, _ = _deliver_reserved(world, "ywc_nqg.1000", "cap_stipend")
        self.assertEqual(first_row["candidate"]["kind"], "normal_queued_event")
        state = world.countries["NQG"]
        self.assertEqual(state.get("ywc_nqg_winter_route"), 1, state)
        self.assertEqual(state.get("ywc_nqg_winter_fee_paid"), 1, state)
        self.assertLess(world.treasury["NQG"], 0, world.treasury)
        # The interpreter does not simulate political economics. Move only an
        # engine-owned country fact to represent the later loss of legitimacy;
        # all stage, defer, timer and notice facts arise from actual source.
        state["government_legitimacy"] = 10
        world.trace.append({"op": "engine_fact_transition", "fact": "government_legitimacy",
                            "old": 80, "new": 10, "day": world.elapsed_months * 30})
        seen = {"notice12": [], "notice36": [], "remedy_final": []}

        def recover_narrow_ready_for_limited_remedy(current, event_id):
            candidate = _candidate_for_event(current, event_id)["candidate"]
            if candidate["kind"] == "notice36":
                old = current.countries["NQG"].get("government_legitimacy")
                current.countries["NQG"]["government_legitimacy"] = 80
                current.trace.append({"op": "engine_fact_transition",
                                      "fact": "government_legitimacy", "old": old,
                                      "new": 80, "day": current.elapsed_months * 30,
                                      "reason": "limited_remedy_choice"})
                return "start_36_month_limited_remedy"
            return None

        for _ in range(55):
            for row, boundary, day in _advance_actual_month(
                    world, [journal_id], recover_narrow_ready_for_limited_remedy):
                kind = row["candidate"]["kind"]
                if kind in seen:
                    seen[kind].append((row, boundary, day))
        self.assertTrue(seen["notice12"], (seen, world.countries["NQG"], world.trace[-40:]))
        self.assertTrue(seen["notice36"], (seen, world.countries["NQG"], world.trace[-40:]))
        for kind in ("notice12", "notice36"):
            row, boundary, day = seen[kind][0]
            self.assertEqual(row["branch"]["event"], "ywc_nqg.1009")
            self.assertEqual(boundary.get("ywc_nqg_winter_pending"), 1001,
                             (kind, day, boundary, world.trace[-30:]))
            self.assertEqual(boundary.get(row["candidate"]["queue"]), 1,
                             (kind, day, row["candidate"], boundary))
            self.assertEqual(boundary.get("ywc_nqg_winter_notice12_open" if kind == "notice12"
                                          else "ywc_nqg_winter_notice36_open"), 1, boundary)
        self.assertTrue(seen["remedy_final"], {
            "seen_kinds": {kind: len(rows) for kind, rows in seen.items()},
            "day": world.elapsed_months * 30,
            "stage": world.countries["NQG"].get("ywc_nqg_winter_stage"),
            "observation_timer": world.countries["NQG"].get("ywc_nqg_winter_observation_timer"),
            "six_months_complete": world.countries["NQG"].get("ywc_nqg_winter_six_months_complete"),
            "trace_tail": world.trace[-25:],
        })
        self.assertEqual(seen["remedy_final"][0][0]["candidate"]["kind"], "remedy_final")
        self.assertNotIn("ywc_nqg_winter_notice12_intent", world.countries["NQG"])
        self.assertNotIn("ywc_nqg_winter_notice36_intent", world.countries["NQG"])

    def test_natural_paid_options_activate_later_review_je_from_source(self):
        world = NqgActualWorld()
        world.run("ywc_v03_initialize_country", "NQG")
        first_je = ARCS[0][1]
        world.start(first_je)
        arc = _arc(world, ARCS[0][0])
        options_by_event = {
            "ywc_nqg.1000": ("cap_stipend",),
            "ywc_nqg.1001": ("cap_household",),
            "ywc_nqg.1002": ("audit_districts", "pay_by_register"),
            "ywc_nqg.1003": ("cap_soldiers", "keep_full_guard"),
        }

        def choose_authored_paid_option(current, event_id):
            return options_by_event.get(event_id)

        for _ in range(20):
            active = list(world.active["NQG"])
            self.assertTrue(active, (world.history["NQG"], world.countries["NQG"]))
            _advance_actual_month(world, active, choose_authored_paid_option)
            if world.countries["NQG"].get("ywc_nqg_winter_stage", 0) >= 1004:
                break

        review_je = "ywc_je_v03_nqg_winter_review"
        self.assertEqual(world.history["NQG"].get(first_je), "complete", world.history["NQG"])
        self.assertIn(review_je, world.active["NQG"], world.history["NQG"])
        self.assertTrue(world.conditions(field(world.journal_defs[review_je], "possible"), "NQG"),
                        world.countries["NQG"])
        self.assertEqual(world.countries["NQG"].get("ywc_nqg_winter_fee_paid"), 1)
        self.assertEqual(world.countries["NQG"].get("ywc_nqg_winter_stage"), 1004)
        self.assertIn("ywc_v03_nqg_inline_live_winter_court_2", world.countries["NQG"])
        self.assertTrue(any(item["op"] == "native_choice" and item["event"] == "ywc_nqg.1003"
                            for item in world.trace), world.trace)

    def test_unit_presence_mode_queue_value_zero_is_a_valid_selected_queue(self):
        world, _, event_id, row = _reserve_first_source_popup({"ywc_nqg_winter_notice12_pending": 0})
        self.assertEqual(row["candidate"]["kind"], "notice12")
        self.assertEqual(row["candidate"]["mode"], "presence")
        self.assertEqual(world.countries["NQG"]["ywc_nqg_winter_notice12_pending"], 0)
        _, boundary = _deliver_reserved(world, event_id)
        self.assertEqual(boundary.get("ywc_nqg_winter_notice12_pending"), 0)
        self.assertNotIn("ywc_nqg_winter_notice12_pending", world.countries["NQG"])

    def test_unit_notice12_preserves_native_36_intent(self):
        world, _, event_id, row = _reserve_first_source_popup({
            "ywc_nqg_winter_notice12_pending": 1,
            "ywc_nqg_winter_notice36_intent": 1,
        })
        self.assertEqual(row["candidate"]["kind"], "notice12")
        _, boundary = _deliver_reserved(world, event_id)
        self.assertEqual(boundary.get("ywc_nqg_winter_notice36_intent"), 1, boundary)
        self.assertEqual(world.countries["NQG"].get("ywc_nqg_winter_notice36_intent"), 1,
                         world.countries["NQG"])

    def test_unit_notice36_with_12_intent_is_blocked_by_native_source(self):
        blocked = NqgActualWorld()
        blocked.run("ywc_v03_initialize_country", "NQG")
        blocked.start(ARCS[0][1])
        blocked.countries["NQG"].update({
            "ywc_nqg_winter_notice36_pending": 1,
            "ywc_nqg_winter_notice12_intent": 1,
        })
        blocked.advance_days(30)
        blocked.elapsed_months += 1
        pulse = field(field(blocked.journal_defs[ARCS[0][1]], "on_monthly_pulse"), "effect")
        blocked.execute(pulse, "NQG")
        self.assertFalse(blocked.events, ("notice36_with_12_intent", blocked.events,
                                           blocked.countries["NQG"], blocked.trace[-12:]))
        self.assertNotIn("ywc_v03_nqg_inline_reservation", blocked.countries["NQG"])

    def test_unit_normal_event_preserves_unconsumed_notice_intents(self):
        cases = (("notice12", "ywc_nqg_winter_notice12_intent"),
                 ("notice36", "ywc_nqg_winter_notice36_intent"))
        for label, intent in cases:
            with self.subTest(intent=label):
                world, _, event_id, row = _reserve_first_source_popup({intent: 1})
                self.assertEqual(row["candidate"]["kind"], "normal_queued_event")
                self.assertEqual(event_id, "ywc_nqg.1000")
                self.assertTrue(world.conditions(field(world.event_defs[event_id], "trigger"), "NQG"))
                # 1000 invokes mark_major_delivered only; notice intents are
                # preserved by its actual immediate and do not block this ACK.
                _, boundary = _deliver_reserved(world, event_id)
                self.assertEqual(boundary.get(intent), 1, boundary)
                self.assertEqual(world.countries["NQG"].get(intent), 1,
                                 world.countries["NQG"])

    def test_unit_notice_intent_exact_state_restore_mints_new_native_epoch(self):
        for initial in (0, 1):
            with self.subTest(initial_intent=initial):
                world, journal_id, event_id, row = _reserve_first_source_popup({
                    "ywc_nqg_winter_notice12_pending": 0,
                    "ywc_nqg_winter_notice12_intent": initial,
                })
                self.assertEqual(row["candidate"]["kind"], "notice12")
                state = world.countries["NQG"]
                old_epoch = state["ywc_v03_nqg_inline_reservation_epoch"]
                # A hostile same-class intent value must invalidate the old popup.
                state["ywc_nqg_winter_notice12_intent"] = 2
                before = dict(state)
                self.assertFalse(world.conditions(field(world.event_defs[event_id], "trigger"), "NQG"),
                                 (initial, state))
                self.assertEqual(state, before)
                # Restore the exact original presence/value, let the reservation
                # expire, and require a new native pulse and epoch.
                state["ywc_nqg_winter_notice12_intent"] = initial
                if initial == 0:
                    state["ywc_nqg_winter_notice12_intent"] = 0
                candidate, epoch = _retry_source_popup_after_fault(world, journal_id, old_epoch)
                self.assertEqual(candidate["candidate"]["kind"], "notice12")
                self.assertGreater(epoch, old_epoch)

    def test_unit_sibling_missing_zero_changes_refuse_old_notice12_snapshot_and_retry(self):
        cases = (
            ("absent_to_present_zero", {"ywc_nqg_winter_notice12_pending": 1},
             "ywc_nqg_winter_notice36_pending", 0, None),
            ("present_zero_to_absent", {"ywc_nqg_winter_notice12_pending": 1,
                                         "ywc_nqg_winter_notice36_pending": 0},
             "ywc_nqg_winter_notice36_pending", None, 0),
        )
        for label, initial, mutation_key, changed, original in cases:
            with self.subTest(label=label):
                world, journal_id, event_id, row = _reserve_first_source_popup(initial)
                self.assertEqual(row["candidate"]["kind"], "notice12")
                state = world.countries["NQG"]
                old_epoch = state["ywc_v03_nqg_inline_reservation_epoch"]
                if changed is None:
                    state.pop(mutation_key)
                else:
                    state[mutation_key] = changed
                mutated = dict(state)
                self.assertFalse(world.conditions(field(world.event_defs[event_id], "trigger"), "NQG"),
                                 (label, state, world.trace[-10:]))
                self.assertEqual(state, mutated, (label, "guard_observation_mutated_world"))
                if original is None:
                    state.pop(mutation_key, None)
                else:
                    state[mutation_key] = original
                candidate, new_epoch = _retry_source_popup_after_fault(world, journal_id, old_epoch)
                self.assertEqual(candidate["candidate"]["kind"], "notice12", label)
                self.assertGreater(new_epoch, old_epoch, label)

    def test_unit_stale_normal_reservations_refuse_without_mutation_then_native_retry(self):
        faults = (
            ("expired_timer", lambda w, s: w.advance_days(2), lambda w, s, old: None),
            ("selected_queue_changed", lambda w, s: s.__setitem__("ywc_nqg_winter_pending", 1001),
             lambda w, s, old: s.__setitem__("ywc_nqg_winter_pending", old)),
            ("selected_queue_absent", lambda w, s: s.pop("ywc_nqg_winter_pending"),
             lambda w, s, old: s.__setitem__("ywc_nqg_winter_pending", old)),
            ("wrong_notice_intent", lambda w, s: s.__setitem__("ywc_nqg_winter_notice12_intent", 1),
             lambda w, s, old: s.pop("ywc_nqg_winter_notice12_intent", None)),
            ("historical_notice_receipt", lambda w, s: s.__setitem__("ywc_nqg_winter_blocked_12_delivered", 1),
             lambda w, s, old: s.pop("ywc_nqg_winter_blocked_12_delivered", None)),
            ("wrong_reservation_epoch", lambda w, s: s.__setitem__("ywc_v03_nqg_inline_reservation_epoch", old_epoch_plus_one(s)),
             lambda w, s, old: s.__setitem__("ywc_v03_nqg_inline_reservation_epoch", old)),
            ("completed_phase", lambda w, s: w.active["NQG"].remove(ARCS[0][1]),
             lambda w, s, old: w.active["NQG"].append(ARCS[0][1])),
            ("already_served", lambda w, s: s.__setitem__("ywc_v03_nqg_inline_served_1", s["ywc_v03_nqg_inline_round"]),
             lambda w, s, old: s.pop("ywc_v03_nqg_inline_served_1", None)),
            ("sibling_absent_to_zero", lambda w, s: s.__setitem__("ywc_nqg_winter_notice12_pending", 0),
             lambda w, s, old: s.pop("ywc_nqg_winter_notice12_pending", None)),
        )
        for label, mutate, restore in faults:
            with self.subTest(fault=label):
                world, journal_id, event_id, row = _reserve_first_source_popup()
                self.assertEqual(row["candidate"]["kind"], "normal_queued_event")
                state = world.countries["NQG"]
                original_epoch = state["ywc_v03_nqg_inline_reservation_epoch"]
                original_queue = state["ywc_nqg_winter_pending"]
                mutate(world, state)
                mutated_state = dict(state)
                self.assertFalse(world.conditions(field(world.event_defs[event_id], "trigger"), "NQG"),
                                 (label, state, world.trace[-12:]))
                self.assertEqual(state, mutated_state, (label, "trigger_observation_mutated_world"))
                restore(world, state, original_epoch if label == "wrong_reservation_epoch" else original_queue)
                _retry_source_popup_after_fault(world, journal_id, original_epoch)


def old_epoch_plus_one(state):
    return state["ywc_v03_nqg_inline_reservation_epoch"] + 1


if __name__ == "__main__":
    unittest.main()
