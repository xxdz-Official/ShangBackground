import ctypes
import os
import subprocess
import sys

from app_config import IS_MACOS, IS_WINDOWS, STYLE_MAP


SPI_GETDESKWALLPAPER = 0x0073


def run_osascript(script):
    result = subprocess.run(
        ["osascript", "-e", script],
        text=True,
        capture_output=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "osascript 执行失败")
    return result.stdout.strip()


def get_screen_size(root=None):
    if IS_WINDOWS:
        try:
            return ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
        except Exception:
            pass
    try:
        if root is not None:
            return root.winfo_screenwidth(), root.winfo_screenheight()
    except Exception:
        pass
    return 1920, 1080


def get_app_command(hidden=False, script_path=None, frozen=False):
    if frozen:
        return [sys.executable] + (["--hide"] if hidden else [])
    script = script_path or os.path.abspath(sys.argv[0])
    return [sys.executable, script] + (["--hide"] if hidden else [])


def quote_applescript_text(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def set_wallpaper_platform(path):
    if IS_WINDOWS:
        ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
        return
    if IS_MACOS:
        escaped = quote_applescript_text(os.path.abspath(path))
        run_osascript(
            f'tell application "System Events" to tell every desktop to set picture to POSIX file "{escaped}"'
        )
        return
    raise RuntimeError(f"暂不支持当前系统: {sys.platform}")


def get_current_wallpaper_platform():
    if IS_WINDOWS:
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, 260, buf, 0)
        return buf.value
    if IS_MACOS:
        return run_osascript('tell application "System Events" to get picture of current desktop')
    return ""


def configure_windows_fit_mode(fit_mode, winreg_module=None, log=None):
    if not IS_WINDOWS or winreg_module is None:
        return
    try:
        key = winreg_module.OpenKey(
            winreg_module.HKEY_CURRENT_USER,
            r"Control Panel\Desktop",
            0,
            winreg_module.KEY_WRITE,
        )
        winreg_module.SetValueEx(key, "WallpaperStyle", 0, winreg_module.REG_SZ, str(STYLE_MAP[fit_mode]))
        winreg_module.SetValueEx(
            key,
            "TileWallpaper",
            0,
            winreg_module.REG_SZ,
            "1" if fit_mode == "平铺" else "0",
        )
        winreg_module.CloseKey(key)
    except Exception as e:
        if log:
            log("设置适应模式失败: " + str(e))
