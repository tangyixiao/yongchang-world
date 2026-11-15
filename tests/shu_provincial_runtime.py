"""Additional observed state fact for the provincial arc's strict source tests."""
import math
from shu_kor_strict_review_runtime import Strict


class ProvincialWorld(Strict):
    def condition(self, node, tag):
        key, op, value = node
        if key == "turmoil":
            if self.state_scope is None:
                raise AssertionError(("turmoil_outside_state_scope", node))
            if op not in self._comparison_ops or not isinstance(value, str):
                raise AssertionError(("malformed_turmoil_query", node))
            actual = self.state_scope.get("turmoil", 0)
            try:
                actual, threshold = float(actual), float(value)
            except (TypeError, ValueError) as error:
                raise AssertionError(("nonnumeric_turmoil_fact", node, actual)) from error
            if not math.isfinite(actual) or not math.isfinite(threshold):
                raise AssertionError(("nonfinite_turmoil_fact", node, actual))
            return self.compare(actual, op, threshold)
        return super().condition(node, tag)
