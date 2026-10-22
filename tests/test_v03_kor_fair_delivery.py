"""KOR fair delivery contract exercised against actual generated scripts.

The world is a migrated legacy Chapter 1 save. Only its public legacy outcome
marker and Clausewitz-owned state facts are fixtures; startup, JE admission,
monthly pulses, event triggers/immediates and defer options use current source.
"""
import unittest
from pathlib import Path

from tests.shu_kor_strict_review_runtime import Strict, field
from tests.clausewitz_harness import parse


SCHOOL = "v03_kor_school_factions"
PORTS = "v03_kor_controlled_ports"
LEGACY_MARKER = "ywc_campaign_kor_c1_outcome"


class KorFairWorld(Strict):
    """Strict actual-source world plus the targeted generated KOR adapter."""
    def __init__(self):
        super().__init__("kor")
        root = Path(__file__).resolve().parents[1]
        effect_file = root / "yongchang_world/common/scripted_effects/ywc_v03_delivery_kor_effects.txt"
        trigger_file = root / "yongchang_world/common/scripted_triggers/ywc_v03_delivery_kor_triggers.txt"
        if not effect_file.is_file() or not trigger_file.is_file():
            raise AssertionError("targeted KOR generated adapter outputs are missing; run the country_kor builder")
        for source_path, destination in ((effect_file, self.effects), (trigger_file, self.trigger_defs)):
            definitions = {key: body for key, _, body in parse(source_path.read_text(encoding="utf-8-sig"))}
            collisions = set(definitions).intersection(destination)
            if collisions:
                raise AssertionError(("generated_helper_name_collision", str(source_path), sorted(collisions)))
            destination.update(definitions)
        self.ack_boundaries = []

    def run(self, name, tag="KOR"):
        # Observe the real generated ACK helper at invocation time, after its
        # callback setters ran and before ACK clears the transient proof.
        if name.startswith("ywc_v03_kor_inline_ack_"):
            self.ack_boundaries.append((name, dict(self.countries[tag])))
        return super().run(name, tag)

    def condition(self, node, tag):
        key, comparison, value = node
        if key == "c:KOR":
            return comparison == "?=" and value == "this" and tag == "KOR"
        return super().condition(node, tag)


def _facts():
    buildings = [
        {"type": kind, "occupancy": 1, "shortage": False, "groups": []}
        for kind in ("building_government_administration", "building_university", "building_port", "building_barrack")
    ]
    return {
        "yearly_gross_income": 52000,
        "gold_reserves": 100000,
        "bureaucracy": 100,
        "net_fixed_income": 100,
        "scaled_debt": 0,
        "army_size": 10,
        "legitimacy": 80,
        "authority": 150,
        "is_at_war": False,
        "in_default": False,
        "is_subject": False,
        "country_has_voting_franchise": False,
        "laws": ["law_per_capita_based_taxation", "law_protectionism", "law_professional_army",
                 "law_tenant_farmers", "law_multicultural", "law_public_schools"],
        "institutions": {"institution_schools": 2},
        "igs": [{"type": name, "approval": 0} for name in
                ("ig_landowners", "ig_devout", "ig_intelligentsia", "ig_armed_forces")],
        "states": [{"owned": True, "region": "s:STATE_KOREA", "buildings": buildings, "pops": []}],
    }


def _arc(world, slug):
    return next(row for row in world.cat["arcs"] if row["slug"] == slug)


def _candidates(world):
    rows = {}
    candidate_id = 0
    for arc in world.cat["arcs"]:
        if arc.get("era") != "foundation":
            continue
        adapter = arc["inline_delivery_adapter"]
        phase_by_je = {phase["journal"]: phase for phase in adapter["live_phases"]}
        for branch in adapter["branches"]:
            for queue in branch["candidates"]:
                candidate_id += 1
                rows[candidate_id] = {
                    "id": candidate_id,
                    "arc": arc,
                    "branch": branch,
                    "queue": queue,
                    "phase": phase_by_je[branch["journal"]],
                }
    return rows


def _callback_fields(world, candidate_id):
    candidate = _candidates(world)[candidate_id]
    event = world.event_defs[candidate["branch"]["event"]]
    expected = {
        f"ywc_v03_kor_inline_callback_{candidate_id}",
        f"ywc_v03_kor_inline_callback_candidate_{candidate_id}",
        f"ywc_v03_kor_inline_callback_epoch_{candidate_id}",
        f"ywc_v03_kor_inline_callback_queue_{candidate_id}",
    }
    found = set()

    def walk(node):
        if isinstance(node, (list, tuple)):
            if isinstance(node, tuple) and len(node) == 3 and node[0] == "set_variable":
                fields = {key: value for key, _, value in node[2]}
                if fields.get("name") in expected:
                    found.add(fields["name"])
            for child in node:
                walk(child)

    walk(field(event, "immediate"))
    return found


def _queue_state(state, names):
    return {name: (name in state, state.get(name)) for name in names}


def _arc_number(world, slug):
    return next(index for index, arc in enumerate(
        [arc for arc in world.cat["arcs"] if arc.get("era") == "foundation"], 1)
        if arc["slug"] == slug)


def _receive_and_defer(world, event_id):
    tag, actual_id = world.events.pop(0)
    if actual_id != event_id or tag != "KOR":
        raise AssertionError(("unexpected_dispatch", tag, actual_id, event_id))
    event = world.event_defs[actual_id]
    candidate_id = int(world.countries["KOR"]["ywc_v03_kor_inline_reservation"])
    candidate = _candidates(world)[candidate_id]
    self_value = int(actual_id.rsplit(".", 1)[1])
    queue = candidate["queue"]["queue"]
    if candidate["branch"]["event"] != actual_id:
        raise AssertionError(("reservation_event_mismatch", candidate_id, candidate["branch"]["event"], actual_id))
    if candidate["phase"]["journal"] not in world.active["KOR"]:
        raise AssertionError(("reservation_phase_not_active", candidate_id, candidate["phase"]["journal"]))
    state = world.countries["KOR"]
    if queue not in state or state[queue] != candidate["queue"].get("value", self_value):
        raise AssertionError(("selected_source_queue_missing_or_changed_before_popup", candidate_id, queue, state.get(queue)))
    epoch = state["ywc_v03_kor_inline_reservation_epoch"]
    if state.get(f"ywc_v03_kor_inline_candidate_epoch_{candidate_id}") != epoch:
        raise AssertionError(("reservation_epoch_not_bound_to_candidate", candidate_id, epoch, state.get(f"ywc_v03_kor_inline_candidate_epoch_{candidate_id}")))
    proof_fields = _callback_fields(world, candidate_id)
    if len(proof_fields) != 4:
        raise AssertionError(("unexpected_callback_proof_shape", candidate_id, proof_fields))
    if any(name in state for name in proof_fields):
        raise AssertionError(("reservation_has_completion_proof", candidate_id, {k: state[k] for k in proof_fields if k in state}))
    if not world.conditions(field(event, "trigger"), "KOR"):
        raise AssertionError(("event_trigger_rejected", actual_id, candidate_id, state))
    adapter_queues = {
        row["queue"]["queue"]
        for row in _candidates(world).values()
        if row["arc"]["slug"] == candidate["arc"]["slug"]
    }
    sibling_queues_before = _queue_state(state, adapter_queues - {queue})
    boundary_cursor = len(world.ack_boundaries)
    world.execute(field(event, "immediate"), "KOR")
    boundary = next(
        (snapshot for hook, snapshot in world.ack_boundaries[boundary_cursor:]
         if hook == f"ywc_v03_kor_inline_ack_{candidate_id}"),
        None,
    )
    if boundary is None:
        raise AssertionError(("actual_callback_did_not_reach_matching_ack", candidate_id, world.ack_boundaries[boundary_cursor:]))
    if not all(name in boundary for name in proof_fields):
        raise AssertionError(("callback_proof_missing_at_ack_boundary", candidate_id, proof_fields, boundary))
    if boundary.get(f"ywc_v03_kor_inline_callback_{candidate_id}") != 1:
        raise AssertionError(("callback_flag_missing_at_ack_boundary", candidate_id, boundary))
    if boundary.get(f"ywc_v03_kor_inline_callback_candidate_{candidate_id}") != candidate_id:
        raise AssertionError(("callback_candidate_mismatch", candidate_id, boundary))
    if boundary.get(f"ywc_v03_kor_inline_callback_epoch_{candidate_id}") != epoch:
        raise AssertionError(("callback_epoch_mismatch", candidate_id, epoch, boundary))
    if boundary.get(f"ywc_v03_kor_inline_callback_queue_{candidate_id}") != state.get(queue, candidate["queue"].get("value", self_value)):
        raise AssertionError(("callback_queue_value_mismatch", candidate_id, queue, boundary))
    if queue in state:
        raise AssertionError(("ack_did_not_consume_selected_queue", candidate_id, queue, state.get(queue)))
    if _queue_state(state, adapter_queues - {queue}) != sibling_queues_before:
        raise AssertionError(("ack_changed_sibling_queue", candidate_id, sibling_queues_before, _queue_state(state, adapter_queues - {queue})))
    if state.get(f"ywc_v03_kor_inline_served_{_arc_number(world, candidate['arc']['slug'])}") != state.get("ywc_v03_kor_inline_round"):
        raise AssertionError(("callback_did_not_mark_arc_served_in_current_epoch", candidate_id, state))
    if any(name in state for name in proof_fields):
        raise AssertionError(("ack_left_transient_callback_proof", candidate_id, state))
    option = next(body for key, _, body in event if key == "option"
                  and field(body, "name").endswith(".defer"))
    if not world.conditions(field(option, "trigger"), "KOR"):
        raise AssertionError(("defer_not_legal", actual_id))
    world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")], "KOR")
    if world.countries["KOR"].get(queue) != self_value:
        raise AssertionError(("defer_did_not_retain_native_queue", actual_id, queue, world.countries["KOR"].get(queue)))
    if "ywc_v03_major_event_cooldown" not in world.countries["KOR"]:
        raise AssertionError(("actual_event_immediate_did_not_start_cooldown", actual_id))
    world.trace.append({"contract_defer": actual_id, "day": world.elapsed_months * 30})


def _receive_and_choose(world, event_id, option_suffix=None):
    """Resolve a real reserved popup through its native immediate and option."""
    tag, actual_id = world.events.pop(0)
    if (tag, actual_id) != ("KOR", event_id):
        raise AssertionError(("unexpected_progression_dispatch", tag, actual_id, event_id))
    event = world.event_defs[actual_id]
    if not world.conditions(field(event, "trigger"), "KOR"):
        raise AssertionError(("progression_event_trigger_rejected", actual_id))
    candidate_id = int(world.countries["KOR"]["ywc_v03_kor_inline_reservation"])
    candidate = _candidates(world)[candidate_id]
    queue = candidate["queue"]["queue"]
    state = world.countries["KOR"]
    expected_queue = candidate["queue"].get("value", int(actual_id.rsplit(".", 1)[1]))
    if state.get(queue) != expected_queue:
        raise AssertionError(("progression_selected_queue_not_exact", actual_id, candidate_id,
                              queue, expected_queue, state.get(queue)))
    sibling_queues = {
        row["queue"]["queue"] for row in _candidates(world).values()
        if row["arc"]["slug"] == candidate["arc"]["slug"] and row["queue"]["queue"] != queue
    }
    sibling_snapshot = _queue_state(state, sibling_queues)
    epoch = state["ywc_v03_kor_inline_reservation_epoch"]
    before = len(world.ack_boundaries)
    world.execute(field(event, "immediate"), "KOR")
    ack = next((row for row in world.ack_boundaries[before:]
                if row[0] == f"ywc_v03_kor_inline_ack_{candidate_id}"), None)
    if ack is None:
        raise AssertionError(("progression_callback_ack_missing", actual_id, world.ack_boundaries[before:]))
    if queue in state:
        raise AssertionError(("progression_ack_did_not_consume_selected_queue", actual_id, queue, state.get(queue)))
    if _queue_state(state, sibling_queues) != sibling_snapshot:
        raise AssertionError(("progression_ack_changed_sibling_queues", actual_id, sibling_snapshot,
                              _queue_state(state, sibling_queues)))
    for key, expected in ((f"ywc_v03_kor_inline_callback_{candidate_id}", 1),
                          (f"ywc_v03_kor_inline_callback_candidate_{candidate_id}", candidate_id),
                          (f"ywc_v03_kor_inline_callback_epoch_{candidate_id}", epoch),
                          (f"ywc_v03_kor_inline_callback_queue_{candidate_id}", candidate["queue"].get("value"))):
        if ack[1].get(key) != expected:
            raise AssertionError(("progression_callback_proof_mismatch", actual_id, key, expected, ack[1].get(key)))
    if option_suffix is not None:
        option = next((body for key, _, body in event if key == "option"
                       and field(body, "name").endswith("." + option_suffix)), None)
        if option is None or not world.conditions(field(option, "trigger"), "KOR"):
            raise AssertionError(("native_route_option_not_legal", actual_id, option_suffix,
                                  world.countries["KOR"], world.trace[-12:]))
        world.execute([node for node in option if node[0] not in
                       ("name", "trigger", "ai_chance", "custom_tooltip")], "KOR")
        world.trace.append({"contract_option": actual_id, "option": option_suffix,
                            "day": world.elapsed_months * 30})


def _drive_actual_school_to_review(world):
    """Use real KOR school/ports pulses and paid event options to reach phase 3."""
    school = _arc(world, SCHOOL)
    ports = _arc(world, PORTS)
    choices = {
        "ywc_kor.1010": "co_manage",
        "ywc_kor.1011": "record_old_invoice",
        "ywc_kor.1012": "share_review",
        "ywc_kor.1013": "university_post",
        "ywc_kor.1014": "keep_docket",
        "ywc_kor.1015": "start_review",
    }
    reached = False
    for _ in range(360):
        world.advance_months(1)
        world.elapsed_months += 1
        school_phase = next((journal_id for journal_id in (
            "ywc_je_v03_kor_school_funding", "ywc_je_v03_kor_school_appointments",
            "ywc_je_v03_kor_school_review") if journal_id in world.active["KOR"]), None)
        for slug, journal_id in ((SCHOOL, school_phase),
                                 (PORTS, "ywc_je_v03_kor_controlled_ports")):
            if journal_id is None:
                continue
            if journal_id not in world.active["KOR"]:
                continue
            pulse = field(field(world.journal_defs[journal_id], "on_monthly_pulse"), "effect")
            world.execute(pulse, "KOR")
            if not world.events:
                continue
            event_id = world.events[0][1]
            if event_id in choices:
                _receive_and_choose(world, event_id, choices[event_id])
                world.refresh(school)
                world.refresh(ports)
                if "ywc_je_v03_kor_school_review" in world.active["KOR"]:
                    reached = True
                    break
            else:
                _receive_and_defer(world, event_id)
        if reached:
            break
    if not reached:
        raise AssertionError(("school_route_did_not_reach_review", world.active["KOR"],
                              world.countries["KOR"], world.trace[-30:]))


def _pulse_active_kor_arcs(world):
    for journal_id in ("ywc_je_v03_kor_school_funding", "ywc_je_v03_kor_school_appointments",
                       "ywc_je_v03_kor_school_review", "ywc_je_v03_kor_controlled_ports"):
        if journal_id in world.active["KOR"]:
            pulse = field(field(world.journal_defs[journal_id], "on_monthly_pulse"), "effect")
            world.execute(pulse, "KOR")


def _advance_one_kor_month(world):
    world.advance_months(1)
    world.elapsed_months += 1
    _pulse_active_kor_arcs(world)


def _recover_actual_school_delivery(world):
    """Wait for a fresh native dispatch; never execute a rejected stale popup."""
    for _ in range(60):
        _advance_one_kor_month(world)
        while world.events:
            tag, event_id = world.events[0]
            event = world.event_defs[event_id]
            if not world.conditions(field(event, "trigger"), tag):
                # Discard the stale UI notification after recording trigger refusal.
                world.events.pop(0)
                continue
            candidate_id = int(world.countries[tag]["ywc_v03_kor_inline_reservation"])
            candidate = _candidates(world)[candidate_id]
            if candidate["arc"]["slug"] == SCHOOL:
                if event_id != "ywc_kor.1010":
                    raise AssertionError(("unexpected_recovery_school_event", event_id, candidate_id))
                _receive_and_defer(world, event_id)
                return
            _receive_and_defer(world, event_id)
    raise AssertionError(("native_pulse_did_not_recover_school_delivery", world.countries["KOR"],
                          world.trace[-30:]))


def _drive_actual_ports_notice_and_normal_1022(world):
    """Reach coexisting native 1022 queues, then observe each real source site."""
    stage_options = {
        "ywc_kor.1018": "licensed_port",
        "ywc_kor.1019": "record_exception",
        "ywc_kor.1020": "assign_auditors",
    }
    stage_counts = {event_id: 0 for event_id in stage_options}
    deferred_1021 = False
    full_review_queued = False
    for _ in range(100):
        _advance_one_kor_month(world)
        if not world.events:
            continue
        event_id = world.events[0][1]
        if event_id in stage_options:
            _receive_and_choose(world, event_id, stage_options[event_id])
            stage_counts[event_id] += 1
            if event_id == "ywc_kor.1018":
                # A real country fact changes after the route is licensed. War
                # blocks the observation target after the licensed option resolves.
                world.countries["KOR"]["is_at_war"] = True
            continue
        if event_id == "ywc_kor.1021":
            choice = "defer" if not deferred_1021 else "verify_full"
            _receive_and_choose(world, event_id, choice)
            if deferred_1021:
                full_review_queued = True
                break
            deferred_1021 = True
            continue
        if event_id == "ywc_kor.1016":
            _receive_and_choose(world, event_id, "wait_for_observation")
        elif event_id == "ywc_kor.1017":
            _receive_and_choose(world, event_id, "retry")
        else:
            _receive_and_defer(world, event_id)
    if not full_review_queued or any(count != 1 for count in stage_counts.values()):
        raise AssertionError(("did_not_reach_native_pending_1022", stage_counts, deferred_1021,
                              world.countries["KOR"], world.trace[-30:]))
    state = world.countries["KOR"]
    if state.get("ywc_kor_ports_pending_event") != 1022:
        raise AssertionError(("native_verify_full_did_not_queue_1022", state))
    for _ in range(20):
        _advance_one_kor_month(world)
        if state.get("ywc_kor_ports_notice_event") == 1022 and world.events:
            break
        if world.events:
            # Before notice maturity, ordinary 1022 delivery is not deferred by
            # source construction; the 1021 delay above keeps it behind notice due.
            raise AssertionError(("unexpected_popup_before_notice_coexistence", world.events,
                                  state.get("ywc_kor_ports_notice_event"), state))
    else:
        raise AssertionError(("native_notice_did_not_mature", state, world.trace[-30:]))
    if world.events[0][1] != "ywc_kor.1022":
        raise AssertionError(("wrong_notice_popup", world.events, state))
    if state.get("ywc_kor_ports_pending_event") != 1022:
        raise AssertionError(("normal_and_notice_1022_not_coexisting", state))
    notice_candidate = int(state["ywc_v03_kor_inline_reservation"])
    if notice_candidate != 20:
        raise AssertionError(("notice_used_wrong_source_site", notice_candidate, world.trace[-20:]))
    _receive_and_choose(world, "ywc_kor.1022", "defer")
    if state.get("ywc_kor_ports_pending_event") != 1022 or "ywc_kor_ports_notice_event" in state:
        raise AssertionError(("notice_defer_did_not_preserve_normal_queue_only", state))
    state["is_at_war"] = False
    for _ in range(8):
        _advance_one_kor_month(world)
        if world.events:
            break
    if not world.events or world.events[0][1] != "ywc_kor.1022":
        raise AssertionError(("normal_1022_not_delivered_after_recovery", world.events, state,
                              world.trace[-30:]))
    normal_candidate = int(state["ywc_v03_kor_inline_reservation"])
    if normal_candidate != 26:
        raise AssertionError(("normal_1022_used_wrong_source_site", normal_candidate,
                              world.trace[-20:]))
    _receive_and_choose(world, "ywc_kor.1022")
    if state.get("ywc_kor_ports_pending_event") is not None:
        raise AssertionError(("normal_1022_ack_did_not_consume_pending_queue", state))
    ack_names = [name for name, _ in world.ack_boundaries]
    if "ywc_v03_kor_inline_ack_20" not in ack_names or "ywc_v03_kor_inline_ack_26" not in ack_names:
        raise AssertionError(("notice_and_normal_callbacks_not_both_reached", ack_names))
    if "ywc_v03_kor_inline_ack_25" in ack_names:
        raise AssertionError(("native_redundant_notice_site_became_dispatchable", ack_names))


class KorFairDeliveryContract(unittest.TestCase):
    def _reserve_school_event(self):
        world = KorFairWorld()
        world.countries["KOR"] = _facts()
        world.countries["KOR"][LEGACY_MARKER] = 1
        world.run("ywc_v03_initialize_country", "KOR")
        world.refresh(_arc(world, SCHOOL))
        world.refresh(_arc(world, PORTS))
        world.advance_months(1)
        world.elapsed_months += 1
        journal = world.journal_defs["ywc_je_v03_kor_school_funding"]
        world.execute(field(field(journal, "on_monthly_pulse"), "effect"), "KOR")
        if not world.events or world.events[0] != ("KOR", "ywc_kor.1010"):
            raise AssertionError(("expected_actual_school_reservation", world.events, world.trace[-8:]))
        return world, world.event_defs["ywc_kor.1010"]

    def test_two_natively_admitted_arcs_each_receive_five_real_monthly_delivery_opportunities(self):
        traces = []
        for order in ((SCHOOL, PORTS), (PORTS, SCHOOL)):
            world = KorFairWorld()
            world.countries["KOR"] = _facts()
            world.countries["KOR"][LEGACY_MARKER] = 1
            # Reproduce the actual startup migration using only a legacy public-history fact.
            world.run("ywc_v03_initialize_country", "KOR")
            self.assertEqual(world.countries["KOR"].get("ywc_v03_kor_v03_kor_military_accounts_settled"), 1)
            self.assertFalse(world.conditions(field(world.journal_defs["ywc_je_v03_kor_military_audit"], "possible"), "KOR"),
                             "legacy migration must close the new M1 entry")
            for slug in order:
                world.refresh(_arc(world, slug))
            self.assertEqual(set(world.active["KOR"]), {"ywc_je_v03_kor_school_funding", "ywc_je_v03_kor_controlled_ports"})
            self.assertEqual(world.countries["KOR"].get("ywc_v03_active_arc_count"), 2)
            self.assertEqual(world.countries["KOR"].get("ywc_v03_visible_task_count"), 2)

            counts = {SCHOOL: 0, PORTS: 0}
            recipient_by_event = {
                **{f"ywc_kor.{n:04d}": SCHOOL for n in range(1010, 1018)},
                **{f"ywc_kor.{n:04d}": PORTS for n in range(1018, 1024)},
            }
            dispatch = []
            while sum(counts.values()) < 10 and world.elapsed_months < 90:
                world.advance_months(1)
                world.elapsed_months += 1
                # Run each active JE's actual monthly pulse in the supplied candidate
                # order, handling its real popup immediately before the next JE pulse.
                # This preserves the native pulse body while exposing old-source priority.
                for slug in order:
                    active_je = ("ywc_je_v03_kor_school_funding" if slug == SCHOOL
                                 else "ywc_je_v03_kor_controlled_ports")
                    if active_je not in world.active["KOR"]:
                        continue
                    journal = world.journal_defs[active_je]
                    if world.conditions(field(journal, "complete"), "KOR") or world.conditions(field(journal, "fail"), "KOR"):
                        raise AssertionError(("terminal_je_still_active", active_je))
                    pulse = field(field(journal, "on_monthly_pulse"), "effect")
                    world.execute(pulse, "KOR")
                    if not world.events:
                        continue
                    tag, event_id = world.events[0]
                    self.assertEqual(tag, "KOR")
                    recipient = recipient_by_event.get(event_id)
                    self.assertIsNotNone(recipient, (order, event_id, world.trace[-10:]))
                    _receive_and_defer(world, event_id)
                    counts[recipient] += 1
                    dispatch.append((world.elapsed_months * 30, recipient, event_id, slug))
            traces.append({"order": order, "counts": dict(counts), "dispatch": dispatch})
            self.assertEqual(sum(counts.values()), 10, (order, counts, dispatch))
            days = [row[0] for row in dispatch]
            self.assertEqual(days, [30 + 90 * i for i in range(10)], (order, days, dispatch))
        expected = {SCHOOL: 5, PORTS: 5}
        self.assertEqual([row["counts"] for row in traces], [expected, expected], traces)

    def test_real_event_guard_rejects_expired_or_mutated_reservations(self):
        mutations = (
            ("expired", lambda world: (world.advance_months(91),
                                        setattr(world, "elapsed_months", world.elapsed_months + 91))),
            ("changed_queue", lambda world: world.countries["KOR"].__setitem__("ywc_kor_school_pending_event", 1011)),
            ("changed_epoch", lambda world: world.countries["KOR"].__setitem__("ywc_v03_kor_inline_reservation_epoch", 2)),
            ("phase_completed", lambda world: world.active["KOR"].remove("ywc_je_v03_kor_school_funding")),
            ("already_served", lambda world: world.countries["KOR"].__setitem__(
                "ywc_v03_kor_inline_served_2", world.countries["KOR"]["ywc_v03_kor_inline_round"])),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=label):
                world, event = self._reserve_school_event()
                state = world.countries["KOR"]
                original_epoch = state["ywc_v03_kor_inline_reservation_epoch"]
                original_queue = state["ywc_kor_school_pending_event"]
                mutate(world)
                self.assertFalse(world.conditions(field(event, "trigger"), "KOR"),
                                 (label, state, world.trace[-8:]))
                self.assertEqual(len(world.events), 1, (label, world.events))
                # The refused popup is never executed. Restore the engine-owned
                # facts or queue, then let the actual timer and monthly source pulse
                # make a fresh reservation and deliver a real callback.
                world.events.pop(0)
                if label == "changed_queue":
                    state["ywc_kor_school_pending_event"] = original_queue
                if label == "changed_epoch":
                    state["ywc_v03_kor_inline_reservation_epoch"] = original_epoch
                if label == "phase_completed":
                    if "ywc_je_v03_kor_school_funding" not in world.active["KOR"]:
                        world.active["KOR"].append("ywc_je_v03_kor_school_funding")
                if label == "already_served":
                    state.pop("ywc_v03_kor_inline_served_2", None)
                if label != "expired":
                    world.advance_months(91)
                    world.elapsed_months += 91
                _recover_actual_school_delivery(world)
                self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1, label)
                self.assertEqual(state.get("ywc_kor_school_pending_event"), original_queue, label)

    def test_paid_school_route_direct_adds_both_later_phases_and_clears_old_witnesses(self):
        world = KorFairWorld()
        world.countries["KOR"] = _facts()
        world.countries["KOR"][LEGACY_MARKER] = 1
        world.run("ywc_v03_initialize_country", "KOR")
        school = _arc(world, SCHOOL)
        world.refresh(school)
        world.refresh(_arc(world, PORTS))
        _drive_actual_school_to_review(world)
        state = world.countries["KOR"]
        self.assertEqual(world.history["KOR"]["ywc_je_v03_kor_school_funding"], "complete")
        self.assertEqual(world.history["KOR"]["ywc_je_v03_kor_school_appointments"], "complete")
        self.assertIn("ywc_je_v03_kor_school_review", world.active["KOR"])
        for je_id in ("ywc_je_v03_kor_school_appointments", "ywc_je_v03_kor_school_review"):
            self.assertFalse(any(key == "possible" for key, _, _ in world.journal_defs[je_id]), je_id)
        for witness in ("ywc_v03_kor_inline_live_school_funding",
                        "ywc_v03_kor_inline_live_school_appointments"):
            self.assertNotIn(witness, state)
        self.assertEqual(state.get("ywc_v03_kor_inline_live_school_review"), 1)
        self.assertTrue(any(("type", "=", "ywc_je_v03_kor_school_appointments") in request
                            for _, request in world.journals))
        self.assertTrue(any(("type", "=", "ywc_je_v03_kor_school_review") in request
                            for _, request in world.journals))
        route_events = [row["contract_option"] for row in world.trace if "contract_option" in row]
        self.assertEqual([value for value in route_events if value.startswith("ywc_kor.101")],
                         [f"ywc_kor.{n}" for n in ("1010", "1011", "1012", "1013", "1014", "1015")])

    def test_fresh_m1_uses_its_real_possible_pulse_and_first_generated_callback(self):
        world = KorFairWorld()
        world.countries["KOR"] = _facts()
        world.run("ywc_v03_initialize_country", "KOR")
        m1_id = "ywc_je_v03_kor_military_audit"
        m1_arc = _arc(world, "v03_kor_military_accounts")
        self.assertFalse(world.countries["KOR"].get(LEGACY_MARKER))
        self.assertTrue(world.conditions(field(world.journal_defs[m1_id], "possible"), "KOR"))
        world.refresh(m1_arc)
        self.assertEqual(world.active["KOR"], [m1_id])
        journal = world.journal_defs[m1_id]
        world.advance_months(1)
        world.elapsed_months += 1
        world.execute(field(field(journal, "on_monthly_pulse"), "effect"), "KOR")
        self.assertEqual(world.events, [("KOR", "ywc_kor.1000")])
        _receive_and_choose(world, "ywc_kor.1000")
        state = world.countries["KOR"]
        self.assertEqual(state.get("ywc_v03_kor_v03_kor_military_accounts_last_event"), 1)
        self.assertEqual(state.get("ywc_v03_major_event_cooldown"), 1)
        self.assertEqual(world.days_until_expiry["KOR"].get("ywc_v03_major_event_cooldown"), 90)
        self.assertEqual(state.get("ywc_v03_active_arc_count"), 1)
        self.assertEqual(state.get("ywc_v03_visible_task_count"), 1)
        self.assertNotIn("ywc_kor_pending_event", state)
        self.assertIn("ywc_v03_kor_inline_ack_1", [name for name, _ in world.ack_boundaries])

    def test_actual_notice_and_normal_1022_callbacks_use_distinct_native_candidates(self):
        world = KorFairWorld()
        world.countries["KOR"] = _facts()
        world.countries["KOR"][LEGACY_MARKER] = 1
        world.run("ywc_v03_initialize_country", "KOR")
        world.refresh(_arc(world, SCHOOL))
        world.refresh(_arc(world, PORTS))
        _drive_actual_school_to_review(world)
        school_retired = False
        for _ in range(30):
            _advance_one_kor_month(world)
            if not world.events:
                continue
            event_id = world.events[0][1]
            if event_id == "ywc_kor.1016":
                _receive_and_choose(world, event_id, "withdraw")
                world.refresh(_arc(world, SCHOOL))
                school_retired = True
                break
            _receive_and_defer(world, event_id)
        self.assertTrue(school_retired, (world.active["KOR"], world.trace[-20:]))
        self.assertNotIn("ywc_je_v03_kor_school_review", world.active["KOR"])
        _drive_actual_ports_notice_and_normal_1022(world)


if __name__ == "__main__":
    unittest.main()
