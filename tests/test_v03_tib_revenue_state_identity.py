"""Synthetic strict StateRef substrate tests; not evidence of game semantics."""
import copy
import unittest
from tests.tib_revenue_state_identity import StateIdentity, StateRef


def province(owner='TIB', with_office=True):
    office = {'type': 'government_administration', 'occupancy': .8, 'shortage': False}
    return {'owner': owner, 'region': 'same-region', 'buildings': [office] if with_office else [],
            'pops': [{'type': 'bureaucrats', 'employed': True, 'workplace': office}] if with_office else []}


class TibRevenueStateIdentityContract(unittest.TestCase):
    def setUp(self):
        self.original, self.other = province(), province()
        self.countries = {'TIB': {'states': [self.original, self.other]}, 'CHI': {'states': []}}
        self.identity = StateIdentity(self.countries)
        self.pilot = self.identity.intern(self.original)

    def test_capture_survives_reordering_without_aliasing_equal_another_state(self):
        other = self.identity.intern(self.other)
        self.countries['TIB']['states'].reverse()
        self.assertEqual(self.identity.intern(self.original), self.pilot)
        self.assertFalse(self.identity.same_live_object(self.pilot, other))
        self.assertIs(self.identity.resolve(self.pilot), self.original)

    def test_transfer_changes_current_ownership_not_object_identity(self):
        self.countries['TIB']['states'].remove(self.original)
        self.original['owner'] = 'CHI'
        self.countries['CHI']['states'].append(self.original)
        self.assertIs(self.identity.resolve(self.pilot), self.original)
        self.assertFalse(self.identity.is_owned_by(self.pilot, 'TIB'))
        self.assertTrue(self.identity.is_owned_by(self.pilot, 'CHI'))

    def test_gone_cannot_be_replaced_by_equal_copy_but_original_can_return(self):
        self.countries['TIB']['states'].remove(self.original)
        self.countries['TIB']['states'].append(copy.deepcopy(self.original))
        self.assertIsNone(self.identity.resolve(self.pilot))
        self.assertFalse(self.identity.is_owned_by(self.pilot, 'TIB'))
        with self.assertRaises(AssertionError): self.identity.same_live_object(self.pilot, self.pilot)
        self.countries['TIB']['states'].append(self.original)
        self.assertIs(self.identity.resolve(self.pilot), self.original)

    def test_other_state_office_cannot_repair_unstaffed_original(self):
        self.original['pops'].clear()
        self.assertFalse(self.identity.has_workplace(self.pilot, pop_type='bureaucrats',
            building_type='government_administration', minimum=.5))
        self.assertTrue(self.identity.has_workplace(self.identity.intern(self.other), pop_type='bureaucrats',
            building_type='government_administration', minimum=.5))

    def test_cross_state_or_string_workplace_is_rejected(self):
        for bad in (self.other['buildings'][0], 'government_administration', None):
            with self.subTest(bad=type(bad).__name__):
                self.original['pops'][0]['workplace'] = bad
                with self.assertRaises(AssertionError):
                    self.identity.has_workplace(self.pilot, pop_type='bureaucrats',
                        building_type='government_administration', minimum=.5)

    def test_unknown_wrong_type_and_duplicate_object_rejected(self):
        for bad in (0, True, 'same-region', StateRef(999), StateRef(True), StateRef(1.0)):
            with self.subTest(bad=bad):
                with self.assertRaises(AssertionError): self.identity.resolve(bad)
        self.countries['CHI']['states'].append(self.original)
        with self.assertRaises(AssertionError): self.identity.resolve(self.pilot)

    def test_missing_or_invalid_current_facts_do_not_default_to_success(self):
        office = self.original['buildings'][0]
        for key, bad in (('occupancy', None), ('occupancy', float('nan')), ('shortage', None)):
            with self.subTest(key=key, bad=bad):
                saved = office.pop(key); office[key] = bad
                with self.assertRaises(AssertionError):
                    self.identity.has_workplace(self.pilot, pop_type='bureaucrats',
                        building_type='government_administration', minimum=.5)
                office[key] = saved
        self.original.pop('owner')
        with self.assertRaises(AssertionError): self.identity.is_owned_by(self.pilot, 'TIB')

    def test_deepcopy_preserves_aliases_but_isolates_original(self):
        clone = copy.deepcopy(self.identity)
        state = clone.resolve(self.pilot)
        self.assertIsNot(state, self.original)
        self.assertIs(state, clone.countries['TIB']['states'][0])
        self.assertIs(state['pops'][0]['workplace'], state['buildings'][0])
        state['buildings'][0]['occupancy'] = .3
        self.assertEqual(self.original['buildings'][0]['occupancy'], .8)


if __name__ == '__main__': unittest.main()
