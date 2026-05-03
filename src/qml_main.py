import argparse
import json
import os
import plistlib
import random
import shlex
import shutil
import sys
import tempfile
import time
import uuid

from PIL import Image, ImageDraw
from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

import random_copy
from app_config import APP_NAME, IS_MACOS, IS_WINDOWS
from macos_desktop_context import stop_desktop_context_menu
from macos_menu_bar import COMMAND_FILE, start_menu_bar, stop_menu_bar
from macos_video_wallpaper import start_video_wallpaper as start_macos_video, stop_video_wallpaper as stop_macos_video
from platform_support import get_current_wallpaper_platform, set_wallpaper_platform
from windows_video_wallpaper import start_video_wallpaper as start_windows_video, stop_video_wallpaper as stop_windows_video


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "shezhi.json")
QML_PATH = os.path.join(BASE_DIR, "qml", "Main.qml")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".gif")
TRAY_ACTION_LABELS = {
    "show": "打开设置主界面",
    "previous": "上一张壁纸",
    "next": "下一张壁纸",
    "random": "随机壁纸",
    "about": "关于作者",
    "jump": "跳转到壁纸",
    "exit": "退出程序",
}
HOTKEY_ITEMS = {
    "previous": "上一张壁纸",
    "next": "下一张壁纸",
    "random": "随机壁纸",
    "show": "打开设置主界面",
    "jump": "跳转到壁纸",
}
DEFAULT_HOTKEYS = {"previous": "u", "next": "n", "random": "3", "show": "x", "jump": "v"}


def log(message):
    print(message)


def default_config():
    return {
        "mode": "幻灯片放映",
        "slide_folder": "",
        "slide_seconds": 300,
        "manual_mode": False,
        "shuffle": False,
        "fit_mode": "填充",
        "single_image": "",
        "video_file": "",
        "video_muted": True,
        "solid_color": "#4facfe",
        "gradient_color2": "#00f2fe",
        "gradient_angle": 60,
        "gradient_type": "linear",
        "current_wallpaper": "",
        "history": [],
        "ctx_last_wallpaper": False,
        "ctx_next_wallpaper": True,
        "ctx_random_wallpaper": False,
        "ctx_personalize": True,
        "ctx_jump_to_wallpaper": True,
        "ctx_set_wallpaper": False,
        "recent_folders": [],
        "run_in_background": True,
        "tray_icon": True,
        "tray_click_action": "next",
        "tray_menu_items": ["show", "previous", "next", "random", "about", "jump", "exit"],
        "transition_animation": True,
        "transition_effect": "smooth",
        "transition_frames": 12,
        "transition_duration": 1.0,
        "smooth_effect": "fade",
        "slide_direction": "right",
    }


def load_config():
    config = default_config()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                config.update(loaded)
        except Exception as e:
            log(f"配置加载失败: {e}")
    return config


def save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"配置保存失败: {e}")


def image_files(folder):
    if not folder or not os.path.isdir(folder):
        return []
    return [
        os.path.join(folder, name)
        for name in os.listdir(folder)
        if name.lower().endswith(IMAGE_EXT) and not name.startswith(random_copy.COPY_PREFIX)
    ]


def path_from_url(value):
    text = str(value or "")
    if text.startswith("PySide6."):
        text = text.split("'", 2)[1] if "'" in text else text
    if text.startswith("file://"):
        return QUrl(text).toLocalFile()
    return text


def file_url(path):
    return QUrl.fromLocalFile(path).toString() if path and os.path.exists(path) else ""


def macos_service_path(name):
    return os.path.expanduser(os.path.join("~/Library/Services", name))


def create_macos_workflow_service(service_dir, title, shell_script, input_type="com.apple.Automator.nothing", send_file_types=None):
    contents_dir = os.path.join(service_dir, "Contents")
    resources_dir = os.path.join(contents_dir, "Resources")
    os.makedirs(resources_dir, exist_ok=True)
    service_info = {
        "NSMenuItem": {"default": title},
        "NSMessage": "runWorkflowAsService",
        "NSRequiredContext": {"NSApplicationIdentifier": "com.apple.finder"},
    }
    if send_file_types:
        service_info["NSSendFileTypes"] = send_file_types
    info_plist = {
        "CFBundleDevelopmentRegion": "en_US",
        "CFBundleIdentifier": "com.xxdz.shangbackground." + uuid.uuid5(uuid.NAMESPACE_URL, service_dir).hex,
        "CFBundleName": title,
        "CFBundlePackageType": "BNDL",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1.0",
        "NSServices": [service_info],
    }
    document_plist = {
        "AMApplicationBuild": "346",
        "AMApplicationVersion": "2.3",
        "AMDocumentVersion": "2",
        "actions": [{
            "action": {
                "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                "ActionName": "Run Shell Script",
                "ActionParameters": {
                    "COMMAND_STRING": "",
                    "CheckedForUserDefaultShell": True,
                    "inputMethod": 1 if send_file_types else 0,
                    "shell": "/bin/sh",
                    "source": shell_script,
                },
                "BundleIdentifier": "com.apple.RunShellScript",
                "Class Name": "RunShellScriptAction",
                "InputUUID": str(uuid.uuid4()).upper(),
                "OutputUUID": str(uuid.uuid4()).upper(),
                "UUID": str(uuid.uuid4()).upper(),
                "arguments": {},
                "isViewVisible": True,
            }
        }],
        "connectors": {},
        "workflowMetaData": {
            "serviceApplicationBundleID": "com.apple.finder",
            "serviceInputTypeIdentifier": input_type,
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceProcessesInput": 0,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }
    with open(os.path.join(contents_dir, "Info.plist"), "wb") as f:
        plistlib.dump(info_plist, f)
    with open(os.path.join(contents_dir, "version.plist"), "wb") as f:
        plistlib.dump({"CFBundleShortVersionString": "1.0"}, f)
    with open(os.path.join(resources_dir, "document.wflow"), "wb") as f:
        plistlib.dump(document_plist, f)


def sync_macos_context_services(config):
    if not IS_MACOS:
        return
    stop_desktop_context_menu()
    actions = [
        ("previous", "ShangBackground - 上一张壁纸", "--previous", "ctx_last_wallpaper", True),
        ("next", "ShangBackground - 下一张壁纸", "--next", "ctx_next_wallpaper", True),
        ("random", "ShangBackground - 随机壁纸", "--random", "ctx_random_wallpaper", True),
        ("jump", "ShangBackground - 跳转到壁纸", "--jump-to-wallpaper", "ctx_jump_to_wallpaper", True),
        ("show", "ShangBackground - 显示主界面", "--show", "ctx_personalize", False),
    ]
    slide_mode = config.get("mode") == "幻灯片放映"
    for action, title, arg, key, requires_slide in actions:
        service_dir = macos_service_path(f"ShangBackground {action}.workflow")
        enabled = config.get(key, True if action in ("next", "show") else False)
        if requires_slide and not slide_mode:
            enabled = False
        if enabled:
            py = shlex.quote(os.path.abspath(sys.executable))
            script = shlex.quote(os.path.abspath(sys.argv[0]))
            create_macos_workflow_service(service_dir, title, f"{py} {script} {arg} >/dev/null 2>&1 &\n")
        elif os.path.exists(service_dir):
            shutil.rmtree(service_dir)
    file_service = macos_service_path("Set As Wallpaper.workflow")
    if config.get("ctx_set_wallpaper", False):
        py = shlex.quote(os.path.abspath(sys.executable))
        script = shlex.quote(os.path.abspath(sys.argv[0]))
        shell_script = f'for f in "$@"; do\n  if [ -f "$f" ]; then\n    {py} {script} --set-wallpaper "$f"\n  fi\ndone\n'
        create_macos_workflow_service(file_service, "设为壁纸", shell_script, "public.image", ["public.image"])
    elif os.path.exists(file_service):
        shutil.rmtree(file_service)


class WallpaperController:
    def __init__(self, config):
        self.config = config
        self.slide_images = []

    def save(self):
        save_config(self.config)

    def push_history(self, path):
        history = [path] + [p for p in self.config.get("history", []) if p != path]
        self.config["history"] = history[:50]

    def set_wallpaper(self, path, operation="用户", skip_history=False):
        if not path or not os.path.isfile(path):
            return False, "壁纸文件不存在"
        try:
            set_wallpaper_platform(path)
            if not skip_history:
                self.push_history(path)
            self.config["current_wallpaper"] = path
            self.save()
            return True, ""
        except Exception as e:
            return False, str(e)

    def reload_slide_images(self):
        images = image_files(self.config.get("slide_folder", ""))
        if self.config.get("shuffle"):
            random.shuffle(images)
        self.slide_images = images
        return images

    def previous_wallpaper(self):
        for path in self.config.get("history", [])[1:]:
            if os.path.exists(path):
                self.config["history"] = [path] + [p for p in self.config.get("history", []) if p != path]
                self.save()
                return self.set_wallpaper(path, "上一张")
        return False, "没有可用的上一张壁纸"

    def next_wallpaper(self):
        if not self.slide_images:
            self.reload_slide_images()
        if not self.slide_images:
            return False, "请先设置幻灯片文件夹"
        current = self.config.get("current_wallpaper", "")
        idx = (self.slide_images.index(current) + 1) % len(self.slide_images) if current in self.slide_images else 0
        return self.set_wallpaper(self.slide_images[idx], "下一张")

    def random_wallpaper(self):
        folder = self.config.get("slide_folder", "")
        images = random_copy.get_all_images_with_copies(folder) if folder else []
        images = images or image_files(folder)
        if not images:
            return False, "请先设置幻灯片文件夹"
        current = self.config.get("current_wallpaper", "")
        available = [p for p in images if p != current] or images
        return self.set_wallpaper(random.choice(available), "随机壁纸")

    def apply_solid(self):
        img = Image.new("RGB", (1920, 1080), self.config.get("solid_color", "#4facfe"))
        path = os.path.join(tempfile.gettempdir(), "shangbackground_solid.bmp")
        img.save(path)
        return self.set_wallpaper(path, "纯色壁纸", skip_history=True)

    def apply_gradient(self):
        color1 = self.config.get("solid_color", "#4facfe")
        color2 = self.config.get("gradient_color2", "#00f2fe")
        img = Image.new("RGB", (1920, 1080), color1)
        draw = ImageDraw.Draw(img)
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        for x in range(1920):
            t = x / 1919
            draw.line([(x, 0), (x, 1080)], fill=(int(r1 * (1 - t) + r2 * t), int(g1 * (1 - t) + g2 * t), int(b1 * (1 - t) + b2 * t)))
        path = os.path.join(tempfile.gettempdir(), "shangbackground_gradient.bmp")
        img.save(path)
        return self.set_wallpaper(path, "渐变壁纸", skip_history=True)

    def apply_video(self):
        path = self.config.get("video_file", "")
        if not path or not os.path.isfile(path):
            return False, "请先选择视频文件"
        if IS_MACOS:
            return start_macos_video(path, muted=self.config.get("video_muted", True))
        if IS_WINDOWS:
            return start_windows_video(path, muted=self.config.get("video_muted", True))
        return False, "视频壁纸暂不支持当前平台"

    def stop_video(self):
        if IS_MACOS:
            stop_macos_video()
        elif IS_WINDOWS:
            stop_windows_video()


class Backend(QObject):
    changed = Signal()
    modeChanged = Signal()
    statusChanged = Signal()
    previewChanged = Signal()
    miniPreviewsChanged = Signal()
    recentFoldersChanged = Signal()
    requestShow = Signal()

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.controller = WallpaperController(self.config)
        self._status = "就绪"
        self._preview = ""
        self.command_seen_at = 0
        self.slide_timer = QTimer(self)
        self.slide_timer.timeout.connect(self.slide_next)
        self.command_timer = QTimer(self)
        self.command_timer.timeout.connect(self.poll_command)
        self.command_timer.start(500)
        self.update_preview()
        self.sync_macos_services()
        self.start_tray()
        self.register_hotkeys()
        if self.config.get("mode") == "幻灯片放映" and self.config.get("slide_folder") and not self.config.get("manual_mode", False):
            self.start_slideshow()

    def get_value(self, key, default=None):
        return self.config.get(key, default)

    def set_status(self, text):
        self._status = text
        self.statusChanged.emit()

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property(str, notify=modeChanged)
    def mode(self):
        return self.config.get("mode", "幻灯片放映")

    @Property(str, notify=previewChanged)
    def previewSource(self):
        return self._preview

    @Property(str, notify=recentFoldersChanged)
    def slideFolderLabel(self):
        folder = self.config.get("slide_folder", "")
        return os.path.basename(folder) if folder else ""

    @Property("QStringList", notify=miniPreviewsChanged)
    def miniPreviews(self):
        return [file_url(p) for p in image_files(self.config.get("slide_folder", ""))[:3]]

    @Property("QStringList", constant=True)
    def trayActionKeys(self):
        return list(TRAY_ACTION_LABELS.keys())

    @Property("QStringList", constant=True)
    def trayActionLabels(self):
        return [TRAY_ACTION_LABELS[k] for k in TRAY_ACTION_LABELS]

    @Slot(str, result="QVariant")
    def value(self, key):
        return self.config.get(key, "")

    @Slot(str, str)
    def setValue(self, key, value):
        if value in ("true", "false"):
            value = value == "true"
        self.config[key] = value
        self.controller.save()
        self.changed.emit()

    @Slot(str, bool)
    def setBool(self, key, value):
        self.config[key] = bool(value)
        self.controller.save()
        self.changed.emit()
        if key.startswith("ctx_") or key == "tray_icon":
            self.sync_macos_services()
            self.start_tray()

    @Slot(str, int)
    def setInt(self, key, value):
        self.config[key] = int(value)
        self.controller.save()
        self.changed.emit()

    @Slot(str, float)
    def setFloat(self, key, value):
        self.config[key] = float(value)
        self.controller.save()
        self.changed.emit()

    @Slot(str)
    def setMode(self, mode):
        self.config["mode"] = mode
        self.controller.save()
        self.modeChanged.emit()
        self.sync_macos_services()
        if mode == "幻灯片放映":
            self.controller.stop_video()
            self.start_slideshow()
        else:
            self.slide_timer.stop()
            if mode != "视频":
                self.controller.stop_video()

    @Slot(str)
    def setSlideFolder(self, url):
        path = path_from_url(url)
        if path and os.path.isdir(path):
            self.config["slide_folder"] = path
            recent = [path] + [p for p in self.config.get("recent_folders", []) if p != path]
            self.config["recent_folders"] = recent[:10]
            self.controller.save()
            self.controller.reload_slide_images()
            self.recentFoldersChanged.emit()
            self.miniPreviewsChanged.emit()
            if self.mode == "幻灯片放映":
                self.start_slideshow()

    @Slot(str)
    def setImageFile(self, url):
        path = path_from_url(url)
        if path:
            self.config["single_image"] = path
            self.controller.save()
            self.changed.emit()

    @Slot(str)
    def setVideoFile(self, url):
        path = path_from_url(url)
        if path:
            self.config["video_file"] = path
            self.controller.save()
            self.changed.emit()

    @Slot()
    def applyCurrentMode(self):
        mode = self.mode
        if mode == "幻灯片放映":
            self.controller.reload_slide_images()
            if self.config.get("slide_folder") and not self.config.get("manual_mode", False):
                self.start_slideshow()
            ok, err = True, ""
        elif mode == "图片":
            ok, err = self.controller.set_wallpaper(self.config.get("single_image", ""), "图片")
        elif mode == "视频":
            ok, err = self.controller.apply_video()
        elif mode == "纯色":
            ok, err = self.controller.apply_solid()
        else:
            ok, err = self.controller.apply_gradient()
        self.set_status(err if not ok else f"{mode} 已应用")
        self.update_preview()

    @Slot()
    def previous(self):
        self._apply_result(self.controller.previous_wallpaper())

    @Slot()
    def next(self):
        self._apply_result(self.controller.next_wallpaper())

    @Slot()
    def randomWallpaper(self):
        self._apply_result(self.controller.random_wallpaper())

    @Slot()
    def stopVideo(self):
        self.controller.stop_video()
        self.set_status("视频壁纸已停止")

    @Slot()
    def openSlideFolder(self):
        folder = self.config.get("slide_folder", "")
        if folder and os.path.isdir(folder):
            QGuiApplication.instance().clipboard()  # keep QGuiApplication referenced for Qt plugins
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    @Slot("QVariant", "QVariant", "QVariant", str, float, int, str, str, bool)
    def saveAdvancedSettings(self, tray_items, hotkey_pairs, transition_values, effect, duration, frames, smooth_effect, direction, transition_enabled):
        self.config["tray_menu_items"] = [str(x) for x in tray_items if str(x) in TRAY_ACTION_LABELS]
        for pair in hotkey_pairs:
            if "=" in pair:
                key, value = pair.split("=", 1)
                if key in HOTKEY_ITEMS:
                    self.config[f"hotkey_{key}"] = value.strip()
        self.config["transition_animation"] = bool(transition_enabled)
        self.config["transition_effect"] = effect
        self.config["transition_duration"] = round(float(duration), 1)
        self.config["transition_frames"] = int(frames)
        self.config["smooth_effect"] = smooth_effect
        self.config["slide_direction"] = direction
        self.controller.save()
        self.register_hotkeys()
        self.start_tray()
        self.changed.emit()
        self.set_status("高级设置已保存")

    @Slot(result="QStringList")
    def trayMenuItems(self):
        return [x for x in self.config.get("tray_menu_items", []) if x in TRAY_ACTION_LABELS]

    @Slot(result="QStringList")
    def hotkeyPairs(self):
        return [f"{k}={self.config.get(f'hotkey_{k}', '')}" for k in HOTKEY_ITEMS]

    def _apply_result(self, result):
        ok, err = result
        if not ok:
            self.set_status(err)
        self.update_preview()

    def update_preview(self):
        path = self.config.get("current_wallpaper", "")
        if not path or not os.path.exists(path):
            try:
                path = get_current_wallpaper_platform()
                if path:
                    self.config["current_wallpaper"] = path
                    self.controller.save()
            except Exception:
                path = ""
        self._preview = file_url(path)
        self.previewChanged.emit()

    def start_slideshow(self):
        if not self.config.get("slide_folder") or self.config.get("manual_mode", False):
            return
        self.controller.reload_slide_images()
        self.slide_timer.start(max(1, int(self.config.get("slide_seconds", 300))) * 1000)

    def slide_next(self):
        result = self.controller.random_wallpaper() if self.config.get("shuffle") else self.controller.next_wallpaper()
        self._apply_result(result)

    def sync_macos_services(self):
        try:
            sync_macos_context_services(self.config)
        except Exception as e:
            log(f"macOS 右键服务同步失败: {e}")

    def start_tray(self):
        if IS_MACOS:
            stop_menu_bar()
            if self.config.get("tray_icon", True):
                start_menu_bar(os.path.abspath(sys.argv[0]), main_pid=os.getpid())

    def register_hotkeys(self):
        if IS_MACOS and hasattr(os, "geteuid") and os.geteuid() != 0:
            self.set_status("macOS 非管理员权限，已跳过全局快捷键注册")
            return
        try:
            import keyboard
        except Exception:
            return
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        actions = {"previous": self.previous, "next": self.next, "random": self.randomWallpaper, "show": self.requestShow.emit}
        for key, callback in actions.items():
            hotkey = self.config.get(f"hotkey_{key}", "") or DEFAULT_HOTKEYS.get(key, "")
            try:
                keyboard.add_hotkey(hotkey, lambda cb=callback: QTimer.singleShot(0, cb), suppress=False)
            except Exception as e:
                log(f"快捷键注册失败 {hotkey}: {e}")

    def poll_command(self):
        if not os.path.exists(COMMAND_FILE):
            return
        try:
            with open(COMMAND_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            timestamp = float(payload.get("time", 0))
            if timestamp and timestamp <= self.command_seen_at:
                return
            self.command_seen_at = timestamp
            command = payload.get("command", "")
            if command == "previous":
                self.previous()
            elif command == "next":
                self.next()
            elif command == "random":
                self.randomWallpaper()
            elif command == "show":
                self.requestShow.emit()
            elif command == "jump":
                import subprocess
                subprocess.Popen([sys.executable, os.path.abspath(sys.argv[0]), "--jump-to-wallpaper"])
            elif command == "open-wallpaper-folder":
                self.openSlideFolder()
        except Exception as e:
            log(f"菜单栏命令处理失败: {e}")


def handle_cli(controller, args):
    if args.previous:
        return controller.previous_wallpaper()
    if args.next:
        return controller.next_wallpaper()
    if args.random:
        return controller.random_wallpaper()
    if args.set_wallpaper:
        return controller.set_wallpaper(args.set_wallpaper, "命令行设置")
    return None


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--previous", action="store_true")
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--random", action="store_true")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--hide", action="store_true")
    parser.add_argument("--jump-to-wallpaper", action="store_true")
    parser.add_argument("--set-wallpaper")
    parser.add_argument("--quick-settings", action="store_true")
    parser.add_argument("--switch-mode", action="store_true")
    parser.add_argument("--open-wallpaper-folder", action="store_true")
    parser.add_argument("--about", action="store_true")
    args = parser.parse_args()

    config = load_config()
    controller = WallpaperController(config)
    cli_result = handle_cli(controller, args)
    if cli_result is not None:
        ok, err = cli_result
        if not ok:
            print(err)
        return

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    backend = Backend()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(QML_PATH))
    if not engine.rootObjects():
        sys.exit(1)
    if args.hide:
        engine.rootObjects()[0].hide()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
