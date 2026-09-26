import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from tools.acceptance_preflight import build_report


ROOT = pathlib.Path(__file__).parents[1]
TOOL = ROOT / "tools/acceptance_preflight.py"
CONFIGS = ("none", "sphere", "charters", "wave", "all")
SEEDS = (11, 23, 47)
COUNTRIES = ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG")
GATE_DLCS = ("dlc010_ep1", "dlc013_mp1", "dlc018_ep2")
PLAYSET_DLC = {
    "none": {},
    "sphere": {"dlc010_ep1": True, "dlc013_mp1": False, "dlc018_ep2": False},
    "charters": {"dlc013_mp1": True, "dlc010_ep1": False, "dlc018_ep2": False},
    "wave": {"dlc018_ep2": True, "dlc010_ep1": False, "dlc013_mp1": False},
    "all": {dlc: True for dlc in GATE_DLCS},
}
EXPECTED_DLC = {
    "none": (),
    "sphere": ("dlc010_ep1",),
    "charters": ("dlc013_mp1",),
    "wave": ("dlc018_ep2",),
    "all": GATE_DLCS,
}

SCHEMA = """
CREATE TABLE playsets (id TEXT, name TEXT, isActive INTEGER, isRemoved INTEGER);
CREATE TABLE mods (id TEXT, name TEXT, displayName TEXT, dirPath TEXT);
CREATE TABLE playsets_mods (playsetId TEXT, modId TEXT, enabled INTEGER, position INTEGER);
CREATE TABLE playsets_dlcs (playsetId TEXT, dlcId TEXT, enabled INTEGER);
"""


def build_launcher(path: pathlib.Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA)
        for index, config in enumerate(CONFIGS):
            playset_id = f"playset-{index}"
            connection.execute("INSERT INTO playsets VALUES (?, ?, 1, 0)", (playset_id, config))
            connection.execute("INSERT INTO mods VALUES (?, 'yongchang_world', 'The Yongchang World', 'D:/mods/yongchang_world')", (f"mod-{index}",))
            connection.execute("INSERT INTO playsets_mods VALUES (?, ?, 1, 1)", (playset_id, f"mod-{index}"))
            for dlc in GATE_DLCS:
                connection.execute(
                    "INSERT INTO playsets_dlcs VALUES (?, ?, ?)",
                    (playset_id, dlc, 1 if PLAYSET_DLC[config].get(dlc) else 0),
                )
        connection.commit()
    finally:
        connection.close()


def write_run(root: pathlib.Path, config: str, seed: int) -> None:
    run_root = root / "artifacts/observe" / config / str(seed)
    run_root.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "year": year,
            "country": country,
            "rank": "major_power",
            "population": 100000,
            "market": country,
            "wars": 0,
            "subjects": 0,
            "error_count": 0,
        }
        for year in (1846, 1866, 1900)
        for country in COUNTRIES
    ]
    (run_root / "checkpoints.json").write_text(json.dumps(rows), encoding="utf-8")
    (run_root / "run.json").write_text(
        json.dumps(
            {
                "config": config,
                "run_id": f"run-{seed}",
                "requested_seed": seed,
                "observed_seed": seed,
                "status": "observed_to_checkpoint",
                "game_version": "1.13.11 (Matcha)",
                "mod_mount": "mounted",
                "version_match_evidence": ["successfully matched game version 1.13.11"],
                "expected_mounted_dlc": EXPECTED_DLC[config],
                "observed_mounted_dlc": EXPECTED_DLC[config],
                "dlc_state_matches_config": "yes",
                "evidence": {"campaign": "fixture campaign", "observed_seed": seed},
            }
        ),
        encoding="utf-8",
    )


def write_log(root: pathlib.Path, user_data: pathlib.Path) -> pathlib.Path:
    path = root / "docs/release/manual-acceptance-log.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    evidence = root / "artifacts/observe/none/11/run.json"
    playsets = "\n".join(
        f"| {config} | 无 | observed | mounted | matched | {evidence} | verified |" for config in CONFIGS
    )
    countries = "\n".join(
        f"| {country} | {country} | entered | checked | — | {evidence} | verified |" for country in COUNTRIES
    )
    suites = "\n".join(
        f"| suite-{index} | none/11 | 1836.1.1 | PASS | {evidence} | verified |" for index in range(2)
    )
    observations = "\n".join(
        f"| {config} | {seed} | {root / 'artifacts/observe' / config / str(seed)} | "
        f"{root / 'artifacts/observe' / config / str(seed) / 'checkpoints.json'} | none | verified |"
        for config in CONFIGS
        for seed in SEEDS
    )
    path.write_text(
        "\n".join(
            [
                "| 项目 | 记录 |",
                "| --- | --- |",
                "| 验收人 | tester |",
                "| 开始时间 | 2026-09-13 |",
                "| 游戏版本 | 1.13.11 (Matcha) |",
                "| Build ID | 24799966 |",
                "| Mod 版本/工作树 | test |",
                f"| 用户数据目录 | {user_data} |",
                "",
                "| 配置 | 预期 DLC | 实际 DLC | Mod 挂载 | 版本匹配 | 证据路径 | 状态 |",
                "| --- | --- | --- | --- | --- | --- | --- |",
                playsets,
                "",
                "| 国家 | 运行时 TAG | 进入 1836 | Journal/事件核对 | 附加动作 | 证据路径 | 状态 |",
                "| --- | --- | --- | --- | --- | --- | --- |",
                countries,
                "",
                "| 套件 | 战局配置/种子 | 游戏日期 | PASS 结果 | 输出路径 | 状态 |",
                "| --- | --- | --- | --- | --- | --- |",
                suites,
                "",
                "| 配置 | 种子 | run 目录 | checkpoints.json | 异常分类 | 状态 |",
                "| --- | --- | --- | --- | --- | --- |",
                observations,
            ]
        ),
        encoding="utf-8",
    )
    return path


def build_complete_repo(base: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    root = base / "repo"
    (root / "yongchang_world").mkdir(parents=True)
    game = base / "game"
    (game / "common/scripted_triggers").mkdir(parents=True)
    (game / "common/scripted_triggers/vanilla.txt").write_text(
        "vanilla_only_trigger = {\n\talways = yes\n}\n", encoding="utf-8"
    )
    (root / "data/scenario").mkdir(parents=True)
    (root / "data/content").mkdir(parents=True)
    (root / "data/baseline").mkdir(parents=True)
    (root / "data/scenario/tag_registry.json").write_text('{"countries": [{"tag": "SHU"}]}', encoding="utf-8")
    (root / "data/baseline/vic3-1.13.11.json").write_text('{"country_tags": ["SHU"]}', encoding="utf-8")
    (root / "data/content/reachability_allowlist.json").write_text(
        '{"unused_scripted_helpers": {}}', encoding="utf-8"
    )
    user_data = base / "user-data"
    user_data.mkdir()
    build_launcher(user_data / "launcher-v2.sqlite")
    for config in CONFIGS:
        for seed in SEEDS:
            write_run(root, config, seed)
    log_path = write_log(root, user_data)
    return root, user_data, log_path, game


class AcceptancePreflightTest(unittest.TestCase):
    def test_empty_repository_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "empty"
            root.mkdir()
            report = build_report(root)
        self.assertFalse(report["ready"])
        self.assertIn("ywc_check", report["blocked"])
        self.assertTrue(report["skipped"])

    def test_skipped_checks_never_count_as_ready(self):
        """A missing launcher database must not silently pass Gate 1."""

        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            root, _user_data, log_path, game = build_complete_repo(base)
            report = build_report(root, observe_root=root / "artifacts/observe", log_path=log_path)
        self.assertFalse(report["ready"])
        self.assertEqual(report["statuses"]["playsets"], "skipped")

    def test_complete_repository_is_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            root, user_data, log_path, game = build_complete_repo(base)
            report = build_report(
                root,
                user_data_dir=user_data,
                observe_root=root / "artifacts/observe",
                log_path=log_path,
                game_root=game,
            )
        statuses = report["statuses"]
        self.assertEqual(statuses["playsets"], "ok", report["entries"])
        self.assertEqual(statuses["countries_1836"], "ok")
        self.assertEqual(statuses["scripted_tests"], "ok")
        self.assertEqual(statuses["observation_matrix"], "ok")
        self.assertTrue(report["ready"], report["entries"])

    def test_unconfirmed_playset_blocks_gate_one(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            root, user_data, log_path, game = build_complete_repo(base)
            connection = sqlite3.connect(user_data / "launcher-v2.sqlite")
            try:
                connection.execute("UPDATE playsets_dlcs SET enabled = 1")
                connection.commit()
            finally:
                connection.close()
            report = build_report(
                root,
                user_data_dir=user_data,
                observe_root=root / "artifacts/observe",
                log_path=log_path,
                game_root=game,
            )
        self.assertFalse(report["ready"])
        self.assertEqual(report["statuses"]["playsets"], "incomplete")

    def test_cli_json_output_reports_statuses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory) / "empty"
            root.mkdir()
            result = subprocess.run(
                [sys.executable, str(TOOL), "--root", str(root), "--json"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertFalse(report["ready"])
        self.assertIn("ywc_check", report["statuses"])


if __name__ == "__main__":
    unittest.main()
