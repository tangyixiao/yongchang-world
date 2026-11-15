"""Earned court discounts cannot override the explicit finite review price."""
import copy
import unittest

from test_v03_kor_provincial_revenue import new_world, P, choose, option_legal
from test_v03_kor_revenue_cross_era import (
    history_world, set_current_route_facts, match_current_cash, revenue_open,
    revenue_sign, native_play, native_month, native_deliver,
)
from test_v03_shu_provincial_contract import force_option


def review_popup(*, earned_court, finite):
    world = history_world("court") if earned_court else new_world("central")
    state = world.countries[world.tag]
    if earned_court:
        assert state["ywc_v03_kor_v03_kor_military_accounts_outcome"] == 1
        assert state["ywc_kor_translation_contract_paid_months"] == 12
        assert state["ywc_kor_veteran_contract_paid_months"] == 12
        set_current_route_facts(world, "central")
    match_current_cash(world)
    arc = revenue_open(world, "central")
    if finite:
        native_play(world, arc, 1102, "narrow_finite")
        native_play(world, arc, 1103, "sign")
    else:
        revenue_sign(world, arc)
    native_month(world, arc, 6)
    event = native_deliver(world, arc, 1104)
    assert state[P + "mode"] == 2
    assert state[P + "target"] == (2 if finite else 1)
    assert state[P + "budget"] == 1000
    return world, arc, event


class KorRevenueFinitePricing(unittest.TestCase):
    def assert_boundary_payment(self, world, arc, event, cash, price):
        state = world.countries[world.tag]
        match_current_cash(world, cash)
        self.assertEqual(option_legal(world, event, "pay_review"), cash >= price)
        before = copy.deepcopy((world.countries, world.treasury, world.active, world.history))
        if cash < price:
            force_option(world, event, "pay_review")
            self.assertEqual((world.countries, world.treasury, world.active, world.history), before)
            self.assertNotIn(P + "review_paid", state)
        else:
            treasury = world.treasury[world.tag]
            choose(world, arc, event, "pay_review")
            self.assertEqual(state[P + "review_paid_amount"], price)
            self.assertEqual(world.treasury[world.tag] - treasury, -price)
            self.assertEqual(state["gold_reserves"] + world.treasury[world.tag], cash - price)

    def test_finite_central_review_is_half_budget_with_or_without_earned_court(self):
        for earned_court in (False, True):
            for cash in (499, 500):
                with self.subTest(earned_court=earned_court, cash=cash):
                    world, arc, event = review_popup(earned_court=earned_court, finite=True)
                    self.assert_boundary_payment(world, arc, event, cash, 500)

    def test_full_central_review_keeps_real_court_discount_and_normal_price(self):
        for earned_court, price in ((True, 1000), (False, 1500)):
            for cash in (price - 1, price):
                with self.subTest(earned_court=earned_court, cash=cash):
                    world, arc, event = review_popup(earned_court=earned_court, finite=False)
                    self.assert_boundary_payment(world, arc, event, cash, price)


if __name__ == "__main__":
    unittest.main()
