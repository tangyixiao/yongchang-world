"""Narrow native world-fact extensions used by LAN's public mandate scenarios."""
from shu_kor_strict_review_runtime import Strict


class LanPublicWorld(Strict):
    def _validate_public_ig_nodes(self, nodes, *, alternatives=False):
        if not isinstance(nodes, list) or not nodes:
            raise AssertionError(("empty_or_malformed_ig_query", nodes))
        seen = set()
        for node in nodes:
            if not isinstance(node, (tuple, list)) or len(node) != 3:
                raise AssertionError(("malformed_ig_node", node))
            key, op, value = node
            if key in ("AND", "OR", "NOT"):
                if op != "=" or (key == "NOT" and (not isinstance(value, list) or len(value) != 1)):
                    raise AssertionError(("malformed_ig_logic", node))
                self._validate_public_ig_nodes(value, alternatives=key == "OR")
                continue
            if key in seen and not alternatives:
                raise AssertionError(("duplicate_ig_field", node))
            seen.add(key)
            if key == "is_interest_group_type":
                if op != "=" or not isinstance(value, str) or not value.startswith("ig_"):
                    raise AssertionError(("malformed_ig_type", node))
            elif key == "is_in_government":
                if op != "=" or value not in ("yes", "no"):
                    raise AssertionError(("malformed_ig_government", node))
            elif key in ("ig_clout", "ig_approval"):
                if op not in self._comparison_ops or not isinstance(value, str):
                    raise AssertionError(("malformed_ig_numeric", node))
                self._number(value, node)
            else:
                raise AssertionError(("unknown_ig_fact", node))

    def condition(self, node, tag):
        key, op, value = node
        if key == "any_scope_building" and self.state_scope is None:
            if op != "=" or not isinstance(value, list) or not value:
                raise AssertionError(("invalid_country_building_query", node))
            previous = self.building_scope
            try:
                for state in self.countries[tag].get("states", []):
                    owned = state["owner"] == tag if "owner" in state else bool(state.get("owned"))
                    if not owned:
                        continue
                    for building in state.get("buildings", []):
                        self.building_scope = building
                        if self.conditions(value, tag):
                            return True
                return False
            finally:
                self.building_scope = previous
        if key == "any_interest_group":
            if op != "=":
                raise AssertionError(("malformed_any_ig", node))
            self._validate_public_ig_nodes(value)
            previous = self.scope_ig
            try:
                for group in self.countries[tag].get("igs", []):
                    self.scope_ig = group
                    if self.conditions(value, tag):
                        return True
                return False
            finally:
                self.scope_ig = previous
        if key == "is_in_government":
            if self.scope_ig is None or op != "=" or value not in ("yes", "no"):
                raise AssertionError(("invalid_government_scope_or_shape", node))
            actual = self.scope_ig.get("in_government", False)
            if not isinstance(actual, bool):
                raise AssertionError(("nonnative_government_fact", actual))
            return actual == (value == "yes")
        if key == "ig_clout":
            if self.scope_ig is None or op not in self._comparison_ops or not isinstance(value, str):
                raise AssertionError(("invalid_clout_scope_or_shape", node))
            actual = self.scope_ig.get("clout", 0)
            if isinstance(actual, bool) or not isinstance(actual, (int, float)):
                raise AssertionError(("nonnumeric_clout_fact", actual))
            number = self._number(actual, node)
            if not 0 <= number <= 1:
                raise AssertionError(("clout_outside_native_fraction", actual))
            return self.compare(number, op, self._number(value, node))
        if key == "level":
            if not isinstance(self.building_scope, dict) or op not in self._comparison_ops:
                raise AssertionError(("invalid_building_level_scope_or_operator", node))
            return self.compare(self._number(self.building_scope.get("level", 0), node),
                                op, self._number(value, node))
        return super().condition(node, tag)
