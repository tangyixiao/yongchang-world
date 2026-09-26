"""Diagnose why the Paradox launcher exits without showing a window.

Runs each candidate entry point, waits briefly, and reports the exit code and
how long the process survived. A sub-second exit means the process bailed before
initialising (single-instance hand-off or an argument/dependency failure);
a longer life with no window points at the UI layer instead.
"""

from __future__ import annotations

import pathlib
import subprocess
import time

LAUNCHER_ROOT = pathlib.Path(r"D:/Paradox Interactive/launcher")
GAME_LAUNCHER = pathlib.Path(r"E:/SteamLibrary/steamapps/common/Victoria 3/launcher")
INSTALL = LAUNCHER_ROOT / "launcher-v2.2026.11.1/Paradox Launcher.exe"

ARGV = [
    "--pdxlLauncherInvokedTimestamp",
    str(int(time.time() * 1000)),
    "--pdxlGameDir",
    str(GAME_LAUNCHER),
    "--gameDir",
    str(GAME_LAUNCHER),
]

CANDIDATES = [
    ("bootstrapper-v2.exe (own dir cwd)", LAUNCHER_ROOT / "bootstrapper-v2.exe", LAUNCHER_ROOT, []),
    ("Paradox Launcher.exe (own dir cwd)", INSTALL, INSTALL.parent, ARGV),
    ("Paradox Launcher.exe (launcher root cwd)", INSTALL, LAUNCHER_ROOT, ARGV),
]

for label, executable, cwd, extra in CANDIDATES:
    print("=" * 72)
    print(label)
    print("  executable:", executable)
    print("  cwd:", cwd)
    if not executable.is_file():
        print("  MISSING")
        continue
    started = time.monotonic()
    try:
        process = subprocess.Popen([str(executable), *extra], cwd=str(cwd))
    except OSError as error:
        print(f"  spawn failed: {error!r}")
        continue
    print("  pid:", process.pid)
    deadline = started + 20
    code = None
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            break
        time.sleep(0.25)
    elapsed = time.monotonic() - started
    if code is None:
        print(f"  still running after {elapsed:.1f}s  <-- it survived")
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        print("  terminated for the next probe")
    else:
        print(f"  exited code={code} after {elapsed:.2f}s")
