"""KOR revenue extends v2 without changing any old source or ACK contract."""
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unittest

from tools import v03_inline_delivery_adapter as adapter

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "9980153ba0edb9c48f141df84c11b2f530ab39b6"
FOUNDATION = ("v03_kor_military_accounts", "v03_kor_school_factions", "v03_kor_controlled_ports")
REVENUE = "v03_kor_provincial_revenue"
JES = ("ywc_je_v03_kor_provincial_revenue_settlement", "ywc_je_v03_kor_provincial_revenue_review")
RECEIPT = "ywc_v03_kor_v03_kor_provincial_revenue_last_event"
QUEUE = "ywc_kor_revenue_pending_event"


def frozen_catalog():
    data = subprocess.run(["git", "show", BASELINE + ":data/content/v03/countries/kor.json"],
                          cwd=ROOT, check=True, capture_output=True).stdout
    return json.loads(data.decode("utf-8-sig"))


def bind_sources(arc):
    phases, records = [], []
    for index, journal in enumerate(arc["journals"]):
        phases.append({"journal": journal["id"],
                       "live_witness": "ywc_v03_kor_inline_live_revenue_" + ("settlement" if index == 0 else "review"),
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
    current = frozen_catalog()
    arc = {"slug": REVENUE, "era": "middle", "journals": [], "events": []}
    for jid, numbers in zip(JES, (range(1100, 1104), range(1104, 1108))):
        sends = []
        for number in numbers:
            sends.append(f"if = {{ limit = {{ var:{QUEUE} = {number} }} "
                         f"remove_variable = {QUEUE} trigger_event = {{ id = ywc_kor.{number} }} }}")
            arc["events"].append({"id": f"ywc_kor.{number}", "trigger": "{ always = yes }", "options": [],
                                  "immediate": "{ ywc_v03_mark_major_delivered = yes "
                                  f"set_variable = {{ name = {RECEIPT} value = {number - 1099} }} }}"})
        arc["journals"].append({"id": jid,
                                "script": "{ possible = { always = yes } immediate = {} "
                                "on_monthly_pulse = { effect = { " + " ".join(sends) + " } } }",
                                "goal": "{ var:synthetic_closed = 1 }",
                                "exit_conditions": "{ var:synthetic_withdrawn = 1 }"})
    bind_sources(arc)
    current["arcs"].append(arc)
    return current


class KorRevenueIsolatedAdapter(unittest.TestCase):
    """Only literals and immutable baseline sources; no current KOR file reads."""

    def test_native_body_requires_the_owned_ordered_ordinal_receipt(self):
        self.assertTrue(hasattr(adapter, "_kor_revenue_native_receipt"), "missing strict revenue native body")
        receipt = adapter._kor_revenue_native_receipt
        for number, ordinal in zip(range(1100, 1108), range(1, 9)):
            text = ("{ ywc_v03_mark_major_delivered = yes "
                    f"set_variable = {{ name = {RECEIPT} value = {ordinal} }} }}")
            event = {"id": f"ywc_kor.{number}", "immediate": text}
            self.assertEqual(receipt(event), (RECEIPT, ordinal))
            for wrong in (text.replace(RECEIPT, "ywc_v03_kor_v03_kor_school_factions_last_event"),
                          text.replace(RECEIPT, "ywc_v03_kor_v03_kor_military_accounts_last_event"),
                          text.replace(f"value = {ordinal}", f"value = {number}"),
                          text.replace(f"value = {ordinal}", "value = 0"),
                          text.replace("= yes", "= no"), text.replace("set_variable", "change_variable"),
                          text.replace("value =", "extra = 1 value ="), text[:-1] + "add_treasury = 1 }",
                          "{ set_variable = { name = " + RECEIPT + f" value = {ordinal} "
                          "} ywc_v03_mark_major_delivered = yes }"):
                with self.subTest(number=number, wrong=wrong), self.assertRaises(ValueError):
                    receipt({**event, "immediate": wrong})
        for bad in (None, 1100, "ywc_kor.1099", "ywc_kor.1108", "ywc_dmg.1100"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                receipt({"id": bad, "immediate": "{}"})

    def test_known_optional_middle_selector_retains_fixed_three_arc_order(self):
        self.assertTrue(hasattr(adapter, "_kor_active_arcs"), "KOR middle selector is missing")
        arcs = [{"slug": slug, "era": "foundation"} for slug in FOUNDATION]
        arcs.append({"slug": REVENUE, "era": "middle"})
        for order in (arcs, list(reversed(arcs))):
            self.assertEqual([a["slug"] for a in adapter._kor_active_arcs({"arcs": order})],
                             [*FOUNDATION, REVENUE])
        self.assertEqual([a["slug"] for a in adapter._kor_active_arcs({"arcs": arcs[:-1]})], list(FOUNDATION))
        for bad in (arcs + [arcs[-1]], arcs + [{"slug": "v03_kor_unknown", "era": "middle"}],
                    [*arcs[:-1], {"slug": REVENUE, "era": "late"}], arcs[1:]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                adapter._kor_active_arcs({"arcs": bad})

    def test_rehashed_queue_phase_chain_and_direct_add_mutants_fail_closed(self):
        valid = synthetic_catalog()
        adapter.validate_inline_catalog(valid)
        for kind in ("military", "school", "ports", "presence", "partition", "order", "prior", "direct_add"):
            current = copy.deepcopy(valid)
            arc = current["arcs"][-1]
            if kind in ("military", "school", "ports", "presence"):
                replacement = {"military": "ywc_kor_pending_event", "school": "ywc_kor_school_pending_event",
                               "ports": "ywc_kor_ports_pending_event"}.get(kind, QUEUE)
                for journal in arc["journals"]:
                    journal["script"] = journal["script"].replace(QUEUE, replacement)
                if kind == "presence":
                    arc["journals"][0]["script"] = arc["journals"][0]["script"].replace(
                        f"var:{QUEUE} = 1100", f"has_variable = {QUEUE}")
            elif kind == "partition":
                arc["journals"][0]["script"] = arc["journals"][0]["script"].replace("1103", "1104")
                arc["journals"][1]["script"] = arc["journals"][1]["script"].replace("1104", "1103")
            elif kind == "order":
                arc["journals"].reverse()
            bind_sources(arc)
            if kind == "prior":
                arc["inline_delivery_adapter"]["branches"][0]["chain_prior"] = [{"ordinal": 0}]
            elif kind == "direct_add":
                arc["events"][0]["options"] = [{"key": "handoff", "effect":
                    "{ add_journal_entry = { type = " + JES[1] + " } }"}]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                adapter.validate_inline_catalog(current)

    def test_render_registers_all_eight_sources_and_exact_receipts_in_ack(self):
        current = synthetic_catalog()
        rendered = adapter.render_inline_country_adapters(current)
        self.assertEqual(len(rendered["journal_scripts"]), 8, "middle sources must reach the renderer")
        self.assertIn("ywc_v03_kor_inline_served_4", rendered["effects"])
        for candidate, value in zip(range(32, 40), range(1, 9)):
            self.assertIn(f"ywc_v03_kor_inline_candidate_{candidate} =", rendered["triggers"])
            definitions = adapter.parse_block("{ " + rendered["effects"] + " }")
            ack = next(node for node in definitions if node.key == f"ywc_v03_kor_inline_ack_{candidate}")
            nodes = list(adapter._walk(ack.value))
            self.assertTrue(any(n.key == "has_variable" and n.value == RECEIPT for n in nodes))
            self.assertTrue(any(n.key == "var:" + RECEIPT and n.value == str(value) for n in nodes))
        reversed_catalog = copy.deepcopy(current)
        reversed_catalog["arcs"].reverse()
        self.assertEqual(adapter.render_inline_country_adapters(reversed_catalog), rendered)

    def test_synthetic_ack_rejects_bad_receipt_with_all_other_callback_proofs_present(self):
        from clausewitz_harness import PulseWorld
        rendered = adapter.render_inline_country_adapters(synthetic_catalog())
        state = {"ywc_v03_kor_inline_reservation": 32, "ywc_v03_kor_inline_timer": 1,
                 "ywc_v03_kor_inline_reservation_epoch": 7, "ywc_v03_kor_inline_candidate_epoch_32": 7,
                 "ywc_v03_kor_inline_c32_revenue_pending_event_present": 1,
                 "ywc_v03_kor_inline_c32_revenue_pending_event_value": 1100,
                 "ywc_v03_kor_inline_live_revenue_settlement": 1, "ywc_v03_kor_inline_round": 1,
                 "ywc_v03_kor_inline_callback_32": 1, "ywc_v03_kor_inline_callback_candidate_32": 32,
                 "ywc_v03_kor_inline_callback_epoch_32": 7, "ywc_v03_kor_inline_callback_queue_32": 1100,
                 QUEUE: 1100, RECEIPT: 0}
        world = PulseWorld(rendered["effects"], {"KOR": state})
        world.journals = [("KOR", [("type", "=", JES[0])])]
        self.assertTrue("ywc_v03_kor_inline_ack_32" in world.effects, "new native ACK must be registered")
        before = copy.deepcopy(state)
        world.run("ywc_v03_kor_inline_ack_32", "KOR")
        self.assertEqual(state, before, "other valid callback proof cannot substitute for native receipt")
        state[RECEIPT] = 1
        world.run("ywc_v03_kor_inline_ack_32", "KOR")
        self.assertNotIn(QUEUE, state)
        self.assertNotIn("ywc_v03_kor_inline_reservation", state)
        self.assertEqual(state["ywc_v03_kor_inline_served_4"], 1)


def choose_revenue_progress(world, arc, event, number):
    """Explicit native keys, including the paid-then-submit review interaction."""
    from test_v03_shu_provincial_contract import choose
    state = world.countries[world.tag]
    if number == 1104 and "ywc_kor_revenue_review_paid" not in state:
        choose(world, arc, event, "pay_review")
        assert state["ywc_kor_revenue_review_paid"] == 1
        assert state["ywc_kor_revenue_stage"] == 1104
        return
    choices = {1100: "written_shares", 1101: "pay_charter", 1102: "settle_reviewer",
               1103: "sign", 1104: "submit", 1105: "review_responsibility",
               1106: "verify", 1107: "request_full"}
    choose(world, arc, event, choices[number])
    assert state.get("ywc_kor_revenue_mode") == 1 and state.get("ywc_kor_revenue_target") == 1
    if number == 1107:
        assert state.get("ywc_kor_revenue_outcome") == 1
    else:
        assert state.get("ywc_kor_revenue_stage") == number + 1, (number, state.get("ywc_kor_revenue_stage"))


class KorRevenueGeneratedAdapter(unittest.TestCase):
    """Deferred until root confirms source, v2 metadata and generation are final."""

    def test_generated_inventory_preserves_old_three_arcs_and_appends_eight_candidates(self):
        source = (ROOT / "yongchang_world/events/ywc_v03_country_kor_events.txt").read_text("utf-8-sig")
        self.assertEqual(set(re.findall(r"(?m)^(ywc_kor\.110[0-7])\s*=\s*\{", source)),
                         {f"ywc_kor.{n}" for n in range(1100, 1108)})
        current = json.loads((ROOT / "data/content/v03/countries/kor.json").read_text("utf-8-sig"))
        active = adapter._kor_active_arcs(current)
        previous = frozen_catalog()["arcs"]
        projected = copy.deepcopy(active[:-1])
        # Approved withdrawal fix: precisely two goal leaves and their phase
        # goal hashes differ; all other old content and source proofs are equal.
        exceptions = (
            ("ywc_je_v03_kor_military_audit",
             "{ OR = { has_variable = ywc_kor_review_complete has_variable = ywc_kor_outcome_withdrawn_breach } }",
             "{ AND = { OR = { has_variable = ywc_kor_review_complete has_variable = ywc_kor_outcome_withdrawn_breach } NOT = { has_variable = ywc_kor_arc_abandoned } } }",
             "f0b47ff01fb6904386cff6f8b7e7f90c556025d3940f4c51c35567bd1ef76148",
             "3f583043a1a4a423b33865261062d366d93bd24c7985e4f4f7cafd53e077f579"),
            ("ywc_je_v03_kor_service_settlement",
             "{ has_variable = ywc_kor_any_outcome }",
             "{ AND = { has_variable = ywc_kor_any_outcome NOT = { has_variable = ywc_kor_arc_abandoned } } }",
             "826b5232a9b3255a726a833e90c8962caf6983c41bf90b8c5fda270fd22098c2",
             "5448f1c8571ba650cefed2470b21efac53ecc62955be59687af98894c8e2ac2e"),
        )
        for jid, old_goal, new_goal, old_hash, new_hash in exceptions:
            before = next(j for a in previous for j in a["journals"] if j["id"] == jid)
            after = next(j for a in projected for j in a["journals"] if j["id"] == jid)
            phase_before = next(p for a in previous for p in a["inline_delivery_adapter"]["live_phases"] if p["journal"] == jid)
            phase_after = next(p for a in projected for p in a["inline_delivery_adapter"]["live_phases"] if p["journal"] == jid)
            self.assertEqual((before["goal"], phase_before["goal_sha256"]), (old_goal, old_hash))
            self.assertEqual((after["goal"], phase_after["goal_sha256"]), (new_goal, new_hash))
            self.assertEqual(hashlib.sha256(new_goal.encode()).hexdigest(), new_hash)
            after["goal"], phase_after["goal_sha256"] = old_goal, old_hash
        self.assertEqual(projected, previous, "old three source content differs beyond the exact four-leaf exception")
        self.assertEqual(active[-1]["slug"], REVENUE)
        self.assertEqual([j["id"] for j in active[-1]["journals"]], list(JES))
        metadata = active[-1]["inline_delivery_adapter"]
        self.assertEqual(metadata["schema"], "v03.foundation_inline_adapter.v2")
        proofs = metadata["branches"]
        self.assertEqual([sum(p["journal"] == jid for p in proofs) for jid in JES], [4, 4])
        self.assertEqual([p["event"] for p in proofs], [f"ywc_kor.{n}" for n in range(1100, 1108)])
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["branches"]) for a in active[:-1]), 31)
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["direct_adds"]) for a in active[:-1]), 5)
        adapter.validate_inline_catalog(current)
        rendered = adapter.render_inline_country_adapters(current)
        self.assertEqual(len(rendered["journal_scripts"]), 8)
        self.assertIn("ywc_v03_kor_inline_served_4", rendered["effects"])
        for candidate in range(32, 40):
            self.assertIn(f"ywc_v03_kor_inline_candidate_{candidate} =", rendered["triggers"])

    def test_rehashed_actual_sources_cannot_borrow_any_old_arc_queue(self):
        for queue in ("ywc_kor_pending_event", "ywc_kor_school_pending_event", "ywc_kor_ports_pending_event"):
            with self.subTest(queue=queue):
                current = json.loads((ROOT / "data/content/v03/countries/kor.json").read_text("utf-8-sig"))
                arc = next(a for a in current["arcs"] if a["slug"] == REVENUE)
                for journal in arc["journals"]:
                    journal["script"] = journal["script"].replace(QUEUE, queue)
                bind_sources(arc)
                with self.assertRaisesRegex(ValueError, "KOR queue ownership crosses arcs"):
                    adapter.validate_inline_catalog(current)

    def test_faulted_actual_native_body_cannot_ack_after_marking_major(self):
        from shu_kor_strict_review_runtime import field
        from test_v03_kor_provincial_revenue import new_world
        world = new_world()
        arc = next(a for a in world.cat["arcs"] if a["slug"] == REVENUE)
        world.pulse(arc)
        self.assertEqual([eid for _, eid in world.events], ["ywc_kor.1100"])
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_v03_kor_inline_reservation"], 32)
        event = world.event_defs["ywc_kor.1100"]
        valid = copy.deepcopy(world)
        fault = copy.deepcopy(field(event, "immediate"))
        changes = []
        def corrupt(nodes):
            for key, _, value in nodes:
                if key == "set_variable" and isinstance(value, list) and field(value, "name") == RECEIPT:
                    for index, child in enumerate(value):
                        if child[0] == "value":
                            value[index] = ("value", "=", "0")
                            changes.append(1)
                if isinstance(value, list):
                    corrupt(value)
        corrupt(fault)
        self.assertEqual(len(changes), 1)
        world.execute(fault, world.tag)
        self.assertIn("ywc_v03_major_event_cooldown", state)
        self.assertEqual(state[RECEIPT], 0)
        world.run("ywc_v03_kor_inline_ack_32", world.tag)
        self.assertEqual(state["ywc_v03_kor_inline_reservation"], 32)
        self.assertEqual(state[QUEUE], 1100)
        valid.execute(field(event, "immediate"), valid.tag)
        self.assertEqual(valid.countries[valid.tag][RECEIPT], 1)
        self.assertNotIn("ywc_v03_kor_inline_reservation", valid.countries[valid.tag])
        self.assertNotIn(QUEUE, valid.countries[valid.tag])

    def test_revenue_school_and_military_are_fair_in_both_native_orders(self):
        from collections import Counter
        from shu_kor_strict_review_runtime import field
        from test_v03_kor_provincial_revenue import new_world
        from test_v03_shu_provincial_contract import choose, option_legal
        current = json.loads((ROOT / "data/content/v03/countries/kor.json").read_text("utf-8-sig"))
        participants = [next(a for a in current["arcs"] if a["slug"] == slug)
                        for slug in (FOUNDATION[0], FOUNDATION[1], REVENUE)]
        mapping = {}
        for arc in adapter._kor_active_arcs(current):
            for proof in arc["inline_delivery_adapter"]["branches"]:
                for queue in proof["candidates"]:
                    mapping[len(mapping) + 1] = (arc["slug"], proof["event"], queue["queue"])
        old_choices = dict(zip(range(1000, 1010), (
            "court_supply", "pay_month", "court_roll", "publish", "fund_local", "fund_transition",
            "begin_renewal", "fund_invoice_review", "peace_ledger", "establish_court")))
        old_choices.update(dict(zip(range(1010, 1018), (
            "co_manage", "record_old_invoice", "share_review", "university_post", "keep_docket",
            "start_review", "establish", "settle_established"))))
        for order in (participants, list(reversed(participants))):
            with self.subTest(order=[a["slug"] for a in order]):
                world = new_world(route="provincial")
                state = world.countries[world.tag]
                # A migrated legacy admission fact permits school alongside a
                # still-unsettled new military line. No new producer/paid state
                # is supplied; this test measures scheduling, not earned history.
                state["laws"] = list(set(state["laws"]) | {"law_professional_army", "law_public_schools"})
                state["institutions"]["institution_schools"] = 2
                world.modifiers.append((world.tag, {"modifier": "military_wages_medium"}))
                province = state["states"][0]
                for kind in ("building_barrack", "building_university"):
                    if not any(b["type"] == kind for b in province["buildings"]):
                        province["buildings"].append({"type": kind, "occupancy": 1, "shortage": False, "groups": []})
                # Military claim itself calls the migration initializer, so
                # the old admission fact must follow that fresh claim.
                world.refresh(participants[0])
                self.assertIn("ywc_v03_kor_v03_kor_military_accounts_started", state)
                self.assertNotIn("ywc_v03_kor_v03_kor_military_accounts_settled", state)
                state["ywc_campaign_kor_c1_outcome"] = 1
                for arc in participants[1:]:
                    world.refresh(arc)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
                deliveries = []
                for month in range(1, 181):
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
                                if arc["slug"] == REVENUE:
                                    choose_revenue_progress(world, arc, event, number)
                                else:
                                    wanted = old_choices[number]
                                    if not option_legal(world, event, wanted):
                                        waits = {1015: "retry", 1016: "wait_for_observation", 1017: "retry"}
                                        self.assertIn(number, waits, (eid, "unexpected old-route loss"))
                                        wanted = waits[number]
                                    choose(world, arc, event, wanted)
                        world.refresh(arc)
                self.assertEqual(Counter(r[0] for r in deliveries[:9]),
                                 Counter({a["slug"]: 3 for a in participants}))
                self.assertTrue(all(b[1] - a[1] >= 90 for a, b in zip(deliveries, deliveries[1:])))
                own = [r for r in deliveries if r[0] == REVENUE]
                # 1104 first pays and later submits the real mature review;
                # every distinct source still owns its fixed candidate.
                distinct = [row for index, row in enumerate(own)
                            if index == 0 or row[2] != own[index - 1][2]]
                self.assertEqual([r[2] for r in distinct], [f"ywc_kor.{n}" for n in range(1100, 1108)])
                self.assertEqual([r[3] for r in distinct], list(range(32, 40)))
                self.assertTrue(all(count == 1 or eid == "ywc_kor.1104"
                                    for eid, count in Counter(r[2] for r in own).items()))
                self.assertEqual(state["ywc_kor_revenue_outcome"], 1)
                self.assertEqual(state["ywc_v03_kor_v03_kor_school_factions_outcome"], 1)
                self.assertEqual(state["ywc_v03_kor_v03_kor_military_accounts_outcome"], 1)
                self.assertEqual(state["ywc_v03_active_arc_count"], 0)


if __name__ == "__main__":
    unittest.main()
