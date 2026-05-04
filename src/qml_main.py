import argparse
import json
import os
import plistlib
import random
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from PIL import Image, ImageDraw, ImageOps
from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QIcon
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
ICON_PATH = os.path.join(BASE_DIR, "img", "LOGO.ico")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".gif")
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".avi", ".mkv")
MODES = ["幻灯片放映", "图片", "视频", "纯色", "渐变"]
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
        "transition_frames": 18,
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


def qml_to_list(value):
    if value is None:
        return []
    if hasattr(value, "toVariant"):
        value = value.toVariant()
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        return [value] if value else []
    try:
        return list(value)
    except TypeError:
        return []


def file_url(path):
    return QUrl.fromLocalFile(path).toString() if path and os.path.exists(path) else ""


def video_preview_path(path):
    safe_name = uuid.uuid5(uuid.NAMESPACE_URL, os.path.abspath(path)).hex + ".jpg"
    return os.path.join(tempfile.gettempdir(), "shangbackground_video_previews", safe_name)


def extract_video_first_frame(path):
    if not path or not os.path.isfile(path):
        return ""
    output = video_preview_path(path)
    try:
        if os.path.exists(output) and os.path.getmtime(output) >= os.path.getmtime(path):
            return output
    except Exception:
        pass
    os.makedirs(os.path.dirname(output), exist_ok=True)

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    path,
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    output,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=True,
            )
            if os.path.exists(output):
                return output
        except Exception as e:
            log(f"ffmpeg 提取视频首帧失败: {e}")

    try:
        import imageio.v3 as iio

        frame = iio.imread(path, index=0)
        Image.fromarray(frame).convert("RGB").save(output, quality=90)
        return output if os.path.exists(output) else ""
    except Exception as e:
        log(f"imageio 提取视频首帧失败: {e}")
        return ""


def compact_path_label(path, used_labels=None):
    base = os.path.basename(path) or path
    if not used_labels or base not in used_labels:
        return base
    parent = os.path.basename(os.path.dirname(path))
    return f"{base} - {parent}" if parent else path


def macos_service_path(name):
    return os.path.expanduser(os.path.join("~/Library/Services", name))


def macos_launch_agent_path():
    return os.path.expanduser("~/Library/LaunchAgents/com.xxdz.shangbackground.plist")


def sync_auto_start(enable):
    if not IS_MACOS:
        return
    agent_path = macos_launch_agent_path()
    if enable:
        os.makedirs(os.path.dirname(agent_path), exist_ok=True)
        plist = {
            "Label": "com.xxdz.shangbackground",
            "ProgramArguments": [os.path.abspath(sys.executable), os.path.abspath(sys.argv[0]), "--hide"],
            "RunAtLoad": True,
            "KeepAlive": False,
            "WorkingDirectory": os.path.dirname(os.path.abspath(sys.argv[0])),
            "StandardOutPath": os.path.join(tempfile.gettempdir(), "shangbackground.log"),
            "StandardErrorPath": os.path.join(tempfile.gettempdir(), "shangbackground.err.log"),
        }
        with open(agent_path, "wb") as f:
            plistlib.dump(plist, f)
    elif os.path.exists(agent_path):
        os.remove(agent_path)


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

    def _transition_enabled_for(self, path):
        return (
            self.config.get("transition_animation", True)
            and path.lower().endswith(IMAGE_EXT)
            and self.config.get("current_wallpaper", "")
            and os.path.exists(self.config.get("current_wallpaper", ""))
        )

    def _transition_image(self, path, size):
        with Image.open(path) as source:
            image = source.convert("RGB")
        return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))

    def _transition_canvas_size(self, path):
        with Image.open(path) as source:
            width, height = source.size
        max_width = 1920
        if width <= max_width:
            return width, height
        ratio = max_width / width
        return max_width, max(1, int(height * ratio))

    def _ease_transition(self, progress):
        progress = max(0.0, min(1.0, progress))
        return progress * progress * progress * (progress * (progress * 6 - 15) + 10)

    def _soft_scan_mask(self, size, progress, direction):
        width, height = size
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        feather = max(24, min(width, height) // 18)
        if direction in ("up", "down"):
            scan_h = max(1, int(height * progress))
            y = 0 if direction == "down" else height - scan_h
            draw.rectangle((0, y, width, y + scan_h), fill=255)
            edge_start = y + scan_h - feather if direction == "down" else y
            for i in range(feather):
                alpha = int(255 * (1 - i / feather)) if direction == "down" else int(255 * (i / feather))
                yy = edge_start + i
                if 0 <= yy < height:
                    draw.line((0, yy, width, yy), fill=alpha)
        else:
            scan_w = max(1, int(width * progress))
            x = 0 if direction == "right" else width - scan_w
            draw.rectangle((x, 0, x + scan_w, height), fill=255)
            edge_start = x + scan_w - feather if direction == "right" else x
            for i in range(feather):
                alpha = int(255 * (1 - i / feather)) if direction == "right" else int(255 * (i / feather))
                xx = edge_start + i
                if 0 <= xx < width:
                    draw.line((xx, 0, xx, height), fill=alpha)
        return mask

    def _transition_frame(self, current, target, progress, effect, direction):
        progress = self._ease_transition(progress)
        if effect == "random":
            effect = random.choice(("fade", "slide", "scan"))
        if direction == "random":
            direction = random.choice(("left", "right", "up", "down"))
        if effect == "fade":
            return Image.blend(current, target, progress)

        width, height = current.size
        if effect == "scan":
            mask = self._soft_scan_mask(current.size, progress, direction)
            return Image.composite(target, current, mask)

        canvas = Image.new("RGB", current.size, (0, 0, 0))
        if direction == "left":
            offset = int(width * progress)
            canvas.paste(current, (-offset, 0))
            canvas.paste(target, (width - offset, 0))
        elif direction == "right":
            offset = int(width * progress)
            canvas.paste(current, (offset, 0))
            canvas.paste(target, (offset - width, 0))
        elif direction == "up":
            offset = int(height * progress)
            canvas.paste(current, (0, -offset))
            canvas.paste(target, (0, height - offset))
        else:
            offset = int(height * progress)
            canvas.paste(current, (0, offset))
            canvas.paste(target, (0, offset - height))
        return Image.blend(canvas, target, progress * 0.18)

    def _apply_transition(self, target_path):
        if not self._transition_enabled_for(target_path):
            return False
        current_path = self.config.get("current_wallpaper", "")
        if os.path.abspath(current_path) == os.path.abspath(target_path):
            return False
        try:
            size = self._transition_canvas_size(current_path)
            current_img = self._transition_image(current_path, size)
            target_img = self._transition_image(target_path, size)
            duration = max(0.1, min(10.0, float(self.config.get("transition_duration", 1.0))))
            if self.config.get("transition_effect", "smooth") == "frame":
                frames = max(8, min(60, int(self.config.get("transition_frames", 18))))
                effect = "fade"
            else:
                frames = max(16, min(60, int(duration * 24)))
                effect = self.config.get("smooth_effect", "fade")
            direction = self.config.get("slide_direction", "right")
            frame_dir = os.path.join(tempfile.gettempdir(), "shangbackground_transition")
            os.makedirs(frame_dir, exist_ok=True)
            frame_paths = []
            for index in range(1, frames + 1):
                frame = self._transition_frame(current_img, target_img, index / frames, effect, direction)
                frame_path = os.path.join(frame_dir, f"frame_{index:03d}.jpg")
                frame.save(frame_path, quality=88, optimize=False, progressive=False)
                frame_paths.append(frame_path)
            start = time.perf_counter()
            interval = duration / frames
            for index, frame_path in enumerate(frame_paths):
                set_wallpaper_platform(frame_path)
                target_time = start + (index + 1) * interval
                delay = target_time - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
            return True
        except Exception as e:
            log(f"过渡动画失败，已降级为直接切换: {e}")
            return False

    def set_wallpaper(self, path, operation="用户", skip_history=False):
        if not path or not os.path.isfile(path):
            return False, "壁纸文件不存在"
        try:
            self._apply_transition(path)
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
        images = image_files(folder)
        if not images:
            return False, "请先设置幻灯片文件夹"
        current = self.config.get("current_wallpaper", "")
        current_name = os.path.basename(current) if current else ""
        weighted = []
        for path in images:
            filename = os.path.basename(path)
            weight = 1
            if self.config.get("shuffle"):
                weight += max(0, int(random_copy.get_copy_count(folder, filename)))
            if filename != current_name:
                weighted.extend([path] * weight)
        weighted = weighted or images
        return self.set_wallpaper(random.choice(weighted), "随机壁纸")

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
    requestAbout = Signal()
    workerStatus = Signal(str)
    workerRefresh = Signal()
    workerChanged = Signal()
    hotkeyAction = Signal(str)

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.controller = WallpaperController(self.config)
        self._status = "就绪"
        self._preview = ""
        self.operation_lock = threading.Lock()
        self.workerStatus.connect(self.set_status)
        self.workerRefresh.connect(self.update_preview)
        self.workerChanged.connect(self.changed.emit)
        self.hotkeyAction.connect(self.handleHotkeyAction)
        self.command_seen_at = 0
        self.slide_timer = QTimer(self)
        self.slide_timer.timeout.connect(self.slide_next)
        self.command_timer = QTimer(self)
        self.command_timer.timeout.connect(self.poll_command)
        self.command_timer.start(500)
        self.update_preview()

        def startup_services():
            self.sync_macos_services()
            self.start_tray()
            return self.register_hotkeys()

        self.run_background("启动系统组件", startup_services)
        if self.config.get("mode") == "幻灯片放映" and self.config.get("slide_folder") and not self.config.get("manual_mode", False):
            self.start_slideshow()

    def get_value(self, key, default=None):
        return self.config.get(key, default)

    def set_status(self, text):
        self._status = text
        self.statusChanged.emit()

    def run_background(self, label, task, success_message=None, refresh=False, changed=False, locked=False):
        self.set_status(f"{label}中...")

        def worker():
            ok = True
            err = ""
            try:
                if locked:
                    with self.operation_lock:
                        result = task()
                else:
                    result = task()
                if isinstance(result, tuple):
                    ok, err = result
                elif result is False:
                    ok = False
            except Exception as e:
                ok = False
                err = str(e)
            if changed:
                self.workerChanged.emit()
            if refresh:
                self.workerRefresh.emit()
            if ok:
                self.workerStatus.emit(err or success_message or f"{label}完成")
            else:
                self.workerStatus.emit(err or f"{label}失败")

        threading.Thread(target=worker, name=f"ShangBackground-{label}", daemon=True).start()

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

    def _slide_folders(self):
        current = self.config.get("slide_folder", "")
        folders = []
        if current and os.path.isdir(current):
            folders.append(current)
        for folder in self.config.get("recent_folders", []):
            if folder and os.path.isdir(folder) and folder not in folders:
                folders.append(folder)
        return folders

    @Property("QStringList", notify=recentFoldersChanged)
    def recentFolderLabels(self):
        folders = self._slide_folders()
        if not folders:
            return ["未选择壁纸相册"]
        labels = []
        used = set()
        for folder in folders:
            label = compact_path_label(folder, used)
            labels.append(label)
            used.add(label)
        return labels

    @Property("QStringList", notify=recentFoldersChanged)
    def recentFolderPaths(self):
        folders = self._slide_folders()
        return folders or [""]

    @Property(int, notify=recentFoldersChanged)
    def currentSlideFolderIndex(self):
        current = self.config.get("slide_folder", "")
        folders = self._slide_folders()
        return folders.index(current) if current in folders else 0

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
        if key in ("single_image", "video_file"):
            self.update_preview()

    @Slot(str, bool)
    def setBool(self, key, value):
        self.config[key] = bool(value)
        self.controller.save()
        self.changed.emit()
        if key == "auto_start":
            self.run_background(
                "开机自启动设置",
                lambda enabled=bool(value): sync_auto_start(enabled),
                success_message="开机自启动设置已保存",
            )
        if key == "shuffle":
            folder = self.config.get("slide_folder", "")
            if folder:
                if bool(value):
                    self.run_background(
                        "随机概率恢复",
                        lambda: random_copy.restore_weights(folder),
                        success_message="随机顺序已开启",
                    )
                else:
                    self.run_background(
                        "随机概率清理",
                        lambda: random_copy.cleanup_physical_only(folder),
                        success_message="随机顺序已关闭",
                    )
        if key.startswith("ctx_") or key == "tray_icon":
            def sync_menus():
                self.sync_macos_services()
                self.start_tray()

            self.run_background(
                "系统菜单同步",
                sync_menus,
                success_message="系统菜单设置已同步",
            )

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
        self.update_preview()
        self.run_background("右键服务同步", self.sync_macos_services, success_message="右键服务已同步")
        if mode == "幻灯片放映":
            self.run_background("停止视频壁纸", self.controller.stop_video, success_message="视频壁纸已停止")
            self.start_slideshow()
        else:
            self.slide_timer.stop()
            if mode != "视频":
                self.run_background("停止视频壁纸", self.controller.stop_video, success_message="视频壁纸已停止")

    @Slot(str)
    def setSlideFolder(self, url):
        path = path_from_url(url)
        self.setSlideFolderPath(path)

    @Slot(str)
    def setSlideFolderPath(self, path):
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
            self.set_status(f"已选择壁纸相册: {os.path.basename(path) or path}")

    @Slot(str)
    def setImageFile(self, url):
        path = path_from_url(url)
        if path:
            self.config["single_image"] = path
            self.controller.save()
            self.changed.emit()
            self.update_preview()

    @Slot(str)
    def setVideoFile(self, url):
        path = path_from_url(url)
        if path:
            self.config["video_file"] = path
            self.controller.save()
            self.changed.emit()
            self.update_preview()

    @Slot()
    def applyCurrentMode(self):
        mode = self.mode
        if mode == "幻灯片放映":
            self.controller.reload_slide_images()
            if self.config.get("slide_folder") and not self.config.get("manual_mode", False):
                self.start_slideshow()
            self.set_status("幻灯片放映已应用")
            return

        def task():
            if mode == "图片":
                return self.controller.set_wallpaper(self.config.get("single_image", ""), "图片")
            if mode == "视频":
                return self.controller.apply_video()
            if mode == "纯色":
                return self.controller.apply_solid()
            return self.controller.apply_gradient()

        self.run_background("应用当前设置", task, success_message=f"{mode} 已应用", refresh=True, locked=True)

    @Slot()
    def previous(self):
        self.run_background("切换上一张壁纸", self.controller.previous_wallpaper, refresh=True, locked=True)

    @Slot()
    def next(self):
        self.run_background("切换下一张壁纸", self.controller.next_wallpaper, refresh=True, locked=True)

    @Slot()
    def randomWallpaper(self):
        self.run_background("随机切换壁纸", self.controller.random_wallpaper, refresh=True, locked=True)

    @Slot()
    def stopVideo(self):
        self.run_background("停止视频壁纸", self.controller.stop_video, success_message="视频壁纸已停止")

    @Slot(str)
    def handleHotkeyAction(self, action):
        if action == "previous":
            self.previous()
        elif action == "next":
            self.next()
        elif action == "random":
            self.randomWallpaper()
        elif action == "show":
            self.requestShow.emit()
        elif action == "jump":
            import subprocess
            subprocess.Popen([sys.executable, os.path.abspath(sys.argv[0]), "--jump-to-wallpaper"])

    @Slot()
    def cycleMode(self):
        current = self.mode
        next_mode = MODES[(MODES.index(current) + 1) % len(MODES)] if current in MODES else MODES[0]
        self.setMode(next_mode)
        self.set_status(f"已切换到 {next_mode}")

    @Slot()
    def openSlideFolder(self):
        folder = self.config.get("slide_folder", "")
        if folder and os.path.isdir(folder):
            QGuiApplication.instance().clipboard()  # keep QGuiApplication referenced for Qt plugins
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    @Slot("QVariant", "QVariant", "QVariant", str, float, int, str, str, bool)
    def saveAdvancedSettings(self, tray_items, hotkey_pairs, transition_values, effect, duration, frames, smooth_effect, direction, transition_enabled):
        self._store_tray_items(tray_items)
        self._store_hotkeys(hotkey_pairs)
        self._store_transition(effect, duration, frames, smooth_effect, direction, transition_enabled)
        self.controller.save()
        self.changed.emit()
        def apply_advanced():
            ok, message = self.register_hotkeys()
            self.start_tray()
            return ok, message

        self.run_background("高级设置生效", apply_advanced, success_message="高级设置已保存")
        self.set_status("高级设置已保存")

    def _store_tray_items(self, tray_items):
        items = []
        for action in qml_to_list(tray_items):
            action = str(action)
            if action in TRAY_ACTION_LABELS and action not in items:
                items.append(action)
        self.config["tray_menu_items"] = items

    def _store_hotkeys(self, hotkey_pairs):
        for pair in qml_to_list(hotkey_pairs):
            if "=" in pair:
                key, value = pair.split("=", 1)
                if key in HOTKEY_ITEMS:
                    self.config[f"hotkey_{key}"] = value.strip()

    def _store_transition(self, effect, duration, frames, smooth_effect, direction, transition_enabled):
        self.config["transition_animation"] = bool(transition_enabled)
        self.config["transition_effect"] = effect if effect in ("smooth", "frame") else "smooth"
        self.config["transition_duration"] = round(max(0.1, min(10.0, float(duration))), 1)
        self.config["transition_frames"] = max(4, min(60, int(frames)))
        self.config["smooth_effect"] = smooth_effect if smooth_effect in ("fade", "slide", "scan", "random") else "fade"
        self.config["slide_direction"] = direction if direction in ("left", "right", "up", "down", "random") else "right"

    @Slot("QVariant")
    def saveTraySettings(self, tray_items):
        self._store_tray_items(tray_items)
        self.controller.save()
        self.changed.emit()
        self.run_background("菜单栏/托盘重载", self.start_tray, success_message="菜单栏/托盘设置已保存")
        self.set_status("菜单栏/托盘设置已保存")

    @Slot("QVariant")
    def saveHotkeySettings(self, hotkey_pairs):
        self._store_hotkeys(hotkey_pairs)
        self.controller.save()
        self.changed.emit()
        self.run_background("快捷键注册", self.register_hotkeys, success_message="快捷键设置已保存")
        self.set_status("快捷键设置已保存")

    @Slot(str, float, int, str, str, bool)
    def saveTransitionSettings(self, effect, duration, frames, smooth_effect, direction, transition_enabled):
        self._store_transition(effect, duration, frames, smooth_effect, direction, transition_enabled)
        self.controller.save()
        self.changed.emit()
        self.set_status("过渡动画设置已保存")

    @Slot(result="QStringList")
    def trayMenuItems(self):
        return [x for x in self.config.get("tray_menu_items", []) if x in TRAY_ACTION_LABELS]

    @Slot(result="QStringList")
    def hotkeyPairs(self):
        return [f"{k}={self.config.get(f'hotkey_{k}', '')}" for k in HOTKEY_ITEMS]

    @Slot(result="QStringList")
    def randomProbabilityItems(self):
        folder = self.config.get("slide_folder", "")
        items = []
        for path in image_files(folder):
            filename = os.path.basename(path)
            count = max(0, int(random_copy.get_copy_count(folder, filename)))
            items.append(json.dumps({
                "filename": filename,
                "count": count,
                "preview": file_url(path),
            }, ensure_ascii=False))
        return items

    @Slot("QVariant")
    def saveRandomProbability(self, pairs):
        folder = self.config.get("slide_folder", "")
        if not folder or not os.path.isdir(folder):
            self.set_status("请先设置幻灯片文件夹")
            return
        changes = {}
        for pair in qml_to_list(pairs):
            text = str(pair)
            if "=" not in text:
                continue
            filename, count = text.rsplit("=", 1)
            if filename:
                try:
                    changes[filename] = max(0, min(20, int(count)))
                except ValueError:
                    changes[filename] = 0

        def save_weights():
            random_copy.save_all_changes(folder, changes)
            if not self.config.get("shuffle", False):
                random_copy.cleanup_physical_only(folder)

        self.run_background(
            "随机概率保存",
            save_weights,
            success_message="随机概率已保存",
            refresh=True,
        )

    def _apply_result(self, result):
        ok, err = result
        if not ok:
            self.set_status(err)
        self.update_preview()

    def update_preview(self):
        mode = self.config.get("mode", "幻灯片放映")
        if mode == "图片":
            path = self.config.get("single_image", "")
            self._preview = file_url(path)
            self.previewChanged.emit()
            return
        if mode == "视频":
            video = self.config.get("video_file", "")
            path = extract_video_first_frame(video) if video and video.lower().endswith(VIDEO_EXT) else ""
            self._preview = file_url(path)
            self.previewChanged.emit()
            return

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
        task = self.controller.random_wallpaper if self.config.get("shuffle") else self.controller.next_wallpaper
        self.run_background("自动切换壁纸", task, refresh=True, locked=True)

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
            return True, "macOS 非管理员权限，已跳过全局快捷键注册"
        try:
            import keyboard
        except Exception as e:
            return False, f"快捷键模块不可用: {e}"
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        failed = []
        for key in HOTKEY_ITEMS:
            hotkey = self.config.get(f"hotkey_{key}", "") or DEFAULT_HOTKEYS.get(key, "")
            try:
                keyboard.add_hotkey(hotkey, lambda action=key: self.hotkeyAction.emit(action), suppress=False)
            except Exception as e:
                log(f"快捷键注册失败 {hotkey}: {e}")
                failed.append(hotkey)
        if failed:
            return False, "部分快捷键注册失败: " + ", ".join(failed)
        return True, "快捷键已注册"

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
            elif command == "about":
                self.requestAbout.emit()
            elif command == "quick-settings":
                self.requestShow.emit()
            elif command == "switch-mode":
                self.cycleMode()
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
    if args.switch_mode:
        current = controller.config.get("mode", MODES[0])
        next_mode = MODES[(MODES.index(current) + 1) % len(MODES)] if current in MODES else MODES[0]
        controller.config["mode"] = next_mode
        controller.save()
        return True, ""
    if args.open_wallpaper_folder:
        folder = controller.config.get("slide_folder", "")
        if folder and os.path.isdir(folder):
            if IS_MACOS:
                import subprocess
                subprocess.Popen(["open", folder])
            elif IS_WINDOWS:
                os.startfile(folder)
            return True, ""
        return False, "请先设置幻灯片文件夹"
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

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
    existing_app = QGuiApplication.instance()
    QQuickStyle.setStyle("Basic")
    app = existing_app or QGuiApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))
    backend = Backend()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    if hasattr(engine, "setInitialProperties"):
        engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(QML_PATH))
    if not engine.rootObjects():
        sys.exit(1)
    if args.hide:
        engine.rootObjects()[0].hide()
    if args.about:
        QTimer.singleShot(0, backend.requestAbout.emit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
