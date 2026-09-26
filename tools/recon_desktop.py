"""Read-only desktop reconnaissance: window inventory + screenshot.

Injects nothing. Writes artifacts/automation/recon-<stamp>.png and prints the
top-level window list so automation targets can be identified before any input
is sent.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import datetime
import pathlib
import sys

OUT = pathlib.Path("artifacts/automation")
OUT.mkdir(parents=True, exist_ok=True)
stamp = datetime.datetime.now().strftime("%H%M%S")

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

INTERESTING = ("victoria", "launcher", "paradox", "dowser", "steam")


def window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def pid_of(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


rows: list[tuple[int, int, str, str, str, int, int]] = []


@ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
def callback(hwnd, _lparam):
    if user32.IsWindowVisible(hwnd):
        title = window_text(hwnd)
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        rows.append(
            (
                hwnd,
                pid_of(hwnd),
                class_name(hwnd),
                title,
                "fg" if hwnd == user32.GetForegroundWindow() else "",
                rect.right - rect.left,
                rect.bottom - rect.top,
            )
        )
    return True


user32.EnumWindows(callback, 0)

print(f"可见顶层窗口 {len(rows)} 个（只列有标题或疑似相关进程的）：")
for hwnd, pid, cls, title, fg, width, height in rows:
    blob = f"{cls} {title}".lower()
    if not title and not any(key in blob for key in INTERESTING):
        continue
    print(f"  hwnd={hwnd:<10} pid={pid:<7} {width:>5}x{height:<5} {fg:2} [{cls}] {title[:70]}")

foreground = user32.GetForegroundWindow()
print(f"\n前台窗口: hwnd={foreground} pid={pid_of(foreground)} [{class_name(foreground)}] {window_text(foreground)!r}")

try:
    from PIL import ImageGrab

    image = ImageGrab.grab(all_screens=True)
    path = OUT / f"recon-{stamp}.png"
    image.save(path)
    print(f"截图: {path}  ({image.width}x{image.height})")
except Exception as error:  # noqa: BLE001 - recon script, report and continue
    print(f"截图失败: {error!r}")

sys.exit(0)
