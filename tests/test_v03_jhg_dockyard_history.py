"""Real JHG prior decisions must genuinely be completed before reuse."""
import unittest
from unittest.mock import patch
from tests import test_v03_jhg_inline_native_story as story
from tests import test_v03_jhg_inline_actual_source as actual

SLUGS={'v03_jhg_court_assembly','v03_jhg_convoy_capacity','v03_jhg_tribute_autonomy'}
_catalog_original=story.catalog

def foundation_only():
    current=_catalog_original()
    return {**current,'arcs':[a for a in current['arcs'] if a['slug'] in SLUGS]}

class JhgDockyardEarnedPriorContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(story,'catalog',side_effect=foundation_only), patch.object(actual,'catalog',side_effect=foundation_only):
            result=story.run_native_route(route=2)
        cls.world=result['world']
        cls.payments=result['payments']

    def test_producers_really_paid_and_completed(self):
        self.assertEqual(self.payments['v03_jhg_court_assembly'],1000)
        self.assertEqual(self.payments['v03_jhg_convoy_capacity'],1500)
        s=self.world.countries['JHG']
        for pre,slug in (('court','v03_jhg_court_assembly'),('convoy','v03_jhg_convoy_capacity')):
            with self.subTest(prior=pre):
                self.assertEqual(s[f'ywc_jhg_{slug}_started'],1)
                self.assertEqual(s[f'ywc_jhg_{slug}_settled'],1)
                self.assertEqual(s[f'ywc_jhg_{slug}_outcome'],1)
                self.assertEqual(s[f'ywc_jhg_{pre}_filing_fee_paid'],1)
                self.assertEqual(s[f'ywc_jhg_{pre}_six_months_complete'],1)

    def test_each_history_reader_rejects_real_earned_receipt_zero_or_absent(self):
        for pre, slug in (('court','v03_jhg_court_assembly'),('convoy','v03_jhg_convoy_capacity')):
            key=f'ywc_jhg_dock_{pre}_source_earned'
            self.assertTrue(key in self.world.triggers, f'missing production prior-history reader {key}')
            self.assertTrue(self.world.conditions([(key,'=','yes')],'JHG'))
            fields=(f'ywc_jhg_{slug}_started',f'ywc_jhg_{slug}_settled',
                    f'ywc_jhg_{slug}_outcome',f'ywc_jhg_{pre}_filing_fee_paid',
                    f'ywc_jhg_{pre}_filing_fee',f'ywc_jhg_{pre}_six_months_complete')
            state=self.world.countries['JHG']
            for name in fields:
                for bad in (None,0):
                    with self.subTest(prior=pre,field=name,bad=bad):
                        original=state[name]
                        try:
                            if bad is None:del state[name]
                            else:state[name]=bad
                            self.assertFalse(self.world.conditions([(key,'=','yes')],'JHG'))
                        finally:
                            state[name]=original
            self.assertTrue(self.world.conditions([(key,'=','yes')],'JHG'))

if __name__=='__main__':unittest.main()
