#!/usr/bin/env python3
"""Build the v0.2 hegemony layer (33 events) from the committed catalog.

``data/content/hegemony_event_catalog.json`` is the single implementation
input for the 顺我者昌，逆我者亡 version: six hegemon events plus three
per-participant events for the nine tribute candidates. Re-running only
rewrites the three generated files and stays deterministic:

- ``yongchang_world/events/ywc_hegemony_events.txt``
- ``yongchang_world/localization/english/ywc_hegemony_l_english.yml``
- ``yongchang_world/localization/simp_chinese/ywc_hegemony_l_simp_chinese.yml``
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CATALOG_PATH = Path("data/content/hegemony_event_catalog.json")
EVENTS_PATH = Path("yongchang_world/events/ywc_hegemony_events.txt")
LOC_EN_PATH = Path("yongchang_world/localization/english/ywc_hegemony_l_english.yml")
LOC_CN_PATH = Path("yongchang_world/localization/simp_chinese/ywc_hegemony_l_simp_chinese.yml")

HEGEMONY_JOURNAL = "ywc_je_hegemony_order"
KNOWN_OPS = {
    "stance", "counter", "treasury", "tribute_to_hegemon", "authority",
    "relations_hegemon", "legitimacy", "subject_pressure", "modifier",
    "modifier_on_stance", "relations_on_stance", "fire_stance", "stage_done",
    "authority_init", "outcome",
}


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
    events = catalog.get("events")
    participants = catalog.get("participants")
    hegemon = catalog.get("hegemon")
    if not isinstance(events, list) or not isinstance(participants, list) or not isinstance(hegemon, dict):
        raise ValueError("catalog needs hegemon, participants and events")
    if not str(hegemon.get("tag", "")).strip() or not str(hegemon.get("journal", "")).startswith("ywc_je_"):
        raise ValueError("hegemon must declare a tag and a journal")
    known = {participant["short"] for participant in participants}
    if len(known) != 9:
        raise ValueError(f"expected nine tribute candidates, found {len(known)}")

    ids: set[str] = set()
    for event in events:
        event_id = event.get("id", "")
        if event_id in ids:
            raise ValueError(f"duplicate event id: {event_id}")
        ids.add(event_id)
        for field in ("title_cn", "desc_cn", "title_en", "desc_en"):
            if not str(event.get(field, "")).strip():
                raise ValueError(f"{event_id}: missing bilingual field {field}")
        choices = event.get("choices")
        if not isinstance(choices, list) or not 2 <= len(choices) <= 3:
            raise ValueError(f"{event_id}: needs two or three choices")
        for choice in choices:
            for field in ("label_cn", "label_en"):
                if not str(choice.get(field, "")).strip():
                    raise ValueError(f"{event_id}: missing choice {field}")
            for op in choice.get("ops", []):
                if op.get("op") not in KNOWN_OPS:
                    raise ValueError(f"{event_id}: unknown op {op!r}")
        if event.get("kind") == "hegemon":
            number = int(event_id.rsplit(".", 1)[1])
            if not event_id.startswith("ywc_hegemony.") or not 1 <= number <= 6:
                raise ValueError(f"{event_id}: hegemon events must be ywc_hegemony.1-.6")
            expected = {"proclaim": 2, "reactions": 2, "reward": 2, "punish": 2, "summit": 2, "settle": 3}
            if len(choices) != expected.get(event.get("slot"), 2):
                raise ValueError(f"{event_id}: slot {event.get('slot')} has wrong choice count")
        else:
            short = event.get("short")
            if short not in known:
                raise ValueError(f"{event_id}: unknown participant {short!r}")
            slot = event.get("slot")
            expected_id = f"ywc_{short}.{ {'summon': 200, 'compliant': 201, 'defiant': 202}[slot] }"
            if event_id != expected_id:
                raise ValueError(f"{event_id}: expected {expected_id} for slot {slot}")
            expected_choices = 3 if slot == "summon" else 2
            if len(choices) != expected_choices:
                raise ValueError(f"{event_id}: slot {slot} needs {expected_choices} choices")
    if len(events) != 33:
        raise ValueError(f"catalog must hold 33 events, found {len(events)}")
    by_id = {event["id"]: event for event in events}
    for participant in participants:
        for suffix in (200, 201, 202):
            if f"ywc_{participant['short']}.{suffix}" not in by_id:
                raise ValueError(f"ywc_{participant['short']}.{suffix}: missing")
    for number in range(1, 7):
        if f"ywc_hegemony.{number}" not in by_id:
            raise ValueError(f"ywc_hegemony.{number}: missing")
    return events


def _guarded_hegemony(body: str) -> str:
    return f"if = {{ limit = {{ exists = c:SHU }} c:SHU = {{ {body} }} }}"


def _guarded_relations(value: int) -> str:
    return (
        f"if = {{ limit = {{ exists = c:SHU }} change_relations = {{ country = c:SHU value = {value} }} }}"
    )


def _stance_guard(short: str, stance: int) -> str:
    return f"c:{short.upper()} ?= {{ var:ywc_tribute_answer = {stance} }}"


def render_op(op: dict, catalog: dict) -> str:
    kind = op["op"]
    hegemon_var = catalog["hegemon"]["authority_var"]
    if kind == "stance":
        return f"set_variable = {{ name = ywc_tribute_answer value = {op['value']} }}"
    if kind == "counter":
        sign = "+" if op["delta"] >= 0 else ""
        return _guarded_hegemony(
            f"change_variable = {{ name = ywc_hegemony_{op['name']} add = {sign}{op['delta']} }}"
        )
    if kind == "treasury":
        return f"add_treasury = {op['amount']}"
    if kind == "tribute_to_hegemon":
        return _guarded_hegemony(f"add_treasury = {op['amount']}")
    if kind == "authority":
        return _guarded_hegemony(
            f"change_variable = {{ name = {hegemon_var} add = {op['delta']} }} "
            f"clamp_variable = {{ name = {hegemon_var} min = 0 max = 100 }}"
        )
    if kind == "relations_hegemon":
        return _guarded_relations(op["value"])
    if kind == "legitimacy":
        # Events must not mutate ywc_heritage_legitimacy directly; the shared
        # wrapper keeps the clamp and refreshes the legitimacy modifiers.
        return f"ywc_shift_heritage_legitimacy = {{ DELTA = {op['delta']} }}"
    if kind == "subject_pressure":
        effect = "ywc_raise_autonomy_pressure = yes" if op.get("raise") else "ywc_lower_autonomy_pressure = yes"
        return f"if = {{ limit = {{ is_subject = yes }} {effect} }}"
    if kind == "modifier":
        return f"add_modifier = {{ name = {op['name']} months = {op['months']} }}"
    if kind == "modifier_on_stance":
        blocks = []
        for participant in catalog["participants"]:
            short = participant["short"]
            guard = _stance_guard(short, op["stance"])
            blocks.append(
                f"if = {{ limit = {{ {guard} }} c:{short.upper()} = {{ "
                f"add_modifier = {{ name = {op['name']} months = {op['months']} }} }} }}"
            )
        return "\n        ".join(blocks)
    if kind == "relations_on_stance":
        blocks = []
        for participant in catalog["participants"]:
            short = participant["short"]
            guard = _stance_guard(short, op["stance"])
            blocks.append(
                f"if = {{ limit = {{ {guard} }} change_relations = {{ country = c:{short.upper()} value = {op['value']} }} }}"
            )
        return "\n        ".join(blocks)
    if kind == "fire_stance":
        slot = {1: 201, 3: 202}[op["stance"]]
        blocks = []
        for participant in catalog["participants"]:
            short = participant["short"]
            guard = _stance_guard(short, op["stance"])
            blocks.append(
                f"if = {{ limit = {{ {guard} }} c:{short.upper()} = {{ trigger_event = {{ id = ywc_{short}.{slot} }} }} }}"
            )
        return "\n        ".join(blocks)
    if kind == "stage_done":
        return f"set_variable = {{ name = ywc_hegemony_s{op['stage']}_done value = 1 }}"
    if kind == "authority_init":
        return (
            f"set_variable = {{ name = {hegemon_var} value = {op['value']} }}\n"
            f"        clamp_variable = {{ name = {hegemon_var} min = 0 max = 100 }}\n"
            "        set_variable = { name = ywc_hegemony_compliant value = 0 }\n"
            "        set_variable = { name = ywc_hegemony_defiant value = 0 }\n"
            "        set_variable = { name = ywc_hegemony_hedging value = 0 }"
        )
    if kind == "outcome":
        return f"set_variable = {{ name = ywc_hegemony_outcome value = {op['value']} }}"
    raise ValueError(f"unhandled op {kind}")  # unreachable: validated earlier


def render_event(event: dict, catalog: dict) -> list[str]:
    lines = [
        "",
        f"{event['id']} = {{",
        "    type = country_event",
        f"    title = {event['id']}.t",
        f"    desc = {event['id']}.d",
        "    duration = 1",
    ]
    if event.get("trigger"):
        lines.append(f"    # full-ratification gate; option a repeats it")
    for index, choice in enumerate(event["choices"]):
        base = 50 if index == 0 else (30 if index == 1 else 20)
        lines += [
            "    option = {",
            f"        name = {event['id']}.{chr(ord('a') + index)}",
            *(["        default_option = yes"] if index == 0 else []),
            f"        ai_chance = {{ base = {base} }}",
        ]
        if index == 0 and event.get("trigger"):
            lines.append(f"        trigger = {{ {event['trigger']} }}")
        for op in choice["ops"]:
            for line in render_op(op, catalog).split("\n"):
                lines.append(f"        {line}")
        lines.append("    }")
    lines.append("}")
    return lines


def render_event_script(events: list[dict], catalog: dict) -> str:
    lines = [
        "# Generated by tools/build_hegemony_content.py from data/content/hegemony_event_catalog.json.",
        "# v0.2 顺我者昌，逆我者亡: six hegemon events plus three per-participant events.",
    ]
    current_namespace = None
    for event in events:
        namespace = "ywc_hegemony" if event["kind"] == "hegemon" else f"ywc_{event['short']}"
        if namespace != current_namespace:
            current_namespace = namespace
            lines += ["", f"namespace = {namespace}"]
        lines.extend(render_event(event, catalog))
    return "\n".join(lines) + "\n"


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
            label = choice["label_en"] if english else choice["label_cn"]
            rows.append(f" {event_id}.{chr(ord('a') + index)}:0 {yaml_quote(label)}")
    return "\n".join(rows) + "\n"


def render_all(root: Path) -> dict[Path, str]:
    catalog = load_catalog(root)
    events = validate(catalog)
    return {
        root / EVENTS_PATH: render_event_script(events, catalog),
        root / LOC_EN_PATH: localization_events(events, "english"),
        root / LOC_CN_PATH: localization_events(events, "simp_chinese"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="verify the committed files are current")
    args = parser.parse_args()
    root = args.root.resolve()
    outputs = render_all(root)
    if args.check:
        stale = [str(path) for path, expected in outputs.items()
                 if path.read_text(encoding="utf-8-sig") != expected]
        if stale:
            print("stale generated files; run tools/build_hegemony_content.py:", file=sys.stderr)
            for path in stale:
                print(f"  {path}", file=sys.stderr)
            return 1
        print("generated hegemony content is up to date")
        return 0
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8-sig", newline="\n")
    print(f"generated {len(outputs)} files: hegemony events, english and simp_chinese localization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
