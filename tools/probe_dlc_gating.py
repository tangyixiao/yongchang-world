"""Probe whether the game honours content_load.json's disabledDLC without the launcher.

Gate 1 and the DLC dimension of Gate 4 are defined by the launcher's playsets,
so this answers a question that decides whether they can be produced at all
while the launcher is unavailable: does a directly launched victoria3.exe mount
only the DLC that content_load.json leaves enabled?

The run is hidden (no window, no injected input) and writes into an isolated
``-userdir``, so it never touches the user's session or saves.  Evidence is read
back from the run's own ``debug.log``, which lists the DLC the engine found and
every content directory it mounted.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

GAME_ROOT = pathlib.Path(r"E:/SteamLibrary/steamapps/common/Victoria 3")
EXE = GAME_ROOT / "binaries/victoria3.exe"

# The three DLC that separate the five observation configurations.
GATE_DLC = {
    "dlc010_ep1": "Sphere of Influence",
    "dlc013_mp1": "Charters of Commerce",
    "dlc018_ep2": "The Great Wave",
}
CONFIG_DISABLED = {
    "none": tuple(GATE_DLC),
    "sphere": ("dlc013_mp1", "dlc018_ep2"),
    "charters": ("dlc010_ep1", "dlc018_ep2"),
    "wave": ("dlc010_ep1", "dlc013_mp1"),
    "all": (),
}

CREATE_NO_WINDOW = 0x08000000


def write_content_load(userdir: pathlib.Path, mod_root: pathlib.Path, disabled: tuple[str, ...]) -> pathlib.Path:
    """BOM-free content_load.json; the game silently rejects a byte-order mark."""

    payload = {
        "enabledMods": [{"path": str(mod_root)}],
        "disabledDLC": list(disabled),
        "enabledUGC": [],
    }
    path = userdir / "content_load.json"
    userdir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    if path.read_bytes()[:3] == b"\xef\xbb\xbf":
        raise SystemExit(f"{path}: BOM present, the game would reject it")
    return path


def parse_log(log_path: pathlib.Path) -> dict:
    """Read the DLC inventory and mounted content directories out of debug.log."""

    if not log_path.is_file():
        return {"found": False}
    text = log_path.read_text("utf-8", errors="replace")
    declared: dict[str, str] = {}
    block = re.search(r"DLC:\n((?:[^\n]+\n)+)", text)
    if block:
        for line in block.group(1).splitlines():
            if "|" in line:
                name, _, dlc_path = line.partition("|")
                declared[pathlib.PurePosixPath(dlc_path).stem] = name.strip()
    mounted = set(re.findall(r"Mounted Data: .*/game/dlc/([A-Za-z0-9_]+)", text))
    return {
        "found": True,
        "declared": declared,
        "mounted": mounted,
        "gate_dlc_mounted": sorted(name for name in GATE_DLC if name in mounted),
        "missing_appid": text.count("Missing paradoxAppId for dlc/mod"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", choices=sorted(CONFIG_DISABLED), required=True)
    parser.add_argument("--mod-root", type=pathlib.Path, default=pathlib.Path("yongchang_world"))
    parser.add_argument("--seconds", type=int, default=75)
    parser.add_argument("--userdir", type=pathlib.Path)
    args = parser.parse_args()

    userdir = args.userdir or pathlib.Path("artifacts/observe/_dlcprobe") / args.config
    disabled = CONFIG_DISABLED[args.config]
    content_load = write_content_load(userdir, args.mod_root.resolve(), disabled)
    print(f"config={args.config} disabledDLC={list(disabled)}")
    print(f"userdir={userdir}")
    print(f"content_load={content_load}")

    argv = [
        str(EXE),
        "-debug_mode",
        "-no_notifications",
        "-userdir",
        str(userdir.resolve()),
    ]
    print("argv:", " ".join(argv))
    process = subprocess.Popen(
        argv,
        cwd=str(GAME_ROOT),
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"launched pid={process.pid} (hidden, no input injected)")
    started = time.monotonic()
    try:
        time.sleep(args.seconds)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
            print(f"terminated pid={process.pid}")
        else:
            print(f"exited on its own pid={process.pid} code={process.returncode}")
    print(f"ran for {time.monotonic() - started:.1f}s")

    report = parse_log(userdir / "logs/debug.log")
    if not report["found"]:
        print("no debug.log produced")
        return 1
    print(f"\n引擎声明的 DLC 数量: {len(report['declared'])}")
    print(f"实际挂载的 dlc 目录: {sorted(report['mounted'])}")
    print(f"三个门槛 DLC 中实际挂载的: {report['gate_dlc_mounted']}")
    if report["missing_appid"]:
        print(f"'Missing paradoxAppId for dlc/mod' 警告: {report['missing_appid']} 次")

    # The 2026-09-21 finding: without the launcher, the engine mounts every DLC
    # in ``game/dlc`` regardless of ``disabledDLC``.  A per-config comparison
    # cannot show that, because the ``all`` config trivially matches.  The
    # decisive check is whether *any* config with a non-empty ``disabledDLC``
    # still mounts everything it asked to disable.
    expected = sorted(name for name in GATE_DLC if name not in disabled)
    matches_expectation = report["gate_dlc_mounted"] == expected

    if disabled and report["gate_dlc_mounted"] == sorted(GATE_DLC):
        print("结论: disabledDLC 被完全忽略 —— 请求禁用 "
              f"{len(disabled)} 个，实际仍挂载全部 {len(GATE_DLC)} 个门槛 DLC。")
        print("      门槛一与门槛四的 DLC 维度只能在 Paradox 启动器的 Playset 里产出。")
        return 1
    print(f"期望挂载 {expected} → {'符合' if matches_expectation else '不符合'}")
    return 0 if matches_expectation else 1


if __name__ == "__main__":
    sys.exit(main())
