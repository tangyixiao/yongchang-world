"""Generated JHG dockyard sender/receipt/ACK source path, no fabricated queues."""
import copy
import json
from pathlib import Path
import unittest
from tests.clausewitz_harness import parse
from tests.test_v03_jhg_dockyard_state import new_world, province
from tests.test_v03_jhg_dockyard_source_story import field, option
from tests import test_v03_jhg_inline_actual_source as actual
from kor_partner_protocol_runtime import PartnerWorld

ROOT=Path(__file__).resolve().parents[1]

class JhgDockyardGeneratedDispatch(unittest.TestCase):
 def test_each_generated_job_is_inert_after_wait_and_same_event_redelivery(self):
  for target in range(1100,1108):
   with self.subTest(stage=target):
    c=json.loads((ROOT/'data/content/v03/countries/jhg.json').read_text(encoding='utf-8-sig'))
    arc=next(a for a in c['arcs'] if a['slug']=='v03_jhg_dockyard_capital')
    w=new_world()
    w.named_values.update({k:v for k,_,v in parse((ROOT/'yongchang_world/common/script_values/ywc_v03_nmg_values.txt').read_text(encoding='utf-8-sig'))})
    w.modifier_defs.update({k:v for k,_,v in parse((ROOT/'yongchang_world/common/static_modifiers/ywc_v03_jhg_dock_modifiers.txt').read_text(encoding='utf-8-sig'))})
    w.run_script('ywc_v03_initialize_country = yes','JHG')
    w.activate(arc['journals'][0]['id'],'JHG')
    def receive(number):
     for _ in range(60):
      w.pulse(arc)
      for job in w.jobs:
       if job.event_id==f'ywc_jhg.{number}' and job not in w._displayed and w.display_job(job):
        return job
      w.advance_days(30)
     self.fail(f'no actual generated callback for {number}')
    for number in range(1100,target):
     job=receive(number)
     key='route_1' if number==1100 else 'observe' if number==1105 else 'advance'
     self.assertTrue(w.job_options(job)[key]);w.choose_job(job,key)
    old=receive(target)
    action='route_1' if target==1100 else 'observe' if target==1105 else 'close' if target==1107 else 'advance'
    self.assertTrue(w.job_options(old)[action]);w.choose_job(old,'wait')
    before=copy.deepcopy((w.countries,w.treasury,w.modifiers,w.state_modifiers,w.active,w.history))
    w.choose_job(old,action)
    self.assertEqual((w.countries,w.treasury,w.modifiers,w.state_modifiers,w.active,w.history),before)
    current=receive(target)
    self.assertNotEqual(old.serial,current.serial)
    before=copy.deepcopy((w.countries,w.treasury,w.modifiers,w.state_modifiers,w.active,w.history))
    w.choose_job(old,action)
    self.assertEqual((w.countries,w.treasury,w.modifiers,w.state_modifiers,w.active,w.history),before)
    self.assertNotEqual(dict(w._displayed[old])['ywc_jhg_dock_popup_epoch'],dict(w._displayed[current])['ywc_jhg_dock_popup_epoch'])
    self.assertTrue(w.job_options(current)[action]);w.choose_job(current,action)
    self.assertNotEqual((w.countries,w.treasury,w.modifiers,w.state_modifiers,w.active,w.history),before)

 def test_eight_native_events_are_received_and_acknowledged_before_closure(self):
  c=json.loads((ROOT/'data/content/v03/countries/jhg.json').read_text(encoding='utf-8-sig'))
  arc=next(a for a in c['arcs'] if a['slug']=='v03_jhg_dockyard_capital')
  w=new_world(); s=w.countries['JHG']
  w.named_values.update({k:v for k,_,v in parse((ROOT/'yongchang_world/common/script_values/ywc_v03_nmg_values.txt').read_text(encoding='utf-8-sig'))})
  w.modifier_defs.update({k:v for k,_,v in parse((ROOT/'yongchang_world/common/static_modifiers/ywc_v03_jhg_dock_modifiers.txt').read_text(encoding='utf-8-sig'))})
  w.run_script('ywc_v03_initialize_country = yes','JHG')
  w.activate(arc['journals'][0]['id'],'JHG')
  self.assertIn(arc['journals'][0]['id'],w.active['JHG'])
  seen=[]
  for number in range(1100,1108):
   expected=f'ywc_jhg.{number}'
   for _ in range(30):
    w.pulse(arc)
    jobs=[job for job in w.jobs if job.event_id==expected and job not in w._displayed]
    if jobs:
     job=jobs[-1]
     if w.display_job(job):break
    w.advance_days(30)
   else:self.fail(f'actual generated sender never delivered {expected}')
   seen.append(job.event_id)
   self.assertEqual(s['ywc_jhg_dock_last_event'],number)
   self.assertNotIn('ywc_jhg_dock_pending_event',s)
   self.assertNotIn('ywc_v03_jhg_inline_reservation',s)
   self.assertNotIn('ywc_jhg_v03_jhg_dockyard_capital_settled',s)
   key='route_1' if number==1100 else 'observe' if number==1105 else 'close' if number==1107 else 'advance'
   self.assertTrue(w.job_options(job)[key],(expected,key))
   w.choose_job(job,key)
  self.assertEqual(seen,[f'ywc_jhg.{n}' for n in range(1100,1108)])
  self.assertEqual(s['ywc_jhg_v03_jhg_dockyard_capital_outcome'],1)
  self.assertEqual(s['ywc_jhg_v03_jhg_dockyard_capital_settled'],1)
  self.assertIn((s['ywc_jhg_dock_pilot'],'ywc_jhg_dock_state_royal'),w.state_modifiers)

 def test_old_court_and_new_yard_receive_fair_rounds_at_real_cooldown(self):
  # Finish actual pre-v0.3 source first; current yard is an explicit world
  # fact, never an injected queue, completed marker or delivered receipt.
  old=actual._initial_world(); actual._run_legacy_and_initialize(old)
  facts=copy.deepcopy(old.countries['JHG'])
  facts.update(states=[province()],igs=[],laws={'law_landed_voting'},is_at_war=False,in_default=False)
  w=PartnerWorld({'JHG':facts,'CHI':{'states':[],'igs':[]}},tag='jhg')
  w.treasury['JHG']=old.treasury['JHG']
  court='ywc_je_v03_jhg_court_assembly';dock='ywc_je_v03_jhg_dockyard_open'
  w.activate(court,'JHG');w.activate(dock,'JHG')
  self.assertTrue({court,dock}.issubset(set(w.active['JHG'])))
  self.assertEqual((facts['ywc_v03_active_arc_count'],facts['ywc_v03_visible_task_count']),(2,2))
  arc=next(a for a in w.cat['arcs'] if a['slug']=='v03_jhg_dockyard_capital')
  rows=[]
  for _ in range(25):
   w.pulse(arc)
   for job in [j for j in w.jobs if j not in w._displayed]:
    if not w.display_job(job):continue
    key='wait' if job.event_id=='ywc_jhg.1100' else 'defer'
    self.assertTrue(job.event_id=='ywc_jhg.1100' or job.event_id.startswith('ywc_jhg.100'))
    node=option(w.event_defs[job.event_id],key)
    with w._chain(job.recipient,w._displayed[job]):
     self.assertTrue(w.conditions(field(node,'trigger',[]),'JHG'))
    rows.append((job.event_id,w.day));w.choose_job(job,key)
   if len(rows)>=6:break
   w.advance_days(30)
  self.assertEqual(len(rows),6,rows)
  self.assertEqual([event=='ywc_jhg.1100' for event,_ in rows],[False,True,False,True,False,True])
  self.assertTrue(all(later[1]-earlier[1]>=90 for earlier,later in zip(rows,rows[1:])),rows)

 def test_three_real_old_claims_block_new_slot_until_real_withdrawal(self):
  old=actual._initial_world();actual._run_legacy_and_initialize(old)
  facts=copy.deepcopy(old.countries['JHG'])
  facts.update(states=[province()],igs=[],laws={'law_landed_voting'},is_at_war=False,in_default=False)
  w=PartnerWorld({'JHG':facts,'CHI':{'states':[],'igs':[]}},tag='jhg')
  w.treasury['JHG']=old.treasury['JHG']
  roots=['ywc_je_v03_jhg_court_assembly','ywc_je_v03_jhg_convoy_capacity','ywc_je_v03_jhg_tribute_autonomy']
  for name in roots:w.activate(name,'JHG')
  self.assertEqual(set(w.active['JHG']),set(roots))
  self.assertEqual((facts['ywc_v03_active_arc_count'],facts['ywc_v03_visible_task_count']),(3,3))
  dock='ywc_je_v03_jhg_dockyard_open'
  w.activate(dock,'JHG')
  self.assertNotIn(dock,w.active['JHG'])
  self.assertNotIn('ywc_jhg_v03_jhg_dockyard_capital_started',facts)
  arc=next(a for a in w.cat['arcs'] if a['slug']=='v03_jhg_dockyard_capital')
  for _ in range(15):
   w.pulse(arc)
   jobs=[j for j in w.jobs if j not in w._displayed and w.display_job(j)]
   if jobs:break
   w.advance_days(30)
  self.assertTrue(jobs,'an old native opening must be delivered')
  job=jobs[0];node=option(w.event_defs[job.event_id],'withdraw')
  with w._chain(job.recipient,w._displayed[job]):
   self.assertTrue(w.conditions(field(node,'trigger',[]),'JHG'))
  w.choose_job(job,'withdraw')
  self.assertEqual(facts['ywc_v03_active_arc_count'],2)
  w.pulse(arc)
  self.assertIn(dock,w.active['JHG'])
  self.assertEqual((facts['ywc_v03_active_arc_count'],facts['ywc_v03_visible_task_count']),(3,3))

 def test_old_opening_receipt_cannot_spend_after_same_event_is_redelivered(self):
  w=new_world();arc=next(a for a in w.cat['arcs'] if a['slug']=='v03_jhg_dockyard_capital')
  w.run_script('ywc_v03_initialize_country = yes','JHG')
  w.activate(arc['journals'][0]['id'],'JHG')
  w.pulse(arc)
  first=next(j for j in w.jobs if j.event_id=='ywc_jhg.1100')
  self.assertTrue(w.display_job(first))
  self.assertTrue(w.job_options(first)['wait'])
  w.choose_job(first,'wait')
  w.advance_days(90)
  w.pulse(arc)
  second=next(j for j in w.jobs if j.event_id=='ywc_jhg.1100' and j!=first)
  self.assertTrue(w.display_job(second))
  before=copy.deepcopy((w.countries,w.treasury,w.modifiers,w.active,w.history))
  w.choose_job(first,'route_1')
  self.assertEqual((w.countries,w.treasury,w.modifiers,w.active,w.history),before)
  self.assertTrue(w.job_options(second)['route_1'])
  w.choose_job(second,'route_1')
  self.assertEqual(w.countries['JHG']['ywc_jhg_dock_paid'],1)

if __name__=='__main__':unittest.main()
