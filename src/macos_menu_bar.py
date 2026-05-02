import argparse
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time

from app_config import IS_MACOS


PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "macos_menu_bar.pid")
COMMAND_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "macos_menu_command.json")


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
    return IS_MACOS and importlib.util.find_spec("AppKit") is not None


def start_menu_bar(script_path, main_pid=None):
    if not IS_MACOS:
        return False, "macOS 菜单栏常驻仅支持 macOS"
    if importlib.util.find_spec("AppKit") is None:
        return False, "缺少 pyobjc-framework-Cocoa，请先安装依赖"

    pid = _read_pid()
    if pid and _is_process_alive(pid):
        return True, ""

    cmd = [
        sys.executable,
        os.path.abspath(__file__),
        "--run",
        "--script",
        os.path.abspath(script_path),
    ]
    if main_pid:
        cmd.extend(["--main-pid", str(main_pid)])
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(process.pid))
        return True, ""
    except Exception as e:
        return False, str(e)


def stop_menu_bar():
    pid = _read_pid()
    if pid and _is_process_alive(pid):
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


def _write_command(command):
    with open(COMMAND_FILE, "w", encoding="utf-8") as f:
        json.dump({"command": command, "time": time.time()}, f)


def run_menu_bar(script_path, main_pid=None):
    import objc
    from AppKit import (
        NSApp,
        NSApplication,
        NSApplicationActivationPolicyAccessory,
        NSMenu,
        NSMenuItem,
        NSStatusBar,
        NSVariableStatusItemLength,
    )
    from Foundation import NSObject

    class MenuController(NSObject):
        script_path = objc.ivar()
        main_pid = objc.ivar()

        def initWithScriptPath_mainPid_(self, path, pid):
            self = objc.super(MenuController, self).init()
            if self is None:
                return None
            self.script_path = path
            self.main_pid = int(pid) if pid else 0
            return self

        def _send_or_launch(self, command, *args):
            if _is_process_alive(self.main_pid):
                try:
                    _write_command(command)
                    return
                except Exception:
                    pass
            subprocess.Popen([sys.executable, self.script_path, *args])

        def show_(self, sender):
            self._send_or_launch("show", "--show")

        def previous_(self, sender):
            self._send_or_launch("previous", "--previous")

        def next_(self, sender):
            self._send_or_launch("next", "--next")

        def random_(self, sender):
            self._send_or_launch("random", "--random")

        def jump_(self, sender):
            self._send_or_launch("jump", "--jump-to-wallpaper")

        def quitMenu_(self, sender):
            try:
                if os.path.exists(PID_FILE):
                    os.remove(PID_FILE)
            except Exception:
                pass
            NSApp.terminate_(None)

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    controller = MenuController.alloc().initWithScriptPath_mainPid_(os.path.abspath(script_path), main_pid or 0)

    status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
    status_item.button().setTitle_("壁")
    status_item.button().setToolTip_("上一个桌面背景")

    menu = NSMenu.alloc().init()

    def add_item(title, action_name):
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action_name, "")
        item.setTarget_(controller)
        menu.addItem_(item)

    add_item("显示主界面", "show:")
    add_item("上一张壁纸", "previous:")
    add_item("下一张壁纸", "next:")
    add_item("随机壁纸", "random:")
    add_item("跳转到壁纸", "jump:")
    menu.addItem_(NSMenuItem.separatorItem())
    add_item("退出菜单栏常驻", "quitMenu:")

    status_item.setMenu_(menu)
    app.run()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--script", required=True)
    parser.add_argument("--main-pid", type=int, default=0)
    args = parser.parse_args()
    if args.run:
        run_menu_bar(args.script, main_pid=args.main_pid)


if __name__ == "__main__":
    main()
