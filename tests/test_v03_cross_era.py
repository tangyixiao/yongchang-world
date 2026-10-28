"""Two middle nodes consume genuinely played early results and their pilot."""
import copy
import unittest

from shu_kor_strict_review_runtime import M1_PLAN
from test_v03_shu_provincial_contract import (
    new_world, middle_arc, play, choose, force_option, option_legal, month, finish_review,
)
from test_v03_shu_withdrawal_terminals import PREFIX


def early_result(world, kind):
    arc = world.cat["arcs"][0]
    if kind == "central":
        # Actual compensated collection keeps central control without also
        # acquiring the separate local right from a landlord quota compromise.
        for number, choice in M1_PLAN:
            play(world, arc, number, "collect_with_compensation" if number == 1002 else choice)
        expected = 1
    else:
        plan = list(PREFIX)
        if kind == "capped":
            plan[1] = (1001, "cap_old_quota")
            plan[-1] = (1006, "pause_as_legacy")
            plan += [(1007, "cap_old_dues"), (1008, "review_in_peace"),
                     (1009, "keep_capped_quotas")]
            expected = 3
        elif kind == "withdrawn":
            plan += [(1007, "withdraw_before_execution")]
            expected = 4
        else:
            assert kind == "shared"
            plan += [(1007, "provincial_retention"), (1008, "review_in_peace"),
                     (1009, "confirm_provincial_share")]
            expected = 2
        for number, choice in plan:
            play(world, arc, number, choice)
    state = world.countries[world.tag]
    assert state["ywc_v03_shu_v03_shu_fiscal_register_outcome"] == expected
    assert state["ywc_v03_active_arc_count"] == 0
    return expected


def enter_from_prior(world):
    arc = middle_arc(world.cat)
    state = world.countries[world.tag]
    prior = state["ywc_shu_v03_pilot_state"]
    play(world, arc, 1100, "reuse_owned_pilot")
    assert state["ywc_shu_v03_pilot_state"] == prior
    assert state["ywc_shu_v03_prov_pilot_state"] == prior
    return arc


def reach_terms(world, arc):
    play(world, arc, 1101, "provincial_funding")
    play(world, arc, 1102, "provincial_self_raise")
    return world.deliver(arc, "ywc_shu.1104")


class ShuProvincialCrossEra(unittest.TestCase):
    def test_two_actual_early_decisions_change_both_middle_payment_nodes(self):
        observed = {}
        for source in ("central", "shared"):
            world = new_world()
            early_result(world, source)
            arc = enter_from_prior(world)
            before = world.treasury[world.tag]
            play(world, arc, 1101, "central_funding")
            budget_delta = world.treasury[world.tag] - before
            play(world, arc, 1102, "provincial_self_raise")
            before = world.treasury[world.tag]
            play(world, arc, 1104, "write_share_terms")
            observed[source] = (budget_delta, world.treasury[world.tag] - before)
        self.assertEqual(observed, {"central": (-500, -500), "shared": (-1000, 0)})

    def test_central_budget_reads_actual_early_result_at_the_payment_node(self):
        for source, amount in ((None, 1000), ("central", 500), ("shared", 1000)):
            with self.subTest(source=source):
                world = new_world()
                if source:
                    early_result(world, source)
                    arc = enter_from_prior(world)
                else:
                    arc = middle_arc(world.cat)
                    play(world, arc, 1100, "pilot_sichuan")
                state = world.countries[world.tag]
                before = world.treasury[world.tag]
                play(world, arc, 1101, "central_funding")
                self.assertEqual(world.treasury[world.tag] - before, -amount)
                self.assertEqual(state["ywc_shu_prov_central_paid_amount"], amount)
                self.assertEqual(state["ywc_shu_prov_stage"], 1102)

    def test_discount_is_rechecked_after_the_menu_when_only_half_the_cash_remains(self):
        world = new_world()
        early_result(world, "central")
        arc = enter_from_prior(world)
        state = world.countries[world.tag]
        event = world.deliver(arc, "ywc_shu.1101")
        state["gold_reserves"] = 500 - world.treasury[world.tag]
        self.assertTrue(option_legal(world, event, "central_funding"))
        state.pop("ywc_shu_fiscal_outcome_central_audit")
        self.assertFalse(option_legal(world, event, "central_funding"))
        before = copy.deepcopy(state)
        treasury = world.treasury[world.tag]
        force_option(world, event, "central_funding")
        self.assertEqual(state, before)
        self.assertEqual(world.treasury[world.tag], treasury)
        self.assertNotIn("ywc_shu_prov_central_paid", state)

    def test_different_owned_pilot_has_its_own_office_and_no_old_state_discount(self):
        world = new_world()
        early_result(world, "central")
        state = world.countries[world.tag]
        second = copy.deepcopy(state["states"][0])
        second["region"] = "s:STATE_CHONGQING"
        for building in second["buildings"]:
            if building["type"] == "building_government_administration":
                building["occupancy"] = 0.25
        state["states"].append(second)
        arc = middle_arc(world.cat)
        play(world, arc, 1100, "pilot_chongqing")
        self.assertEqual(state["ywc_shu_v03_pilot_state"], 1)
        self.assertEqual(state["ywc_shu_v03_prov_pilot_state"], 2)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_shu_v03_prov_admin_ready"], world.tag))
        self.assertTrue(world.conditions(world.trigger_defs["ywc_shu_v03_prov_limited_ready"], world.tag))
        before = world.treasury[world.tag]
        play(world, arc, 1101, "central_funding")
        self.assertEqual(world.treasury[world.tag] - before, -1000)
        state["states"][0]["owned"] = False
        self.assertTrue(world.conditions(world.trigger_defs["ywc_shu_v03_has_prov_pilot"], world.tag))
        self.assertFalse(world.conditions(world.trigger_defs["ywc_shu_v03_has_pilot_state"], world.tag))

    def test_second_node_uses_real_local_right_but_rebuilds_absent_or_withdrawn_rights(self):
        for source, amount in (("shared", 0), ("central", 500), ("withdrawn", 500), (None, 500)):
            with self.subTest(source=source):
                world = new_world(bare=source is None)
                if source:
                    early_result(world, source)
                    arc = enter_from_prior(world)
                else:
                    arc = middle_arc(world.cat)
                    play(world, arc, 1100, "pilot_sichuan")
                    # Negative control: a bare flag and state ID have no actual
                    # first audit or started source; they cannot waive a fee.
                    world.countries[world.tag]["ywc_shu_local_audit_right"] = 1
                    world.countries[world.tag]["ywc_shu_v03_pilot_state"] = 1
                state = world.countries[world.tag]
                event = reach_terms(world, arc)
                self.assertNotIn("ywc_shu_prov_share_terms", state)
                self.assertEqual(world.conditions(world.trigger_defs["ywc_shu_v03_prior_local_right"],
                                                  world.tag), source == "shared")
                before = world.treasury[world.tag]
                choose(world, arc, event, "write_share_terms")
                self.assertEqual(world.treasury[world.tag] - before, -amount)
                self.assertEqual(state["ywc_shu_prov_terms_pilot"], state["ywc_shu_v03_prov_pilot_state"])
                self.assertEqual(state.get("ywc_shu_prov_meeting_fee_waived", 0), amount == 0)
                self.assertEqual(state.get("ywc_shu_prov_meeting_fee_paid", 0), amount != 0)
                month(world, arc, 6)
                finish_review(world, arc, 2)
                self.assertEqual(state["ywc_shu_prov_outcome"], 2)

    def test_already_granted_waiver_does_not_turn_into_a_new_debt_after_source_record_loss(self):
        world = new_world()
        early_result(world, "shared")
        arc = enter_from_prior(world)
        state = world.countries[world.tag]
        event = reach_terms(world, arc)
        choose(world, arc, event, "write_share_terms")
        before = world.treasury[world.tag]
        state.pop("ywc_shu_local_audit_right", None)
        state["ywc_shu_settlement_mode"] = 3
        self.assertFalse(world.conditions(world.trigger_defs["ywc_shu_v03_prior_local_right"], world.tag))
        self.assertTrue(world.conditions(world.trigger_defs["ywc_shu_v03_prov_share_terms_effective"], world.tag))
        month(world, arc, 6)
        finish_review(world, arc, 2)
        self.assertEqual(world.treasury[world.tag], before)
        self.assertEqual(state["ywc_shu_prov_outcome"], 2)

    def test_earned_budget_discount_is_not_recharged_after_payment(self):
        world = new_world()
        early_result(world, "central")
        arc = enter_from_prior(world)
        state = world.countries[world.tag]
        event = play(world, arc, 1101, "central_funding")
        self.assertEqual(state["ywc_shu_prov_central_paid_amount"], 500)
        before = world.treasury[world.tag]
        state.pop("ywc_shu_fiscal_outcome_central_audit")
        force_option(world, event, "central_funding")
        self.assertEqual(world.treasury[world.tag], before)
        play(world, arc, 1102, "pay_relief_once")
        self.assertEqual(world.treasury[world.tag] - before, -1000)

    def test_all_real_early_outcomes_and_nonparticipation_can_enter_a_peaceful_legacy_continuation(self):
        for source in (None, "central", "shared", "capped", "withdrawn"):
            with self.subTest(source=source):
                world = new_world()
                if source:
                    early_result(world, source)
                    arc = enter_from_prior(world)
                else:
                    arc = middle_arc(world.cat)
                    play(world, arc, 1100, "pilot_sichuan")
                state = world.countries[world.tag]
                before = world.treasury[world.tag]
                play(world, arc, 1101, "keep_old_office")
                play(world, arc, 1102, "push_old_quota")
                play(world, arc, 1105, "confirm_old_quota")
                month(world, arc, 6)
                finish_review(world, arc, 2)
                self.assertEqual(state["ywc_shu_prov_outcome"], 2)
                self.assertEqual(state["ywc_v03_active_arc_count"], 0)
                self.assertEqual(world.treasury[world.tag], before)
