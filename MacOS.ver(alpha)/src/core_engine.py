# ShangBackground runtime core used by the PySide6 UI.
from __future__ import annotations

import os
import sys
import json
import ctypes
import threading
import time
import random
import tempfile
import plistlib
try:
    import ctypes.wintypes
except ImportError:
    ctypes.wintypes = None
try:
    import winreg
except ImportError:
    winreg = None
try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
    ImageDraw = None
import logging  # 仅用于禁用第三方库日志输出
import math
import argparse
try:
    import psutil
except ImportError:
    psutil = None
import signal
import shutil
try:
    import requests
except ImportError:
    requests = None
import subprocess
import random_copy
import single_instance
from collections import deque
from app_config import APP_NAME, DEFAULT_GRADIENT_COLOR2, DEFAULT_SOLID_COLOR, DEFAULT_THEME_COLOR, FONT_FAMILY, IS_LINUX, IS_MACOS, IS_WINDOWS, STYLE_MAP, UI_ACCENT, UI_BG, UI_BORDER, normalize_mode_key, normalize_style_key
from i18n import t
from platform_support import (
    configure_windows_fit_mode,
    get_app_command,
    get_current_wallpaper_platform,
    get_screen_size,
    quote_applescript_text,
    set_wallpaper_platform,
)
try:
    from wallpaper_sidebar import WallpaperSidebar
except Exception:
    WallpaperSidebar = None

# 试试看能不能导入numpy，能的话会快一丢丢 (不能也没关系啦)
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
# Windows消息常量
WM_COPYDATA = 0x004A
HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x001A
SPI_GETDESKWALLPAPER = 0x0073
HWND_MESSAGE = -3  # message-only window parent; prevents the IPC window from appearing on screen/taskbar

# Win32 ctypes 类型在运行时会被 _configure_win32_ctypes() 更新；先提供兜底，避免局部变量未导出。
HWND = ctypes.c_void_p
HMENU = ctypes.c_void_p
HINSTANCE = ctypes.c_void_p
HMODULE = ctypes.c_void_p
HANDLE = ctypes.c_void_p
BOOL = ctypes.c_int
DWORD = ctypes.c_ulong
UINT = ctypes.c_uint
LPCWSTR = ctypes.c_wchar_p
ATOM = ctypes.c_ushort
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
LRESULT = ctypes.c_ssize_t


# 定义WNDCLASS结构
class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ('style', ctypes.c_uint),
        ('lpfnWndProc', ctypes.c_void_p),
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', ctypes.c_void_p),
        ('hIcon', ctypes.c_void_p),
        ('hCursor', ctypes.c_void_p),
        ('hbrBackground', ctypes.c_void_p),
        ('lpszMenuName', ctypes.c_wchar_p),
        ('lpszClassName', ctypes.c_wchar_p)
    ]


# 定义COPYDATASTRUCT结构
class COPYDATASTRUCT(ctypes.Structure):
    _fields_ = [
        ('dwData', ctypes.c_size_t),
        ('cbData', ctypes.c_ulong),
        ('lpData', ctypes.c_void_p)
    ]


def is_frozen():
    return getattr(sys, 'frozen', False)


def _resource_base_dir() -> str:
    """Return bundled/source resource directory for images, translations, and helper modules."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _user_data_dir() -> str:
    """Return a per-user writable config/runtime directory on macOS/Linux."""
    if IS_MACOS:
        root = os.path.expanduser("~/Library/Application Support")
        path = os.path.join(root, APP_NAME)
    elif IS_LINUX:
        root = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        path = os.path.join(root, APP_NAME.lower())
    else:
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        path = os.path.join(root, APP_NAME)
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        path = os.path.join(tempfile.gettempdir(), APP_NAME)
        os.makedirs(path, exist_ok=True)
    return path


BASE_DIR = _resource_base_dir()
DATA_DIR = _user_data_dir()
try:
    random_copy.configure_storage(DATA_DIR)
except Exception as exc:
    log_message = f"随机概率配置目录初始化失败: {exc}"
    print(log_message)

# 全局常量
VERSION = "1.3.0"
CONFIG_PATH = os.path.join(DATA_DIR, "settings.json")
BUNDLED_CONFIG_PATH = os.path.join(BASE_DIR, "settings.json")
LEGACY_CONFIG_PATH = os.path.join(DATA_DIR, "shezhi.json")
LEGACY_BUNDLED_CONFIG_PATH = os.path.join(BASE_DIR, "shezhi.json")
TRIGGER_FILE_PREV = os.path.join(DATA_DIR, "prev.txt")
TRIGGER_FILE_NEXT = os.path.join(DATA_DIR, "next.txt")
TRIGGER_FILE_RANDOM = os.path.join(DATA_DIR, "random.txt")
style_map = STYLE_MAP


# 日志文件写入已禁用咯
# log_file = os.path.join(BASE_DIR, "#wallpaper_debug.log")
# logging.basicConfig(
#     filename=log_file,
#     level=logging.DEBUG,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )


def log(msg):
    """带时间戳的日志输出函数，格式 [HH:MM:SS]。

    默认只输出到控制台；新版 PySide6 日志页开启并选择路径后才写入文件。
    """
    timestamp = time.strftime("[%H:%M:%S]")
    line = f"{timestamp} {msg}"
    print(line)
    try:
        cfg = globals().get("config", {})
        if cfg.get("log_enabled", False) and cfg.get("log_file_path"):
            with open(cfg.get("log_file_path"), "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass


def apply_image_fit_mode(img, mode, target_size):
    mode = normalize_style_key(mode)
    """根据适应模式处理图片，统一5种适应模式的处理逻辑。

    参数:
        img: PIL.Image 对象
        mode: 适应模式字符串，支持 "填充"/"适应"/"拉伸"/"居中"/"平铺"
        target_size: 目标尺寸元组 (width, height)

    返回:
        处理后的 PIL.Image 对象
    """
    target_w, target_h = target_size
    orig_w, orig_h = img.size

    if mode == "填充":
        ratio = max(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        result = img_resized.crop((left, top, left + target_w, top + target_h))
    elif mode == "适应":
        ratio = min(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        result = Image.new("RGB", target_size, (0, 0, 0))
        x_offset = (target_w - new_w) // 2
        y_offset = (target_h - new_h) // 2
        result.paste(img_resized, (x_offset, y_offset))
    elif mode == "拉伸":
        result = img.resize(target_size, Image.Resampling.LANCZOS)
    elif mode == "居中":
        result = Image.new("RGB", target_size, (0, 0, 0))
        x_offset = (target_w - orig_w) // 2
        y_offset = (target_h - orig_h) // 2
        result.paste(img, (x_offset, y_offset))
    elif mode == "平铺":
        result = Image.new("RGB", target_size)
        for x in range(0, target_w, orig_w):
            for y in range(0, target_h, orig_h):
                result.paste(img, (x, y))
    else:
        result = img.resize(target_size, Image.Resampling.LANCZOS)
    return result


def show_message(title, msg):
    """显示系统消息；GUI 内部优先由 PySide6 弹窗处理。"""
    if IS_WINDOWS:
        try:
            ctypes.windll.user32.MessageBoxW(None, msg, title, 0x40)
            return
        except Exception:
            pass
    # macOS: use osascript for native dialog
    if IS_MACOS:
        try:
            subprocess.run(
                ["osascript", "-e", f'display dialog "{quote_applescript_text(str(msg))}" with title "{quote_applescript_text(str(title))}" buttons "OK" default button 1 with icon note'],
                timeout=10, capture_output=True,
            )
            return
        except Exception:
            pass
    # Linux: try zenity, kdialog, or xmessage
    if IS_LINUX:
        try:
            subprocess.run(
                ["zenity", "--info", "--title", str(title), "--text", str(msg), "--no-wrap"],
                timeout=10, capture_output=True,
            )
            return
        except Exception:
            pass
        try:
            subprocess.run(
                ["kdialog", "--title", str(title), "--msgbox", str(msg)],
                timeout=10, capture_output=True,
            )
            return
        except Exception:
            pass
        try:
            subprocess.run(
                ["xmessage", "-center", f"{title}: {msg}"],
                timeout=10, capture_output=True,
            )
            return
        except Exception:
            pass
    log(f"{title}: {msg}")


def resolve_ui_font_family(master=None):
    candidates = [
        FONT_FAMILY,
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "SimHei",
        "SimSun",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Arial Unicode MS",
        "Segoe UI",
    ]
    for family in candidates:
        if family:
            return family
    return "Segoe UI"


def apply_global_font_settings(master=None):
    return


# 全局变量
hwnd = None
WND_CLASS_NAME = "ShangBackgroundIpcWindowClass"
use_message = False
apply_timer = None
root = None
pending_action = None  # 用于存储待执行的动作（无主进程时）
hide_window = False  # 是否隐藏主窗口（由 --hide 参数控制）
canvas = None
slide_frame = None
shuffle_var = None
chk_next = None
chk_random = None
chk_prev = None
single_frame = None
gradient_frame = None
color1_var = None
color1_preview = None
color2_var = None
color2_preview = None
angle_var = None
solid_frame = None
solid_color_var = None
solid_color_preview = None
mode_var = None
fit_var = None
ctx_prev_var = None
ctx_next_var = None
ctx_random_var = None
ctx_personalize_var = None
ctx_file_wallpaper_var = None
wallpaper_monitor_running = False
wallpaper_monitor_last = None
hotkey_running = False
hotkey_thread = None
preview_images_frame = None
wallpaper_preview_labels = None
folder_entry = None
tray_icon_obj = None
ctx_global_settings_var = None

_message_loop_thread = None
session_original_wallpaper = ""
session_original_wallpaper_style = {}
session_original_wallpaper_captured = False

# 跨权限/跨进程保存“本次启动前壁纸”。管理员提权会开启新进程，
# 仅靠内存变量会丢失或被新进程覆盖，所以用 TEMP 下的轻量 JSON 作为会话锚点。
SESSION_WALLPAPER_FILE = os.path.join(tempfile.gettempdir(), "ShangBackground_session_wallpaper.json")

def _persist_session_original_wallpaper():
    try:
        data = {
            "wallpaper": session_original_wallpaper,
            "style": session_original_wallpaper_style or {},
            "captured_at": time.time(),
            "pid": os.getpid(),
        }
        with open(SESSION_WALLPAPER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"保存启动前壁纸会话失败: {e}")

def _load_session_original_wallpaper(max_age_seconds=12 * 3600):
    try:
        if not os.path.exists(SESSION_WALLPAPER_FILE):
            return False
        with open(SESSION_WALLPAPER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - float(data.get("captured_at", 0)) > max_age_seconds:
            return False
        target = data.get("wallpaper") or ""
        if not target:
            return False
        global session_original_wallpaper, session_original_wallpaper_style, session_original_wallpaper_captured
        session_original_wallpaper = target
        session_original_wallpaper_style = data.get("style") or {}
        session_original_wallpaper_captured = True
        log(f"已从会话文件恢复启动前壁纸记录: {session_original_wallpaper}")
        return True
    except Exception as e:
        log(f"读取启动前壁纸会话失败: {e}")
        return False
pending_show_request = False

APP_MUTEX_NAME = single_instance.APP_MUTEX_NAME
STARTUP_ITEM_NAME = "ShangBackground"
STARTUP_VBS_NAME = f"{STARTUP_ITEM_NAME}.vbs"
LEGACY_STARTUP_VALUE_NAMES = ["xxdz_WallpaperController"]
ALL_STARTUP_VALUE_NAMES = LEGACY_STARTUP_VALUE_NAMES + [STARTUP_ITEM_NAME]
LEGACY_STARTUP_VBS_NAMES = ["PowerOn.vbs"]
ALL_STARTUP_VBS_NAMES = LEGACY_STARTUP_VBS_NAMES + [STARTUP_VBS_NAME]
_instance_mutex_handle = None


def _win_type(name, fallback):
    """ctypes.wintypes 在不同 Python 版本里字段不完全一致；这里集中做兜底。"""
    try:
        return getattr(ctypes.wintypes, name)
    except Exception:
        return fallback


def _win_int(value):
    """把 WNDPROC 回调里可能出现的 None / c_void_p 安全转换成 Win32 整数值。"""
    if value is None:
        return 0
    try:
        return int(value)
    except Exception:
        try:
            return int(value.value or 0)
        except Exception:
            return 0


def _configure_win32_ctypes():
    """声明常用 Win32 API 的参数/返回类型，兼容 Python 3.14 的严格 ctypes 转换。"""
    global HWND, HMENU, HINSTANCE, HMODULE, HANDLE, BOOL, DWORD, UINT, LPCWSTR, ATOM, WPARAM, LPARAM, LRESULT
    if not IS_WINDOWS or ctypes.wintypes is None:
        return
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        shell32 = ctypes.windll.shell32
        HWND = _win_type("HWND", ctypes.c_void_p)
        HMENU = _win_type("HMENU", ctypes.c_void_p)
        HINSTANCE = _win_type("HINSTANCE", ctypes.c_void_p)
        HMODULE = _win_type("HMODULE", ctypes.c_void_p)
        HANDLE = _win_type("HANDLE", ctypes.c_void_p)
        BOOL = _win_type("BOOL", ctypes.c_int)
        DWORD = _win_type("DWORD", ctypes.c_ulong)
        UINT = _win_type("UINT", ctypes.c_uint)
        LPCWSTR = _win_type("LPCWSTR", ctypes.c_wchar_p)
        ATOM = _win_type("ATOM", ctypes.c_ushort)
        WPARAM = _win_type("WPARAM", ctypes.c_size_t)
        LPARAM = _win_type("LPARAM", ctypes.c_ssize_t)
        LRESULT = _win_type("LRESULT", ctypes.c_ssize_t)

        kernel32.GetModuleHandleW.argtypes = [LPCWSTR]
        kernel32.GetModuleHandleW.restype = HMODULE
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, BOOL, LPCWSTR]
        kernel32.CreateMutexW.restype = HANDLE
        kernel32.CloseHandle.argtypes = [HANDLE]
        kernel32.CloseHandle.restype = BOOL
        kernel32.GetLastError.argtypes = []
        kernel32.GetLastError.restype = DWORD
        user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
        user32.RegisterClassW.restype = ATOM
        user32.CreateWindowExW.argtypes = [
            DWORD, LPCWSTR, LPCWSTR, DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            HWND, HMENU, HINSTANCE, ctypes.c_void_p,
        ]
        user32.CreateWindowExW.restype = HWND
        user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
        user32.DefWindowProcW.restype = LRESULT
        user32.SendMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
        user32.SendMessageW.restype = LRESULT
        user32.FindWindowW.argtypes = [LPCWSTR, LPCWSTR]
        user32.FindWindowW.restype = HWND
        user32.FindWindowExW.argtypes = [HWND, HWND, LPCWSTR, LPCWSTR]
        user32.FindWindowExW.restype = HWND
        user32.DestroyWindow.argtypes = [HWND]
        user32.DestroyWindow.restype = BOOL
        shell32.ShellExecuteW.argtypes = [HWND, LPCWSTR, LPCWSTR, LPCWSTR, LPCWSTR, ctypes.c_int]
        shell32.ShellExecuteW.restype = HINSTANCE
    except Exception as e:
        log(f"Win32 API 类型声明失败: {e}")


_configure_win32_ctypes()


def is_windows_admin():
    """检测当前进程是否以管理员权限运行（仅 Windows 有效）。"""
    if not IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception as e:
        log(f"管理员权限检测失败: {e}")
        return False


def release_single_instance_mutex():
    """释放单实例守卫，用于提权重启或退出前清理。"""
    global _instance_mutex_handle, hwnd, use_message
    try:
        if hwnd and IS_WINDOWS:
            try:
                ctypes.windll.user32.DestroyWindow(HWND(int(hwnd)))
            except Exception:
                pass
            hwnd = None
            use_message = False
        single_instance.release()
        _instance_mutex_handle = None
        log("已释放单实例守卫")
    except Exception as e:
        log(f"释放单实例守卫失败: {e}")


def restart_as_admin(extra_args=None):
    """以管理员身份重启当前应用。

    使用 ShellExecuteW 的 "runas" 动词触发 UAC 提权，
    然后退出当前非管理员进程。
    注意：提权前必须先释放互斥体和销毁托盘图标，
    否则新实例无法获取互斥体，且旧托盘图标会残留。
    """
    if not IS_WINDOWS:
        log(t("非 Windows 平台，无法自动提权重启"))
        return False
    try:
        # 获取当前解释器路径和脚本路径。脚本运行时优先用 pythonw.exe，避免提权后出现控制台日志窗口。
        if is_frozen():
            executable = sys.executable
            base_args = []
        else:
            pythonw_exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            executable = pythonw_exe if os.path.exists(pythonw_exe) else sys.executable
            base_args = [os.path.abspath(sys.argv[0])]

        current_args = [a for a in sys.argv[1:] if a != "--hide"]
        for arg in list(extra_args or []):
            if arg not in current_args:
                current_args.append(arg)
        params = subprocess.list2cmdline([str(a) for a in [*base_args, *current_args]])

        # 先落盘启动前壁纸，再释放互斥体和托盘图标。管理员提权会产生新进程，内存状态不可依赖。
        capture_session_original_wallpaper()
        _persist_session_original_wallpaper()
        # 先释放互斥体和托盘图标，再触发 UAC。否则被提权的新实例可能先启动、发现旧互斥体后退出，
        # 造成“旧实例退出 + 新实例也退出”的双杀问题。
        release_single_instance_mutex()
        _cleanup_tray_icon_on_exit()

        # 使用 ShellExecuteW 以管理员身份运行
        ret = ctypes.windll.shell32.ShellExecuteW(
            0, "runas", executable, params, None, 1  # SW_SHOWNORMAL=1
        )
        if ret <= 32:
            log(f"提权重启失败，ShellExecuteW 返回值: {ret}")
            acquire_single_instance_mutex()
            return False
        log("已请求管理员权限重启")

        # 销毁消息窗口
        global hwnd
        if hwnd:
            try:
                ctypes.windll.user32.DestroyWindow(hwnd)
            except Exception:
                pass
            hwnd = None

        return True
    except Exception as e:
        log(f"提权重启异常: {e}")
        return False


def _do_exit(code=0):
    """安全退出当前进程，用于提权重启后终止旧实例。"""
    # 退出前确保释放互斥体和清理托盘图标
    release_single_instance_mutex()
    _cleanup_tray_icon_on_exit()
    try:
        os._exit(code)
    except Exception:
        sys.exit(code)


def _cleanup_tray_icon_on_exit():
    """清理托盘相关对象并刷新通知区域。"""
    global tray_icon_obj
    tray_icon_obj = globals().get("tray_icon_obj", None)
    if tray_icon_obj is not None:
        icon = tray_icon_obj
        tray_icon_obj = None
        try:
            icon.visible = False
        except Exception:
            pass
        try:
            icon.stop()
        except Exception:
            pass
    # 使用 Win32 API 刷新通知区域，强制系统回收残留的幽灵图标
    if IS_WINDOWS:
        try:
            # 方法：通过向通知区域发送鼠标移动消息来触发图标刷新
            # 找到系统托盘通知区域窗口
            tray_hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
            if tray_hwnd:
                # 查找通知区域子窗口
                tray_notify = ctypes.windll.user32.FindWindowExW(tray_hwnd, None, "TrayNotifyWnd", None)
                if tray_notify:
                    # 查找工具提示子窗口
                    toolbar_hwnd = ctypes.windll.user32.FindWindowExW(tray_notify, None, "ToolbarWindow32", None)
                    if toolbar_hwnd:
                        # 发送 WM_MOUSEMOVE 消息触发图标刷新
                        ctypes.windll.user32.SendMessageW(toolbar_hwnd, 0x0200, 0, 0)
        except Exception:
            pass
    try:
        time.sleep(0.08)
    except Exception:
        pass


def acquire_single_instance_mutex():
    """普通权限单实例检测：系统文件锁 + 本机回环端口辅助。"""
    try:
        return single_instance.acquire()
    except Exception as e:
        log(f"单实例守卫检测失败: {e}")
        return True


def _hwnd_message_parent():
    """返回 HWND_MESSAGE 的 ctypes 表示，用于创建/查找不可见 message-only IPC 窗口。"""
    try:
        return HWND(HWND_MESSAGE)
    except Exception:
        try:
            return ctypes.c_void_p(HWND_MESSAGE)
        except Exception:
            pointer_bits = ctypes.sizeof(ctypes.c_void_p) * 8
            return ctypes.c_void_p((1 << pointer_bits) + HWND_MESSAGE)


def find_existing_main_window(timeout=2.0):
    if not IS_WINDOWS:
        return None
    deadline = time.time() + max(0, timeout)
    while True:
        try:
            user32 = ctypes.windll.user32
            # 新版本使用 message-only 窗口承载 WM_COPYDATA，避免出现空白 WallpaperController 顶层窗口。
            existing = user32.FindWindowExW(_hwnd_message_parent(), HWND(0), WND_CLASS_NAME, None)
            if not existing:
                # 兼容旧版本曾创建的 0x0 顶层控制窗口。
                existing = user32.FindWindowW(WND_CLASS_NAME, None)
            if existing:
                return existing
            raise Exception("no window yet")
        except Exception as e:
            if "no window yet" not in str(e):
                log(f"查找已有实例 IPC 窗口失败: {e}")
        if time.time() >= deadline:
            return None
        time.sleep(0.1)


def send_command_to_hwnd(target_hwnd, command):
    if not IS_WINDOWS or not target_hwnd:
        return False
    try:
        payload = command.encode("utf-8") + b"\x00"
        buffer = ctypes.create_string_buffer(payload)
        cds = COPYDATASTRUCT()
        cds.dwData = 1
        cds.cbData = len(payload)
        cds.lpData = ctypes.cast(buffer, ctypes.c_void_p)
        # SendMessageW 的 lParam 是整数大小的 LPARAM。Python 3.14/ctypes 对类型更严格，
        # 直接传 byref(cds) 会报 “_ctypes.CArgObject cannot be interpreted as an integer”。
        lparam = LPARAM(ctypes.addressof(cds)) if IS_WINDOWS else ctypes.addressof(cds)
        result = ctypes.windll.user32.SendMessageW(HWND(_win_int(target_hwnd)), UINT(WM_COPYDATA), WPARAM(0), lparam)
        return int(result or 0) == 1
    except Exception as e:
        log(f"发送命令到已有实例失败: {e}")
        return False


def activate_existing_instance(show_notice=True):
    """激活已有实例的主窗口。

    使用多种方式确保窗口能被正确激活：
    1. 通过 WM_COPYDATA 发送 "show" 命令
    2. 使用 ShowWindow + SetForegroundWindow 强制前台显示
    3. 使用 AttachThreadInput 解决前台窗口锁定问题
    """
    existing = find_existing_main_window(timeout=5.0)
    activated = False
    if existing:
        activated = send_command_to_hwnd(existing, "show")
        try:
            # 获取当前线程和目标窗口的线程
            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            target_thread = ctypes.windll.user32.GetWindowThreadProcessId(existing, None)
            # 附加线程输入，解决 SetForegroundWindow 在某些情况下不生效的问题
            if current_thread != target_thread:
                ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, True)
            ctypes.windll.user32.ShowWindow(existing, 9)  # SW_RESTORE
            ctypes.windll.user32.ShowWindow(existing, 1)  # SW_SHOWNORMAL
            ctypes.windll.user32.SetForegroundWindow(existing)
            ctypes.windll.user32.BringWindowToTop(existing)
            # 取消线程附加
            if current_thread != target_thread:
                try:
                    ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, False)
                except Exception:
                    pass
        except Exception as e:
            log(f"激活已有实例失败: {e}")
    if show_notice:
        if existing:
            show_message(t("不要重复运行"), t("不要重复运行，已为您打开现有主界面。"))
        else:
            show_message(t("不要重复运行"), t("不要重复运行。检测到 ShangBackground 已经在启动或运行，本次启动已取消。"))
    return activated or existing is not None


def ensure_single_instance_or_exit():
    """单实例检测（已弃用，检测逻辑已移至 main() 最前面）。

    保留此函数以兼容可能的调用点，但 main() 中已不再使用。
    新代码应直接调用 acquire_single_instance_mutex() + find_existing_main_window()。
    """
    if not IS_WINDOWS:
        return
    if not acquire_single_instance_mutex():
        log("检测到已有实例，打开现有主界面并退出本次启动")
        activate_existing_instance(show_notice=True)
        sys.exit(0)
    existing = find_existing_main_window(timeout=0.3)
    if existing:
        log("检测到已有主窗口，打开现有主界面并退出本次启动")
        # 释放刚获取的互斥体（因为要退出了）
        release_single_instance_mutex()
        activate_existing_instance(show_notice=True)
        sys.exit(0)


def get_startup_folder_path_windows():
    if not IS_WINDOWS:
        return ""
    try:
        CSIDL_STARTUP = 7
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_STARTUP, None, 0, buf)
        return buf.value
    except Exception as e:
        log(f"获取 Windows 启动文件夹失败: {e}")
        return os.path.join(os.path.expanduser('~'), r'AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup')


def get_startup_vbs_path(name=STARTUP_VBS_NAME):
    folder = get_startup_folder_path_windows()
    return os.path.join(folder, name) if folder else name


def remove_legacy_startup_entries():
    if not IS_WINDOWS:
        return
    # 清理旧注册表启动项名称，避免任务管理器/启动项里显示旧名称。
    if winreg is not None:
        try:
            run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE)
            for value_name in LEGACY_STARTUP_VALUE_NAMES:
                if value_name != STARTUP_ITEM_NAME:
                    try:
                        winreg.DeleteValue(key, value_name)
                        log(f"已清理旧开机自启动注册表项: {value_name}")
                    except FileNotFoundError:
                        pass
            winreg.CloseKey(key)
        except Exception as e:
            log(f"清理旧开机自启动注册表项失败: {e}")
    # 如果已经启用新 VBS，则删除旧 PowerOn.vbs，避免出现两个启动项。
    try:
        new_vbs = get_startup_vbs_path(STARTUP_VBS_NAME)
        old_vbs = get_startup_vbs_path("PowerOn.vbs")
        if os.path.exists(new_vbs) and old_vbs != new_vbs and os.path.exists(old_vbs):
            os.remove(old_vbs)
            log(f"已清理旧开机自启动 VBS: {old_vbs}")
    except Exception as e:
        log(f"清理旧开机自启动 VBS 失败: {e}")


# 版本检查全局变量
remote_version = "1"
remote_release_notes = ""
remote_download_urls = {"GitHub Release": "", t("发布页"): "https://github.com/purrfecto114-lgtm/ShangBackground/releases/latest"}
show_update_flag = False
check_failed = False


def _history_key(path: str) -> str:
    """Return a stable key so the same image path only appears once in history."""
    try:
        return os.path.normcase(os.path.abspath(os.path.expanduser(str(path or ""))))
    except Exception:
        return str(path or "").strip().lower()


def _normalize_wallpaper_path(path: str) -> str:
    if not path:
        return ""
    try:
        return os.path.abspath(os.path.expanduser(str(path)))
    except Exception:
        return str(path)


def dedupe_wallpaper_history(history, *, keep_missing: bool = True, limit: int = 50):
    """Remove duplicate wallpaper entries while preserving order.

    This prevents language switching / elevated restart / path case differences from creating
    repeated history thumbnails for the same image.
    """
    result = []
    seen = set()
    for item in history or []:
        if not item:
            continue
        normalized = _normalize_wallpaper_path(item)
        if not keep_missing and not os.path.isfile(normalized):
            continue
        key = _history_key(normalized)
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


def load_config():
    """加载配置文件，如果不存在则返回默认配置。"""
    default = {
        "mode": "幻灯片放映",
        "slide_folder": "",
        "slide_seconds": 300,
        "shuffle": False,
        "fit_mode": "填充",
        "single_image": "",
        "solid_color": DEFAULT_SOLID_COLOR,
        "gradient_color2": DEFAULT_GRADIENT_COLOR2,
        "theme_color": DEFAULT_THEME_COLOR,
        "gradient_angle": 60,
        "current_wallpaper": "",
        "history": [],
        "auto_start": False,
        "ctx_last_wallpaper": False,
        "ctx_next_wallpaper": False,
        "ctx_random_wallpaper": False,
        "ctx_personalize": False,
        "ctx_jump_to_wallpaper": False,
        "ctx_global_settings": False,
        "ctx_set_wallpaper": False,
        "hotkey_previous": "U",
        "hotkey_next": "N",
        "hotkey_random": "3",
        "hotkey_jump": "V",
        "recent_folders": [],
        "run_in_background": True,  # 默认后台运行
        "tray_icon": True,  # 默认托盘图标
        "tray_click_action": "next",
        "tray_menu_items": ["show", "previous", "next", "random", "bing", "jump", "about", "exit"],
        "dark_mode": False,
        "bing_cache_dir": "",
        "bing_sync_count": 1,
        "bing_next_index": 0,
        "bing_auto_cleanup": False,
        "bing_auto_update_on_start": False,
        "bing_auto_update_count": 1,
        "bing_auto_delete_on_start": False,
        "bing_auto_delete_count": 1,
        "log_enabled": False,  # 默认关闭日志文件记录；在新版日志页开启时需要先选择路径
        "log_file_path": "",  # 日志文件保存路径，首次开启日志时填写
        "ignored_version": "",  # 用户选择忽略的版本号
        "app_theme": "default",  # 默认使用 Qt/系统原生样式
        "font_path": "",
        "dpi_scale": 1.0,
        "language": "zh",
    }
    source_path = ""
    for candidate in (CONFIG_PATH, LEGACY_CONFIG_PATH, BUNDLED_CONFIG_PATH, LEGACY_BUNDLED_CONFIG_PATH):
        if candidate and os.path.exists(candidate):
            source_path = candidate
            break
    if source_path:
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("settings.json 根节点必须是对象")
            data = default.copy()
            data.update(loaded)
            log(f"配置加载成功: {os.path.basename(source_path)}")
            # 自动转换旧配置。
            converted = False
            if "user_id" in data:
                data.pop("user_id", None)
                converted = True
            if "tray_menu_items" in data and data["tray_menu_items"]:
                first_item = data["tray_menu_items"][0]
                if isinstance(first_item, dict) and "action" in first_item:
                    # 旧格式：转换为只存储 action 字符串的新格式
                    new_items = [item["action"] for item in data["tray_menu_items"]]
                    data["tray_menu_items"] = new_items
                    converted = True
            # 迁移右键菜单配置。
            if "ctx_jump_to_wallpaper" not in data:
                data["ctx_jump_to_wallpaper"] = bool(data.get("ctx_global_settings", False))
                converted = True
            data["ctx_personalize"] = False
            data["ctx_global_settings"] = False
            data["ctx_set_wallpaper"] = False
            for _key, _default in {"hotkey_previous": "U", "hotkey_next": "N", "hotkey_random": "3", "hotkey_jump": "V"}.items():
                if _key not in data:
                    data[_key] = _default
                    converted = True
            if "log_enabled" not in data:
                data["log_enabled"] = False
                converted = True
            if "log_file_path" not in data:
                data["log_file_path"] = ""
                converted = True
            if "app_theme" not in data:
                data["app_theme"] = "default"
                converted = True
            if "theme_color" not in data:
                data["theme_color"] = default.get("theme_color", DEFAULT_THEME_COLOR)
                converted = True
            if "font_path" not in data:
                data["font_path"] = ""
                converted = True
            if "dpi_scale" not in data:
                data["dpi_scale"] = 1.0
                converted = True
            if "language" not in data:
                data["language"] = "zh"
                converted = True
            if "font_size" in data:
                data.pop("font_size", None)
                converted = True
            if str(data.get("solid_color", "")).lower() in {"#4facfe", "#2d2d2d"}:
                data["solid_color"] = "#ffffff"
                converted = True
            if str(data.get("gradient_color2", "")).lower() in {"#00f2fe", "#4a4a4a"}:
                data["gradient_color2"] = "#ffffff"
                converted = True
            if data.get("bing_cache_dir") == os.path.join(BASE_DIR, "bing_wallpapers"):
                data["bing_cache_dir"] = ""
                converted = True
            if "bing_next_index" not in data:
                data["bing_next_index"] = 0
                converted = True
            if "bing_auto_cleanup" not in data:
                data["bing_auto_cleanup"] = False
                converted = True
            for _key, _default in {
                "bing_auto_update_on_start": False,
                "bing_auto_update_count": 1,
                "bing_auto_delete_on_start": False,
                "bing_auto_delete_count": 1,
            }.items():
                if _key not in data:
                    data[_key] = _default
                    converted = True
            cleaned_history = dedupe_wallpaper_history(data.get("history", []), keep_missing=True)
            if cleaned_history != data.get("history", []):
                data["history"] = cleaned_history
                converted = True
            if data.get("current_wallpaper"):
                normalized_current = _normalize_wallpaper_path(data.get("current_wallpaper", ""))
                if normalized_current != data.get("current_wallpaper"):
                    data["current_wallpaper"] = normalized_current
                    converted = True
            old_mode = data.get("mode")
            new_mode = normalize_mode_key(old_mode, default.get("mode", "幻灯片放映"))
            if old_mode != new_mode:
                data["mode"] = new_mode
                converted = True
            old_fit = data.get("fit_mode")
            new_fit = normalize_style_key(old_fit, default.get("fit_mode", "填充"))
            if old_fit != new_fit:
                data["fit_mode"] = new_fit
                converted = True

            # 转换完或从旧 shezhi.json 读取时，统一保存到 settings.json。
            if converted or source_path != CONFIG_PATH:
                try:
                    tmp_path = CONFIG_PATH + ".tmp"
                    with open(tmp_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    try:
                        os.chmod(tmp_path, 0o600)
                    except OSError:
                        pass
                    os.replace(tmp_path, CONFIG_PATH)
                    log("已保存转换后的 settings.json 配置文件")
                except Exception as e:
                    log(f"保存转换后的配置失败: {e}")
            return data
        except Exception as e:
            log("加载配置失败: " + str(e))
            return default
    return default


def save_config():
    """保存配置到文件，使用线程锁保护写入操作。"""
    with _config_lock:
        try:
            config.pop("user_id", None)
            if "tray_click_action" not in config:
                config["tray_click_action"] = "next"
            if "tray_menu_items" not in config:
                config["tray_menu_items"] = ["show", "previous", "next", "random", "bing", "jump", "about", "exit"]
            if "log_enabled" not in config:
                config["log_enabled"] = False
            if "log_file_path" not in config:
                config["log_file_path"] = ""
            if "app_theme" not in config:
                config["app_theme"] = "default"
            if "theme_color" not in config:
                config["theme_color"] = DEFAULT_THEME_COLOR
            if "font_path" not in config:
                config["font_path"] = ""
            if "dpi_scale" not in config:
                config["dpi_scale"] = 1.0
            try:
                config["dpi_scale"] = max(0.75, min(2.0, float(config.get("dpi_scale", 1.0))))
            except Exception:
                config["dpi_scale"] = 1.0
            config.pop("font_size", None)
            config["ctx_jump_to_wallpaper"] = bool(config.get("ctx_jump_to_wallpaper", config.get("ctx_global_settings", False)))
            config["ctx_global_settings"] = False
            config["ctx_personalize"] = False
            config["ctx_set_wallpaper"] = False
            for _key, _default in {"hotkey_previous": "U", "hotkey_next": "N", "hotkey_random": "3", "hotkey_jump": "V"}.items():
                config.setdefault(_key, _default)
            if config.get("bing_cache_dir") is None:
                config["bing_cache_dir"] = ""
            config["bing_auto_cleanup"] = bool(config.get("bing_auto_cleanup", False))
            config["bing_auto_update_on_start"] = bool(config.get("bing_auto_update_on_start", False))
            config["bing_auto_delete_on_start"] = bool(config.get("bing_auto_delete_on_start", False))
            try:
                config["bing_auto_update_count"] = max(1, min(16, int(config.get("bing_auto_update_count", 1))))
            except Exception:
                config["bing_auto_update_count"] = 1
            try:
                config["bing_auto_delete_count"] = max(1, min(200, int(config.get("bing_auto_delete_count", 1))))
            except Exception:
                config["bing_auto_delete_count"] = 1
            try:
                config["bing_next_index"] = max(0, int(config.get("bing_next_index", 0)))
            except Exception:
                config["bing_next_index"] = 0
            config["history"] = dedupe_wallpaper_history(config.get("history", []), keep_missing=True)
            if config.get("current_wallpaper"):
                config["current_wallpaper"] = _normalize_wallpaper_path(config.get("current_wallpaper", ""))
            config["mode"] = normalize_mode_key(config.get("mode", "幻灯片放映"))
            config["fit_mode"] = normalize_style_key(config.get("fit_mode", "填充"))
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            tmp_path = CONFIG_PATH + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            try:
                os.chmod(tmp_path, 0o600)
            except OSError:
                pass
            os.replace(tmp_path, CONFIG_PATH)
            log("配置已保存")
        except Exception as e:
            log("保存配置失败: " + str(e))


# 配置文件写入线程锁，避免多线程并发写入导致数据损坏
_config_lock = threading.Lock()

config = load_config()



# 上报用户使用情况（另开个线程，能不卡界面）
def report_usage():
    """隐私保护：默认不进行联网统计。"""
    return


slide_timer = None
slide_timer_lock = threading.Lock()
slide_enabled = False
slide_images = []

last_wallpaper_change_time = None


def log_time_diff(operation_name, new_wallpaper):
    global last_wallpaper_change_time
    current_time = time.time() * 1000
    if last_wallpaper_change_time is not None:
        time_diff = current_time - last_wallpaper_change_time
        log(f"[时间差] {operation_name} 切换到 {os.path.basename(new_wallpaper)}，距离上次切换 {time_diff:.2f} ms")
    else:
        log(f"[时间差] {operation_name} 首次切换到 {os.path.basename(new_wallpaper)}")
    last_wallpaper_change_time = current_time


current_preview_image = None
overlay_image = None


def get_current_wallpaper():
    """获取当前系统壁纸路径"""
    try:
        return get_current_wallpaper_platform()
    except Exception as e:
        log("获取当前壁纸失败: " + str(e))
        return ""


def push_wallpaper(path):
    """将壁纸路径推入历史记录；同一张图片在历史中只保留一次。"""
    path = _normalize_wallpaper_path(path)
    if not path or not os.path.isfile(path):
        return
    hist = dedupe_wallpaper_history(config.get("history", []), keep_missing=True)
    path_key = _history_key(path)
    hist = [p for p in hist if _history_key(p) != path_key]
    hist.insert(0, path)
    config["history"] = hist[:50]
    config["current_wallpaper"] = path
    save_config()
    log("已记录壁纸: " + os.path.basename(path) + " | 历史总数: " + str(len(config.get("history", []))))
    if root and canvas:
        root.after(0, lambda: update_preview(path))


def set_wallpaper_direct(path, operation_name="系统", skip_history=False):
    """直接设置壁纸到系统，区分 OSError 和通用异常。"""
    path = _normalize_wallpaper_path(path)
    if not os.path.isfile(path):
        log("壁纸文件不存在: " + path)
        return False
    try:
        fit_mode = config.get("fit_mode", "填充")
        configure_windows_fit_mode(fit_mode, winreg, log)
        set_wallpaper_platform(path)
        if not skip_history:
            config["current_wallpaper"] = path
            save_config()
        log("设置壁纸成功: " + os.path.basename(path))
        log_time_diff(operation_name, path)
        if root and canvas:
            root.after(0, lambda: update_preview(path))
        return True
    except OSError as e:
        log("设置壁纸失败（系统错误）: " + str(e))
        return False
    except Exception as e:
        log("设置壁纸失败（未知错误）: " + str(e))
        return False


def get_windows_wallpaper_style():
    if not IS_WINDOWS or winreg is None:
        return {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
            style = {}
            for value_name in ("WallpaperStyle", "TileWallpaper"):
                try:
                    style[value_name] = winreg.QueryValueEx(key, value_name)[0]
                except FileNotFoundError:
                    pass
            return style
    except Exception as e:
        log(f"读取原始壁纸样式失败: {e}")
        return {}


def restore_windows_wallpaper_style(style):
    if not IS_WINDOWS or winreg is None or not style:
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE) as key:
            for value_name, value in style.items():
                winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, str(value))
    except Exception as e:
        log(f"恢复原始壁纸样式失败: {e}")


def capture_session_original_wallpaper():
    global session_original_wallpaper, session_original_wallpaper_style, session_original_wallpaper_captured
    if session_original_wallpaper_captured:
        return
    # 提权后的新进程优先继承提权前写入的会话记录，避免把“已经被本程序改过的壁纸”误认为启动前壁纸。
    if _load_session_original_wallpaper():
        return
    session_original_wallpaper_captured = True
    try:
        current = get_current_wallpaper()
        if current:
            session_original_wallpaper = current
            session_original_wallpaper_style = get_windows_wallpaper_style()
            _persist_session_original_wallpaper()
            log(f"已记录启动前壁纸: {session_original_wallpaper}")
        else:
            log("启动前壁纸为空，退出时不执行恢复")
    except Exception as e:
        log(f"记录启动前壁纸失败: {e}")


def restore_session_original_wallpaper():
    if not session_original_wallpaper:
        _load_session_original_wallpaper()
    target = session_original_wallpaper
    if not target:
        return False
    if not os.path.isfile(target):
        log(f"启动前壁纸文件不存在，跳过恢复: {target}")
        return False
    try:
        current = get_current_wallpaper()
        if current and os.path.normcase(os.path.abspath(current)) == os.path.normcase(os.path.abspath(target)):
            log("当前壁纸已经是启动前壁纸，无需恢复")
            return True
    except Exception:
        pass
    try:
        restore_windows_wallpaper_style(session_original_wallpaper_style)
        set_wallpaper_platform(target)
        config["current_wallpaper"] = _normalize_wallpaper_path(target)
        save_config()
        log("已恢复启动前壁纸: " + os.path.basename(target))
        return True
    except Exception as e:
        log(f"恢复启动前壁纸失败: {e}")
        return False


def set_wallpaper(path, operation_name="用户", force=False):
    path = _normalize_wallpaper_path(path)
    if not os.path.isfile(path):
        return False
    push_wallpaper(path)
    return set_wallpaper_direct(path, operation_name)


def previous_wallpaper():
    """切换到上一张壁纸，支持历史记录回退。"""
    hist = dedupe_wallpaper_history(config.get("history", []), keep_missing=False)
    config["history"] = hist[:50]
    log("当前历史: " + str([os.path.basename(p) for p in hist[:5]]) + ("..." if len(hist) > 5 else ""))
    if len(hist) < 2:
        log("没有上一张壁纸")
        show_message(t("提示喵"), t("没有上一张壁纸"))
        log("=" * 50)
        return
    found = None
    for p in hist[1:]:
        if os.path.exists(p):
            found = p
            break
        else:
            log("历史壁纸文件丢失: " + p)
    if found is None:
        log("历史壁纸文件都已丢失")
        show_message(t("错误"), t("历史壁纸文件已丢失"))
        log("=" * 50)
        return
    found_key = _history_key(found)
    new_hist = [found] + [p for p in hist if _history_key(p) != found_key]
    config["history"] = dedupe_wallpaper_history(new_hist, keep_missing=True)[:50]
    save_config()
    log("回退到: " + os.path.basename(found))
    success = set_wallpaper(found, "右键菜单(上一张)")
    if success and normalize_mode_key(config.get("mode")) == "幻灯片放映":
        try:
            reset_slide_timer()
        except Exception:
            pass
    log("=" * 50)


def next_wallpaper():
    """切换到下一张壁纸，根据当前模式选择顺序或随机切换。"""
    if normalize_mode_key(config.get("mode")) != "幻灯片放映":
        log("当前模式不是幻灯片放映，无法使用下一张功能")
        show_message(t("提示喵"), t("请在幻灯片放映模式下使用此功能"))
        log("=" * 50)
        return
    global slide_images
    if not slide_images:
        folder = config["slide_folder"]
        if folder and os.path.isdir(folder):
            images = [os.path.join(folder, f) for f in os.listdir(folder)
                      if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))]
            if images:
                if config["shuffle"]:
                    random.shuffle(images)
                slide_images = images
                log(f"重新加载 {len(images)} 张图片")
            else:
                log("幻灯片列表为空，无法切换到下一张")
                show_message(t("提示喵"), t("请先设置幻灯片文件夹"))
                log("=" * 50)
                return
        else:
            log("幻灯片列表为空，无法切换到下一张")
            show_message(t("提示喵"), t("请先设置幻灯片文件夹"))
            log("=" * 50)
            return
    next_img = get_next_wallpaper()
    if next_img is None:
        log("无法获取下一张壁纸")
        show_message(t("提示喵"), t("无法获取下一张壁纸"))
        log("=" * 50)
        return
    log("切换到: " + os.path.basename(next_img))
    success = set_wallpaper(next_img, "右键菜单(下一张)")
    if success:
        try:
            reset_slide_timer()
        except Exception:
            pass
    log("=" * 50)


def random_wallpaper():
    """随机切换到一张壁纸，从幻灯片文件夹中随机选择。"""
    if normalize_mode_key(config.get("mode")) != "幻灯片放映":
        log("当前模式不是幻灯片放映，无法使用随机功能")
        show_message(t("提示喵"), t("请在幻灯片放映模式下使用此功能"))
        log("=" * 50)
        return
    global slide_images
    folder = config["slide_folder"]
    if not folder or not os.path.isdir(folder):
        log("幻灯片文件夹无效")
        show_message(t("提示喵"), t("请先设置幻灯片文件夹"))
        log("=" * 50)
        return

    # 新版随机概率使用 random.json 中的权重，不再依赖物理副本文件。
    slide_images = random_copy.get_original_image_paths(folder)
    if not slide_images:
        log("文件夹中没有图片")
        show_message(t("提示喵"), t("文件夹中没有图片"))
        log("=" * 50)
        return

    current = config.get("current_wallpaper", "")
    random_img = random_copy.weighted_choice(folder, current)
    if not random_img:
        random_img = random.choice(slide_images)
    log("随机切换到: " + os.path.basename(random_img))
    success = set_wallpaper(random_img, "右键菜单(随机)")
    if success:
        try:
            reset_slide_timer()
        except Exception:
            pass
    log("=" * 50)


def set_fit_mode(mode):
    try:
        mode = normalize_style_key(mode)
        config["fit_mode"] = mode
        configure_windows_fit_mode(mode, winreg, log)
        current = config.get("current_wallpaper")
        if current and os.path.exists(current):
            set_wallpaper_direct(current, "适应模式")
        log("适应模式: " + mode)
    except Exception as e:
        log("设置适应模式失败: " + str(e))


def get_next_wallpaper():
    global slide_images
    if not slide_images:
        return None
    current = config.get("current_wallpaper", "")
    if current in slide_images:
        idx = slide_images.index(current)
        next_idx = (idx + 1) % len(slide_images)
        return slide_images[next_idx]
    return slide_images[0] if slide_images else None


def slide_next():
    global slide_timer, slide_enabled
    with slide_timer_lock:
        if not slide_enabled:
            return
        # 如果开启了随机顺序，使用 random.json 中的权重选择原始壁纸。
        if config.get("shuffle", False):
            folder = config["slide_folder"]
            if folder and os.path.isdir(folder):
                current = config.get("current_wallpaper", "")
                next_img = random_copy.weighted_choice(folder, current) or get_next_wallpaper()
            else:
                next_img = get_next_wallpaper()
        else:
            next_img = get_next_wallpaper()

        if next_img is None:
            return
        set_wallpaper(next_img, "幻灯片")
        if slide_enabled:
            if root is not None:
                slide_timer = root.after(int(config["slide_seconds"] * 1000), slide_next)
            else:
                # 降级：使用 threading.Timer（但 root 应该存在）
                slide_timer = threading.Timer(config["slide_seconds"], slide_next)
                slide_timer.daemon = True
                slide_timer.start()


def reset_slide_timer():
    """重置幻灯片定时器，根据配置的间隔时间重新计时。"""
    with slide_timer_lock:
        if not slide_enabled or not slide_images:
            return
        current = config.get("current_wallpaper", "")
        if current not in slide_images:
            return
        if slide_timer:
            if root is not None and isinstance(slide_timer, str):
                try:
                    root.after_cancel(slide_timer)
                except Exception:
                    pass
            else:
                try:
                    slide_timer.cancel()
                except Exception:
                    pass
            slide_timer = None
        if root is not None:
            slide_timer = root.after(int(config["slide_seconds"] * 1000), slide_next)
        else:
            slide_timer = threading.Timer(config["slide_seconds"], slide_next)
            slide_timer.daemon = True
            slide_timer.start()


def start_slideshow():
    """启动幻灯片。先计算播放列表并释放锁，再执行可能较慢的壁纸设置，降低切换模式卡顿和死锁风险。"""
    global slide_images, slide_enabled, slide_timer
    target_to_apply = None
    restore_current = None
    with slide_timer_lock:
        if normalize_mode_key(config.get("mode")) != "幻灯片放映":
            return False
        folder = config["slide_folder"]
        if not folder or not os.path.isdir(folder):
            return False
        images = random_copy.get_original_image_paths(folder)
        if not images:
            return False
        if config["shuffle"]:
            random.shuffle(images)
        slide_images = images
        log(f"加载 {len(images)} 张图片")
        current = config.get("current_wallpaper", "")
        if current not in images:
            target_to_apply = images[0]
        else:
            restore_current = current

        if slide_timer:
            try:
                if root is not None and isinstance(slide_timer, str):
                    root.after_cancel(slide_timer)
                else:
                    slide_timer.cancel()
            except Exception as e:
                log(f"取消旧定时器失败: {e}")
            slide_timer = None
        slide_enabled = True

    # 不在 slide_timer_lock 中执行系统壁纸设置；系统 API 可能耗时。
    if target_to_apply:
        set_wallpaper(target_to_apply, "幻灯片启动")
    elif restore_current:
        set_wallpaper_direct(restore_current, "幻灯片恢复")

    with slide_timer_lock:
        if not slide_enabled:
            return True
        if root is not None:
            slide_timer = root.after(int(config["slide_seconds"] * 1000), slide_next)
        else:
            slide_timer = threading.Timer(config["slide_seconds"], slide_next)
            slide_timer.daemon = True
            slide_timer.start()
    log(f"幻灯片启动，间隔 {config['slide_seconds']} 秒")
    return True


def stop_slideshow():
    global slide_enabled, slide_timer
    with slide_timer_lock:
        slide_enabled = False
        if slide_timer:
            try:
                if root is not None and isinstance(slide_timer, str):
                    root.after_cancel(slide_timer)
                else:
                    slide_timer.cancel()
            except Exception:
                pass
            slide_timer = None
        log("幻灯片已停止")


def restart_slideshow():
    stop_slideshow()
    if normalize_mode_key(config.get("mode")) == "幻灯片放映" and config["slide_folder"]:
        start_slideshow()


# ====================== 优化的渐变生成函数 ======================
def create_gradient_wallpaper_optimized(color1, color2, angle=0):
    """生成渐变壁纸，用向量化操作加快速度"""
    try:
        screen_width = get_screen_size(root)[0]
        screen_height = get_screen_size(root)[1]
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        rad = math.radians(angle)
        dx = math.cos(rad)
        dy = math.sin(rad)
        center_x = screen_width / 2
        center_y = screen_height / 2
        length = math.sqrt(screen_width ** 2 + screen_height ** 2)
        start_x = center_x - dx * length / 2
        start_y = center_y - dy * length / 2
        end_x = center_x + dx * length / 2
        end_y = center_y + dy * length / 2
        line_dx = end_x - start_x
        line_dy = end_y - start_y
        line_len_sq = line_dx ** 2 + line_dy ** 2
        if HAS_NUMPY:
            x = np.arange(screen_width)
            y = np.arange(screen_height)
            xx, yy = np.meshgrid(x, y)
            px = xx - start_x
            py = yy - start_y
            if line_len_sq == 0:
                t = np.zeros((screen_height, screen_width))
            else:
                t = (px * line_dx + py * line_dy) / line_len_sq
                t = np.clip(t, 0, 1)
            r = (r1 * (1 - t) + r2 * t).astype(np.uint8)
            g = (g1 * (1 - t) + g2 * t).astype(np.uint8)
            b = (b1 * (1 - t) + b2 * t).astype(np.uint8)
            rgb_array = np.stack([r, g, b], axis=2)
            img = Image.fromarray(rgb_array, 'RGB')
        else:
            img = Image.new("RGB", (screen_width, screen_height))
            pixels = img.load()
            for y in range(screen_height):
                for x in range(screen_width):
                    px = x - start_x
                    py = y - start_y
                    if line_len_sq == 0:
                        t = 0
                    else:
                        t = (px * line_dx + py * line_dy) / line_len_sq
                        t = max(0, min(1, t))
                    r = int(r1 * (1 - t) + r2 * t)
                    g = int(g1 * (1 - t) + g2 * t)
                    b = int(b1 * (1 - t) + b2 * t)
                    pixels[x, y] = (r, g, b)
        diy_dir = os.path.join(BASE_DIR, "diy")
        os.makedirs(diy_dir, exist_ok=True)
        bmp_path = os.path.join(diy_dir, "gradient_wallpaper.bmp")
        img.save(bmp_path)
        log(f"渐变壁纸生成完成 (使用{'NumPy' if HAS_NUMPY else '优化Python'}引擎)")
        return bmp_path
    except Exception as e:
        log("创建渐变壁纸失败: " + str(e))
        return None


def create_gradient_wallpaper(color1, color2, angle=0):
    return create_gradient_wallpaper_optimized(color1, color2, angle)


def apply_gradient():
    color1 = config.get("solid_color", "#2d2d2d")
    color2 = config.get("gradient_color2", "#4a4a4a")
    angle = config.get("gradient_angle", 0)
    bmp_path = create_gradient_wallpaper(color1, color2, angle)
    if bmp_path and os.path.exists(bmp_path):
        set_wallpaper(bmp_path, "渐变壁纸", force=True)


def apply_solid():
    color = config.get("solid_color", "#2d2d2d")
    screen_width = get_screen_size(root)[0]
    screen_height = get_screen_size(root)[1]
    img = Image.new("RGB", (screen_width, screen_height), color)
    diy_dir = os.path.join(BASE_DIR, "diy")
    os.makedirs(diy_dir, exist_ok=True)
    bmp_path = os.path.join(diy_dir, "solid_wallpaper.bmp")
    img.save(bmp_path)
    if os.path.exists(bmp_path):
        set_wallpaper(bmp_path, "纯色壁纸", force=True)


def schedule_apply():
    if normalize_mode_key(config.get("mode")) == "渐变":
        apply_gradient()
    elif normalize_mode_key(config.get("mode")) == "纯色":
        apply_solid()


def update_preview(img_path):
    return


def show_overlay():
    return

def show_main_window_now():
    """显示主窗口并强制置于前台。

    使用 AttachThreadInput 解决 SetForegroundWindow 在某些情况下
    无法将窗口置于前台的问题（Windows 前台锁定限制）。
    """
    global pending_show_request
    pending_show_request = False
    if root is None:
        return
    try:
        root.deiconify()
        root.state("normal")
        root.lift()
        root.focus_force()
        if IS_WINDOWS:
            try:
                hwnd_root = root.winfo_id()
                current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
                target_thread = ctypes.windll.user32.GetWindowThreadProcessId(hwnd_root, None)
                if current_thread != target_thread:
                    ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, True)
                ctypes.windll.user32.SetForegroundWindow(hwnd_root)
                ctypes.windll.user32.BringWindowToTop(hwnd_root)
                if current_thread != target_thread:
                    try:
                        ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, False)
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception as e:
        log(f"打开已有主界面失败: {e}")


def request_show_main_window():
    global pending_show_request
    pending_show_request = True
    if root is not None:
        try:
            root.after(0, show_main_window_now)
        except Exception as e:
            log(f"请求打开主界面失败: {e}")


_WINFUNCTYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
WNDPROC = _WINFUNCTYPE(
    ctypes.c_ssize_t,
    ctypes.c_void_p,
    ctypes.c_uint,
    ctypes.c_void_p,
    ctypes.c_void_p,
) if IS_WINDOWS else (lambda func: func)


@WNDPROC
def window_proc(hwnd, msg, wparam, lparam):
    hwnd_i = _win_int(hwnd)
    msg_i = int(msg or 0)
    wparam_i = _win_int(wparam)
    lparam_i = _win_int(lparam)
    if msg_i == WM_SETTINGCHANGE:
        log("检测到系统设置变化，检查壁纸")
        current = get_current_wallpaper()
        if current and current != config.get("current_wallpaper", ""):
            log(f"系统壁纸已改变: {os.path.basename(current)}")
            push_wallpaper(current)
            if root and canvas:
                root.after(0, lambda: update_preview(current))
        return 0
    elif msg_i == WM_COPYDATA:
        try:
            if not lparam_i:
                return 0
            cds = ctypes.cast(lparam_i, ctypes.POINTER(COPYDATASTRUCT)).contents
            if cds.dwData == 1:
                data = ctypes.string_at(cds.lpData, cds.cbData)
                command = data.decode('utf-8').rstrip('\x00')
                log(f"收到消息: {command}")
                if command == "previous":
                    previous_wallpaper()
                    return 1
                elif command == "next":
                    next_wallpaper()
                    return 1
                elif command == "random":
                    random_wallpaper()
                    return 1
                elif command == "show":
                    request_show_main_window()
                    return 1
                elif command.startswith("set_wallpaper|"):
                    target = command.split("|", 1)[1]
                    if os.path.isfile(target):
                        log(f"侧边栏请求切换壁纸: {target}")
                        push_wallpaper(target)
                        set_wallpaper_direct(target, "侧边栏切换")
                    return 1
                elif command == "create_file":
                    return 1
        except Exception as e:
            log(f"消息处理错误: {e}")
        return 0
    return ctypes.windll.user32.DefWindowProcW(hwnd_i, msg_i, wparam_i, lparam_i)


def create_message_window():
    global hwnd, use_message
    if not IS_WINDOWS:
        log("当前平台不需要 Windows 消息窗口")
        return None
    try:
        wc = WNDCLASS()
        wc.style = 0
        wc.lpfnWndProc = ctypes.cast(window_proc, ctypes.c_void_p)
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        wc.hIcon = None
        wc.hCursor = None
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = WND_CLASS_NAME
        atom = ctypes.windll.user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            err = ctypes.windll.kernel32.GetLastError()
            if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS
                log(f"注册窗口类失败: {err}")
                return None
        hwnd = ctypes.windll.user32.CreateWindowExW(
            0,
            WND_CLASS_NAME,
            "",
            0,
            0, 0, 0, 0,
            _hwnd_message_parent(),
            0,
            wc.hInstance,
            0
        )
        if not hwnd:
            log("创建窗口失败")
            return None
        use_message = True
        log(f"IPC message-only 窗口创建成功, HWND: {hwnd}")
        return hwnd
    except Exception as e:
        log(f"创建消息窗口失败: " + str(e))
        return None


def message_loop():
    if not IS_WINDOWS or ctypes.wintypes is None:
        return
    msg = ctypes.wintypes.MSG()
    while True:
        ret = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret <= 0:
            break
        ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
        ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))


def start_message_window():
    global _message_loop_thread
    if not IS_WINDOWS:
        return None
    if hwnd:
        return hwnd
    msg_hwnd = create_message_window()
    if msg_hwnd and (_message_loop_thread is None or not _message_loop_thread.is_alive()):
        _message_loop_thread = threading.Thread(target=message_loop, daemon=True)
        _message_loop_thread.start()
        log("消息循环已启动")
    return msg_hwnd


def send_command(command):
    if not IS_WINDOWS:
        return False
    if not hwnd or not use_message:
        return False
    return send_command_to_hwnd(hwnd, command)


def register_context(show_admin_prompt=False):
    """注册或同步 Windows 桌面右键菜单。

    参数:
        show_admin_prompt: 是否在权限不足时弹窗提示用户以管理员身份重启

    返回:
        True 注册成功，False 注册失败或权限不足
    """
    if not IS_WINDOWS or winreg is None:
        log("当前平台不支持 Windows 桌面右键菜单注册，已跳过")
        return False
    if not is_windows_admin():
        msg = (
            t("桌面右键菜单需要写入注册表 HKEY_CLASSES_ROOT，必须以管理员身份运行才能添加或移除。\n\n")
            + t("点击「确定」将以管理员身份重启应用并自动完成注册，\n")
            + t("点击「取消」则跳过注册，不影响主程序、托盘和壁纸切换功能。")
        )
        log("未以管理员权限启动，已跳过右键菜单注册/同步")
        if show_admin_prompt:
            show_message(t("需要管理员权限"), msg)
        return False
    try:
        def build_action_command(*args):
            """生成右键菜单命令。

            PyInstaller onedir 打包后必须直接调用 exe；源码运行时使用 sys.executable + main.py。
            """
            if is_frozen():
                parts = [sys.executable, *args]
            else:
                parts = [sys.executable, os.path.join(BASE_DIR, "main.py"), *args]
            return subprocess.list2cmdline([str(part) for part in parts])

        # 辅助函数：获取快捷键后缀
        def get_hotkey_suffix(key_name):
            hotkey = config.get(f"hotkey_{key_name}", "")
            if hotkey:
                # 格式化快捷键显示（例如 "ctrl+shift+n" -> "Ctrl+Shift+N"）
                parts = hotkey.split('+')
                formatted = []
                for p in parts:
                    if p == "ctrl":
                        formatted.append("Ctrl")
                    elif p == "alt":
                        formatted.append("Alt")
                    elif p == "shift":
                        formatted.append("Shift")
                    elif p == "win":
                        formatted.append("Win")
                    else:
                        # 首字母大写
                        formatted.append(p.capitalize() if len(p) == 1 else p)
                display = "+".join(formatted)
                # 对于单个字母或数字，作为加速键（Alt+Key）处理，添加 & 前缀
                if len(parts) == 1 and len(parts[0]) == 1:
                    key_char = parts[0].upper()
                    return f"\t&{key_char}"
                else:
                    # 多个键组合，只显示快捷键，不设加速键
                    return f"\t{display}"
            # 默认使用原快捷键（兼容旧配置）
            if key_name == "previous":
                return "\t&U"
            elif key_name == "next":
                return "\t&N"
            elif key_name == "random":
                return "\t&3"
            elif key_name == "jump":
                return "\t&V"
            else:
                return ""

        # 上一个壁纸菜单
        prev_reg_path = r"DesktopBackground\Shell\LastWallpaper"
        if config.get("ctx_last_wallpaper", False):
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, prev_reg_path)
            suffix = get_hotkey_suffix("previous")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"上一个桌面背景{suffix}")
            winreg.CloseKey(key)
            cmd_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, prev_reg_path + r"\command")
            cmd = build_action_command("--previous")
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(cmd_key)
            log("上一个右键菜单安装成功")
        else:
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, prev_reg_path + r"\command")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, prev_reg_path)
                log("上一个右键菜单已关闭")
            except Exception:
                pass

        # 下一个壁纸菜单
        next_reg_path = r"DesktopBackground\Shell\NextWallpaper"
        if config.get("ctx_next_wallpaper", False):
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, next_reg_path)
            suffix = get_hotkey_suffix("next")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"下一个桌面背景{suffix}")
            winreg.CloseKey(key)
            cmd_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, next_reg_path + r"\command")
            cmd = build_action_command("--next")
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(cmd_key)
            log("下一个右键菜单安装成功")
        else:
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, next_reg_path + r"\command")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, next_reg_path)
                log("下一个右键菜单已关闭")
            except Exception:
                pass

        # 随机壁纸菜单
        random_reg_path = r"DesktopBackground\Shell\RandomWallpaper"
        if config.get("ctx_random_wallpaper", False):
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, random_reg_path)
            suffix = get_hotkey_suffix("random")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"随机一个桌面背景{suffix}")
            winreg.CloseKey(key)
            cmd_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, random_reg_path + r"\command")
            cmd = build_action_command("--random")
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(cmd_key)
            log("随机右键菜单安装成功")
        else:
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, random_reg_path + r"\command")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, random_reg_path)
                log("随机右键菜单已关闭")
            except Exception:
                pass

        # 个性化设置菜单（放在最后）
        # 跳转到壁纸菜单（位于随机壁纸之后，个性化设置之前）
        # 先删除旧版本可能存在的路径（兼容性）
        old_jump_path = r"DesktopBackground\Shell\JumpToWallpaper"
        try:
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, old_jump_path + r"\command")
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, old_jump_path)
        except Exception:
            pass
        jump_reg_path = r"DesktopBackground\Shell\ZJumpToWallpaper"
        if config.get("ctx_jump_to_wallpaper", False):
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, jump_reg_path)
            # 获取快捷键后缀
            suffix = get_hotkey_suffix("jump")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"跳转到壁纸{suffix}")
            winreg.CloseKey(key)
            cmd_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, jump_reg_path + r"\command")
            cmd = build_action_command("--jump-to-wallpaper")
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(cmd_key)
            log("跳转到壁纸右键菜单安装成功")
        else:
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, jump_reg_path + r"\command")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, jump_reg_path)
                log("跳转到壁纸右键菜单已关闭")
            except Exception:
                pass

        personalize_reg_path = r"DesktopBackground\Shell\~~PersonalizeBackground"
        try:
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, personalize_reg_path + r"\command")
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, personalize_reg_path)
        except Exception:
            pass

        config["ctx_set_wallpaper"] = False
        file_wallpaper_path = r"SystemFileAssociations\image\shell\ShangBackgroundSetWallpaper"
        try:
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, file_wallpaper_path + r"\command")
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, file_wallpaper_path)
        except Exception:
            pass

        return True

    except Exception as e:
        log("右键注册失败: " + str(e))
        if show_admin_prompt:
            show_message(t("错误"), t("右键菜单注册失败，请以管理员身份运行一次本程序。"))
        return False

