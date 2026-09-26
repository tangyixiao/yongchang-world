"""Audit the native scripted-test suites before they are run in a real campaign.

Gate 3 costs a real in-game session, and the suites have never produced a
passing result in this project, so their vocabulary is the least verified part
of the repo. A misspelled trigger name does not stop the suite from loading, it
just never satisfies the test, which wastes the session.

Every key used in `yongchang_world/tools/scripted_tests/*.txt` must therefore be
one of:

* a suite-format key documented in the game's own
  `tools/scripted_tests/scripted_tests.md` (`tests`, `last_date`,
  `acceptable_fail_rate`, `run_count`, `success`, `fail`);
* an identifier that occurs in the installed game's script;
* an identifier this repository declares.

The default vanilla corpus is deliberately narrow (scripted triggers, effects,
on_actions, journals, decisions, events and the vanilla suites) because that is
enough to cover every trigger the suites use while staying fast. If a key is
reported as unknown, rerun with `--full` to search the entire vanilla script
tree before treating it as a real problem.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SUITE_DIRECTORY = "tools/scripted_tests"
NARROW_CORPUS = (
    "common/scripted_triggers",
    "common/scripted_effects",
    "common/on_actions",
    "common/journal_entries",
    "common/decisions",
    "events",
    SUITE_DIRECTORY,
)
FULL_CORPUS = ("common", "events", "tools")
FORMAT_KEYS = {"tests", "last_date", "acceptable_fail_rate", "run_count", "success", "fail"}
TOKEN = re.compile(r"[A-Za-z0-9_.:]+")
KEY = re.compile(r"(?m)^\s*([A-Za-z][A-Za-z0-9_]*)\s*=(?!=)")
TEST_CASE_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _text_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            files.extend(path for path in root.rglob("*.txt") if path.is_file())
    return files


def build_vocabulary(game_root: Path, full: bool = False) -> set[str]:
    directories = FULL_CORPUS if full else NARROW_CORPUS
    files = _text_files([Path(game_root) / name for name in directories])
    vocabulary: set[str] = set()
    for path in files:
        try:
            text = path.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:  # pragma: no cover - a locked file must not stop the audit.
            continue
        vocabulary.update(TOKEN.findall(text))
    return vocabulary


def suite_keys(text: str) -> dict[str, list[int]]:
    """Return every key used in a suite, mapped to its line numbers."""

    keys: dict[str, list[int]] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        match = KEY.match(line)
        if not match:
            continue
        name = match.group(1)
        if TEST_CASE_NAME.match(name):
            continue
        keys.setdefault(name, []).append(line_number)
    return keys


def build_mod_vocabulary(mod_root: Path) -> set[str]:
    """Tokenize the Mod's own scripts, excluding the suites themselves.

    The suites must not seed their own vocabulary: otherwise a misspelled key
    would be found in the suite text itself and the audit would always pass.
    """

    vocabulary: set[str] = set()
    for path in _text_files([Path(mod_root)]):
        # Suites are the thing being audited, so their own text must not seed
        # the vocabulary; a misspelled key would otherwise validate itself.
        if "scripted_tests" in {part.lower() for part in path.relative_to(mod_root).parts}:
            continue
        try:
            vocabulary.update(TOKEN.findall(path.read_text(encoding="utf-8-sig", errors="ignore")))
        except OSError:  # pragma: no cover
            continue
    return vocabulary


def audit(mod_root: Path, game_root: Path, full: bool = False) -> dict:
    suite_root = Path(mod_root) / SUITE_DIRECTORY
    vocabulary = build_vocabulary(Path(game_root), full=full) | build_mod_vocabulary(Path(mod_root))

    suites: dict[str, dict] = {}
    unknown: list[str] = []
    used: set[str] = set()
    for path in sorted(suite_root.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        keys = suite_keys(text)
        suites[path.name] = {
            "keys": sorted(keys),
            "test_cases": sorted(set(re.findall(r"(?m)^\s{4}([A-Z][A-Z0-9_]*)\s*=\s*\{", text))),
        }
        for name, lines in sorted(keys.items()):
            used.add(name)
            if name in FORMAT_KEYS or name in vocabulary:
                continue
            locations = ", ".join(str(line) for line in lines)
            unknown.append(f"{path}:{lines[0]}: unknown trigger or effect {name} (lines {locations})")
    return {
        "corpus": "full" if full else "narrow",
        "vocabulary_size": len(vocabulary),
        "suites": suites,
        "used_keys": sorted(used),
        "unknown_keys": unknown,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod-root", type=Path, default=Path("yongchang_world"))
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--full", action="store_true", help="search the whole vanilla script tree")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    import json

    report = audit(args.mod_root, args.game_root, full=args.full)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"corpus={report['corpus']} vocabulary={report['vocabulary_size']} "
            f"suites={len(report['suites'])} keys={len(report['used_keys'])}"
        )
        for name, data in report["suites"].items():
            print(f"  {name}: {len(data['test_cases'])} test case(s)")
        for problem in report["unknown_keys"]:
            print(problem)
        if report["unknown_keys"]:
            print("Rerun with --full to search the entire vanilla script tree before fixing names.")
            return 1
        print("Scripted-test vocabulary is grounded in the installed game.")
    return 0 if not report["unknown_keys"] else 1


if __name__ == "__main__":
    sys.exit(main())
