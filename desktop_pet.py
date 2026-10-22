#!/usr/bin/env python3
"""白霜桌面精灵（独立版）

透明置顶小窗 + 自绘云朵气泡 + 完整交互状态机。为什么不用 Codex 内置桌宠：
pet.json 只有 5 个字段，气泡、对白、保持时间、余额查询都在应用侧写死，插件无法介入。

交互约定
    单击        对话互动（按当前状态决定台词与姿态）
    快速连点    气急败坏「干什么？烦不烦！」
    鼠标悬停    只"抬头看鼠标"，不触发变身动画
    拖动        移动位置
    右键菜单    说句话 / 查余额 / 退出

只依赖标准库（tkinter + urllib）。帧图需先用 prepare_frames.py 处理成绿底硬边 PNG。
"""

from __future__ import annotations

import json
import faulthandler
import math
import os
import pathlib
import queue
import random
import re
import sqlite3
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from datetime import date, datetime, time as clock_time, timedelta, timezone

from bubble_shape import (
    BUBBLE_FILL,
    BUBBLE_STROKE,
    BUBBLE_TEXT,
    cloud_contains_normalized,
    cloud_points,
)

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

CHROMA = "#00ff00"          # 透明色（角色图中没有纯绿）
# 素材放大倍数。2026-10-15：1.5 -> 2.25（帧 432x468），配套的帧也一起重做了。
# 配合 DPI 感知，150% 缩放下她是 1:1 物理像素，不再被系统拉伸。
SCALE = 2.25
FRAME_MS = 120              # 帧间隔
TRANS_FRAME_MS = 140        # 过渡帧的基准间隔：比普通帧慢，变身过程才看得清
LONG_STATE_MIN_FRAMES = 20   # waving/waiting 的 69 帧状态内演出
LONG_STATE_FRAME_MS = 33     # 按 30fps 播，不被 120ms 的状态帧间隔拖慢
LONG_STATE_TAIL_FRAMES = 36  # 末尾 04 保持段长度
TRANS_MIDDLE_BOOST = 1.6    # 过渡正中那帧两侧的加时倍数
TRANS_MIDDLE_HOLD_MS = 8000 # 过渡正中那帧的停留时长：那一帧没有任何光效遮挡，是给人看清的
                            # 2026-10-15：5000 -> 8000（用户要求更久）
LONG_TRANS_MIN_FRAMES = 20  # 2026-10-18：running 四组已换成 30fps 长序列
LONG_TRANS_FRAME_MS = 33    # 长序列按原生 30fps 播，不再套 140ms + 8s 正中定格
HOLD_FRAME_MS = 340         # 保持期"呼吸"的帧间隔（比正常慢，才像呼吸而不是抖）
HOLD_MS = 15000             # 变身姿态与气泡的停留时间：15 秒
MULTI_CLICK_WINDOW = 0.9    # 多久内的连续点击算"多次点按"
MULTI_CLICK_LIMIT = 3       # 达到这个次数就炸毛
DRAG_SLOP = 8               # 按下后位移不超过这么多像素才算"点击"（原来是 4；触控板轻点很容易
                            # 漂移出 4 像素，于是被当成拖动——用户的感觉就是"点了没反应"）
IDLE_PEEK_MS = 25000        # 多久没互动就"偷偷看一眼"
WORK_FRESH_SECONDS = 30     # Codex 实时日志多久内有回合活动 = 正在工作
WORK_IDLE_SECONDS = 75      # 要连续这么久没活动才算"收工"（比 30 秒长得多：单一阈值会让
                            # "写一下停一下"直接变成 running/review 来回变身）
DSH_WORK_FRESH_SECONDS = 12.0
DSH_WORK_IDLE_SECONDS = 35.0
WORK_CHECK_SECONDS = 5.0    # 多久查一次"是否在工作"
ALIVE_CHECK_SECONDS = 10.0  # 多久查一次"Codex 是否还开着"
TOPMOST_REASSERT_SECONDS = 0.6   # 多久重申一次置顶（360壁纸这类全屏置顶程序会反复抢）
EXTRA_ACTION_FRAME_MS = 83       # 导入动作已抽成 12fps
EXTRA_IDLE_TRIGGER_SECONDS = 35.0
EXTRA_IDLE_CHECK_SECONDS = 7.0
EXTRA_IDLE_TRIGGER_PROBABILITY = 0.18
TRACKING_RADIUS_PX = 320.0
TRACKING_MAX_X = 8.0
TRACKING_MAX_Y = 4.0
ANIMATION_IDLE_BREATH_PX = 1.0
BEIJING_TZ = timezone(timedelta(hours=8))
DEEPSEEK_PEAK_WINDOWS = (
    (clock_time(9, 0), clock_time(12, 0)),
    (clock_time(14, 0), clock_time(18, 0)),
)
# 2026 年中国大陆法定节假日与调休工作日。官方年度安排发布后按年更新。
CN_2026_HOLIDAY_RANGES = (
    (date(2026, 1, 1), date(2026, 1, 3)),
    (date(2026, 2, 15), date(2026, 2, 23)),
    (date(2026, 4, 4), date(2026, 4, 6)),
    (date(2026, 5, 1), date(2026, 5, 5)),
    (date(2026, 6, 19), date(2026, 6, 21)),
    (date(2026, 9, 25), date(2026, 9, 27)),
    (date(2026, 10, 1), date(2026, 10, 7)),
)
CN_2026_MAKEUP_WORKDAYS = frozenset({
    date(2026, 1, 4),
    date(2026, 2, 14),
    date(2026, 2, 28),
    date(2026, 5, 9),
    date(2026, 9, 20),
    date(2026, 10, 10),
})

LOG_PATH = pathlib.Path(__file__).with_name("pet.log")
PID_PATH = pathlib.Path(__file__).with_name("pet.pid")      # 单实例标记：里面是本实例的 PID
FAULT_PATH = pathlib.Path(__file__).with_name("pet-fault.log")
PET_MODE_PATH = pathlib.Path(__file__).with_name("pet-mode.txt")
STARTUP_ANIMATION_DIR = pathlib.Path(__file__).with_name("startup-animation") / "frames"
STARTUP_ANIMATION_REQUEST = pathlib.Path(__file__).with_name("startup-animation.request")
BUBBLE_FONT_PATH = (
    pathlib.Path(__file__).with_name("fonts")
    / "Yozai-0.868"
    / "Yozai-Regular.ttf"
)
BUBBLE_FONT_FAMILY = "悠哉字体"
BUBBLE_FONT_FALLBACK = "Microsoft YaHei"
BUBBLE_FONT_SIZE = 18
_BUBBLE_FONT_LOADED = False
STARTUP_ANIMATION_FPS = 24
STARTUP_ANIMATION_WIDTH = 960
STARTUP_ANIMATION_HEIGHT = 540
# frame_0488 中 Q 版角色最低点约在 (489, 495)；桌宠 sprite 的可见脚底
# 距离 432x468 帧图底边约 23px。把两个脚底锚点重合，动画结束后角色就不会跳位。
STARTUP_ANIMATION_Q_ANCHOR = (489, 495)
PET_SPRITE_BOTTOM_GAP = 23
_fault_handle = None


def register_bubble_font() -> bool:
    """把随应用打包的悠哉字体注册到当前进程，不修改系统字体目录。"""
    global _BUBBLE_FONT_LOADED
    if sys.platform != "win32" or not BUBBLE_FONT_PATH.is_file():
        _BUBBLE_FONT_LOADED = False
        return False
    try:
        # FR_PRIVATE：字体只对白霜进程可见，退出后自动从会话字体表移除。
        added = ctypes.windll.gdi32.AddFontResourceExW(
            str(BUBBLE_FONT_PATH), 0x10, 0
        )
    except (AttributeError, OSError):
        _BUBBLE_FONT_LOADED = False
        return False
    _BUBBLE_FONT_LOADED = added > 0
    return _BUBBLE_FONT_LOADED


def bubble_font_family() -> str:
    return BUBBLE_FONT_FAMILY if _BUBBLE_FONT_LOADED else BUBBLE_FONT_FALLBACK


def other_instance_pid() -> int | None:
    """pet.pid 里记着上一只的 PID；那只还活着就返回它，避免同时跑出好几只。

    这里刻意不用任何外部命令：这台机器上 `Get-CimInstance Win32_Process` 被拒绝访问、
    `tasklist` 也拿不到结果（都实测过），于是"查进程"的写法会悄悄失效、每双击一次就多出一只。
    直接用 kernel32 开句柄问系统：拿得到句柄就说明那只还活着，再核一下镜像名是 python*。
    """
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    if pid == os.getpid():
        return None
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)      # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            size = wintypes.DWORD(4096)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                name = pathlib.Path(buffer.value).name.lower()
                if "python" in name:
                    return pid
            return None
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001
        return None
# 心跳日志：设环境变量 PET_TRACE=1 启动时，每次 tick 记一行（状态/帧号/间隔）。
# 排查"播放卡顿"用——正常使用不用开，它会把日志刷得很大。
TRACE = os.environ.get("PET_TRACE") == "1"


def transition_total_ms(count: int = 7) -> int:
    """一段过渡的总毫秒数（含正中那帧的定格）。

    给"连环演出"排时序用：过渡从第 1 帧播到第 7 帧才算走完，之后才轮到下一个动作。
    改 TRANS_FRAME_MS / TRANS_MIDDLE_HOLD_MS 后这里会自动跟着变，不用手改数字。
    """
    if count >= LONG_TRANS_MIN_FRAMES:
        return count * LONG_TRANS_FRAME_MS
    middle = (count - 1) // 2
    span = max(1, middle)
    total = TRANS_MIDDLE_HOLD_MS
    for index in range(count):
        if index == middle:
            continue
        closeness = max(0.0, 1.0 - abs(index - middle) / span)
        total += int(round(TRANS_FRAME_MS * (1.0 + (TRANS_MIDDLE_BOOST - 1.0) * closeness)))
    return total
# pythonw 没有控制台，调用 tasklist 这类控制台程序会为每次调用弹出黑窗，
# 必须显式禁止创建窗口，否则会疯狂闪窗。
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0

# ---------------------------------------------------------------- 桌面归属
# 从 Codex（对话框或它自带的终端）启动时，进程会被放进一个隐藏桌面
# （CodexSandboxDesktop-<hash>）。窗口建在那里，用户在真实桌面上永远看不到，
# 表现就是"双击/输入后打不开"；而且隐藏桌面上 GetCursorPos 拿不到真实光标，
# 视线追踪也会失灵。建窗之前把本线程挂到交互桌面即可彻底解决。
_DESKTOP_RIGHTS = 0x0001 | 0x0002 | 0x0040   # READOBJECTS | CREATEWINDOW | WRITEOBJECTS
_desktop_keepalive: list[object] = []        # 句柄必须存活到进程结束
UOI_NAME = 2


def _object_name(handle) -> str:
    if not handle:
        return "<null>"
    need = ctypes.wintypes.DWORD()
    ctypes.windll.user32.GetUserObjectInformationW(handle, UOI_NAME, None, 0, ctypes.byref(need))
    buffer = ctypes.create_unicode_buffer(max(need.value, 2))
    ctypes.windll.user32.GetUserObjectInformationW(
        handle, UOI_NAME, buffer, need.value, ctypes.byref(need)
    )
    return buffer.value


def current_desktop() -> str:
    if sys.platform != "win32":
        return "-"
    try:
        handle = ctypes.windll.user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
        return _object_name(handle)
    except Exception:  # noqa: BLE001
        return "<读不到>"


def attach_to_interactive_desktop() -> str:
    """把当前线程挂到用户正在看的那个桌面，返回一行可供日志的诊断文本。"""
    if sys.platform != "win32":
        return "非 Windows，跳过桌面检查"
    before = current_desktop()
    try:
        user32 = ctypes.windll.user32
        target = user32.OpenInputDesktop(0, False, _DESKTOP_RIGHTS)
        if not target:
            target = user32.OpenDesktopW("Default", 0, False, _DESKTOP_RIGHTS)
        if not target:
            return f"桌面={before}，且无法打开交互桌面（错误 {ctypes.get_last_error()}）"
        name = _object_name(target)
        if name == before:
            return f"桌面={before}（无需切换）"
        if not user32.SetThreadDesktop(target):
            return f"桌面={before} -> 切到 {name} 失败（错误 {ctypes.get_last_error()}）"
        _desktop_keepalive.append(target)
        return f"桌面已从 {before} 切换到 {name}（否则窗口会开在隐藏桌面上看不见）"
    except Exception as exc:  # noqa: BLE001
        return f"桌面切换异常：{type(exc).__name__}: {exc}"


def enable_dpi_awareness() -> str:
    """声明本进程是 DPI 感知的。

    不声明的话，150% 缩放下 Windows 会把整个窗口按 1.5 倍拉伸——那正是"画面发虚"的根因。
    声明之后 Tk 的坐标系就是物理像素，288x312 的帧正好 1:1 映射到屏幕上。
    必须在创建任何窗口之前调用。
    """
    if sys.platform != "win32":
        return "非 Windows，跳过 DPI 设置"
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # PER_MONITOR_AWARE_V2
        return "DPI 感知已启用（PER_MONITOR_AWARE_V2）"
    except Exception:  # noqa: BLE001
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)                            # PER_MONITOR_AWARE
        return "DPI 感知已启用（shcore 回退）"
    except Exception as exc:  # noqa: BLE001
        return f"DPI 感知设置失败：{type(exc).__name__}"


def log(message: str) -> None:
    try:
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {message}\n")
    except OSError:
        pass


def hidden_run(command: list[str], timeout: float = 15.0):
    """后台执行命令且绝不弹出窗口（pythonw 环境下的关键细节）。"""
    startup = None
    if sys.platform == "win32":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
    return subprocess.run(
        command, capture_output=True, text=True, timeout=timeout,
        startupinfo=startup, creationflags=_NO_WINDOW,
    )


def cursor_pos() -> tuple[int, int] | None:
    """系统级鼠标位置。绑窗口的 <Motion> 只在鼠标位于窗口上时才触发，
    要"鼠标在桌面任何位置都跟过去看"必须直接问系统。"""
    if sys.platform != "win32":
        return None
    try:
        point = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        if point.x == 0 and point.y == 0:
            return None      # 受限环境读不到真实位置，当作"没有光标信息"
        return int(point.x), int(point.y)
    except Exception:  # noqa: BLE001
        return None


def foreground_hwnd() -> int:
    """返回当前前台窗口句柄；受限环境返回 0。"""
    if sys.platform != "win32":
        return 0
    try:
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.wintypes.HWND
        return int(user32.GetForegroundWindow() or 0)
    except Exception:  # noqa: BLE001
        return 0


def restore_foreground(hwnd: int) -> None:
    """把键盘焦点还给显示桌宠前的应用，失败时静默。"""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow.argtypes = [ctypes.wintypes.HWND]
        if int(user32.GetForegroundWindow() or 0) != hwnd:
            user32.SetForegroundWindow(ctypes.wintypes.HWND(hwnd))
    except Exception:  # noqa: BLE001
        pass


def load_pet_mode() -> str:
    """读取持久化模式；默认立绘模式，未知内容也按立绘模式处理。"""
    try:
        mode = PET_MODE_PATH.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return "portrait"
    return "animation" if mode == "animation" else "portrait"


class StartupAnimationPlayer:
    """Play the pre-extracted startup video as a borderless Tk window."""

    def __init__(
        self,
        master: tk.Misc,
        frames_dir: pathlib.Path,
        on_start=None,
        on_finish=None,
    ) -> None:
        self.master = master
        self.frames_dir = frames_dir
        self.frames = sorted(frames_dir.glob("frame_*.png")) if frames_dir.is_dir() else []
        self.on_start = on_start
        self.on_finish = on_finish
        self.window: tk.Toplevel | None = None
        self.canvas: tk.Canvas | None = None
        self.image_id: int | None = None
        self.photo: tk.PhotoImage | None = None
        self.after_id: str | None = None
        self.started_at = 0.0
        self.last_index = -1
        self.previous_foreground = 0

    @property
    def active(self) -> bool:
        return bool(self.window and self.window.winfo_exists())

    def play(self) -> bool:
        if not self.frames:
            log(f"启动动画未播放：缺少帧目录 {self.frames_dir}")
            return False
        if self.active:
            log("启动动画已在播放，忽略重复启动请求")
            return False
        self.previous_foreground = foreground_hwnd()
        width, height = STARTUP_ANIMATION_WIDTH, STARTUP_ANIMATION_HEIGHT
        self.master.update_idletasks()
        # 不把动画固定在屏幕中央：以白霜当前窗口为基准对齐末帧脚底锚点。
        # 桌宠被拖到别处或从菜单重播时，动画也会在同一位置衔接。
        pet_left = int(self.master.winfo_rootx())
        pet_top = int(self.master.winfo_rooty())
        pet_width = int(self.master.winfo_width())
        pet_height = int(self.master.winfo_height())
        pet_foot_x = pet_left + pet_width // 2
        pet_foot_y = pet_top + pet_height - PET_SPRITE_BOTTOM_GAP
        anchor_x, anchor_y = STARTUP_ANIMATION_Q_ANCHOR
        x = pet_foot_x - anchor_x
        y = pet_foot_y - anchor_y
        self.window = tk.Toplevel(self.master)
        self.window.overrideredirect(True)
        self.window.configure(bg="#211927", highlightthickness=2, highlightbackground="#c9b4ff")
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.attributes("-topmost", True)
        if self.on_start is not None:
            self.on_start()
        self.canvas = tk.Canvas(
            self.window,
            width=width,
            height=height,
            bg="#ffffff",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        self.image_id = self.canvas.create_image(0, 0, anchor="nw")
        # 点击画面可跳过；Esc 在窗口获得焦点时同样可跳过。
        self.window.bind("<Button-1>", self.close)
        self.window.bind("<Escape>", self.close)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.started_at = time.monotonic()
        self.last_index = -1
        log(
            f"启动动画开始（{len(self.frames)} 帧，{STARTUP_ANIMATION_FPS}fps，"
            f"窗口={width}x{height}+{x}+{y}，脚底锚点=({anchor_x},{anchor_y})）"
        )
        self._show_frame()
        return True

    def _show_frame(self) -> None:
        if not self.active or self.canvas is None or self.image_id is None:
            return
        elapsed = time.monotonic() - self.started_at
        index = int(elapsed * STARTUP_ANIMATION_FPS)
        if index >= len(self.frames):
            self.close()
            return
        try:
            self.photo = tk.PhotoImage(file=str(self.frames[index]))
            self.canvas.itemconfig(self.image_id, image=self.photo)
        except tk.TclError as exc:
            log(f"启动动画帧读取失败：{self.frames[index].name}: {exc}")
            self.close()
            return
        self.last_index = index
        next_index = index + 1
        delay_ms = max(1, int((next_index / STARTUP_ANIMATION_FPS - elapsed) * 1000))
        self.after_id = self.master.after(delay_ms, self._show_frame)

    def close(self, _event=None, *, notify: bool = True) -> None:
        was_active = self.active
        if self.after_id is not None:
            try:
                self.master.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
        self.window = None
        self.canvas = None
        self.image_id = None
        self.photo = None
        if self.last_index >= 0:
            log(f"启动动画结束（停在第 {self.last_index + 1} 帧）")
            self.last_index = -1
        if notify and was_active and self.on_finish is not None:
            self.on_finish()

IDLE_CHAT = ["嗯？有事？", "干什么？"]
# 非工作状态单击的两种反应（台词, 姿态/气泡配色）：抬头看你 / 害羞。
# 2026-10-15：这两句以前只出现在"干活被点"那条连环演出的尾巴上，
# 非工作状态的单击分支整个漏了（chat() 里只有"连点炸毛"和"干活被点"两条路），
# 于是平常点她一点反应都没有——表现就是"单点经常/永远没反应"。
NONWORK_CLICK_REPLIES = (("嗯？有事？", "waving"), ("干什么？", "waiting"))
WORK_CHAT = "哼，这点小事都要我来吗，真是拿你没办法。"
WORK_CLICK_CHAT = "别来打扰我，没看见在忙吗。"
DONE_CHAT = "喏，弄完了，下次别来麻烦我。"
ANGRY_CHAT = "干什么？烦不烦！"
HELLO_CHAT = "又要我帮忙了吗？真是的。"
BYE_CHAT = "要走了吗？哼，才不是舍不得呢。"
EAT_CHAT = "就吃一小口……应该不会被发现吧。"
PEEK_CHAT = "只看一眼，就一眼。"
GAME_CHAT = "就玩一小会儿，真的。"
GAME_LOOP_CHAT = "嗯~ o(*￣▽￣*)o 巴适滴板"
WORK_HAPPY_CHAT = "啊，终于结束了，可以休息一下了~"
DUAL_WORK_CHAT = "哼，你这家伙到底要让我干什么啊"
BALANCE_NETWORK_BLOCKED_CHAT = "禁网：双击启动器重开。"
BUBBLE_MAX_TEXT_WIDTH_RATIO = 0.86
BUBBLE_WRAP_STEP_PX = 6
CAUGHT_CHAT = "谁、谁在玩？我只是检查一下它有没有电。"
ACTION_BUBBLES = {
    "eating": EAT_CHAT,
    "peeking": PEEK_CHAT,
    "gaming": GAME_CHAT,
    "fidget_a": ANGRY_CHAT,
    "work_a": WORK_CHAT,
    "work_b": DONE_CHAT,
    "happy": WORK_HAPPY_CHAT,
    "shy_a": BYE_CHAT,
    "shy_b": BYE_CHAT,
}
DISABLED_EXTRA_ACTIONS = frozenset({"shy_b"})

# 2026-10-18：气泡统一成白云 + 淡紫描边 + 淡紫字（用户指定）。
# 配色常量在 bubble_shape.py，桌面端与样图共用同一份几何和颜色。

# 逻辑状态 -> 实际帧目录。look 由 16 个视线帧按鼠标方位实时选取，不走状态机。
STATE_DIRS = {
    "idle": "idle",
    "wave": "waving",
    "running": "running",       # 双手掐腰低头（工作姿态）
    "review": "review",         # 昂首（完成姿态）
    "failed": "failed",         # 抱胸跺脚（生气姿态）
    "jumping": "jumping",       # 跺脚
    "waiting": "waiting",       # 歪头举手（近似"害羞/等你"）
    "shy": "waiting",
    "look": "look-row-9",
    "drag-right": "running-right",
    "drag-left": "running-left",
}


_BUBBLE_CONTAINMENT_SAMPLES = (-1.0, -0.5, 0.0, 0.5, 1.0)


def bubble_contains_text_rect(
    bubble_width: float,
    bubble_height: float,
    text_width: float,
    text_height: float,
    clearance: float,
) -> bool:
    """文字矩形连同安全边距必须完整落在云朵内部。"""
    if bubble_width <= 0 or bubble_height <= 0:
        return False
    nx = (text_width / 2 + clearance) / bubble_width
    ny = (text_height / 2 + clearance) / bubble_height
    if nx >= 0.5 or ny >= 0.5:
        return False
    return all(
        cloud_contains_normalized(sx * nx, sy * ny)
        for sy in _BUBBLE_CONTAINMENT_SAMPLES
        for sx in _BUBBLE_CONTAINMENT_SAMPLES
    )


def fit_bubble_dimensions(
    text_width: float,
    text_height: float,
    min_width: float,
    max_width: float,
    min_height: float,
    max_height: float,
    clearance: float,
) -> tuple[float, float] | None:
    """在画布约束内寻找最小的云朵尺寸，使整块文字矩形都在内部。"""
    min_width = max(min_width, text_width + 2 * clearance)
    min_height = max(min_height, text_height + 2 * clearance)
    if min_width > max_width or min_height > max_height:
        return None

    best: tuple[float, float] | None = None
    best_area = math.inf
    width = min_width
    while width <= max_width:
        if not bubble_contains_text_rect(
            width, max_height, text_width, text_height, clearance
        ):
            width += 4.0
            continue
        lo, hi = min_height, max_height
        for _ in range(12):
            mid = (lo + hi) / 2
            if bubble_contains_text_rect(
                width, mid, text_width, text_height, clearance
            ):
                hi = mid
            else:
                lo = mid
        area = width * hi
        if area < best_area:
            best_area = area
            best = (width, hi)
        width += 8.0
    return best


class Pet:
    def __init__(self, frames_root: pathlib.Path, debug: bool = False) -> None:
        self.debug = debug
        # 必须在 tk.Tk() 之前切换桌面：一旦线程有了窗口就再也切不动了
        self.desktop_note = attach_to_interactive_desktop()
        self.root = tk.Tk()
        # 启动阶段先隐藏本体，等入场动画结束时再以不抢焦点的方式显示。
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        if debug:
            # 诊断模式：用不透明的可见背景 + 边框，确认窗口到底有没有显示出来
            self.root.configure(bg="#ffffff", highlightthickness=2,
                                highlightbackground="#7c5cd6")
        else:
            try:
                self.root.attributes("-transparentcolor", CHROMA)
            except tk.TclError as exc:
                log(f"透明色设置失败（Tk 版本差异？）：{exc}")
            self.root.configure(bg=CHROMA)

        self.frames_root = frames_root
        self.cache: dict[str, list[tk.PhotoImage]] = {}
        self.states = sorted(p.name for p in frames_root.iterdir() if p.is_dir())

        self.width = int(round(192 * SCALE))
        self.height = int(round(208 * SCALE))
        bg_color = "#ffffff" if debug else CHROMA
        # 窗口高度：正常是"气泡区 + 角色区"两倍高，debug 模式只留角色区
        self.canvas_height = self.height * (1 if debug else 2)
        self.canvas = tk.Canvas(
            self.root, width=self.width, height=self.canvas_height,
            bg=bg_color, highlightthickness=0, bd=0,
        )
        self.canvas.pack()
        # 角色画在下半部分，上半部分留给气泡
        self.sprite_id = self.canvas.create_image(
            self.width // 2, self.canvas_height, anchor="s"
        )

        self.state = "idle"
        self.frame_index = 0
        self.state_until = 0.0
        self.last_click = 0.0
        self.click_count = 0
        self.last_interaction = time.time()
        self._bubble_deadline = 0.0
        self._codex_working = False
        self._dsh_working = False
        self._dual_work_active = False
        self._work_entry_pending: str | None = None
        self._work_entry_pending_at = 0.0
        self.was_codex_working = self.codex_working()
        self.was_dsh_working = self.dsh_working()
        # 启动时若工作已经在进行，也让首个检查周期补播一次进入工作。
        self.was_working = False
        self._last_pointer: tuple[int, int] | None = None
        self._peek_override: tuple[str, int] | None = None
        self._working = self.was_working
        self._shown = None          # 当前画面上那张 PhotoImage，用来跳过没必要的重绘
        self._alive = True
        self._next_work_check = 0.0
        self._next_alive_check = 0.0
        self._next_topmost = 0.0
        self.play_once = False
        self._pending: tuple[str, float, bool, int] | None = None
        self._middle_hold = True
        self._breathe_alive = False      # 定格期间的呼吸循环是否在工作
        self._breathe_cycle = 0
        self.breathe_cache: dict[str, list[tk.PhotoImage]] = {}
        self._hold_cycle = 0
        self._balance_busy = False
        self._balance_queue: queue.Queue[str] = queue.Queue()
        # Tk 9 在当前桌面环境无法分配原生 Menu，右键菜单改用自绘 Toplevel。
        self._context_menu: tk.Toplevel | None = None
        self._mode_selector: tk.Toplevel | None = None
        self._menu_restore_foreground = 0
        self._selector_restore_foreground = 0
        self._last_context_menu_at = 0.0
        self._pet_mode = load_pet_mode()
        self._extra_menu_mode = self._pet_mode == "animation"
        self._extra_action_dirs = {
            "eating": ("anim-idle-eat",),
            "peeking": ("anim-idle-peek",),
            "gaming": ("anim-game-intro", "anim-game-loop"),
            "caught": ("anim-caught-playing",),
            "fidget_a": ("anim-multi-click-a",),
            "fidget_b": ("anim-multi-click-b",),
            "shy_a": ("anim-work-stop-a",),
            "shy_b": ("anim-work-stop-b",),
            "happy": ("anim-work-success-b",),
            "protest_a": ("anim-click-protest-a",),
            "protest_b": ("anim-click-protest-b",),
            "work_a": ("anim-work-start",),
            "work_intro": ("anim-work-intro",),
            "work_hold": ("anim-work-hold",),
            "work_b": ("anim-work-success-a",),
        }
        self._extra_sequence: list[str] = []
        self._next_extra_idle_check = 0.0
        self._startup_animation_hidden = False
        self._last_startup_animation_started = 0.0
        self._startup_animation = StartupAnimationPlayer(
            self.root,
            STARTUP_ANIMATION_DIR,
            on_start=self._hide_for_startup_animation,
            on_finish=self._show_after_startup_animation,
        )
        self._next_animation_request_check = 0.0

        self._place_bottom_right()
        self._bind()
        if self._extra_menu_mode:
            self.say(HELLO_CHAT, hold=True)
            self.set_state("idle")
        else:
            self.say(HELLO_CHAT, hold=True, tone="wave")
            self.set_state("wave", ms=4000)
        log(f"桌宠启动（debug={debug}，{self.desktop_note}）")
        self.root.after(800, self._log_geometry)
        # 首次启动时系统可能暂时让窗口落在 (0,0)。等 2 秒校正后再播放，
        # 动画才能以真正稳定的桌宠坐标为锚点。
        self.root.after(2000, self._play_startup_after_placement)
        self.root.after(1200, self._prewarm)
        self._tick()

    def _prewarm(self) -> None:
        """空闲时逐个把状态目录的帧读进缓存。

        不预热的话，第一次进入某个状态要现场解码 6~7 张 PNG（十几到几十毫秒），
        那一下就是明显的"顿"。首屏先出来，再慢慢补，用户看不到加载过程。
        """
        for directory in self.states:
            # 导入动作帧数较多，按需加载，避免启动时占用数百 MB 内存。
            if directory.startswith("anim-"):
                continue
            if directory in self.cache:
                continue
            self.frames(directory)
            self.root.after(60, self._prewarm)
            return
        log(f"帧预热完成（{len(self.cache)} 组）")

    def _log_geometry(self) -> None:
        log(
            f"窗口几何={self.root.geometry()} viewable={self.root.winfo_viewable()} "
            f"屏幕={self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()} "
            f"透明色={'-' if self.debug else CHROMA} 桌面={current_desktop()}"
        )

    # ---------------------------------------------------------------- 帧
    def frames(self, state: str) -> list[tk.PhotoImage]:
        directory_name = STATE_DIRS.get(state, state)
        if directory_name in self.cache:
            return self.cache[directory_name]
        directory = self.frames_root / directory_name
        images: list[tk.PhotoImage] = []
        if directory.is_dir():
            for path in sorted(directory.glob("*.png")):
                try:
                    images.append(tk.PhotoImage(file=str(path)))
                except tk.TclError:
                    continue
            breathe = directory / "breathe"      # 定格帧的呼吸变体（子目录，不进主序列）
            if breathe.is_dir():
                variants = []
                for path in sorted(breathe.glob("*.png")):
                    try:
                        variants.append(tk.PhotoImage(file=str(path)))
                    except tk.TclError:
                        continue
                if variants:
                    self.breathe_cache[directory_name] = variants
        if not images and directory_name != "idle":
            images = self.frames("idle")
        self.cache[directory_name] = images
        return images

    # ---------------------------------------------------------------- 定格呼吸
    def _breathe_step(self) -> None:
        if not self._breathe_alive:
            return
        variants = self.breathe_cache.get(self.state, [])
        if variants:
            self._breathe_cycle = (self._breathe_cycle + 1) % len(variants)
            image = variants[self._breathe_cycle]
            if image is not self._shown:
                self.canvas.itemconfig(self.sprite_id, image=image)
                self._shown = image
        self.root.after(HOLD_FRAME_MS, self._breathe_step)

    def _update_breathe(self, count: int) -> None:
        """定格那 5 秒里循环 ±1 像素的呼吸帧：完全不动会被当成卡死。"""
        holding = (
            self._middle_hold
            and self.state.startswith("trans-")
            and count > 2
            and count < LONG_TRANS_MIN_FRAMES
            and self.frame_index == (count - 1) // 2
        )
        if holding and not self._breathe_alive:
            self._breathe_alive = True
            self._breathe_cycle = 0
            self.root.after(HOLD_FRAME_MS, self._breathe_step)
        elif not holding and self._breathe_alive:
            self._breathe_alive = False

    def look_frame(self, pointer_x: int, pointer_y: int) -> tuple[str, int]:
        """按鼠标相对桌宠的方位，从 16 个视线帧里挑最接近的一档（22.5 度为一档）。

        这是"看向鼠标"的实现：只换帧、不切状态，所以悬停时绝不会触发变身动画。
        """
        center_x = self.root.winfo_x() + self.width // 2
        base_y = self.root.winfo_y() + self.canvas_height
        dx = pointer_x - center_x
        dy = base_y - pointer_y
        degree = math.degrees(math.atan2(dx, dy)) % 360.0
        index = int(round(degree / 22.5)) % 16
        directory = "look-row-9" if index < 8 else "look-row-10"
        return directory, index % 8

    # ---------------------------------------------------------------- 窗口
    def _work_area(self) -> tuple[int, int, int, int]:
        """可用桌面区域（不含任务栏）。

        不能只信 Tk 的 winfo_screen*：屏幕被别的全屏程序接管时它会返回 0，
        我们的兜底就会把窗口摆到左上角。这里优先问 Win32。
        """
        if sys.platform == "win32":
            try:
                rect = ctypes.wintypes.RECT()
                if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                    width, height = rect.right - rect.left, rect.bottom - rect.top
                    if width > 200 and height > 200:
                        return rect.left, rect.top, rect.right, rect.bottom
            except Exception:  # noqa: BLE001
                pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _place_bottom_right(self) -> None:
        self.root.update_idletasks()
        left, top, right, bottom = self._work_area()
        height = self.canvas_height
        if right - left < 200 or bottom - top < 200:
            # 连工作区都读不到：用一个保守的默认位置，而不是 (0,0)
            x, y = 1200, 400
        else:
            x = right - left - self.width - 80
            y = bottom - top - height - 60
            x = max(left, min(x + left, right - self.width))
            y = max(top, min(y + top, bottom - height))
        self.root.geometry(f"{self.width}x{height}+{x}+{y}")

    def _recheck_placement(self) -> None:
        """启动时屏幕指标读不到（被全屏程序占用）的话，稍后再摆一次。"""
        geometry = self.root.geometry()
        if geometry.startswith(f"{self.width}x{self.canvas_height}+0+0"):
            log("窗口落在了 (0,0)，重新摆放")
            self._place_bottom_right()
            log(f"重新摆放后几何={self.root.geometry()}")

    def _play_startup_after_placement(self) -> None:
        """先校正首次启动位置，再以桌宠脚底为锚点播放开场动画。"""
        self._recheck_placement()
        self.root.update_idletasks()
        if not self.play_startup_animation() and not self._startup_animation.active:
            self._show_pet_root_passively()

    def _set_topmost(self, topmost: bool) -> None:
        """设置/取消置顶，不移动、不缩放、不抢焦点。

        让位时用 HWND_BOTTOM 而不是 HWND_NOTOPMOST：后者只是退出置顶层，
        仍可能压在设置框上面；沉到底部才能保证菜单/设置框在她上面。
        """
        if sys.platform != "win32":
            return
        try:
            user32 = ctypes.windll.user32
            user32.SetWindowPos.argtypes = [
                ctypes.wintypes.HWND, ctypes.wintypes.HWND,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
            ]
            user32.SetWindowPos.restype = ctypes.wintypes.BOOL
            user32.GetAncestor.argtypes = [ctypes.wintypes.HWND, ctypes.c_uint]
            user32.GetAncestor.restype = ctypes.wintypes.HWND
            hwnd = user32.GetAncestor(self.root.winfo_id(), 2)      # GA_ROOT
            user32.SetWindowPos(
                ctypes.wintypes.HWND(hwnd),
                ctypes.wintypes.HWND(-1 if topmost else 1),          # TOPMOST / BOTTOM
                0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010,                # NOMOVE|NOSIZE|NOACTIVATE
            )
        except Exception:  # noqa: BLE001
            pass

    def _bind(self) -> None:
        # Canvas 覆盖整个窗口；只在这里绑定，避免 Canvas 与根窗口的 bindtag
        # 对同一次点击各触发一遍（右键会连续建两个菜单，后一个把前一个顶掉）。
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_menu)
        self.canvas.bind("<Motion>", self._on_motion)

    # ---------------------------------------------------------------- 交互
    def _on_menu(self, event) -> None:
        now = time.monotonic()
        if now - self._last_context_menu_at < 0.25:
            return "break"
        self._last_context_menu_at = now
        self._close_context_menu()
        self._close_mode_selector()
        self._menu_restore_foreground = foreground_hwnd()
        menu = tk.Toplevel(self.root)
        menu.withdraw()
        menu.overrideredirect(True)
        menu.attributes("-topmost", True)
        menu.configure(bg=BUBBLE_STROKE)

        body = tk.Frame(menu, bg=BUBBLE_FILL, padx=6, pady=6)
        body.pack(padx=1, pady=1, fill="both", expand=True)
        font = ("Microsoft YaHei UI", 10)

        def add_item(label: str, command, danger: bool = False) -> None:
            item = tk.Label(
                body,
                text=label,
                anchor="w",
                font=font,
                fg="#9b3658" if danger else BUBBLE_TEXT,
                bg=BUBBLE_FILL,
                padx=14,
                pady=7,
                cursor="hand2",
            )
            item.pack(fill="x")
            item.bind("<Enter>", lambda _e, w=item: w.configure(bg="#eee6ff"))
            item.bind("<Leave>", lambda _e, w=item: w.configure(bg=BUBBLE_FILL))
            item.bind("<Button-1>", lambda _e, c=command: self._activate_context_action(c))

        add_item("说句话", self.chat)
        add_item("查余额", self.show_balance)
        add_item("看动画", self.play_startup_animation)
        mode_label = "模式选择（动画）" if self._extra_menu_mode else "模式选择（立绘）"
        add_item(mode_label, self._open_mode_selector)
        if self._extra_menu_mode:
            separator = tk.Frame(body, bg="#e4d9f2", height=1)
            separator.pack(fill="x", padx=8, pady=4)
            add_item("吃东西", lambda: self.play_extra_action("eating"))
            add_item("偷看", lambda: self.play_extra_action("peeking"))
            add_item("玩游戏", lambda: self.play_extra_action("gaming"))
            add_item(
                "被抓包",
                lambda: self.play_extra_action("caught", show_caught_bubble=False),
            )
        separator = tk.Frame(body, bg="#e4d9f2", height=1)
        separator.pack(fill="x", padx=8, pady=4)
        add_item("退出", self._quit, danger=True)

        self._context_menu = menu
        log(f"右键菜单触发：屏幕坐标=({event.x_root}, {event.y_root})")
        menu.update_idletasks()
        menu_width = max(168, menu.winfo_reqwidth())
        menu_height = max(120, menu.winfo_reqheight())
        left, top, right, bottom = self._work_area()
        menu_x = min(max(left, event.x_root), max(left, right - menu_width))
        menu_y = min(max(top, event.y_root), max(top, bottom - menu_height))
        menu.geometry(f"{menu_width}x{menu_height}+{menu_x}+{menu_y}")
        menu.bind("<Escape>", lambda _e: self._close_context_menu())
        menu.bind("<FocusOut>", lambda _e: self.root.after_idle(self._close_context_menu))
        menu.deiconify()
        menu.lift()
        menu.focus_force()
        log("右键菜单已弹出")
        return "break"

    def _activate_context_action(self, command) -> None:
        self._close_context_menu()
        self.root.after_idle(command)

    def _close_context_menu(self) -> None:
        menu = self._context_menu
        self._context_menu = None
        if menu is not None:
            try:
                menu.destroy()
            except tk.TclError:
                pass
        previous = self._menu_restore_foreground
        self._menu_restore_foreground = 0
        if previous:
            self.root.after_idle(lambda: restore_foreground(previous))

    def _close_mode_selector(self) -> None:
        selector = self._mode_selector
        self._mode_selector = None
        if selector is not None:
            try:
                selector.destroy()
            except tk.TclError:
                pass
        previous = self._selector_restore_foreground
        self._selector_restore_foreground = 0
        if previous:
            self.root.after_idle(lambda: restore_foreground(previous))

    def _open_mode_selector(self) -> None:
        self._close_mode_selector()
        self._selector_restore_foreground = foreground_hwnd()
        selector = tk.Toplevel(self.root)
        selector.withdraw()
        selector.overrideredirect(True)
        selector.attributes("-topmost", True)
        selector.configure(bg=BUBBLE_STROKE)

        body = tk.Frame(selector, bg=BUBBLE_FILL, padx=6, pady=6)
        body.pack(padx=1, pady=1, fill="both", expand=True)
        font = ("Microsoft YaHei UI", 10)

        def add_option(mode: str, label: str) -> None:
            checked = "✓ " if self._pet_mode == mode else "   "
            item = tk.Label(
                body,
                text=checked + label,
                anchor="w",
                font=font,
                fg=BUBBLE_TEXT,
                bg=BUBBLE_FILL,
                padx=14,
                pady=8,
                cursor="hand2",
            )
            item.pack(fill="x")
            item.bind("<Enter>", lambda _e, w=item: w.configure(bg="#eee6ff"))
            item.bind("<Leave>", lambda _e, w=item: w.configure(bg=BUBBLE_FILL))
            item.bind(
                "<Button-1>",
                lambda _e, selected=mode: self.root.after_idle(
                    lambda: self._select_pet_mode(selected)
                ),
            )

        add_option("portrait", "立绘模式")
        add_option("animation", "动画模式")
        self._mode_selector = selector

        pointer = cursor_pos()
        if pointer is None:
            pointer = (self.root.winfo_rootx(), self.root.winfo_rooty())
        selector.update_idletasks()
        width = max(170, selector.winfo_reqwidth())
        height = max(90, selector.winfo_reqheight())
        left, top, right, bottom = self._work_area()
        x = min(max(left, pointer[0]), max(left, right - width))
        y = min(max(top, pointer[1]), max(top, bottom - height))
        selector.geometry(f"{width}x{height}+{x}+{y}")
        selector.bind("<Escape>", lambda _e: self._close_mode_selector())
        selector.bind(
            "<FocusOut>",
            lambda _e: self.root.after_idle(self._close_mode_selector),
        )
        selector.deiconify()
        selector.lift()
        selector.focus_force()
        log("模式选择菜单已弹出")

    def _select_pet_mode(self, mode: str) -> None:
        self._close_mode_selector()
        mode = "animation" if mode == "animation" else "portrait"
        if mode == self._pet_mode:
            return
        self._pet_mode = mode
        self._extra_menu_mode = mode == "animation"
        self._extra_sequence.clear()
        self._pending = None
        self._peek_override = None
        try:
            PET_MODE_PATH.write_text(mode, encoding="utf-8")
        except OSError as exc:
            log(f"模式记忆写入失败：{exc}")
        self.last_interaction = time.time()
        self._next_extra_idle_check = self.last_interaction + EXTRA_IDLE_CHECK_SECONDS
        self.set_state("idle", trans=False)
        if mode == "animation":
            self.say("动画模式。", hold=True)
            log("模式选择：动画模式")
        else:
            self.say("立绘模式。", hold=True)
            log("模式选择：立绘模式")

    def play_extra_action(
        self,
        action: str,
        *,
        show_caught_bubble: bool = False,
        show_action_bubble: bool = True,
        _keep_sequence: bool = False,
    ) -> None:
        """播放新接入的额外动作；素材不存在时安全回退，不改变当前状态。"""
        if action in DISABLED_EXTRA_ACTIONS:
            log(f"额外动作已停用：{action}")
            return
        if not _keep_sequence:
            self._extra_sequence.clear()
        names = getattr(self, "_extra_action_dirs", {}).get(action, ())
        state_name = next((name for name in names if name in self.states), None)
        if state_name is None:
            labels = {
                "eating": "吃东西",
                "peeking": "偷看",
                "gaming": "玩游戏",
                "caught": "被抓包",
            }
            label = labels.get(action, action)
            self.say(f"{label}动作还没接进来，等素材做好再说。", hold=True)
            log(f"额外动作未接入：{action}，候选目录={names}")
            return

        if show_action_bubble and action in ACTION_BUBBLES:
            self.say(ACTION_BUBBLES[action], hold=True)

        if action == "gaming" and state_name == "anim-game-intro":
            # 手动选择的游戏动画优先于工作排队，必须先进入游戏循环。
            self._work_entry_pending = None
            images = self.frames(state_name)
            duration_ms = max(1000, len(images) * EXTRA_ACTION_FRAME_MS)
            self.set_state(
                state_name,
                ms=duration_ms,
                hold=False,
                once=True,
                trans=False,
            )
            log(f"额外动作开始：gaming 入场 -> {state_name}，{len(images)} 帧")
            return

        if action == "gaming" and state_name == "anim-game-loop":
            self._start_gaming_loop()
            return

        if action == "work_hold":
            self.set_state(
                state_name,
                ms=10**12,
                hold=False,
                once=False,
                trans=False,
            )
            log("双工作流程进入工作保持循环")
            return

        images = self.frames(state_name)
        duration_ms = max(1000, len(images) * EXTRA_ACTION_FRAME_MS)
        self.set_state(
            state_name,
            ms=duration_ms,
            hold=False,
            once=True,
            trans=False,
        )
        if action == "caught" and show_caught_bubble:
            self.say(CAUGHT_CHAT, hold=True)
        log(f"额外动作开始：{action} -> {state_name}，{len(images)} 帧")

    def play_extra_sequence(self, actions: tuple[str, ...]) -> None:
        if not actions:
            return
        self._extra_sequence = list(actions[1:])
        self.play_extra_action(actions[0], _keep_sequence=True)

    def _enter_normal_work_state(self) -> None:
        if self._extra_menu_mode:
            self._extra_sequence = ["work_hold"]
            self.play_extra_action("work_a", _keep_sequence=True)
            log(
                "正常进入工作：完整动画 "
                f"{len(self.frames('anim-work-start'))} 帧 -> 稳定保持循环"
            )
        else:
            self.say(WORK_CHAT, hold=True, tone="running")
            self.set_state("running", hold=True)

    def _is_casual_animation_running(self) -> bool:
        if not self.state.startswith("anim-"):
            return False
        working_states = {
            "anim-work-start",
            "anim-work-intro",
            "anim-work-hold",
        }
        if self.state in working_states:
            return False
        return bool(self.frames(self.state))

    def _request_or_enter_work(self, dual: bool, now: float) -> None:
        mode = "dual" if dual else "normal"
        if self._is_casual_animation_running():
            self._work_entry_pending = mode
            self._work_entry_pending_at = now
            log(f"{mode} 工作已检测到，等待当前休闲动画播完：{self.state}")
            return
        self._work_entry_pending = None
        if dual:
            self._dual_work_active = True
            self._start_dual_work_loop()
        else:
            self._enter_normal_work_state()

    def _start_dual_work_loop(self) -> None:
        """多次点击反应 A -> 进入工作 -> 稳定保持循环。"""
        if "anim-multi-click-a" not in self.states:
            log("双工作反应素材缺失，回退普通工作状态")
            self._enter_normal_work_state()
            return
        self._extra_sequence = ["work_intro", "work_hold"]
        self.play_extra_action(
            "fidget_a",
            show_action_bubble=False,
            _keep_sequence=True,
        )
        self.say(DUAL_WORK_CHAT, hold=True)
        log("Codex 与 DSH 同时工作：反应 A -> 进入工作 -> 保持循环")

    def _start_gaming_loop(self) -> None:
        self._work_entry_pending = None
        if "anim-game-loop" not in self.states:
            log("游戏循环帧缺失，回退待机")
            self.set_state("idle")
            return
        self.set_state(
            "anim-game-loop",
            ms=10**12,
            hold=False,
            once=False,
            trans=False,
        )
        self.say(GAME_LOOP_CHAT, hold=True)
        log("额外动作进入游戏机循环段")

    def play_startup_animation(self) -> bool:
        now = time.monotonic()
        if self._startup_animation.active:
            log("启动动画请求已忽略：当前动画仍在播放")
            return False
        if now - self._last_startup_animation_started < 2.0:
            log("启动动画请求已忽略：启动冷却中")
            return False
        if self._startup_animation.play():
            self._last_startup_animation_started = now
            return True
        return False

    def _show_pet_root_passively(self) -> None:
        """显示桌宠本体，但不把当前工作应用挤到后台。"""
        previous = foreground_hwnd()
        self._startup_animation_hidden = False
        self.root.deiconify()
        self._set_topmost(True)
        restore_foreground(previous)

    def _hide_for_startup_animation(self) -> None:
        """动画期间隐藏桌宠本体，避免它压在入场画面上或被周期性置顶抬起。"""
        if self._startup_animation_hidden:
            return
        self._close_context_menu()
        self._close_mode_selector()
        self._startup_animation_hidden = True
        self.root.withdraw()
        log("启动动画开始：桌宠本体已隐藏")

    def _show_after_startup_animation(self) -> None:
        """Q 版落地后恢复桌宠，并用一次短促的回落完成出场。"""
        if not self._startup_animation_hidden or not self._alive:
            return
        self._startup_animation_hidden = False
        x = int(self.root.winfo_x())
        y = int(self.root.winfo_y())
        lift_px = 12
        self.root.geometry(f"+{x}+{y - lift_px}")
        self.root.deiconify()
        self._set_topmost(True)
        restore_foreground(self._startup_animation.previous_foreground)
        self._next_topmost = time.time() + TOPMOST_REASSERT_SECONDS
        self.root.after(85, lambda: self.root.geometry(f"+{x}+{y + 3}"))
        self.root.after(170, lambda: self.root.geometry(f"+{x}+{y}"))
        log("启动动画落地：桌宠本体恢复")

    def _on_press(self, event) -> None:
        self._drag = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())
        now = time.time()
        self.click_count = self.click_count + 1 if now - self.last_click < MULTI_CLICK_WINDOW else 1
        self.last_click = now
        self.last_interaction = now

    def _on_drag(self, event) -> None:
        if not hasattr(self, "_drag"):
            return
        dx, dy = self._drag
        self.root.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    def _on_release(self, event) -> None:
        if not hasattr(self, "_drag"):
            return
        dx, dy = self._drag
        moved = abs(event.x_root - self.root.winfo_x() - dx) > DRAG_SLOP or abs(
            event.y_root - self.root.winfo_y() - dy
        ) > DRAG_SLOP
        del self._drag
        if moved:
            if TRACE:
                log("按下与松开之间位移超过阈值，判为拖动（这次不算点击）")
            return
        if self.state in ("anim-game-intro", "anim-game-loop"):
            self.play_extra_action("caught", show_caught_bubble=True)
            return
        self.chat()

    def _on_motion(self, event) -> None:
        """鼠标进入窗口范围时刷新"最后互动时间"；实际追踪由 _tick 的系统级轮询负责。"""
        self.last_interaction = time.time()
        self._last_pointer = (event.x_root, event.y_root)

    # ---------------------------------------------------------------- 对话
    def chat(self) -> None:
        """单击 = 对话互动。按"是否在工作 / 点了几次"决定台词与姿态。"""
        # 正在播变身时被点：先把过渡落到目标状态，再从那个姿势接着演。
        # 否则 set_state 会拿 "trans-xxx" 去拼过渡组名（trans-trans-idle-waving-waving），
        # 拼不出来就退化成"直接跳过去"，看着像瞬移。
        if self._pending and self.state.startswith("trans-"):
            target, ms, hold, start_index = self._pending
            self._pending = None
            self.set_state(target, ms=ms, hold=hold, start_index=start_index, trans=False)
        if self._extra_menu_mode:
            if self.click_count >= MULTI_CLICK_LIMIT:
                self.play_extra_sequence(("fidget_a", "fidget_b"))
                self.click_count = 0
                return
            if self._working:
                self.say(WORK_CLICK_CHAT, hold=True)
                self.play_extra_action(random.choice(("protest_a", "protest_b")))
            else:
                self.say(random.choice(IDLE_CHAT), hold=True)
                self.play_extra_action(random.choice(("protest_a", "protest_b")))
            return
        if TRACE:
            log(f"chat：count={self.click_count} working={self._working} state={self.state}")
        if self.click_count >= MULTI_CLICK_LIMIT:
            self.say(ANGRY_CHAT, hold=True, tone="failed")
            self.set_state("failed", hold=True)
            self.click_count = 0
            return
        if self._working:
            self.say(WORK_CLICK_CHAT, hold=True, tone="jumping")
            stomp_ms = 1200
            self.set_state("jumping", ms=stomp_ms)          # 先跺脚（这段也走 5 秒定格）
            # 原本是固定 1300ms 后切"低头心虚"，但过渡里含 5 秒定格，
            # 1300ms 会从定格中途把它打断——改成按过渡实际长度排期
            trans_count = len(self.frames("trans-running-jumping")) or 7
            self.root.after(
                transition_total_ms(trans_count) + stomp_ms + 100,
                self._stomp_then_shy,
            )
            return

        # 非工作状态：抬头看你 / 害羞，二选一
        reply, tone = random.choice(NONWORK_CLICK_REPLIES)
        self.say(reply, hold=True, tone=tone)
        self.set_state(tone, hold=True)

    def _stomp_then_shy(self) -> None:
        """跺脚摆完再低头心虚。

        这一等就是七八秒，中间很可能发生别的事（工作状态变化、用户又点了一下）把画面换掉；
        那时候不该再硬插进来——否则她会在几秒后毫无来由地突然害羞。
        """
        if self.state in ("jumping", "trans-running-jumping"):
            self.set_state("shy", hold=True)
        tone = "wave" if random.random() < 0.5 else "waiting"
        self.say(random.choice(IDLE_CHAT), hold=True, tone=tone)
        self.set_state(tone, hold=True)

    def show_balance(self) -> None:
        # 余额气泡画在她自己的窗口里，先把窗口提到最上层，避免被别的窗口压住。
        self._set_topmost(True)
        if self._balance_busy:
            self.say("还在查呢，催什么催。", hold=True)
            return
        self._balance_busy = True
        self.say("查一下……", hold=True)

        def worker() -> None:
            result = self.query_balance()
            log(f"余额查询结果：{result}")
            # 只把结果放进队列；后台线程不碰 Tk（Tcl 不是线程安全的）。
            self._balance_queue.put(result)

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(120, self._poll_balance)

    def _poll_balance(self) -> None:
        """在主线程里取后台查询结果；后台线程绝不调用 Tk。"""
        try:
            result = self._balance_queue.get_nowait()
        except queue.Empty:
            self.root.after(120, self._poll_balance)
            return
        self._balance_busy = False
        self._set_topmost(True)
        self.say(result, hold=True)

    # ---------------------------------------------------------------- Codex 状态
    @staticmethod
    def codex_home() -> pathlib.Path:
        return pathlib.Path.home() / ".codex"

    def codex_working(self) -> bool:
        """用会话文件的写入时间判断 Codex 是否正在干活。

        两个阈值构成滞回：8 秒内有写入算"开始干活"，要连续 25 秒没写入才算"收工"。
        只用一个阈值的话，Codex 写一下停一下就会让她在 干活/收工 之间反复变身。

        另外只扫最近两天目录：以前 rglob 整个 sessions，几百个历史文件每 5 秒 stat 一遍，
        白白占着 CPU（也是"不够顺"的一部分）。
        """
        now = time.time()
        freshest = 0.0
        sessions = self.codex_home() / "sessions"
        if sessions.is_dir():
            for offset in (0, -1):
                stamp = time.mktime(time.localtime(now)) + offset * 86400
                day = time.strftime("%Y/%m/%d", time.localtime(stamp)).split("/")
                directory = sessions.joinpath(*day)
                if not directory.is_dir():
                    continue
                for path in directory.glob("*.jsonl"):
                    try:
                        modified = path.stat().st_mtime
                    except OSError:
                        continue
                    freshest = max(freshest, modified)
        freshest = max(freshest, self.codex_log_activity())
        if not freshest:
            return False
        started = getattr(self, "_codex_working", False)
        return now - freshest < (WORK_IDLE_SECONDS if started else WORK_FRESH_SECONDS)

    def codex_log_activity(self) -> float:
        """读取 Codex 日志库中最近一次真实回合活动时间。

        session JSONL 可能整轮结束后才落盘；工具调用和流式回复则持续写入
        logs_2.sqlite。只取回合相关 target，避免把空闲 websocket 心跳算成工作。
        """
        database = self.codex_home() / "logs_2.sqlite"
        if not database.is_file():
            return 0.0
        connection = None
        try:
            connection = sqlite3.connect(
                database.as_uri() + "?mode=ro",
                uri=True,
                timeout=0.4,
            )
            row = connection.execute(
                """
                SELECT MAX(ts)
                FROM (
                    SELECT ts, target
                    FROM logs
                    ORDER BY id DESC
                    LIMIT 500
                )
                WHERE target LIKE 'codex_core::%'
                   OR target = 'codex_app_server::outgoing_message'
                   OR target = 'feedback_tags'
                """
            ).fetchone()
            return float(row[0] or 0.0)
        except (OSError, sqlite3.Error, TypeError, ValueError):
            return 0.0
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def dsh_home() -> pathlib.Path:
        configured = os.environ.get("DSH_HOME")
        return (
            pathlib.Path(configured).expanduser()
            if configured
            else pathlib.Path.home() / ".dsh"
        )

    def dsh_working(self) -> bool:
        """用 DSH 持久化会话的写入时间判断它是否正在执行任务。"""
        now = time.time()
        sessions = self.dsh_home() / "sessions"
        if not sessions.is_dir():
            return False
        freshest = 0.0
        try:
            workspace_dirs = tuple(sessions.iterdir())
        except OSError:
            return False
        for workspace in workspace_dirs:
            if not workspace.is_dir():
                continue
            try:
                session_dirs = tuple(workspace.iterdir())
            except OSError:
                continue
            for session_dir in session_dirs:
                if not session_dir.is_dir():
                    continue
                try:
                    candidates = tuple(
                        session_dir.glob("session*.jsonl*")
                    )
                except OSError:
                    continue
                for path in candidates:
                    try:
                        modified = path.stat().st_mtime
                    except OSError:
                        continue
                    freshest = max(freshest, modified)
        if not freshest:
            return False
        started = getattr(self, "_dsh_working", False)
        return now - freshest < (
            DSH_WORK_IDLE_SECONDS if started else DSH_WORK_FRESH_SECONDS
        )

    def dsh_alive(self) -> bool:
        """DSH 有活动运行标记，或刚有任务写入时，桌宠继续陪着它。"""
        active_run = self.dsh_home() / "logs" / "active-run.json"
        try:
            payload = json.loads(active_run.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = {}
        if isinstance(payload, dict) and payload.get("pid") and not payload.get("ended"):
            return True
        return self.dsh_working()

    def codex_alive(self) -> bool:
        """Codex 桌面端是否还在运行（查不到就当作在运行，避免误退）。"""
        try:
            out = hidden_run(["tasklist"], timeout=15.0)
        except (OSError, subprocess.SubprocessError):
            return True
        text = (out.stdout or "").lower()
        if not text:
            return True
        return "chatgpt" in text or "codex" in text

    def api_credentials(self) -> tuple[str, str]:
        """从 Codex 配置里取 (base_url, token)。provider 段的 bearer token 才是有效的 API 密钥。"""
        config = self.codex_home() / "config.toml"
        base, token = "https://api.deepseek.com", ""
        try:
            text = config.read_text(encoding="utf-8")
        except OSError:
            text = ""
        match = re.search(r'base_url\s*=\s*"([^"]+)"', text)
        if match:
            base = match.group(1).rstrip("/")
        match = re.search(r'experimental_bearer_token\s*=\s*"([^"]+)"', text)
        if match:
            token = match.group(1)
        if not token:
            try:
                auth = json.loads((self.codex_home() / "auth.json").read_text(encoding="utf-8"))
                token = auth.get("OPENAI_API_KEY", "")
            except Exception:  # noqa: BLE001
                token = ""
        return base, token

    @staticmethod
    def is_deepseek_peak(at: datetime | None = None) -> bool:
        """按 DeepSeek 官方北京时间规则判断当前是否处于高峰时段。"""
        if at is None:
            now = datetime.now(BEIJING_TZ)
        elif at.tzinfo is None:
            now = at.replace(tzinfo=BEIJING_TZ)
        else:
            now = at.astimezone(BEIJING_TZ)
        day = now.date()
        workday = day.weekday() < 5
        if day.year == 2026:
            if any(start <= day <= end for start, end in CN_2026_HOLIDAY_RANGES):
                workday = False
            elif day in CN_2026_MAKEUP_WORKDAYS:
                workday = True
        current = now.time()
        in_peak_window = any(start <= current < end for start, end in DEEPSEEK_PEAK_WINDOWS)
        return workday and in_peak_window

    @classmethod
    def deepseek_pricing_label(cls, at: datetime | None = None) -> str:
        if cls.is_deepseek_peak(at):
            return "现在是 梁文峰 时间"
        return "现在是 梁文谷 时间"

    def query_balance(self) -> str:
        result = self._query_balance_value()
        if result.startswith("余额 "):
            return f"{result}\n{self.deepseek_pricing_label()}"
        return result

    def _query_balance_value(self) -> str:
        base, token = self.api_credentials()
        if not token:
            return "查不到余额：没找到可用的 API 密钥。"
        request = urllib.request.Request(
            f"{base}/user/balance",
            headers={"Authorization": f"Bearer {token}", "User-Agent": "baishuang-pet"},
        )
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            hint = {401: "密钥无效", 403: "无权限", 404: "接口不存在"}.get(exc.code, "服务端错误")
            try:
                detail = exc.read().decode("utf-8", "replace").strip()[:80]
            except Exception:  # noqa: BLE001
                detail = ""
            return f"余额查询失败：HTTP {exc.code}（{hint}）{detail}"
        except urllib.error.URLError as exc:
            reason = exc.reason
            if (
                isinstance(reason, PermissionError)
                or getattr(reason, "winerror", None) == 10013
            ):
                return BALANCE_NETWORK_BLOCKED_CHAT
            detail = str(reason).strip()[:40]
            return f"网络异常：{detail or type(reason).__name__}"
        except Exception as exc:  # noqa: BLE001
            return f"余额查询失败：{type(exc).__name__}"
        return self.format_balance(payload)

    @staticmethod
    def format_balance(payload: dict) -> str:
        """DeepSeek 的金额在 balance_infos[0] 里，顶层没有 total_balance 字段。"""
        infos = payload.get("balance_infos") or []
        if not infos:
            return "接口通了，但没有余额数据。"
        first = infos[0] if isinstance(infos[0], dict) else {}
        total = first.get("total_balance") or payload.get("total_balance") or "?"
        currency = first.get("currency", "")
        topped = first.get("topped_up_balance", "?")
        granted = first.get("granted_balance", "?")
        return f"余额 {total} {currency}（充值 {topped} / 赠金 {granted}）"

    # ---------------------------------------------------------------- 气泡
    def say(self, text: str, hold: bool = False, tone: str | None = None) -> None:
        for item in self.canvas.find_all():
            if item != self.sprite_id:
                self.canvas.delete(item)

        # 云朵轮廓不是矩形，固定留白不能让多行文字始终落在内部。
        # 先换行测量，再对云朵实际轮廓做包含验算，优先保留最宽的自然排版。
        pad_x = 18 * SCALE
        pad_y = 18 * SCALE
        text_font = (bubble_font_family(), BUBBLE_FONT_SIZE)
        head_y = self.canvas_height - self.height - 8 * SCALE
        cx = self.width // 2
        bottom = head_y - 6 * SCALE
        max_bubble_width = self.width - 6.0
        max_bubble_height = max(90.0, bottom - 2.0)
        min_bubble_width = 2 * pad_x + 20
        min_bubble_height = 2 * pad_y + 20
        clearance = 7.0

        choices: list[tuple[float, int, float, float, float, float]] = []
        # 在云朵轮廓允许的最大内宽内尽量增加每行字数，减少长文本行数。
        max_wrap = int(self.width * BUBBLE_MAX_TEXT_WIDTH_RATIO)
        for wrap_width in range(max_wrap, 109, -BUBBLE_WRAP_STEP_PX):
            probe_id = self.canvas.create_text(
                -10000,
                0,
                text=text,
                fill=BUBBLE_TEXT,
                font=text_font,
                width=wrap_width,
                anchor="center",
                justify="center",
            )
            box = self.canvas.bbox(probe_id)
            self.canvas.delete(probe_id)
            text_width = box[2] - box[0]
            text_height = box[3] - box[1]
            dimensions = fit_bubble_dimensions(
                text_width,
                text_height,
                min_bubble_width,
                max_bubble_width,
                min_bubble_height,
                max_bubble_height,
                clearance,
            )
            if dimensions is None:
                continue
            bubble_width, bubble_height = dimensions
            choices.append(
                (
                    bubble_width * bubble_height,
                    wrap_width,
                    bubble_width,
                    bubble_height,
                    text_width,
                    text_height,
                )
            )

        if choices:
            # 候选宽度从宽到窄生成；优先保留最宽的自然换行。
            _, text_wrap, bubble_width, bubble_height, text_width, text_height = choices[0]
        else:
            # 极端长文本仍保证有足够字符宽度，并记录一次便于后续调整文案。
            text_wrap = 110
            bubble_width = max_bubble_width
            bubble_height = max_bubble_height
            probe_id = self.canvas.create_text(
                -10000,
                0,
                text=text,
                fill=BUBBLE_TEXT,
                font=text_font,
                width=text_wrap,
                anchor="center",
                justify="center",
            )
            box = self.canvas.bbox(probe_id)
            self.canvas.delete(probe_id)
            text_width = box[2] - box[0]
            text_height = box[3] - box[1]
            log("气泡文字过长：已使用最大气泡尺寸，仍可能有文字贴近边界")

        text_id = self.canvas.create_text(
            0,
            0,
            text=text,
            fill=BUBBLE_TEXT,
            font=text_font,
            width=text_wrap,
            anchor="center",
            justify="center",
        )
        cy = bottom - bubble_height / 2
        cy = max(bubble_height / 2 + 2, cy)

        points = cloud_points(cx, cy, bubble_width, bubble_height)
        cloud_id = self.canvas.create_polygon(
            *points,
            fill=BUBBLE_FILL,
            outline=BUBBLE_STROKE,
            width=2.5,
            smooth=True,
            splinesteps=18,
        )
        self.canvas.coords(text_id, cx, cy)
        self.canvas.tag_raise(text_id)
        if not bubble_contains_text_rect(
            bubble_width,
            bubble_height,
            text_width,
            text_height,
            clearance,
        ):
            log("气泡自适应校验失败：文字未完全落在云朵内部")
        self._bubble_deadline = time.time() + (HOLD_MS if hold else HOLD_MS) / 1000.0
        _ = cloud_id

    # ---------------------------------------------------------------- 状态
    def set_state(
        self,
        state: str,
        ms: float = 0.0,
        hold: bool = False,
        once: bool = True,
        trans: bool = True,
        start_index: int = 0,
        hold_middle: bool = True,
    ) -> None:
        """once=True：从第一帧播到最后一帧后**停住**（不再循环），配合 hold 保持 15 秒。

        这是修掉"点按后持续变身"的关键：循环播放会让光效帧每轮闪一次。
        trans=True：若存在 trans-<旧状态>-<新状态> 帧组，先把它播一遍（交叉溶解 + 变身闪光），
        播完再进目标状态——状态之间就不再是硬切。
        hold_middle=False：这条过渡不做"正中帧停 5 秒"（只给需要快节奏的连环演出用，
        比如"干活中被点"的 跺脚 → 低头心虚）。
        """
        # 这里要比对**目录名**：调用方传的是逻辑状态名（"wave"、"shy"），
        # 早期版本直接拿 "wave" 去比对目录，比对不到就一律降级成 idle——
        # 于是开场招手和一半的点按变身是"点了没反应"。
        if STATE_DIRS.get(state, state) not in self.states:
            state = "idle"
        self._pending = None
        self._middle_hold = hold_middle
        from_dir = STATE_DIRS.get(self.state, self.state)
        to_dir = STATE_DIRS.get(state, state)
        for cached_name in tuple(self.cache):
            if cached_name.startswith("anim-") and cached_name != to_dir:
                self.cache.pop(cached_name, None)
        # 2026-10-18：running 四组过渡已替换为和新眼镜版一致的长序列。
        if trans and state != self.state:
            name = f"trans-{from_dir}-{to_dir}"
            if name in self.states:
                # 弹出式过渡的末帧就是目标状态的保持帧（idle/failed=05，其余=04）。
                # 进目标状态后从同一张保持帧起播，避免先跳回 00 再走一遍。
                target_count = len(self.frames(to_dir))
                if to_dir in ("waving", "waiting") and target_count >= LONG_STATE_MIN_FRAMES:
                    start_at = max(0, target_count - LONG_STATE_TAIL_FRAMES)
                else:
                    start_at = 5 if to_dir in ("idle", "failed") else 4
                self._pending = (state, ms, hold, start_at)
                state = name
        self.state = state
        self.frame_index = start_index
        self._hold_cycle = 0
        self.play_once = once
        duration = HOLD_MS if hold else (ms or HOLD_MS)
        self.state_until = time.time() + duration / 1000.0

    def _tick(self) -> None:
        try:
            self._tick_body()
        except Exception as exc:  # noqa: BLE001
            log(f"tick 异常：{type(exc).__name__}: {exc}")
            self.root.after(1000, self._tick)

    def _tick_body(self) -> None:
        now = time.time()
        if now >= self._next_animation_request_check:
            self._next_animation_request_check = now + 1.0
            if STARTUP_ANIMATION_REQUEST.exists():
                try:
                    STARTUP_ANIMATION_REQUEST.unlink(missing_ok=True)
                    self.play_startup_animation()
                except OSError as exc:
                    log(f"启动动画请求处理失败：{exc}")
        # 过渡帧播完 -> 进目标状态（时长从这一刻开始算）
        if self._pending and self.state.startswith("trans-"):
            images = self.frames(self.state)
            if images and self.frame_index >= len(images) - 1:
                target, ms, hold, start_index = self._pending
                self._pending = None
                self.set_state(target, ms=ms, hold=hold, start_index=start_index, trans=False)
        if self.state == "anim-game-intro":
            intro_images = self.frames(self.state)
            if (
                intro_images
                and self.frame_index >= len(intro_images) - 1
            ):
                self._start_gaming_loop()
        if self.state.startswith("anim-") and self._extra_sequence:
            sequence_images = self.frames(self.state)
            if sequence_images and self.frame_index >= len(sequence_images) - 1:
                next_action = self._extra_sequence.pop(0)
                self.play_extra_action(
                    next_action,
                    _keep_sequence=True,
                    show_action_bubble=not self._dual_work_active,
                )
        if self._bubble_deadline and now > self._bubble_deadline:
            for item in self.canvas.find_all():
                if item != self.sprite_id:
                    self.canvas.delete(item)
            self._bubble_deadline = 0.0

        # 状态检测降频：进程查询 10 秒一次、Codex/DSH 会话文件 5 秒一次
        if now >= self._next_work_check:
            previous = (self._codex_working, self._dsh_working)
            self._codex_working = self.codex_working()
            self._dsh_working = self.dsh_working()
            self._working = self._codex_working or self._dsh_working
            current = (self._codex_working, self._dsh_working)
            if current != previous:
                log(
                    "工作检测："
                    f"Codex={self._codex_working}，DSH={self._dsh_working}"
                )
            self._next_work_check = now + WORK_CHECK_SECONDS
        if now >= self._next_alive_check:
            self._alive = self.codex_alive() or self.dsh_alive()
            self._next_alive_check = now + ALIVE_CHECK_SECONDS
        if (
            now >= self._next_topmost
            and not self._startup_animation_hidden
            and self._context_menu is None
            and self._mode_selector is None
        ):
            # 白霜始终置顶；壁纸、挂件这类程序会反复抢，所以定期重申。
            self._set_topmost(True)
            self._next_topmost = now + TOPMOST_REASSERT_SECONDS

        working = self._working
        dual_working = self._codex_working and self._dsh_working
        in_extra_game = self.state in ("anim-game-intro", "anim-game-loop")
        in_extra_sequence = bool(self._extra_sequence)
        if not working:
            self._work_entry_pending = None
        elif self._work_entry_pending == "dual" and not dual_working:
            self._work_entry_pending = "normal"
        if dual_working:
            if (
                not self._dual_work_active
                and self._work_entry_pending != "dual"
            ):
                self._request_or_enter_work(True, now)
        elif self._dual_work_active:
            self._dual_work_active = False
            self._extra_sequence.clear()
            if working:
                if self.state not in {
                    "anim-work-start",
                    "anim-work-intro",
                    "anim-work-hold",
                }:
                    self._enter_normal_work_state()
            elif self.was_working:
                if self._extra_menu_mode:
                    self.play_extra_sequence(("work_b", "happy"))
                else:
                    self.say(DONE_CHAT, hold=True, tone="review")
                    self.set_state("review", hold=True)
        elif working and not self.was_working:
            self._request_or_enter_work(False, now)
        elif (
            not in_extra_game
            and not in_extra_sequence
            and not working
            and self.was_working
        ):
            if self._extra_menu_mode:
                self.play_extra_sequence(("work_b", "happy"))
            else:
                self.say(DONE_CHAT, hold=True, tone="review")
                self.set_state("review", hold=True)
        self.was_working = working

        if (
            self._work_entry_pending
            and working
            and now > self._work_entry_pending_at
            and self.state not in ("anim-game-intro", "anim-game-loop")
        ):
            pending_images = self.frames(self.state)
            cycle_finished = (
                self.state.startswith("anim-")
                and bool(pending_images)
                and self.frame_index >= len(pending_images) - 1
            )
            if cycle_finished or not self._is_casual_animation_running():
                mode = self._work_entry_pending
                self._work_entry_pending = None
                if mode == "dual":
                    self._dual_work_active = True
                    self._start_dual_work_loop()
                else:
                    self._enter_normal_work_state()

        if (
            self._dual_work_active
            and self.state == "idle"
            and not self._pending
            and not self._extra_sequence
        ):
            self._start_dual_work_loop()

        # 过渡还在播时不要被"回待机"打断：过渡里含 5 秒定格，整段比目标状态的时长还长
        if not self._pending and now > self.state_until and self.state != "idle":
            self.set_state("idle")
        elif self.state == "idle":
            idle_seconds = now - self.last_interaction
            if self._extra_menu_mode:
                if (
                    not working
                    and idle_seconds >= EXTRA_IDLE_TRIGGER_SECONDS
                    and now >= self._next_extra_idle_check
                ):
                    self._next_extra_idle_check = now + EXTRA_IDLE_CHECK_SECONDS
                    if random.random() < EXTRA_IDLE_TRIGGER_PROBABILITY:
                        self.last_interaction = now
                        action = random.choices(
                            (
                                "eating",
                                "peeking",
                                "gaming",
                                "fidget_a",
                                "fidget_b",
                                "shy_a",
                                "protest_a",
                                "protest_b",
                                "happy",
                            ),
                            weights=(0.18, 0.17, 0.10, 0.10, 0.10, 0.18, 0.06, 0.06, 0.05),
                            k=1,
                        )[0]
                        log(f"扩展模式：待机随机触发 {action}")
                        self.play_extra_action(action)
            elif idle_seconds > IDLE_PEEK_MS / 1000.0:
                self.last_interaction = now
                if self._last_pointer:                              # 偷偷抬头看向鼠标
                    directory, index = self.look_frame(*self._last_pointer)
                    self._peek_override = (directory, index)
                    self.root.after(1500, self._clear_peek)
                self.root.after(1600, lambda: self.set_state("shy", ms=2500))   # 被发现就害羞

        if not self._alive:
            if self._extra_menu_mode:
                self.play_extra_action("shy_a")
                quit_delay_ms = 2900
            else:
                self.say(BYE_CHAT, hold=False)
                self.set_state("shy", ms=2500)
                quit_delay_ms = 2600
            log("检测到 Codex 已退出，说告别语并收工")
            self.root.after(quit_delay_ms, self._quit)
            return

        images = self.frames(self.state)
        interval = self._frame_interval(len(images))
        self._update_breathe(len(images))
        if images:
            if self.state == "idle":
                if self._extra_menu_mode:
                    # 动画模式固定使用最稳定的待机帧，跳跃幅度由鼠标追踪和 1px 慢呼吸控制。
                    stable_idle = self.frames("idle")
                    if stable_idle:
                        images = [stable_idle[-1]]
                        self.frame_index = 0
                else:
                    # 立绘模式保留原来的系统级鼠标视线帧。
                    pointer = cursor_pos() or self._last_pointer
                    if pointer:
                        self._last_pointer = pointer
                        directory, index = self.look_frame(*pointer)
                        look_images = self.frames(directory) or images
                        images = look_images
                        self.frame_index = index % len(look_images)
            # 帧没变就别重绘：待机时她可能连续几十个 tick 都停在同一张视线帧上，
            # 每个 tick 都重画一遍 288x312 纯属浪费（这也是之前"不够顺"的一部分）
            image = images[min(self.frame_index, len(images) - 1)]
            if image is not self._shown:
                self.canvas.itemconfig(self.sprite_id, image=image)
                self._shown = image
            if self.play_once and self.state != "idle":
                if self.frame_index < len(images) - 1:
                    self.frame_index += 1
                else:
                    # 播完一遍后不再冻成一张贴图：末尾三帧（压轴姿势 + 两帧 ±1 像素）缓慢循环，
                    # 15 秒的保持期里她会轻轻起伏
                    self._hold_cycle = (self._hold_cycle + 1) % 3
                    self.frame_index = max(0, len(images) - 3) + self._hold_cycle
                    interval = HOLD_FRAME_MS
            else:
                self.frame_index = (self.frame_index + 1) % len(images)
        self._update_sprite_tracking(now)
        self.root.after(int(interval), self._tick)     # after() 只收整数毫秒，先兜一道
        if TRACE:
            log(f"tick state={self.state} frame={self.frame_index} interval={interval} t={time.strftime('%H:%M:%S')}")

    def _update_sprite_tracking(self, now: float) -> None:
        base_x = self.width // 2
        base_y = self.canvas_height
        offset_x = 0.0
        offset_y = 0.0
        if self._extra_menu_mode and not self._startup_animation_hidden:
            pointer = cursor_pos()
            if pointer:
                center_x = self.root.winfo_rootx() + base_x
                center_y = self.root.winfo_rooty() + base_y - self.height / 2
                delta_x = pointer[0] - center_x
                delta_y = pointer[1] - center_y
                distance = math.hypot(delta_x, delta_y)
                if distance <= TRACKING_RADIUS_PX:
                    offset_x = max(
                        -TRACKING_MAX_X,
                        min(
                            TRACKING_MAX_X,
                            delta_x / TRACKING_RADIUS_PX * TRACKING_MAX_X,
                        ),
                    )
                    offset_y = max(
                        -TRACKING_MAX_Y,
                        min(
                            TRACKING_MAX_Y,
                            delta_y / TRACKING_RADIUS_PX * TRACKING_MAX_Y,
                        ),
                    )
            if self.state == "idle":
                # 2 秒一个周期，只保留 1px 的极轻微呼吸。
                offset_y += ANIMATION_IDLE_BREATH_PX * math.sin(math.pi * now)
        self.canvas.coords(
            self.sprite_id,
            int(round(base_x + offset_x)),
            int(round(base_y + offset_y)),
        )

    def _frame_interval(self, count: int) -> int:
        """过渡帧放慢；正中那帧直接停 TRANS_MIDDLE_HOLD_MS（它没有光效遮挡，是给人看清的一帧）。

        必须返回整数毫秒：Tk 的 after() 只认整数，传浮点会抛
        `TclError: bad argument "140.0": must be cancel, idle, info, or an integer`，
        被 _tick 的兜底接住后每帧变成整整 1 秒——表现就是"变身卡住"（真踩过）。
        """
        if self.state.startswith("anim-"):
            return EXTRA_ACTION_FRAME_MS
        if (
            self.play_once
            and self.state != "idle"
            and count >= 3
            and self.frame_index >= count - 3
        ):
            return HOLD_FRAME_MS
        if self.state in ("waving", "waiting") and count >= LONG_STATE_MIN_FRAMES:
            return LONG_STATE_FRAME_MS
        if not self.state.startswith("trans-") or count <= 1:
            return FRAME_MS
        if count >= LONG_TRANS_MIN_FRAMES:
            return LONG_TRANS_FRAME_MS
        middle = (count - 1) // 2
        if self._middle_hold and self.frame_index == middle:
            return TRANS_MIDDLE_HOLD_MS
        span = max(1, middle)
        closeness = max(0.0, 1.0 - abs(self.frame_index - middle) / span)
        return int(round(TRANS_FRAME_MS * (1.0 + (TRANS_MIDDLE_BOOST - 1.0) * closeness)))

    def _clear_peek(self) -> None:
        self._peek_override = None

    def _quit(self) -> None:
        log("桌宠退出（菜单）")
        self._close_context_menu()
        self._close_mode_selector()
        self._startup_animation.close(notify=False)
        try:
            PID_PATH.unlink(missing_ok=True)
        except OSError:
            pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    try:
        _fault_handle = open(FAULT_PATH, "a", encoding="utf-8")
        faulthandler.enable(file=_fault_handle, all_threads=True)
    except Exception:  # noqa: BLE001
        pass
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    frames_dir = pathlib.Path(args[0] if args else "frames").resolve()
    # 单实例：已经有一只活着就别再开第二只（双击多次、或启动器没杀干净时兜底）
    alive = other_instance_pid()
    if alive is not None:
        log(f"已有一只白霜在跑（PID {alive}），本次不重复启动")
        raise SystemExit(0)
    try:
        PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass
    dpi_note = enable_dpi_awareness()          # 必须在 tk.Tk() 之前
    if register_bubble_font():
        log(f"气泡字体：{BUBBLE_FONT_FAMILY} {BUBBLE_FONT_SIZE} 号")
    else:
        log(f"气泡字体加载失败，回退：{BUBBLE_FONT_FALLBACK} {BUBBLE_FONT_SIZE} 号")
    pet = Pet(frames_dir, debug="--debug" in sys.argv)
    log(f"分辨率：素材 x{SCALE}（{pet.width}x{pet.canvas_height}），{dpi_note}")
    pet.run()
    log("主循环结束")
