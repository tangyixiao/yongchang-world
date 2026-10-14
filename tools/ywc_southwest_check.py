"""Static acceptance checks for the v0.2 六六大顺 southwest layer.

Verifies the chain without launching the game:

* the catalog is structurally valid (six lines, three events each, bilingual
  copy, two choices per event) and the four generated files are current;
* each country's journal chains its three events through the done markers
  and completes on the line settlement markers;
* every line's last event writes both settlement markers and every country
  block mounts its journal behind the shared-variable reset;
* referenced modifiers are declared and both localizations are complete.

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
    from tools.build_southwest_content import (
        CATALOG_PATH,
        EVENTS_PATH,
        JOURNAL_PATH,
        LOC_CN_PATH,
        LOC_EN_PATH,
        load_catalog,
        render_all,
        validate,
    )
except ModuleNotFoundError:  # Running this file directly puts ``tools`` on sys.path.
    from build_campaign_content import EVENTS_PATH as CAMPAIGN_EVENTS_PATH
    from build_southwest_content import (
        CATALOG_PATH,
        EVENTS_PATH,
        JOURNAL_PATH,
        LOC_CN_PATH,
        LOC_EN_PATH,
        load_catalog,
        render_all,
        validate,
    )

STARTS_PATH = Path("yongchang_world/common/history/countries/ywc_regional_countries.txt")
MODIFIERS_PATH = Path("yongchang_world/common/static_modifiers/ywc_static_modifiers.txt")

EVENT_BLOCK = re.compile(r"(?ms)^(ywc_[a-z]+\.\d+) = \{")
OPTION_NAME = re.compile(r"(?m)^\s*name = (ywc_[a-z]+\.\d+\.[a-z])\s*$")


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
        problems.append("southwest event script mismatch with the catalog")
        return
    for event in events:
        block = blocks[event["id"]]
        expected = {f"{event['id']}.{chr(ord('a') + index)}" for index in range(len(event["choices"]))}
        if set(OPTION_NAME.findall(block)) != expected:
            problems.append(f"{event['id']}: option names do not match the catalog")
        if f"title = {event['id']}.t" not in block or f"desc = {event['id']}.d" not in block:
            problems.append(f"{event['id']}: title/desc keys missing")


def check_journals(catalog: dict, journal: str, script: str, starts: str, problems: list[str]) -> None:
    for line in catalog["lines"]:
        short, tag = line["short"], line["tag"]
        if f"{line['journal']} = {{" not in journal:
            problems.append(f"{line['journal']}: missing from ywc_southwest_journal.txt")
        for slot in (1, 2, 3):
            if f"trigger_event = {{ id = ywc_{short}.{slot} }}" not in journal:
                problems.append(f"{line['journal']}: does not fire ywc_{short}.{slot}")
        if f"has_variable = ywc_sw_{short}_resolved" not in journal:
            problems.append(f"{line['journal']}: complete must read the line settlement marker")
        for suffix in (1, 2, 3):
            event_id = f"ywc_{short}.{suffix}"
            if event_id not in script or f"ywc_sw_{short}_e{suffix}_done" not in script:
                problems.append(f"{event_id}: its choices must write the done marker")
        settled = "ywc_sw_%s_resolved" % short in script and "ywc_sw_%s_failed" % short in script
        if not settled:
            problems.append(f"ywc_{short}.3: must write both line settlement markers")
        block_pattern = re.compile(rf"(?ms)^(    c:{tag} \?=\s*\{{\n)(.*?)(?=^    c:[A-Z]{{3}}|\Z)")
        match = block_pattern.search(starts)
        if not match:
            problems.append(f"{tag}: no country block found in ywc_regional_countries.txt")
            continue
        block = match.group(2)
        if "ywc_reset_shared_variables = yes" not in block:
            problems.append(f"{tag}: block must run ywc_reset_shared_variables before journals")
        if f"add_journal_entry = {{ type = ywc_je_sw_{short} }}" not in block:
            problems.append(f"{tag}: block must mount {line['journal']}")


def check_modifiers(script: str, modifiers: str, problems: list[str]) -> None:
    declared = set(re.findall(r"(?m)^(ywc_[A-Za-z0-9_]+) = \{", modifiers))
    referenced = set(re.findall(r"add_modifier = \{ name = (ywc_[A-Za-z0-9_]+)", script))
    for name in sorted(referenced):
        if name not in declared:
            problems.append(f"add_modifier {name} is not a declared static modifier")
    for name in (
        "ywc_sw_tea_charter",
        "ywc_sw_market_open",
        "ywc_sw_caravan_guard",
        "ywc_sw_drill_effect",
        "ywc_sw_levy_burden",
        "ywc_sw_poppy_shadow",
        "ywc_sw_rice_contract",
        "ywc_sw_exile_strain",
    ):
        if name not in declared:
            problems.append(f"{name}: southwest static modifier missing")


def check_localization(catalog: dict, root: Path, problems: list[str]) -> None:
    for language, path in (("english", LOC_EN_PATH), ("simp_chinese", LOC_CN_PATH)):
        text = _read(root, path)
        keys = set(re.findall(r"(?m)^\s*(ywc_[A-Za-z0-9_.]+):\d+", text))
        expected = set()
        for line in catalog["lines"]:
            for event in line["events"]:
                expected |= {f"{event['id']}.t", f"{event['id']}.d"}
                expected |= {f"{event['id']}.{chr(ord('a') + index)}" for index in range(len(event["choices"]))}
        for missing in sorted(expected - keys):
            problems.append(f"{path}: missing key {missing}")
        keys_file = (root / f"yongchang_world/localization/{language}/ywc_southwest_keys_l_{language}.yml").read_text(encoding="utf-8-sig")
        for line in catalog["lines"]:
            if f" {line['journal']}:0" not in keys_file:
                problems.append(f"ywc_southwest_keys_l_{language}.yml: missing key {line['journal']}")


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
            problems.append(f"{path.relative_to(root)}: generated file is stale, rerun tools/build_southwest_content.py")

    check_events(events, _read(root, EVENTS_PATH), problems)
    check_journals(
        catalog,
        _read(root, JOURNAL_PATH),
        _read(root, EVENTS_PATH),
        _read(root, STARTS_PATH),
        problems,
    )
    check_modifiers(_read(root, EVENTS_PATH), _read(root, MODIFIERS_PATH), problems)
    check_localization(catalog, root, problems)

    if problems:
        print(f"{len(problems)} southwest content problem(s) found:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("southwest content is consistent: six lines, 18 events, journals mounted at start")
    return 0


if __name__ == "__main__":
    sys.exit(main())
