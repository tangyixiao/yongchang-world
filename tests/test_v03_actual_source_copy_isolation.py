"""Copy isolation controls for the test-only authored-source AST fast path."""
import copy
import unittest

from tests.actual_source_ast_copy import copy_source_ast
from tests import test_v03_jhg_inline_actual_source as jhg
from tests import test_v03_tib_inline_actual_source as tib


class CustomBlock(list):
    def __deepcopy__(self, memo):
        clone = type(self)()
        memo[id(self)] = clone
        clone.extend(copy.deepcopy(list(self), memo))
        clone.copied_by_protocol = True
        return clone


class MemoSetter:
    def __init__(self, leaf, replacement):
        self.leaf = leaf
        self.replacement = replacement

    def __deepcopy__(self, memo):
        memo[id(self.leaf)] = self.replacement
        return type(self)(self.leaf, self.replacement)


class ActualSourceCopyIsolation(unittest.TestCase):
    def test_terminal_tuple_honors_preseeded_deepcopy_memo(self):
        leaf = ('key', '=', 'leaf')
        replacement = ['replacement']
        source = {'probe': [leaf, leaf]}
        expected = copy.deepcopy(source, {id(leaf): replacement})
        clone = copy_source_ast(source, {id(leaf): replacement})
        self.assertIs(clone['probe'][0], expected['probe'][0])
        self.assertIs(clone['probe'][1], replacement)

    def test_custom_deepcopy_memo_update_is_seen_by_later_ast_leaf(self):
        leaf = ('key', '=', 'leaf')
        replacement = ['replacement']
        source = [MemoSetter(leaf, replacement), leaf]
        expected = copy.deepcopy(source)
        clone = copy_source_ast(source, {})
        self.assertIsNot(clone[0], source[0])
        self.assertIs(clone[1], expected[1])
        self.assertIs(clone[1], replacement)

    def test_atomic_values_follow_runtime_deepcopy_memo_order(self):
        for atom in ('unique_atomic_probe', None, True, 999999, 1.5):
            with self.subTest(atom=atom):
                source = {'probe': atom, 'branch': [('key', '=', atom)]}
                memo = {id(atom): ['replacement']}
                expected = copy.deepcopy(source, memo.copy())
                clone = copy_source_ast(source, memo)
                self.assertIs(clone['probe'], expected['probe'])
                self.assertIs(clone['branch'][0][2], expected['branch'][0][2])

    def test_ast_graph_preserves_aliases_cycles_and_fallback_protocol(self):
        leaf = ('name', '=', 'probe')
        child = [leaf]
        branch = ('if', '=', child)
        child.append(branch)  # A deliberate tuple/list cycle must terminate.
        special = CustomBlock([leaf])
        source = {'effects': [branch, branch], 'triggers': child, 'special': special}
        memo = {}
        clone = copy_source_ast(source, memo)
        aliases = copy.deepcopy({'child': child, 'branch': branch}, memo)
        self.assertIs(clone['effects'][0], clone['effects'][1])
        self.assertIs(clone['effects'][0][2], clone['triggers'])
        self.assertIs(clone['triggers'][1], clone['effects'][0])
        self.assertIs(aliases['child'], clone['triggers'])
        self.assertIs(aliases['branch'], clone['effects'][0])
        self.assertIsNot(clone['triggers'], child)
        self.assertIsNot(clone['special'], special)
        self.assertTrue(clone['special'].copied_by_protocol)
        clone['triggers'].append(('changed', '=', 'yes'))
        self.assertEqual(len(child), 2)
        self.assertNotIn('changed', [n[0] for n in special])

    def test_each_source_world_keeps_registry_aliases_isolated_between_copies(self):
        for actual in (jhg, tib):
            with self.subTest(country=actual.TAG):
                source, _ = (actual.actual_jhg_inline_world() if actual is jhg
                             else actual.actual_tib_inline_world())
                if actual is jhg:
                    source.attach_escort_partner_world()
                    source.partner_callback = source.escort_partner_world.run
                body = [('set_variable', '=', [('name', '=', 'copy_probe'), ('value', '=', '7')])]
                source.effects['copy_probe'] = body
                source.triggers['copy_probe_alias'] = body
                source.countries[actual.TAG]['copy_ast_alias'] = body
                source.probe_callback = source.run
                first = actual.copy_actual_world_without_observers(source)
                second = actual.copy_actual_world_without_observers(source)
                self.assertIs(first.effects['copy_probe'], first.triggers['copy_probe_alias'])
                self.assertIs(first.effects['copy_probe'], first.countries[actual.TAG]['copy_ast_alias'])
                self.assertIs(first.probe_callback.__self__, first)
                self.assertIs(first.events.world, first)
                first.run('copy_probe', actual.TAG)
                self.assertEqual(first.countries[actual.TAG]['copy_probe'], 7)
                self.assertNotIn('copy_probe', source.countries[actual.TAG])
                self.assertNotIn('copy_probe', second.countries[actual.TAG])
                first.effects['copy_probe'][0][2].append(('days', '=', '2'))
                self.assertEqual(len(body[0][2]), 2)
                self.assertEqual(len(second.effects['copy_probe'][0][2]), 2)
                if actual is jhg:
                    partner = first.escort_partner_world
                    self.assertIs(first.partner_callback.__self__, partner)
                    self.assertIs(partner.countries[actual.TAG], first.countries[actual.TAG])
                    self.assertIsNot(partner.effects, source.escort_partner_world.effects)
                    name = next(iter(partner.effects))
                    partner.effects[name].append(('future_unsupported_primitive', '=', 'yes'))
                    self.assertNotEqual(partner.effects[name], source.escort_partner_world.effects[name])

    def test_later_ast_edits_and_live_dispatch_checkpoints_are_copied_fresh(self):
        for actual in (jhg, tib):
            with self.subTest(country=actual.TAG):
                source = actual.source_scope_model_control_world()
                source.effects['copy_probe'] = [('set_variable', '=', [('name', '=', 'copy_probe'), ('value', '=', '7')])]
                earlier = actual.copy_actual_world_without_observers(source)
                source.effects['copy_probe'][0][2][1] = ('value', '=', '9')
                source.effects['unsupported_probe'] = [('future_unsupported_primitive', '=', 'yes')]
                pending = []
                def checkpoint(current, dispatch):
                    pending.append((actual.copy_actual_world_without_observers(current), copy.deepcopy(dispatch)))
                source._owned_ack_observer = lambda *_: None
                source._owned_ack_after_observer = lambda *_: None
                source._effect_run_observer = lambda *_: None
                with actual.observe_actual_dispatch_append(source, checkpoint):
                    with source.invocation({'copy_epoch': 17.0}):
                        source.execute([('trigger_event', '=', [('id', '=', 'copy_probe.1')])], actual.TAG)
                    self.assertIs(source._dispatch_append_observer, checkpoint)
                clone, dispatch = pending[0]
                self.assertEqual(clone.dispatch_contexts, [dispatch])
                self.assertEqual(list(clone.events), list(source.events))
                self.assertIs(clone.events.world, clone)
                self.assertEqual(clone.scope_context, {})
                self.assertEqual(clone._execute_depth, 0)
                for name in ('_dispatch_append_observer', '_owned_ack_observer', '_owned_ack_after_observer', '_effect_run_observer'):
                    self.assertIsNone(getattr(clone, name))
                earlier.run('copy_probe', actual.TAG)
                clone.run('copy_probe', actual.TAG)
                self.assertEqual(earlier.countries[actual.TAG]['copy_probe'], 7)
                self.assertEqual(clone.countries[actual.TAG]['copy_probe'], 9)
                self.assertNotIn('copy_probe', source.countries[actual.TAG])
                for world in (source, clone):
                    with self.assertRaises(AssertionError):
                        world.run('unsupported_probe', actual.TAG)
                clone.dispatch_contexts[0]['scope_context']['copy_epoch'] = 99
                self.assertEqual(source.dispatch_contexts[0]['scope_context']['copy_epoch'], 17)
                clone.events.append((actual.TAG, 'copy_probe.2'))
                self.assertEqual(len(source.events), 1)
                self.assertEqual(len(source.dispatch_contexts), 1)
                self.assertEqual(len(clone.dispatch_contexts), 2)


if __name__ == '__main__':
    unittest.main()
