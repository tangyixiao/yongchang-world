"""Explicit registration of DMG's first middle arc in the existing coordinator."""
import copy
import json
from pathlib import Path
import unittest

from tools.v03_inline_delivery_adapter import render_inline_country_adapters, validate_inline_catalog

ROOT = Path(__file__).resolve().parents[1]
SLUG = "v03_dmg_school_languages"


def catalog():
    return json.loads((ROOT / "data/content/v03/countries/dmg.json").read_text(encoding="utf-8"))


class DmgSchoolAdapterTests(unittest.TestCase):
    def test_rehashing_cannot_give_school_a_foundation_queue(self):
        import hashlib
        from tools.v03_inline_delivery_adapter import source_binding, queue_candidates
        current = catalog()
        arc = next(a for a in current["arcs"] if a["slug"] == SLUG)
        journal = arc["journals"][0]
        journal["script"] = journal["script"].replace("ywc_dmg_school_pending_event",
                                                     "ywc_dmg_pending_event")
        metadata = arc["inline_delivery_adapter"]
        metadata["live_phases"][0]["source_script_sha256"] = hashlib.sha256(
            journal["script"].encode("utf-8")).hexdigest()
        for proof, source in zip(metadata["branches"],
                                 source_binding(journal["id"], journal["script"])["branches"]):
            proof["branch_sha256"] = source["sha256"]
            proof["limit_sha256"] = source["limit_sha256"]
            proof["candidates"] = queue_candidates(source["limit_source"])
        with self.assertRaisesRegex(ValueError, "DMG queue ownership crosses arcs"):
            validate_inline_catalog(current)

    def test_actual_school_and_two_old_sources_are_fair_in_both_native_orders(self):
        from collections import Counter
        from shu_kor_strict_review_runtime import field
        from test_v03_dmg_school_languages import new_world
        from test_v03_shu_provincial_contract import choose

        current = catalog()
        participants = [current["arcs"][0], current["arcs"][1], current["arcs"][3]]
        candidate_map = {}
        ident = 0
        for arc in current["arcs"]:
            for proof in arc["inline_delivery_adapter"]["branches"]:
                for queue in proof["candidates"]:
                    ident += 1
                    candidate_map[ident] = (arc["slug"], proof["event"], queue["queue"])
        choices = {1120: "bilingual_public", 1121: "pay_setup", 1122: "confirm_supply",
                   1123: "write_new_appeal", 1124: "pay_next_term", 1125: "close_established"}
        for order in (participants, list(reversed(participants))):
            with self.subTest(order=[a["slug"] for a in order]):
                world = new_world()
                state = world.countries[world.tag]
                for arc in order:
                    world.refresh(arc)
                self.assertEqual((state["ywc_v03_active_arc_count"],
                                  state["ywc_v03_visible_task_count"]), (3, 3))
                deliveries = []
                for month in range(1, 91):
                    world.advance_months(1)
                    world.elapsed_months += 1
                    for arc in order:
                        for journal in arc["journals"]:
                            jid = journal["id"]
                            if jid not in world.active[world.tag]:
                                continue
                            body = world.journal_defs[jid]
                            world.execute(field(field(body, "on_monthly_pulse"), "effect"), world.tag)
                            while world.events:
                                _, event_id = world.events.pop(0)
                                candidate = int(state["ywc_v03_dmg_inline_reservation"])
                                self.assertEqual(candidate_map[candidate][:2], (arc["slug"], event_id))
                                selected_queue = candidate_map[candidate][2]
                                other_queues = {key: value for key, value in state.items()
                                                if key.startswith("ywc_dmg_")
                                                and key.endswith("pending_event") and key != selected_queue}
                                event = world.event_defs[event_id]
                                self.assertTrue(world.conditions(field(event, "trigger"), world.tag))
                                world.execute(field(event, "immediate"), world.tag)
                                self.assertNotIn("ywc_v03_dmg_inline_reservation", state)
                                self.assertNotIn("ywc_v03_dmg_inline_timer", state)
                                self.assertNotIn(selected_queue, state)
                                self.assertEqual({key: state[key] for key in other_queues}, other_queues)
                                slot = next(i for i, a in enumerate(current["arcs"], 1)
                                            if a["slug"] == arc["slug"])
                                self.assertEqual(state[f"ywc_v03_dmg_inline_served_{slot}"],
                                                 state["ywc_v03_dmg_inline_round"])
                                deliveries.append((arc["slug"], month * 30, event_id, candidate))
                                number = int(event_id.split(".")[1])
                                if arc["slug"] == SLUG:
                                    key = choices[number]
                                else:
                                    authored = next(e for e in arc["events"] if e["id"] == event_id)
                                    available = {o["key"] for o in authored["options"]}
                                    key = next(k for k in ("defer", "wait_for_posting", "renegotiate")
                                               if k in available)
                                choose(world, arc, event, key)
                        world.refresh(arc)
                first = deliveries[:9]
                self.assertEqual(len(first), 9)
                self.assertEqual(Counter(row[0] for row in first),
                                 Counter({a["slug"]: 3 for a in participants}))
                self.assertTrue(all(b[1] - a[1] >= 90 for a, b in zip(deliveries, deliveries[1:])))
                school_rows = [row for row in deliveries if row[0] == SLUG]
                self.assertEqual([row[2] for row in school_rows],
                                 [f"ywc_dmg.{n}" for n in range(1120, 1126)])
                self.assertEqual([row[3] for row in school_rows], list(range(49, 55)))
                self.assertEqual(state["ywc_dmg_school_outcome"], 1)
                self.assertEqual((state["ywc_v03_active_arc_count"],
                                  state["ywc_v03_visible_task_count"]), (2, 2))

    def test_unknown_extension_cannot_bypass_native_source_registration(self):
        for metadata in (True, False):
            with self.subTest(metadata=metadata):
                current = catalog()
                extra = copy.deepcopy(current["arcs"][0])
                extra["slug"] = "v03_dmg_unregistered_extension"
                extra["era"] = "middle"
                if not metadata:
                    extra.pop("inline_delivery_adapter")
                current["arcs"].append(extra)
                with self.assertRaisesRegex(ValueError, "unregistered DMG inline arc"):
                    validate_inline_catalog(current)

    def test_school_has_six_registered_sources_and_keeps_the_original_48_candidates(self):
        current = catalog()
        arcs = [arc for arc in current["arcs"] if arc["slug"] == SLUG]
        self.assertEqual(len(arcs), 1, "the approved school arc has not been registered")
        school = arcs[0]
        self.assertEqual(school["era"], "middle")
        self.assertEqual({event["id"] for event in school["events"]},
                         {f"ywc_dmg.{n}" for n in range(1120, 1126)})
        self.assertEqual(len(school["journals"]), 1)
        metadata = school["inline_delivery_adapter"]
        self.assertEqual(metadata["schema"], "v03.foundation_inline_adapter.v1")
        self.assertEqual(len(metadata["live_phases"]), 1)
        self.assertEqual(len(metadata["branches"]), 6)
        foundation = [arc for arc in current["arcs"] if arc["era"] == "foundation"]
        self.assertEqual(sum(len(arc["inline_delivery_adapter"]["branches"]) for arc in foundation), 29)
        self.assertEqual(sum(len(branch["candidates"]) for arc in foundation
                             for branch in arc["inline_delivery_adapter"]["branches"]), 48)
        validate_inline_catalog(current)
        generated = render_inline_country_adapters(current)
        self.assertIn("ywc_v03_dmg_inline_served_4", generated["effects"])
        for number in range(49, 55):
            self.assertIn(f"ywc_v03_dmg_inline_candidate_{number} =", generated["triggers"])

    def test_renderer_refuses_unregistered_middle_sources(self):
        current = catalog()
        extra = copy.deepcopy(current["arcs"][0])
        extra["era"] = "middle"
        extra["slug"] = "v03_dmg_unregistered_extension"
        current["arcs"].append(extra)
        with self.assertRaisesRegex(ValueError, "unregistered DMG inline arc"):
            render_inline_country_adapters(current)
