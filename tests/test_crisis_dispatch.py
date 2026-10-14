"""Execute shipped crisis pulses and journal effects; clocks advance explicitly."""
import json
from pathlib import Path
import unittest

from clausewitz_harness import PulseWorld, parse


ROOT = Path(__file__).resolve().parents[1]
EFFECTS = (ROOT / "yongchang_world/common/scripted_effects/ywc_campaign_effects.txt").read_text("utf-8-sig")
JOURNALS = dict((key, body) for key, _, body in parse(
    (ROOT / "yongchang_world/common/journal_entries/ywc_large_campaign_crises.txt").read_text("utf-8-sig")))
CATALOG = json.loads((ROOT / "data/content/large_campaign_event_catalog.json").read_text("utf-8-sig"))
COOLDOWN = "ywc_campaign_crisis_card_cooldown"


class CrisisDispatchTest(unittest.TestCase):
    def world(self, number=2, stage=2, age=0):
        tags = {tag for config in CATALOG["crises"].values() for tag in config["participants"]}
        tags.update(("KOR", "SPA", "HOL", "LAN"))
        world = PulseWorld(EFFECTS, {tag: {} for tag in tags})
        self.start(world, number, stage, age)
        return world

    def start(self, world, number, stage, age=0):
        holder = CATALOG["crises"][str(number)]["holder"]
        world.countries[holder].update({f"ywc_campaign_crisis{number}_stage": stage,
                                      f"ywc_campaign_crisis{number}_age": age})
        return world.countries[holder]

    def pulse(self, world, number, journal=False):
        config = CATALOG["crises"][str(number)]
        if journal:
            monthly = next(body for key, _, body in JOURNALS[config["journal"]] if key == "on_monthly_pulse")
            effects = next(body for key, _, body in monthly if key == "effect")
            world.execute(effects, config["holder"])
        else:
            world.run(config["journal"].replace("ywc_je_crisis_", "ywc_crisis_pulse_"), config["holder"])

    def test_same_recipient_is_reserved_across_holders_in_both_orders(self):
        for order in ((2, 3), (3, 2)):
            with self.subTest(order=order):
                world = self.world()
                self.start(world, 3, 2)
                for number in order:
                    self.pulse(world, number)
                self.assertEqual(world.events, [("SHU", f"ywc_crisis.{8 if order[0] == 2 else 14}")])
                self.assertEqual(world.countries["SHU"][COOLDOWN], 1)
                for _ in range(2):
                    world.advance_months()
                    self.pulse(world, order[1])
                    self.assertEqual(len(world.events), 1)
                world.advance_months()
                self.pulse(world, order[1])
                self.assertEqual(len(world.events), 2)

    def test_all_catalog_stages_wait_on_actual_recipient_then_deliver_once(self):
        for event in CATALOG["events"]:
            if "crisis" not in event:
                continue
            number, stage = event["crisis"], event["stage"]
            recipient = "SPA" if event["answerer"] == "ESP" else event["answerer"]
            with self.subTest(event=event["id"]):
                world = self.world(number, stage, 11)
                holder = CATALOG["crises"][str(number)]["holder"]
                state = world.countries[holder]
                world.countries[recipient][COOLDOWN] = 1
                for _ in range(15):
                    self.pulse(world, number)
                self.assertEqual(world.events, [])
                self.assertEqual(state[f"ywc_campaign_crisis{number}_stage"], stage)
                self.assertEqual(state[f"ywc_campaign_crisis{number}_age"], 11)
                self.assertNotIn(f"ywc_campaign_crisis{number}_asked", state)
                self.assertNotIn(f"ywc_campaign_crisis{number}_s{stage}_answer", state)
                del world.countries[recipient][COOLDOWN]
                self.pulse(world, number)
                self.assertEqual(world.events, [(recipient, event["id"])])
                self.assertEqual(state[f"ywc_campaign_crisis{number}_age"], 0)
                self.pulse(world, number)
                self.assertEqual(len(world.events), 1)

    def test_timeout_counts_twelve_subsequent_pulses_after_delivery(self):
        world = self.world(age=11)
        state = world.countries["NQG"]
        world.countries["SHU"][COOLDOWN] = 1
        for _ in range(15):
            self.pulse(world, 2)
        del world.countries["SHU"][COOLDOWN]
        self.pulse(world, 2)
        for age in range(1, 12):
            self.pulse(world, 2)
            self.assertEqual(state["ywc_campaign_crisis2_stage"], 2)
            self.assertEqual(state["ywc_campaign_crisis2_age"], age)
        self.pulse(world, 2)
        self.assertEqual(state["ywc_campaign_crisis2_stage"], 3)
        self.assertEqual(state["ywc_campaign_crisis2_s2_answer"], 0)

    def test_absent_recipient_skips_immediately_even_with_cooled_holder(self):
        world = self.world(age=11)
        del world.countries["SHU"]
        world.countries["NQG"][COOLDOWN] = 1
        self.pulse(world, 2, journal=True)
        state = world.countries["NQG"]
        self.assertEqual(world.events, [])
        self.assertEqual(state["ywc_campaign_crisis2_stage"], 3)
        self.assertEqual(state["ywc_campaign_crisis2_s2_answer"], 0)
        self.assertNotIn("ywc_campaign_crisis2_asked", state)

    def test_journals_do_not_tick_or_gate_on_holder_cooldowns(self):
        for number in range(1, 6):
            with self.subTest(crisis=number):
                world = self.world(number, 2)
                holder = CATALOG["crises"][str(number)]["holder"]
                world.countries[holder].update({COOLDOWN: 1, "ywc_campaign_dialogue_cooldown": 99})
                self.pulse(world, number, journal=True)
                self.assertEqual(len(world.events), 1)
                self.assertEqual(world.countries[holder]["ywc_campaign_dialogue_cooldown"], 99)
                self.assertEqual(world.countries[holder][COOLDOWN], 1)

    def test_answered_stages_advance_during_holder_cooldown(self):
        for number in range(1, 6):
            world = self.world(number, 1)
            holder = CATALOG["crises"][str(number)]["holder"]
            self.pulse(world, number, journal=True)
            state = world.countries[holder]
            state.update({COOLDOWN: 1, "ywc_campaign_dialogue_cooldown": 99,
                          f"ywc_campaign_crisis{number}_s1_answer": 1})
            self.pulse(world, number, journal=True)
            self.assertEqual(state[f"ywc_campaign_crisis{number}_stage"], 2)

    def test_answers_only_write_answer_and_preserve_delivery_expiry(self):
        world = self.world()
        self.pulse(world, 2)
        world.advance_months(2)
        body = EFFECTS[EFFECTS.index("ywc_campaign_crisis_answer = {"):]
        body = body[:body.index("\n}") + 2]
        body = body.replace("$CRISIS$", "2").replace("$STAGE$", "2").replace("$ANSWER$", "1")
        answer_effect = parse(body)[0][2]
        world.execute(answer_effect, "SHU")
        self.assertEqual(world.countries["SHU"]["ywc_campaign_crisis2_s2_answer"], 1)
        self.assertNotIn("ywc_campaign_dialogue_cooldown", world.countries["SHU"])
        world.advance_months()
        self.assertNotIn(COOLDOWN, world.countries["SHU"])

    def test_maritime_priority_recipient_waits_without_rerouting(self):
        for recipient, absent in (("SPA", ()), ("HOL", ("SPA",)), ("LAN", ("SPA", "HOL"))):
            world = self.world(4, 3)
            for tag in absent:
                del world.countries[tag]
            world.countries[recipient][COOLDOWN] = 1
            self.pulse(world, 4)
            self.assertEqual(world.events, [])
            del world.countries[recipient][COOLDOWN]
            self.pulse(world, 4)
            self.assertEqual(world.events, [(recipient, "ywc_crisis.21")])

    def test_settled_pulses_are_idempotent(self):
        for number in range(1, 6):
            world = self.world(number, 6)
            holder = CATALOG["crises"][str(number)]["holder"]
            state = world.countries[holder]
            state[f"ywc_campaign_crisis{number}_outcome"] = 2
            before = dict(state)
            for _ in range(15):
                self.pulse(world, number, journal=True)
            self.assertEqual(world.events, [])
            self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
