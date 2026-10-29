"""Read-only native political-movement facts for KOR public-court tests."""
from kor_revenue_runtime import KorRevenueWorld
from kor_partner_protocol_runtime import CountryRef


class KorPublicWorld(KorRevenueWorld):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.movement_scope = None

    def _validate_movement_query(self, nodes):
        if not isinstance(nodes, list) or not nodes:
            raise AssertionError(("malformed_movement_query", nodes))
        for node in nodes:
            if not isinstance(node, (tuple, list)) or len(node) != 3:
                raise AssertionError(("malformed_movement_node", node))
            key, op, value = node
            if key in ("AND", "OR", "NOT", "NOR"):
                if op != "=" or (key == "NOT" and (not isinstance(value, list) or len(value) != 1)):
                    raise AssertionError(("malformed_movement_logic", node))
                self._validate_movement_query(value)
            elif key == "is_being_suppressed":
                if op != "=" or not isinstance(value, str) or value not in ("yes", "no"):
                    raise AssertionError(("malformed_movement_boolean", node))
            elif key == "political_movement_radicalism":
                if not isinstance(op, str) or op not in self._comparison_ops or not isinstance(value, str):
                    raise AssertionError(("malformed_movement_comparison", node))
                self._number(value, node)
            else:
                raise AssertionError(("unsupported_movement_query_field", node))

    def condition(self, node, tag):
        if not isinstance(node, (tuple, list)) or len(node) != 3 or not isinstance(node[0], str):
            raise AssertionError(("malformed_public_predicate", node))
        key, op, value = node
        if self.movement_scope is not None:
            self._validate_movement_query([node])
        if key == "any_political_movement":
            if op != "=":
                raise AssertionError(("malformed_movement_iterator", node))
            self._validate_movement_query(value)
            if self._current is None:
                with self._chain(self.country_ref(tag)):
                    return self.condition(node, tag)
            if (not isinstance(self._current, CountryRef) or not self._stack
                    or self._stack[-1] != self._current
                    or any(scope is not None for scope in
                           (self.state_scope, self.building_scope, self.pop_scope, self.scope_ig, self.market_scope))):
                raise AssertionError(("movement_iterator_requires_country", node))
            country = self.countries[self._current.tag]
            if "movements" not in country or not isinstance(country["movements"], list):
                raise AssertionError(("missing_or_malformed_movement_collection", self._current.tag))
            rows = country["movements"]
            if any(not isinstance(row, dict) for row in rows):
                raise AssertionError(("malformed_movement_fact", rows))
            previous = self.movement_scope
            try:
                for row in rows:
                    self.movement_scope = row
                    if self.conditions(value, self._current.tag):
                        return True
                return False
            finally:
                self.movement_scope = previous
        if key in ("is_being_suppressed", "political_movement_radicalism"):
            self._validate_movement_query([node])
            if not isinstance(self.movement_scope, dict) or key not in self.movement_scope:
                raise AssertionError(("missing_movement_scope_or_fact", node))
            actual = self.movement_scope[key]
            if key == "is_being_suppressed":
                if type(actual) is not bool:
                    raise AssertionError(("invalid_movement_suppression_fact", actual))
                return actual == (value == "yes")
            if isinstance(actual, bool) or not isinstance(actual, (int, float)):
                raise AssertionError(("invalid_movement_radicalism_fact", actual))
            number = self._number(actual, node)
            if not 0 <= number <= 1:
                raise AssertionError(("movement_radicalism_outside_native_fraction", actual))
            return self.compare(number, op, self._number(value, node))
        if key in ("is_interest_group_type", "is_in_government", "ig_clout", "ig_approval"):
            self._validate_public_ig_nodes([node])
            field = {"is_interest_group_type": "type", "is_in_government": "in_government",
                     "ig_clout": "clout", "ig_approval": "approval"}[key]
            if not isinstance(self.scope_ig, dict) or field not in self.scope_ig:
                raise AssertionError(("missing_queried_public_ig_fact", field))
            actual = self.scope_ig[field]
            if key == "is_interest_group_type":
                if not isinstance(actual, str) or not actual.startswith("ig_"):
                    raise AssertionError(("malformed_public_ig_type_fact", actual))
                return actual == value
            if key == "is_in_government":
                if type(actual) is not bool:
                    raise AssertionError(("malformed_public_ig_government_fact", actual))
                return actual == (value == "yes")
            if isinstance(actual, bool) or not isinstance(actual, (int, float)):
                raise AssertionError(("malformed_public_ig_numeric_fact", field, actual))
            number = self._number(actual, node)
            if key == "ig_clout" and not 0 <= number <= 1:
                raise AssertionError(("public_ig_clout_outside_native_fraction", actual))
            return self.compare(number, op, self._number(value, node))
        return super().condition(node, tag)
