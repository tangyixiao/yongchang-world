"""Permanent source-driven LAN story and inline-delivery acceptance.

The fixture interprets shipped Clausewitz source; it is not the game engine. It
provides only the authored SHU->LAN subject fact and explicit ordinary law,
building, and finance inputs needed for the paid option gates. No private
adapter state is seeded. Engine event-queue scheduling, market simulation,
actual UI popups, and same-value external ABA are outside this interpreter.
"""
from __future__ import annotations

import itertools
import json
import unittest
from pathlib import Path

from tests.test_v03_lan_actual_fairness import _fresh_three_arcs, ARC_ORDER, _fields, _effects
from tools.v03_inline_delivery_adapter import render_inline_country_adapters

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/content/v03/countries/lan.json"
ORDERINGS = tuple(itertools.permutations(ARC_ORDER))
PAID = {1000: "public_audit", 1010: "compensate", 1020: "mutual_fund"}
FOLLOWUP = {
    1001: "staff_audit", 1002: "public_share_first", 1003: "use_shipping", 1004: "merge_customs", 1005: "fund_audit",
    1011: "deed_review", 1012: "notify_neighbour", 1013: "fund_board", 1014: "keep_restricted", 1015: "expand_blocks",
    1021: "enrol_mine", 1022: "assume_debt", 1023: "fund", 1024: "borrow_practice", 1025: "pay_both",
}
REVIEW = {1006: "reconsider_mine_12", 1016: "reconsider_river_12", 1026: "reconsider_fund_12"}
NOTICE36 = {1007: "narrow_mine_36", 1017: "narrow_river_36", 1027: "narrow_fund_36"}
TERMINAL = {1007: "settle_full", 1017: "settle_full", 1027: "settle_full"}


def _scenario(order):
    world, active, native, evidence = _fresh_three_arcs(order)
    country = world.countries["LAN"]
    country.update({
        "gold_reserves": 10000,
        "yearly_gross_income": 52000,
        "test_laws": {"law_commercialized_agriculture", "law_poor_laws"},
        "test_buildings": [
            {"type": "building_government_administration", "groups": set(), "level": 2, "occupancy": .9, "shortage": False},
            {"type": "building_mine", "groups": {"bg_mining"}, "level": 3, "occupancy": .75, "shortage": False},
            {"type": "building_port", "groups": set(), "level": 1, "occupancy": .7, "shortage": False},
        ],
    })
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    arcs = {a["slug"]: a for a in catalog["arcs"]}
    current = {slug: arcs[slug]["journals"][0]["id"] for slug in ARC_ORDER}
    by_event = {}
    for slug in ARC_ORDER:
        for event in arcs[slug]["events"]:
            by_event[event["id"]] = slug
    return world, active, native, catalog, arcs, current, len(world.journals), by_event


def _refresh(world, slug, arcs, current, cursor, active):
    jid = current[slug]
    if jid is None:
        return cursor
    je = world.journal_defs[jid]
    complete = next(v for k, _, v in je if k == "complete")
    failed = next(v for k, _, v in je if k == "fail")
    done, fail = world.conditions(complete, "LAN"), world.conditions(failed, "LAN")
    if done and fail:
        raise AssertionError((jid, "both terminal predicates true"))
    if not (done or fail):
        return cursor
    active[jid]["status"] = "completed" if done else "failed"
    terminal_handler = "on_complete" if done else "on_fail"
    handler = next((v for key, _, v in je if key == terminal_handler), None)
    if handler is not None:
        world.execute(handler, "LAN")
    world.active_journal_ids["LAN"].discard(jid)
    assert jid not in world.active_journal_ids["LAN"], (jid, "source terminal JE remained active")
    current[slug] = None
    for tag, body in world.journals[cursor:]:
        cursor += 1
        if tag != "LAN":
            continue
        next_id = _fields(body).get("type")
        if next_id not in {j["id"] for j in arcs[slug]["journals"]}:
            continue
        next_je = world.journal_defs[next_id]
        shown = next(v for k, _, v in next_je if k == "is_shown_when_inactive")
        possible = next(v for k, _, v in next_je if k == "possible")
        if world.conditions(shown, "LAN") and world.conditions(possible, "LAN"):
            world.execute(next(v for k, _, v in next_je if k == "immediate"), "LAN")
            current[slug] = next_id
            active[next_id] = {"status": "active", "origin": "source_option_handoff"}
            world.active_journal_ids["LAN"].add(next_id)
    return cursor


def _dispatch(world, slug, event_id, day, adapter, blocked_story=False):
    event = world.event_defs[event_id]
    trigger = next((v for k, _, v in event if k == "trigger"), [])
    if trigger:
        assert world.conditions(trigger, "LAN"), (event_id, day, "source event trigger false")
    country = world.countries["LAN"]
    prefix = "ywc_v03_lan_inline"
    hooks = adapter["event_hooks"].get(event_id, [])
    # Every emitted native event must have its concrete queue candidate mapped into
    # this event's generated source guard. The reservation is produced by source.
    reservation = country.get(prefix + "_reservation")
    assert reservation is not None and reservation > 0, (event_id, day, "no source reservation")
    cid = int(reservation)
    selected = f"{prefix}_dispatch_{cid}"
    assert selected in hooks, (event_id, cid, hooks)
    assert selected in world.trigger_defs, (event_id, selected)
    assert world.conditions(world.trigger_defs[selected], "LAN"), (event_id, selected, day)
    before = dict(country)
    ack_witnesses = []
    flat_candidates = [(branch["journal"], c)
                       for arc in json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["arcs"]
                      for branch in arc["inline_delivery_adapter"]["branches"]
                      for c in branch["candidates"]]
    candidate_journal, candidate = flat_candidates[cid - 1]
    queue_name = candidate["queue"]
    snapshot_value = f"{prefix}_c{cid}_{queue_name}_value"
    live_witness = adapter["live_witnesses"][candidate_journal]
    original_run = world.run
    def witness_run(name, tag="SHU"):
        if name.startswith(prefix + "_ack_"):
            state = dict(country)
            assert name == f"{prefix}_ack_{cid}", (event_id, cid, name)
            self_owned = {
                "reservation": state.get(prefix + "_reservation") == cid,
                "timer": prefix + "_timer" in state,
                "global_epoch_positive": state.get(prefix + "_reservation_epoch", 0) > 0,
                "candidate_epoch_matches": state.get(f"{prefix}_candidate_epoch_{cid}") == state.get(prefix + "_reservation_epoch"),
                "source_je_active": candidate_journal in world.active_journal_ids["LAN"],
                "phase_live": state.get(live_witness) == 1,
                "body_completed": state.get(f"{prefix}_body_completed_{cid}") == 1,
                "body_epoch_matches": state.get(f"{prefix}_body_completed_epoch_{cid}") == state.get(prefix + "_reservation_epoch"),
                "callback_proof": state.get(f"{prefix}_callback_{cid}") == 1,
                "callback_id": state.get(f"{prefix}_callback_candidate_{cid}") == cid,
                "callback_epoch": state.get(f"{prefix}_callback_epoch_{cid}") == state.get(prefix + "_reservation_epoch"),
                "callback_queue": state.get(f"{prefix}_callback_queue_{cid}") == state.get(snapshot_value),
                "exact_live_queue": state.get(queue_name) == state.get(snapshot_value),
            }
            assert all(self_owned.values()), (event_id, cid, self_owned)
            ack_witnesses.append((name, state))
        return original_run(name, tag)
    world.run = witness_run
    immediate = next((v for k, _, v in event if k == "immediate"), [])
    assert immediate, (event_id, "expected guarded native immediate")
    # Execute the whole guarded native immediate, so proof and callback hooks occur
    # only after the complete source body. Never execute an AST suffix as an ACK.
    try:
        world.execute(immediate, "LAN")
    finally:
        world.run = original_run
    after_body = dict(country)
    served_name = f"{prefix}_served_{next(i for i, arc in enumerate(ARC_ORDER, 1) if arc == slug)}"
    round_before = before.get(prefix + "_round", 0)
    assert queue_name not in after_body, (event_id, queue_name, "ACK did not remove selected source queue")
    assert prefix + "_reservation" not in after_body, (event_id, "ACK did not release reservation before option")
    assert prefix + "_timer" not in after_body, (event_id, "ACK did not release timer before option")
    assert after_body.get(served_name) == round_before, (event_id, served_name, round_before, after_body.get(served_name))
    options = [v for k, _, v in event if k == "option"]
    legal = []
    for option in options:
        gate = next((v for k, _, v in option if k == "trigger"), [])
        if not gate or world.conditions(gate, "LAN"):
            legal.append(_fields(option)["name"].rsplit(".", 1)[-1])
    number = int(event_id.rsplit(".", 1)[1])
    if number in PAID:
        choice = PAID[number]
    elif number in FOLLOWUP:
        choice = ("defer" if blocked_story and number in {1001, 1011, 1021}
                  else FOLLOWUP[number])
    elif number in REVIEW:
        slot = {1006: "mine", 1016: "river", 1026: "fund"}[number]
        choice = REVIEW[number] if country.get(f"ywc_lan_{slot}_notice_current") == 12 else (
            "begin_review" if country.get(f"ywc_lan_{slot}_six_months_complete") else "defer")
    elif number in NOTICE36:
        slot = {1007: "mine", 1017: "river", 1027: "fund"}[number]
        choice = NOTICE36[number] if country.get(f"ywc_lan_{slot}_notice_current") == 36 else "settle_full"
    elif number in TERMINAL:
        choice = TERMINAL[number]
    else:
        choice = next((x for x in legal if x != "withdraw"), legal[0])
    assert choice in legal, (event_id, choice, legal, day)
    option = next(o for o in options if _fields(o)["name"].rsplit(".", 1)[-1] == choice)
    gate = next((v for k, _, v in option if k == "trigger"), [])
    if gate:
        assert world.conditions(gate, "LAN"), (event_id, choice, "option gate false")
    world.execute(_effects(option), "LAN")
    # Inline callback/ACK source effects are part of the complete native immediate.
    # A successful candidate records its per-arc served round and releases slot.
    assert any(name == f"{prefix}_ack_{cid}" for name, _ in ack_witnesses), (event_id, cid, "actual immediate did not invoke candidate ACK")
    assert country.get(served_name) == round_before, (event_id, cid, "actual immediate did not ACK")
    assert prefix + "_reservation" not in country, (event_id, "ACK did not release reservation")
    return {"day": day, "event": event_id, "arc": slug, "candidate": cid,
            "event_hooks": hooks, "before": before, "after_immediate": after_body,
            "after_option": dict(country), "legal_options": legal, "selected": choice}


class LanNativeStoryAcceptanceTest(unittest.TestCase):
    def test_all_six_admission_and_pulse_orders_reach_five_native_deliveries_each(self):
        for admission_and_pulse_order in ORDERINGS:
            with self.subTest(order=admission_and_pulse_order):
                (world, active, native, catalog, arcs, current, cursor,
                 by_event) = _scenario(admission_and_pulse_order)
                adapter = render_inline_country_adapters(catalog)
                counts = {slug: 0 for slug in ARC_ORDER}
                paid = {}
                event_days = {slug: [] for slug in ARC_ORDER}
                all_recipient_days = []
                fairness_day = None
                for month in range(1, 601):
                    world.advance_months(1)
                    day = 540 + 30 * month
                    for slug in admission_and_pulse_order:
                        jid = current[slug]
                        if jid is None:
                            continue
                        je = world.journal_defs[jid]
                        pulse = next(v for k, _, v in je if k == "on_monthly_pulse")
                        effect = next(v for k, _, v in pulse if k == "effect")
                        before_events = len(world.events)
                        world.execute(effect, "LAN")
                        emitted = world.events[before_events:]
                        self.assertLessEqual(len(emitted), 1, (slug, day, emitted))
                        if emitted:
                            event_id = emitted[0][1]
                            world.events.remove(emitted[0])
                            self.assertEqual(by_event[event_id], slug)
                            observation = _dispatch(world, slug, event_id, day, adapter)
                            counts[slug] += 1
                            event_days[slug].append(day)
                            all_recipient_days.append(day)
                            n = int(event_id.rsplit(".", 1)[1])
                            if n in PAID and slug not in paid:
                                paid[slug] = (day, observation["selected"])
                            cursor = _refresh(world, slug, arcs, current, cursor, active)
                    if min(counts.values()) >= 5:
                        fairness_day = day if fairness_day is None else fairness_day
                        break
                self.assertTrue(all(value >= 5 for value in counts.values()), (admission_and_pulse_order, counts))
                self.assertEqual(set(paid), set(ARC_ORDER))
                for slug, (paid_day, choice) in paid.items():
                    self.assertIn(choice, PAID.values())
                    later_days = [delivery_day for delivery_day in event_days[slug]
                                  if delivery_day >= paid_day + 180]
                    self.assertGreaterEqual(len(later_days), 2, (slug, paid_day, event_days[slug]))
                self.assertEqual(world.countries["LAN"].get("ywc_v03_active_arc_count"), 3)
                self.assertEqual(len(native), 3)
                self.assertIsNotNone(fairness_day)
                ordered_recipient_days = sorted(all_recipient_days)
                self.assertTrue(all(b - a >= 90 for a, b in zip(ordered_recipient_days, ordered_recipient_days[1:])),
                                (admission_and_pulse_order, "LAN recipients across arcs violated the real 90-day cooldown", ordered_recipient_days))

    def test_source_options_handoff_through_six_terminal_journal_entries(self):
        (world, active, native, catalog, arcs, current, cursor,
         by_event) = _scenario(ARC_ORDER)
        adapter = render_inline_country_adapters(catalog)
        seen = {slug: set() for slug in ARC_ORDER}
        for month in range(1, 601):
            world.advance_months(1)
            day = 540 + 30 * month
            for slug in ARC_ORDER:
                jid = current[slug]
                if jid is None:
                    continue
                seen[slug].add(jid)
                je = world.journal_defs[jid]
                pulse = next(v for k, _, v in je if k == "on_monthly_pulse")
                effect = next(v for k, _, v in pulse if k == "effect")
                before = len(world.events)
                world.execute(effect, "LAN")
                emitted = world.events[before:]
                self.assertLessEqual(len(emitted), 1, (slug, day, emitted))
                if emitted:
                    event_id = emitted[0][1]
                    world.events.remove(emitted[0])
                    self.assertEqual(by_event[event_id], slug)
                    _dispatch(world, slug, event_id, day, adapter)
                    cursor = _refresh(world, slug, arcs, current, cursor, active)
            if all(current[s] is None for s in ARC_ORDER):
                break
        self.assertEqual(current, {slug: None for slug in ARC_ORDER})
        self.assertEqual(seen, {slug: {j["id"] for j in arcs[slug]["journals"]}
                                for slug in ARC_ORDER})
        self.assertEqual(world.countries["LAN"].get("ywc_v03_active_arc_count"), 0)
        self.assertEqual(world.countries["LAN"].get("ywc_v03_visible_task_count"), 0)
        for slug in ARC_ORDER:
            self.assertTrue(all(active[j["id"]]["status"] == "completed"
                                for j in arcs[slug]["journals"]))
        self.assertEqual(len(native), 3)

    def test_native_paid_to_blocked_12_36_notices_and_default_recovery(self):
        (world, active, native, catalog, arcs, current, cursor,
         by_event) = _scenario(ARC_ORDER)
        adapter = render_inline_country_adapters(catalog)
        paid = set()
        notices = {slug: {} for slug in ARC_ORDER}
        all_recipient_days = []
        blocked = False
        for month in range(1, 401):
            world.advance_months(1)
            day = 540 + 30 * month
            for slug in ARC_ORDER:
                jid = current[slug]
                if jid is None:
                    continue
                je = world.journal_defs[jid]
                pulse = next(v for k, _, v in je if k == "on_monthly_pulse")
                effect = next(v for k, _, v in pulse if k == "effect")
                before_events = len(world.events)
                world.execute(effect, "LAN")
                emitted = world.events[before_events:]
                self.assertLessEqual(len(emitted), 1, (slug, day, emitted))
                if not emitted:
                    continue
                event_id = emitted[0][1]
                world.events.remove(emitted[0])
                self.assertEqual(by_event[event_id], slug)
                observation = _dispatch(world, slug, event_id, day, adapter,
                                        blocked_story=blocked)
                all_recipient_days.append(day)
                number = int(event_id.rsplit(".", 1)[1])
                short = {ARC_ORDER[0]: "mine", ARC_ORDER[1]: "river", ARC_ORDER[2]: "fund"}[slug]
                if number in PAID:
                    paid.add(slug)
                if number in {1006, 1016, 1026} and observation["before"].get(f"ywc_lan_{short}_notice_current") == 12:
                    notices[slug][12] = observation
                if number in {1007, 1017, 1027} and observation["before"].get(f"ywc_lan_{short}_notice_current") == 36:
                    notices[slug][36] = observation
                cursor = _refresh(world, slug, arcs, current, cursor, active)
            if len(paid) == len(ARC_ORDER) and not blocked:
                # A normal world fact changes affordability only after every native
                # paid option has actually been selected.
                world.countries["LAN"]["in_default"] = True
                blocked = True
            if blocked and all(set(notices[s]) == {12, 36} for s in ARC_ORDER):
                break
        self.assertEqual(paid, set(ARC_ORDER))
        self.assertTrue(blocked)
        for slug in ARC_ORDER:
            short = {ARC_ORDER[0]: "mine", ARC_ORDER[1]: "river", ARC_ORDER[2]: "fund"}[slug]
            self.assertEqual(set(notices[slug]), {12, 36}, (slug, notices[slug].keys()))
            first, second = notices[slug][12], notices[slug][36]
            self.assertGreaterEqual(second["day"] - first["day"], 90, (slug, first["day"], second["day"]))
            for threshold, row in ((12, first), (36, second)):
                self.assertEqual(row["before"].get(f"ywc_lan_{short}_notice_current"), threshold)
                self.assertEqual(row["selected"], f"{'reconsider' if threshold == 12 else 'narrow'}_{short}_{threshold}")
                self.assertEqual(row["before"].get(f"ywc_lan_{short}_notice12_sent"), 1)
                if threshold == 12:
                    self.assertNotIn(f"ywc_lan_{short}_notice36_sent", row["before"])
                else:
                    self.assertEqual(row["before"].get(f"ywc_lan_{short}_notice36_sent"), 1)
                self.assertEqual(row["after_immediate"].get(f"ywc_lan_{short}_notice_event"), None)
                self.assertIsNone(row["after_option"].get(f"ywc_lan_{short}_notice_current"))
                ordinary = {"mine": 1001, "river": 1011, "fund": 1021}[short]
                self.assertEqual(row["after_option"].get(f"ywc_lan_{short}_pending_event"), ordinary)
        ordered_recipient_days = sorted(all_recipient_days)
        self.assertTrue(all(b - a >= 90 for a, b in zip(ordered_recipient_days, ordered_recipient_days[1:])),
                        ("global notice story bypassed the real 90-day cooldown", ordered_recipient_days))
        # Restore only the ordinary finance fact; real month advances and monthly
        # source helpers must clear stale blocked-notice context themselves.
        world.countries["LAN"]["in_default"] = False
        recovery_days = 0
        recovery_start_day = 540 + 30 * month
        for _ in range(12):
            recovery_days += 30
            world.advance_months(1)
            for slug in ARC_ORDER:
                jid = current[slug]
                if jid is None:
                    continue
                je = world.journal_defs[jid]
                pulse = next(v for k, _, v in je if k == "on_monthly_pulse")
                world.execute(next(v for k, _, v in pulse if k == "effect"), "LAN")
                emitted = [item for item in world.events if item[0] == "LAN"]
                for item in emitted:
                    world.events.remove(item)
                    recovery_event_day = recovery_start_day + recovery_days
                    _dispatch(world, slug, item[1], recovery_event_day, adapter)
                cursor = _refresh(world, slug, arcs, current, cursor, active)
        country = world.countries["LAN"]
        for short in ("mine", "river", "fund"):
            for suffix in ("blocked_months", "notice_event", "notice_current", "notice12_sent", "notice36_sent"):
                self.assertNotIn(f"ywc_lan_{short}_{suffix}", country,
                                 f"ordinary recovery did not clear {short} {suffix}")
        self.assertEqual(len(native), 3)


if __name__ == "__main__":
    unittest.main()
