"""Read the launcher's playset configuration as Gate 1 evidence, read-only.

Directly launched executables ignore `disabledDLC`, so the only trustworthy
per-configuration DLC switch is the official launcher's playset UI. This tool
reads what the launcher itself stored in `launcher-v2.sqlite` and reports
whether the five observation playsets match their intended DLC set and have
`The Yongchang World` enabled.

It opens the database through a read-only SQLite URI and never writes to the
user data directory; the optional `--output` file is the only file it creates.
A playset the launcher has not recorded a DLC row for is reported as unknown
rather than assumed, because an untoggled DLC is exactly the kind of gap that
silently changes a run.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.summarize_observation import CONFIGS, EXPECTED_DLC  # noqa: E402

DATABASE_NAME = "launcher-v2.sqlite"
GATE_DLCS = ("dlc010_ep1", "dlc013_mp1", "dlc018_ep2")
MOD_MARKERS = ("yongchang_world",)
UNKNOWN = "unknown"


class PlaysetError(Exception):
    """Raised when the launcher database cannot be read."""


def _connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise PlaysetError(f"launcher database does not exist: {db_path}")
    try:
        return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error as error:  # pragma: no cover - depends on launcher state
        raise PlaysetError(f"cannot open launcher database: {error}") from error


def load_playsets(db_path: Path) -> list[dict]:
    """Return every live playset with its enabled mods and recorded DLC rows."""

    connection = _connect(db_path)
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT id, name, isActive FROM playsets WHERE COALESCE(isRemoved, 0) = 0 ORDER BY name"
        ).fetchall()
        playsets: list[dict] = []
        for row in rows:
            mods = connection.execute(
                """
                SELECT m.name AS name, m.displayName AS display_name, m.dirPath AS dir_path, pm.enabled AS enabled
                FROM playsets_mods pm
                JOIN mods m ON m.id = pm.modId
                WHERE pm.playsetId = ?
                """,
                (row["id"],),
            ).fetchall()
            dlc_rows = connection.execute(
                "SELECT dlcId, enabled FROM playsets_dlcs WHERE playsetId = ?",
                (row["id"],),
            ).fetchall()
            playsets.append(
                {
                    "playset": row["name"],
                    "is_active": bool(row["isActive"]),
                    "mods": [
                        {
                            "name": mod["name"] or mod["display_name"] or "",
                            "display_name": mod["display_name"] or "",
                            "dir_path": mod["dir_path"] or "",
                            "enabled": bool(mod["enabled"]),
                        }
                        for mod in mods
                    ],
                    "dlc": {dlc["dlcId"]: bool(dlc["enabled"]) for dlc in dlc_rows},
                }
            )
        return playsets
    finally:
        connection.close()


def _is_target_mod(mod: dict) -> bool:
    fields = (mod.get("name", ""), mod.get("display_name", ""), mod.get("dir_path", ""))
    return any(marker in field for field in fields for marker in MOD_MARKERS)


def evaluate(playsets: list[dict]) -> list[dict]:
    """Compare every observation configuration against the recorded playsets."""

    by_name = {playset["playset"].strip().lower(): playset for playset in playsets}
    report: list[dict] = []
    for config in CONFIGS:
        expected = list(EXPECTED_DLC[config])
        playset = by_name.get(config)
        if playset is None:
            report.append(
                {
                    "config": config,
                    "playset": None,
                    "found": False,
                    "mod_enabled": False,
                    "expected_dlc": expected,
                    "observed_dlc": [],
                    "unknown_dlc": sorted(GATE_DLCS),
                    "other_mods": [],
                    "matches": False,
                    "reasons": [f"playset '{config}' does not exist in the launcher"],
                }
            )
            continue
        target_mods = [mod for mod in playset["mods"] if _is_target_mod(mod)]
        mod_enabled = any(mod["enabled"] for mod in target_mods)
        other_mods = sorted(
            (mod.get("display_name") or mod.get("name") or "?")
            for mod in playset["mods"]
            if mod["enabled"] and not _is_target_mod(mod)
        )
        observed = [dlc for dlc in GATE_DLCS if playset["dlc"].get(dlc) is True]
        unknown = [dlc for dlc in GATE_DLCS if dlc not in playset["dlc"]]
        reasons = []
        if not mod_enabled:
            reasons.append("The Yongchang World is not enabled in this playset")
        if unknown:
            reasons.append("launcher has not recorded: " + ", ".join(unknown))
        if sorted(observed) != sorted(expected):
            reasons.append(f"DLC set is {sorted(observed)}, expected {sorted(expected)}")
        if other_mods:
            reasons.append("other enabled mods would contaminate the run: " + ", ".join(other_mods))
        report.append(
            {
                "config": config,
                "playset": playset["playset"],
                "found": True,
                "mod_enabled": mod_enabled,
                "expected_dlc": expected,
                "observed_dlc": observed,
                "unknown_dlc": unknown,
                "other_mods": other_mods,
                "matches": not reasons,
                "reasons": reasons,
            }
        )
    return report


def _format_table(report: list[dict], active: str | None) -> str:
    header = f"{'config':<10}{'playset':<20}{'mod':<6}{'observed DLC':<34}match"
    lines = [header, "-" * len(header)]
    for row in report:
        observed = ",".join(row["observed_dlc"]) or "-"
        lines.append(
            f"{row['config']:<10}"
            f"{str(row['playset'] or '-'):<20}"
            f"{('yes' if row['mod_enabled'] else 'no'):<6}"
            f"{observed:<34}"
            f"{'yes' if row['matches'] else 'no'}"
        )
    lines.append("")
    lines.append(f"active playset: {active or 'unknown'}")
    for row in report:
        for reason in row["reasons"]:
            lines.append(f"  {row['config']}: {reason}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-data-dir", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, help="write the report as JSON evidence")
    args = parser.parse_args()
    db_path = args.user_data_dir / DATABASE_NAME
    try:
        playsets = load_playsets(db_path)
    except (PlaysetError, sqlite3.Error) as error:
        print(error)
        return 1
    report = evaluate(playsets)
    active = next((playset["playset"] for playset in playsets if playset["is_active"]), None)
    payload = {
        "database": str(db_path),
        "active_playset": active,
        "playsets": [playset["playset"] for playset in playsets],
        "configs": report,
        "all_match": all(row["matches"] for row in report),
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote playset evidence: {args.output}")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_format_table(report, active))
    return 0 if payload["all_match"] else 1


if __name__ == "__main__":
    sys.exit(main())
