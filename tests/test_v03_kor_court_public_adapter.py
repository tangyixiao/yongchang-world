"""KOR court-public isolation: immutable old four arcs plus literal new sources.

No current country/helper/generated files or business worlds are read here.
Actual-source acceptance is added only after the root's terminal source gate.
"""
import copy
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import types
import unittest

from tools import v03_inline_delivery_adapter as adapter

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "ce03a2f8a6f328788475d5692ec1eed1749095c4"
FOUNDATION = ("v03_kor_military_accounts", "v03_kor_school_factions", "v03_kor_controlled_ports")
REVENUE = "v03_kor_provincial_revenue"
COURT = "v03_kor_court_public"
JES = ("ywc_je_v03_kor_court_public_deliberation", "ywc_je_v03_kor_court_public_review")
QUEUE = "ywc_kor_public_pending_event"
RECEIPT = "ywc_v03_kor_v03_kor_court_public_last_event"


def frozen(path):
    return subprocess.run(["git", "show", BASELINE + ":" + path], cwd=ROOT,
                          check=True, capture_output=True).stdout.decode("utf-8-sig")


def bind_sources(arc):
    """Root binding interface: derive v2 proof fields from the supplied source."""
    phases, records = [], []
    for index, journal in enumerate(arc["journals"]):
        phases.append({"journal": journal["id"],
                       "live_witness": "ywc_v03_kor_inline_live_court_public_" + ("deliberation" if index == 0 else "review"),
                       **{target: hashlib.sha256(journal[source].encode()).hexdigest()
                          for target, source in (("source_script_sha256", "script"),
                                                 ("goal_sha256", "goal"), ("exit_sha256", "exit_conditions"))}})
        for source in adapter._kor_source_binding(journal["id"], journal["script"])["branches"]:
            records.append({"journal": journal["id"],
                            **{key: source[key] for key in ("branch_index", "statement_ordinal", "chain_index",
                                                           "branch_kind", "event", "chain_prior", "chain_sha256",
                                                           "candidates", "queue_exclusions")},
                            "branch_sha256": source["sha256"], "limit_sha256": source["limit_sha256"]})
    arc["inline_delivery_adapter"] = {"schema": "v03.foundation_inline_adapter.v2",
                                       "live_phases": phases, "branches": records,
                                       "direct_adds": adapter._kor_direct_adds(arc)}


def synthetic_catalog():
    catalog = json.loads(frozen("data/content/v03/countries/kor.json"))
    arc = {"slug": COURT, "era": "middle", "journals": [], "events": []}
    for jid, numbers in zip(JES, (range(1120, 1124), range(1124, 1128))):
        sends = []
        for index, number in enumerate(numbers):
            kind = "if" if index == 0 else "else_if"
            sends.append(f"{kind} = {{ limit = {{ var:{QUEUE} = {number} }} "
                         f"remove_variable = {QUEUE} trigger_event = {{ id = ywc_kor.{number} }} }}")
            arc["events"].append({"id": f"ywc_kor.{number}", "trigger": "{ always = yes }", "options": [],
                                  "immediate": "{ ywc_v03_mark_major_delivered = yes "
                                  f"set_variable = {{ name = {RECEIPT} value = {number - 1119} }} }}"})
        arc["journals"].append({"id": jid,
                                "script": "{ possible = { always = yes } immediate = {} "
                                "on_monthly_pulse = { effect = { " + " ".join(sends) + " } } }",
                                "goal": "{ var:synthetic_closed = 1 }",
                                "exit_conditions": "{ var:synthetic_withdrawn = 1 }"})
    bind_sources(arc)
    catalog["arcs"].append(arc)
    return catalog


class KorCourtPublicIsolatedAdapter(unittest.TestCase):
    def test_native_body_is_exact_mark_then_own_ordinal_without_dispatch(self):
        self.assertTrue(hasattr(adapter, "_kor_court_public_native_receipt"), "court native ABI missing")
        for number, ordinal in zip(range(1120, 1128), range(1, 9)):
            body = ("{ ywc_v03_mark_major_delivered = yes "
                    f"set_variable = {{ name = {RECEIPT} value = {ordinal} }} }}")
            event = {"id": f"ywc_kor.{number}", "immediate": body}
            self.assertEqual(adapter._kor_court_public_native_receipt(event), (RECEIPT, ordinal))
            wrong_bodies = (body.replace(RECEIPT, "ywc_v03_kor_v03_kor_provincial_revenue_last_event"),
                            body.replace(RECEIPT, "ywc_v03_kor_v03_kor_school_factions_last_event"),
                            body.replace(f"value = {ordinal}", f"value = {number}"),
                            body.replace(f"value = {ordinal}", "value = 0"),
                            body.replace("= yes", "= no"), body.replace("set_variable", "change_variable"),
                            body.replace("value =", "extra = 1 value ="),
                            body[:-1] + "add_treasury = 1 }",
                            body[:-1] + f"set_variable = {{ name = ywc_v03_shu_event_dispatch value = {number} }} }}",
                            "{ set_variable = { name = " + RECEIPT + f" value = {ordinal} "
                            "} ywc_v03_mark_major_delivered = yes }")
            for wrong in wrong_bodies:
                with self.subTest(number=number, wrong=wrong), self.assertRaises(ValueError):
                    adapter._kor_court_public_native_receipt({**event, "immediate": wrong})
        for bad in (None, 1120, "ywc_kor.1119", "ywc_kor.1128", "ywc_shu.1120"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                adapter._kor_court_public_native_receipt({"id": bad, "immediate": "{}"})

    def test_fixed_selector_preserves_four_arcs_and_rejects_unregistered_inputs(self):
        arcs = [{"slug": s, "era": "foundation"} for s in FOUNDATION]
        arcs += [{"slug": s, "era": "middle"} for s in (REVENUE, COURT)]
        for order in (arcs, list(reversed(arcs))):
            try:
                selected = adapter._kor_active_arcs({"arcs": order})
            except ValueError as exc:
                self.fail(f"registered fifth court arc must be selectable: {exc}")
            self.assertEqual([a["slug"] for a in selected], [*FOUNDATION, REVENUE, COURT])
        for bad in (arcs + [arcs[-1]], arcs[1:], [a for a in arcs if a["slug"] != REVENUE],
                    arcs + [{"slug": "v03_kor_unknown", "era": "middle"}],
                    [*arcs[:-1], {"slug": COURT, "era": "late"}]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                adapter._kor_active_arcs({"arcs": bad})

    def test_rehashed_aliases_partition_body_chain_and_direct_add_mutants_reject(self):
        valid = synthetic_catalog()
        adapter.validate_inline_catalog(valid)
        for fault in ("military", "school", "ports", "revenue", "unknown_queue", "presence",
                      "partition", "order", "prior", "exclusion", "source_hash", "bool_ordinal",
                      "body_extra", "hidden", "direct_add"):
            current = copy.deepcopy(valid)
            arc = current["arcs"][-1]
            if fault in ("military", "school", "ports", "revenue", "unknown_queue", "presence"):
                queue = {"military": "ywc_kor_pending_event", "school": "ywc_kor_school_pending_event",
                         "ports": "ywc_kor_ports_pending_event", "revenue": "ywc_kor_revenue_pending_event",
                         "unknown_queue": "ywc_kor_unknown_pending_event"}.get(fault, QUEUE)
                for journal in arc["journals"]:
                    journal["script"] = journal["script"].replace(QUEUE, queue)
                if fault == "presence":
                    arc["journals"][0]["script"] = arc["journals"][0]["script"].replace(
                        f"var:{QUEUE} = 1120", f"has_variable = {QUEUE}")
            elif fault == "partition":
                arc["journals"][0]["script"] = arc["journals"][0]["script"].replace("1123", "1124")
                arc["journals"][1]["script"] = arc["journals"][1]["script"].replace("1124", "1123")
            elif fault == "order":
                arc["journals"].reverse()
            elif fault == "body_extra":
                arc["events"][0]["immediate"] = arc["events"][0]["immediate"][:-1] + "add_treasury = 1 }"
            elif fault == "hidden":
                arc["events"][0]["hidden"] = "yes"
            elif fault == "direct_add":
                arc["events"][0]["options"] = [{"key": "handoff", "effect":
                    "{ add_journal_entry = { type = " + JES[1] + " } }"}]
            bind_sources(arc)
            if fault == "prior":
                arc["inline_delivery_adapter"]["branches"][1]["chain_prior"] = []
            elif fault == "exclusion":
                arc["inline_delivery_adapter"]["branches"][0]["queue_exclusions"] = [
                    {"queue": QUEUE, "op": "=", "mode": "presence"}]
            elif fault == "source_hash":
                arc["inline_delivery_adapter"]["live_phases"][0]["source_script_sha256"] = "0" * 64
            elif fault == "bool_ordinal":
                arc["inline_delivery_adapter"]["branches"][0]["branch_index"] = False
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                adapter.validate_inline_catalog(current)

    def test_renderer_registers_fifth_arc_and_receipt_in_postproof_and_ack(self):
        catalog = synthetic_catalog()
        rendered = adapter.render_inline_country_adapters(catalog)
        self.assertEqual(len(rendered["journal_scripts"]), 10)
        self.assertIn("ywc_v03_kor_inline_served_5", rendered["effects"])
        definitions = adapter.parse_block("{ " + rendered["effects"] + " }")
        for candidate, ordinal, number in zip(range(40, 48), range(1, 9), range(1120, 1128)):
            self.assertIn(f"ywc_v03_kor_inline_candidate_{candidate} =", rendered["triggers"])
            ack = next(n for n in definitions if n.key == f"ywc_v03_kor_inline_ack_{candidate}")
            self.assertTrue(any(n.key == "var:" + RECEIPT and n.value == str(ordinal)
                                for n in adapter._walk(ack.value)))
            self.assertIn(f"var:{RECEIPT} = {ordinal}", " ".join(rendered["inline_proofs"][f"ywc_kor.{number}"]))
        reverse = copy.deepcopy(catalog)
        reverse["arcs"].reverse()
        self.assertEqual(adapter.render_inline_country_adapters(reverse), rendered)

    def test_synthetic_ack_cannot_consume_queue_with_other_callback_proofs_complete(self):
        from clausewitz_harness import PulseWorld
        rendered = adapter.render_inline_country_adapters(synthetic_catalog())
        state = {"ywc_v03_kor_inline_reservation": 40, "ywc_v03_kor_inline_timer": 1,
                 "ywc_v03_kor_inline_reservation_epoch": 7, "ywc_v03_kor_inline_candidate_epoch_40": 7,
                 "ywc_v03_kor_inline_c40_public_pending_event_present": 1,
                 "ywc_v03_kor_inline_c40_public_pending_event_value": 1120,
                 "ywc_v03_kor_inline_live_court_public_deliberation": 1, "ywc_v03_kor_inline_round": 1,
                 "ywc_v03_kor_inline_callback_40": 1, "ywc_v03_kor_inline_callback_candidate_40": 40,
                 "ywc_v03_kor_inline_callback_epoch_40": 7, "ywc_v03_kor_inline_callback_queue_40": 1120,
                 QUEUE: 1120, RECEIPT: 0}
        world = PulseWorld(rendered["effects"], {"KOR": state})
        world.journals = [("KOR", [("type", "=", JES[0])])]
        for wrong in (0, 1120):
            state[RECEIPT] = wrong
            before = copy.deepcopy(state)
            world.run("ywc_v03_kor_inline_ack_40", "KOR")
            self.assertEqual(state, before)
        state[RECEIPT] = 1
        world.run("ywc_v03_kor_inline_ack_40", "KOR")
        self.assertNotIn(QUEUE, state)
        self.assertNotIn("ywc_v03_kor_inline_reservation", state)
        self.assertEqual(state["ywc_v03_kor_inline_served_5"], 1)

    def test_immutable_old_four_and_all_nine_complete_renders_match_baseline(self):
        old = types.ModuleType("kor_court_public_frozen_adapter")
        sys.modules[old.__name__] = old
        try:
            exec(compile(frozen("tools/v03_inline_delivery_adapter.py"), old.__name__, "exec"), old.__dict__)
            for country in ("kor", "dmg", "nqg", "nmg", "mgl", "lan", "shu", "tib", "jhg"):
                catalog = json.loads(frozen(f"data/content/v03/countries/{country}.json"))
                with self.subTest(country=country):
                    self.assertEqual(adapter.render_inline_country_adapters(catalog),
                                     old.render_inline_country_adapters(catalog))
                if country == "kor":
                    self.assertEqual(len(catalog["arcs"]), 4)
                    self.assertEqual(sum(len(a["journals"]) for a in catalog["arcs"]), 8)
                    self.assertEqual(sum(len(a["inline_delivery_adapter"]["branches"]) for a in catalog["arcs"]), 39)
                    self.assertEqual(sum(len(a["inline_delivery_adapter"]["direct_adds"]) for a in catalog["arcs"]), 5)
        finally:
            sys.modules.pop(old.__name__, None)


def current_catalog():
    return json.loads((ROOT / "data/content/v03/countries/kor.json").read_text("utf-8-sig"))


def capture_native_event(world, arc, wanted):
    """Stop before a currently eligible real generated event's immediate."""
    from shu_kor_strict_review_runtime import field
    for _ in range(75):
        world.pulse(arc)
        while world.events:
            _, event_id = world.events.pop(0)
            event = world.event_defs[event_id]
            if not world.conditions(field(event, "trigger"), world.tag):
                continue
            if event_id != wanted:
                raise AssertionError(("unexpected_native_event", event_id, wanted))
            return event
        world.advance_months(1)  # PartnerWorld owns elapsed_months and Gregorian day.
    raise AssertionError(("missing_native_event", wanted, world.date))


COURT_CHOICES = dict(zip(range(1120, 1128), (
    "court_open", "pay_petition", "new_professional_witness", "sign_responsibility",
    "court_read_reply", "pay_review", "request_full", "close_full")))


class KorCourtPublicGeneratedAdapter(unittest.TestCase):
    """Actual-source tests run only after terminal/binding/generation gate."""

    def test_actual_old_four_and_exact_new_native_inventory(self):
        catalog = current_catalog()
        active = adapter._kor_active_arcs(catalog)
        prior = json.loads(frozen("data/content/v03/countries/kor.json"))["arcs"]
        self.assertEqual(active[:-1], prior, "all four accepted arcs and exact metadata remain frozen")
        self.assertEqual([a["slug"] for a in active], [*FOUNDATION, REVENUE, COURT])
        self.assertEqual(sum(len(a["journals"]) for a in active[:-1]), 8)
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["branches"]) for a in active[:-1]), 39)
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["direct_adds"]) for a in active[:-1]), 5)
        arc = active[-1]
        self.assertEqual([j["id"] for j in arc["journals"]], list(JES))
        proofs = arc["inline_delivery_adapter"]["branches"]
        self.assertEqual([p["event"] for p in proofs], [f"ywc_kor.{n}" for n in range(1120, 1128)])
        self.assertEqual([sum(p["journal"] == jid for p in proofs) for jid in JES], [4, 4])
        self.assertEqual(arc["inline_delivery_adapter"]["direct_adds"], [])
        for number, proof in zip(range(1120, 1128), proofs):
            self.assertEqual(proof["candidates"], [
                {"queue": QUEUE, "kind": "normal", "mode": "exact", "value": number}])
        for event in arc["events"]:
            self.assertEqual(adapter._kor_court_public_native_receipt(event),
                             (RECEIPT, int(event["id"].rsplit(".", 1)[1]) - 1119))
        adapter.validate_inline_catalog(catalog)
        rendered = adapter.render_inline_country_adapters(catalog)
        self.assertEqual(len(rendered["journal_scripts"]), 10)
        self.assertIn("ywc_v03_kor_inline_served_5", rendered["effects"])
        for candidate in range(40, 48):
            self.assertIn(f"ywc_v03_kor_inline_candidate_{candidate} =", rendered["triggers"])
        generated = (ROOT / "yongchang_world/events/ywc_v03_country_kor_events.txt").read_text("utf-8-sig")
        self.assertEqual(set(re.findall(r"(?m)^(ywc_kor\.112[0-7])\s*=\s*\{", generated)),
                         {f"ywc_kor.{n}" for n in range(1120, 1128)})

    def test_rehashed_actual_public_sources_cannot_borrow_any_old_queue(self):
        for queue in ("ywc_kor_pending_event", "ywc_kor_school_pending_event",
                      "ywc_kor_ports_pending_event", "ywc_kor_revenue_pending_event"):
            with self.subTest(queue=queue):
                catalog = current_catalog()
                arc = next(a for a in catalog["arcs"] if a["slug"] == COURT)
                for journal in arc["journals"]:
                    journal["script"] = journal["script"].replace(QUEUE, queue)
                bind_sources(arc)
                with self.assertRaises(ValueError):
                    adapter.validate_inline_catalog(catalog)

    def test_eight_real_native_receipts_ack_and_faulted_mark_does_not(self):
        from shu_kor_strict_review_runtime import field
        from test_v03_kor_court_public import new_world, choose, month
        world = new_world()
        arc = next(a for a in world.cat["arcs"] if a["slug"] == COURT)
        acknowledgements = []
        for number in range(1120, 1128):
            event = capture_native_event(world, arc, f"ywc_kor.{number}")
            ordinal, candidate = number - 1119, number - 1080
            state = world.countries[world.tag]
            self.assertEqual(state["ywc_v03_kor_inline_reservation"], candidate)
            self.assertEqual(state[QUEUE], number)
            for wrong in sorted({0, ordinal - 1, number}):
                with self.subTest(number=number, wrong=wrong):
                    fault = copy.deepcopy(world)
                    immediate = copy.deepcopy(field(event, "immediate"))
                    changes = []
                    def corrupt(nodes):
                        for key, _, value in nodes:
                            if key == "set_variable" and isinstance(value, list) and field(value, "name") == RECEIPT:
                                for index, child in enumerate(value):
                                    if child[0] == "value":
                                        value[index] = ("value", "=", str(wrong))
                                        changes.append(1)
                            if isinstance(value, list):
                                corrupt(value)
                    corrupt(immediate)
                    self.assertEqual(len(changes), 1)
                    fault.execute(immediate, world.tag)
                    failed = fault.countries[world.tag]
                    self.assertIn("ywc_v03_major_event_cooldown", failed)
                    self.assertEqual(failed[RECEIPT], wrong)
                    fault.run(f"ywc_v03_kor_inline_ack_{candidate}", world.tag)
                    self.assertEqual(failed["ywc_v03_kor_inline_reservation"], candidate)
                    self.assertEqual(failed[QUEUE], number)
            world.execute(field(event, "immediate"), world.tag)
            self.assertEqual(state[RECEIPT], ordinal)
            self.assertNotIn("ywc_v03_kor_inline_reservation", state)
            self.assertNotIn(QUEUE, state)
            acknowledgements.append((f"ywc_kor.{number}", candidate))
            choose(world, arc, event, COURT_CHOICES[number])
            if number == 1124:
                month(world, arc, 6)
        self.assertEqual(acknowledgements, [(f"ywc_kor.{n}", n - 1080) for n in range(1120, 1128)])
        self.assertEqual(state["ywc_kor_public_outcome"], 1)
        self.assertTrue(all(world.history[world.tag][jid] == "complete" for jid in JES))
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))

    def test_court_revenue_military_fair_native_orders_and_all_court_acks(self):
        from collections import Counter
        from shu_kor_strict_review_runtime import field
        from test_v03_kor_court_public import new_world, choose
        catalog = current_catalog()
        participants = [next(a for a in catalog["arcs"] if a["slug"] == slug)
                        for slug in (FOUNDATION[0], REVENUE, COURT)]
        mapping = {}
        for arc in adapter._kor_active_arcs(catalog):
            for proof in arc["inline_delivery_adapter"]["branches"]:
                for queue in proof["candidates"]:
                    mapping[len(mapping) + 1] = (arc["slug"], proof["event"], queue["queue"])
        choices = dict(zip(range(1000, 1010), (
            "court_supply", "pay_month", "court_roll", "publish", "fund_local", "fund_transition",
            "begin_renewal", "fund_invoice_review", "peace_ledger", "establish_court")))
        choices.update({1100: "written_shares", 1101: "pay_charter", 1102: "settle_reviewer", 1103: "sign",
                        1104: "submit", 1105: "review_responsibility", 1106: "verify", 1107: "request_full"})
        choices.update(COURT_CHOICES)
        for order in (participants, list(reversed(participants))):
            with self.subTest(order=[a["slug"] for a in order]):
                world = new_world()
                state = world.countries[world.tag]
                # Ordinary current wage policy, never a paid/history/admission seed.
                world.modifiers.append((world.tag, {"modifier": "military_wages_medium"}))
                for arc in participants:
                    world.refresh(arc)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
                deliveries = []
                for _ in range(180):
                    world.advance_months(1)
                    for arc in order:
                        for journal in arc["journals"]:
                            if journal["id"] not in world.active[world.tag]:
                                continue
                            world.execute(field(field(world.journal_defs[journal["id"]], "on_monthly_pulse"), "effect"), world.tag)
                            while world.events:
                                _, eid = world.events.pop(0)
                                candidate = int(state["ywc_v03_kor_inline_reservation"])
                                self.assertEqual(mapping[candidate][:2], (arc["slug"], eid))
                                queue = mapping[candidate][2]
                                others = {k: v for k, v in state.items() if k.startswith("ywc_kor_")
                                          and k.endswith(("pending_event", "notice_event")) and k != queue}
                                event = world.event_defs[eid]
                                self.assertTrue(world.conditions(field(event, "trigger"), world.tag))
                                world.execute(field(event, "immediate"), world.tag)
                                self.assertNotIn("ywc_v03_kor_inline_reservation", state)
                                self.assertNotIn(queue, state)
                                self.assertEqual({k: state[k] for k in others}, others)
                                deliveries.append((arc["slug"], world.day, eid, candidate))
                                number = int(eid.rsplit(".", 1)[1])
                                key = choices[number]
                                if number == 1104 and "ywc_kor_revenue_review_paid" not in state:
                                    key = "pay_review"
                                choose(world, arc, event, key)
                        world.refresh(arc)
                self.assertEqual(len(deliveries[:9]), 9)
                self.assertEqual(Counter(r[0] for r in deliveries[:9]),
                                 Counter({a["slug"]: 3 for a in participants}))
                self.assertTrue(all(b[1] - a[1] >= 90 for a, b in zip(deliveries, deliveries[1:])))
                own = [r for r in deliveries if r[0] == COURT]
                self.assertEqual([r[2] for r in own], [f"ywc_kor.{n}" for n in range(1120, 1128)])
                self.assertEqual([r[3] for r in own], list(range(40, 48)))
                for slug in (FOUNDATION[0], REVENUE, COURT):
                    self.assertEqual(state[f"ywc_v03_kor_{slug}_outcome"], 1)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
