import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "configure_eacr_companion.py"
spec = importlib.util.spec_from_file_location("configure_eacr_companion", SCRIPT)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class ConfigureEacrTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db_path = self.root / "launcher-v2.sqlite"
        self.mod_path = self.root / "mod" / "east_asian_clothes_redux"
        self.mod_path.mkdir(parents=True)
        self.metadata = self.root / "metadata.json"
        self.metadata.write_text(json.dumps({"id": helper.EXPECTED_METADATA_ID, "version": "1.0.4", "game_id": "victoria3"}), encoding="utf-8")
        db = sqlite3.connect(self.db_path)
        db.executescript("""
            CREATE TABLE mods (id TEXT PRIMARY KEY, name TEXT, displayName TEXT, version TEXT, requiredVersion TEXT, dirPath TEXT, status TEXT, source TEXT, metadataId TEXT, metadataVersion TEXT, isMetadataApplied INTEGER NOT NULL DEFAULT 0, metadataStatus TEXT NOT NULL DEFAULT 'not_applied', metadataGameId TEXT);
            CREATE TABLE playsets (id TEXT PRIMARY KEY, name TEXT, isActive INTEGER NOT NULL DEFAULT 0, isRemoved INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE playsets_mods (playsetId TEXT, modId TEXT, enabled INTEGER, position INTEGER, PRIMARY KEY(playsetId,modId));
            CREATE TABLE dlc (id TEXT PRIMARY KEY, name TEXT, dirPath TEXT);
            CREATE TABLE playsets_dlcs (playsetId TEXT, dlcId TEXT, enabled INTEGER, PRIMARY KEY(playsetId,dlcId));
            INSERT INTO mods (id,name,displayName,status,source) VALUES ('ywc','yongchang_world','The Yongchang World','ready_to_play','local');
            INSERT INTO mods (id,name,displayName,status,source) VALUES ('other','other_mod','Other Mod','ready_to_play','local');
            INSERT INTO playsets (id,name,isActive,isRemoved) VALUES ('active-ywc','Yongchang World Active',1,0);
            INSERT INTO playsets (id,name,isActive,isRemoved) VALUES ('inactive-ywc','Yongchang World Inactive',0,0);
            INSERT INTO playsets (id,name,isActive,isRemoved) VALUES ('removed-ywc','Removed Yongchang World',0,1);
            INSERT INTO playsets (id,name,isActive,isRemoved) VALUES ('unrelated','Other Playset',0,0);
            INSERT INTO playsets_mods VALUES ('active-ywc','ywc',1,2);
            INSERT INTO playsets_mods VALUES ('active-ywc','other',0,3);
            INSERT INTO playsets_mods VALUES ('inactive-ywc','ywc',0,0);
            INSERT INTO playsets_mods VALUES ('removed-ywc','ywc',1,0);
            INSERT INTO playsets_mods VALUES ('unrelated','other',1,0);
            INSERT INTO dlc VALUES ('dlc1','A DLC','/fake/dlc');
            INSERT INTO playsets_dlcs VALUES ('active-ywc','dlc1',1);
        """)
        db.commit()
        db.close()

    def tearDown(self):
        self.temp.cleanup()

    def run_config(self):
        return helper.configure(self.db_path, self.mod_path, self.metadata, self.root / "backups")

    def test_appends_only_to_playsets_with_enabled_yongchang_and_is_idempotent(self):
        first = self.run_config()
        second = self.run_config()
        db = sqlite3.connect(self.db_path)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM mods WHERE metadataId=?", (helper.EXPECTED_METADATA_ID,)).fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT modId,enabled,position FROM playsets_mods WHERE playsetId='active-ywc' AND modId=?", (first["mod_id"],)).fetchone(), (first["mod_id"], 1, 4))
        self.assertIsNone(db.execute("SELECT 1 FROM playsets_mods WHERE playsetId='inactive-ywc' AND modId=?", (first["mod_id"],)).fetchone())
        self.assertIsNone(db.execute("SELECT 1 FROM playsets_mods WHERE playsetId='removed-ywc' AND modId=?", (first["mod_id"],)).fetchone())
        self.assertIsNone(db.execute("SELECT 1 FROM playsets_mods WHERE playsetId='unrelated' AND modId=?", (first["mod_id"],)).fetchone())
        self.assertEqual(db.execute("SELECT enabled FROM playsets_mods WHERE playsetId='active-ywc' AND modId='other'").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT enabled FROM playsets_dlcs WHERE playsetId='active-ywc' AND dlcId='dlc1'").fetchone()[0], 1)
        self.assertEqual(first["mod_id"], second["mod_id"])
        self.assertEqual(len(db.execute("SELECT * FROM playsets_mods WHERE playsetId='active-ywc' AND modId=?", (first["mod_id"],)).fetchall()), 1)
        db.close()

    def test_reuses_existing_eacr_link_and_enables_it_without_changing_position(self):
        db = sqlite3.connect(self.db_path)
        db.execute("INSERT INTO mods (id,name,displayName,dirPath,status,source,metadataId,metadataVersion,isMetadataApplied,metadataStatus,metadataGameId) VALUES ('existing-eacr','east_asian_clothes_redux','East Asian Clothes Redux',?,'ready_to_play','local',?,'1.0.4',1,'applied','victoria3')", (str(self.mod_path), helper.EXPECTED_METADATA_ID))
        db.execute("INSERT INTO playsets_mods VALUES ('active-ywc','existing-eacr',0,8)")
        db.execute("INSERT INTO playsets_mods VALUES ('unrelated','existing-eacr',0,5)")
        db.commit()
        db.close()

        result = self.run_config()
        db = sqlite3.connect(self.db_path)
        self.assertEqual(result["mod_id"], "existing-eacr")
        self.assertEqual(db.execute("SELECT enabled,position FROM playsets_mods WHERE playsetId='active-ywc' AND modId='existing-eacr'").fetchone(), (1, 8))
        self.assertEqual(db.execute("SELECT enabled,position FROM playsets_mods WHERE playsetId='unrelated' AND modId='existing-eacr'").fetchone(), (0, 5))
        self.assertEqual(db.execute("SELECT enabled FROM playsets_mods WHERE playsetId='active-ywc' AND modId='other'").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT enabled FROM playsets_dlcs WHERE playsetId='active-ywc' AND dlcId='dlc1'").fetchone()[0], 1)
        db.close()

    def test_no_enabled_yongchang_playset_rolls_back_new_mod_registration(self):
        db = sqlite3.connect(self.db_path)
        db.execute("UPDATE playsets_mods SET enabled=0 WHERE modId='ywc'")
        db.commit()
        db.close()

        with self.assertRaisesRegex(RuntimeError, "No playset has Yongchang World enabled"):
            self.run_config()

        db = sqlite3.connect(self.db_path)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM mods WHERE metadataId=?", (helper.EXPECTED_METADATA_ID,)).fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM playsets_mods WHERE modId IN (SELECT id FROM mods WHERE metadataId=?)", (helper.EXPECTED_METADATA_ID,)).fetchone()[0], 0)
        db.close()

    def test_missing_launcher_database_is_not_created(self):
        missing = self.root / "wrong-user-data" / "launcher-v2.sqlite"
        with self.assertRaisesRegex(RuntimeError, "Launcher database does not exist"):
            helper.configure(missing, self.mod_path, self.metadata, self.root / "backups")
        self.assertFalse(missing.exists())



if __name__ == "__main__":
    unittest.main()
