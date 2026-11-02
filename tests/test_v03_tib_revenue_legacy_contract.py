"""Independent TIB revenue legacy-source contract.

Runs real old journal/event ASTs and their actual fees against the final source.
No revenue success marker, historical paid marker or earned result is injected.
This module does not claim engine or gameplay behavior.
"""
import hashlib
import json
from pathlib import Path
import unittest

from tools import build_v03_content
from tests import test_v03_tib_foundation_lifecycle as legacy

ROOT = Path(__file__).resolve().parents[1]
OLD = {
    'v03_tib_service_register': ('register', '65afae11efa9b1687c1016aadadf269e11433cff32a2e95fe8a1d9b265150ec2'),
    'v03_tib_grain_credit': ('grain', '65bac7fa00717bccecade48f1f19aaa4b74219b0e3a8fbec903f132af123e2c1'),
    'v03_tib_shared_schools': ('schools', '4b5498fd5833ca461e393c6aae3fa8443918a06cc9097227a8b52254768e8659'),
}
PREFIXES = {
    'yongchang_world/common/scripted_effects/ywc_v03_tib_effects.txt':
        (41184, 'a7d3a6758f442ebc44b4cd73be53feb4d2c68deb1452d75019457a9f0a367c81'),
    'yongchang_world/common/scripted_triggers/ywc_v03_tib_triggers.txt':
        (6112, 'd4f32e9947fdce65fb910c8c213d2a8e715bc6b6bd140f4657f83acbcb93718d'),
}


def canonical_hash(obj):
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def catalog():
    return json.loads((ROOT / 'data/content/v03/countries/tib.json').read_text(encoding='utf-8-sig'))


def text(path):
    return (ROOT / path).read_text(encoding='utf-8-sig').replace('\r\n', '\n')


def old_driver():
    """Real legacy scripts/rendered AST, using only existing old arcs.

    Preserves the original driver rather than adding a source-level business
    condition. Final source is loaded when called, not at import time.
    """
    full = catalog()
    old_catalog = dict(full)
    old_catalog['arcs'] = [a for a in full['arcs'] if a['slug'] in OLD]
    driver = legacy.TibStrictLifecycleTest()
    driver.effects = text('yongchang_world/common/scripted_effects/ywc_v03_effects.txt') + '\n' + text('yongchang_world/common/scripted_effects/ywc_v03_tib_effects.txt')
    driver.triggers = text('yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt') + '\n' + text('yongchang_world/common/scripted_triggers/ywc_v03_tib_triggers.txt')
    driver.journals = legacy.definitions(build_v03_content._render_journal_file(old_catalog, None))
    driver.events = legacy.definitions(build_v03_content._render_event_file(old_catalog, ROOT, None))
    return driver, {a['slug']: a for a in old_catalog['arcs']}


def earn_old_history(driver, world, arc, route=1):
    """Add a complete old story to this same world through real choices."""
    driver.entry(arc, world)
    event = driver.deliver(world, arc, arc['events'][0]['id'])
    before = world.treasury['TIB']
    driver.choose(world, arc, event, f'route_{route}')
    paid = before - world.treasury['TIB']
    driver.implement(world, arc, route)
    expected = route if route in (1, 2) else 3
    driver.settle(world, arc, expected)
    return paid


def complete_old_history(driver, arc, prefix, route=1):
    """Full real story, starting without injected paid/settled fields."""
    world = driver.world(prefix, route, 5000)
    return world, earn_old_history(driver, world, arc, route)


class TibRevenueOldHistoryContract(unittest.TestCase):
    def test_old_catalog_records_remain_exact(self):
        current = catalog()
        arcs = {a['slug']: a for a in current['arcs']}
        self.assertTrue(set(OLD).issubset(arcs))
        for slug, (_, expected) in OLD.items():
            with self.subTest(slug=slug):
                self.assertEqual(canonical_hash(arcs[slug]), expected)

    def test_old_native_helper_prefixes_are_preserved(self):
        for path, (length, expected) in PREFIXES.items():
            with self.subTest(path=path):
                prefix = text(path)[:length].encode('utf-8')
                self.assertEqual(hashlib.sha256(prefix).hexdigest(), expected)

    def test_all_old_positive_histories_come_from_real_paid_completed_stories(self):
        driver, arcs = old_driver()
        for slug, (prefix, _) in OLD.items():
            with self.subTest(slug=slug):
                world, paid = complete_old_history(driver, arcs[slug], prefix)
                s = world.countries['TIB']
                self.assertEqual(paid, 200)
                self.assertEqual(s['ywc_tib_' + prefix + '_paid'], 1)
                self.assertEqual(s['ywc_tib_' + prefix + '_implementation_complete'], 1)
                self.assertEqual(s['ywc_tib_' + prefix + '_six_months_complete'], 1)
                for key in ('started', 'settled', 'outcome'):
                    self.assertEqual(s[f'ywc_v03_tib_{slug}_{key}'], 1)
                self.assertEqual(world.treasury['TIB'], -200)
                self.assertEqual(s['ywc_v03_active_arc_count'], 0)
                self.assertEqual(s['ywc_v03_visible_task_count'], 0)
                self.assertTrue(all(world.history['TIB'][j['id']] == 'complete' for j in arcs[slug]['journals']))

    def test_real_withdrawal_is_not_a_completed_positive_history(self):
        driver, arcs = old_driver()
        for slug, (prefix, _) in OLD.items():
            with self.subTest(slug=slug):
                arc = arcs[slug]
                world = driver.world(prefix, 1, 5000)
                driver.entry(arc, world)
                event = driver.deliver(world, arc, arc['events'][0]['id'])
                driver.choose(world, arc, event, 'withdraw')
                s = world.countries['TIB']
                self.assertEqual(s[f'ywc_v03_tib_{slug}_outcome'], 4)
                self.assertNotIn(f'ywc_tib_{prefix}_paid', s)
                self.assertNotIn(f'ywc_tib_{prefix}_six_months_complete', s)
                self.assertEqual(world.treasury['TIB'], 0)

    def test_second_route_is_also_a_real_paid_completed_history(self):
        driver, arcs = old_driver()
        for slug, (prefix, _) in OLD.items():
            with self.subTest(slug=slug):
                world, paid = complete_old_history(driver, arcs[slug], prefix, route=2)
                s = world.countries['TIB']
                self.assertEqual(paid, 150)
                self.assertEqual(s[f'ywc_v03_tib_{slug}_outcome'], 2)
                self.assertEqual(s[f'ywc_v03_tib_{slug}_settled'], 1)
                self.assertEqual(s[f'ywc_tib_{prefix}_paid'], 1)
                self.assertEqual(s[f'ywc_tib_{prefix}_six_months_complete'], 1)

    def test_each_pair_of_old_histories_is_genuinely_earned_in_one_world(self):
        driver, arcs = old_driver()
        items = list(OLD.items())
        for index, (first_slug, (first_prefix, _)) in enumerate(items):
            for second_slug, (second_prefix, _) in items[index + 1:]:
                with self.subTest(first=first_slug, second=second_slug):
                    world = driver.world(first_prefix, 1, 5000)
                    self.assertEqual(earn_old_history(driver, world, arcs[first_slug]), 200)
                    self.assertEqual(earn_old_history(driver, world, arcs[second_slug]), 200)
                    s = world.countries['TIB']
                    self.assertEqual(world.treasury['TIB'], -400)
                    for slug, prefix in ((first_slug, first_prefix), (second_slug, second_prefix)):
                        self.assertEqual(s[f'ywc_v03_tib_{slug}_outcome'], 1)
                        self.assertEqual(s[f'ywc_v03_tib_{slug}_settled'], 1)
                        self.assertEqual(s[f'ywc_tib_{prefix}_paid'], 1)
                        self.assertEqual(s[f'ywc_tib_{prefix}_six_months_complete'], 1)


if __name__ == '__main__':
    unittest.main()
