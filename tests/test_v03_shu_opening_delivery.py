"""Source-backed SHU opening pulse checks; these do not emulate the game UI."""
from pathlib import Path
import unittest
from tests.clausewitz_harness import PulseWorld, parse

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / 'yongchang_world'
JOURNALS = (
    ('common/journal_entries/ywc_bootstrap_journal.txt', 'ywc_je_eternal_yongchang'),
    ('common/journal_entries/ywc_shared_journal.txt', 'ywc_je_who_inherits_china'),
    *[('common/journal_entries/ywc_shu.txt', key) for key in (
        'ywc_je_yongchang_century', 'ywc_je_shu_scholar_merchants',
        'ywc_je_shu_blackwater_frontier', 'ywc_je_shu_opium_question',
        'ywc_route_shu_bureaucratic_integration', 'ywc_route_shu_customs_reform',
        'ywc_je_flavor_shu_court_1')],
)

def definitions(path):
    return {key: body for key, _, body in parse((MOD / path).read_text(encoding='utf-8-sig'))}

def field(nodes, key):
    return next(body for name, _, body in nodes if name == key)

def pulse(world, journal):
    before = len(world.events)
    world.execute(field(field(journal, 'on_monthly_pulse'), 'effect'), 'SHU')
    for _, event_id in world.events[before:]:
        if event_id.startswith('ywc_bootstrap.'):
            path = 'events/ywc_bootstrap_events.txt'
        elif event_id.startswith('ywc_shared.'):
            path = 'events/ywc_shared_events.txt'
        elif event_id.startswith('ywc_shu.') and 100 <= int(event_id.split('.')[1]) <= 114:
            path = 'events/ywc_large_campaign_events.txt'
        else:
            path = 'events/ywc_shu_jhg_events.txt'
        event = definitions(path)[event_id]
        world.execute(field(event, 'immediate'), 'SHU')

class ScriptWorld(PulseWorld):
    def __init__(self, effects, triggers):
        super().__init__(effects, {'SHU': {}})
        self.trigger_defs = triggers
        self.journals = [('SHU', [('type', '=', key)]) for _, key in JOURNALS]

    def condition(self, node, tag):
        key, comparison, value = node
        if key == 'is_country_alive':
            return bool(self.countries[tag].get('alive', True)) == (value == 'yes')
        if key == 'is_subject':
            return bool(self.countries[tag].get('is_subject', False)) == (value == 'yes')
        if key in self.trigger_defs:
            assert comparison == '=' and value in ('yes', 'no')
            return self.conditions(self.trigger_defs[key], tag) == (value == 'yes')
        return super().condition(node, tag)

    def execute(self, nodes, tag):
        expanded = []
        for key, op, value in nodes:
            if key in ('ywc_campaign_settle_mid', 'ywc_campaign_settle_final') and isinstance(value, list):
                args = {name: val for name, _, val in value}
                source = (MOD / 'common/scripted_effects/ywc_campaign_effects.txt').read_text(encoding='utf-8-sig')
                for name, val in args.items():
                    source = source.replace(f'${name}$', val)
                body = next(body for name, _, body in parse(source) if name == key)
                alias = f'test_expanded_{key}_{args["CH"]}'
                self.effects[alias] = body
                expanded.append((alias, '=', 'yes'))
            else:
                expanded.append((key, op, value))
        return super().execute(expanded, tag)


def source_world():
    effects_paths = list((MOD / 'common/scripted_effects').glob('ywc_shu_legacy_delivery*.txt')) + [
        MOD / 'common/scripted_effects/ywc_campaign_effects.txt',
        MOD / 'common/scripted_effects/ywc_shared_effects.txt',
        MOD / 'common/scripted_effects/ywc_flavor_effects.txt',
        MOD / 'common/scripted_effects/ywc_v03_shu_effects.txt',
        MOD / 'common/scripted_effects/ywc_v03_effects.txt']
    triggers_paths = list((MOD / 'common/scripted_triggers').glob('ywc_shu_legacy_delivery*.txt')) + [
        MOD / 'common/scripted_triggers/ywc_v03_triggers.txt']
    effect_text = '\n'.join(p.read_text(encoding='utf-8-sig') for p in effects_paths)
    triggers = {key: body for p in triggers_paths for key, _, body in parse(p.read_text(encoding='utf-8-sig'))}
    return ScriptWorld(effect_text, triggers)

class ShuOpeningDelivery(unittest.TestCase):
    def test_nine_eligible_openings_do_not_all_dispatch_in_same_month(self):
        world = source_world()
        for path, key in JOURNALS:
            pulse(world, definitions(path)[key])
        events = [event for tag, event in world.events if tag == 'SHU']
        self.assertEqual(len(events), 1, events)

    def test_continuously_eligible_legacy_journals_all_get_a_turn(self):
        world = source_world()
        seen = set()
        for _ in range(60):
            world.advance_months()
            before = len(world.events)
            for path, key in JOURNALS:
                pulse(world, definitions(path)[key])
            month = world.events[before:]
            self.assertLessEqual(len(month), 1, month)
            seen.update(event for tag, event in month if tag == 'SHU')
        self.assertEqual(seen, {'ywc_bootstrap.1', 'ywc_shared.1', 'ywc_shu.6',
             'ywc_shu.1', 'ywc_shu.2', 'ywc_shu.3', 'ywc_shu.4',
             'ywc_shu.5', 'ywc_shu.7'})

    def test_absent_journal_never_blocks_other_candidates(self):
        world = source_world()
        world.journals = [entry for entry in world.journals if entry[1][0][2] != 'ywc_je_eternal_yongchang']
        for _ in range(12):
            world.advance_months()
            for path, key in JOURNALS[1:]:
                pulse(world, definitions(path)[key])
        self.assertIn('ywc_shared.1', [event for _, event in world.events])
        self.assertNotIn('ywc_bootstrap.1', [event for _, event in world.events])

    def test_v03_and_legacy_have_a_turn_after_either_kind_of_delivery(self):
        world = source_world()
        world.run('ywc_v03_mark_major_delivered')
        world.run('ywc_shu_legacy_after_v03')
        world.advance_days(90)
        gate = ('ywc_v03_can_deliver_major', '=', 'yes')
        self.assertFalse(world.condition(gate, 'SHU'), 'v03 must leave legacy a chance')
        for path, key in JOURNALS:
            pulse(world, definitions(path)[key])
        self.assertEqual(len(world.events), 1)
        world.advance_days(90)
        self.assertTrue(world.condition(gate, 'SHU'), 'v03 must have the next opportunity')
        count = len(world.events)
        for path, key in JOURNALS:
            pulse(world, definitions(path)[key])
        self.assertEqual(len(world.events), count, 'legacy must leave v03 a chance')

    def test_absent_legacy_never_blocks_v03(self):
        world = source_world()
        world.journals.clear()
        world.run('ywc_v03_mark_major_delivered')
        world.run('ywc_shu_legacy_after_v03')
        world.advance_days(90)
        self.assertTrue(world.condition(('ywc_v03_can_deliver_major', '=', 'yes'), 'SHU'))

    def test_old_unscoped_popup_may_resolve_once_but_cannot_replay_other_choice(self):
        world = source_world()
        event = definitions('events/ywc_shu_jhg_events.txt')['ywc_shu.1']
        options = [body for key, _, body in event if key == 'option']
        def apply(option):
            world.execute([node for node in option if node[0] not in ('name', 'default_option', 'trigger', 'ai_chance')], 'SHU')
        apply(options[0])
        self.assertIn('ywc_je_shu_scholar_merchants_resolved', world.countries['SHU'])
        before = dict(world.countries['SHU'])
        apply(options[1])
        self.assertEqual(world.countries['SHU'], before)

    def test_redelivered_popup_rejects_earlier_receipt_and_new_popup_works_once(self):
        world = source_world()
        key = 'ywc_je_shu_scholar_merchants'
        world.journals = [entry for entry in world.journals if entry[1][0][2] == key]
        journal = definitions('common/journal_entries/ywc_shu.txt')[key]
        event = definitions('events/ywc_shu_jhg_events.txt')['ywc_shu.1']
        options = [body for name, _, body in event if name == 'option']
        def deliver():
            before = len(world.events)
            pulse(world, journal)
            self.assertEqual(world.events[before:], [('SHU', 'ywc_shu.1')])
            return dict(world.scopes)
        first = deliver()
        world.advance_days(150)
        second = deliver()
        self.assertNotEqual(first, second)
        def click(which, scopes):
            world.scopes = dict(scopes)
            world.execute([node for node in options[which] if node[0] not in ('name','default_option','trigger','ai_chance')], 'SHU')
        before = dict(world.countries['SHU'])
        click(1, first)
        self.assertEqual(world.countries['SHU'], before)
        click(0, second)
        self.assertIn('ywc_je_shu_scholar_merchants_resolved', world.countries['SHU'])
        after = dict(world.countries['SHU'])
        click(1, second)
        self.assertEqual(world.countries['SHU'], after)

    def test_removed_journal_blocks_open_popup(self):
        world = source_world()
        event = definitions('events/ywc_shu_jhg_events.txt')['ywc_shu.1']
        option = next(body for key, _, body in event if key == 'option')
        world.journals = [entry for entry in world.journals if entry[1][0][2] != 'ywc_je_shu_scholar_merchants']
        before = dict(world.countries['SHU'])
        world.execute([node for node in option if node[0] not in ('name','default_option','trigger','ai_chance')], 'SHU')
        self.assertEqual(world.countries['SHU'], before)

    def test_unacknowledged_attempt_sets_no_cooldown_or_pending_and_retries(self):
        world = source_world()
        key = 'ywc_je_eternal_yongchang'
        world.journals = [entry for entry in world.journals if entry[1][0][2] == key]
        journal = definitions('common/journal_entries/ywc_bootstrap_journal.txt')[key]
        # Execute the JE source only. Deliberately do not execute event immediate.
        body = field(field(journal, 'on_monthly_pulse'), 'effect')
        world.execute(body, 'SHU')
        self.assertEqual(world.events, [('SHU', 'ywc_bootstrap.1')])
        self.assertNotIn('ywc_eternal_yongchang_pending', world.countries['SHU'])
        self.assertNotIn('ywc_v03_major_event_cooldown', world.countries['SHU'])
        world.execute(body, 'SHU')
        self.assertEqual(world.events, [('SHU', 'ywc_bootstrap.1')] * 2)

    def test_unanswered_bootstrap_pending_expires_and_retries(self):
        world = source_world()
        key = 'ywc_je_eternal_yongchang'
        world.journals = [entry for entry in world.journals if entry[1][0][2] == key]
        journal = definitions('common/journal_entries/ywc_bootstrap_journal.txt')[key]
        pulse(world, journal)
        self.assertEqual(world.days_until_expiry['SHU']['ywc_eternal_yongchang_pending'], 60)
        world.advance_days(60)
        self.assertNotIn('ywc_eternal_yongchang_pending', world.countries['SHU'])
        world.advance_days(90)
        pulse(world, journal)
        self.assertEqual(world.events, [('SHU','ywc_bootstrap.1')] * 2)

    def test_existing_unbounded_pending_gets_a_finite_expiry(self):
        world = source_world()
        key = 'ywc_je_eternal_yongchang'
        world.journals = [entry for entry in world.journals if entry[1][0][2] == key]
        world.countries['SHU']['ywc_eternal_yongchang_pending'] = 1
        journal = definitions('common/journal_entries/ywc_bootstrap_journal.txt')[key]
        pulse(world, journal)
        self.assertEqual(world.events, [])
        self.assertEqual(world.days_until_expiry['SHU']['ywc_eternal_yongchang_pending'], 60)
        world.advance_days(60)
        pulse(world, journal)
        self.assertEqual(world.events, [('SHU','ywc_bootstrap.1')])

    def test_ai_default_options_apply_from_actual_openings(self):
        ids = ['ywc_bootstrap.1', 'ywc_shared.1', 'ywc_shu.6', 'ywc_shu.1',
               'ywc_shu.2', 'ywc_shu.3', 'ywc_shu.4', 'ywc_shu.5', 'ywc_shu.7']
        facts = ['ywc_eternal_yongchang_resolved', 'ywc_shared_direction_chosen',
                 'ywc_je_yongchang_century_progress', 'ywc_je_shu_scholar_merchants_resolved',
                 'ywc_je_shu_blackwater_frontier_resolved', 'ywc_je_shu_opium_question_resolved',
                 'ywc_route_shu_bureaucratic_integration_active', 'ywc_route_shu_customs_reform_active',
                 'ywc_campaign_shu_c1_prelude']
        for (path,key), event_id, fact in zip(JOURNALS, ids, facts):
            with self.subTest(event=event_id):
                world = source_world()
                world.journals = [entry for entry in world.journals if entry[1][0][2] == key]
                pulse(world, definitions(path)[key])
                self.assertEqual(world.events, [('SHU',event_id)])
                event_path = ('events/ywc_bootstrap_events.txt' if event_id.startswith('ywc_bootstrap.') else
                              'events/ywc_shared_events.txt' if event_id.startswith('ywc_shared.') else
                              'events/ywc_shu_jhg_events.txt')
                event = definitions(event_path)[event_id]
                options = [body for name, _, body in event if name == 'option']
                default = next(opt for opt in options if any(k == 'default_option' and v == 'yes' for k,_,v in opt))
                world.execute([node for node in default if node[0] not in ('name','default_option','trigger','ai_chance','fallback')], 'SHU')
                self.assertIn(fact, world.countries['SHU'])

    def test_late_dispatch_rechecks_cooldown_before_immediate(self):
        world = source_world()
        key = 'ywc_je_eternal_yongchang'
        world.journals = [entry for entry in world.journals if entry[1][0][2] == key]
        journal = definitions('common/journal_entries/ywc_bootstrap_journal.txt')[key]
        event = definitions('events/ywc_bootstrap_events.txt')['ywc_bootstrap.1']
        world.execute(field(field(journal, 'on_monthly_pulse'), 'effect'), 'SHU')
        self.assertTrue(world.conditions(field(event, 'trigger'), 'SHU'))
        world.countries['SHU']['ywc_v03_major_event_cooldown'] = 1
        self.assertFalse(world.conditions(field(event, 'trigger'), 'SHU'))
        before = dict(world.countries['SHU'])
        world.execute(field(event, 'immediate'), 'SHU')
        self.assertEqual(world.countries['SHU'], before)
        self.assertNotIn('ywc_eternal_yongchang_pending', world.countries['SHU'])

    def test_destroyed_country_blocks_delayed_choice_and_future_dispatch(self):
        world = source_world()
        key = 'ywc_je_shu_scholar_merchants'
        world.journals = [entry for entry in world.journals if entry[1][0][2] == key]
        journal = definitions('common/journal_entries/ywc_shu.txt')[key]
        event = definitions('events/ywc_shu_jhg_events.txt')['ywc_shu.1']
        pulse(world, journal)
        world.countries['SHU']['alive'] = False
        option = next(body for name, _, body in event if name == 'option')
        before = dict(world.countries['SHU'])
        world.execute([node for node in option if node[0] not in ('name','default_option','trigger','ai_chance')], 'SHU')
        self.assertEqual(world.countries['SHU'], before)
        world.advance_days(150)
        pulse(world, journal)
        self.assertEqual(len(world.events), 1)

    def test_shared_event_non_shu_country_still_delivers_and_resolves(self):
        world = source_world()
        world.countries['JHG'] = {}
        journal = definitions('common/journal_entries/ywc_shared_journal.txt')['ywc_je_who_inherits_china']
        world.execute(field(field(journal, 'on_monthly_pulse'), 'effect'), 'JHG')
        self.assertEqual(world.events, [('JHG', 'ywc_shared.1')])
        event = definitions('events/ywc_shared_events.txt')['ywc_shared.1']
        self.assertTrue(world.conditions(field(event, 'trigger'), 'JHG'))
        world.execute(field(event, 'immediate'), 'JHG')
        option = next(body for name, _, body in event if name == 'option')
        world.execute([node for node in option if node[0] not in ('name','default_option','trigger','ai_chance')], 'JHG')
        self.assertEqual(world.countries['JHG']['ywc_shared_direction_chosen'], 1)
        self.assertNotIn('ywc_shu_legacy_popup_epoch_2', world.countries['JHG'])

    def test_candidate_predicates_match_real_legacy_journal_limits(self):
        def walk(nodes):
            for key, op, value in nodes:
                yield key, op, value
                if isinstance(value, list):
                    yield from walk(value)
        for index, (path, key) in enumerate(JOURNALS, 1):
            with self.subTest(journal=key):
                world = source_world()
                journal = definitions(path)[key]
                effects = field(field(journal, 'on_monthly_pulse'), 'effect')
                selected = next(value for name, _, value in effects if name == 'if' and
                    any(child_key == ('ywc_shu_legacy_try_shared' if index == 2 else f'ywc_shu_legacy_try_{index}')
                        for child_key, _, _ in walk(value)))
                original_limit = list(field(selected, 'limit'))
                names = {value for name, _, value in walk(original_limit)
                         if name == 'has_variable' and isinstance(value, str)}
                for variant in [None, *sorted(names)]:
                    world.countries['SHU'] = {} if variant is None else {variant: 1}
                    if variant == 'ywc_campaign_national_wait':
                        world.countries['SHU'][variant] = 2
                    original = world.conditions(original_limit, 'SHU')
                    candidate = world.condition((f'ywc_shu_legacy_candidate_{index}', '=', 'yes'), 'SHU')
                    self.assertEqual(candidate, original, (key, variant))

    def test_real_v03_immediate_and_legacy_source_share_delivery_opportunities(self):
        from tests.test_v03_shu_actual_fairness import (
            _new_world, _install_real_shu_render, _render_real_shu,
            _native_admission, _journal, _deliver_actual_event, ROOTS, FRESH_M1_EVENT,
        )
        world = _new_world()
        _install_real_shu_render(world, _render_real_shu())
        world.effects.update(definitions('common/scripted_effects/ywc_shu_legacy_delivery_effects.txt'))
        world.trigger_defs.update(definitions('common/scripted_triggers/ywc_shu_legacy_delivery_triggers.txt'))
        original_condition = world.condition
        def condition(node, tag):
            if node[0] == 'is_country_alive':
                return node[2] == 'yes'
            return original_condition(node, tag)
        world.condition = condition
        world.run('ywc_v03_initialize_country', 'SHU')
        _native_admission(world, *ROOTS[0])
        world.active['SHU'].append('ywc_je_eternal_yongchang')
        world.advance_days(30)
        pulse_v03 = field(field(_journal(world, ROOTS[0][1]), 'on_monthly_pulse'), 'effect')
        world.execute(pulse_v03, 'SHU')
        self.assertEqual(world.events.pop(), ('SHU', FRESH_M1_EVENT))
        _deliver_actual_event(world, FRESH_M1_EVENT, 30)
        self.assertIn('ywc_shu_v03_delivery_backoff', world.countries['SHU'])
        world.advance_days(90)
        self.assertFalse(world.condition(('ywc_v03_can_deliver_major', '=', 'yes'), 'SHU'))
        legacy = definitions('common/journal_entries/ywc_bootstrap_journal.txt')['ywc_je_eternal_yongchang']
        world.execute(field(field(legacy, 'on_monthly_pulse'), 'effect'), 'SHU')
        self.assertEqual(world.events.pop(), ('SHU', 'ywc_bootstrap.1'))
        popup = definitions('events/ywc_bootstrap_events.txt')['ywc_bootstrap.1']
        self.assertTrue(world.conditions(field(popup, 'trigger'), 'SHU'))
        world.execute(field(popup, 'immediate'), 'SHU')
        self.assertIn('ywc_eternal_yongchang_pending', world.countries['SHU'])
        world.advance_days(90)
        self.assertTrue(world.condition(('ywc_v03_can_deliver_major', '=', 'yes'), 'SHU'))
        self.assertIn('ywc_shu_legacy_backoff', world.countries['SHU'])

    def test_finished_court_prelude_cannot_claim_round_robin_priority(self):
        world = source_world()
        allowed = {'ywc_je_who_inherits_china', 'ywc_je_flavor_shu_court_1'}
        world.journals = [entry for entry in world.journals if entry[1][0][2] in allowed]
        world.countries['SHU'].update({'ywc_campaign_shu_c1_prelude': 1, 'ywc_shu_legacy_cursor': 8})
        journal = definitions('common/journal_entries/ywc_shu.txt')['ywc_je_flavor_shu_court_1']
        pulse_effect = field(field(journal, 'on_monthly_pulse'), 'effect')
        outer = next(body for name, _, body in pulse_effect if name == 'if')
        branch = next(body for name, _, body in outer if name == 'if')
        self.assertFalse(world.conditions(field(branch, 'limit'), 'SHU'), 'real prelude sender is ineligible')
        self.assertFalse(world.condition(('ywc_shu_legacy_phase_9', '=', 'yes'), 'SHU'))
        self.assertTrue(world.condition(('ywc_shu_legacy_phase_10', '=', 'yes'), 'SHU'))

    def test_completed_prelude_followup_and_shared_do_not_both_dispatch(self):
        world = source_world()
        allowed = {'ywc_je_who_inherits_china', 'ywc_je_flavor_shu_court_1'}
        world.journals = [entry for entry in world.journals if entry[1][0][2] in allowed]
        world.countries['SHU'].update({'ywc_campaign_shu_c1_prelude': 1, 'ywc_shu_legacy_cursor': 8})
        campaign = definitions('common/journal_entries/ywc_shu.txt')['ywc_je_flavor_shu_court_1']
        shared = definitions('common/journal_entries/ywc_shared_journal.txt')['ywc_je_who_inherits_china']
        pulse(world, campaign)
        pulse(world, shared)
        self.assertEqual(world.events, [('SHU', 'ywc_shu.100')])

    def test_old_unscoped_chapter_windows_remain_actionable_during_wait(self):
        world = source_world()
        world.journals = [('SHU', [('type', '=', f'ywc_je_flavor_shu_court_{chapter}')]) for chapter in (1,2)]
        world.countries['SHU'].update({'ywc_campaign_shu_c1_prelude': 1,
                                      'ywc_campaign_shu_c2_prelude': 1,
                                      'ywc_campaign_national_wait': 4})
        events = definitions('events/ywc_large_campaign_events.txt')
        for event_id, fact in (('ywc_shu.100', 'ywc_campaign_shu_c1_e100_done'),
                               ('ywc_shu.105', 'ywc_campaign_shu_c2_e105_done')):
            world.scopes = {}  # separately saved windows made before this update
            option = next(body for name, _, body in events[event_id] if name == 'option')
            world.execute([node for node in option if node[0] not in ('name','default_option','trigger','ai_chance')], 'SHU')
            self.assertIn(fact, world.countries['SHU'])

    def test_all_three_real_legacy_chapters_finish_in_stage_order_with_ai_defaults(self):
        old_events = definitions('events/ywc_shu_jhg_events.txt')
        generated = definitions('events/ywc_large_campaign_events.txt')
        for chapter, first in ((1,100), (2,105), (3,110)):
            with self.subTest(chapter=chapter):
                world = source_world()
                je = f'ywc_je_flavor_shu_court_{chapter}'
                world.journals = [('SHU', [('type', '=', je)])]
                journal = definitions('common/journal_entries/ywc_shu.txt')[je]
                expected = [f'ywc_shu.{6+chapter}'] + [f'ywc_shu.{n}' for n in range(first,first+5)]
                seen=[]
                for month in range(100):
                    world.advance_months()
                    before=len(world.events)
                    pulse(world, journal)
                    emitted=world.events[before:]
                    self.assertLessEqual(len(emitted),1)
                    if not emitted:
                        continue
                    event_id=emitted[0][1]
                    seen.append(event_id)
                    event=(old_events if event_id==expected[0] else generated)[event_id]
                    option=next(body for name,_,body in event if name=='option' and
                                any(k=='default_option' and v=='yes' for k,_,v in body))
                    world.execute([node for node in option if node[0] not in ('name','default_option','trigger','ai_chance','fallback')], 'SHU')
                    if len(seen)==len(expected):
                        break
                self.assertEqual(seen, expected)
                self.assertIn(f'ywc_campaign_shu_c{chapter}_outcome', world.countries['SHU'])

    def test_each_chapter_phase_requires_all_prior_done_and_current_not_done(self):
        for chapter, first in ((1,100),(2,105),(3,110)):
            for offset in range(5):
                with self.subTest(chapter=chapter, offset=offset):
                    world=source_world()
                    je=f'ywc_je_flavor_shu_court_{chapter}'
                    world.journals=[('SHU',[('type','=',je)])]
                    state=world.countries['SHU']
                    state[f'ywc_campaign_shu_c{chapter}_prelude']=1
                    for n in range(first,first+offset): state[f'ywc_campaign_shu_c{chapter}_e{n}_done']=1
                    index=9+(chapter-1)*6+offset+1
                    node=(f'ywc_shu_legacy_phase_{index}','=', 'yes')
                    self.assertTrue(world.condition(node,'SHU'))
                    state[f'ywc_campaign_shu_c{chapter}_e{first+offset}_done']=1
                    self.assertFalse(world.condition(node,'SHU'))
                    state.pop(f'ywc_campaign_shu_c{chapter}_e{first+offset}_done')
                    if offset:
                        state.pop(f'ywc_campaign_shu_c{chapter}_e{first}_done')
                        self.assertFalse(world.condition(node,'SHU'))

    def test_all_eleven_continuously_ready_groups_get_a_turn(self):
        world=source_world()
        extra=[('common/journal_entries/ywc_shu.txt', f'ywc_je_flavor_shu_court_{n}') for n in (2,3)]
        world.journals.extend([('SHU',[('type','=',key)]) for _,key in extra])
        seen=set()
        for month in range(75):
            world.advance_months()
            before=len(world.events)
            for path,key in [*JOURNALS,*extra]:
                pulse(world, definitions(path)[key])
            emitted=world.events[before:]
            self.assertLessEqual(len(emitted),1,emitted)
            seen.update(event for _,event in emitted)
        self.assertEqual(seen, {'ywc_bootstrap.1','ywc_shared.1',
            'ywc_shu.1','ywc_shu.2','ywc_shu.3','ywc_shu.4','ywc_shu.5',
            'ywc_shu.6','ywc_shu.7','ywc_shu.8','ywc_shu.9'})

    def test_every_chapter_popup_retries_and_rejects_its_older_receipt(self):
        import copy
        manual=definitions('events/ywc_shu_jhg_events.txt')
        generated=definitions('events/ywc_large_campaign_events.txt')
        for chapter,first in ((1,100),(2,105),(3,110)):
            for offset in range(6):
                event_id=f'ywc_shu.{6+chapter}' if offset==0 else f'ywc_shu.{first+offset-1}'
                with self.subTest(event=event_id):
                    world=source_world()
                    je=f'ywc_je_flavor_shu_court_{chapter}'
                    world.journals=[('SHU',[('type','=',je)])]
                    state=world.countries['SHU']
                    if offset:
                        state[f'ywc_campaign_shu_c{chapter}_prelude']=1
                        for n in range(first,first+offset-1): state[f'ywc_campaign_shu_c{chapter}_e{n}_done']=1
                    journal=definitions('common/journal_entries/ywc_shu.txt')[je]
                    event=(manual if offset==0 else generated)[event_id]
                    option=next(body for name,_,body in event if name=='option' and
                                any(k=='default_option' and v=='yes' for k,_,v in body))
                    effects=[node for node in option if node[0] not in ('name','default_option','trigger','ai_chance','fallback')]
                    pulse(world,journal); self.assertEqual(world.events[-1],('SHU',event_id))
                    old=dict(world.scopes)
                    world.advance_days(150)
                    pulse(world,journal); self.assertEqual(world.events[-2:],[('SHU',event_id)]*2)
                    fresh=dict(world.scopes)
                    before=copy.deepcopy((world.countries,world.treasury,world.modifiers,world.journals))
                    world.scopes=old; world.execute(effects,'SHU')
                    self.assertEqual((world.countries,world.treasury,world.modifiers,world.journals),before)
                    world.scopes=fresh; world.execute(effects,'SHU')
                    after=copy.deepcopy((world.countries,world.treasury,world.modifiers,world.journals))
                    self.assertNotEqual(after,before)
                    world.execute(effects,'SHU')
                    self.assertEqual((world.countries,world.treasury,world.modifiers,world.journals),after)

    def test_campaign_checker_rejects_fair_sender_retargeting(self):
        import json
        from tools import ywc_campaign_check as checker
        catalog = json.loads((ROOT / 'data/content/large_campaign_event_catalog.json').read_text(encoding='utf-8'))
        countries = {'shu': catalog['countries']['shu']}
        starts = (MOD / 'common/history/countries/ywc_content_starts.txt').read_text(encoding='utf-8-sig')
        journals = {'ywc_shu.txt': (MOD / 'common/journal_entries/ywc_shu.txt').read_text(encoding='utf-8-sig')}
        effects = (MOD / 'common/scripted_effects/ywc_shu_legacy_delivery_effects.txt').read_text(encoding='utf-8-sig')
        problems=[]
        checker.check_journals(countries, starts, journals, problems, effects)
        self.assertEqual(problems, [])
        mutated=effects.replace('trigger_event = { id = ywc_shu.100 }', 'trigger_event = { id = ywc_shu.101 }', 1)
        self.assertNotEqual(mutated, effects)
        checker.check_journals(countries, starts, journals, problems, mutated)
        self.assertTrue(any('ywc_shu.100' in problem for problem in problems), problems)

    def test_shared_campaign_wait_ticks_per_active_journal_not_per_calendar_month(self):
        world=source_world()
        world.journals=[('SHU',[('type','=',f'ywc_je_flavor_shu_court_{n}')]) for n in (1,2,3)]
        world.countries['SHU']['ywc_campaign_national_wait']=4
        journals=definitions('common/journal_entries/ywc_shu.txt')
        for chapter in (1,2,3):
            pulse(world,journals[f'ywc_je_flavor_shu_court_{chapter}'])
        self.assertEqual(world.countries['SHU']['ywc_campaign_national_wait'],1)
        self.assertEqual(world.events,[])

    def test_late_first_delivery_cannot_borrow_second_request_receipt(self):
        world=source_world()
        key='ywc_je_eternal_yongchang'
        world.journals=[entry for entry in world.journals if entry[1][0][2]==key]
        journal=definitions('common/journal_entries/ywc_bootstrap_journal.txt')[key]
        body=field(field(journal,'on_monthly_pulse'),'effect')
        event=definitions('events/ywc_bootstrap_events.txt')['ywc_bootstrap.1']
        world.execute(body,'SHU'); first=dict(world.scopes)
        world.scopes={}
        world.execute(body,'SHU'); second=dict(world.scopes)
        self.assertNotEqual(first,second, 'each trigger_event must retain its own receipt')
        before=dict(world.countries['SHU'])
        world.scopes=first; world.execute(field(event,'immediate'),'SHU')
        self.assertEqual(world.countries['SHU'],before)
        world.scopes=second; world.execute(field(event,'immediate'),'SHU')
        self.assertIn('ywc_eternal_yongchang_pending',world.countries['SHU'])

    def test_expired_or_invalid_second_request_preserves_later_retry(self):
        for invalidation in ('expired', 'journal_removed'):
            with self.subTest(invalidation=invalidation):
                world=source_world()
                key='ywc_je_eternal_yongchang'
                journal_entry=('SHU',[('type','=',key)])
                world.journals=[journal_entry]
                journal=definitions('common/journal_entries/ywc_bootstrap_journal.txt')[key]
                body=field(field(journal,'on_monthly_pulse'),'effect')
                event=definitions('events/ywc_bootstrap_events.txt')['ywc_bootstrap.1']
                world.execute(body,'SHU'); first=dict(world.scopes)
                world.scopes={};world.execute(body,'SHU'); second=dict(world.scopes)
                self.assertNotEqual(first,second)
                if invalidation=='expired': world.advance_days(31)
                else: world.journals=[]
                before=dict(world.countries['SHU'])
                for stale in (first,second):
                    world.scopes=stale;world.execute(field(event,'immediate'),'SHU')
                    self.assertEqual(world.countries['SHU'],before)
                world.journals=[journal_entry]
                world.scopes={};world.execute(body,'SHU'); third=dict(world.scopes)
                self.assertNotEqual(third,second)
                world.scopes=first;world.execute(field(event,'immediate'),'SHU')
                self.assertNotIn('ywc_eternal_yongchang_pending',world.countries['SHU'])
                world.scopes=third;world.execute(field(event,'immediate'),'SHU')
                self.assertIn('ywc_eternal_yongchang_pending',world.countries['SHU'])

    def test_all_twenty_six_authored_senders_bind_scope_before_trigger_and_ack(self):
        entries=[(path,key,event_id,None,None) for (path,key),event_id in zip(JOURNALS,
            ('ywc_bootstrap.1','ywc_shared.1','ywc_shu.6','ywc_shu.1','ywc_shu.2',
             'ywc_shu.3','ywc_shu.4','ywc_shu.5','ywc_shu.7'))]
        for chapter,first in ((1,100),(2,105),(3,110)):
            je=f'ywc_je_flavor_shu_court_{chapter}'
            if chapter>1:
                entries.append(('common/journal_entries/ywc_shu.txt',je,f'ywc_shu.{6+chapter}',chapter,0))
            for offset in range(1,6):
                entries.append(('common/journal_entries/ywc_shu.txt',je,f'ywc_shu.{first+offset-1}',chapter,offset))
        self.assertEqual(len(entries),26)
        for path,je,event_id,chapter,offset in entries:
            with self.subTest(event=event_id):
                world=source_world()
                world.journals=[('SHU',[('type','=',je)])]
                if chapter is not None and offset:
                    first={1:100,2:105,3:110}[chapter]
                    world.countries['SHU'][f'ywc_campaign_shu_c{chapter}_prelude']=1
                    for n in range(first,first+offset-1): world.countries['SHU'][f'ywc_campaign_shu_c{chapter}_e{n}_done']=1
                journal=definitions(path)[je]
                world.execute(field(field(journal,'on_monthly_pulse'),'effect'),'SHU')
                self.assertEqual(world.events,[('SHU',event_id)])
                scoped=dict(world.scopes)
                self.assertTrue(scoped)
                event_path=('events/ywc_bootstrap_events.txt' if event_id.startswith('ywc_bootstrap.') else
                            'events/ywc_shared_events.txt' if event_id.startswith('ywc_shared.') else
                            'events/ywc_large_campaign_events.txt' if int(event_id.split('.')[1])>=100 else
                            'events/ywc_shu_jhg_events.txt')
                event=definitions(event_path)[event_id]
                self.assertTrue(world.conditions(field(event,'trigger'),'SHU'))
                world.scopes={}
                self.assertFalse(world.conditions(field(event,'trigger'),'SHU'))
                world.scopes=scoped
                world.execute(field(event,'immediate'),'SHU')
                self.assertIn('ywc_v03_major_event_cooldown',world.countries['SHU'])
                option=next(body for name,_,body in event if name=='option' and
                            any(k=='default_option' and v=='yes' for k,_,v in body))
                before=dict(world.countries['SHU'])
                world.execute([node for node in option if node[0] not in ('name','default_option','trigger','ai_chance','fallback')],'SHU')
                self.assertNotEqual(world.countries['SHU'],before)

if __name__ == '__main__':
    unittest.main()
