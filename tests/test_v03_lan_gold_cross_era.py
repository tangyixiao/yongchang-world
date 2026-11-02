"""Earn prior LAN policy through actual events before testing the new card."""
import copy
import unittest

from lan_gold_runtime import LanGoldWorld
from lan_public_runtime import LanPublicWorld
from test_v03_lan_beyond_gold import new_world, reach_review, gold_arc, month
from test_v03_lan_company_cross_era import earn_foundation, MINE_PUBLIC
from test_v03_lan_company_public import run_actual_legacy_prelude, ready_for_review, finish_review


class BothLanWorlds(LanGoldWorld, LanPublicWorld):
    """Compose the strict typed-state and existing LAN native-fact subsets."""


class LanGoldRealHistory(unittest.TestCase):
    def earned_mine(self):
        world = new_world()
        world.__class__ = BothLanWorlds
        run_actual_legacy_prelude(world)
        earn_foundation(world, 'mine', MINE_PUBLIC)
        world.refresh(gold_arc())
        return world

    def earned_public(self):
        world = new_world()
        world.__class__ = BothLanWorlds
        state = world.countries[world.tag]
        state['is_subject'] = True
        state['literacy_rate'] = .35
        state['laws'] = ['law_presidential_republic', 'law_poor_laws', 'law_tenant_farmers',
                         'law_multicultural', 'law_census_voting', 'law_per_capita_based_taxation']
        state.update({'modifier:country_voting_power_base_add': 1,
                      'modifier:country_voting_power_wealth_threshold_add': 0,
                      'modifier:country_allow_voting_full_acceptance_bool': True})
        run_actual_legacy_prelude(world)
        arc = ready_for_review(world)
        month(world, arc, 6)
        finish_review(world, arc)
        world.refresh(gold_arc())
        return world

    def test_actual_mine_history_discounts_two_distinct_paid_nodes(self):
        world = self.earned_mine()
        state = world.countries[world.tag]
        self.assertEqual(state['ywc_v03_lan_v03_lan_mine_accounts_outcome'], 1)
        prior_treasury = world.treasury[world.tag]
        self.assertLess(prior_treasury, 0)
        reach_review(world, 'monopoly')
        self.assertEqual(state['ywc_lan_gold_seed_paid_amount'], 500)
        self.assertEqual(state['ywc_lan_gold_basis_paid_amount'], 250)
        self.assertEqual(world.treasury[world.tag] - prior_treasury, -750)
        self.assertEqual(state['ywc_v03_lan_v03_lan_mine_accounts_settled'], 1)

    def test_zero_or_missing_paid_history_cannot_authorize_old_right(self):
        world = self.earned_mine()
        positive = (
            'ywc_v03_lan_v03_lan_mine_accounts_started',
            'ywc_v03_lan_v03_lan_mine_accounts_settled',
            'ywc_lan_mine_established', 'ywc_lan_mine_settled',
            'ywc_lan_mine_filing_fee_paid', 'ywc_lan_mine_reserve_paid',
            'ywc_lan_mine_public_share_taken',
        )
        self.assertTrue(world.condition(('ywc_lan_gold_source_precedent', '=', 'yes'), world.tag))
        for name in positive:
            for zero in (False, True):
                with self.subTest(name=name, zero=zero):
                    mutant = copy.deepcopy(world)
                    state = mutant.countries[mutant.tag]
                    if zero:
                        state[name] = 0
                    else:
                        state.pop(name)
                    self.assertFalse(mutant.condition(('ywc_lan_gold_source_precedent', '=', 'yes'), mutant.tag))

    def test_actual_public_history_changes_two_paid_nodes(self):
        world = self.earned_public()
        state = world.countries[world.tag]
        self.assertEqual(state['ywc_lan_public_outcome'], 1)
        previous = world.treasury[world.tag]
        reach_review(world, 'processing')
        self.assertEqual(state['ywc_lan_gold_seed_paid_amount'], 500)
        self.assertEqual(state['ywc_lan_gold_basis_paid_amount'], 750)
        self.assertEqual(world.treasury[world.tag] - previous, -1250)

    def test_public_right_requires_actual_positive_payments_and_full_outcome(self):
        world = self.earned_public()
        self.assertTrue(world.condition(('ywc_lan_gold_source_leverage', '=', 'yes'), world.tag))
        required = ('ywc_v03_lan_v03_lan_company_public_started',
                    'ywc_v03_lan_v03_lan_company_public_settled',
                    'ywc_v03_lan_v03_lan_company_public_outcome',
                    'ywc_lan_public_outcome', 'ywc_lan_public_charter_paid',
                    'ywc_lan_public_review_paid', 'ywc_lan_public_charter_paid_amount',
                    'ywc_lan_public_review_paid_amount')
        for name in required:
            for zero in (False, True):
                with self.subTest(name=name, zero=zero):
                    mutant = copy.deepcopy(world)
                    state = mutant.countries[mutant.tag]
                    if zero:
                        state[name] = 0
                    else:
                        state.pop(name)
                    self.assertFalse(mutant.condition(('ywc_lan_gold_source_leverage', '=', 'yes'), mutant.tag))
        for outcome in (2, 3, 4):
            with self.subTest(non_full_outcome=outcome):
                mutant = copy.deepcopy(world)
                state = mutant.countries[mutant.tag]
                state['ywc_lan_public_outcome'] = outcome
                state['ywc_v03_lan_v03_lan_company_public_outcome'] = outcome
                self.assertFalse(mutant.condition(('ywc_lan_gold_source_leverage', '=', 'yes'), mutant.tag))


if __name__ == '__main__':
    unittest.main()
