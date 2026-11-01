"""Strict SHU rural literal primitives; no business predicate, fee, stage or ready flag.

ShuRuralWorld extends ShuPublicWorld with exactly three native literal features,
each backed only by explicit fail-closed world facts (missing data is an error,
never a zero/calm/cheap default):

- POP standard_of_living: read from the actual POP scope dict key
  "standard_of_living" as a finite number (0 allowed); bool/string/NaN/Inf or a
  missing key are rejected. It is deliberately separate from the STATE leaf
  "average_sol"; outside a real pop scope the query fails closed.
- BUILDING has_active_production_method = pm_x: reads the actual building scope
  dict key "active_production_methods", which must be a list/tuple/set of
  well-formed "pm_*" id strings. An explicit empty collection is a valid fact
  that answers False; a missing or malformed fact, or a malformed query
  (wrong operator, non-"pm_" id, non-building scope) fails closed. The current
  workplace object stays the actual inherited workplace scope.
- COUNTRY market_capital.market -> mg:<good> -> market_goods_pricier: reads the
  country fact dict key "market" as {good: {"pricier": finite number}} from
  self.countries[tag] only (no other tag, no state-level surrogate, native .25
  price scale unchanged). Every listed good block must hold (conjunction, not
  any); missing market/good/price fails closed, and the good scope is restored
  via finally on True, False and exceptions.

Unverified predicates (urbanization scalars, state_goods_pricier/sg: scopes,
other market_goods_* measures, persistent state refs) are NOT implemented and
continue to fall through to the strict parent as unknown triggers.
"""
import math

from shu_public_runtime import ShuPublicWorld


class ShuRuralWorld(ShuPublicWorld):
    @staticmethod
    def _wellformed_pm(value):
        return (isinstance(value, str) and value.startswith("pm_")
                and len(value) > len("pm_") and value.isidentifier())

    def _market_price_fact(self, tag, good, node):
        market = self._fact(self.countries[tag], "market", node)
        self._require(isinstance(market, dict),
                      ("malformed_current_market_facts", node, market))
        self._require(good in market, ("missing_current_market_good", good, node))
        row = market[good]
        self._require(isinstance(row, dict),
                      ("malformed_current_market_good_facts", good, node))
        self._require("pricier" in row, ("missing_current_market_price", good, node))
        actual = row["pricier"]
        self._require(isinstance(actual, (int, float)) and not isinstance(actual, bool),
                      ("nonnumeric_current_market_price", good, actual, node))
        number = self._number(actual, node)
        self._require(math.isfinite(number),
                      ("nonfinite_current_market_price", good, actual, node))
        return number

    def condition(self, node, tag):
        key, op, value = node
        if key == "market_capital.market":
            saved = self.good_scope
            try:
                self._require(op == "=" and isinstance(value, list) and bool(value),
                              ("malformed_current_market_query", node))
                for good, good_op, body in value:
                    self._require(isinstance(good, str) and good.startswith("mg:")
                                  and len(good) > len("mg:"),
                                  ("malformed_current_market_good_scope", node))
                    self._require(good_op == "=" and isinstance(body, list) and bool(body),
                                  ("malformed_current_market_good_query", node))
                    good_name = good[len("mg:"):]
                    self._require(good_name == good_name.lower()
                                  and good_name.isidentifier(),
                                  ("malformed_current_market_good_id", good, node))
                    self.good_scope = good_name
                    if not self.conditions(body, tag):
                        return False
                return True
            finally:
                self.good_scope = saved
        if key == "market_goods_pricier":
            self._require(self.good_scope is not None,
                          ("market_goods_pricier_outside_market_scope", node))
            self._require(op in self._comparison_ops and isinstance(value, str),
                          ("malformed_current_market_price_query", node))
            actual = self._market_price_fact(tag, self.good_scope, node)
            return self.compare(actual, op, self._number(value, node))
        if key.startswith("market_goods_"):
            raise AssertionError(("unsupported_market_goods_measure", node))
        if key == "standard_of_living":
            self._require(isinstance(self.pop_scope, dict),
                          ("standard_of_living_outside_pop_scope", node))
            return self._numeric_leaf(self.pop_scope, "standard_of_living", node)
        if key == "has_active_production_method":
            self._require(isinstance(self.building_scope, dict),
                          ("active_pm_outside_building_scope", node))
            self._require(op == "=" and self._wellformed_pm(value),
                          ("malformed_current_active_pm_query", node))
            methods = self._fact(self.building_scope, "active_production_methods", node)
            self._require(isinstance(methods, (list, tuple, set)),
                          ("malformed_current_active_pm_facts", methods, node))
            self._require(all(self._wellformed_pm(item) for item in methods),
                          ("malformed_current_active_pm_id", methods, node))
            return value in methods
        return super().condition(node, tag)
