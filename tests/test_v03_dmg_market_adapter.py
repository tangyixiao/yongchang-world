"""The market card appends to DMG's current source-bound coordinator."""
import copy
import json
from pathlib import Path
import re
import subprocess
import unittest

from tools import v03_inline_delivery_adapter as adapter

ROOT = Path(__file__).resolve().parents[1]
MARKET = "v03_dmg_luzon_border_market"
SCHOOL = "v03_dmg_school_languages"
FOUNDATION = ("v03_dmg_common_subjects", "v03_dmg_two_land_titles", "v03_dmg_court_provinces")


class DmgMarketAdapter(unittest.TestCase):
    def test_market_cannot_steal_a_school_queue_even_with_rehashed_metadata(self):
        import hashlib
        current = json.loads((ROOT / "data/content/v03/countries/dmg.json").read_text("utf-8"))
        market = next(a for a in current["arcs"] if a["slug"] == MARKET)
        journal = market["journals"][0]
        journal["script"] = journal["script"].replace("ywc_dmg_market_pending_event",
                                                     "ywc_dmg_school_pending_event")
        metadata = market["inline_delivery_adapter"]
        metadata["live_phases"][0]["source_script_sha256"] = hashlib.sha256(
            journal["script"].encode("utf-8")).hexdigest()
        proofs = [p for p in metadata["branches"] if p["journal"] == journal["id"]]
        for proof, source in zip(proofs, adapter.source_binding(journal["id"], journal["script"])["branches"]):
            proof["branch_sha256"] = source["sha256"]
            proof["limit_sha256"] = source["limit_sha256"]
            proof["candidates"] = adapter.queue_candidates(source["limit_source"])
        with self.assertRaisesRegex(ValueError, "DMG queue ownership crosses arcs"):
            adapter.validate_inline_catalog(current)

    def test_actual_market_school_and_foundation_are_fair_in_both_native_orders(self):
        from collections import Counter
        from shu_kor_strict_review_runtime import field
        from test_v03_dmg_luzon_market import new_world
        from test_v03_shu_provincial_contract import choose
        current = json.loads((ROOT / "data/content/v03/countries/dmg.json").read_text("utf-8"))
        participants = [current["arcs"][0], current["arcs"][3], current["arcs"][4]]
        mapping = {}
        for arc in current["arcs"]:
            for proof in arc["inline_delivery_adapter"]["branches"]:
                for queue in proof["candidates"]:
                    mapping[len(mapping) + 1] = (arc["slug"], proof["event"], queue["queue"])
        choices = dict(zip(range(1100, 1108), (
            "controlled_market", "pay_setup", "confirm_existing_access", "write_new_hearing",
            "sign_six_month_terms", "pay_review_bill", "retain_controlled", "close_established")))
        choices.update(dict(zip(range(1120, 1126), (
            "bilingual_public", "pay_setup", "confirm_supply", "write_new_appeal",
            "pay_next_term", "close_established"))))
        for order in (participants, list(reversed(participants))):
            with self.subTest(order=[a["slug"] for a in order]):
                world = new_world()
                state = world.countries[world.tag]
                for arc in order:
                    world.refresh(arc)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
                rows = []
                for month in range(1, 121):
                    world.advance_months(1)
                    world.elapsed_months += 1
                    for arc in order:
                        for journal in arc["journals"]:
                            jid = journal["id"]
                            if jid not in world.active[world.tag]:
                                continue
                            world.execute(field(field(world.journal_defs[jid], "on_monthly_pulse"), "effect"), world.tag)
                            while world.events:
                                _, event_id = world.events.pop(0)
                                candidate = int(state["ywc_v03_dmg_inline_reservation"])
                                self.assertEqual(mapping[candidate][:2], (arc["slug"], event_id))
                                queue = mapping[candidate][2]
                                others = {k: v for k, v in state.items() if k.startswith("ywc_dmg_")
                                          and k.endswith("pending_event") and k != queue}
                                event = world.event_defs[event_id]
                                self.assertTrue(world.conditions(field(event, "trigger"), world.tag))
                                world.execute(field(event, "immediate"), world.tag)
                                self.assertNotIn("ywc_v03_dmg_inline_reservation", state)
                                self.assertNotIn(queue, state)
                                self.assertEqual({k: state[k] for k in others}, others)
                                rows.append((arc["slug"], month * 30, event_id, candidate))
                                number = int(event_id.split(".")[1])
                                choose(world, arc, event, choices[number] if number in choices else "defer")
                        world.refresh(arc)
                self.assertEqual(Counter(r[0] for r in rows[:9]), Counter({a["slug"]: 3 for a in participants}))
                self.assertTrue(all(b[1] - a[1] >= 90 for a, b in zip(rows, rows[1:])))
                for slug, numbers, ids in ((MARKET, range(1100, 1108), range(55, 63)),
                                           (SCHOOL, range(1120, 1126), range(49, 55))):
                    own = [r for r in rows if r[0] == slug]
                    self.assertEqual([r[2] for r in own], [f"ywc_dmg.{n}" for n in numbers])
                    self.assertEqual([r[3] for r in own], list(ids))
                self.assertEqual(state["ywc_dmg_market_outcome"], 1)
                self.assertEqual(state["ywc_dmg_school_outcome"], 1)
                self.assertEqual(state["ywc_v03_active_arc_count"], 1)

    def test_market_native_body_is_exact_and_receipts_cannot_alias_school(self):
        self.assertTrue(hasattr(adapter, "_dmg_market_native_receipt"),
                        "the market's exact native body validation is absent")
        receipt = adapter._dmg_market_native_receipt
        for number in range(1100, 1108):
            name = "ywc_v03_dmg_v03_dmg_luzon_border_market_last_event"
            text = ("{ ywc_v03_mark_major_delivered = yes "
                    f"set_variable = {{ name = {name} value = {number - 1099} }} }}")
            event = {"id": f"ywc_dmg.{number}", "immediate": text}
            self.assertEqual(receipt(event), (name, number - 1099))
            for wrong in (
                text.replace(name, "ywc_v03_dmg_v03_dmg_school_languages_last_event"),
                text.replace(f"value = {number - 1099}", "value = 0"),
                text.replace("set_variable", "change_variable"),
                text.replace("= yes", "= no"),
                text[:-1] + "add_treasury = 1 }",
                "{ set_variable = { name = " + name + f" value = {number - 1099} "
                "} ywc_v03_mark_major_delivered = yes }",
            ):
                with self.subTest(number=number, wrong=wrong), self.assertRaises(ValueError):
                    receipt({**event, "immediate": wrong})
        for number in (1099, 1108, 1120):
            with self.assertRaises(ValueError):
                receipt({"id": f"ywc_dmg.{number}", "immediate": "{ ywc_v03_mark_major_delivered = yes }"})

    def test_selector_keeps_school_then_market_ids_in_any_catalog_input_order(self):
        arcs = [{"slug": slug, "era": "foundation"} for slug in FOUNDATION]
        arcs += [{"slug": SCHOOL, "era": "middle"}, {"slug": MARKET, "era": "middle"}]
        for order in (arcs, list(reversed(arcs))):
            self.assertEqual([a["slug"] for a in adapter._dmg_active_arcs({"arcs": order})],
                             [*FOUNDATION, SCHOOL, MARKET])
        for extra in ({"slug": "v03_dmg_unregistered_market", "era": "middle"},
                      {"slug": MARKET, "era": "late"}, {"slug": MARKET, "era": "middle"}):
            with self.assertRaises(ValueError):
                adapter._dmg_active_arcs({"arcs": [*arcs, extra]})

    def test_actual_market_has_eight_native_events_two_phases_and_appended_candidates(self):
        # Read generated source first: this is a true missing-content RED even
        # while the bounded country author owns an unbound catalog draft.
        event_source = (ROOT / "yongchang_world/events/ywc_v03_country_dmg_events.txt").read_text("utf-8-sig")
        generated = set(re.findall(r"(?m)^(ywc_dmg\.110[0-7])\s*=\s*\{", event_source))
        self.assertEqual(generated, {f"ywc_dmg.{n}" for n in range(1100, 1108)},
                         "the approved market's generated native events are missing")
        catalog = json.loads((ROOT / "data/content/v03/countries/dmg.json").read_text("utf-8"))
        matches = [a for a in catalog["arcs"] if a["slug"] == MARKET]
        self.assertEqual(len(matches), 1)
        market = matches[0]
        self.assertEqual(market["era"], "middle")
        self.assertEqual(market["depends_on"], [])
        self.assertEqual([j["id"] for j in market["journals"]],
                         ["ywc_je_v03_dmg_luzon_market_terms", "ywc_je_v03_dmg_luzon_market_review"])
        metadata = market["inline_delivery_adapter"]
        self.assertEqual(metadata["schema"], "v03.foundation_inline_adapter.v1")
        self.assertEqual(len(metadata["branches"]), 8)
        active = adapter._dmg_active_arcs(catalog)
        self.assertEqual(len(active), 6)
        baseline = json.loads(subprocess.run(
            ["git", "show", "9980153ba0edb9c48f141df84c11b2f530ab39b6:data/content/v03/countries/dmg.json"],
            cwd=ROOT, check=True, capture_output=True).stdout.decode("utf-8-sig"))
        self.assertEqual(active[:5], baseline["arcs"], "the original five market-era source bindings are frozen")
        self.assertEqual([a["slug"] for a in active], [*FOUNDATION, SCHOOL, MARKET, "v03_dmg_representative_crown"])
        self.assertEqual(sum(len(a["inline_delivery_adapter"]["branches"]) for a in active[:3]), 29)
        self.assertEqual(sum(len(b["candidates"]) for a in active[:3]
                             for b in a["inline_delivery_adapter"]["branches"]), 48)
        self.assertEqual(active[3]["slug"], SCHOOL)
        self.assertEqual(len(active[3]["inline_delivery_adapter"]["branches"]), 6)
        adapter.validate_inline_catalog(catalog)
        result = adapter.render_inline_country_adapters(catalog)
        original = adapter.render_inline_country_adapters({**catalog, "arcs": active[:5]})
        self.assertEqual(len(original["journal_scripts"]), 9)
        self.assertEqual(original["journal_scripts"],
                         {jid: result["journal_scripts"][jid] for jid in original["journal_scripts"]})
        self.assertEqual(len(result["journal_scripts"]), 12)
        self.assertEqual(set(result["journal_scripts"]) - set(original["journal_scripts"]), {
            "ywc_je_v03_dmg_crown_representation", "ywc_je_v03_dmg_crown_budget",
            "ywc_je_v03_dmg_crown_continuity"})
        self.assertIn("ywc_v03_dmg_inline_served_5", result["effects"])
        for number in range(49, 63):
            self.assertIn(f"ywc_v03_dmg_inline_candidate_{number} =", result["triggers"])
        reordered = copy.deepcopy(catalog)
        reordered["arcs"].reverse()
        self.assertEqual(adapter.render_inline_country_adapters(reordered), result)


if __name__ == "__main__":
    unittest.main()
