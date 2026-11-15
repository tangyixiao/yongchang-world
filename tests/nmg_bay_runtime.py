"""Load the real independent NMG bay country pulse in the strict world.

The world models facts and Clausewitz execution only.  It never provides a
substitute bay predicate, transfer, state machine or paid/ready flag.
"""
from pathlib import Path

from clausewitz_harness import parse
from nmg_school_runtime import NmgSchoolWorld


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "yongchang_world/common/on_actions/ywc_v03_nmg_bay_accounts.txt"
MODIFIERS = ROOT / "yongchang_world/common/static_modifiers/ywc_v03_nmg_bay_modifiers.txt"
CHILD = "ywc_v03_nmg_bay_accounts_monthly"


class NmgBayWorld(NmgSchoolWorld):
    def __init__(self, countries, **kwargs):
        super().__init__(countries, **kwargs)
        if HOOK.exists():
            self.merge_on_actions(parse(HOOK.read_text(encoding="utf-8-sig")))
        if MODIFIERS.exists():
            for name, _, body in parse(MODIFIERS.read_text(encoding="utf-8-sig")):
                if name in self.modifier_defs:
                    raise AssertionError(("duplicate_bay_modifier", name))
                self.modifier_defs[name] = body

    def assert_bay_hook_loaded_once(self):
        if not HOOK.exists():
            raise AssertionError("independent bay monthly on_action source is missing")
        children = [child for key, _, body in self.on_actions.get("on_monthly_pulse_country", [])
                    if key == "on_actions" for child, op, val in body
                    if child == CHILD and op == "=" and val == "yes"]
        if children != [CHILD] or CHILD not in self.on_actions:
            raise AssertionError(("bay monthly hook must be installed exactly once", children))
