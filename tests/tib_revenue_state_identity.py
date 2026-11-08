"""Test-only identity substrate for a future TIB literal state-scope adapter.

No country/tag or revenue rules are hardcoded. This is a strict object graph
fixture, not a Clausewitz emulator; the source adapter remains to be bound only
once the author has finished and its native AST/scope syntax is known.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class StateRef:
    serial: int


class StateIdentity:
    def __init__(self, countries):
        if type(countries) is not dict:
            raise AssertionError('countries must be an explicit dict')
        self.countries = countries
        self._objects = {}
        self._next = 1

    def _locations(self, target):
        found = []
        for tag, country in self.countries.items():
            if not isinstance(tag, str) or type(country) is not dict:
                raise AssertionError('malformed country')
            states = country.get('states')
            if type(states) is not list:
                raise AssertionError(('missing explicit state list', tag))
            found.extend((tag, state) for state in states if state is target)
        if len(found) > 1:
            raise AssertionError('state object appears more than once')
        return found

    def intern(self, target):
        if type(target) is not dict:
            raise AssertionError('state must be an explicit dict')
        if not self._locations(target):
            raise AssertionError('cannot capture a state absent from the world')
        for serial, state in self._objects.items():
            if state is target:
                return StateRef(serial)
        ref = StateRef(self._next)
        self._next += 1
        self._objects[ref.serial] = target
        return ref

    def resolve(self, ref):
        if type(ref) is not StateRef or type(ref.serial) is not int or ref.serial <= 0:
            raise AssertionError(('invalid typed state reference', ref))
        if ref.serial not in self._objects:
            raise AssertionError(('unknown typed state reference', ref))
        state = self._objects[ref.serial]
        return state if self._locations(state) else None

    def is_owned_by(self, ref, tag):
        if not isinstance(tag, str) or tag not in self.countries:
            raise AssertionError(('unknown country', tag))
        state = self.resolve(ref)
        if state is None:
            return False
        owner = state.get('owner')
        if not isinstance(owner, str) or owner not in self.countries:
            raise AssertionError(('missing or unknown live owner', owner))
        return owner == tag

    def same_live_object(self, left, right):
        a, b = self.resolve(left), self.resolve(right)
        if a is None or b is None:
            raise AssertionError('comparison of unavailable state references is unsupported')
        return a is b

    def has_workplace(self, ref, *, pop_type, building_type, minimum):
        state = self.resolve(ref)
        if state is None:
            return False
        if not isinstance(pop_type, str) or not isinstance(building_type, str):
            raise AssertionError('explicit pop and building types required')
        if type(minimum) not in (int, float) or not math.isfinite(minimum) or not 0 <= minimum <= 1:
            raise AssertionError('invalid occupancy threshold')
        pops, buildings = state.get('pops'), state.get('buildings')
        if type(pops) is not list or type(buildings) is not list:
            raise AssertionError('explicit pop and building lists required')
        for pop in pops:
            if type(pop) is not dict or type(pop.get('employed')) is not bool or not isinstance(pop.get('type'), str):
                raise AssertionError('malformed pop facts')
            if pop['type'] != pop_type or not pop['employed']:
                continue
            workplace = pop.get('workplace')
            if type(workplace) is not dict or not any(b is workplace for b in buildings):
                raise AssertionError('workplace must be a real building in the same state')
            if workplace.get('type') != building_type:
                continue
            occupancy, shortage = workplace.get('occupancy'), workplace.get('shortage')
            if type(occupancy) not in (int, float) or not math.isfinite(occupancy) or not 0 <= occupancy <= 1:
                raise AssertionError('explicit finite occupancy required')
            if type(shortage) is not bool:
                raise AssertionError('explicit shortage fact required')
            if occupancy >= minimum and not shortage:
                return True
        return False
