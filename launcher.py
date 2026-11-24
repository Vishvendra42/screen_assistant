"""
WDALauncher — Silent background launcher for WDAService.exe
Disguised as: Windows Driver Assistant Launcher
Runs silently at Windows login.
Listens for / + 1 globally -> launches or brings WDAService.exe to front.
Zero UI. Zero taskbar presence. Zero Alt+Tab visibility.
"""
import os
import sys
import time
import ctypes
import subprocess
import threading
from ctypes import wintypes
from pathlib import Path

# ── Base Directory & Target Search ──────────────────────────────
if getattr(sys, "frozen", False):
    HERE = Path(sys.executable).resolve().parent
else:
    HERE = Path(__file__).resolve().parent

def _find_main_exe():
    candidates = [
        HERE / "WDAService.exe",
        HERE / "dist" / "WDAService.exe",
        Path(r"c:\Users\ASUS\Downloads\prev onw\screen_assistant\screen_assistant\dist\WDAService.exe"),
        Path(r"c:\Users\ASUS\Downloads\prev onw\screen_assistant\screen_assistant\WDAService.exe"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return HERE / "WDAService.exe"

MAIN_EXE = _find_main_exe()

# ── Single-instance mutex ───────────────────────────────────────
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_mutex = _kernel32.CreateMutexW(None, False, "Local\\WDALauncherWindowsApp")
if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
    sys.exit(0)

user32 = ctypes.windll.user32

# ── KBDLL hook structures ───────────────────────────────────────
ULONG_PTR = ctypes.c_size_t

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode",      wintypes.DWORD),
        ("scanCode",    wintypes.DWORD),
        ("flags",       wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

VK_SLASH   = 0xBF  # '/' key (VK_OEM_2)
VK_DIVIDE = 0x6F  # numpad '/'
VK_DIVIDE = 0x6F  # numpad '/' key
VK_CONTROL = 0x11
VK_MENU    = 0x12  # Alt
VK_LWIN    = 0x5B
VK_RWIN    = 0x5C

_slash_down       = False
_slash_count      = 0
_slash_time       = 0.0
_swallow_slash_up = False
_blocked_keys     = set()
_hhook            = None


def _launch_main():
    """Start or unhide WDAService.exe."""
    try:
        exe = _find_main_exe()
        if exe and exe.exists():
            subprocess.Popen(
                [str(exe), "--show"],
                cwd=str(exe.parent),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
    except Exception:
        pass


def _keyboard_proc(nCode, wParam, lParam):
    global _slash_down, _slash_count, _slash_time, _swallow_slash_up, _blocked_keys
    if nCode >= 0:
        kbd = KBDLLHOOKSTRUCT.from_address(lParam)

        # Ignore injected keys
        if kbd.flags & 0x10:
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        vk = kbd.vkCode
        is_down = wParam in (0x0100, 0x0104)
        is_up   = wParam in (0x0101, 0x0105)

        # If Ctrl, Alt, or Win is pressed, this is an IDE/system shortcut (e.g. Ctrl + / in VS Code, Ctrl + 1, etc.).
        # Screen Assistant shortcuts NEVER use Ctrl/Alt/Win. Pass through immediately and clean up chord state.
        is_modifier_active = (
            (user32.GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0 or
            (user32.GetAsyncKeyState(VK_MENU) & 0x8000) != 0 or
            (user32.GetAsyncKeyState(VK_LWIN) & 0x8000) != 0 or
            (user32.GetAsyncKeyState(VK_RWIN) & 0x8000) != 0
        )
        if is_modifier_active:
            _slash_down = False
            _slash_count = 0
            _swallow_slash_up = False
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        is_slash_physically_down = (
            ((user32.GetAsyncKeyState(VK_SLASH) & 0x8000) != 0) or
            ((user32.GetAsyncKeyState(VK_DIVIDE) & 0x8000) != 0)
        )

        if vk in (VK_SLASH, VK_DIVIDE):
            if is_down:
                if not _slash_down:
                    _slash_down = True
                    _slash_count = 1
                    _slash_time = time.time()
                else:
                    _slash_count += 1
            elif is_up:
                _slash_down = False
                _slash_count = 0
                if _swallow_slash_up:
                    _swallow_slash_up = False
                    return 1  # swallow slash keyup after chord triggered

        elif is_down:
            now = time.time()
            is_recent_slash = _slash_down and ((now - _slash_time) <= 1.5)
            is_active_chord = is_slash_physically_down or is_recent_slash

            if not is_active_chord:
                _slash_down = False
                _slash_count = 0
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            # WDALauncher ONLY handles / + 1 to launch/show the main app. Never intercept other keys!
            if vk == 0x31:  # '1' key
                _blocked_keys.add(vk)
                _swallow_slash_up = True
                _slash_down = False
                for _ in range(max(1, _slash_count)):
                    user32.keybd_event(0x08, 0, 0, 0)
                    user32.keybd_event(0x08, 0, 2, 0)
                _slash_count = 0
                threading.Thread(target=_launch_main, daemon=True).start()
                return 1  # block '1' from typing

        elif is_up:
            if vk in _blocked_keys:
                _blocked_keys.discard(vk)
                return 1

    return user32.CallNextHookEx(None, nCode, wParam, lParam)


def main():
    global _hhook

    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.SetWindowsHookExW.argtypes = [
        ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD
    ]
    user32.CallNextHookEx.restype  = ctypes.c_longlong
    user32.CallNextHookEx.argtypes = [
        wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
    ]
    user32.UnhookWindowsHookEx.restype  = wintypes.BOOL
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]

    c_hook = HOOKPROC(_keyboard_proc)
    _hhook  = user32.SetWindowsHookExW(13, c_hook, None, 0)  # WH_KEYBOARD_LL

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    if _hhook:
        user32.UnhookWindowsHookEx(_hhook)


if __name__ == "__main__":
    main()
