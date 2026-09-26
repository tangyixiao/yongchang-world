"""Static acceptance checks for the 2026-09-25 large campaign content.

The campaign adds 150 national chapter events (ywc_<tag>.100-.114), 30
cross-country crisis events (ywc_crisis.1-.30), three-chapter journal
chaining for the ten countries and five crisis journals. This tool verifies
the whole chain without launching the game:

* the committed catalog is structurally valid (180 unique ids, chapter order,
  bilingual copy, option counts) and the three generated files are current;
* every national event is fired by exactly the chapter journal that owns it
  and writes the completion marker that journal's pulse waits on;
* every chapter's last event settles through ywc_campaign_settle_mid/final
  with the catalog's real-world gate, writes the legacy resolved/failed
  markers and opens the next chapter (chapter three leaves an aftermath);
* every crisis stage event is fired by its holder's pulse and answers on the
  design's country; stage six confirms the computed outcome;
* both localizations carry every event key and all campaign helper, journal
  and modifier names.

Static checks cannot prove in-game behaviour; the release playbook keeps the
live acceptance gates separate.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from tools.build_campaign_content import (
        LOC_CN_PATH,
        LOC_EN_PATH,
        EVENTS_PATH,
        CATALOG_PATH,
        load_catalog,
        render_all,
        validate,
    )
except ModuleNotFoundError:  # Running this file directly puts ``tools`` on sys.path.
    from build_campaign_content import (
        LOC_CN_PATH,
        LOC_EN_PATH,
        EVENTS_PATH,
        CATALOG_PATH,
        load_catalog,
        render_all,
        validate,
    )

CRISIS_JOURNAL_PATH = Path("yongchang_world/common/journal_entries/ywc_large_campaign_crises.txt")
EFFECTS_PATH = Path("yongchang_world/common/scripted_effects/ywc_campaign_effects.txt")
MODIFIERS_PATH = Path("yongchang_world/common/static_modifiers/ywc_static_modifiers.txt")
STARTS_PATH = Path("yongchang_world/common/history/countries/ywc_content_starts.txt")

OPTION_BLOCK = re.compile(r"(?ms)^    option = \{.*?^    \}")
NAME_IN_OPTION = re.compile(r"(?m)^\s*name = (ywc_[a-z]+\.\d+\.[a-z])\s*$")


def _read(root: Path, relative: Path) -> str:
    return (root / relative).read_text(encoding="utf-8-sig")


def event_blocks(text: str) -> dict[str, str]:
    blocks = {}
    pattern = re.compile(r"(?ms)^(ywc_[a-z]+\.\d+) = \{")
    matches = list(pattern.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks[match.group(1)] = text[match.start():end]
    return blocks


def check_events(events: list[dict], countries: dict, crises: dict, script: str, problems: list[str]) -> None:
    blocks = event_blocks(script)
    catalog_ids = {event["id"] for event in events}
    if set(blocks) != catalog_ids:
        missing = sorted(catalog_ids - set(blocks))
        extra = sorted(set(blocks) - catalog_ids)
        problems.append(f"event script mismatch: missing={missing} extra={extra}")
        return
    for event in events:
        block = blocks[event["id"]]
        letters = [chr(ord("a") + index) for index in range(len(event["choices"]))]
        found = NAME_IN_OPTION.findall(block)
        expected_names = {f"{event['id']}.{letter}" for letter in letters}
        if set(found) != expected_names:
            problems.append(f"{event['id']}: option names {sorted(found)} != {sorted(expected_names)}")
        if f"title = {event['id']}.t" not in block or f"desc = {event['id']}.d" not in block:
            problems.append(f"{event['id']}: title/desc keys missing")
        if event["kind"] == "national":
            short, chapter = event["short"], event["chapter"]
            done = f"ywc_campaign_{short}_c{chapter}_e{event['id'].rsplit('.', 1)[1]}_done"
            if block.count(f"name = {done} value = 1") < 2:
                problems.append(f"{event['id']}: both options must write {done}")
            if event.get("final"):
                settle = "ywc_campaign_settle_final" if chapter == 3 else "ywc_campaign_settle_mid"
                if settle not in block:
                    problems.append(f"{event['id']}: chapter settlement must call {settle}")
                    continue
                gate = countries[short]["gates"][str(chapter)]
                if f'GATE = "{gate}"' not in block:
                    problems.append(f"{event['id']}: GATE does not match the catalog gate for {short} c{chapter}")
                stem = countries[short]["journal_stem"]
                marker = f"ywc_je_flavor_{stem}_{chapter}_resolved"
                if marker not in block:
                    problems.append(f"{event['id']}: settlement must write {marker}")
                if chapter < 3:
                    nxt = f"ywc_je_flavor_{stem}_{chapter + 1}"
                    if f"add_journal_entry = {{ type = {nxt} }}" not in block:
                        problems.append(f"{event['id']}: settlement must open {nxt}")
        else:
            crisis, stage = event["crisis"], event["stage"]
            if stage < 6:
                call = f"ywc_campaign_crisis_answer = {{ CRISIS = {crisis} STAGE = {stage}"
                if call not in block:
                    problems.append(f"{event['id']}: options must record the stage answer")
                if len(blocks[event["id"]]) and "add_journal_entry" in block:
                    problems.append(f"{event['id']}: mid-crisis stages must not add journals")
            else:
                config = crises[str(crisis)]
                outcome = f"ywc_campaign_crisis{crisis}_outcome"
                for outcome_value in (1, 2, 3):
                    if f"set_variable = {{ name = {outcome} value = {outcome_value} }}" not in block:
                        problems.append(f"{event['id']}: outcome {outcome_value} option missing")
                full = config["settle_full"]
                if f"trigger = {{ {full} }}" not in block:
                    problems.append(f"{event['id']}: the full-agreement option must require the catalog settle conditions")
                for participant in config["participants"]:
                    if f"exists = c:{participant}" not in block:
                        problems.append(f"{event['id']}: participant {participant} effect is unguarded")


def journal_block(journal: str, text: str) -> str | None:
    match = re.search(rf"(?ms)^{re.escape(journal)} = \{{(.*?)(?=^\S|\Z)", text)
    return match.group(0) if match else None


def check_journals(countries: dict, starts: str, journal_texts: dict[str, str], problems: list[str]) -> None:
    for short, config in countries.items():
        for chapter in (1, 2, 3):
            journal = f"ywc_je_flavor_{config['journal_stem']}_{chapter}"
            source = journal_texts.get(f"ywc_{short}.txt")
            block = journal_block(journal, source) if source else None
            if block is None:
                problems.append(f"{journal}: missing from ywc_{short}.txt")
                continue
            events = [config["preludes"][str(chapter)]] + [
                f"ywc_{short}.{99 + (chapter - 1) * 5 + position}" for position in range(1, 6)
            ]
            for event_id in events:
                if f"trigger_event = {{ id = {event_id} }}" not in block:
                    problems.append(f"{journal}: does not fire {event_id}")
            for suffix in ("resolved", "failed"):
                if f"has_variable = ywc_je_flavor_{config['journal_stem']}_{chapter}_{suffix}" not in block:
                    problems.append(f"{journal}: complete/fail must read the legacy {suffix} marker")
            outcome = f"ywc_campaign_{short}_c{chapter}_outcome"
            if outcome not in block:
                problems.append(f"{journal}: pulse must be gated on {outcome}")
        if f"type = ywc_je_flavor_{config['journal_stem']}_1" not in starts:
            problems.append(f"{short}: chapter one journal must start with the country")
        for chapter in (2, 3):
            if f"ywc_je_flavor_{config['journal_stem']}_{chapter} }}" in starts:
                problems.append(f"{short}: chapter {chapter} journal must only open at settlement")


def check_crisis_journals(crises: dict, journal_text: str, effects: str, problems: list[str]) -> None:
    for crisis_id, config in crises.items():
        n = int(crisis_id)
        journal = config["journal"]
        block = journal_block(journal, journal_text)
        if block is None:
            problems.append(f"{journal}: missing from ywc_large_campaign_crises.txt")
            continue
        if f"has_variable = ywc_campaign_crisis{n}_outcome" not in block:
            problems.append(f"{journal}: complete must read the crisis outcome")
        pulse = f"ywc_crisis_pulse_" + config["journal"].replace("ywc_je_crisis_", "")
        if pulse not in block:
            problems.append(f"{journal}: must drive the stages through {pulse}")
        pulse_block = journal_block(pulse, effects)
        if pulse_block is None:
            problems.append(f"{pulse}: missing from ywc_campaign_effects.txt")
            continue
        for stage in range(1, 7):
            event_id = f"ywc_crisis.{(n - 1) * 6 + stage}"
            if f"trigger_event = {{ id = {event_id} }}" not in pulse_block:
                problems.append(f"{pulse}: stage {stage} never fires {event_id}")
            if f"var:ywc_campaign_crisis{n}_stage = {stage}" not in pulse_block:
                problems.append(f"{pulse}: stage {stage} state is not tracked")
        if f"ywc_campaign_crisis{n}_outcome value = 2" not in pulse_block:
            problems.append(f"{pulse}: timeout must settle as a limited pact")


def check_helpers(effects: str, problems: list[str]) -> None:
    for helper in (
        "ywc_campaign_settle_mid",
        "ywc_campaign_settle_final",
        "ywc_campaign_crisis_answer",
        "ywc_campaign_tick_national_wait",
        "ywc_campaign_tick_dialogue_cooldown",
    ):
        if not re.search(rf"(?m)^{helper} = \{{", effects):
            problems.append(f"{helper}: missing from ywc_campaign_effects.txt")


def check_modifiers(script: str, effects: str, modifiers: str, problems: list[str]) -> None:
    referenced = set(re.findall(r"add_modifier = \{ name = (ywc_[A-Za-z0-9_]+)", script + "\n" + effects))
    declared = set(re.findall(r"(?m)^(ywc_[A-Za-z0-9_]+) = \{", modifiers))
    for name in sorted(referenced):
        if name not in declared:
            problems.append(f"add_modifier {name} is not a declared static modifier")
    for name in (
        "ywc_campaign_commitment",
        "ywc_campaign_local_compromise",
        "ywc_campaign_reform_backlash",
        "ywc_campaign_charter_established",
        "ywc_campaign_aftermath_established",
        "ywc_campaign_aftermath_compromise",
        "ywc_campaign_aftermath_backlash",
        "ywc_campaign_crisis_pact",
        "ywc_campaign_crisis_limited",
        "ywc_campaign_crisis_fallout",
    ):
        if name not in declared:
            problems.append(f"{name}: campaign static modifier missing")


def check_localization(events: list[dict], root: Path, problems: list[str]) -> None:
    for language, path in (("english", LOC_EN_PATH), ("simp_chinese", LOC_CN_PATH)):
        text = _read(root, path)
        header = "l_english:" if language == "english" else "l_simp_chinese:"
        if not text.lstrip("\ufeff").startswith(header):
            problems.append(f"{path}: localization must start with {header}")
        keys = set(re.findall(r"(?m)^\s*(ywc_[A-Za-z0-9_.]+):\d+", text))
        expected = set()
        for event in events:
            letters = (chr(ord("a") + index) for index in range(len(event["choices"])))
            expected |= {f"{event['id']}.t", f"{event['id']}.d"}
            expected |= {f"{event['id']}.{letter}" for letter in letters}
        for missing in sorted(expected - keys):
            problems.append(f"{path}: missing key {missing}")
    campaign_keys = (
        "ywc_je_crisis_suzerainty",
        "ywc_je_crisis_blackwater",
        "ywc_je_crisis_inner_asian_routes",
        "ywc_je_crisis_south_seas",
        "ywc_je_crisis_pacific_autonomy",
        "ywc_campaign_settle_mid",
        "ywc_campaign_settle_final",
        "ywc_campaign_crisis_answer",
        "ywc_campaign_commitment",
        "ywc_campaign_crisis_pact",
    )
    for language in ("english", "simp_chinese"):
        loc = (root / f"yongchang_world/localization/{language}/ywc_campaign_l_{language}.yml").read_text(encoding="utf-8-sig")
        for key in campaign_keys:
            if f" {key}:0" not in loc:
                problems.append(f"ywc_campaign_l_{language}.yml: missing key {key}")


def check_preludes(countries: dict, event_files: dict[str, str], problems: list[str]) -> None:
    for short, config in countries.items():
        for chapter in (1, 2, 3):
            prelude = config["preludes"][str(chapter)]
            source = None
            for name, text in event_files.items():
                if f"{prelude} = {{" in text:
                    source = text
                    break
            if source is None:
                problems.append(f"{prelude}: prelude event not found")
                continue
            block = journal_block(prelude, source)
            marker = f"ywc_campaign_{short}_c{chapter}_prelude"
            if not block or f"name = {marker} value = 1" not in block:
                problems.append(f"{prelude}: every option must record {marker}")
            stem = config["journal_stem"]
            legacy = f"ywc_je_flavor_{stem}_{chapter}_resolved"
            if re.search(rf"set_variable = \{{ name = {re.escape(legacy)} ", source):
                problems.append(f"{prelude}: the prelude must not settle the chapter; only the last event may")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    problems: list[str] = []

    try:
        catalog = load_catalog(root)
        countries = catalog["countries"]
        crises = catalog["crises"]
        events = validate(catalog)
    except ValueError as error:
        print(error)
        return 1

    rendered = render_all(root)
    for path, expected in rendered.items():
        if path.read_text(encoding="utf-8-sig") != expected:
            problems.append(f"{path.relative_to(root)}: generated file is stale, rerun tools/build_campaign_content.py")

    script = _read(root, EVENTS_PATH)
    effects = _read(root, EFFECTS_PATH)
    modifiers = _read(root, MODIFIERS_PATH)
    starts = _read(root, STARTS_PATH)
    journal_dir = root / "yongchang_world/common/journal_entries"
    journal_texts = {
        path.name: path.read_text(encoding="utf-8-sig") for path in sorted(journal_dir.glob("ywc_*.txt"))
    }

    check_events(events, countries, crises, script, problems)
    check_journals(countries, starts, journal_texts, problems)
    check_crisis_journals(crises, journal_texts.get("ywc_large_campaign_crises.txt", ""), effects, problems)
    check_helpers(effects, problems)
    check_modifiers(script, effects, modifiers, problems)
    check_localization(events, root, problems)
    check_preludes(
        countries,
        {
            path.name: path.read_text(encoding="utf-8-sig")
            for path in sorted((root / "yongchang_world/events").glob("ywc_*.txt"))
        },
        problems,
    )

    if problems:
        print(f"{len(problems)} campaign content problem(s) found:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(
        "campaign content is consistent: 180 events, 30 chained chapter journals, "
        "5 crisis journals, bilingual localization current"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
