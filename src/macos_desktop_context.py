import argparse
import os
import signal
import subprocess
import time

from app_config import IS_MACOS


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(BASE_DIR, "macos_desktop_context.pid")


def _read_pid():
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def _is_process_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def is_available():
    return False


def _helper_patterns():
    return (
        "macos_desktop_context.py",
        "macos_desktop_context",
        "desktop-context",
    )


def _find_helper_pids():
    pids = set()
    current_pid = os.getpid()
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "cmdline"]):
            pid = proc.info.get("pid")
            if not pid or pid == current_pid:
                continue
            command = " ".join(str(part) for part in (proc.info.get("cmdline") or []))
            if any(pattern in command for pattern in _helper_patterns()):
                pids.add(pid)
    except Exception:
        pass

    for pattern in _helper_patterns():
        try:
            output = subprocess.check_output(
                ["pgrep", "-f", pattern],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            continue
        for line in output.splitlines():
            try:
                pid = int(line.strip())
            except ValueError:
                continue
            if pid != current_pid:
                pids.add(pid)
    return pids


def start_desktop_context_menu(script_path=None, main_pid=None):
    stop_desktop_context_menu()
    return False, "macOS 桌面右键监听已禁用，请使用 Finder 系统服务，避免覆盖系统右键菜单"


def stop_desktop_context_menu():
    pids = set()
    pid = _read_pid()
    if pid:
        pids.add(pid)
    pids.update(_find_helper_pids())

    for pid in pids:
        if not _is_process_alive(pid):
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                if not _is_process_alive(pid):
                    break
                time.sleep(0.05)
            if _is_process_alive(pid):
                os.kill(pid, signal.SIGKILL)
        except Exception:
            pass

    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass


def run_desktop_context(script_path=None, main_pid=None):
    stop_desktop_context_menu()


def main():
    parser = argparse.ArgumentParser(description="禁用旧版 macOS 桌面右键监听")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--script")
    parser.add_argument("--main-pid", type=int)
    parser.parse_args()
    if IS_MACOS:
        stop_desktop_context_menu()


if __name__ == "__main__":
    main()
