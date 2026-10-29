"""NMG parish school appends one explicit v2 arc with its own ordinal receipt."""
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
BASELINE = "00ccb05803d4c04cfe328e0bcff33825ed88ca5e"
FOUNDATION = ("v03_nmg_land_arbitration", "v03_nmg_bilingual_office", "v03_nmg_autonomy_revenue")
SCHOOL = "v03_nmg_parish_school"
JES = ("ywc_je_v03_nmg_parish_school", "ywc_je_v03_nmg_parish_settlement")
QUEUE = "ywc_nmg_school_pending_event"
RECEIPT = "ywc_v03_nmg_v03_nmg_parish_school_last_event"


def frozen(path):
    return subprocess.run(["git", "show", BASELINE + ":" + path], cwd=ROOT,
                          check=True, capture_output=True).stdout.decode("utf-8-sig")


def bind_sources(arc):
    phases, records = [], []
    for index, journal in enumerate(arc["journals"]):
        phases.append({"journal": journal["id"],
                       "live_witness": "ywc_v03_nmg_inline_live_parish_" + ("school" if index == 0 else "settlement"),
                       **{target: hashlib.sha256(journal[source].encode()).hexdigest()
                          for target, source in (("source_script_sha256", "script"),
                                                 ("goal_sha256", "goal"), ("exit_sha256", "exit_conditions"))}})
        for source in adapter._nmg_source_binding(journal["id"], journal["script"])["branches"]:
            records.append({"journal": journal["id"],
                            **{key: source[key] for key in ("branch_index", "statement_ordinal", "chain_index",
                                                           "branch_kind", "event", "chain_prior", "chain_sha256",
                                                           "candidates", "queue_exclusions")},
                            "branch_sha256": source["sha256"], "limit_sha256": source["limit_sha256"]})
    arc["inline_delivery_adapter"] = {"schema": "v03.foundation_inline_adapter.v2",
                                       "live_phases": phases, "branches": records,
                                       "direct_adds": adapter._kor_direct_adds(arc)}


def synthetic_catalog():
    current = json.loads(frozen("data/content/v03/countries/nmg.json"))
    arc = {"slug": SCHOOL, "era": "middle", "journals": [], "events": []}
    for jid, numbers in zip(JES, (range(1110, 1114), range(1114, 1118))):
        sends = []
        for number in numbers:
            sends.append(f"if = {{ limit = {{ var:{QUEUE} = {number} }} "
                         f"remove_variable = {QUEUE} trigger_event = {{ id = ywc_nmg.{number} }} }}")
            arc["events"].append({"id": f"ywc_nmg.{number}", "trigger": "{ always = yes }", "options": [],
                                  "immediate": "{ ywc_v03_mark_major_delivered = yes "
                                  f"set_variable = {{ name = {RECEIPT} value = {number - 1109} }} }}"})
        arc["journals"].append({"id": jid,
                                "script": "{ possible = { always = yes } immediate = {} "
                                "on_monthly_pulse = { effect = { " + " ".join(sends) + " } } }",
                                "goal": "{ var:synthetic_closed = 1 }",
                                "exit_conditions": "{ var:synthetic_withdrawn = 1 }"})
    bind_sources(arc)
    current["arcs"].append(arc)
    return current


class NmgSchoolIsolatedAdapter(unittest.TestCase):
    def catalog(self):
        try:
            return synthetic_catalog()
        except ValueError as exc:
            self.fail(f"the new private exact queue requires a registered parser path: {exc}")

    def test_native_exact_two_nodes_use_own_ordinal_receipt_through_nmg_api(self):
        self.assertTrue(hasattr(adapter, "_nmg_school_native_receipt"), "school native ABI is unregistered")
        for number, ordinal in zip(range(1110, 1118), range(1, 9)):
            text = ("{ ywc_v03_mark_major_delivered = yes "
                    f"set_variable = {{ name = {RECEIPT} value = {ordinal} }} }}")
            event = {"id": f"ywc_nmg.{number}", "immediate": text}
            self.assertEqual(adapter._nmg_school_native_receipt(event), (RECEIPT, ordinal))
            self.assertEqual(adapter._nmg_native_receipt(event, "school"), (RECEIPT, ordinal))
            for wrong in (text.replace(RECEIPT, "ywc_nmg_office_last_event"),
                          text.replace(RECEIPT, "ywc_nmg_school_last_event"),
                          text.replace(f"value = {ordinal}", f"value = {number}"),
                          text.replace(f"value = {ordinal}", "value = 0"),
                          text.replace("= yes", "= no"), text.replace("set_variable", "change_variable"),
                          text.replace("value =", "extra = 1 value ="), text[:-1] + "add_treasury = 1 }",
                          "{ set_variable = { name = " + RECEIPT + f" value = {ordinal} "
                          "} ywc_v03_mark_major_delivered = yes }"):
                with self.subTest(number=number, wrong=wrong), self.assertRaises(ValueError):
                    adapter._nmg_school_native_receipt({**event, "immediate": wrong})
        for bad in (None, 1110, "ywc_nmg.1109", "ywc_nmg.1118", "ywc_kor.1110"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                adapter._nmg_school_native_receipt({"id": bad, "immediate": "{}"})

    def test_fixed_selector_rejects_unknown_duplicate_wrong_era_or_missing_foundation(self):
        self.assertTrue(hasattr(adapter, "_nmg_active_arcs"), "NMG school selector is absent")
        arcs = [{"slug": slug, "era": "foundation"} for slug in FOUNDATION]
        arcs.append({"slug": SCHOOL, "era": "middle"})
        for order in (arcs, list(reversed(arcs))):
            self.assertEqual([a["slug"] for a in adapter._nmg_active_arcs({"arcs": order})], [*FOUNDATION, SCHOOL])
        for bad in (arcs + [arcs[-1]], arcs[1:],
                    [*arcs[:-1], {"slug": SCHOOL, "era": "late"}],
                    [*arcs, {"slug": "v03_nmg_unknown", "era": "middle"}]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                adapter._nmg_active_arcs({"arcs": bad})

    def test_rehashed_private_queue_partition_body_and_source_metadata_mutants_reject(self):
        valid = self.catalog()
        adapter.validate_inline_catalog(valid)
        for fault in ("land_queue", "office_queue", "revenue_queue", "partition", "body", "source_hash", "bool_ordinal", "direct_add"):
            current = copy.deepcopy(valid)
            arc = current["arcs"][-1]
            if fault.endswith("_queue"):
                owner = fault.removesuffix("_queue")
                for journal in arc["journals"]:
                    journal["script"] = journal["script"].replace(QUEUE, f"ywc_nmg_{owner}_pending")
            elif fault == "partition":
                arc["journals"][0]["script"] = arc["journals"][0]["script"].replace("1113", "1114")
                arc["journals"][1]["script"] = arc["journals"][1]["script"].replace("1114", "1113")
            elif fault == "body":
                arc["events"][0]["immediate"] = arc["events"][0]["immediate"][:-1] + "add_treasury = 1 }"
            bind_sources(arc)
            if fault == "source_hash":
                arc["inline_delivery_adapter"]["live_phases"][0]["source_script_sha256"] = "0" * 64
            elif fault == "bool_ordinal":
                arc["inline_delivery_adapter"]["branches"][0]["branch_index"] = False
            elif fault == "direct_add":
                arc["events"][0]["options"] = [{"key": "handoff", "effect": "{ add_journal_entry = { type = " + JES[1] + " } }"}]
                bind_sources(arc)
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                adapter.validate_inline_catalog(current)
        with self.assertRaises(ValueError):
            adapter._nmg_queue_candidates(
                "if = { limit = { var:ywc_nmg_unregistered_pending_event = 1110 } "
                "trigger_event = { id = ywc_nmg.1110 } }")

    def test_render_appends_eight_candidates_and_receipt_bound_ack(self):
        current = self.catalog()
        rendered = adapter.render_inline_country_adapters(current)
        self.assertEqual(len(rendered["journal_scripts"]), 8)
        self.assertIn("ywc_v03_nmg_inline_served_4", rendered["effects"])
        for number in range(37, 45):
            self.assertIn(f"ywc_v03_nmg_inline_candidate_{number} =", rendered["triggers"])
        reordered = copy.deepcopy(current)
        reordered["arcs"].reverse()
        self.assertEqual(adapter.render_inline_country_adapters(reordered), rendered)

    def test_synthetic_ack_rejects_wrong_owned_receipt_with_other_proofs_complete(self):
        from clausewitz_harness import PulseWorld
        rendered = adapter.render_inline_country_adapters(self.catalog())
        state = {"ywc_v03_nmg_inline_reservation": 37, "ywc_v03_nmg_inline_timer": 1,
                 "ywc_v03_nmg_inline_reservation_epoch": 7, "ywc_v03_nmg_inline_candidate_epoch_37": 7,
                 "ywc_v03_nmg_inline_c37_ywc_nmg_school_pending_event_present": 1,
                 "ywc_v03_nmg_inline_c37_ywc_nmg_school_pending_event_value": 1110,
                 "ywc_v03_nmg_inline_live_parish_school": 1, "ywc_v03_nmg_inline_round": 1,
                 "ywc_v03_nmg_inline_callback_37": 1, "ywc_v03_nmg_inline_callback_candidate_37": 37,
                 "ywc_v03_nmg_inline_callback_epoch_37": 7, "ywc_v03_nmg_inline_callback_queue_37": 1110,
                 "ywc_v03_nmg_inline_body_completed_37": 1, "ywc_v03_nmg_inline_body_completed_epoch_37": 7,
                 QUEUE: 1110, RECEIPT: 0}
        world = PulseWorld(rendered["effects"], {"NMG": state})
        world.journals = [("NMG", [("type", "=", JES[0])])]
        self.assertTrue("ywc_v03_nmg_inline_ack_37" in world.effects)
        before = copy.deepcopy(state)
        world.run("ywc_v03_nmg_inline_ack_37", "NMG")
        self.assertEqual(state, before)
        state[RECEIPT] = 1
        world.run("ywc_v03_nmg_inline_ack_37", "NMG")
        self.assertNotIn(QUEUE, state)
        self.assertNotIn("ywc_v03_nmg_inline_reservation", state)

    def test_immutable_old_three_complete_render_matches_head(self):
        catalog = json.loads(frozen("data/content/v03/countries/nmg.json"))
        old = types.ModuleType("nmg_school_frozen_adapter")
        sys.modules[old.__name__] = old
        try:
            exec(compile(frozen("tools/v03_inline_delivery_adapter.py"), old.__name__, "exec"), old.__dict__)
            self.assertEqual(adapter.render_inline_country_adapters(catalog), old.render_inline_country_adapters(catalog))
            for country in ("dmg", "kor", "nqg", "mgl", "lan", "shu", "tib", "jhg"):
                with self.subTest(country=country):
                    other = json.loads(frozen(f"data/content/v03/countries/{country}.json"))
                    self.assertEqual(adapter.render_inline_country_adapters(other),
                                     old.render_inline_country_adapters(other))
        finally:
            sys.modules.pop(old.__name__, None)
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["branches"]) for a in catalog["arcs"]), 36)
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["direct_adds"]) for a in catalog["arcs"]), 0)


def current_catalog():
    """Actual source read occurs only when a gated generated test executes."""
    return json.loads((ROOT / "data/content/v03/countries/nmg.json").read_text("utf-8-sig"))


def pending_school_job(world, arc, number):
    """Reach a real queued EventJob, before display executes its immediate."""
    from shu_kor_strict_review_runtime import field
    from test_v03_nmg_parish_school import _country_monthly_once
    wanted = f"ywc_nmg.{number}"
    for _ in range(72):
        _country_monthly_once(world)
        world.pulse(arc)
        for job in world.jobs:
            if job.serial in world._school_handled_jobs or job.due_day > world.day:
                continue
            if job.recipient.tag != "NMG":
                raise AssertionError(("unexpected_native_school_job", wanted, job))
            with world._chain(job.recipient, job.saved):
                if not world.conditions(field(world.event_defs[job.event_id], "trigger"), "NMG"):
                    continue
            if job.event_id != wanted:
                raise AssertionError(("unexpected_native_school_job", wanted, job))
            return job
        # PartnerWorld owns both the Gregorian date/day and elapsed_months.
        world.advance_months(1)
    raise AssertionError(("no_native_school_job", wanted, world.date))


def choose_native_job(world, arc, job, key):
    """Reuse the public native-chain choice helper, with only runner bookkeeping."""
    from test_v03_nmg_parish_school import choose
    event = world.event_defs[job.event_id]
    world.__dict__.setdefault("_school_event_jobs", {})[id(event)] = job
    choose(world, arc, event, key)


def native_choice_is_legal(world, job, key):
    """Check the chosen real option, without evaluating unrelated menu routes."""
    from test_v03_nmg_parish_school import option_legal
    event = world.event_defs[job.event_id]
    world.__dict__.setdefault("_school_event_jobs", {})[id(event)] = job
    return option_legal(world, event, key)


class NmgSchoolGeneratedAdapter(unittest.TestCase):
    """Run only after root announces actual source/bind/generation terminal gate.

    All production-reading imports are lazy. Static preparation or discovery
    does not construct worlds or read the active country/helper/generated files.
    """

    def test_actual_inventory_preserves_three_arcs_and_appends_eight_owned_sources(self):
        current = current_catalog()
        active = adapter._nmg_active_arcs(current)
        previous = json.loads(frozen("data/content/v03/countries/nmg.json"))["arcs"]
        self.assertEqual(active[:-1], previous, "all three old arcs and exact source proofs remain frozen")
        self.assertEqual([a["slug"] for a in active], [*FOUNDATION, SCHOOL])
        self.assertEqual(sum(len(a["journals"]) for a in active[:-1]), 6)
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["branches"]) for a in active[:-1]), 36)
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["direct_adds"]) for a in active[:-1]), 0)
        arc = active[-1]
        self.assertEqual([j["id"] for j in arc["journals"]], list(JES))
        self.assertEqual(arc["inline_delivery_adapter"]["schema"], "v03.foundation_inline_adapter.v2")
        proofs = arc["inline_delivery_adapter"]["branches"]
        self.assertEqual([p["event"] for p in proofs], [f"ywc_nmg.{n}" for n in range(1110, 1118)])
        self.assertEqual([sum(p["journal"] == jid for p in proofs) for jid in JES], [4, 4])
        self.assertEqual(arc["inline_delivery_adapter"]["direct_adds"], [])
        for number, proof in zip(range(1110, 1118), proofs):
            self.assertEqual(proof["candidates"], [
                {"queue": QUEUE, "kind": "normal", "mode": "exact", "value": number}])
        for event in arc["events"]:
            number = int(event["id"].rsplit(".", 1)[1])
            self.assertEqual(adapter._nmg_native_receipt(event, "school"), (RECEIPT, number - 1109))
        adapter.validate_inline_catalog(current)
        rendered = adapter.render_inline_country_adapters(current)
        self.assertEqual(len(rendered["journal_scripts"]), 8)
        self.assertIn("ywc_v03_nmg_inline_served_4", rendered["effects"])
        for candidate in range(37, 45):
            self.assertIn(f"ywc_v03_nmg_inline_candidate_{candidate} =", rendered["triggers"])
        generated = (ROOT / "yongchang_world/events/ywc_v03_country_nmg_events.txt").read_text("utf-8-sig")
        self.assertEqual(set(re.findall(r"(?m)^(ywc_nmg\.111[0-7])\s*=\s*\{", generated)),
                         {f"ywc_nmg.{n}" for n in range(1110, 1118)})

    def test_rehashed_actual_school_sources_cannot_borrow_old_arc_queues(self):
        for queue in ("ywc_nmg_land_pending", "ywc_nmg_office_pending", "ywc_nmg_revenue_pending"):
            with self.subTest(queue=queue):
                current = current_catalog()
                arc = next(a for a in current["arcs"] if a["slug"] == SCHOOL)
                for journal in arc["journals"]:
                    journal["script"] = journal["script"].replace(QUEUE, queue)
                bind_sources(arc)
                with self.assertRaises(ValueError):
                    adapter.validate_inline_catalog(current)

    def test_all_eight_actual_jobs_ack_only_after_their_owned_native_receipt(self):
        from shu_kor_strict_review_runtime import field
        from test_v03_nmg_parish_school import new_world, ACTIONS, month
        world = new_world(mode=1)
        arc = next(a for a in world.cat["arcs"] if a["slug"] == SCHOOL)
        acknowledged = []
        for number in range(1110, 1118):
            job = pending_school_job(world, arc, number)
            ordinal, candidate = number - 1109, number - 1073
            state = world.countries["NMG"]
            self.assertEqual(state["ywc_v03_nmg_inline_reservation"], candidate)
            self.assertEqual(state[QUEUE], number)
            for wrong in sorted({0, ordinal - 1, number}):
                with self.subTest(number=number, wrong=wrong):
                    fault = copy.deepcopy(world)
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
                    corrupt(field(fault.event_defs[job.event_id], "immediate"))
                    self.assertEqual(len(changes), 1)
                    self.assertTrue(fault.display_job(job))
                    failed = fault.countries["NMG"]
                    self.assertIn("ywc_v03_major_event_cooldown", failed)
                    self.assertEqual(failed[RECEIPT], wrong)
                    fault.run(f"ywc_v03_nmg_inline_ack_{candidate}", "NMG")
                    self.assertEqual(failed["ywc_v03_nmg_inline_reservation"], candidate)
                    self.assertEqual(failed[QUEUE], number)
            self.assertTrue(world.display_job(job))
            world._school_handled_jobs.add(job.serial)
            self.assertEqual(state[RECEIPT], ordinal)
            self.assertNotIn("ywc_v03_nmg_inline_reservation", state)
            self.assertNotIn(QUEUE, state)
            acknowledged.append((job.event_id, candidate))
            choose_native_job(world, arc, job, ACTIONS[number])
            if number == 1115:
                # Audit starts a real run; the popup cooldown alone is only
                # about three months and cannot supply six monthly observations.
                month(world, arc, 6)
        self.assertEqual(acknowledged, [(f"ywc_nmg.{n}", n - 1073) for n in range(1110, 1118)])
        self.assertEqual(state["ywc_v03_nmg_v03_nmg_parish_school_outcome"], 1)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
        self.assertTrue(all(world.history["NMG"][jid] == "complete" for jid in JES))

    def test_school_office_and_land_share_fair_native_turns_in_both_orders(self):
        from collections import Counter
        from shu_kor_strict_review_runtime import field
        from test_v03_nmg_parish_school import new_world, literal_countries, ACTIONS
        current = current_catalog()
        participants = [next(a for a in current["arcs"] if a["slug"] == slug)
                        for slug in (FOUNDATION[0], FOUNDATION[1], SCHOOL)]
        mapping = {}
        for arc in adapter._nmg_active_arcs(current):
            for proof in arc["inline_delivery_adapter"]["branches"]:
                for queue in proof["candidates"]:
                    mapping[len(mapping) + 1] = (arc["slug"], proof["event"], queue["queue"])
        choices = dict(zip(range(1000, 1008), (
            "mixed", "rule_register", "finish_survey", "keep_old", "keep_recording",
            "old_assessment", "renegotiate", "settle_full")))
        choices.update(dict(zip(range(1010, 1016), (
            "bilingual", "hire_full", "court_parish", "fund_schools", "keep_route", "close_full"))))
        choices.update(ACTIONS)
        for order in (participants, list(reversed(participants))):
            with self.subTest(order=[a["slug"] for a in order]):
                countries = literal_countries(mode=1, office_occupancy=1, academics_occupancy=1)
                world = new_world(countries=countries, mode=1)
                state = world.countries["NMG"]
                for arc in participants:
                    world.refresh(arc)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
                handled = set(world._school_handled_jobs)
                deliveries = []
                for _ in range(180):
                    world.advance_months(1)
                    # The typed runtime advances actual Gregorian days and owns
                    # elapsed_months. No month*30 estimate or second increment.
                    world.run_country_monthly("NMG")
                    for arc in order:
                        for journal in arc["journals"]:
                            if journal["id"] not in world.active["NMG"]:
                                continue
                            world.execute(field(field(world.journal_defs[journal["id"]], "on_monthly_pulse"), "effect"), "NMG")
                            for job in world.jobs:
                                if job.serial in handled or job.due_day > world.day:
                                    continue
                                candidate = int(state["ywc_v03_nmg_inline_reservation"])
                                self.assertEqual(mapping[candidate][:2], (arc["slug"], job.event_id))
                                queue = mapping[candidate][2]
                                others = {k: v for k, v in state.items() if k.startswith("ywc_nmg_")
                                          and k.endswith(("_pending", "_pending_event")) and k != queue}
                                self.assertTrue(world.display_job(job))
                                handled.add(job.serial)
                                self.assertNotIn("ywc_v03_nmg_inline_reservation", state)
                                self.assertNotIn(queue, state)
                                self.assertEqual({k: state[k] for k in others}, others)
                                deliveries.append((arc["slug"], world.day, job.event_id, candidate))
                                number = int(job.event_id.rsplit(".", 1)[1])
                                key = choices[number]
                                # These two old terminal events have real wait
                                # options until their own observation matures.
                                if not native_choice_is_legal(world, job, key):
                                    self.assertIn(number, (1007, 1015), (job.event_id, key))
                                    key = "wait_retry"
                                choose_native_job(world, arc, job, key)
                        world.refresh(arc)
                self.assertEqual(len(deliveries[:9]), 9)
                self.assertEqual(Counter(r[0] for r in deliveries[:9]),
                                 Counter({a["slug"]: 3 for a in participants}))
                self.assertTrue(all(b[1] - a[1] >= 90 for a, b in zip(deliveries, deliveries[1:])))
                own = [r for r in deliveries if r[0] == SCHOOL]
                self.assertEqual([r[2] for r in own], [f"ywc_nmg.{n}" for n in range(1110, 1118)])
                self.assertEqual([r[3] for r in own], list(range(37, 45)))
                self.assertEqual(state[f"ywc_v03_nmg_{SCHOOL}_outcome"], 1)
                for slug in FOUNDATION[:2]:
                    self.assertEqual(state[f"ywc_v03_nmg_{slug}_outcome"], 3)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
