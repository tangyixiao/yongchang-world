"""Audit that Mod content can actually be reached or triggered.

`content_unreachable` is one of the manual-observation anomaly categories, but
most of the ways content becomes unreachable are visible statically:

* an event or journal entry that nothing ever references can never fire;
* a `trigger_event`/`add_journal_entry` reference to a name that is not
  declared can never fire, and fails silently in game;
* a scripted effect or trigger that nothing calls is dead weight.

Reference counting is deliberately token based: every script form vanilla uses
(`trigger_event = { id = X }`, `events = { X }`, `random_events = { 10 = X }`,
`add_journal_entry = { type = X }`, `X = yes`) contains the name as a whole
token, so counting whole-token occurrences outside the declaration itself
covers all of them without re-implementing the Clausewitz grammar.

Scripted effects and triggers that are intentionally unused must be listed in
`data/content/reachability_allowlist.json` with a reason, so dead content stays
explicit instead of accumulating silently.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ywc_check import _script_files, _without_comments_and_strings  # noqa: E402

ALLOWLIST_PATH = Path("data/content/reachability_allowlist.json")
EVENT_DECLARATION = re.compile(r"^\s*(ywc_[a-z_]+\.\d+)\s*=\s*\{", re.M)
JOURNAL_DECLARATION = re.compile(r"^\s*(ywc_(?:je|route)_[a-z0-9_]+)\s*=\s*\{", re.M)
ROUTE_DECLARATION = re.compile(r"^\s*(ywc_route_[a-z0-9_]+)\s*=\s*\{", re.M)
HELPER_DECLARATION = re.compile(r"^\s*(ywc_[a-z0-9_]+)\s*=\s*\{", re.M)
REFERENCE_PATTERNS = (
    re.compile(r"trigger_event\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.]+)"),
    re.compile(r"add_journal_entry\s*=\s*\{\s*type\s*=\s*([A-Za-z0-9_.]+)"),
    re.compile(r"^\s*events\s*=\s*\{([^}]*)\}", re.M | re.S),
)


def _script_texts(root: Path) -> dict[Path, str]:
    texts: dict[Path, str] = {}
    for path in _script_files(Path(root)):
        texts[path] = _without_comments_and_strings(path.read_text(encoding="utf-8-sig"))
    return texts


TOKEN = re.compile(r"[A-Za-z0-9_.]+")


def _token_counts(text: str) -> Counter[str]:
    """Count whole tokens once, so per-name lookups stay O(1).

    The token pattern is the same character class as a Clausewitz identifier,
    so a name embedded in a longer identifier is not counted as a reference.
    """

    return Counter(TOKEN.findall(text))


def _declarations(texts: dict[Path, str], pattern: re.Pattern[str]) -> dict[str, Path]:
    declared: dict[str, Path] = {}
    for path, text in texts.items():
        for match in pattern.finditer(text):
            declared.setdefault(match.group(1), path)
    return declared


def _journal_declarations(texts: dict[Path, str], pattern: re.Pattern[str]) -> dict[str, Path]:
    journal_texts = {
        path: text for path, text in texts.items()
        if "journal_entries" in {part.lower() for part in path.parts}
    }
    return _declarations(journal_texts, pattern)


def _extract_block(text: str, start: int) -> str | None:
    """Return a balanced Clausewitz block beginning at its opening brace."""
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index]
    return None


def _named_blocks(text: str, name: str) -> list[str]:
    blocks = []
    pattern = re.compile(rf"\b{re.escape(name)}\s*=\s*\{{")
    for match in pattern.finditer(text):
        # JE activation fields must be direct members of the JE declaration;
        # a similarly named field buried in an unrelated effect is not a gate.
        if text[:match.start()].count("{") != text[:match.start()].count("}"):
            continue
        block = _extract_block(text, match.end() - 1)
        if block is not None:
            blocks.append(block)
    return blocks


COUNTRY_FILTER = re.compile(
    r"\bc:([A-Z0-9]{2,4})\s*\??=\s*(?:this|root|\{)|"
    r"\b(?:this|root)\s*=\s*c:([A-Z0-9]{2,4})\b"
)


def _country_filter_tags(blocks: list[str]) -> set[str]:
    return {
        tag
        for block in blocks
        for match in COUNTRY_FILTER.finditer(block)
        for tag in match.groups()
        if tag is not None
    }


def _auto_journal_entries(texts: dict[Path, str]) -> set[str]:
    """Recognize explicit country-scoped JE self-activation conditions.

    Victoria 3 activates an inactive JE when both `is_shown_when_inactive`
    and `possible` pass. Require a country filter in both blocks so generic
    always-true entries cannot bypass reachability review.
    """
    journal_texts = {
        path: text for path, text in texts.items()
        if "journal_entries" in {part.lower() for part in path.parts}
    }
    result: set[str] = set()
    for path, text in journal_texts.items():
        for match in JOURNAL_DECLARATION.finditer(text):
            entry = _extract_block(text, match.end() - 1)
            if entry is None:
                continue
            shown = _named_blocks(entry, "is_shown_when_inactive")
            possible = _named_blocks(entry, "possible")
            if _country_filter_tags(shown) & _country_filter_tags(possible):
                result.add(match.group(1))
    return result


def _referenced_names(texts: dict[Path, str]) -> set[str]:
    names: set[str] = set()
    for text in texts.values():
        for pattern in REFERENCE_PATTERNS[:2]:
            names.update(pattern.findall(text))
        for block in REFERENCE_PATTERNS[2].findall(text):
            names.update(re.findall(r"[A-Za-z0-9_.]+", block))
    return names


def load_allowlist(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected an object")
    allowed = data.get("unused_scripted_helpers", {})
    if not isinstance(allowed, dict):
        raise ValueError(f"{path}: unused_scripted_helpers must be an object")
    return {str(key): str(value) for key, value in allowed.items()}


def audit(root: Path, allowlist_path: Path | None = None) -> dict:
    root = Path(root)
    texts = _script_texts(root)
    counts = _token_counts("\n".join(texts.values()))
    events = _declarations(texts, EVENT_DECLARATION)
    journals = _journal_declarations(texts, JOURNAL_DECLARATION)
    routes = _journal_declarations(texts, ROUTE_DECLARATION)
    auto_journals = _auto_journal_entries(texts)
    helpers = {
        name: path
        for name, path in _declarations(texts, HELPER_DECLARATION).items()
        if {"scripted_effects", "scripted_triggers"} & {part.lower() for part in path.parts}
    }
    referenced = _referenced_names(texts)

    unreferenced_events = sorted(name for name in events if counts[name] <= 1)
    unreferenced_journals = sorted(
        name for name in journals if counts[name] <= 1 and name not in auto_journals
    )
    dangling = sorted(
        name
        for name in referenced
        if (name.startswith("ywc_") and "." in name and name not in events)
        or (name.startswith(("ywc_je_", "ywc_route_")) and name not in journals)
    )
    allowlist = load_allowlist(allowlist_path or (root.parent / ALLOWLIST_PATH))
    unused_helpers = sorted(
        name for name in helpers if counts[name] <= 1 and name not in allowlist
    )
    return {
        "root": str(root),
        "event_count": len(events),
        "journal_count": len(journals),
        "route_count": len(routes),
        "helper_count": len(helpers),
        "dangling_references": dangling,
        "unreferenced_events": unreferenced_events,
        "unreferenced_journals": unreferenced_journals,
        "unused_scripted_helpers": unused_helpers,
        "allowlisted_helpers": sorted(name for name in helpers if name in allowlist),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("yongchang_world"))
    parser.add_argument("--allowlist", type=Path, default=ALLOWLIST_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = audit(args.root, args.allowlist)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(error)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"events={report['event_count']} journals={report['journal_count']} "
            f"scripted_helpers={report['helper_count']}"
        )
        for field, label in (
            ("dangling_references", "dangling reference"),
            ("unreferenced_events", "unreferenced event"),
            ("unreferenced_journals", "unreferenced journal"),
            ("unused_scripted_helpers", "unused scripted helper"),
        ):
            for name in report[field]:
                print(f"{label}: {name}")
        if report["allowlisted_helpers"]:
            print("allowlisted unused helpers: " + ", ".join(report["allowlisted_helpers"]))
    failures = (
        report["dangling_references"]
        + report["unreferenced_events"]
        + report["unreferenced_journals"]
        + report["unused_scripted_helpers"]
    )
    if failures:
        print(f"{len(failures)} reachability problem(s) found")
        return 1
    print("Content reachability is clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
