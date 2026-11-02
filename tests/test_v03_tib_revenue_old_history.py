"""Actual completed TIB sources must be proved, not inferred from outcome alone."""
import unittest
from tests import test_v03_tib_revenue_legacy_contract as prior

class TibRevenueOldHistoryProof(unittest.TestCase):
    def test_actual_second_route_histories_remain_eligible(self):
        driver,arcs=prior.old_driver()
        for prefix,slug,helper in (
            ('register','v03_tib_service_register','ywc_tib_revenue_has_service_ledger'),
            ('grain','v03_tib_grain_credit','ywc_tib_revenue_has_grain_ledger')):
            with self.subTest(source=prefix):
                world,paid=prior.complete_old_history(driver,arcs[slug],prefix,route=2)
                self.assertEqual(paid,150)
                self.assertTrue(world.conditions([(helper,'=','yes')],'TIB'))

    def test_each_real_source_rejects_zero_and_missing_earned_records(self):
        driver,arcs=prior.old_driver()
        for prefix,slug,helper in (
            ('register','v03_tib_service_register','ywc_tib_revenue_has_service_ledger'),
            ('grain','v03_tib_grain_credit','ywc_tib_revenue_has_grain_ledger')):
            with self.subTest(source=prefix):
                world,_=prior.complete_old_history(driver,arcs[slug],prefix)
                state=world.countries['TIB']
                self.assertTrue(world.conditions([(helper,'=','yes')],'TIB'))
                fields=(f'ywc_v03_tib_{slug}_started',f'ywc_v03_tib_{slug}_settled',
                        f'ywc_v03_tib_{slug}_outcome',f'ywc_tib_{prefix}_paid',
                        f'ywc_tib_{prefix}_route',f'ywc_tib_{prefix}_route_cost_1',
                        f'ywc_tib_{prefix}_implementation_complete',f'ywc_tib_{prefix}_six_months_complete')
                for name in fields:
                    for bad in (0,None):
                        with self.subTest(source=prefix,field=name,bad=bad):
                            original=state[name]
                            try:
                                if bad is None:del state[name]
                                else:state[name]=bad
                                self.assertFalse(world.conditions([(helper,'=','yes')],'TIB'))
                            finally:state[name]=original
                self.assertTrue(world.conditions([(helper,'=','yes')],'TIB'))

if __name__=='__main__':unittest.main()
