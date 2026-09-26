"""One-command readiness report for every release gate, read-only.

The manual acceptance is spread over five different evidence sources (static
checks, the launcher's playset state, the acceptance log, the native scripted
suites, and the 15-run observation matrix). This tool runs the read-only parts
of each one and prints a single table, so an operator can see what is still
missing before starting a session and what is still wrong after finishing one.

It never writes game data, never edits a run, and never upgrades a status: an
incomplete gate stays `incomplete` here too.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.inspect_playsets import evaluate as evaluate_playsets  # noqa: E402
from tools.inspect_playsets import load_playsets  # noqa: E402
from tools.observation_status import inspect_matrix  # noqa: E402
from tools.validate_manual_acceptance import validate as validate_log  # noqa: E402

EXPECTED_PLAYSETS = 5
EXPECTED_COUNTRIES = 10
EXPECTED_SUITES = 2
EXPECTED_RUNS = 15
EXPECTED_ROWS = 450


def _entry(gate: str, name: str, status: str, detail: str) -> dict:
    return {"gate": gate, "name": name, "status": status, "detail": detail}


def build_report(
    root: Path,
    user_data_dir: Path | None = None,
    observe_root: Path | None = None,
    log_path: Path | None = None,
    game_root: Path | None = None,
) -> dict:
    root = Path(root)
    mod_root = root / "yongchang_world"
    entries: list[dict] = []

    try:
        from tools.ywc_check import validate as validate_mod
    except ModuleNotFoundError:  # pragma: no cover - direct execution path only.
        from ywc_check import validate as validate_mod

    if mod_root.is_dir():
        try:
            diagnostics = validate_mod(mod_root, game_root)
        except (OSError, ValueError, KeyError) as error:
            entries.append(_entry("static", "ywc_check", "blocked", f"check failed to run: {error}"))
        else:
            entries.append(
                _entry(
                    "static",
                    "ywc_check",
                    "ok" if not diagnostics else "blocked",
                    f"{len(diagnostics)} diagnostic(s)" if diagnostics else "clean",
                )
            )
    else:
        entries.append(_entry("static", "ywc_check", "blocked", f"missing mod root {mod_root}"))

    registry = root / "data/scenario/tag_registry.json"
    if registry.is_file():
        try:
            from tools.scenario_tag_audit import audit_repository_tags
        except ModuleNotFoundError:  # pragma: no cover
            from scenario_tag_audit import audit_repository_tags

        try:
            diagnostics = audit_repository_tags(root)
        except (OSError, ValueError, KeyError) as error:
            entries.append(
                _entry("static", "scenario_tag_audit", "blocked", f"audit failed to run: {error}")
            )
        else:
            entries.append(
                _entry(
                    "static",
                    "scenario_tag_audit",
                    "ok" if not diagnostics else "blocked",
                    f"{len(diagnostics)} diagnostic(s)" if diagnostics else "clean",
                )
            )
    else:
        entries.append(_entry("static", "scenario_tag_audit", "skipped", "no tag registry"))

    allowlist = root / "data/content/reachability_allowlist.json"
    if allowlist.is_file():
        try:
            from tools.content_reachability import audit as audit_reachability
        except ModuleNotFoundError:  # pragma: no cover
            from content_reachability import audit as audit_reachability

        try:
            report = audit_reachability(mod_root, allowlist)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            entries.append(
                _entry("static", "content_reachability", "blocked", f"audit failed to run: {error}")
            )
        else:
            problems = (
                report["dangling_references"]
                + report["unreferenced_events"]
                + report["unreferenced_journals"]
                + report["unused_scripted_helpers"]
            )
            entries.append(
                _entry(
                    "static",
                    "content_reachability",
                    "ok" if not problems else "blocked",
                    f"events={report['event_count']} journals={report['journal_count']} "
                    + ("clean" if not problems else f"{len(problems)} problem(s)"),
                )
            )
    else:
        entries.append(_entry("static", "content_reachability", "skipped", "no allowlist"))

    # Startup pops and buildings are only read when a campaign starts, so a
    # bad key costs a real 1836 session to discover.
    if game_root is not None:
        try:
            from tools.startup_data_audit import audit as audit_startup_data
        except ModuleNotFoundError:  # pragma: no cover
            from startup_data_audit import audit as audit_startup_data

        try:
            startup_report = audit_startup_data(mod_root, Path(game_root))
        except (OSError, ValueError, KeyError) as error:
            entries.append(
                _entry("static", "startup_data", "blocked", f"audit failed to run: {error}")
            )
        else:
            problems = startup_report["problems"]
            entries.append(
                _entry(
                    "static",
                    "startup_data",
                    "ok" if not problems else "blocked",
                    f"buildings={startup_report['checked_buildings']} "
                    f"pop fields={startup_report['checked_pops']}"
                    + (" clean" if not problems else f", {len(problems)} problem(s)"),
                )
            )
    else:
        entries.append(_entry("static", "startup_data", "skipped", "no game root"))

    database = (user_data_dir / "launcher-v2.sqlite") if user_data_dir else None
    if database is not None and database.is_file():
        try:
            playsets = evaluate_playsets(load_playsets(database))
        except Exception as error:  # pragma: no cover - depends on launcher state.
            entries.append(_entry("gate1", "playsets", "blocked", f"cannot read launcher: {error}"))
        else:
            matched = [row for row in playsets if row["matches"]]
            detail = "; ".join(f"{row['config']}: {row['reasons'][0]}" for row in playsets if not row["matches"])
            entries.append(
                _entry(
                    "gate1",
                    "playsets",
                    "ok" if len(matched) == EXPECTED_PLAYSETS else "incomplete",
                    f"{len(matched)}/{EXPECTED_PLAYSETS} configurations confirmed"
                    + (f" — {detail}" if detail else ""),
                )
            )
    else:
        entries.append(_entry("gate1", "playsets", "skipped", "no launcher database supplied"))

    # Gate 3 costs a real campaign session, so the suites' vocabulary is worth
    # checking before anyone plays: an unknown trigger never satisfies a test.
    if game_root is not None and (Path(game_root) / "common").is_dir():
        try:
            from tools.scripted_test_audit import audit as audit_scripted_tests
        except ModuleNotFoundError:  # pragma: no cover
            from scripted_test_audit import audit as audit_scripted_tests

        try:
            scripted_report = audit_scripted_tests(mod_root, Path(game_root))
        except (OSError, ValueError, KeyError) as error:
            entries.append(
                _entry("gate3", "scripted_test_vocabulary", "blocked", f"audit failed to run: {error}")
            )
        else:
            unknown = scripted_report["unknown_keys"]
            entries.append(
                _entry(
                    "gate3",
                    "scripted_test_vocabulary",
                    "ok" if not unknown else "blocked",
                    f"{len(scripted_report['used_keys'])} keys used, "
                    + ("all grounded in the installed game" if not unknown else f"{len(unknown)} unknown"),
                )
            )
    else:
        entries.append(_entry("gate3", "scripted_test_vocabulary", "skipped", "no game root"))

    if log_path is not None and Path(log_path).is_file():
        log_errors, log_counts = validate_log(Path(log_path))
        entries.append(
            _entry(
                "gate2",
                "acceptance_log",
                "ok" if not log_errors else "blocked",
                f"{log_counts.get('verified', 0)} verified / "
                f"{log_counts.get('pending', 0)} pending / {log_counts.get('failed', 0)} failed",
            )
        )
        for gate, name, key, expected in (
            ("gate2", "countries_1836", "countries", EXPECTED_COUNTRIES),
            ("gate3", "scripted_tests", "scripted_tests", EXPECTED_SUITES),
        ):
            verified = log_counts.get(f"verified_{key}", 0)
            entries.append(
                _entry(
                    gate,
                    name,
                    "ok" if verified == expected else "incomplete",
                    f"{verified}/{expected} rows verified in the acceptance log",
                )
            )
    else:
        entries.append(_entry("gate2", "acceptance_log", "skipped", "no acceptance log"))
        entries.append(_entry("gate2", "countries_1836", "skipped", "no acceptance log"))
        entries.append(_entry("gate3", "scripted_tests", "skipped", "no acceptance log"))

    if observe_root is not None and Path(observe_root).is_dir():
        report = inspect_matrix(Path(observe_root))
        entries.append(
            _entry(
                "gate4",
                "observation_matrix",
                "ok" if len(report["ready_runs"]) == EXPECTED_RUNS else "incomplete",
                f"{report['recorded_rows']}/{EXPECTED_ROWS} checkpoint rows; "
                f"{len(report['ready_runs'])}/{EXPECTED_RUNS} runs ready",
            )
        )
    else:
        entries.append(_entry("gate4", "observation_matrix", "skipped", "no observation root"))

    # A skipped check is not evidence: readiness needs every gate to be ok.
    ready = all(entry["status"] == "ok" for entry in entries)
    return {
        "root": str(root),
        "entries": entries,
        "statuses": {entry["name"]: entry["status"] for entry in entries},
        "ready": ready,
        "blocked": [entry["name"] for entry in entries if entry["status"] == "blocked"],
        "incomplete": [entry["name"] for entry in entries if entry["status"] == "incomplete"],
        "skipped": [entry["name"] for entry in entries if entry["status"] == "skipped"],
    }


def format_report(report: dict) -> str:
    width = max(len(entry["name"]) for entry in report["entries"]) if report["entries"] else 0
    lines = [f"{'gate':<8}{'check':<{width + 2}}status", "-" * (width + 26)]
    for entry in report["entries"]:
        lines.append(
            f"{entry['gate']:<8}{entry['name']:<{width + 2}}{entry['status']:<12}{entry['detail']}"
        )
    lines.append("")
    if report["ready"]:
        lines.append("All gates are complete.")
    else:
        parts = []
        if report["blocked"]:
            parts.append(f"blocked={report['blocked']}")
        if report["incomplete"]:
            parts.append(f"incomplete={report['incomplete']}")
        if report["skipped"]:
            parts.append(f"not-run={report['skipped']}")
        lines.append("Not release-ready: " + " ".join(parts))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--user-data-dir", type=Path)
    parser.add_argument("--observe-root", type=Path, default=Path("artifacts/observe"))
    parser.add_argument("--log", type=Path, default=Path("docs/release/manual-acceptance-log.md"))
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(
        args.root,
        user_data_dir=args.user_data_dir,
        observe_root=args.observe_root,
        log_path=args.log,
        game_root=args.game_root,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
