import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]


class MetadataTest(unittest.TestCase):
    def test_metadata_targets_113(self):
        data = json.loads(
            (ROOT / "yongchang_world/.metadata/metadata.json").read_text("utf-8")
        )
        self.assertEqual(data["name"], "The Yongchang World")
        self.assertEqual(data["game_id"], "victoria3")
        self.assertEqual(data["version"], "0.1.0")
        self.assertEqual(data["supported_game_version"], "1.13.*")
        self.assertEqual(data["short_description"], "1836年永昌世界四国垂直切片")
        self.assertEqual(data["relationships"], [])
        self.assertEqual(
            data["tags"],
            ["Alternative History", "Map"],
        )
        self.assertTrue(data["game_custom_data"]["multiplayer_synchronized"])

    def test_descriptor_has_launcher_identity(self):
        descriptor = (ROOT / "yongchang_world/descriptor.mod").read_text("utf-8")
        self.assertIn('name="The Yongchang World"', descriptor)
        self.assertIn('version="0.1.0"', descriptor)
        self.assertIn('supported_version="1.13.*"', descriptor)

    def test_localization_files_have_utf8_bom(self):
        files = sorted((ROOT / "yongchang_world/localization").rglob("*.yml"))
        self.assertTrue(files)
        for path in files:
            self.assertTrue(
                path.read_bytes().startswith(b"\xef\xbb\xbf"),
                f"Missing UTF-8 BOM: {path}",
            )

    def test_install_script_is_idempotent_by_contract(self):
        script = (ROOT / "tools/install_dev_mod.ps1").read_text("utf-8")
        self.assertIn("New-Item -ItemType Directory -Force", script)
        self.assertIn("yongchang_world.mod", script)

    def test_install_script_writes_bom_free_descriptor_without_set_content(self):
        # Windows PowerShell 5.1 (the machine default) rejects
        # -Encoding utf8NoBOM, so the script must write BOM-free UTF-8 via
        # UTF8Encoding($false) instead of Set-Content.
        script = (ROOT / "tools/install_dev_mod.ps1").read_text("utf-8")
        self.assertNotIn("Set-Content", script)
        self.assertNotIn("-Encoding utf8NoBOM", script)
        self.assertIn("UTF8Encoding($false)", script)

    def test_install_script_uses_redirected_windows_documents(self):
        script = (ROOT / "tools/install_dev_mod.ps1").read_text("utf-8")
        self.assertIn("[Environment]::GetFolderPath('MyDocuments')", script)
        self.assertNotIn("$env:USERPROFILE 'Documents", script)


if __name__ == "__main__":
    unittest.main()
