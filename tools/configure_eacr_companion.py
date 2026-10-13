#!/usr/bin/env python3
"""Register EACR in the Victoria 3 launcher and enable it alongside Yongchang World."""
from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_METADATA_ID = "xyz.1230james.east_asian_clothes_redux"
EXPECTED_VERSION = "1.0.4"
YONGCHANG_NAME = "yongchang_world"


def columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}


def validate_schema(db: sqlite3.Connection) -> None:
    required = {
        "mods": {"id", "name", "displayName", "version", "requiredVersion", "dirPath", "status", "source", "metadataId", "metadataVersion", "isMetadataApplied", "metadataStatus", "metadataGameId"},
        "playsets": {"id", "name", "isRemoved"},
        "playsets_mods": {"playsetId", "modId", "enabled", "position"},
    }
    for table, expected in required.items():
        actual = columns(db, table)
        if not expected <= actual:
            raise RuntimeError(f"Unsupported launcher schema: {table} missing {sorted(expected - actual)}")


def configure(db_path: Path, mod_path: Path, metadata_path: Path, backup_dir: Path) -> dict:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("id") != EXPECTED_METADATA_ID or metadata.get("version") != EXPECTED_VERSION or metadata.get("game_id") != "victoria3":
        raise RuntimeError("EACR metadata does not match the pinned 1.0.4 Victoria 3 mod")
    if not mod_path.exists():
        raise RuntimeError(f"Mod junction does not exist: {mod_path}")
    if not db_path.is_file():
        raise RuntimeError(f"Launcher database does not exist: {db_path}")

    db = sqlite3.connect(db_path, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        validate_schema(db)
        # A consistent SQLite backup is made before any write transaction.
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"launcher-v2-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.sqlite"
        backup = sqlite3.connect(backup_path)
        try:
            db.backup(backup)
        finally:
            backup.close()

        db.execute("BEGIN IMMEDIATE")
        candidates = db.execute(
            "SELECT * FROM mods WHERE metadataId=? OR dirPath=?",
            (EXPECTED_METADATA_ID, str(mod_path)),
        ).fetchall()
        if len(candidates) > 1:
            raise RuntimeError("Multiple launcher mods match EACR metadata/path; refusing ambiguous update")
        if candidates:
            mod = candidates[0]
            if mod["metadataId"] not in (None, EXPECTED_METADATA_ID) or mod["dirPath"] not in (None, str(mod_path)):
                raise RuntimeError("Existing launcher mod row has conflicting identity/path")
            mod_id = mod["id"]
            # Bring the reused local entry into the same known-good launcher state.
            db.execute(
                "UPDATE mods SET name=?,displayName=?,version=?,requiredVersion=?,dirPath=?,status='ready_to_play',source='local',metadataId=?,metadataVersion=?,isMetadataApplied=1,metadataStatus='applied',metadataGameId='victoria3' WHERE id=?",
                ("east_asian_clothes_redux", "East Asian Clothes Redux", EXPECTED_VERSION, "1.13.*", str(mod_path), EXPECTED_METADATA_ID, EXPECTED_VERSION, mod_id),
            )
        else:
            mod_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO mods (id,name,displayName,version,requiredVersion,dirPath,status,source,metadataId,metadataVersion,isMetadataApplied,metadataStatus,metadataGameId) VALUES (?,?,?,?,?,?,'ready_to_play','local',?,?,1,'applied','victoria3')",
                (mod_id, "east_asian_clothes_redux", "East Asian Clothes Redux", EXPECTED_VERSION, "1.13.*", str(mod_path), EXPECTED_METADATA_ID, EXPECTED_VERSION),
            )

        # A Yongchang World playset is one with that mod enabled. Do not touch other playsets.
        target_playsets = [r[0] for r in db.execute(
            "SELECT DISTINCT p.id FROM playsets p JOIN playsets_mods pm ON pm.playsetId=p.id JOIN mods m ON m.id=pm.modId WHERE m.name=? AND pm.enabled=1 AND p.isRemoved=0",
            (YONGCHANG_NAME,),
        )]
        if not target_playsets:
            raise RuntimeError("No playset has Yongchang World enabled; no playset changes made")
        for playset_id in target_playsets:
            existing = db.execute("SELECT enabled FROM playsets_mods WHERE playsetId=? AND modId=?", (playset_id, mod_id)).fetchone()
            if existing:
                db.execute("UPDATE playsets_mods SET enabled=1 WHERE playsetId=? AND modId=?", (playset_id, mod_id))
            else:
                max_position = db.execute("SELECT COALESCE(MAX(position),-1) FROM playsets_mods WHERE playsetId=?", (playset_id,)).fetchone()[0]
                db.execute("INSERT INTO playsets_mods (playsetId,modId,enabled,position) VALUES (?,?,1,?)", (playset_id, mod_id, max_position + 1))

        db.commit()
        # Read back the identity and only the intended playset links.
        row = db.execute("SELECT * FROM mods WHERE id=?", (mod_id,)).fetchone()
        enabled = db.execute("SELECT playsetId,enabled,position FROM playsets_mods WHERE modId=? AND enabled=1 ORDER BY playsetId", (mod_id,)).fetchall()
        if not row or row["metadataId"] != EXPECTED_METADATA_ID or row["dirPath"] != str(mod_path):
            raise RuntimeError("Launcher mod readback failed")
        enabled_ids = {r["playsetId"] for r in enabled}
        if not set(target_playsets) <= enabled_ids:
            raise RuntimeError("Launcher playset-link readback failed")
        return {"backup": str(backup_path), "mod_id": mod_id, "target_playsets": target_playsets, "enabled_links": [dict(r) for r in enabled]}
    except Exception:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-data-dir", required=True, type=Path, help="Paradox Launcher user data directory")
    parser.add_argument("--mod-path", type=Path)
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    args = parser.parse_args()
    source_path = args.repository_root / "refs" / "eacr-companion"
    mod_path = args.mod_path or (args.user_data_dir / "mod" / "east_asian_clothes_redux")
    if not mod_path.exists() or not source_path.exists() or not mod_path.samefile(source_path):
        raise RuntimeError(f"Launcher mod path must resolve to the pinned source: {mod_path} -> {source_path}")
    result = configure(
        args.user_data_dir / "launcher-v2.sqlite",
        mod_path,
        source_path / ".metadata" / "metadata.json",
        args.repository_root / "artifacts" / "launcher-backup",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
