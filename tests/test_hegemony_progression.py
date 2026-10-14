import json
from pathlib import Path
import unittest

from clausewitz_harness import PulseWorld, parse
from tools import build_hegemony_content as builder
from tools import build_campaign_content as campaign_builder


ROOT = Path(__file__).resolve().parents[1]
HEGEMONY = (ROOT / "yongchang_world/common/scripted_effects/ywc_hegemony_effects.txt").read_text("utf-8-sig")
CAMPAIGN = (ROOT / "yongchang_world/common/scripted_effects/ywc_campaign_effects.txt").read_text("utf-8-sig")
CATALOG = builder.load_catalog(ROOT)
PARTICIPANTS = [row["tag"] for row in CATALOG["participants"]]


class HegemonyProgressionTest(unittest.TestCase):
    def world(self):
        countries = {tag: {} for tag in ["SHU", *PARTICIPANTS]}
        countries["SHU"] = {"ywc_hegemony_stage": 1, "ywc_hegemony_age": 0}
        return PulseWorld(HEGEMONY, countries)

    def test_initialized_clock_does_not_block_proclamation(self):
        world = self.world()
        world.run("ywc_hegemony_pulse")
        self.assertEqual(world.events, [("SHU", "ywc_hegemony.1")])

    def test_summons_are_quarterly_in_the_catalog_order(self):
        world = self.world()
        world.countries["SHU"].update(ywc_hegemony_stage=2)
        for month in range(1, 28):
            world.run("ywc_hegemony_pulse")
            self.assertEqual(len(world.events), month // 3, month)
        self.assertEqual(world.events, [(row["tag"], f"ywc_{row['short']}.200") for row in CATALOG["participants"]])

    def test_unanswered_court_events_finish_with_a_bounded_stalled_order(self):
        world = self.world()
        for _ in range(140):
            world.run("ywc_hegemony_pulse")
        self.assertEqual(world.countries["SHU"].get("ywc_hegemony_outcome"), 2)
        self.assertEqual([event for tag, event in world.events if tag == "SHU"],
                         [f"ywc_hegemony.{number}" for number in range(1, 7)])
        self.assertIn("ywc_hegemony_stalled", [fields["name"] for _, fields in world.modifiers])
        before = list(world.events)
        world.run("ywc_hegemony_pulse")
        self.assertEqual(world.events, before)

    def test_counts_follow_current_living_countries_not_old_answers(self):
        world = self.world()
        court = world.countries["SHU"]
        court.update(ywc_hegemony_compliant=99, ywc_hegemony_defiant=99, ywc_hegemony_hedging=99)
        world.countries["JHG"]["ywc_tribute_answer"] = 1
        world.countries["KOR"]["ywc_tribute_answer"] = 3
        world.countries["NMG"]["ywc_tribute_answer"] = 2
        world.run("ywc_hegemony_pulse")
        self.assertEqual([court[f"ywc_hegemony_{name}"] for name in ("compliant", "defiant", "hedging")], [1, 1, 1])
        del world.countries["KOR"]
        world.run("ywc_hegemony_pulse")
        self.assertEqual(court["ywc_hegemony_defiant"], 0)

    def test_legacy_stage_eight_closes_with_stalled_aftermath(self):
        world = self.world()
        world.countries["SHU"]["ywc_hegemony_stage"] = 8
        world.run("ywc_hegemony_pulse")
        self.assertEqual(world.countries["SHU"].get("ywc_hegemony_outcome"), 2)

    def test_start_accepts_any_four_surviving_participants(self):
        for tags in (PARTICIPANTS[:4], PARTICIPANTS[-4:]):
            world = PulseWorld("", {tag: {} for tag in ["SHU", *tags]})
            world.countries["SHU"].update(ywc_heritage_legitimacy=60, ywc_campaign_shu_c3_outcome=1)
            script = campaign_builder.HEGEMONY_START_BLOCK.format(gate=campaign_builder.HEGEMONY_START_OUTCOME_GATES["shu_ch3"])
            world.execute(parse(script), "SHU")
            self.assertEqual(len(world.journals), 1, tags)
            world.execute(parse(script), "SHU")
            self.assertEqual(len(world.journals), 1, "the second qualifying hook must not reopen the order")


class CrisisProgressionTest(unittest.TestCase):
    def test_each_initialized_crisis_dispatches_and_advances_on_an_answer(self):
        names = ["suzerainty", "blackwater", "caravan", "maritime", "california"]
        declared = {key for key, _, _ in parse(CAMPAIGN)}
        pulses = [name for name in declared if name.startswith("ywc_crisis_pulse_")]
        self.assertEqual(len(pulses), len(names))
        # Match crisis prefixes from each pulse's actual clock declaration.
        import re
        for name in sorted(pulses):
            body = CAMPAIGN[CAMPAIGN.index(name + " = {"):]
            number = int(re.search(r"name = ywc_campaign_crisis(\d+)_age", body)[1])
            with self.subTest(crisis=number):
                prefix = f"ywc_campaign_crisis{number}"
                world = PulseWorld(CAMPAIGN, {"SHU": {f"{prefix}_stage": 1, f"{prefix}_age": 0}})
                world.run(name)
                self.assertEqual(world.events, [("SHU", f"ywc_crisis.{(number - 1) * 6 + 1}")])
                world.countries["SHU"][f"{prefix}_s1_answer"] = 1
                world.run(name)
                self.assertEqual(world.countries["SHU"][f"{prefix}_stage"], 2)


class TributeTransferTest(unittest.TestCase):
    def test_all_tribute_payments_credit_the_exact_debit(self):
        for event in CATALOG["events"]:
            if event["kind"] != "participant":
                continue
            for choice in event["choices"]:
                paid = -sum(op["amount"] for op in choice["ops"] if op["op"] == "treasury")
                credited = sum(op["amount"] for op in choice["ops"] if op["op"] == "tribute_to_hegemon")
                with self.subTest(event=event["id"], label=choice["label_en"]):
                    self.assertEqual(paid, credited)

    def test_stern_and_lenient_proclamations_change_ai_stance_weights(self):
        proclamation = next(event for event in CATALOG["events"] if event["id"] == "ywc_hegemony.1")
        for policy, choice in enumerate(proclamation["choices"], 1):
            self.assertIn({"op": "edict_policy", "value": policy}, choice["ops"])
        for event in CATALOG["events"]:
            if event.get("slot") == "summon":
                script = "\n".join(builder.render_event(event, CATALOG))
                options = [body for key, _, body in parse(script)[0][2] if key == "option"]
                weights = []
                for policy in (1, 2):
                    world = PulseWorld("", {"SHU": {"ywc_hegemony_edict": policy}, event["tag"]: {}})
                    weights.append([world.ai_weight(next(body for key, _, body in option if key == "ai_chance"), event["tag"]) for option in options])
                self.assertLess(weights[1][0] / sum(weights[1]), weights[0][0] / sum(weights[0]), event["id"])
                self.assertGreater(weights[1][2] / sum(weights[1]), weights[0][2] / sum(weights[0]), event["id"])

    def test_validator_rejects_a_nonconserving_tribute_choice(self):
        catalog = json.loads(json.dumps(CATALOG))
        choice = next(event for event in catalog["events"] if event["id"] == "ywc_jhg.201")["choices"][0]
        next(op for op in choice["ops"] if op["op"] == "tribute_to_hegemon")["amount"] += 1
        with self.assertRaisesRegex(ValueError, "tribute"):
            builder.validate(catalog)

    def test_absent_hegemon_cannot_destroy_the_payers_treasury(self):
        event = next(event for event in CATALOG["events"] if event["id"] == "ywc_jhg.201")
        script = "\n".join(builder.render_event(event, CATALOG))
        option = next(body for key, _, body in parse(script)[0][2] if key == "option")
        payments = [node for node in option if node[0] in ("add_treasury", "if") and (node[0] == "add_treasury" or "add_treasury" in str(node))]
        for countries in ({"JHG": {}}, {"JHG": {}, "SHU": {}}):
            world = PulseWorld("", countries)
            world.execute(payments, "JHG")
            self.assertEqual(sum(world.treasury.values()), 0)
            if "SHU" in countries:
                self.assertLess(world.treasury["JHG"], 0)


if __name__ == "__main__":
    unittest.main()
