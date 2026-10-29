"""The crown appends source-bound delivery without changing earlier DMG cards."""
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unittest

from tools import v03_inline_delivery_adapter as adapter

ROOT = Path(__file__).resolve().parents[1]
CROWN = "v03_dmg_representative_crown"
SCHOOL = "v03_dmg_school_languages"
MARKET = "v03_dmg_luzon_border_market"
FOUNDATION = ("v03_dmg_common_subjects", "v03_dmg_two_land_titles", "v03_dmg_court_provinces")
JES = ("ywc_je_v03_dmg_crown_representation", "ywc_je_v03_dmg_crown_budget",
       "ywc_je_v03_dmg_crown_continuity")
RECEIPT = "ywc_v03_dmg_v03_dmg_representative_crown_last_event"


def bind_sources(arc):
    """Rebind mutated literal sources, so rejection cannot rely on stale hashes."""
    phases, branches = [], []
    for index, journal in enumerate(arc["journals"]):
        phases.append({"journal": journal["id"],
                       "live_witness": f"ywc_v03_dmg_live_{arc['slug']}_{index}",
                       **{target: hashlib.sha256(journal[source].encode()).hexdigest()
                          for target, source in (("source_script_sha256", "script"),
                                                 ("goal_sha256", "goal"),
                                                 ("exit_sha256", "exit_conditions"))}})
        for source in adapter.source_binding(journal["id"], journal["script"])["branches"]:
            branches.append({"journal": journal["id"], "branch_index": source["branch_index"],
                             "event": source["event"], "branch_sha256": source["sha256"],
                             "limit_sha256": source["limit_sha256"],
                             "candidates": adapter.queue_candidates(source["limit_source"])})
    arc["inline_delivery_adapter"] = {"schema": "v03.foundation_inline_adapter.v1",
                                       "live_phases": phases, "branches": branches}


def synthetic_catalog():
    """Minimal complete native source inputs, with no production file access."""
    arcs = []
    specs = [(slug, "foundation", [(f"ywc_je_synthetic_{n}", [1000 + n * 10])],
              f"ywc_dmg_synthetic_{n}_pending_event") for n, slug in enumerate(FOUNDATION)]
    specs += [(SCHOOL, "middle", [("ywc_je_v03_dmg_school_languages", range(1120, 1126))],
               "ywc_dmg_school_pending_event"),
              (MARKET, "middle", [("ywc_je_v03_dmg_luzon_market_terms", range(1100, 1105)),
                                    ("ywc_je_v03_dmg_luzon_market_review", range(1105, 1108))],
               "ywc_dmg_market_pending_event"),
              (CROWN, "middle", list(zip(JES, (range(1110, 1114), range(1114, 1117),
                                                range(1117, 1120)))),
               "ywc_dmg_crown_pending_event")]
    for slug, era, phases, queue in specs:
        arc = {"slug": slug, "era": era, "journals": [], "events": []}
        for jid, numbers in phases:
            sends = []
            for number in numbers:
                sends.append(f"if = {{ limit = {{ var:{queue} = {number} }} "
                             f"remove_variable = {queue} trigger_event = {{ id = ywc_dmg.{number} }} }}")
                name = f"ywc_v03_dmg_{slug}_last_event"
                ordinal = number - (1109 if slug == CROWN else 1099 if slug == MARKET else 1119)
                arc["events"].append({"id": f"ywc_dmg.{number}", "trigger": "{ always = yes }",
                                      "immediate": "{ ywc_v03_mark_major_delivered = yes "
                                      f"set_variable = {{ name = {name} value = {ordinal} }} }}"})
            arc["journals"].append({"id": jid,
                                    "script": "{ on_monthly_pulse = { effect = { " + " ".join(sends) + " } } }",
                                    "goal": "{ var:synthetic_complete = 1 }",
                                    "exit_conditions": "{ var:synthetic_withdrawn = 1 }"})
        bind_sources(arc)
        arcs.append(arc)
    return {"key": "country_dmg", "arcs": arcs}


class DmgCrownIsolatedAdapter(unittest.TestCase):
    """These literal inputs never open the changing country catalog/helpers."""

    def test_native_body_accepts_only_the_owned_ordered_receipt(self):
        self.assertTrue(hasattr(adapter, "_dmg_crown_native_receipt"),
                        "crown native-body validation is missing")
        receipt = adapter._dmg_crown_native_receipt
        for number, ordinal in zip(range(1110, 1120), range(1, 11)):
            body = ("{ ywc_v03_mark_major_delivered = yes "
                    f"set_variable = {{ name = {RECEIPT} value = {ordinal} }} }}")
            event = {"id": f"ywc_dmg.{number}", "immediate": body}
            self.assertEqual(receipt(event), (RECEIPT, ordinal))
            wrong_bodies = (
                body.replace(RECEIPT, "ywc_v03_dmg_v03_dmg_school_languages_last_event"),
                body.replace(RECEIPT, "ywc_v03_dmg_v03_dmg_luzon_border_market_last_event"),
                body.replace(f"value = {ordinal}", f"value = {number}"),
                body.replace(f"value = {ordinal}", "value = 0"),
                body.replace("set_variable", "change_variable"),
                body.replace("= yes", "= no"),
                body[:-1] + "add_treasury = 1 }",
                body.replace("value =", "extra_field = 1 value ="),
                "{ set_variable = { name = " + RECEIPT + f" value = {ordinal} "
                "} ywc_v03_mark_major_delivered = yes }",
            )
            for wrong in wrong_bodies:
                with self.subTest(number=number, wrong=wrong), self.assertRaises(ValueError):
                    receipt({**event, "immediate": wrong})
        for bad_id in (None, 1110, "ywc_dmg.1109", "ywc_dmg.1120", "ywc_kor.1110"):
            with self.subTest(bad_id=bad_id), self.assertRaises(ValueError):
                receipt({"id": bad_id, "immediate": "{}"})

    def test_selector_appends_crown_after_all_five_old_arcs_and_requires_them(self):
        arcs = [{"slug": slug, "era": "foundation"} for slug in FOUNDATION]
        arcs += [{"slug": slug, "era": "middle"} for slug in (SCHOOL, MARKET, CROWN)]
        for order in (arcs, list(reversed(arcs))):
            with self.subTest(order=order):
                try:
                    selected = adapter._dmg_active_arcs({"arcs": order})
                except ValueError as exc:
                    self.fail(f"registered crown must be selected: {exc}")
                self.assertEqual([a["slug"] for a in selected], [*FOUNDATION, SCHOOL, MARKET, CROWN])
        for missing in (SCHOOL, MARKET):
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                adapter._dmg_active_arcs({"arcs": [a for a in arcs if a["slug"] != missing]})
        for extra in ({"slug": CROWN, "era": "middle"},
                      {"slug": CROWN, "era": "late"},
                      {"slug": "v03_dmg_unknown_crown", "era": "middle"}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                adapter._dmg_active_arcs({"arcs": [*arcs, extra]})

    def test_phase_partition_and_queue_ownership_survive_rehashed_metadata(self):
        valid = synthetic_catalog()
        try:
            adapter.validate_inline_catalog(valid)
        except ValueError as exc:
            self.fail(f"registered 4/3/3 crown source must validate: {exc}")
        for queue in ("ywc_dmg_school_pending_event", "ywc_dmg_market_pending_event",
                      "ywc_dmg_unregistered_pending_event"):
            current = copy.deepcopy(valid)
            crown = current["arcs"][-1]
            for journal in crown["journals"]:
                journal["script"] = journal["script"].replace("ywc_dmg_crown_pending_event", queue)
            bind_sources(crown)
            with self.subTest(queue=queue), self.assertRaises(ValueError):
                adapter.validate_inline_catalog(current)
        for mutation in ("journal_order", "phase_swap", "presence", "wrong_receipt"):
            current = copy.deepcopy(valid)
            crown = current["arcs"][-1]
            if mutation == "journal_order":
                crown["journals"].reverse()
            elif mutation == "phase_swap":
                left, right = crown["journals"][:2]
                left["script"] = left["script"].replace("1113", "1114")
                right["script"] = right["script"].replace("1114", "1113")
            elif mutation == "presence":
                crown["journals"][0]["script"] = crown["journals"][0]["script"].replace(
                    "var:ywc_dmg_crown_pending_event = 1110", "has_variable = ywc_dmg_crown_pending_event")
            else:
                crown["events"][0]["immediate"] = crown["events"][0]["immediate"].replace(
                    RECEIPT, "ywc_v03_dmg_v03_dmg_school_languages_last_event")
            bind_sources(crown)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                adapter.validate_inline_catalog(current)


def crown_world():
    """Current constitutional facts; all business runs the generated native AST."""
    from lan_public_runtime import LanPublicWorld
    from shu_kor_strict_review_runtime import facts
    world = LanPublicWorld("dmg", load_inline=True)
    state = facts()
    state["literacy_rate"] = .35
    state["laws"] += ["law_monarchy", "law_census_voting", "law_total_separation"]
    state["country_has_voting_franchise"] = True
    state["igs"] = [{"type": kind, "in_government": kind == "ig_intelligentsia",
                     "clout": .20, "approval": 2}
                    for kind in ("ig_intelligentsia", "ig_rural_folk", "ig_landowners", "ig_armed_forces")]
    province = state["states"][0]
    province.update(owner="DMG", region="s:STATE_LUZON")
    academic = copy.deepcopy(province["pops"][0])
    academic.update(type="academics", workplace=next(
        b for b in province["buildings"] if b["type"] == "building_university"))
    province["pops"].append(academic)
    world.countries[world.tag] = state
    world.run("ywc_v03_initialize_country", world.tag)
    return world


def choose_crown_progress(world, arc, event, number):
    """Use the now-frozen native keys and assert every required transition."""
    from test_v03_shu_provincial_contract import choose
    choices = dict(zip(range(1110, 1120), (
        "constitutional_crown", "pay_registry", "new_hearing", "sign_appointment",
        "pay_share", "write_statement", "handoff_continuity", "pay_review", "request_full", "close_full")))
    choose(world, arc, event, choices[number])
    state = world.countries[world.tag]
    assert state.get("ywc_dmg_crown_mode") == 1 and state.get("ywc_dmg_crown_target") == 1
    if number == 1119:
        assert state.get("ywc_dmg_crown_outcome") == 1
    else:
        assert state.get("ywc_dmg_crown_stage") == number + 1, (number, state.get("ywc_dmg_crown_stage"))


class DmgCrownGeneratedAdapter(unittest.TestCase):
    """Run only after country authorship, metadata and generation are complete."""

    def test_generated_inventory_appends_ten_candidates_and_preserves_old_bindings(self):
        source = (ROOT / "yongchang_world/events/ywc_v03_country_dmg_events.txt").read_text("utf-8-sig")
        self.assertEqual(set(re.findall(r"(?m)^(ywc_dmg\.111[0-9])\s*=\s*\{", source)),
                         {f"ywc_dmg.{n}" for n in range(1110, 1120)})
        current = json.loads((ROOT / "data/content/v03/countries/dmg.json").read_text("utf-8-sig"))
        active = adapter._dmg_active_arcs(current)
        baseline = json.loads(subprocess.run(
            ["git", "show", "9980153ba0edb9c48f141df84c11b2f530ab39b6:data/content/v03/countries/dmg.json"],
            cwd=ROOT, check=True, capture_output=True).stdout.decode("utf-8-sig"))
        self.assertEqual(active[:-1], baseline["arcs"], "old five complete source bindings must remain unchanged")
        self.assertEqual([a["slug"] for a in active], [*FOUNDATION, SCHOOL, MARKET, CROWN])
        self.assertEqual([j["id"] for j in active[-1]["journals"]], list(JES))
        self.assertEqual(active[-1]["depends_on"], [])
        self.assertEqual(active[-1]["inline_delivery_adapter"]["schema"], "v03.foundation_inline_adapter.v1")
        proofs = active[-1]["inline_delivery_adapter"]["branches"]
        self.assertEqual([sum(p["journal"] == jid for p in proofs) for jid in JES], [4, 3, 3])
        self.assertEqual([p["event"] for p in proofs], [f"ywc_dmg.{n}" for n in range(1110, 1120)])
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["branches"]) for a in active[:-1]), 43)
        self.assertEqual(sum(len(p["candidates"]) for a in active[:-1]
                             for p in a["inline_delivery_adapter"]["branches"]), 62)
        adapter.validate_inline_catalog(current)
        rendered = adapter.render_inline_country_adapters(current)
        self.assertEqual(len(rendered["journal_scripts"]), 12)
        self.assertIn("ywc_v03_dmg_inline_served_6", rendered["effects"])
        for number in range(63, 73):
            self.assertIn(f"ywc_v03_dmg_inline_candidate_{number} =", rendered["triggers"])
        reordered = copy.deepcopy(current)
        reordered["arcs"].reverse()
        self.assertEqual(adapter.render_inline_country_adapters(reordered), rendered)

    def test_rehashed_actual_sources_cannot_steal_school_or_market_queues(self):
        for queue in ("ywc_dmg_school_pending_event", "ywc_dmg_market_pending_event"):
            with self.subTest(queue=queue):
                current = json.loads((ROOT / "data/content/v03/countries/dmg.json").read_text("utf-8-sig"))
                crown = next(a for a in current["arcs"] if a["slug"] == CROWN)
                for journal in crown["journals"]:
                    journal["script"] = journal["script"].replace("ywc_dmg_crown_pending_event", queue)
                bind_sources(crown)
                with self.assertRaisesRegex(ValueError, "DMG queue ownership crosses arcs"):
                    adapter.validate_inline_catalog(current)

    def test_faulted_native_receipt_cannot_ack_even_after_marking_major(self):
        from shu_kor_strict_review_runtime import field
        world = crown_world()
        arc = next(a for a in world.cat["arcs"] if a["slug"] == CROWN)
        world.pulse(arc)
        self.assertEqual([event for _, event in world.events], ["ywc_dmg.1110"])
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_v03_dmg_inline_reservation"], 63)
        event = world.event_defs["ywc_dmg.1110"]
        valid = copy.deepcopy(world)
        fault = copy.deepcopy(field(event, "immediate"))
        changes = []
        def corrupt_receipt(nodes):
            for key, _, value in nodes:
                if key == "set_variable" and isinstance(value, list) and field(value, "name") == RECEIPT:
                    for index, child in enumerate(value):
                        if child[0] == "value":
                            value[index] = ("value", "=", "0")
                            changes.append(1)
                if isinstance(value, list):
                    corrupt_receipt(value)
        corrupt_receipt(fault)
        self.assertEqual(len(changes), 1)
        world.execute(fault, world.tag)
        self.assertIn("ywc_v03_major_event_cooldown", state)
        self.assertEqual(state[RECEIPT], 0)
        self.assertEqual(state["ywc_v03_dmg_inline_reservation"], 63)
        self.assertEqual(state["ywc_dmg_crown_pending_event"], 1110)
        world.run("ywc_v03_dmg_inline_ack_63", world.tag)
        self.assertEqual(state["ywc_v03_dmg_inline_reservation"], 63)
        self.assertEqual(state["ywc_dmg_crown_pending_event"], 1110)
        valid.execute(field(event, "immediate"), valid.tag)
        actual = valid.countries[valid.tag]
        self.assertEqual(actual[RECEIPT], 1)
        self.assertNotIn("ywc_v03_dmg_inline_reservation", actual)
        self.assertNotIn("ywc_dmg_crown_pending_event", actual)

    def test_crown_school_and_foundation_progress_fairly_in_both_native_orders(self):
        from collections import Counter
        from shu_kor_strict_review_runtime import field
        from test_v03_shu_provincial_contract import choose
        current = json.loads((ROOT / "data/content/v03/countries/dmg.json").read_text("utf-8-sig"))
        participants = [next(a for a in current["arcs"] if a["slug"] == slug)
                        for slug in (FOUNDATION[0], SCHOOL, CROWN)]
        mapping = {}
        for arc in adapter._dmg_active_arcs(current):
            for proof in arc["inline_delivery_adapter"]["branches"]:
                for queue in proof["candidates"]:
                    mapping[len(mapping) + 1] = (arc["slug"], proof["event"], queue["queue"])
        school_choices = dict(zip(range(1120, 1126), (
            "bilingual_public", "pay_setup", "confirm_supply", "write_new_appeal",
            "pay_next_term", "close_established")))
        for order in (participants, list(reversed(participants))):
            with self.subTest(order=[a["slug"] for a in order]):
                world = crown_world()
                state = world.countries[world.tag]
                for arc in order:
                    world.refresh(arc)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
                deliveries = []
                for month in range(1, 151):
                    world.advance_months(1)
                    world.elapsed_months += 1
                    for arc in order:
                        for journal in arc["journals"]:
                            if journal["id"] not in world.active[world.tag]:
                                continue
                            world.execute(field(field(world.journal_defs[journal["id"]], "on_monthly_pulse"), "effect"), world.tag)
                            while world.events:
                                _, eid = world.events.pop(0)
                                candidate = int(state["ywc_v03_dmg_inline_reservation"])
                                self.assertEqual(mapping[candidate][:2], (arc["slug"], eid))
                                queue = mapping[candidate][2]
                                others = {k: v for k, v in state.items() if k.startswith("ywc_dmg_")
                                          and k.endswith("pending_event") and k != queue}
                                event = world.event_defs[eid]
                                self.assertTrue(world.conditions(field(event, "trigger"), world.tag))
                                world.execute(field(event, "immediate"), world.tag)
                                self.assertNotIn("ywc_v03_dmg_inline_reservation", state)
                                self.assertNotIn(queue, state)
                                self.assertEqual({k: state[k] for k in others}, others)
                                deliveries.append((arc["slug"], month * 30, eid, candidate))
                                number = int(eid.rsplit(".", 1)[1])
                                if arc["slug"] == CROWN:
                                    choose_crown_progress(world, arc, event, number)
                                else:
                                    choose(world, arc, event, school_choices[number] if number in school_choices else "defer")
                        world.refresh(arc)
                self.assertEqual(Counter(r[0] for r in deliveries[:9]),
                                 Counter({a["slug"]: 3 for a in participants}))
                self.assertTrue(all(b[1] - a[1] >= 90 for a, b in zip(deliveries, deliveries[1:])))
                for slug, numbers, candidates in ((CROWN, range(1110, 1120), range(63, 73)),
                                                   (SCHOOL, range(1120, 1126), range(49, 55))):
                    own = [r for r in deliveries if r[0] == slug]
                    self.assertEqual([r[2] for r in own], [f"ywc_dmg.{n}" for n in numbers])
                    self.assertEqual([r[3] for r in own], list(candidates))
                self.assertEqual(state["ywc_dmg_crown_outcome"], 1)
                self.assertEqual(state["ywc_dmg_school_outcome"], 1)
                self.assertEqual(world.treasury[world.tag], -5000)
                self.assertTrue(all(world.history[world.tag][jid] == "complete" for jid in JES))
                self.assertEqual(state["ywc_v03_active_arc_count"], 1)


if __name__ == "__main__":
    unittest.main()
