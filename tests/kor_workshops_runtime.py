"""Strict, factual building-profit and worker-living-standard extensions.

No story states, financing, paid markers, modifiers, or readiness are modeled
here; actual country and generated source must produce every such value.
"""
import math
from pathlib import Path

from clausewitz_harness import parse
from kor_revenue_runtime import KorRevenueWorld


class KorWorkshopsWorld(KorRevenueWorld):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base = Path("yongchang_world/common")
        modifiers = base / "static_modifiers/ywc_v03_kor_workshops_modifiers.txt"
        if modifiers.exists():
            for key, _, body in parse(modifiers.read_text(encoding="utf-8-sig")):
                if key in self.modifier_defs:
                    raise AssertionError(("duplicate_workshop_modifier", key))
                self.modifier_defs[key] = body
        hooks = base / "on_actions/ywc_v03_kor_workshops_accounts.txt"
        if hooks.exists():
            self.merge_on_actions(parse(hooks.read_text(encoding="utf-8-sig")))

    def condition(self, node, tag):
        key, op, value = node
        if key == "has_active_production_method":
            if (op != "=" or not isinstance(value, str) or not value.startswith("pm_")
                    or not isinstance(self.building_scope, dict)):
                raise AssertionError(("invalid_active_production_method_query", node))
            methods = self.building_scope.get("active_production_methods")
            if not isinstance(methods, list) or any(not isinstance(method, str) or not method.startswith("pm_") for method in methods):
                raise AssertionError(("missing_or_invalid_active_production_methods", methods))
            return value in methods
        if key == "is_employed":
            if not isinstance(self.pop_scope, dict) or type(self.pop_scope.get("employed")) is not bool:
                raise AssertionError(("invalid_workshop_employment_fact", self.pop_scope))
        if key == "workplace":
            if op != "?=" or not isinstance(self.pop_scope, dict) or not isinstance(self.state_scope, dict):
                raise AssertionError(("workplace_requires_same_state_pop", node))
            workplace = self.pop_scope.get("workplace")
            buildings = self.state_scope.get("buildings")
            if not isinstance(buildings, list):
                raise AssertionError(("missing_state_building_collection", node))
            if not isinstance(workplace, dict) or not any(building is workplace for building in buildings):
                return False
        if key in ("weekly_profit", "cash_reserves_ratio", "standard_of_living"):
            scope = self.pop_scope if key == "standard_of_living" else self.building_scope
            if not isinstance(scope, dict) or key not in scope or op not in self._comparison_ops:
                raise AssertionError(("missing_workshop_literal_fact_or_scope", node))
            actual = scope[key]
            if type(actual) not in (int, float) or not math.isfinite(actual):
                raise AssertionError(("invalid_workshop_literal_number", key, actual))
            if key == "cash_reserves_ratio" and not 0 <= actual <= 1:
                raise AssertionError(("cash_reserve_ratio_outside_range", actual))
            if key == "standard_of_living" and actual < 0:
                raise AssertionError(("negative_standard_of_living", actual))
            return self.compare(actual, op, self._number(value, node))
        return super().condition(node, tag)
