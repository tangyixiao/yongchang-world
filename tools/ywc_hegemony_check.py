"""Static acceptance checks for the v0.2 hegemony layer (顺我者昌，逆我者亡).

Verifies the whole chain without launching the game:

* the catalog is structurally valid (33 unique ids, nine tribute candidates,
  bilingual copy, option counts) and the three generated files are current;
* every participant receives exactly one summons from the holder pulse and
  every choice of a summons records a stance answer;
* the hegemon line fires in order and its settlement writes one of three
  mutually exclusive outcomes (established / stalled / collapsed);
* the campaign settlement options (chapter three mandate, fully ratified
  suzerainty crisis) start the journal behind real gates;
* both localizations carry every event key and the modifier/journal names.

Static checks cannot prove in-game behaviour; the release playbook keeps the
live acceptance gates separate.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from tools.build_campaign_content import EVENTS_PATH as CAMPAIGN_EVENTS_PATH
    from tools.build_hegemony_content import (
        CATALOG_PATH,
        EVENTS_PATH,
        LOC_CN_PATH,
        LOC_EN_PATH,
        load_catalog,
        render_all,
        validate,
    )
except ModuleNotFoundError:  # Running this file directly puts ``tools`` on sys.path.
    from build_campaign_content import EVENTS_PATH as CAMPAIGN_EVENTS_PATH
    from build_hegemony_content import (
        CATALOG_PATH,
        EVENTS_PATH,
        LOC_CN_PATH,
        LOC_EN_PATH,
        load_catalog,
        render_all,
        validate,
    )

JOURNAL_PATH = Path("yongchang_world/common/journal_entries/ywc_hegemony_journals.txt")
EFFECTS_PATH = Path("yongchang_world/common/scripted_effects/ywc_hegemony_effects.txt")
MODIFIERS_PATH = Path("yongchang_world/common/static_modifiers/ywc_static_modifiers.txt")

EVENT_BLOCK = re.compile(r"(?ms)^(ywc_[a-z]+\.\d+) = \{")
OPTION_NAME = re.compile(r"(?m)^\s*name = (ywc_[a-z]+\.\d+\.[a-z])\s*$")
HEGEMONY_HOOK = re.compile(
    r"add_journal_entry = \{ type = ywc_je_hegemony_order \}"
)
REQUIRED_MODIFIERS = (
    "ywc_tributary_trade",
    "ywc_defiance_isolation",
    "ywc_celestial_authority",
    "ywc_hegemony_established",
    "ywc_hegemony_stalled",
    "ywc_hegemony_collapsed",
)
REQUIRED_LOC_KEYS = (
    "ywc_je_hegemony_order",
    "ywc_hegemony_pulse",
    "ywc_shift_heritage_legitimacy",
    *REQUIRED_MODIFIERS,
)


def _read(root: Path, relative: Path) -> str:
    return (root / relative).read_text(encoding="utf-8-sig")


def event_blocks(text: str) -> dict[str, str]:
    matches = list(EVENT_BLOCK.finditer(text))
    return {
        match.group(1): text[match.start():(matches[index + 1].start() if index + 1 < len(matches) else len(text))]
        for index, match in enumerate(matches)
    }


def check_events(events: list[dict], script: str, problems: list[str]) -> None:
    blocks = event_blocks(script)
    if set(blocks) != {event["id"] for event in events}:
        missing = sorted({event["id"] for event in events} - set(blocks))
        extra = sorted(set(blocks) - {event["id"] for event in events})
        problems.append(f"hegemony event script mismatch: missing={missing} extra={extra}")
        return
    for event in events:
        block = blocks[event["id"]]
        expected = {f"{event['id']}.{chr(ord('a') + index)}" for index in range(len(event["choices"]))}
        found = set(OPTION_NAME.findall(block))
        if found != expected:
            problems.append(f"{event['id']}: option names {sorted(found)} != {sorted(expected)}")
        if f"title = {event['id']}.t" not in block or f"desc = {event['id']}.d" not in block:
            problems.append(f"{event['id']}: title/desc keys missing")
        if event.get("slot") == "summon":
            answers = block.count("set_variable = { name = ywc_tribute_answer value =")
            if answers < len(event["choices"]):
                problems.append(f"{event['id']}: every choice must record ywc_tribute_answer")
        if event["id"] == "ywc_hegemony.6":
            for outcome in (1, 2, 3):
                if f"set_variable = {{ name = ywc_hegemony_outcome value = {outcome} }}" not in block:
                    problems.append(f"ywc_hegemony.6: outcome {outcome} option missing")
            if "trigger = {" not in block:
                problems.append("ywc_hegemony.6: the establishment option must be trigger-gated")


def check_pulse(catalog: dict, effects: str, problems: list[str]) -> None:
    if "ywc_hegemony_pulse = {" not in effects:
        problems.append("ywc_hegemony_pulse: missing from ywc_hegemony_effects.txt")
        return
    for participant in catalog["participants"]:
        short = participant["short"]
        if f"trigger_event = {{ id = ywc_{short}.200 }}" not in effects:
            problems.append(f"ywc_hegemony_pulse: never summons {short} ({participant['name_cn']})")
        if f"ywc_trib_asked_{short}" not in effects:
            problems.append(f"ywc_hegemony_pulse: dispatch state for {short} missing")
    for number in range(1, 7):
        if f"trigger_event = {{ id = ywc_hegemony.{number} }}" not in effects:
            problems.append(f"ywc_hegemony_pulse: stage event ywc_hegemony.{number} never fires")
    if "ywc_hegemony_outcome value = 2" not in effects:
        problems.append("ywc_hegemony_pulse: timeout must default to a stalled order")


def check_hooks(campaign_script: str, problems: list[str]) -> None:
    hooks = HEGEMONY_HOOK.findall(campaign_script)
    if len(hooks) < 3:
        problems.append(f"hegemony start hooks missing: found {len(hooks)}, expected 3 (chapter three + crisis settlement)")
    if "var:ywc_campaign_shu_c3_outcome = 1" not in campaign_script:
        problems.append("the chapter-three hook must require the established outcome")
    if "var:ywc_campaign_crisis1_outcome = 1" not in campaign_script:
        problems.append("the crisis hook must require the full-agreement outcome")
    if "ywc_heritage_legitimacy >= 60" not in campaign_script:
        problems.append("hegemony hooks must require legitimacy >= 60")


def check_journal(journal: str, problems: list[str]) -> None:
    if "ywc_je_hegemony_order = {" not in journal:
        problems.append("ywc_je_hegemony_order: missing from ywc_hegemony_journals.txt")
    if "ywc_hegemony_pulse = yes" not in journal:
        problems.append("ywc_je_hegemony_order: pulse must drive the stage machine")
    if "has_variable = ywc_hegemony_outcome" not in journal:
        problems.append("ywc_je_hegemony_order: complete must read the outcome")


def check_modifiers(effects: str, script: str, modifiers: str, problems: list[str]) -> None:
    declared = set(re.findall(r"(?m)^(ywc_[A-Za-z0-9_]+) = \{", modifiers))
    for name in REQUIRED_MODIFIERS:
        if name not in declared:
            problems.append(f"{name}: hegemony static modifier missing")
    referenced = set(re.findall(r"add_modifier = \{ name = (ywc_[A-Za-z0-9_]+)", script + "\n" + effects))
    for name in sorted(referenced):
        if name not in declared:
            problems.append(f"add_modifier {name} is not a declared static modifier")


def check_localization(events: list[dict], root: Path, problems: list[str]) -> None:
    for language, path in (("english", LOC_EN_PATH), ("simp_chinese", LOC_CN_PATH)):
        text = _read(root, path)
        keys = set(re.findall(r"(?m)^\s*(ywc_[A-Za-z0-9_.]+):\d+", text))
        expected = set()
        for event in events:
            expected |= {f"{event['id']}.t", f"{event['id']}.d"}
            expected |= {f"{event['id']}.{chr(ord('a') + index)}" for index in range(len(event["choices"]))}
        for missing in sorted(expected - keys):
            problems.append(f"{path}: missing key {missing}")
        keys_file = (root / f"yongchang_world/localization/{language}/ywc_hegemony_keys_l_{language}.yml").read_text(encoding="utf-8-sig")
        for key in REQUIRED_LOC_KEYS:
            if f" {key}:0" not in keys_file:
                problems.append(f"ywc_hegemony_keys_l_{language}.yml: missing key {key}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    problems: list[str] = []

    try:
        catalog = load_catalog(root)
        events = validate(catalog)
    except ValueError as error:
        print(error)
        return 1

    rendered = render_all(root)
    for path, expected in rendered.items():
        if path.read_text(encoding="utf-8-sig") != expected:
            problems.append(f"{path.relative_to(root)}: generated file is stale, rerun tools/build_hegemony_content.py")

    check_events(events, _read(root, EVENTS_PATH), problems)
    check_pulse(catalog, _read(root, EFFECTS_PATH), problems)
    check_hooks(_read(root, CAMPAIGN_EVENTS_PATH), problems)
    check_journal(_read(root, JOURNAL_PATH), problems)
    check_modifiers(
        _read(root, EFFECTS_PATH),
        _read(root, EVENTS_PATH) + "\n" + _read(root, CAMPAIGN_EVENTS_PATH),
        _read(root, MODIFIERS_PATH),
        problems,
    )
    check_localization(events, root, problems)

    if problems:
        print(f"{len(problems)} hegemony content problem(s) found:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("hegemony content is consistent: 33 events, nine tribute candidates, three settlement outcomes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
