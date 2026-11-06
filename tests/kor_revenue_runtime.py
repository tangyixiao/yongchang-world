"""Narrow native facts used by KOR's provincial revenue scenarios."""
from lan_public_runtime import LanPublicWorld
from kor_partner_protocol_runtime import PartnerWorld


class KorRevenueWorld(LanPublicWorld, PartnerWorld):
    def __init__(self, tag="kor", *, load_inline=True, countries=None):
        if tag.lower() != "kor" or load_inline is not True:
            raise AssertionError("KOR revenue uses its actual generated inline source")
        PartnerWorld.__init__(self, countries if countries is not None else {"KOR": {}}, tag=tag)

    def condition(self, node, tag):
        key, op, value = node
        if key == "turmoil":
            # Installed native example: agitators_law_events.txt:146-148.
            if (not isinstance(self.state_scope, dict) or op not in self._comparison_ops
                    or not isinstance(value, str)):
                raise AssertionError(("invalid_state_turmoil_scope_or_shape", node))
            actual = self.state_scope.get("turmoil")
            if isinstance(actual, bool) or not isinstance(actual, (int, float)):
                raise AssertionError(("invalid_state_turmoil_fact", actual))
            number = self._number(actual, node)
            if not 0 <= number <= 1:
                raise AssertionError(("state_turmoil_outside_native_fraction", actual))
            return self.compare(number, op, self._number(value, node))
        return super().condition(node, tag)
