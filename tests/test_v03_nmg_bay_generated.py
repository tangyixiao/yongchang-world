"""Non-skipping assertions against the actual authored and generated NMG card."""
import json
from collections import Counter
from pathlib import Path
import re
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools import v03_inline_delivery_adapter as adapter


ROOT = Path(__file__).resolve().parents[1]
BASE = "2595db93ba5a4f213f7c52210d311d5aa11a23cc"
SLUG = "v03_nmg_bay_ports"
JES = ("ywc_je_v03_nmg_bay_charter", "ywc_je_v03_nmg_bay_operations")
QUEUE = "ywc_nmg_bay_pending_event"


class NmgBayGeneratedContract(unittest.TestCase):
    def test_actual_bind_preserves_four_cards_and_excludes_foreign_reply_from_delivery(self):
        prior = json.loads(subprocess.run(["git", "show", BASE + ":data/content/v03/countries/nmg.json"],
                                         cwd=ROOT, check=True, capture_output=True).stdout.decode("utf-8-sig"))
        catalog = json.loads((ROOT / "data/content/v03/countries/nmg.json").read_text("utf-8-sig"))
        rows = [arc for arc in catalog["arcs"] if arc.get("slug") == SLUG]
        self.assertEqual(len(rows), 1, "actual authored bay card is not present")
        arc = rows[0]
        self.assertEqual([a for a in catalog["arcs"] if a.get("slug") != SLUG], prior["arcs"])
        self.assertEqual([j["id"] for j in arc["journals"]], list(JES))
        self.assertEqual([e["id"] for e in arc["events"]], [f"ywc_nmg.{n}" for n in range(1100, 1109)])
        proofs = arc["inline_delivery_adapter"]["branches"]
        self.assertEqual([p["event"] for p in proofs], [f"ywc_nmg.{n}" for n in range(1100, 1108)])
        self.assertEqual([sum(p["journal"] == jid for p in proofs) for jid in JES], [4, 4])
        self.assertEqual(arc["inline_delivery_adapter"]["direct_adds"], [])
        for n, proof in zip(range(1100, 1108), proofs):
            self.assertEqual(proof["candidates"], [{"queue": QUEUE, "kind": "normal", "mode": "exact", "value": n}])
        adapter.validate_inline_catalog(catalog)
        rendered = adapter.render_inline_country_adapters(catalog)
        self.assertEqual(len(rendered["journal_scripts"]), 10)
        self.assertNotIn("ywc_nmg.1108", rendered.get("event_hooks", {}))
        self.assertNotIn("ywc_nmg.1108", rendered.get("ack_hooks", {}))
        for candidate in range(45, 53):
            self.assertIn(f"ywc_v03_nmg_inline_candidate_{candidate} =", rendered["triggers"])
        events = (ROOT / "yongchang_world/events/ywc_v03_country_nmg_events.txt").read_text("utf-8-sig")
        self.assertEqual(set(re.findall(r"(?m)^(ywc_nmg\.110[0-8])\s*=\s*\{", events)),
                         {f"ywc_nmg.{n}" for n in range(1100, 1109)})

    def test_bay_school_and_land_share_first_nine_native_turns_under_cap(self):
        from shu_kor_strict_review_runtime import field
        from test_v03_nmg_bay_protocol import world_and_arc
        from test_v03_nmg_school_adapter import native_choice_is_legal

        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                world, bay = world_and_arc()
                arcs = {arc["slug"]: arc for arc in world.cat["arcs"]}
                participants = [arcs["v03_nmg_land_arbitration"], arcs["v03_nmg_parish_school"], bay]
                for arc in participants:
                    world.refresh(arc)
                state = world.countries["NMG"]
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
                world.refresh(arcs["v03_nmg_bilingual_office"])
                self.assertNotIn(arcs["v03_nmg_bilingual_office"]["journals"][0]["id"], world.active["NMG"])
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
                mapping = {}
                for arc in adapter._nmg_active_arcs(world.cat):
                    for proof in arc["inline_delivery_adapter"]["branches"]:
                        for queue in proof["candidates"]:
                            mapping[len(mapping) + 1] = (arc["slug"], proof["event"], queue["queue"])
                choices = {1000: "mixed", 1001: "rule_register", 1002: "finish_survey",
                           1110: "joint_school", 1111: "pay_register", 1112: "hire_academic",
                           1100: "public_port", 1101: "local_terms", 1102: "pay_charter"}
                handled, deliveries = set(world._school_handled_jobs), []
                order = list(reversed(participants)) if reverse else participants
                for _ in range(120):
                    world.advance_months(1)
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
                                own_queue = mapping[candidate][2]
                                others = {k: v for k, v in state.items() if k.startswith("ywc_nmg_")
                                          and k.endswith(("_pending", "_pending_event")) and k != own_queue}
                                self.assertTrue(world.display_job(job))
                                handled.add(job.serial)
                                self.assertNotIn(own_queue, state)
                                self.assertEqual({k: state[k] for k in others}, others)
                                deliveries.append((arc["slug"], world.day, job.event_id))
                                number = int(job.event_id.rsplit(".", 1)[1])
                                if len(deliveries) < 9:
                                    key = choices[number]
                                    self.assertTrue(native_choice_is_legal(world, job, key))
                                    world.choose_job(job, key)
                        world.refresh(arc)
                        if len(deliveries) >= 9:
                            break
                    if len(deliveries) >= 9:
                        break
                self.assertEqual(len(deliveries), 9)
                self.assertEqual(Counter(item[0] for item in deliveries), Counter({a["slug"]: 3 for a in participants}))
                self.assertTrue(all(later[1] - earlier[1] >= 90 for earlier, later in zip(deliveries, deliveries[1:])))


if __name__ == "__main__":
    unittest.main()
