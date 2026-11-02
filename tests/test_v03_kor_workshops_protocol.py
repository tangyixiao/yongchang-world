"""Real generated KOR workshop events, receipts and recovery, without seeded progress."""
import copy
import calendar
from datetime import date
import unittest
from test_v03_kor_workshops_business import new_world, arc_for, event, play, month, choose, force_option, option_legal, P, L
from test_v03_kor_revenue_cross_era import earn_military, earn_school


def ready(w, mode='office_service'):
    arc=arc_for(w)
    for number,key in ((1110,mode),(1111,'pay_program'),(1112,'new_reviewer'),
                       (1113,'sign_duties'),(1114,'accept_duties')):
        play(w,arc,number,key)
    return arc


def snapshot(w):
    return copy.deepcopy((w.countries,w.treasury,w.state_modifiers,w.active,w.history,w.jobs))


class KorWorkshopsProtocol(unittest.TestCase):
    def test_six_months_require_full_elapsed_time_and_six_distinct_checks(self):
        w=new_world();arc=arc_for(w)
        for number,key in ((1110,'office_service'),(1111,'pay_program'),(1112,'new_reviewer'),(1113,'sign_duties')):
            play(w,arc,number,key)
        e=event(w,arc,1114);today=w.date
        last=calendar.monthrange(today.year,today.month)[1]
        w.advance_days(last-today.day);start=w.date;choose(w,arc,e,'accept_duties');s=w.countries['KOR']
        for _ in range(6):
            year=w.date.year+(w.date.month==12);month_number=w.date.month%12+1
            w.advance_days((date(year,month_number,1)-w.date).days);w.pulse(arc)
        self.assertEqual(s[P+'review_streak'],6)
        self.assertNotIn(P+'review_mature',s,'six month boundaries are not six elapsed months')
        absolute=start.year*12+start.month-1+6;year,zero_month=divmod(absolute,12)
        due=date(year,zero_month+1,min(start.day,calendar.monthrange(year,zero_month+1)[1]))
        w.advance_days((due-w.date).days);w.pulse(arc)
        self.assertEqual(s[P+'review_mature'],1)

    def test_final_popup_can_reconsider_a_changed_request_without_recharging(self):
        for request in ('full','setback'):
            with self.subTest(original_request=request):
                w=new_world();arc=ready(w);month(w,arc,6);play(w,arc,1115,'pay_review')
                s=w.countries['KOR'];factory=next(b for b in s['states'][0]['buildings'] if b['type']=='building_textile_mill')
                if request=='setback':factory['shortage']=True
                play(w,arc,1116,'request_'+request);old=event(w,arc,1117)
                factory['shortage']=(request=='full')
                self.assertTrue(option_legal(w,old,'reconsider'));before=w.treasury['KOR']
                choose(w,arc,old,'reconsider');self.assertEqual(w.treasury['KOR'],before)
                frozen=snapshot(w);force_option(w,old,'close_full');force_option(w,old,'close_setback')
                self.assertEqual(snapshot(w),frozen)
                desired='setback' if request=='full' else 'full'
                play(w,arc,1116,'request_'+desired);play(w,arc,1117,'close_'+desired)
                self.assertEqual(s[L+'outcome'],3 if desired=='setback' else 1)
                self.assertEqual(w.treasury['KOR'],before)

    def test_paid_military_history_survives_current_loss_for_honest_setback(self):
        w=new_world();w.modifiers.append(('KOR',{'modifier':'military_wages_medium'}))
        earn_military(w,'provincial');arc=ready(w);month(w,arc,6)
        play(w,arc,1115,'reuse_military_review');e=event(w,arc,1116);s=w.countries['KOR']
        barracks=next(b for b in s['states'][0]['buildings'] if b['type']=='building_barrack')
        barracks['shortage']=True;before=w.treasury['KOR']
        self.assertFalse(option_legal(w,e,'request_full'))
        self.assertTrue(option_legal(w,e,'request_setback'))
        choose(w,arc,e,'request_setback');play(w,arc,1117,'close_setback')
        self.assertEqual(s[L+'outcome'],3);self.assertEqual(w.treasury['KOR'],before)

    def test_lost_original_does_not_excuse_a_different_live_recorded_state(self):
        for field in ('program_pilot','sign_pilot','accept_pilot','review_pilot'):
            with self.subTest(field=field):
                w=new_world();arc=ready(w);month(w,arc,6);play(w,arc,1115,'pay_review')
                e=event(w,arc,1116);s=w.countries['KOR'];original=s['states'][0]
                other=copy.deepcopy(original);other.pop('_sid',None);s['states'].append(other);w._register_states('KOR')
                s[P+field]=type(s[P+'pilot'])(other['_sid']);s['states'].remove(original)
                before=snapshot(w);self.assertFalse(option_legal(w,e,'request_setback'))
                force_option(w,e,'request_setback');self.assertEqual(snapshot(w),before)

    def test_discounted_review_must_retain_its_real_military_source_at_settlement(self):
        w=new_world();w.modifiers.append(('KOR',{'modifier':'military_wages_medium'}))
        earn_military(w,'provincial');arc=ready(w);month(w,arc,6)
        play(w,arc,1115,'reuse_military_review');e=event(w,arc,1116);s=w.countries['KOR']
        self.assertTrue(option_legal(w,e,'request_full'));self.assertEqual(s['ywc_kor_audit_paid'],1)
        s['ywc_kor_audit_paid']=0;before=snapshot(w)
        self.assertFalse(option_legal(w,e,'request_full'))
        force_option(w,e,'request_full');self.assertEqual(snapshot(w),before)
        self.assertTrue(option_legal(w,e,'withdraw'))

    def test_missing_military_proof_fails_closed_without_crashing(self):
        w=new_world();w.modifiers.append(('KOR',{'modifier':'military_wages_medium'}))
        earn_military(w,'provincial');arc=ready(w);month(w,arc,6)
        play(w,arc,1115,'reuse_military_review');e=event(w,arc,1116)
        for field in ('ywc_v03_kor_v03_kor_military_accounts_started','ywc_v03_kor_v03_kor_military_accounts_settled',
                      'ywc_v03_kor_v03_kor_military_accounts_outcome','ywc_kor_supply_route','ywc_kor_reporting_mode',
                      'ywc_kor_any_outcome','ywc_kor_provincial_report_right','ywc_kor_outcome_provincial_supply',
                      'ywc_kor_audit_paid','ywc_kor_invoice_review_paid','ywc_kor_supply_account_accepted',
                      'ywc_kor_audit_public','ywc_kor_review_complete','ywc_kor_service_review_complete',
                      'ywc_kor_six_months_complete','ywc_kor_nine_months_complete',
                      'ywc_kor_translation_contract_started','ywc_kor_translation_contract_paid_months',
                      'ywc_kor_veteran_contract_started','ywc_kor_veteran_contract_paid_months'):
            with self.subTest(field=field):
                trial=copy.deepcopy(w);state=trial.countries['KOR'];self.assertIn(field,state);del state[field]
                before=snapshot(trial);self.assertFalse(option_legal(trial,e,'request_full'))
                force_option(trial,e,'request_full');self.assertEqual(snapshot(trial),before)
                self.assertTrue(option_legal(trial,e,'withdraw'))

    def test_program_payment_rechecks_the_captured_exact_quote(self):
        w=new_world();arc=arc_for(w);play(w,arc,1110,'office_service');e=event(w,arc,1111)
        s=w.countries['KOR'];self.assertEqual(s[P+'program_due'],1000)
        s[P+'program_due']=1;before=snapshot(w)
        self.assertFalse(option_legal(w,e,'pay_program'))
        force_option(w,e,'pay_program');self.assertEqual(snapshot(w),before)

    def test_restart_rechecks_actual_paid_signed_and_accepted_proofs(self):
        for field in ('program_paid','signed','accepted'):
            for bad in (0,None):
                with self.subTest(field=field,bad=bad):
                    w=new_world();arc=ready(w);month(w,arc,2);s=w.countries['KOR']
                    factory=next(b for b in s['states'][0]['buildings'] if b['type']=='building_textile_mill')
                    factory['shortage']=True;w.pulse(arc);self.assertEqual(s[P+'review_interrupted'],1)
                    factory['shortage']=False;e=event(w,arc,1115)
                    self.assertTrue(option_legal(w,e,'restart_review'));key=P+field;self.assertEqual(s[key],1)
                    if bad is None:del s[key]
                    else:s[key]=bad
                    before=snapshot(w);self.assertFalse(option_legal(w,e,'restart_review'))
                    force_option(w,e,'restart_review');self.assertEqual(snapshot(w),before)
                    w.run_script('ywc_kor_workshops_start_review = yes','KOR');self.assertEqual(snapshot(w),before)

    def test_altered_fee_amount_cannot_prove_actual_paid_history(self):
        for field in ('program_paid_amount','review_paid_amount'):
            with self.subTest(field=field):
                w=new_world();arc=ready(w);month(w,arc,6);play(w,arc,1115,'pay_review')
                e=event(w,arc,1116);s=w.countries['KOR'];self.assertEqual(s[P+field],1000)
                s[P+field]=1;before=snapshot(w)
                self.assertFalse(option_legal(w,e,'request_full'))
                force_option(w,e,'request_full');self.assertEqual(snapshot(w),before)

    def test_actual_shared_capacity_and_ninety_day_delivery_with_two_old_arcs(self):
        w=new_world();arc=arc_for(w)
        military='ywc_je_v03_kor_military_audit';court='ywc_je_v03_kor_court_public_deliberation'
        workshop='ywc_je_v03_kor_workshops_program';revenue='ywc_je_v03_kor_provincial_revenue_settlement'
        for journal in (military,court,workshop):w.activate(journal,'KOR')
        s=w.countries['KOR'];self.assertEqual((s['ywc_v03_active_arc_count'],s['ywc_v03_visible_task_count']),(3,3))
        w.activate(revenue,'KOR');self.assertNotIn(revenue,w.active['KOR'])
        seen=[];workshop_job=None
        for _ in range(30):
            w.pulse(arc)
            for job in w.jobs:
                if job not in w._displayed and w.display_job(job):
                    seen.append((job.event_id,w.day))
                    if job.event_id=='ywc_kor.1110':workshop_job=job
            if len(seen)>=3:break
            w.advance_days(30)
        self.assertEqual({row[0] for row in seen},{'ywc_kor.1000','ywc_kor.1120','ywc_kor.1110'})
        self.assertTrue(all(b[1]-a[1]>=90 for a,b in zip(seen,seen[1:])),seen)
        self.assertIsNotNone(workshop_job);self.assertTrue(w.job_options(workshop_job)['withdraw'])
        w.choose_job(workshop_job,'withdraw')
        self.assertEqual((s['ywc_v03_active_arc_count'],s['ywc_v03_visible_task_count']),(2,2))

    def test_sign_and_accept_reject_a_different_live_earned_pilot(self):
        for target,field in ((1112,'program_pilot'),(1113,'program_pilot'),(1114,'sign_pilot')):
            with self.subTest(stage=target,field=field):
                w=new_world();arc=arc_for(w)
                for number,key in ((1110,'office_service'),(1111,'pay_program')):
                    play(w,arc,number,key)
                if target>=1113:play(w,arc,1112,'new_reviewer')
                if target==1114:play(w,arc,1113,'sign_duties')
                e=event(w,arc,target);action={1112:'new_reviewer',1113:'sign_duties',1114:'accept_duties'}[target]
                self.assertTrue(option_legal(w,e,action));s=w.countries['KOR']
                other=copy.deepcopy(s['states'][0]);other.pop('_sid',None);s['states'].append(other);w._register_states('KOR')
                s[P+field]=type(s[P+'pilot'])(other['_sid'])
                before=snapshot(w);self.assertFalse(option_legal(w,e,action))
                force_option(w,e,action);self.assertEqual(snapshot(w),before)

    def test_completed_state_effect_is_removed_on_real_transfer(self):
        w=new_world();arc=ready(w,'infrastructure');month(w,arc,6)
        play(w,arc,1115,'pay_review');play(w,arc,1116,'request_full');play(w,arc,1117,'close_full')
        s=w.countries['KOR'];pilot=s[P+'pilot'];key=(pilot,'ywc_kor_workshops_infrastructure')
        self.assertEqual(s[L+'outcome'],1);self.assertIn(key,w.state_modifiers)
        s['states'][0]['owner']='CHI';w.run_state_owner_change(pilot)
        self.assertNotIn(key,w.state_modifiers);self.assertEqual(s[L+'outcome'],1)

    def test_service_expires_without_renewal_and_withdrawal_removes_it(self):
        for end in ('expiry','withdrawal'):
            with self.subTest(end=end):
                w=new_world();arc=arc_for(w);play(w,arc,1110,'office_service');play(w,arc,1111,'pay_program')
                s=w.countries['KOR'];key=(s[P+'pilot'],'ywc_kor_workshops_office_service')
                self.assertIn(key,w.state_modifiers)
                if end=='withdrawal':
                    e=event(w,arc,1112);choose(w,arc,e,'withdraw');self.assertEqual(s[L+'outcome'],4)
                else:
                    w.advance_months(24)
                self.assertNotIn(key,w.state_modifiers)

    def test_genuinely_earned_school_and_military_proofs_are_reread(self):
        w=new_world();w.modifiers.append(('KOR',{'modifier':'military_wages_medium'}))
        earn_military(w,'provincial');earn_school(w,'cooperative');arc=arc_for(w)
        play(w,arc,1110,'office_service');play(w,arc,1111,'pay_program')
        mentor=event(w,arc,1112);self.assertTrue(option_legal(w,mentor,'reuse_school_mentor'))
        choose(w,arc,mentor,'reuse_school_mentor');signature=event(w,arc,1113)
        s=w.countries['KOR'];self.assertEqual(s['ywc_kor_school_coop_paid'],1)
        s['ywc_kor_school_coop_paid']=0;before=snapshot(w)
        self.assertFalse(option_legal(w,signature,'sign_duties'))
        force_option(w,signature,'sign_duties');self.assertEqual(snapshot(w),before)
        s['ywc_kor_school_coop_paid']=1;choose(w,arc,signature,'sign_duties')
        play(w,arc,1114,'accept_duties');month(w,arc,6);review=event(w,arc,1115)
        self.assertTrue(option_legal(w,review,'reuse_military_review'))
        self.assertEqual(s['ywc_kor_translation_contract_paid_months'],12)
        s['ywc_kor_translation_contract_paid_months']=11;before=snapshot(w)
        self.assertFalse(option_legal(w,review,'reuse_military_review'))
        force_option(w,review,'reuse_military_review');self.assertEqual(snapshot(w),before)

    def test_discounted_review_rechecks_each_real_earned_responsibility(self):
        w=new_world();w.modifiers.append(('KOR',{'modifier':'military_wages_medium'}))
        earn_military(w,'provincial');arc=ready(w);month(w,arc,6);e=event(w,arc,1115)
        self.assertTrue(option_legal(w,e,'reuse_military_review'))
        for field in ('program_paid','signed','accepted'):
            for bad in (0,None):
                with self.subTest(field=field,bad=bad):
                    trial=copy.deepcopy(w);state=trial.countries['KOR'];key=P+field
                    self.assertEqual(state[key],1)
                    if bad is None:del state[key]
                    else:state[key]=bad
                    before=snapshot(trial)
                    self.assertFalse(option_legal(trial,e,'reuse_military_review'))
                    force_option(trial,e,'reuse_military_review');self.assertEqual(snapshot(trial),before)

    def test_review_fee_requires_all_earned_responsibilities(self):
        for field in ('program_paid','signed','accepted','review_mature'):
            for bad in (0,None):
                with self.subTest(field=field,bad=bad):
                    w=new_world();arc=ready(w);month(w,arc,6);e=event(w,arc,1115)
                    s=w.countries['KOR'];key=P+field;self.assertEqual(s[key],1)
                    if bad is None:del s[key]
                    else:s[key]=bad
                    before=snapshot(w);self.assertFalse(option_legal(w,e,'pay_review'))
                    force_option(w,e,'pay_review');self.assertEqual(snapshot(w),before)

    def test_setback_rejects_wrong_live_state_snapshots_but_allows_lost_original(self):
        for field in ('program_pilot','sign_pilot','accept_pilot','review_pilot'):
            with self.subTest(field=field):
                w=new_world();arc=ready(w);month(w,arc,6);play(w,arc,1115,'pay_review')
                e=event(w,arc,1116);s=w.countries['KOR'];original=s['states'][0]
                other=copy.deepcopy(original);other.pop('_sid',None);s['states'].append(other);w._register_states('KOR')
                wrong=type(s[P+'pilot'])(other['_sid']);s[P+field]=wrong
                next(b for b in original['buildings'] if b['type']=='building_textile_mill')['shortage']=True
                before=snapshot(w);self.assertFalse(option_legal(w,e,'request_setback'))
                force_option(w,e,'request_setback');self.assertEqual(snapshot(w),before)
        w=new_world();arc=ready(w);month(w,arc,6);play(w,arc,1115,'pay_review')
        e=event(w,arc,1116);s=w.countries['KOR'];s['states'].clear()
        self.assertTrue(option_legal(w,e,'request_setback'))
        choose(w,arc,e,'request_setback');play(w,arc,1117,'close_setback')
        self.assertEqual(s[L+'outcome'],3)

    def test_loss_after_maturity_before_review_fee_requires_fresh_observation(self):
        w=new_world();arc=ready(w);s=w.countries['KOR'];month(w,arc,6)
        self.assertEqual(s[P+'review_mature'],1)
        factory=next(b for b in s['states'][0]['buildings'] if b['type']=='building_textile_mill')
        factory['shortage']=True;w.pulse(arc)
        self.assertNotIn(P+'review_mature',s)
        self.assertEqual(s[P+'review_interrupted'],1)
        factory['shortage']=False;e=event(w,arc,1115)
        self.assertFalse(option_legal(w,e,'pay_review'));choose(w,arc,e,'restart_review')
        month(w,arc,5);self.assertNotIn(P+'review_mature',s)
        month(w,arc);self.assertEqual(s[P+'review_mature'],1)

    def test_each_policy_reaches_its_honest_outcome_after_six_real_months(self):
        for mode,paid,outcome in (('office_service',1000,1),('infrastructure',2000,1),
                                  ('home_workshops',500,1),('limited_preparation',250,2)):
            with self.subTest(mode=mode):
                w=new_world();arc=ready(w,mode);s=w.countries['KOR']
                self.assertEqual(s[P+'program_paid_amount'],paid)
                self.assertEqual(s[P+'review_streak'],0)
                for _ in range(3):w.pulse(arc)
                self.assertEqual(s[P+'review_streak'],0)
                month(w,arc,5);self.assertNotIn(P+'review_mature',s)
                month(w,arc);self.assertEqual(s[P+'review_mature'],1)
                play(w,arc,1115,'pay_review')
                self.assertEqual(s[P+'review_paid_amount'],1000)
                play(w,arc,1116,'request_limited' if outcome==2 else 'request_full')
                play(w,arc,1117,'close_limited' if outcome==2 else 'close_full')
                self.assertEqual((s[L+'settled'],s[L+'outcome']),(1,outcome))
                self.assertEqual(w.treasury['KOR'],-paid-1000)
                self.assertFalse(any(k.startswith(P) and ('principal' in k or 'repaid' in k) for k in s))

    def test_each_real_popup_stays_inert_after_wait_and_redelivery(self):
        actions={1110:'office_service',1111:'pay_program',1112:'new_reviewer',1113:'sign_duties',
                 1114:'accept_duties',1115:'pay_review',1116:'request_full',1117:'close_full'}
        for target,action in actions.items():
            with self.subTest(stage=target):
                w=new_world();arc=arc_for(w)
                for number in range(1110,target):
                    if number==1115:month(w,arc,6)
                    play(w,arc,number,actions[number])
                if target==1115:month(w,arc,6)
                old=event(w,arc,target);displayed_day=w.day
                self.assertTrue(option_legal(w,old,action));choose(w,arc,old,'wait')
                before=snapshot(w);force_option(w,old,action);self.assertEqual(snapshot(w),before)
                current=event(w,arc,target)
                self.assertNotEqual(old.serial,current.serial)
                self.assertGreaterEqual(w.day-displayed_day,90)
                self.assertNotEqual(dict(w._displayed[old])[P+'popup_epoch'],dict(w._displayed[current])[P+'popup_epoch'])
                before=snapshot(w);force_option(w,old,action);self.assertEqual(snapshot(w),before)
                self.assertTrue(option_legal(w,current,action));choose(w,arc,current,action)
                self.assertNotEqual(snapshot(w),before)

    def test_lost_original_state_is_not_replaced_by_healthy_same_region(self):
        w=new_world();arc=ready(w);state=w.countries['KOR'];original=state['states'][0]
        second=copy.deepcopy(original);second.pop('_sid',None);state['states'].append(second);w._register_states('KOR')
        original['owner']='CHI';w.run_country_monthly('KOR');w.pulse(arc)
        self.assertEqual(state[P+'review_interrupted'],1)
        e=event(w,arc,1115);self.assertFalse(option_legal(w,e,'pay_review'))
        self.assertFalse(option_legal(w,e,'restart_review'))
        self.assertTrue(option_legal(w,e,'withdraw'));choose(w,arc,e,'withdraw')
        self.assertEqual(state[L+'outcome'],4)

    def test_same_month_shortage_interrupts_and_requires_six_fresh_months(self):
        w=new_world();arc=ready(w);s=w.countries['KOR']
        month(w,arc,2);self.assertEqual(s[P+'review_streak'],2)
        factory=next(b for b in s['states'][0]['buildings'] if b['type']=='building_textile_mill')
        factory['shortage']=True;w.pulse(arc)
        self.assertEqual(s[P+'review_interrupted'],1);self.assertEqual(s[P+'review_streak'],0)
        factory['shortage']=False;e=event(w,arc,1115);choose(w,arc,e,'restart_review')
        month(w,arc,5);self.assertNotIn(P+'review_mature',s)
        month(w,arc);self.assertEqual(s[P+'review_mature'],1)

    def test_zero_or_missing_earned_proof_cannot_become_full_settlement(self):
        for field in ('program_paid','signed','accepted','review_paid','review_mature'):
            for bad in (0,None):
                with self.subTest(field=field,bad=bad):
                    w=new_world();arc=ready(w);month(w,arc,6);play(w,arc,1115,'pay_review')
                    e=event(w,arc,1116);s=w.countries['KOR'];name=P+field
                    self.assertEqual(s[name],1)
                    if bad is None:del s[name]
                    else:s[name]=bad
                    before=snapshot(w);self.assertFalse(option_legal(w,e,'request_full'))
                    force_option(w,e,'request_full');self.assertEqual(snapshot(w),before)
                    self.assertTrue(option_legal(w,e,'withdraw'))

    def test_duplicate_program_payment_cannot_charge_or_refresh_service(self):
        w=new_world();arc=arc_for(w);play(w,arc,1110,'office_service');old=event(w,arc,1111)
        choose(w,arc,old,'pay_program');before=snapshot(w)
        force_option(w,old,'pay_program');self.assertEqual(snapshot(w),before)
