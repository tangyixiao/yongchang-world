"""Strict synthetic isolation and actual SHU rural generated-source contracts."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from tools import v03_inline_delivery_adapter as adapter

BASELINE_REF = "39187884b0084fa29e9194507ee59fd1f26a2927"
COUNTRIES = ("dmg", "jhg", "kor", "lan", "mgl", "nmg", "nqg", "oir", "shu", "tib")
SLUG = "v03_shu_rural_workshop"
QUEUE = "ywc_shu_workshop_pending_event"
RECEIPT = "ywc_shu_workshop_last_event"
JOURNALS = ("ywc_je_v03_shu_workshop_ground", "ywc_je_v03_shu_workshop_yields")


def immutable_bytes(path):
    """An immutable Git object, never a working-tree country/helper/generated file."""
    return subprocess.check_output(["git", "show", f"{BASELINE_REF}:{path}"], cwd=Path(__file__).resolve().parents[1])


def baseline_catalogs():
    return {tag: json.loads(immutable_bytes(f"data/content/v03/countries/{tag}.json")) for tag in COUNTRIES}


def baseline_adapter():
    module = types.ModuleType("_shu_rural_immutable_adapter")
    sys.modules[module.__name__] = module
    exec(compile(immutable_bytes("tools/v03_inline_delivery_adapter.py"), "immutable_adapter.py", "exec"), module.__dict__)
    return module


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def immediate(number):
    return ("{ ywc_v03_mark_major_delivered = yes "
            f"set_variable = {{ name = ywc_v03_shu_event_dispatch value = {number} }} "
            f"set_variable = {{ name = {RECEIPT} value = {number} }} }}")


def synthetic_catalog():
    catalog = copy.deepcopy(baseline_catalogs()["shu"])
    arc = {"slug": SLUG, "era": "middle", "journals": [], "events": []}
    for number in range(1110, 1118):
        arc["events"].append({"id": f"ywc_shu.{number}", "trigger": "{ c:SHU ?= this }",
                              "immediate": immediate(number), "options": []})
    for jid, numbers in zip(JOURNALS, (range(1110, 1114), range(1114, 1118))):
        branches = []
        for number in numbers:
            kind = "if" if number == numbers.start else "else_if"
            branches.append(f"{kind} = {{ limit = {{ ywc_v03_can_deliver_major = yes var:{QUEUE} = {number} }} "
                            f"remove_variable = {QUEUE} trigger_event = {{ id = ywc_shu.{number} }} }}")
        arc["journals"].append({"id": jid,
            "script": "{ on_monthly_pulse = { effect = { " + " ".join(branches) + " } } }",
            "goal": "{ has_variable = synthetic_workshop_done }",
            "exit_conditions": "{ has_variable = synthetic_workshop_withdrawn }"})
    catalog["arcs"].append(arc)
    rebind_synthetic(arc)
    return catalog


def rebind_synthetic(arc):
    """Calculate real metadata from this test's literal source, with no production IO."""
    phases, records = [], []
    for journal in arc["journals"]:
        jid, script = journal["id"], journal["script"]
        phases.append({"journal": jid, "live_witness": "ywc_v03_shu_inline_live_" + jid,
                       "source_script_sha256": digest(script), "goal_sha256": digest(journal["goal"]),
                       "exit_sha256": digest(journal["exit_conditions"])})
        for source in adapter._kor_source_binding(jid, script, candidate_parser=adapter._shu_queue_candidates)["branches"]:
            record = {key: copy.deepcopy(source[key]) for key in (
                "branch_index", "statement_ordinal", "chain_index", "branch_kind", "event",
                "limit_sha256", "chain_prior", "chain_sha256", "candidates", "queue_exclusions")}
            record.update(journal=jid, branch_sha256=source["sha256"])
            native = adapter._branch_node(script, source)[0]
            record["source_ops"] = [{"key": node.key, "op": node.op,
                "value": node.value if isinstance(node.value, str) else adapter.render_node(node, script)}
                for node in adapter.children(native) if node.key not in {"limit", "trigger_event"}]
            records.append(record)
    arc["inline_delivery_adapter"] = {"schema": "v03.foundation_inline_adapter.v3",
                                       "live_phases": phases, "branches": records, "direct_adds": []}


def synthetic_pins(arc):
    return ({j["id"]: digest(j["script"]) for j in arc["journals"]},
            {event["id"]: digest(event["immediate"]) for event in arc["events"]})


class RuralAdapterIsolationTests(unittest.TestCase):
    def bind(self, catalog):
        source, immediates = synthetic_pins(catalog["arcs"][-1])
        self.enterContext(patch.dict(adapter._SHU_RURAL_SOURCE_HASHES, source, clear=True))
        self.enterContext(patch.dict(adapter._SHU_RURAL_IMMEDIATE_HASHES, immediates, clear=True))

    def assert_rejected(self, catalog, pattern=None):
        with self.assertRaisesRegex(ValueError, pattern or ".+"):
            adapter.validate_inline_catalog(catalog)

    def test_unbound_new_pins_fail_closed_and_known_five_remain_exact(self):
        catalog = synthetic_catalog()
        try:
            adapter._shu_active_arcs(catalog)
        except ValueError as exc:
            self.fail(f"registered sixth SHU arc rejected: {exc}")
        with patch.dict(adapter._SHU_RURAL_SOURCE_HASHES, {}, clear=True), \
                patch.dict(adapter._SHU_RURAL_IMMEDIATE_HASHES, {}, clear=True):
            self.assert_rejected(catalog, "frozen native source")
        old = baseline_catalogs()["shu"]
        adapter.validate_inline_catalog(old)  # Full known catalog before any bounded legacy projection.
        legacy = baseline_adapter()
        for count in (3, 4, 5):
            with self.subTest(registered_arcs=count):
                projection = copy.deepcopy(old)
                projection["arcs"] = projection["arcs"][:count]
                self.assertEqual(adapter.render_inline_country_adapters(projection), legacy.render_inline_country_adapters(projection))

    def test_sixth_arc_has_eight_exact_ack_receipts_and_other_nine_returns_unchanged(self):
        catalog = synthetic_catalog()
        self.bind(catalog)
        result = adapter.render_inline_country_adapters(catalog)
        self.assertEqual(sum(len(rows) for rows in result["inline_proofs"].values()), 55)
        self.assertEqual(len(result["journal_scripts"]), 12)
        self.assertEqual(len(result["live_witnesses"]), 12)
        self.assertEqual(set(re.findall(r"ywc_v03_shu_inline_served_(\d+)", result["effects"] + result["triggers"])), set("123456"))
        effects_source = "{ " + result["effects"] + " }"
        effects_nodes = adapter.parse_block(effects_source)
        for candidate, number in zip(range(48, 56), range(1110, 1118)):
            event = f"ywc_shu.{number}"
            ack = f"ywc_v03_shu_inline_ack_{candidate}"
            self.assertIn(f"ywc_v03_shu_inline_callback_{candidate}", result["ack_hooks"][event])
            node = next(node for node in effects_nodes if node.key == ack)
            body = adapter.render_node(node, effects_source)
            self.assertIn(f"has_variable = {RECEIPT}", body)
            self.assertIn(f"var:{RECEIPT} = {number}", body)
            self.assertIn(f"var:ywc_v03_shu_inline_reservation = {candidate}", body)
        # Execute the generated ACK literally: shared dispatch alone must not consume.
        from clausewitz_harness import PulseWorld
        prefix = "ywc_v03_shu_inline"
        for candidate, number in zip(range(48, 56), range(1110, 1118)):
            phase_index = (number - 1110) // 4
            witness = catalog["arcs"][-1]["inline_delivery_adapter"]["live_phases"][phase_index]["live_witness"]
            state = {f"{prefix}_reservation": candidate, f"{prefix}_timer": 1,
                     f"{prefix}_reservation_epoch": 7, f"{prefix}_candidate_epoch_{candidate}": 7,
                     adapter._queue_snapshot_name(candidate, QUEUE, "present", prefix): 1,
                     adapter._queue_snapshot_name(candidate, QUEUE, "value", prefix): number,
                     witness: 1, f"{prefix}_round": 1, f"{prefix}_callback_{candidate}": 1,
                     f"{prefix}_callback_candidate_{candidate}": candidate,
                     f"{prefix}_callback_epoch_{candidate}": 7,
                     f"{prefix}_callback_queue_{candidate}": number,
                     "ywc_v03_shu_event_dispatch": number, QUEUE: number,
                     "ywc_shu_delib_pending_event": 1120}
            for wrong in (None, 0, number - 1109, number + 1):
                trial = copy.deepcopy(state)
                if wrong is not None:
                    trial[RECEIPT] = wrong
                before = copy.deepcopy(trial)
                world = PulseWorld(result["effects"], {"SHU": trial})
                world.journals = [("SHU", [("type", "=", JOURNALS[phase_index])])]
                world.run(f"{prefix}_ack_{candidate}", "SHU")
                self.assertEqual(trial, before)
            state[RECEIPT] = number
            world = PulseWorld(result["effects"], {"SHU": state})
            world.journals = [("SHU", [("type", "=", JOURNALS[phase_index])])]
            world.run(f"{prefix}_ack_{candidate}", "SHU")
            self.assertNotIn(QUEUE, state)
            self.assertNotIn(f"{prefix}_reservation", state)
            self.assertEqual(state["ywc_shu_delib_pending_event"], 1120)
        legacy = baseline_adapter()
        for tag, old in baseline_catalogs().items():
            if tag == "shu":
                continue
            with self.subTest(country=tag):
                if tag == "oir":
                    # The immutable old adapter does not register OIR at all.
                    with self.assertRaises(ValueError) as old_error:
                        legacy.render_inline_country_adapters(old)
                    with self.assertRaises(ValueError) as new_error:
                        adapter.render_inline_country_adapters(old)
                    self.assertEqual(str(new_error.exception), str(old_error.exception))
                else:
                    self.assertEqual(adapter.render_inline_country_adapters(old), legacy.render_inline_country_adapters(old))

    def test_only_registered_slug_and_exact_own_queue_are_admitted(self):
        catalog = synthetic_catalog()
        self.bind(catalog)
        for alias in ("v03_shu_workshops", "v03_shu_rural_workshops", "v03_unknown"):
            bad = copy.deepcopy(catalog)
            bad["arcs"][-1]["slug"] = alias
            self.assert_rejected(bad, "unregistered")
        for queue in ("ywc_shu_delib_pending_event", "ywc_shu_other_pending_event", "ywc_kor_workshop_pending_event"):
            with self.subTest(queue=queue):
                bad = copy.deepcopy(catalog)
                for journal in bad["arcs"][-1]["journals"]:
                    journal["script"] = journal["script"].replace(QUEUE, queue)
                rebind_synthetic(bad["arcs"][-1])
                with patch.dict(adapter._SHU_RURAL_SOURCE_HASHES, synthetic_pins(bad["arcs"][-1])[0], clear=True):
                    self.assert_rejected(bad)
        for removed in (3, 4):
            bad = copy.deepcopy(catalog)
            del bad["arcs"][removed]
            self.assert_rejected(bad, "preserve")
        for limit in (f"has_variable = {QUEUE}", f"var:{QUEUE} = 1111"):
            bad = copy.deepcopy(catalog)
            journal = bad["arcs"][-1]["journals"][0]
            journal["script"] = journal["script"].replace(f"var:{QUEUE} = 1110", limit)
            rebind_synthetic(bad["arcs"][-1])
            with patch.dict(adapter._SHU_RURAL_SOURCE_HASHES, synthetic_pins(bad["arcs"][-1])[0], clear=True):
                self.assert_rejected(bad)

    def test_three_native_nodes_require_actual_event_id_and_exact_names_order(self):
        catalog = synthetic_catalog()
        self.bind(catalog)
        valid = catalog["arcs"][-1]["events"][0]["immediate"]
        variants = (
            valid.replace(f"name = {RECEIPT} value = 1110", f"name = {RECEIPT} value = 1"),
            valid.replace(RECEIPT, "ywc_shu_delib_last_event"),
            valid.replace("name = ywc_v03_shu_event_dispatch value = 1110", "name = ywc_v03_shu_event_dispatch value = 1"),
            valid.replace("ywc_v03_mark_major_delivered = yes", "ywc_v03_mark_major_delivered = no"),
            valid[:-1] + " set_variable = { name = extra_node value = 1 } }",
            "{ " + valid[valid.index("set_variable"): -1] + " ywc_v03_mark_major_delivered = yes }",
        )
        for source in variants:
            with self.subTest(immediate=source):
                bad = copy.deepcopy(catalog)
                bad["arcs"][-1]["events"][0]["immediate"] = source
                # Re-pin mutated synthetic text so the structural receipt check is exercised.
                with patch.dict(adapter._SHU_RURAL_IMMEDIATE_HASHES, synthetic_pins(bad["arcs"][-1])[1], clear=True):
                    self.assert_rejected(bad, "native immediate")

    def test_source_phase_and_direct_add_proofs_cannot_be_self_rebound(self):
        catalog = synthetic_catalog()
        self.bind(catalog)
        bad = copy.deepcopy(catalog)
        bad["arcs"][-1]["journals"][0]["script"] += " # metadata cannot authorize changed source"
        rebind_synthetic(bad["arcs"][-1])
        self.assert_rejected(bad, "frozen native source")
        mutations = (
            lambda arc: arc["inline_delivery_adapter"]["live_phases"][0].update(goal_sha256="0" * 64),
            lambda arc: arc["inline_delivery_adapter"]["live_phases"].reverse(),
            lambda arc: arc["inline_delivery_adapter"]["live_phases"][1].update(live_witness=arc["inline_delivery_adapter"]["live_phases"][0]["live_witness"]),
            lambda arc: arc["inline_delivery_adapter"]["branches"][0].update(source_ops=[]),
            lambda arc: arc["inline_delivery_adapter"]["direct_adds"].append({}),
        )
        for mutation in mutations:
            bad = copy.deepcopy(catalog)
            mutation(bad["arcs"][-1])
            self.assert_rejected(bad)
        bad = copy.deepcopy(catalog)
        arc = bad["arcs"][-1]
        arc["events"][0]["options"] = [{"key": "forbidden_direct_add",
            "effect": f"{{ add_journal_entry = {{ type = {JOURNALS[1]} }} }}"}]
        arc["inline_delivery_adapter"]["direct_adds"] = adapter._kor_direct_adds(arc)
        self.assert_rejected(bad, "direct-add caller/target baseline drift")

    def test_eight_events_eight_sites_and_four_four_phase_partition_are_exact(self):
        catalog = synthetic_catalog()
        self.bind(catalog)
        mutations = (
            lambda arc: arc["events"].pop(),
            lambda arc: arc["events"].append(copy.deepcopy(arc["events"][0])),
            lambda arc: arc["inline_delivery_adapter"]["branches"].pop(),
            lambda arc: arc["inline_delivery_adapter"]["branches"].append(copy.deepcopy(arc["inline_delivery_adapter"]["branches"][0])),
            lambda arc: arc["inline_delivery_adapter"]["branches"][3].update(journal=JOURNALS[1]),
            lambda arc: arc["journals"].reverse(),
        )
        for mutation in mutations:
            bad = copy.deepcopy(catalog)
            mutation(bad["arcs"][-1])
            self.assert_rejected(bad)


ROOT = Path(__file__).resolve().parents[1]
OLD_FISCAL = "v03_shu_fiscal_register"
OLD_PROVINCE = "v03_shu_provincial_contract"
RURAL_CHOICES = dict(zip(range(1110, 1118), (
    "rural_processing", "pay_admin", "new_witness", "sign_responsibility",
    "record_rural_duties", "pay_survey", "request_full", "close_full")))


def current_catalog():
    return json.loads((ROOT / "data/content/v03/countries/shu.json").read_text("utf-8-sig"))


def capture_actual_event(world, arc, number):
    """Stop at a real queued callback before its generated native immediate."""
    from test_v03_shu_rural_workshop import month
    wanted = f"ywc_shu.{number}"
    for _ in range(120):
        world.pulse(arc)
        if world.events:
            tag, event_id = world.events.pop(0)
            assert (tag, event_id) == (world.tag, wanted), ("unexpected_native_event", event_id, wanted)
            return world.event_defs[event_id]
        month(world, arc)
    raise AssertionError(("missing_actual_callback", wanted, world.trace[-8:]))


def fault_native_receipt(nodes, wrong):
    """Fault one actual generated immediate in memory; never seed business progress."""
    from test_v03_shu_provincial_contract import field
    changes = []

    def visit(items):
        result = []
        for key, op, value in items:
            if key == "set_variable" and isinstance(value, list) and field(value, "name") == RECEIPT:
                changes.append(1)
                if wrong is None:
                    continue
                value = [(child, comparison, str(wrong) if child == "value" else raw)
                         for child, comparison, raw in value]
            elif isinstance(value, list):
                value = visit(value)
            result.append((key, op, value))
        return result

    result = visit(copy.deepcopy(nodes))
    assert len(changes) == 1, ("expected_exactly_one_actual_native_receipt", changes)
    return result


class RuralActualGeneratedAdapterTests(unittest.TestCase):
    """Run only after root's source/bind/gen gate and business BINDING_READY."""

    def test_actual_inventory_pins_generated_outputs_and_all_five_old_arcs(self):
        catalog = current_catalog()
        adapter.validate_inline_catalog(catalog)
        active = adapter._shu_active_arcs(catalog)
        old = baseline_catalogs()["shu"]
        self.assertEqual(active[:-1], old["arcs"])
        arc = active[-1]
        self.assertEqual(arc["slug"], SLUG)
        self.assertEqual([j["id"] for j in arc["journals"]], list(JOURNALS))
        self.assertEqual({j["id"]: digest(j["script"]) for j in arc["journals"]}, adapter._SHU_RURAL_SOURCE_HASHES)
        self.assertEqual({e["id"]: digest(e["immediate"]) for e in arc["events"]}, adapter._SHU_RURAL_IMMEDIATE_HASHES)
        proofs = arc["inline_delivery_adapter"]["branches"]
        self.assertEqual([p["event"] for p in proofs], [f"ywc_shu.{n}" for n in range(1110, 1118)])
        self.assertEqual([sum(p["journal"] == jid for p in proofs) for jid in JOURNALS], [4, 4])
        self.assertEqual(arc["inline_delivery_adapter"]["direct_adds"], [])
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["direct_adds"]) for a in active), 1)
        for event, proof in zip(arc["events"], proofs):
            number = int(event["id"].rsplit(".", 1)[1])
            self.assertEqual(adapter._shu_rural_native_receipt(event), (RECEIPT, number))
            self.assertEqual(len(adapter.parse_block(event["immediate"])), 3)
            self.assertEqual(proof["candidates"], [{"queue": QUEUE, "kind": "normal", "mode": "exact", "value": number}])
        rendered = adapter.render_inline_country_adapters(catalog)
        self.assertEqual(sum(map(len, rendered["inline_proofs"].values())), 55)
        self.assertEqual(len(rendered["journal_scripts"]), 12)
        self.assertEqual(len(rendered["live_witnesses"]), 12)
        self.assertIn("ywc_v03_shu_inline_served_6", rendered["effects"])
        for candidate in range(48, 56):
            self.assertIn(f"ywc_v03_shu_inline_candidate_{candidate} =", rendered["triggers"])
        for kind in ("effects", "triggers"):
            generated = (ROOT / f"yongchang_world/common/scripted_{kind}/ywc_v03_delivery_shu_{kind}.txt").read_text("utf-8-sig")
            self.assertEqual(generated, f"# Generated SHU inline delivery scheduler scripted {kind}.\n\n" + rendered[kind])
        generated_events = (ROOT / "yongchang_world/events/ywc_v03_country_shu_events.txt").read_text("utf-8-sig")
        self.assertEqual(set(re.findall(r"(?m)^(ywc_shu\.111[0-7])\s*=\s*\{", generated_events)),
                         {f"ywc_shu.{n}" for n in range(1110, 1118)})

    def test_actual_source_rehash_cannot_borrow_a_foreign_arc_queue(self):
        for queue in ("ywc_shu_pending_event", "ywc_shu_service_pending_event",
                      "ywc_shu_port_pending_event", "ywc_shu_prov_pending_event",
                      "ywc_shu_delib_pending_event", "ywc_shu_unknown_pending_event"):
            with self.subTest(queue=queue):
                catalog = current_catalog()
                arc = next(a for a in catalog["arcs"] if a["slug"] == SLUG)
                for journal in arc["journals"]:
                    journal["script"] = journal["script"].replace(QUEUE, queue)
                rebind_synthetic(arc)
                with self.assertRaisesRegex(ValueError, "frozen native source"):
                    adapter.validate_inline_catalog(catalog)
                # Structural ownership must still reject a consciously re-pinned test copy.
                with patch.dict(adapter._SHU_RURAL_SOURCE_HASHES, synthetic_pins(arc)[0], clear=True), \
                        self.assertRaises(ValueError):
                    adapter.validate_inline_catalog(catalog)

    def test_all_eight_actual_callbacks_ack_only_their_own_actual_id_receipt(self):
        from test_v03_shu_rural_workshop import new_world, workshop_arc, month, choose, field
        world = new_world()
        arc = workshop_arc(world.cat)
        for number in range(1110, 1118):
            if number == 1115:
                month(world, arc, 6)
            event = capture_actual_event(world, arc, number)
            candidate = number - 1062
            state = world.countries[world.tag]
            self.assertTrue(world.conditions(field(event, "trigger"), world.tag))
            self.assertEqual(state["ywc_v03_shu_inline_reservation"], candidate)
            self.assertEqual(state[QUEUE], number)
            for wrong in (None, 0, number - 1109, number + 1):
                with self.subTest(event=number, receipt=wrong):
                    fault_world = copy.deepcopy(world)
                    if wrong is None:
                        fault_world.countries[world.tag].pop(RECEIPT, None)
                    native = fault_native_receipt(field(event, "immediate"), wrong)
                    fault_world.execute(native, world.tag)
                    failed = fault_world.countries[world.tag]
                    self.assertIn("ywc_v03_major_event_cooldown", failed)
                    self.assertEqual(failed["ywc_v03_shu_event_dispatch"], number)
                    if wrong is None:
                        self.assertNotIn(RECEIPT, failed)
                    else:
                        self.assertEqual(failed[RECEIPT], wrong)
                    fault_world.run(f"ywc_v03_shu_inline_ack_{candidate}", world.tag)
                    self.assertEqual(failed["ywc_v03_shu_inline_reservation"], candidate)
                    self.assertEqual(failed[QUEUE], number)
            world.execute(field(event, "immediate"), world.tag)
            self.assertEqual(state[RECEIPT], number)
            self.assertNotIn("ywc_v03_shu_inline_reservation", state)
            self.assertNotIn(QUEUE, state)
            choose(world, arc, event, RURAL_CHOICES[number])
        self.assertEqual(state["ywc_shu_workshop_outcome"], 1)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))

    def test_actual_rural_province_and_fiscal_share_fair_native_turns_in_both_orders(self):
        from collections import Counter
        from shu_kor_strict_review_runtime import M1_PLAN
        from test_v03_shu_rural_workshop import new_world, choose, field
        from test_v03_shu_content import shu_monthly_effect
        catalog = current_catalog()
        participants = [next(a for a in catalog["arcs"] if a["slug"] == slug)
                        for slug in (OLD_FISCAL, OLD_PROVINCE, SLUG)]
        mapping = {}
        for arc in adapter._shu_active_arcs(catalog):
            for proof in arc["inline_delivery_adapter"]["branches"]:
                for queue in proof["candidates"]:
                    mapping[len(mapping) + 1] = (arc["slug"], proof["event"], queue["queue"])
        choices = dict(M1_PLAN)
        choices.update({1100: "pilot_sichuan", 1101: "central_funding", 1102: "pay_relief_once",
                        1103: "establish_central", 1106: "settle_on_time", 1107: "close_established"})
        choices.update(RURAL_CHOICES)
        for order in (participants, list(reversed(participants))):
            with self.subTest(order=[a["slug"] for a in order]):
                world = new_world()
                state = world.countries[world.tag]
                # Ordinary current staffing only; no old history, queue or paid markers.
                for building in state["states"][0]["buildings"]:
                    if building["type"] == "building_government_administration":
                        building["occupancy"] = 1
                for arc in participants:
                    world.refresh(arc)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
                deliveries = []
                for calendar_month in range(1, 181):
                    before = world.elapsed_months
                    world.advance_months(1)
                    if world.elapsed_months == before:
                        world.elapsed_months += 1
                    self.assertEqual(world.elapsed_months, before + 1)
                    world.execute(shu_monthly_effect(), world.tag)
                    for arc in order:
                        for journal in arc["journals"]:
                            if journal["id"] not in world.active[world.tag]:
                                continue
                            native_pulse = field(field(world.journal_defs[journal["id"]], "on_monthly_pulse"), "effect")
                            world.execute(native_pulse, world.tag)
                            while world.events:
                                _, event_id = world.events.pop(0)
                                candidate = int(state["ywc_v03_shu_inline_reservation"])
                                self.assertEqual(mapping[candidate][:2], (arc["slug"], event_id))
                                queue = mapping[candidate][2]
                                others = {k: v for k, v in state.items() if k.startswith("ywc_shu_")
                                          and k.endswith(("pending_event", "notice_event")) and k != queue}
                                event = world.event_defs[event_id]
                                self.assertTrue(world.conditions(field(event, "trigger"), world.tag))
                                world.execute(field(event, "immediate"), world.tag)
                                self.assertNotIn("ywc_v03_shu_inline_reservation", state)
                                self.assertNotIn(queue, state)
                                self.assertEqual({k: state[k] for k in others}, others)
                                deliveries.append((arc["slug"], calendar_month * 30, event_id, candidate))
                                choose(world, arc, event, choices[int(event_id.rsplit(".", 1)[1])])
                        world.refresh(arc)
                    if all(state.get(f"ywc_v03_shu_{a['slug']}_settled") == 1 for a in participants):
                        break
                self.assertEqual(len(deliveries[:9]), 9)
                self.assertEqual(Counter(row[0] for row in deliveries[:9]), Counter({a["slug"]: 3 for a in participants}))
                self.assertTrue(all(b[1] - a[1] >= 90 for a, b in zip(deliveries, deliveries[1:])))
                rural = [row for row in deliveries if row[0] == SLUG]
                self.assertEqual([row[2] for row in rural], [f"ywc_shu.{n}" for n in range(1110, 1118)])
                self.assertEqual([row[3] for row in rural], list(range(48, 56)))
                for slug in (OLD_FISCAL, OLD_PROVINCE, SLUG):
                    self.assertEqual(state[f"ywc_v03_shu_{slug}_outcome"], 1)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
