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
with optional days delay, and treasury value/multiply. Existing local factual
predicates/scripted helpers delegate to Strict. No general script-value parser,
random scopes, temporary scopes, flags, AI simulation, treaties or transactions.
The supported stack contains countries only: PREV/this/local-variable reads
inside inherited state/building/pop iterators fail explicitly rather than
mistaking that actual non-country scope for a country. Explicit root/saved
country reads and legacy state is_owned_by checks remain supported there.
Legacy owned=True facts mean owner=containing country; an explicit owner
overrides it. is_owned_by is fixture compatibility, not verified engine syntax.
The inherited calendar approximation is 30 days/month, not a game calendar.
Scalar custom_tooltip labels are metadata; block wrappers execute their source
children after validating/removing only the scalar text localization field.
Direct advance_months owns its elapsed counter; inherited deliver owns that
same increment while its original waiting loop is active.
"""
from contextlib import contextmanager
from dataclasses import dataclass
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
class EventJob:
    serial: int
    recipient: CountryRef
    event_id: str
    due_day: int
    explicit_delay: bool
    saved: tuple


_MISSING = object()


class PartnerWorld(Strict):
    def __init__(self, countries, events=""):
        super().__init__("kor")
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
        self.jobs = []
        self._displayed = {}
        self._delivery_owns_months = False
        self.day = 0

    def country_ref(self, tag):
        if tag not in self.countries:
            raise UnsupportedSubset(f"undefined country: {tag}")
        return CountryRef(tag, self._incarnations[tag])

    def _present(self, ref):
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

    @contextmanager
    def _chain(self, recipient, saved=()):
        previous = self._current, self._root, self._prev, self._saved
        self._current = self._root = recipient
        self._prev = None
        self._saved = dict(saved)
        try:
            yield
        finally:
            self._current, self._root, self._prev, self._saved = previous

    @contextmanager
    def _scope(self, target):
        previous = self._current, self._prev
        self._prev, self._current = self._current, target
        try:
            yield
        finally:
            self._current, self._prev = previous

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
        return (isinstance(token, str) and (token.lower() in ("this", "root", "prev")
                or token.startswith(("c:", "scope:", "var:"))
                or ".var:" in token))

    def _value(self, token, *, optional=False):
        if isinstance(token, list):
            fields = self._fields(token, {"value", "multiply"}, {"value"})
            value = self._numeric(self._value(fields["value"]))
            return self._numeric(value * self._numeric(self._value(fields.get("multiply", "1"))))
        if not isinstance(token, str):
            raise UnsupportedSubset(f"unsupported value: {token!r}")
        if any(scope is not None for scope in (self.state_scope, self.building_scope, self.pop_scope)):
            if token.lower() in ("prev", "this") or token.lower().startswith(("prev.var:", "this.var:")) or token.startswith("var:"):
                raise UnsupportedSubset("unsupported PREV/this/local variable read inside non-country iterator")
        if ".var:" in token:
            owner, name = token.rsplit(".var:", 1)
            ref = self._value(owner, optional=True)
            result = self.countries[ref.tag].get(name, _MISSING) if self._present(ref) else _MISSING
        elif token.lower() in ("this", "root", "prev"):
            result = {"this": self._current, "root": self._root, "prev": self._prev}[token.lower()]
            if result is None:
                result = _MISSING
        elif token.startswith("c:"):
            result = self.country_ref(token[2:]) if token[2:] in self.countries else _MISSING
        elif token.startswith("scope:"):
            result = self._saved.get(token[6:], _MISSING)
        elif token.startswith("var:"):
            result = self.countries[self._current.tag].get(token[4:], _MISSING)
        elif token in ("yes", "no"):
            result = token == "yes"
        elif re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", token):
            result = float(token)
            self._numeric(result)
        elif token in ("yearly_gross_income", "gdp", "scaled_debt", "gold_reserves", "net_fixed_income", "bureaucracy", "army_size", "legitimacy", "authority"):
            result = self.countries[self._current.tag].get(token, _MISSING)
            if token == "gold_reserves" and result is not _MISSING:
                result += self.treasury[self._current.tag]
        else:
            raise UnsupportedSubset(f"unsupported value token: {token}")
        if isinstance(result, CountryRef) and not self._present(result):
            result = _MISSING
        if result is _MISSING and not optional:
            raise UnsupportedSubset(f"undefined value/country: {token}")
        if result is not _MISSING and not isinstance(result, CountryRef):
            if type(result) is not bool:
                self._numeric(result)
        return result

    def compare(self, left, op, right):
        if isinstance(left, CountryRef) or isinstance(right, CountryRef):
            if not isinstance(left, CountryRef) or not isinstance(right, CountryRef) or op not in ("=", "!=", "?="):
                raise UnsupportedSubset(f"unsupported typed country comparison: {left!r} {op} {right!r}")
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
        if key in ("any_scope_state", "any_scope_building", "any_scope_pop", "workplace"):
            previous = self.state_scope, self.building_scope, self.pop_scope
            try:
                return super().condition(node, tag)
            finally:
                self.state_scope, self.building_scope, self.pop_scope = previous
        if key == "is_owned_by":
            if op not in ("=", "?=") or self.state_scope is None:
                raise UnsupportedSubset(f"unsupported state ownership predicate: {node}")
            target = self._value(value, optional=True)
            if target is _MISSING:
                return False
            if not isinstance(target, CountryRef):
                raise UnsupportedSubset("country reference required for state owner")
            owner = self.state_scope.get("owner")
            if owner is None:
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
                if op not in ("=", "?="):
                    raise UnsupportedSubset(f"unsupported country scope operator: {node}")
                if left is _MISSING:
                    return False
                if not isinstance(left, CountryRef):
                    raise UnsupportedSubset(f"country scope requires country reference: {key}")
                with self._scope(left):
                    return self.conditions(value, left.tag)
            right = self._value(value, optional=(op == "?="))
            if left is _MISSING or right is _MISSING:
                if op == "?=":
                    return False
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
                    mapping[tag][name] = timers[unit]
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
                if not isinstance(target, CountryRef):
                    raise UnsupportedSubset(f"country scope requires country reference: {key}")
                with self._scope(target):
                    self.execute(body, target.tag)
            elif op != "=":
                raise UnsupportedSubset(f"unsupported effect operator: {key} {op}")
            elif key in ("set_variable", "change_variable", "clamp_variable"):
                self._variable(key, body, tag)
            elif key == "save_scope_as":
                if not isinstance(body, str):
                    raise UnsupportedSubset("unsupported saved scope name")
                self._saved[body] = self._current
            elif key == "save_scope_value_as":
                fields = self._fields(body, {"name", "value"}, {"name", "value"})
                value = self._value(fields["value"])
                if type(value) is not bool:
                    self._numeric(value)
                self._saved[fields["name"]] = value
            elif key == "trigger_event":
                fields = self._fields(body, {"id", "days"}, {"id"})
                if fields["id"] not in self.event_defs:
                    raise UnsupportedSubset(f"unsupported unknown event: {fields['id']}")
                days = self._numeric(self._value(fields.get("days", "0")))
                if days < 0 or int(days) != days:
                    raise UnsupportedSubset(f"unsupported event delay: {days}")
                self.jobs.append(EventJob(len(self.jobs) + 1, self._current, fields["id"], self.day + int(days), "days" in fields, tuple(sorted(self._saved.items()))))
                self.events.append((tag, fields["id"]))
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

    def advance_days(self, days=1):
        if type(days) is not int or days < 0:
            raise UnsupportedSubset(f"unsupported elapsed days: {days}")
        super().advance_days(days)
        self.day += days

    def advance_months(self, months=1):
        if type(months) is not int or months < 0:
            raise UnsupportedSubset(f"unsupported elapsed months: {months}")
        super().advance_months(months)
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
