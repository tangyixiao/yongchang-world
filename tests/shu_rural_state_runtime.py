"""Bounded, cooperative native state-object scope support for SHU literal worlds."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
import calendar
from pathlib import Path
import re

from clausewitz_harness import parse
from kor_partner_protocol_runtime import StateRef


@dataclass(frozen=True)
class _CountryScope:
    tag: str


class StateScopeMixin:
    """Place before a SHU literal world in the MRO; no country/source substitution.

    Supports country ROOT/PREV/this/c: scopes, explicit save_scope_as aliases,
    native first-state ROOT-variable capture and strict StateRef comparisons.
    It does not supply market/pop/building object references or business facts.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._state_scope_setup()

    def _state_scope_setup(self):
        if not hasattr(self, "_state_scope_stack"):
            self._state_scope_stack = ()
            self._state_scope_saved = {}
            self._state_scope_objects = {}
            self._state_scope_serial = 0

    def _state_intern(self, state):
        if not isinstance(state, dict):
            raise AssertionError(("invalid_native_state_object", state))
        for sid, actual in self._state_scope_objects.items():
            if actual is state:
                return StateRef(sid)
        self._state_scope_serial += 1
        self._state_scope_objects[self._state_scope_serial] = state
        return StateRef(self._state_scope_serial)

    def _state_object(self, reference):
        if (type(reference) is not StateRef or type(reference.sid) is not int
                or reference.sid <= 0 or reference.sid not in self._state_scope_objects):
            raise AssertionError(("unknown_native_state_reference", reference))
        original = self._state_scope_objects[reference.sid]
        locations = sum(any(state is original for state in facts.get("states", []))
                        for facts in self.countries.values())
        if locations > 1:
            raise AssertionError(("ambiguous_native_state_location", reference))
        return original if locations == 1 else None

    @contextmanager
    def _state_context(self, target):
        names = ("state_scope", "pop_scope", "building_scope", "scope_ig")
        previous = tuple(getattr(self, name, None) for name in names)
        stack = self._state_scope_stack
        if type(target) is StateRef:
            state = self._state_object(target)
            if state is None:
                raise AssertionError(("unavailable_native_state_effect", target))
        elif isinstance(target, _CountryScope) and target.tag in self.countries:
            state = None
        else:
            raise AssertionError(("unsupported_native_scope_object", target))
        self.state_scope, self.pop_scope, self.building_scope, self.scope_ig = state, None, None, None
        self._state_scope_stack = stack + (target,)
        try:
            yield
        finally:
            self.state_scope, self.pop_scope, self.building_scope, self.scope_ig = previous
            self._state_scope_stack = stack

    @staticmethod
    def _state_token(token):
        return (isinstance(token, str) and
                (token.lower() in ("root", "prev", "this", "prev.prev")
                 or token.startswith(("c:", "scope:", "var:")) or ".var:" in token))

    def _state_country(self):
        frame = self._state_scope_stack[-1]
        if not isinstance(frame, _CountryScope):
            raise AssertionError("country variable operation inside state/pop/building scope")
        return frame.tag

    def _state_value(self, token):
        if not isinstance(token, str):
            raise AssertionError(("malformed_native_reference_token", token))
        if ".var:" in token:
            owner, name = token.rsplit(".var:", 1)
            frame = self._state_value(owner)
            if not isinstance(frame, _CountryScope) or name not in self.countries[frame.tag]:
                raise AssertionError(("missing_native_country_variable", token))
            return self.countries[frame.tag][name]
        if token.startswith("var:"):
            tag = self._state_country()
            if token[4:] not in self.countries[tag]:
                raise AssertionError(("missing_native_country_variable", token))
            return self.countries[tag][token[4:]]
        if token.lower() in ("root", "this", "prev", "prev.prev"):
            if token.lower() != "root" and any(scope is not None for scope in
                                                (self.pop_scope, self.building_scope, self.scope_ig)):
                raise AssertionError(("untyped_inner_scope_has_no_state_reference", token))
            index = 0 if token.lower() == "root" else -{"this": 1, "prev": 2, "prev.prev": 3}[token.lower()]
            if len(self._state_scope_stack) < (1 if index == 0 else -index):
                raise AssertionError(("missing_native_previous_scope", token))
            return self._state_scope_stack[index]
        if token.startswith("scope:"):
            name = token[6:]
            if name in self._state_scope_saved:
                return self._state_scope_saved[name]
            # Keep the inherited numeric callback/value scopes strict; never
            # coerce an arbitrary string/object from that namespace to a state.
            if name in self.scopes:
                actual = self.scopes[name]
                if type(actual) is bool: return actual
                return self._state_number(actual, token)
            raise AssertionError(("missing_native_saved_scope", token))
        if token.startswith("c:"):
            if token[2:] not in self.countries:
                raise AssertionError(("unknown_native_country_scope", token))
            return _CountryScope(token[2:])
        if token.startswith(("ROOT.", "root.")) and ".var:" not in token:
            frame = self._state_scope_stack[0]
            name = token.split(".", 1)[1]
            if not isinstance(frame, _CountryScope) or name not in self.countries[frame.tag]:
                raise AssertionError(("missing_native_root_numeric_fact", token))
            return self._state_number(self.countries[frame.tag][name], token)
        if token in ("yearly_gross_income", "gdp", "scaled_debt", "gold_reserves",
                     "net_fixed_income", "bureaucracy", "legitimacy", "authority"):
            current = self._state_country()
            if token not in self.countries[current]:
                raise AssertionError(("missing_native_country_numeric_fact", token))
            return self._state_number(self.countries[current][token], token)
        if token in ("yes", "no"):
            return token == "yes"
        if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", token):
            return self._number(token, token)
        raise AssertionError(("unsupported_native_reference_token", token))

    def _state_number(self, value, node):
        if type(value) not in (int, float):
            raise AssertionError(("native_numeric_value_required", value, node))
        return self._number(value, node)

    def _reference_number(self, value, node):
        if self._state_token(value) or (isinstance(value, str) and value.startswith(("ROOT.", "root."))):
            self._state_scope_setup()
            if not self._state_scope_stack:
                with self._state_context(_CountryScope(self.tag)):
                    return self._state_number(self._state_value(value), node)
            return self._state_number(self._state_value(value), node)
        return super()._reference_number(value, node)

    def _state_compare(self, left, op, right):
        if op not in ("=", "!=", "?=", ">", ">=", "<", "<="):
            raise AssertionError(("unsupported_state_reference_operator", op))
        if isinstance(left, (StateRef, _CountryScope)) or isinstance(right, (StateRef, _CountryScope)):
            if type(left) is not type(right) or op not in ("=", "!=", "?="):
                raise AssertionError(("non_numeric_native_object_comparison", left, op, right))
            for item in (left, right):
                if type(item) is StateRef and self._state_object(item) is None:
                    raise AssertionError(("unavailable_native_state_comparison", item))
            return (left != right) if op == "!=" else (left == right)
        if type(left) is bool or type(right) is bool:
            if type(left) is not bool or type(right) is not bool or op not in ("=", "!=", "?="):
                raise AssertionError(("invalid_native_boolean_comparison", left, op, right))
        else:
            if type(left) not in (int, float) or type(right) not in (int, float):
                raise AssertionError(("invalid_native_numeric_comparison", left, right))
            self._number(left, left); self._number(right, right)
        return self.compare(left, "=" if op == "?=" else op, right)

    def _ordinary_numeric_guard(self, node, tag):
        """Identify inherited scalar guards without dereferencing absent state objects.

        Country script variables are not mandatory current world facts. In
        particular, generated reservation/served guards run before assignment.
        Their absence semantics belong to the inherited numeric dispatcher.
        """
        key, op, value = node
        if (not key.startswith("var:") or ".var:" in key or not isinstance(value, str)
                or op not in ("=", "!=", "?=", ">", ">=", "<", "<=")):
            return False
        variables = self.countries[tag]
        missing = object()
        left = variables.get(key[4:], missing)
        if value.startswith("var:") and ".var:" not in value:
            right = variables.get(value[4:], missing)
        elif value.startswith("scope:") and ".var:" not in value:
            name = value[6:]
            if name in self._state_scope_saved or name not in self.scopes:
                return False
            right = self.scopes[name]
        elif re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value):
            right = self._number(value, node)
        else:
            return False
        if any(isinstance(item, (StateRef, _CountryScope)) or type(item) is bool for item in (left, right)):
            return False
        for item in (left, right):
            if item is not missing:
                self._state_number(item, node)
        return True

    def condition(self, node, tag):
        self._state_scope_setup()
        if not isinstance(node, (tuple, list)) or len(node) != 3:
            raise AssertionError(("malformed_native_state_condition", node))
        key, op, value = node
        if self._ordinary_numeric_guard(node, tag):
            return super().condition(node, tag)
        handled = key in ("any_scope_state", "exists") or self._state_token(key)
        if handled and not self._state_scope_stack:
            with self._state_context(_CountryScope(tag)):
                return self.condition(node, tag)
        if self._state_scope_stack and key in ("AND", "OR", "NOT", "NOR"):
            if op != "=" or not isinstance(value, list):
                raise AssertionError(("malformed_native_state_logic", node))
            if key in ("AND", "NOT"):
                matched = all(self.condition(child, tag) for child in value)
            else:
                matched = any(self.condition(child, tag) for child in value)
            return not matched if key in ("NOT", "NOR") else matched
        if key == "any_scope_state":
            current = self._state_country()
            if op != "=" or not isinstance(value, list) or not value:
                raise AssertionError(("malformed_native_state_query", node))
            states = self.countries[current].get("states")
            if not isinstance(states, list):
                raise AssertionError(("missing_native_states", current))
            for state in states:
                with self._state_context(self._state_intern(state)):
                    if self.conditions(value, current): return True
            return False
        if self._state_scope_stack and key == "owner":
            if (type(self._state_scope_stack[-1]) is not StateRef or
                    self.pop_scope is not None or self.building_scope is not None or self.scope_ig is not None):
                raise AssertionError(("owner_requires_actual_state_scope", node))
            if op != "=": raise AssertionError(("unsupported_native_owner_operator", node))
            target = self._state_value(value)
            if not isinstance(target, _CountryScope):
                raise AssertionError(("owner_requires_country_reference", node))
            owner = self._fact(self.state_scope, "owner", node)
            if not isinstance(owner, str) or owner not in self.countries:
                raise AssertionError(("invalid_native_owner_fact", owner))
            return owner == target.tag
        if self._state_scope_stack and key == "has_variable":
            if op != "=" or not isinstance(value, str): raise AssertionError(node)
            return value in self.countries[self._state_country()]
        if key == "exists":
            if op != "=": raise AssertionError(node)
            try: actual = self._state_value(value)
            except AssertionError:
                if isinstance(value, str) and value.startswith(("var:", "scope:")): return False
                raise
            if type(actual) is StateRef: return self._state_object(actual) is not None
            if isinstance(actual, _CountryScope): return actual.tag in self.countries
            if isinstance(value, str) and value.startswith("scope:") and type(actual) in (int, float, bool):
                return True  # Native inline numeric saved-value scope, as in PartnerWorld.
            raise AssertionError(("exists_requires_native_object", actual))
        if self._state_token(key):
            target = self._state_value(key)
            if isinstance(value, list):
                if op not in ("=", "?="): raise AssertionError(node)
                if type(target) is StateRef and self._state_object(target) is None: return False
                if self.pop_scope is not None or self.building_scope is not None or self.scope_ig is not None:
                    raise AssertionError(("scope_block_inside_untyped_object", key))
                with self._state_context(target):
                    return self.conditions(value, target.tag if isinstance(target, _CountryScope) else tag)
            return self._state_compare(target, op, self._state_value(value))
        return super().condition(node, tag)

    def execute(self, nodes, tag):
        self._state_scope_setup()
        if not self._state_scope_stack:
            with self._state_context(_CountryScope(tag)):
                return self.execute(nodes, tag)
        index = 0
        while index < len(nodes):
            key, op, body = nodes[index]; index += 1
            if key == "if":
                end = index
                while end < len(nodes) and nodes[end][0] in ("else_if", "else"): end += 1
                super().execute(nodes[index - 1:end], tag); index = end
            elif key == "every_scope_state":
                if op != "=" or not isinstance(body, list): raise AssertionError((key, op, body))
                limits = [v for k, _, v in body if k == "limit"]
                if len(limits) != 1: raise AssertionError(("state_iterator_requires_one_limit", body))
                current = self._state_country(); states = self.countries[current].get("states")
                if not isinstance(states, list): raise AssertionError(("missing_native_states", current))
                for state in states:
                    with self._state_context(self._state_intern(state)):
                        if self.conditions(limits[0], current):
                            self.execute([n for n in body if n[0] != "limit"], current)
            elif self._state_token(key) and isinstance(body, list):
                if op not in ("=", "?="): raise AssertionError((key, op, body))
                if self.pop_scope is not None or self.building_scope is not None or self.scope_ig is not None:
                    raise AssertionError(("scope_effect_inside_untyped_object", key))
                target = self._state_value(key)
                with self._state_context(target):
                    self.execute(body, target.tag if isinstance(target, _CountryScope) else tag)
            elif key == "save_scope_as":
                if op != "=" or not isinstance(body, str) or not body.isidentifier(): raise AssertionError((key, op, body))
                if self.pop_scope is not None or self.building_scope is not None or self.scope_ig is not None:
                    raise AssertionError(("cannot_save_untyped_object_as_state", body))
                self._state_scope_saved[body] = self._state_scope_stack[-1]
                self.scopes.pop(body, None)
            elif key == "save_scope_value_as":
                if op != "=" or not isinstance(body, list): raise AssertionError((key, op, body))
                fields = {k: v for k, field_op, v in body if field_op == "="}
                if (len(fields) != len(body) or set(fields) != {"name", "value"}
                        or not isinstance(fields["name"], str) or not fields["name"].isidentifier()):
                    raise AssertionError(("malformed_native_saved_value", body))
                actual = self._state_value(fields["value"])
                if type(actual) is StateRef:
                    if self._state_object(actual) is None: raise AssertionError(body)
                    self._state_scope_saved[fields["name"]] = actual
                    self.scopes.pop(fields["name"], None)
                else:
                    if type(actual) is not bool: self._state_number(actual, body)
                    self.scopes[fields["name"]] = actual
                    self._state_scope_saved.pop(fields["name"], None)
            elif key in ("set_variable", "change_variable", "clamp_variable"):
                current = self._state_country()
                if op != "=" or not isinstance(body, list): raise AssertionError((key, op, body))
                fields = {k: v for k, field_op, v in body if field_op == "="}
                if len(fields) != len(body) or not isinstance(fields.get("name"), str): raise AssertionError(body)
                allowed = ({"name", "value", "days", "months"} if key == "set_variable" else
                           {"name", "min", "max"} if key == "clamp_variable" else
                           {"name", "add", "multiply", "divide"})
                if set(fields) - allowed or not fields["name"].isidentifier(): raise AssertionError(body)
                if key == "set_variable":
                    for unit in ("days", "months"):
                        if unit in fields:
                            duration = self._state_number(self._state_value(fields[unit]), body)
                            if duration <= 0 or int(duration) != duration: raise AssertionError(body)
                if key == "set_variable" and "value" in fields:
                    actual = self._state_value(fields["value"])
                    if type(actual) is StateRef:
                        if set(fields) != {"name", "value"} or self._state_object(actual) is None: raise AssertionError(body)
                        self.countries[current][fields["name"]] = actual
                        self.months_until_expiry.setdefault(current, {}).pop(fields["name"], None)
                        self.days_until_expiry.setdefault(current, {}).pop(fields["name"], None)
                        continue
                    if type(actual) not in (int, float, bool): raise AssertionError(("unsupported_variable_object", actual))
                    rewritten = [(k, "=", ("yes" if actual else "no") if type(actual) is bool else str(actual)) if k == "value" else (k, "=", v) for k, v in fields.items()]
                    super().execute([(key, "=", rewritten)], current)
                else:
                    if key != "set_variable":
                        old = self.countries[current].get(fields["name"])
                        self._state_number(old, body)
                        if key == "clamp_variable":
                            if set(fields) != {"name", "min", "max"}: raise AssertionError(body)
                            low, high = (self._state_number(self._state_value(fields[k]), body) for k in ("min", "max"))
                            if low > high: raise AssertionError(body)
                            result = min(high, max(low, old))
                        else:
                            actions = set(fields) - {"name"}
                            if len(actions) != 1: raise AssertionError(body)
                            action = actions.pop(); amount = self._state_number(self._state_value(fields[action]), body)
                            if action == "divide" and amount == 0: raise AssertionError(body)
                            result = old + amount if action == "add" else old * amount if action == "multiply" else old / amount
                        self.countries[current][fields["name"]] = self._state_number(result, body)
                    else:
                        super().execute([(key, op, body)], current)
            else:
                if type(self._state_scope_stack[-1]) is StateRef and key not in ("custom_tooltip",):
                    raise AssertionError(("effect_requires_explicit_country_scope", key))
                super().execute([(key, op, body)], tag)


# The separate rural literal author completed and root opened this import gate.
from shu_rural_runtime import ShuRuralWorld


class ShuRuralStateWorld(StateScopeMixin, ShuRuralWorld):
    """Actual SHU source plus the accepted rural leaves and native state identity."""
    _calendar_value_name = "ywc_nmg_current_calendar_month"

    def __init__(self, tag="shu", *, load_inline=True, start_date=date(1836, 1, 1)):
        if type(start_date) is not date:
            raise AssertionError(("explicit_native_calendar_date_required", start_date))
        super().__init__(tag, load_inline=load_inline)
        self.date = self._epoch = start_date
        self.day = 0
        # This is a global definition despite its historical NMG filename/name.
        # No NMG country, world, facts or business helper is imported/evaluated.
        path = Path(__file__).resolve().parents[1] / "yongchang_world/common/script_values/ywc_v03_nmg_values.txt"
        declarations = parse(path.read_text(encoding="utf-8-sig"))
        found = [(op, body) for key, op, body in declarations if key == self._calendar_value_name]
        if len(found) != 1 or found[0][0] != "=":
            raise AssertionError(("missing_or_duplicate_global_calendar_value", self._calendar_value_name))
        self._calendar_value_body = found[0][1]

    def _calendar_scalar(self, token):
        if type(self.date) is not date:
            raise AssertionError(("invalid_native_calendar_date", self.date))
        if token == "year":
            return self.date.year
        if token == "month":
            return self.date.month - 1  # Same zero-based native month as accepted KOR/NMG.
        if isinstance(token, str) and re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", token):
            return self._number(token, token)
        raise AssertionError(("unsupported_native_calendar_operand", token))

    def _calendar_script_value(self):
        body = self._calendar_value_body
        if not isinstance(body, (list, tuple)) or len(body) != 3:
            raise AssertionError(("unsupported_native_calendar_value_shape", body))
        result = None
        for node, operation in zip(body, ("value", "multiply", "add")):
            if (not isinstance(node, (list, tuple)) or len(node) != 3
                    or node[0] != operation or node[1] != "="):
                raise AssertionError(("unsupported_native_calendar_value_operation", node))
            operand = self._calendar_scalar(node[2])
            result = operand if operation == "value" else result * operand if operation == "multiply" else result + operand
            self._state_number(result, node)
        return result

    def _state_value(self, token):
        if token == self._calendar_value_name:
            return self._calendar_script_value()
        return super()._state_value(token)

    def advance_days(self, days=1):
        if type(days) is not int or days < 0 or type(self.date) is not date or type(self._epoch) is not date:
            raise AssertionError(("unsupported_native_calendar_days", days))
        try:
            target = self.date + timedelta(days=days)
        except (OverflowError, ValueError) as exc:
            raise AssertionError(("native_calendar_out_of_range", days)) from exc
        super().advance_days(days)
        self.date = target
        self.day = (target - self._epoch).days

    def advance_months(self, months=1):
        if type(months) is not int or months < 0 or type(self.date) is not date or type(self._epoch) is not date:
            raise AssertionError(("unsupported_native_calendar_months", months))
        absolute = self.date.year * 12 + self.date.month - 1 + months
        year, zero_month = divmod(absolute, 12)
        try:
            target = date(year, zero_month + 1, min(self.date.day, calendar.monthrange(year, zero_month + 1)[1]))
        except (OverflowError, ValueError) as exc:
            raise AssertionError(("native_calendar_out_of_range", months)) from exc
        # Keep the inherited caller-owned elapsed_months and explicit month-timer
        # counters. Only day expiry/calendar advance uses Gregorian elapsed days.
        for tag, timers in self.months_until_expiry.items():
            for name in list(timers):
                timers[name] -= months
                if timers[name] <= 0:
                    timers.pop(name)
                    self.countries[tag].pop(name, None)
        self.advance_days((target - self.date).days)
