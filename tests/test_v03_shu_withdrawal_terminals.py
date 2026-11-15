"""A withdrawn SHU fiscal JE must fail exclusively while retaining its result."""
import unittest
from shu_kor_strict_review_runtime import Strict, facts, field


PREFIX = ((1000, "pilot_state_sichuan"), (1001, "local_register"),
          (1002, "time_limited_exemption"), (1003, "budget_queue"),
          (1004, "local_mediation"), (1005, "refuse_private_advance"),
          (1006, "settle_as_provincial"))


def apply_choice(world, arc, number, key, refresh=True):
    event = world.deliver(arc, f"ywc_shu.{number}")
    option = next(value for name, _, value in event
                  if name == "option" and field(value, "name").endswith("." + key))
    assert world.conditions(field(option, "trigger"), world.tag)
    world.execute([node for node in option
                   if node[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")],
                  world.tag)
    if refresh:
        world.refresh(arc)


class ShuFiscalWithdrawalTerminalTests(unittest.TestCase):
    def test_both_real_withdrawal_points_fail_without_satisfying_complete(self):
        for number, key in ((1007, "withdraw_before_execution"), (1009, "withdraw_as_breach")):
            with self.subTest(event=number):
                world = Strict("shu")
                world.countries[world.tag] = facts()
                arc = world.cat["arcs"][0]
                for no, choice in PREFIX:
                    apply_choice(world, arc, no, choice)
                if number == 1009:
                    apply_choice(world, arc, 1007, "provincial_retention")
                    apply_choice(world, arc, 1008, "review_in_peace")
                apply_choice(world, arc, number, key, refresh=False)
                state = world.countries[world.tag]
                journal = world.journal_defs["ywc_je_v03_shu_fiscal_settlement"]
                self.assertTrue(world.conditions(field(journal, "fail"), world.tag))
                self.assertFalse(world.conditions(field(journal, "complete"), world.tag))
                self.assertEqual(state["ywc_shu_register_resolved"], 1)
                self.assertEqual(state["ywc_v03_shu_v03_shu_fiscal_register_outcome"], 4)
                world.refresh(arc)
                self.assertEqual(world.history[world.tag]["ywc_je_v03_shu_fiscal_settlement"], "failed")
                self.assertEqual(state["ywc_v03_active_arc_count"], 0)

    def test_real_provincial_success_still_completes_and_preserves_its_right(self):
        world = Strict("shu")
        world.countries[world.tag] = facts()
        arc = world.cat["arcs"][0]
        for no, choice in (*PREFIX, (1007, "provincial_retention"),
                           (1008, "review_in_peace"), (1009, "confirm_provincial_share")):
            apply_choice(world, arc, no, choice)
        state = world.countries[world.tag]
        journal = world.journal_defs["ywc_je_v03_shu_fiscal_settlement"]
        self.assertTrue(world.conditions(field(journal, "complete"), world.tag))
        self.assertFalse(world.conditions(field(journal, "fail"), world.tag))
        self.assertEqual(state["ywc_shu_local_audit_right"], 1)
        self.assertEqual(state["ywc_v03_shu_v03_shu_fiscal_register_outcome"], 2)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
