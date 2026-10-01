"""Check that the built Windows app refuses to shrink below its minimum size.

test/minimum_window_test.dart proves the layout fits the minimum declared in
windows/runner/flutter_window.h. It cannot prove the runner enforces it - that
is C++ handling WM_GETMINMAXINFO, which no Dart test reaches. This does: it
launches the real executable, asks Windows to make the window 400x300, and
measures the client area it actually got.

SetWindowPos is a fair stand-in for a user dragging the border. Both end in
DefWindowProc's WM_WINDOWPOSCHANGING handling, which is where the minimum
track size from WM_GETMINMAXINFO is applied.

Needs a release build first, and nothing else - the client starts without a
backend and simply shows its connecting state:

    flutter build windows
    python tool/check_min_window.py

Exit status 0 if the window held its minimum, 1 if it shrank below it.
"""

import ctypes
import ctypes.wintypes as wt
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "build" / "windows" / "x64" / "runner" / "Release" / "pip_flutter_client.exe"
HEADER = ROOT / "windows" / "runner" / "flutter_window.h"

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2, so rects are physical pixels

EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def declared_minimum() -> tuple[int, int] | None:
    text = HEADER.read_text(encoding="utf-8")
    w = re.search(r"constexpr int kMinClientWidth = (\d+);", text)
    h = re.search(r"constexpr int kMinClientHeight = (\d+);", text)
    return (int(w.group(1)), int(h.group(1))) if w and h else None


def main_window_of(pid: int) -> int | None:
    found: list[int] = []

    def visit(hwnd, _):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(EnumWindowsProc(visit), 0)
    return found[0] if found else None


def main() -> int:
    if not EXE.exists():
        print(f"no build at {EXE} - run `flutter build windows` first")
        return 1

    # Without a declared minimum there is nothing to hold the window to, but the
    # check still runs: what the window shrinks to is the evidence.
    minimum = declared_minimum() or (800, 640)
    process = subprocess.Popen([str(EXE)])
    try:
        hwnd = None
        for _ in range(100):
            hwnd = main_window_of(process.pid)
            if hwnd:
                break
            time.sleep(0.1)
        if not hwnd:
            print("the app never showed a window")
            return 1
        time.sleep(1.0)

        scale = user32.GetDpiForWindow(hwnd) / 96
        SWP_NOMOVE, SWP_NOZORDER = 0x0002, 0x0004
        user32.SetWindowPos(hwnd, None, 0, 0, 400, 300, SWP_NOMOVE | SWP_NOZORDER)
        time.sleep(0.5)

        client = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(client))
        got_w, got_h = client.right / scale, client.bottom / scale

        # The runner clamps the minimum to the monitor's work area, so on a
        # screen smaller than the minimum the window can legitimately be
        # smaller. Note it rather than fail: this machine's screen is the test.
        work = wt.RECT()
        user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0)  # SPI_GETWORKAREA
        work_w, work_h = (work.right - work.left) / scale, (work.bottom - work.top) / scale

        want_w, want_h = min(minimum[0], work_w), min(minimum[1], work_h)
        print(f"declared minimum {minimum[0]}x{minimum[1]} logical "
              f"(header {'defines it' if declared_minimum() else 'defines NONE'})")
        print(f"asked for 400x300, got client {got_w:.0f}x{got_h:.0f} logical at {scale:.2f}x scale")
        # One logical pixel of slack for rounding between scales.
        if got_w + 1 >= want_w and got_h + 1 >= want_h:
            print("PASS: the window held its minimum")
            return 0
        print("FAIL: the window shrank below the minimum")
        return 1
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    sys.exit(main())
