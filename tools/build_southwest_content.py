#!/usr/bin/env python3
"""Build the v0.2 六六大顺 southwest layer (18 events) from the catalog.

``data/content/southwest_event_catalog.json`` is the single implementation
input: six regional countries (Lijiang, Sipsongpanna, Derge, Gyalrong, Shan,
Arakan) each carrying one core journal with three events. Re-running rewrites
the four generated files deterministically:

- ``yongchang_world/events/ywc_southwest_events.txt``
- ``yongchang_world/common/journal_entries/ywc_southwest_journal.txt``
- ``yongchang_world/localization/english/ywc_southwest_l_english.yml``
- ``yongchang_world/localization/simp_chinese/ywc_southwest_l_simp_chinese.yml``
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CATALOG_PATH = Path("data/content/southwest_event_catalog.json")
EVENTS_PATH = Path("yongchang_world/events/ywc_southwest_events.txt")
JOURNAL_PATH = Path("yongchang_world/common/journal_entries/ywc_southwest_journal.txt")
LOC_EN_PATH = Path("yongchang_world/localization/english/ywc_southwest_l_english.yml")
LOC_CN_PATH = Path("yongchang_world/localization/simp_chinese/ywc_southwest_l_simp_chinese.yml")

KNOWN_OPS = {"marker", "treasury", "relations", "modifier"}


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
    lines = catalog.get("lines")
    if not isinstance(lines, list) or len(lines) != 6:
        raise ValueError("catalog must hold six country lines")
    ids: set[str] = set()
    for line in lines:
        short, tag = line.get("short"), line.get("tag")
        if not str(short).strip() or not re.fullmatch(r"[A-Z]{3}", str(tag)):
            raise ValueError(f"line needs a short and a three-letter tag: {line!r}")
        journal = line.get("journal", "")
        if journal != f"ywc_je_sw_{short}":
            raise ValueError(f"{tag}: journal must be ywc_je_sw_{short}")
        events = line.get("events")
        if not isinstance(events, list) or len(events) != 3:
            raise ValueError(f"{tag}: line needs exactly three events")
        for event in events:
            event_id = event.get("id", "")
            if event_id in ids:
                raise ValueError(f"duplicate event id: {event_id}")
            ids.add(event_id)
            if event_id != f"ywc_{short.lower()}.{event.get('slot')}":
                raise ValueError(f"{event_id}: id must be ywc_{short.lower()}.<slot>")
            if event.get("slot") not in (1, 2, 3):
                raise ValueError(f"{event_id}: slot must be 1-3")
            for field in ("title_cn", "desc_cn", "title_en", "desc_en"):
                if not str(event.get(field, "")).strip():
                    raise ValueError(f"{event_id}: missing bilingual field {field}")
            choices = event.get("choices")
            if not isinstance(choices, list) or len(choices) != 2:
                raise ValueError(f"{event_id}: regional events take exactly two choices")
            for choice in choices:
                for field in ("label_cn", "label_en"):
                    if not str(choice.get(field, "")).strip():
                        raise ValueError(f"{event_id}: missing choice {field}")
                for op in choice.get("ops", []):
                    if op.get("op") not in KNOWN_OPS:
                        raise ValueError(f"{event_id}: unknown op {op!r}")
            if event["slot"] == 3:
                names = {op.get("name") for choice in choices for op in choice.get("ops", [])
                         if op["op"] == "marker"}
                if {f"ywc_sw_{short}_resolved", f"ywc_sw_{short}_failed"} - names:
                    raise ValueError(f"{event_id}: the last event must settle the line")
    return [event for line in lines for event in line["events"]]


def render_op(op: dict) -> str:
    kind = op["op"]
    if kind == "marker":
        return f"set_variable = {{ name = {op['name']} value = 1 }}"
    if kind == "treasury":
        return f"add_treasury = {op['amount']}"
    if kind == "relations":
        return (
            f"if = {{ limit = {{ exists = c:{op['tag']} }} "
            f"change_relations = {{ country = c:{op['tag']} value = {op['value']} }} }}"
        )
    if kind == "modifier":
        return f"add_modifier = {{ name = {op['name']} months = {op['months']} }}"
    raise ValueError(f"unhandled op {kind}")  # unreachable: validated earlier


def render_event(event: dict) -> list[str]:
    lines = [
        "",
        f"{event['id']} = {{",
        "    type = country_event",
        f"    title = {event['id']}.t",
        f"    desc = {event['id']}.d",
        "    duration = 1",
    ]
    for index, choice in enumerate(event["choices"]):
        lines += [
            "    option = {",
            f"        name = {event['id']}.{chr(ord('a') + index)}",
            *(["        default_option = yes"] if index == 0 else []),
            f"        ai_chance = {{ base = {50 if index == 0 else 35} }}",
        ]
        for op in choice["ops"]:
            lines.append(f"        {render_op(op)}")
        lines.append("    }")
    lines.append("}")
    return lines


def render_event_script(catalog: dict) -> str:
    lines = [
        "# Generated by tools/build_southwest_content.py from data/content/southwest_event_catalog.json.",
        "# v0.2 六六大顺: three events for each of the six southwest countries.",
    ]
    for line in catalog["lines"]:
        lines += ["", f"namespace = ywc_{line['short']}"]
        for event in line["events"]:
            lines.extend(render_event(event))
    return "\n".join(lines) + "\n"


def render_journal_file(catalog: dict) -> str:
    blocks = []
    for line in catalog["lines"]:
        short, tag = line["short"], line["tag"]
        blocks.append(
            f"{line['journal']} = {{\n"
            f"    icon = \"gfx/interface/icons/event_icons/event_portrait.dds\"\n"
            f"    group = je_group_internal_affairs\n"
            f"    on_monthly_pulse = {{\n"
            f"        effect = {{\n"
            f"            if = {{\n"
            f"                limit = {{ NOT = {{ has_variable = ywc_sw_{short}_e1_done }} }}\n"
            f"                trigger_event = {{ id = ywc_{short}.1 }}\n"
            f"            }}\n"
            f"            else_if = {{\n"
            f"                limit = {{ NOT = {{ has_variable = ywc_sw_{short}_e2_done }} }}\n"
            f"                trigger_event = {{ id = ywc_{short}.2 }}\n"
            f"            }}\n"
            f"            else_if = {{\n"
            f"                limit = {{ NOT = {{ has_variable = ywc_sw_{short}_e3_done }} }}\n"
            f"                trigger_event = {{ id = ywc_{short}.3 }}\n"
            f"            }}\n"
            f"        }}\n"
            f"    }}\n"
            f"    complete = {{ has_variable = ywc_sw_{short}_resolved }}\n"
            f"    fail = {{ has_variable = ywc_sw_{short}_failed }}\n"
            f"}}"
        )
    return (
        "# Southwest regional journals (v0.2 六六大顺).\n"
        "# The old regional journal ywc_je_highland_without_master was removed:\n"
        "# it duplicated TIB's main journal ywc_je_tibet_highland_without_master\n"
        "# and was visible to every country. TIB is wired through its own file.\n\n"
        + "\n\n".join(blocks)
        + "\n"
    )


def localization_events(catalog: dict, language: str) -> str:
    english = language == "english"
    rows = ["l_english:" if english else "l_simp_chinese:"]
    for line in catalog["lines"]:
        for event in line["events"]:
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
    validate(catalog)
    return {
        root / EVENTS_PATH: render_event_script(catalog),
        root / JOURNAL_PATH: render_journal_file(catalog),
        root / LOC_EN_PATH: localization_events(catalog, "english"),
        root / LOC_CN_PATH: localization_events(catalog, "simp_chinese"),
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
            print("stale generated files; run tools/build_southwest_content.py:", file=sys.stderr)
            for path in stale:
                print(f"  {path}", file=sys.stderr)
            return 1
        print("generated southwest content is up to date")
        return 0
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8-sig", newline="\n")
    print(f"generated {len(outputs)} files: southwest events, journal file and both localizations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
