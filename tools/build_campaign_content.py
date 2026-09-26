#!/usr/bin/env python3
"""Build the 180-event campaign script and localization from the committed catalog.

``data/content/large_campaign_event_catalog.json`` is the single implementation
input derived from the 2026-09-25 event card specs (150 national chapter events
plus 30 cross-country crisis events). Re-running this generator only rewrites
the three generated files and must stay deterministic:

- ``yongchang_world/events/ywc_large_campaign_events.txt``
- ``yongchang_world/localization/english/ywc_large_campaign_l_english.yml``
- ``yongchang_world/localization/simp_chinese/ywc_large_campaign_l_simp_chinese.yml``

Everything the events reference (journal chaining, settlement helpers, crisis
pulses, static modifiers) is authored outside this generator and validated by
``tools/ywc_campaign_check.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

CATALOG_PATH = Path("data/content/large_campaign_event_catalog.json")
EVENTS_PATH = Path("yongchang_world/events/ywc_large_campaign_events.txt")
LOC_EN_PATH = Path("yongchang_world/localization/english/ywc_large_campaign_l_english.yml")
LOC_CN_PATH = Path("yongchang_world/localization/simp_chinese/ywc_large_campaign_l_simp_chinese.yml")

NATIONAL_WAIT_MONTHS = 4
DIALOGUE_COOLDOWN_MONTHS = 3
CHOICE_MODIFIERS = {
    "bold": ("ywc_campaign_commitment", 24),
    "cautious": ("ywc_campaign_local_compromise", 24),
}
CRISIS_CHOICE_MODIFIERS = {
    "bold": ("ywc_campaign_commitment", 18),
    "limited": ("ywc_campaign_crisis_limited", 12),
    "cautious": ("ywc_campaign_reform_backlash", 12),
}
CRISIS_SETTLE_MODIFIERS = {
    1: ("ywc_campaign_crisis_pact", 24, 20),
    2: ("ywc_campaign_crisis_limited", 18, 10),
    3: ("ywc_campaign_crisis_fallout", 18, -15),
}
# v0.2 hook: the hegemony layer (顺我者昌，逆我者亡) starts from a settled
# chapter-three mandate or a fully ratified suzerainty crisis. The block is
# emitted into those exact settlement options so the two content packs stay
# wired without cross-pack runtime lookups.
HEGEMONY_START_OUTCOME_GATES = {
    "shu_ch3": "var:ywc_campaign_shu_c3_outcome = 1",
    "crisis1": "var:ywc_campaign_crisis1_outcome = 1 c:SHU ?= this",
}
HEGEMONY_START_BLOCK = """if = {{
            limit = {{
                {gate}
                var:ywc_heritage_legitimacy >= 60
                exists = c:JHG
                exists = c:KOR
                OR = {{ exists = c:LAN exists = c:NQG }}
                OR = {{ exists = c:DMG exists = c:MGL }}
                NOT = {{ has_variable = ywc_hegemony_started }}
            }}
            set_variable = {{ name = ywc_hegemony_started value = 1 }}
            add_journal_entry = {{ type = ywc_je_hegemony_order }}
            set_variable = {{ name = ywc_hegemony_stage value = 1 }}
            set_variable = {{ name = ywc_hegemony_age value = 0 }}
        }}"""


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def load_catalog(root: Path) -> dict:
    path = root / CATALOG_PATH
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: catalog failed to load: {error}") from error
    if catalog.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported schema_version")
    return catalog


def validate(catalog: dict) -> list[dict]:
    """Reject structurally invalid catalogs before any file is written."""

    countries = catalog.get("countries")
    crises = catalog.get("crises")
    events = catalog.get("events")
    if not isinstance(countries, dict) or not isinstance(crises, dict):
        raise ValueError("catalog needs a countries and a crises table")
    if not isinstance(events, list):
        raise ValueError("catalog needs an events list")

    ids: set[str] = set()
    national: dict[str, list[dict]] = {}
    crisis_seen: dict[int, set[int]] = {}
    for event in events:
        event_id = event.get("id", "")
        if event_id in ids:
            raise ValueError(f"duplicate event id: {event_id}")
        if not event_id.startswith("ywc_") or "." not in event_id:
            raise ValueError(f"invalid event id: {event_id!r}")
        ids.add(event_id)
        for field in ("title_cn", "desc_cn", "title_en", "desc_en"):
            if not str(event.get(field, "")).strip():
                raise ValueError(f"{event_id}: missing bilingual field {field}")
        choices = event.get("choices")
        if not isinstance(choices, list) or len(choices) < 2:
            raise ValueError(f"{event_id}: needs at least two choices")
        if len(choices) > 3:
            raise ValueError(f"{event_id}: more than three choices")
        for index, choice in enumerate(choices):
            for field in ("label_cn", "label_en"):
                if not str(choice.get(field, "")).strip():
                    raise ValueError(f"{event_id}.{chr(97 + index)}: missing {field}")
        if event.get("kind") == "national":
            short = event.get("short")
            if short not in countries:
                raise ValueError(f"{event_id}: unknown country {short!r}")
            chapter, position = event.get("chapter"), event.get("position")
            if chapter not in (1, 2, 3) or position not in (1, 2, 3, 4, 5):
                raise ValueError(f"{event_id}: bad chapter/position")
            expected_id = f"ywc_{short}.{99 + (chapter - 1) * 5 + position}"
            if event_id != expected_id:
                raise ValueError(f"{event_id}: out of chapter order, expected {expected_id}")
            if len(choices) != 2:
                raise ValueError(f"{event_id}: national events need exactly two choices")
            if event.get("final") and position != 5:
                raise ValueError(f"{event_id}: only the fifth event settles the chapter")
            if event.get("final"):
                gates = countries[short].get("gates", {})
                if not str(gates.get(str(chapter), "")).strip():
                    raise ValueError(f"{event_id}: chapter {chapter} has no establishment gate")
            national.setdefault(short, []).append(event)
        elif event.get("kind") == "crisis":
            crisis, stage = event.get("crisis"), event.get("stage")
            if str(crisis) not in crises:
                raise ValueError(f"{event_id}: unknown crisis {crisis!r}")
            if stage not in (1, 2, 3, 4, 5, 6):
                raise ValueError(f"{event_id}: bad stage")
            expected_id = f"ywc_crisis.{(crisis - 1) * 6 + stage}"
            if event_id != expected_id:
                raise ValueError(f"{event_id}: out of stage order, expected {expected_id}")
            expected_choices = 3 if stage == 6 else 2
            if len(choices) != expected_choices:
                raise ValueError(f"{event_id}: stage {stage} needs {expected_choices} choices")
            answerer = event.get("answerer")
            if not str(answerer).strip():
                raise ValueError(f"{event_id}: missing answerer")
            crisis_seen.setdefault(crisis, set()).add(stage)
        else:
            raise ValueError(f"{event_id}: unknown kind {event.get('kind')!r}")

    if len(events) != 180:
        raise ValueError(f"catalog must hold 180 events, found {len(events)}")
    for short, rows in national.items():
        if len(rows) != 15:
            raise ValueError(f"{short}: expected 15 national events, found {len(rows)}")
    if len(national) != len(countries):
        raise ValueError("every catalog country needs its 15 events")
    for crisis in crises:
        stages = crisis_seen.get(int(crisis), set())
        if stages != set(range(1, 7)):
            raise ValueError(f"crisis {crisis} must cover stages 1-6, found {sorted(stages)}")
    if len(crisis_seen) != len(crises):
        raise ValueError("every catalog crisis needs its 6 events")
    return events


def chapter_journal(short: str, config: dict, chapter: int) -> str:
    return f"ywc_je_flavor_{config['journal_stem']}_{chapter}"


def cost_line(cost: int, english: bool) -> str:
    if not cost:
        return ""
    return f" (Treasury cost: £{cost:,}.)" if english else f"（国库支出 £{cost:,}）"


def national_regular_effect(event: dict, choice: dict, config: dict, direction_index: int) -> list[str]:
    short, chapter = event["short"], event["chapter"]
    sign = 1 if direction_index == 0 else -1
    modifier, months = CHOICE_MODIFIERS["bold" if sign > 0 else "cautious"]
    lines = [
        f"set_variable = {{ name = ywc_campaign_{short}_c{chapter}_e{event['id'].rsplit('.', 1)[1]}_done value = 1 }}",
        f"change_variable = {{ name = ywc_campaign_{short}_c{chapter}_score add = {sign} }}",
        f"change_variable = {{ name = {config['flavor']} add = {5 * sign} }}",
        f"clamp_variable = {{ name = {config['flavor']} min = 0 max = 100 }}",
        f"add_modifier = {{ name = {modifier} months = {months} }}",
    ]
    if choice.get("cost"):
        lines.append(f"add_treasury = -{choice['cost']}")
    lines.append("ywc_add_heritage_legitimacy = yes" if sign > 0 else "ywc_lower_heritage_legitimacy = yes")
    if choice.get("trade"):
        lines.append("ywc_add_maritime_network = yes" if sign > 0 else "ywc_reduce_maritime_network = yes")
    if choice.get("subject"):
        pressure = "ywc_lower_autonomy_pressure = yes" if sign > 0 else "ywc_raise_autonomy_pressure = yes"
        lines.append(f"if = {{ limit = {{ is_subject = yes }} {pressure} }}")
    lines.append(f"set_variable = {{ name = ywc_campaign_national_wait value = {NATIONAL_WAIT_MONTHS} }}")
    return lines


def chapter_marker_lines(event: dict) -> list[str]:
    """Write the legacy journal result markers at chapter settlement time.

    ``chapter_journal`` already ends with the chapter number, so the marker
    names stay identical to the pre-campaign interface (ywc_je_flavor_*_1
    _resolved/_failed) while the write point moves to the chapter's last event.
    """

    short, chapter = event["short"], event["chapter"]
    stem = chapter_journal(short, COUNTRIES[short], chapter)
    resolved = f"{stem}_resolved"
    failed = f"{stem}_failed"
    outcome = f"ywc_campaign_{short}_c{chapter}_outcome"
    return [
        f"if = {{ limit = {{ var:{outcome} <= 2 }} set_variable = {{ name = {resolved} value = 1 }} }}",
        f"else = {{ set_variable = {{ name = {failed} value = 1 }} }}",
    ]


def next_chapter_journal_lines(event: dict) -> list[str]:
    short, chapter = event["short"], event["chapter"]
    if chapter == 3:
        return []
    config = COUNTRIES[short]
    return [f"add_journal_entry = {{ type = {chapter_journal(short, config, chapter + 1)} }}"]


def crisis_start_lines(event: dict) -> list[str]:
    """Start the cross-country crises gated behind this chapter settlement."""

    short, chapter = event["short"], event["chapter"]
    starts = COUNTRIES[short].get("crisis_start", {})
    entry = starts.get(str(chapter))
    if not entry:
        return []
    crisis = entry["crisis"]
    config = CRISES[str(crisis)]
    journal = config["journal"]
    stage_vars = (
        f"set_variable = {{ name = ywc_campaign_crisis{crisis}_started value = 1 }}\n"
        f"            add_journal_entry = {{ type = {journal} }}\n"
        f"            set_variable = {{ name = ywc_campaign_crisis{crisis}_stage value = 1 }}\n"
        f"            set_variable = {{ name = ywc_campaign_crisis{crisis}_age value = 0 }}"
    )
    holder = config["holder"]
    lines = []
    if entry.get("cross_holder") and holder != COUNTRIES[short]["tag"]:
        target = entry["cross_holder"]
        lines.append(
            "if = {\n"
            f"            limit = {{ exists = c:{target} }}\n"
            f"            c:{target} = {{\n"
            "                if = {\n"
            f"                    limit = {{ NOT = {{ has_variable = ywc_campaign_crisis{crisis}_started }} }}\n"
            f"                    {stage_vars}\n"
            "                }\n"
            "            }\n"
            "        }"
        )
        lines.append(
            "if = {\n"
            f"            limit = {{ NOT = {{ exists = c:{target} }} NOT = {{ has_variable = ywc_campaign_crisis{crisis}_started }} }}\n"
            f"            {stage_vars}\n"
            "        }"
        )
    else:
        lines.append(
            "if = {\n"
            f"            limit = {{ NOT = {{ has_variable = ywc_campaign_crisis{crisis}_started }} }}\n"
            f"            {stage_vars}\n"
            "        }"
        )
    return lines


def final_option_effects(event: dict, direction_index: int) -> list[str]:
    short, chapter = event["short"], event["chapter"]
    config = COUNTRIES[short]
    lines = [
        # The chapter journal fires the settlement only once, so the pulse
        # marker must be written by every settlement option.
        f"set_variable = {{ name = ywc_campaign_{short}_c{chapter}_e{event['id'].rsplit('.', 1)[1]}_done value = 1 }}"
    ]
    if direction_index == 0:
        gate = config["gates"][str(chapter)]
        settle = "ywc_campaign_settle_final" if chapter == 3 else "ywc_campaign_settle_mid"
        lines.append(
            f"{settle} = {{ SHORT = {short} CH = {chapter} "
            f'GATE = "{gate}" FLAVOR = {config["flavor"]} }}'
        )
        lines.extend(chapter_marker_lines(event))
    else:
        if chapter == 3:
            lines.append(
                f"set_variable = {{ name = ywc_campaign_{short}_c{chapter}_outcome value = 2 }}"
            )
            lines.append(
                "add_modifier = { name = ywc_campaign_aftermath_compromise months = 60 }"
            )
            stem = chapter_journal(short, config, chapter)
            lines.append(f"set_variable = {{ name = {stem}_resolved value = 1 }}")
        else:
            lines.append(
                f"set_variable = {{ name = ywc_campaign_{short}_c{chapter}_outcome value = 2 }}"
            )
            lines.append("add_modifier = { name = ywc_campaign_local_compromise months = 24 }")
            stem = chapter_journal(short, config, chapter)
            lines.append(f"set_variable = {{ name = {stem}_resolved value = 1 }}")
    lines.extend(next_chapter_journal_lines(event))
    lines.extend(crisis_start_lines(event))
    if short == "shu" and chapter == 3:
        lines.append(
            HEGEMONY_START_BLOCK.format(gate=HEGEMONY_START_OUTCOME_GATES["shu_ch3"])
        )
    return lines


COUNTRIES: dict = {}
CRISES: dict = {}


def render_event_script(events: list[dict]) -> str:
    lines = [
        "# Generated by tools/build_campaign_content.py from data/content/large_campaign_event_catalog.json.",
        "# 150 national chapter events (ywc_<tag>.100-.114) plus 30 cross-country crisis events (ywc_crisis.1-.30).",
        "# The legacy flavor events (ywc_<tag>.6-.9) stay in their own files as chapter preludes.",
    ]
    current_namespace = None
    for event in events:
        namespace = f"ywc_{event['short']}" if event["kind"] == "national" else "ywc_crisis"
        if namespace != current_namespace:
            current_namespace = namespace
            lines += ["", f"namespace = {namespace}"]
        lines += [
            "",
            f"{event['id']} = {{",
            "    type = country_event",
            f"    title = {event['id']}.t",
            f"    desc = {event['id']}.d",
            "    duration = 1",
        ]
        for index, choice in enumerate(event["choices"]):
            letter = chr(ord("a") + index)
            base = 50 if index == 0 else (30 if index == 1 else 20)
            if event["kind"] == "crisis" and event["stage"] == 6:
                # The settlement option renders its own complete block.
                lines.extend(render_settlement_option(event, index))
                continue
            lines += [
                "    option = {",
                f"        name = {event['id']}.{letter}",
                *(["        default_option = yes"] if index == 0 else []),
                f"        ai_chance = {{ base = {base} }}",
            ]
            if event["kind"] == "national" and not event.get("final"):
                for effect in national_regular_effect(event, choice, COUNTRIES[event["short"]], index):
                    lines.append(f"        {effect}")
            elif event["kind"] == "national":
                for effect in final_option_effects(event, index):
                    lines.append("        " + effect.replace("\n", "\n        "))
            else:
                lines.append(
                    f"        ywc_campaign_crisis_answer = {{ CRISIS = {event['crisis']} "
                    f"STAGE = {event['stage']} ANSWER = {index + 1} }}"
                )
                modifier, months = CRISIS_CHOICE_MODIFIERS[choice["direction"]]
                lines.append(f"        add_modifier = {{ name = {modifier} months = {months} }}")
                if choice.get("cost"):
                    lines.append(f"        add_treasury = -{choice['cost']}")
                partner = event.get("partner")
                if partner:
                    shift = 15 if index == 0 else (-10 if index == 1 else -15)
                    lines += [
                        f"        if = {{ limit = {{ exists = c:{partner} }} change_relations = {{ country = c:{partner} value = {shift} }} }}"
                    ]
            lines.append("    }")
        lines.append("}")
    return "\n".join(lines) + "\n"


def render_settlement_option(event: dict, index: int) -> list[str]:
    """Stage-6 crisis options confirm the computed outcome for the participants."""

    crisis = event["crisis"]
    config = CRISES[str(crisis)]
    outcome_var = f"ywc_campaign_crisis{crisis}_outcome"
    letter = chr(ord("a") + index)
    outcome = index + 1
    modifier, months, relations = CRISIS_SETTLE_MODIFIERS[outcome]
    base = 50 if index == 0 else (30 if index == 1 else 20)
    lines = [
        "    option = {",
        f"        name = {event['id']}.{letter}",
        f"        ai_chance = {{ base = {base} }}",
    ]
    if outcome == 1:
        lines.append(f"        trigger = {{ {config['settle_full']} }}")
    lines += [
        f"        ywc_campaign_crisis_answer = {{ CRISIS = {crisis} STAGE = 6 ANSWER = {outcome} }}",
        f"        set_variable = {{ name = {outcome_var} value = {outcome} }}",
    ]
    for participant in config["participants"]:
        lines.append(
            f"        if = {{ limit = {{ exists = c:{participant} }} c:{participant} = {{ add_modifier = {{ name = {modifier} months = {months} }} }} }}"
        )
    if event["choices"][index].get("cost"):
        lines.append(f"        add_treasury = -{event['choices'][index]['cost']}")
    if crisis == 1 and outcome == 1:
        lines.append(
            HEGEMONY_START_BLOCK.format(gate=HEGEMONY_START_OUTCOME_GATES["crisis1"])
        )
    lines.append("    }")
    return lines


def localization_events(events: list[dict], language: str) -> str:
    english = language == "english"
    rows = ["l_english:" if english else "l_simp_chinese:"]
    for event in events:
        event_id = event["id"]
        title = event["title_en"] if english else event["title_cn"]
        desc = event["desc_en"] if english else event["desc_cn"]
        rows.append(f" {event_id}.t:0 {yaml_quote(title)}")
        rows.append(f" {event_id}.d:0 {yaml_quote(desc)}")
        for index, choice in enumerate(event["choices"]):
            label = (choice["label_en"] if english else choice["label_cn"]) + cost_line(
                choice.get("cost", 0), english
            )
            rows.append(f" {event_id}.{chr(ord('a') + index)}:0 {yaml_quote(label)}")
    return "\n".join(rows) + "\n"


def render_all(root: Path) -> dict[Path, str]:
    """Render the three generated files without touching the repository."""

    global COUNTRIES, CRISES
    catalog = load_catalog(root)
    COUNTRIES = catalog["countries"]
    CRISES = catalog["crises"]
    events = validate(catalog)
    return {
        root / EVENTS_PATH: render_event_script(events),
        root / LOC_EN_PATH: localization_events(events, "english"),
        root / LOC_CN_PATH: localization_events(events, "simp_chinese"),
    }


def build(root: Path) -> list[Path]:
    outputs = render_all(root)

    events_file, en_file, cn_file = outputs
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    (events_file).write_text(outputs[events_file], encoding="utf-8-sig", newline="\n")
    (en_file).write_text(outputs[en_file], encoding="utf-8-sig", newline="\n")
    (cn_file).write_text(outputs[cn_file], encoding="utf-8-sig", newline="\n")
    print(
        f"generated {len(outputs[events_file].splitlines())} script lines: "
        "150 national, 30 crisis events with both localizations"
    )
    return list(outputs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="verify the committed files are current")
    args = parser.parse_args()
    root = args.root.resolve()
    outputs = render_all(root)
    if args.check:
        stale = []
        for path, expected in outputs.items():
            actual = path.read_text(encoding="utf-8-sig")
            if actual != expected:
                stale.append(str(path))
        if stale:
            print("stale generated files; run tools/build_campaign_content.py:", file=sys.stderr)
            for path in stale:
                print(f"  {path}", file=sys.stderr)
            return 1
        print("generated campaign content is up to date")
        return 0
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8-sig", newline="\n")
    print(
        f"generated {len(outputs)} files: events script, english and simp_chinese localization"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
