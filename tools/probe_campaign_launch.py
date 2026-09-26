"""Probe whether a command line can drop the game straight into a running campaign.

Navigating the main menu and the country picker is the least reliable part of
desktop automation, and Gate 4 needs fifteen campaigns started the same way.  If
``-continue`` (or any other argument) loads a save into a live session without a
single click, the whole matrix gets far cheaper and far more reproducible.

The probe stages a real save into an isolated ``-userdir``, launches hidden (no
window, no injected input), then judges the run from its own ``debug.log``:

* the main menu stops growing as soon as it is built (~260 lines), while a live
  campaign keeps logging every tick;
* code ``on_actions`` only fire while a game is running;
* the engine logs ``Transition ...->Game`` for a real session.

Every verdict is reported with the numbers behind it, never inferred from a
timeout alone.
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
# A save from a real 1836 session of this Mod.
DEFAULT_SAVE = pathlib.Path(
    "artifacts/observe/manual-gate23-1836-shu-01/userdata/save games/autosave.v3"
)
MOD_ROOT = pathlib.Path("yongchang_world").resolve()

CREATE_NO_WINDOW = 0x08000000
# The main menu settles at roughly this size and then stops logging.
MAIN_MENU_LINE_CEILING = 400


def stage(userdir: pathlib.Path, save: pathlib.Path) -> pathlib.Path:
    (userdir / "save games").mkdir(parents=True, exist_ok=True)
    payload = {
        "enabledMods": [{"path": str(MOD_ROOT)}],
        "disabledDLC": [],
        "enabledUGC": [],
    }
    (userdir / "content_load.json").write_text(
        json.dumps(payload, separators=(",", ":")), encoding="utf-8"
    )
    target = userdir / "save games" / save.name
    if not target.is_file():
        target.write_bytes(save.read_bytes())
    return target


def verdict(userdir: pathlib.Path) -> dict:
    log = userdir / "logs/debug.log"
    if not log.is_file():
        return {"entered_campaign": False, "reason": "no debug.log"}
    text = log.read_text("utf-8", errors="replace")
    lines = text.count("\n")
    on_action_hits = len(re.findall(r"common/on_actions/00_code_on_actions", text))
    transitions = re.findall(r"Transition (\S+)->(\S+)", text)
    into_game = [pair for pair in transitions if pair[1] == "Game"]
    return {
        "entered_campaign": lines > MAIN_MENU_LINE_CEILING or bool(into_game),
        "log_lines": lines,
        "main_menu_ceiling": MAIN_MENU_LINE_CEILING,
        "code_on_action_lines": on_action_hits,
        "transitions": [f"{a}->{b}" for a, b in transitions],
        "last_log_line": text.rstrip().splitlines()[-1][:160] if text.strip() else "",
    }


def run_variant(label: str, userdir: pathlib.Path, extra: list[str], seconds: int) -> dict:
    print("=" * 72)
    print(f"{label}  args={extra}")
    argv = [str(EXE), "-debug_mode", "-userdir", str(userdir.resolve()), *extra]
    print("argv:", " ".join(argv[1:]))
    for stale in ("debug.log", "error.log"):
        (userdir / "logs" / stale).unlink(missing_ok=True)
    process = subprocess.Popen(
        argv,
        cwd=str(GAME_ROOT),
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"pid={process.pid} (hidden, no input injected)")
    started = time.monotonic()
    samples: list[tuple[float, int]] = []
    try:
        while time.monotonic() - started < seconds:
            time.sleep(15)
            log = userdir / "logs/debug.log"
            size = log.stat().st_size if log.is_file() else 0
            samples.append((round(time.monotonic() - started), log.read_text("utf-8", errors="replace").count("\n") if log.is_file() else 0))
            print(f"  t={samples[-1][0]:>4}s lines={samples[-1][1]:>6} bytes={size}")
    finally:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
        time.sleep(2)
        print(f"terminated pid={process.pid}")

    result = verdict(userdir)
    result["label"] = label
    result["samples"] = samples
    saves = sorted((userdir / "save games").glob("*.v3"))
    result["saves"] = [f"{p.name} {p.stat().st_size}" for p in saves]
    print(f"  -> log_lines={result['log_lines']} code_on_actions={result['code_on_action_lines']}")
    print(f"  -> transitions={result['transitions']}")
    print(f"  -> entered_campaign={result['entered_campaign']}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", type=pathlib.Path, default=DEFAULT_SAVE)
    parser.add_argument("--seconds", type=int, default=150)
    parser.add_argument("--only", help="run a single variant by name")
    args = parser.parse_args()

    if not args.save.is_file():
        print(f"staging save does not exist: {args.save}")
        return 1

    variants = [
        ("continue", ["-continue", "-no_notifications"]),
        ("continue_handsoff", ["-continue", "-handsoff", "-no_notifications"]),
    ]
    if args.only:
        variants = [item for item in variants if item[0] == args.only]

    report = {"save": str(args.save), "results": []}
    out = pathlib.Path("artifacts/observe/_campaign_probe.json")
    for label, extra in variants:
        userdir = pathlib.Path("artifacts/observe/_campaignprobe") / label
        staged = stage(userdir, args.save)
        print(f"staged save: {staged}")
        report["results"].append(run_variant(label, userdir, extra, args.seconds))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n" + "=" * 72)
    for result in report["results"]:
        print(f"{result['label']:22} entered_campaign={result['entered_campaign']} lines={result['log_lines']}")
    print(f"report: {out}")
    return 0 if any(result["entered_campaign"] for result in report["results"]) else 1


if __name__ == "__main__":
    sys.exit(main())
