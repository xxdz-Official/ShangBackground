# 喵~ 这里是 上一个桌面背景 的代码 (by 小小电子xxdz)
# 嗷~ 代码由deepseek辅助编写的
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
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
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    Image = None
    ImageTk = None
    ImageDraw = None
# import logging  # 已禁用日志文件写入喵
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
try:
    from smooth_transition import SmoothTransition
except ImportError:
    SmoothTransition = None
import random_copy
from app_config import APP_NAME, FONT_FAMILY, IS_MACOS, IS_WINDOWS, STYLE_MAP, UI_ACCENT, UI_BG, UI_BORDER
from dependency_prompt import prompt_install_dependencies
from platform_support import (
    configure_windows_fit_mode,
    get_app_command,
    get_current_wallpaper_platform,
    get_screen_size,
    set_wallpaper_platform,
)
from ui_support import ask_image_file, ask_video_file, setup_modern_style
from macos_video_wallpaper import start_video_wallpaper, stop_video_wallpaper
from macos_menu_bar import COMMAND_FILE as MACOS_MENU_COMMAND_FILE, start_menu_bar, stop_menu_bar
from wallpaper_sidebar import WallpaperSidebar

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
        ('dwData', ctypes.c_ulong),
        ('cbData', ctypes.c_ulong),
        ('lpData', ctypes.c_void_p)
    ]


def is_frozen():
    return getattr(sys, 'frozen', False)


if is_frozen():
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "shezhi.json")
TRIGGER_FILE_PREV = os.path.join(BASE_DIR, "prev.txt")
TRIGGER_FILE_NEXT = os.path.join(BASE_DIR, "next.txt")
TRIGGER_FILE_RANDOM = os.path.join(BASE_DIR, "random.txt")
style_map = STYLE_MAP


# 日志文件写入已禁用咯
# log_file = os.path.join(BASE_DIR, "#wallpaper_debug.log")
# logging.basicConfig(
#     filename=log_file,
#     level=logging.DEBUG,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )


def log(msg):
    print(msg)
    # logging.info(msg)  # 已禁用日志文件写入


def show_message(title, msg):
    if not IS_WINDOWS:
        try:
            messagebox.showinfo(title, msg)
        except Exception:
            log(f"{title}: {msg}")
        return

    def _show():
        try:
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0)
        except:
            pass

    if threading.current_thread() is threading.main_thread():
        _show()
    else:
        try:
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0)
        except:
            pass


# 全局变量
hwnd = None
WND_CLASS_NAME = "WallpaperControllerClass"
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
video_frame = None
video_entry = None
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

# 版本检查全局变量
remote_version = "1"
remote_release_notes = ""
remote_download_urls = {"123云盘": "", "111网盘": "", "夸克网盘": ""}  # 如果不是夸克找我合作，打死我也不做夸克线路。。。
show_update_flag = False
check_failed = False


def load_config():
    default = {
        "mode": "幻灯片放映",
        "slide_folder": "",
        "slide_seconds": 300,
        "shuffle": False,
        "fit_mode": "填充",
        "single_image": "",
        "video_file": "",
        "video_muted": True,
        "solid_color": "#4facfe",
        "gradient_color2": "#00f2fe",
        "gradient_angle": 60,
        "current_wallpaper": "",
        "history": [],
        "auto_start": False,
        "ctx_last_wallpaper": False,
        "ctx_next_wallpaper": True,
        "ctx_random_wallpaper": False,
        "ctx_personalize": True,  # 默认开启右键个性化
        "ctx_jump_to_wallpaper": True,  # 默认开启“跳转到壁纸”右键菜单
        "ctx_set_wallpaper": False,
        "recent_folders": [],
        "run_in_background": True,  # 默认后台运行
        "tray_icon": True,  # 默认托盘图标
        "tray_click_action": "next",
        "tray_menu_items": ["show", "previous", "next", "random", "about", "jump", "exit"],
        "transition_animation": True,  # 默认开启过渡动画
        "transition_effect": "smooth",  # "frame" 或 "smooth"（默认丝滑转场）
        "ignored_version": "",  # 用户选择忽略的版本号
        "user_id": "",  # 用户唯一标识（10位随机数字）
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            log("配置加载成功")
            # 自动转换旧的托盘菜单格式
            converted = False
            if "tray_menu_items" in data and data["tray_menu_items"]:
                first_item = data["tray_menu_items"][0]
                if isinstance(first_item, dict) and "action" in first_item:
                    # 旧格式：转换为只存储 action 字符串的新格式
                    new_items = [item["action"] for item in data["tray_menu_items"]]
                    data["tray_menu_items"] = new_items
                    converted = True
            # 转换完就赶紧存一下
            if converted:
                try:
                    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    log("已保存转换后的配置文件")
                except Exception as e:
                    log(f"保存转换后的配置失败: {e}")
            return data
        except Exception as e:
            log("加载配置失败: " + str(e))
            return default
    return default


def save_config():
    try:
        if "tray_click_action" not in config:
            config["tray_click_action"] = "next"
        if "tray_menu_items" not in config:
            config["tray_menu_items"] = ["show", "previous", "next", "random", "about", "exit"]
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        log("配置已保存")
    except Exception as e:
        log("保存配置失败: " + str(e))


config = load_config()

# 第一次运行的话，生成一个10位的随机用户ID
import random as _random

if not config.get("user_id"):
    config["user_id"] = ''.join(str(_random.randint(0, 9)) for _ in range(10))
    save_config()


# 上报用户使用情况（另开个线程，能不卡界面）
def report_usage():
    """向远程JSON Bin上报用户使用记录（不阻塞主线程）"""
    import json
    import threading
    from datetime import datetime

    if requests is None:
        log("requests 未安装，跳过使用统计上报")
        return

    def _do_report():
        try:
            user_id = config.get("user_id", "")
            if not user_id:
                return

            bin_id = "我是马赛克，你的新bin_id（从jsonbin复制粘贴过来）"
            master_key = "我是马赛克，你的新master_key（一串长长的字符）"
            url = f"https://api.jsonbin.io/v3/b/{bin_id}"
            headers = {"X-Master-Key": master_key, "Content-Type": "application/json"}

            # 获取当前数据
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                record = data.get("record", {})
            else:
                # 若获取失败，初始化空结构
                record = {}

            today = datetime.now().strftime("%Y-%m-%d")

            # 初始化各字段
            record.setdefault("total_use", 0)  # 唯一用户总数（去重）
            record.setdefault("daily_use", {})  # 每日唯一用户数
            record.setdefault("total_uses", 0)  # 总使用次数（不去重）
            record.setdefault("daily_uses", {})  # 每日使用次数
            record.setdefault("user_id", [])  # 所有唯一用户ID列表
            record.setdefault("user_num", 0)  # 唯一用户数量
            record.setdefault("last_updated", today)

            # 更新唯一用户相关
            if user_id not in record["user_id"]:
                record["user_id"].append(user_id)
                record["user_num"] = len(record["user_id"])
                record["total_use"] = record["user_num"]  # total_use 等于唯一用户总数

                # 每日唯一用户计数
                record["daily_use"][today] = record["daily_use"].get(today, 0) + 1
            else:
                # 已存在的用户，不增加 total_use 和 daily_use（唯一）
                pass

            # 更新总使用次数（不去重，每次启动都加1）
            record["total_uses"] = record.get("total_uses", 0) + 1
            record["daily_uses"][today] = record["daily_uses"].get(today, 0) + 1

            record["last_updated"] = today

            # 写回
            put_resp = requests.put(url, headers=headers, json=record, timeout=10)
            if put_resp.status_code == 200:
                log(f"用户统计上报成功: user_id={user_id}")
            else:
                log(f"用户统计上报失败: HTTP {put_resp.status_code}")
        except Exception as e:
            log(f"用户统计上报异常: {e}")

    # 开个新线程跑
    threading.Thread(target=_do_report, daemon=True).start()


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
    if not path or not os.path.isfile(path):
        return
    hist = config.get("history", [])
    if path in hist:
        hist.remove(path)
    hist.insert(0, path)
    config["history"] = hist[:50]
    config["current_wallpaper"] = path
    save_config()
    log("已记录壁纸: " + os.path.basename(path) + " | 历史总数: " + str(len(hist)))
    if root and canvas:
        root.after(0, lambda: update_preview(path))


def set_wallpaper_direct(path, operation_name="系统", skip_history=False):
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
    except Exception as e:
        log("设置壁纸失败: " + str(e))
        return False


def set_wallpaper(path, operation_name="用户", force=False):
    if not os.path.isfile(path):
        return False
    # 无窗口时也支持过渡动画（使用 threading.Timer 代替 root.after）
    use_transition = (config.get("transition_animation", False) and
                      path.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")))
    if use_transition:
        return safe_switch_with_transition(path, operation_name, force=force)
    else:
        push_wallpaper(path)
        return set_wallpaper_direct(path, operation_name)


def previous_wallpaper():
    log("=" * 50)
    log("触发上一张壁纸")
    hist = config.get("history", [])
    log("当前历史: " + str([os.path.basename(p) for p in hist[:5]]) + ("..." if len(hist) > 5 else ""))
    if len(hist) < 2:
        log("没有上一张壁纸")
        show_message("提示喵", "没有上一张壁纸")
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
        show_message("错误", "历史壁纸文件已丢失")
        log("=" * 50)
        return
    new_hist = [found] + [p for p in hist if p != found]
    config["history"] = new_hist[:50]
    save_config()
    log("回退到: " + os.path.basename(found))
    success = set_wallpaper(found, "右键菜单(上一张)")
    if success and config["mode"] == "幻灯片放映":
        try:
            reset_slide_timer()
        except:
            pass
    log("=" * 50)


def next_wallpaper():
    log("=" * 50)
    log("触发下一张壁纸")
    if config["mode"] != "幻灯片放映":
        log("当前模式不是幻灯片放映，无法使用下一张功能")
        show_message("提示喵", "请在幻灯片放映模式下使用此功能")
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
                show_message("提示喵", "请先设置幻灯片文件夹")
                log("=" * 50)
                return
        else:
            log("幻灯片列表为空，无法切换到下一张")
            show_message("提示喵", "请先设置幻灯片文件夹")
            log("=" * 50)
            return
    next_img = get_next_wallpaper()
    if next_img is None:
        log("无法获取下一张壁纸")
        show_message("提示喵", "无法获取下一张壁纸")
        log("=" * 50)
        return
    log("切换到: " + os.path.basename(next_img))
    success = set_wallpaper(next_img, "右键菜单(下一张)")
    if success:
        try:
            reset_slide_timer()
        except:
            pass
    log("=" * 50)


def random_wallpaper():
    log("=" * 50)
    log("触发随机壁纸")
    if config["mode"] != "幻灯片放映":
        log("当前模式不是幻灯片放映，无法使用随机功能")
        show_message("提示喵", "请在幻灯片放映模式下使用此功能")
        log("=" * 50)
        return
    global slide_images
    folder = config["slide_folder"]
    if not folder or not os.path.isdir(folder):
        log("幻灯片文件夹无效")
        show_message("提示喵", "请先设置幻灯片文件夹")
        log("=" * 50)
        return

    # 获取包含副本的所有图片路径
    all_images = random_copy.get_all_images_with_copies(folder)
    if not all_images:
        log("文件夹中没有图片")
        show_message("提示喵", "文件夹中没有图片")
        log("=" * 50)
        return

    # 刷新 slide_images（用于其他地方，但这里不依赖）
    slide_images = [img for img in all_images if not os.path.basename(img).startswith(random_copy.COPY_PREFIX)]

    current = config.get("current_wallpaper", "")
    available = [img for img in all_images if img != current]
    if not available:
        available = all_images.copy()
    random_img = random.choice(available)
    log("随机切换到: " + os.path.basename(random_img))
    success = set_wallpaper(random_img, "右键菜单(随机)")
    if success:
        try:
            reset_slide_timer()
        except:
            pass
    log("=" * 50)


def set_fit_mode(mode):
    try:
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
        # 如果开启了随机顺序，使用带副本的随机列表
        if config.get("shuffle", False):
            folder = config["slide_folder"]
            if folder and os.path.isdir(folder):
                all_images = random_copy.get_all_images_with_copies(folder)
                if all_images:
                    current = config.get("current_wallpaper", "")
                    available = [img for img in all_images if img != current]
                    if available:
                        next_img = random.choice(available)
                    else:
                        next_img = random.choice(all_images)
                else:
                    next_img = get_next_wallpaper()
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
    global slide_timer, slide_enabled
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
                except:
                    pass
            else:
                try:
                    slide_timer.cancel()
                except:
                    pass
            slide_timer = None
        if root is not None:
            slide_timer = root.after(int(config["slide_seconds"] * 1000), slide_next)
        else:
            slide_timer = threading.Timer(config["slide_seconds"], slide_next)
            slide_timer.daemon = True
            slide_timer.start()


def start_slideshow():
    global slide_images, slide_enabled, slide_timer
    with slide_timer_lock:
        if config["mode"] != "幻灯片放映":
            return False
        folder = config["slide_folder"]
        if not folder or not os.path.isdir(folder):
            return False
        images = [os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))]
        if not images:
            return False
        if config["shuffle"]:
            random.shuffle(images)
        slide_images = images
        log(f"加载 {len(images)} 张图片")
        current = config.get("current_wallpaper", "")
        if current not in images:
            if images:
                set_wallpaper(images[0], "幻灯片启动")
        else:
            set_wallpaper_direct(current, "幻灯片恢复")
        # 安全取消现有定时器
        if slide_timer:
            try:
                # 如果是 root.after 返回的字符串 ID
                if root is not None and isinstance(slide_timer, str):
                    root.after_cancel(slide_timer)
                else:
                    # 如果是 threading.Timer 对象
                    slide_timer.cancel()
            except Exception as e:
                log(f"取消旧定时器失败: {e}")
            slide_timer = None
        slide_enabled = True
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
            except:
                pass
            slide_timer = None
        log("幻灯片已停止")


def restart_slideshow():
    stop_slideshow()
    if config["mode"] == "幻灯片放映" and config["slide_folder"]:
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


# ====================== 断点续传功能 ======================
TRANSITION_LOG_PATH = os.path.join(BASE_DIR, "transition_log.json")


def save_transition_state(state):
    """把过渡动画的状态存到日志文件里吧"""
    try:
        # 确保 GuoduTemp 目录存在（用于存放临时帧）
        temp_dir = os.path.join(BASE_DIR, "GuoduTemp")
        os.makedirs(temp_dir, exist_ok=True)
        # 日志文件直接保存在根目录
        with open(TRANSITION_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        log(f"保存过渡状态: {state}")
    except Exception as e:
        log(f"保存过渡状态失败: {e}")


def load_transition_state():
    """加载未完成的过渡动画状态"""
    try:
        if os.path.exists(TRANSITION_LOG_PATH):
            with open(TRANSITION_LOG_PATH, 'r', encoding='utf-8') as f:
                state = json.load(f)
            # 看看帧文件还在不在
            frame_paths = state.get('frame_paths', [])
            valid_frames = [p for p in frame_paths if os.path.exists(p)]
            if valid_frames:
                state['frame_paths'] = valid_frames
                log(f"加载未完成过渡状态: 剩余 {len(valid_frames)} 帧, 目标: {state.get('final_target', '')}")
                return state
            else:
                # 没有能用的帧了，清掉日志吧
                os.remove(TRANSITION_LOG_PATH)
                return None
    except Exception as e:
        log(f"加载过渡状态失败: {e}")
    return None


def clear_transition_state():
    """清除过渡动画状态"""
    try:
        if os.path.exists(TRANSITION_LOG_PATH):
            os.remove(TRANSITION_LOG_PATH)
            log("已清除过渡状态日志")
    except Exception as e:
        log(f"清除过渡状态失败: {e}")


def resume_interrupted_transition():
    """恢复中断的过渡动画"""
    state = load_transition_state()
    if not state:
        return False

    frame_paths = state.get('frame_paths', [])
    final_target = state.get('final_target', '')
    operation_name = state.get('operation_name', '恢复中断')

    if not frame_paths or not os.path.exists(final_target):
        clear_transition_state()
        return False

    log(f"恢复中断的过渡动画: 剩余 {len(frame_paths)} 帧, 最终目标: {os.path.basename(final_target)}")

    # 直接播放剩下的帧
    def play_remaining():
        idx = 0

        def set_next():
            nonlocal idx
            if idx < len(frame_paths):
                set_wallpaper_direct(frame_paths[idx], f"{operation_name}_恢复帧{idx + 1}")
                idx += 1
                root.after(200, set_next)
            else:
                # 播放完成，设置最终壁纸
                push_wallpaper(final_target)
                set_wallpaper_direct(final_target, operation_name, skip_history=False)
                # 清理临时文件
                temp_dir = os.path.join(BASE_DIR, "GuoduTemp")
                if os.path.exists(temp_dir):
                    for file in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, file)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                        except:
                            pass
                clear_transition_state()
                log("中断的过渡动画已恢复完成")

        set_next()

    if root is not None:
        root.after(0, play_remaining)
    else:
        log("无窗口实例，使用 threading.Timer 恢复过渡动画")
        # 直接启动恢复（play_remaining 内部使用 threading.Timer）
        play_remaining()


# ====================== 壁纸切换时的过渡动画 ======================
transition_in_progress = False
transition_lock = threading.Lock()


def create_transition_frame(arr1, arr2, t):
    """
    使用 numpy 向量化混合两个图像数组
    arr1, arr2: numpy 数组 (height, width, 3) dtype=uint8
    t: 混合系数 (0~1)
    返回 PIL Image
    """
    if not HAS_NUMPY:
        blended = Image.blend(Image.fromarray(arr1), Image.fromarray(arr2), t)
        return blended
    blended = (arr1.astype(np.float32) * (1 - t) + arr2.astype(np.float32) * t).astype(np.uint8)
    return Image.fromarray(blended, 'RGB')


def generate_transition_frames(current_img, target_img, fit_mode, frames=None):
    if frames is None:
        frames = config.get("transition_frames", 12)
    # 无帧数上限限制
    if frames > 200:
        frames = 200  # 最大200帧防止内存过载，但用户可自由设置
    temp_dir = os.path.join(BASE_DIR, "GuoduTemp")
    if os.path.exists(temp_dir):
        for file in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, file)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                log(f"删除临时文件失败: {e}")
    else:
        os.makedirs(temp_dir, exist_ok=True)

    screen_width = get_screen_size(root)[0]
    screen_height = get_screen_size(root)[1]
    target_size = (screen_width, screen_height)

    def pre_resize_to_array(img_path, mode, size):
        img = Image.open(img_path).convert("RGB")
        orig_w, orig_h = img.size
        target_w, target_h = size

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
            result = Image.new("RGB", size, (0, 0, 0))
            x_offset = (target_w - new_w) // 2
            y_offset = (target_h - new_h) // 2
            result.paste(img_resized, (x_offset, y_offset))
        elif mode == "拉伸":
            result = img.resize(size, Image.Resampling.LANCZOS)
        elif mode == "居中":
            result = Image.new("RGB", size, (0, 0, 0))
            x_offset = (target_w - orig_w) // 2
            y_offset = (target_h - orig_h) // 2
            result.paste(img, (x_offset, y_offset))
        elif mode == "平铺":
            result = Image.new("RGB", size)
            for x in range(0, target_w, orig_w):
                for y in range(0, target_h, orig_h):
                    result.paste(img, (x, y))
        else:
            result = img.resize(size, Image.Resampling.LANCZOS)
        return np.array(result) if HAS_NUMPY else result

    if HAS_NUMPY:
        arr1 = pre_resize_to_array(current_img, fit_mode, target_size)
        arr2 = pre_resize_to_array(target_img, fit_mode, target_size)
        frame_paths = []
        for i in range(frames):
            t = i / (frames - 1) if frames > 1 else 1.0
            blended_img = create_transition_frame(arr1, arr2, t)
            frame_path = os.path.join(temp_dir, f"frame_{i:04d}.bmp")
            blended_img.save(frame_path, "BMP")
            frame_paths.append(frame_path)
        return frame_paths
    else:
        frame_paths = []
        for i in range(frames):
            t = i / (frames - 1) if frames > 1 else 1.0
            blended_img = create_transition_frame(current_img, target_img, t, fit_mode)
            frame_path = os.path.join(temp_dir, f"frame_{i:04d}.bmp")
            blended_img.save(frame_path, "BMP")
            frame_paths.append(frame_path)
        return frame_paths


def play_transition_frames(frame_paths, final_target, operation_name, interval_ms=None, timeout_callback=None):
    if interval_ms is None:
        duration = config.get("transition_duration", 1.0)
        frames = config.get("transition_frames", 8)
        interval_ms = int((duration / frames) * 1000) if frames > 0 else 125
    global transition_in_progress
    idx = 0

    # 保存状态以便断点续传
    state = {
        'frame_paths': frame_paths,
        'final_target': final_target,
        'operation_name': operation_name,
        'current_frame': 0
    }
    save_transition_state(state)

    # 标记超时是否已触发
    timeout_triggered = False

    def set_next_frame():
        nonlocal idx, timeout_triggered
        if idx < len(frame_paths) and not timeout_triggered:
            set_wallpaper_direct(frame_paths[idx], f"{operation_name}_过渡帧{idx + 1}", skip_history=True)
            idx += 1
            # 更新当前进度
            state['current_frame'] = idx
            save_transition_state(state)
            if root is not None:
                root.after(interval_ms, set_next_frame)
            else:
                # 无窗口模式：使用 threading.Timer 模拟延迟
                timer = threading.Timer(interval_ms / 1000.0, set_next_frame)
                timer.daemon = True
                timer.start()
        elif not timeout_triggered:
            # 动画正常完成 - 直接设置最终壁纸，不经过过渡帧
            # 注意：最后一帧已经设置过，这里确保最终壁纸被正确设置
            log(f"动画完成，设置最终壁纸: {os.path.basename(final_target)}")

            # 直接设置最终壁纸（不经过过渡动画）
            push_wallpaper(final_target)
            set_wallpaper_direct(final_target, operation_name, skip_history=False)

            # 清理临时文件
            temp_dir = os.path.join(BASE_DIR, "GuoduTemp")
            if os.path.exists(temp_dir):
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        log(f"删除临时文件失败: {e}")

            clear_transition_state()
            with transition_lock:
                transition_in_progress = False

            # 取消超时回调
            if timeout_callback:
                try:
                    timeout_callback.cancel()
                except:
                    pass

    set_next_frame()


def safe_switch_with_transition(target_path, operation_name, force=False):
    global transition_in_progress
    import threading
    # 如果当前不在主线程，则调度到主线程执行
    if threading.current_thread() is not threading.main_thread() and root is not None:
        log(f"后台线程调用切换，已调度到主线程: {operation_name}")
        root.after(0, lambda: safe_switch_with_transition(target_path, operation_name))
        return True  # 表示已调度，实际结果稍后执行

    with transition_lock:
        if transition_in_progress:
            log(f"已有过渡动画进行中，忽略本次切换请求: {operation_name}")
            return False
        transition_in_progress = True

    current = config.get("current_wallpaper", "")
    if not current or not os.path.exists(current):
        push_wallpaper(target_path)
        set_wallpaper_direct(target_path, operation_name)
        with transition_lock:
            transition_in_progress = False
        return True

    if not force and os.path.samefile(current, target_path):
        log(f"目标壁纸与当前相同，跳过切换: {operation_name}")
        with transition_lock:
            transition_in_progress = False
        return True

    fit_mode = config.get("fit_mode", "填充")
    if fit_mode in ["平铺", "居中"]:
        log(f"当前适应模式为 {fit_mode}，不支持过渡动画，直接切换")
        push_wallpaper(target_path)
        set_wallpaper_direct(target_path, operation_name)
        with transition_lock:
            transition_in_progress = False
        return True

    # 新增：丝滑转场效果
    transition_effect = config.get("transition_effect", "smooth")
    if transition_effect == "smooth" and SmoothTransition is None:
        log("缺少 smooth_transition 模块，已降级为直接切换")
        push_wallpaper(target_path)
        set_wallpaper_direct(target_path, operation_name)
        with transition_lock:
            transition_in_progress = False
        return True
    if transition_effect == "smooth":
        log(f"使用丝滑转场: {os.path.basename(current)} -> {os.path.basename(target_path)}")
    else:
        # 如果不是丝滑转场，走帧动画逻辑（略过，保持原有）
        log(f"开始生成过渡帧: {os.path.basename(current)} -> {os.path.basename(target_path)}")
        try:
            frames = generate_transition_frames(current, target_path, fit_mode)
        except Exception as e:
            log(f"生成过渡帧失败: {e}，降级为直接切换")
            push_wallpaper(target_path)
            set_wallpaper_direct(target_path, operation_name)
            with transition_lock:
                transition_in_progress = False
            return False

        log(f"生成 {len(frames)} 帧，开始播放动画")
        total_duration = config.get("transition_duration", 1.0)
        timeout_seconds = min(max(total_duration + 5, 10), 60)

        def reset_transition_timeout():
            global transition_in_progress
            with transition_lock:
                if transition_in_progress:
                    log(f"过渡动画超时（{timeout_seconds}秒），强制重置标志")
                    transition_in_progress = False
                    clear_transition_state()
                    temp_dir = os.path.join(BASE_DIR, "GuoduTemp")
                    if os.path.exists(temp_dir):
                        for file in os.listdir(temp_dir):
                            file_path = os.path.join(temp_dir, file)
                            try:
                                if os.path.isfile(file_path):
                                    os.remove(file_path)
                            except:
                                pass

        if root is not None:
            timeout_obj = root.after(int(timeout_seconds * 1000), reset_transition_timeout)
            root.after(0, lambda: play_transition_frames(frames, target_path, operation_name, None, timeout_obj))
        else:
            log("无窗口实例，使用 threading.Timer 播放动画")
            timeout_timer = threading.Timer(timeout_seconds, reset_transition_timeout)
            timeout_timer.daemon = True
            timeout_timer.start()
            play_transition_frames(frames, target_path, operation_name, None, timeout_timer)
        return True

    # 以下是丝滑转场（smooth）的逻辑
    duration = config.get("transition_duration", 1.0)
    smooth_effect = config.get("smooth_effect", "fade")
    if smooth_effect == "random":
        import random as _random
        smooth_effect = _random.choice(["fade", "slide", "scan"])
        log(f"随机转场效果: 选择了 {smooth_effect}")

    def on_smooth_complete():
        push_wallpaper(target_path)
        set_wallpaper_direct(target_path, operation_name, skip_history=False)
        with transition_lock:
            global transition_in_progress
            transition_in_progress = False
        log("丝滑转场完成")
        # 如果主窗口处于隐藏状态（后台运行），切换后保持隐藏
        if root and config.get("run_in_background", True) and root.state() == 'withdrawn':
            root.withdraw()
        # 手动切换后重置幻灯片定时器，确保自动切换继续
        try:
            reset_slide_timer()
        except Exception as e:
            log(f"重置幻灯片定时器失败: {e}")
        # 手动切换后重置幻灯片定时器，确保自动切换继续
        try:
            reset_slide_timer()
        except:
            pass

    # 获取 master：优先使用全局 root，如果为 None 则创建临时隐藏根窗口
    if root is not None:
        master = root
        log("使用已有主窗口执行丝滑转场")
    else:
        log("无主窗口，创建临时隐藏窗口执行丝滑转场")
        temp_root = tk.Tk()
        temp_root.withdraw()
        master = temp_root
        # 动画完成后销毁临时窗口
        original_complete = on_smooth_complete

        def on_complete_with_cleanup():
            original_complete()
            try:
                temp_root.after(100, temp_root.destroy)
            except:
                pass

        on_smooth_complete = on_complete_with_cleanup

    smoother = SmoothTransition(current, target_path, duration, on_smooth_complete, master=master,
                                fit_mode=fit_mode, effect=smooth_effect,
                                direction=config.get("slide_direction", "right"))
    smoother.start()

    # 如果使用了临时窗口，需要启动其事件循环（阻塞直到窗口销毁）
    if root is None:
        log("启动临时窗口事件循环...")
        temp_root.mainloop()
        log("临时窗口事件循环结束")

    return True


def schedule_apply():
    if config["mode"] == "渐变":
        apply_gradient()
    elif config["mode"] == "纯色":
        apply_solid()
    elif config["mode"] == "视频":
        apply_video_wallpaper()


def apply_video_wallpaper():
    if not IS_MACOS:
        show_message("提示", "视频壁纸当前仅支持 macOS")
        return False
    video_path = config.get("video_file", "")
    if not video_path or not os.path.isfile(video_path):
        show_message("提示", "请先选择视频文件")
        return False
    success, error = start_video_wallpaper(video_path, muted=config.get("video_muted", True))
    if success:
        log("视频壁纸已启动: " + os.path.basename(video_path))
        return True
    show_message("视频壁纸启动失败", error or "请确认已安装 pyobjc-framework-AVFoundation")
    return False


def update_preview(img_path):
    global current_preview_image, overlay_image
    # 取消之前的过渡动画定时器
    if hasattr(update_preview, 'timer') and update_preview.timer:
        try:
            root.after_cancel(update_preview.timer)
        except:
            pass
        update_preview.timer = None
    try:
        if not canvas:
            return
        if not img_path or not os.path.isfile(img_path):
            canvas.delete("all")
            canvas.create_text(190, 120, text="暂无预览", font=(FONT_FAMILY, 12), fill="#666")
            show_overlay()
            update_preview.current_path = None
            update_preview.current_pil = None
            update_preview.current_photo = None
            return

        # 获取配置的适应模式
        fit_mode = config.get("fit_mode", "填充")

        # 加载新图片并按适应模式处理
        new_img_original = Image.open(img_path).convert("RGB")
        new_img, new_photo = resize_image_for_preview(new_img_original, (380, 240), fit_mode)

        # 获取当前显示的图片
        old_path = getattr(update_preview, 'current_path', None)
        old_pil = getattr(update_preview, 'current_pil', None)
        old_photo = getattr(update_preview, 'current_photo', None)

        # 判断是否使用动画：有旧图片、且路径不同
        use_animation = (old_pil is not None and old_photo is not None and
                         old_path is not None and old_path != img_path)

        if not use_animation:
            # 首次加载，直接显示
            canvas.delete("all")
            canvas.create_image(190, 120, image=new_photo)
            canvas.image = new_photo
            show_overlay()

            current_preview_image = new_photo
            update_preview.current_path = img_path
            update_preview.current_pil = new_img
            update_preview.current_photo = new_photo
            log(f"预览已更新(直接): {os.path.basename(img_path)}")
            return

        # 丝滑渐显动画
        log(f"预览动画开始: {os.path.basename(old_path)} -> {os.path.basename(img_path)}")

        frames = 20
        interval = 25
        step = 0

        # 保存动画帧
        if not hasattr(update_preview, 'animation_frames'):
            update_preview.animation_frames = []
        else:
            update_preview.animation_frames.clear()

        # 确保两张图片尺寸一致（都已经按适应模式处理过了）
        old_pil_resized = old_pil
        new_img_resized = new_img

        # 重新生成缩放后的PhotoImage
        old_photo_resized = ImageTk.PhotoImage(old_pil_resized)
        new_photo_resized = new_photo

        # 先显示旧图片
        canvas.delete("all")
        canvas.create_image(190, 120, image=old_photo_resized)
        canvas.image = old_photo_resized
        show_overlay()

        def animate():
            nonlocal step
            if step <= frames:
                t = step / frames
                alpha = t

                try:
                    blended = Image.blend(old_pil_resized, new_img_resized, alpha)
                    blended_photo = ImageTk.PhotoImage(blended)
                    update_preview.animation_frames.append(blended_photo)

                    canvas.delete("all")
                    canvas.create_image(190, 120, image=blended_photo)
                    canvas.image = blended_photo
                    show_overlay()
                except Exception as e:
                    log(f"动画帧混合失败: {e}")
                    # 直接跳到完成
                    step = frames + 1

                step += 1
                if step <= frames:
                    update_preview.timer = root.after(interval, animate)
                else:
                    # 动画完成
                    canvas.delete("all")
                    canvas.create_image(190, 120, image=new_photo_resized)
                    canvas.image = new_photo_resized
                    show_overlay()

                    current_preview_image = new_photo_resized
                    update_preview.current_path = img_path
                    update_preview.current_pil = new_img_resized
                    update_preview.current_photo = new_photo_resized
                    update_preview.animation_frames.clear()
                    update_preview.timer = None
                    log(f"预览动画完成: {os.path.basename(img_path)}")
            else:
                # 兜底
                canvas.delete("all")
                canvas.create_image(190, 120, image=new_photo_resized)
                canvas.image = new_photo_resized
                show_overlay()
                update_preview.current_path = img_path
                update_preview.current_pil = new_img_resized
                update_preview.current_photo = new_photo_resized
                update_preview.timer = None

        # 开始动画
        animate()

    except Exception as e:
        log(f"预览失败: {e}")
        import traceback
        log(traceback.format_exc())
        show_overlay()


def resize_image_for_preview(img, target_size, fit_mode):
    """按适应模式处理预览图片，保持屏幕分辨率比例"""
    target_w, target_h = target_size
    orig_w, orig_h = img.size

    # 获取屏幕分辨率比例
    screen_width = get_screen_size(root)[0]
    screen_height = get_screen_size(root)[1]
    screen_ratio = screen_width / screen_height

    # 计算预览区域应该使用的尺寸（保持屏幕比例）
    # 预览区域最大 380x240，但需要保持屏幕比例
    if screen_ratio > target_w / target_h:
        # 屏幕更宽，以高度为准
        preview_h = target_h
        preview_w = int(preview_h * screen_ratio)
    else:
        # 屏幕更高，以宽度为准
        preview_w = target_w
        preview_h = int(preview_w / screen_ratio)

    # 如果计算出的尺寸超出预览区域，需要缩小
    if preview_w > target_w:
        preview_w = target_w
        preview_h = int(preview_w / screen_ratio)
    if preview_h > target_h:
        preview_h = target_h
        preview_w = int(preview_h * screen_ratio)

    # 创建背景画布（使用 #F9FAFB 颜色）
    result = Image.new("RGB", (target_w, target_h), (249, 250, 251))

    # 先按适应模式处理图片到预览尺寸
    if fit_mode == "填充":
        ratio = max(preview_w / orig_w, preview_h / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - preview_w) // 2
        top = (new_h - preview_h) // 2
        img_fitted = img_resized.crop((left, top, left + preview_w, top + preview_h))
    elif fit_mode == "适应":
        ratio = min(preview_w / orig_w, preview_h / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        img_fitted = Image.new("RGB", (preview_w, preview_h), (0, 0, 0))
        x_offset = (preview_w - new_w) // 2
        y_offset = (preview_h - new_h) // 2
        img_fitted.paste(img_resized, (x_offset, y_offset))
    elif fit_mode == "拉伸":
        img_fitted = img.resize((preview_w, preview_h), Image.Resampling.LANCZOS)
    elif fit_mode == "居中":
        img_fitted = Image.new("RGB", (preview_w, preview_h), (0, 0, 0))
        x_offset = (preview_w - orig_w) // 2
        y_offset = (preview_h - orig_h) // 2
        if x_offset >= 0 and y_offset >= 0:
            img_fitted.paste(img, (x_offset, y_offset))
        else:
            # 图片大于预览区域，需要缩放
            ratio = min(preview_w / orig_w, preview_h / orig_h)
            new_w = int(orig_w * ratio)
            new_h = int(orig_h * ratio)
            img_scaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            x_offset = (preview_w - new_w) // 2
            y_offset = (preview_h - new_h) // 2
            img_fitted.paste(img_scaled, (x_offset, y_offset))
    elif fit_mode == "平铺":
        img_fitted = Image.new("RGB", (preview_w, preview_h))
        for x in range(0, preview_w, orig_w):
            for y in range(0, preview_h, orig_h):
                img_fitted.paste(img, (x, y))
    else:
        img_fitted = img.resize((preview_w, preview_h), Image.Resampling.LANCZOS)

    # 将处理好的图片居中放置在预览区域中
    x_offset = (target_w - preview_w) // 2
    y_offset = (target_h - preview_h) // 2
    result.paste(img_fitted, (x_offset, y_offset))

    photo = ImageTk.PhotoImage(result)
    return result, photo


def show_overlay():
    global overlay_image
    try:
        if not canvas:
            return
        overlay_path = os.path.join(BASE_DIR, "img", "image.png")
        if os.path.exists(overlay_path):
            overlay = Image.open(overlay_path).convert("RGBA")
            overlay = overlay.resize((380, 240), Image.Resampling.LANCZOS)
            overlay_image = ImageTk.PhotoImage(overlay)
            canvas.create_image(190, 120, image=overlay_image)
    except Exception as e:
        log(f"叠加图片加载失败: {e}")


# ====================== 优化的预览渐变函数 ======================
def preview_gradient_optimized():
    color1 = config.get("solid_color", "#2d2d2d")
    color2 = config.get("gradient_color2", "#4a4a4a")
    angle = config.get("gradient_angle", 0)
    try:
        if not canvas:
            return
        width, height = 380, 240
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        rad = math.radians(angle)
        dx = math.cos(rad)
        dy = math.sin(rad)
        center_x = width / 2
        center_y = height / 2
        length = math.sqrt(width ** 2 + height ** 2)
        start_x = center_x - dx * length / 2
        start_y = center_y - dy * length / 2
        end_x = center_x + dx * length / 2
        end_y = center_y + dy * length / 2
        line_dx = end_x - start_x
        line_dy = end_y - start_y
        line_len_sq = line_dx ** 2 + line_dy ** 2
        if HAS_NUMPY:
            x = np.arange(width)
            y = np.arange(height)
            xx, yy = np.meshgrid(x, y)
            px = xx - start_x
            py = yy - start_y
            if line_len_sq == 0:
                t = np.zeros((height, width))
            else:
                t = (px * line_dx + py * line_dy) / line_len_sq
                t = np.clip(t, 0, 1)
            r = (r1 * (1 - t) + r2 * t).astype(np.uint8)
            g = (g1 * (1 - t) + g2 * t).astype(np.uint8)
            b = (b1 * (1 - t) + b2 * t).astype(np.uint8)
            rgb_array = np.stack([r, g, b], axis=2)
            img = Image.fromarray(rgb_array, 'RGB')
        else:
            img = Image.new("RGB", (width, height))
            pixels = img.load()
            for y in range(height):
                for x in range(width):
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
        preview_img = ImageTk.PhotoImage(img)
        canvas.delete("all")
        canvas.create_image(190, 120, image=preview_img)
        canvas.image = preview_img
        show_overlay()
    except Exception as e:
        log(f"预览渐变失败: {e}")


def preview_gradient():
    preview_gradient_optimized()


def preview_solid():
    color = config.get("solid_color", "#2d2d2d")
    try:
        if not canvas:
            return
        img = Image.new("RGB", (380, 240), color)
        preview_img = ImageTk.PhotoImage(img)
        canvas.delete("all")
        canvas.create_image(190, 120, image=preview_img)
        canvas.image = preview_img
        show_overlay()
    except Exception as e:
        log(f"预览纯色失败: {e}")


def monitor_wallpaper_changes():
    global wallpaper_monitor_running
    last_wallpaper = get_current_wallpaper()
    log(f"开始监控壁纸变化，当前壁纸: {last_wallpaper}")
    while wallpaper_monitor_running:
        time.sleep(1)
        try:
            current_wallpaper = get_current_wallpaper()
            if current_wallpaper and current_wallpaper != last_wallpaper:
                log(f"检测到壁纸变化: {os.path.basename(current_wallpaper)}")
                last_wallpaper = current_wallpaper
                config["current_wallpaper"] = current_wallpaper
                push_wallpaper(current_wallpaper)
                if root and canvas:
                    root.after(0, lambda: update_preview(current_wallpaper))
        except Exception as e:
            log(f"监控壁纸变化出错: {e}")


def monitor_wallpaper_changes_on_main_thread():
    global wallpaper_monitor_last
    if not wallpaper_monitor_running:
        return
    try:
        current_wallpaper = get_current_wallpaper()
        if wallpaper_monitor_last is None:
            wallpaper_monitor_last = current_wallpaper
            log(f"开始主线程监控壁纸变化，当前壁纸: {current_wallpaper}")
        elif current_wallpaper and current_wallpaper != wallpaper_monitor_last:
            log(f"检测到壁纸变化: {os.path.basename(current_wallpaper)}")
            wallpaper_monitor_last = current_wallpaper
            config["current_wallpaper"] = current_wallpaper
            push_wallpaper(current_wallpaper)
            if root and canvas:
                update_preview(current_wallpaper)
    except Exception as e:
        log(f"主线程监控壁纸变化出错: {e}")
    if root and wallpaper_monitor_running:
        root.after(1000, monitor_wallpaper_changes_on_main_thread)


def poll_macos_menu_commands():
    if not IS_MACOS:
        return
    try:
        if os.path.exists(MACOS_MENU_COMMAND_FILE):
            with open(MACOS_MENU_COMMAND_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            try:
                os.remove(MACOS_MENU_COMMAND_FILE)
            except Exception:
                pass
            command = data.get("command")
            if command == "show":
                if root:
                    root.deiconify()
                    root.lift()
                    root.focus_force()
            elif command == "previous":
                previous_wallpaper()
            elif command == "next":
                next_wallpaper()
            elif command == "random":
                random_wallpaper()
            elif command == "jump":
                subprocess.Popen([sys.executable, os.path.abspath(__file__), "--jump-to-wallpaper"])
    except Exception as e:
        log(f"处理 macOS 菜单栏命令失败: {e}")
    if root:
        root.after(500, poll_macos_menu_commands)


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int) if IS_WINDOWS else (lambda func: func)


@WNDPROC
def window_proc(hwnd, msg, wparam, lparam):
    if msg == WM_SETTINGCHANGE:
        log("检测到系统设置变化，检查壁纸")
        current = get_current_wallpaper()
        if current and current != config.get("current_wallpaper", ""):
            log(f"系统壁纸已改变: {os.path.basename(current)}")
            push_wallpaper(current)
            if root and canvas:
                root.after(0, lambda: update_preview(current))
        return 0
    elif msg == WM_COPYDATA:
        try:
            cds = ctypes.cast(lparam, ctypes.POINTER(COPYDATASTRUCT)).contents
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
                    if root:
                        root.deiconify()
                        root.lift()
                        root.focus_force()
                    return 1
                elif command.startswith("set_wallpaper|"):
                    target = command.split("|", 1)[1]
                    if os.path.isfile(target):
                        log(f"侧边栏请求切换壁纸: {target}")
                        # 记录到历史记录
                        push_wallpaper(target)
                        # [弃坑说明] 侧边栏切换动画尝试失败，原因：Tkinter多线程冲突 + 窗口层级问题
                        # 侧边栏改用直接切换（无动画），主程序其他功能（右键菜单、幻灯片）动画正常
                        set_wallpaper_direct(target, "侧边栏切换")
                    return 1
                elif command == "create_file":
                    # 调试功能已经撇了
                    return 1
        except Exception as e:
            log(f"消息处理错误: {e}")
        return 0
    return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)


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
            log("注册窗口类失败")
            return None
        hwnd = ctypes.windll.user32.CreateWindowExW(
            0,
            WND_CLASS_NAME,
            "WallpaperController",
            0,
            0, 0, 0, 0,
            0,
            0,
            wc.hInstance,
            0
        )
        if not hwnd:
            log("创建窗口失败")
            return None
        use_message = True
        log(f"消息窗口创建成功, HWND: {hwnd}")
        return hwnd
    except Exception as e:
        log(f"创建消息窗口失败: " + str(e))
        return None


def send_command(command):
    if not IS_WINDOWS:
        return False
    if not hwnd or not use_message:
        return False
    try:
        cmd_bytes = command.encode('utf-8')
        cds = COPYDATASTRUCT()
        cds.dwData = 1
        cds.cbData = len(cmd_bytes) + 1
        cds.lpData = ctypes.cast(cmd_bytes, ctypes.c_void_p)
        result = ctypes.windll.user32.SendMessageW(hwnd, WM_COPYDATA, 0, ctypes.byref(cds))
        return result == 1
    except Exception as e:
        log(f"发送消息失败: " + str(e))
        return False


def register_context():
    if not IS_WINDOWS or winreg is None:
        log("当前平台不支持 Windows 桌面右键菜单注册，已跳过")
        return
    try:
        remote_script = os.path.join(BASE_DIR, "wallpaper_remote.py")
        if not os.path.exists(remote_script):
            remote_script = os.path.abspath(sys.argv[0])
        python_dir = os.path.dirname(sys.executable)
        pythonw_exe = os.path.join(python_dir, "pythonw.exe")
        if not os.path.exists(pythonw_exe):
            pythonw_exe = sys.executable

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
        if config["mode"] == "幻灯片放映" and config.get("ctx_last_wallpaper", False):
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, prev_reg_path)
            suffix = get_hotkey_suffix("previous")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"上一个桌面背景{suffix}")
            winreg.CloseKey(key)
            cmd_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, prev_reg_path + r"\command")
            cmd = f'"{pythonw_exe}" "{remote_script}" --previous'
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(cmd_key)
            log("上一个右键菜单安装成功")
        else:
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, prev_reg_path + r"\command")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, prev_reg_path)
                log("上一个右键菜单已移除")
            except:
                pass

        # 下一个壁纸菜单
        next_reg_path = r"DesktopBackground\Shell\NextWallpaper"
        if config["mode"] == "幻灯片放映" and config.get("ctx_next_wallpaper", True):
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, next_reg_path)
            suffix = get_hotkey_suffix("next")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"下一个桌面背景{suffix}")
            winreg.CloseKey(key)
            cmd_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, next_reg_path + r"\command")
            cmd = f'"{pythonw_exe}" "{remote_script}" --next'
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(cmd_key)
            log("下一个右键菜单安装成功")
        else:
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, next_reg_path + r"\command")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, next_reg_path)
                log("下一个右键菜单已移除")
            except:
                pass

        # 随机壁纸菜单
        random_reg_path = r"DesktopBackground\Shell\RandomWallpaper"
        if config["mode"] == "幻灯片放映" and config.get("ctx_random_wallpaper", False):
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, random_reg_path)
            suffix = get_hotkey_suffix("random")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"随机一个桌面背景{suffix}")
            winreg.CloseKey(key)
            cmd_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, random_reg_path + r"\command")
            cmd = f'"{pythonw_exe}" "{remote_script}" --random'
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(cmd_key)
            log("随机右键菜单安装成功")
        else:
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, random_reg_path + r"\command")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, random_reg_path)
                log("随机右键菜单已移除")
            except:
                pass

        # 个性化设置菜单（放在最后）
        # 跳转到壁纸菜单（位于随机壁纸之后，个性化设置之前）
        # 先删除旧版本可能存在的路径（兼容性）
        old_jump_path = r"DesktopBackground\Shell\JumpToWallpaper"
        try:
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, old_jump_path + r"\command")
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, old_jump_path)
            log("已删除旧的跳转到壁纸菜单")
        except:
            pass
        jump_reg_path = r"DesktopBackground\Shell\ZJumpToWallpaper"
        if config["mode"] == "幻灯片放映" and config.get("ctx_jump_to_wallpaper", False):
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, jump_reg_path)
            # 获取快捷键后缀
            suffix = get_hotkey_suffix("jump")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"跳转到壁纸{suffix}")
            winreg.CloseKey(key)
            cmd_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, jump_reg_path + r"\command")
            # 重要：直接调用 main.py 而不是 wallpaper_remote.py
            main_script = os.path.abspath(sys.argv[0])
            cmd = f'"{pythonw_exe}" "{main_script}" --jump-to-wallpaper'
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(cmd_key)
            log("跳转到壁纸右键菜单安装成功")
        else:
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, jump_reg_path + r"\command")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, jump_reg_path)
                log("跳转到壁纸右键菜单已移除")
            except:
                pass

        personalize_reg_path = r"DesktopBackground\Shell\~~PersonalizeBackground"
        if config.get("ctx_personalize", True):
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, personalize_reg_path)
            # 个性化设置菜单使用快捷键 X（默认）
            suffix = get_hotkey_suffix("show")
            if not suffix:
                suffix = "\t&X"
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"个性化设置{suffix}")
            winreg.CloseKey(key)
            cmd_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, personalize_reg_path + r"\command")
            cmd = f'"{pythonw_exe}" "{remote_script}" --show'
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(cmd_key)
            log("个性化设置右键菜单安装成功")
        else:
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, personalize_reg_path + r"\command")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, personalize_reg_path)
                log("个性化设置右键菜单已移除")
            except:
                pass


    except Exception as e:
        log("右键注册失败: " + str(e))
        show_message("错误", "请以管理员身份运行一次本程序")


def toggle_ctx_prev():
    config["ctx_last_wallpaper"] = ctx_prev_var.get()
    save_config()
    if config["mode"] == "幻灯片放映":
        register_context()
    else:
        try:
            prev_reg_path = r"DesktopBackground\Shell\LastWallpaper"
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, prev_reg_path + r"\command")
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, prev_reg_path)
            log("上一个右键菜单已移除（非幻灯片模式）")
        except:
            pass


def toggle_ctx_next():
    config["ctx_next_wallpaper"] = ctx_next_var.get()
    save_config()
    register_context()


def toggle_ctx_random():
    if ctx_random_var.get():
        if config.get("shuffle", False):
            config["shuffle"] = False
            shuffle_var.set(False)
            if config["mode"] == "幻灯片放映":
                restart_slideshow()
            log("开启随机菜单，自动关闭随机顺序")
    config["ctx_random_wallpaper"] = ctx_random_var.get()
    save_config()
    register_context()


def toggle_ctx_personalize():
    global ctx_personalize_var
    config["ctx_personalize"] = ctx_personalize_var.get()
    save_config()
    register_context()


def toggle_ctx_jump():
    global ctx_jump_var
    config["ctx_jump_to_wallpaper"] = ctx_jump_var.get()
    save_config()
    register_context()


def on_shuffle_changed():
    global prob_btn
    if shuffle_var.get():
        # 开启随机顺序
        if config.get("ctx_random_wallpaper", False):
            config["ctx_random_wallpaper"] = False
            ctx_random_var.set(False)
            register_context()
            log("开启随机顺序，自动关闭随机菜单")
            # 同步托盘菜单（删除随机壁纸）- 延迟调用避免未定义
            try:
                if 'sync_tray_random_with_ctx' in globals():
                    root.after(100, sync_tray_random_with_ctx)
            except:
                pass
        # 启用设置随机概率按钮
        try:
            prob_btn.config(state="normal")
        except:
            pass
        # 恢复随机概率（重新创建副本文件）
        folder = config.get("slide_folder", "")
        log(f"[随机顺序] 开启, 文件夹={folder}")
        if folder and os.path.isdir(folder):
            # 先彻底清理旧副本，避免残留干扰（仅删除物理文件，保留配置）
            random_copy.cleanup_physical_only(folder)
            log("[随机顺序] 已清理旧副本（仅物理文件）")
            # 从 random.json 恢复权重
            random_copy.restore_weights(folder)
            log("[随机顺序] 已调用 restore_weights")
            # 验证副本是否创建成功（仅日志）
            after_files = os.listdir(folder)
            copy_files = [f for f in after_files if f.startswith(random_copy.COPY_PREFIX)]
            log(f"[随机顺序] 恢复后副本文件数: {len(copy_files)}")
        else:
            log("[随机顺序] 文件夹无效, 跳过恢复")
    else:
        # 关闭随机顺序
        # 禁用设置随机概率按钮
        try:
            prob_btn.config(state="disabled")
        except:
            pass
        # 仅删除所有副本文件，保留配置文件中的权重数据
        folder = config.get("slide_folder", "")
        if folder and os.path.isdir(folder):
            random_copy.cleanup_physical_only(folder)
            log("已删除所有随机概率副本文件（配置已保留）")
    config["shuffle"] = shuffle_var.get()
    save_config()
    if config["mode"] == "幻灯片放映":
        restart_slideshow()


# 壁纸预览更新函数
def update_wallpaper_preview():
    """更新壁纸预览区域"""
    global wallpaper_preview_labels, preview_images_frame
    if wallpaper_preview_labels is None:
        wallpaper_preview_labels = []
    for label in wallpaper_preview_labels:
        label.destroy()
    wallpaper_preview_labels.clear()
    folder = config.get("slide_folder", "")
    if not folder or not os.path.isdir(folder):
        tip_label = ttk.Label(preview_images_frame, text="请选择文件夹", foreground="#999")
        tip_label.pack(side="left", padx=5)
        wallpaper_preview_labels.append(tip_label)
        return
    # 过滤掉副本文件（以 COPY_PREFIX 开头的文件）
    images = [f for f in os.listdir(folder)
              if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))
              and not f.startswith(random_copy.COPY_PREFIX)]
    if not images:
        tip_label = ttk.Label(preview_images_frame, text="文件夹中没有图片", foreground="#999")
        tip_label.pack(side="left", padx=5)
        wallpaper_preview_labels.append(tip_label)
        return
    for i, img_file in enumerate(images[:3]):
        img_path = os.path.join(folder, img_file)
        try:
            img = Image.open(img_path)
            img.thumbnail((130, 110), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            frame = tk.Frame(preview_images_frame, relief="flat", borderwidth=0, highlightthickness=0, bg="#ffffff")
            frame.pack(side="left", padx=8, pady=2)
            label = tk.Label(frame, image=photo)
            label.image = photo
            label.pack()
            wallpaper_preview_labels.append(frame)
        except Exception as e:
            log(f"预览图片失败 {img_file}: {e}")
    if len(images) > 3:
        root.after(100, add_mask)


def add_mask():
    if len(wallpaper_preview_labels) >= 3:
        target_frame = wallpaper_preview_labels[2]
        target_label = target_frame.winfo_children()[0]
        if isinstance(target_label, tk.Label) and hasattr(target_label, 'image'):
            try:
                img_path = os.path.join(config.get("slide_folder", ""), os.listdir(config.get("slide_folder", ""))[2])
                original_img = Image.open(img_path).convert("RGBA")
                original_img.thumbnail((130, 110), Image.Resampling.LANCZOS)
                orig_size = original_img.size
                mask_path = os.path.join(BASE_DIR, "img", "zhezhao.png")
                if os.path.exists(mask_path):
                    mask_img = Image.open(mask_path).convert("RGBA")
                    mask_img = mask_img.resize(orig_size, Image.Resampling.LANCZOS)
                    combined = Image.alpha_composite(original_img, mask_img)
                    combined_photo = ImageTk.PhotoImage(combined)
                    target_label.config(image=combined_photo)
                    target_label.image = combined_photo
            except Exception as e:
                log(f"合成遮罩失败: {e}")


# 浏览文件夹函数
def browse_folder():
    d = filedialog.askdirectory()
    if d:
        # 清理旧文件夹的副本
        old_folder = config.get("slide_folder", "")
        if old_folder and os.path.isdir(old_folder) and old_folder != d:
            random_copy.cleanup_folder(old_folder)
        config["slide_folder"] = d
        folder_entry.delete(0, "end")
        folder_entry.insert(0, os.path.basename(d))
        save_config()
        if config["mode"] == "幻灯片放映":
            restart_slideshow()
        update_wallpaper_preview()


def on_mode_changed():
    global single_entry, video_entry
    mode = mode_var.get()
    config["mode"] = mode
    save_config()
    slide_frame.pack_forget()
    single_frame.pack_forget()
    video_frame.pack_forget()
    gradient_frame.pack_forget()
    solid_frame.pack_forget()
    if mode != "视频":
        stop_video_wallpaper()
    if mode == "幻灯片放映":
        slide_frame.pack(fill="both", expand=True)
        chk_next.config(state="normal")
        chk_random.config(state="normal")
        chk_prev.config(state="normal")
        chk_jump.config(state="normal")  # 幻灯片模式下启用跳转到壁纸
        ctx_prev_var.set(config.get("ctx_last_wallpaper", False))
        save_config()
        register_context()
        update_wallpaper_preview()
        if config["slide_folder"]:
            start_slideshow()
        else:
            # 尝试获取当前桌面壁纸的文件夹
            current_wallpaper = get_current_wallpaper()
            if current_wallpaper and os.path.exists(current_wallpaper):
                current_folder = os.path.dirname(current_wallpaper)
                # 检查文件夹中是否有图片
                images_in_folder = [f for f in os.listdir(current_folder)
                                    if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))]
                if images_in_folder:
                    config["slide_folder"] = current_folder
                    save_config()
                    # 更新界面显示（这些变量可能还未定义，用 try-except 保护）
                    try:
                        if folder_combo:
                            update_folder_combo()
                            folder_combo.set(os.path.basename(current_folder))
                    except NameError:
                        pass
                    try:
                        if open_folder_btn:
                            update_open_folder_btn_state()
                    except NameError:
                        pass
                    update_wallpaper_preview()
                    start_slideshow()
                    log(f"自动设置幻灯片文件夹为当前壁纸所在目录: {current_folder}")
                else:
                    show_message("提示喵", "当前壁纸文件夹中没有图片，请手动设置幻灯片文件夹")
            else:
                show_message("提示喵", "请先设置幻灯片文件夹")
    elif mode == "图片":
        single_frame.pack(fill="both", expand=True)
        chk_next.config(state="disabled")
        chk_random.config(state="disabled")
        chk_prev.config(state="disabled")
        chk_jump.config(state="disabled")  # 非幻灯片模式下禁用跳转到壁纸
        config["ctx_last_wallpaper"] = ctx_prev_var.get()
        save_config()
        register_context()
        stop_slideshow()

        # 如果没有设置图片，尝试使用当前壁纸
        if config.get("single_image") and os.path.exists(config["single_image"]):
            set_wallpaper(config["single_image"], "切换图片模式")
            # 确保输入框显示正确的文件名
            single_entry.delete(0, "end")
            single_entry.insert(0, os.path.basename(config["single_image"]))
        else:
            current_wallpaper = get_current_wallpaper()
            if current_wallpaper and os.path.exists(current_wallpaper):
                # 自动使用当前壁纸作为图片模式的图片
                config["single_image"] = current_wallpaper
                save_config()
                # 更新界面显示
                single_entry.delete(0, "end")
                single_entry.insert(0, os.path.basename(current_wallpaper))
                set_wallpaper(current_wallpaper, "切换图片模式")
                log(f"图片模式自动使用当前壁纸: {current_wallpaper}")
            else:
                show_message("提示喵", "请先选择图片文件")
    elif mode == "视频":
        video_frame.pack(fill="both", expand=True)
        chk_next.config(state="disabled")
        chk_random.config(state="disabled")
        chk_prev.config(state="disabled")
        chk_jump.config(state="disabled")
        config["ctx_last_wallpaper"] = ctx_prev_var.get()
        save_config()
        register_context()
        stop_slideshow()
        if config.get("video_file") and os.path.exists(config["video_file"]):
            if video_entry:
                video_entry.delete(0, "end")
                video_entry.insert(0, os.path.basename(config["video_file"]))
            apply_video_wallpaper()
        else:
            show_message("提示喵", "请先选择视频文件")
    elif mode == "纯色":
        solid_frame.pack(fill="both", expand=True)
        chk_next.config(state="disabled")
        chk_random.config(state="disabled")
        chk_prev.config(state="disabled")
        chk_jump.config(state="disabled")  # 非幻灯片模式下禁用跳转到壁纸
        config["ctx_last_wallpaper"] = ctx_prev_var.get()
        save_config()
        register_context()
        stop_slideshow()
        apply_solid()
        preview_solid()
    elif mode == "渐变":
        gradient_frame.pack(fill="both", expand=True)
        chk_next.config(state="disabled")
        chk_random.config(state="disabled")
        chk_prev.config(state="disabled")
        chk_jump.config(state="disabled")  # 非幻灯片模式下禁用跳转到壁纸
        config["ctx_last_wallpaper"] = ctx_prev_var.get()
        save_config()
        register_context()
        stop_slideshow()
        apply_gradient()
        preview_gradient()
    register_context()


def choose_gradient_color1():
    color = colorchooser.askcolor(color=config.get("solid_color", "#2d2d2d"))
    if color:
        config["solid_color"] = color[1]
        if color1_var:
            color1_var.set(color[1])
        if color1_preview:
            color1_preview.config(bg=color[1])
        save_config()
        if config["mode"] == "渐变":
            preview_gradient()
            apply_gradient()
        elif config["mode"] == "纯色":
            preview_solid()
            apply_solid()


def choose_gradient_color2():
    color = colorchooser.askcolor(color=config.get("gradient_color2", "#4a4a4a"))
    if color:
        config["gradient_color2"] = color[1]
        if color2_var:
            color2_var.set(color[1])
        if color2_preview:
            color2_preview.config(bg=color[1])
        save_config()
        if config["mode"] == "渐变":
            preview_gradient()
            apply_gradient()


def on_angle_changed(value):
    config["gradient_angle"] = int(float(value))
    if angle_var:
        angle_var.set(str(config["gradient_angle"]))
    save_config()
    if config["mode"] == "渐变":
        preview_gradient()
        # 拖拽角度条时，临时关闭过渡动画，直接切换
        original_anim = config.get("transition_animation", False)
        config["transition_animation"] = False
        apply_gradient()
        config["transition_animation"] = original_anim


def set_preset_gradient(color1, color2):
    config["solid_color"] = color1
    config["gradient_color2"] = color2
    if color1_var:
        color1_var.set(color1)
    if color2_var:
        color2_var.set(color2)
    if color1_preview:
        color1_preview.config(bg=color1)
    if color2_preview:
        color2_preview.config(bg=color2)
    save_config()
    if config["mode"] == "渐变":
        preview_gradient()
        apply_gradient()


def set_preset_solid(color):
    config["solid_color"] = color
    if solid_color_var:
        solid_color_var.set(color)
    if solid_color_preview:
        solid_color_preview.config(bg=color)
    save_config()
    if config["mode"] == "纯色":
        apply_solid()
        preview_solid()


def dummy_toggle():
    show_message("提示喵", "此功能尚未实现")


# ====================== 全局快捷键功能 ======================
def open_global_hotkey_dialog():
    """打开全局快捷键设置对话框"""
    dialog = GlobalShortcutDialog(root)
    # 对话框内部已经处理保存，不需要额外处理


def open_init_dialog():
    """打开初始化设置对话框"""
    dialog = InitSettingsDialog(root)


def exit_program():
    """彻底退出程序"""
    stop_video_wallpaper()
    # 直接关闭，不显示确认对话框
    if root:
        root.after(0, lambda: root.quit() or root.destroy())
    # 强制退出
    import os as os_module
    os_module._exit(0)


# ====================== 初始化设置对话框 ======================
class InitSettingsDialog:
    """初始化设置对话框 - 现代化UI，类似Edge清除浏览数据"""

    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("初始化设置")
        # 计算窗口居中位置（固定大小640x480，宽度增加140px用于侧边栏）
        x = (self.dialog.winfo_screenwidth() - 640) // 2
        y = (self.dialog.winfo_screenheight() - 480) // 2
        self.dialog.geometry(f"640x480+{x}+{y}")
        # 设置窗口图标
        icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
        if os.path.exists(icon_path):
            try:
                self.dialog.iconbitmap(icon_path)
            except:
                pass
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.configure(bg="#ffffff")

        # 清除选项列表（顺序显示）
        self.clear_options_list = [
            {"key": "slide_folder", "label": "幻灯片文件夹路径", "desc": "清空壁纸相册文件夹设置"},
            {"key": "recent_folders", "label": "最近使用的文件夹", "desc": "清空最近打开的文件夹记录"},
            {"key": "history", "label": "壁纸历史记录", "desc": "清空所有壁纸切换历史"},
            {"key": "current_wallpaper", "label": "当前壁纸记录", "desc": "清空当前壁纸路径记录"},
            {"key": "single_image", "label": "单图片设置", "desc": "清空单图片模式下的图片路径"},
            {"key": "hotkeys", "label": "快捷键设置", "desc": "清空所有自定义快捷键"},
            {"key": "ctx_menu", "label": "右键菜单设置", "desc": "重置右键菜单选项"},
            {"key": "tray_menu", "label": "托盘菜单自定义", "desc": "恢复托盘菜单为默认顺序"},
            {"key": "transition", "label": "过渡动画设置", "desc": "重置过渡动画参数为默认值"},
            {"key": "fit_mode", "label": "适应模式", "desc": "重置壁纸适应模式为「填充」"},
            {"key": "shuffle", "label": "随机概率", "desc": "清除所有的随机概率临时文件"},
            {"key": "registry", "label": "注册表项", "desc": "删除本软件在注册表中的所有右键菜单与启动项"},
            {"key": "startup_vbs", "label": "开机自启动VBS文件", "desc": "删除启动文件夹中的 PowerOn.vbs"}
        ]

        # 存储复选框变量
        self.check_vars = {}

        self.create_widgets()
        self.dialog.wait_window(self.dialog)

    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.dialog, bg="#ffffff")
        main_frame.pack(fill="both", expand=True)

        # 左侧说明区域
        left_frame = tk.Frame(main_frame, bg="#9BFFF2", width=140)
        left_frame.pack(side="left", fill="y")
        left_frame.pack_propagate(False)

        title_label = tk.Label(left_frame, text="初始化设置", font=(FONT_FAMILY, 14, "bold"), bg="#9BFFF2", fg="#2c3e50")
        title_label.pack(pady=(40, 10))

        desc_label = tk.Label(left_frame, text="清除配置数据\n恢复软件初始状态", font=(FONT_FAMILY, 9), bg="#9BFFF2",
                              fg="#7f8c8d", justify="center")
        desc_label.pack(pady=(10, 0))

        # 右侧内容区域
        right_frame = tk.Frame(main_frame, bg="#ffffff")
        right_frame.pack(side="left", fill="both", expand=True, padx=25, pady=20)

        # 标题
        title_label = tk.Label(right_frame, text="清除数据", font=("Segoe UI", 16, "bold"),
                               bg="#ffffff", fg="#2c3e50")
        title_label.pack(anchor="w", pady=(0, 5))

        desc_label = tk.Label(right_frame, text="选择要清除的数据类型", font=("Segoe UI", 9),
                              bg="#ffffff", fg="#7f8c8d")
        desc_label.pack(anchor="w", pady=(0, 15))

        # 选项列表框架
        list_frame = tk.Frame(right_frame, bg="#ffffff", relief="flat", bd=1, highlightthickness=1,
                              highlightbackground="#e0e0e0")
        list_frame.pack(fill="both", expand=True, pady=(0, 15))

        # Canvas 和 Scrollbar 实现滚动
        canvas = tk.Canvas(list_frame, bg="#ffffff", highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#ffffff")

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # 创建窗口并存储ID，稍后设置宽度
        canvas_window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 当 canvas 大小变化时调整内部框架宽度
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window_id, width=event.width)

        canvas.bind("<Configure>", on_canvas_configure)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 鼠标滚轮支持 - 平滑滚动（模拟原生手感）
        def on_mousewheel(event):
            # 获取内容总高度和可见高度
            total_height = scrollable_frame.winfo_reqheight()
            visible_height = canvas.winfo_height()
            if total_height <= visible_height:
                return  # 无需滚动

            # 计算滚动比例：每次滚动 step 像素对应的比例
            step = 30  # 像素步长，数值越小越平滑
            delta_ratio = step / total_height

            # 获取当前滚动位置 (0~1)
            current = canvas.yview()[0]
            # 根据滚轮方向调整 (event.delta 为正表示向上滚动)
            new_pos = current - (event.delta / 120) * delta_ratio
            new_pos = max(0.0, min(1.0, new_pos))
            canvas.yview_moveto(new_pos)

        # 绑定滚轮事件（不需要 focus_set，避免抢焦点）
        canvas.bind("<MouseWheel>", on_mousewheel)
        scrollable_frame.bind("<MouseWheel>", on_mousewheel)

        # 全选复选框（使用 ttk 风格）
        self.select_all_var = tk.BooleanVar(value=True)
        select_all_frame = tk.Frame(scrollable_frame, bg="#ffffff")
        select_all_frame.pack(fill="x", padx=15, pady=(10, 8))

        self.select_all_cb = ttk.Checkbutton(select_all_frame, text="全选", variable=self.select_all_var,
                                             command=self.toggle_select_all)
        self.select_all_cb.pack(side="left")

        # 分隔线
        sep_line = tk.Frame(scrollable_frame, bg="#e8e8e8", height=1)
        sep_line.pack(fill="x", padx=15, pady=5)

        # 创建选项列表
        for option in self.clear_options_list:
            key = option["key"]
            # 选项容器
            item_frame = tk.Frame(scrollable_frame, bg="#ffffff")
            item_frame.pack(fill="x", padx=15, pady=8)

            # 复选框
            var = tk.BooleanVar(value=True)
            self.check_vars[key] = var

            cb = ttk.Checkbutton(item_frame, text=option["label"], variable=var)
            cb.pack(side="left")

            # 描述文字
            desc = tk.Label(item_frame, text=option["desc"], font=("Segoe UI", 8),
                            bg="#ffffff", fg="#888888")
            desc.pack(side="left", padx=(12, 0))

        # 按钮区域
        btn_frame = tk.Frame(right_frame, bg="#ffffff")
        btn_frame.pack(fill="x", pady=(10, 0))

        def on_clear():
            self.clear_selected_data()

        def on_cancel():
            self.dialog.destroy()

        ttk.Button(btn_frame, text="清除", command=on_clear, width=12).pack(side="right", padx=(5, 0))
        ttk.Button(btn_frame, text="取消", command=on_cancel, width=12).pack(side="right")

    def toggle_select_all(self):
        """全选/取消全选"""
        is_selected = self.select_all_var.get()
        for key, var in self.check_vars.items():
            var.set(is_selected)

    def clear_selected_data(self):
        """清除选中的数据"""
        cleared_items = []

        # 获取要清除的项目
        to_clear = [key for key, var in self.check_vars.items() if var.get()]
        # 如果所有选项都被选中，视为"清除全部"
        all_keys = [opt["key"] for opt in self.clear_options_list]
        if set(to_clear) == set(all_keys):
            # 清除全部：删除整个配置文件，让软件回到初始状态
            try:
                # 删除配置文件
                if os.path.exists(CONFIG_PATH):
                    os.remove(CONFIG_PATH)
                # 删除过渡动画临时文件夹
                temp_dir = os.path.join(BASE_DIR, "GuoduTemp")
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                # 删除过渡日志
                if os.path.exists(TRANSITION_LOG_PATH):
                    os.remove(TRANSITION_LOG_PATH)
                # 删除 diy 目录（包含渐变壁纸、纯色壁纸、临时幻灯片等）
                diy_dir = os.path.join(BASE_DIR, "diy")
                if os.path.exists(diy_dir):
                    shutil.rmtree(diy_dir, ignore_errors=True)
                # 清理所有幻灯片文件夹中的随机副本文件（xxdz_random_copy）
                # 获取所有可能存在的幻灯片文件夹：当前 slide_folder 和 recent_folders
                folders_to_clean = set()
                current_folder = config.get("slide_folder", "")
                if current_folder and os.path.isdir(current_folder):
                    folders_to_clean.add(current_folder)
                recent_folders = config.get("recent_folders", [])
                for folder in recent_folders:
                    if folder and os.path.isdir(folder):
                        folders_to_clean.add(folder)
                for folder in folders_to_clean:
                    try:
                        random_copy.cleanup_folder(folder)  # 删除所有副本文件并清空配置
                    except Exception as e:
                        log(f"清理副本文件失败 {folder}: {e}")
                # 清理注册表
                reg_paths = [
                    r"DesktopBackground\Shell\LastWallpaper",
                    r"DesktopBackground\Shell\NextWallpaper",
                    r"DesktopBackground\Shell\RandomWallpaper",
                    r"DesktopBackground\Shell\ZJumpToWallpaper",
                    r"DesktopBackground\Shell\~~PersonalizeBackground"
                ]
                for reg_path in reg_paths:
                    try:
                        cmd_path = reg_path + r"\command"
                        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, cmd_path)
                        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg_path)
                    except:
                        pass

                # 退出程序：直接强制退出，避免后台线程导致进程残留
                stop_video_wallpaper()
                self.dialog.destroy()
                import os as os_module
                os_module._exit(0)
            except Exception as e:
                log(f"清除全部失败: {e}")
                messagebox.showerror("错误", f"清除失败: {e}", parent=self.dialog)
                return
        if not to_clear:
            messagebox.showinfo("提示喵", "请至少选择一项要清除的数据", parent=self.dialog)
            return

        # 执行清除
        for key in to_clear:
            if key == "slide_folder":
                config["slide_folder"] = ""
                cleared_items.append("幻灯片文件夹路径")
            elif key == "recent_folders":
                config["recent_folders"] = []
                cleared_items.append("最近使用的文件夹")
            elif key == "history":
                config["history"] = []
                cleared_items.append("壁纸历史记录")
            elif key == "current_wallpaper":
                config["current_wallpaper"] = ""
                cleared_items.append("当前壁纸记录")
            elif key == "single_image":
                config["single_image"] = ""
                cleared_items.append("单图片设置")
            elif key == "hotkeys":
                for hotkey_key in ["hotkey_previous", "hotkey_next", "hotkey_random", "hotkey_show", "hotkey_jump"]:
                    if hotkey_key in config:
                        del config[hotkey_key]
                cleared_items.append("快捷键设置")
            elif key == "ctx_menu":
                config["ctx_last_wallpaper"] = False
                config["ctx_next_wallpaper"] = True
                config["ctx_random_wallpaper"] = False
                config["ctx_personalize"] = True  # 默认开启个性化设置
                cleared_items.append("右键菜单设置")
            elif key == "tray_menu":
                config["tray_menu_items"] = ["show", "previous", "next", "random", "about", "exit"]
                config["tray_click_action"] = "next"
                config["tray_icon"] = True  # 确保托盘图标默认开启
                cleared_items.append("托盘菜单自定义")
            elif key == "transition":
                config["transition_animation"] = True  # 默认开启过渡动画
                config["transition_effect"] = "smooth"
                if "transition_frames" in config:
                    del config["transition_frames"]
                if "transition_duration" in config:
                    del config["transition_duration"]
                cleared_items.append("过渡动画设置")
            elif key == "fit_mode":
                config["fit_mode"] = "填充"
                if fit_var:
                    fit_var.set("填充")
                cleared_items.append("适应模式")
            elif key == "shuffle":
                config["shuffle"] = False
                if shuffle_var:
                    shuffle_var.set(False)
                cleared_items.append("随机顺序")
            elif key == "registry":
                # 清理注册表项
                cleared_reg_items = []
                reg_paths = [
                    r"DesktopBackground\Shell\LastWallpaper",
                    r"DesktopBackground\Shell\NextWallpaper",
                    r"DesktopBackground\Shell\RandomWallpaper",
                    r"DesktopBackground\Shell\ZJumpToWallpaper",
                    r"DesktopBackground\Shell\~~PersonalizeBackground"
                ]
                for reg_path in reg_paths:
                    try:
                        cmd_path = reg_path + r"\command"
                        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, cmd_path)
                        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg_path)
                        cleared_reg_items.append(reg_path)
                    except WindowsError:
                        pass
                    except Exception as e:
                        log(f"清理注册表失败 {reg_path}: {e}")
                # 清理开机自启动注册表项
                try:
                    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE)
                    winreg.DeleteValue(key, "xxdz_WallpaperController")
                    winreg.CloseKey(key)
                    cleared_reg_items.append("开机自启动项")
                    log("已清理开机自启动注册表项")
                except FileNotFoundError:
                    pass
                except Exception as e:
                    log(f"清理开机自启动注册表项失败: {e}")
                if cleared_reg_items:
                    cleared_items.append(f"注册表项 ({len(cleared_reg_items)} 个)")
                else:
                    cleared_items.append("注册表项 (无残留)")
            elif key == "startup_vbs":
                # 清理启动文件夹中的 PowerOn.vbs
                try:
                    import ctypes.wintypes
                    CSIDL_STARTUP = 7
                    buf = ctypes.create_unicode_buffer(260)
                    ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_STARTUP, None, 0, buf)
                    startup_folder = buf.value
                    vbs_path = os.path.join(startup_folder, "PowerOn.vbs")
                    if os.path.exists(vbs_path):
                        os.remove(vbs_path)
                        cleared_items.append("开机自启动VBS文件 (已删除)")
                        log(f"已删除启动文件夹中的 VBS: {vbs_path}")
                    else:
                        cleared_items.append("开机自启动VBS文件 (不存在)")
                except Exception as e:
                    log(f"清理开机自启动VBS失败: {e}")
                    cleared_items.append("开机自启动VBS文件 (清理失败)")

        # 保存配置
        save_config()

        # 刷新托盘图标（如果清除了托盘菜单）
        if "tray_menu" in to_clear and config.get("tray_icon", False):
            try:
                destroy_tray_icon()
                root.after(500, create_tray_icon)
            except:
                pass

        # 更新界面控件状态
        if shuffle_var:
            shuffle_var.set(config.get("shuffle", False))
        if fit_var:
            fit_var.set(config.get("fit_mode", "填充"))

        # 刷新预览
        current = get_current_wallpaper()
        if current and os.path.exists(current):
            update_preview(current)

        # 如果幻灯片文件夹被清空，停止幻灯片并刷新预览区
        if "slide_folder" in to_clear:
            stop_slideshow()
            try:
                update_folder_combo()
                folder_combo.set("")
            except:
                pass
            update_wallpaper_preview()

        # 显示结果
        result_msg = f"已清除以下 {len(cleared_items)} 项数据：\n\n" + "\n".join(cleared_items)
        messagebox.showinfo("清除完成", result_msg, parent=self.dialog)

        # 重新注册右键菜单（如果清除了右键菜单设置）
        if "ctx_menu" in to_clear:
            register_context()

        # 重新注册全局快捷键（如果清除了快捷键）
        if "hotkeys" in to_clear:
            register_global_hotkeys()

        self.dialog.destroy()


class GlobalShortcutDialog:
    """全局快捷键设置对话框 - Windows原生控件"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("设置快捷键")
        # 计算窗口居中位置（固定大小760x400，宽度增加140px用于侧边栏）
        x = (self.dialog.winfo_screenwidth() - 760) // 2
        y = (self.dialog.winfo_screenheight() - 400) // 2
        self.dialog.geometry(f"760x400+{x}+{y}")
        # 设置窗口图标
        icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
        if os.path.exists(icon_path):
            try:
                self.dialog.iconbitmap(icon_path)
            except:
                pass
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 快捷键配置映射（功能ID -> 显示名）
        self.hotkey_items = {
            "previous": {"name": "上一张壁纸", "current": config.get("hotkey_previous", "")},
            "next": {"name": "下一张壁纸", "current": config.get("hotkey_next", "")},
            "random": {"name": "随机壁纸", "current": config.get("hotkey_random", "")},
            "show": {"name": "打开设置主界面", "current": config.get("hotkey_show", "")},
            "jump": {"name": "跳转到壁纸", "current": config.get("hotkey_jump", "")}
        }

        # 当前选中的功能ID
        self.selected_key = "next"

        # 当前记录的按键
        self.recorded_keys = ""
        # 记录当前按下的修饰键
        self.modifiers = set()

        # 创建界面
        self.create_widgets()

        # 加载当前选中项的快捷键
        self.load_current_hotkey()

        # 等待关闭
        self.dialog.wait_window(self.dialog)

    def create_widgets(self):
        # 主框架（使用Frame以支持侧边栏）
        main_frame = tk.Frame(self.dialog, bg="#ffffff")
        main_frame.pack(fill="both", expand=True)

        # 左侧说明区域
        left_frame = tk.Frame(main_frame, bg="#9BFFF2", width=140)
        left_frame.pack(side="left", fill="y")
        left_frame.pack_propagate(False)

        title_label = tk.Label(left_frame, text="全局快捷键", font=(FONT_FAMILY, 14, "bold"), bg="#9BFFF2", fg="#2c3e50")
        title_label.pack(pady=(40, 10))

        desc_label = tk.Label(left_frame, text="设置全局快捷键\n快速切换壁纸", font=(FONT_FAMILY, 9), bg="#9BFFF2",
                              fg="#7f8c8d", justify="center")
        desc_label.pack(pady=(10, 0))

        # 右侧内容区域
        right_main = tk.Frame(main_frame, bg="#ffffff")
        right_main.pack(side="left", fill="both", expand=True)

        # 主框架（带内边距）
        content_frame = ttk.Frame(right_main)
        content_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # 顶部说明区域
        top_frame = ttk.Frame(content_frame)
        top_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(top_frame, text="全局快捷键设置", font=("Segoe UI", 14, "bold")).pack(anchor="w")

        # 内容区域（左右分割）
        inner_content = ttk.Frame(content_frame)
        inner_content.pack(fill="both", expand=True)

        # 左侧：功能列表
        left_list_frame = ttk.LabelFrame(inner_content, text="功能列表", padding=5)
        left_list_frame.pack(side="left", fill="y", padx=(0, 15))

        self.listbox = tk.Listbox(left_list_frame, height=6, width=18, font=(FONT_FAMILY, 10), relief="sunken", bd=1)
        self.listbox.pack(fill="both", expand=True)
        for key, info in self.hotkey_items.items():
            self.listbox.insert(tk.END, info["name"])
        self.listbox.selection_set(1)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        # 右侧：设置区域
        right_frame = ttk.Frame(inner_content)
        right_frame.pack(side="left", fill="both", expand=True)

        # 当前功能标签
        self.current_func_label = ttk.Label(right_frame, text="当前功能：下一张壁纸", font=(FONT_FAMILY, 10, "bold"))
        self.current_func_label.pack(anchor="w", pady=(0, 15))

        # 当前快捷键
        current_frame = ttk.Frame(right_frame)
        current_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(current_frame, text="当前快捷键：", width=10).pack(side="left")
        self.hotkey_display = ttk.Entry(current_frame, state="readonly", width=25)
        self.hotkey_display.pack(side="left", padx=5)

        # 新快捷键设置
        new_frame = ttk.Frame(right_frame)
        new_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(new_frame, text="新快捷键：", width=10).pack(side="left")
        self.new_key_display = ttk.Entry(new_frame, state="readonly", width=25)
        self.new_key_display.pack(side="left", padx=5)
        record_btn = ttk.Button(new_frame, text="录制", command=self.start_recording, width=8)
        record_btn.pack(side="left", padx=5)

        # 清除按钮
        clear_btn = ttk.Button(right_frame, text="清除当前快捷键", command=self.clear_current_hotkey)
        clear_btn.pack(anchor="w", pady=(10, 0))

        # 底部按钮区域
        btn_frame = ttk.Frame(content_frame)
        btn_frame.pack(fill="x", pady=(15, 0))

        # 保存按钮（右侧）
        save_btn = ttk.Button(btn_frame, text="保存", command=self._apply_and_save_close, width=10)
        save_btn.pack(side="right", padx=(0, 0))

        # 取消按钮（保存按钮左侧）
        cancel_btn = ttk.Button(btn_frame, text="取消", command=self.dialog.destroy, width=10)
        cancel_btn.pack(side="right", padx=(5, 0))

    def on_select(self, event):
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        keys = list(self.hotkey_items.keys())
        self.selected_key = keys[idx]
        self.load_current_hotkey()
        self.current_func_label.config(text=f"当前功能：{self.hotkey_items[self.selected_key]['name']}")

    def load_current_hotkey(self):
        current = self.hotkey_items[self.selected_key]["current"]
        # 如果没有设置，则显示默认快捷键
        if not current:
            default_map = {
                "previous": "U",
                "next": "N",
                "random": "3",
                "show": "X",
                "jump": "V"
            }
            default = default_map.get(self.selected_key, "")
            display_text = default if default else "未设置"
        else:
            display_text = current
        self.hotkey_display.config(state="normal")
        self.hotkey_display.delete(0, tk.END)
        self.hotkey_display.insert(0, display_text)
        self.hotkey_display.config(state="readonly")
        self.new_key_display.config(state="normal")
        self.new_key_display.delete(0, tk.END)
        self.new_key_display.config(state="readonly")
        self.recorded_keys = ""

    def start_recording(self):
        self.modifiers.clear()
        self.recorded_keys = ""

        record_win = tk.Toplevel(self.dialog)
        record_win.title("记录按键")
        record_win.geometry("300x150")
        icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
        if os.path.exists(icon_path):
            try:
                record_win.iconbitmap(icon_path)
            except:
                pass
        record_win.transient(self.dialog)
        record_win.grab_set()

        ttk.Label(record_win, text="请按下快捷键组合...\n(按ESC取消)", font=(FONT_FAMILY, 11)).pack(expand=True, pady=20)

        def on_key_press(event):
            if event.keysym == "Escape":
                record_win.destroy()
                return

            # 修饰键
            if event.keysym in ('Control_L', 'Control_R'):
                self.modifiers.add("ctrl")
                return
            elif event.keysym in ('Alt_L', 'Alt_R'):
                self.modifiers.add("alt")
                return
            elif event.keysym in ('Shift_L', 'Shift_R'):
                self.modifiers.add("shift")
                return
            elif event.keysym in ('Super_L', 'Super_R', 'Win_L', 'Win_R'):
                self.modifiers.add("win")
                return

            key = event.keysym.lower()
            special = {
                "space": "space", "return": "enter", "backspace": "backspace",
                "tab": "tab", "escape": "escape", "delete": "delete",
                "home": "home", "end": "end", "prior": "pageup", "next": "pagedown",
                "left": "left", "right": "right", "up": "up", "down": "down",
                "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
                "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
                "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12"
            }
            if key in special:
                key = special[key]

            modifiers = sorted(self.modifiers)
            if modifiers:
                combo = '+'.join(modifiers + [key])
            else:
                combo = key

            self.recorded_keys = combo
            # 【修复】更新内存中的当前快捷键
            self.hotkey_items[self.selected_key]["current"] = combo
            # 刷新显示
            self.load_current_hotkey()
            # 添加调试日志
            log(f"[快捷键录制] 功能 {self.selected_key} 录制到: {combo}")

            self.new_key_display.config(state="normal")
            self.new_key_display.delete(0, tk.END)
            self.new_key_display.insert(0, combo)
            self.new_key_display.config(state="readonly")
            record_win.destroy()

        def on_key_release(event):
            if event.keysym in ('Control_L', 'Control_R'):
                self.modifiers.discard("ctrl")
            elif event.keysym in ('Alt_L', 'Alt_R'):
                self.modifiers.discard("alt")
            elif event.keysym in ('Shift_L', 'Shift_R'):
                self.modifiers.discard("shift")
            elif event.keysym in ('Super_L', 'Super_R', 'Win_L', 'Win_R'):
                self.modifiers.discard("win")

        record_win.bind('<KeyPress>', on_key_press)
        record_win.bind('<KeyRelease>', on_key_release)
        record_win.focus_set()
        record_win.protocol("WM_DELETE_WINDOW", record_win.destroy)

    def clear_current_hotkey(self):
        """清除当前功能的快捷键"""
        self.hotkey_items[self.selected_key]["current"] = ""
        self.load_current_hotkey()
        log(f"[快捷键清除] 功能 {self.selected_key} 已清除")

    def _apply_and_save_close(self):
        """保存所有配置并关闭窗口"""
        log("[快捷键保存] 开始保存快捷键配置")
        for key, info in self.hotkey_items.items():
            new_val = info["current"]
            config[f"hotkey_{key}"] = new_val
            log(f"[快捷键保存] {key} -> '{new_val}'")
        save_config()
        log("[快捷键保存] 配置已写入文件")
        register_context()
        register_global_hotkeys()
        log("[快捷键保存] 已重新注册全局快捷键")

        # 刷新托盘图标快捷键显示（安全处理，避免未定义错误）
        if config.get("tray_icon", False):
            # 由于无法直接刷新托盘图标，提示用户重启程序
            messagebox.showinfo("提示喵", "快捷键设置已经保存啦\n为了使菜单的快捷键生效，建议重启本软件")
        self.dialog.destroy()


# ====================== 过渡动画设置对话框 ======================
class TransitionSettingsDialog:
    """过渡动画设置对话框 - 现代化UI，按钮固定在底部"""

    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("过渡动画设置")
        # 计算窗口居中位置（固定大小500x380）
        x = (self.dialog.winfo_screenwidth() - 500) // 2
        y = (self.dialog.winfo_screenheight() - 380) // 2
        self.dialog.geometry(f"500x380+{x}+{y}")
        # 设置窗口图标
        icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
        if os.path.exists(icon_path):
            try:
                self.dialog.iconbitmap(icon_path)
            except:
                pass
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.configure(bg="#ffffff")

        # 从配置加载当前设置
        self.transition_frames = config.get("transition_frames", 12)
        self.transition_duration = config.get("transition_duration", 1.0)
        self.transition_effect = config.get("transition_effect", "smooth")
        self.smooth_effect = config.get("smooth_effect", "fade")  # 新增：丝滑转场子效果
        self.slide_direction = config.get("slide_direction", "right")  # 新增：放映机/滑入方向

        self.create_widgets()

        self.dialog.wait_window(self.dialog)

    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.dialog, bg="#ffffff")
        main_frame.pack(fill="both", expand=True)

        # 左侧说明区域
        left_frame = tk.Frame(main_frame, bg="#9BFFF2", width=140)
        left_frame.pack(side="left", fill="y")
        left_frame.pack_propagate(False)

        title_label = tk.Label(left_frame, text="过渡动画", font=(FONT_FAMILY, 14, "bold"), bg="#9BFFF2", fg="#2c3e50")
        title_label.pack(pady=(40, 10))

        desc_label = tk.Label(left_frame,
                              text="设置壁纸切换时的\n动画效果不过无法调用原生\n壁纸切换动画\n所以此动画为自制甚至可以\n达到原生比支持的动画效果\n？！",
                              font=(FONT_FAMILY, 8), bg="#9BFFF2",
                              fg="#7f8c8d", justify="center")
        desc_label.pack(pady=(10, 0))

        # 右侧设置区域
        right_frame = tk.Frame(main_frame, bg="#ffffff")
        right_frame.pack(side="left", fill="both", expand=True, padx=25, pady=25)

        # 效果选择
        effect_row = tk.Frame(right_frame, bg="#ffffff")
        effect_row.pack(fill="x", pady=(0, 20))

        tk.Label(effect_row, text="转场原理", font=(FONT_FAMILY, 10), fg="#34495e", bg="#ffffff", width=8,
                 anchor="w").pack(side="left")

        effect_display_map = {"frame": "帧动画", "smooth": "丝滑转场"}
        effect_reverse_map = {"帧动画": "frame", "丝滑转场": "smooth"}

        current_display = effect_display_map.get(self.transition_effect, "丝滑转场")
        self.effect_display_var = tk.StringVar(value=current_display)
        effect_combo = ttk.Combobox(effect_row, textvariable=self.effect_display_var,
                                    values=["帧动画", "丝滑转场"],
                                    state="readonly", width=12)
        effect_combo.pack(side="left", padx=5)
        effect_combo.bind("<<ComboboxSelected>>", self.on_effect_changed)

        # 新增：丝滑转场子效果选择（仅在丝滑转场时显示）
        self.smooth_effect_row = tk.Frame(right_frame, bg="#ffffff")
        tk.Label(self.smooth_effect_row, text="转场效果", font=(FONT_FAMILY, 10), fg="#34495e", bg="#ffffff", width=8,
                 anchor="w").pack(side="left")
        self.smooth_effect_var = tk.StringVar(value=self.smooth_effect)
        smooth_effect_map = {"fade": "渐显混合", "slide": "放映机", "scan": "滑入", "random": "随机转场"}
        reverse_map = {"渐显混合": "fade", "放映机": "slide", "滑入": "scan", "随机转场": "random"}
        current_display = smooth_effect_map.get(self.smooth_effect, "渐显混合")
        self.smooth_effect_display_var = tk.StringVar(value=current_display)
        self.smooth_effect_combo = ttk.Combobox(self.smooth_effect_row, textvariable=self.smooth_effect_display_var,
                                                values=["渐显混合", "放映机", "滑入", "随机转场"],
                                                state="readonly", width=12)
        self.smooth_effect_combo.pack(side="left", padx=5)
        self.smooth_effect_combo.bind("<<ComboboxSelected>>", lambda e: self._update_direction_visibility())

        # 新增：动画方向选择（仅在放映机且丝滑转场时显示）
        self.slide_direction_row = tk.Frame(right_frame, bg="#ffffff")
        tk.Label(self.slide_direction_row, text="动画方向", font=(FONT_FAMILY, 10), fg="#34495e", bg="#ffffff", width=8,
                 anchor="w").pack(side="left")
        direction_map = {"left": "← 向左", "right": "向右 →", "up": "↑ 向上", "down": "向下 ↓"}
        self.slide_direction_var = tk.StringVar(value=direction_map.get(self.slide_direction, "向右 →"))
        self.slide_direction_combo = ttk.Combobox(self.slide_direction_row, textvariable=self.slide_direction_var,
                                                  values=["← 向左", "向右 →", "↑ 向上", "向下 ↓", "随机方向 [?]"],
                                                  state="readonly", width=12)
        self.slide_direction_combo.pack(side="left", padx=5)

        # 初始根据当前效果显示/隐藏
        self.update_smooth_effect_visibility()

        # 持续时间
        duration_row = tk.Frame(right_frame, bg="#ffffff")
        duration_row.pack(fill="x", pady=(0, 20))

        tk.Label(duration_row, text="持续时间", font=(FONT_FAMILY, 10), fg="#34495e", bg="#ffffff", width=8,
                 anchor="w").pack(side="left")

        self.duration_var = tk.DoubleVar(value=self.transition_duration)

        def on_duration_spinbox_change(*args):
            val = self.duration_var.get()
            duration_scale.set(val)

        duration_spinbox = ttk.Spinbox(duration_row, from_=0.1, to=10.0, increment=0.1, textvariable=self.duration_var,
                                       width=8, font=(FONT_FAMILY, 10), command=on_duration_spinbox_change)
        duration_spinbox.pack(side="left", padx=(0, 10))

        tk.Label(duration_row, text="秒", font=(FONT_FAMILY, 10), fg="#7f8c8d", bg="#ffffff").pack(side="left")

        duration_scale = ttk.Scale(duration_row, from_=0.1, to=10.0, orient="horizontal", length=180)
        duration_scale.pack(side="left", padx=(15, 0))
        duration_scale.set(self.transition_duration)

        def on_duration_scale_change(val):
            self.duration_var.set(float(val))

        duration_scale.configure(command=on_duration_scale_change)

        # 帧数行放在持续时间行后面，与持续时间对齐
        # 先放置丝滑子效果行（初始可能隐藏）
        self.smooth_effect_row.pack(fill="x", pady=(0, 20))
        # 再放置动画方向行（初始可能隐藏）
        self.slide_direction_row.pack(fill="x", pady=(0, 20))
        # 再放置帧数行
        self.frame_row = tk.Frame(right_frame, bg="#ffffff")

        tk.Label(self.frame_row, text="帧数", font=(FONT_FAMILY, 10), fg="#34495e", bg="#ffffff", width=8,
                 anchor="w").pack(side="left")

        self.frame_var = tk.IntVar(value=self.transition_frames)

        def on_frame_spinbox_change(*args):
            val = self.frame_var.get()
            frame_scale.set(val)

        frame_spinbox = ttk.Spinbox(self.frame_row, from_=4, to=30, textvariable=self.frame_var, width=8,
                                    font=(FONT_FAMILY, 10), command=on_frame_spinbox_change)
        frame_spinbox.pack(side="left", padx=(0, 10))

        tk.Label(self.frame_row, text="帧", font=(FONT_FAMILY, 10), fg="#7f8c8d", bg="#ffffff").pack(side="left")

        frame_scale = ttk.Scale(self.frame_row, from_=4, to=30, orient="horizontal", length=180)
        frame_scale.pack(side="left", padx=(15, 0))
        frame_scale.set(self.transition_frames)

        def on_frame_scale_change(val):
            self.frame_var.set(int(float(val)))

        frame_scale.configure(command=on_frame_scale_change)

        # 弹性空间，将按钮推到底部
        spacer = tk.Frame(right_frame, bg="#ffffff", height=1)
        spacer.pack(fill="both", expand=True)

        # 按钮区域（固定在底部）
        btn_frame = tk.Frame(right_frame, bg="#ffffff")
        btn_frame.pack(fill="x", side="bottom")

        def save_settings():
            effect_display = self.effect_display_var.get()
            effect = effect_reverse_map.get(effect_display, "smooth")
            frames = self.frame_var.get()
            duration = round(self.duration_var.get(), 1)

            if frames < 4:
                frames = 4
            if frames > 30:
                frames = 30
            if duration < 0.1:
                duration = 0.1
            if duration > 10.0:
                duration = 10.0

            # 获取丝滑转场子效果
            smooth_effect_display = self.smooth_effect_display_var.get()
            smooth_effect_map_rev = {"渐显混合": "fade", "放映机": "slide", "滑入": "scan", "随机转场": "random"}
            smooth_effect = smooth_effect_map_rev.get(smooth_effect_display, "fade")

            config["transition_effect"] = effect
            config["transition_frames"] = frames
            config["transition_duration"] = duration
            config["smooth_effect"] = smooth_effect  # 新增
            # 保存动画方向
            direction_display = self.slide_direction_var.get()
            direction_map_rev = {"← 向左": "left", "向右 →": "right", "↑ 向上": "up", "向下 ↓": "down",
                                 "随机方向 [?]": "random"}
            config["slide_direction"] = direction_map_rev.get(direction_display, "right")
            save_config()
            self.dialog.destroy()

        def restore_default():
            self.effect_display_var.set("丝滑转场")
            self.smooth_effect_display_var.set("渐显混合")
            self.slide_direction_var.set("向右 →")
            self.frame_var.set(12)
            self.duration_var.set(1.0)
            self.update_ui_by_effect()
            self.update_smooth_effect_visibility()

        ttk.Button(btn_frame, text="恢复默认", command=restore_default, width=11).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="保存", command=save_settings, width=11).pack(side="right", padx=(0, 10))
        ttk.Button(btn_frame, text="取消", command=self.dialog.destroy, width=11).pack(side="right")

        # 确保小数保留1位
        def on_duration_validate(*args):
            self.duration_var.set(round(self.duration_var.get(), 1))

        self.duration_var.trace_add("write", on_duration_validate)

    def on_effect_changed(self, event=None):
        """效果切换时的处理"""
        old_effect = config.get("transition_effect", "smooth")
        new_effect_display = self.effect_display_var.get()
        new_effect = "frame" if new_effect_display == "帧动画" else "smooth"

        if new_effect == "frame" and old_effect != "frame":
            self.show_frame_warning()
        else:
            self.update_ui_by_effect()
            self.update_smooth_effect_visibility()
            # 当子效果改变时，也需要更新方向可见性
            self.smooth_effect_combo.bind("<<ComboboxSelected>>", lambda e: self._update_direction_visibility())
            # 保存当前动画方向设置到配置
            direction_display = self.slide_direction_var.get()
            direction_map_rev = {"← 向左": "left", "向右 →": "right", "↑ 向上": "up", "向下 ↓": "down",
                                 "随机方向 [?]": "random"}
            if direction_display in direction_map_rev:
                config["slide_direction"] = direction_map_rev[direction_display]
                save_config()

    def show_frame_warning(self):
        """显示帧动画性能警告对话框"""
        msg = "由于目前无法调用Windows原生渐显混合动画，\n\n" \
              "所以采用逐帧渲染壁纸文件，\n" \
              "这可能导致壁纸切换时影响电脑性能，\n" \
              "并且壁纸切换画面也并不流畅\n\n" \
              "您也可以继续使用「丝滑转场」效果"

        if IS_WINDOWS:
            result = ctypes.windll.user32.MessageBoxW(0, msg, "性能警告", 0x00000001 | 0x00000030)
        else:
            result = 1 if messagebox.askokcancel("性能警告", msg) else 0

        if result == 1:
            self.update_ui_by_effect()
        else:
            self.effect_display_var.set("丝滑转场")
            self.update_ui_by_effect()

    def update_ui_by_effect(self):
        """根据当前选择的效果显示/隐藏帧数控件、丝滑子效果及方向"""
        is_frame = self.effect_display_var.get() == "帧动画"
        is_smooth = self.effect_display_var.get() == "丝滑转场"
        if is_frame:
            self.frame_row.pack(fill="x", pady=(20, 0))
            self.smooth_effect_row.pack_forget()
            self.slide_direction_row.pack_forget()
        elif is_smooth:
            self.frame_row.pack_forget()
            # 丝滑子效果行始终显示，但方向行根据子效果类型显示
            self.smooth_effect_row.pack(fill="x", pady=(0, 20))
            self._update_direction_visibility()
        else:
            self.frame_row.pack_forget()
            self.smooth_effect_row.pack_forget()
            self.slide_direction_row.pack_forget()

    def update_smooth_effect_visibility(self):
        """根据效果选择显示/隐藏丝滑子效果下拉框，并联动方向行"""
        is_smooth = self.effect_display_var.get() == "丝滑转场"
        if is_smooth:
            self.smooth_effect_row.pack(fill="x", pady=(0, 20))
            self._update_direction_visibility()
        else:
            self.smooth_effect_row.pack_forget()
            self.slide_direction_row.pack_forget()

    def _update_direction_visibility(self):
        """根据当前选择的转场效果决定是否显示方向选择"""
        current_effect_display = self.smooth_effect_display_var.get()
        is_direction_sensitive = (current_effect_display == "放映机" or current_effect_display == "滑入")
        if is_direction_sensitive:
            self.slide_direction_row.pack(fill="x", pady=(0, 20))
        else:
            self.slide_direction_row.pack_forget()


def register_global_hotkeys():
    """注册所有全局快捷键"""
    global hotkey_running, hotkey_thread
    log("[全局快捷键] 开始注册...")
    try:
        import keyboard
        log("[全局快捷键] keyboard 模块导入成功")
    except ImportError:
        log("[全局快捷键] keyboard 模块未安装，跳过注册")
        return

    # 先取消现有注册
    unregister_global_hotkeys()
    log("[全局快捷键] 已取消原有注册")

    # 定义动作映射
    action_map = {
        "previous": previous_wallpaper,
        "next": next_wallpaper,
        "random": random_wallpaper,
        "show": lambda: root.deiconify() if root else None,
        "jump": lambda: __import__('subprocess').Popen([os.path.join(os.path.dirname(sys.executable),
                                                                     "pythonw.exe") if os.path.exists(
            os.path.join(os.path.dirname(sys.executable), "pythonw.exe")) else sys.executable,
                                                        os.path.abspath(sys.argv[0]), "--jump-to-wallpaper"])
    }

    # 默认快捷键映射（如果配置中没有设置）
    default_hotkeys = {
        "previous": "U",
        "next": "N",
        "random": "3",
        "show": "X",
        "jump": "V"
    }

    # 为每个设置的热键注册回调
    for key_name, func in action_map.items():
        hotkey = config.get(f"hotkey_{key_name}", "")
        if not hotkey:
            hotkey = default_hotkeys.get(key_name, "")
            log(f"[全局快捷键] {key_name} 配置为空，使用默认值 '{hotkey}'")
        else:
            log(f"[全局快捷键] {key_name} 使用配置值 '{hotkey}'")

        if hotkey and func:
            try:
                keyboard.add_hotkey(hotkey, func, suppress=False)
                log(f"[全局快捷键] 注册成功: {hotkey} -> {key_name}")
            except Exception as e:
                log(f"[全局快捷键] 注册失败: {hotkey} -> {key_name}, 错误: {e}")
        else:
            log(f"[全局快捷键] {key_name} 未设置有效快捷键，跳过")

    hotkey_running = True
    log("[全局快捷键] 注册流程完成")


def unregister_global_hotkeys():
    """取消注册所有全局快捷键"""
    global hotkey_running
    try:
        import keyboard
        keyboard.unhook_all_hotkeys()
        hotkey_running = False
        log("已取消所有全局快捷键")
    except:
        pass


# 在程序启动时注册
def init_global_hotkeys():
    """初始化全局快捷键（在 main() 中调用）"""
    log("[init_global_hotkeys] 开始")
    try:
        import keyboard
        log("[init_global_hotkeys] keyboard 模块导入成功")
        register_global_hotkeys()
        log("[init_global_hotkeys] register_global_hotkeys 调用完成")
    except ImportError as e:
        log(f"[init_global_hotkeys] keyboard 模块未安装: {e}")
    except Exception as e:
        log(f"[init_global_hotkeys] 未知错误: {e}")


def handle_command_line():
    global apply_timer, slide_timer, transition_in_progress, hide_window, pending_action
    # 修复编译后 sys.stderr 为 None 的问题
    if sys.stderr is None:
        import io
        sys.stderr = io.StringIO()

    # ========== 修复 auto-py-to-exe 打包后参数混乱的问题 ==========
    # 获取当前 exe 的文件名（不含路径）
    exe_name = os.path.basename(sys.argv[0])
    # 过滤掉干扰项，只保留真正的参数
    clean_args = [sys.argv[0]]
    for arg in sys.argv[1:]:
        # 跳过以下几种情况：
        # 1. 等于 exe 完整路径
        # 2. 等于 exe 文件名
        # 3. 是 .exe 结尾的字符串（可能是重复的路径）
        if arg == sys.argv[0]:
            continue
        if arg == exe_name:
            continue
        if arg.lower().endswith('.exe'):
            continue
        clean_args.append(arg)
    sys.argv = clean_args
    # ============================================================

    parser = argparse.ArgumentParser(description='xxdz_上一个桌面背景')
    parser.add_argument('--previous', action='store_true', help='切换到上一张壁纸')
    parser.add_argument('--next', action='store_true', help='切换到下一张壁纸')
    parser.add_argument('--random', action='store_true', help='随机切换壁纸')
    parser.add_argument('--show', action='store_true', help='显示主窗口')
    parser.add_argument('--hide', action='store_true', help='隐藏主窗口（用于后台启动）')
    parser.add_argument('--jump-to-wallpaper', action='store_true', help='打开壁纸侧边栏')
    parser.add_argument('--set-wallpaper', type=str, help='设置指定壁纸')
    args = parser.parse_args()

    if args.hide:
        hide_window = True

    # ========== 新逻辑：直接执行动作，然后退出 ==========
    if args.previous:
        # 直接执行上一张壁纸，不依赖主窗口
        previous_wallpaper()
        sys.exit(0)
    elif args.next:
        next_wallpaper()
        sys.exit(0)
    elif args.random:
        random_wallpaper()
        sys.exit(0)
    elif args.show:
        # 显示主窗口：如果已有主窗口则激活，否则正常启动
        hwnd_existing = ctypes.windll.user32.FindWindowW(WND_CLASS_NAME, None) if IS_WINDOWS else None
        if hwnd_existing:
            log("找到已有窗口，尝试激活")
            cmd_bytes = "show".encode('utf-8')
            cds = COPYDATASTRUCT()
            cds.dwData = 1
            cds.cbData = len(cmd_bytes) + 1
            cds.lpData = ctypes.cast(cmd_bytes, ctypes.c_void_p)
            ctypes.windll.user32.SendMessageW(hwnd_existing, WM_COPYDATA, 0, ctypes.byref(cds))
            ctypes.windll.user32.ShowWindow(hwnd_existing, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd_existing)
            ctypes.windll.user32.ShowWindow(hwnd_existing, 1)
            sys.exit(0)
        else:
            # 没有主窗口，正常启动（不退出，让 main 继续）
            return False
    elif args.jump_to_wallpaper:
        log("收到 --jump-to-wallpaper 命令，直接创建侧边栏窗口")
        try:
            folder = config.get("slide_folder", "")
            current = config.get("current_wallpaper", "")
            log(f"壁纸文件夹: {folder}")
            log(f"当前壁纸: {current}")
            if not folder or not os.path.isdir(folder):
                log("壁纸文件夹无效，显示提示")
                show_message("提示喵", "请先在软件中设置壁纸文件夹")
                sys.exit(0)
            # 创建侧边栏窗口（复用或新建 root）
            global root
            if root is None or not root.winfo_exists():
                sidebar_root = tk.Tk()
            else:
                # 如果主窗口已存在，用 Toplevel 避免冲突
                sidebar_root = tk.Toplevel(root)
            log_file_path = os.path.join(BASE_DIR, "wallpaper_debug.log")
            app = WallpaperSidebar(
                sidebar_root,
                folder,
                current,
                None,
                show_message=show_message,
                switch_wallpaper=lambda target: (
                    push_wallpaper(target),
                    set_wallpaper_direct(target, "侧边栏切换"),
                ),
            )
            sidebar_root.mainloop()
            sys.exit(0)
        except Exception as e:
            log(f"打开侧边栏失败: {e}")
            import traceback
            log(traceback.format_exc())
            show_message("错误", f"打开侧边栏失败: {e}")
            sys.exit(0)
    elif args.set_wallpaper:
        target = args.set_wallpaper
        if os.path.isfile(target):
            # 直接设置壁纸（不依赖主窗口）
            log(f"设置指定壁纸: {target}")
            push_wallpaper(target)
            set_wallpaper_direct(target, "命令行设置")
            sys.exit(0)
        else:
            log(f"壁纸文件不存在: {target}")
            sys.exit(0)

    # 如果没有匹配任何动作，正常启动（返回 False 让 main 继续）
    return False


# ====================== 缩小的色块按钮 ======================
def create_color_button(parent, color, row, col, command):
    btn = tk.Button(parent, bg=color, width=6, height=1, relief="flat", borderwidth=1, highlightthickness=0,
                    command=command)
    btn.grid(row=row, column=col, padx=2, pady=2)

    def on_enter(e): btn.config(relief="solid", highlightbackground="#555")

    def on_leave(e): btn.config(relief="flat", highlightbackground="white")

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def create_gradient_button(parent, color1, color2, row, col, command):
    btn_width = 45  # 渐变预设色块的尺寸
    btn_height = 30
    img = Image.new("RGB", (btn_width, btn_height))
    color1_rgb = (int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16))
    color2_rgb = (int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16))

    for x in range(btn_width):
        t = x / (btn_width - 1) if btn_width > 1 else 0.0
        r = int(color1_rgb[0] * (1 - t) + color2_rgb[0] * t)
        g = int(color1_rgb[1] * (1 - t) + color2_rgb[1] * t)
        b = int(color1_rgb[2] * (1 - t) + color2_rgb[2] * t)
        for y in range(btn_height):
            img.putpixel((x, y), (r, g, b))

    photo = ImageTk.PhotoImage(img)
    btn = tk.Button(parent, image=photo, width=btn_width, height=btn_height, relief="flat", borderwidth=1,
                    highlightthickness=0, command=command)
    btn.image = photo
    btn.grid(row=row, column=col, padx=2, pady=2)

    def on_enter(e):
        btn.config(relief="solid", highlightbackground="#555")

    def on_leave(e):
        btn.config(relief="flat", highlightbackground="white")

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def main():
    import logging
    logging.disable(logging.CRITICAL)  # 完全禁用所有日志输出（包括第三方库）
    global config, root, canvas, slide_frame, shuffle_var, chk_next, chk_random, chk_prev
    global single_frame, video_frame, video_entry, gradient_frame, color1_var, color1_preview, color2_var, color2_preview, angle_var
    global solid_frame, solid_color_var, solid_color_preview, mode_var, fit_var
    global ctx_prev_var, ctx_next_var, ctx_random_var, ctx_personalize_var, ctx_jump_var, ctx_file_wallpaper_var, wallpaper_monitor_running, wallpaper_monitor_last
    global preview_images_frame, wallpaper_preview_labels, folder_entry
    global tray_icon_obj
    global apply_timer, slide_timer, transition_in_progress
    global stop_slideshow, start_slideshow, restart_slideshow, reset_slide_timer, slide_next
    global apply_timer, slide_timer, transition_in_progress
    global hide_window, pending_action
    global single_entry
    version_label = None  # 版本标签引用，用于更新

    # 检查开机自启动标志文件（由 PowerOn.vbs 创建）
    flag_file = os.path.join(os.environ.get('TEMP') or tempfile.gettempdir(), 'WallpaperHideFlag.tmp')
    if os.path.exists(flag_file):
        try:
            with open(flag_file, 'r') as f:
                flag_content = f.read().strip()
            if flag_content == 'T':
                hide_window = True
                log("检测到开机自启动标志文件（内容=T），以无窗口模式启动")
            else:
                log(f"开机自启动标志文件内容为 '{flag_content}'，不以无窗口模式启动")
            os.remove(flag_file)
            log("已删除开机自启动标志文件")
        except Exception as e:
            log(f"处理开机自启动标志文件失败: {e}")

    # 先处理命令行参数，如果已有主进程则直接退出，否则继续启动
    if handle_command_line():
        sys.exit(0)

    # 判断是否为“动作启动”（右键菜单触发），非动作启动才上报使用统计
    args_for_check = argparse.ArgumentParser()
    args_for_check.add_argument('--previous', action='store_true')
    args_for_check.add_argument('--next', action='store_true')
    args_for_check.add_argument('--random', action='store_true')
    args_for_check.add_argument('--show', action='store_true')
    parsed_args, _ = args_for_check.parse_known_args()
    is_action_launch = (parsed_args.previous or parsed_args.next or parsed_args.random or parsed_args.show)
    if not is_action_launch:
        # 在独立线程中上报（避免阻塞主窗口）
        report_usage()

    # 双重检查：如果已有主进程（例如 handle_command_line 因窗口未找到而未退出），则退出
    existing_hwnd = ctypes.windll.user32.FindWindowW(WND_CLASS_NAME, None) if IS_WINDOWS else None
    if existing_hwnd:
        log("检测到已有主进程，退出本实例")
        if pending_action:
            cmd_bytes = pending_action.encode('utf-8')
            cds = COPYDATASTRUCT()
            cds.dwData = 1
            cds.cbData = len(cmd_bytes) + 1
            cds.lpData = ctypes.cast(cmd_bytes, ctypes.c_void_p)
            ctypes.windll.user32.SendMessageW(existing_hwnd, WM_COPYDATA, 0, ctypes.byref(cds))
        sys.exit(0)

    log("=== 启动新的壁纸控制器实例 ===")

    root = tk.Tk()
    dependency_availability = {
        "PIL": Image is not None,
        "requests": requests is not None,
        "numpy": HAS_NUMPY,
        "psutil": psutil is not None,
    }
    if not prompt_install_dependencies(messagebox, dependency_availability, parent=root):
        try:
            root.destroy()
        except Exception:
            pass
        sys.exit(0)

    # 只有在正常显示主窗口时才创建白色矩形覆盖层动画（非 --hide 模式）
    if not hide_window:
        # 创建蓝色覆盖层窗口（透明效果专用）
        blue_overlay = tk.Toplevel(root)
        blue_overlay.overrideredirect(True)  # 无边框
        blue_overlay.configure(bg='white')

        # 设置覆盖层大小与主窗口相同并跟随主窗口
        overlay_alive = True  # 标志位，标记覆盖层是否还存在

        def update_overlay_geometry():
            nonlocal overlay_alive
            if not overlay_alive:
                return  # 覆盖层已销毁，停止更新
            try:
                x = root.winfo_x()
                y = root.winfo_y()
                w = root.winfo_width()
                h = root.winfo_height()
                if w > 1 and h > 1:
                    blue_overlay.geometry(f'{w}x{h + 35}+{x}+{y}')  # 让白色矩形动画蒙版增加35的高度，因为下面有的没覆盖到
                root.after(50, update_overlay_geometry)
            except tk.TclError:
                # 窗口已销毁，停止更新
                overlay_alive = False

        update_overlay_geometry()

        # 将覆盖层置顶
        blue_overlay.lift()
        blue_overlay.attributes('-topmost', True)

        # 淡出动画：0.5秒内透明度从1.0降到0.0（丝滑版，使用 ease-out 缓动）
        import math
        duration = 0.5  # 秒
        fps = 60  # 每秒帧数
        interval = int(1000 / fps)  # 约16.67毫秒
        total_frames = int(duration * fps)  # 30帧

        def ease_out_cubic(t):
            """缓动曲线：开始快，结束慢"""
            return 1 - (1 - t) ** 3

        frame = 0

        def fade_out():
            nonlocal frame, overlay_alive
            if frame <= total_frames:
                # 计算进度 t (0~1)
                t = frame / total_frames
                # 应用缓动曲线，使透明度变化更自然
                alpha = 1.0 - ease_out_cubic(t)
                if alpha < 0:
                    alpha = 0
                try:
                    blue_overlay.attributes('-alpha', alpha)
                    frame += 1
                    root.after(interval, fade_out)
                except tk.TclError:
                    overlay_alive = False
            else:
                try:
                    blue_overlay.destroy()
                except:
                    pass
                overlay_alive = False

        fade_out()

    if hide_window:
        root.withdraw()
    root.title(f"{APP_NAME} v1")
    # 设置主窗口图标
    icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
    if os.path.exists(icon_path):
        try:
            root.iconbitmap(icon_path)
        except:
            pass

    # 检查是否有中断的过渡动画需要恢复
    def check_and_resume():
        if resume_interrupted_transition():
            log("已恢复中断的过渡动画")

    root.after(500, check_and_resume)
    root.geometry("980x560")
    root.minsize(920, 520)
    root.resizable(True, True)
    root.configure(bg=UI_BG)
    # 如果标题图片已创建，同步背景色
    if 'title_label' in locals():
        title_label.config(bg=root.cget("bg"))
    style = ttk.Style()
    setup_modern_style(style)

    main_container = ttk.Frame(root, style="Panel.TFrame")
    main_container.pack(fill="both", expand=True, padx=24, pady=18)

    # ========== 在窗口完全加载后再加载标题图片（带从右向左缓动动画） ==========
    def load_title_image_after_window_ready():
        """窗口完全渲染后加载标题图片，带从右向左缓动进入动画"""
        global title_label
        title_img_path = os.path.join(BASE_DIR, "img", "txtlogo.png")
        if not os.path.exists(title_img_path):
            log(f"标题图片不存在: {title_img_path}")
            return

        # 先清理可能存在的旧标题图片（避免图层叠加）
        try:
            if title_label is not None:
                title_label.destroy()
        except:
            pass

        try:
            import hashlib
            expected_md5 = "44e891d1c8423ff89baefdadd4d60b53"
            with open(title_img_path, "rb") as f:
                file_md5 = hashlib.md5(f.read()).hexdigest()
            if file_md5 != expected_md5:
                raise ValueError("MD5 verification failed")

            original_img = Image.open(title_img_path)
            if original_img.mode != 'RGBA':
                original_img = original_img.convert('RGBA')

            target_height = 114
            ratio = target_height / original_img.height
            new_width = int(original_img.width * ratio)
            resized_img = original_img.resize((new_width, target_height), Image.Resampling.LANCZOS)
            title_photo = ImageTk.PhotoImage(resized_img)

            # 创建 Label 显示图片
            title_label = tk.Label(root, image=title_photo, bg=root.cget("bg"), highlightthickness=0, bd=0)
            title_label.image = title_photo

            # 获取最终位置
            window_width = root.winfo_width()
            if window_width <= 0:
                window_width = 950  # 默认宽度
            final_x = window_width - new_width - 20

            # 从右侧外面开始（x = 窗口右边缘）
            start_x = window_width
            title_label.place(x=start_x, y=3)
            title_label.lift()

            # 缓动动画参数
            steps = 20
            step = 0

            def ease_out_cubic(t):
                return 1 - (1 - t) ** 3

            def animate():
                nonlocal step
                step += 1
                if step <= steps:
                    t = step / steps
                    ease_t = ease_out_cubic(t)
                    current_x = start_x - (start_x - final_x) * ease_t
                    try:
                        title_label.place(x=int(current_x), y=3)
                    except:
                        pass
                    root.after(12, animate)
                else:
                    try:
                        title_label.place(x=final_x, y=3)
                        log(f"标题图片动画完成，位置: x={final_x}, y=3")
                    except:
                        pass

            # 开始动画
            animate()

            # 监听窗口大小变化（重新计算最终位置，但不做动画）
            def on_window_resize(event):
                if event.widget == root:
                    try:
                        if title_label.winfo_exists():
                            new_window_width = event.width
                            if new_window_width > 0:
                                new_final_x = new_window_width - new_width - 20
                                title_label.place(x=new_final_x, y=3)
                                title_label.lift()
                    except:
                        pass

            root.bind("<Configure>", on_window_resize)

        except Exception as e:
            log(f"加载标题图片失败: {e}")

    # 等待窗口完全渲染后再加载标题图片
    root.update_idletasks()
    root.after(300, load_title_image_after_window_ready)
    preview_frame = ttk.Frame(main_container, width=400)
    preview_frame.pack(side="left", fill="both", expand=True, padx=(0, 20))
    preview_frame.pack_propagate(False)
    canvas = tk.Canvas(preview_frame, bg="#eef6f5", width=400, height=250, highlightthickness=1,
                       highlightbackground=UI_BORDER, highlightcolor=UI_ACCENT)
    canvas.pack(pady=20)
    util_frame = ttk.Frame(preview_frame)
    util_frame.pack(fill="x", pady=(20, 0))
    ttk.Label(util_frame, text="实用设置", style="Title.TLabel").pack(anchor="w", pady=(0, 8))

    auto_start_var = tk.BooleanVar(value=config.get("auto_start", False))
    # 确保首次启动时开机自启动复选框默认不勾选（与配置同步）
    if not config.get("auto_start_prompt_shown", False):
        auto_start_var.set(False)

    def set_auto_start(enable):
        """设置开机自启动"""
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        value_name = "xxdz_WallpaperController"
        if is_frozen():
            exe_path = sys.executable
        else:
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if os.path.exists(pythonw):
                exe_path = f'"{pythonw}" "{os.path.abspath(__file__)}" --hide'
            else:
                exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}" --hide'
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enable:
                winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, exe_path)
                log("开机自启动已启用")
            else:
                try:
                    winreg.DeleteValue(key, value_name)
                    log("开机自启动已禁用")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            log(f"设置开机自启动失败: {e}")
            show_message("错误", f"设置开机自启动失败: {e}")

    def toggle_auto_start():
        """切换开机自启动状态"""
        enable = auto_start_var.get()
        set_auto_start(enable)
        config["auto_start"] = enable
        save_config()

    chk_auto = ttk.Checkbutton(util_frame, text="开机自启动", variable=auto_start_var, command=toggle_auto_start)
    chk_auto.pack(anchor="w", pady=2)
    run_in_background_var = tk.BooleanVar(value=config.get("run_in_background", True))
    chk_background = ttk.Checkbutton(util_frame, text="能后台运行", variable=run_in_background_var,
                                     command=dummy_toggle)
    chk_background.pack(anchor="w", pady=2)
    tray_row_frame = ttk.Frame(util_frame)
    tray_row_frame.pack(anchor="w", pady=2, fill="x")
    tray_icon_var = tk.BooleanVar(value=config.get("tray_icon", True))
    chk_tray = ttk.Checkbutton(tray_row_frame, text="系统托盘图标", variable=tray_icon_var)
    chk_tray.pack(side="left")
    if IS_MACOS:
        chk_tray.configure(text="菜单栏常驻")
        tray_icon_var.set(config.get("tray_icon", True))
        run_in_background_var.set(config.get("run_in_background", True))
        config["tray_icon"] = tray_icon_var.get()
        config["run_in_background"] = run_in_background_var.get()
        save_config()
        log("macOS 下使用独立原生菜单栏 helper，避免 AppKit 与 Tk 主循环冲突")

    # ========== 托盘图标相关函数 ==========
    tray_icon_obj = None

    def handle_tray_action(action):
        """处理托盘菜单动作"""
        if action == "previous":
            previous_wallpaper()
        elif action == "next":
            next_wallpaper()
        elif action == "random":
            random_wallpaper()
        elif action == "show":
            root.deiconify()
            root.lift()
            root.focus_force()
        elif action == "jump":
            # 调用跳转到壁纸功能
            import subprocess
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if not os.path.exists(pythonw):
                pythonw = sys.executable
            main_script = os.path.abspath(sys.argv[0])
            subprocess.Popen([pythonw, main_script, "--jump-to-wallpaper"])

    def open_tray_settings():
        """打开托盘功能设置窗口 - 现代化UI"""
        win = tk.Toplevel(root)
        win.title("托盘设置")
        # 计算窗口居中位置（固定大小720x520，宽度增加140px用于侧边栏）
        x = (win.winfo_screenwidth() - 720) // 2
        y = (win.winfo_screenheight() - 520) // 2
        win.geometry(f"720x520+{x}+{y}")
        # 设置窗口图标
        icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
        if os.path.exists(icon_path):
            try:
                win.iconbitmap(icon_path)
            except:
                pass
        win.resizable(False, False)
        win.transient(root)
        win.grab_set()
        win.configure(bg="#ffffff")

        # 设置样式
        style = ttk.Style()
        style.configure("Modern.TFrame", background="#ffffff")
        style.configure("Modern.TLabel", background="#ffffff", font=(FONT_FAMILY, 10))
        style.configure("Modern.TButton", font=(FONT_FAMILY, 9), padding=5)

        # 主容器（使用Frame而不是ttk.Frame以支持侧边栏）
        main_frame = tk.Frame(win, bg="#ffffff")
        main_frame.pack(fill="both", expand=True)

        # 左侧说明区域
        left_frame = tk.Frame(main_frame, bg="#9BFFF2", width=140)
        left_frame.pack(side="left", fill="y")
        left_frame.pack_propagate(False)

        title_label = tk.Label(left_frame, text="托盘功能", font=(FONT_FAMILY, 14, "bold"), bg="#9BFFF2", fg="#2c3e50")
        title_label.pack(pady=(40, 10))

        desc_label = tk.Label(left_frame, text="设置系统托盘图标的\n菜单项和行为\n\nOwO 为已启用\nXwX 为已禁用",
                              font=(FONT_FAMILY, 9), bg="#9BFFF2",
                              fg="#7f8c8d", justify="center")
        desc_label.pack(pady=(10, 0))

        # 右侧内容区域
        right_frame = tk.Frame(main_frame, bg="#ffffff")
        right_frame.pack(side="left", fill="both", expand=True)

        # 内容容器（带内边距）
        content_frame = ttk.Frame(right_frame, style="Modern.TFrame")
        content_frame.pack(fill="both", expand=True, padx=25, pady=20)

        # 标题
        title_label = tk.Label(content_frame, text="托盘图标设置", font=(FONT_FAMILY, 16, "bold"),
                               bg="#ffffff", fg="#2c3e50")
        title_label.pack(anchor="w", pady=(0, 15))

        # 单击行为区域（禁用状态）
        click_frame = ttk.Frame(content_frame, style="Modern.TFrame")
        click_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(click_frame, text="单击托盘图标", font=(FONT_FAMILY, 11, "bold"),
                  style="Modern.TLabel").pack(anchor="w")

        # 下拉菜单容器
        combo_container = ttk.Frame(click_frame, style="Modern.TFrame")
        combo_container.pack(anchor="w", pady=(8, 5))

        click_combo = ttk.Combobox(combo_container, values=["下一张壁纸"],
                                   state="disabled", width=18, font=(FONT_FAMILY, 9))
        click_combo.set("下一张壁纸")
        click_combo.pack(side="left")

        dev_label = tk.Label(combo_container, text="<-- 单击动作功能开发中捏...QwQ", font=(FONT_FAMILY, 8),
                             fg="#e74c3c", bg="#ffffff")
        dev_label.pack(side="left", padx=(10, 0))

        # 分隔线
        separator = ttk.Separator(content_frame, orient="horizontal")
        separator.pack(fill="x", pady=10)

        # 右键菜单区域
        menu_frame = ttk.Frame(content_frame, style="Modern.TFrame")
        menu_frame.pack(fill="both", expand=True, pady=(5, 0))

        # 标题栏
        title_bar = ttk.Frame(menu_frame, style="Modern.TFrame")
        title_bar.pack(fill="x", pady=(0, 10))

        ttk.Label(title_bar, text="右键菜单项", font=(FONT_FAMILY, 11, "bold"),
                  style="Modern.TLabel").pack(side="left")

        tip_label = ttk.Label(title_bar, text=">w<  拖拽排序 & 勾选启用/禁用",
                              font=(FONT_FAMILY, 8), foreground="#7f8c8d")
        tip_label.pack(side="right")

        # Treeview 表格
        tree_frame = ttk.Frame(menu_frame)
        tree_frame.pack(fill="both", expand=True)

        # 创建 Treeview
        columns = ("enabled", "label", "action")
        tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=7)

        # 设置列
        tree.heading("#0", text="")
        tree.column("#0", width=0, stretch=False)
        tree.heading("enabled", text="启用", anchor="center")
        tree.column("enabled", width=50, anchor="center")
        tree.heading("label", text="菜单项名称", anchor="w")
        tree.column("label", width=200, anchor="w")
        tree.heading("action", text="功能", anchor="w")
        tree.column("action", width=130, anchor="w")

        # 滚动条
        v_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=v_scrollbar.set)

        tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")

        # 存储数据
        menu_items = []

        # 动作映射
        action_map = {
            "show": "显示主界面",
            "previous": "上一张壁纸",
            "next": "下一张壁纸",
            "random": "随机壁纸",
            "exit": "退出程序",
            "about": "关于作者",
            "jump": "通过侧边栏跳转到指定壁纸"
        }

        # 加载现有菜单项（从 action 列表恢复）
        # 动作到默认标签的映射
        action_to_label = {
            "show": "打开设置主界面",
            "previous": "上一张壁纸",
            "next": "下一张壁纸",
            "random": "随机壁纸",
            "about": "关于作者",
            "jump": "跳转到壁纸",
            "exit": "退出程序"
        }

        tray_actions = config.get("tray_menu_items", [])
        if tray_actions and isinstance(tray_actions[0], str):
            # 新格式：只存储 action 字符串
            for action in tray_actions:
                menu_items.append({
                    "label": action_to_label.get(action, action),
                    "action": action,
                    "enabled": True
                })
        else:
            # 兼容旧格式：存储的是字典
            for item in tray_actions:
                menu_items.append({
                    "label": item.get("label", action_to_label.get(item.get("action", ""), "")),
                    "action": item.get("action", ""),
                    "enabled": True
                })

        # 配置高亮标签
        tree.tag_configure("drag_highlight", background="#cce5ff", foreground="#000")
        tree.tag_configure("normal", background="white", foreground="#000")

        # 刷新表格
        def refresh_tree():
            tree.delete(*tree.get_children())
            for i, item in enumerate(menu_items):
                enabled_mark = "OwO" if item["enabled"] else "XwX"
                values = (enabled_mark, item["label"], action_map.get(item["action"], item["action"]))
                tree.insert("", "end", iid=str(i), values=values, tags=("normal",))

        refresh_tree()

        # 点击复选框切换启用状态
        def on_tree_click(event):
            region = tree.identify_region(event.x, event.y)
            if region == "cell":
                column = tree.identify_column(event.x)
                if column == "#1":  # 启用列
                    item_id = tree.identify_row(event.y)
                    if item_id:
                        idx = int(item_id)
                        menu_items[idx]["enabled"] = not menu_items[idx]["enabled"]
                        refresh_tree()
                        tree.selection_set(item_id)

        tree.bind("<Button-1>", on_tree_click)

        # 拖拽排序功能（带高亮反馈）
        drag_item = None
        highlight_item = None

        def clear_highlight():
            nonlocal highlight_item
            if highlight_item is not None:
                tree.item(highlight_item, tags=("normal",))
                highlight_item = None

        def set_highlight(item_id):
            nonlocal highlight_item
            clear_highlight()
            if item_id is not None:
                tree.item(item_id, tags=("drag_highlight",))
                highlight_item = item_id

        def on_drag_start(event):
            nonlocal drag_item
            item_id = tree.identify_row(event.y)
            if item_id:
                drag_item = int(item_id)
                tree.selection_set(item_id)
                # 改变光标为手型
                tree.config(cursor="fleur")
                # 开始拖拽时，高亮当前项
                set_highlight(item_id)

        def on_drag_motion(event):
            nonlocal drag_item
            if drag_item is None:
                return
            target_id = tree.identify_row(event.y)
            if target_id and target_id != str(drag_item):
                # 高亮目标行
                set_highlight(target_id)
                # 为了视觉反馈，可以轻微滚动
                tree.see(target_id)
            elif target_id == str(drag_item):
                clear_highlight()

        def on_drag_end(event):
            nonlocal drag_item, highlight_item
            if drag_item is not None:
                target_id = tree.identify_row(event.y)
                if target_id and target_id != str(drag_item):
                    target_idx = int(target_id)
                    # 移动项目
                    item = menu_items.pop(drag_item)
                    menu_items.insert(target_idx, item)
                    refresh_tree()
                    tree.selection_set(str(target_idx))
                    # 高亮目标行（移动后）
                    set_highlight(str(target_idx))
                else:
                    # 无移动，清除高亮
                    clear_highlight()
                drag_item = None
                # 恢复光标
                tree.config(cursor="")

        tree.bind("<Button-1>", on_drag_start, add="+")
        tree.bind("<B1-Motion>", on_drag_motion)
        tree.bind("<ButtonRelease-1>", on_drag_end)

        # 按钮栏
        btn_frame = ttk.Frame(content_frame, style="Modern.TFrame")
        btn_frame.pack(fill="x", pady=(15, 0))

        def reset_default():
            """恢复默认"""
            nonlocal menu_items
            default_items = [
                {"label": "打开设置主界面", "action": "show", "enabled": True},
                {"label": "上一张壁纸", "action": "previous", "enabled": True},
                {"label": "下一张壁纸", "action": "next", "enabled": True},
                {"label": "随机壁纸", "action": "random", "enabled": True},
                {"label": "关于作者", "action": "about", "enabled": True},
                {"label": "跳转到壁纸", "action": "jump", "enabled": True},
                {"label": "退出程序", "action": "exit", "enabled": True}
            ]
            menu_items = default_items
            refresh_tree()
            clear_highlight()

        def save_settings():
            """保存设置"""
            # 保存启用的菜单项（只保存 action，不保存 label）
            enabled_items = [item["action"] for item in menu_items if item["enabled"]]

            config["tray_click_action"] = "next"  # 暂时固定
            config["tray_menu_items"] = enabled_items
            save_config()

            # 更新托盘菜单
            if tray_icon_obj:
                try:
                    import pystray

                    def get_hotkey_suffix(action):
                        """获取动作对应的快捷键显示文本"""
                        action_to_key = {
                            "previous": "previous",
                            "next": "next",
                            "random": "random",
                            "show": "show"
                        }
                        key_name = action_to_key.get(action, "")
                        if key_name:
                            hotkey = config.get(f"hotkey_{key_name}", "")
                            if hotkey:
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
                                        formatted.append(p.capitalize() if len(p) == 1 else p)
                                return "\t" + "+".join(formatted)
                        return ""

                    new_menu_items = []
                    for item in enabled_items:
                        label = item["label"]
                        action = item["action"]
                        hotkey_suffix = get_hotkey_suffix(action)
                        display_label = label + hotkey_suffix if hotkey_suffix else label

                        if action == "customize":
                            new_menu_items.append(pystray.MenuItem(display_label, open_tray_settings))
                        elif action == "about":
                            new_menu_items.append(pystray.MenuItem(display_label, lambda: show_about_window()))
                        elif action == "exit":
                            def do_exit():
                                def exit_in_main_thread():
                                    try:
                                        unregister_global_hotkeys()
                                        global wallpaper_monitor_running
                                        wallpaper_monitor_running = False
                                        stop_slideshow()
                                        if tray_icon_obj:
                                            try:
                                                tray_icon_obj.stop()
                                            except:
                                                pass
                                        if root:
                                            root.quit()
                                            root.destroy()
                                        import sys
                                        sys.exit(0)
                                    except:
                                        import sys
                                        sys.exit(0)

                                if root:
                                    root.after(0, exit_in_main_thread)
                                else:
                                    exit_in_main_thread()

                            new_menu_items.append(pystray.MenuItem(display_label, do_exit))
                        else:
                            new_menu_items.append(
                                pystray.MenuItem(display_label, (lambda a=action: handle_tray_action(a))))
                    tray_icon_obj.menu = pystray.Menu(*new_menu_items)
                except:
                    pass
            win.destroy()
            # 父窗口已销毁，不传递 parent 参数
            messagebox.showinfo("成功嗷", "设置已保存并应用，您可以重启托盘图标以刷新")

        # 按钮
        ttk.Button(btn_frame, text="恢复默认", command=reset_default, width=12).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="保存设置", command=save_settings, width=12).pack(side="right", padx=(0, 10))
        ttk.Button(btn_frame, text="取消", command=win.destroy, width=12).pack(side="right")

    def create_tray_icon():
        """创建托盘图标"""
        global tray_icon_obj
        if IS_MACOS:
            success, error = start_menu_bar(os.path.abspath(__file__), main_pid=os.getpid())
            if success:
                log("macOS 菜单栏常驻已启动")
            else:
                show_message("菜单栏启动失败", error)
            return
        try:
            import pystray
        except ImportError:
            messagebox.showerror("缺少依赖", "请安装 pystray 库：\npip install pystray")
            return

        if tray_icon_obj is not None:
            return

        icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
        if os.path.exists(icon_path):
            icon_image = Image.open(icon_path)
        else:
            icon_image = Image.new('RGB', (64, 64), color='#3399ff')
            draw = ImageDraw.Draw(icon_image)
            draw.rectangle((16, 16, 48, 48), fill='white')

        def get_hotkey_suffix(action):
            """获取动作对应的快捷键显示文本"""
            # 退出程序固定使用 E 快捷键
            if action == "exit":
                return "\t&E"
            # 关于作者固定使用 A 快捷键
            if action == "about":
                return "\t&A"

            # 动作到配置键名的映射
            action_to_key = {
                "previous": "previous",
                "next": "next",
                "random": "random",
                "show": "show",
                "jump": "jump"
            }
            key_name = action_to_key.get(action, "")
            if key_name:
                hotkey = config.get(f"hotkey_{key_name}", "")
                if hotkey:
                    # 格式化快捷键显示（与桌面菜单风格一致，使用 \t 缩进）
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
                    return "\t" + "+".join(formatted)
            # 如果没有设置快捷键，使用默认快捷键
            default_map = {
                "previous": "U",
                "next": "N",
                "random": "3",
                "show": "X",
                "jump": "V"
            }
            default_key = default_map.get(action, "")
            if default_key:
                return f"\t&{default_key.upper()}" if len(default_key) == 1 else f"\t{default_key.upper()}"
            return ""

        def build_menu():
            # 动作到默认标签的映射
            action_to_label = {
                "show": "打开设置主界面",
                "previous": "上一张壁纸",
                "next": "下一张壁纸",
                "random": "随机壁纸",
                "about": "关于作者",
                "jump": "跳转到壁纸",
                "exit": "退出程序"
            }

            menu_items = []
            tray_actions = config.get("tray_menu_items", [])
            for item in tray_actions:
                if isinstance(item, str):
                    # 新格式：只存储 action 字符串
                    action = item
                    # 如果是 random 动作，检查配置中的 ctx_random_wallpaper 开关
                    if action == "random" and not config.get("ctx_random_wallpaper", False):
                        continue  # 跳过随机壁纸菜单项
                    label = action_to_label.get(action, action)
                else:
                    # 兼容旧格式
                    action = item.get("action", "")
                    if action == "random" and not config.get("ctx_random_wallpaper", False):
                        continue
                    label = item.get("label", action_to_label.get(action, action))

                # 添加快捷键后缀
                hotkey_suffix = get_hotkey_suffix(action)
                display_label = label + hotkey_suffix if hotkey_suffix else label

                if action == "customize":
                    menu_items.append(pystray.MenuItem(display_label, open_tray_settings))
                elif action == "about":
                    menu_items.append(pystray.MenuItem(display_label, lambda: show_about_window()))
                elif action == "jump":
                    menu_items.append(pystray.MenuItem(display_label, lambda: handle_tray_action("jump")))
                elif action == "exit":
                    def do_exit():
                        log("用户通过托盘菜单退出程序")
                        stop_video_wallpaper()
                        # 直接强制退出，避免复杂的清理逻辑导致死锁
                        import os as os_module
                        os_module._exit(0)

                    menu_items.append(pystray.MenuItem(display_label, do_exit))
                else:
                    # 使用默认参数捕获当前action值
                    def make_callback(a):
                        return lambda: handle_tray_action(a)

                    menu_items.append(pystray.MenuItem(display_label, make_callback(action)))
            return pystray.Menu(*menu_items)

        def on_click(icon, item=None):
            # 兼容不同版本的 pystray
            action = config.get("tray_click_action", "next")
            log(f"托盘图标被单击，执行动作: {action}")
            handle_tray_action(action)

        def on_click_wrapper(icon, item=None):
            action = config.get("tray_click_action", "next")
            log(f"托盘图标被单击，执行动作: {action}")
            handle_tray_action(action)

        tray_icon_obj = pystray.Icon("wallpaper_controller", icon_image, "xxdz_上一个桌面背景", build_menu())
        tray_icon_obj.on_click = on_click_wrapper
        tray_icon_obj.run_detached()

    def destroy_tray_icon():
        """销毁托盘图标"""
        global tray_icon_obj
        if IS_MACOS:
            stop_menu_bar()
            log("macOS 菜单栏常驻已停止")
            return
        if tray_icon_obj is not None:
            try:
                tray_icon_obj.stop()
            except:
                pass
            tray_icon_obj = None

    tray_settings_btn = ttk.Button(tray_row_frame, text="托盘功能设置", state="disabled", width=12,
                                   command=open_tray_settings)
    tray_settings_btn.pack(side="right", padx=(5, 0))

    transition_var = tk.BooleanVar(value=config.get("transition_animation", True))

    def show_transition_warning():
        """显示过渡动画性能警告对话框（已废弃，仅保留兼容性）"""
        # 现在只有手动切换到帧动画时才弹警告，勾选复选框直接开启
        apply_transition_change()

    def apply_transition_change():
        """实际应用过渡动画设置"""
        config["transition_animation"] = transition_var.get()
        save_config()
        update_transition_btn_state()
        log(f"过渡动画设置已变更为: {config['transition_animation']}")

    def on_transition_changed_real():
        """当复选框状态改变时调用"""
        if transition_var.get():
            show_transition_warning()
        else:
            apply_transition_change()

    # 过渡动画复选框和设置按钮放在同一行
    transition_row_frame = ttk.Frame(util_frame)
    transition_row_frame.pack(anchor="w", pady=2, fill="x")

    transition_var = tk.BooleanVar(value=config.get("transition_animation", True))

    def update_transition_btn_state():
        if transition_var.get():
            transition_settings_btn.config(state="normal")
        else:
            transition_settings_btn.config(state="disabled")

    def on_transition_changed_real():
        """当复选框状态改变时调用"""
        if transition_var.get():
            # 开启过渡动画时显示警告
            show_transition_warning()
        else:
            # 关闭过渡动画时直接保存
            apply_transition_change()

    chk_transition = ttk.Checkbutton(transition_row_frame, text="壁纸切换过渡动画", variable=transition_var,
                                     command=on_transition_changed_real)
    chk_transition.pack(side="left")

    def open_transition_settings():
        TransitionSettingsDialog(root)

    transition_settings_btn = ttk.Button(transition_row_frame, text="过渡动画设置", command=open_transition_settings,
                                         width=12)
    transition_settings_btn.pack(side="right", padx=(5, 0))

    # 根据初始状态设置按钮是否启用
    update_transition_btn_state()

    # 全局快捷键和初始化设置按钮放在同一行
    hotkey_row_frame = ttk.Frame(util_frame)
    hotkey_row_frame.pack(anchor="w", pady=2, fill="x")

    hotkey_btn = ttk.Button(hotkey_row_frame, text="⚡设置全局快捷键", command=open_global_hotkey_dialog, width=18)
    hotkey_btn.pack(side="left", padx=(0, 0))

    init_btn = ttk.Button(hotkey_row_frame, text="⚡初始化全局设置", command=open_init_dialog, width=18)
    init_btn.pack(side="left")
    init_btn.pack(side="left", padx=(0, 0))

    exit_btn = ttk.Button(hotkey_row_frame, text="× 一键关掉本工具", command=exit_program, width=18)
    exit_btn.pack(side="left")

    def update_tray_btn_state():
        if tray_icon_var.get():
            tray_settings_btn.config(state="normal")
        else:
            tray_settings_btn.config(state="disabled")

    def on_tray_changed():
        update_tray_btn_state()
        config["tray_icon"] = tray_icon_var.get()
        save_config()
        if config["tray_icon"]:
            create_tray_icon()
        else:
            destroy_tray_icon()

    # 同步托盘菜单中的随机壁纸与右键菜单的随机开关
    def sync_tray_random_with_ctx():
        tray_items = config.get("tray_menu_items", [])
        ctx_random_enabled = config.get("ctx_random_wallpaper", False)
        need_update = False

        if ctx_random_enabled:
            if "random" not in tray_items:
                if "next" in tray_items:
                    next_idx = tray_items.index("next")
                    tray_items.insert(next_idx + 1, "random")
                else:
                    tray_items.append("random")
                config["tray_menu_items"] = tray_items
                save_config()
                need_update = True
        else:
            if "random" in tray_items:
                tray_items.remove("random")
                config["tray_menu_items"] = tray_items
                save_config()
                need_update = True

        # 如果托盘图标存在且需要更新菜单，则直接更新菜单，不销毁重建
        if need_update and tray_icon_obj is not None:
            try:
                import pystray
                # 复用创建托盘图标时的菜单构建逻辑（简化版）
                action_to_label = {
                    "show": "打开设置主界面",
                    "previous": "上一张壁纸",
                    "next": "下一张壁纸",
                    "random": "随机壁纸",
                    "about": "关于作者",
                    "jump": "跳转到壁纸",
                    "exit": "退出程序"
                }
                def get_hotkey_suffix(action):
                    if action == "exit":
                        return "\t&E"
                    if action == "about":
                        return "\t&A"
                    action_to_key = {
                        "previous": "previous",
                        "next": "next",
                        "random": "random",
                        "show": "show",
                        "jump": "jump"
                    }
                    key_name = action_to_key.get(action, "")
                    if key_name:
                        hotkey = config.get(f"hotkey_{key_name}", "")
                        if hotkey:
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
                                    formatted.append(p.capitalize() if len(p) == 1 else p)
                            return "\t" + "+".join(formatted)
                    return ""
                new_menu_items = []
                for action in tray_items:
                    label = action_to_label.get(action, action)
                    hotkey_suffix = get_hotkey_suffix(action)
                    display_label = label + hotkey_suffix if hotkey_suffix else label
                    if action == "about":
                        new_menu_items.append(pystray.MenuItem(display_label, lambda: show_about_window()))
                    elif action == "exit":
                        def do_exit():
                            stop_video_wallpaper()
                            import os as os_module
                            os_module._exit(0)
                        new_menu_items.append(pystray.MenuItem(display_label, do_exit))
                    elif action == "jump":
                        new_menu_items.append(pystray.MenuItem(display_label, lambda: handle_tray_action("jump")))
                    else:
                        new_menu_items.append(pystray.MenuItem(display_label, (lambda a=action: handle_tray_action(a))))
                tray_icon_obj.menu = pystray.Menu(*new_menu_items)
                log("托盘菜单已动态更新")
            except Exception as e:
                log(f"更新托盘菜单失败: {e}")

    # 修改 toggle_ctx_random 函数，在切换时同步托盘菜单
    original_toggle_ctx_random = toggle_ctx_random

    def new_toggle_ctx_random():
        original_toggle_ctx_random()

        # 延迟一下再同步，让配置先保存完成，并且确保在同一个线程中重建托盘图标
        def do_sync():
            try:
                # 同步托盘菜单
                sync_tray_random_with_ctx()
                # 强制刷新右键菜单注册（确保生效）
                register_context()
            except Exception as e:
                log(f"同步托盘菜单失败: {e}")

        root.after(200, do_sync)

    # 替换全局函数
    globals()['toggle_ctx_random'] = new_toggle_ctx_random
    # 同时，程序启动时也执行一次同步
    root.after(500, lambda: sync_tray_random_with_ctx())

    chk_tray.config(command=on_tray_changed)
    update_tray_btn_state()

    def on_background_changed():
        config["run_in_background"] = run_in_background_var.get()
        save_config()
        if run_in_background_var.get() and not tray_icon_var.get():
            response = tk.messagebox.askyesno(
                "是否使用建议？",
                "電籽建议您开启后台运行后同时将系统托盘图标开启，\n"
                "这样您即使关闭了程序窗口，也依然能通过托盘图标打开程序\n\n"
                "是否自动开启系统托盘图标？",
                parent=root
            )
            if response:
                tray_icon_var.set(True)
                config["tray_icon"] = True
                save_config()
                update_tray_btn_state()
                chk_tray.state(['selected'])

    # 重新绑定 chk_background 的真实命令
    chk_background.config(command=on_background_changed)

    # ========== 开机自启动功能 ==========
    def get_startup_folder_path():
        """获取当前用户的启动文件夹路径"""
        try:
            import ctypes.wintypes
            CSIDL_STARTUP = 7
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_STARTUP, None, 0, buf)
            return buf.value
        except Exception as e:
            log(f"获取启动文件夹失败: {e}")
            return os.path.join(os.environ.get('APPDATA', ''),
                                r'Microsoft\Windows\Start Menu\Programs\Startup')

    def set_auto_start(enable):
        """设置开机自启动（使用启动文件夹 + VBS脚本，动态生成正确路径，ANSI编码）"""
        if IS_MACOS:
            agents_dir = os.path.expanduser("~/Library/LaunchAgents")
            plist_path = os.path.join(agents_dir, "com.xxdz.shangbackground.plist")
            if enable:
                try:
                    os.makedirs(agents_dir, exist_ok=True)
                    plist = {
                        "Label": "com.xxdz.shangbackground",
                        "ProgramArguments": get_app_command(
                            hidden=True,
                            script_path=os.path.abspath(__file__),
                            frozen=is_frozen(),
                        ),
                        "RunAtLoad": True,
                        "WorkingDirectory": BASE_DIR,
                    }
                    with open(plist_path, "wb") as f:
                        plistlib.dump(plist, f)
                    subprocess.run(["launchctl", "unload", plist_path], capture_output=True, timeout=5)
                    subprocess.run(["launchctl", "load", plist_path], capture_output=True, timeout=5)
                    log(f"macOS 开机自启动已启用: {plist_path}")
                except Exception as e:
                    log(f"设置 macOS 开机自启动失败: {e}")
                    show_message("错误", f"设置 macOS 开机自启动失败: {e}")
            else:
                try:
                    subprocess.run(["launchctl", "unload", plist_path], capture_output=True, timeout=5)
                    if os.path.exists(plist_path):
                        os.remove(plist_path)
                    log("macOS 开机自启动已禁用")
                except Exception as e:
                    log(f"禁用 macOS 开机自启动失败: {e}")
            return

        startup_folder = get_startup_folder_path()
        vbs_name = "PowerOn.vbs"
        vbs_path = os.path.join(startup_folder, vbs_name)

        # 获取当前 exe 的完整路径（编译后是 .exe，开发时是 .py）
        if is_frozen():
            exe_full_path = sys.executable
        else:
            # 开发环境：使用 pythonw.exe 运行 main.py
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if os.path.exists(pythonw):
                exe_full_path = pythonw
            else:
                exe_full_path = sys.executable

        if enable:
            # 启用开机自启动：动态生成 VBS 文件到启动文件夹
            try:
                # 转义反斜杠为双反斜杠（VBS 中需要）
                escaped_exe_path = exe_full_path.replace('\\', '\\\\')

                # 获取当前脚本所在目录（用于开发模式）
                script_dir = os.path.dirname(os.path.abspath(__file__)).replace('\\', '\\\\')

                # 动态生成 VBS 内容（简化版，更可靠）
                vbs_content = []
                vbs_content.append(
                    "'此文件仅用做开机自启动xxdz_上一个桌面背景！\tpy哔哩哔哩_小小电子xxdz   UID:3461569935575626")
                vbs_content.append("' PowerOn.vbs - 开机自启动时创建标志文件，然后启动主程序")
                vbs_content.append("")
                vbs_content.append("' 创建标志文件（写入 \"T\" 表示需要无窗口启动）")
                vbs_content.append("Dim flagFile")
                vbs_content.append(
                    "flagFile = CreateObject(\"WScript.Shell\").ExpandEnvironmentStrings(\"%TEMP%\") & \"\\WallpaperHideFlag.tmp\"")
                vbs_content.append("")
                vbs_content.append("Dim objFSO")
                vbs_content.append("Set objFSO = CreateObject(\"Scripting.FileSystemObject\")")
                vbs_content.append("")
                vbs_content.append("Dim objFile")
                vbs_content.append("Set objFile = objFSO.CreateTextFile(flagFile, True)")
                vbs_content.append("objFile.Write \"T\"")
                vbs_content.append("objFile.Close")
                vbs_content.append("")
                vbs_content.append("' 直接启动主程序")
                vbs_content.append("Dim exePath")
                vbs_content.append("exePath = \"" + escaped_exe_path + "\"")
                vbs_content.append("")
                vbs_content.append("' 检查文件是否存在")
                vbs_content.append("If objFSO.FileExists(exePath) Then")
                vbs_content.append("    CreateObject(\"WScript.Shell\").Run \"\"\"\" & exePath & \"\"\"\", 1, False")
                vbs_content.append("Else")
                vbs_content.append("    MsgBox \"找不到主程序: \" & exePath, 16, \"启动失败\"")
                vbs_content.append("End If")
                vbs_content.append("")
                vbs_content.append("Set objFile = Nothing")
                vbs_content.append("Set objFSO = Nothing")

                vbs_string = '\r\n'.join(vbs_content)

                # 使用 ANSI 编码写入（VBS 默认使用 ANSI）
                with open(vbs_path, 'w', encoding='gb2312') as f:
                    f.write(vbs_string)
                log(f"已动态生成 VBS 到启动文件夹: {vbs_path}")
                log(f"VBS 中的 exe 路径: {exe_full_path}")

                log("开机自启动已启用（使用启动文件夹 + 动态生成 VBS）")
            except Exception as e:
                log(f"生成 VBS 到启动文件夹失败: {e}")
                show_message("错误", f"设置开机自启动失败: {e}\\n请检查是否有权限写入启动文件夹")
        else:
            # 禁用开机自启动：删除启动文件夹中的 VBS 文件
            try:
                if os.path.exists(vbs_path):
                    os.remove(vbs_path)
                    log(f"已删除启动文件夹中的 VBS: {vbs_path}")
                log("开机自启动已禁用（已删除启动文件夹中的文件）")
            except Exception as e:
                log(f"删除启动文件夹中的 VBS 失败: {e}")

    def toggle_auto_start():
        """切换开机自启动状态"""
        enable = auto_start_var.get()
        set_auto_start(enable)
        config["auto_start"] = enable
        save_config()

    def sync_auto_start_config():
        """同步配置与启动文件夹中的VBS文件状态（不再使用注册表）"""
        if IS_MACOS:
            plist_path = os.path.expanduser("~/Library/LaunchAgents/com.xxdz.shangbackground.plist")
            exists = os.path.exists(plist_path)
            if auto_start_var is not None:
                auto_start_var.set(exists)
            if config.get("auto_start", False) != exists:
                config["auto_start"] = exists
                save_config()
            log(f"同步 macOS 开机自启动状态: plist存在={exists}")
            return
        try:
            import ctypes.wintypes
            CSIDL_STARTUP = 7
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_STARTUP, None, 0, buf)
            startup_folder = buf.value
            vbs_path = os.path.join(startup_folder, "PowerOn.vbs")
            vbs_exists = os.path.exists(vbs_path)

            # 根据VBS文件是否存在来更新复选框
            if auto_start_var is not None:
                auto_start_var.set(vbs_exists)

            # 同步配置中的 auto_start 值
            if config.get("auto_start", False) != vbs_exists:
                config["auto_start"] = vbs_exists
                save_config()
                log(f"同步开机自启动状态: VBS文件存在={vbs_exists}, 已更新配置")
            else:
                log(f"同步开机自启动状态: VBS文件存在={vbs_exists}, 配置中auto_start={config.get('auto_start', False)}")
        except Exception as e:
            log(f"同步开机自启动状态失败: {e}")

    sync_auto_start_config()

    settings_frame = ttk.Frame(main_container, width=500)
    settings_frame.pack(side="right", fill="both", expand=True)
    settings_frame.pack_propagate(False)
    mode_frame = ttk.Frame(settings_frame)
    mode_frame.pack(fill="x", pady=(10, 16))
    ttk.Label(mode_frame, text="背景模式", font=(FONT_FAMILY, 12)).pack(anchor="w", pady=(0, 6))
    mode_var = tk.StringVar(value=config["mode"])
    mode_combo = ttk.Combobox(mode_frame, textvariable=mode_var, values=["幻灯片放映", "图片", "视频", "纯色", "渐变"],
                              state="readonly", width=22)
    mode_combo.pack(anchor="w")
    dynamic_frame = ttk.Frame(settings_frame)
    dynamic_frame.pack(fill="both", expand=True)
    slide_frame = ttk.Frame(dynamic_frame)
    ttk.Label(slide_frame, text="幻灯片设置", font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", pady=(0, 10))
    folder_frame = ttk.Frame(slide_frame)
    folder_frame.pack(fill="x", pady=5)
    ttk.Label(folder_frame, text="壁纸相册:", width=8).pack(side="left")
    folder_var = tk.StringVar()
    if config.get("slide_folder"):
        folder_var.set(config["slide_folder"])
    else:
        folder_var.set("")
    recent_folders = config.get("recent_folders", [])
    if config["slide_folder"] and config["slide_folder"] not in recent_folders:
        recent_folders.insert(0, config["slide_folder"])
        recent_folders = recent_folders[:10]
        config["recent_folders"] = recent_folders
        save_config()
    folder_combo = ttk.Combobox(folder_frame, width=25, state="readonly")
    folder_combo.pack(side="left", padx=5)

    def update_folder_combo():
        values = []
        display_values = []
        if config.get("recent_folders"):
            for folder_path in config["recent_folders"][:10]:
                if os.path.isdir(folder_path):
                    values.append(folder_path)
                    display_values.append(os.path.basename(folder_path))
        if config.get("slide_folder") and os.path.isdir(config["slide_folder"]):
            if config["slide_folder"] not in values:
                values.insert(0, config["slide_folder"])
                display_values.insert(0, os.path.basename(config["slide_folder"]))
        folder_combo['values'] = display_values
        folder_combo.full_paths = values
        if config.get("slide_folder") and os.path.isdir(config["slide_folder"]):
            folder_combo.set(os.path.basename(config["slide_folder"]))
            log(f"update_folder_combo: 已设置下拉菜单为 {os.path.basename(config['slide_folder'])}")
        else:
            folder_combo.set("")
            log("update_folder_combo: 下拉菜单已清空")

    update_folder_combo()
    if config["slide_folder"]:
        folder_combo.set(os.path.basename(config["slide_folder"]))

    def on_folder_selected(event):
        selected_index = folder_combo.current()
        if selected_index >= 0 and hasattr(folder_combo, 'full_paths'):
            selected_path = folder_combo.full_paths[selected_index]
            if selected_path and os.path.isdir(selected_path):
                # 清理旧文件夹的副本
                old_folder = config.get("slide_folder", "")
                if old_folder and os.path.isdir(old_folder) and old_folder != selected_path:
                    random_copy.cleanup_folder(old_folder)
                config["slide_folder"] = selected_path
                recent = config.get("recent_folders", [])
                if selected_path in recent:
                    recent.remove(selected_path)
                recent.insert(0, selected_path)
                config["recent_folders"] = recent[:10]
                save_config()
                if config["mode"] == "幻灯片放映":
                    restart_slideshow()
                update_wallpaper_preview()
                update_open_folder_btn_state()

    folder_combo.bind("<<ComboboxSelected>>", on_folder_selected)

    def browse_and_add():
        d = filedialog.askdirectory()
        if d:
            config["slide_folder"] = d
            recent = config.get("recent_folders", [])
            if d in recent:
                recent.remove(d)
            recent.insert(0, d)
            config["recent_folders"] = recent[:10]
            save_config()
            update_folder_combo()
            folder_combo.set(os.path.basename(d))
            if config["mode"] == "幻灯片放映":
                restart_slideshow()
            update_wallpaper_preview()
            update_open_folder_btn_state()

    ttk.Button(folder_frame, text="浏览", command=browse_and_add, width=6).pack(side="left")
    open_folder_btn = ttk.Button(folder_frame, text="打开文件夹", width=10, state="disabled")
    open_folder_btn.pack(side="left", padx=5)

    def update_open_folder_btn_state():
        if config.get("slide_folder") and os.path.isdir(config["slide_folder"]):
            open_folder_btn.config(state="normal")
        else:
            open_folder_btn.config(state="disabled")

    def open_current_folder():
        folder_path = config.get("slide_folder")
        if folder_path and os.path.isdir(folder_path):
            os.startfile(folder_path)

    open_folder_btn.config(command=open_current_folder)
    update_open_folder_btn_state()
    preview_images_frame = ttk.Frame(slide_frame)
    preview_images_frame.pack(fill="x", pady=5)
    wallpaper_preview_labels = []
    update_wallpaper_preview()
    interval_frame = ttk.Frame(slide_frame)
    interval_frame.pack(fill="x", pady=5)
    ttk.Label(interval_frame, text="切换间隔:", width=8).pack(side="left")
    freq_map = {"自定义时间": None, "5秒": 5, "10秒": 10, "30秒": 30, "1分钟": 60, "5分钟": 300, "30分钟": 1800,
                "1小时": 3600,
                "6小时": 21600, "12小时": 43200, "1天": 86400, "2天": 172800, "1周": 604800,
                "1个月": 2592000, "6个月": 15552000, "1年": 31536000, "50年": 1576800000,
                "666年": 210000000}
    # 自定义下拉菜单顺序，让"自定义时间"排在第一位
    freq_values = ["自定义时间", "5秒", "10秒", "30秒", "1分钟", "5分钟", "30分钟", "1小时",
                   "6小时", "12小时", "1天", "2天", "1周", "1个月", "6个月", "1年", "50年", "666年"]
    freq_combo = ttk.Combobox(interval_frame, values=freq_values, state="readonly", width=15)
    freq_combo.config(height=18)  # 显示18项，这样所有选项都能看到，不需要滚动
    freq_combo.pack(side="left", padx=5)

    # 手动档复选框
    manual_mode_var = tk.BooleanVar(value=config.get("manual_mode", False))

    def toggle_manual_mode():
        is_manual = manual_mode_var.get()
        config["manual_mode"] = is_manual

        folder = config.get("slide_folder", "")

        if is_manual:
            # 手动档开启：停止幻灯片，禁用下拉菜单
            # 使用全局的 stop_slideshow 函数
            try:
                stop_slideshow()
            except NameError:
                # 如果找不到，尝试使用 globals()
                globals().get('stop_slideshow', lambda: None)()
            freq_combo.config(state="disabled")

            # 删除所有副本文件（保留配置），但不改变随机顺序的开关状态
            if folder and os.path.isdir(folder):
                random_copy.cleanup_physical_only(folder)
                log("[手动档] 已删除所有随机概率副本文件（配置已保留，随机顺序开关状态未变）")

            # 根据随机顺序状态决定概率按钮状态
            if config.get("shuffle", False):
                # 随机顺序开启，但手动档开启时没有副本，所以按钮应该禁用（因为此时设置概率无意义）
                try:
                    prob_btn.config(state="disabled")
                except:
                    pass
            else:
                try:
                    prob_btn.config(state="disabled")
                except:
                    pass
        else:
            # 手动档关闭：启用下拉菜单
            freq_combo.config(state="readonly")

            # 如果随机顺序是开启的，恢复副本文件（与 on_shuffle_changed 逻辑一致）
            if config.get("shuffle", False):
                log(f"[手动档] 关闭手动档，随机顺序为开启状态，开始恢复副本文件")
                if folder and os.path.isdir(folder):
                    # 先清理旧副本（仅物理）
                    random_copy.cleanup_physical_only(folder)
                    log("[手动档] 已清理旧副本（仅物理文件）")
                    # 从 random.json 恢复权重
                    random_copy.restore_weights(folder)
                    log("[手动档] 已调用 restore_weights")
                    # 验证副本是否创建成功
                    after_files = os.listdir(folder)
                    copy_files = [f for f in after_files if f.startswith(random_copy.COPY_PREFIX)]
                    log(f"[手动档] 恢复后副本文件数: {len(copy_files)}")
                    # 启用设置随机概率按钮
                    try:
                        prob_btn.config(state="normal")
                    except:
                        pass
                else:
                    log("[手动档] 文件夹无效, 跳过恢复")
            else:
                log("[手动档] 关闭手动档，随机顺序为关闭状态，无需恢复副本")
                # 确保设置随机概率按钮是禁用的
                try:
                    prob_btn.config(state="disabled")
                except:
                    pass

            # 重启幻灯片
            if config["mode"] == "幻灯片放映" and folder:
                start_slideshow()

        save_config()
        register_context()  # 刷新右键菜单（随机菜单状态可能变化）

    manual_check = ttk.Checkbutton(interval_frame, text="手动档", variable=manual_mode_var, command=toggle_manual_mode)
    manual_check.pack(side="left", padx=10)

    for k, v in freq_map.items():
        if v is not None and v == config["slide_seconds"]:
            freq_combo.set(k)
    # 如果当前配置的时间不在预设中，显示为自定义
    current_seconds = config["slide_seconds"]
    if current_seconds not in [v for v in freq_map.values() if v is not None]:
        freq_combo.set("自定义时间")

    # 根据手动档状态初始化下拉菜单状态
    if config.get("manual_mode", False):
        freq_combo.config(state="disabled")
    else:
        freq_combo.config(state="readonly")

    def open_custom_time_dialog():
        """打开自定义时间输入对话框"""
        dialog = tk.Toplevel(root)
        dialog.title("自定义切换间隔")
        dialog.resizable(False, False)
        dialog.transient(root)
        dialog.grab_set()

        # 窗口居中
        dialog.update_idletasks()
        w, h = 320, 180
        x = (dialog.winfo_screenwidth() - w) // 2
        y = (dialog.winfo_screenheight() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.configure(bg="#ffffff")

        # 设置窗口图标
        icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
        if os.path.exists(icon_path):
            try:
                dialog.iconbitmap(icon_path)
            except:
                pass

        main_frame = tk.Frame(dialog, bg="#ffffff", padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text="输入时间数值:", font=(FONT_FAMILY, 10), bg="#ffffff").pack(anchor="w")
        value_frame = tk.Frame(main_frame, bg="#ffffff")
        value_frame.pack(fill="x", pady=(5, 10))

        time_value = tk.StringVar(value="1")
        value_entry = tk.Entry(value_frame, textvariable=time_value, width=10, font=(FONT_FAMILY, 10))
        value_entry.pack(side="left", padx=(0, 10))

        unit_map = {"秒": 1, "分钟": 60, "小时": 3600, "天": 86400, "周": 604800, "年": 31536000}
        unit_var = tk.StringVar(value="分钟")
        unit_combo = ttk.Combobox(value_frame, textvariable=unit_var, values=list(unit_map.keys()), state="readonly",
                                  width=8)
        unit_combo.pack(side="left")

        # 自动选中输入框内容
        value_entry.focus_set()
        value_entry.select_range(0, tk.END)

        error_label = tk.Label(main_frame, text="", fg="red", bg="#ffffff", font=(FONT_FAMILY, 8))
        error_label.pack(pady=(0, 10))

        def confirm():
            try:
                val = float(time_value.get().strip())
                if val <= 0:
                    error_label.config(text="请输入大于0的数字")
                    return
                unit = unit_var.get()
                multiplier = unit_map[unit]
                total_seconds = int(val * multiplier)
                if total_seconds < 1:
                    total_seconds = 1
                config["slide_seconds"] = total_seconds
                save_config()
                # 更新下拉框显示
                freq_combo.set("自定义时间")
                reset_slide_timer()
                dialog.destroy()
            except ValueError:
                error_label.config(text="请输入有效的数字")

        def on_enter(event):
            confirm()

        value_entry.bind("<Return>", on_enter)

        btn_frame = tk.Frame(main_frame, bg="#ffffff")
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="确定", command=confirm, width=10).pack(side="right", padx=(5, 0))
        ttk.Button(btn_frame, text="取消", command=dialog.destroy, width=10).pack(side="right")

    def freq_change(evt):
        # 手动档开启时不允许修改间隔
        if config.get("manual_mode", False):
            return
        selected = freq_combo.get()
        if selected == "自定义时间":
            open_custom_time_dialog()
        else:
            new_seconds = freq_map[selected]
            config["slide_seconds"] = new_seconds
            save_config()
            reset_slide_timer()

    freq_combo.bind("<<ComboboxSelected>>", freq_change)
    # 随机顺序和随机概率按钮放在同一行
    random_row = ttk.Frame(slide_frame)
    random_row.pack(anchor="w", pady=5)

    shuffle_var = tk.BooleanVar(value=config["shuffle"])
    shuffle_check = ttk.Checkbutton(random_row, text="随机顺序", variable=shuffle_var)
    shuffle_check.pack(side="left")
    shuffle_check.config(command=on_shuffle_changed)

    # 创建一个自定义样式，让按钮更瘪
    style = ttk.Style()
    style.configure("Flat.TButton", padding=(0, 0))
    prob_btn = ttk.Button(random_row, text="设置随机概率",
                          command=lambda: random_copy.open_random_probability_window(root,
                                                                                     config.get("slide_folder", "")),
                          width=15, style="Flat.TButton")
    prob_btn.pack(side="left", padx=(10, 0))

    fit_frame_slide = ttk.Frame(slide_frame)
    fit_frame_slide.pack(fill="x", pady=2)
    ttk.Label(fit_frame_slide, text="适应模式:", width=8).pack(side="left")
    fit_var = tk.StringVar(value=config["fit_mode"])
    fit_combo = ttk.Combobox(fit_frame_slide, textvariable=fit_var, values=["填充", "适应", "拉伸", "平铺", "居中"],
                             state="readonly", width=15)
    fit_combo.pack(side="left", padx=5)

    def fit_change(evt):
        config["fit_mode"] = fit_var.get()
        save_config()
        set_fit_mode(fit_var.get())

    fit_combo.bind("<<ComboboxSelected>>", fit_change)
    single_frame = ttk.Frame(dynamic_frame)
    ttk.Label(single_frame, text="图片设置", font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", pady=(0, 10))
    image_frame = ttk.Frame(single_frame)
    image_frame.pack(fill="x", pady=5)
    ttk.Label(image_frame, text="图片文件:", width=8).pack(side="left")
    single_entry = ttk.Entry(image_frame, width=25)
    single_entry.pack(side="left", padx=5)
    if config.get("single_image"):
        single_entry.insert(0, os.path.basename(config["single_image"]))

    def browse_single():
        f = ask_image_file(root)
        if f:
            config["single_image"] = f
            single_entry.delete(0, "end")
            single_entry.insert(0, os.path.basename(f))
            save_config()
            set_fit_mode(fit_var.get())
            set_wallpaper(f, "手动选择")

    ttk.Button(image_frame, text="浏览", command=browse_single, width=6).pack(side="left")
    single_fit_frame = ttk.Frame(single_frame)
    single_fit_frame.pack(fill="x", pady=5)
    ttk.Label(single_fit_frame, text="适应模式:", width=8).pack(side="left")
    fit_combo_s = ttk.Combobox(single_fit_frame, textvariable=fit_var, values=["填充", "适应", "拉伸", "平铺", "居中"],
                               state="readonly", width=10)
    fit_combo_s.pack(side="left", padx=5)
    fit_combo_s.bind("<<ComboboxSelected>>", fit_change)
    video_frame = ttk.Frame(dynamic_frame)
    ttk.Label(video_frame, text="视频壁纸设置", font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", pady=(0, 10))
    video_file_frame = ttk.Frame(video_frame)
    video_file_frame.pack(fill="x", pady=5)
    ttk.Label(video_file_frame, text="视频文件:", width=8).pack(side="left")
    video_entry = ttk.Entry(video_file_frame, width=25)
    video_entry.pack(side="left", padx=5)
    if config.get("video_file"):
        video_entry.insert(0, os.path.basename(config["video_file"]))

    def browse_video():
        f = ask_video_file(root)
        if f:
            config["video_file"] = f
            video_entry.delete(0, "end")
            video_entry.insert(0, os.path.basename(f))
            save_config()
            if config["mode"] == "视频":
                apply_video_wallpaper()

    def stop_video_from_ui():
        stop_video_wallpaper()
        log("视频壁纸已停止")

    video_button_frame = ttk.Frame(video_frame)
    video_button_frame.pack(fill="x", pady=5)
    ttk.Button(video_file_frame, text="浏览", command=browse_video, width=6).pack(side="left")
    ttk.Button(video_button_frame, text="播放视频壁纸", command=apply_video_wallpaper, width=14).pack(side="left")
    ttk.Button(video_button_frame, text="停止视频壁纸", command=stop_video_from_ui, width=14).pack(side="left", padx=8)
    ttk.Label(video_frame, text="macOS 会使用独立桌面层级视频播放器，窗口不接收鼠标事件。", foreground="#666").pack(anchor="w", pady=(8, 0))
    gradient_frame = ttk.Frame(dynamic_frame)
    ttk.Label(gradient_frame, text="渐变设置", font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", pady=(0, 10))
    color1_frame = ttk.Frame(gradient_frame)
    color1_frame.pack(fill="x", pady=5)
    ttk.Label(color1_frame, text="起始颜色:", width=10).pack(side="left")
    color1_var = tk.StringVar(value=config.get("solid_color", "#2d2d2d"))
    color1_entry = ttk.Entry(color1_frame, textvariable=color1_var, width=10)
    color1_entry.pack(side="left", padx=5)
    color1_preview = tk.Frame(color1_frame, width=30, height=25, bg=config.get("solid_color", "#2d2d2d"),
                              relief="sunken", borderwidth=1, cursor="hand2")
    color1_preview.bind("<Button-1>", lambda e: choose_gradient_color1())
    color1_preview.pack(side="left", padx=5)
    color2_frame = ttk.Frame(gradient_frame)
    color2_frame.pack(fill="x", pady=5)
    ttk.Label(color2_frame, text="结束颜色:", width=10).pack(side="left")
    color2_var = tk.StringVar(value=config.get("gradient_color2", "#4a4a4a"))
    color2_entry = ttk.Entry(color2_frame, textvariable=color2_var, width=10)
    color2_entry.pack(side="left", padx=5)
    color2_preview = tk.Frame(color2_frame, width=30, height=25, bg=config.get("gradient_color2", "#4a4a4a"),
                              relief="sunken", borderwidth=1, cursor="hand2")
    color2_preview.bind("<Button-1>", lambda e: choose_gradient_color2())
    color2_preview.pack(side="left", padx=5)
    angle_frame = ttk.Frame(gradient_frame)
    angle_frame.pack(fill="x", pady=5)
    ttk.Label(angle_frame, text="渐变角度:", width=10).pack(side="left")
    angle_var = tk.StringVar(value=str(config.get("gradient_angle", 0)))
    angle_scale = ttk.Scale(angle_frame, from_=0, to=180, orient=tk.HORIZONTAL, length=150,
                            command=on_angle_changed)
    angle_scale.set(config.get("gradient_angle", 0))
    angle_scale.pack(side="left", padx=5, fill="x", expand=True)
    angle_label = ttk.Label(angle_frame, textvariable=angle_var, width=5)
    angle_label.pack(side="left", padx=5)
    ttk.Label(angle_frame, text="度").pack(side="left")
    preset_frame = ttk.Frame(gradient_frame)
    preset_frame.pack(fill="x", pady=10)
    ttk.Label(preset_frame, text="预设渐变:", width=10).pack(anchor="w")
    gradient_presets = [
        ("#667eea", "#764ba2"), ("#4facfe", "#00f2fe"), ("#f093fb", "#f5576c"),
        ("#43e97b", "#38f9d7"), ("#fa709a", "#fee140"), ("#a18cd1", "#fbc2eb"),
        ("#ff9a9e", "#fecfef"), ("#a6c1ee", "#fbc2eb"), ("#fbc2eb", "#a6c1ee"),
        ("#84fab0", "#8fd3f4"), ("#ffecd2", "#fcb69f"), ("#c2e9fb", "#a1c4fd"),
        ("#ffe259", "#ffa751"), ("#b224ef", "#7579ff")
    ]
    gradient_container = ttk.Frame(preset_frame)
    gradient_container.pack(fill="x", pady=5)
    for idx, (c1, c2) in enumerate(gradient_presets):
        create_gradient_button(gradient_container, c1, c2, idx // 7, idx % 7,
                               lambda a=c1, b=c2: set_preset_gradient(a, b))
    solid_frame = ttk.Frame(dynamic_frame)
    ttk.Label(solid_frame, text="纯色设置", font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", pady=(0, 10))
    solid_color_frame = ttk.Frame(solid_frame)
    solid_color_frame.pack(fill="x", pady=5)
    ttk.Label(solid_color_frame, text="颜色:", width=8).pack(side="left")
    solid_color_var = tk.StringVar(value=config.get("solid_color", "#2d2d2d"))
    solid_color_entry = ttk.Entry(solid_color_frame, textvariable=solid_color_var, width=10)
    solid_color_entry.pack(side="left", padx=5)
    solid_color_preview = tk.Frame(solid_color_frame, width=30, height=25, bg=config.get("solid_color", "#2d2d2d"),
                                   relief="sunken", borderwidth=1, cursor="hand2")
    solid_color_preview.bind("<Button-1>", lambda e: choose_solid_color())
    solid_color_preview.pack(side="left", padx=5)

    def choose_solid_color():
        color = colorchooser.askcolor(color=config.get("solid_color", "#2d2d2d"))
        if color:
            set_preset_solid(color[1])

    preset_solid_frame = ttk.Frame(solid_frame)
    preset_solid_frame.pack(fill="x", pady=10)
    ttk.Label(preset_solid_frame, text="预设颜色:", width=8).pack(anchor="w")
    solid_presets = ["#667eea", "#764ba2", "#4facfe", "#f093fb", "#43e97b", "#fa709a", "#a18cd1",
                     "#fbc2eb", "#84fab0", "#ffecd2", "#a6c1ee", "#ff9a9e", "#ffe259", "#b224ef"]
    solid_container = ttk.Frame(preset_solid_frame)
    solid_container.pack(fill="x", pady=5)
    for idx, color in enumerate(solid_presets):
        create_color_button(solid_container, color, idx // 7, idx % 7, lambda c=color: set_preset_solid(c))
    extra_frame = ttk.Frame(settings_frame)
    extra_frame.pack(fill="x", pady=(0, 0))
    ttk.Label(extra_frame, text="右键菜单设置", font=(FONT_FAMILY, 12, "bold")).pack(anchor="w", pady=(0, 0))

    # 辅助函数：获取快捷键显示文本（用于界面显示）
    def get_hotkey_display_text(key_name, default_key=None):
        hotkey = config.get(f"hotkey_{key_name}", "")
        if hotkey:
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
                    formatted.append(p.capitalize() if len(p) == 1 else p)
            return "+".join(formatted)
        elif default_key:
            return default_key.upper()
        return ""

    # 更新右键菜单复选框文本（当快捷键改变时调用）
    def update_ctx_checkbutton_texts():
        global chk_prev, chk_next, chk_random, chk_jump, chk_personalize
        # 获取各菜单的快捷键
        prev_hotkey = get_hotkey_display_text("previous", "U")
        next_hotkey = get_hotkey_display_text("next", "N")
        random_hotkey = get_hotkey_display_text("random", "3")
        jump_hotkey = get_hotkey_display_text("jump", "V")
        personalize_hotkey = get_hotkey_display_text("show", "X")

        # 更新复选框文本
        chk_prev.config(text=f"添加【桌面右键 → 上一个桌面背景】\t(快捷键{prev_hotkey})")
        chk_next.config(text=f"添加【桌面右键 → 下一个桌面背景】\t(快捷键{next_hotkey})")
        chk_random.config(text=f"添加【桌面右键 → 随机一个桌面背景】\t(快捷键{random_hotkey})")
        chk_jump.config(text=f"添加【桌面右键 → 跳转到壁纸】\t(快捷键{jump_hotkey})")
        chk_personalize.config(text=f"添加【桌面右键 → 个性化设置】\t(快捷键{personalize_hotkey})")

    # 创建右键菜单复选框
    ctx_prev_var = tk.BooleanVar(value=config.get("ctx_last_wallpaper", False))
    global chk_prev
    chk_prev = ttk.Checkbutton(extra_frame, text="", variable=ctx_prev_var, command=toggle_ctx_prev)
    chk_prev.pack(anchor="w", pady=0)
    if config["mode"] != "幻灯片放映":
        chk_prev.config(state="disabled")

    ctx_next_var = tk.BooleanVar(value=config.get("ctx_next_wallpaper", True))
    chk_next = ttk.Checkbutton(extra_frame, text="", variable=ctx_next_var, command=toggle_ctx_next)
    chk_next.pack(anchor="w", pady=0)

    ctx_random_var = tk.BooleanVar(value=config.get("ctx_random_wallpaper", False))
    chk_random = ttk.Checkbutton(extra_frame, text="", variable=ctx_random_var, command=toggle_ctx_random)
    chk_random.pack(anchor="w", pady=0)

    ctx_jump_var = tk.BooleanVar(value=config.get("ctx_jump_to_wallpaper", False))
    global chk_jump
    chk_jump = ttk.Checkbutton(extra_frame, text="", variable=ctx_jump_var, command=toggle_ctx_jump)
    chk_jump.pack(anchor="w", pady=0)

    ctx_personalize_var = tk.BooleanVar(value=config.get("ctx_personalize", True))
    global chk_personalize
    chk_personalize = ttk.Checkbutton(extra_frame, text="", variable=ctx_personalize_var,
                                      command=toggle_ctx_personalize)
    chk_personalize.pack(anchor="w", pady=0)

    # 初始化复选框文本
    update_ctx_checkbutton_texts()

    def message_loop():
        msg = ctypes.wintypes.MSG()
        while True:
            ret = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret <= 0:
                break
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

    def on_closing():
        """关闭窗口时的行为"""
        global root, tray_icon_obj

        # 如果开启了后台运行，则仅隐藏窗口，不退出程序
        if config.get("run_in_background", True):
            log("后台运行模式：窗口隐藏到托盘")
            root.withdraw()  # 隐藏窗口
            # 确保托盘图标存在
            if not config.get("tray_icon", False):
                # 如果托盘图标/菜单栏未开启，自动开启
                config["tray_icon"] = True
                save_config()
                root.after(100, create_tray_icon)
        else:
            # 未开启后台运行，则完全退出程序
            log("程序关闭（非后台模式）")
            global apply_timer, wallpaper_monitor_running, slide_timer, transition_in_progress

            # 先停止所有定时器和线程，避免在退出时还在运行
            log("停止幻灯片定时器...")
            if slide_timer:
                try:
                    if root is not None and isinstance(slide_timer, str):
                        root.after_cancel(slide_timer)
                    else:
                        slide_timer.cancel()
                except:
                    pass
            if apply_timer:
                try:
                    apply_timer.cancel()
                except:
                    pass

            # 停止过渡动画
            transition_in_progress = False

            # 停止壁纸监控线程
            log("停止壁纸监控...")
            wallpaper_monitor_running = False
            time.sleep(0.1)  # 给线程一点时间退出

            # 停止幻灯片
            stop_slideshow()
            stop_video_wallpaper()

            # 清理触发文件
            for f in [TRIGGER_FILE_PREV, TRIGGER_FILE_NEXT, TRIGGER_FILE_RANDOM]:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass

            # 清理过渡动画临时文件夹（但如果有未完成的动画状态，不要清理）
            if not os.path.exists(TRANSITION_LOG_PATH):
                temp_dir = os.path.join(BASE_DIR, "GuoduTemp")
                if os.path.exists(temp_dir):
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    except:
                        pass
            else:
                log("检测到未完成的过渡动画，保留临时文件以便下次恢复")

            # 取消全局快捷键
            try:
                unregister_global_hotkeys()
            except:
                pass

            # 销毁托盘图标（如果存在）
            if tray_icon_obj:
                try:
                    tray_icon_obj.stop()
                except:
                    pass
                tray_icon_obj = None

            # 销毁消息窗口
            if hwnd:
                try:
                    ctypes.windll.user32.DestroyWindow(hwnd)
                except:
                    pass

            # 退出程序
            try:
                root.quit()
                root.destroy()
            except:
                pass

            # 强制退出进程（避免卡死）
            import sys
            import os as os_module
            os_module._exit(0)

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # 如果配置开启托盘，启动时创建
    if config.get("tray_icon", False):
        root.after(100, create_tray_icon)

    mode_combo.bind("<<ComboboxSelected>>", lambda e: on_mode_changed())

    def on_solid_color_change(*args):
        color = solid_color_var.get()
        if color.startswith("#") and len(color) == 7:
            solid_color_preview.config(bg=color)
            config["solid_color"] = color
            save_config()
            if config["mode"] == "纯色":
                preview_solid()
                apply_solid()

    def on_gradient_color1_change(*args):
        color = color1_var.get()
        if color.startswith("#") and len(color) == 7:
            color1_preview.config(bg=color)
            config["solid_color"] = color
            save_config()
            if config["mode"] == "渐变":
                preview_gradient()
                apply_gradient()

    def on_gradient_color2_change(*args):
        color = color2_var.get()
        if color.startswith("#") and len(color) == 7:
            color2_preview.config(bg=color)
            config["gradient_color2"] = color
            save_config()
            if config["mode"] == "渐变":
                preview_gradient()
                apply_gradient()

    solid_color_var.trace("w", on_solid_color_change)
    color1_var.trace("w", on_gradient_color1_change)
    color2_var.trace("w", on_gradient_color2_change)
    msg_hwnd = create_message_window()
    if msg_hwnd:
        msg_thread = threading.Thread(target=message_loop, daemon=True)
        msg_thread.start()
        log("消息循环已启动")
    else:
        log("消息窗口创建失败，将使用纯壁纸切换功能")
    wallpaper_monitor_running = True
    wallpaper_monitor_last = None
    if IS_MACOS:
        root.after(1000, monitor_wallpaper_changes_on_main_thread)
        log("壁纸监控已切换为 macOS 主线程轮询")
        root.after(500, poll_macos_menu_commands)
    else:
        wallpaper_monitor_thread = threading.Thread(target=monitor_wallpaper_changes, daemon=True)
        wallpaper_monitor_thread.start()
        log("壁纸监控线程已启动")
    # 如果是首次使用（没有配置文件或没有设置任何数据），默认开启推荐功能（开机自启动改为询问）
    is_first_time = (not os.path.exists(CONFIG_PATH) or
                     (not config.get("history") and not config.get("slide_folder")))
    if is_first_time:
        # 开启上一个桌面背景右键菜单
        if config["mode"] == "幻灯片放映" and not config.get("ctx_last_wallpaper", False):
            config["ctx_last_wallpaper"] = True
        # 开启个性化设置右键菜单
        if not config.get("ctx_personalize", False):
            config["ctx_personalize"] = True
        # 开启跳转到壁纸右键菜单
        if not config.get("ctx_jump_to_wallpaper", False):
            config["ctx_jump_to_wallpaper"] = True
        # 如果模式为幻灯片放映，开启随机顺序
        if config["mode"] == "幻灯片放映" and not config.get("shuffle", False):
            config["shuffle"] = True
            shuffle_var.set(True)
        # 确保后台运行和托盘图标已开启（默认值已设置）
        save_config()
        log("首次使用，已自动开启推荐功能：上一个桌面背景菜单、个性化菜单、跳转到壁纸菜单、随机顺序、后台运行、托盘图标")

        # 询问用户是否开启开机自启动（仅首次，且未询问过）
        if not config.get("auto_start_prompt_shown", False):
            # 显示自定义风格的开机自启动建议弹窗
            self_root = root  # 捕获当前 root 窗口
            dialog = tk.Toplevel(self_root)
            dialog.title("开机自启动建议")
            dialog.resizable(False, False)
            dialog.transient(self_root)
            dialog.grab_set()

            # 设置窗口图标
            icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
            if os.path.exists(icon_path):
                try:
                    dialog.iconbitmap(icon_path)
                except:
                    pass

            # 计算窗口居中位置
            dialog.update_idletasks()
            dialog_width = 480
            dialog_height = 280
            x = (dialog.winfo_screenwidth() - dialog_width) // 2
            y = (dialog.winfo_screenheight() - dialog_height) // 2
            dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
            dialog.configure(bg="#ffffff")

            # 主框架
            main_frame = tk.Frame(dialog, bg="#ffffff", padx=20, pady=20)
            main_frame.pack(fill="both", expand=True)

            # 图片和标题行（图片在左，文字在右）
            top_row = tk.Frame(main_frame, bg="#ffffff")
            top_row.pack(fill="x", pady=(0, 0))

            # 左侧图片
            hello_img_path = os.path.join(BASE_DIR, "img", "hello.png")
            if os.path.exists(hello_img_path):
                try:
                    hello_img = Image.open(hello_img_path)
                    # 缩放到0.12倍（约96x96）
                    scale = 0.12
                    new_width = int(hello_img.width * scale)
                    new_height = int(hello_img.height * scale)
                    hello_img_resized = hello_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    hello_photo = ImageTk.PhotoImage(hello_img_resized)
                    hello_label = tk.Label(top_row, image=hello_photo, bg="#ffffff")
                    hello_label.image = hello_photo  # 保持引用
                    hello_label.pack(side="left", padx=(0, 10))
                except Exception as e:
                    log(f"加载hello.png失败: {e}")

            # 右侧文字
            desc_label = tk.Label(top_row, text="您是否想要开机自启动本工具？",
                                  font=(FONT_FAMILY, 15, "bold"), bg="#ffffff", fg="#34495e")
            desc_label.pack(side="left")

            # 文本框（紧贴上方，无外边距）
            info_text = tk.Text(main_frame, height=2, wrap="word", font=(FONT_FAMILY, 12),
                                bg="#f8f9fa", relief="flat", borderwidth=1)
            info_text.pack(fill="both", expand=True, pady=(0, 0))
            info_text.insert("1.0",
                             "开机自启动后，软件会后台运行，而且占用资源极少，基本不会影响开机速度\t\tヾ(≧▽≦*)o\n您确定后，此操作可能会被杀毒软件拦截，您可以选择允许或加入白名单。")
            info_text.config(state="disabled")

            # 按钮框架 - 放在右下角
            btn_frame = tk.Frame(main_frame, bg="#ffffff")
            btn_frame.pack(side="bottom", fill="x", pady=(0, 0))

            def on_yes():
                config["auto_start"] = True
                set_auto_start(True)
                auto_start_var.set(True)
                config["auto_start_prompt_shown"] = True
                save_config()
                log("用户同意开机自启动")
                dialog.destroy()

            def on_no():
                # 用户拒绝，不勾选开机自启动，保持未勾选状态
                config["auto_start"] = False
                auto_start_var.set(False)
                config["auto_start_prompt_shown"] = True
                save_config()
                log("用户拒绝开机自启动，不再提醒")
                dialog.destroy()

            # 按钮容器 - 用于右对齐
            button_container = tk.Frame(btn_frame, bg="#ffffff")
            button_container.pack(side="right")

            # 好哒 按钮
            btn_yes = tk.Button(button_container, text="好哒", command=on_yes,
                                bg="#0078D4", fg="#ffffff", font=(FONT_FAMILY, 9),
                                relief="flat", padx=15, pady=5, cursor="hand2")
            btn_yes.pack(side="left", padx=(0, 10))

            # 不，并不再提示 按钮
            btn_no = tk.Button(button_container, text="不，并不再提示", command=on_no,
                               bg="#e0e0e0", fg="#333333", font=(FONT_FAMILY, 9),
                               relief="flat", padx=15, pady=5, cursor="hand2")
            btn_no.pack(side="left")

            # 按钮悬停效果
            def on_enter_yes(e):
                btn_yes.config(bg="#106EBE")

            def on_leave_yes(e):
                btn_yes.config(bg="#0078D4")

            def on_enter_no(e):
                btn_no.config(bg="#d0d0d0")

            def on_leave_no(e):
                btn_no.config(bg="#e0e0e0")

            btn_yes.bind("<Enter>", on_enter_yes)
            btn_yes.bind("<Leave>", on_leave_yes)
            btn_no.bind("<Enter>", on_enter_no)
            btn_no.bind("<Leave>", on_leave_no)

            # 按 ESC 键相当于“否”
            dialog.bind("<Escape>", lambda e: on_no())

            # 等待窗口关闭
            dialog.wait_window()

    register_context()
    on_mode_changed()

    # 更新复选框状态（如果界面已创建）
    try:
        if ctx_prev_var:
            ctx_prev_var.set(config.get("ctx_last_wallpaper", False))
    except:
        pass

    # 智能检测：如果幻灯片模式但没有设置文件夹，尝试使用当前壁纸所在文件夹（在界面创建后）
    # 注意：这个检测必须在 root.mainloop() 之前执行，但要确保界面控件已创建
    if config["mode"] == "幻灯片放映" and not config.get("slide_folder"):
        current_wallpaper = get_current_wallpaper()
        log(f"智能检测: 当前壁纸路径 = {current_wallpaper}")
        if current_wallpaper and os.path.exists(current_wallpaper):
            current_folder = os.path.dirname(current_wallpaper)
            log(f"智能检测: 当前壁纸所在文件夹 = {current_folder}")
            images_in_folder = [f for f in os.listdir(current_folder)
                                if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))]
            if images_in_folder:
                config["slide_folder"] = current_folder
                # 同时添加到最近文件夹列表
                recent = config.get("recent_folders", [])
                if current_folder in recent:
                    recent.remove(current_folder)
                recent.insert(0, current_folder)
                config["recent_folders"] = recent[:10]
                save_config()
                log(f"已设置 slide_folder = {current_folder}")

                # 直接更新下拉菜单（不通过 after，因为现在还在主线程）
                try:
                    # 重新构建下拉菜单
                    values = []
                    display_values = []
                    for folder_path in config.get("recent_folders", [])[:10]:
                        if os.path.isdir(folder_path):
                            values.append(folder_path)
                            display_values.append(os.path.basename(folder_path))
                    if current_folder not in values:
                        values.insert(0, current_folder)
                        display_values.insert(0, os.path.basename(current_folder))
                    folder_combo['values'] = display_values
                    folder_combo.full_paths = values
                    folder_combo.set(os.path.basename(current_folder))
                    log(f"直接更新: 下拉菜单已设置为 {os.path.basename(current_folder)}")
                    # 启用打开文件夹按钮
                    open_folder_btn.config(state="normal")
                    log("直接更新: 打开文件夹按钮已启用")
                    # 刷新预览区
                    update_wallpaper_preview()
                except Exception as e:
                    log(f"直接更新UI失败: {e}")

                    # 如果直接更新失败，延迟重试
                    def retry_update():
                        try:
                            folder_combo['values'] = display_values
                            folder_combo.full_paths = values
                            folder_combo.set(os.path.basename(current_folder))
                            open_folder_btn.config(state="normal")
                            update_wallpaper_preview()
                            log("延迟重试: 更新成功")
                        except Exception as e2:
                            log(f"延迟重试失败: {e2}")

                    root.after(100, retry_update)

                restart_slideshow()
                log(f"启动时自动设置幻灯片文件夹为当前壁纸所在目录: {current_folder}")
            else:
                log(f"当前壁纸文件夹 {current_folder} 中没有图片，无法自动设置")
        else:
            log("无法获取当前壁纸路径，跳过自动设置幻灯片文件夹")
    current = get_current_wallpaper()
    if current and os.path.exists(current):
        config["current_wallpaper"] = current
        update_preview(current)
    else:
        update_preview(None)

    # 初始化全局快捷键（添加详细日志）
    log("[主程序] 准备初始化全局快捷键...")
    try:
        init_global_hotkeys()
        log("[主程序] 全局快捷键初始化完成")
    except Exception as e:
        log(f"[主程序] 全局快捷键初始化失败: {e}")

    # 设置一个定时器，在窗口关闭后强制退出（备用方案）
    def force_exit():
        import sys
        stop_video_wallpaper()
        sys.exit(0)

    # ====================== 版本检查与更新功能 ======================
    # 版本相关变量已移至文件顶部全局区域，这里只需声明 global
    global remote_version, remote_release_notes, remote_download_urls, show_update_flag, check_failed

    def get_remote_version_info():
        """从网络获取版本信息（与Carousel_img.py风格一致）"""
        global remote_version, remote_release_notes, remote_download_urls, show_update_flag
        try:
            bin_id = "69d3940136566621a8833a25"
            master_key = "$2a$10$usS36BdO17gWRxIMd56gjOwrDWBlfrGdsPW1AFFhcp1TBUrbqFg4G"
            url = f"https://api.jsonbin.io/v3/b/{bin_id}"
            headers = {"X-Master-Key": master_key}
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                version_data = data.get('record', data)
                remote_version = version_data.get('version', '1')
                remote_release_notes = version_data.get('releaseNotes', '暂无更新说明喵')
                remote_download_urls = {
                    "123云盘": version_data.get('download1', ''),
                    "111网盘": version_data.get('download2', ''),
                    "夸克网盘": version_data.get('download3', '')
                }
                if remote_version != '1':
                    show_update_flag = True
                    log(f"发现新版本: v{remote_version}.0")
                else:
                    show_update_flag = False
                    log("当前已是最新版本")
            else:
                log(f"获取版本信息失败: HTTP {response.status_code}")
                show_update_flag = False
        except Exception as e:
            log(f"获取版本信息失败: {e}")
            show_update_flag = False
        return show_update_flag

    def show_update_prompt():
        """显示更新提示弹窗（使用 Tkinter 自定义对话框）"""
        log("=== 显示更新提示弹窗 ===")
        log(f"remote_version: {remote_version}")
        log(f"show_update_flag: {show_update_flag}")
        # 创建自定义对话框
        dialog = tk.Toplevel(root)
        dialog.title("软件更新提示")
        dialog.resizable(False, False)
        dialog.transient(root)
        dialog.grab_set()

        # 设置窗口图标
        icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
        if os.path.exists(icon_path):
            try:
                dialog.iconbitmap(icon_path)
            except:
                pass

        # 计算窗口居中位置
        dialog.update_idletasks()
        dialog_width = 480
        dialog_height = 300
        x = (dialog.winfo_screenwidth() - dialog_width) // 2
        y = (dialog.winfo_screenheight() - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        dialog.configure(bg="#ffffff")

        # 主框架
        main_frame = tk.Frame(dialog, bg="#ffffff", padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        # 标题（新版本）
        title_label = tk.Label(main_frame, text=f"✨ 发现新版本 v{remote_version}.0！",
                               font=(FONT_FAMILY, 14, "bold"), bg="#ffffff", fg="#2c3e50")
        title_label.pack(anchor="w", pady=(0, 10))

        # 图片和标题行（图片在左，文字在右）
        top_row = tk.Frame(main_frame, bg="#ffffff")
        top_row.pack(fill="x", pady=(0, 0))

        # 左侧图片
        hello_img_path = os.path.join(BASE_DIR, "img", "hello.png")
        if os.path.exists(hello_img_path):
            try:
                hello_img = Image.open(hello_img_path)
                # 缩放到0.12倍（约96x96）
                scale = 0.12
                new_width = int(hello_img.width * scale)
                new_height = int(hello_img.height * scale)
                hello_img_resized = hello_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                hello_photo = ImageTk.PhotoImage(hello_img_resized)
                hello_label = tk.Label(top_row, image=hello_photo, bg="#ffffff")
                hello_label.image = hello_photo  # 保持引用
                hello_label.pack(side="left", padx=(0, 10))
            except Exception as e:
                log(f"加载hello.png失败: {e}")

        # 右侧文字
        content_label = tk.Label(top_row, text="更新内容：",
                                 font=(FONT_FAMILY, 15, "bold"), bg="#ffffff", fg="#34495e")
        content_label.pack(side="left")

        # 更新内容文本框（紧贴上方，无外边距）
        notes_text = tk.Text(main_frame, height=4, wrap="word", font=(FONT_FAMILY, 10),
                             bg="#f8f9fa", relief="flat", borderwidth=1)
        notes_text.pack(fill="both", expand=True, pady=(0, 0))
        notes_text.insert("1.0", remote_release_notes)
        notes_text.config(state="disabled")

        # 按钮框架 - 放在右下角
        btn_frame = tk.Frame(main_frame, bg="#ffffff")
        btn_frame.pack(side="bottom", fill="x", pady=(0, 0))

        # 按钮点击处理
        def on_update():
            dialog.destroy()
            log("用户选择立即更新")
            show_update_window()

        def on_later():
            dialog.destroy()
            log("用户选择稍后提醒")

        def on_ignore():
            dialog.destroy()
            config["ignored_version"] = remote_version
            save_config()
            log(f"用户选择忽略版本 {remote_version}")
            # 更新版本标签
            if hasattr(root, 'version_label') and root.version_label is not None:
                root.version_label.config(text="[版本] v1.0 忽略了更新", fg="#50A14F", cursor="")
                root.version_label.unbind("<Button-1>")
                root.version_label.bind("<Button-1>", lambda e: messagebox.showinfo("我の版本信息  OwO",
                                                                                    f"当前版本: v1.0\n最新版本: {remote_version}\n{remote_release_notes}"))
            messagebox.showinfo("忽略!", f"已忽略版本v {remote_version}.0 的更新,这个选择真明智（？）。。", parent=root)

        # 按钮容器 - 用于右对齐
        button_container = tk.Frame(btn_frame, bg="#ffffff")
        button_container.pack(side="right")

        # 立即更新按钮
        btn_update = tk.Button(button_container, text="立即更新", command=on_update,
                               bg="#0078D4", fg="#ffffff", font=(FONT_FAMILY, 9),
                               relief="flat", padx=15, pady=5, cursor="hand2")
        btn_update.pack(side="left", padx=(0, 10))

        # 稍后提醒按钮
        btn_later = tk.Button(button_container, text="稍后提醒", command=on_later,
                              bg="#e0e0e0", fg="#333333", font=(FONT_FAMILY, 9),
                              relief="flat", padx=15, pady=5, cursor="hand2")
        btn_later.pack(side="left", padx=(0, 10))

        # 忽略本次更新并不再提醒按钮
        btn_ignore = tk.Button(button_container, text="忽略本次更新并不再提醒", command=on_ignore,
                               bg="#ffffff", fg="#888888", font=(FONT_FAMILY, 9),
                               relief="solid", borderwidth=1, padx=15, pady=5, cursor="hand2")
        btn_ignore.pack(side="left")

        # 按钮悬停效果
        def on_enter_update(e):
            btn_update.config(bg="#106EBE")

        def on_leave_update(e):
            btn_update.config(bg="#0078D4")

        def on_enter_later(e):
            btn_later.config(bg="#d0d0d0")

        def on_leave_later(e):
            btn_later.config(bg="#e0e0e0")

        def on_enter_ignore(e):
            btn_ignore.config(bg="#f0f0f0")

        def on_leave_ignore(e):
            btn_ignore.config(bg="#ffffff")

        btn_update.bind("<Enter>", on_enter_update)
        btn_update.bind("<Leave>", on_leave_update)
        btn_later.bind("<Enter>", on_enter_later)
        btn_later.bind("<Leave>", on_leave_later)
        btn_ignore.bind("<Enter>", on_enter_ignore)
        btn_ignore.bind("<Leave>", on_leave_ignore)

        # 按 ESC 键关闭（相当于稍后提醒）
        dialog.bind("<Escape>", lambda e: on_later())

        # 等待窗口关闭
        dialog.wait_window()

    def show_update_window():
        """显示更新窗口（与Carousel_img.py的_create_update_window风格一致）"""
        try:
            root.after(0, _create_update_window)
        except Exception as e:
            log(f"创建更新窗口失败: {e}")

    def _create_update_window():
        """在主线程中创建更新窗口（现代化 Windows 原生 UI）"""
        update_win = tk.Toplevel(root)
        update_win.title("软件更新")
        width, height = 500, 380
        x = (update_win.winfo_screenwidth() - width) // 2
        y = (update_win.winfo_screenheight() - height) // 2
        update_win.geometry(f"{width}x{height}+{x}+{y}")
        update_win.resizable(False, False)
        # 设置窗口图标
        icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
        if os.path.exists(icon_path):
            try:
                update_win.iconbitmap(icon_path)
            except:
                pass
        # 使用 ttk 主题（vista 风格）
        style = ttk.Style()
        setup_modern_style(style)
        update_win.configure(bg="#f0f0f0")

        # 主框架
        main_frame = ttk.Frame(update_win, padding="20 15 20 15")
        main_frame.pack(fill="both", expand=True)

        # 标题区域
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill="x", pady=(0, 15))
        version_label = ttk.Label(title_frame, text=f"✨ 发现新版本 v{remote_version}.0",
                                  font=("Segoe UI", 14, "bold"))
        version_label.pack(side="left")

        # 更新内容区域
        notes_frame = ttk.LabelFrame(main_frame, text="更新内容", padding="10 5")
        notes_frame.pack(fill="both", expand=True, pady=(0, 15))

        notes_text = tk.Text(notes_frame, wrap="word", font=("Segoe UI", 10),
                             bg="#ffffff", relief="flat", borderwidth=0, height=5)
        notes_text.pack(fill="both", expand=True)
        notes_text.insert("1.0", remote_release_notes)
        notes_text.config(state="disabled")

        # 下载线路区域
        download_frame = ttk.LabelFrame(main_frame, text="下载线路", padding="10 5")
        download_frame.pack(fill="x", pady=(0, 15))

        urls = remote_download_urls
        btn_container = ttk.Frame(download_frame)
        btn_container.pack(fill="x", pady=5)

        import webbrowser
        def make_download_callback(url):
            return lambda: webbrowser.open(url)

        # 线路顺序：夸克、123、111（推荐夸克放最前）
        order = [("夸克网盘", "夸克网盘线路", True), ("123云盘", "123云盘线路", False),
                 ("111网盘", "111网盘线路", False)]
        for key, text, recommend in order:
            if urls.get(key) and urls[key]:
                btn = ttk.Button(btn_container, text=text, command=make_download_callback(urls[key]))
                btn.pack(side="left", padx=5, expand=True, fill="x")

        # 推荐说明（恢复原始文案）
        tip_label = ttk.Label(download_frame,
                              text="夸克已与本阿婆主合作，推荐用夸克线路哈，\n文件不大不会限啥速，毕竟为爱发电嘛",
                              font=("Segoe UI", 8), foreground="#4B8FE0")
        tip_label.pack(pady=(5, 0))

        # 底部按钮区域
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill="x", pady=(5, 0))

        def ignore_this_version():
            config["ignored_version"] = remote_version
            save_config()
            log(f"用户选择忽略版本 {remote_version}")
            update_win.destroy()
            if hasattr(root, 'version_label') and root.version_label is not None:
                root.version_label.config(text="[版本] v1.0 忽略了更新", fg="#50A14F", cursor="")
                root.version_label.unbind("<Button-1>")
                root.version_label.bind("<Button-1>", lambda e: messagebox.showinfo("我の版本信息  OwO",
                                                                                    f"当前版本: v1.0\n最新版本: {remote_version}\n{remote_release_notes}"))
            messagebox.showinfo("忽略！", f"已忽略版本v {remote_version} .0 的更新,这个选择真明智（？）。。", parent=root)

        ignore_btn = ttk.Button(bottom_frame, text="忽略本次更新", command=ignore_this_version)
        ignore_btn.pack(side="left", padx=(0, 10))

        close_btn = ttk.Button(bottom_frame, text="关闭", command=update_win.destroy)
        close_btn.pack(side="right")

        # 可选：为强调按钮添加样式（蓝色）
        style.configure("Accent.TButton", foreground="#ffffff", background="#0078D4")
        style.map("Accent.TButton",
                  background=[("active", "#106EBE"), ("pressed", "#005A9E")])

    # ====================== 右下角精灵图按钮 ======================
    class SpriteButton:
        """精灵图按钮 - 支持普通、悬浮、按下三态渐变混合"""

        def __init__(self, parent, image_path, frame_width, frame_height, frames=3, size=50):
            self.parent = parent
            self.frame_width = frame_width
            self.frame_height = frame_height
            self.frames = frames
            self.size = size
            self.current_state = 0  # 0:普通, 1:悬浮, 2:按下
            self.animation_id = None

            # 加载并缩放精灵图，保存 PIL Image 对象用于混合
            original_img = Image.open(image_path).convert("RGBA")
            self.state_pil = []  # 存储 PIL Image 对象
            self.state_photos = []  # 存储对应的 PhotoImage 对象
            for i in range(frames):
                frame = original_img.crop((0, i * frame_height, frame_width, (i + 1) * frame_height))
                scaled = frame.resize((size, size), Image.Resampling.LANCZOS)
                self.state_pil.append(scaled)
                self.state_photos.append(ImageTk.PhotoImage(scaled))

            # 创建按钮 Canvas
            self.canvas = tk.Canvas(parent, width=size, height=size, highlightthickness=0, bd=0, bg='white')
            self.canvas.create_image(0, 0, anchor='nw', image=self.state_photos[0])
            self.canvas.image = self.state_photos[0]

            # 绑定事件
            self.canvas.bind("<Enter>", self.on_enter)
            self.canvas.bind("<Leave>", self.on_leave)
            self.canvas.bind("<ButtonPress-1>", self.on_press)
            self.canvas.bind("<ButtonRelease-1>", self.on_release)

            # 放置到右下角
            self.canvas.place(relx=1.0, rely=1.0, x=-10, y=5, anchor='se')

        def _crossfade(self, target_state):
            """渐变混合动画"""
            if self.animation_id:
                self.parent.after_cancel(self.animation_id)

            start_pil = self.state_pil[self.current_state]
            target_pil = self.state_pil[target_state]

            steps = 10
            step = 0

            def animate():
                nonlocal step
                if step <= steps:
                    t = step / steps
                    blended = Image.blend(start_pil, target_pil, t)
                    blended_photo = ImageTk.PhotoImage(blended)
                    self.canvas.itemconfig(1, image=blended_photo)
                    self.canvas.image = blended_photo
                    step += 1
                    self.animation_id = self.parent.after(20, animate)
                else:
                    self.canvas.itemconfig(1, image=self.state_photos[target_state])
                    self.canvas.image = self.state_photos[target_state]
                    self.current_state = target_state
                    self.animation_id = None

            animate()

        def on_enter(self, event):
            self._crossfade(1)

        def on_leave(self, event):
            self._crossfade(0)

        def on_press(self, event):
            self._crossfade(2)

        def on_release(self, event):
            self._crossfade(1)

    # ====================== 工具提示函数（与Carousel_img.py同风格） ======================
    tip_window = None

    def show_sprite_tooltip(event):
        """显示精灵图工具提示"""
        nonlocal tip_window
        if tip_window:
            return

        x, y = event.x_root + 10, event.y_root + 10
        tip = tk.Toplevel(root)
        tip.wm_overrideredirect(True)
        tip.withdraw()

        label = tk.Label(tip, text="关于 上一个桌面背景", bg="#FFFFE0",
                         relief="solid", borderwidth=1, padx=8, pady=4,
                         font=("Microsoft YaHei", 10))
        label.pack()

        tip.update_idletasks()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        tip_width = tip.winfo_width()
        tip_height = tip.winfo_height()

        if x + tip_width > screen_width:
            x = screen_width - tip_width - 10
        if y + tip_height > screen_height:
            y = screen_height - tip_height - 10

        tip.wm_geometry(f"+{x}+{y}")

        tip_window = tip

        current_y = y - 10
        target_y = y
        tip.deiconify()
        tip.attributes('-alpha', 0.7)

        def animate_slide(step=0):
            nonlocal tip_window
            if step <= 10:
                progress = step / 10
                ease_progress = 1 - (1 - progress) * (1 - progress)
                current_pos_y = current_y + (target_y - current_y) * ease_progress
                current_alpha = 0.7 + 0.3 * ease_progress
                try:
                    tip.wm_geometry(f"+{x}+{int(current_pos_y)}")
                    tip.attributes('-alpha', current_alpha)
                    tip.after(20, lambda: animate_slide(step + 1))
                except:
                    pass

        animate_slide()

    def hide_sprite_tooltip(event):
        """隐藏精灵图工具提示"""
        nonlocal tip_window
        if tip_window:
            tip = tip_window

            def fade_out_animate(step=0):
                nonlocal tip_window
                if step >= 10:
                    try:
                        tip.destroy()
                    except:
                        pass
                    tip_window = None
                    return
                alpha = 1.0 - (step / 10)
                try:
                    tip.attributes('-alpha', alpha)
                    tip.after(15, lambda: fade_out_animate(step + 1))
                except:
                    try:
                        tip.destroy()
                    except:
                        pass
                    tip_window = None

            fade_out_animate()

    # 检查更新（异步，不阻塞界面，使用单独线程）
    # check_failed 已定义为全局变量，此处不再重复定义

    def check_version_in_thread():
        """在后台线程中检查版本"""
        global remote_version, remote_release_notes, remote_download_urls, show_update_flag, check_failed
        try:
            bin_id = "69d3940136566621a8833a25"
            master_key = "$2a$10$usS36BdO17gWRxIMd56gjOwrDWBlfrGdsPW1AFFhcp1TBUrbqFg4G"
            url = f"https://api.jsonbin.io/v3/b/{bin_id}"
            headers = {"X-Master-Key": master_key}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                version_data = data.get('record', data)
                remote_version = version_data.get('version', '1')
                remote_release_notes = version_data.get('releaseNotes', '暂无更新说明喵')
                remote_download_urls = {
                    "123云盘": version_data.get('download1', ''),
                    "111网盘": version_data.get('download2', ''),
                    "夸克网盘": version_data.get('download3', '')
                }
                # 检查是否被用户忽略
                ignored_version = config.get("ignored_version", "")
                if remote_version != '1' and remote_version != ignored_version:
                    show_update_flag = True
                    log(f"发现新版本: v{remote_version}.0")
                else:
                    if remote_version == ignored_version:
                        log(f"版本 {remote_version} 已被用户忽略，跳过提醒")
                    show_update_flag = False
                    log("当前已是最新版本")
                check_failed = False
            else:
                log(f"获取版本信息失败: HTTP {response.status_code}")
                show_update_flag = False
                check_failed = True
        except Exception as e:
            log(f"获取版本信息失败: {e}")
            show_update_flag = False
            check_failed = True

        # 在主线程中更新UI并弹出更新提示
        root.after(0, update_version_label)
        # 如果是后台模式（开机自启），不弹出更新提示窗口
        if show_update_flag and not hide_window:
            root.after(500, show_update_prompt)  # 延迟500ms确保主窗口已完全加载

    def update_version_label():
        """在主线程中更新版本标签UI"""
        # 使用 root.version_label 获取标签引用
        if hasattr(root, 'version_label') and root.version_label is not None:
            try:
                ignored_version = config.get("ignored_version", "")
                if check_failed:
                    root.version_label.config(text="[版本] v1.0 检查失败", fg="#50A14F", cursor="")
                    root.version_label.unbind("<Button-1>")
                    root.version_label.bind("<Button-1>",
                                            lambda e: messagebox.showinfo("啊这",
                                                                          "∑( 口 ||\n\n電籽の网络服务器连接失败，不过习惯就好...这是经常的事\n况且電籽...真的会发布新版本吗？"))
                elif remote_version == ignored_version and remote_version != '1':
                    root.version_label.config(text="[版本] v1.0 忽略了更新", fg="#50A14F", cursor="hand2")
                    root.version_label.unbind("<Button-1>")
                    root.version_label.bind("<Button-1>", lambda e: show_update_window())
                elif show_update_flag:
                    root.version_label.config(text="[版本] v1.0 有新版本!", fg="#ff0000", cursor="hand2")
                    root.version_label.unbind("<Button-1>")
                    root.version_label.bind("<Button-1>", lambda e: show_update_window())
                else:
                    root.version_label.config(text="[版本] v1.0 已是最新版本", fg="#50A14F", cursor="")
                    root.version_label.unbind("<Button-1>")
                    root.version_label.bind("<Button-1>", lambda e: messagebox.showinfo("我の版本信息  OwO",
                                                                                        f"当前版本: v1.0\n最新版本: v{remote_version}.0\n{remote_release_notes}"))
            except Exception as e:
                log(f"更新版本标签失败了: {e}")

    # 启动版本检查（使用单独线程，不阻塞界面）
    version_check_thread = threading.Thread(target=check_version_in_thread, daemon=True)
    version_check_thread.start()

    # 创建右下角按钮
    about_img_path = os.path.join(BASE_DIR, "img", "about.png")
    if os.path.exists(about_img_path):
        try:
            about_btn = SpriteButton(root, about_img_path, 216, 216, frames=3, size=50)
            log("右下角精灵图按钮加载成功")

            # 为精灵图按钮绑定工具提示事件（保留原有动画功能）
            about_btn.canvas.bind("<Enter>", lambda e: (about_btn.on_enter(e), show_sprite_tooltip(e)))
            about_btn.canvas.bind("<Leave>", lambda e: (about_btn.on_leave(e), hide_sprite_tooltip(e)))

            # 绑定点击事件显示关于窗口
            def show_about_window():
                about_img_path = os.path.join(BASE_DIR, "img", "about-window.png")
                if not os.path.exists(about_img_path):
                    messagebox.showerror("错误", "找不到图片文件: about-window.png")
                    return

                # MD5哈希值验证
                import hashlib
                expected_md5 = "227b84cd84f18110a80d323538934e9e"
                with open(about_img_path, "rb") as f:
                    file_md5 = hashlib.md5(f.read()).hexdigest()
                if file_md5 != expected_md5:
                    messagebox.showerror("错误",
                                         "图片文件已损坏或被第三方篡改！为了你我的安全，已隐藏，或请重新下载本软件噢")
                    return

                about_win = tk.Toplevel(root)
                about_win.title("关于 上一个桌面背景")
                about_win.resizable(False, False)
                about_win.transient(root)

                # 加载并缩放图片
                img = Image.open(about_img_path)
                scale = 0.5
                new_width = int(img.width * scale)
                new_height = int(img.height * scale)
                img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img_resized)

                # 创建画布显示图片
                canvas_about = tk.Canvas(about_win, width=new_width, height=new_height, highlightthickness=0)
                canvas_about.pack()
                canvas_about.create_image(0, 0, anchor='nw', image=photo)
                canvas_about.image = photo  # 保持引用

                # 窗口居中后向左偏移 424px，其实就是about-window.png*0.5+悄悄话窗口宽度/2
                about_win.update_idletasks()
                x = (about_win.winfo_screenwidth() - new_width) // 2 - 224  # 可我发现写224才差不多是两个窗口位于居中的位置
                y = (about_win.winfo_screenheight() - new_height) // 2
                about_win.geometry(f"{new_width}x{new_height}+{x}+{y}")

                # 点击任意位置关闭（已禁用，改为按ESC关闭）
                # canvas_about.bind("<Button-1>", lambda e: about_win.destroy())
                about_win.bind("<Escape>", lambda e: about_win.destroy())

                # 设置窗口图标
                icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
                if os.path.exists(icon_path):
                    try:
                        about_win.iconbitmap(icon_path)
                    except:
                        pass

                # ========== 窗口向上滑动动画（从下方50px滑入） ==========
                # 存储变量供动画使用
                anime_current_step = 0
                anime_steps = 15  # 动画帧数
                anime_duration = 250  # 动画总时长250ms
                anime_interval = anime_duration // anime_steps
                text_line1_id = None
                text_line2_id = None
                text_line3_id = None

                # 目标位置
                target_x = x
                target_y = y
                full_width = new_width
                full_height = new_height

                # 起始位置：向下偏移50px
                start_y = y + 50

                # 需要移动的距离（负值表示向上移动）
                y_increment = target_y - start_y  # = -50

                # 设置窗口初始位置在下方50px处
                about_win.geometry(f"{full_width}x{full_height}+{target_x}+{start_y}")
                # 确保窗口可见
                about_win.deiconify()
                about_win.lift()
                about_win.update()

                def slide_up_animation():
                    nonlocal anime_current_step
                    if anime_current_step <= anime_steps:
                        # 缓动曲线：ease-out 先快后慢
                        t = anime_current_step / anime_steps
                        ease_t = 1 - (1 - t) ** 2
                        current_y = start_y + int(y_increment * ease_t)
                        about_win.geometry(f"{full_width}x{full_height}+{target_x}+{current_y}")
                        about_win.update()
                        anime_current_step += 1
                        about_win.after(anime_interval, slide_up_animation)
                    else:
                        # 动画完成，确保最终位置正确
                        about_win.geometry(f"{full_width}x{full_height}+{target_x}+{target_y}")
                        # 动画完成后创建统计文字并获取数据
                        create_stats_and_fetch()

                def create_stats_and_fetch():
                    nonlocal text_line1_id, text_line2_id, text_line3_id
                    # 创建画布文字（位于窗口底部）
                    line_height = 22
                    start_y_pos = full_height - 30

                    text_line1_id = canvas_about.create_text(
                        10,
                        start_y_pos - line_height * 2,
                        anchor="sw",
                        text="正在获取全球用户数...",
                        font=(FONT_FAMILY, 11, "bold"),
                        fill="#0066cc"
                    )
                    text_line2_id = canvas_about.create_text(
                        10,
                        start_y_pos - line_height,
                        anchor="sw",
                        text="正在获取全球使用量...",
                        font=(FONT_FAMILY, 11, "bold"),
                        fill="#0066cc"
                    )
                    text_line3_id = canvas_about.create_text(
                        10,
                        start_y_pos,
                        anchor="sw",
                        text="正在获取今日使用量...",
                        font=(FONT_FAMILY, 11, "bold"),
                        fill="#0066cc"
                    )

                    # 异步获取统计数据
                    import threading
                    import requests

                    def fetch_stats():
                        try:
                            bin_id = "我是马赛克，你的另一个bin_id（版本仓库的）"
                            master_key = "我是马赛克，你的另一个master_key（跟上面那个不一样很正常）"
                            url = f"https://api.jsonbin.io/v3/b/{bin_id}"
                            headers = {"X-Master-Key": master_key}
                            resp = requests.get(url, headers=headers, timeout=10)
                            if resp.status_code == 200:
                                data = resp.json()
                                record = data.get("record", {})
                                total_use = record.get("total_use", 0)
                                total_uses = record.get("total_uses", 0)
                                today = datetime.now().strftime("%Y-%m-%d")
                                daily_uses = record.get("daily_uses", {})
                                today_uses = daily_uses.get(today, 0)
                                line1_text = f"全球用户数：{total_use}人"
                                line2_text = f"全球使用量：{total_uses}次"
                                line3_text = f"全球今日使用量：{today_uses}次"
                            else:
                                line1_text = "获取统计数据失败"
                                line2_text = ""
                                line3_text = ""
                        except Exception as e:
                            log(f"获取统计数据失败: {e}")
                            line1_text = "获取统计数据失败"
                            line2_text = ""
                            line3_text = ""

                        def update_text():
                            try:
                                if text_line1_id:
                                    canvas_about.itemconfig(text_line1_id, text=line1_text)
                                if text_line2_id:
                                    canvas_about.itemconfig(text_line2_id, text=line2_text)
                                if text_line3_id:
                                    canvas_about.itemconfig(text_line3_id, text=line3_text)
                            except Exception as e:
                                log(f"更新统计文字失败: {e}")

                        about_win.after(0, update_text)

                    from datetime import datetime
                    threading.Thread(target=fetch_stats, daemon=True).start()

                    # 创建右下角小窗口（Windows原生UI风格）- 使用Frame布局
                    sub_window = tk.Toplevel(about_win)
                    sub_window.title("悄悄话")
                    sub_window.resizable(False, False)
                    sub_window.configure(bg='#18F3D8')
                    # 设置窗口图标
                    icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
                    if os.path.exists(icon_path):
                        try:
                            sub_window.iconbitmap(icon_path)
                        except:
                            pass

                    # 定义打开链接的函数
                    import webbrowser
                    def open_url(url):
                        webbrowser.open(url)

                    # 主框架，水平排列
                    main_frame = tk.Frame(sub_window, bg='#ffffff')
                    main_frame.pack(fill='both', expand=True)

                    # 左侧彩色矩形（固定宽度142，高度随窗口拉伸）
                    left_frame = tk.Frame(main_frame, bg='#18F3D8', width=50)
                    left_frame.pack(side='left', fill='y')
                    # 防止宽度被压缩
                    left_frame.pack_propagate(False)

                    # 右侧内容框架
                    right_frame = tk.Frame(main_frame, bg='#ffffff', padx=15, pady=15)
                    right_frame.pack(side='left', fill='both', expand=True)

                    # 链接列表
                    links = [
                        ("【B站主页】我是小小电子xxdz，欢迎来关注我~", "https://space.bilibili.com/3461569935575626"),
                        ("【发布视频】啊？你真的舍得给我三连喵？",
                         "https://xxdz-official.github.io/ShangBackground/gotoBV.html"),  # 为了方便发布，这里使用一个跳转页
                        ("【我の官网】https://xxdz-official.github.io/x", "https://xxdz-official.github.io/x"),
                        ("【项目官网】这是“上一个桌面背景”的项目主页", "https://xxdz-official.github.io/ShangBackground"),
                        ("【友情链接】展示为我助力的朋友们~", "https://xxdz-official.github.io/x/FriendURL.html"),
                        ("【开源仓库】能加个星标，加个关注喵？QwQ", "https://github.com/xxdz-Official/ShangBackground"),
                        (
                        "【前往论坛】为术力口 furry 极客圈搭建的专属论坛：Miku66ccff", "https://miku66ccff.freeflarum.com")
                    ]

                    for text, url in links:
                        # 分割【】内的文字和其他文字
                        if "】" in text:
                            bracket_part = text.split("】")[0] + "】"
                            rest_part = text.split("】")[1]
                            # 哔哩哔哩粉 #FE7398，哔哩哔哩蓝 #0098FF
                            label_frame = tk.Frame(right_frame, bg='#ffffff')
                            label_frame.pack(anchor="w", pady=3)
                            pink_label = tk.Label(label_frame, text=bracket_part, font=("Segoe UI", 10), fg="#FE7398",
                                                  bg='#ffffff', cursor="hand2")
                            pink_label.pack(side="left")
                            blue_label = tk.Label(label_frame, text=rest_part, font=("Segoe UI", 10), fg="#0098FF",
                                                  bg='#ffffff', cursor="hand2")
                            blue_label.pack(side="left")
                            # 绑定点击事件
                            pink_label.bind("<Button-1>", lambda e, u=url: open_url(u))
                            blue_label.bind("<Button-1>", lambda e, u=url: open_url(u))
                        else:
                            link_label = tk.Label(right_frame, text=text, font=("Segoe UI", 10), fg="#0098FF",
                                                  bg='#ffffff', cursor="hand2", anchor="w")
                            link_label.pack(anchor="w", pady=3)
                            link_label.bind("<Button-1>", lambda e, u=url: open_url(u))

                    # 更新窗口大小以适应内容
                    sub_window.update_idletasks()
                    window_width = right_frame.winfo_reqwidth() + 50
                    window_height = right_frame.winfo_reqheight() + 0

                    # 设置位置：关于窗口的右下角紧贴小窗口左下角
                    about_win.update_idletasks()
                    about_x = about_win.winfo_x()
                    about_y = about_win.winfo_y()
                    about_width = about_win.winfo_width()
                    about_height = about_win.winfo_height()
                    sub_x = about_x + about_width
                    sub_y = about_y + about_height - window_height
                    sub_window.geometry(f"{window_width}x{window_height}+{sub_x}+{sub_y}")

                    # 小窗口跟随关于窗口移动
                    def update_sub_window_position():
                        try:
                            if sub_window.winfo_exists() and about_win.winfo_exists():
                                new_about_x = about_win.winfo_x()
                                new_about_y = about_win.winfo_y()
                                new_about_width = about_win.winfo_width()
                                new_about_height = about_win.winfo_height()
                                new_sub_x = new_about_x + new_about_width
                                new_sub_y = new_about_y + new_about_height - window_height
                                sub_window.geometry(f"{window_width}x{window_height}+{new_sub_x}+{new_sub_y}")
                                about_win.after(100, update_sub_window_position)
                            else:
                                try:
                                    sub_window.destroy()
                                except:
                                    pass
                        except:
                            pass

                    update_sub_window_position()

                    # 关于窗口关闭时同时关闭小窗口
                    def on_about_close():
                        try:
                            sub_window.destroy()
                        except:
                            pass
                        about_win.destroy()

                    about_win.protocol("WM_DELETE_WINDOW", on_about_close)

                # 开始向上滑动动画
                about_win.after(30, slide_up_animation)

            about_btn.canvas.bind("<ButtonRelease-1>", lambda e: (about_btn.on_release(e), show_about_window()))

            # 版本标签（位于施舍标签上方）—— 初始显示“检查更新捏...”
            root.version_label = tk.Label(
                root,
                text="[版本] v1.0 检查更新捏...",
                fg="#50A14F",
                bg=root.cget("bg"),
                font=(FONT_FAMILY, 9),
                cursor=""
            )
            # 临时绑定点击事件：显示正在检查
            root.version_label.bind("<Button-1>", lambda e: messagebox.showinfo("唉？！",
                                                                                "∑( 口 ||\n\n别着急呐~\n正在连接服务器检查更新捏，请稍后..."))

            # 施舍标签（位于電籽标签上方）
            donation_label = tk.Label(
                root,
                text="[施舍] 为爱发电的项目",
                fg="#FE7398",  # 哔哩哔哩粉
                bg=root.cget("bg"),
                font=(FONT_FAMILY, 9),
                cursor="hand2"
            )
            donation_label.bind("<Button-1>", lambda e: shishe.show_donation_window(root, BASE_DIR))

            # 添加電籽小字（紧贴按钮左侧）
            author_label = tk.Label(
                root,
                text="[作者] B站_小小电子xxdz",
                fg="#0098FF",
                bg=root.cget("bg"),
                font=(FONT_FAMILY, 9),
                cursor="hand2"
            )
            author_label.bind("<Button-1>",
                              lambda e: __import__('webbrowser').open("https://space.bilibili.com/3461569935575626"))

            # 刷新壁纸相册下拉菜单和打开文件夹按钮状态
            def refresh_folder_combo_and_btn():
                try:
                    # 刷新下拉菜单
                    folder = config.get("slide_folder", "")
                    if folder and os.path.isdir(folder):
                        # 更新最近文件夹列表
                        recent = config.get("recent_folders", [])
                        if folder in recent:
                            recent.remove(folder)
                        recent.insert(0, folder)
                        config["recent_folders"] = recent[:10]
                        save_config()
                        # 更新下拉菜单显示
                        values = []
                        display_values = []
                        for folder_path in config.get("recent_folders", [])[:10]:
                            if os.path.isdir(folder_path):
                                values.append(folder_path)
                                display_values.append(os.path.basename(folder_path))
                        if folder not in values:
                            values.insert(0, folder)
                            display_values.insert(0, os.path.basename(folder))
                        folder_combo['values'] = display_values
                        folder_combo.full_paths = values
                        folder_combo.set(os.path.basename(folder))
                    # 刷新打开文件夹按钮状态
                    update_open_folder_btn_state()
                except Exception as e:
                    log(f"刷新文件夹下拉菜单失败: {e}")

            # 执行一次刷新
            refresh_folder_combo_and_btn()

            def place_labels():
                left_edge_x = -205
                # 電籽标签最下方，依次向上排列
                author_label.place(relx=1.0, rely=1.0, x=left_edge_x, y=5, anchor='sw')
                donation_label.place(relx=1.0, rely=1.0, x=left_edge_x, y=5 - 19, anchor='sw')
                root.version_label.place(relx=1.0, rely=1.0, x=left_edge_x, y=5 - 38, anchor='sw')

            root.after(10, place_labels)

        except Exception as e:
            log(f"加载右下角按钮失败: {e}")

    # 如果是一次性任务（hide_window=True 且有 pending_action），在初始化完成后执行壁纸切换
    if hide_window and pending_action:
        log("执行延迟的一次性任务")
        if pending_action == "previous":
            previous_wallpaper()
        elif pending_action == "next":
            next_wallpaper()
        elif pending_action == "random":
            random_wallpaper()
        # 清空 pending_action 避免重复执行
        pending_action = None

    # 当 Tkinter 主循环结束时，立即退出
    root.mainloop()
    # 如果主循环异常退出，强制结束进程
    force_exit()


if __name__ == "__main__":
    main()
