from __future__ import annotations

import ctypes
import json
import os
# plistlib: lazy-imported inside configure_macos_login_startup (macOS-only)
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from app_config import IS_LINUX, IS_MACOS, IS_WINDOWS, STYLE_MAP, normalize_style_key


SPI_GETDESKWALLPAPER = 0x0073
SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x0001
SPIF_SENDCHANGE = 0x0002


def _run_args(args: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a command without a shell and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return -1, "", str(exc)


def _ensure_existing_file(path: str) -> str:
    """Return an absolute path and fail early with a useful error."""
    abs_path = str(Path(path).expanduser().resolve())
    if not Path(abs_path).is_file():
        raise FileNotFoundError(f"Wallpaper file does not exist: {abs_path}")
    return abs_path


def run_osascript(script: str) -> str:
    rc, out, err = _run_args(["osascript", "-e", script], timeout=10)
    if rc != 0:
        raise RuntimeError(err or "osascript execution failed")
    return out


def _file_uri(path: str) -> str:
    return Path(path).expanduser().resolve().as_uri()


def _path_from_uri(value: str) -> str:
    value = (value or "").strip().strip("'\"")
    if value.startswith("file://"):
        parsed = urlparse(value)
        return unquote(parsed.path)
    return value


def get_screen_size(root=None):
    if IS_WINDOWS:
        try:
            return ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
        except Exception:
            pass
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            screen = app.primaryScreen()
            if screen is not None:
                geo = screen.geometry()
                return geo.width(), geo.height()
    except Exception:
        pass
    if IS_MACOS:
        try:
            out = run_osascript('tell application "Finder" to get bounds of window of desktop')
            parts = [p.strip() for p in out.split(",")]
            if len(parts) >= 4:
                return int(parts[2]), int(parts[3])
        except Exception:
            pass
    if IS_LINUX:
        try:
            rc, out, _ = _run_args(["xrandr", "--current"], timeout=5)
            if rc == 0 and out:
                import re
                for line in out.splitlines():
                    if "*" in line:
                        match = re.search(r"(\d+)x(\d+)", line)
                        if match:
                            return int(match.group(1)), int(match.group(2))
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
    executable = sys.executable
    if IS_WINDOWS:
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(pythonw):
            executable = pythonw
    return [executable, script] + (["--hide"] if hidden else [])


MACOS_LAUNCH_AGENT_LABEL = "com.xxdz.shangbackground"
MACOS_LEGACY_LAUNCH_AGENT_LABELS = ("org.dcstudio.ShangBackground",)


def macos_launch_agents_dir() -> str:
    return os.path.expanduser("~/Library/LaunchAgents")


def macos_launch_agent_path(label: str = MACOS_LAUNCH_AGENT_LABEL) -> str:
    return os.path.join(macos_launch_agents_dir(), f"{label}.plist")


def _run_launchctl_variants(variants: list[list[str]], timeout: int = 8) -> tuple[bool, str]:
    """Try launchctl commands in order; return success and joined diagnostics."""
    diagnostics: list[str] = []
    for args in variants:
        rc, out, err = _run_args(args, timeout=timeout)
        if rc == 0:
            return True, out
        diagnostics.append(f"{' '.join(args)} -> {err or out or f'exit {rc}'}")
    return False, " | ".join(diagnostics)


def _macos_unload_agent(plist_path: str) -> tuple[bool, str]:
    uid = os.getuid() if hasattr(os, "getuid") else None
    variants: list[list[str]] = []
    if uid is not None:
        variants.append(["launchctl", "bootout", f"gui/{uid}", plist_path])
    variants.append(["launchctl", "unload", plist_path])
    return _run_launchctl_variants(variants)


def _macos_load_agent(plist_path: str) -> tuple[bool, str]:
    uid = os.getuid() if hasattr(os, "getuid") else None
    variants: list[list[str]] = []
    if uid is not None:
        variants.append(["launchctl", "bootstrap", f"gui/{uid}", plist_path])
    variants.append(["launchctl", "load", plist_path])
    return _run_launchctl_variants(variants)


def configure_macos_login_startup(
    enable: bool,
    command: list[str],
    working_dir: str,
    label: str = MACOS_LAUNCH_AGENT_LABEL,
    legacy_labels: tuple[str, ...] = MACOS_LEGACY_LAUNCH_AGENT_LABELS,
    log_dir: str | None = None,
) -> str:
    """Create/remove a per-user LaunchAgent for login auto-start on macOS."""
    import plistlib  # stdlib; imported lazily since this function is macOS-only
    if not IS_MACOS:
        raise RuntimeError(f"configure_macos_login_startup called on unsupported platform: {sys.platform}")

    agents_dir = macos_launch_agents_dir()
    plist_path = macos_launch_agent_path(label)
    old_paths = [macos_launch_agent_path(old_label) for old_label in legacy_labels]
    all_paths = [plist_path] + old_paths

    if not enable:
        errors: list[str] = []
        for path in all_paths:
            if os.path.exists(path):
                ok, detail = _macos_unload_agent(path)
                # Not-loaded errors are harmless during disable, but permission/syntax errors are still useful diagnostics.
                if not ok and detail:
                    errors.append(detail)
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
        if errors:
            # Disable should still succeed if files were removed; return details through the exception only when removal failed.
            pass
        return plist_path

    if not command:
        raise ValueError("LaunchAgent ProgramArguments cannot be empty")
    command = [str(part) for part in command]
    if not os.path.isabs(command[0]):
        raise ValueError(f"LaunchAgent executable must be an absolute path: {command[0]}")

    os.makedirs(agents_dir, exist_ok=True)
    if log_dir is None:
        log_dir = os.path.expanduser("~/Library/Logs/ShangBackground")
    os.makedirs(log_dir, exist_ok=True)

    plist = {
        "Label": label,
        "ProgramArguments": command,
        "RunAtLoad": True,
        "WorkingDirectory": working_dir,
        "StandardOutPath": os.path.join(log_dir, "launchagent.out.log"),
        "StandardErrorPath": os.path.join(log_dir, "launchagent.err.log"),
    }
    with open(plist_path, "wb") as f:
        plistlib.dump(plist, f)
    os.chmod(plist_path, 0o600)
    with open(plist_path, "rb") as f:
        plistlib.load(f)

    # Replace any previously loaded job and remove fork/native-app legacy labels to avoid duplicate login starts.
    for path in all_paths:
        if os.path.exists(path):
            _macos_unload_agent(path)
            if path != plist_path:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

    ok, detail = _macos_load_agent(plist_path)
    if not ok:
        raise RuntimeError(detail or "launchctl failed to load LaunchAgent")
    return plist_path



def quote_applescript_text(value: str) -> str:
    """Escape a Python string for a double-quoted AppleScript string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _set_windows_wallpaper(path: str) -> None:
    abs_path = _ensure_existing_file(path)
    ok = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER,
        0,
        abs_path,
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
    )
    if not ok:
        try:
            err = ctypes.windll.kernel32.GetLastError()
        except Exception:
            err = "unknown"
        raise RuntimeError(f"Windows wallpaper change failed, GetLastError={err}")


def _set_macos_wallpaper(path: str) -> None:
    abs_path = _ensure_existing_file(path)
    escaped = quote_applescript_text(abs_path)
    errors = []
    scripts = [
        # System Events supports multiple desktops; this is the preferred path.
        f'tell application "System Events" to set picture of every desktop to POSIX file "{escaped}"',
        # Finder fallback for older or restricted sessions.
        f'tell application "Finder" to set desktop picture to POSIX file "{escaped}"',
    ]
    for script in scripts:
        try:
            run_osascript(script)
            return
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError(
        "macOS wallpaper change failed; grant Automation/System Events permission to the app. "
        + " | ".join(errors)
    )


def _desktop_session_tokens() -> str:
    values = [
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("KDE_FULL_SESSION", ""),
        os.environ.get("WAYLAND_DISPLAY", ""),
    ]
    return " ".join(values).lower()


def _is_kde_session() -> bool:
    tokens = _desktop_session_tokens()
    return "kde" in tokens or "plasma" in tokens


def _set_kde_wallpaper(path: str) -> tuple[bool, str]:
    abs_path = _ensure_existing_file(path)
    uri = _file_uri(abs_path)
    errors: list[str] = []
    # KDE Plasma ships this helper in plasma-workspace; it is the safest first try.
    for candidate in ("plasma-apply-wallpaperimage",):
        if not shutil.which(candidate):
            continue
        rc, out, err = _run_args([candidate, abs_path], timeout=10)
        if rc == 0:
            return True, out
        if err or out:
            errors.append(f"{candidate}: {err or out}")
    # Fallback for Plasma sessions where the helper is missing but qdbus/qdbus6 is available.
    script = """
var allDesktops = desktops();
for (i = 0; i < allDesktops.length; i++) {
    d = allDesktops[i];
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");
    d.writeConfig("Image", %s);
    d.reloadConfig();
}
""" % json.dumps(uri)
    for qdbus in ("qdbus6", "qdbus", "dbus-send"):
        if not shutil.which(qdbus):
            continue
        if qdbus == "dbus-send":
            rc, out, err = _run_args([
                "dbus-send", "--session", "--dest=org.kde.plasmashell", "--type=method_call",
                "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript", f"string:{script}",
            ], timeout=10)
        else:
            rc, out, err = _run_args([qdbus, "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript", script], timeout=10)
        if rc == 0:
            return True, out
        if err or out:
            errors.append(f"{qdbus}: {err or out}")
    return False, " | ".join(errors)


def _set_linux_wallpaper(path: str) -> None:
    abs_path = _ensure_existing_file(path)
    uri = _file_uri(abs_path)
    errors = []
    # KDE must be tried before gsettings: GNOME schemas may exist on KDE but will not change Plasma wallpaper.
    if _is_kde_session():
        ok, detail = _set_kde_wallpaper(abs_path)
        if ok:
            return
        if detail:
            errors.append(detail)
    # GNOME / Unity / Budgie / Cinnamon / compatible desktops.
    if shutil.which("gsettings"):
        rc, out, err = _run_args(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri])
        if rc == 0:
            # GNOME 42+ can use a separate dark-mode key. Ignore its absence on older desktops.
            _run_args(["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri])
            return
        if err or out:
            errors.append(f"gsettings: {err or out}")
    else:
        errors.append("gsettings: command not found")
    # KDE Plasma fallback for sessions that did not advertise KDE.
    ok, detail = _set_kde_wallpaper(abs_path)
    if ok:
        return
    if detail:
        errors.append(detail)
    # LXDE / PCManFM desktop.
    if shutil.which("pcmanfm"):
        rc, out, err = _run_args(["pcmanfm", f"--set-wallpaper={abs_path}", "--wallpaper-mode=fit"], timeout=10)
        if rc == 0:
            return
        if err or out:
            errors.append(f"pcmanfm: {err or out}")
    # XFCE common paths. Some multi-monitor setups use different xfconf paths; this is best effort.
    if shutil.which("xfconf-query"):
        xfce_paths = [
            "/backdrop/screen0/monitor0/image-path",
            "/backdrop/screen0/monitor0/workspace0/last-image",
        ]
        for prop in xfce_paths:
            rc, out, err = _run_args(["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", abs_path])
            if rc == 0:
                return
            if err or out:
                errors.append(f"xfconf-query {prop}: {err or out}")
    # Lightweight window managers.
    for cmd in (["feh", "--bg-scale", abs_path], ["nitrogen", "--set-scaled", abs_path]):
        if not shutil.which(cmd[0]):
            continue
        rc, out, err = _run_args(cmd)
        if rc == 0:
            return
        if err or out:
            errors.append(f"{cmd[0]}: {err or out}")
    raise RuntimeError(
        "Cannot set wallpaper on Linux. Install/use gsettings (GNOME/Unity/Budgie), "
        "pcmanfm (LXDE), xfconf-query (XFCE), plasma-workspace (KDE), feh, or nitrogen. "
        + " | ".join(errors[-5:])
    )


def set_wallpaper_platform(path: str) -> None:
    if IS_WINDOWS:
        _set_windows_wallpaper(path)
        return
    if IS_MACOS:
        _set_macos_wallpaper(path)
        return
    if IS_LINUX:
        _set_linux_wallpaper(path)
        return
    raise RuntimeError(f"Unsupported system: {sys.platform}")


def get_current_wallpaper_platform() -> str:
    if IS_WINDOWS:
        buf = ctypes.create_unicode_buffer(260)
        ok = ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, 260, buf, 0)
        return buf.value if ok else ""
    if IS_MACOS:
        return run_osascript('tell application "System Events" to get picture of current desktop')
    if IS_LINUX:
        # KDE does not expose the current wallpaper consistently through a tiny stable CLI; keep best-effort.
        if not _is_kde_session() and shutil.which("gsettings"):
            for key in ("picture-uri", "picture-uri-dark"):
                rc, out, _ = _run_args(["gsettings", "get", "org.gnome.desktop.background", key])
                if rc == 0 and out:
                    path = _path_from_uri(out)
                    if path:
                        return path
        if shutil.which("xfconf-query"):
            for prop in ("/backdrop/screen0/monitor0/image-path", "/backdrop/screen0/monitor0/workspace0/last-image"):
                rc, out, _ = _run_args(["xfconf-query", "-c", "xfce4-desktop", "-p", prop])
                if rc == 0 and out:
                    return out
        return ""
    return ""


def configure_windows_fit_mode(fit_mode, winreg_module=None, log=None):
    fit_mode = normalize_style_key(fit_mode)
    if not IS_WINDOWS or winreg_module is None:
        if IS_MACOS:
            _configure_macos_fit_mode(fit_mode, log)
        elif IS_LINUX:
            _configure_linux_fit_mode(fit_mode, log)
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
    except Exception as exc:
        if log:
            log("设置适应模式失败: " + str(exc))


def _configure_macos_fit_mode(fit_mode, log=None):
    # macOS System Events can set the picture reliably; picture scaling style is not exposed consistently.
    if log:
        log("macOS picture scaling is controlled by System Settings; continuing with image change only.")


def _configure_linux_fit_mode(fit_mode, log=None):
    try:
        style_map_linux = {
            "填充": "zoom",
            "适应": "scaled",
            "拉伸": "stretched",
            "居中": "centered",
            "平铺": "wallpaper",
        }
        option = style_map_linux.get(fit_mode, "zoom")
        if not _is_kde_session() and shutil.which("gsettings"):
            _run_args(["gsettings", "set", "org.gnome.desktop.background", "picture-options", option])
    except Exception as exc:
        if log:
            log(f"Linux fit mode config failed: {exc}")
