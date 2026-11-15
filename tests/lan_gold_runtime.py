"""Typed-state runtime used by LAN's beyond-gold scenarios.

Reuses the proven PartnerWorld StateRef semantics (the same interpreter the KOR
provincial-revenue arc uses for captured pilot states and state-scoped
modifiers) and loads LAN's own static modifier definitions. It never drives a
stage machine; it executes the shipped authored source.
"""
from pathlib import Path
from contextlib import contextmanager

from clausewitz_harness import parse
from kor_partner_protocol_runtime import PartnerWorld

ROOT = Path(__file__).resolve().parents[1]


class LanGoldPopup(list):
    """One displayed event and its own saved event-chain scopes."""
    def __init__(self, nodes, saved):
        super().__init__(nodes)
        self.saved = dict(saved)


class LanGoldWorld(PartnerWorld):
    def __init__(self, tag="lan", *, countries, start_date=None):
        kwargs = {} if start_date is None else {"start_date": start_date}
        super().__init__(countries, tag=tag, **kwargs)
        # Load LAN's modifier keys so state/country modifier records are real.
        source = ROOT / "yongchang_world/common/static_modifiers/ywc_v03_lan_modifiers.txt"
        if source.exists():
            self.modifier_defs = {
                key: body for key, _, body in parse(source.read_text(encoding="utf-8-sig"))
            }

    def condition(self, node, tag):
        key, op, value = node
        if key == 'level':
            building = self.building_scope
            if (not isinstance(building, dict) or type(building.get('level')) not in (int, float)
                    or building['level'] < 0 or op not in self._comparison_ops
                    or not isinstance(value, str)):
                raise AssertionError(('invalid_building_level', node, building))
            return self.compare(building['level'], op, self._number(value, node))
        return super().condition(node, tag)

    def deliver(self, arc, want):
        with self._chain(self.country_ref(self.tag)):
            event = super().deliver(arc, want)
            return LanGoldPopup(event, self._saved)

    @contextmanager
    def popup_context(self, event):
        saved = event.saved if isinstance(event, LanGoldPopup) else {}
        with self._chain(self.country_ref(self.tag), saved.items()):
            yield
