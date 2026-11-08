"""KOR test-only recipient/context extension of the existing Strict interpreter.

API: run_script/check_script start a fresh country ROOT and saved-scope chain.
trigger_event adds an immutable EventJob to jobs (and preserves the inherited
events tuple log). display_job checks due time/recipient/trigger and executes
immediate once. job_options evaluates visibility; choose_job executes the full
selected source effect even after visibility changes, to probe stale guards.
These explicit APIs do not replace Strict.deliver/options/choose defaults.

Supported additions: country scopes this/root/prev, c:TAG, scope:name, var:name;
typed numeric/bool/country variables and .var: reads; permanent saved scopes
and numeric/bool snapshots; numeric comparisons and add/multiply/divide/clamp;
relations:<country>, alive/exists, day/month timers, current-recipient events
    with optional integer day/month delay, and treasury value/multiply. Existing local factual
predicates/scripted helpers delegate to Strict. No general script-value parser,
random scopes, temporary scopes, flags, AI simulation, treaties or transactions.
The supported stack contains countries plus typed state and market objects:
states carry a world-unique object identity that survives ownership transfer,
and markets are distinct objects addressable through the documented .market and
market .owner links. state_imports/state_exports/state_goods_production use the
documented strict operand blocks (target state object, g:/sg: goods token,
compared value) and only ever read real fixture economics fields; marker
booleans can never satisfy them. every_scope_state is the sole added effect
iterator and is restricted to the current country's states. prev/prev.prev and
owner resolve through the live scope chain inside state or market context.
Legacy owned=True facts mean owner=containing country; an explicit owner
overrides it. owner is documented syntax; is_owned_by remains fixture compatibility.
The offline calendar uses actual Gregorian dates; engine timing remains separate.
Scalar custom_tooltip labels are metadata; block wrappers execute their source
children after validating/removing only the scalar text localization field.
Direct advance_months owns its elapsed counter; inherited deliver owns that
same increment while its original waiting loop is active.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
import calendar
import math
import re

from shu_kor_strict_review_runtime import Strict, field
from clausewitz_harness import parse


class UnsupportedSubset(AssertionError):
    """Invalid or unsupported source in this explicitly bounded interpreter."""


@dataclass(frozen=True)
class CountryRef:
    tag: str
    incarnation: int


@dataclass(frozen=True)
class StateRef:
    """A state object identity; ownership is read live from the world."""

    sid: int


@dataclass(frozen=True)
class MarketRef:
    mid: str


@dataclass(frozen=True)
class GoodsRef:
    name: str


@dataclass(frozen=True)
class EventJob:
    serial: int
    recipient: CountryRef
    event_id: str
    due_day: int
    explicit_delay: bool
    saved: tuple


_MISSING = object()


def _add_months(start, months):
    absolute = start.year * 12 + start.month - 1 + months
    year, zero_month = divmod(absolute, 12)
    month = zero_month + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


class PartnerWorld(Strict):
    def __init__(self, countries, events="", start_date=date(1836, 1, 1), tag="kor"):
        super().__init__(tag, load_inline=True)
        self.countries = countries
        self.treasury = {tag: 0 for tag in countries}
        self.months_until_expiry = {tag: {} for tag in countries}
        self.days_until_expiry = {tag: {} for tag in countries}
        self.active = {tag: [] for tag in countries}
        self.history = {tag: {} for tag in countries}
        self.event_defs.update({k: v for k, _, v in parse(events)})
        self._incarnations = {tag: i for i, tag in enumerate(countries, 1)}
        self._next_incarnation = len(countries) + 1
        self._current = self._root = self._prev = None
        self._saved = {}
        self._stack = []
        self.market_scope = None
        self._explicit_state_ref = None
        self.jobs = []
        self._displayed = {}
        self._delivery_owns_months = False
        self.day = 0
        if not isinstance(start_date, date):
            raise UnsupportedSubset("explicit calendar start_date required")
        self.date = start_date
        self._epoch = self.date
        self.modifier_expires = {}
        from pathlib import Path
        source = Path("yongchang_world/common/script_values/ywc_v03_kor_values.txt")
        self.named_values = {key: body for key, _, body in parse(source.read_text(encoding="utf-8-sig"))} if source.exists() else {}
        source = Path("yongchang_world/common/static_modifiers/ywc_v03_kor_modifiers.txt")
        self.modifier_defs = {key: body for key, _, body in parse(source.read_text(encoding="utf-8-sig"))} if source.exists() else {}
        source = Path("yongchang_world/common/on_actions/ywc_v03_kor_accounts.txt")
        self.on_actions = {key: body for key, _, body in parse(source.read_text(encoding="utf-8-sig"))}
        # Typed world objects: states get a world-unique identity that survives
        # ownership transfer; markets are distinct objects owned at world level.
        self.markets = {}
        self._next_sid = 1
        for tag in countries:
            self._register_states(tag)

    def _register_states(self, tag):
        for state in self.countries[tag].get("states", []):
            if "_sid" not in state:
                state["_sid"] = self._next_sid
                self._next_sid += 1

    def _state_dict(self, sid):
        return self._state_location(sid)[0]

    def _state_location(self, sid):
        """Return (state dict, containing country tag) for a state object id."""
        for tag, facts in self.countries.items():
            for state in facts.get("states", []):
                if state.get("_sid") == sid:
                    return state, tag
        raise UnsupportedSubset(f"state object vanished: {sid}")

    def _state_owner_tag(self, ref):
        state, containing = self._state_location(ref.sid)
        owner = state.get("owner")
        if owner is None and state.get("owned"):
            owner = containing
        if owner not in self.countries:
            raise UnsupportedSubset(f"state object has no live owner: {ref.sid}")
        return owner

    def _state_owner_ref(self, ref):
        owner = self._state_owner_tag(ref)
        return self.country_ref(owner)

    def _state_present(self, sid):
        for facts in self.countries.values():
            for state in facts.get("states", []):
                if state.get("_sid") == sid:
                    return True
        return False

    def _market_ref(self, obj):
        if isinstance(obj, MarketRef):
            return obj
        if isinstance(obj, StateRef):
            state = self._state_dict(obj.sid)
            if "market" in state:
                return MarketRef(state["market"])
            owner = state.get("owner")
            if owner is None and state.get("owned"):
                owner = self._state_location(obj.sid)[1]
        elif isinstance(obj, CountryRef):
            owner = obj.tag
        else:
            raise UnsupportedSubset(f"market link requires a country or state object: {obj!r}")
        mid = self.countries.get(owner, {}).get("market", f"m_{owner}") if owner else None
        if not mid:
            return _MISSING
        return MarketRef(mid)

    def _market_owner(self, mid):
        market = self.markets.setdefault(mid, {"owner": None, "adjacent": set()})
        if market["owner"] is None and mid.startswith("m_") and mid[2:] in self.countries:
            market["owner"] = mid[2:]
        return market["owner"]

    def market_ref(self, mid):
        self._market_owner(mid)
        return MarketRef(mid)

    def country_ref(self, tag):
        if tag not in self.countries:
            raise UnsupportedSubset(f"undefined country: {tag}")
        return CountryRef(tag, self._incarnations[tag])

    def _present(self, ref):
        if isinstance(ref, StateRef):
            return self._state_present(ref.sid)
        if isinstance(ref, MarketRef):
            return True
        return (isinstance(ref, CountryRef) and ref.tag in self.countries
                and self._incarnations.get(ref.tag) == ref.incarnation)

    def _alive(self, ref):
        return self._present(ref) and self.countries[ref.tag].get("is_country_alive", True)

    def remove_country(self, tag):
        """Remove one incarnation; re-adding its tag never revives old objects."""
        if tag not in self.countries:
            raise UnsupportedSubset(f"undefined country removal: {tag}")
        for mapping in (self.countries, self.treasury, self.months_until_expiry,
                        self.days_until_expiry, self.active, self.history):
            mapping.pop(tag, None)

    def add_country(self, tag, facts):
        if tag in self.countries:
            raise UnsupportedSubset(f"country already exists: {tag}")
        self._incarnations[tag] = self._next_incarnation
        self._next_incarnation += 1
        self.countries[tag] = facts
        self.treasury[tag] = 0
        self.months_until_expiry[tag] = {}
        self.days_until_expiry[tag] = {}
        self.active[tag] = []
        self.history[tag] = {}
        self._register_states(tag)

    @contextmanager
    def _chain(self, recipient, saved=()):
        previous = self._current, self._root, self._prev, self._saved, self._stack
        self._current = self._root = recipient
        self._prev = None
        self._saved = dict(saved)
        self._stack = [recipient]
        try:
            yield
        finally:
            self._current, self._root, self._prev, self._saved, self._stack = previous

    @contextmanager
    def _scope(self, target):
        previous = self._current, self._prev, self._stack
        self._prev = self._current
        self._current = target
        self._stack = self._stack + [target]
        try:
            yield
        finally:
            self._current, self._prev, self._stack = previous

    @contextmanager
    def _state_context(self, ref):
        previous = self.state_scope, self.building_scope, self.pop_scope, self._stack, self._explicit_state_ref
        self.state_scope = self._state_dict(ref.sid)
        self.building_scope = self.pop_scope = None
        self._stack = self._stack + [ref]
        self._explicit_state_ref = ref
        try:
            yield
        finally:
            self.state_scope, self.building_scope, self.pop_scope, self._stack, self._explicit_state_ref = previous

    @contextmanager
    def _market_context(self, ref):
        previous = self.market_scope, self._stack
        self.market_scope = self.markets.setdefault(ref.mid, {"owner": None, "adjacent": set()})
        self._stack = self._stack + [ref]
        try:
            yield
        finally:
            self.market_scope, self._stack = previous

    def run_script(self, text, tag="KOR"):
        with self._chain(self.country_ref(tag)):
            return self.execute(parse(text), tag)

    def check_script(self, text, tag="KOR"):
        with self._chain(self.country_ref(tag)):
            return self.conditions(parse(text), tag)

    @staticmethod
    def _fields(nodes, allowed, required=()):
        if not isinstance(nodes, list):
            raise UnsupportedSubset(f"unsupported fields: {nodes!r}")
        result = {}
        for key, op, value in nodes:
            if op != "=" or key not in allowed or key in result:
                raise UnsupportedSubset(f"unsupported field: {(key, op, value)!r}")
            result[key] = value
        if not set(required) <= result.keys():
            raise UnsupportedSubset(f"unsupported incomplete fields: {nodes!r}")
        return result

    @staticmethod
    def _numeric(value):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise UnsupportedSubset(f"numeric value required, got {value!r}")
        return value

    @staticmethod
    def _scope_token(token):
        return (isinstance(token, str) and (token.lower() in ("this", "root", "prev", "prev.prev", "market")
                or token.startswith(("c:", "scope:", "var:"))
                or ".var:" in token))

    def _scope_link(self, obj, suffix):
        if suffix == "market":
            return self._market_ref(obj)
        if suffix == "owner":
            if isinstance(obj, StateRef):
                return self._state_owner_ref(obj)
            if isinstance(obj, MarketRef):
                owner = self._market_owner(obj.mid)
                return self.country_ref(owner) if owner and owner in self.countries else _MISSING
            raise UnsupportedSubset(f"owner link requires a state or market object: {obj!r}")
        raise UnsupportedSubset(f"unsupported scope link: {suffix}")

    def _value(self, token, *, optional=False):
        if isinstance(token, list):
            fields = self._fields(token, {"value", "multiply", "divide", "add"}, {"value"})
            value = self._numeric(self._value(fields["value"]))
            value *= self._numeric(self._value(fields.get("multiply", "1")))
            divisor = self._numeric(self._value(fields.get("divide", "1")))
            if divisor == 0:
                raise UnsupportedSubset("script value division by zero")
            return self._numeric(value / divisor + self._numeric(self._value(fields.get("add", "0"))))
        if not isinstance(token, str):
            raise UnsupportedSubset(f"unsupported value: {token!r}")
        if any(scope is not None for scope in (self.state_scope, self.building_scope, self.pop_scope)):
            typed_state = isinstance(self._stack[-1] if self._stack else None, StateRef)
            if token.lower() in ("prev", "this", "prev.prev") and not typed_state:
                raise UnsupportedSubset("unsupported PREV/this read inside an untyped non-country iterator")
            if token.lower().startswith("prev.var:"):
                if (not typed_state or self._explicit_state_ref != self._stack[-1]
                        or self.building_scope is not None or self.pop_scope is not None
                        or len(self._stack) < 2 or not isinstance(self._stack[-2], CountryRef)):
                    raise UnsupportedSubset("unsupported PREV variable read without an explicitly scoped country and state")
            elif token.lower().startswith("this.var:") or token.startswith("var:"):
                raise UnsupportedSubset("unsupported this/local variable read inside non-country iterator")
        suffixes = []
        rest = token
        if ".var:" not in token:
            while rest.endswith(".market") or rest.endswith(".owner"):
                if rest.endswith(".market"):
                    suffixes.append("market")
                    rest = rest[:-len(".market")]
                else:
                    suffixes.append("owner")
                    rest = rest[:-len(".owner")]
            if rest != token and not rest:
                raise UnsupportedSubset(f"unsupported bare scope link: {token}")
        if ".var:" in token:
            owner, name = token.rsplit(".var:", 1)
            ref = self._value(owner, optional=True)
            result = self.countries[ref.tag].get(name, _MISSING) if self._present(ref) and isinstance(ref, CountryRef) else _MISSING
        elif rest.lower() in ("this", "root", "prev", "prev.prev"):
            depth = {"this": 1, "prev": 2, "prev.prev": 3}.get(rest.lower())
            if rest.lower() == "root":
                result = self._stack[0] if self._stack else _MISSING
            elif depth and len(self._stack) >= depth:
                result = self._stack[-depth]
            else:
                result = _MISSING
        elif rest.lower() == "owner":
            top = self._stack[-1] if self._stack else None
            if isinstance(top, StateRef):
                result = self._state_owner_ref(top)
            elif isinstance(top, MarketRef):
                owner = self._market_owner(top.mid)
                result = self.country_ref(owner) if owner and owner in self.countries else _MISSING
            else:
                raise UnsupportedSubset("owner read requires a state or market scope")
        elif rest.lower() == "market":
            top = self._stack[-1] if self._stack else None
            if isinstance(top, MarketRef):
                raise UnsupportedSubset("market link is not valid inside a market scope")
            result = self._market_ref(top) if top is not None else _MISSING
        elif rest.startswith("c:"):
            result = self.country_ref(rest[2:]) if rest[2:] in self.countries else _MISSING
        elif rest.startswith("scope:"):
            result = self._saved.get(rest[6:], _MISSING)
        elif rest.startswith("var:"):
            result = self.countries[self._current.tag].get(rest[4:], _MISSING)
        elif rest.startswith(("g:", "sg:")):
            result = GoodsRef(rest.split(":", 1)[1])
        elif rest in ("yes", "no"):
            result = rest == "yes"
        elif rest == "year":
            result = self.date.year
        elif rest == "month":
            result = self.date.month - 1
        elif rest in self.named_values:
            result = self._value(self.named_values[rest])
        elif re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", rest):
            result = float(rest)
            self._numeric(result)
        elif rest in ("yearly_gross_income", "gdp", "scaled_debt", "gold_reserves", "net_fixed_income", "bureaucracy", "army_size", "legitimacy", "authority"):
            result = self.countries[self._current.tag].get(rest, _MISSING)
            if rest == "gold_reserves" and result is not _MISSING:
                result += self.treasury[self._current.tag]
        else:
            raise UnsupportedSubset(f"unsupported value token: {token}")
        for suffix in suffixes:
            if result is not _MISSING:
                result = self._scope_link(result, suffix)
        if isinstance(result, CountryRef) and not self._present(result):
            result = _MISSING
        if isinstance(result, StateRef) and not self._state_present(result.sid):
            result = _MISSING
        if result is _MISSING and not optional:
            raise UnsupportedSubset(f"undefined value/country: {token}")
        if result is not _MISSING and not isinstance(result, (CountryRef, StateRef, MarketRef, GoodsRef)):
            if type(result) is not bool:
                self._numeric(result)
        return result

    def compare(self, left, op, right):
        object_refs = (CountryRef, StateRef, MarketRef)
        if isinstance(left, object_refs) or isinstance(right, object_refs):
            if not isinstance(left, object_refs) or not isinstance(right, object_refs) or op not in ("=", "!=", "?="):
                raise UnsupportedSubset(f"unsupported typed object comparison: {left!r} {op} {right!r}")
            if type(left) is not type(right):
                return False
            return left == right if op in ("=", "?=") else left != right
        if type(left) is GoodsRef or type(right) is GoodsRef:
            if type(left) is not type(right) or op not in ("=", "!="):
                raise UnsupportedSubset(f"unsupported typed goods comparison: {left!r} {op} {right!r}")
            return left == right
        elif type(left) is bool or type(right) is bool:
            if type(left) is not bool or type(right) is not bool or op not in ("=", "!=", "?="):
                raise UnsupportedSubset(f"unsupported typed bool comparison: {left!r} {op} {right!r}")
        else:
            self._numeric(left)
            self._numeric(right)
        return super().compare(left, "=" if op == "?=" else op, right)

    def condition(self, node, tag):
        if self._current is None:
            with self._chain(self.country_ref(tag)):
                return self.condition(node, tag)
        key, op, value = node
        if key in ("AND", "OR", "NOT", "NOR"):
            if not isinstance(value, list):
                raise UnsupportedSubset(f"logical block required: {node}")
            if key == "AND":
                return all(self.condition(child, tag) for child in value)
            if key == "OR":
                return any(self.condition(child, tag) for child in value)
            if key == "NOT":
                return not all(self.condition(child, tag) for child in value)
            return not any(self.condition(child, tag) for child in value)
        if key == "any_scope_state":
            if op != "=" or not isinstance(value, list):
                raise UnsupportedSubset(f"unsupported state iteration: {node}")
            top = self._stack[-1] if self._stack else None
            if not isinstance(top, CountryRef):
                raise UnsupportedSubset("any_scope_state requires an actual country scope")
            previous = self.state_scope, self.building_scope, self.pop_scope
            try:
                for state in self.countries[top.tag].get("states", []):
                    ref = StateRef(state["_sid"])
                    self.state_scope = state
                    self.building_scope = self.pop_scope = None
                    self._stack.append(ref)
                    try:
                        if self.conditions(value, tag):
                            return True
                    finally:
                        self._stack.pop()
                return False
            finally:
                self.state_scope, self.building_scope, self.pop_scope = previous
        if key in ("any_scope_building", "any_scope_pop", "workplace"):
            previous = self.state_scope, self.building_scope, self.pop_scope
            try:
                return super().condition(node, tag)
            finally:
                self.state_scope, self.building_scope, self.pop_scope = previous
        if key == "state_goods_production":
            if op != "=" or not isinstance(value, list) or not isinstance(self._stack[-1] if self._stack else None, StateRef):
                raise UnsupportedSubset(f"state_goods_production requires an actual state scope: {node}")
            target = next((v for k, o, v in value if k == "target" and o == "="), None)
            amount = next(((o, v) for k, o, v in value if k == "value"), None)
            if target is None or amount is None or len(value) != 2:
                raise UnsupportedSubset(f"unsupported state_goods_production operands: {node}")
            if not isinstance(target, str) or not target.startswith("sg:"):
                raise UnsupportedSubset(f"state_goods_production target must use the sg: goods form: {node}")
            goods = self._value(target, optional=True)
            if goods is _MISSING:
                return False
            produced = self.state_scope.get("production", {}).get(goods.name, 0)
            return self.compare(produced, amount[0], self._value(amount[1]))
        if key in ("state_imports", "state_exports"):
            if op != "=" or not isinstance(value, list) or not isinstance(self._stack[-1] if self._stack else None, StateRef):
                raise UnsupportedSubset(f"{key} requires an actual state scope: {node}")
            target = next((v for k, o, v in value if k == "target" and o == "="), None)
            goods_node = next((v for k, o, v in value if k == "goods" and o == "="), None)
            amount = next(((o, v) for k, o, v in value if k == "value"), None)
            if target is None or goods_node is None or amount is None or len(value) != 3:
                raise UnsupportedSubset(f"unsupported {key} operands: {node}")
            if not isinstance(goods_node, str) or not goods_node.startswith("g:"):
                raise UnsupportedSubset(f"{key} goods must use the g: goods form: {node}")
            goods = self._value(goods_node, optional=True)
            other = self._value(target, optional=True)
            if goods is _MISSING or other is _MISSING or not isinstance(other, StateRef):
                return False
            field_name = "source" if key == "state_imports" else "target"
            matched = [float(row.get("value", 0)) for row in self.state_scope.get(key.removeprefix("state_"), [])
                       if row.get(field_name) == other.sid and row.get("goods") == goods.name]
            return any(self.compare(row, amount[0], self._value(amount[1])) for row in matched)
        if key == "has_port_state":
            if not isinstance(self._stack[-1] if self._stack else None, StateRef):
                raise UnsupportedSubset(f"has_port_state requires an actual state scope: {node}")
            if op != "=" or value not in ("yes", "no"):
                raise UnsupportedSubset(f"unsupported boolean predicate: {node}")
            return bool(self.state_scope.get("port")) == (value == "yes")
        if key == "market" and not isinstance(value, list):
            top = self._stack[-1] if self._stack else None
            if op not in ("=", "!=", "?="):
                raise UnsupportedSubset(f"unsupported market comparison: {node}")
            left = self._market_ref(top) if top is not None else _MISSING
            right = self._value(value, optional=(op == "?="))
            if left is _MISSING or right is _MISSING:
                if op == "?=":
                    return False
                raise UnsupportedSubset(f"undefined market comparison value: {node}")
            return self.compare(left, op, right)
        if key == "market":
            top = self._stack[-1] if self._stack else None
            if op != "=" or not isinstance(value, list) or not isinstance(top, (CountryRef, StateRef)):
                raise UnsupportedSubset(f"market scope requires an actual country or state scope: {node}")
            ref = self._market_ref(top)
            if ref is _MISSING:
                return False
            with self._market_context(ref):
                return self.conditions(value, tag)
        if key == "is_adjacent_to_market":
            top = self._stack[-1] if self._stack else None
            if not isinstance(top, MarketRef) or op != "=":
                raise UnsupportedSubset(f"is_adjacent_to_market requires an actual market scope: {node}")
            other = self._value(value, optional=True)
            if other is _MISSING or not isinstance(other, MarketRef):
                return False
            return other.mid in self.markets.setdefault(top.mid, {"owner": None, "adjacent": set()}).get("adjacent", set())
        if key in ("owner", "is_owned_by"):
            if op not in ("=", "?=") or self.state_scope is None:
                raise UnsupportedSubset(f"unsupported state ownership predicate: {node}")
            target = self._value(value, optional=True)
            if target is _MISSING:
                return False
            if not isinstance(target, CountryRef):
                raise UnsupportedSubset("country reference required for state owner")
            owner = self.state_scope.get("owner")
            if "owner" not in self.state_scope:
                owner = self.country_ref(tag) if self.state_scope.get("owned", False) else _MISSING
            elif isinstance(owner, str):
                owner = self.country_ref(owner) if owner in self.countries else _MISSING
            return self._present(owner) and self.compare(owner, "=", target)
        if key in ("always", "is_subject", "in_default", "is_at_war", "country_has_voting_franchise", "building_has_goods_shortage", "pop_has_primary_culture", "is_employed"):
            if op != "=" or value not in ("yes", "no"):
                raise UnsupportedSubset(f"unsupported boolean predicate: {node}")
        if key == "exists":
            if op != "=":
                raise UnsupportedSubset(f"unsupported exists comparison: {node}")
            return self._present(self._value(value, optional=True))
        if key == "is_country_alive":
            return self.compare(bool(self._alive(self._current)), op, self._value(value))
        if self._scope_token(key):
            left = self._value(key, optional=True)
            if isinstance(value, list):
                if op in ("<", "<=", ">", ">="):
                    if left is _MISSING:
                        return False
                    return self.compare(left, op, self._value(value))
                if op not in ("=", "?="):
                    raise UnsupportedSubset(f"unsupported country scope operator: {node}")
                if left is _MISSING:
                    return False
                if isinstance(left, StateRef):
                    with self._state_context(left):
                        return self.conditions(value, self._state_owner_tag(left))
                if isinstance(left, MarketRef):
                    with self._market_context(left):
                        return self.conditions(value, tag)
                if not isinstance(left, CountryRef):
                    raise UnsupportedSubset(f"country scope requires country reference: {key}")
                with self._scope(left):
                    return self.conditions(value, left.tag)
            right = self._value(value, optional=(op == "?="))
            if left is _MISSING or right is _MISSING:
                if op == "?=":
                    return False
                # Generated inline guards compare an optional served marker
                # before its first assignment. A missing country variable is
                # unequal to a present round; saved event-chain values remain
                # strict because their absence is a broken capture.
                if key.startswith("var:") and left is _MISSING and right is not _MISSING and op in ("=", "!="):
                    return op == "!="
                raise UnsupportedSubset(f"undefined comparison value: {node}")
            return self.compare(left, op, right)
        if key.startswith("relations:"):
            target = self._value(key[len("relations:"):], optional=True)
            if not self._present(target):
                return False
            relations = self.countries[tag].get("relations", {})
            if target.tag not in relations:
                raise UnsupportedSubset(f"undefined relation fact: {tag} -> {target.tag}")
            return self.compare(relations[target.tag], op, self._value(value))
        if key in ("gold_reserves", "net_fixed_income", "yearly_gross_income", "scaled_debt", "bureaucracy", "army_size", "legitimacy", "authority"):
            return self.compare(self._value(key), op, self._value(value))
        return super().condition(node, tag)

    def _variable(self, key, body, tag):
        allowed = {"name", "value", "days", "months"} if key == "set_variable" else ({"name", "min", "max"} if key == "clamp_variable" else {"name", "add", "multiply", "divide"})
        fields = self._fields(body, allowed, {"name"})
        name = fields["name"]
        if not isinstance(name, str):
            raise UnsupportedSubset("unsupported variable name")
        state = self.countries[tag]
        if key == "set_variable":
            if "value" not in fields and not ({"days", "months"} & fields.keys()):
                raise UnsupportedSubset("unsupported variable without value/timer")
            value = self._value(fields.get("value", "1"))
            timers = {}
            for unit in ("days", "months"):
                if unit in fields:
                    duration = self._numeric(self._value(fields[unit]))
                    if duration <= 0 or int(duration) != duration:
                        raise UnsupportedSubset(f"unsupported timer duration: {duration}")
                    timers[unit] = int(duration)
            state[name] = value
            for unit, mapping in (("days", self.days_until_expiry), ("months", self.months_until_expiry)):
                mapping[tag].pop(name, None)
                if unit in timers:
                    mapping[tag][name] = (self.date + timedelta(days=timers[unit])) if unit == "days" else _add_months(self.date, timers[unit])
            return
        old = self._numeric(self._value("var:" + name))
        if key == "clamp_variable":
            if set(fields) != {"name", "min", "max"}:
                raise UnsupportedSubset("unsupported clamp fields")
            low, high = (self._numeric(self._value(fields[k])) for k in ("min", "max"))
            if low > high:
                raise UnsupportedSubset("unsupported inverted clamp")
            value = min(high, max(low, old))
        else:
            operations = set(fields) - {"name"}
            if len(operations) != 1:
                raise UnsupportedSubset("unsupported change_variable fields")
            action = operations.pop()
            amount = self._numeric(self._value(fields[action]))
            if action == "divide" and amount == 0:
                raise UnsupportedSubset("unsupported numeric division by zero")
            value = old + amount if action == "add" else old * amount if action == "multiply" else old / amount
        state[name] = self._numeric(value)

    def execute(self, nodes, tag):
        if self._current is None:
            with self._chain(self.country_ref(tag)):
                return self.execute(nodes, tag)
        index = 0
        while index < len(nodes):
            key, op, body = nodes[index]
            index += 1
            top = self._stack[-1] if self._stack else None
            if (isinstance(top, (StateRef, MarketRef))
                    and key not in ("save_scope_as", "custom_tooltip", "every_scope_state", "if", "else_if", "else")
                    and not (self._scope_token(key) and isinstance(body, list))):
                raise UnsupportedSubset(f"effect {key} requires an actual country scope")
            # Reuse the existing branch executor intact, including else chains.
            if key == "if":
                end = index
                while end < len(nodes) and nodes[end][0] in ("else_if", "else"):
                    end += 1
                super().execute(nodes[index - 1:end], tag)
                index = end
            elif self._scope_token(key) and isinstance(body, list):
                if op not in ("=", "?="):
                    raise UnsupportedSubset(f"unsupported country scope effect: {key} {op}")
                target = self._value(key, optional=(op == "?="))
                if target is _MISSING:
                    continue
                if isinstance(target, StateRef):
                    with self._state_context(target):
                        self.execute(body, self._state_owner_tag(target))
                    continue
                if isinstance(target, MarketRef):
                    with self._market_context(target):
                        self.execute(body, tag)
                    continue
                if not isinstance(target, CountryRef):
                    raise UnsupportedSubset(f"country scope requires country reference: {key}")
                with self._scope(target):
                    self.execute(body, target.tag)
            elif key == "every_scope_state":
                if op != "=" or not isinstance(body, list):
                    raise UnsupportedSubset(f"unsupported state effect iterator: {key} {op}")
                top = self._stack[-1] if self._stack else None
                if not isinstance(top, CountryRef):
                    raise UnsupportedSubset("every_scope_state requires an actual country scope")
                limit_nodes = [child for child in body if child[0] == "limit"]
                if len(limit_nodes) != 1:
                    raise UnsupportedSubset("every_scope_state requires exactly one limit")
                body_nodes = [child for child in body if child[0] != "limit"]
                for state in self.countries[top.tag].get("states", []):
                    ref = StateRef(state["_sid"])
                    with self._state_context(ref):
                        if self.conditions(limit_nodes[0][2], tag):
                            self.execute(body_nodes, tag)
            elif op != "=":
                raise UnsupportedSubset(f"unsupported effect operator: {key} {op}")
            elif key in ("set_variable", "change_variable", "clamp_variable"):
                self._variable(key, body, tag)
            elif key == "save_scope_as":
                if not isinstance(body, str):
                    raise UnsupportedSubset("unsupported saved scope name")
                top = self._stack[-1] if self._stack else None
                self._saved[body] = top if isinstance(top, (StateRef, MarketRef)) else self._current
            elif key == "save_scope_value_as":
                fields = self._fields(body, {"name", "value"}, {"name", "value"})
                value = self._value(fields["value"])
                if type(value) is not bool and not isinstance(value, (StateRef, MarketRef)):
                    self._numeric(value)
                self._saved[fields["name"]] = value
            elif key == "trigger_event":
                fields = self._fields(body, {"id", "days", "months"}, {"id"})
                if fields["id"] not in self.event_defs:
                    raise UnsupportedSubset(f"unsupported unknown event: {fields['id']}")
                if "days" in fields and "months" in fields:
                    raise UnsupportedSubset("mixed event delay units")
                delay_key = "months" if "months" in fields else "days"
                delay = self._numeric(self._value(fields.get(delay_key, "0")))
                if delay < 0 or int(delay) != delay:
                    raise UnsupportedSubset(f"unsupported event delay: {delay}")
                due = _add_months(self.date, int(delay)) if delay_key == "months" else self.date + timedelta(days=int(delay))
                self.jobs.append(EventJob(len(self.jobs) + 1, self._current, fields["id"], (due - self._epoch).days, delay_key in fields, tuple(sorted(self._saved.items()))))
                self.events.append((tag, fields["id"]))
            elif key == "add_modifier":
                fields = self._fields(body, {"name", "modifier", "days", "months"})
                identity = fields.get("modifier", fields.get("name"))
                if not isinstance(identity, str):
                    raise UnsupportedSubset("modifier identity required")
                if identity == "ywc_v03_kor_paid_instructor_training" and identity not in self.modifier_defs:
                    raise UnsupportedSubset("instructor modifier has no formal definition")
                self._remove_modifier(tag, identity)
                record = (tag, fields)
                self.modifiers.append(record)
                if "days" in fields or "months" in fields:
                    if "days" in fields and "months" in fields:
                        raise UnsupportedSubset("mixed modifier duration")
                    unit = "days" if "days" in fields else "months"
                    duration = self._numeric(self._value(fields[unit]))
                    if duration <= 0 or int(duration) != duration:
                        raise UnsupportedSubset("invalid modifier duration")
                    self.modifier_expires[id(fields)] = (self.date + timedelta(days=int(duration))) if unit == "days" else _add_months(self.date, int(duration))
            elif key == "remove_modifier":
                self._remove_modifier(tag, body)
            elif key == "remove_variable":
                self.countries[tag].pop(body, None)
                self.days_until_expiry[tag].pop(body, None)
                self.months_until_expiry[tag].pop(body, None)
            elif key == "add_treasury":
                self.treasury[tag] += self._numeric(self._value(body))
            elif key == "custom_tooltip":
                if isinstance(body, str):
                    continue
                if not isinstance(body, list):
                    raise UnsupportedSubset("unsupported custom_tooltip wrapper")
                metadata = self._fields([node for node in body if node[0] == "text"], {"text"}, {"text"})
                if not isinstance(metadata["text"], str):
                    raise UnsupportedSubset("unsupported custom_tooltip text metadata")
                self.execute([node for node in body if node[0] != "text"], tag)
            else:
                super().execute([(key, op, body)], tag)

    def _remove_modifier(self, tag, identity):
        retained = []
        for record in self.modifiers:
            owner, fields = record
            if owner == tag and fields.get("modifier", fields.get("name")) == identity:
                self.modifier_expires.pop(id(fields), None)
            else:
                retained.append(record)
        self.modifiers = retained

    def _advance_to(self, target):
        if target < self.date:
            raise UnsupportedSubset("calendar cannot move backwards")
        self.date = target
        self.day = (target - self._epoch).days
        for tag in self.countries:
            for mapping in (self.days_until_expiry[tag], self.months_until_expiry[tag]):
                for name, expiry in list(mapping.items()):
                    if target >= expiry:
                        mapping.pop(name)
                        self.countries[tag].pop(name, None)
        retained = []
        for record in self.modifiers:
            expiry = self.modifier_expires.get(id(record[1]))
            if expiry is not None and target >= expiry:
                self.modifier_expires.pop(id(record[1]), None)
            else:
                retained.append(record)
        self.modifiers = retained

    def advance_days(self, days=1):
        if type(days) is not int or days < 0:
            raise UnsupportedSubset(f"unsupported elapsed days: {days}")
        self._advance_to(self.date + timedelta(days=days))

    def advance_months(self, months=1):
        if type(months) is not int or months < 0:
            raise UnsupportedSubset(f"unsupported elapsed months: {months}")
        self._advance_to(_add_months(self.date, months))
        if not self._delivery_owns_months:
            self.elapsed_months += months

    def deliver(self, arc, want):
        # Strict.deliver already increments elapsed_months after each virtual
        # advance_months call. Keep that original loop, with one clear owner.
        previous = self._delivery_owns_months
        self._delivery_owns_months = True
        try:
            return super().deliver(arc, want)
        finally:
            self._delivery_owns_months = previous

    def display_job(self, job):
        if self.day < job.due_day or not self._alive(job.recipient):
            return False
        with self._chain(job.recipient, job.saved):
            event = self.event_defs[job.event_id]
            if not self.conditions(field(event, "trigger"), job.recipient.tag):
                return False
            if job not in self._displayed:
                self.execute(field(event, "immediate"), job.recipient.tag)
                self._displayed[job] = tuple(sorted(self._saved.items()))
            return True

    def run_due_hidden(self):
        """Run each due hidden event once; caller chooses ordering versus pulse."""
        for job in list(self.jobs):
            if job in self._displayed or self.day < job.due_day or not self._alive(job.recipient):
                continue
            event = self.event_defs[job.event_id]
            if field(event, "hidden") != "yes":
                continue
            with self._chain(job.recipient, job.saved):
                if self.conditions(field(event, "trigger"), job.recipient.tag):
                    self.execute(field(event, "immediate"), job.recipient.tag)
                self._displayed[job] = tuple(sorted(self._saved.items()))

    def run_country_monthly(self, tag="KOR"):
        action = self.on_actions["on_monthly_pulse_country"]
        with self._chain(self.country_ref(tag)):
            self.execute(field(action, "effect"), tag)

    def job_options(self, job):
        if job not in self._displayed or not self._alive(job.recipient):
            return {}
        with self._chain(job.recipient, self._displayed[job]):
            return {field(option, "name").rsplit(".", 1)[-1]: self.conditions(field(option, "trigger"), job.recipient.tag)
                    for key, _, option in self.event_defs[job.event_id] if key == "option"}

    def choose_job(self, job, key):
        if job not in self._displayed:
            raise UnsupportedSubset("unsupported choice before event display")
        if not self._alive(job.recipient):
            return False
        with self._chain(job.recipient, self._displayed[job]):
            options = [option for name, _, option in self.event_defs[job.event_id] if name == "option" and field(option, "name").endswith("." + key)]
            if len(options) != 1:
                raise UnsupportedSubset(f"unsupported option: {key}")
            self.execute([node for node in options[0] if node[0] not in ("name", "trigger", "ai_chance")], job.recipient.tag)
            return True
