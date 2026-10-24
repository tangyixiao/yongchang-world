"""Complete authored TIB stories in the controlled source interpreter.

Native controls execute today. Paired public inline contracts intentionally fail
at the real unsupported-country gate until production support is released.
The monthly scheduler ages authored timers through advance_months only; its day
timers use 30 days per model month (365/1095 therefore expire at 13/37).
"""
from __future__ import annotations

import copy
import json
import math
import unittest

from tests.clausewitz_harness import parse
from tests.test_v03_tib_inline_adapter import catalog, _binding
from tests.test_v03_tib_inline_actual_source import (
    actual_tib_inline_identity_control_world, actual_tib_inline_world,
    pulse_inline_journals, run_queued_inline_event_immediate,
    choose_inline_option, observe_actual_dispatch_append,
    observe_actual_effect_runs,
)

TAG = 'TIB'
CEILING = 360
PREFIXES = ('register', 'grain', 'schools')
ARC_SLUGS = dict(zip(PREFIXES, ('v03_tib_service_register',
    'v03_tib_grain_credit', 'v03_tib_shared_schools')))
NORMAL_NUMBERS = {'register': (1000,1001,1002,1003,1004,1007,1008,1009),
    'grain': (1010,1011,1012,1013,1016,1017), 'schools': (1020,1021,1022,1025)}
NOTICE_NUMBERS = {'register': (1005,1006), 'grain': (1014,1015), 'schools': (1023,1024)}


def field(nodes, key, default=None):
    return next((v for k, _, v in nodes if k == key), default)


def variable(prefix, suffix):
    return f'ywc_tib_{prefix}_{suffix}'


def outcome_variable(prefix, suffix):
    return f'ywc_v03_tib_{ARC_SLUGS[prefix]}_{suffix}'


def public_projection(world):
    """Compare complete business state at stable after-event/after-month seams.

    Only adapter-owned private variables/timers are excluded. Native queues are
    retained verbatim here: selected-clear timing differs only inside dispatch,
    and both paths must have completed that transaction at these stable seams.
    """
    def native(mapping):
        return {k: copy.deepcopy(v) for k, v in mapping.items()
                if not k.startswith('ywc_v03_tib_inline_')}
    return {'country': native(world.countries[TAG]),
        'treasury': world.treasury[TAG], 'modifiers': copy.deepcopy(world.modifiers),
        'months': native(world.months_until_expiry[TAG]),
        'days': native(world.days_until_expiry[TAG]),
        'active': list(world.active[TAG]), 'history': dict(world.history[TAG])}


class Story:
    """One shared calendar, a deterministic all-live pulse, and legal options."""
    def __init__(self, testcase, strategy, inline=False, obstruction=None):
        self.test = testcase
        self.strategy = strategy
        self.obstruction = obstruction
        self.world, self.bridge = (actual_tib_inline_world if inline else
            actual_tib_inline_identity_control_world)(strategy)
        self.state = self.world.countries[TAG]
        self.month = 0
        self.trace = []
        self.events = []
        self.effects = []
        self.observations = {p: [] for p in PREFIXES}
        self.implementations = {p: [] for p in PREFIXES}
        self.settlements = {}
        self.block = None
        self.restore_data = None
        self.notice36_count = 0
        self.fees = []
        self.pending_dispatches = []
        self.pulse_rows = []
        self.source = catalog()
        self.arcs = dict(zip(PREFIXES, self.source['arcs']))
        self.journals = {j['id']: j for a in self.source['arcs'] for j in a['journals']}
        self.event_source = {e['id']: (p,e) for p,a in self.arcs.items() for e in a['events']}
        self.bindings = {j['id']: _binding(j['id'],j['script']) for j in self.journals.values()}
        self.legacy_treasury = self.world.treasury[TAG]
        self.record('bridge', evidence=self.bridge,
            legacy_options=[e+'.b' for e in self.bridge['legacy_events']],
            root_gates=self.world.root_gates_before_initialize,
            root_counts=self.world.root_counts, initial=public_projection(self.world))
        self.check(self.bridge['legacy_events'] == ['ywc_tib.7', *[f'ywc_tib.{i}' for i in range(100,105)]], 'six real legacy choices')
        self.check(self.world.root_gates_before_initialize == [(False,False)]*3, 'initializer gate')
        self.check(self.world.root_counts == [(1,1),(2,2),(3,3)], 'root counters')
        self.check(self.world.history[TAG]['ywc_je_flavor_tib_estate_1'] == 'complete', 'legacy terminal')
        self.check([self.state[variable(p,'pending_event')] for p in PREFIXES] == [1000,1010,1020], 'source root queues')
        self.check([len(a['journals']) for a in self.source['arcs']] == [3,2,1], 'six phases')
        for p,a in self.arcs.items():
            normal = []
            for j in a['journals']:
                for row in self.bindings[j['id']]:
                    if row['candidates'][0]['kind'] == 'normal' and row['event'] not in normal:
                        normal.append(row['event'])
            self.check(normal == [f'ywc_tib.{i}' for i in NORMAL_NUMBERS[p]], (p,'complete semantic normal chain',normal))
            self.check(self.state[variable(p,'fee')] == 100, (p,'5200 / 52 captured base'))
            self.check(self.ready(p, f'route_{strategy}_ready'), (p,'legal actual route'))
            if strategy == 2:
                self.check(not self.ready(p,'route_1_ready'), (p,'route1 actually unavailable'))
        self.check_facts()

    def record(self, record_type, **data):
        self.trace.append({'month': self.month, 'record_type': record_type, **copy.deepcopy(data)})

    def check(self, condition, label):
        if not condition:
            self.test.fail(f'{label}\nFULL SOURCE STORY TRACE:\n' + json.dumps(self.trace,ensure_ascii=False,default=sorted,indent=2))

    def ready(self, prefix, predicate='route_execution_ready'):
        return self.world.conditions([(f'ywc_tib_{prefix}_{predicate}','=','yes')],TAG)

    def check_facts(self):
        self.check(self.state['laws'] == {'law_serfdom','law_religious_schools'}, 'one actual land/school law')
        for state in self.state['states']:
            for pop in state['pops']:
                if pop['employed']:
                    self.check(state['owned'] and any(pop['workplace'] is b and b['occupancy'] > 0
                        for b in state['buildings']), 'employed pop has owned staffed workplace')

    def effect_run(self, world, name, tag):
        self.effects.append((self.month,name,tag))

    def append(self, world, dispatch):
        # Observation only. No B, option, state edit, or receipt is run while
        # the actual source JE continuation is suspended inside trigger_event.
        self.check(world._execute_depth > 0, 'append remains inside source')
        self.pending_dispatches.append(dispatch)

    def after_journal(self, world, jid, emitted):
        self.check(world._execute_depth == 0, 'B waits for full source JE return')
        if not self.pulse_rows:
            self.expected_pulses = sorted(j for j in world.active[TAG]
                if j == jid or (not world.conditions(field(world.journal_defs[j],'complete',[]),TAG)
                and not world.conditions(field(world.journal_defs[j],'fail',[]),TAG)))
        self.check(jid not in self.pulse_rows, ('JE pulsed twice this month',jid))
        self.pulse_rows.append(jid)
        dispatches = self.pending_dispatches
        self.pending_dispatches = []
        self.check([(d['tag'],d['event_id']) for d in dispatches] == emitted, 'frozen actual appends match JE emission list')
        for dispatch in dispatches:
            eid = dispatch['event_id']
            prefix, definition = self.event_source[eid]
            rows = [r for r in self.bindings[jid] if r['event'] == eid]
            old_marker = self.month_before.get(variable(prefix,'notice_last_delivered'))
            if len(rows) > 1:
                # Preferred 12's negative last_delivered=1 condition is the
                # actual source distinction; monthly_review never writes it.
                rows = [rows[0] if old_marker != 1 else rows[-1]]
            self.check(len(rows) == 1, ('unambiguous authored sender',jid,eid))
            row = rows[0]
            candidate = row['candidates'][0]
            notice_clock = None
            if candidate['kind'].startswith('notice'):
                mark = 1 if candidate['kind'] == 'notice12' else 2
                self.check(self.state[variable(prefix,'notice_last_delivered')] == mark, 'source notice marker precedes append')
                self.check(variable(prefix,'paid') in self.state, 'notice requires actual prior payment')
                self.check(self.block is not None and prefix == self.obstruction, 'only declared arc obstructed')
                elapsed = self.month - self.block['start']
                due = variable(prefix, 'blocked_12_due' if mark == 1 else 'blocked_36_due')
                days = self.block['initial_days'][due]
                notice_clock = {'blocked_start':self.block['start'],
                    'elapsed_model_months':elapsed,'initial_days':days,
                    'remaining_days':world.days_until_expiry[TAG].get(due,0),
                    'nominal_months':12 if mark==1 else 36,
                    'model_expiry_months':math.ceil(days/30)}
                self.check(elapsed * 30 >= days and due not in self.state, 'notice follows actual day expiry')
                if not any(e['prefix']==prefix and e['kind']==candidate['kind'] for e in self.events):
                    self.check(elapsed >= math.ceil(days/30), 'first notice threshold')
            # Event B is the whole immediate. The option is intentionally later.
            treasury_before = world.treasury[TAG]
            paid_before = self.state.get(variable(prefix,'paid'))
            runs_before = len(self.effects)
            run_queued_inline_event_immediate(world,dispatch)
            self.check(world.treasury[TAG] == treasury_before, 'B itself does not pay route fees')
            self.check(sum(n=='ywc_v03_mark_major_delivered' for _,n,_ in self.effects[runs_before:]) == 1,
                'complete B runs shared cooldown exactly once')
            self.check(world.days_until_expiry[TAG]['ywc_v03_major_event_cooldown'] == 90, 'B establishes actual shared cooldown')
            options = {o['key']: o for o in definition['options']}
            legal = {field(o,'name').rsplit('.',1)[-1]: world.conditions(field(o,'trigger',[]),TAG)
                for k,_,o in world.event_defs[eid] if k=='option'}
            if candidate['kind'] == 'notice12':
                choice = 'defer'
            elif candidate['kind'] == 'notice36':
                self.notice36_count += 1
                choice = 'defer' if self.notice36_count == 1 else 'renegotiate'
            elif any(k.startswith('route_') for k in options):
                choice = f'route_{self.strategy}'
                self.check(legal[choice], 'route option actual trigger true')
                if self.strategy == 2:
                    self.check(not legal['route_1'], 'actual route1 option false for strategy2')
            else:
                choice = 'review_next'
            self.check(choice in options and legal[choice], ('legal authored option',eid,choice))
            # Check the formal field is effect and the registered option really
            # contains that source effect; effects is not a catalog field.
            option = next(o for k,_,o in world.event_defs[eid] if k=='option'
                and field(o,'name') == eid+'.'+choice)
            body = [n for n in option if n[0] not in ('name','trigger','ai_chance','default_option','custom_tooltip')]
            self.check(parse(options[choice]['effect'].strip()[1:-1]) == body, 'formal option effect binding')
            runs_before = len(self.effects)
            choose_inline_option(world,eid,choice)
            debit = world.treasury[TAG] - treasury_before
            if choice.startswith('route_'):
                fee = self.state[variable(prefix,f'route_cost_{self.strategy}')]
                self.check(fee == (200 if self.strategy==1 else 150), 'authored fee multiplier')
                self.check(paid_before is None and self.state[variable(prefix,'paid')] == 1,
                    'actual unpaid -> paid transition')
                self.check(debit == -fee, 'paid bit paired with actual treasury debit')
                helper = f'ywc_tib_choose_{prefix}_{self.strategy}'
                self.check(sum(n==helper for _,n,_ in self.effects[runs_before:]) == 1, 'actual source fee helper once')
                self.fees.append({'prefix':prefix,'month':self.month,'helper':helper,'debit':debit})
            else:
                self.check(debit == 0, 'review/notice does not repeat fee')
            self.check(world.available_gold(TAG) == self.state['gold_reserves']+world.treasury[TAG], 'cash includes actual treasury movement')
            event = {'month':self.month,'journal':jid,'event':eid,'prefix':prefix,
                'kind':candidate['kind'],'branch_index':row['branch_index'],
                'statement_ordinal':row['statement_ordinal'],'chain_index':row['chain_index'],
                'option':choice,'legal_options':legal,'debit':debit,
                'notice_marker':self.state.get(variable(prefix,'notice_last_delivered')),
                'notice_clock':notice_clock}
            self.events.append(event)
            self.record('event', **{k:v for k,v in event.items() if k!='month'}, projection=public_projection(world))
            if candidate['kind'].startswith('notice'):
                self.check(self.state[variable(prefix,'paid')] == 1, 'obstruction preserves payment')
                self.check(self.state[variable(prefix,'stage')] == self.block['stage'], 'obstruction retains native progress')
                self.check(not self.state.get(outcome_variable(prefix,'settled')), 'notice cannot settle prematurely')
                if choice == 'defer':
                    self.check(self.state[candidate['queue']] == candidate['value'], 'defer requeues identical authored notice')
                else:
                    self.check(variable(prefix,'implementation_complete') not in self.state, 'renegotiate clears old implementation')
                    self.check(self.state[variable(prefix,'pending_event')] == NORMAL_NUMBERS[prefix][-1], 'renegotiate requeues actual final review')
                    self.check(variable(prefix,'timer_started') not in self.state, 'renegotiate resets observation')
                    self.restore()
            if self.state.get(variable(prefix,'implementation_complete')) and paid_before is not None:
                if not self.implementations[prefix] or self.implementations[prefix][-1] != self.month:
                    if eid == f'ywc_tib.{NORMAL_NUMBERS[prefix][-1]}':
                        self.implementations[prefix].append(self.month)

    def obstruct(self):
        p = self.obstruction
        self.check(self.ready(p), 'paid execution readiness true before ordinary intervention')
        self.check(self.state[variable(p,'paid')] == 1 and self.state.get(variable(p,'implementation_complete')) == 1, 'real implementation checkpoint')
        state = self.state['states'][0]
        if p == 'grain':
            self.restore_data = ('market_access',state['market_access'])
            state['market_access'] = 0
        else:
            building = ('building_rice_farm' if p=='register' and self.strategy==2 else
                'building_university' if p=='schools' and self.strategy==1 else 'building_government_administration')
            self.restore_data = ('employment',list(state['buildings']),list(state['pops']))
            removed = [b for b in state['buildings'] if b['type']==building]
            state['buildings'] = [b for b in state['buildings'] if not any(b is r for r in removed)]
            state['pops'] = [pop for pop in state['pops'] if not any(pop['workplace'] is r for r in removed)]
        self.check_facts()
        self.check(not self.ready(p), 'ordinary intervention makes paid readiness false')
        # A farm obstruction is reached only after grain has settled through
        # the same driver. Other removed workplaces do not silently block a
        # still-live paid route: collateral readiness is checked explicitly.
        for other in PREFIXES:
            if other!=p and self.state.get(variable(other,'paid')) and not self.state.get(outcome_variable(other,'settled')):
                self.check(self.ready(other), ('no undeclared collateral paid obstruction',other))
        self.block = {'intervention':self.month,'start':None,'stage':self.state[variable(p,'stage')],
            'initial_days':{},'expired_at':{},'restored':None}
        self.record('ordinary_block',prefix=p,facts=public_projection(self.world),readiness=[True,False])

    def restore(self):
        p = self.obstruction
        self.check(not self.ready(p), 'ordinary facts remain blocked until restore')
        state = self.state['states'][0]
        if self.restore_data[0]=='market_access':
            state['market_access'] = self.restore_data[1]
        else:
            state['buildings'],state['pops'] = self.restore_data[1:]
        self.check_facts()
        self.check(self.ready(p), 'ordinary restoration makes paid readiness true')
        self.block['restored'] = self.month
        self.record('ordinary_restore',prefix=p,readiness=[True,False,True],facts=public_projection(self.world))

    def tick(self):
        self.world.advance_months(1)
        self.month += 1
        self.check(self.month <= CEILING, 'finite common-month ceiling')
        self.month_before = copy.deepcopy(self.state)
        active_before = list(self.world.active[TAG])
        self.pulse_rows = []
        self.expected_pulses = []
        emitted = pulse_inline_journals(self.world,after_journal=self.after_journal)
        self.check(not self.pending_dispatches, 'all frozen dispatches drained after full JE')
        # Reconciliation may remove terminals and admit actual next phases;
        # none is selected by expected route progress or a separate calendar.
        self.check(self.pulse_rows == self.expected_pulses,
            ('every live JE exactly once',self.pulse_rows,self.expected_pulses))
        self.check(len(emitted) <= 1, 'actual B cooldown gates subsequent JEs in same month')
        self.check(len(self.world.active[TAG]) == len(set(self.world.active[TAG])), 'unique active membership')
        for p in PREFIXES:
            timer = variable(p,'timer')
            started = variable(p,'timer_started')
            if started in self.state and started not in self.month_before:
                self.check(self.state.get(variable(p,'implementation_complete')) == 1, 'observation begins after implementation')
                self.check(self.world.months_until_expiry[TAG].get(timer) == 6, 'actual six month timer starts')
                self.observations[p].append(self.month)
                self.record('observation_start',prefix=p,timer_months=6,implementation=self.implementations[p][-1])
                self.check(self.month > self.implementations[p][-1], 'route selection is not observation start')
            if self.state.get(outcome_variable(p,'settled')) and p not in self.settlements:
                self.check(bool(self.observations[p]), 'settlement has real observation start')
                self.check(self.month-self.observations[p][-1] >= 6, 'six actual healthy months after implementation')
                self.check(timer not in self.state and timer not in self.world.months_until_expiry[TAG], 'actual month timer expired')
                self.settlements[p] = self.month
                self.record('settlement',prefix=p,start=self.observations[p][-1],outcome=self.state[outcome_variable(p,'outcome')])
        if self.obstruction and self.block is None and variable(self.obstruction,'timer_started') in self.state:
            self.obstruct()
        if self.block and self.block['restored'] is None:
            p = self.obstruction
            if self.block['start'] is None and variable(p,'blocked_started') in self.state:
                self.block['start'] = self.month
                self.block['initial_days'] = {variable(p,f'blocked_{n}_due'): self.world.days_until_expiry[TAG][variable(p,f'blocked_{n}_due')] for n in (12,36)}
                self.check(list(self.block['initial_days'].values()) == [365,1095], 'authored blocked timers start exactly')
                self.check(all(variable(p,s) not in self.state for s in ('timer','timer_started','six_months_complete')),
                    'actual monthly review resets interrupted observation')
            if self.block['start'] is not None:
                elapsed = self.month-self.block['start']
                for due,initial in self.block['initial_days'].items():
                    remaining = max(0,initial-elapsed*30)
                    self.check(self.world.days_until_expiry[TAG].get(due,0) == remaining, 'actual daytimer remaining/expiry boundary')
                    self.check((due in self.state) == (remaining>0), 'due variable presence follows interpreter expiry')
                    if remaining == 0 and due not in self.block['expired_at']:
                        self.block['expired_at'][due] = self.month
                        self.check(elapsed == math.ceil(initial/30), 'first observed daytimer expiry')
                        self.record('blocked_due_expired',prefix=p,due=due,initial_days=initial,
                            elapsed_model_months=elapsed,remaining_days=0)
        self.record('month',active_before=active_before,pulsed=self.pulse_rows,
            active_after=list(self.world.active[TAG]),history=dict(self.world.history[TAG]),
            emitted=emitted,projection=public_projection(self.world))

    def run(self):
        with observe_actual_dispatch_append(self.world,self.append), observe_actual_effect_runs(self.world,self.effect_run):
            while len(self.settlements) != 3 or self.world.active[TAG]:
                self.tick()
            stable = public_projection(self.world)
            # Extra complete monthly reconciliations must not repeat fees,
            # counter decrements, outcome settlement, or native queue delivery.
            for _ in range(4):
                self.tick()
            after = public_projection(self.world)
            self.check(stable['country'] == after['country'] and stable['treasury'] == after['treasury']
                and stable['active'] == after['active'] and stable['history'] == after['history'], 'terminal reconciliation is idempotent')
        self.check(set(self.settlements)==set(PREFIXES), 'all three arcs settle')
        self.check([self.state[outcome_variable(p,'outcome')] for p in PREFIXES] == [self.strategy]*3, 'actual route outcomes')
        self.check((self.state['ywc_v03_active_arc_count'],self.state['ywc_v03_visible_task_count']) == (0,0), 'actual final counters zero')
        self.check(all(self.world.history[TAG].get(j)=='complete' for j in self.journals), 'all six terminal JEs reconciled')
        self.check(len(self.fees)==3 and {f['prefix'] for f in self.fees}==set(PREFIXES), 'one paid fee per arc')
        self.check(self.world.treasury[TAG]-self.legacy_treasury == -(600 if self.strategy==1 else 450), 'route fees separate from legacy costs')
        for p in PREFIXES:
            normal = [e['event'] for e in self.events if e['prefix']==p and e['kind']=='normal']
            expected = [f'ywc_tib.{n}' for n in NORMAL_NUMBERS[p]]
            if p==self.obstruction:
                expected.append(expected[-1])
            self.check(normal == expected, (p,'full actual normal event ordering',normal,expected))
            self.check(all(variable(p,s) not in self.state for s in ('pending_event','notice_12_event','notice_36_event')), 'native queues cleared at settlement')
            self.check(sum(n==f'ywc_tib_choose_{p}_{self.strategy}' for _,n,_ in self.effects)==1, 'no repeated actual fee helper')
        if self.obstruction:
            p = self.obstruction
            notices = [e for e in self.events if e['prefix']==p and e['kind'].startswith('notice')]
            kinds = [e['kind'] for e in notices]
            self.check(kinds.count('notice12') >= 2 and kinds.count('notice36') == 2, '12 repeat plus 36 defer/redelivery')
            first36 = kinds.index('notice36')
            self.check(kinds[first36:first36+3] == ['notice36','notice12','notice36'], 'authored preferred12/36/fallback12 alternation')
            self.check(notices[-1]['option']=='renegotiate' and self.block['restored'] is not None, 'legal renegotiate then ordinary restore')
            self.check(len(self.implementations[p])==2 and self.implementations[p][-1] > self.block['restored'], 'actual final review reexecutes implementation after restore')
            self.check(len(self.observations[p])==2 and self.observations[p][0] == self.block['intervention'],
                'real initial observation interrupted and restarted')
            self.check(self.observations[p][-1] > self.implementations[p][-1], 'new healthy observation after restored implementation')
        return self


def run_story(testcase, strategy, inline=False, obstruction=None):
    """Public evidence runner surface; formal tests never write artifacts."""
    return Story(testcase,strategy,inline,obstruction).run()


class TibInlineNativeStoryControls(unittest.TestCase):
    def test_after_full_journal_callback_preserves_all_live_monthly_driver(self):
        world,_ = actual_tib_inline_identity_control_world()
        appended = []
        callbacks = []
        roots = sorted(world.active[TAG])
        def observer(current, dispatch):
            self.assertGreater(current._execute_depth,0)
            self.assertNotIn('ywc_v03_major_event_cooldown',current.countries[TAG])
            appended.append(dispatch)
        def after(current,jid,rows):
            self.assertEqual(current._execute_depth,0)
            callbacks.append((jid,list(rows)))
            for dispatch in appended:
                run_queued_inline_event_immediate(current,dispatch)
            appended.clear()
        with observe_actual_dispatch_append(world,observer):
            emitted = pulse_inline_journals(world,after_journal=after)
        self.assertEqual([j for j,_ in callbacks],roots)
        self.assertEqual(emitted,[(TAG,'ywc_tib.1010')])
        self.assertEqual([rows for _,rows in callbacks],[emitted,[],[]])
        self.assertEqual(world.days_until_expiry[TAG]['ywc_v03_major_event_cooldown'],90)
        self.assertEqual(list(world.events),[])
        # Default is still source-only: no callback means no B/cooldown and all
        # three real root events remain in the returned emission list.
        default,_ = actual_tib_inline_identity_control_world()
        self.assertEqual(pulse_inline_journals(default),[(TAG,'ywc_tib.1010'),(TAG,'ywc_tib.1000'),(TAG,'ywc_tib.1020')])
        self.assertNotIn('ywc_v03_major_event_cooldown',default.countries[TAG])

    def test_native_healthy_strategy1_complete_six_phases(self):
        run_story(self,1)

    def test_native_healthy_strategy2_complete_six_phases(self):
        run_story(self,2)

    def test_native_both_strategies_all_arc_notices_restore_and_24_events(self):
        seen = set()
        for strategy in (1,2):
            for prefix in PREFIXES:
                with self.subTest(strategy=strategy,obstruction=prefix):
                    story = run_story(self,strategy,obstruction=prefix)
                    seen.update(e['event'] for e in story.events)
        self.assertEqual(seen,{e['id'] for a in catalog()['arcs'] for e in a['events']})
        self.assertEqual(len(seen),24)


class TibInlineGeneratedStoryContracts(unittest.TestCase):
    def compare(self,strategy,obstruction=None):
        # Direct real factory gate first: unsupported is an honest FAIL. There
        # is no expected failure, catch, fake registry, or positive receipt.
        generated = run_story(self,strategy,inline=True,obstruction=obstruction)
        native = run_story(self,strategy,obstruction=obstruction)
        self.assertEqual(generated.events,native.events)
        self.assertEqual(generated.fees,native.fees)
        self.assertEqual(generated.implementations,native.implementations)
        self.assertEqual(generated.observations,native.observations)
        self.assertEqual(generated.settlements,native.settlements)
        self.assertEqual(generated.block,native.block)
        self.assertEqual(generated.trace,native.trace)
        self.assertEqual(public_projection(generated.world),public_projection(native.world))

    def test_generated_healthy_strategy1_matches_native_story(self):
        self.compare(1)

    def test_generated_healthy_strategy2_matches_native_story(self):
        self.compare(2)

    def test_generated_strategy1_register_notice_recovery_matches_native(self):
        self.compare(1,'register')

    def test_generated_strategy1_grain_notice_recovery_matches_native(self):
        self.compare(1,'grain')

    def test_generated_strategy1_schools_notice_recovery_matches_native(self):
        self.compare(1,'schools')

    def test_generated_strategy2_register_notice_recovery_matches_native(self):
        self.compare(2,'register')

    def test_generated_strategy2_grain_notice_recovery_matches_native(self):
        self.compare(2,'grain')

    def test_generated_strategy2_schools_notice_recovery_matches_native(self):
        self.compare(2,'schools')


if __name__ == '__main__':
    unittest.main()
