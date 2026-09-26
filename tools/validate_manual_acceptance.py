"""Validate the human acceptance log without turning pending evidence into a pass."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


STATUS_VALUES = {"pending", "verified", "failed"}
BASIC_INFO_FIELDS = (
    "验收人",
    "开始时间",
    "游戏版本",
    "Build ID",
    "Mod 版本/工作树",
    "用户数据目录",
)
BASIC_INFO_FIXED_VALUES = {
    "游戏版本": "1.13.11 (Matcha)",
    "Build ID": "24799966",
}
TABLE_HEADERS = {
    "basic_info": ["项目", "记录"],
    "playset": ["配置", "预期 DLC", "实际 DLC", "Mod 挂载", "版本匹配", "证据路径", "状态"],
    "countries": ["国家", "运行时 TAG", "进入 1836", "Journal/事件核对", "附加动作", "证据路径", "状态"],
    "scripted_tests": ["套件", "战局配置/种子", "游戏日期", "PASS 结果", "输出路径", "状态"],
    "observation": ["配置", "种子", "run 目录", "checkpoints.json", "异常分类", "状态"],
}
TABLE_SPECS = {
    "basic_info": ("项目", "记录", 6),
    "playset": ("配置", "预期 DLC", 5),
    "countries": ("国家", "运行时 TAG", 10),
    "scripted_tests": ("套件", "战局配置/种子", 2),
    "observation": ("配置", "种子", 15),
}
PATH_HEADER_MARKERS = ("证据路径", "输出路径", "run 目录", "checkpoints.json")


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(line: str) -> bool:
    cells = _cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _parse_tables(text: str) -> list[tuple[list[str], list[tuple[int, list[str]]]]]:
    lines = text.splitlines()
    tables: list[tuple[list[str], list[tuple[int, list[str]]]]] = []
    index = 0
    while index + 1 < len(lines):
        if "|" not in lines[index] or "|" not in lines[index + 1] or not _is_separator(lines[index + 1]):
            index += 1
            continue
        headers = _cells(lines[index])
        rows: list[tuple[int, list[str]]] = []
        index += 2
        while index < len(lines) and "|" in lines[index] and lines[index].strip():
            rows.append((index + 1, _cells(lines[index])))
            index += 1
        tables.append((headers, rows))
    return tables


def _classify(headers: list[str]) -> str | None:
    if len(headers) >= 2 and headers[0] == "配置" and headers[1] == "种子":
        return "observation"
    for name, (first, second, _count) in TABLE_SPECS.items():
        if headers[:2] == [first, second]:
            return name
    return None


def _resolve_path(log_path: Path, value: str) -> Path:
    cleaned = value.strip().strip("`")
    candidate = Path(cleaned)
    if candidate.is_absolute():
        return candidate
    for base in (Path.cwd(), log_path.parent, log_path.parent.parent):
        resolved = base / candidate
        if resolved.exists():
            return resolved
    return Path.cwd() / candidate


def load_playset_evidence(path: Path) -> tuple[dict[str, dict], list[str]]:
    """Load an `inspect_playsets.py --output` report keyed by configuration."""

    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, [f"cannot read playset evidence: {error}"]
    if not isinstance(data, dict) or not isinstance(data.get("configs"), list):
        return {}, [f"{path}: playset evidence must contain a configs list"]
    entries: dict[str, dict] = {}
    for entry in data["configs"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("config"), str):
            return {}, [f"{path}: every playset evidence entry needs a config name"]
        entries[entry["config"]] = entry
    return entries, []


def validate(
    log_path: Path,
    require_complete: bool = False,
    playset_evidence_path: Path | None = None,
) -> tuple[list[str], dict[str, int]]:
    try:
        text = log_path.read_text("utf-8")
    except OSError as error:
        return [f"cannot read acceptance log: {error}"], {}

    errors: list[str] = []
    playset_evidence: dict[str, dict] = {}
    if playset_evidence_path is not None:
        playset_evidence, evidence_errors = load_playset_evidence(playset_evidence_path)
        errors.extend(evidence_errors)
    tables = _parse_tables(text)
    found: dict[str, int] = {}
    status_counts = {status: 0 for status in STATUS_VALUES}
    # Per-table verified counts let callers (acceptance_preflight) judge each
    # gate on its own rows instead of on a single global total.
    verified_by_table: dict[str, int] = {name: 0 for name in TABLE_SPECS if name != "basic_info"}
    for headers, rows in tables:
        name = _classify(headers)
        if name is None:
            continue
        if name in found:
            errors.append(f"duplicate {name} table")
            continue
        found[name] = len(rows)
        expected_count = TABLE_SPECS[name][2]
        if len(rows) != expected_count:
            errors.append(f"{name} table must contain {expected_count} rows, got {len(rows)}")
        if headers != TABLE_HEADERS[name]:
            errors.append(f"{name} columns must be: " + " | ".join(TABLE_HEADERS[name]))
        if name == "basic_info":
            field_names = [row[1][0] for row in rows if row[1]]
            if field_names != list(BASIC_INFO_FIELDS):
                errors.append(
                    "basic_info fields must be: " + ", ".join(BASIC_INFO_FIELDS)
                )
            for line_number, row in rows:
                if len(row) != len(headers):
                    errors.append(f"line {line_number}: basic_info row has {len(row)} columns, expected {len(headers)}")
                    continue
                value = row[1].strip()
                if value.lower() in {"", "pending"}:
                    status_counts["pending"] += 1
                    if require_complete:
                        errors.append(f"line {line_number}: basic info field {row[0]!r} is pending")
                    continue
                if require_complete and row[0] in BASIC_INFO_FIXED_VALUES:
                    normalized = value.strip("`").strip()
                    expected = BASIC_INFO_FIXED_VALUES[row[0]]
                    if normalized != expected:
                        errors.append(
                            f"line {line_number}: basic info {row[0]} must be {expected!r}"
                        )
                if require_complete and row[0] == "用户数据目录":
                    resolved_directory = _resolve_path(log_path, value)
                    if not resolved_directory.is_dir():
                        errors.append(
                            f"line {line_number}: user data directory must be a directory: {value}"
                        )
            continue
        if headers != TABLE_HEADERS[name]:
            continue
        path_indices = [
            index
            for index, header in enumerate(headers[:-1])
            if any(marker in header for marker in PATH_HEADER_MARKERS)
        ]
        for line_number, row in rows:
            if len(row) != len(headers):
                errors.append(f"line {line_number}: {name} row has {len(row)} columns, expected {len(headers)}")
                continue
            status = row[-1].strip().lower()
            if status not in STATUS_VALUES:
                errors.append(f"line {line_number}: unknown status {row[-1]!r}")
                continue
            status_counts[status] += 1
            if status == "verified":
                verified_by_table[name] += 1
            if not require_complete:
                continue
            if status != "verified":
                errors.append(f"line {line_number}: status is {status}, require-complete needs verified")
                continue
            pending_fields = [
                headers[index]
                for index, value in enumerate(row[:-1])
                if value.strip().lower() == "pending"
            ]
            if pending_fields:
                errors.append(
                    f"line {line_number}: verified row has pending field(s): {', '.join(pending_fields)}"
                )
            if not path_indices:
                errors.append(f"line {line_number}: verified row has no evidence path column")
                continue
            if name == "playset" and playset_evidence_path is not None:
                config = row[0].strip()
                entry = playset_evidence.get(config)
                if entry is None:
                    errors.append(
                        f"line {line_number}: playset evidence has no entry for config {config!r}"
                    )
                elif not entry.get("matches"):
                    reasons = entry.get("reasons")
                    detail = "; ".join(str(reason) for reason in reasons) if isinstance(reasons, list) else ""
                    errors.append(
                        f"line {line_number}: playset evidence does not confirm config {config!r}"
                        + (f": {detail}" if detail else "")
                    )
                cited = {
                    _resolve_path(log_path, candidate).resolve()
                    for path_index in path_indices
                    for candidate in re.split(r"\s*;\s*", row[path_index].strip())
                    if candidate
                }
                if playset_evidence_path.resolve() not in cited:
                    errors.append(
                        f"line {line_number}: playset row for {config!r} must cite the supplied "
                        f"playset evidence file"
                    )
            for path_index in path_indices:
                value = row[path_index].strip()
                if not value or value.lower() == "pending":
                    errors.append(f"line {line_number}: verified row has pending evidence path")
                    continue
                for path_value in re.split(r"\s*;\s*", value):
                    resolved_path = _resolve_path(log_path, path_value)
                    if not resolved_path.exists():
                        errors.append(f"line {line_number}: evidence path does not exist: {path_value}")
                    elif headers[path_index] == "run 目录" and not resolved_path.is_dir():
                        errors.append(f"line {line_number}: run directory must be a directory: {path_value}")
                    elif headers[path_index] != "run 目录" and not resolved_path.is_file():
                        errors.append(f"line {line_number}: evidence path must be a file: {path_value}")

    for name, (_first, _second, expected_count) in TABLE_SPECS.items():
        if name not in found:
            errors.append(f"missing {name} table")
        elif found[name] != expected_count:
            # The detailed row-count error is already emitted above; this keeps
            # the summary complete without duplicating another diagnostic.
            continue
    return errors, {
        **status_counts,
        **found,
        **{f"verified_{name}": count for name, count in verified_by_table.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument(
        "--playset-evidence",
        type=Path,
        help="JSON written by tools/inspect_playsets.py --output; cross-checks the playset table",
    )
    args = parser.parse_args()
    errors, counts = validate(args.log, args.require_complete, args.playset_evidence)
    if counts:
        summary = " ".join(f"{key}={counts[key]}" for key in ("basic_info", "playset", "countries", "scripted_tests", "observation", "verified", "pending", "failed"))
        print(f"tables/statuses: {summary}")
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Manual acceptance log structure is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
