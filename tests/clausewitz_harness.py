"""Small, strict interpreter for the variable/scoping subset used by pulse tests.

This executes the shipped scripts, not a Python copy of their stage machines.
It is deliberately not an engine emulator: unsupported commands fail loudly.
"""
import operator
import re


def parse(text):
    text = re.sub(r"#[^\n]*", "", text.lstrip("\ufeff"))
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|\?=|>=|<=|!=|[={}<>]|[^\s={}<>!?]+', text)
    index = 0

    def block(nested=False):
        nonlocal index
        result = []
        while index < len(tokens) and tokens[index] != "}":
            if index + 1 >= len(tokens) or tokens[index + 1] not in ("=", "?=", ">=", "<=", "!=", ">", "<"):
                result.append((tokens[index], "=", "yes"))
                index += 1
                continue
            key, comparison = tokens[index:index + 2]
            index += 2
            if tokens[index] == "{":
                index += 1
                value = block(True)
            else:
                value = tokens[index].strip('"')
                index += 1
            result.append((key, comparison, value))
        if nested:
            assert tokens[index] == "}"
            index += 1
        return result

    return block()


class PulseWorld:
    def __init__(self, effects, countries):
        self.effects = {key: body for key, _, body in parse(effects)}
        self.countries = countries
        self.events = []
        self.modifiers = []
        self.treasury = {tag: 0 for tag in countries}
        self.journals = []
        self.months_until_expiry = {tag: {} for tag in countries}
        self.days_until_expiry = {tag: {} for tag in countries}
        # Saved event-chain scopes: name -> country tag (str) or numeric value.
        self.scopes = {}

    def resolve_operand(self, operand, tag, variables):
        """Resolve a condition operand; None means an absent country or scope."""
        if operand.startswith("var:"):
            return variables.get(operand[4:], 0)
        if operand.startswith("scope:"):
            return self.scopes.get(operand[6:])
        if operand.startswith("c:"):
            return operand[2:] if operand[2:] in self.countries else None
        if operand == "this":
            return tag
        try:
            return float(operand)
        except ValueError:
            return operand

    def resolve_value_operand(self, operand, tag, variables):
        """Resolve an effect value operand, including scope:X.var:Y reads."""
        if operand.startswith("scope:") and ".var:" in operand:
            scope_name, variable = operand[6:].split(".var:", 1)
            holder = self.scopes.get(scope_name)
            if not (isinstance(holder, str) and holder in self.countries):
                raise AssertionError(f"missing saved country scope for value: {operand}")
            return self.countries[holder].get(variable, 0)
        if operand.startswith("scope:"):
            scope_name = operand[6:]
            if scope_name not in self.scopes:
                raise AssertionError(f"missing saved scope for value: {operand}")
            return self.scopes[scope_name]
        return self.resolve_operand(operand, tag, variables)

    def advance_months(self, months=1):
        """Advance calendar months; Clausewitz day timers age by 30 days here."""
        for _ in range(months):
            for tag, timers in self.months_until_expiry.items():
                expired = []
                for name in list(timers):
                    timers[name] -= 1
                    if timers[name] <= 0:
                        expired.append(name)
                for name in expired:
                    timers.pop(name)
                    self.countries[tag].pop(name, None)
            self.advance_days(30)

    def advance_days(self, days=1):
        """Advance explicit days-based variable expiry used by authored effects."""
        for tag, timers in self.days_until_expiry.items():
            expired = []
            for name in list(timers):
                timers[name] -= days
                if timers[name] <= 0:
                    expired.append(name)
            for name in expired:
                timers.pop(name)
                self.countries[tag].pop(name, None)

    def conditions(self, nodes, tag):
        return all(self.condition(node, tag) for node in nodes)

    def condition(self, node, tag):
        key, comparison, value = node
        variables = self.countries[tag]
        if key in ("AND", "NOT", "OR", "NOR"):
            results = [self.condition(child, tag) for child in value]
            return {"AND": all, "NOT": lambda xs: not all(xs),
                    "OR": any, "NOR": lambda xs: not any(xs)}[key](results)
        if key == "has_variable":
            return value in variables
        if key == "has_modifier":
            return any(modifier_tag == tag and fields.get("modifier") == value
                       for modifier_tag, fields in self.modifiers)
        if key == "ywc_shu_v03_finance_safe":
            return (not variables.get("in_default", False)
                    and not any(modifier_tag == tag and fields.get("modifier") == "declared_bankruptcy"
                                for modifier_tag, fields in self.modifiers)
                    and variables.get("ywc_shu_scaled_debt_rise_months", 0) < 3)
        if key == "ywc_shu_v03_real_execution_ready":
            return bool(variables.get("test_ready", False))
        if key == "ywc_shu_v03_has_pilot_state":
            return bool(variables.get("test_has_pilot", False))
        if key == "has_journal_entry":
            return any(
                entry_tag == tag
                and dict((name, field) for name, _, field in body).get("type") == value
                for entry_tag, body in self.journals
            )
        if key == "exists":
            if value.startswith("var:"):
                return value[4:] in variables
            if value.startswith("scope:"):
                return value[6:] in self.scopes
            return value.removeprefix("c:") in self.countries
        if key == "always":
            return value == "yes"
        if key in ("net_fixed_income", "bureaucracy", "gold_reserves", "yearly_gross_income", "scaled_debt", "army_size", "in_default", "is_at_war"):
            left = variables.get(key, 0)
            if isinstance(value, list):
                fields = {name: field for name, _, field in value}
                raw_value = fields["value"]
                right = variables.get(raw_value[4:], 0) if raw_value.startswith("var:") else float(raw_value)
                right *= float(fields.get("multiply", 1))
                if "divide" in fields:
                    divisor = float(fields["divide"])
                    if divisor == 0:
                        raise AssertionError(f"divide by zero in trigger block: {value}")
                    right /= divisor
            elif value.startswith("var:"):
                right = variables.get(value[4:], 0)
            elif value.startswith("scope:"):
                right = self.scopes.get(value[6:])
                if right is None:
                    return False
            elif value in ("yes", "no"):
                right = value == "yes"
            else:
                right = float(value)
            return {"=": operator.eq, "?=": operator.eq, ">=": operator.ge, "<=": operator.le,
                    ">": operator.gt, "<": operator.lt, "!=": operator.ne}[comparison](left, right)
        if key.startswith("c:"):
            other = key[2:]
            if other not in self.countries:
                return False
            return tag == other if isinstance(value, str) else self.conditions(value, other)
        if key.startswith("var:"):
            name = key[4:]
            if not isinstance(value, str):
                # Object-var block condition, e.g. var:X = { is_country_alive = yes }.
                holder = variables.get(name)
                if not (isinstance(holder, str) and holder in self.countries):
                    return False
                fields = {inner_key: field for inner_key, _, field in value}
                if set(fields) == {"is_country_alive"}:
                    return fields["is_country_alive"] == "yes"
                raise AssertionError(f"unsupported object-var condition: {node}")
            if comparison == "?=" and name not in variables:
                return False
            left = variables.get(name, 0)
            right = self.resolve_operand(value, tag, variables)
            if right is None:
                return False
            return {"=": operator.eq, "?=": operator.eq, ">=": operator.ge, "<=": operator.le,
                    ">": operator.gt, "<": operator.lt, "!=": operator.ne}[comparison](left, right)
        if key.startswith("scope:"):
            name = key[6:]
            if name not in self.scopes:
                return False
            if comparison not in ("=", "?=", "!="):
                raise AssertionError(f"unsupported scope comparison: {node}")
            right = self.resolve_operand(value, tag, variables)
            if right is None:
                return False
            return {"=": operator.eq, "?=": operator.eq, "!=": operator.ne}[comparison](self.scopes[name], right)
        if key == "trigger_if":
            limit = next(body for name, _, body in value if name == "limit")
            body = [node for node in value if node[0] not in ("limit", "trigger_else")]
            if not self.conditions(limit, tag):
                fallback = next((body for name, _, body in value if name == "trigger_else"), [])
                return self.conditions(fallback, tag)
            return not self.conditions(limit, tag) or self.conditions(body, tag)
        if key == "calc_true_if":
            amount = next(node for node in value if node[0] == "amount")
            count = sum(self.condition(child, tag) for child in value if child[0] != "amount")
            return {">=": operator.ge, "=": operator.eq}[amount[1]](count, float(amount[2]))
        raise AssertionError(f"unsupported test trigger: {node}")

    def ai_weight(self, nodes, tag):
        weight = float(next(value for key, _, value in nodes if key == "base"))
        for key, _, body in nodes:
            if key == "modifier":
                triggers = next(value for name, _, value in body if name == "trigger")
                if self.conditions(triggers, tag):
                    for name, _, value in body:
                        if name == "multiply":
                            weight *= float(value)
                        elif name == "add":
                            weight += float(value)
        return weight

    def run(self, name, tag="SHU"):
        self.execute(self.effects[name], tag)

    def execute(self, nodes, tag):
        taken = None
        variables = self.countries[tag]
        for key, _, body in nodes:
            if key in ("if", "else_if", "else"):
                if key == "if":
                    taken = False
                assert taken is not None, "orphan conditional branch"
                limit = next((value for name, _, value in body if name == "limit"), [])
                if not taken and (key == "else" or self.conditions(limit, tag)):
                    self.execute([node for node in body if node[0] != "limit"], tag)
                    taken = True
                continue
            taken = None
            if key in ("set_variable", "change_variable", "clamp_variable"):
                fields = {name: value for name, _, value in body}
                name = fields["name"]
                if key == "set_variable":
                    if "value" not in fields:
                        if "days" not in fields:
                            raise AssertionError(f"unsupported set_variable without value: {fields}")
                        resolved_value = 1
                    else:
                        raw_value = fields["value"]
                        if raw_value.startswith("var:"):
                            resolved_value = variables.get(raw_value[4:], 0)
                        elif raw_value.startswith("scope:"):
                            resolved_value = self.resolve_value_operand(raw_value, tag, variables)
                        elif raw_value.startswith("this."):
                            resolved_value = variables.get(raw_value[5:], 0)
                        elif raw_value in ("yearly_gross_income", "gdp", "scaled_debt"):
                            resolved_value = variables.get(raw_value, 0)
                        else:
                            try:
                                resolved_value = float(raw_value)
                            except ValueError:
                                resolved_value = raw_value == "yes"
                    variables[name] = resolved_value
                    if "months" in fields:
                        self.months_until_expiry.setdefault(tag, {})[name] = int(float(fields["months"]))
                    else:
                        self.months_until_expiry.setdefault(tag, {}).pop(name, None)
                    if "days" in fields:
                        self.days_until_expiry.setdefault(tag, {})[name] = int(float(fields["days"]))
                    else:
                        self.days_until_expiry.setdefault(tag, {}).pop(name, None)
                elif key == "change_variable":
                    if "multiply" in fields:
                        variables[name] = variables.get(name, 0) * float(fields["multiply"])
                    elif "divide" in fields:
                        divisor = float(fields["divide"])
                        if divisor == 0:
                            raise AssertionError(f"change_variable divide by zero: {fields}")
                        variables[name] = variables.get(name, 0) / divisor
                    elif "add" in fields:
                        raw_add = fields["add"]
                        if raw_add.startswith("var:"):
                            amount = variables.get(raw_add[4:], 0)
                        elif raw_add.startswith("scope:"):
                            amount = self.resolve_value_operand(raw_add, tag, variables)
                        elif raw_add.startswith("this."):
                            amount = variables.get(raw_add[5:], 0)
                        else:
                            amount = float(raw_add)
                        variables[name] = variables.get(name, 0) + amount
                    else:
                        raise AssertionError(f"unsupported change_variable fields: {fields}")
                else:
                    variables[name] = min(float(fields["max"]), max(float(fields["min"]), variables[name]))
            elif key == "remove_variable":
                variables.pop(body, None)
                self.months_until_expiry.setdefault(tag, {}).pop(body, None)
                self.days_until_expiry.setdefault(tag, {}).pop(body, None)
            elif key == "trigger_event":
                self.events.append((tag, dict((name, value) for name, _, value in body)["id"]))
            elif key == "add_modifier":
                self.modifiers.append((tag, dict((name, value) for name, _, value in body)))
            elif key == "remove_modifier":
                self.modifiers = [(modifier_tag, fields) for modifier_tag, fields in self.modifiers
                                  if modifier_tag != tag or fields.get("modifier") != body]
            elif key == "add_treasury":
                if isinstance(body, list):
                    fields = {name: value for name, _, value in body}
                    raw_value = fields["value"]
                    if raw_value.startswith("var:"):
                        amount = variables.get(raw_value[4:], 0)
                    elif raw_value.startswith("scope:"):
                        amount = self.resolve_value_operand(raw_value, tag, variables)
                    elif raw_value.startswith("this."):
                        amount = variables.get(raw_value[5:], 0)
                    else:
                        amount = float(raw_value)
                    amount *= float(fields.get("multiply", 1))
                else:
                    amount = float(body)
                self.treasury[tag] += amount
            elif key == "add_journal_entry":
                self.journals.append((tag, body))
            elif key == "save_scope_as":
                self.scopes[body] = tag
            elif key == "save_scope_value_as":
                fields = {name: value for name, _, value in body}
                self.scopes[fields["name"]] = self.resolve_value_operand(fields["value"], tag, variables)
            elif key.startswith("var:") and isinstance(body, list):
                holder = variables.get(key[4:])
                if holder is None:
                    continue
                if not (isinstance(holder, str) and holder in self.countries):
                    raise AssertionError(f"object-var effect on non-country variable: {key}")
                self.execute(body, holder)
            elif key.startswith("scope:") and isinstance(body, list):
                holder = self.scopes.get(key[6:])
                if holder is None:
                    continue
                if not (isinstance(holder, str) and holder in self.countries):
                    raise AssertionError(f"scope effect on non-country scope: {key}")
                self.execute(body, holder)
            elif key.startswith("c:"):
                if key[2:] in self.countries:
                    self.execute(body, key[2:])
            elif key in self.effects and body == "yes":
                self.run(key, tag)
            else:
                raise AssertionError(f"unsupported test effect: {key}")
