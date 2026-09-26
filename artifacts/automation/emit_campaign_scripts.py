"""Emit the campaign scripted effects, journal chaining and crisis journals.

The committed artifacts (ywc_campaign_effects.txt, the ten country journal
files' flavor blocks, ywc_large_campaign_crises.txt, the prelude marker swaps,
ywc_content_starts trim and ywc_campaign_l_*.yml) are authored here so the
highly regular stage machines stay consistent. Run once; outputs are static
content afterwards and validated by tools/ywc_campaign_check.py.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAT = json.loads((ROOT / "data/content/large_campaign_event_catalog.json").read_text(encoding="utf-8"))
COUNTRIES = CAT["countries"]
CRISES = CAT["crises"]

# answerers/fallbacks per (crisis, stage); stage 1 asks the holder itself.
STAGE_ASK = {
    ("1", 1): (None, []), ("1", 2): ("JHG", []), ("1", 3): ("KOR", []),
    ("1", 4): ("SHU", []), ("1", 5): ("JHG", []), ("1", 6): (None, []),
    ("2", 1): (None, []), ("2", 2): ("SHU", []), ("2", 3): ("MGL", []),
    ("2", 4): ("NQG", []), ("2", 5): ("SHU", []), ("2", 6): (None, []),
    ("3", 1): (None, []), ("3", 2): ("SHU", []), ("3", 3): ("MGL", []),
    ("3", 4): ("TIB", []), ("3", 5): ("OIR", []), ("3", 6): (None, []),
    ("4", 1): (None, []), ("4", 2): ("DMG", []), ("4", 3): ("SPA", ["HOL", "LAN"]),
    ("4", 4): ("JHG", []), ("4", 5): ("LAN", []), ("4", 6): (None, []),
    ("5", 1): (None, []), ("5", 2): ("MEX", []), ("5", 3): ("USA", []),
    ("5", 4): ("NMG", []), ("5", 5): ("NMG", []), ("5", 6): (None, []),
}
CRISIS_KEY = {"1": "suzerainty", "2": "blackwater", "3": "inner_asian_routes",
              "4": "south_seas", "5": "pacific_autonomy"}
TIMEOUT_MONTHS = 12

CRISIS_EVENT = lambda crisis, stage: f"ywc_crisis.{(crisis - 1) * 6 + stage}"


def w(lines, text, depth=0):
    lines.append("    " * depth + text)


def answer_check_lines(n: int, stage: int, chain) -> list[str]:
    """Trigger conditions: the stage's answerer (or fallback) has answered."""
    parts = []
    if chain[0] is None:
        parts.append(f"has_variable = ywc_campaign_crisis{n}_s{stage}_answer")
    else:
        for tag in chain:
            parts.append(f"c:{tag} ?= {{ has_variable = ywc_campaign_crisis{n}_s{stage}_answer }}")
    parts.append(f"var:ywc_campaign_crisis{n}_age >= {TIMEOUT_MONTHS}")
    if len(parts) == 2:
        return [f"OR = {{ {parts[0]} {parts[1]} }}"]
    return ["OR = {", *[f"    {part}" for part in parts], "}"]


def record_default(n: int, stage: int, chain, lines, depth):
    if chain[0] is None:
        w(lines, f"if = {{ limit = {{ NOT = {{ has_variable = ywc_campaign_crisis{n}_s{stage}_answer }} }} set_variable = {{ name = ywc_campaign_crisis{n}_s{stage}_answer value = 0 }} }}", depth)
    else:
        nots = " ".join(f"c:{tag} ?= {{ has_variable = ywc_campaign_crisis{n}_s{stage}_answer }}" for tag in chain)
        w(lines, f"if = {{ limit = {{ NOR = {{ {nots} }} }} set_variable = {{ name = ywc_campaign_crisis{n}_s{stage}_answer value = 0 }} }}", depth)


def pulse_effect(crisis_id: str) -> list[str]:
    n = int(crisis_id)
    lines = [f"ywc_crisis_pulse_{CRISIS_KEY[crisis_id]} = {{"]
    w(lines, "# Holder pulse for the crisis journal. Stages fire once; the stage", 1)
    w(lines, f"# advances when the design's answerer replies or after {TIMEOUT_MONTHS} months of", 1)
    w(lines, '# silence, which records "no representative" and moves on.', 1)
    w(lines, "if = {", 1)
    w(lines, f"    limit = {{ NOT = {{ has_variable = ywc_campaign_crisis{n}_outcome }} }}", 2)
    w(lines, "    if = {", 3)
    w(lines, f"        limit = {{ has_variable = ywc_campaign_crisis{n}_age }}", 4)
    w(lines, f"        change_variable = {{ name = ywc_campaign_crisis{n}_age add = 1 }}", 5)
    w(lines, "    }", 4)
    for stage in range(1, 7):
        answerer, fallbacks = STAGE_ASK[(crisis_id, stage)]
        chain = [answerer] + fallbacks
        event_id = CRISIS_EVENT(n, stage)
        last = stage == 6
        # ask branch
        w(lines, f"    else_if = {{", 3)
        w(lines, f"        limit = {{", 4)
        w(lines, f"            var:ywc_campaign_crisis{n}_stage = {stage}", 5)
        w(lines, f"            NOT = {{ has_variable = ywc_campaign_crisis{n}_asked }}", 5)
        w(lines, "        }", 5)
        w(lines, f"        set_variable = {{ name = ywc_campaign_crisis{n}_asked value = 1 }}", 4)
        if chain[0] is None:
            w(lines, f"        trigger_event = {{ id = {event_id} }}", 4)
        else:
            for index, tag in enumerate(chain):
                keyword = "if" if index == 0 else "else_if"
                w(lines, f"        {keyword} = {{", 4)
                w(lines, f"            limit = {{ exists = c:{tag} }}", 5)
                w(lines, f"            c:{tag} = {{ trigger_event = {{ id = {event_id} }} }}", 5)
                w(lines, "        }", 5)
            w(lines, "        else = {", 4)
            w(lines, f"            set_variable = {{ name = ywc_campaign_crisis{n}_s{stage}_answer value = 0 }}", 5)
            w(lines, f"            set_variable = {{ name = ywc_campaign_crisis{n}_stage value = {stage + 1} }}", 5)
            w(lines, f"            set_variable = {{ name = ywc_campaign_crisis{n}_age value = 0 }}", 5)
            w(lines, f"            remove_variable = ywc_campaign_crisis{n}_asked", 5)
            w(lines, "        }", 5)
        w(lines, "    }", 4)
        # check branch
        w(lines, "    else_if = {", 4)
        w(lines, "        limit = {", 5)
        w(lines, f"            var:ywc_campaign_crisis{n}_stage = {stage}", 6)
        for line in answer_check_lines(n, stage, chain):
            w(lines, f"            {line}", 6)
        w(lines, "        }", 6)
        record_default(n, stage, chain, lines, 5)
        if last:
            w(lines, "        if = {", 5)
            w(lines, f"            limit = {{ NOT = {{ has_variable = ywc_campaign_crisis{n}_outcome }} }}", 6)
            w(lines, f"            set_variable = {{ name = ywc_campaign_crisis{n}_outcome value = 2 }}", 6)
            w(lines, "        }", 6)
        else:
            w(lines, f"        set_variable = {{ name = ywc_campaign_crisis{n}_stage value = {stage + 1} }}", 5)
            w(lines, f"        set_variable = {{ name = ywc_campaign_crisis{n}_age value = 0 }}", 5)
            w(lines, f"        remove_variable = ywc_campaign_crisis{n}_asked", 5)
        w(lines, "    }", 5)
    # defensive: a journal without its stage state re-enters at stage one
    w(lines, "    else_if = {", 4)
    w(lines, f"        limit = {{ NOT = {{ has_variable = ywc_campaign_crisis{n}_stage }} }}", 5)
    w(lines, f"        set_variable = {{ name = ywc_campaign_crisis{n}_stage value = 1 }}", 5)
    w(lines, f"        set_variable = {{ name = ywc_campaign_crisis{n}_age value = 0 }}", 5)
    w(lines, "    }", 5)
    w(lines, "}", 3)
    lines.append("}")
    return lines


def national_journal(short: str, config: dict, chapter: int) -> list[str]:
    stem = config["journal_stem"]
    journal = f"ywc_je_flavor_{stem}_{chapter}"
    lines = [f"{journal} = {{"]
    w(lines, 'icon = "gfx/interface/icons/event_icons/event_portrait.dds"', 1)
    w(lines, "group = je_group_internal_affairs", 1)
    w(lines, "on_monthly_pulse = {", 1)
    w(lines, "effect = {", 2)
    w(lines, "ywc_campaign_tick_national_wait = yes", 3)
    w(lines, "if = {", 3)
    w(lines, "    limit = {", 4)
    w(lines, f"        NOT = {{ has_variable = ywc_campaign_{short}_c{chapter}_outcome }}", 5)
    w(lines, "        OR = {", 5)
    w(lines, "            NOT = { has_variable = ywc_campaign_national_wait }", 6)
    w(lines, "            var:ywc_campaign_national_wait <= 0", 6)
    w(lines, "        }", 5)
    w(lines, "    }", 5)
    branches = [f"ywc_campaign_{short}_c{chapter}_prelude", ]
    events = [config["preludes"][str(chapter)]]
    events += [f"ywc_{short}.{99 + (chapter - 1) * 5 + position}" for position in range(1, 6)]
    names = [f"ywc_campaign_{short}_c{chapter}_prelude"] + [
        f"ywc_campaign_{short}_c{chapter}_e{99 + (chapter - 1) * 5 + position}_done"
        for position in range(1, 6)
    ]
    for index, (marker, event_id) in enumerate(zip(names, events)):
        keyword = "if" if index == 0 else "else_if"
        w(lines, f"    {keyword} = {{", 5)
        w(lines, f"        limit = {{ NOT = {{ has_variable = {marker} }} }}", 6)
        w(lines, f"        trigger_event = {{ id = {event_id} }}", 6)
        w(lines, "    }", 6)
    w(lines, "}", 5)
    w(lines, "}", 4)
    w(lines, "}", 3)
    w(lines, "complete = {", 1)
    w(lines, "has_variable = ywc_je_flavor_" + stem + f"_{chapter}_resolved", 2)
    w(lines, "}", 1)
    w(lines, "fail = { has_variable = ywc_je_flavor_" + stem + f"_{chapter}_failed }}", 1)
    lines.append("}")
    return lines


def crisis_journal(crisis_id: str) -> list[str]:
    n = int(crisis_id)
    config = CRISES[crisis_id]
    lines = [f"{config['journal']} = {{"]
    w(lines, 'icon = "gfx/interface/icons/event_icons/event_portrait.dds"', 1)
    w(lines, "group = je_group_foreign_affairs", 1)
    w(lines, "on_monthly_pulse = {", 1)
    w(lines, "effect = {", 2)
    w(lines, "ywc_campaign_tick_dialogue_cooldown = yes", 3)
    w(lines, "if = {", 3)
    w(lines, "    limit = {", 4)
    w(lines, "        OR = {", 5)
    w(lines, "            NOT = { has_variable = ywc_campaign_dialogue_cooldown }", 6)
    w(lines, "            var:ywc_campaign_dialogue_cooldown <= 0", 6)
    w(lines, "        }", 5)
    w(lines, "    }", 5)
    w(lines, f"    ywc_crisis_pulse_{CRISIS_KEY[crisis_id]} = yes", 5)
    w(lines, "}", 5)
    w(lines, "}", 4)
    w(lines, "}", 3)
    w(lines, f"complete = {{ has_variable = ywc_campaign_crisis{n}_outcome }}", 1)
    lines.append("}")
    return lines


EFFECTS_HEAD = '''# Shared effects for the three-chapter national campaign and the five
# cross-country crises added on 2026-09-25. Every modifier applied here is
# time-limited; chapter outcomes are mutually exclusive per chapter
# (1 established, 2 compromise, 3 frustrated) and never reopen a settled
# chapter. Text substitutions use the vanilla scripted-effect parameter form.

ywc_campaign_tick_national_wait = {
    if = {
        limit = { has_variable = ywc_campaign_national_wait }
        change_variable = { name = ywc_campaign_national_wait add = -1 }
        if = {
            limit = { var:ywc_campaign_national_wait <= 0 }
            remove_variable = ywc_campaign_national_wait
        }
    }
}

ywc_campaign_tick_dialogue_cooldown = {
    if = {
        limit = { has_variable = ywc_campaign_dialogue_cooldown }
        change_variable = { name = ywc_campaign_dialogue_cooldown add = -1 }
        if = {
            limit = { var:ywc_campaign_dialogue_cooldown <= 0 }
            remove_variable = ywc_campaign_dialogue_cooldown
        }
    }
}

# Chapter settlement for the bold option of the chapter's last event.
# Outcome 1 needs a positive campaign record plus the real-world gate passed
# in $GATE$; the gate alone still secures a compromise; a negative record with
# no gate means the chapter coalition fell apart.
ywc_campaign_settle_mid = {
    if = {
        limit = {
            var:ywc_campaign_$SHORT$_c$CH$_score >= 2
            $GATE$
        }
        set_variable = { name = ywc_campaign_$SHORT$_c$CH$_outcome value = 1 }
        add_modifier = { name = ywc_campaign_charter_established months = 60 }
    }
    else_if = {
        limit = {
            OR = {
                var:ywc_campaign_$SHORT$_c$CH$_score >= 0
                $GATE$
            }
        }
        set_variable = { name = ywc_campaign_$SHORT$_c$CH$_outcome value = 2 }
        add_modifier = { name = ywc_campaign_local_compromise months = 36 }
    }
    else = {
        set_variable = { name = ywc_campaign_$SHORT$_c$CH$_outcome value = 3 }
        add_modifier = { name = ywc_campaign_reform_backlash months = 24 }
    }
    set_variable = { name = ywc_campaign_national_wait value = 4 }
}

# Chapter three settlement: no successor chapter opens, so the aftermath is a
# longer bounded modifier instead of the mid-campaign charter terms.
ywc_campaign_settle_final = {
    if = {
        limit = {
            var:ywc_campaign_$SHORT$_c$CH$_score >= 2
            $GATE$
        }
        set_variable = { name = ywc_campaign_$SHORT$_c$CH$_outcome value = 1 }
        add_modifier = { name = ywc_campaign_aftermath_established months = 120 }
    }
    else_if = {
        limit = {
            OR = {
                var:ywc_campaign_$SHORT$_c$CH$_score >= 0
                $GATE$
            }
        }
        set_variable = { name = ywc_campaign_$SHORT$_c$CH$_outcome value = 2 }
        add_modifier = { name = ywc_campaign_aftermath_compromise months = 60 }
    }
    else = {
        set_variable = { name = ywc_campaign_$SHORT$_c$CH$_outcome value = 3 }
        add_modifier = { name = ywc_campaign_aftermath_backlash months = 36 }
    }
}

# Records a crisis stage answer on the answering country. 1 agree, 2 refuse,
# 3 rupture confirmation at stage six; the holder records 0 for "no
# representative". The dialogue cooldown keeps one active crisis card per
# quarter at most.
ywc_campaign_crisis_answer = {
    set_variable = { name = ywc_campaign_crisis$CRISIS$_s$STAGE$_answer value = $ANSWER$ }
    set_variable = { name = ywc_campaign_dialogue_cooldown value = 3 }
}
'''

LOC_CN = {
    "ywc_campaign_tick_national_wait": "推进章节间隔",
    "ywc_campaign_tick_dialogue_cooldown": "推进外交磋商间隔",
    "ywc_campaign_settle_mid": "章节中期结算",
    "ywc_campaign_settle_final": "章节终章结算",
    "ywc_campaign_crisis_answer": "记录危机答复",
    "ywc_crisis_pulse_suzerainty": "推进天下名分危机",
    "ywc_crisis_pulse_blackwater": "推进黑水边疆危机",
    "ywc_crisis_pulse_inner_asian_routes": "推进草原与高原商路危机",
    "ywc_crisis_pulse_south_seas": "推进南洋航路危机",
    "ywc_crisis_pulse_pacific_autonomy": "推进太平洋自治危机",
    "ywc_je_crisis_suzerainty": "天下名分与宗藩再议",
    "ywc_je_crisis_suzerainty_reason": "大顺或靖海进入第三章后，各国就外交称谓、关税与使团费用展开再议。",
    "ywc_je_crisis_blackwater": "黑水边疆",
    "ywc_je_crisis_blackwater_reason": "北清的第二、三章期间，黑水边防与边市压力迫使各方就测界与护路表态。",
    "ywc_je_crisis_inner_asian_routes": "草原与高原商路",
    "ywc_je_crisis_inner_asian_routes_reason": "关卡重复征费与驿站短缺让卫拉特、喀尔喀、西藏与大顺必须商定通行规则。",
    "ywc_je_crisis_south_seas": "南洋航路",
    "ywc_je_crisis_south_seas_reason": "护航费、港口准入与荷兰对兰芳的主张把靖海、东明、兰芳和外部海权拉上谈判桌。",
    "ywc_je_crisis_pacific_autonomy": "太平洋自治争议",
    "ywc_je_crisis_pacific_autonomy_reason": "新明与墨西哥就税权、防务与任命范围重议主体关系，第三方只影响筹码。",
    "ywc_campaign_commitment": "章程承诺",
    "ywc_campaign_local_compromise": "地方妥协",
    "ywc_campaign_reform_backlash": "改革反弹",
    "ywc_campaign_charter_established": "章程确立",
    "ywc_campaign_aftermath_established": "新秩序余荫",
    "ywc_campaign_aftermath_compromise": "妥协安排余波",
    "ywc_campaign_aftermath_backlash": "受挫余波",
    "ywc_campaign_crisis_pact": "危机公约",
    "ywc_campaign_crisis_limited": "有限协定",
    "ywc_campaign_crisis_fallout": "谈判破裂余波",
}
LOC_EN = {
    "ywc_campaign_tick_national_wait": "Advance chapter interval",
    "ywc_campaign_tick_dialogue_cooldown": "Advance dialogue cooldown",
    "ywc_campaign_settle_mid": "Settle mid campaign chapter",
    "ywc_campaign_settle_final": "Settle final campaign chapter",
    "ywc_campaign_crisis_answer": "Record crisis answer",
    "ywc_crisis_pulse_suzerainty": "Advance the suzerainty crisis",
    "ywc_crisis_pulse_blackwater": "Advance the Blackwater crisis",
    "ywc_crisis_pulse_inner_asian_routes": "Advance the steppe and highland routes crisis",
    "ywc_crisis_pulse_south_seas": "Advance the South Sea navigation crisis",
    "ywc_crisis_pulse_pacific_autonomy": "Advance the Pacific autonomy crisis",
    "ywc_je_crisis_suzerainty": "Renegotiating the Tributary Order",
    "ywc_je_crisis_suzerainty_reason": "With Shun or Jinghai in their third chapter, the participants renegotiate diplomatic styles, tariffs and envoy budgets.",
    "ywc_je_crisis_blackwater": "The Blackwater Frontier",
    "ywc_je_crisis_blackwater_reason": "During Northern Qing's later chapters, frontier defence and border-market pressure force the neighbours to answer surveys and patrols.",
    "ywc_je_crisis_inner_asian_routes": "Steppe and Highland Trade Routes",
    "ywc_je_crisis_inner_asian_routes_reason": "Duplicate tolls and short stations push Oirat, Khalkha, Tibet and Shun to agree on passage rules.",
    "ywc_je_crisis_south_seas": "South Sea Navigation",
    "ywc_je_crisis_south_seas_reason": "Convoy fees, harbour access and Dutch claims on Lanfang bring Jinghai, Dongming, Lanfang and the sea powers to the table.",
    "ywc_je_crisis_pacific_autonomy": "Pacific Autonomy",
    "ywc_je_crisis_pacific_autonomy_reason": "New Ming and Mexico renegotiate taxes, defence and appointments; third parties only shift the bargaining chips.",
    "ywc_campaign_commitment": "Campaign Commitment",
    "ywc_campaign_local_compromise": "Local Compromise",
    "ywc_campaign_reform_backlash": "Reform Backlash",
    "ywc_campaign_charter_established": "Charter Established",
    "ywc_campaign_aftermath_established": "Established Aftermath",
    "ywc_campaign_aftermath_compromise": "Compromise Aftermath",
    "ywc_campaign_aftermath_backlash": "Frustrated Aftermath",
    "ywc_campaign_crisis_pact": "Crisis Pact",
    "ywc_campaign_crisis_limited": "Limited Accord",
    "ywc_campaign_crisis_fallout": "Rupture Fallout",
}

STATIC_MODIFIERS = '''
ywc_campaign_commitment = {
    country_authority_mult = 0.03
    country_bureaucracy_mult = 0.02
}

ywc_campaign_local_compromise = {
    country_authority_mult = 0.01
    country_legitimacy_base_add = 1
}

ywc_campaign_reform_backlash = {
    country_authority_mult = -0.03
    country_legitimacy_base_add = -5
}

ywc_campaign_charter_established = {
    country_authority_mult = 0.05
    country_bureaucracy_mult = 0.03
    country_legitimacy_base_add = 5
}

ywc_campaign_aftermath_established = {
    country_authority_mult = 0.03
    country_bureaucracy_mult = 0.02
    country_legitimacy_base_add = 4
}

ywc_campaign_aftermath_compromise = {
    country_legitimacy_base_add = 1
}

ywc_campaign_aftermath_backlash = {
    country_authority_mult = -0.02
    country_legitimacy_base_add = -3
}

ywc_campaign_crisis_pact = {
    country_authority_mult = 0.02
    country_legitimacy_base_add = 2
}

ywc_campaign_crisis_limited = {
    country_legitimacy_base_add = 1
}

ywc_campaign_crisis_fallout = {
    country_authority_mult = -0.02
    country_legitimacy_base_add = -4
}
'''


def splice_journals() -> None:
    for short, config in COUNTRIES.items():
        path = ROOT / "yongchang_world/common/journal_entries" / f"ywc_{short}.txt"
        text = path.read_text(encoding="utf-8-sig")
        stem = config["journal_stem"]
        pattern = re.compile(
            rf"(?ms)^ywc_je_flavor_{re.escape(stem)}_1 = \{{.*\Z"
        )
        match = pattern.search(text)
        assert match, path
        blocks: list[str] = []
        for chapter in (1, 2, 3):
            blocks.append("\n".join(national_journal(short, config, chapter)))
        new_text = text[:match.start()] + "\n# Campaign chapters: the legacy event stays as the prelude and the\n# chapter settles with its last new event.\n\n" + "\n\n".join(blocks) + "\n"
        path.write_text(new_text, encoding="utf-8-sig", newline="\n")
        print(f"spliced {path.name}")


def write_effects() -> None:
    lines = [EFFECTS_HEAD]
    for crisis_id in CRISES:
        lines.append("")
        lines.extend(pulse_effect(crisis_id))
    path = ROOT / "yongchang_world/common/scripted_effects/ywc_campaign_effects.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig", newline="\n")
    print(f"wrote {path.name}")


def write_crises_journal() -> None:
    blocks = []
    for crisis_id in CRISES:
        blocks.append("\n".join(crisis_journal(crisis_id)))
    text = (
        "# Crisis journals for the 2026-09-25 cross-country crises. Each journal\n"
        "# is added to its holder when the gating chapter settles; the pulse\n"
        "# advances one stage at a time and every stage answers on its own country.\n\n"
        + "\n\n".join(blocks)
        + "\n"
    )
    path = ROOT / "yongchang_world/common/journal_entries/ywc_large_campaign_crises.txt"
    path.write_text(text, encoding="utf-8-sig", newline="\n")
    print(f"wrote {path.name}")


def swap_prelude_markers() -> None:
    swaps = []
    for short, config in COUNTRIES.items():
        stem = config["journal_stem"]
        for chapter in (1, 2, 3):
            swaps.append((f"ywc_je_flavor_{stem}_{chapter}_resolved", f"ywc_campaign_{short}_c{chapter}_prelude"))
            swaps.append((f"ywc_je_flavor_{stem}_{chapter}_failed", f"ywc_campaign_{short}_c{chapter}_prelude"))
    files = [
        "ywc_shu_jhg_events.txt",
        "ywc_dmg_nqg_events.txt",
        "ywc_steppe_highland_events.txt",
        "ywc_kor_lan_nmg_events.txt",
    ]
    for name in files:
        path = ROOT / "yongchang_world/events" / name
        text = path.read_text(encoding="utf-8-sig")
        total = 0
        for old, new in swaps:
            text, count = re.subn(re.escape(old), new, text)
            total += count
        path.write_text(text, encoding="utf-8-sig", newline="\n")
        print(f"swapped {total} markers in {name}")


def trim_content_starts() -> None:
    path = ROOT / "yongchang_world/common/history/countries/ywc_content_starts.txt"
    text = path.read_text(encoding="utf-8-sig")
    total = 0
    for short, config in COUNTRIES.items():
        stem = config["journal_stem"]
        for chapter in (2, 3):
            line_pattern = re.compile(
                rf"^\s*add_journal_entry = \{{ type = ywc_je_flavor_{re.escape(stem)}_{chapter} }}\n",
                re.M,
            )
            text, count = line_pattern.subn("", text)
            total += count
    path.write_text(text, encoding="utf-8-sig", newline="\n")
    print(f"removed {total} chapter 2/3 journal starts")


def write_campaign_loc() -> None:
    for language, table in (("simp_chinese", LOC_CN), ("english", LOC_EN)):
        root_key = "l_simp_chinese:" if language == "simp_chinese" else "l_english:"
        rows = [root_key]
        for key, value in table.items():
            rows.append(f' {key}:0 "{value}"')
        path = ROOT / f"yongchang_world/localization/{language}/ywc_campaign_l_{language}.yml"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8-sig", newline="\n")
        print(f"wrote {path.name}")


def append_static_modifiers() -> None:
    path = ROOT / "yongchang_world/common/static_modifiers/ywc_static_modifiers.txt"
    text = path.read_text(encoding="utf-8-sig")
    assert "ywc_campaign_commitment" not in text
    text = text.rstrip("\n") + "\n" + STATIC_MODIFIERS
    path.write_text(text, encoding="utf-8-sig", newline="\n")
    print("appended campaign static modifiers")


STEPS = {
    "effects": write_effects,
    "crises": write_crises_journal,
    "journals": splice_journals,
    "markers": swap_prelude_markers,
    "starts": trim_content_starts,
    "modifiers": append_static_modifiers,
    "loc": write_campaign_loc,
}


def main() -> int:
    import sys

    only = sys.argv[1:] or list(STEPS)
    for step in only:
        STEPS[step]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
