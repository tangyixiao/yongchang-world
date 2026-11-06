"""KOR workshop source binding rejects foreign queues and hidden callers."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest
from tools import v03_inline_delivery_adapter as adapter

ROOT=Path(__file__).resolve().parents[1]
BASE='2595db93ba5a4f213f7c52210d311d5aa11a23cc'
SLUG='v03_kor_workshops_credit'


def catalog():return json.loads((ROOT/'data/content/v03/countries/kor.json').read_text(encoding='utf-8-sig'))
def original(path):return subprocess.run(['git','show',BASE+':'+path],cwd=ROOT,check=True,capture_output=True).stdout
def arc(c):return next(a for a in c['arcs'] if a['slug']==SLUG)


class KorWorkshopsAdapter(unittest.TestCase):
    def test_exact_eight_receipts_and_private_four_four_partition(self):
        c=catalog();adapter.validate_inline_catalog(c);a=arc(c)
        self.assertEqual(len(a['inline_delivery_adapter']['branches']),8)
        for index,e in enumerate(a['events'],1):
            self.assertEqual(adapter._kor_workshops_native_receipt(e),('ywc_v03_kor_v03_kor_workshops_credit_last_event',index))
            for old,new in (('add = 1','add = 2'),('value = var:ywc_kor_workshops_popup_epoch','value = 1'),
                            ('save_scope_value_as','save_scope_as')):
                bad=copy.deepcopy(c);mutant=arc(bad)['events'][index-1];mutant['immediate']=mutant['immediate'].replace(old,new)
                with self.subTest(event=e['id'],mutation=old),self.assertRaises(ValueError):adapter.validate_inline_catalog(bad)
        bad=copy.deepcopy(c);arc(bad)['inline_delivery_adapter']['branches'][0]['candidates'][0]['queue']='ywc_kor_public_pending_event'
        with self.assertRaises(ValueError):adapter.validate_inline_catalog(bad)

    def test_existing_five_arcs_and_old_render_are_unchanged(self):
        c=catalog();base=json.loads(original('data/content/v03/countries/kor.json').decode('utf-8-sig'))
        self.assertEqual(c['arcs'][:5],base['arcs'])
        old=types.ModuleType('_workshops_baseline_adapter');sys.modules[old.__name__]=old
        try:
            exec(compile(original('tools/v03_inline_delivery_adapter.py'),old.__name__,'exec'),old.__dict__)
            self.assertEqual(adapter.render_inline_country_adapters(base),old.render_inline_country_adapters(base))
        finally:sys.modules.pop(old.__name__,None)

    def test_existing_kor_helper_prefixes_match_the_immutable_base(self):
        for kind in ('effects','triggers'):
            path=f'yongchang_world/common/scripted_{kind}/ywc_v03_kor_{kind}.txt'
            base=original(path).replace(b'\r\n',b'\n')
            actual=(ROOT/path).read_bytes().replace(b'\r\n',b'\n')
            self.assertTrue(actual.startswith(base),path)

    def test_unknown_arc_and_hidden_direct_journal_caller_are_rejected(self):
        c=catalog();bad=copy.deepcopy(c);bad['arcs'].append({'slug':'unknown','era':'middle'})
        with self.assertRaises(ValueError):adapter.validate_inline_catalog(bad)
        bad=copy.deepcopy(c);a=arc(bad);a['journals'][0]['script']=a['journals'][0]['script'].replace('on_fail = {',
                    'extra = { add_journal_entry = ywc_je_v03_kor_workshops_review } on_fail = {',1)
        # Rebind actual source hashes and branches: metadata may not authorize hidden callers.
        from test_v03_kor_court_public_adapter import bind_sources
        bind_sources(a)
        for i,phase in enumerate(a['inline_delivery_adapter']['live_phases']):phase['live_witness']=f'ywc_v03_kor_inline_live_workshops_{i+1}'
        with self.assertRaises(ValueError):adapter.validate_inline_catalog(bad)

    def test_rebound_source_cannot_borrow_existing_country_queue(self):
        from test_v03_kor_court_public_adapter import bind_sources
        c=catalog()
        for foreign in ('ywc_kor_pending_event','ywc_kor_school_pending_event',
                        'ywc_kor_revenue_pending_event','ywc_kor_public_pending_event'):
            with self.subTest(queue=foreign):
                bad=copy.deepcopy(c);a=arc(bad)
                for j in a['journals']:
                    j['script']=j['script'].replace('ywc_kor_workshops_pending_event',foreign)
                bind_sources(a)
                for i,phase in enumerate(a['inline_delivery_adapter']['live_phases']):phase['live_witness']=f'ywc_v03_kor_inline_live_workshops_{i+1}'
                with self.assertRaises(ValueError):adapter.validate_inline_catalog(bad)
