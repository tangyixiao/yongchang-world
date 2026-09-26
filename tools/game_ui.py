"""Minimal desktop driver for Victoria 3 (launch / screenshot / click / key).

The game cannot be started into a campaign from the command line (see
``docs/release/automation-pilot-log.md``), so the main menu and country
selection have to be driven through the real UI.  This tool keeps that in one
place: it launches the game into an isolated ``-userdir``, finds the game's own
window by process id, brings it to the front, screenshots the window crop for a
human/agent to look at, and injects clicks and keys.

Input is only ever sent to the Victoria 3 window: every click is checked against
the window rect first, so a mis-aimed coordinate fails loudly instead of landing
in whatever the user has open.

    python tools/game_ui.py launch            # hidden-free launch, isolated userdir
    python tools/game_ui.py shot              # window crop + full screen
    python tools/game_ui.py click --x 640 --y 400
    python tools/game_ui.py key --name space
    python tools/game_ui.py kill              # stop the game this tool started
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import json
import pathlib
import subprocess
import sys
import time

GAME_ROOT = pathlib.Path(r"E:/SteamLibrary/steamapps/common/Victoria 3")
EXE = GAME_ROOT / "binaries/victoria3.exe"
STATE = pathlib.Path("artifacts/automation/game-ui-state.json")
SHOTS = pathlib.Path("artifacts/automation")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.SetProcessDPIAware()

SYNCHRONIZE = 0x00100000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WAIT_TIMEOUT = 0x00000102


def process_alive(pid: int) -> bool:
    """Is ``pid`` still running?

    Deliberately ctypes instead of parsing ``tasklist``: its output is emitted in
    the console code page (GBK here), and decoding it as UTF-8 raises inside the
    reader thread, leaving ``stdout`` as ``None`` and taking the caller down with
    a TypeError.  That killed a long-running keep-alive task mid-campaign.
    """

    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
    finally:
        kernel32.CloseHandle(handle)


def image_name(pid: int) -> str:
    """Executable file name of ``pid``, or an empty string when unreadable."""

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(4096)
        size = wintypes.DWORD(4096)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return pathlib.PureWindowsPath(buffer.value).name.lower()
        return ""
    finally:
        kernel32.CloseHandle(handle)


def window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def window_pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def find_window(pid: int) -> int | None:
    """Largest visible top-level window owned by ``pid``."""

    found: list[tuple[int, int]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd) and window_pid(hwnd) == pid:
            left, top, right, bottom = window_rect(hwnd)
            area = max(0, right - left) * max(0, bottom - top)
            if area > 0:
                found.append((area, hwnd))
        return True

    user32.EnumWindows(callback, 0)
    if not found:
        return None
    return max(found)[1]


def load_state() -> dict:
    if STATE.is_file():
        return json.loads(STATE.read_text("utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def game_window(require: bool = True) -> tuple[int, int]:
    state = load_state()
    pid = state.get("pid")
    if pid is not None:
        hwnd = find_window(pid)
        if hwnd:
            return pid, hwnd
    # Fall back to any visible victoria3.exe window, matched by executable name
    # rather than by parsing tasklist output.
    found: list[tuple[int, int]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            candidate = window_pid(hwnd)
            if image_name(candidate) == "victoria3.exe":
                found.append((candidate, hwnd))
        return True

    user32.EnumWindows(callback, 0)
    if found:
        return found[0]
    if require:
        raise SystemExit("no visible victoria3.exe window; run `launch` first")
    return 0, 0


def bring_to_front(hwnd: int) -> None:
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    for _ in range(20):
        if user32.GetForegroundWindow() == hwnd:
            return
        time.sleep(0.1)


def take_shot(hwnd: int | None, label: str) -> list[pathlib.Path]:
    from PIL import ImageGrab

    SHOTS.mkdir(parents=True, exist_ok=True)
    written: list[pathlib.Path] = []
    full = ImageGrab.grab(all_screens=True)
    path = SHOTS / f"{label}-full.png"
    full.save(path)
    written.append(path)
    if hwnd:
        left, top, right, bottom = window_rect(hwnd)
        crop = full.crop((left, top, right, bottom))
        path = SHOTS / f"{label}-window.png"
        crop.save(path)
        written.append(path)
    return written


def cmd_launch(args: argparse.Namespace) -> int:
    argv = [
        str(EXE),
        "-debug_mode",
        "-userdir",
        str(args.userdir.resolve()),
    ]
    if args.no_notifications:
        argv.append("-no_notifications")
    argv.extend(args.extra_arg)
    print("argv:", " ".join(argv))
    # Detach: the game must outlive this process, otherwise the shell that ran
    # the launch reaps the whole tree and the window disappears mid-boot.  A job
    # object can still kill it, so breakaway is requested when the host allows
    # it; callers that need certainty keep their own command alive (see
    # tools/keep_game_running.ps1) because breakaway is frequently refused.
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    breakaway = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000)
    try:
        process = subprocess.Popen(
            argv,
            cwd=str(GAME_ROOT),
            creationflags=flags | breakaway,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        print("launch flags: DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP|CREATE_BREAKAWAY_FROM_JOB")
    except OSError as error:
        print(f"breakaway refused ({error}); falling back to a plain detached launch")
        process = subprocess.Popen(
            argv,
            cwd=str(GAME_ROOT),
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    save_state({"pid": process.pid, "userdir": str(args.userdir.resolve()), "argv": argv})
    print(f"launched pid={process.pid} (detached)")

    deadline = time.monotonic() + args.wait
    hwnd = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            print(f"game exited early with code {process.returncode}")
            return 1
        hwnd = find_window(process.pid)
        if hwnd:
            break
        time.sleep(1)
    if not hwnd:
        print(f"no window after {args.wait}s")
        return 1
    print(f"window hwnd={hwnd} rect={window_rect(hwnd)}")
    time.sleep(args.settle)
    bring_to_front(hwnd)
    for path in take_shot(hwnd, args.label):
        print("shot:", path)
    return 0


def cmd_shot(args: argparse.Namespace) -> int:
    pid, hwnd = game_window()
    if not args.no_focus:
        bring_to_front(hwnd)
        time.sleep(0.4)
    for path in take_shot(hwnd, args.label):
        print("shot:", path)
    print(f"pid={pid} hwnd={hwnd} rect={window_rect(hwnd)}")
    return 0


def cmd_click(args: argparse.Namespace) -> int:
    import pyautogui

    _pid, hwnd = game_window()
    left, top, right, bottom = window_rect(hwnd)
    if not args.absolute:
        x, y = left + args.x, top + args.y
    else:
        x, y = args.x, args.y
    if not (left <= x <= right and top <= y <= bottom):
        raise SystemExit(f"click ({x},{y}) is outside the game window {left, top, right, bottom}")
    bring_to_front(hwnd)
    time.sleep(0.3)
    pyautogui.moveTo(x, y, duration=0.2)
    if args.double:
        pyautogui.doubleClick(x, y)
    else:
        pyautogui.click(x, y)
    print(f"clicked ({x},{y}) absolute; window-relative ({x - left},{y - top})")
    time.sleep(args.settle)
    if args.label:
        for path in take_shot(hwnd, args.label):
            print("shot:", path)
    return 0


def cmd_key(args: argparse.Namespace) -> int:
    import pyautogui

    _pid, hwnd = game_window()
    bring_to_front(hwnd)
    time.sleep(0.3)
    if args.text:
        pyautogui.typewrite(args.text, interval=0.05)
        print(f"typed {args.text!r}")
    if args.name:
        for _ in range(args.repeat):
            pyautogui.press(args.name)
        print(f"pressed {args.name} x{args.repeat}")
    time.sleep(args.settle)
    if args.label:
        for path in take_shot(hwnd, args.label):
            print("shot:", path)
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    rows: list[tuple[int, int, str, tuple[int, int, int, int]]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            rows.append((hwnd, window_pid(hwnd), window_title(hwnd), window_rect(hwnd)))
        return True

    user32.EnumWindows(callback, 0)
    for hwnd, pid, title, rect in rows:
        if title:
            print(f"hwnd={hwnd} pid={pid} rect={rect} {title[:70]}")
    return 0


def cmd_kill(_args: argparse.Namespace) -> int:
    state = load_state()
    pid = state.get("pid")
    if pid is None:
        print("no pid recorded")
        return 1
    if not process_alive(pid) or image_name(pid) != "victoria3.exe":
        print(f"pid {pid} is not a running victoria3.exe")
        return 0
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    print(f"killed pid {pid}")
    state.pop("pid", None)
    save_state(state)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    launch = sub.add_parser("launch")
    launch.add_argument("--userdir", type=pathlib.Path, default=pathlib.Path("artifacts/observe/_gui"))
    launch.add_argument("--wait", type=int, default=120)
    launch.add_argument("--settle", type=float, default=3.0)
    launch.add_argument("--label", default="launch")
    launch.add_argument("--no-notifications", action="store_true")
    launch.add_argument("--extra-arg", action="append", default=[])
    launch.set_defaults(func=cmd_launch)

    shot = sub.add_parser("shot")
    shot.add_argument("--label", default="shot")
    shot.add_argument("--no-focus", action="store_true")
    shot.set_defaults(func=cmd_shot)

    click = sub.add_parser("click")
    click.add_argument("--x", type=int, required=True)
    click.add_argument("--y", type=int, required=True)
    click.add_argument("--absolute", action="store_true", help="treat x/y as screen coordinates")
    click.add_argument("--double", action="store_true")
    click.add_argument("--settle", type=float, default=1.5)
    click.add_argument("--label")
    click.set_defaults(func=cmd_click)

    key = sub.add_parser("key")
    key.add_argument("--name")
    key.add_argument("--text")
    key.add_argument("--repeat", type=int, default=1)
    key.add_argument("--settle", type=float, default=1.5)
    key.add_argument("--label")
    key.set_defaults(func=cmd_key)

    listing = sub.add_parser("list")
    listing.set_defaults(func=cmd_list)

    kill = sub.add_parser("kill")
    kill.set_defaults(func=cmd_kill)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
