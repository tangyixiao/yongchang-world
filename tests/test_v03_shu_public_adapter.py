"""SHU public deliberation extends the pinned native v3 delivery contract."""
import copy
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import types
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from tools import v03_inline_delivery_adapter as adapter

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "8222a4cb1164c0d60ed5208044168c55b4e91650"
FOUNDATION = ("v03_shu_fiscal_register", "v03_shu_service_compact", "v03_shu_port_treasury")
PROVINCE = "v03_shu_provincial_contract"
PUBLIC = "v03_shu_public_deliberation"
JES = ("ywc_je_v03_shu_deliberation_eligibility", "ywc_je_v03_shu_deliberation_appeal_execution")
QUEUE = "ywc_shu_delib_pending_event"
RECEIPT = "ywc_shu_delib_last_event"


def frozen(path):
    return subprocess.run(["git", "show", BASELINE + ":" + path], cwd=ROOT,
                          check=True, capture_output=True).stdout.decode("utf-8-sig")


def bind_sources(arc):
    phases, records = [], []
    for index, journal in enumerate(arc["journals"]):
        phases.append({"journal": journal["id"],
                       "live_witness": "ywc_v03_shu_inline_live_public_" + ("eligibility" if index == 0 else "appeal_execution"),
                       **{target: hashlib.sha256(journal[source].encode()).hexdigest()
                          for target, source in (("source_script_sha256", "script"),
                                                 ("goal_sha256", "goal"), ("exit_sha256", "exit_conditions"))}})
        for source in adapter._kor_source_binding(journal["id"], journal["script"],
                                                   candidate_parser=adapter._shu_queue_candidates)["branches"]:
            native = adapter._branch_node(journal["script"], source)[0]
            operations = [{"key": node.key, "op": node.op,
                           "value": node.value if isinstance(node.value, str) else adapter.render_node(node, journal["script"])}
                          for node in adapter.children(native) if node.key not in {"limit", "trigger_event"}]
            records.append({"journal": journal["id"],
                            **{key: source[key] for key in ("branch_index", "statement_ordinal", "chain_index",
                                                           "branch_kind", "event", "chain_prior", "chain_sha256",
                                                           "candidates", "queue_exclusions")},
                            "branch_sha256": source["sha256"], "limit_sha256": source["limit_sha256"],
                            "source_ops": operations})
    arc["inline_delivery_adapter"] = {"schema": "v03.foundation_inline_adapter.v3",
                                       "live_phases": phases, "branches": records,
                                       "direct_adds": adapter._kor_direct_adds(arc)}


def synthetic_catalog():
    current = json.loads(frozen("data/content/v03/countries/shu.json"))
    arc = {"slug": PUBLIC, "era": "middle", "journals": [], "events": []}
    for jid, numbers in zip(JES, (range(1120, 1124), range(1124, 1128))):
        sends = []
        for number in numbers:
            sends.append(f"if = {{ limit = {{ var:{QUEUE} = {number} }} remove_variable = {QUEUE} "
                         f"trigger_event = {{ id = ywc_shu.{number} }} }}")
            arc["events"].append({"id": f"ywc_shu.{number}", "trigger": "{ always = yes }", "options": [],
                                  "immediate": "{ ywc_v03_mark_major_delivered = yes "
                                  f"set_variable = {{ name = ywc_v03_shu_event_dispatch value = {number} }} "
                                  f"set_variable = {{ name = {RECEIPT} value = {number} }} }}"})
        arc["journals"].append({"id": jid,
                                "script": "{ possible = { always = yes } immediate = {} "
                                "on_monthly_pulse = { effect = { " + " ".join(sends) + " } } }",
                                "goal": "{ var:synthetic_closed = 1 }",
                                "exit_conditions": "{ var:synthetic_withdrawn = 1 }"})
    bind_sources(arc)
    current["arcs"].append(arc)
    return current


@contextmanager
def reviewed_synthetic_pins(catalog):
    """Only this literal test fixture gets temporary pins; no production fallback."""
    arc = catalog["arcs"][-1]
    sources = {j["id"]: hashlib.sha256(j["script"].encode()).hexdigest() for j in arc["journals"]}
    immediates = {e["id"]: hashlib.sha256(e["immediate"].encode()).hexdigest() for e in arc["events"]}
    with patch.dict(adapter._SHU_PUBLIC_SOURCE_HASHES, sources, clear=True), \
            patch.dict(adapter._SHU_PUBLIC_IMMEDIATE_HASHES, immediates, clear=True):
        yield


class ShuPublicIsolatedAdapter(unittest.TestCase):
    """No current country/helper/generated reads while the source author runs."""

    def require_pin_api(self):
        self.assertTrue(hasattr(adapter, "_SHU_PUBLIC_SOURCE_HASHES"), "new source pin registry is absent")
        self.assertTrue(hasattr(adapter, "_SHU_PUBLIC_IMMEDIATE_HASHES"), "new immediate pin registry is absent")

    def test_native_body_has_exact_three_operations_and_owned_actual_id_receipt(self):
        self.assertTrue(hasattr(adapter, "_shu_public_native_receipt"), "strict public native body is absent")
        for number in range(1120, 1128):
            body = ("{ ywc_v03_mark_major_delivered = yes "
                    f"set_variable = {{ name = ywc_v03_shu_event_dispatch value = {number} }} "
                    f"set_variable = {{ name = {RECEIPT} value = {number} }} }}")
            event = {"id": f"ywc_shu.{number}", "immediate": body}
            self.assertEqual(adapter._shu_public_native_receipt(event), (RECEIPT, number))
            self.assertEqual(adapter._shu_expected_receipt(event["id"]), (RECEIPT, number))
            for wrong in (body.replace(RECEIPT, "ywc_shu_prov_last_event"),
                          body.replace(f"value = {number}", f"value = {number - 1119}"),
                          body.replace("= yes", "= no"), body.replace("set_variable", "change_variable"),
                          body[:-1] + "add_treasury = 1 }", body.replace("value =", "extra = 1 value ="),
                          "{ ywc_v03_mark_major_delivered = yes "
                          f"set_variable = {{ name = {RECEIPT} value = {number} }} "
                          f"set_variable = {{ name = ywc_v03_shu_event_dispatch value = {number} }} }}"):
                with self.subTest(number=number, wrong=wrong), self.assertRaises(ValueError):
                    adapter._shu_public_native_receipt({**event, "immediate": wrong})
        for bad in (None, 1120, "ywc_shu.1119", "ywc_shu.1128", "ywc_kor.1120"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                adapter._shu_public_native_receipt({"id": bad, "immediate": "{}"})

    def test_selector_appends_after_all_four_old_arcs_and_rejects_unknown_or_missing_middle(self):
        arcs = [{"slug": slug, "era": "foundation"} for slug in FOUNDATION]
        arcs += [{"slug": slug, "era": "middle"} for slug in (PROVINCE, PUBLIC)]
        for order in (arcs, list(reversed(arcs))):
            try:
                selected = adapter._shu_active_arcs({"arcs": order})
            except ValueError as exc:
                self.fail(f"the registered public arc must be selected: {exc}")
            self.assertEqual([a["slug"] for a in selected], [*FOUNDATION, PROVINCE, PUBLIC])
        bad_inputs = (arcs + [arcs[-1]], arcs + [{"slug": "v03_shu_unknown", "era": "middle"}],
                      [a for a in arcs if a["slug"] != PROVINCE],
                      [*arcs[:-1], {"slug": PUBLIC, "era": "late"}])
        for bad in bad_inputs:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                adapter._shu_active_arcs({"arcs": bad})

    def test_frozen_source_and_immediate_pins_cannot_be_replaced_by_rehashed_metadata(self):
        self.require_pin_api()
        current = synthetic_catalog()
        with reviewed_synthetic_pins(current):
            adapter.validate_inline_catalog(current)
            changed = copy.deepcopy(current)
            arc = changed["arcs"][-1]
            arc["journals"][0]["script"] = arc["journals"][0]["script"].replace("immediate = {}", "immediate = { add_treasury = 1 }")
            bind_sources(arc)
            with self.assertRaisesRegex(ValueError, "frozen native source"):
                adapter.validate_inline_catalog(changed)
            changed = copy.deepcopy(current)
            changed["arcs"][-1]["events"][0]["immediate"] += " "
            with self.assertRaisesRegex(ValueError, "frozen native immediate"):
                adapter.validate_inline_catalog(changed)
        # No synthetic pin escapes the context to authorize an unseen source.
        with self.assertRaises(ValueError):
            adapter.validate_inline_catalog(current)

    def test_rehashed_queue_aliases_wrong_partition_and_extra_native_effects_reject(self):
        self.require_pin_api()
        valid = synthetic_catalog()
        for fault in ("fiscal_queue", "province_queue", "presence", "partition", "body_extra"):
            current = copy.deepcopy(valid)
            arc = current["arcs"][-1]
            if fault in ("fiscal_queue", "province_queue"):
                queue = "ywc_shu_pending_event" if fault == "fiscal_queue" else "ywc_shu_prov_pending_event"
                for j in arc["journals"]:
                    j["script"] = j["script"].replace(QUEUE, queue)
            elif fault == "presence":
                arc["journals"][0]["script"] = arc["journals"][0]["script"].replace(
                    f"var:{QUEUE} = 1120", f"has_variable = {QUEUE}")
            elif fault == "partition":
                arc["journals"][0]["script"] = arc["journals"][0]["script"].replace("1123", "1124")
                arc["journals"][1]["script"] = arc["journals"][1]["script"].replace("1124", "1123")
            else:
                arc["events"][0]["immediate"] = arc["events"][0]["immediate"][:-1] + "add_treasury = 1 }"
            bind_sources(arc)
            with self.subTest(fault=fault), reviewed_synthetic_pins(current), self.assertRaises(ValueError):
                adapter.validate_inline_catalog(current)

    def test_synthetic_new_candidate_ack_requires_independent_receipt(self):
        from clausewitz_harness import PulseWorld
        self.require_pin_api()
        current = synthetic_catalog()
        with reviewed_synthetic_pins(current):
            rendered = adapter.render_inline_country_adapters(current)
        self.assertEqual(len(rendered["journal_scripts"]), 10)
        self.assertIn("ywc_v03_shu_inline_served_5", rendered["effects"])
        state = {"ywc_v03_shu_inline_reservation": 40, "ywc_v03_shu_inline_timer": 1,
                 "ywc_v03_shu_inline_reservation_epoch": 7, "ywc_v03_shu_inline_candidate_epoch_40": 7,
                 "ywc_v03_shu_inline_c40_delib_pending_event_present": 1,
                 "ywc_v03_shu_inline_c40_delib_pending_event_value": 1120,
                 "ywc_v03_shu_inline_live_public_eligibility": 1, "ywc_v03_shu_inline_round": 1,
                 "ywc_v03_shu_inline_callback_40": 1, "ywc_v03_shu_inline_callback_candidate_40": 40,
                 "ywc_v03_shu_inline_callback_epoch_40": 7, "ywc_v03_shu_inline_callback_queue_40": 1120,
                 "ywc_v03_shu_event_dispatch": 1120, QUEUE: 1120, RECEIPT: 0}
        world = PulseWorld(rendered["effects"], {"SHU": state})
        world.journals = [("SHU", [("type", "=", JES[0])])]
        self.assertTrue("ywc_v03_shu_inline_ack_40" in world.effects)
        before = copy.deepcopy(state)
        world.run("ywc_v03_shu_inline_ack_40", "SHU")
        self.assertEqual(state, before, "shared dispatch alone cannot ACK public's own native receipt")
        state[RECEIPT] = 1120
        world.run("ywc_v03_shu_inline_ack_40", "SHU")
        self.assertNotIn(QUEUE, state)
        self.assertNotIn("ywc_v03_shu_inline_reservation", state)

    def test_immutable_old_four_arc_render_stays_equal_to_head_adapter(self):
        catalog = json.loads(frozen("data/content/v03/countries/shu.json"))
        old = types.ModuleType("shu_public_frozen_adapter")
        sys.modules[old.__name__] = old
        try:
            exec(compile(frozen("tools/v03_inline_delivery_adapter.py"), old.__name__, "exec"), old.__dict__)
            self.assertEqual(adapter.render_inline_country_adapters(catalog), old.render_inline_country_adapters(catalog))
            for country in ("dmg", "kor", "nqg", "nmg", "mgl", "lan", "tib", "jhg"):
                with self.subTest(country=country):
                    other = json.loads(frozen(f"data/content/v03/countries/{country}.json"))
                    self.assertEqual(adapter.render_inline_country_adapters(other),
                                     old.render_inline_country_adapters(other))
        finally:
            sys.modules.pop(old.__name__, None)
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["branches"]) for a in catalog["arcs"]), 39)
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["direct_adds"]) for a in catalog["arcs"]), 1)


def current_catalog():
    return json.loads((ROOT / "data/content/v03/countries/shu.json").read_text("utf-8-sig"))


def capture_native_event(world, arc, wanted):
    """Stop before the actual generated immediate, retaining its reservation."""
    for _ in range(75):
        world.pulse(arc)
        if world.events:
            _, event_id = world.events.pop(0)
            if event_id != wanted:
                raise AssertionError(("unexpected_native_event", event_id, wanted))
            return world.event_defs[event_id]
        world.advance_months(1)
        world.elapsed_months += 1
    raise AssertionError(("missing_native_event", wanted))


PUBLIC_CHOICES = dict(zip(range(1120, 1128), (
    "court_consultation", "pay_register", "new_witness", "sign_budget",
    "register_public_appeal", "pay_review", "request_full", "close_full")))


class ShuPublicGeneratedAdapter(unittest.TestCase):
    """Actual source tests run only after the author's terminal/bind/gen gate."""

    def test_actual_inventory_preserves_four_arcs_and_appends_exact_eight_sources(self):
        current = current_catalog()
        active = adapter._shu_active_arcs(current)
        previous = json.loads(frozen("data/content/v03/countries/shu.json"))["arcs"]
        self.assertEqual(active[:-1], previous, "all four old arcs must remain exactly frozen")
        self.assertEqual([a["slug"] for a in active], [*FOUNDATION, PROVINCE, PUBLIC])
        self.assertEqual(sum(len(a["journals"]) for a in active[:-1]), 8)
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["branches"]) for a in active[:-1]), 39)
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["direct_adds"]) for a in active[:-1]), 1)
        arc = active[-1]
        self.assertEqual([j["id"] for j in arc["journals"]], list(JES))
        proofs = arc["inline_delivery_adapter"]["branches"]
        self.assertEqual([p["event"] for p in proofs], [f"ywc_shu.{n}" for n in range(1120, 1128)])
        self.assertEqual([sum(p["journal"] == jid for p in proofs) for jid in JES], [4, 4])
        self.assertEqual(arc["inline_delivery_adapter"]["direct_adds"], [])
        for number, proof in zip(range(1120, 1128), proofs):
            self.assertEqual(proof["candidates"], [
                {"queue": QUEUE, "kind": "normal", "mode": "exact", "value": number}])
        for event in arc["events"]:
            number = int(event["id"].rsplit(".", 1)[1])
            self.assertEqual(adapter._shu_public_native_receipt(event), (RECEIPT, number))
        adapter.validate_inline_catalog(current)
        rendered = adapter.render_inline_country_adapters(current)
        self.assertEqual(len(rendered["journal_scripts"]), 10)
        self.assertIn("ywc_v03_shu_inline_served_5", rendered["effects"])
        for candidate in range(40, 48):
            self.assertIn(f"ywc_v03_shu_inline_candidate_{candidate} =", rendered["triggers"])
        source = (ROOT / "yongchang_world/events/ywc_v03_country_shu_events.txt").read_text("utf-8-sig")
        self.assertEqual(set(re.findall(r"(?m)^(ywc_shu\.112[0-7])\s*=\s*\{", source)),
                         {f"ywc_shu.{n}" for n in range(1120, 1128)})

    def test_rehashed_actual_source_cannot_borrow_old_queues_even_with_new_pins(self):
        for queue in ("ywc_shu_pending_event", "ywc_shu_service_pending_event",
                      "ywc_shu_port_pending_event", "ywc_shu_prov_pending_event"):
            with self.subTest(queue=queue):
                current = current_catalog()
                arc = next(a for a in current["arcs"] if a["slug"] == PUBLIC)
                for journal in arc["journals"]:
                    journal["script"] = journal["script"].replace(QUEUE, queue)
                bind_sources(arc)
                # First immutable source pins reject mutable metadata rehashing.
                with self.assertRaisesRegex(ValueError, "frozen native source"):
                    adapter.validate_inline_catalog(current)
                # Even an explicit test-only re-pin cannot evade arc queue ownership.
                with reviewed_synthetic_pins(current), self.assertRaises(ValueError):
                    adapter.validate_inline_catalog(current)

    def test_all_eight_actual_native_receipts_ack_and_faults_stay_reserved(self):
        from shu_kor_strict_review_runtime import field
        from test_v03_shu_public_deliberation import new_world
        from test_v03_shu_provincial_contract import choose
        world = new_world()
        arc = next(a for a in world.cat["arcs"] if a["slug"] == PUBLIC)
        for number in range(1120, 1128):
            event = capture_native_event(world, arc, f"ywc_shu.{number}")
            candidate = number - 1080
            state = world.countries[world.tag]
            self.assertTrue(world.conditions(field(event, "trigger"), world.tag))
            self.assertEqual(state["ywc_v03_shu_inline_reservation"], candidate)
            self.assertEqual(state[QUEUE], number)
            for wrong in (0, number - 1):
                with self.subTest(number=number, wrong=wrong):
                    fault_world = copy.deepcopy(world)
                    native = copy.deepcopy(field(event, "immediate"))
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
                    corrupt(native)
                    self.assertEqual(len(changes), 1)
                    fault_world.execute(native, world.tag)
                    failed = fault_world.countries[world.tag]
                    self.assertIn("ywc_v03_major_event_cooldown", failed)
                    self.assertEqual(failed["ywc_v03_shu_event_dispatch"], number)
                    self.assertEqual(failed[RECEIPT], wrong)
                    fault_world.run(f"ywc_v03_shu_inline_ack_{candidate}", world.tag)
                    self.assertEqual(failed["ywc_v03_shu_inline_reservation"], candidate)
                    self.assertEqual(failed[QUEUE], number)
            world.execute(field(event, "immediate"), world.tag)
            self.assertEqual(state[RECEIPT], number)
            self.assertNotIn("ywc_v03_shu_inline_reservation", state)
            self.assertNotIn(QUEUE, state)
            choose(world, arc, event, PUBLIC_CHOICES[number])
        self.assertEqual(state["ywc_shu_delib_outcome"], 1)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))

    def test_public_province_and_fiscal_share_fair_native_turns_in_both_orders(self):
        from collections import Counter
        from shu_kor_strict_review_runtime import field, M1_PLAN
        from test_v03_shu_public_deliberation import new_world
        from test_v03_shu_provincial_contract import choose
        current = current_catalog()
        participants = [next(a for a in current["arcs"] if a["slug"] == slug)
                        for slug in (FOUNDATION[0], PROVINCE, PUBLIC)]
        mapping = {}
        for arc in adapter._shu_active_arcs(current):
            for proof in arc["inline_delivery_adapter"]["branches"]:
                for queue in proof["candidates"]:
                    mapping[len(mapping) + 1] = (arc["slug"], proof["event"], queue["queue"])
        choices = dict(M1_PLAN)
        choices.update({1100: "pilot_sichuan", 1101: "central_funding", 1102: "pay_relief_once",
                        1103: "establish_central", 1106: "settle_on_time", 1107: "close_established"})
        choices.update(PUBLIC_CHOICES)
        for order in (participants, list(reversed(participants))):
            with self.subTest(order=[a["slug"] for a in order]):
                world = new_world()
                state = world.countries[world.tag]
                # Current native staffing facts only; no old outcome/paid/queue seeds.
                for building in state["states"][0]["buildings"]:
                    if building["type"] == "building_government_administration":
                        building["occupancy"] = 1
                for arc in participants:
                    world.refresh(arc)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
                deliveries = []
                day = 0
                for _ in range(180):
                    # PulseWorld.advance_months is explicitly 30 days, unlike
                    # PartnerWorld's Gregorian calendar; elapsed_months is caller-owned.
                    world.advance_months(1)
                    world.elapsed_months += 1
                    day += 30
                    for arc in order:
                        for journal in arc["journals"]:
                            if journal["id"] not in world.active[world.tag]:
                                continue
                            world.execute(field(field(world.journal_defs[journal["id"]], "on_monthly_pulse"), "effect"), world.tag)
                            while world.events:
                                _, eid = world.events.pop(0)
                                candidate = int(state["ywc_v03_shu_inline_reservation"])
                                self.assertEqual(mapping[candidate][:2], (arc["slug"], eid))
                                queue = mapping[candidate][2]
                                others = {k: v for k, v in state.items() if k.startswith("ywc_shu_")
                                          and k.endswith(("pending_event", "notice_event")) and k != queue}
                                event = world.event_defs[eid]
                                self.assertTrue(world.conditions(field(event, "trigger"), world.tag))
                                world.execute(field(event, "immediate"), world.tag)
                                self.assertNotIn("ywc_v03_shu_inline_reservation", state)
                                self.assertNotIn(queue, state)
                                self.assertEqual({k: state[k] for k in others}, others)
                                deliveries.append((arc["slug"], day, eid, candidate))
                                number = int(eid.rsplit(".", 1)[1])
                                choose(world, arc, event, choices[number])
                        world.refresh(arc)
                self.assertEqual(len(deliveries[:9]), 9)
                self.assertEqual(Counter(r[0] for r in deliveries[:9]),
                                 Counter({a["slug"]: 3 for a in participants}))
                self.assertTrue(all(b[1] - a[1] >= 90 for a, b in zip(deliveries, deliveries[1:])))
                own = [r for r in deliveries if r[0] == PUBLIC]
                self.assertEqual([r[2] for r in own], [f"ywc_shu.{n}" for n in range(1120, 1128)])
                self.assertEqual([r[3] for r in own], list(range(40, 48)))
                for slug in (FOUNDATION[0], PROVINCE, PUBLIC):
                    self.assertEqual(state[f"ywc_v03_shu_{slug}_outcome"], 1)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
