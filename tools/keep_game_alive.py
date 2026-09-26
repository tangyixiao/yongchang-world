"""Launch Victoria 3 and stay alive so the host's job object cannot kill it.

The game is started with DETACHED_PROCESS, but ``CREATE_BREAKAWAY_FROM_JOB`` is
refused on this host (WinError 5), so the game stays inside the job object of
whoever started it: when that command finishes, the whole tree is reaped and the
game dies mid-boot.  Running this script as a long-lived background task keeps
the job open, which is what lets the window survive between automation steps.

Stops when ``artifacts/automation/stop.flag`` appears, when the game exits on its
own, or after ``--minutes``.  On the way out it terminates the game it started,
so no orphan is left behind.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import game_ui  # noqa: E402  (needs the path setup above)

STOP_FLAG = pathlib.Path("artifacts/automation/stop.flag")
HEARTBEAT = pathlib.Path("artifacts/automation/keeper-heartbeat.txt")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--userdir", type=pathlib.Path, default=pathlib.Path("artifacts/observe/_gui/userdata"))
    parser.add_argument("--minutes", type=float, default=480)
    parser.add_argument("--no-launch", action="store_true", help="only hold an existing game open")
    parser.add_argument("--extra-arg", action="append", default=[])
    args = parser.parse_args()

    STOP_FLAG.unlink(missing_ok=True)
    STOP_FLAG.parent.mkdir(parents=True, exist_ok=True)

    if args.no_launch:
        pid, hwnd = game_ui.game_window()
        print(f"adopting pid={pid} hwnd={hwnd}", flush=True)
    else:
        argv = [
            str(game_ui.EXE),
            "-debug_mode",
            "-userdir",
            str(args.userdir.resolve()),
            *args.extra_arg,
        ]
        process = subprocess.Popen(
            argv,
            cwd=str(game_ui.GAME_ROOT),
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        pid = process.pid
        game_ui.save_state({"pid": pid, "userdir": str(args.userdir.resolve()), "argv": argv})
        print(f"launched pid={pid}", flush=True)

    deadline = time.monotonic() + args.minutes * 60
    try:
        while time.monotonic() < deadline:
            if STOP_FLAG.exists():
                print("stop flag seen", flush=True)
                break
            if not game_ui.process_alive(pid):
                print(f"game pid {pid} exited on its own", flush=True)
                return 0
            HEARTBEAT.write_text(
                f"pid={pid} at={time.strftime('%H:%M:%S')}\n", encoding="utf-8"
            )
            time.sleep(10)
    finally:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        print(f"terminated pid {pid}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
