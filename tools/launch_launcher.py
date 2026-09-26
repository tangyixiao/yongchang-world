"""Launch the installed Paradox launcher for Victoria 3 with the bootstrapper's argv.

Git Bash mangles Windows paths passed through ``cmd start`` (``\\common`` loses
its separator), so the launcher is started from Python with an explicit argv
list and working directory.  The command line mirrors what
``launcher-bootstrapper.log`` records for a normal launch, which is the only
way ``Paradox Launcher.exe`` will show its window when started directly.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import time

DEFAULT_LAUNCHER_ROOT = pathlib.Path(r"D:/Paradox Interactive/launcher")
DEFAULT_GAME_LAUNCHER = pathlib.Path(r"E:/SteamLibrary/steamapps/common/Victoria 3/launcher")


def find_launcher(launcher_root: pathlib.Path) -> pathlib.Path:
    """Newest ``launcher-v2.<version>/Paradox Launcher.exe`` present."""

    candidates = [
        path
        for path in launcher_root.glob("launcher-v2.*/Paradox Launcher.exe")
        if path.is_file()
    ]
    if not candidates:
        raise SystemExit(f"no launcher install found under {launcher_root}")

    def version_key(path: pathlib.Path) -> tuple[int, ...]:
        digits = path.parent.name.split("-v2.")[-1].split(".")
        return tuple(int(part) if part.isdigit() else 0 for part in digits)

    return max(candidates, key=version_key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher-root", type=pathlib.Path, default=DEFAULT_LAUNCHER_ROOT)
    parser.add_argument("--game-launcher-dir", type=pathlib.Path, default=DEFAULT_GAME_LAUNCHER)
    parser.add_argument("--extra-arg", action="append", default=[], help="additional launcher argument")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    executable = find_launcher(args.launcher_root)
    game_dir = str(args.game_launcher_dir)
    argv = [
        str(executable),
        "--pdxlLauncherInvokedTimestamp",
        str(int(time.time() * 1000)),
        "--pdxlGameDir",
        game_dir,
        "--gameDir",
        game_dir,
        *args.extra_arg,
    ]
    print("executable:", executable)
    print("argv:", argv)
    if args.dry_run:
        return 0

    process = subprocess.Popen(argv, cwd=str(executable.parent))
    print(f"launched pid={process.pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
