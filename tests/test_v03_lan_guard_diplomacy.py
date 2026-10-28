"""Actual guard payment/application and replay safety; no engine influence model."""
import unittest
from pathlib import Path

from clausewitz_harness import parse
from test_v03_lan_foundation import LanRuntimeWorld, EFFECTS_PATH, TRIGGERS_PATH, SHARED_EFFECTS_PATH, SHARED_TRIGGERS_PATH, MODIFIERS_PATH


def world(cash=5000):
    effects = EFFECTS_PATH.read_text(encoding="utf-8-sig") + "\n" + SHARED_EFFECTS_PATH.read_text(encoding="utf-8-sig")
    triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig") + "\n" + SHARED_TRIGGERS_PATH.read_text(encoding="utf-8-sig")
    state = {"gold_reserves": cash, "in_default": False,
             "ywc_v03_lan_v03_lan_river_compacts_started": 1,
             "ywc_lan_river_route": 3, "ywc_lan_river_fee": 1000}
    return LanRuntimeWorld(effects, triggers, {"LAN": state})


def hire_option():
    root = Path(__file__).resolve().parents[1]
    event = dict((key, value) for key, _, value in parse((root / "yongchang_world/events/ywc_v03_country_lan_events.txt").read_text(encoding="utf-8-sig")))["ywc_lan.1014"]
    for key, _, option in event:
        if key == "option" and any(k == "name" and v.endswith(".hire_guards") for k, _, v in option):
            def executable(nodes):
                for node in nodes:
                    if node[0] in ("name", "trigger", "ai_chance"):
                        continue
                    if node[0] == "custom_tooltip":
                        if isinstance(node[2], list):
                            # Remove only tooltip text; retain executable
                            # children in their original command position.
                            yield from executable([n for n in node[2] if n[0] != "text"])
                    else:
                        yield node
            return list(executable(option))
    raise AssertionError("actual generated hire_guards option missing")


class LanGuardDiplomacyTests(unittest.TestCase):
    def test_paid_guard_choice_applies_the_native_diplomatic_capacity_cost(self):
        definitions = dict((key, body) for key, _, body in parse(MODIFIERS_PATH.read_text(encoding="utf-8-sig")))
        values = dict((key, value) for key, _, value in definitions["ywc_lan_guard_backlash"])
        self.assertEqual(float(values.get("country_influence_mult", 0)), -0.1)
        w = world(); w.execute(hire_option(), "LAN")
        self.assertEqual(w.treasury["LAN"], -1000)
        self.assertEqual(w.countries["LAN"]["ywc_lan_river_guards_hired"], 1)
        self.assertEqual(w.countries["LAN"]["ywc_lan_river_pending_event"], 1015)
        self.assertEqual(w.modifiers, [("LAN", {"name": "ywc_lan_guard_backlash", "days": "1095"})])

    def test_replaying_the_same_hire_does_not_refresh_the_penalty_or_charge(self):
        w = world(); w.run("ywc_lan_river_hire_guards", "LAN")
        before = list(w.modifiers)
        w.run("ywc_lan_river_hire_guards", "LAN")
        self.assertEqual(w.treasury["LAN"], -1000)
        self.assertEqual(w.modifiers, before)

    def test_old_generated_option_after_settlement_preserves_the_later_queue(self):
        w = world(); state = w.countries["LAN"]
        w.run("ywc_lan_river_hire_guards", "LAN")
        state.update(ywc_lan_river_settled=1, ywc_v03_lan_v03_lan_river_compacts_settled=1,
                     ywc_lan_river_pending_event=1017)
        w.modifiers.clear()
        w.execute(hire_option(), "LAN")
        self.assertEqual(w.treasury["LAN"], -1000)
        self.assertEqual(state["ywc_lan_river_pending_event"], 1017)
        self.assertEqual(w.modifiers, [])

    def test_unaffordable_guards_create_no_payment_or_diplomatic_penalty(self):
        w = world(999); w.run("ywc_lan_river_hire_guards", "LAN")
        self.assertEqual(w.treasury["LAN"], 0)
        self.assertNotIn("ywc_lan_river_guard_fee_paid", w.countries["LAN"])
        self.assertNotIn("ywc_lan_river_guards_hired", w.countries["LAN"])
        self.assertEqual(w.modifiers, [])

    def test_changed_policy_cannot_be_undone_by_the_old_guard_option(self):
        for helper in ("ywc_lan_river_convert_board", "ywc_lan_river_keep_restricted"):
            for queued in (True, False):
                with self.subTest(changed_policy=helper, next_event_queued=queued):
                    w = world(); state = w.countries["LAN"]
                    w.run(helper, "LAN")
                    if queued:
                        state["ywc_lan_river_pending_event"] = 1015
                    cash = w.treasury["LAN"]
                    w.execute(hire_option(), "LAN")
                    self.assertEqual(w.treasury["LAN"], cash)
                    self.assertEqual(state.get("ywc_lan_river_pending_event"), 1015 if queued else None)
                    self.assertNotIn("ywc_lan_river_guards_hired", state)
                    self.assertEqual(w.modifiers, [])


if __name__ == "__main__":
    unittest.main()
