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
from PySide6.QtCore import QTimer, Qt
from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QPalette, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QListView,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

import random_copy
from app_config import (
    APP_NAME,
    IS_MACOS,
    IS_WINDOWS,
    UI_ACCENT,
    UI_ACCENT_SOFT,
    UI_BG,
    UI_BORDER,
    UI_BORDER_SOFT,
    UI_MUTED,
    UI_PANEL,
    UI_SURFACE,
    UI_TEXT,
)
from macos_desktop_context import stop_desktop_context_menu
from macos_menu_bar import COMMAND_FILE, start_menu_bar, stop_menu_bar
from macos_video_wallpaper import start_video_wallpaper as start_macos_video, stop_video_wallpaper as stop_macos_video
from platform_support import get_current_wallpaper_platform, set_wallpaper_platform
from windows_video_wallpaper import start_video_wallpaper as start_windows_video, stop_video_wallpaper as stop_windows_video


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "shezhi.json")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".gif")


def log(message):
    print(message)


def default_config():
    return {
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


def show_error(parent, title, message):
    QMessageBox.warning(parent, title, message)


def macos_service_path(name):
    return os.path.expanduser(os.path.join("~/Library/Services", name))


def create_macos_workflow_service(service_dir, title, shell_script, input_type="com.apple.Automator.nothing",
                                  send_file_types=None):
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
        "actions": [
            {
                "action": {
                    "AMAccepts": {"Container": "List", "Optional": True, "Types": ["com.apple.cocoa.string"]},
                    "AMActionVersion": "2.0.3",
                    "AMApplication": ["Automator"],
                    "AMParameterProperties": {
                        "COMMAND_STRING": {},
                        "CheckedForUserDefaultShell": {},
                        "inputMethod": {},
                        "shell": {},
                        "source": {},
                    },
                    "AMProvides": {"Container": "List", "Types": ["com.apple.cocoa.string"]},
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
                    "CFBundleVersion": "2.0.3",
                    "CanShowSelectedItemsWhenRun": False,
                    "CanShowWhenRun": True,
                    "Category": ["AMCategoryUtilities"],
                    "Class Name": "RunShellScriptAction",
                    "InputUUID": str(uuid.uuid4()).upper(),
                    "Keywords": ["Shell", "Script", "Command", "Run", "Unix"],
                    "OutputUUID": str(uuid.uuid4()).upper(),
                    "UUID": str(uuid.uuid4()).upper(),
                    "UnlocalizedApplications": ["Automator"],
                    "arguments": {
                        "0": {"default value": 1 if send_file_types else 0, "name": "inputMethod", "required": "0", "type": "0", "uuid": "0"},
                        "1": {"default value": shell_script, "name": "source", "required": "0", "type": "0", "uuid": "1"},
                        "2": {"default value": False, "name": "CheckedForUserDefaultShell", "required": "0", "type": "0", "uuid": "2"},
                        "3": {"default value": "", "name": "COMMAND_STRING", "required": "0", "type": "0", "uuid": "3"},
                        "4": {"default value": "/bin/sh", "name": "shell", "required": "0", "type": "0", "uuid": "4"},
                    },
                    "isViewVisible": True,
                    "location": "0.000000:0.000000",
                    "nibPath": "/System/Library/Automator/Run Shell Script.action/Contents/Resources/en.lproj/main.nib",
                }
            }
        ],
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


MACOS_CONTEXT_ACTIONS = [
    ("previous", "ShangBackground - 上一张壁纸", "--previous", "ctx_last_wallpaper", True),
    ("next", "ShangBackground - 下一张壁纸", "--next", "ctx_next_wallpaper", True),
    ("random", "ShangBackground - 随机壁纸", "--random", "ctx_random_wallpaper", True),
    ("jump", "ShangBackground - 跳转到壁纸", "--jump-to-wallpaper", "ctx_jump_to_wallpaper", True),
    ("show", "ShangBackground - 显示主界面", "--show", "ctx_personalize", False),
]


def create_macos_action_service(action, title, arg):
    service_dir = macos_service_path(f"ShangBackground {action}.workflow")
    python_executable = shlex.quote(os.path.abspath(sys.executable))
    target_script = shlex.quote(os.path.abspath(sys.argv[0]))
    shell_script = f"{python_executable} {target_script} {arg} >/dev/null 2>&1 &\n"
    create_macos_workflow_service(service_dir, title, shell_script)


def remove_macos_service(service_dir):
    if os.path.exists(service_dir):
        shutil.rmtree(service_dir)


def sync_macos_context_services(config):
    stop_desktop_context_menu()
    slide_mode = config.get("mode") == "幻灯片放映"
    for action, title, arg, config_key, requires_slide in MACOS_CONTEXT_ACTIONS:
        enabled = config.get(config_key, True if action in ("next", "show") else False)
        if requires_slide and not slide_mode:
            enabled = False
        service_dir = macos_service_path(f"ShangBackground {action}.workflow")
        if enabled:
            create_macos_action_service(action, title, arg)
        else:
            remove_macos_service(service_dir)

    file_service = macos_service_path("Set As Wallpaper.workflow")
    if config.get("ctx_set_wallpaper", False):
        python_executable = shlex.quote(os.path.abspath(sys.executable))
        target_script = shlex.quote(os.path.abspath(sys.argv[0]))
        shell_script = (
            'for f in "$@"; do\n'
            '  if [ -f "$f" ]; then\n'
            f'    {python_executable} {target_script} --set-wallpaper "$f"\n'
            '  fi\n'
            'done\n'
        )
        create_macos_workflow_service(
            file_service,
            "设为壁纸",
            shell_script,
            input_type="public.image",
            send_file_types=["public.image"],
        )
    else:
        remove_macos_service(file_service)


HOTKEY_ITEMS = {
    "previous": "上一张壁纸",
    "next": "下一张壁纸",
    "random": "随机壁纸",
    "show": "打开设置主界面",
    "jump": "跳转到壁纸",
}
DEFAULT_HOTKEYS = {
    "previous": "u",
    "next": "n",
    "random": "3",
    "show": "x",
    "jump": "v",
}
TRAY_ACTION_LABELS = {
    "show": "打开设置主界面",
    "previous": "上一张壁纸",
    "next": "下一张壁纸",
    "random": "随机壁纸",
    "about": "关于作者",
    "jump": "跳转到壁纸",
    "exit": "退出程序",
}


def normalize_hotkey(sequence):
    text = sequence.toString().strip() if hasattr(sequence, "toString") else str(sequence).strip()
    if not text:
        return ""
    replacements = {
        "Ctrl": "ctrl",
        "Control": "ctrl",
        "Alt": "alt",
        "Shift": "shift",
        "Meta": "win",
        "Cmd": "win",
        "Command": "win",
        "Return": "enter",
        "Del": "delete",
        "PgUp": "pageup",
        "PgDown": "pagedown",
        "Space": "space",
    }
    parts = [part.strip() for part in text.replace(",", "+").split("+") if part.strip()]
    normalized = []
    for part in parts:
        normalized.append(replacements.get(part, part.lower()))
    return "+".join(normalized)


def display_hotkey(value, fallback=""):
    value = value or fallback
    if not value:
        return "未设置"
    names = {
        "ctrl": "Ctrl",
        "alt": "Alt",
        "shift": "Shift",
        "win": "Cmd" if IS_MACOS else "Win",
        "enter": "Enter",
        "space": "Space",
        "delete": "Delete",
        "pageup": "PageUp",
        "pagedown": "PageDown",
    }
    return "+".join(names.get(part, part.upper() if len(part) == 1 else part.title()) for part in value.split("+"))


class RoundedComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView(self)
        view.setObjectName("comboPopupView")
        view.setFrameShape(QFrame.NoFrame)
        view.setEditTriggers(QListView.NoEditTriggers)
        view.setMouseTracking(True)
        view.setAutoFillBackground(True)
        view.viewport().setObjectName("comboPopupViewport")
        view.viewport().setAutoFillBackground(True)
        self.setView(view)
        self.apply_popup_surface()

    def apply_popup_surface(self):
        palette = self.view().palette()
        palette.setColor(QPalette.Base, QColor(UI_PANEL))
        palette.setColor(QPalette.Window, QColor(UI_PANEL))
        palette.setColor(QPalette.Text, QColor(UI_TEXT))
        palette.setColor(QPalette.Highlight, QColor(UI_ACCENT_SOFT))
        palette.setColor(QPalette.HighlightedText, QColor(UI_TEXT))
        self.view().setPalette(palette)
        self.view().viewport().setPalette(palette)
        self.view().setStyleSheet(f"""
            QListView#comboPopupView {{
                color: {UI_TEXT};
                background: {UI_PANEL};
                background-color: {UI_PANEL};
                border: 1px solid {UI_BORDER};
                border-radius: 16px;
                padding: 8px;
                outline: 0;
            }}
            QListView#comboPopupView::item {{
                background: transparent;
                min-height: 30px;
                padding: 6px 10px;
                border-radius: 10px;
                color: {UI_TEXT};
            }}
            QListView#comboPopupView::item:hover,
            QListView#comboPopupView::item:selected {{
                background: {UI_ACCENT_SOFT};
                color: {UI_TEXT};
            }}
        """)
        self.view().viewport().setStyleSheet(f"background: {UI_PANEL}; background-color: {UI_PANEL};")

    def showPopup(self):
        self.apply_popup_surface()
        super().showPopup()
        popup = self.view().window()
        popup.setObjectName("comboPopupWindow")
        popup.setAttribute(Qt.WA_TranslucentBackground, True)
        popup.setStyleSheet("background: transparent; border: none;")
        self.apply_popup_surface()


class HotkeySettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("设置快捷键")
        self.setFixedSize(760, 400)
        self.hotkeys = {key: config.get(f"hotkey_{key}", "") for key in HOTKEY_ITEMS}
        self.current_key = "next"
        self.build_ui()
        self.load_current()

    def build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QFrame()
        side.setObjectName("dialogSide")
        side.setFixedWidth(150)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(18, 38, 18, 18)
        title = QLabel("全局快捷键")
        title.setObjectName("dialogSideTitle")
        desc = QLabel("设置全局快捷键\n快速切换壁纸")
        desc.setObjectName("muted")
        desc.setAlignment(Qt.AlignCenter)
        side_layout.addWidget(title, 0, Qt.AlignHCenter)
        side_layout.addSpacing(10)
        side_layout.addWidget(desc)
        side_layout.addStretch(1)
        outer.addWidget(side)

        content = QFrame()
        content.setObjectName("dialogContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 22, 22, 18)
        heading = QLabel("全局快捷键设置")
        heading.setObjectName("dialogTitle")
        layout.addWidget(heading)

        body = QHBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("settingsList")
        self.list_widget.setFixedWidth(180)
        for key, label in HOTKEY_ITEMS.items():
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self.list_widget.addItem(item)
            if key == self.current_key:
                self.list_widget.setCurrentItem(item)
        self.list_widget.currentItemChanged.connect(self.on_select)
        body.addWidget(self.list_widget)

        form_wrap = QFrame()
        form_layout = QVBoxLayout(form_wrap)
        form_layout.setContentsMargins(12, 0, 0, 0)
        self.current_label = QLabel("")
        self.current_label.setObjectName("sectionTitle")
        form_layout.addWidget(self.current_label)
        form = QFormLayout()
        self.current_value = QLineEdit()
        self.current_value.setReadOnly(True)
        self.key_edit = QKeySequenceEdit()
        form.addRow("当前快捷键:", self.current_value)
        form.addRow("新快捷键:", self.key_edit)
        form_layout.addLayout(form)
        clear_btn = QPushButton("清除当前快捷键")
        clear_btn.clicked.connect(self.clear_current)
        form_layout.addWidget(clear_btn, 0, Qt.AlignLeft)
        form_layout.addStretch(1)
        body.addWidget(form_wrap, 1)
        layout.addLayout(body, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        outer.addWidget(content, 1)

    def on_select(self, current, previous):
        if previous is not None:
            old_key = previous.data(Qt.UserRole)
            new_value = normalize_hotkey(self.key_edit.keySequence())
            if new_value:
                self.hotkeys[old_key] = new_value
        if current is not None:
            self.current_key = current.data(Qt.UserRole)
        self.load_current()

    def load_current(self):
        value = self.hotkeys.get(self.current_key, "")
        self.current_label.setText(f"当前功能：{HOTKEY_ITEMS[self.current_key]}")
        self.current_value.setText(display_hotkey(value, DEFAULT_HOTKEYS.get(self.current_key, "")))
        self.key_edit.clear()

    def clear_current(self):
        self.hotkeys[self.current_key] = ""
        self.load_current()

    def accept(self):
        new_value = normalize_hotkey(self.key_edit.keySequence())
        if new_value:
            self.hotkeys[self.current_key] = new_value
        for key, value in self.hotkeys.items():
            self.config[f"hotkey_{key}"] = value
        save_config(self.config)
        super().accept()


class TraySettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("托盘设置")
        self.setFixedSize(720, 520)
        self.build_ui()

    def build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QFrame()
        side.setObjectName("dialogSide")
        side.setFixedWidth(150)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(18, 38, 18, 18)
        title = QLabel("托盘功能")
        title.setObjectName("dialogSideTitle")
        desc = QLabel("设置菜单栏/托盘\n菜单项和行为\n\n拖拽排序\n勾选启用")
        desc.setObjectName("muted")
        desc.setAlignment(Qt.AlignCenter)
        side_layout.addWidget(title, 0, Qt.AlignHCenter)
        side_layout.addSpacing(10)
        side_layout.addWidget(desc)
        side_layout.addStretch(1)
        outer.addWidget(side)

        content = QFrame()
        content.setObjectName("dialogContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 18)
        heading = QLabel("托盘图标设置" if not IS_MACOS else "菜单栏常驻设置")
        heading.setObjectName("dialogTitle")
        layout.addWidget(heading)

        click_row = QHBoxLayout()
        click_row.addWidget(QLabel("单击托盘图标:"))
        self.click_combo = RoundedComboBox()
        self.click_combo.addItems([TRAY_ACTION_LABELS["next"]])
        self.click_combo.setCurrentText(TRAY_ACTION_LABELS["next"])
        self.click_combo.setEnabled(False)
        click_row.addWidget(self.click_combo)
        tip = QLabel("单击动作暂固定为下一张壁纸")
        tip.setObjectName("muted")
        click_row.addWidget(tip)
        click_row.addStretch(1)
        layout.addLayout(click_row)

        label = QLabel("右键菜单项 / 主菜单项")
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("settingsList")
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        saved = self.config.get("tray_menu_items") or list(TRAY_ACTION_LABELS.keys())
        ordered = [action for action in saved if action in TRAY_ACTION_LABELS]
        ordered.extend(action for action in TRAY_ACTION_LABELS if action not in ordered)
        enabled = set(saved)
        for action in ordered:
            item = QListWidgetItem(TRAY_ACTION_LABELS[action])
            item.setData(Qt.UserRole, action)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
            item.setCheckState(Qt.Checked if action in enabled else Qt.Unchecked)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)

        buttons_row = QHBoxLayout()
        reset = QPushButton("恢复默认")
        reset.clicked.connect(self.reset_default)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存设置")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons_row.addWidget(reset)
        buttons_row.addStretch(1)
        buttons_row.addWidget(buttons)
        layout.addLayout(buttons_row)
        outer.addWidget(content, 1)

    def reset_default(self):
        self.list_widget.clear()
        defaults = ["show", "previous", "next", "random", "about", "jump", "exit"]
        for action in defaults:
            item = QListWidgetItem(TRAY_ACTION_LABELS[action])
            item.setData(Qt.UserRole, action)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
            item.setCheckState(Qt.Checked)
            self.list_widget.addItem(item)

    def accept(self):
        enabled = []
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item.checkState() == Qt.Checked:
                enabled.append(item.data(Qt.UserRole))
        self.config["tray_click_action"] = "next"
        self.config["tray_menu_items"] = enabled
        save_config(self.config)
        super().accept()


class TransitionSettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("过渡动画设置")
        self.setFixedSize(520, 390)
        self.build_ui()
        self.update_visibility()

    def build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QFrame()
        side.setObjectName("dialogSide")
        side.setFixedWidth(150)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(18, 38, 18, 18)
        title = QLabel("过渡动画")
        title.setObjectName("dialogSideTitle")
        desc = QLabel("设置壁纸切换时\n使用的动画方式\n和播放参数")
        desc.setObjectName("muted")
        desc.setAlignment(Qt.AlignCenter)
        side_layout.addWidget(title, 0, Qt.AlignHCenter)
        side_layout.addSpacing(10)
        side_layout.addWidget(desc)
        side_layout.addStretch(1)
        outer.addWidget(side)

        content = QFrame()
        content.setObjectName("dialogContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 18)
        form = QFormLayout()
        self.effect_combo = RoundedComboBox()
        self.effect_combo.addItems(["丝滑转场", "帧动画"])
        self.effect_combo.setCurrentText("帧动画" if self.config.get("transition_effect", "smooth") == "frame" else "丝滑转场")
        self.effect_combo.currentTextChanged.connect(self.update_visibility)

        self.smooth_combo = RoundedComboBox()
        self.smooth_map = {"fade": "渐显混合", "slide": "放映机", "scan": "滑入", "random": "随机转场"}
        self.smooth_reverse = {value: key for key, value in self.smooth_map.items()}
        self.smooth_combo.addItems(list(self.smooth_reverse.keys()))
        self.smooth_combo.setCurrentText(self.smooth_map.get(self.config.get("smooth_effect", "fade"), "渐显混合"))
        self.smooth_combo.currentTextChanged.connect(self.update_visibility)

        self.direction_combo = RoundedComboBox()
        self.direction_map = {"left": "← 向左", "right": "向右 →", "up": "↑ 向上", "down": "向下 ↓", "random": "随机方向"}
        self.direction_reverse = {value: key for key, value in self.direction_map.items()}
        self.direction_combo.addItems(list(self.direction_reverse.keys()))
        self.direction_combo.setCurrentText(self.direction_map.get(self.config.get("slide_direction", "right"), "向右 →"))

        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 10.0)
        self.duration_spin.setSingleStep(0.1)
        self.duration_spin.setSuffix(" 秒")
        self.duration_spin.setValue(float(self.config.get("transition_duration", 1.0)))

        self.frames_spin = QSpinBox()
        self.frames_spin.setRange(4, 30)
        self.frames_spin.setSuffix(" 帧")
        self.frames_spin.setValue(int(self.config.get("transition_frames", 12)))

        form.addRow("转场原理:", self.effect_combo)
        self.smooth_label = QLabel("转场效果:")
        form.addRow(self.smooth_label, self.smooth_combo)
        self.direction_label = QLabel("动画方向:")
        form.addRow(self.direction_label, self.direction_combo)
        form.addRow("持续时间:", self.duration_spin)
        self.frames_label = QLabel("帧数:")
        form.addRow(self.frames_label, self.frames_spin)
        layout.addLayout(form)
        layout.addStretch(1)

        buttons_row = QHBoxLayout()
        reset = QPushButton("恢复默认")
        reset.clicked.connect(self.reset_default)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons_row.addWidget(reset)
        buttons_row.addStretch(1)
        buttons_row.addWidget(buttons)
        layout.addLayout(buttons_row)
        outer.addWidget(content, 1)

    def update_visibility(self):
        smooth = self.effect_combo.currentText() == "丝滑转场"
        direction = smooth and self.smooth_combo.currentText() in ("放映机", "滑入")
        self.smooth_label.setVisible(smooth)
        self.smooth_combo.setVisible(smooth)
        self.direction_label.setVisible(direction)
        self.direction_combo.setVisible(direction)
        self.frames_label.setVisible(not smooth)
        self.frames_spin.setVisible(not smooth)

    def reset_default(self):
        self.effect_combo.setCurrentText("丝滑转场")
        self.smooth_combo.setCurrentText("渐显混合")
        self.direction_combo.setCurrentText("向右 →")
        self.duration_spin.setValue(1.0)
        self.frames_spin.setValue(12)

    def accept(self):
        self.config["transition_effect"] = "frame" if self.effect_combo.currentText() == "帧动画" else "smooth"
        self.config["smooth_effect"] = self.smooth_reverse.get(self.smooth_combo.currentText(), "fade")
        self.config["slide_direction"] = self.direction_reverse.get(self.direction_combo.currentText(), "right")
        self.config["transition_duration"] = round(float(self.duration_spin.value()), 1)
        self.config["transition_frames"] = int(self.frames_spin.value())
        save_config(self.config)
        super().accept()


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
            log(f"{operation}: {os.path.basename(path)}")
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
        if current in self.slide_images:
            idx = (self.slide_images.index(current) + 1) % len(self.slide_images)
        else:
            idx = 0
        return self.set_wallpaper(self.slide_images[idx], "下一张")

    def random_wallpaper(self):
        folder = self.config.get("slide_folder", "")
        all_images = random_copy.get_all_images_with_copies(folder) if folder else []
        if not all_images:
            all_images = image_files(folder)
        if not all_images:
            return False, "请先设置幻灯片文件夹"
        current = self.config.get("current_wallpaper", "")
        available = [p for p in all_images if p != current] or all_images
        return self.set_wallpaper(random.choice(available), "随机壁纸")

    def apply_solid(self):
        return self._render_color_wallpaper(self.config.get("solid_color", "#4facfe"))

    def apply_gradient(self):
        width, height = 1920, 1080
        color1 = self.config.get("solid_color", "#4facfe")
        color2 = self.config.get("gradient_color2", "#00f2fe")
        img = Image.new("RGB", (width, height), color1)
        draw = ImageDraw.Draw(img)
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        for x in range(width):
            t = x / max(1, width - 1)
            draw.line(
                [(x, 0), (x, height)],
                fill=(int(r1 * (1 - t) + r2 * t), int(g1 * (1 - t) + g2 * t), int(b1 * (1 - t) + b2 * t)),
            )
        path = os.path.join(tempfile.gettempdir(), "shangbackground_gradient.bmp")
        img.save(path)
        return self.set_wallpaper(path, "渐变壁纸", skip_history=True)

    def _render_color_wallpaper(self, color):
        img = Image.new("RGB", (1920, 1080), color)
        path = os.path.join(tempfile.gettempdir(), "shangbackground_solid.bmp")
        img.save(path)
        return self.set_wallpaper(path, "纯色壁纸", skip_history=True)

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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.controller = WallpaperController(self.config)
        self.slide_timer = QTimer(self)
        self.slide_timer.timeout.connect(self.slide_next)
        self.command_timer = QTimer(self)
        self.command_timer.timeout.connect(self.poll_external_command)
        self.command_seen_at = 0
        self.tray = None
        self.setWindowTitle(APP_NAME)
        self.resize(980, 560)
        self.setMinimumSize(920, 520)
        self.build_ui()
        self.refresh_from_config()
        self.sync_context_services()
        self.setup_tray()
        self.register_global_hotkeys()
        self.command_timer.start(500)
        if self.config.get("mode") == "幻灯片放映" and self.config.get("slide_folder"):
            self.start_slideshow()

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root.setObjectName("root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(20, 16, 20, 16)
        root_layout.setSpacing(0)

        main_container = QFrame()
        main_container.setObjectName("mainContainer")
        root_layout.addWidget(main_container, 1)

        outer = QHBoxLayout(main_container)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(18)

        self.preview_panel = QFrame()
        self.preview_panel.setObjectName("panel")
        self.preview_panel.setFixedWidth(400)
        left = QVBoxLayout(self.preview_panel)
        left.setContentsMargins(12, 12, 12, 12)
        left.setSpacing(0)
        self.preview = QLabel("暂无预览")
        self.preview.setObjectName("preview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedHeight(250)
        left.addWidget(self.preview)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 20, 0, 0)
        btn_row.setSpacing(8)
        for text, slot in [
            ("上一张", self.handle_previous),
            ("下一张", self.handle_next),
            ("随机", self.handle_random),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        left.addLayout(btn_row)

        self.status = QLabel("就绪")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        left.addSpacing(8)
        left.addWidget(self.status)

        self.build_utility_section(left)
        left.addStretch(1)

        self.settings_panel = QFrame()
        self.settings_panel.setObjectName("panel")
        self.settings_panel.setFixedWidth(500)
        right = QVBoxLayout(self.settings_panel)
        right.setContentsMargins(12, 12, 12, 12)
        right.setSpacing(0)

        mode_frame = QFrame()
        mode_frame.setObjectName("plainSection")
        mode_layout = QVBoxLayout(mode_frame)
        mode_layout.setContentsMargins(0, 10, 0, 16)
        mode_layout.setSpacing(6)
        mode_label = QLabel("背景模式")
        mode_label.setObjectName("modeTitle")
        self.mode_combo = RoundedComboBox()
        self.mode_combo.addItems(["幻灯片放映", "图片", "视频", "纯色", "渐变"])
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        self.mode_combo.setFixedWidth(220)
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_combo, 0, Qt.AlignLeft)
        right.addWidget(mode_frame)

        self.stack_area = QScrollArea()
        self.stack_area.setWidgetResizable(True)
        self.stack_area.setFrameShape(QFrame.NoFrame)
        self.form = QWidget()
        self.form_layout = QVBoxLayout(self.form)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setSpacing(12)
        self.stack_area.setWidget(self.form)
        right.addWidget(self.stack_area, 1)

        self.build_slideshow_section()
        self.build_image_section()
        self.build_video_section()
        self.build_color_section()
        self.build_context_section()

        apply_btn = QPushButton("应用当前设置")
        apply_btn.setObjectName("primary")
        apply_btn.clicked.connect(self.apply_current_mode)
        apply_btn.setFixedWidth(140)
        right.addWidget(apply_btn)

        outer.addWidget(self.preview_panel)
        outer.addWidget(self.settings_panel)
        self.setStyleSheet(self.stylesheet())

    def section(self, title):
        box = QFrame()
        box.setObjectName("plainSection")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
        self.form_layout.addWidget(box)
        return box, layout

    def make_row(self, label_text, label_width=82):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(label_width)
        row.addWidget(label)
        return row

    def build_utility_section(self, parent_layout):
        util = QFrame()
        util.setObjectName("plainSection")
        layout = QVBoxLayout(util)
        layout.setContentsMargins(0, 20, 0, 0)
        layout.setSpacing(7)
        title = QLabel("实用设置")
        title.setObjectName("utilityTitle")
        layout.addWidget(title)

        self.auto_start_check = QCheckBox("开机自启动")
        self.auto_start_check.setChecked(bool(self.config.get("auto_start", False)))
        self.auto_start_check.toggled.connect(lambda checked: self.update_config("auto_start", checked))
        layout.addWidget(self.auto_start_check)

        self.background_check = QCheckBox("能后台运行")
        self.background_check.toggled.connect(lambda checked: self.update_config("run_in_background", checked))
        layout.addWidget(self.background_check)

        tray_row = QHBoxLayout()
        tray_row.setContentsMargins(0, 0, 0, 0)
        self.tray_check = QCheckBox("菜单栏常驻" if IS_MACOS else "系统托盘图标")
        self.tray_check.toggled.connect(self.on_tray_enabled_changed)
        tray_btn = QPushButton("托盘功能设置")
        tray_btn.clicked.connect(self.open_tray_settings)
        tray_row.addWidget(self.tray_check, 1)
        tray_row.addWidget(tray_btn)
        layout.addLayout(tray_row)

        transition_row = QHBoxLayout()
        transition_row.setContentsMargins(0, 0, 0, 0)
        self.transition_check = QCheckBox("壁纸切换过渡动画")
        self.transition_check.setChecked(bool(self.config.get("transition_animation", True)))
        self.transition_check.toggled.connect(lambda checked: self.update_config("transition_animation", checked))
        transition_btn = QPushButton("过渡动画设置")
        transition_btn.clicked.connect(self.open_transition_settings)
        transition_row.addWidget(self.transition_check, 1)
        transition_row.addWidget(transition_btn)
        layout.addLayout(transition_row)

        quick_row = QHBoxLayout()
        quick_row.setContentsMargins(0, 0, 0, 0)
        quick_row.setSpacing(6)
        hotkey_btn = QPushButton("设置全局快捷键")
        hotkey_btn.clicked.connect(self.open_hotkey_settings)
        init_btn = QPushButton("初始化全局设置")
        init_btn.clicked.connect(lambda: show_error(self, "提示", "初始化设置将在 Qt 版后续迁移。"))
        exit_btn = QPushButton("一键关掉本工具")
        exit_btn.clicked.connect(QApplication.instance().quit)
        quick_row.addWidget(hotkey_btn)
        quick_row.addWidget(init_btn)
        quick_row.addWidget(exit_btn)
        layout.addLayout(quick_row)
        parent_layout.addWidget(util)

    def build_slideshow_section(self):
        self.slide_box, layout = self.section("幻灯片设置")
        row = self.make_row("壁纸相册:")
        self.folder_combo = RoundedComboBox()
        self.folder_combo.setFixedWidth(180)
        self.folder_combo.currentIndexChanged.connect(self.on_folder_combo_changed)
        self.folder_combo_paths = []
        browse = QPushButton("浏览")
        browse.clicked.connect(self.choose_folder)
        open_folder = QPushButton("打开文件夹")
        open_folder.clicked.connect(self.open_current_folder)
        row.addWidget(self.folder_combo)
        row.addWidget(browse)
        row.addWidget(open_folder)
        layout.addLayout(row)

        self.wallpaper_preview_row = QHBoxLayout()
        self.wallpaper_preview_row.setContentsMargins(0, 0, 0, 0)
        self.wallpaper_preview_row.setSpacing(8)
        self.wallpaper_preview_labels = []
        for _ in range(3):
            label = QLabel("预览")
            label.setObjectName("miniPreview")
            label.setAlignment(Qt.AlignCenter)
            label.setFixedSize(86, 54)
            self.wallpaper_preview_labels.append(label)
            self.wallpaper_preview_row.addWidget(label)
        self.wallpaper_preview_row.addStretch(1)
        layout.addLayout(self.wallpaper_preview_row)

        interval_row = self.make_row("切换间隔:")
        self.freq_combo = RoundedComboBox()
        self.freq_map = {
            "自定义时间": None,
            "5秒": 5,
            "10秒": 10,
            "30秒": 30,
            "1分钟": 60,
            "5分钟": 300,
            "30分钟": 1800,
            "1小时": 3600,
            "6小时": 21600,
            "12小时": 43200,
            "1天": 86400,
            "2天": 172800,
            "1周": 604800,
            "1个月": 2592000,
            "6个月": 15552000,
            "1年": 31536000,
            "50年": 1576800000,
            "666年": 210000000,
        }
        self.freq_combo.addItems(list(self.freq_map.keys()))
        self.freq_combo.currentTextChanged.connect(self.on_frequency_changed)
        self.manual_check = QCheckBox("手动档")
        self.manual_check.toggled.connect(self.on_manual_changed)
        interval_row.addWidget(self.freq_combo)
        interval_row.addWidget(self.manual_check)
        interval_row.addStretch(1)
        layout.addLayout(interval_row)

        random_row = QHBoxLayout()
        random_row.setContentsMargins(0, 0, 0, 0)
        self.shuffle_check = QCheckBox("随机顺序")
        self.shuffle_check.toggled.connect(self.on_shuffle_changed)
        prob_btn = QPushButton("设置随机概率")
        prob_btn.clicked.connect(lambda: show_error(self, "提示", "随机概率设置将在 Qt 版后续迁移。"))
        random_row.addWidget(self.shuffle_check)
        random_row.addWidget(prob_btn)
        random_row.addStretch(1)
        layout.addLayout(random_row)

        fit_row = self.make_row("适应模式:")
        self.fit_combo = RoundedComboBox()
        self.fit_combo.addItems(["填充", "适应", "拉伸", "平铺", "居中"])
        self.fit_combo.currentTextChanged.connect(lambda value: self.update_config("fit_mode", value))
        fit_row.addWidget(self.fit_combo)
        fit_row.addStretch(1)
        layout.addLayout(fit_row)

    def on_tray_enabled_changed(self, checked):
        self.config["tray_icon"] = checked
        self.controller.save()
        self.refresh_tray()

    def open_tray_settings(self):
        dialog = TraySettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = load_config()
            self.controller.config = self.config
            self.refresh_tray()
            self.status.setText("菜单栏/托盘设置已保存")

    def open_transition_settings(self):
        dialog = TransitionSettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = load_config()
            self.controller.config = self.config
            self.transition_check.setChecked(bool(self.config.get("transition_animation", True)))
            self.status.setText("过渡动画设置已保存")

    def open_hotkey_settings(self):
        dialog = HotkeySettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = load_config()
            self.controller.config = self.config
            self.register_global_hotkeys()
            self.sync_context_services()
            self.refresh_tray()
            self.status.setText("全局快捷键设置已保存")

    def build_image_section(self):
        self.image_box, layout = self.section("图片设置")
        row = self.make_row("图片文件:")
        self.image_edit = QLineEdit()
        browse = QPushButton("选择图片")
        browse.clicked.connect(self.choose_image)
        row.addWidget(self.image_edit, 1)
        row.addWidget(browse)
        layout.addLayout(row)

        fit_row = self.make_row("适应模式:")
        self.image_fit_combo = RoundedComboBox()
        self.image_fit_combo.addItems(["填充", "适应", "拉伸", "平铺", "居中"])
        self.image_fit_combo.currentTextChanged.connect(lambda value: self.update_config("fit_mode", value))
        fit_row.addWidget(self.image_fit_combo)
        fit_row.addStretch(1)
        layout.addLayout(fit_row)

    def build_video_section(self):
        self.video_box, layout = self.section("视频壁纸设置")
        row = self.make_row("视频文件:")
        self.video_edit = QLineEdit()
        browse = QPushButton("选择视频")
        browse.clicked.connect(self.choose_video)
        row.addWidget(self.video_edit, 1)
        row.addWidget(browse)
        layout.addLayout(row)
        muted = QCheckBox("静音播放")
        muted.setChecked(self.config.get("video_muted", True))
        muted.toggled.connect(lambda checked: self.update_config("video_muted", checked))
        layout.addWidget(muted)
        button_row = QHBoxLayout()
        play = QPushButton("播放视频壁纸")
        play.clicked.connect(self.apply_current_mode)
        stop = QPushButton("停止视频壁纸")
        stop.clicked.connect(self.controller.stop_video)
        button_row.addWidget(play)
        button_row.addWidget(stop)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        tip = QLabel("视频壁纸会使用独立播放器，窗口不接收鼠标事件。")
        tip.setObjectName("muted")
        layout.addWidget(tip)

    def build_color_section(self):
        self.color_box, layout = self.section("颜色设置")
        self.color1_row = self.color_row("起始颜色:", "solid_color", self.choose_color)
        self.color2_row = self.color_row("结束颜色:", "gradient_color2", self.choose_color)
        layout.addLayout(self.color1_row)
        layout.addLayout(self.color2_row)

        angle_row = self.make_row("渐变角度:")
        self.angle_slider = QSlider(Qt.Horizontal)
        self.angle_slider.setRange(0, 180)
        self.angle_slider.valueChanged.connect(self.on_angle_changed)
        self.angle_label = QLabel("0 度")
        self.angle_label.setFixedWidth(54)
        angle_row.addWidget(self.angle_slider, 1)
        angle_row.addWidget(self.angle_label)
        layout.addLayout(angle_row)

        type_row = self.make_row("渐变类型:")
        self.gradient_type_combo = RoundedComboBox()
        self.gradient_type_combo.addItems(["linear", "radial", "diagonal"])
        self.gradient_type_combo.currentTextChanged.connect(lambda value: self.update_config("gradient_type", value))
        type_row.addWidget(self.gradient_type_combo)
        type_row.addStretch(1)
        layout.addLayout(type_row)

        preset_label = QLabel("预设颜色:")
        preset_label.setObjectName("fieldLabel")
        layout.addWidget(preset_label)
        grid = QGridLayout()
        grid.setSpacing(7)
        presets = [
            ("#667eea", "#764ba2"), ("#4facfe", "#00f2fe"), ("#f093fb", "#f5576c"),
            ("#43e97b", "#38f9d7"), ("#fa709a", "#fee140"), ("#a18cd1", "#fbc2eb"),
            ("#ff9a9e", "#fecfef"), ("#84fab0", "#8fd3f4"), ("#ffe259", "#ffa751"),
            ("#b224ef", "#7579ff"),
        ]
        for idx, (first, second) in enumerate(presets):
            swatch = QPushButton("")
            swatch.setObjectName("swatch")
            swatch.setStyleSheet(f"background: {first}; border: 1px solid {UI_BORDER}; border-radius: 10px;")
            swatch.clicked.connect(lambda checked=False, a=first, b=second: self.set_preset_gradient(a, b))
            grid.addWidget(swatch, idx // 5, idx % 5)
        layout.addLayout(grid)

        solid_row = self.make_row("纯色:")
        self.solid_btn = QPushButton("选择主色")
        self.solid_btn.clicked.connect(lambda: self.choose_color("solid_color"))
        solid_row.addWidget(self.solid_btn)
        solid_row.addStretch(1)
        layout.addLayout(solid_row)

    def color_row(self, label, key, picker):
        row = self.make_row(label)
        edit = QLineEdit(self.config.get(key, "#000000"))
        edit.setFixedWidth(100)
        edit.textChanged.connect(lambda value, k=key: self.update_config(k, value))
        swatch = QPushButton("")
        swatch.setObjectName("colorSwatch")
        swatch.setFixedSize(34, 28)
        swatch.clicked.connect(lambda checked=False, k=key: picker(k))
        setattr(self, f"{key}_edit", edit)
        setattr(self, f"{key}_swatch", swatch)
        row.addWidget(edit)
        row.addWidget(swatch)
        row.addStretch(1)
        return row

    def build_context_section(self):
        self.context_box, layout = self.section("右键菜单设置")
        labels = self.context_labels()
        self.ctx_prev_check = self.config_check(labels["previous"], "ctx_last_wallpaper")
        self.ctx_next_check = self.config_check(labels["next"], "ctx_next_wallpaper")
        self.ctx_random_check = self.config_check(labels["random"], "ctx_random_wallpaper")
        self.ctx_jump_check = self.config_check(labels["jump"], "ctx_jump_to_wallpaper")
        self.ctx_file_check = self.config_check(labels["file"], "ctx_set_wallpaper")
        self.ctx_personalize_check = self.config_check(labels["personalize"], "ctx_personalize")
        for check in [
            self.ctx_prev_check,
            self.ctx_next_check,
            self.ctx_random_check,
            self.ctx_jump_check,
            self.ctx_file_check,
            self.ctx_personalize_check,
        ]:
            check.setWordWrap(True) if hasattr(check, "setWordWrap") else None
            layout.addWidget(check)

    def context_labels(self):
        if IS_MACOS:
            return {
                "previous": "添加【Finder右键服务 → 上一张壁纸】",
                "next": "添加【Finder右键服务 → 下一张壁纸】",
                "random": "添加【Finder右键服务 → 随机壁纸】",
                "jump": "添加【Finder右键服务 → 跳转到壁纸】",
                "file": "添加【Finder文件右键 → 设为壁纸】",
                "personalize": "添加【Finder右键服务 → 显示主界面】",
            }
        return {
            "previous": "添加【桌面右键 → 上一个桌面背景】",
            "next": "添加【桌面右键 → 下一个桌面背景】",
            "random": "添加【桌面右键 → 随机一个桌面背景】",
            "jump": "添加【桌面右键 → 跳转到壁纸】",
            "file": "添加【Finder右键 → 设为壁纸】",
            "personalize": "添加【桌面右键 → 个性化设置】",
        }

    def config_check(self, text, key):
        check = QCheckBox(text)
        check.setChecked(bool(self.config.get(key, False)))
        check.toggled.connect(lambda checked, k=key: self.on_context_toggle(k, checked))
        return check

    def on_context_toggle(self, key, checked):
        self.config[key] = checked
        self.controller.save()
        self.sync_context_services()

    def sync_context_services(self):
        if not IS_MACOS:
            return
        try:
            sync_macos_context_services(self.config)
            self.status.setText("Finder 右键服务已同步")
        except Exception as e:
            self.status.setText(f"Finder 右键服务同步失败: {e}")

    def stylesheet(self):
        return f"""
        QWidget {{
            color: {UI_TEXT};
            background: transparent;
            font-family: "PingFang SC", "Microsoft YaHei";
            font-size: 13px;
        }}
        QDialog {{
            background: {UI_PANEL};
        }}
        QWidget#root {{ background: {UI_BG}; }}
        QFrame#mainContainer {{
            background: {UI_PANEL};
            border: 1px solid {UI_BORDER_SOFT};
            border-radius: 24px;
        }}
        QFrame#panel {{
            background: {UI_PANEL};
            border: 1px solid {UI_BORDER_SOFT};
            border-radius: 18px;
        }}
        QFrame#plainSection {{
            background: transparent;
            border: none;
        }}
        QFrame#dialogSide {{
            background: {UI_ACCENT_SOFT};
            border: none;
        }}
        QFrame#dialogContent {{
            background: {UI_PANEL};
            border: none;
        }}
        QLabel {{
            color: {UI_TEXT};
            background: transparent;
        }}
        QLabel#title {{
            color: {UI_TEXT};
            font-size: 22px;
            font-weight: 700;
        }}
        QLabel#modeTitle {{
            color: {UI_TEXT};
            font-size: 16px;
            font-weight: 500;
        }}
        QLabel#utilityTitle {{
            color: {UI_TEXT};
            font-size: 15px;
            font-weight: 700;
        }}
        QLabel#dialogSideTitle {{
            color: {UI_TEXT};
            font-size: 18px;
            font-weight: 700;
        }}
        QLabel#dialogTitle {{
            color: {UI_TEXT};
            font-size: 20px;
            font-weight: 700;
        }}
        QLabel#sectionTitle {{
            color: {UI_TEXT};
            font-weight: 700;
            font-size: 14px;
        }}
        QLabel#fieldLabel {{
            color: {UI_TEXT};
            font-weight: 500;
        }}
        QLabel#muted {{ color: {UI_MUTED}; }}
        QLabel#preview {{
            background: {UI_SURFACE};
            border: 1px solid {UI_BORDER_SOFT};
            border-radius: 18px;
            color: {UI_TEXT};
            font-weight: 600;
        }}
        QLabel#miniPreview {{
            background: {UI_SURFACE};
            border: 1px solid {UI_BORDER_SOFT};
            border-radius: 10px;
            color: {UI_MUTED};
            font-size: 12px;
        }}
        QPushButton {{
            color: {UI_TEXT};
            background: {UI_PANEL};
            border: 1px solid {UI_BORDER};
            border-radius: 12px;
            padding: 8px 14px;
            min-height: 18px;
        }}
        QPushButton#swatch {{
            min-width: 34px;
            max-width: 34px;
            min-height: 24px;
            max-height: 24px;
            padding: 0;
        }}
        QPushButton#colorSwatch {{
            padding: 0;
        }}
        QPushButton:hover {{ background: {UI_SURFACE}; }}
        QPushButton:pressed {{ background: #E4E7EC; }}
        QPushButton:disabled {{
            color: #98A2B3;
            background: {UI_SURFACE};
            border-color: {UI_BORDER_SOFT};
        }}
        QPushButton#primary {{
            background: {UI_ACCENT};
            border-color: {UI_ACCENT};
            color: white;
            font-weight: 700;
        }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit {{
            color: {UI_TEXT};
            background: {UI_PANEL};
            border: 1px solid {UI_BORDER};
            border-radius: 12px;
            padding: 8px 12px;
            min-height: 20px;
            selection-background-color: {UI_ACCENT_SOFT};
            selection-color: {UI_TEXT};
        }}
        QComboBox {{
            combobox-popup: 0;
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QKeySequenceEdit:focus {{
            border-color: {UI_ACCENT};
        }}
        QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {{
            border: none;
            width: 26px;
        }}
        QComboBox QAbstractItemView {{
            color: {UI_TEXT};
            background: {UI_PANEL};
            border: 1px solid {UI_BORDER};
            border-radius: 16px;
            padding: 8px;
            selection-background-color: {UI_ACCENT_SOFT};
            selection-color: {UI_TEXT};
            outline: 0;
        }}
        QListView#comboPopupView {{
            color: {UI_TEXT};
            background: {UI_PANEL};
            background-color: {UI_PANEL};
            border: 1px solid {UI_BORDER};
            border-radius: 16px;
            padding: 8px;
            outline: 0;
        }}
        QListView#comboPopupView QWidget#comboPopupViewport {{
            background: {UI_PANEL};
            background-color: {UI_PANEL};
        }}
        QListView#comboPopupView::item {{
            background: transparent;
            min-height: 30px;
            padding: 6px 10px;
            border-radius: 10px;
            color: {UI_TEXT};
        }}
        QListView#comboPopupView::item:hover,
        QListView#comboPopupView::item:selected {{
            background: {UI_ACCENT_SOFT};
            color: {UI_TEXT};
        }}
        QCheckBox {{
            color: {UI_TEXT};
            spacing: 8px;
            background: transparent;
        }}
        QCheckBox:disabled {{ color: #98A2B3; }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 6px;
            border: 1px solid {UI_BORDER};
            background: {UI_PANEL};
        }}
        QCheckBox::indicator:checked {{
            background: {UI_ACCENT};
            border-color: {UI_ACCENT};
        }}
        QSlider::groove:horizontal {{
            height: 6px;
            background: {UI_BORDER_SOFT};
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            width: 18px;
            height: 18px;
            margin: -7px 0;
            border-radius: 9px;
            background: {UI_ACCENT};
            border: 2px solid white;
        }}
        QScrollArea {{ background: transparent; }}
        QScrollArea > QWidget > QWidget {{ background: transparent; }}
        QListWidget#settingsList {{
            color: {UI_TEXT};
            background: {UI_PANEL};
            border: 1px solid {UI_BORDER_SOFT};
            border-radius: 14px;
            padding: 6px;
            outline: 0;
        }}
        QListWidget#settingsList::item {{
            background: transparent;
            border-radius: 10px;
            padding: 8px;
            min-height: 24px;
        }}
        QListWidget#settingsList::item:hover,
        QListWidget#settingsList::item:selected {{
            background: {UI_ACCENT_SOFT};
            color: {UI_TEXT};
        }}
        QMenu {{
            color: {UI_TEXT};
            background: {UI_PANEL};
            border: 1px solid {UI_BORDER_SOFT};
            border-radius: 10px;
            padding: 6px;
        }}
        QMenu::item {{
            color: {UI_TEXT};
            background: transparent;
            padding: 8px 22px;
            border-radius: 8px;
        }}
        QMenu::item:selected {{
            background: {UI_ACCENT_SOFT};
            color: {UI_TEXT};
        }}
        QMessageBox, QFileDialog {{
            color: {UI_TEXT};
            background: {UI_PANEL};
        }}
        """

    def refresh_from_config(self):
        self.mode_combo.setCurrentText(self.config.get("mode", "幻灯片放映"))
        self.update_folder_combo()
        self.image_edit.setText(self.config.get("single_image", ""))
        self.video_edit.setText(self.config.get("video_file", ""))
        self.set_frequency_display()
        self.manual_check.setChecked(bool(self.config.get("manual_mode", False)))
        self.shuffle_check.setChecked(bool(self.config.get("shuffle", False)))
        fit = self.config.get("fit_mode", "填充")
        self.fit_combo.setCurrentText(fit)
        self.image_fit_combo.setCurrentText(fit)
        self.angle_slider.setValue(int(self.config.get("gradient_angle", 0)))
        self.gradient_type_combo.setCurrentText(self.config.get("gradient_type", "linear"))
        self.update_color_controls()
        self.background_check.setChecked(bool(self.config.get("run_in_background", True)))
        self.tray_check.setChecked(bool(self.config.get("tray_icon", True)))
        self.update_sections()
        self.update_preview()
        self.update_wallpaper_previews()

    def update_sections(self):
        mode = self.mode_combo.currentText()
        self.slide_box.setVisible(mode == "幻灯片放映")
        self.image_box.setVisible(mode == "图片")
        self.video_box.setVisible(mode == "视频")
        self.color_box.setVisible(mode in ("纯色", "渐变"))
        for check in (self.ctx_prev_check, self.ctx_next_check, self.ctx_random_check, self.ctx_jump_check):
            check.setEnabled(mode == "幻灯片放映")
        self.ctx_file_check.setEnabled(True)
        self.ctx_personalize_check.setEnabled(True)

    def update_config(self, key, value):
        self.config[key] = value
        self.controller.save()

    def update_folder_combo(self):
        current = self.config.get("slide_folder", "")
        folders = []
        for folder in self.config.get("recent_folders", []):
            if folder and os.path.isdir(folder) and folder not in folders:
                folders.append(folder)
        if current and os.path.isdir(current) and current not in folders:
            folders.insert(0, current)

        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        self.folder_combo_paths = folders
        for folder in folders:
            self.folder_combo.addItem(os.path.basename(folder) or folder)
        if current in folders:
            self.folder_combo.setCurrentIndex(folders.index(current))
        self.folder_combo.blockSignals(False)

    def on_folder_combo_changed(self, index):
        if index < 0 or index >= len(self.folder_combo_paths):
            return
        path = self.folder_combo_paths[index]
        if not os.path.isdir(path):
            return
        self.config["slide_folder"] = path
        recent = [path] + [p for p in self.config.get("recent_folders", []) if p != path]
        self.config["recent_folders"] = recent[:10]
        self.controller.save()
        self.controller.reload_slide_images()
        self.update_wallpaper_previews()
        if self.config.get("mode") == "幻灯片放映" and not self.config.get("manual_mode", False):
            self.start_slideshow()

    def open_current_folder(self):
        folder = self.config.get("slide_folder", "")
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def update_wallpaper_previews(self):
        images = image_files(self.config.get("slide_folder", ""))[:3]
        for idx, label in enumerate(self.wallpaper_preview_labels):
            if idx >= len(images):
                label.clear()
                label.setText("请选择文件夹" if idx == 0 and not images else "")
                continue
            pixmap = QPixmap(images[idx])
            if pixmap.isNull():
                label.setText(os.path.basename(images[idx])[:8])
            else:
                label.setText("")
                label.setPixmap(pixmap.scaled(label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def set_frequency_display(self):
        seconds = int(self.config.get("slide_seconds", 300))
        label = next((name for name, value in self.freq_map.items() if value == seconds), "自定义时间")
        self.freq_combo.blockSignals(True)
        self.freq_combo.setCurrentText(label)
        self.freq_combo.blockSignals(False)

    def on_frequency_changed(self, label):
        if self.config.get("manual_mode", False):
            return
        value = self.freq_map.get(label)
        if value is None:
            return
        self.config["slide_seconds"] = value
        self.controller.save()
        self.start_slideshow()

    def on_manual_changed(self, checked):
        self.config["manual_mode"] = checked
        self.controller.save()
        self.freq_combo.setEnabled(not checked)
        if checked:
            self.stop_slideshow()
        elif self.config.get("mode") == "幻灯片放映":
            self.start_slideshow()

    def on_shuffle_changed(self, checked):
        self.config["shuffle"] = checked
        self.controller.save()
        self.controller.reload_slide_images()

    def on_angle_changed(self, value):
        self.angle_label.setText(f"{value} 度")
        self.config["gradient_angle"] = int(value)
        self.controller.save()

    def set_preset_gradient(self, color1, color2):
        self.config["solid_color"] = color1
        self.config["gradient_color2"] = color2
        self.controller.save()
        self.update_color_controls()
        if self.config.get("mode") == "渐变":
            self.apply_current_mode()

    def update_color_controls(self):
        for key in ("solid_color", "gradient_color2"):
            color = self.config.get(key, "#000000")
            edit = getattr(self, f"{key}_edit", None)
            swatch = getattr(self, f"{key}_swatch", None)
            if edit:
                edit.blockSignals(True)
                edit.setText(color)
                edit.blockSignals(False)
            if swatch:
                swatch.setStyleSheet(f"background: {color}; border: 1px solid {UI_BORDER}; border-radius: 8px;")

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择幻灯片文件夹", self.config.get("slide_folder", ""))
        if path:
            self.config["slide_folder"] = path
            recent = [path] + [p for p in self.config.get("recent_folders", []) if p != path]
            self.config["recent_folders"] = recent[:10]
            self.controller.save()
            self.update_folder_combo()
            self.controller.reload_slide_images()
            self.update_wallpaper_previews()
            if self.config.get("mode") == "幻灯片放映":
                self.start_slideshow()

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.jpg *.jpeg *.png *.bmp *.gif)")
        if path:
            self.image_edit.setText(path)
            self.config["single_image"] = path
            self.controller.save()
            if self.config.get("mode") == "图片":
                self.apply_current_mode()

    def choose_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择视频", "", "Videos (*.mp4 *.mov *.m4v *.avi *.mkv)")
        if path:
            self.video_edit.setText(path)
            self.config["video_file"] = path
            self.controller.save()
            if self.config.get("mode") == "视频":
                self.apply_current_mode()

    def choose_color(self, key):
        color = QColorDialog.getColor(QColor(self.config.get(key, "#4facfe")), self, "选择颜色")
        if color.isValid():
            self.config[key] = color.name()
            self.controller.save()
            self.update_color_controls()
            if self.config.get("mode") in ("纯色", "渐变"):
                self.apply_current_mode()

    def on_mode_changed(self, mode):
        self.config["mode"] = mode
        self.controller.save()
        self.update_sections()
        self.sync_context_services()
        if mode == "幻灯片放映":
            self.controller.stop_video()
            self.start_slideshow()
        else:
            self.stop_slideshow()
            if mode != "视频":
                self.controller.stop_video()

    def apply_current_mode(self):
        mode = self.config.get("mode")
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
        if not ok:
            show_error(self, "操作失败", err)
        self.status.setText(err if not ok else f"{mode} 已应用")
        self.update_preview()

    def update_preview(self):
        path = self.config.get("current_wallpaper", "")
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.preview.setText("")
                self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        try:
            current = get_current_wallpaper_platform()
            if current and os.path.exists(current):
                self.config["current_wallpaper"] = current
                self.controller.save()
                self.update_preview()
                return
        except Exception:
            pass
        self.preview.clear()
        self.preview.setText("暂无预览")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()

    def start_slideshow(self):
        if not self.config.get("slide_folder"):
            return
        self.controller.reload_slide_images()
        self.slide_timer.start(max(1, int(self.config.get("slide_seconds", 300))) * 1000)

    def stop_slideshow(self):
        self.slide_timer.stop()

    def slide_next(self):
        ok, err = self.controller.random_wallpaper() if self.config.get("shuffle") else self.controller.next_wallpaper()
        if not ok:
            self.status.setText(err)
            self.stop_slideshow()
        else:
            self.update_preview()

    def handle_previous(self):
        ok, err = self.controller.previous_wallpaper()
        if not ok:
            show_error(self, "提示", err)
        self.update_preview()

    def handle_next(self):
        ok, err = self.controller.next_wallpaper()
        if not ok:
            show_error(self, "提示", err)
        self.update_preview()

    def handle_random(self):
        ok, err = self.controller.random_wallpaper()
        if not ok:
            show_error(self, "提示", err)
        self.update_preview()

    def handle_show(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def handle_jump(self):
        import subprocess
        subprocess.Popen([sys.executable, os.path.abspath(sys.argv[0]), "--jump-to-wallpaper"])

    def handle_about(self):
        QMessageBox.information(self, "关于", "ShangBackground\n上一个桌面背景")

    def handle_tray_action(self, action):
        if action == "show":
            self.handle_show()
        elif action == "previous":
            self.handle_previous()
        elif action == "next":
            self.handle_next()
        elif action == "random":
            self.handle_random()
        elif action == "jump":
            self.handle_jump()
        elif action == "about":
            self.handle_about()
        elif action == "exit":
            QApplication.instance().quit()

    def poll_external_command(self):
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
            command_map = {
                "open-folder": "open-wallpaper-folder",
                "quick-settings": "show",
                "switch-mode": "switch-mode",
            }
            command = command_map.get(command, command)
            if command == "switch-mode":
                modes = ["幻灯片放映", "图片", "视频", "纯色", "渐变"]
                current = self.mode_combo.currentText()
                self.mode_combo.setCurrentText(modes[(modes.index(current) + 1) % len(modes)] if current in modes else modes[0])
            elif command == "open-wallpaper-folder":
                self.open_current_folder()
            else:
                self.handle_tray_action(command)
        except Exception as e:
            log(f"处理外部菜单命令失败: {e}")

    def tray_action_title(self, action):
        label = TRAY_ACTION_LABELS.get(action, action)
        hotkey_key = action if action in HOTKEY_ITEMS else ""
        if hotkey_key:
            hotkey = self.config.get(f"hotkey_{hotkey_key}", "")
            if hotkey:
                label += "\t" + display_hotkey(hotkey)
        return label

    def refresh_tray(self):
        if IS_MACOS:
            stop_menu_bar()
            if self.config.get("tray_icon", True):
                start_menu_bar(os.path.abspath(sys.argv[0]), main_pid=os.getpid())
            return
        if self.tray:
            self.tray.hide()
            self.tray.deleteLater()
            self.tray = None
        self.setup_tray()

    def setup_tray(self):
        if not self.config.get("tray_icon", True):
            return
        if IS_MACOS:
            start_menu_bar(os.path.abspath(sys.argv[0]), main_pid=os.getpid())
            return
        self.tray = QSystemTrayIcon(self)
        menu = QMenu()
        for action_key in self.config.get("tray_menu_items", ["show", "previous", "next", "random", "about", "jump", "exit"]):
            if action_key not in TRAY_ACTION_LABELS:
                continue
            action = QAction(self.tray_action_title(action_key), self)
            action.triggered.connect(lambda checked=False, key=action_key: self.handle_tray_action(key))
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def register_global_hotkeys(self):
        try:
            import keyboard
        except ImportError:
            self.status.setText("缺少 keyboard 模块，已保存快捷键但未注册")
            return
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        action_map = {
            "previous": self.handle_previous,
            "next": self.handle_next,
            "random": self.handle_random,
            "show": self.handle_show,
            "jump": self.handle_jump,
        }
        registered = 0
        for key, callback in action_map.items():
            hotkey = self.config.get(f"hotkey_{key}", "") or DEFAULT_HOTKEYS.get(key, "")
            if not hotkey:
                continue
            try:
                keyboard.add_hotkey(hotkey, lambda cb=callback: QTimer.singleShot(0, cb), suppress=False)
                registered += 1
            except Exception as e:
                log(f"全局快捷键注册失败: {hotkey} -> {key}: {e}")
        self.status.setText(f"已注册 {registered} 个全局快捷键")

    def closeEvent(self, event):
        if self.config.get("run_in_background", True):
            event.ignore()
            self.hide()
            return
        self.controller.stop_video()
        stop_menu_bar()
        super().closeEvent(event)


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

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    palette = app.palette()
    palette.setColor(QPalette.WindowText, QColor(UI_TEXT))
    palette.setColor(QPalette.Text, QColor(UI_TEXT))
    palette.setColor(QPalette.ButtonText, QColor(UI_TEXT))
    palette.setColor(QPalette.PlaceholderText, QColor(UI_MUTED))
    palette.setColor(QPalette.Window, QColor(UI_BG))
    palette.setColor(QPalette.Base, QColor(UI_PANEL))
    palette.setColor(QPalette.Button, QColor(UI_PANEL))
    palette.setColor(QPalette.Highlight, QColor(UI_ACCENT_SOFT))
    palette.setColor(QPalette.HighlightedText, QColor(UI_TEXT))
    app.setPalette(palette)
    window = MainWindow()
    if not args.hide:
        window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
