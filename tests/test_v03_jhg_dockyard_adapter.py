"""JHG fourth arc must join the real source-bound delivery protocol."""
import copy
import json
from pathlib import Path
import unittest
from tools.v03_jhg_inline_delivery_adapter import annotate_jhg_catalog, render_jhg_inline_country_adapters, validate_jhg_native_helper_source

ROOT=Path(__file__).resolve().parents[1]
SLUG='v03_jhg_dockyard_capital'

class JhgDockyardSourceBinding(unittest.TestCase):
 def test_dockyard_snapshots_capture_real_queue_without_inventing_notice_variables(self):
  c=json.loads((ROOT/'data/content/v03/countries/jhg.json').read_text(encoding='utf-8-sig'))
  result=render_jhg_inline_country_adapters(c)
  source='\n'.join(result['journal_scripts'].values())+'\n'+result['effects']
  self.assertIn('has_variable = ywc_jhg_dock_pending_event',source)
  for suffix in ('_36_notice','_notice_delivery_active','_notice_delivery_12',
                 '_notice_delivery_36','_12_notice_delivered','_36_notice_delivered'):
   with self.subTest(suffix=suffix):
    self.assertNotIn('ywc_jhg_dock'+suffix,source)
  for stem in ('court','convoy','tribute'):
   self.assertIn('ywc_jhg_'+stem+'_12_notice_delivered',source)

 def test_each_native_receipt_binds_the_exact_popup_scope_operations(self):
  c=json.loads((ROOT/'data/content/v03/countries/jhg.json').read_text(encoding='utf-8-sig'))
  original=next(a for a in c['arcs'] if a['slug']==SLUG)
  for number in range(1100,1108):
   e=next(e for e in original['events'] if e['id']==f'ywc_jhg.{number}')
   immediate=e['immediate']
   self.assertIn('save_scope_value_as = { name = ywc_jhg_dock_popup_epoch value = var:ywc_jhg_dock_popup_epoch }',immediate)
   for before,after in (('add = 1','add = 2'),('value = var:ywc_jhg_dock_popup_epoch','value = 1'),
                        ('save_scope_value_as','save_scope_as')):
    with self.subTest(event=number,mutation=before):
     bad=copy.deepcopy(c);arc=next(a for a in bad['arcs'] if a['slug']==SLUG)
     event=next(e for e in arc['events'] if e['id']==f'ywc_jhg.{number}')
     event['immediate']=immediate.replace(before,after)
     self.assertNotEqual(event['immediate'],immediate)
     with self.assertRaises(ValueError):render_jhg_inline_country_adapters(bad)

 def test_all_eight_actual_senders_and_two_phases_are_bound(self):
  c=json.loads((ROOT/'data/content/v03/countries/jhg.json').read_text(encoding='utf-8-sig'))
  annotated=annotate_jhg_catalog(c)
  prior={a['slug']:a['inline_delivery_adapter'] for a in c['arcs'] if a['slug']!=SLUG}
  for arc in annotated['arcs']:
   if arc['slug'] in prior:self.assertEqual(arc['inline_delivery_adapter'],prior[arc['slug']])
  arc=next(a for a in annotated['arcs'] if a['slug']==SLUG)
  self.assertEqual(len(arc['inline_delivery_adapter']['live_phases']),2)
  self.assertEqual(len(arc['inline_delivery_adapter']['branches']),8)
  result=render_jhg_inline_country_adapters(annotated)
  for n in range(1100,1108):
   with self.subTest(event=n):
    event=f'ywc_jhg.{n}'
    self.assertTrue(result.get('event_hooks',{}).get(event),f'missing event dispatch {event}')
    self.assertTrue(result.get('ack_hooks',{}).get(event),f'missing event ACK {event}')

 def test_rehashed_dockyard_sender_cannot_consume_an_old_arc_queue(self):
  c=json.loads((ROOT/'data/content/v03/countries/jhg.json').read_text(encoding='utf-8-sig'))
  c=copy.deepcopy(c)
  arc=next(a for a in c['arcs'] if a['slug']==SLUG)
  journal=arc['journals'][0]
  journal['script']=journal['script'].replace('ywc_jhg_dock_pending_event','ywc_jhg_court_pending_event')
  rebound=annotate_jhg_catalog(c)
  with self.assertRaises(ValueError):render_jhg_inline_country_adapters(rebound)

 def test_rehashed_dockyard_journal_cannot_add_unapproved_business_effect(self):
  c=json.loads((ROOT/'data/content/v03/countries/jhg.json').read_text(encoding='utf-8-sig'))
  arc=next(a for a in c['arcs'] if a['slug']==SLUG)
  journal=arc['journals'][0]
  before=journal['script']
  journal['script']=before.replace('ywc_jhg_dock_claim = yes',
    'ywc_jhg_dock_claim = yes set_variable = { name = ywc_jhg_dock_fake value = 1 }',1)
  self.assertNotEqual(journal['script'],before)
  rebound=annotate_jhg_catalog(c)
  with self.assertRaises(ValueError):render_jhg_inline_country_adapters(rebound)

 def test_actual_helper_sources_accept_only_pinned_old_and_new_definitions(self):
  base=ROOT/'yongchang_world/common'
  effects=(base/'scripted_effects/ywc_v03_jhg_effects.txt').read_text(encoding='utf-8-sig')
  triggers=(base/'scripted_triggers/ywc_v03_jhg_triggers.txt').read_text(encoding='utf-8-sig')
  validate_jhg_native_helper_source(effects,triggers)
  damaged=effects.replace('ywc_jhg_dock_claim = {','ywc_jhg_dock_unregistered = {',1)
  self.assertNotEqual(damaged,effects)
  with self.assertRaises(ValueError):validate_jhg_native_helper_source(damaged,triggers)

if __name__=='__main__':unittest.main()
