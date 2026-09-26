# One-off emitter: build ywc_hegemony_effects.txt (the v0.2 hegemony stage
# machine), ywc_hegemony_journals.txt, the six static modifiers and the
# campaign-key localization rows. Outputs are static content afterwards.
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAT = json.loads((ROOT / "data/content/hegemony_event_catalog.json").read_text(encoding="utf-8"))
PARTICIPANTS = CAT["participants"]

SUMMON_ORDER = [p["short"] for p in PARTICIPANTS]
TIMEOUT_MONTHS = 12

HEGEMON_STAGE_EVENT = {3: "ywc_hegemony.2", 4: "ywc_hegemony.3", 5: "ywc_hegemony.4", 6: "ywc_hegemony.5", 7: "ywc_hegemony.6"}
STAGE_DONE = {3: "s3_done", 4: "s4_done", 5: "s5_done", 6: "s6_done", 7: "s7_done"}


def w(lines, text, depth):
    lines.append("    " * depth + text)


def emit_pulse() -> list[str]:
    lines = ["ywc_hegemony_pulse = {"]
    w(lines, "# Holder pulse for ywc_je_hegemony_order (scope: SHU).", 1)
    w(lines, "# s1 proclamation, s2 quarterly summons loop, s3-s6 court politics,", 1)
    w(lines, f"# s7 settlement; silence past {TIMEOUT_MONTHS} months defaults each stage.", 1)
    w(lines, "if = {", 1)
    w(lines, "    limit = { NOT = { has_variable = ywc_hegemony_outcome } }", 2)
    w(lines, "    if = {", 3)
    w(lines, "        limit = { has_variable = ywc_hegemony_age }", 4)
    w(lines, "        change_variable = { name = ywc_hegemony_age add = 1 }", 5)
    w(lines, "    }", 4)
    # s1
    w(lines, "    else_if = {", 4)
    w(lines, "        limit = {", 5)
    w(lines, "            var:ywc_hegemony_stage = 1", 6)
    w(lines, "            NOT = { has_variable = ywc_hegemony_asked }", 6)
    w(lines, "        }", 6)
    w(lines, "        set_variable = { name = ywc_hegemony_asked value = 1 }", 5)
    w(lines, "        trigger_event = { id = ywc_hegemony.1 }", 5)
    w(lines, "    }", 5)
    w(lines, "    else_if = {", 5)
    w(lines, "        limit = {", 6)
    w(lines, "            var:ywc_hegemony_stage = 1", 7)
    w(lines, f"            OR = {{ has_variable = ywc_hegemony_s1_done var:ywc_hegemony_age >= {TIMEOUT_MONTHS} }}", 7)
    w(lines, "        }", 7)
    w(lines, "        if = {", 6)
    w(lines, "            limit = { NOT = { has_variable = ywc_hegemony_s1_done } }", 7)
    w(lines, "            set_variable = { name = ywc_hegemony_authority value = 50 }", 8)
    w(lines, "            set_variable = { name = ywc_hegemony_compliant value = 0 }", 8)
    w(lines, "            set_variable = { name = ywc_hegemony_defiant value = 0 }", 8)
    w(lines, "            set_variable = { name = ywc_hegemony_hedging value = 0 }", 8)
    w(lines, "        }", 7)
    w(lines, "        set_variable = { name = ywc_hegemony_stage value = 2 }", 6)
    w(lines, "        set_variable = { name = ywc_hegemony_age value = 0 }", 6)
    w(lines, "        remove_variable = ywc_hegemony_asked", 6)
    w(lines, "    }", 6)
    # s2: quarterly summons loop
    for short in SUMMON_ORDER:
        tag = short.upper()
        w(lines, "    else_if = {", 5)
        w(lines, "        limit = {", 6)
        w(lines, "            var:ywc_hegemony_stage = 2", 7)
        w(lines, f"            NOT = {{ has_variable = ywc_trib_asked_{short} }}", 7)
        w(lines, "        }", 7)
        w(lines, f"        set_variable = {{ name = ywc_trib_asked_{short} value = 1 }}", 6)
        w(lines, "        if = {", 6)
        w(lines, f"            limit = {{ exists = c:{tag} }}", 7)
        w(lines, f"            c:{tag} = {{ trigger_event = {{ id = ywc_{short}.200 }} }}", 8)
        w(lines, "        }", 7)
        w(lines, "    }", 6)
    w(lines, "    else_if = {", 5)
    w(lines, "        limit = {", 6)
    w(lines, "            var:ywc_hegemony_stage = 2", 7)
    w(lines, f"            has_variable = ywc_trib_asked_{SUMMON_ORDER[-1]}", 7)
    w(lines, "        }", 7)
    w(lines, "        set_variable = { name = ywc_hegemony_stage value = 3 }", 6)
    w(lines, "        set_variable = { name = ywc_hegemony_age value = 0 }", 6)
    w(lines, "    }", 6)
    # s3-s6: court politics events
    for stage, event_id in HEGEMON_STAGE_EVENT.items():
        done = STAGE_DONE[stage]
        w(lines, "    else_if = {", 5)
        w(lines, "        limit = {", 6)
        w(lines, f"            var:ywc_hegemony_stage = {stage}", 7)
        w(lines, "            NOT = { has_variable = ywc_hegemony_asked }", 7)
        w(lines, "        }", 7)
        w(lines, "        set_variable = { name = ywc_hegemony_asked value = 1 }", 6)
        w(lines, f"        trigger_event = {{ id = {event_id} }}", 6)
        w(lines, "    }", 6)
        w(lines, "    else_if = {", 5)
        w(lines, "        limit = {", 6)
        w(lines, f"            var:ywc_hegemony_stage = {stage}", 7)
        w(lines, f"            OR = {{ has_variable = ywc_hegemony_{done} var:ywc_hegemony_age >= {TIMEOUT_MONTHS} }}", 7)
        w(lines, "        }", 7)
        w(lines, "        if = {", 6)
        w(lines, f"            limit = {{ NOT = {{ has_variable = ywc_hegemony_{done} }} }}", 7)
        w(lines, f"            set_variable = {{ name = ywc_hegemony_{done} value = 1 }}", 8)
        w(lines, "        }", 7)
        w(lines, f"        set_variable = {{ name = ywc_hegemony_stage value = {stage + 1} }}", 6)
        w(lines, "        set_variable = { name = ywc_hegemony_age value = 0 }", 6)
        w(lines, "        remove_variable = ywc_hegemony_asked", 6)
        w(lines, "    }", 6)
    # s7: settlement
    w(lines, "    else_if = {", 5)
    w(lines, "        limit = {", 6)
    w(lines, "            var:ywc_hegemony_stage = 7", 7)
    w(lines, "            NOT = { has_variable = ywc_hegemony_asked }", 7)
    w(lines, "        }", 7)
    w(lines, "        set_variable = { name = ywc_hegemony_asked value = 1 }", 6)
    w(lines, "        trigger_event = { id = ywc_hegemony.6 }", 6)
    w(lines, "    }", 6)
    w(lines, "    else_if = {", 5)
    w(lines, "        limit = {", 6)
    w(lines, "            var:ywc_hegemony_stage = 7", 7)
    w(lines, f"            OR = {{ has_variable = ywc_hegemony_s7_done var:ywc_hegemony_age >= {TIMEOUT_MONTHS} }}", 7)
    w(lines, "        }", 7)
    w(lines, "        if = {", 6)
    w(lines, "            limit = { NOT = { has_variable = ywc_hegemony_outcome } }", 7)
    w(lines, "            set_variable = { name = ywc_hegemony_outcome value = 2 }", 8)
    w(lines, "        }", 7)
    w(lines, "        remove_variable = ywc_hegemony_asked", 6)
    w(lines, "    }", 6)
    w(lines, "    else_if = {", 5)
    w(lines, "        limit = { NOT = { has_variable = ywc_hegemony_stage } }", 6)
    w(lines, "        set_variable = { name = ywc_hegemony_stage value = 1 }", 6)
    w(lines, "        set_variable = { name = ywc_hegemony_age value = 0 }", 6)
    w(lines, "    }", 6)
    w(lines, "}", 4)
    lines.append("}")
    return lines


EFFECTS_HEAD = '''# Shared effects for the v0.2 hegemony layer (顺我者昌，逆我者亡).
# The holder pulse drives ywc_je_hegemony_order stage by stage; answers live
# on the participant countries as ywc_tribute_answer (1 enrolled, 2 hedging,
# 3 defiant) and the court keeps ywc_hegemony_authority plus the
# compliant/defiant/hedging counters on SHU.

# Bounded legitimacy shift for tribute decisions. Events must not mutate
# ywc_heritage_legitimacy directly: this wrapper keeps the clamp and routes
# through the shared refresh so the high/low legitimacy modifiers stay in step.
ywc_shift_heritage_legitimacy = {
    change_variable = { name = ywc_heritage_legitimacy add = $DELTA$ }
    clamp_variable = { name = ywc_heritage_legitimacy min = 0 max = 100 }
    ywc_refresh_heritage_legitimacy_modifier = yes
}

'''

LOC_CN = {
    "ywc_hegemony_pulse": "推进天命霸权进程",
    "ywc_shift_heritage_legitimacy": "调整传统正统",
    "ywc_je_hegemony_order": "受命于天，既寿永昌——天命霸权",
    "ywc_je_hegemony_order_reason": "大顺既定天下之名，颁朝贡新籍：顺者得互市与庇护，逆者受孤立与问责。",
    "ywc_tributary_trade": "朝贡互市",
    "ywc_defiance_isolation": "逆藩之罚",
    "ywc_celestial_authority": "天威赫赫",
    "ywc_hegemony_established": "天命确立",
    "ywc_hegemony_stalled": "新制受挫",
    "ywc_hegemony_collapsed": "霸权崩解",
}
LOC_EN = {
    "ywc_hegemony_pulse": "Advance the mandate process",
    "ywc_shift_heritage_legitimacy": "Shift heritage legitimacy",
    "ywc_je_hegemony_order": "The Mandate of Heaven: Enduring Prosperity",
    "ywc_je_hegemony_order_reason": "With the mandate settled, Shun's tribute registry is proclaimed: the enrolled trade and find shelter; the defiant face isolation and censure.",
    "ywc_tributary_trade": "Tributary Trade",
    "ywc_defiance_isolation": "Defiance Censure",
    "ywc_celestial_authority": "Celestial Authority",
    "ywc_hegemony_established": "Mandate Established",
    "ywc_hegemony_stalled": "Order Stalled",
    "ywc_hegemony_collapsed": "Hegemony Collapsed",
}

STATIC_MODIFIERS = '''
ywc_tributary_trade = {
    country_authority_mult = 0.02
    country_legitimacy_base_add = 2
}

ywc_defiance_isolation = {
    country_authority_mult = -0.03
    country_legitimacy_base_add = -6
}

ywc_celestial_authority = {
    country_authority_mult = 0.05
    country_legitimacy_base_add = 3
}

ywc_hegemony_established = {
    country_authority_mult = 0.08
    country_bureaucracy_mult = 0.03
    country_legitimacy_base_add = 8
}

ywc_hegemony_stalled = {
    country_legitimacy_base_add = -3
}

ywc_hegemony_collapsed = {
    country_authority_mult = -0.05
    country_legitimacy_base_add = -8
}
'''


def write_effects() -> None:
    text = EFFECTS_HEAD + "\n".join(emit_pulse()) + "\n"
    path = ROOT / "yongchang_world/common/scripted_effects/ywc_hegemony_effects.txt"
    path.write_text(text, encoding="utf-8-sig", newline="\n")
    print(f"wrote {path.name}")


def write_journal() -> None:
    text = (
        "# v0.2 hegemony journal: the tribute registry proclaimed by the mandate\n"
        "# holder once the campaign's chapter three (or the suzerainty crisis)\n"
        "# settles in its favour. Added from the generated settlement options.\n\n"
        "ywc_je_hegemony_order = {\n"
        "    icon = \"gfx/interface/icons/event_icons/event_portrait.dds\"\n"
        "    group = je_group_foreign_affairs\n"
        "    on_monthly_pulse = {\n"
        "        effect = {\n"
        "            ywc_hegemony_pulse = yes\n"
        "        }\n"
        "    }\n"
        "    complete = { has_variable = ywc_hegemony_outcome }\n"
        "}\n"
    )
    path = ROOT / "yongchang_world/common/journal_entries/ywc_hegemony_journals.txt"
    path.write_text(text, encoding="utf-8-sig", newline="\n")
    print(f"wrote {path.name}")


def append_static_modifiers() -> None:
    path = ROOT / "yongchang_world/common/static_modifiers/ywc_static_modifiers.txt"
    text = path.read_text(encoding="utf-8-sig")
    assert "ywc_tributary_trade" not in text
    text = text.rstrip("\n") + "\n" + STATIC_MODIFIERS
    path.write_text(text, encoding="utf-8-sig", newline="\n")
    print("appended hegemony static modifiers")


def write_loc() -> None:
    for language, table in (("simp_chinese", LOC_CN), ("english", LOC_EN)):
        root_key = "l_simp_chinese:" if language == "simp_chinese" else "l_english:"
        rows = [root_key]
        for key, value in table.items():
            rows.append(f' {key}:0 "{value}"')
        path = ROOT / f"yongchang_world/localization/{language}/ywc_hegemony_keys_l_{language}.yml"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8-sig", newline="\n")
        print(f"wrote {path.name}")


STEPS = {
    "effects": write_effects,
    "journal": write_journal,
    "modifiers": append_static_modifiers,
    "loc": write_loc,
}


def main() -> int:
    import sys

    for step in sys.argv[1:] or list(STEPS):
        STEPS[step]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
