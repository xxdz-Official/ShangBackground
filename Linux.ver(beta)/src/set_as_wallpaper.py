"""
设置壁纸右键菜单处理脚本
支持单文件和多文件选择，通过临时文件传递参数
"""
import sys
import os
import json
import ctypes
import shutil
import time
import subprocess
try:
    import psutil
except ImportError:
    psutil = None
import traceback
from datetime import datetime
import tempfile

try:
    from app_config import APP_NAME, IS_WINDOWS, IS_MACOS, IS_LINUX
except Exception:
    APP_NAME = "ShangBackground"
    IS_WINDOWS = sys.platform.startswith("win")
    IS_MACOS = sys.platform == "darwin"
    IS_LINUX = sys.platform.startswith("linux")
try:
    from platform_support import set_wallpaper_platform
except Exception:
    set_wallpaper_platform = None

# 是否在 PyInstaller 打包环境中运行
IS_FROZEN = getattr(sys, 'frozen', False)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _user_data_dir():
    if IS_MACOS:
        root = os.path.expanduser("~/Library/Application Support")
        path = os.path.join(root, APP_NAME)
    elif IS_LINUX:
        root = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        path = os.path.join(root, APP_NAME.lower())
    else:
        path = BASE_DIR
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        path = os.path.join(tempfile.gettempdir(), APP_NAME)
        os.makedirs(path, exist_ok=True)
    return path

DATA_DIR = _user_data_dir()
CONFIG_PATH = os.path.join(DATA_DIR, "settings.json")
LEGACY_CONFIG_PATH = os.path.join(DATA_DIR, "shezhi.json")
BUNDLED_CONFIG_PATH = os.path.join(BASE_DIR, "settings.json")
BUNDLED_LEGACY_CONFIG_PATH = os.path.join(BASE_DIR, "shezhi.json")
DIY_DIR = os.path.join(DATA_DIR, "diy")
DIY_JSON = os.path.join(DIY_DIR, "DIY.json")
TEMP_FILE = os.path.join(DATA_DIR, "temp_wallpaper_selection.json")
LOG_FILE = os.path.join(os.path.expanduser("~"), "Desktop", "wallpaper_rightclick_debug.log")
if not os.path.isdir(os.path.dirname(LOG_FILE)):
    LOG_FILE = os.path.join(tempfile.gettempdir(), "wallpaper_rightclick_debug.log")

def log_debug(msg):
    """写入调试日志到桌面"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {msg}\n")
        print(msg)
    except Exception:
        print(msg)

def load_config():
    for path in (CONFIG_PATH, LEGACY_CONFIG_PATH, BUNDLED_CONFIG_PATH, BUNDLED_LEGACY_CONFIG_PATH):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    return {}

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_diy():
    if not os.path.exists(DIY_DIR):
        os.makedirs(DIY_DIR, exist_ok=True)
    if os.path.exists(DIY_JSON):
        with open(DIY_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_diy(diy_list):
    with open(DIY_JSON, 'w', encoding='utf-8') as f:
        json.dump(diy_list, f, ensure_ascii=False, indent=2)

def set_wallpaper(path):
    """设置壁纸；优先使用 platform_support 中已按目标 OS 修复的实现。"""
    if set_wallpaper_platform is not None:
        set_wallpaper_platform(path)
        return

    # 极端情况下 platform_support 导入失败，保留一个最小兜底。
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"壁纸文件不存在: {abs_path}")
    if IS_WINDOWS:
        ok = ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)
        if not ok:
            raise RuntimeError("Windows 壁纸设置失败")
        return
    if IS_MACOS:
        escaped = abs_path.replace("\\", "\\\\").replace('"', '\"')
        subprocess.run(["osascript", "-e", f'tell application "System Events" to set picture of every desktop to POSIX file "{escaped}"'], check=True, timeout=10)
        return
    if IS_LINUX:
        from pathlib import Path
        uri = Path(abs_path).as_uri()
        last_error = None
        for key in ("picture-uri", "picture-uri-dark"):
            try:
                subprocess.run(["gsettings", "set", "org.gnome.desktop.background", key, uri], check=True, timeout=10)
                return
            except Exception as exc:
                last_error = exc
        raise RuntimeError("Linux 壁纸设置失败，请安装 gsettings/feh/pcmanfm 等工具") from last_error
    raise RuntimeError(f"暂不支持当前系统: {sys.platform}")

def kill_all_main_processes():
    """结束所有主程序进程（温和终止，给配置保存时间）"""
    if psutil is None:
        log_debug("未安装 psutil，跳过旧进程清理")
        return
    log_debug("开始结束旧进程...")
    current_pid = os.getpid()
    killed = []
    for proc in psutil.process_iter(['pid', 'cmdline', 'name']):
        try:
            if proc.info['pid'] == current_pid:
                continue
            cmdline = proc.info['cmdline']
            proc_name = (proc.info.get('name') or '').lower()
            if cmdline and 'main.py' in str(cmdline):
                log_debug(f"终止进程: PID={proc.info['pid']}, CMD={cmdline}")
                # 使用 terminate 而不是 kill，让进程有机会保存状态
                proc.terminate()
                killed.append(proc.info['pid'])
        except Exception as e:
            log_debug(f"终止进程出错: {e}")

    if killed:
        log_debug(f"等待 {len(killed)} 个进程退出...")
        time.sleep(2)  # 等待进程保存状态
        for pid in killed:
            try:
                # 如果还没退出，再强制结束
                proc = psutil.Process(pid)
                if proc.is_running():
                    log_debug(f"进程 {pid} 未响应，强制结束")
                    proc.kill()
                else:
                    log_debug(f"进程 {pid} 已正常退出")
            except Exception:
                pass
    log_debug("结束旧进程完成")

def start_main_program():
    """启动主程序（Linux 分支直接使用 python3）。"""
    main_script = os.path.join(BASE_DIR, "main.py")
    log_debug(f"启动新进程: {sys.executable} {main_script}")
    subprocess.Popen([sys.executable, main_script])

def main():
    log_debug("=" * 60)
    log_debug(f"右键菜单脚本启动，时间: {datetime.now()}")
    log_debug(f"命令行参数: {sys.argv}")

    if len(sys.argv) < 2:
        log_debug("参数不足，退出")
        return

    # 收集所有选中的文件
    files = [arg.strip('"') for arg in sys.argv[1:]]
    log_debug(f"原始参数列表: {files}")

    image_ext = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')
    images = [f for f in files if os.path.isfile(f) and os.path.splitext(f)[1].lower() in image_ext]
    log_debug(f"识别到的图片文件: {images}")

    if not images:
        log_debug("没有有效的图片文件，退出")
        return

    # 避免多次执行（多选时可能触发多次）
    if os.path.exists(TEMP_FILE):
        try:
            with open(TEMP_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            if existing.get("timestamp", 0) > time.time() - 2:
                log_debug(f"临时文件存在且时间戳在2秒内，跳过执行: {existing}")
                return
        except Exception as e:
            log_debug(f"检查临时文件出错: {e}")

    config = load_config()
    log_debug(f"当前配置: mode={config.get('mode')}, slide_folder={config.get('slide_folder')}")

    # 先结束旧进程（避免旧进程覆盖新配置）
    kill_all_main_processes()
    time.sleep(0.5)
    log_debug("旧进程已结束")

    if len(images) == 1:
        # 单图片
        img = images[0]
        log_debug(f"单图片模式，图片: {img}")
        set_wallpaper(img)
        config["current_wallpaper"] = img
        hist = config.get("history", [])
        if img in hist:
            hist.remove(img)
        hist.insert(0, img)
        config["history"] = hist[:50]
        config["mode"] = "图片"
        config["single_image"] = img
        save_config(config)
        log_debug("配置已保存（图片模式）")

        diy = load_diy()
        if img not in diy:
            diy.append(img)
            save_diy(diy)
            log_debug(f"已添加到DIY记录: {img}")
    else:
        # 多图片：创建幻灯片相册
        slide_folder = os.path.join(DIY_DIR, f"temp_slide_{int(time.time())}")
        os.makedirs(slide_folder, exist_ok=True)
        log_debug(f"多图片模式，创建幻灯片文件夹: {slide_folder}")

        for src in images:
            dst = os.path.join(slide_folder, os.path.basename(src))
            shutil.copy2(src, dst)
            log_debug(f"复制图片: {src} -> {dst}")

        config["mode"] = "幻灯片放映"
        config["slide_folder"] = slide_folder
        config["shuffle"] = False
        save_config(config)
        log_debug(f"配置已保存（幻灯片模式），文件夹: {slide_folder}")

        diy = load_diy()
        for img in images:
            if img not in diy:
                diy.append(img)
        save_diy(diy)
        log_debug(f"已添加到DIY记录: {len(images)} 张图片")

    # 启动新进程
    start_main_program()
    log_debug("新进程已启动")

    if IS_WINDOWS:
        ctypes.windll.user32.MessageBoxW(0, "壁纸设置成功！\n程序将自动重启应用新设置。", "提示", 0)
    elif IS_MACOS:
        try:
            subprocess.run(
                ["osascript", "-e", 'display dialog "壁纸设置成功！\n程序将自动重启应用新设置。" with title "提示" buttons "OK" default button 1'],
                timeout=10, capture_output=True,
            )
        except Exception:
            pass
    elif IS_LINUX:
        try:
            subprocess.run(
                ["zenity", "--info", "--title=提示", "--text=壁纸设置成功！\n程序将自动重启应用新设置。", "--no-wrap"],
                timeout=10, capture_output=True,
            )
        except Exception:
            pass
    log_debug("右键菜单脚本执行完成")
    log_debug("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_debug(f"执行出错: {e}")
        log_debug(traceback.format_exc())