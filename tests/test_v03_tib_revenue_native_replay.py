"""Actual-source stale-button and native JE handoff obligations for TIB revenue.

Run only after the source author has terminated. The generated event/JE text is
rendered in memory from the authored catalog with no adapter and no file writes.
Tests exercise real source options and real original JE pulse, not a controller
that inserts paid/stage/success markers. Unsupported native primitives fail.
"""
import copy
from contextlib import contextmanager
from pathlib import Path
import unittest

from tools import build_v03_content
from tests import test_v03_tib_foundation_lifecycle as legacy
from tests import test_v03_tib_current_choice as choices
from tests.test_v03_tib_revenue_legacy_contract import catalog, old_driver
from tests import test_v03_tib_revenue_state_source as typed

ROOT = Path(__file__).resolve().parents[1]
SLUG = 'v03_tib_public_revenue'


class RevenuePopup(list):
    def __init__(self, nodes, saved):
        super().__init__(nodes)
        self.saved = dict(saved)


class RevenuePopupWorld(typed.PartnerWorld):
    def deliver(self, arc, want):
        with self._chain(self.country_ref(self.tag)):
            event = super().deliver(arc, want)
            return RevenuePopup(event, self._saved)

    @contextmanager
    def popup_context(self, event):
        with self._chain(self.country_ref(self.tag), event.saved.items()):
            yield


def source_context():
    full = catalog()
    matches = [arc for arc in full['arcs'] if arc['slug'] == SLUG]
    if len(matches) != 1:
        raise AssertionError('expected exactly one actual TIB revenue arc')
    arc = matches[0]
    source_only = dict(full)
    source_only['arcs'] = [arc]
    driver, _ = old_driver()
    # Native text in memory, never file generation, index binding or runtime stub.
    driver.journals.update(legacy.definitions(build_v03_content._render_journal_file(source_only, None)))
    driver.events.update(legacy.definitions(build_v03_content._render_event_file(source_only, ROOT, None)))
    driver.deliver = lambda w, a, event, max_months=45: w.deliver(a, event)
    original_choose = driver.choose
    def choose(w, arc, event, key):
        with w.popup_context(event):
            return original_choose(w, arc, event, key)
    driver.choose = choose
    return driver, arc


def world(driver, generated=False):
    w, _ = typed.new_world(RevenuePopupWorld, generated=generated)
    w.run_script('ywc_v03_initialize_country = yes', 'TIB')
    return w


def snapshot(w):
    return copy.deepcopy((w.countries, w.treasury, w.modifiers, w.active, w.history,
                          w.events, w.days_until_expiry, w.months_until_expiry))


def force_cached(w, event, name):
    option = choices.option(event, name)
    with w.popup_context(event):
        w.execute(choices.executable(option), 'TIB')


class TibRevenueNativeReplayContract(unittest.TestCase):
    def opened(self, generated=False):
        driver, arc = source_context()
        w = world(driver, generated)
        driver.entry(arc, w)
        first = driver.deliver(w, arc, 'ywc_tib.1120')
        return driver, arc, w, first

    def test_withdrawn_opening_cannot_be_revived_by_held_buttons(self):
        driver, arc, w, first = self.opened()
        driver.choose(w, arc, first, 'withdraw')
        self.assertEqual(w.countries['TIB']['ywc_v03_tib_v03_tib_public_revenue_outcome'], 4)
        before = snapshot(w)
        for key in ('defer', 'route_1', 'route_2', 'route_3', 'withdraw'):
            with self.subTest(stale=key):
                trial=copy.deepcopy(w)
                force_cached(trial, first, key)
                self.assertEqual(snapshot(trial), before)

    def test_old_paid_stage_button_cannot_rewind_or_withdraw_current_story(self):
        driver, arc, w, first = self.opened()
        driver.choose(w, arc, first, 'route_1')
        old = driver.deliver(w, arc, 'ywc_tib.1121')
        driver.choose(w, arc, old, 'review_next')
        driver.deliver(w, arc, 'ywc_tib.1122')
        before = snapshot(w)
        for key in ('defer', 'review_next', 'withdraw'):
            with self.subTest(stale=key):
                force_cached(w, old, key)
                self.assertEqual(snapshot(w), before)

    def test_three_real_opening_choices_reach_the_next_live_journal(self):
        driver, arc, w, first = self.opened()
        driver.choose(w, arc, first, 'route_1')
        for event_id in ('ywc_tib.1121', 'ywc_tib.1122', 'ywc_tib.1123'):
            event = driver.deliver(w, arc, event_id, max_months=18)
            driver.choose(w, arc, event, 'review_next')
        # No out-of-band activation: the real source handoff must have occurred.
        self.assertEqual(w.history['TIB'].get(arc['journals'][0]['id']), 'complete')
        self.assertIn(arc['journals'][1]['id'], w.active['TIB'])

    def test_all_three_routes_pay_and_reach_real_delivered_terminal(self):
        for route in (1, 2, 3):
            with self.subTest(route=route):
                driver, arc, w, first = self.opened()
                country = w.countries['TIB']
                start = w.treasury['TIB']
                cost = country[f'ywc_tib_revenue_route_cost_{route}']
                driver.choose(w, arc, first, f'route_{route}')
                self.assertEqual(w.treasury['TIB'], start - cost)
                for number in (1121, 1122, 1123, 1124, 1128, 1129):
                    event = driver.deliver(w, arc, f'ywc_tib.{number}')
                    driver.choose(w, arc, event, 'review_next')
                self.assertNotIn('ywc_v03_tib_v03_tib_public_revenue_settled', country)
                event = driver.deliver(w, arc, 'ywc_tib.1127')
                self.assertEqual(country['ywc_tib_revenue_six_months_complete'], 1)
                self.assertNotIn('ywc_v03_tib_v03_tib_public_revenue_settled', country)
                driver.choose(w, arc, event, 'review_next')
                self.assertEqual(country['ywc_v03_tib_v03_tib_public_revenue_outcome'], route)
                self.assertEqual(country['ywc_v03_tib_v03_tib_public_revenue_settled'], 1)

    def test_zero_implementation_cannot_start_observation(self):
        driver, arc, w, first = self.opened()
        driver.choose(w, arc, first, 'route_1')
        for number in (1121,1122,1123,1124,1128,1129):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        country = w.countries['TIB']
        country['ywc_tib_revenue_implementation_complete'] = 0
        w.run_script('ywc_tib_revenue_monthly_review = yes', 'TIB')
        self.assertNotIn('ywc_tib_revenue_timer_started', country)
        self.assertNotIn('ywc_tib_revenue_six_months_complete', country)

    def test_redelivered_opening_rejects_old_popup_charge_and_withdraw(self):
        driver, arc, w, old = self.opened()
        driver.choose(w, arc, old, 'defer')
        current = driver.deliver(w, arc, 'ywc_tib.1120')
        before = w.treasury['TIB']
        force_cached(w, old, 'route_1')
        self.assertEqual(w.treasury['TIB'], before)
        force_cached(w, old, 'withdraw')
        self.assertNotIn('ywc_v03_tib_v03_tib_public_revenue_outcome', w.countries['TIB'])
        driver.choose(w, arc, current, 'route_1')
        self.assertEqual(w.countries['TIB']['ywc_tib_revenue_paid'], 1)

    def test_mature_terminal_is_redelivered_after_site_loss_and_fresh_observation(self):
        driver, arc, w, first = self.opened()
        driver.choose(w, arc, first, 'route_1')
        for number in (1121,1122,1123,1124,1128,1129):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        old = driver.deliver(w, arc, 'ywc_tib.1127')
        country = w.countries['TIB']
        original = country['states'][0]
        saved_pops = original['pops']
        original['pops'] = []
        w.run_script('ywc_tib_revenue_monthly_review = yes', 'TIB')
        force_cached(w, old, 'review_next')
        self.assertNotIn('ywc_v03_tib_v03_tib_public_revenue_settled', country)
        original['pops'] = saved_pops
        current = driver.deliver(w, arc, 'ywc_tib.1127')
        driver.choose(w, arc, current, 'review_next')
        self.assertEqual(country['ywc_v03_tib_v03_tib_public_revenue_settled'], 1)

    def test_generated_sender_and_same_id_popup_preserve_receipts(self):
        driver, arc, w, old = self.opened(generated=True)
        driver.choose(w, arc, old, 'defer')
        current = driver.deliver(w, arc, 'ywc_tib.1120')
        self.assertNotEqual(old.saved['ywc_tib_revenue_popup_epoch'], current.saved['ywc_tib_revenue_popup_epoch'])
        before = w.treasury['TIB']
        force_cached(w, old, 'route_1')
        force_cached(w, old, 'withdraw')
        self.assertEqual(w.treasury['TIB'], before)
        self.assertNotIn('ywc_v03_tib_v03_tib_public_revenue_outcome', w.countries['TIB'])
        driver.choose(w, arc, current, 'route_1')
        self.assertEqual(w.countries['TIB']['ywc_tib_revenue_paid'], 1)
        for number in (1121,1122,1123,1124,1128,1129,1127):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        self.assertEqual(w.countries['TIB']['ywc_v03_tib_v03_tib_public_revenue_outcome'], 1)

    def test_generated_redelivered_adjustment_rejects_old_double_payment(self):
        driver, arc, w, first = self.opened(generated=True)
        driver.choose(w, arc, first, 'route_1')
        for number in (1121,1122,1123,1124):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        old = driver.deliver(w, arc, 'ywc_tib.1128')
        driver.choose(w, arc, old, 'defer')
        current = driver.deliver(w, arc, 'ywc_tib.1128')
        before = w.treasury['TIB']
        force_cached(w, old, 'review_next')
        force_cached(w, old, 'withdraw')
        self.assertEqual(w.treasury['TIB'], before)
        self.assertNotIn('ywc_v03_tib_v03_tib_public_revenue_outcome', w.countries['TIB'])
        driver.choose(w, arc, current, 'review_next')
        self.assertEqual(w.treasury['TIB'], before - w.countries['TIB']['ywc_tib_revenue_adjust_cost'])
        force_cached(w, old, 'review_next')
        force_cached(w, current, 'review_next')
        self.assertEqual(w.treasury['TIB'], before - w.countries['TIB']['ywc_tib_revenue_adjust_cost'])

    def test_generated_sender_rejects_changed_queue_until_exact_callback(self):
        driver, arc = source_context()
        w = world(driver, generated=True)
        driver.entry(arc, w)
        with w._chain(w.country_ref('TIB')):
            w.pulse(arc)
        self.assertTrue(w.jobs)
        job = w.jobs[-1]
        self.assertEqual(job.event_id, 'ywc_tib.1120')
        country = w.countries['TIB']
        self.assertEqual(country['ywc_tib_revenue_pending_event'], 1120)
        country['ywc_tib_revenue_pending_event'] = 1121
        self.assertFalse(w.display_job(job))
        self.assertEqual(country['ywc_tib_revenue_pending_event'], 1121)
        self.assertNotIn('ywc_tib_revenue_receipt', country)
        country['ywc_tib_revenue_pending_event'] = 1120
        self.assertTrue(w.display_job(job))
        self.assertEqual(country['ywc_tib_revenue_receipt'], 1120)
        self.assertNotIn('ywc_tib_revenue_pending_event', country)
        self.assertNotIn('ywc_v03_tib_inline_reservation', country)

    def test_generated_notice_cannot_strand_an_open_normal_popup(self):
        driver, arc, w, first = self.opened(generated=True)
        driver.choose(w, arc, first, 'route_1')
        for number in (1121,1122,1123,1124):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        old = driver.deliver(w, arc, 'ywc_tib.1128')
        country = w.countries['TIB']
        original = country['states'][0]
        saved_pops = original['pops']; original['pops'] = []
        w.run_script('ywc_tib_revenue_monthly_review = yes', 'TIB')
        w.advance_days(365)
        driver.deliver(w, arc, 'ywc_tib.1125')
        original['pops'] = saved_pops
        w.run_script('ywc_tib_revenue_monthly_review = yes', 'TIB')
        self.assertEqual(country.get('ywc_tib_revenue_pending_event'), 1128)
        current = driver.deliver(w, arc, 'ywc_tib.1128')
        before = w.treasury['TIB']
        force_cached(w, old, 'review_next')
        self.assertEqual(w.treasury['TIB'], before)
        driver.choose(w, arc, current, 'review_next')
        self.assertLess(w.treasury['TIB'], before)

    def test_blocked_second_journal_narrowing_returns_to_its_live_sender(self):
        driver, arc, w, first = self.opened(generated=True)
        driver.choose(w, arc, first, 'route_1')
        for number in (1121, 1122, 1123):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        self.assertIn(arc['journals'][1]['id'], w.active['TIB'])
        driver.deliver(w, arc, 'ywc_tib.1124')
        original = w.countries['TIB']['states'][0]
        original['pops'][1]['radical_fraction'] = 0.01
        w.run_script('ywc_tib_revenue_monthly_review = yes', 'TIB')
        w.advance_days(365)
        notice = driver.deliver(w, arc, 'ywc_tib.1125')
        driver.choose(w, arc, notice, 'narrow_scope')
        self.assertEqual(w.countries['TIB'].get('ywc_tib_revenue_pending_event'), 1124)
        retry = driver.deliver(w, arc, 'ywc_tib.1124')
        driver.choose(w, arc, retry, 'review_next')
        self.assertIn(arc['journals'][2]['id'], w.active['TIB'])

    def test_blocked_second_journal_renegotiation_returns_to_its_live_sender(self):
        driver, arc, w, first = self.opened(generated=True)
        driver.choose(w, arc, first, 'route_1')
        for number in (1121, 1122, 1123):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        driver.deliver(w, arc, 'ywc_tib.1124')
        original = w.countries['TIB']['states'][0]
        original['pops'][1]['radical_fraction'] = 0.01
        w.run_script('ywc_tib_revenue_monthly_review = yes', 'TIB')
        w.advance_days(1095)
        notice12 = driver.deliver(w, arc, 'ywc_tib.1125')
        driver.choose(w, arc, notice12, 'defer')
        notice36 = driver.deliver(w, arc, 'ywc_tib.1126')
        driver.choose(w, arc, notice36, 'renegotiate')
        self.assertEqual(w.countries['TIB'].get('ywc_tib_revenue_pending_event'), 1124)
        self.assertNotIn('ywc_tib_revenue_notice_12_event', w.countries['TIB'])
        self.assertNotIn('ywc_tib_revenue_notice_36_event', w.countries['TIB'])
        force_cached(w, notice12, 'defer')
        force_cached(w, notice36, 'defer')
        self.assertNotIn('ywc_tib_revenue_notice_12_event', w.countries['TIB'])
        self.assertNotIn('ywc_tib_revenue_notice_36_event', w.countries['TIB'])
        original['pops'][1]['radical_fraction'] = 0.3
        retry = driver.deliver(w, arc, 'ywc_tib.1124')
        driver.choose(w, arc, retry, 'review_next')
        self.assertIn(arc['journals'][2]['id'], w.active['TIB'])

    def test_third_journal_narrowing_preserves_unpaid_adjustment(self):
        driver, arc, w, first = self.opened(generated=True)
        driver.choose(w, arc, first, 'route_1')
        for number in (1121, 1122, 1123, 1124):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        self.assertIn(arc['journals'][2]['id'], w.active['TIB'])
        driver.deliver(w, arc, 'ywc_tib.1128')
        original = w.countries['TIB']['states'][0]
        original['pops'][1]['radical_fraction'] = 0.01
        w.run_script('ywc_tib_revenue_monthly_review = yes', 'TIB')
        w.advance_days(365)
        notice = driver.deliver(w, arc, 'ywc_tib.1125')
        driver.choose(w, arc, notice, 'narrow_scope')
        self.assertEqual(w.countries['TIB'].get('ywc_tib_revenue_pending_event'), 1128)
        before = w.treasury['TIB']
        event = driver.deliver(w, arc, 'ywc_tib.1128')
        driver.choose(w, arc, event, 'review_next')
        self.assertEqual(w.treasury['TIB'], before - w.countries['TIB']['ywc_tib_revenue_adjust_cost'])

    def test_third_journal_renegotiation_keeps_unpaid_adjustment(self):
        driver, arc, w, first = self.opened(generated=True)
        driver.choose(w, arc, first, 'route_1')
        for number in (1121, 1122, 1123, 1124):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        old = driver.deliver(w, arc, 'ywc_tib.1128')
        state = w.countries['TIB']
        original = state['states'][0]
        original['pops'][1]['radical_fraction'] = 0.01
        w.run_script('ywc_tib_revenue_monthly_review = yes', 'TIB')
        w.advance_days(1095)
        notice12 = driver.deliver(w, arc, 'ywc_tib.1125')
        driver.choose(w, arc, notice12, 'defer')
        notice36 = driver.deliver(w, arc, 'ywc_tib.1126')
        driver.choose(w, arc, notice36, 'renegotiate')
        self.assertEqual(state.get('ywc_tib_revenue_pending_event'), 1128)
        before = w.treasury['TIB']
        original['pops'][1]['radical_fraction'] = 0.3
        force_cached(w, old, 'review_next')
        self.assertEqual(w.treasury['TIB'], before)
        current = driver.deliver(w, arc, 'ywc_tib.1128')
        driver.choose(w, arc, current, 'review_next')
        self.assertEqual(w.treasury['TIB'], before - state['ywc_tib_revenue_adjust_cost'])

    def test_third_journal_renegotiation_does_not_charge_a_paid_adjustment_again(self):
        driver, arc, w, first = self.opened(generated=True)
        driver.choose(w, arc, first, 'route_1')
        for number in (1121, 1122, 1123, 1124, 1128):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        old = driver.deliver(w, arc, 'ywc_tib.1129')
        state = w.countries['TIB']
        before = w.treasury['TIB']
        original = state['states'][0]
        original['pops'][1]['radical_fraction'] = 0.01
        w.run_script('ywc_tib_revenue_monthly_review = yes', 'TIB')
        w.advance_days(1095)
        notice12 = driver.deliver(w, arc, 'ywc_tib.1125')
        driver.choose(w, arc, notice12, 'defer')
        notice36 = driver.deliver(w, arc, 'ywc_tib.1126')
        driver.choose(w, arc, notice36, 'renegotiate')
        self.assertEqual(state.get('ywc_tib_revenue_pending_event'), 1129)
        original['pops'][1]['radical_fraction'] = 0.3
        force_cached(w, old, 'review_next')
        self.assertNotIn('ywc_tib_revenue_implementation_complete', state)
        current = driver.deliver(w, arc, 'ywc_tib.1129')
        driver.choose(w, arc, current, 'review_next')
        self.assertEqual(state['ywc_tib_revenue_implementation_complete'], 1)
        self.assertEqual(w.treasury['TIB'], before)

    def test_terminal_rechecks_positive_implementation_after_popup_opens(self):
        driver, arc, w, first = self.opened(generated=True)
        driver.choose(w, arc, first, 'route_1')
        for number in (1121, 1122, 1123, 1124, 1128, 1129):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        terminal = driver.deliver(w, arc, 'ywc_tib.1127')
        state = w.countries['TIB']
        option = choices.option(terminal, 'review_next')
        for value in (0, None):
            with self.subTest(implementation=value):
                if value is None:
                    state.pop('ywc_tib_revenue_implementation_complete', None)
                else:
                    state['ywc_tib_revenue_implementation_complete'] = value
                with w.popup_context(terminal):
                    self.assertFalse(w.conditions(legacy.field(option, 'trigger'), 'TIB'))
                force_cached(w, terminal, 'review_next')
                self.assertNotIn('ywc_v03_tib_v03_tib_public_revenue_settled', state)
        state['ywc_tib_revenue_implementation_complete'] = 1
        driver.choose(w, arc, terminal, 'review_next')
        self.assertEqual(state['ywc_v03_tib_v03_tib_public_revenue_outcome'], 1)

    def test_adjustment_does_not_charge_after_original_office_loss(self):
        driver, arc, w, first = self.opened()
        driver.choose(w, arc, first, 'route_1')
        for number in (1121,1122,1123,1124):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        event = driver.deliver(w, arc, 'ywc_tib.1128')
        w.countries['TIB']['states'][0]['pops'] = []
        before = w.treasury['TIB']
        force_cached(w, event, 'review_next')
        self.assertEqual(w.treasury['TIB'], before)
        self.assertNotEqual(w.countries['TIB'].get('ywc_tib_revenue_pending_event'), 1129)

    def test_lost_office_requeues_and_invalidates_same_adjustment_popup(self):
        driver, arc, w, first = self.opened(generated=True)
        driver.choose(w, arc, first, 'route_1')
        for number in (1121, 1122, 1123, 1124):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        old = driver.deliver(w, arc, 'ywc_tib.1128')
        state = w.countries['TIB']
        site = state['states'][0]
        saved_pops = site['pops']
        site['pops'] = []
        option = choices.option(old, 'review_next')
        with w.popup_context(old):
            self.assertFalse(w.conditions(legacy.field(option, 'trigger'), 'TIB'))
        before = w.treasury['TIB']
        force_cached(w, old, 'review_next')
        self.assertEqual(state.get('ywc_tib_revenue_pending_event'), 1128)
        site['pops'] = saved_pops
        force_cached(w, old, 'review_next')
        self.assertEqual(w.treasury['TIB'], before)
        current = driver.deliver(w, arc, 'ywc_tib.1128')
        driver.choose(w, arc, current, 'review_next')
        self.assertEqual(w.treasury['TIB'], before - state['ywc_tib_revenue_adjust_cost'])

    def test_failed_adjustment_popup_cannot_charge_after_site_recovers(self):
        driver, arc, w, first = self.opened(generated=True)
        driver.choose(w, arc, first, 'route_1')
        for number in (1121, 1122, 1123, 1124):
            event = driver.deliver(w, arc, f'ywc_tib.{number}')
            driver.choose(w, arc, event, 'review_next')
        old = driver.deliver(w, arc, 'ywc_tib.1128')
        site = w.countries['TIB']['states'][0]
        saved_pops = site['pops']
        site['pops'] = []
        before = w.treasury['TIB']
        force_cached(w, old, 'review_next')
        self.assertEqual(w.treasury['TIB'], before)
        site['pops'] = saved_pops
        force_cached(w, old, 'review_next')
        self.assertEqual(w.treasury['TIB'], before)

    def test_real_final_phase_reaches_adjustment_before_unmatured_final(self):
        driver, arc, w, first = self.opened()
        driver.choose(w, arc, first, 'route_1')
        for number in (1121,1122,1123,1124):
            event=driver.deliver(w,arc,f'ywc_tib.{number}',max_months=18)
            driver.choose(w,arc,event,'review_next')
        self.assertNotIn('ywc_tib_revenue_six_months_complete',w.countries['TIB'])
        event=driver.deliver(w,arc,'ywc_tib.1128',max_months=18)
        self.assertNotIn('ywc_v03_tib_v03_tib_public_revenue_settled',w.countries['TIB'])
        with w.popup_context(event):
            self.assertTrue(w.conditions(legacy.field(choices.option(event,'review_next'),'trigger'),'TIB'))


if __name__ == '__main__': unittest.main()
