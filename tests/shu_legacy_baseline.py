"""Apply the accepted engine-syntax correction to immutable SHU baselines."""
from copy import deepcopy


def with_engine_modifier_fix(arcs):
    """Return an exact old-arc snapshot with only 1004's two accepted fixes.

    The historic snapshots predate b8588f9's correction from `modifier` to
    `name` in add_modifier. Keep every other field frozen, and require the
    expected old fragment once so an unrelated baseline cannot be normalized.
    """
    updated = deepcopy(arcs)
    fiscal = [arc for arc in updated if arc.get("slug") == "v03_shu_fiscal_register"]
    if len(fiscal) != 1:
        raise AssertionError("expected exactly one historical SHU fiscal arc")
    events = [event for event in fiscal[0]["events"] if event.get("id") == "ywc_shu.1004"]
    if len(events) != 1:
        raise AssertionError("expected exactly one historical SHU 1004 event")
    for key, modifier in (("central_appeal", "ywc_shu_central_appeal_cost"),
                          ("local_mediation", "ywc_shu_local_appeal_cost")):
        options = [option for option in events[0]["options"] if option.get("key") == key]
        if len(options) != 1:
            raise AssertionError(f"expected exactly one historical {key} option")
        old = f"add_modifier = {{ modifier = {modifier} months = 24 }}"
        new = f"add_modifier = {{ name = {modifier} months = 24 }}"
        effect = options[0]["effect"]
        if effect.count(old) != 1 or new in effect:
            raise AssertionError(f"unexpected historical modifier syntax for {key}")
        options[0]["effect"] = effect.replace(old, new, 1)
    return updated
