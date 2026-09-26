import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / "tools/validate_manual_acceptance.py"
TEMPLATE = ROOT / "docs/release/manual-acceptance-log.md"
CONFIGS = ("none", "sphere", "charters", "wave", "all")


def complete_log_text(root: pathlib.Path, evidence_path: str, playset_path: str) -> str:
    """Build a fully verified log whose playset rows cite the playset evidence."""

    user_data_directory = root / "user-data"
    user_data_directory.mkdir(exist_ok=True)
    run_directory = root / "run"
    run_directory.mkdir(exist_ok=True)
    playsets = "\n".join(
        f"| {config} | 无 | observed | mounted | matched | {evidence_path}; {playset_path} | verified |"
        for config in CONFIGS
    )
    countries = "\n".join(
        f"| C{index:02d} | C{index:02d} | entered | checked | — | {evidence_path} | verified |"
        for index in range(10)
    )
    suites = "\n".join(
        f"| suite-{index} | none/11 | 1836.1.1 | PASS | {evidence_path} | verified |"
        for index in range(2)
    )
    observations = "\n".join(
        f"| {config} | 11 | {run_directory} | {evidence_path} | none | verified |"
        for config in CONFIGS
        for _ in range(3)
    )
    return "\n".join(
        [
            "| 项目 | 记录 |",
            "| --- | --- |",
            "| 验收人 | tester |",
            "| 开始时间 | 2026-09-13 |",
            "| 游戏版本 | 1.13.11 (Matcha) |",
            "| Build ID | 24799966 |",
            "| Mod 版本/工作树 | test |",
            f"| 用户数据目录 | {user_data_directory} |",
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
    )


def playset_evidence(root: pathlib.Path, matches: dict[str, bool] | None = None) -> pathlib.Path:
    matches = matches or {}
    path = root / "launcher-evidence.json"
    path.write_text(
        json.dumps(
            {
                "database": "launcher-v2.sqlite",
                "active_playset": "none",
                "playsets": list(CONFIGS),
                "configs": [
                    {
                        "config": config,
                        "matches": matches.get(config, True),
                        "reasons": [] if matches.get(config, True) else ["DLC set is [], expected ['dlc010_ep1']"],
                    }
                    for config in CONFIGS
                ],
                "all_match": all(matches.get(config, True) for config in CONFIGS),
            }
        ),
        encoding="utf-8",
    )
    return path


class ManualAcceptanceValidatorTest(unittest.TestCase):
    def run_validator(self, log_path, *extra_args):
        return subprocess.run(
            [
                "python",
                str(SCRIPT),
                "--log",
                str(log_path),
                *extra_args,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_template_is_structurally_valid_but_not_complete(self):
        structural = self.run_validator(TEMPLATE)
        self.assertEqual(structural.returncode, 0, structural.stdout + structural.stderr)
        self.assertIn("playset=5", structural.stdout)
        self.assertIn("countries=10", structural.stdout)
        self.assertIn("scripted_tests=2", structural.stdout)
        self.assertIn("observation=15", structural.stdout)
        self.assertIn("basic_info=6", structural.stdout)
        self.assertIn("pending=36", structural.stdout)

        complete = self.run_validator(TEMPLATE, "--require-complete")
        self.assertEqual(complete.returncode, 1, complete.stdout + complete.stderr)
        self.assertIn("pending", complete.stdout)

    def test_unknown_status_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = pathlib.Path(directory) / "acceptance.md"
            text = TEMPLATE.read_text("utf-8")
            text = text.replace(
                "| none | 无 | pending | pending | pending | pending | pending |",
                "| none | 无 | pending | pending | pending | pending | done |",
                1,
            )
            log_path.write_text(text, encoding="utf-8")
            result = self.run_validator(log_path)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("unknown status", result.stdout)

    def test_basic_info_requires_the_expected_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = pathlib.Path(directory) / "acceptance.md"
            text = TEMPLATE.read_text("utf-8").replace("| 验收人 | pending |", "| owner | pending |", 1)
            log_path.write_text(text, encoding="utf-8")
            result = self.run_validator(log_path)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("basic_info fields", result.stdout)

    def test_acceptance_tables_require_the_expected_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = pathlib.Path(directory) / "acceptance.md"
            text = TEMPLATE.read_text("utf-8").replace(
                "| 配置 | 预期 DLC | 实际 DLC | Mod 挂载 | 版本匹配 | 证据路径 | 状态 |",
                "| 配置 | 预期 DLC | altered | Mod 挂载 | 版本匹配 | 证据路径 | 状态 |",
                1,
            )
            log_path.write_text(text, encoding="utf-8")
            result = self.run_validator(log_path)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("playset columns", result.stdout)

    def test_require_complete_rejects_wrong_game_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = pathlib.Path(directory) / "acceptance.md"
            text = TEMPLATE.read_text("utf-8").replace(
                "| 游戏版本 | `1.13.11 (Matcha)` |",
                "| 游戏版本 | `1.13.10` |",
                1,
            )
            log_path.write_text(text, encoding="utf-8")
            result = self.run_validator(log_path, "--require-complete")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("must be", result.stdout)

    def test_require_complete_accepts_verified_rows_with_existing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            evidence = root / "evidence.txt"
            evidence.write_text("real evidence\n", encoding="utf-8")
            path = str(evidence)
            run_directory = root / "run"
            run_directory.mkdir()
            run_path = str(run_directory)
            user_data_directory = root / "user-data"
            user_data_directory.mkdir()
            playsets = "\n".join(
                f"| config-{index} | 无 | observed | mounted | matched | {path} | verified |"
                for index in range(5)
            )
            countries = "\n".join(
                f"| C{index:02d} | C{index:02d} | entered | checked | — | {path} | verified |"
                for index in range(10)
            )
            suites = "\n".join(
                f"| suite-{index} | none/11 | 1836.1.1 | PASS | {path} | verified |"
                for index in range(2)
            )
            observations = "\n".join(
                f"| config-{index} | 11 | {run_path} | {path} | none | verified |"
                for index in range(15)
            )
            log_path = root / "acceptance.md"
            log_path.write_text(
                "\n".join(
                    [
                        "| 项目 | 记录 |",
                        "| --- | --- |",
                        "| 验收人 | tester |",
                        "| 开始时间 | 2026-09-13 |",
                        "| 游戏版本 | 1.13.11 (Matcha) |",
                        "| Build ID | 24799966 |",
                        "| Mod 版本/工作树 | test |",
                        f"| 用户数据目录 | {user_data_directory} |",
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
            result = self.run_validator(log_path, "--require-complete")
            complete_text = log_path.read_text("utf-8")
            incomplete = complete_text.replace(
                f"| config-0 | 无 | observed | mounted | matched | {path} | verified |",
                f"| config-0 | 无 | pending | mounted | matched | {path} | verified |",
                1,
            )
            log_path.write_text(incomplete, encoding="utf-8")
            incomplete_result = self.run_validator(log_path, "--require-complete")
            basic_info_incomplete = complete_text.replace(
                "| 验收人 | tester |",
                "| 验收人 | pending |",
                1,
            )
            log_path.write_text(basic_info_incomplete, encoding="utf-8")
            basic_info_result = self.run_validator(log_path, "--require-complete")
            wrong_user_data = complete_text.replace(
                str(user_data_directory),
                path,
                1,
            )
            log_path.write_text(wrong_user_data, encoding="utf-8")
            wrong_user_data_result = self.run_validator(log_path, "--require-complete")
            directory_evidence = root / "evidence-directory"
            directory_evidence.mkdir()
            directory_log = complete_text.replace(
                f"| config-0 | 无 | observed | mounted | matched | {path} | verified |",
                f"| config-0 | 无 | observed | mounted | matched | {directory_evidence} | verified |",
                1,
            )
            log_path.write_text(directory_log, encoding="utf-8")
            directory_result = self.run_validator(log_path, "--require-complete")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("basic_info=6", result.stdout)
        self.assertIn("verified=32", result.stdout)
        self.assertEqual(incomplete_result.returncode, 1, incomplete_result.stdout + incomplete_result.stderr)
        self.assertIn("pending field", incomplete_result.stdout)
        self.assertEqual(basic_info_result.returncode, 1, basic_info_result.stdout + basic_info_result.stderr)
        self.assertIn("basic info", basic_info_result.stdout)
        self.assertEqual(wrong_user_data_result.returncode, 1, wrong_user_data_result.stdout + wrong_user_data_result.stderr)
        self.assertIn("user data directory must be a directory", wrong_user_data_result.stdout)
        self.assertEqual(directory_result.returncode, 1, directory_result.stdout + directory_result.stderr)
        self.assertIn("must be a file", directory_result.stdout)


class PlaysetEvidenceCrossCheckTest(unittest.TestCase):
    def run_validator(self, log_path, *extra_args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--log", str(log_path), *extra_args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_matching_evidence_and_citation_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            evidence = root / "evidence.txt"
            evidence.write_text("real evidence\n", encoding="utf-8")
            launcher = playset_evidence(root)
            log_path = root / "acceptance.md"
            log_path.write_text(
                complete_log_text(root, str(evidence), str(launcher)), encoding="utf-8"
            )
            result = self.run_validator(
                log_path, "--require-complete", "--playset-evidence", str(launcher)
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("verified=32", result.stdout)

    def test_unconfirmed_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            evidence = root / "evidence.txt"
            evidence.write_text("real evidence\n", encoding="utf-8")
            launcher = playset_evidence(root, {"sphere": False})
            log_path = root / "acceptance.md"
            log_path.write_text(
                complete_log_text(root, str(evidence), str(launcher)), encoding="utf-8"
            )
            result = self.run_validator(
                log_path, "--require-complete", "--playset-evidence", str(launcher)
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("does not confirm config 'sphere'", result.stdout)

    def test_missing_config_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            evidence = root / "evidence.txt"
            evidence.write_text("real evidence\n", encoding="utf-8")
            launcher = playset_evidence(root)
            payload = json.loads(launcher.read_text("utf-8"))
            payload["configs"] = [entry for entry in payload["configs"] if entry["config"] != "wave"]
            launcher.write_text(json.dumps(payload), encoding="utf-8")
            log_path = root / "acceptance.md"
            log_path.write_text(
                complete_log_text(root, str(evidence), str(launcher)), encoding="utf-8"
            )
            result = self.run_validator(
                log_path, "--require-complete", "--playset-evidence", str(launcher)
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no entry for config 'wave'", result.stdout)

    def test_row_must_cite_the_supplied_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            evidence = root / "evidence.txt"
            evidence.write_text("real evidence\n", encoding="utf-8")
            launcher = playset_evidence(root)
            other = root / "other-launcher-evidence.json"
            other.write_text(launcher.read_text("utf-8"), encoding="utf-8")
            log_path = root / "acceptance.md"
            text = complete_log_text(root, str(evidence), str(launcher)).replace(
                str(launcher), str(other)
            )
            log_path.write_text(text, encoding="utf-8")
            result = self.run_validator(
                log_path, "--require-complete", "--playset-evidence", str(launcher)
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("must cite the supplied playset evidence file", result.stdout)

    def test_malformed_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            evidence = root / "evidence.txt"
            evidence.write_text("real evidence\n", encoding="utf-8")
            launcher = root / "launcher-evidence.json"
            launcher.write_text(json.dumps({"playsets": []}), encoding="utf-8")
            log_path = root / "acceptance.md"
            log_path.write_text(
                complete_log_text(root, str(evidence), str(launcher)), encoding="utf-8"
            )
            result = self.run_validator(
                log_path, "--require-complete", "--playset-evidence", str(launcher)
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("must contain a configs list", result.stdout)

    def test_evidence_flag_is_ignored_without_require_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            launcher = playset_evidence(root)
            log_path = root / "acceptance.md"
            log_path.write_text(TEMPLATE.read_text("utf-8"), encoding="utf-8")
            result = self.run_validator(log_path, "--playset-evidence", str(launcher))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("pending=36", result.stdout)


if __name__ == "__main__":
    unittest.main()
