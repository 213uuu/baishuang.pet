#!/usr/bin/env python3
"""白霜托盘入口（B 方案）。

只负责把“打开 / 重启 / 关闭 / 状态”转给 pet-control.ps1：
不 import desktop_pet，不读 frames，也不改 pet.json，
所以 Codex 的 Pets 页和桌宠本身的画面都不会受影响。

用法：
    双击 白霜托盘.lnk（或 pythonw pet-tray.py）常驻托盘。
    Ctrl+Alt+B          打开白霜
    Ctrl+Alt+Shift+B    关闭白霜
    左键单击托盘图标     打开白霜
    右键托盘图标         打开 / 重启 / 关闭 / 状态 / 退出托盘

也支持命令行直调，便于排查：
    python pet-tray.py open|restart|close|status
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import locale
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONTROL = os.path.join(APP_DIR, "pet-control.ps1")
ICON_PATH = os.path.join(APP_DIR, "assets", "baishuang.ico")
LOG_PATH = os.path.join(APP_DIR, "pet-tray.log")
PID_PATH = os.path.join(APP_DIR, "pet-tray.pid")
ANIMATION_REQUEST_PATH = os.path.join(APP_DIR, "startup-animation.request")
WINDOW_CLASS = "BaishuangPetTrayWnd"

POWERSHELL = (
    shutil.which("powershell")
    or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
)

# --- Win32 常量 ---------------------------------------------------------
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_NULL = 0x0000
WM_COMMAND = 0x0111
WM_HOTKEY = 0x0312
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205

WM_APP = 0x8000
WM_TRAY = WM_APP + 1

NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010

NIIF_INFO = 0x00000001

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040
IDI_APPLICATION = 32512

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

HOTKEY_OPEN = 0xB501
HOTKEY_CLOSE = 0xB502

ID_OPEN = 1001
ID_RESTART = 1002
ID_CLOSE = 1003
ID_STATUS = 1004
ID_QUIT = 1005

CREATE_NO_WINDOW = 0x08000000


def log(message: str) -> None:
    try:
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 512 * 1024:
            os.replace(LOG_PATH, LOG_PATH + ".1")
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


# 从 Codex（对话框或它自带的终端）启动时，进程会被放进隐藏桌面
# CodexSandboxDesktop-<hash>；托盘图标建在那里用户看不到。
# 建任何窗口之前把线程挂到交互桌面，和白霜本体用同一套办法。
DESKTOP_RIGHTS = 0x0001 | 0x0002 | 0x0040   # READOBJECTS | CREATEWINDOW | WRITEOBJECTS
UOI_NAME = 2
DESKTOP_KEEPALIVE = []


def _object_name(handle) -> str:
    if not handle:
        return "<null>"
    need = wt.DWORD()
    user32.GetUserObjectInformationW(handle, UOI_NAME, None, 0, ctypes.byref(need))
    buffer = ctypes.create_unicode_buffer(max(need.value, 2))
    user32.GetUserObjectInformationW(
        handle, UOI_NAME, buffer, need.value, ctypes.byref(need)
    )
    return buffer.value


def current_desktop() -> str:
    try:
        handle = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
        return _object_name(handle)
    except Exception:
        return "<读不到>"


def attach_to_interactive_desktop() -> str:
    before = current_desktop()
    try:
        target = user32.OpenInputDesktop(0, False, DESKTOP_RIGHTS)
        if not target:
            target = user32.OpenDesktopW("Default", 0, False, DESKTOP_RIGHTS)
        if not target:
            return f"桌面={before}，且无法打开交互桌面（错误 {ctypes.get_last_error()}）"
        name = _object_name(target)
        if name == before:
            return f"桌面={before}（无需切换）"
        if not user32.SetThreadDesktop(target):
            return f"桌面={before} -> 切到 {name} 失败（错误 {ctypes.get_last_error()}）"
        DESKTOP_KEEPALIVE.append(target)
        return f"桌面已从 {before} 切换到 {name}"
    except Exception as exc:
        return f"桌面切换异常：{type(exc).__name__}: {exc}"


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wt.DWORD),
        ("Data2", wt.WORD),
        ("Data3", wt.WORD),
        ("Data4", ctypes.c_byte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("hWnd", wt.HWND),
        ("uID", wt.UINT),
        ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT),
        ("hIcon", wt.HICON),
        ("szTip", wt.WCHAR * 128),
        ("dwState", wt.DWORD),
        ("dwStateMask", wt.DWORD),
        ("szInfo", wt.WCHAR * 256),
        ("uTimeout", wt.UINT),
        ("szInfoTitle", wt.WCHAR * 64),
        ("dwInfoFlags", wt.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wt.HICON),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wt.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
    ]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * 260),
    ]


user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM
)

user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wt.ATOM
user32.CreateWindowExW.argtypes = [
    wt.DWORD,
    wt.LPCWSTR,
    wt.LPCWSTR,
    wt.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wt.HWND,
    wt.HMENU,
    wt.HINSTANCE,
    wt.LPVOID,
]
user32.CreateWindowExW.restype = wt.HWND
user32.DestroyWindow.argtypes = [wt.HWND]
user32.DestroyWindow.restype = wt.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.TranslateMessage.restype = wt.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.PostMessageW.restype = wt.BOOL
user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
user32.RegisterHotKey.restype = wt.BOOL
user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wt.BOOL
user32.LoadImageW.argtypes = [
    wt.HINSTANCE,
    wt.LPCWSTR,
    wt.UINT,
    ctypes.c_int,
    ctypes.c_int,
    wt.UINT,
]
user32.LoadImageW.restype = wt.HANDLE
user32.LoadIconW.argtypes = [wt.HINSTANCE, wt.LPCWSTR]
user32.LoadIconW.restype = wt.HICON
user32.DestroyIcon.argtypes = [wt.HICON]
user32.DestroyIcon.restype = wt.BOOL
user32.CreatePopupMenu.argtypes = []
user32.CreatePopupMenu.restype = wt.HMENU
user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, wt.UINT, wt.LPCWSTR]
user32.AppendMenuW.restype = wt.BOOL
user32.DestroyMenu.argtypes = [wt.HMENU]
user32.DestroyMenu.restype = wt.BOOL
user32.TrackPopupMenu.argtypes = [
    wt.HMENU,
    wt.UINT,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wt.HWND,
    ctypes.c_void_p,
]
user32.TrackPopupMenu.restype = wt.UINT
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.SetForegroundWindow.restype = wt.BOOL
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wt.HWND
user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
user32.GetCursorPos.restype = wt.BOOL
user32.RegisterWindowMessageW.argtypes = [wt.LPCWSTR]
user32.RegisterWindowMessageW.restype = wt.UINT
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowW.restype = wt.HWND
user32.GetThreadDesktop.argtypes = [wt.DWORD]
user32.GetThreadDesktop.restype = wt.HANDLE
user32.OpenInputDesktop.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
user32.OpenInputDesktop.restype = wt.HANDLE
user32.OpenDesktopW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.BOOL, wt.DWORD]
user32.OpenDesktopW.restype = wt.HANDLE
user32.SetThreadDesktop.argtypes = [wt.HANDLE]
user32.SetThreadDesktop.restype = wt.BOOL
user32.GetUserObjectInformationW.argtypes = [
    wt.HANDLE,
    ctypes.c_int,
    wt.LPVOID,
    wt.DWORD,
    ctypes.POINTER(wt.DWORD),
]
user32.GetUserObjectInformationW.restype = wt.BOOL
user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
user32.SetProcessDpiAwarenessContext.restype = wt.BOOL

shell32.Shell_NotifyIconW.argtypes = [
    wt.DWORD,
    ctypes.POINTER(NOTIFYICONDATAW),
]
shell32.Shell_NotifyIconW.restype = wt.BOOL

kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HINSTANCE
kernel32.GetCurrentThreadId.restype = wt.DWORD
kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
kernel32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wt.BOOL
kernel32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wt.BOOL
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype = wt.BOOL


WINDOW_PROC = None
NID = NOTIFYICONDATAW()
HWND = wt.HWND()
ICON_HANDLE = wt.HICON()
LAST_OPEN_AT = 0.0
OPEN_LOCK = threading.Lock()
TASKBAR_CREATED = 0
ICON_RETRYING = False
ICON_RETRY_LOCK = threading.Lock()


def call_control(action: str) -> tuple[int, str]:
    """同步调用 pet-control.ps1，返回 (returncode, 输出)。"""
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            CONTROL,
            "-Action",
            action,
        ],
        cwd=APP_DIR,
        capture_output=True,
        timeout=45,
        creationflags=CREATE_NO_WINDOW,
    )
    encoding = locale.getpreferredencoding(False) or "utf-8"
    stdout = completed.stdout.decode(encoding, "replace").strip()
    stderr = completed.stderr.decode(encoding, "replace").strip()
    output = stdout or stderr
    log(f"{action}: rc={completed.returncode} out={output!r}")
    return completed.returncode, output


def describe(action: str, returncode: int, output: str) -> tuple[str, str]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    first = lines[0] if lines else ""

    if first.startswith("STARTED"):
        pid = first.split(maxsplit=1)[-1]
        return "白霜", f"白霜出来了（PID {pid}）"
    if first.startswith("ALREADY_RUNNING"):
        pid = first.split(maxsplit=1)[-1]
        return "白霜", f"白霜已经在屏幕上（PID {pid}）"
    if first.startswith("RUNNING"):
        pid = first.split(maxsplit=1)[-1]
        return "白霜", f"白霜正在运行（PID {pid}）"
    if first.startswith("STOPPED"):
        return "白霜", "白霜收起来了"
    if first == "NOT_RUNNING":
        return "白霜", "白霜本来就没在跑"
    if first.startswith("START_FAILED"):
        tail = " / ".join(lines[1:6])[:220]
        return "白霜启动失败", tail or first
    if first.startswith("STOP_FAILED"):
        return "白霜关闭失败", first
    if returncode != 0:
        return "白霜", f"调用失败（{returncode}）：{output[:220]}"
    return "白霜", (first or f"{action} 完成")[:220]


def balloon(title: str, text: str) -> None:
    if not HWND:
        return
    try:
        NID.uFlags = NIF_INFO
        NID.szInfoTitle = title[:63]
        NID.szInfo = text[:255]
        NID.uTimeout = 4000
        NID.dwInfoFlags = NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(NID))
    except Exception:
        log("balloon failed\n" + traceback.format_exc())


def run_control(action: str) -> None:
    """后台执行，避免托盘菜单在等待时卡住。"""

    def worker() -> None:
        try:
            returncode, output = call_control(action)
            title, text = describe(action, returncode, output)
            balloon(title, text)
        except Exception as exc:
            log(f"{action} failed\n{traceback.format_exc()}")
            balloon("白霜", f"调用失败：{exc}")

    threading.Thread(target=worker, daemon=True).start()


def codex_desktop_running() -> bool:
    """Detect the Codex desktop process without tasklist/WMI."""
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    invalid = wt.HANDLE(-1).value
    if not snapshot or snapshot == invalid:
        return False
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    try:
        more = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.szExeFile.lower() == "chatgpt.exe":
                return True
            more = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return False


def request_animation_replay() -> None:
    try:
        with open(ANIMATION_REQUEST_PATH, "w", encoding="utf-8") as handle:
            handle.write(str(time.time()))
    except OSError as exc:
        log(f"write animation request failed: {exc}")


def codex_watch_worker() -> None:
    """Open the pet and play its startup clip whenever Codex starts."""
    last_alive: bool | None = None
    initialized = False
    while True:
        try:
            alive = codex_desktop_running()
            if not initialized:
                # 首次采样只负责确保桌宠已打开，不能把“进程本来就在”
                # 误判成一次新的 Codex 启动，否则会和白霜自动开场撞车。
                if alive:
                    returncode, output = call_control("open")
                    first = next(
                        (line.strip() for line in output.splitlines() if line.strip()),
                        "",
                    )
                    log(
                        f"codex-initial trigger: alive={alive} rc={returncode} "
                        f"first={first!r}"
                    )
                initialized = True
            elif alive and last_alive is not True:
                returncode, output = call_control("open")
                first = next((line.strip() for line in output.splitlines() if line.strip()), "")
                if first.startswith("ALREADY_RUNNING"):
                    request_animation_replay()
                log(
                    f"codex-open trigger: alive={alive} rc={returncode} "
                    f"first={first!r}"
                )
            last_alive = alive
        except Exception as exc:  # noqa: BLE001
            log(f"codex watcher failed: {type(exc).__name__}: {exc}")
        time.sleep(2.0)


def request_open() -> None:
    """单击与双击可能连发，这里做 0.8 秒去抖。"""
    global LAST_OPEN_AT
    now = time.monotonic()
    with OPEN_LOCK:
        if now - LAST_OPEN_AT < 0.8:
            return
        LAST_OPEN_AT = now
    run_control("open")


def _add_icon_once() -> bool:
    global NID
    if not HWND:
        return False
    NID = NOTIFYICONDATAW()
    NID.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    NID.hWnd = HWND
    NID.uID = 1
    NID.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    NID.uCallbackMessage = WM_TRAY
    NID.hIcon = ICON_HANDLE
    NID.szTip = "白霜 · 单击打开 | 右键菜单"
    if shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(NID)):
        log("tray icon added")
        return True
    log(f"Shell_NotifyIcon NIM_ADD failed: {ctypes.get_last_error()}")
    return False


def _retry_icon_later() -> None:
    """登录时托盘可能比 Explorer 先就绪，失败后隔几秒重试。"""
    global ICON_RETRYING
    with ICON_RETRY_LOCK:
        if ICON_RETRYING:
            return
        ICON_RETRYING = True

    def worker() -> None:
        global ICON_RETRYING
        try:
            for delay in (2, 5, 10, 20, 30):
                time.sleep(delay)
                if _add_icon_once():
                    log("tray icon added on retry")
                    balloon(
                        "白霜托盘已就绪",
                        "Ctrl+Alt+B 打开白霜；右键托盘图标可关闭或退出。",
                    )
                    return
        finally:
            ICON_RETRYING = False

    threading.Thread(target=worker, daemon=True).start()


def add_icon() -> None:
    if not _add_icon_once():
        _retry_icon_later()


def remove_icon() -> None:
    if HWND:
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(NID))


def show_menu() -> None:
    menu = user32.CreatePopupMenu()
    if not menu:
        return
    command = 0
    previous_foreground = user32.GetForegroundWindow()
    try:
        user32.AppendMenuW(menu, MF_STRING, ID_OPEN, "打开白霜\tCtrl+Alt+B")
        user32.AppendMenuW(menu, MF_STRING, ID_RESTART, "重启白霜")
        user32.AppendMenuW(menu, MF_STRING, ID_CLOSE, "关闭白霜\tCtrl+Alt+Shift+B")
        user32.AppendMenuW(menu, MF_STRING, ID_STATUS, "查看状态")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, ID_QUIT, "退出托盘")

        point = wt.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        # 弹出菜单必须短暂设为前台，菜单关闭后立即还给原应用。
        user32.SetForegroundWindow(HWND)
        command = user32.TrackPopupMenu(
            menu,
            TPM_RETURNCMD | TPM_RIGHTBUTTON,
            point.x,
            point.y,
            0,
            HWND,
            None,
        )
        user32.PostMessageW(HWND, WM_NULL, 0, 0)
    finally:
        user32.DestroyMenu(menu)
        if previous_foreground and previous_foreground != HWND:
            user32.SetForegroundWindow(previous_foreground)

    if command == ID_OPEN:
        request_open()
    elif command == ID_RESTART:
        run_control("restart")
    elif command == ID_CLOSE:
        run_control("close")
    elif command == ID_STATUS:
        run_control("status")
    elif command == ID_QUIT:
        user32.PostMessageW(HWND, WM_CLOSE, 0, 0)


def window_proc(hwnd: int, message: int, wparam: int, lparam: int) -> int:
    global TASKBAR_CREATED
    try:
        if message == WM_TRAY:
            event = lparam & 0xFFFF
            if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                request_open()
            elif event == WM_RBUTTONUP:
                show_menu()
            return 0
        if message == WM_HOTKEY:
            if wparam == HOTKEY_OPEN:
                request_open()
            elif wparam == HOTKEY_CLOSE:
                run_control("close")
            return 0
        if message == TASKBAR_CREATED:
            add_icon()
            return 0
        if message == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if message == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
    except Exception:
        log("window_proc failed\n" + traceback.format_exc())
    return user32.DefWindowProcW(hwnd, message, wparam, lparam)


def bind_cli() -> bool:
    actions = {"open", "restart", "close", "status"}
    if len(sys.argv) < 2 or sys.argv[1] not in actions:
        return False
    action = sys.argv[1]
    try:
        _, output = call_control(action)
        print(output)
        return True
    except Exception as exc:
        print(f"CALL_FAILED {exc}", file=sys.stderr)
        return True


def main() -> int:
    global WINDOW_PROC, HWND, ICON_HANDLE, TASKBAR_CREATED

    if os.name != "nt":
        print("pet-tray.py 只支持 Windows", file=sys.stderr)
        return 2

    if bind_cli():
        return 0

    desktop_note = attach_to_interactive_desktop()
    log(f"desktop: {desktop_note}")

    if user32.FindWindowW(WINDOW_CLASS, None):
        log("tray already running on this desktop; second instance exited")
        return 0

    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass

    instance = kernel32.GetModuleHandleW(None)
    TASKBAR_CREATED = user32.RegisterWindowMessageW("TaskbarCreated")

    ICON_HANDLE = user32.LoadImageW(
        None,
        ICON_PATH,
        IMAGE_ICON,
        0,
        0,
        LR_LOADFROMFILE | LR_DEFAULTSIZE,
    )
    if not ICON_HANDLE:
        fallback_icon = ctypes.cast(
            ctypes.c_void_p(IDI_APPLICATION), ctypes.c_wchar_p
        )
        ICON_HANDLE = user32.LoadIconW(None, fallback_icon)

    WINDOW_PROC = WNDPROC(window_proc)
    window_class = WNDCLASSW()
    window_class.lpfnWndProc = ctypes.cast(WINDOW_PROC, ctypes.c_void_p)
    window_class.hInstance = instance
    window_class.hIcon = ICON_HANDLE
    window_class.lpszClassName = WINDOW_CLASS

    atom = user32.RegisterClassW(ctypes.byref(window_class))
    if not atom:
        log(f"RegisterClassW failed: {ctypes.get_last_error()}")
        return 3

    HWND = user32.CreateWindowExW(
        0,
        WINDOW_CLASS,
        "BaishuangPetTray",
        0,
        0,
        0,
        0,
        0,
        None,
        None,
        instance,
        None,
    )
    if not HWND:
        log(f"CreateWindowExW failed: {ctypes.get_last_error()}")
        return 4

    add_icon()
    threading.Thread(target=codex_watch_worker, daemon=True).start()

    hotkey_open = user32.RegisterHotKey(
        HWND, HOTKEY_OPEN, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("B")
    )
    hotkey_close = user32.RegisterHotKey(
        HWND,
        HOTKEY_CLOSE,
        MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT,
        ord("B"),
    )
    if not hotkey_open:
        log("RegisterHotKey Ctrl+Alt+B failed (already in use?)")
    if not hotkey_close:
        log("RegisterHotKey Ctrl+Alt+Shift+B failed (already in use?)")

    try:
        with open(PID_PATH, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
    except Exception:
        pass
    log(
        f"tray started pid={os.getpid()} hotkey_open={bool(hotkey_open)} "
        f"hotkey_close={bool(hotkey_close)}"
    )
    balloon(
        "白霜托盘已就绪",
        "Ctrl+Alt+B 打开；右键菜单。"
        if hotkey_open
        else "托盘已就绪；右键菜单可用。",
    )

    message = wt.MSG()
    while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(message))
        user32.DispatchMessageW(ctypes.byref(message))

    user32.UnregisterHotKey(HWND, HOTKEY_OPEN)
    user32.UnregisterHotKey(HWND, HOTKEY_CLOSE)
    remove_icon()
    if ICON_HANDLE:
        user32.DestroyIcon(ICON_HANDLE)
    try:
        os.remove(PID_PATH)
    except Exception:
        pass
    log("tray exited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
