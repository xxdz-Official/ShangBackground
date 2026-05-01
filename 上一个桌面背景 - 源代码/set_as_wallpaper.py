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
import psutil
import traceback
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "shezhi.json")
DIY_DIR = os.path.join(BASE_DIR, "diy")
DIY_JSON = os.path.join(DIY_DIR, "DIY.json")
TEMP_FILE = os.path.join(BASE_DIR, "temp_wallpaper_selection.json")
LOG_FILE = os.path.join(os.path.expanduser("~"), "Desktop", "wallpaper_rightclick_debug.log")

def log_debug(msg):
    """写入调试日志到桌面"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {msg}\n")
        print(msg)
    except:
        print(msg)

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config):
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
    ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)

def kill_all_main_processes():
    """结束所有主程序进程（温和终止，给过渡动画保存时间）"""
    log_debug("开始结束旧进程...")
    current_pid = os.getpid()
    killed = []
    for proc in psutil.process_iter(['pid', 'cmdline', 'name']):
        try:
            if proc.info['pid'] == current_pid:
                continue
            cmdline = proc.info['cmdline']
            if cmdline and ('main.py' in str(cmdline) or 'pythonw.exe' in str(proc.info['name']).lower()):
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
            except:
                pass
    log_debug("结束旧进程完成")

def start_main_program():
    """启动主程序（使用 pythonw 隐藏控制台）"""
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    main_script = os.path.join(BASE_DIR, "main.py")
    log_debug(f"启动新进程: {pythonw} {main_script}")
    subprocess.Popen([pythonw, main_script], creationflags=subprocess.CREATE_NO_WINDOW)

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

    # 防止多次执行（多选时可能触发多次）
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

    ctypes.windll.user32.MessageBoxW(0, "壁纸设置成功！\n程序将自动重启应用新设置。", "提示", 0)
    log_debug("右键菜单脚本执行完成")
    log_debug("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_debug(f"执行出错: {e}")
        log_debug(traceback.format_exc())