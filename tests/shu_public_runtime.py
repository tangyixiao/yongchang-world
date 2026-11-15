"""Narrow SHU current facts; all existing story ASTs still execute unchanged.

No public-deliberation business predicate, stage, fee or observation is defined
here. Missing current numeric facts are rejected instead of becoming zero.
Existing Strict variable/effect semantics are inherited without modification.
"""
from lan_public_runtime import LanPublicWorld


class ShuPublicWorld(LanPublicWorld):
    def __init__(self, tag="shu", *, load_inline=True):
        if tag != "shu" or load_inline is not True:
            raise AssertionError("SHU public facts require actual SHU inline source")
        super().__init__(tag, load_inline=True)

    @staticmethod
    def _require(ok, detail):
        if not ok:
            raise AssertionError(detail)

    def _fact(self, scope, name, node):
        self._require(isinstance(scope, dict) and name in scope,
                      ("missing_or_wrong_scope_current_fact", name, node))
        return scope[name]

    def _numeric_fact(self, scope, name, node, *, fraction=False):
        actual = self._fact(scope, name, node)
        self._require(isinstance(actual, (int, float)) and not isinstance(actual, bool),
                      ("nonnumeric_current_fact", name, actual, node))
        number = self._number(actual, node)
        if fraction:
            self._require(0 <= number <= 1, ("current_fraction_outside_range", name, actual))
        return number

    def _numeric_leaf(self, scope, name, node, *, fraction=False):
        _, op, expected = node
        self._require(op in self._comparison_ops and isinstance(expected, str),
                      ("malformed_current_numeric_query", node))
        actual = self._numeric_fact(scope, name, node, fraction=fraction)
        return self.compare(actual, op, self._reference_number(expected, node))

    def _reference_number(self, value, node):
        if value.startswith("var:"):
            return self._numeric_fact(self.countries[self.tag], value[4:], node)
        if value.startswith("ROOT."):
            return self._numeric_fact(self.countries[self.tag], value[5:], node)
        return self._number(value, node)

    def _boolean_leaf(self, scope, name, node):
        _, op, expected = node
        actual = self._fact(scope, name, node)
        self._require(op == "=" and expected in ("yes", "no") and isinstance(actual, bool),
                      ("malformed_current_boolean", node, actual))
        return actual == (expected == "yes")

    def condition(self, node, tag):
        key, op, value = node
        state = self.countries[tag]
        if key in ("has_law", "has_law_or_variant"):
            laws = self._fact(state, "laws", node)
            self._require(op == "=" and isinstance(value, str) and value.startswith("law_type:law_"),
                          ("malformed_current_law_query", node))
            self._require(isinstance(laws, (list, tuple, set))
                          and all(isinstance(law, str) and law.startswith("law_") for law in laws),
                          ("malformed_current_law_facts", laws))
            return value.removeprefix("law_type:") in laws
        if key in ("owner", "is_owned_by"):
            owner = self._fact(self.state_scope, "owner", node)
            self._require(op == "=" and value == "ROOT" and isinstance(owner, str)
                          and owner.isupper(), ("malformed_current_owner", node, owner))
            return owner == tag
        if key == "is_in_government":
            return self._boolean_leaf(self.scope_ig, "in_government", node)
        if key == "ig_clout":
            return self._numeric_leaf(self.scope_ig, "clout", node, fraction=True)
        if key == "ig_approval":
            return self._numeric_leaf(self.scope_ig, "approval", node)
        if key == "turmoil":
            return self._numeric_leaf(self.state_scope, "turmoil", node, fraction=True)
        if key in ("occupancy", "level"):
            return self._numeric_leaf(self.building_scope, key, node, fraction=key == "occupancy")
        if key in ("market_access", "average_sol"):
            return self._numeric_leaf(self.state_scope, key, node, fraction=key == "market_access")
        if key == "is_employed":
            return self._boolean_leaf(self.pop_scope, "employed", node)
        if key == "pop_has_primary_culture":
            return self._boolean_leaf(self.pop_scope, "primary", node)
        if key == "building_has_goods_shortage":
            return self._boolean_leaf(self.building_scope, "shortage", node)
        if key in ("is_at_war", "in_default", "is_subject", "country_has_voting_franchise"):
            return self._boolean_leaf(state, key, node)
        if key in ("bureaucracy", "net_fixed_income", "legitimacy", "authority",
                   "yearly_gross_income", "scaled_debt", "army_size", "navy_size"):
            return self._numeric_leaf(state, key, node)
        if key == "gold_reserves":
            self._numeric_fact(state, key, node)
            # Keep Strict's native structured-price grammar, while refusing
            # an undefined named amount before it can become a free zero bill.
            operands = [value] if isinstance(value, str) else [
                child[2] for child in value
                if isinstance(child, (tuple, list)) and len(child) == 3 and child[0] == "value"
            ] if isinstance(value, list) else []
            for operand in operands:
                if isinstance(operand, str) and operand.startswith(("var:", "ROOT.")):
                    self._reference_number(operand, node)
        if key == "wealth":
            return self._numeric_leaf(self.pop_scope, "wealth", node)
        if key == "literacy_rate":
            scope, name = (self.pop_scope, "literacy") if self.pop_scope is not None else (state, key)
            return self._numeric_leaf(scope, name, node, fraction=True)
        if key == "pop_acceptance":
            actual = self._numeric_fact(self.pop_scope, "acceptance", node)
            self._require(op in self._comparison_ops and value in tuple(
                "acceptance_status_" + str(tier) for tier in range(1, 6)),
                ("malformed_current_acceptance_query", node))
            self._require(1 <= actual <= 5 and actual == int(actual),
                          ("malformed_current_acceptance_tier", actual))
            return self.compare(actual, op, int(value.rsplit("_", 1)[1]))
        if key in ("any_scope_state", "any_scope_pop", "any_scope_building", "workplace"):
            saved = self.state_scope, self.pop_scope, self.building_scope, self.scope_ig
            try:
                self._require(op == ("?=" if key == "workplace" else "=")
                              and isinstance(value, list) and bool(value),
                              ("malformed_current_scope_query", node))
                if key == "any_scope_state":
                    self._require(isinstance(self._fact(state, "states", node), list),
                                  ("malformed_current_states", node))
                elif key == "any_scope_pop":
                    self._require(isinstance(self._fact(self.state_scope, "pops", node), list),
                                  ("malformed_current_pops", node))
                elif key == "any_scope_building" and self.state_scope is None:
                    for province in self._fact(state, "states", node):
                        self._fact(province, "owner", node)
                elif key == "any_scope_building":
                    self._require(isinstance(self._fact(self.state_scope, "buildings", node), list),
                                  ("malformed_current_buildings", node))
                else:
                    self._require(isinstance(self.pop_scope, dict), ("workplace_outside_pop", node))
                    workplace = self.pop_scope.get("workplace")
                    if workplace is None:
                        return False
                    self._require(isinstance(workplace, dict), ("malformed_current_workplace", workplace))
                return super().condition(node, tag)
            finally:
                self.state_scope, self.pop_scope, self.building_scope, self.scope_ig = saved
        if key == "any_interest_group":
            self._require(isinstance(self._fact(state, "igs", node), list),
                          ("malformed_current_interest_groups", node))
        return super().condition(node, tag)
