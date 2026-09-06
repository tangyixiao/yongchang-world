import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
BASELINE_FILE = ROOT / "data/baseline/vic3-1.13.11.json"
OVERRIDES_FILE = ROOT / "data/scenario/ownership_overrides.json"
STATE_FILE = ROOT / "yongchang_world/common/history/states/00_states.txt"
BUILDER = ROOT / "tools/build_state_history.py"

HAN_CORE_STATES = {
    "STATE_BEIJING",
    "STATE_ZHILI",
    "STATE_SHANXI",
    "STATE_SHANDONG",
    "STATE_HENAN",
    "STATE_XIAN",
    "STATE_NINGXIA",
    "STATE_GANSU",
    "STATE_SICHUAN",
    "STATE_CHONGQING",
    "STATE_GUIZHOU",
    "STATE_YUNNAN",
    "STATE_GUANGXI",
    "STATE_GUANGDONG",
    "STATE_SHAOZHOU",
    "STATE_FUJIAN",
    "STATE_ZHEJIANG",
    "STATE_JIANGXI",
    "STATE_HUNAN",
    "STATE_EASTERN_HUBEI",
    "STATE_WESTERN_HUBEI",
    "STATE_NORTHERN_ANHUI",
    "STATE_SOUTHERN_ANHUI",
    "STATE_JIANGSU",
    "STATE_NANJING",
    "STATE_SUZHOU",
}


class StateHistoryGenerationTest(unittest.TestCase):
    def setUp(self):
        self.baseline = json.loads(BASELINE_FILE.read_text("utf-8"))

    def test_authority_file_exists_and_has_unique_province_owners(self):
        overrides = json.loads(OVERRIDES_FILE.read_text("utf-8"))
        self.assertEqual(overrides["version"], "1.13.11")
        state_names = [row["state"] for row in overrides["states"]]
        self.assertEqual(len(state_names), len(set(state_names)))
        owners = {}
        for row in overrides["states"]:
            self.assertIn(row["state"], self.baseline["state_regions"])
            for group in row["groups"]:
                self.assertNotIn(group["owner"], {"AIN", "ALK"})
                for province in group["owned_provinces"]:
                    self.assertNotIn(province, owners, province)
                    owners[province] = group["owner"]

    def test_each_override_covers_vanilla_state_exactly(self):
        overrides = json.loads(OVERRIDES_FILE.read_text("utf-8"))
        for row in overrides["states"]:
            provinces = [
                province
                for group in row["groups"]
                for province in group["owned_provinces"]
            ]
            self.assertEqual(len(provinces), len(set(provinces)), row["state"])
            self.assertEqual(
                set(provinces),
                set(self.baseline["state_regions"][row["state"]]),
                row["state"],
            )

    def test_regional_ledgers_no_longer_duplicate_owned_provinces(self):
        for name in (
            "core_states",
            "northeast_states",
            "inner_asia_states",
            "southwest_states",
            "ocean_states",
        ):
            data = json.loads((ROOT / f"data/scenario/{name}.json").read_text("utf-8"))
            serialized = json.dumps(data, ensure_ascii=False)
            self.assertNotIn('"owned_provinces"', serialized, name)

    def test_generated_state_history_is_deterministic_and_matches_shipped_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "00_states.txt"
            result = subprocess.run(
                [
                    sys.executable,
                    str(BUILDER),
                    "--game-root",
                    "E:/SteamLibrary/steamapps/common/Victoria 3/game",
                    "--baseline",
                    str(BASELINE_FILE),
                    "--overrides",
                    str(OVERRIDES_FILE),
                    "--template",
                    str(STATE_FILE),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(output.read_bytes(), STATE_FILE.read_bytes())

    def test_han_core_has_no_chi_ownership_after_generation(self):
        text = STATE_FILE.read_text("utf-8")
        for state in HAN_CORE_STATES:
            start = text.find(f"s:{state} = {{")
            self.assertGreaterEqual(start, 0, state)
            end = text.find("\ns:", start + 1)
            block = text[start:] if end == -1 else text[start:end]
            self.assertNotIn("country = c:CHI", block, state)


if __name__ == "__main__":
    unittest.main()
