# ShangBackground PySide6 主入口
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import threading
import shutil
import subprocess
from pathlib import Path

import core_engine as core
import single_instance
from app_config import DEFAULT_THEME_COLOR, MODE_KEYS, STYLE_KEYS, normalize_mode_key, normalize_style_key
from i18n import t, init_i18n, get_language, set_language, load_language
from ui_scaling import apply_dpi_environment, clamp_dpi_scale, dpi_percent
from update_services import GITHUB_LATEST_RELEASE_URL, GITHUB_PROJECT_URL, UpdateChecker

# Load configured UI language before any translated constants/widgets are created.
init_i18n(core.config)

# ---------- 版本号 ----------
APP_VERSION = "1.3.0"
APP_ID = "xxdz.ShangBackground"
APP_PROCESS_NAME = "ShangBackground"
APP_DISPLAY_NAME = t("上一个桌面背景")
APP_ORGANIZATION = t("XXDZ工作室")
core.VERSION = APP_VERSION


def shlex_join(parts: list[str]) -> str:
    try:
        import shlex
        return shlex.join(parts)
    except Exception:
        return " ".join(f'"{p}"' if " " in p else p for p in parts)



def _set_windows_app_identity() -> None:
    """设置 Windows AppUserModelID，避免任务栏/通知区域沿用 python.exe 身份。"""
    if not core.IS_WINDOWS:
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(APP_DISPLAY_NAME)
    except Exception:
        pass

def _is_action_launch(args: argparse.Namespace) -> bool:
    return any([
        getattr(args, "previous", False),
        getattr(args, "next", False),
        getattr(args, "random", False),
        getattr(args, "show", False),
        bool(getattr(args, "set_wallpaper", None)),
        getattr(args, "jump_to_wallpaper", False),
    ])


def _parse_early_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--previous", action="store_true")
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--random", action="store_true")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--hide", action="store_true")
    parser.add_argument("--jump-to-wallpaper", action="store_true")
    parser.add_argument("--set-wallpaper", dest="set_wallpaper")
    parser.add_argument("--sync-context-on-start", action="store_true")
    return parser.parse_known_args()[0]


def _open_sidebar_standalone() -> None:
    """
    独立进程模式（由 --jump-to-wallpaper 触发）：
    创建最小 QApplication → 显示 PySide6 侧边栏 → exec → 退出。
    此函数在 QApplication 创建之前可安全调用。
    """
    import sys as _sys
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    folder = core.config.get("slide_folder", "")
    current = core.config.get("current_wallpaper", "") or core.get_current_wallpaper()

    _set_windows_app_identity()
    _app = QApplication.instance() or QApplication(_sys.argv)
    _app.setOrganizationName(APP_ORGANIZATION)
    _app.setApplicationName(APP_PROCESS_NAME)
    _app.setApplicationDisplayName(APP_DISPLAY_NAME)
    _install_qt_chinese_translator(_app)
    icon_path = os.path.join(core.BASE_DIR, "img", "LOGO.ico")
    if os.path.exists(icon_path):
        _app.setWindowIcon(QIcon(icon_path))

    if not folder or not os.path.isdir(folder):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(None, t("提示"), t("请先在软件中设置壁纸文件夹"))
        return

    try:
        from wallpaper_sidebar import WallpaperSidebar

        def _switch(path: str) -> None:
            try:
                core.push_wallpaper(path)
                core.set_wallpaper_direct(path, t("侧边栏切换"))
            except Exception as exc:
                core.log(f"侧边栏切换壁纸失败: {exc}")

        sidebar_log = core.config.get("log_file_path") if core.config.get("log_enabled", False) else None
        sidebar = WallpaperSidebar(
            None, folder, current, sidebar_log,
            show_message=lambda t, m: None,
            switch_wallpaper=_switch,
        )
        # 侧边栏关闭时退出独立 QApplication
        sidebar.closed.connect(_app.quit)
        _app.exec()

    except Exception as exc:
        core.log(f"打开侧边栏失败: {exc}")
        import traceback
        core.log(traceback.format_exc())


def _handle_action_args(args: argparse.Namespace) -> bool:
    """在 PySide6 GUI 创建前处理右键菜单/命令行动作。"""
    if args.hide:
        core.hide_window = True
    if args.previous:
        core.previous_wallpaper()
        return True
    if args.next:
        core.next_wallpaper()
        return True
    if args.random:
        core.random_wallpaper()
        return True
    if args.set_wallpaper:
        target = args.set_wallpaper
        if os.path.isfile(target):
            core.push_wallpaper(target)
            core.set_wallpaper_direct(target, t("命令行设置"))
        else:
            core.log(f"壁纸文件不存在: {target}")
        return True
    if args.jump_to_wallpaper:
        _open_sidebar_standalone()
        return True
    return False


# ---------- 单实例检测 ----------
# 单实例锁在 single_instance.py 中实现：用户级 PID 锁文件 + 本机回环端口锁，普通权限即可工作。
_SINGLE_INSTANCE_MUTEX_NAME = single_instance.APP_MUTEX_NAME


def _activate_existing_window() -> bool:
    """激活已运行的主窗口；若窗口被隐藏到托盘则强制显示。"""
    if not core.IS_WINDOWS:
        return False
    try:
        if core.activate_existing_instance(show_notice=False):
            return True
    except Exception:
        pass
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(core.WND_CLASS_NAME, None)
        if not hwnd:
            hwnd = user32.FindWindowW(None, APP_DISPLAY_NAME)
        if not hwnd:
            hwnd = user32.FindWindowW(None, "ShangBackground")
        if not hwnd:
            return False
        current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        attached = False
        if current_thread != target_thread:
            try:
                attached = bool(user32.AttachThreadInput(current_thread, target_thread, True))
            except Exception:
                attached = False
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        if not user32.IsWindowVisible(hwnd):
            user32.ShowWindow(hwnd, 1)  # SW_SHOWNORMAL
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        if attached:
            try:
                user32.AttachThreadInput(current_thread, target_thread, False)
            except Exception:
                pass
        return True
    except Exception:
        return False


def _is_already_running() -> bool:
    """普通权限单实例检测。"""
    return not single_instance.acquire()


def _release_singleton_mutex():
    """释放单实例守卫。"""
    try:
        single_instance.release()
    except Exception:
        pass


try:
    from PySide6.QtCore import QObject, QTimer, Qt, Signal, QSize, QPropertyAnimation, QEasingCurve, QUrl, QEvent, QRect, QPoint, QThread, QTranslator, QLibraryInfo, QLocale
    from PySide6.QtGui import QAction, QColor, QIcon, QPixmap, QDesktopServices, QPainter, QImageReader, QFont, QFontDatabase, QPalette
    from PySide6.QtWidgets import (
        QApplication,
        QAbstractSpinBox,
        QCheckBox,
        QColorDialog,
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QSlider,
        QSystemTrayIcon,
        QTabWidget,
        QTextEdit,
        QListWidget,
        QListWidgetItem,
        QListView,
        QProgressBar,
        QGraphicsOpacityEffect,
        QStackedWidget,
        QScroller,
        QScrollerProperties,
        QVBoxLayout,
        QWidget,
        QStyleFactory,
    )
    PYSIDE_AVAILABLE = True
except Exception as exc:  # pragma: no cover - 运行环境缺 PySide6 时回退
    PYSIDE_AVAILABLE = False
    PYSIDE_IMPORT_ERROR = exc


_QT_TRANSLATORS = []


def _install_qt_chinese_translator(app) -> None:
    """Load Qt Chinese translations only when the app UI is Chinese."""
    if not PYSIDE_AVAILABLE or app is None or get_language() != "zh":
        return
    try:
        QLocale.setDefault(QLocale(QLocale.Language.Chinese, QLocale.Country.China))
    except Exception:
        pass
    try:
        paths = []
        try:
            paths.append(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
        except Exception:
            pass
        paths.extend([
            os.path.join(core.BASE_DIR, "translations"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations"),
        ])
        for base_name in ("qtbase_zh_CN", "qt_zh_CN"):
            for path in paths:
                if not path:
                    continue
                translator = QTranslator(app)
                if translator.load(base_name, path):
                    app.installTranslator(translator)
                    _QT_TRANSLATORS.append(translator)
                    break
    except Exception as exc:
        try:
            core.log(f"Qt 中文翻译加载失败: {exc}")
        except Exception:
            pass


def _dependency_availability_for_pyside() -> dict:
    """供 PySide6 主入口使用的依赖可用性表。未列出的依赖由 dependency_prompt 自行探测。"""
    return {
        "PIL": getattr(core, "Image", None) is not None,
        "requests": getattr(core, "requests", None) is not None,
        "numpy": bool(getattr(core, "HAS_NUMPY", False)),
        "PySide6": PYSIDE_AVAILABLE,
        "psutil": getattr(core, "psutil", None) is not None,
        "httpx": importlib.util.find_spec("httpx") is not None,
    }


if PYSIDE_AVAILABLE:
    class PreviewCanvas(QFrame):
        """首页壁纸预览画布。

        只显示真实壁纸缩略图，不再把桌面示意图/文字遮罩叠到预览图上。
        画布尺寸由自身控制，路径、历史列表和按钮全部放在画布外部，避免挤压时互相覆盖。
        """

        PREVIEW_HEIGHT = 280

        def __init__(self, parent=None):
            super().__init__(parent)
            self._pixmap = QPixmap()
            self._caption = t("实际壁纸预览")
            self.setMinimumSize(360, self.PREVIEW_HEIGHT)
            self.setMaximumHeight(self.PREVIEW_HEIGHT)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.setToolTip(t("当前壁纸预览：不叠加文字或桌面示意图"))

        def sizeHint(self):  # noqa: N802 - Qt API
            return QSize(500, self.PREVIEW_HEIGHT)

        def _load_scaled_pixmap(self, image_path: str) -> QPixmap:
            """按预览控件尺寸读取缩略图，避免每次刷新都把原图完整解码到界面线程。"""
            target = self.size().boundedTo(QSize(900, self.PREVIEW_HEIGHT))
            if target.width() <= 0 or target.height() <= 0:
                target = QSize(500, self.PREVIEW_HEIGHT)
            reader = QImageReader(image_path)
            reader.setAutoTransform(True)
            reader.setAllocationLimit(256)  # 限制单张图片解码内存上限 256MB，防止超大图 OOM
            original = reader.size()
            if original.isValid():
                scaled = original.scaled(target, Qt.KeepAspectRatio)
                if scaled.isValid():
                    reader.setScaledSize(scaled)
            image = reader.read()
            return QPixmap.fromImage(image) if not image.isNull() else QPixmap()

        def set_preview(self, image_path: str = "", overlay_path: str = ""):
            # overlay_path 参数保留为兼容旧调用，但故意不再使用，避免文字/示意图压到壁纸预览上。
            if image_path and os.path.exists(image_path):
                self._pixmap = self._load_scaled_pixmap(image_path)
                self._caption = os.path.basename(image_path) or t("实际壁纸预览")
            else:
                self._pixmap = QPixmap()
                self._caption = t("暂无预览")
            self.update()

        def paintEvent(self, event):  # noqa: N802 - Qt API
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)

            rect = self.rect().adjusted(0, 0, -1, -1)
            painter.fillRect(rect, QColor("#f8fafc"))
            painter.setPen(QColor("#d8dee9"))
            painter.drawRoundedRect(rect, 12, 12)

            image_rect = rect.adjusted(14, 14, -14, -44)
            painter.fillRect(image_rect, QColor("#eef2f7"))
            painter.setPen(QColor("#e5e7eb"))
            painter.drawRoundedRect(image_rect, 8, 8)

            if not self._pixmap.isNull():
                scaled = self._pixmap if self._pixmap.size().boundedTo(image_rect.size()) == self._pixmap.size() else self._pixmap.scaled(image_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = image_rect.x() + (image_rect.width() - scaled.width()) // 2
                y = image_rect.y() + (image_rect.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            else:
                painter.setPen(QColor("#6b7280"))
                painter.drawText(image_rect, Qt.AlignCenter, t("暂无预览"))

            caption_rect = rect.adjusted(14, rect.height() - 34, -14, -8)
            painter.setPen(QColor("#64748b"))
            metrics = painter.fontMetrics()
            caption = metrics.elidedText(self._caption, Qt.ElideMiddle, caption_rect.width())
            painter.drawText(caption_rect, Qt.AlignLeft | Qt.AlignVCenter, caption)

            painter.end()


    class QtRootShim(QObject):
        """给核心模块提供最小 root.after/deiconify 兼容层。"""

        def __init__(self, window: "ShangBackgroundWindow"):
            super().__init__(window)
            self.window = window
            self._timers: dict[str, QTimer] = {}
            self._seq = 0

        def after(self, ms: int, func=None, *args):
            self._seq += 1
            timer_id = f"qt-after-{self._seq}"
            timer = QTimer(self)
            timer.setSingleShot(True)

            def _fire():
                self._timers.pop(timer_id, None)
                if callable(func):
                    func(*args)

            timer.timeout.connect(_fire)
            self._timers[timer_id] = timer
            timer.start(max(0, int(ms)))
            return timer_id

        def after_cancel(self, timer_id):
            timer = self._timers.pop(str(timer_id), None)
            if timer is not None:
                timer.stop()
                timer.deleteLater()

        def deiconify(self):
            self.window.showNormal()
            self.window.raise_()
            self.window.activateWindow()

        def state(self, value=None):
            if value == "normal":
                self.deiconify()
            return "normal"

        def lift(self):
            self.window.raise_()

        def focus_force(self):
            self.window.activateWindow()

        def winfo_id(self):
            return int(self.window.winId())

        def winfo_exists(self):
            return True

        def winfo_screenwidth(self):
            screen = QApplication.primaryScreen()
            return screen.geometry().width() if screen else 1920

        def winfo_screenheight(self):
            screen = QApplication.primaryScreen()
            return screen.geometry().height() if screen else 1080

        def quit(self):
            QApplication.instance().quit()

        def destroy(self):
            self.window.close()


    class BingSyncWorker(QObject):
        finished = Signal(bool, str, str)

        def __init__(self, resolution: str):
            super().__init__()
            self.resolution = resolution

        def run(self):
            try:
                from bing_downloader import BingDownloader
                downloader = BingDownloader()
                info = downloader.fetch_wallpaper_info(resolution=self.resolution)
                if not info:
                    self.finished.emit(False, t("获取必应壁纸信息失败"), "")
                    return
                path = downloader.download_wallpaper(info)
                if not path:
                    self.finished.emit(False, t("下载必应壁纸失败"), "")
                    return
                core.push_wallpaper(path)
                core.set_wallpaper_direct(path, t("必应今日壁纸"))
                self.finished.emit(True, f"已设置必应壁纸：{info.title} / {info.resolution}（{info.resolution_source}）", path)
            except Exception as e:
                self.finished.emit(False, f"同步必应壁纸失败：{e}", "")


    def _iter_font_files(path: str):
        if not path:
            return []
        target = Path(path).expanduser()
        if target.is_file() and target.suffix.lower() in {".ttf", ".ttc", ".otf"}:
            return [target]
        if target.is_dir():
            files = []
            for suffix in ("*.ttf", "*.ttc", "*.otf"):
                files.extend(target.glob(suffix))
            return sorted(files)
        return []


    def apply_application_font(app: QApplication) -> str:
        """应用自定义字体文件/目录；显示大小由程序内 DPI 统一控制。"""
        if app is None:
            return ""
        candidates = []
        custom_path = core.config.get("font_path", "")
        candidates.extend(_iter_font_files(custom_path))
        candidates.extend(_iter_font_files(os.path.join(core.BASE_DIR, "fonts")))

        current_size = app.font().pointSize() if app.font().pointSize() > 0 else -1
        for font_file in candidates:
            try:
                font_id = QFontDatabase.addApplicationFont(str(font_file))
                if font_id < 0:
                    continue
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    font = QFont(families[0])
                    if current_size > 0:
                        font.setPointSize(current_size)
                    app.setFont(font)
                    return families[0]
            except Exception as exc:
                core.log(f"字体加载失败: {font_file.name}: {exc}")

        fallback = [
            core.config.get("font_family", ""),
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "SimHei",
            "Noto Sans CJK SC",
            "Source Han Sans SC",
            "PingFang SC",
            "Segoe UI",
            "Arial",
        ]
        available = set(QFontDatabase.families())
        for family in fallback:
            if family and family in available:
                font = QFont(family)
                if current_size > 0:
                    font.setPointSize(current_size)
                app.setFont(font)
                return family
        return app.font().family()



    class ShangBackgroundWindow(QMainWindow):
        log_signal = Signal(str)
        bing_result_signal = Signal(bool, str, str)
        core_result_signal = Signal(bool, str, object)

        def __init__(self):
            super().__init__()
            self.setWindowTitle(APP_DISPLAY_NAME)
            self.setMinimumSize(1020, 700)
            self._settings_dialog = None
            self.lang_combo = None
            self.header_lang_buttons = {}
            self._closing_for_exit = False
            self.tray: QSystemTrayIcon | None = None
            self._bing_worker_thread: threading.Thread | None = None
            self._startup_bing_automation_done = False
            self._core_worker_thread: threading.Thread | None = None
            self._core_busy = False
            self._animations = []
            self._first_show_anim = True
            self._last_preview_path = ""
            self._history_single_click_timer = QTimer(self)
            self._history_single_click_timer.setSingleShot(True)
            self._pending_history_item = None
            self._bing_preview_timer = QTimer(self)
            self._bing_preview_timer.setSingleShot(True)
            self._bing_preview_timer.timeout.connect(self.apply_pending_bing_preview)
            self._pending_bing_path = ""
            self._current_operation_name = ""
            self._current_operation_cancel = threading.Event()
            self._operation_panel_expanded = False
            self._init_icon()
            self._apply_theme()
            self._build_ui()
            self._apply_button_sizes()
            self.log_signal.connect(self.append_log)
            self.bing_result_signal.connect(self._on_bing_finished)
            self.core_result_signal.connect(self._on_core_finished)
            self._install_core_log_bridge()
            self._preview_refresh_timer = QTimer(self)
            self._preview_refresh_timer.setInterval(1200)
            self._preview_refresh_timer.timeout.connect(self.update_preview_if_changed)
            self._preview_refresh_timer.start()
            QTimer.singleShot(0, self._deferred_gui_startup)

        def _init_icon(self):
            icon_name = "LOGO.ico" if core.IS_WINDOWS else "LOGO.png"
            self.icon_path = os.path.join(core.BASE_DIR, "img", icon_name)
            if not os.path.exists(self.icon_path):
                self.icon_path = os.path.join(core.BASE_DIR, "img", "LOGO.ico")
            self.app_icon = QIcon(self.icon_path) if os.path.exists(self.icon_path) else QIcon()
            app = QApplication.instance()
            if app is not None:
                app.setOrganizationName(APP_ORGANIZATION)
                app.setApplicationName(APP_PROCESS_NAME)
                app.setApplicationDisplayName(APP_DISPLAY_NAME)
            if not self.app_icon.isNull():
                QApplication.setWindowIcon(self.app_icon)
                self.setWindowIcon(self.app_icon)

        def _install_core_log_bridge(self):
            self._orig_log = core.log

            def _log(msg):
                self._orig_log(msg)
                try:
                    self.log_signal.emit(str(msg))
                except Exception:
                    pass

            core.log = _log

        def append_log(self, text: str):
            if hasattr(self, "log_box"):
                self.log_box.append(text)

        def _img_path(self, name: str) -> str:
            return os.path.join(core.BASE_DIR, "img", name)

        def _set_button_svg_icon(self, button, icon_name: str, size: int = 20):
            """给按钮设置统一 SVG 图标，记录以便暗色模式切换时刷新 SVG 颜色。"""
            try:
                path = self._img_path(icon_name)
                if os.path.exists(path):
                    button.setIcon(QIcon(path))
                    button.setIconSize(QSize(size, size))
                    # 记录需要刷新的按钮及其 SVG 路径
                    if not hasattr(self, "_svg_button_icons"):
                        self._svg_button_icons = {}
                    self._svg_button_icons[id(button)] = (button, path, size)
            except Exception:
                pass

        def _refresh_svg_button_icons(self):
            """暗色模式切换后刷新所有 SVG 按钮图标，确保 currentColor 正确生效。"""
            icons = getattr(self, "_svg_button_icons", {})
            for btn_id, (button, path, size) in list(icons.items()):
                try:
                    button.setIcon(QIcon(path))
                    button.setIconSize(QSize(size, size))
                except RuntimeError:
                    icons.pop(btn_id, None)

        def _is_qobject_alive(self, obj) -> bool:
            """Return False when a PySide wrapper points at an already-deleted C++ object."""
            if obj is None:
                return False
            try:
                import shiboken6
                if not shiboken6.isValid(obj):
                    return False
            except RuntimeError:
                return False
            except Exception:
                pass
            try:
                obj.objectName()
                return True
            except RuntimeError:
                return False
            except Exception:
                return True

        def _animate_widget_flash(self, widget, duration: int = 180):
            """Small opacity pulse for compact header controls."""
            if not self._is_qobject_alive(widget):
                return
            try:
                effect = QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(effect)
                anim = QPropertyAnimation(effect, b"opacity", self)
                anim.setDuration(duration)
                anim.setStartValue(0.45)
                anim.setEndValue(1.0)
                anim.setEasingCurve(QEasingCurve.OutCubic)
                self._animations.append(anim)
                anim.finished.connect(lambda: widget.setGraphicsEffect(None) if self._is_qobject_alive(widget) else None)
                anim.start()
            except Exception:
                pass

        def _header_lang_button_style(self, selected: bool) -> str:
            qcolor = QColor(self._theme_color)
            brightness = (qcolor.red() * 299 + qcolor.green() * 587 + qcolor.blue() * 114) / 1000 if qcolor.isValid() else 80
            colors = self._theme_role_colors()
            if selected:
                text = "#24292f" if brightness >= 170 else "#ffffff"
                border = self._theme_color if brightness < 230 else ("#8c959f" if not self._theme_is_dark() else "#6d6d85")
                bg = self._theme_color if brightness < 235 else ("#eaeef2" if not self._theme_is_dark() else "#3a3a50")
                return (
                    f"background: {bg}; color: {text}; border: 1px solid {border};"
                    " border-radius: 6px; padding: 0; font-size: 12px; font-weight: 700;"
                    " min-width: 31px; max-width: 31px; min-height: 24px; max-height: 24px;"
                )
            return (
                f"background: {colors['bg_input']}; color: {colors['fg_secondary']}; border: 1px solid {colors['border']};"
                " border-radius: 6px; padding: 0; font-size: 12px; font-weight: 600;"
                " min-width: 31px; max-width: 31px; min-height: 24px; max-height: 24px;"
            )

        def _refresh_header_language_buttons(self, active_lang: str | None = None):
            active_lang = active_lang or core.config.get("language", get_language()) or "zh"
            for lang, btn in list(getattr(self, "header_lang_buttons", {}).items()):
                if not self._is_qobject_alive(btn):
                    self.header_lang_buttons.pop(lang, None)
                    continue
                selected = (lang == active_lang)
                try:
                    btn.blockSignals(True)
                    btn.setChecked(selected)
                    btn.setStyleSheet(self._header_lang_button_style(selected))
                    btn.blockSignals(False)
                except RuntimeError:
                    self.header_lang_buttons.pop(lang, None)

        def _set_combo_current_data(self, combo, value, default_index: int = 0):
            """Set a QComboBox by item data, not translated display text."""
            if not self._is_qobject_alive(combo):
                return
            try:
                idx = combo.findData(value)
                if idx < 0:
                    idx = default_index
                combo.blockSignals(True)
                combo.setCurrentIndex(idx)
                combo.blockSignals(False)
            except RuntimeError:
                return
            except Exception:
                return

        def _prepare_combo_popup(self, combo: QComboBox) -> QComboBox:
            """Use a styled QListView popup so combo drop-downs match the current GUI theme."""
            try:
                view = QListView(combo)
                view.setObjectName("ComboPopupView")
                view.setMouseTracking(True)
                view.setUniformItemSizes(True)
                view.setSpacing(2)
                view.installEventFilter(self)
                combo.setView(view)
                combo.setMaxVisibleItems(max(8, combo.count()))
            except Exception:
                pass
            return combo

        def _create_header_language_switch(self) -> QWidget:
            """Create the compact CN/EN switch placed immediately after txtlogo."""
            wrapper = QFrame()
            wrapper.setObjectName("HeaderLangSwitch")
            wrapper.setToolTip(t("语言"))
            lay = QHBoxLayout(wrapper)
            lay.setContentsMargins(4, 0, 0, 0)
            lay.setSpacing(4)
            self.header_lang_buttons = {}
            for caption, lang in (("中", "zh"), ("EN", "en")):
                btn = QPushButton(caption)
                btn.setCheckable(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setToolTip("中文" if lang == "zh" else "English")
                btn.clicked.connect(lambda _checked=False, value=lang, button=btn: self._on_language_button_clicked(value, button))
                self.header_lang_buttons[lang] = btn
                lay.addWidget(btn)
            self._refresh_header_language_buttons(core.config.get("language", get_language()))
            return wrapper

        def _on_language_button_clicked(self, lang_data: str, button=None):
            if button is not None:
                self._animate_widget_flash(button)
            self._apply_language_change(lang_data, source=button)

        def _clear_settings_widget_refs(self):
            """Settings dialog owns these widgets; never keep stale PySide wrappers after it closes."""
            self._settings_dialog = None
            for attr in (
                "lang_combo", "theme_color_edit", "theme_color_preview", "font_path_edit",
                "dpi_scale_slider", "dpi_scale_value_label", "bg_check", "auto_start_check",
                "tray_check", "tray_action", "tray_notify_check", "_settings_nav",
            ):
                try:
                    if hasattr(self, attr):
                        delattr(self, attr)
                except Exception:
                    pass

        def _add_status_animation(self):
            """轻量状态淡入动画：只动画一个 QLabel 的 opacity，避免对壁纸预览做高频重绘。"""
            try:
                effect = QGraphicsOpacityEffect(self.status_label)
                self.status_label.setGraphicsEffect(effect)
                anim = QPropertyAnimation(effect, b"opacity", self)
                anim.setDuration(220)
                anim.setStartValue(0.35)
                anim.setEndValue(1.0)
                anim.setEasingCurve(QEasingCurve.OutCubic)
                self._animations.append(anim)
                anim.start()
            except Exception:
                pass

        def set_status(self, text: str):
            if hasattr(self, "status_label"):
                self.status_label.setText(text)
                self.status_label.setToolTip(text)
            self._add_status_animation()

        def begin_operation(self, name: str, cancellable: bool = False):
            self._current_operation_name = name
            self._current_operation_cancel.clear()
            if hasattr(self, "cancel_operation_btn"):
                self.cancel_operation_btn.setEnabled(bool(cancellable))
            self.set_status(name)

        def finish_operation(self, text: str = t("操作完成")):
            self._current_operation_name = ""
            self._current_operation_cancel.clear()
            if hasattr(self, "cancel_operation_btn"):
                self.cancel_operation_btn.setEnabled(False)
            self.set_status(text)

        def _toggle_operation_panel(self):
            self._operation_panel_expanded = not getattr(self, "_operation_panel_expanded", False)
            if hasattr(self, "operation_panel"):
                self.operation_panel.setVisible(self._operation_panel_expanded)
            if hasattr(self, "operation_expand_btn"):
                self.operation_expand_btn.setToolTip(t("收起当前操作详情") if self._operation_panel_expanded else t("当前操作详情"))
                if self.operation_expand_btn.icon().isNull():
                    self.operation_expand_btn.setText("i")

        def request_cancel_current_operation(self):
            self._current_operation_cancel.set()
            self.set_status(t("正在请求终止当前操作…"))
            if hasattr(self, "bing_status") and self._current_operation_name.startswith(t("正在同步必应")):
                self.bing_status.setText(t("正在请求终止当前同步…"))

        def _deferred_gui_startup(self):
            """把非必要工作延后到窗口显示后执行，减少启动阶段卡顿。"""
            self.begin_operation(t("正在读取配置…"))
            self.refresh_from_config()
            self._schedule_preview_refresh(80)
            QTimer.singleShot(180, self.refresh_bing_cache_list)
            QTimer.singleShot(260, self.apply_native_window_effect)
            QTimer.singleShot(360, lambda: self.create_or_update_tray() if core.config.get("tray_icon", True) else None)
            QTimer.singleShot(700, self.maybe_show_auto_start_prompt)
            QTimer.singleShot(1150, self.run_bing_startup_tasks)
            # 更新检查保留在“关于”窗口手动触发，启动流程最后只显示欢迎。
            QTimer.singleShot(950, lambda: self.finish_operation(t("欢迎使用")) if self._current_operation_name == t("正在读取配置…") else None)

        def showEvent(self, event):
            super().showEvent(event)
            if not getattr(self, "_first_show_anim", False):
                return
            self._first_show_anim = False
            try:
                self.setWindowOpacity(0.0)
                fade = QPropertyAnimation(self, b"windowOpacity", self)
                fade.setDuration(220)
                fade.setStartValue(0.0)
                fade.setEndValue(1.0)
                fade.setEasingCurve(QEasingCurve.OutCubic)
                self._animations.append(fade)
                fade.start()
            except Exception:
                self.setWindowOpacity(1.0)

        def _apply_theme(self):
            """应用 UI 主题：使用精心调校的 QSS 样式表美化界面，支持主题色。"""
            app = QApplication.instance()
            try:
                if app is not None:
                    app.setStyle(QStyleFactory.create("Fusion"))
            except Exception:
                pass
            self.setMinimumSize(1020, 700)
            self._theme_color = core.config.get("theme_color", DEFAULT_THEME_COLOR) or DEFAULT_THEME_COLOR
            self._rebuild_stylesheet()

        def _stylesheet_font_family(self) -> str:
            """返回 QSS 使用的字体族列表，避免全局样式表覆盖用户选择的字体。"""
            app = QApplication.instance()
            primary = app.font().family() if app is not None else ""
            families = [
                primary,
                "Microsoft YaHei UI",
                "Microsoft YaHei",
                "SimHei",
                "Noto Sans CJK SC",
                "Source Han Sans SC",
                "PingFang SC",
                "Segoe UI",
                "Arial",
            ]
            seen = []
            for family in families:
                family = str(family or "").replace('"', "").strip()
                if family and family not in seen:
                    seen.append(family)
            return ", ".join(f'"{family}"' for family in seen) or '"Segoe UI"'


        def _theme_is_dark(self) -> bool:
            return bool(core.config.get("dark_mode", False))

        def _theme_role_colors(self) -> dict[str, str]:
            if self._theme_is_dark():
                return {
                    "bg_main": "#1e1e2e", "bg_widget": "#252536", "bg_input": "#2d2d3f",
                    "fg_primary": "#e6e6f0", "fg_secondary": "#c7c7d8", "fg_muted": "#a7a7ba",
                    "border": "#4d4d65", "note_bg": "#2d2d3f", "danger_bg": "#3b1010",
                }
            return {
                "bg_main": "#ffffff", "bg_widget": "#ffffff", "bg_input": "#ffffff",
                "fg_primary": "#24292f", "fg_secondary": "#57606a", "fg_muted": "#57606a",
                "border": "#d0d7de", "note_bg": "#f6f8fa", "danger_bg": "#fff5f5",
            }

        def _text_style(self, role: str = "primary", extra: str = "") -> str:
            colors = self._theme_role_colors()
            key = "fg_primary" if role == "primary" else "fg_muted" if role == "muted" else "fg_secondary"
            prefix = (extra.strip().rstrip(";") + "; ") if extra else ""
            return f"{prefix}color: {colors[key]};"

        def _surface_note_style(self, extra: str = "") -> str:
            colors = self._theme_role_colors()
            prefix = (extra.strip().rstrip(";") + "; ") if extra else ""
            return (f"{prefix}color: {colors['fg_secondary']}; background: {colors['note_bg']}; "
                    f"border: 1px solid {colors['border']}; border-radius: 8px;")

        def _extra_theme_qss(self, dark: bool) -> str:
            if dark:
                bg_widget = "#252536"; bg_input = "#2d2d3f"; fg_primary = "#e6e6f0"; fg_muted = "#a7a7ba"
                border = "#4d4d65"; hover = "#34344a"; disabled_bg = "#3d3d55"; disabled_fg = "#8b8ba3"
            else:
                bg_widget = "#ffffff"; bg_input = "#ffffff"; fg_primary = "#24292f"; fg_muted = "#57606a"
                border = "#d0d7de"; hover = "#f6f8fa"; disabled_bg = "#d8dee4"; disabled_fg = "#8c959f"
            icon_dir = os.path.join(getattr(core, "BASE_DIR", os.path.dirname(os.path.abspath(__file__))), "img")
            spin_up_fg_icon = "spin_arrow_up_light.svg" if dark else "spin_arrow_up_dark.svg"
            spin_down_fg_icon = "spin_arrow_down_light.svg" if dark else "spin_arrow_down_dark.svg"
            spin_up_disabled_name = "spin_arrow_up_disabled_dark.svg" if dark else "spin_arrow_up_disabled_light.svg"
            spin_down_disabled_name = "spin_arrow_down_disabled_dark.svg" if dark else "spin_arrow_down_disabled_light.svg"
            spin_up_icon = Path(os.path.join(icon_dir, spin_up_fg_icon)).as_posix()
            spin_down_icon = Path(os.path.join(icon_dir, spin_down_fg_icon)).as_posix()
            spin_up_disabled_icon = Path(os.path.join(icon_dir, spin_up_disabled_name)).as_posix()
            spin_down_disabled_icon = Path(os.path.join(icon_dir, spin_down_disabled_name)).as_posix()
            checkbox_check_icon = Path(os.path.join(icon_dir, "checkbox_check.svg")).as_posix()
            checkbox_dash_icon = Path(os.path.join(icon_dir, "checkbox_dash.svg")).as_posix()
            checkbox_check_disabled_icon = Path(os.path.join(icon_dir, "checkbox_check_disabled.svg")).as_posix()
            qss = """
/* Extra cross-platform contrast fixes */
QMessageBox, QFileDialog, QColorDialog, QInputDialog, QDialogButtonBox { background-color: __BG_WIDGET__; color: __FG_PRIMARY__; }
QDialog QLabel, QMessageBox QLabel, QFileDialog QLabel, QColorDialog QLabel { background-color: transparent; color: __FG_PRIMARY__; }
QDialogButtonBox QPushButton { background: %%tc%%; color: %%btn_text%%; border: 1px solid %%btn_border%%; border-radius: 6px; padding: 5px 14px; min-height: 28px; }
QDialogButtonBox QPushButton:hover:enabled { background: %%hover_c%%; }
QDialogButtonBox QPushButton:disabled { background: __DISABLED_BG__; color: __DISABLED_FG__; border-color: __BORDER__; }
QAbstractItemView { background-color: __BG_INPUT__; color: __FG_PRIMARY__; border: 1px solid __BORDER__; selection-background-color: %%visible_accent%%; selection-color: %%accent_text%%; }
QComboBox QAbstractItemView, QListView#ComboPopupView { background-color: __BG_INPUT__; color: __FG_PRIMARY__; border: 1px solid __BORDER__; border-radius: 8px; padding: 4px; outline: 0; }
QComboBox QAbstractItemView::item, QListView#ComboPopupView::item { min-height: 28px; padding: 6px 10px; border-radius: 5px; }
QComboBox QAbstractItemView::item:hover, QListView#ComboPopupView::item:hover { background-color: __HOVER__; }
QComboBox QAbstractItemView::item:selected, QListView#ComboPopupView::item:selected { background-color: %%visible_accent%%; color: %%accent_text%%; }
QHeaderView::section { background-color: __HOVER__; color: __FG_PRIMARY__; border: 1px solid __BORDER__; padding: 4px; }
QTableWidget, QTreeWidget, QTableView, QTreeView { background-color: __BG_INPUT__; color: __FG_PRIMARY__; gridline-color: __BORDER__; alternate-background-color: __BG_WIDGET__; }
QSpinBox, QDoubleSpinBox {
    border: 1px solid __BORDER__;
    border-radius: 8px;
    padding: 5px 36px 5px 10px;
    background-color: __BG_INPUT__;
    color: __FG_PRIMARY__;
    font-size: 13px;
    min-height: 36px;
    min-width: 82px;
}
QSpinBox:focus, QDoubleSpinBox:focus { border: 2px solid %%visible_accent%%; padding: 4px 35px 4px 9px; }
QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled, QComboBox:disabled, QTextEdit:disabled { background-color: __DISABLED_BG__; color: __DISABLED_FG__; border-color: __BORDER__; }
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 30px;
    height: 18px;
    border-left: 1px solid __BORDER__;
    border-bottom: 0px solid transparent;
    border-top-right-radius: 7px;
    background-color: __HOVER__;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 30px;
    height: 18px;
    border-left: 1px solid __BORDER__;
    border-top: 1px solid __BORDER__;
    border-bottom-right-radius: 7px;
    background-color: __HOVER__;
}
QSpinBox::up-button:hover:enabled, QDoubleSpinBox::up-button:hover:enabled,
QSpinBox::down-button:hover:enabled, QDoubleSpinBox::down-button:hover:enabled { background-color: __BG_INPUT__; border-color: %%visible_accent%%; }
QSpinBox::up-button:pressed:enabled, QDoubleSpinBox::up-button:pressed:enabled,
QSpinBox::down-button:pressed:enabled, QDoubleSpinBox::down-button:pressed:enabled { background-color: __HOVER__; border-color: %%visible_accent%%; }
QSpinBox::up-button:disabled, QDoubleSpinBox::up-button:disabled,
QSpinBox::down-button:disabled, QDoubleSpinBox::down-button:disabled { background-color: __DISABLED_BG__; border-color: __BORDER__; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { width: 13px; height: 13px; margin: 0px; image: url("%%spin_up_icon%%"); }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { width: 13px; height: 13px; margin: 0px; image: url("%%spin_down_icon%%"); }
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled { image: url("%%spin_up_disabled_icon%%"); }
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled { image: url("%%spin_down_disabled_icon%%"); }
QCheckBox { spacing: 9px; font-size: 13px; font-weight: 400; min-height: 24px; background-color: transparent; color: __FG_PRIMARY__; }
QCheckBox:hover { font-size: 13px; font-weight: 400; }
QCheckBox:disabled { color: __DISABLED_FG__; }
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid __BORDER__;
    border-radius: 4px;
    background-color: __BG_INPUT__;
}
QCheckBox::indicator:hover:enabled { border: 1px solid %%visible_accent%%; background-color: __HOVER__; }
QCheckBox::indicator:checked { border-color: %%visible_accent%%; background-color: %%visible_accent%%; image: url("%%checkbox_check_icon%%"); }
QCheckBox::indicator:checked:hover:enabled { border-color: %%pressed_c%%; background-color: %%pressed_c%%; }
QCheckBox::indicator:indeterminate { border-color: %%visible_accent%%; background-color: %%visible_accent%%; image: url("%%checkbox_dash_icon%%"); }
QCheckBox::indicator:disabled { border-color: __BORDER__; background-color: __DISABLED_BG__; }
QCheckBox::indicator:checked:disabled { border-color: __BORDER__; background-color: __DISABLED_BG__; image: url("%%checkbox_check_disabled_icon%%"); }
QSlider::groove:horizontal { height: 6px; background: __BORDER__; border-radius: 3px; }
QSlider::handle:horizontal { width: 18px; margin: -6px 0; border-radius: 9px; background: %%visible_accent%%; }
QToolTip { background-color: __BG_INPUT__; color: __FG_PRIMARY__; border: 1px solid __BORDER__; padding: 4px; }
QMenu { background-color: __BG_WIDGET__; color: __FG_PRIMARY__; border: 1px solid __BORDER__; }
QMenu::item { padding: 6px 18px; }
QMenu::item:disabled { color: __DISABLED_FG__; }
QFrame#HeaderLangSwitch { background-color: transparent; }
QLabel[muted="true"] { color: __FG_MUTED__; }
"""
            return (qss.replace("__BG_WIDGET__", bg_widget).replace("__BG_INPUT__", bg_input)
                       .replace("__FG_PRIMARY__", fg_primary).replace("__FG_MUTED__", fg_muted)
                       .replace("__BORDER__", border).replace("__HOVER__", hover)
                       .replace("__DISABLED_BG__", disabled_bg).replace("__DISABLED_FG__", disabled_fg)
                       .replace("%%spin_up_icon%%", spin_up_icon).replace("%%spin_down_icon%%", spin_down_icon)
                       .replace("%%spin_up_disabled_icon%%", spin_up_disabled_icon).replace("%%spin_down_disabled_icon%%", spin_down_disabled_icon)
                       .replace("%%checkbox_check_icon%%", checkbox_check_icon).replace("%%checkbox_dash_icon%%", checkbox_dash_icon)
                       .replace("%%checkbox_check_disabled_icon%%", checkbox_check_disabled_icon))

        def _rebuild_stylesheet(self):
            """根据当前主题色和暗色模式重建 QSS 样式表。"""
            app = QApplication.instance()
            tc = self._theme_color
            dark = bool(core.config.get("dark_mode", False))
            from PySide6.QtGui import QColor
            base = QColor(tc)
            if not base.isValid():
                tc = DEFAULT_THEME_COLOR
                self._theme_color = tc
                base = QColor(tc)

            if dark:
                # ── 暗色模式配色 ──
                bg_main = "#1e1e2e"
                bg_widget = "#252536"
                bg_input = "#2d2d3f"
                fg_primary = "#e0e0e0"
                fg_secondary = "#a0a0b0"
                border_color = "#3d3d55"
                border_focus = base.lighter(130).name()
                group_bg = "#252536"
                scroll_handle = "#4d4d65"
                scroll_handle_hover = "#6d6d85"
                theme_brightness = (base.red() * 299 + base.green() * 587 + base.blue() * 114) / 1000
                if theme_brightness >= 230:
                    # Very light accent colors turn buttons white in dark mode; use a darkened accent-safe surface instead.
                    tc_for_buttons = "#3a3a50"
                    hover_c = "#45455f"
                    pressed_c = "#50506a"
                    btn_top = tc_for_buttons
                    btn_hover_top = hover_c
                    btn_text = "#e6e6f0"
                    btn_border = "#5a5a73"
                    visible_accent = "#8b8ba3"
                    progress_chunk = visible_accent
                    accent_text = "#ffffff"
                else:
                    tc_for_buttons = tc
                    hover_c = base.lighter(115).name()
                    pressed_c = base.lighter(130).name()
                    btn_top = base.name()
                    btn_hover_top = base.lighter(110).name()
                    btn_text = "#e0e0e0" if theme_brightness >= 170 else "#ffffff"
                    btn_border = base.darker(118).name()
                    visible_accent = tc
                    progress_chunk = tc
                    accent_text = "#ffffff"
                disabled_bg = "#3d3d55"
                disabled_text = "#6d6d85"
                muted_color = "#8888a0"
                tab_bg = "#252536"
                tab_selected = "#2d2d3f"
                nav_bg = "#1e1e2e"
                nav_hover = "#2d2d3f"
                nav_selected = base.darker(150).name()
                link_color = "#8ab4f8"
                _TPL = (
                    "/* ── 暗色模式 ── */\n"
                    f"QMainWindow, QDialog {{ background-color: {bg_main}; }}\n"
                    f"QWidget {{ background-color: {bg_widget}; color: {fg_primary}; font-family: %%font_family%%; }}\n"
                    f"QLabel {{ background-color: transparent; color: {fg_primary}; }}\n"
                    "\n"
                    "/* 分组框 */\n"
                    f"QGroupBox {{ font-weight: 600; font-size: 13px; border: 1px solid {border_color}; border-radius: 8px;"
                    f" margin-top: 12px; padding: 16px 12px 10px 12px; background-color: {group_bg}; }}\n"
                    f"QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left;"
                    f" padding: 2px 10px; color: {fg_primary}; background-color: {group_bg}; border-radius: 4px; }}\n"
                    "\n"
                    "/* 按钮 */\n"
                    f"QPushButton {{ background: %%tc%%; color: %%btn_text%%; border: 1px solid %%btn_border%%; border-radius: 6px;"
                    f" padding: 5px 14px; font-size: 13px; font-weight: 500; min-height: 28px; }}\n"
                    f"QPushButton:hover:enabled {{ background: %%hover_c%%; }}\n"
                    f"QPushButton:pressed:enabled {{ background: %%pressed_c%%; padding-top: 6px; padding-bottom: 4px; }}\n"
                    f"QPushButton:disabled {{ background: {disabled_bg}; border-color: {border_color}; color: {disabled_text}; }}\n"
                    f"QPushButton[secondary=\"true\"] {{ background: %%tc%%; color: %%btn_text%%; border: 1px solid %%btn_border%%; }}\n"
                    f"QPushButton[secondary=\"true\"]:hover:enabled {{ background: %%hover_c%%; }}\n"
                    f"QPushButton[secondary=\"true\"]:pressed:enabled {{ background: %%pressed_c%%; padding-top: 6px; padding-bottom: 4px; }}\n"
                    f"QPushButton[secondary=\"true\"]:disabled {{ background: {disabled_bg}; border-color: {border_color}; color: {disabled_text}; }}\n"
                    "\n"
                    "/* 输入框 */\n"
                    f"QLineEdit {{ border: 1px solid {border_color}; border-radius: 6px; padding: 6px 10px;"
                    f" background-color: {bg_input}; color: {fg_primary}; font-size: 13px; min-height: 28px; }}\n"
                    f"QLineEdit:focus {{ border-color: %%visible_accent%%; border-width: 2px; padding: 5px 9px; }}\n"
                    "\n"
                    "/* 下拉框 */\n"
                    f"QComboBox {{ border: 1px solid {border_color}; border-radius: 6px; padding: 5px 10px;"
                    f" background-color: {bg_input}; color: {fg_primary}; font-size: 13px; min-height: 28px; }}\n"
                    f"QComboBox:focus {{ border-color: %%visible_accent%%; }}\n"
                    f"QComboBox::drop-down {{ border: none; width: 24px; }}\n"
                    "\n"
                    "/* 复选框 */\n"
                    f"QCheckBox {{ spacing: 8px; font-size: 13px; font-weight: 400; min-height: 24px; background-color: transparent; color: {fg_primary}; }}\n"
                    f"QCheckBox:hover {{ font-size: 13px; font-weight: 400; }}\n"
                    "\n"
                    "/* 滑块 */\n"
                    f"QSlider::groove:horizontal {{ border: 1px solid {border_color}; border-radius: 4px; background: {bg_input}; height: 6px; }}\n"
                    f"QSlider::handle:horizontal {{ background: %%tc%%; border: 1px solid %%btn_border%%; width: 14px; margin: -5px 0; border-radius: 7px; }}\n"
                    "\n"
                    "/* 选项卡 */\n"
                    f"QTabWidget::pane {{ border: 1px solid {border_color}; border-radius: 6px; background: {tab_bg}; }}\n"
                    f"QTabBar::tab {{ background: {tab_bg}; color: {fg_secondary}; border: 1px solid {border_color}; border-radius: 4px;"
                    f" padding: 6px 14px; margin: 2px; }}\n"
                    f"QTabBar::tab:selected {{ background: {tab_selected}; color: {fg_primary}; border-bottom: 2px solid %%visible_accent%%; }}\n"
                    f"QTabBar::tab:hover {{ background: {nav_hover}; }}\n"
                    "\n"
                    "/* 滚动条 */\n"
                    f"QScrollBar:vertical {{ background: {bg_main}; width: 10px; border: none; }}\n"
                    f"QScrollBar::handle:vertical {{ background: %%scroll_handle%%; border-radius: 5px; min-height: 30px; }}\n"
                    f"QScrollBar::handle:vertical:hover {{ background: %%scroll_handle_hover%%; }}\n"
                    f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}\n"
                    "\n"
                    "/* 进度条 */\n"
                    f"QProgressBar {{ border: 1px solid {border_color}; border-radius: 4px; background: {bg_input}; text-align: center;"
                    f" color: {fg_primary}; font-size: 11px; height: 18px; }}\n"
                    f"QProgressBar::chunk {{ background: %%progress_chunk%%; border-radius: 3px; }}\n"
                    "\n"
                    "/* 列表控件 */\n"
                    f"QListWidget {{ background: {bg_widget}; border: 1px solid {border_color}; border-radius: 6px;"
                    f" color: {fg_primary}; outline: none; }}\n"
                    f"QListWidget::item {{ padding: 8px 12px; border-radius: 4px; }}\n"
                    f"QListWidget::item:hover {{ background: {nav_hover}; }}\n"
                    f"QListWidget::item:selected {{ background: %%visible_accent%%; color: {accent_text}; }}\n"
                    "\n"
                    "/* 文本编辑 */\n"
                    f"QTextEdit, QPlainTextEdit {{ background: {bg_input}; color: {fg_primary}; border: 1px solid {border_color};"
                    f" border-radius: 6px; padding: 8px; font-size: 12px; }}\n"
                    "\n"
                    "/* 信息提示 */\n"
                    f"*[muted=\"true\"] {{ color: {muted_color}; }}\n"
                    "\n"
                    "/* 链接标签 */\n"
                    f"*[link=\"true\"] {{ color: {link_color}; text-decoration: underline; }}\n"
                    "\n"
                    "/* 托盘菜单 */\n"
                    f"QMenu {{ background: {bg_widget}; color: {fg_primary}; border: 1px solid {border_color}; border-radius: 6px; padding: 4px; }}\n"
                    f"QMenu::item {{ padding: 6px 24px; border-radius: 4px; }}\n"
                    f"QMenu::item:selected {{ background: {nav_hover}; }}\n"
                    f"QMenu::separator {{ height: 1px; background: {border_color}; margin: 4px 8px; }}\n"
                )
            else:
                hover_c = base.darker(110).name()
                pressed_c = base.darker(130).name()
                btn_top = base.lighter(118).name()
                btn_hover_top = base.lighter(128).name()
                theme_brightness = (base.red() * 299 + base.green() * 587 + base.blue() * 114) / 1000
                btn_border = "#d0d7de" if theme_brightness >= 230 else base.darker(118).name()
                btn_text = "#24292f" if theme_brightness >= 170 else "#ffffff"
                visible_accent = "#8c959f" if theme_brightness >= 230 else tc
                scroll_handle = "#c9d1d9" if theme_brightness >= 230 else base.lighter(135).name()
                scroll_handle_hover = "#8c959f" if theme_brightness >= 230 else base.darker(105).name()
                progress_chunk = "#8c959f" if theme_brightness >= 230 else tc
                accent_text = "#ffffff" if theme_brightness >= 230 else btn_text

                _TPL = (
                    "/* 全局字体与背景 */\n"
                    "QMainWindow, QDialog { background-color: #ffffff; }\n"
                    "QWidget { background-color: #ffffff; color: #24292f; font-family: %%font_family%%; }\n"
                    "QLabel { background-color: transparent; }\n"
                "\n"
                "/* 分组框样式 */\n"
                "QGroupBox { font-weight: 600; font-size: 13px; border: 1px solid #d0d7de; border-radius: 8px;"
                " margin-top: 12px; padding: 16px 12px 10px 12px; background-color: #ffffff; }\n"
                "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;"
                " padding: 2px 10px; color: #24292f; background-color: #ffffff; border-radius: 4px; }\n"
                "\n"
                "/* 按钮样式：主按钮、次要按钮统一从 settings.json 的 theme_color 取色；精灵图和色块按钮另行覆盖。 */\n"
                "QPushButton { background: %%tc%%;"
                " color: %%btn_text%%; border: 1px solid %%btn_border%%; border-radius: 6px;"
                " padding: 5px 14px; font-size: 13px; font-weight: 500; min-height: 28px; }\n"
                "QPushButton:hover:enabled { background: %%hover_c%%; }\n"
                "QPushButton:pressed:enabled { background: %%pressed_c%%; padding-top: 6px; padding-bottom: 4px; }\n"
                "QPushButton:disabled { background: #d8dee4; border-color: #c9d1d9; color: #8c959f; }\n"
                "QPushButton[secondary=\"true\"] { background: %%tc%%; color: %%btn_text%%; border: 1px solid %%btn_border%%; }\n"
                "QPushButton[secondary=\"true\"]:hover:enabled { background: %%hover_c%%; }\n"
                "QPushButton[secondary=\"true\"]:pressed:enabled { background: %%pressed_c%%; padding-top: 6px; padding-bottom: 4px; }\n"
                "QPushButton[secondary=\"true\"]:disabled { background: #d8dee4; border-color: #c9d1d9; color: #8c959f; }\n"
                "\n"
                "/* 输入框样式 */\n"
                "QLineEdit { border: 1px solid #d0d7de; border-radius: 6px; padding: 6px 10px;"
                " background-color: #ffffff; font-size: 13px; min-height: 28px; }\n"
                "QLineEdit:focus { border-color: %%visible_accent%%; border-width: 2px; padding: 5px 9px; }\n"
                "\n"
                "/* 下拉框样式 */\n"
                "QComboBox { border: 1px solid #d0d7de; border-radius: 6px; padding: 5px 10px;"
                " background-color: #ffffff; font-size: 13px; min-height: 28px; }\n"
                "QComboBox:focus { border-color: %%visible_accent%%; }\n"
                "QComboBox::drop-down { border: none; width: 24px; }\n"
                "\n"
                "/* 数值输入框保持 Qt/系统默认外观，仅保留外层布局尺寸，不用 QSS 重绘箭头。 */\n"
                "\n"
                "/* 复选框保持 Qt 默认勾选样式，避免主题色为白色时看不出勾选状态。 */\n"
                "QCheckBox { spacing: 8px; font-size: 13px; background-color: transparent; }\n"
                "\n"
                "/* 滑块保持 Qt/系统默认外观，避免自绘造成触屏拖动时的撕裂感。 */\n"
                "\n"
                "/* 选项卡 */\n"
                "QTabWidget::pane { border: 1px solid #d0d7de; border-radius: 8px;"
                " background-color: #ffffff; padding: 4px; }\n"
                "QTabBar::tab { padding: 8px 20px; font-size: 13px; font-weight: 500;"
                " border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;"
                " background-color: #ffffff; color: #57606a; border: 1px solid transparent; border-bottom: none; }\n"
                "QTabBar::tab:selected { background-color: #ffffff; color: #24292f;"
                " border: 1px solid #d0d7de; border-bottom: 2px solid %%visible_accent%%; }\n"
                "QTabBar::tab:hover:!selected { background-color: #f0f2f5; }\n"
                "\n"
                "/* 进度条 */\n"
                "QProgressBar { border: 1px solid #d0d7de; border-radius: 6px; text-align: center;"
                " background-color: #ffffff; height: 20px; font-size: 12px; }\n"
                "QProgressBar::chunk { background-color: %%progress_chunk%%; border-radius: 5px; }\n"
                "\n"
                "/* 列表视图 */\n"
                "QListWidget { border: 1px solid #d0d7de; border-radius: 6px;"
                " background-color: #ffffff; padding: 4px; }\n"
                "QListWidget::item:selected, QComboBox QAbstractItemView::item:selected { background: %%visible_accent%%; color: %%accent_text%%; }\n"
                "QMenu::item:selected { background: %%visible_accent%%; color: %%accent_text%%; }\n"
                "QTextEdit selection, QLineEdit selection { background: %%visible_accent%%; color: %%accent_text%%; }\n"
                "\n"
                "/* 滚动区域与滚动条 */\n"
                "QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget, QStackedWidget { border: none; background-color: #ffffff; }\n"
                "QScrollBar:vertical { background: #f6f8fa; width: 10px; margin: 0; border-radius: 5px; }\n"
                "QScrollBar::handle:vertical { background: %%scroll_handle%%; min-height: 30px; border-radius: 5px; }\n"
                "QScrollBar::handle:vertical:hover { background: %%scroll_handle_hover%%; }\n"
                "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: transparent; }\n"
                "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }\n"
                "QScrollBar:horizontal { background: #f6f8fa; height: 10px; margin: 0; border-radius: 5px; }\n"
                "QScrollBar::handle:horizontal { background: %%scroll_handle%%; min-width: 30px; border-radius: 5px; }\n"
                "QScrollBar::handle:horizontal:hover { background: %%scroll_handle_hover%%; }\n"
                "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; background: transparent; }\n"
                "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }\n"
                "\n"
                "/* 文本编辑框 */\n"
                "QTextEdit, QPlainTextEdit { border: 1px solid #d0d7de; border-radius: 6px;"
                " background-color: #ffffff; padding: 6px;"
                " font-family: \"Cascadia Code\", \"Consolas\", \"Microsoft YaHei UI\", monospace;"
                " font-size: 12px; }\n"
                "QPushButton#OperationInfoButton { background: #ffffff; color: #57606a; border: 1px solid #d0d7de;"
                " border-radius: 13px; padding: 0; min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; }\n"
                "QPushButton#OperationInfoButton:hover { border-color: %%visible_accent%%; color: %%visible_accent%%; background: #ffffff; }\n"
                "QPushButton#OperationInfoButton:pressed { background: #f6f8fa; }\n"
                "QPushButton#CancelOperationButton { background: #ffffff; color: #57606a; border: 1px solid #d0d7de;"
                " border-radius: 6px; padding: 4px 10px; min-height: 24px; }\n"
                "QPushButton#CancelOperationButton:hover:enabled { color: #b42318; border-color: #f1aeb5; background: #fff5f5; }\n"
                "QPushButton#CancelOperationButton:pressed:enabled { background: #ffe3e3; }\n"
            )
            stylesheet = (
                _TPL.replace("%%tc%%", tc_for_buttons if dark else tc)
                .replace("%%hover_c%%", hover_c)
                .replace("%%pressed_c%%", pressed_c)
                .replace("%%btn_top%%", btn_top)
                .replace("%%btn_hover_top%%", btn_hover_top)
                .replace("%%btn_border%%", btn_border)
                .replace("%%btn_text%%", btn_text)
                .replace("%%visible_accent%%", visible_accent)
                .replace("%%scroll_handle%%", scroll_handle)
                .replace("%%scroll_handle_hover%%", scroll_handle_hover)
                .replace("%%progress_chunk%%", progress_chunk)
                .replace("%%accent_text%%", accent_text)
                .replace("%%font_family%%", self._stylesheet_font_family())
            )
            stylesheet += self._extra_theme_qss(dark)
            stylesheet = (stylesheet
                .replace("%%tc%%", tc_for_buttons if dark else tc)
                .replace("%%hover_c%%", hover_c)
                .replace("%%pressed_c%%", pressed_c)
                .replace("%%btn_border%%", btn_border)
                .replace("%%btn_text%%", btn_text)
                .replace("%%visible_accent%%", visible_accent)
                .replace("%%accent_text%%", accent_text))
            self._theme_stylesheet = stylesheet
            if app is not None:
                app.setStyleSheet(stylesheet)
            # 精灵图按钮背景必须和当前页面背景一致，避免透明 PNG 边缘露出主题色。
            if hasattr(self, "about_sprite_btn"):
                sprite_bg = "#252536" if dark else "#ffffff"
                sprite_border = "#252536" if dark else "#ffffff"
                self.about_sprite_btn.setStyleSheet(
                    f"background-color: {sprite_bg}; border: 1px solid {sprite_border}; border-radius: 8px;")
            self._refresh_styled_widgets()
            if hasattr(self, "_apply_button_sizes"):
                self._apply_button_sizes()
            if hasattr(self, "_refresh_color_buttons"):
                self._refresh_color_buttons()
            if hasattr(self, "_refresh_settings_nav_style"):
                self._refresh_settings_nav_style()

        def _refresh_styled_widgets(self):
            app = QApplication.instance()
            if app is None:
                return
            dark = bool(core.config.get("dark_mode", False))
            try:
                pal = app.palette()
                qcolor = QColor(self._theme_color)
                brightness = (qcolor.red() * 299 + qcolor.green() * 587 + qcolor.blue() * 114) / 1000 if qcolor.isValid() else 255
                highlight = QColor("#8c959f") if brightness >= 230 else qcolor
                pal.setColor(QPalette.ColorRole.Highlight, highlight)
                pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
                if dark:
                    # 设置暗色模式基础调色板
                    pal.setColor(QPalette.ColorRole.Window, QColor("#252536"))
                    pal.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
                    pal.setColor(QPalette.ColorRole.Base, QColor("#2d2d3f"))
                    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#252536"))
                    pal.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
                    pal.setColor(QPalette.ColorRole.Button, QColor("#2d2d3f"))
                    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#e0e0e0"))
                    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#a7a7ba"))
                    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2d2d3f"))
                    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#e6e6f0"))
                    pal.setColor(QPalette.ColorRole.Link, QColor(self._theme_color))
                    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
                        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor("#8b8ba3"))
                    for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button):
                        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor("#3d3d55"))
                app.setPalette(pal)
            except Exception:
                pass
            try:
                for widget in app.allWidgets():
                    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                        try:
                            widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
                            if widget.minimumHeight() < 36:
                                widget.setMinimumHeight(36)
                            if widget.minimumWidth() < 90:
                                widget.setMinimumWidth(90)
                        except Exception:
                            pass
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                    widget.update()
            except Exception:
                pass

        def apply_native_window_effect(self):
            """默认 Qt 原生主题不额外套玻璃效果。"""
            return

        def _enable_touch_scrolling(self, widget, *, horizontal: bool = False):
            """为可滚动控件启用单指惯性滑动；只触及 viewport，避免影响按钮点击。"""
            try:
                target = widget.viewport() if hasattr(widget, "viewport") else widget
                target.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
                QScroller.grabGesture(target, QScroller.ScrollerGestureType.TouchGesture)
                scroller = QScroller.scroller(target)
                props = scroller.scrollerProperties()
                props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragResistanceFactor, 0.18)
                props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.10)
                props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.10)
                try:
                    props.setScrollMetric(QScrollerProperties.ScrollMetric.DragStartDistance, 0.008)
                    props.setScrollMetric(QScrollerProperties.ScrollMetric.FrameRate, QScrollerProperties.FrameRates.Fps60)
                except Exception:
                    pass
                if not horizontal:
                    props.setScrollMetric(QScrollerProperties.ScrollMetric.HorizontalOvershootPolicy, QScrollerProperties.OvershootPolicy.OvershootAlwaysOff)
                props.setScrollMetric(QScrollerProperties.ScrollMetric.VerticalOvershootPolicy, QScrollerProperties.OvershootPolicy.OvershootWhenScrollable)
                scroller.setScrollerProperties(props)
            except Exception:
                pass

        def _apply_button_sizes(self):
            for btn in self.findChildren(QPushButton):
                if btn is getattr(self, "about_sprite_btn", None):
                    continue
                if btn.property("colorButton"):
                    if btn.minimumHeight() < 40:
                        btn.setMinimumHeight(40)
                    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    continue
                if btn.property("wideAction"):
                    if btn.minimumHeight() < 38:
                        btn.setMinimumHeight(38)
                    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    continue
                if btn.minimumHeight() < 30:
                    btn.setMinimumHeight(30)
                btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        def _settings_nav_stylesheet(self, color=None) -> str:
            color = color or getattr(self, "_theme_color", core.config.get("theme_color", DEFAULT_THEME_COLOR))
            qcolor = QColor(color)
            if not qcolor.isValid():
                color = DEFAULT_THEME_COLOR
                qcolor = QColor(color)
            dark = bool(core.config.get("dark_mode", False))
            if dark:
                bg = "#1e1e2e"
                border = "#3d3d55"
                item_bg = "#252536"
                item_fg = "#a0a0b0"
                selected_bg = color
                selected_text = "#ffffff"
                selected_border = color
                hover_bg = "#2d2d3f"
            else:
                brightness = (qcolor.red() * 299 + qcolor.green() * 587 + qcolor.blue() * 114) / 1000
                bg = "#ffffff"
                border = "#d0d7de"
                item_fg = "#57606a"
                selected_text = "#24292f" if brightness >= 170 else "#ffffff"
                selected_bg = "#f6f8fa" if brightness >= 230 else color
                selected_border = "#8c959f" if brightness >= 230 else color
                hover_bg = "#eaeef2"
            return (
                f"QListWidget#SettingsNav {{ background-color: {bg}; border: 1px solid {border};"
                f" border-radius: 8px; padding: 6px; outline: none; }}"
                f"QListWidget#SettingsNav::item {{ padding: 10px 14px; border-radius: 6px;"
                f" color: {item_fg}; font-size: 13px; }}"
                f"QListWidget#SettingsNav::item:selected {{ background-color: {selected_bg}; color: {selected_text}; border: 1px solid {selected_border}; font-weight: 500; }}"
                f"QListWidget#SettingsNav::item:hover:!selected {{ background-color: {hover_bg}; }}"
            )

        def _refresh_settings_nav_style(self, nav_list=None):
            nav_list = nav_list or getattr(self, "_settings_nav", None)
            if nav_list is None and hasattr(self, "_settings_dialog") and self._settings_dialog is not None:
                try:
                    nav_list = self._settings_dialog.findChild(QListWidget, "SettingsNav")
                except Exception:
                    nav_list = None
            if nav_list is None:
                return
            try:
                nav_list.setStyleSheet(self._settings_nav_stylesheet())
            except RuntimeError:
                pass

        def _build_ui(self):
            central = QWidget(self)
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setContentsMargins(16, 12, 16, 12)
            layout.setSpacing(10)

            header = QHBoxLayout()
            header.setSpacing(12)
            logo_path = self._img_path("txtlogo.png")
            if os.path.exists(logo_path):
                logo = QLabel()
                pix = QPixmap(logo_path)
                if not pix.isNull():
                    logo.setPixmap(pix.scaledToHeight(56, Qt.SmoothTransformation))
                    logo.setMaximumWidth(320)
                    logo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    header.addWidget(logo)
                else:
                    header.addWidget(QLabel(t("上一个桌面背景")))
            else:
                title = QLabel(t("上一个桌面背景"))
                title.setStyleSheet(self._text_style("primary", "font-size: 22px; font-weight: 700;"))
                header.addWidget(title)
            self.header_lang_switch = self._create_header_language_switch()
            header.addWidget(self.header_lang_switch, 0, Qt.AlignVCenter)
            header.addStretch(1)
            self.status_label = QLabel(t("正在初始化界面…"))
            self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.status_label.setMinimumWidth(220)
            self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.status_label.setStyleSheet(self._text_style("muted", "font-size: 12px;"))
            header.addWidget(self.status_label, 1)
            self.operation_expand_btn = QPushButton()
            self.operation_expand_btn.setObjectName("OperationInfoButton")
            info_icon = self._img_path("info.svg")
            if os.path.exists(info_icon):
                self.operation_expand_btn.setIcon(QIcon(info_icon))
                self.operation_expand_btn.setIconSize(QSize(16, 16))
            else:
                self.operation_expand_btn.setText("i")
            self.operation_expand_btn.setFixedSize(26, 26)
            self.operation_expand_btn.setToolTip(t("当前操作详情"))
            self.operation_expand_btn.clicked.connect(self._toggle_operation_panel)
            header.addWidget(self.operation_expand_btn)
            layout.addLayout(header)

            self.operation_panel = QFrame()
            self.operation_panel.setVisible(False)
            op_layout = QHBoxLayout(self.operation_panel)
            op_layout.setContentsMargins(0, 0, 0, 0)
            op_layout.addStretch(1)
            op_hint = QLabel(t("当前操作可在这里请求终止；已开始的系统壁纸设置会尽量安全收尾。"))
            op_hint.setProperty("muted", True)
            op_layout.addWidget(op_hint)
            self.cancel_operation_btn = QPushButton(t("请求终止"))
            self.cancel_operation_btn.setObjectName("CancelOperationButton")
            self.cancel_operation_btn.setEnabled(False)
            self.cancel_operation_btn.clicked.connect(self.request_cancel_current_operation)
            op_layout.addWidget(self.cancel_operation_btn)
            layout.addWidget(self.operation_panel)

            self.tabs = QTabWidget()
            layout.addWidget(self.tabs, 1)
            self.wallpaper_tab_page = self._wallpaper_tab()
            self.tabs.addTab(self.wallpaper_tab_page, t("首页"))
            self.tabs.addTab(self._bing_tab(), t("必应壁纸"))
            self.tabs.addTab(self._about_tab(), t("关于 / 资源"))
            self.tabs.addTab(self._log_tab(), t("日志"))

        def _wallpaper_tab(self):
            page = QWidget()
            outer = QVBoxLayout(page)
            outer.setContentsMargins(0, 0, 0, 0)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            self._enable_touch_scrolling(scroll)
            outer.addWidget(scroll)

            body = QWidget()
            scroll.setWidget(body)
            root = QHBoxLayout(body)
            root.setContentsMargins(16, 16, 16, 16)
            root.setSpacing(18)
            left = QVBoxLayout()
            right = QVBoxLayout()
            left.setSpacing(12)
            right.setSpacing(12)
            root.addLayout(left, 4)
            root.addLayout(right, 5)

            mode_box = QGroupBox(t("壁纸模式"))
            form = QFormLayout(mode_box)
            form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            form.setHorizontalSpacing(12)
            form.setVerticalSpacing(10)
            self.mode_combo = QComboBox()
            for mode_key in MODE_KEYS:
                self.mode_combo.addItem(t(mode_key), mode_key)
            self._prepare_combo_popup(self.mode_combo)
            self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
            form.addRow(t("当前模式"), self.mode_combo)
            self.fit_combo = QComboBox()
            for style_key in STYLE_KEYS:
                self.fit_combo.addItem(t(style_key), style_key)
            self._prepare_combo_popup(self.fit_combo)
            self.fit_combo.currentIndexChanged.connect(self.on_fit_changed)
            form.addRow(t("适应方式"), self.fit_combo)
            left.addWidget(mode_box)

            slide_box = QGroupBox(t("幻灯片放映"))
            slide_layout = QGridLayout(slide_box)
            slide_layout.setHorizontalSpacing(10)
            slide_layout.setVerticalSpacing(10)
            self.folder_edit = QLineEdit()
            self.folder_edit.setPlaceholderText(t("首次使用请先选择壁纸文件夹"))
            self.btn_browse_folder = QPushButton(t("选择文件夹"))
            self.btn_browse_folder.setProperty("secondary", True)
            btn_browse_folder = self.btn_browse_folder
            btn_browse_folder.clicked.connect(self.choose_folder)
            slide_layout.addWidget(QLabel(t("文件夹")), 0, 0)
            slide_layout.addWidget(self.folder_edit, 0, 1, 1, 2)
            slide_layout.addWidget(btn_browse_folder, 0, 3)
            self.seconds_spin = QSpinBox()
            self.seconds_spin.setRange(5, 24 * 3600)
            self.seconds_spin.setSuffix(t(" 秒"))
            self.seconds_spin.valueChanged.connect(self.on_seconds_changed)
            slide_layout.addWidget(QLabel(t("间隔")), 1, 0)
            slide_layout.addWidget(self.seconds_spin, 1, 1)
            self.shuffle_check = QCheckBox(t("随机顺序"))
            self.shuffle_check.toggled.connect(self.on_shuffle_changed)
            slide_layout.addWidget(self.shuffle_check, 1, 2, 1, 2)

            nav_row = QGridLayout()
            nav_row.setHorizontalSpacing(8)
            nav_row.setVerticalSpacing(8)
            self.btn_prev = btn_prev = QPushButton(t("上一张"))
            self.btn_next = btn_next = QPushButton(t("下一张"))
            self.btn_random = btn_random = QPushButton(t("随机"))
            self.btn_random_prob = btn_random_prob = QPushButton(t("随机概率（百分比）"))
            btn_random_prob.setToolTip(t("打开百分比编辑器，为每张壁纸分配 0% 到 100% 的随机概率"))
            self.btn_start = btn_start = QPushButton(t("应用并播放"))
            self.btn_stop = btn_stop = QPushButton(t("暂停"))
            for btn in (btn_prev, btn_next, btn_random, btn_random_prob, btn_start, btn_stop):
                btn.setMinimumHeight(38)
            nav_row.addWidget(btn_prev, 0, 0)
            nav_row.addWidget(btn_next, 0, 1)
            nav_row.addWidget(btn_random, 0, 2)
            nav_row.addWidget(btn_random_prob, 0, 3)
            nav_row.addWidget(btn_start, 1, 0, 1, 2)
            nav_row.addWidget(btn_stop, 1, 2, 1, 2)
            btn_prev.clicked.connect(lambda: self.run_core(core.previous_wallpaper))
            btn_next.clicked.connect(lambda: self.run_core(core.next_wallpaper))
            btn_random.clicked.connect(lambda: self.run_core(core.random_wallpaper))
            btn_random_prob.clicked.connect(self.open_random_probability_settings)
            btn_start.clicked.connect(lambda: self.run_core(core.start_slideshow))
            btn_stop.clicked.connect(lambda: self.run_core(core.stop_slideshow))
            slide_layout.addLayout(nav_row, 2, 0, 1, 4)
            self.slide_box = slide_box
            left.addWidget(slide_box)

            single_box = QGroupBox(t("单张图片"))
            single_layout = QHBoxLayout(single_box)
            single_layout.setSpacing(10)
            self.single_edit = QLineEdit()
            self.single_edit.setPlaceholderText(t("选择一张图片作为桌面背景"))
            self.btn_single = QPushButton(t("选择并设置"))
            self.btn_single.setProperty("secondary", True)
            btn_single = self.btn_single
            btn_single.clicked.connect(self.choose_single_image)
            single_layout.addWidget(self.single_edit, 1)
            single_layout.addWidget(btn_single)
            self.single_box = single_box
            left.addWidget(single_box)

            color_box = QGroupBox(t("纯色 / 渐变"))
            color_layout = QGridLayout(color_box)
            color_layout.setHorizontalSpacing(10)
            color_layout.setVerticalSpacing(10)
            color_layout.setColumnStretch(0, 0)
            color_layout.setColumnStretch(1, 1)
            color_layout.setColumnStretch(2, 1)
            self.solid_btn = QPushButton(t("选择纯色"))
            self.solid_btn.setProperty("colorButton", True)
            self.grad1_btn = QPushButton(t("渐变颜色 1"))
            self.grad1_btn.setProperty("colorButton", True)
            self.grad2_btn = QPushButton(t("渐变颜色 2"))
            self.grad2_btn.setProperty("colorButton", True)
            for _btn in (self.solid_btn, self.grad1_btn, self.grad2_btn):
                _btn.setMinimumHeight(40)
                _btn.setMinimumWidth(150)
                _btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.angle_spin = QSpinBox()
            self.angle_spin.setRange(0, 360)
            self.angle_spin.setSuffix("°")
            self.solid_btn.clicked.connect(self.choose_solid_color)
            self.grad1_btn.clicked.connect(lambda: self.choose_gradient_color(1))
            self.grad2_btn.clicked.connect(lambda: self.choose_gradient_color(2))
            self.angle_apply_btn = QPushButton(t("应用渐变"))
            self.angle_apply_btn.clicked.connect(self.on_gradient_apply)
            self.angle_spin.valueChanged.connect(self.on_gradient_changed)
            color_layout.addWidget(QLabel(t("纯色")), 0, 0)
            color_layout.addWidget(self.solid_btn, 0, 1, 1, 2)
            color_layout.addWidget(QLabel(t("渐变颜色")), 1, 0)
            color_layout.addWidget(self.grad1_btn, 1, 1)
            color_layout.addWidget(self.grad2_btn, 1, 2)
            color_layout.addWidget(QLabel(t("渐变角度")), 2, 0)
            color_layout.addWidget(self.angle_spin, 2, 1)
            color_layout.addWidget(self.angle_apply_btn, 2, 2)
            self.color_box = color_box
            left.addWidget(color_box)

            action_box = QGroupBox(t("快捷操作"))
            action_layout = QVBoxLayout(action_box)
            action_layout.setContentsMargins(12, 18, 12, 12)
            action_layout.setSpacing(8)
            action_tabs = QTabWidget()
            action_tabs.setDocumentMode(True)
            action_layout.addWidget(action_tabs)

            quick_page = QWidget()
            quick_grid = QGridLayout(quick_page)
            quick_grid.setContentsMargins(4, 6, 4, 4)
            quick_grid.setHorizontalSpacing(10)
            quick_grid.setVerticalSpacing(10)
            btn_refresh = QPushButton(t("刷新预览"))
            btn_refresh.setProperty("secondary", True)
            self._set_button_svg_icon(btn_refresh, "refresh.svg")
            btn_refresh.clicked.connect(self.update_preview)
            btn_open_folder = QPushButton(t("打开当前文件夹"))
            btn_open_folder.setProperty("secondary", True)
            self._set_button_svg_icon(btn_open_folder, "folder.svg")
            btn_open_folder.clicked.connect(self.open_current_folder)
            btn_sidebar = QPushButton(t("跳转到壁纸"))
            btn_sidebar.setProperty("secondary", True)
            self._set_button_svg_icon(btn_sidebar, "image.svg")
            btn_sidebar.clicked.connect(self.open_wallpaper_sidebar)
            self.settings_icon_btn = QPushButton(t("全局设置"))
            self.settings_icon_btn.setToolTip(t("打开全局设置窗口"))
            self._set_button_svg_icon(self.settings_icon_btn, "settings.svg")
            self.settings_icon_btn.clicked.connect(self.open_global_settings_from_home)
            btn_exit_home = QPushButton(t("退出程序"))
            btn_exit_home.setProperty("secondary", True)
            self._set_button_svg_icon(btn_exit_home, "power.svg")
            btn_exit_home.clicked.connect(self.exit_app)
            for btn in (btn_refresh, btn_open_folder, btn_sidebar, self.settings_icon_btn, btn_exit_home):
                btn.setMinimumHeight(40)
            quick_grid.addWidget(btn_refresh, 0, 0)
            quick_grid.addWidget(btn_open_folder, 0, 1)
            quick_grid.addWidget(btn_sidebar, 1, 0)
            quick_grid.addWidget(self.settings_icon_btn, 1, 1)
            quick_grid.addWidget(btn_exit_home, 2, 0, 1, 2)
            action_tabs.addTab(quick_page, t("常用"))

            maint_page = QWidget()
            mh = QGridLayout(maint_page)
            mh.setContentsMargins(4, 6, 4, 4)
            mh.setHorizontalSpacing(10)
            mh.setVerticalSpacing(10)
            btn_save = QPushButton(t("保存配置"))
            btn_save.setProperty("secondary", True)
            self._set_button_svg_icon(btn_save, "save.svg")
            btn_save.clicked.connect(lambda: self.run_core(core.save_config))
            btn_admin_home = QPushButton(t("管理员重启"))
            btn_admin_home.setProperty("secondary", True)
            self._set_button_svg_icon(btn_admin_home, "restart.svg")
            btn_admin_home.clicked.connect(self.restart_as_admin)
            btn_restore_home = QPushButton(t("恢复启动前壁纸"))
            btn_restore_home.setProperty("secondary", True)
            self._set_button_svg_icon(btn_restore_home, "undo.svg")
            btn_restore_home.clicked.connect(lambda: self.run_core(core.restore_session_original_wallpaper))
            for btn in (btn_save, btn_admin_home, btn_restore_home):
                btn.setMinimumHeight(40)
            mh.addWidget(btn_save, 0, 0)
            mh.addWidget(btn_restore_home, 0, 1)
            mh.addWidget(btn_admin_home, 1, 0, 1, 2)
            action_tabs.addTab(maint_page, t("维护"))
            left.addWidget(action_box)
            left.addStretch(1)

            preview_box = QGroupBox(t("当前壁纸"))
            preview_box.setMinimumWidth(400)
            pv_layout = QVBoxLayout(preview_box)
            pv_layout.setContentsMargins(14, 20, 14, 14)
            pv_layout.setSpacing(10)
            self.preview_canvas = PreviewCanvas()
            pv_layout.addWidget(self.preview_canvas)

            self.current_label = QLineEdit("")
            self.current_label.setReadOnly(True)
            self.current_label.setPlaceholderText(t("未检测到当前壁纸"))
            self.current_label.setMinimumHeight(34)
            self.current_label.setToolTip(t("当前壁纸路径，可选中文本复制"))
            pv_layout.addWidget(self.current_label)

            hist_row = QHBoxLayout()
            hist_row.setSpacing(8)
            hist_title = QLabel(t("之前使用过的壁纸（单击后应用，双击打开位置）"))
            hist_title.setProperty("muted", True)
            hist_title.setStyleSheet("font-size: 12px;")
            hist_row.addWidget(hist_title)
            hist_row.addStretch(1)
            pv_layout.addLayout(hist_row)
            self.history_list = QListWidget()
            self.history_list.setObjectName("HistoryThumbs")
            self.history_list.setViewMode(QListView.ViewMode.IconMode)
            self.history_list.setFlow(QListView.Flow.LeftToRight)
            self.history_list.setResizeMode(QListView.ResizeMode.Adjust)
            self.history_list.setMovement(QListView.Movement.Static)
            self.history_list.setWrapping(False)
            self.history_list.setSpacing(8)
            self.history_list.setIconSize(QSize(112, 70))
            self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.history_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.history_list.setFixedHeight(106)
            self.history_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._history_single_click_timer.timeout.connect(self.apply_pending_history_item)
            self.history_list.itemClicked.connect(self.schedule_apply_history_item)
            self.history_list.itemDoubleClicked.connect(self.open_history_item_location)
            self._enable_touch_scrolling(self.history_list, horizontal=True)
            pv_layout.addWidget(self.history_list)

            right.addWidget(preview_box)

            if core.IS_WINDOWS:
                ctx_box = QGroupBox(t("右键菜单"))
                ctx_layout = QVBoxLayout(ctx_box)
                ctx_layout.setContentsMargins(10, 18, 10, 10)
                ctx_layout.setSpacing(6)
                self.ctx_prev = QCheckBox()
                self.ctx_next = QCheckBox()
                self.ctx_random = QCheckBox()
                self.ctx_jump = QCheckBox()
                self.ctx_prev.toggled.connect(lambda v: self._update_ctx("ctx_last_wallpaper", v))
                self.ctx_next.toggled.connect(lambda v: self._update_ctx("ctx_next_wallpaper", v))
                self.ctx_random.toggled.connect(lambda v: self._update_ctx("ctx_random_wallpaper", v))
                self.ctx_jump.toggled.connect(lambda v: self._update_ctx("ctx_jump_to_wallpaper", v))
                for cb in (self.ctx_prev, self.ctx_next, self.ctx_random, self.ctx_jump):
                    ctx_layout.addWidget(cb)
                self._refresh_context_shortcut_labels()
                btn_reg_ctx = QPushButton(t("注册右键菜单"))
                btn_reg_ctx.clicked.connect(self.register_context_with_prompt)
                ctx_layout.addWidget(btn_reg_ctx)
                right.addWidget(ctx_box)

            right.addStretch(1)
            about_row = QHBoxLayout()
            about_row.addStretch(1)
            about_box = QVBoxLayout()
            about_box.setAlignment(Qt.AlignCenter)
            self.about_sprite_btn = QPushButton()
            self.about_sprite_btn.setToolTip(t("悬停播放，点击打开关于"))
            self.about_sprite_btn.setFlat(True)
            self.about_sprite_btn.setFixedSize(80, 80)
            sprite_bg = self._theme_role_colors()["bg_widget"]
            self.about_sprite_btn.setStyleSheet(
                f"background-color: {sprite_bg}; border: 1px solid {sprite_bg}; border-radius: 10px;")
            self.about_sprite_btn.clicked.connect(self.show_about_dialog)
            self.about_sprite_btn.installEventFilter(self)
            about_box.addWidget(self.about_sprite_btn, alignment=Qt.AlignCenter)
            bili_link = QLabel('<a href="https://space.bilibili.com/3461569935575626?spm_id_from=333.788">b站@小小电子xxdz</a>')
            bili_link.setOpenExternalLinks(True)
            bili_link.setAlignment(Qt.AlignCenter)
            bili_link.setStyleSheet("font-size: 12px;")
            about_box.addWidget(bili_link, alignment=Qt.AlignCenter)
            about_row.addLayout(about_box)
            right.addLayout(about_row)
            self._setup_about_sprite_animation()
            return page

        def _settings_tab(self):
            page = QWidget()
            root = QHBoxLayout(page)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(12)

            nav = QListWidget()
            nav.setObjectName("SettingsNav")
            nav.setFixedWidth(190)
            nav.setSpacing(4)
            self._settings_nav = nav
            self._refresh_settings_nav_style(nav)
            nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._enable_touch_scrolling(nav)
            root.addWidget(nav)

            stack = QStackedWidget()
            root.addWidget(stack, 1)

            def add_settings_page(title: str, widget: QWidget):
                # 将每个设置页面包裹在 QScrollArea 中，防止控件溢出
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QFrame.NoFrame)
                scroll.viewport().setStyleSheet(f"background-color: {self._theme_role_colors()['bg_widget']};")
                widget.setAutoFillBackground(True)
                scroll.setWidget(widget)
                item = QListWidgetItem(title)
                item.setSizeHint(QSize(170, 48))
                nav.addItem(item)
                stack.addWidget(scroll)

            appearance_page = QWidget()
            appearance_layout = QVBoxLayout(appearance_page)
            appearance_layout.setContentsMargins(0, 0, 0, 0)
            appearance_layout.setSpacing(12)

            appearance_box = QGroupBox(t("外观与显示"))
            appearance_form = QFormLayout(appearance_box)
            appearance_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            appearance_form.setHorizontalSpacing(14)
            appearance_form.setVerticalSpacing(10)

            theme_color_row = QWidget()
            theme_color_layout = QHBoxLayout(theme_color_row)
            theme_color_layout.setContentsMargins(0, 0, 0, 0)
            theme_color_layout.setSpacing(8)
            self.theme_color_edit = QLineEdit(self._theme_color if hasattr(self, "_theme_color") else core.config.get("theme_color", DEFAULT_THEME_COLOR))
            self.theme_color_edit.setPlaceholderText("#ffffff")
            self.theme_color_edit.setMaximumWidth(120)
            self.theme_color_preview = QLabel()
            self.theme_color_preview.setFixedSize(28, 28)
            self._update_theme_color_preview()
            theme_color_btn = QPushButton(t("选择颜色"))
            theme_color_btn.setProperty("secondary", True)
            theme_color_btn.clicked.connect(self._choose_theme_color)
            theme_color_apply_btn = QPushButton(t("应用"))
            theme_color_apply_btn.clicked.connect(self._apply_theme_color)
            theme_color_layout.addWidget(self.theme_color_edit)
            theme_color_layout.addWidget(self.theme_color_preview)
            theme_color_layout.addWidget(theme_color_btn)
            theme_color_layout.addWidget(theme_color_apply_btn)
            theme_color_layout.addStretch(1)
            appearance_form.addRow(t("主题色"), theme_color_row)

            preset_row = QWidget()
            preset_layout = QHBoxLayout(preset_row)
            preset_layout.setContentsMargins(0, 0, 0, 0)
            preset_layout.setSpacing(6)
            preset_colors = [
                (t("白"), "#ffffff"), (t("红"), "#d73a49"), (t("橙"), "#f97316"), (t("黄"), "#d4a72c"),
                (t("绿"), "#2da44e"), (t("青"), "#14b8a6"), (t("蓝"), "#0969da"), (t("紫"), "#8250df"),
            ]
            for name, hex_color in preset_colors:
                btn = QPushButton(name)
                btn.setFixedSize(46, 26)
                btn.setToolTip(hex_color)
                preset_qcolor = QColor(hex_color)
                preset_brightness = (preset_qcolor.red() * 299 + preset_qcolor.green() * 587 + preset_qcolor.blue() * 114) / 1000
                preset_text = "#24292f" if preset_brightness >= 170 else "#ffffff"
                preset_border = "#d0d7de" if preset_brightness >= 230 else preset_qcolor.darker(115).name()
                btn.setStyleSheet(
                    f"background: {hex_color};"
                    f" color: {preset_text}; border: 1px solid {preset_border};"
                    f" border-radius: 4px; font-size: 11px; font-weight: 600;")
                btn.clicked.connect(lambda checked, c=hex_color: self._set_theme_color_preset(c))
                preset_layout.addWidget(btn)
            preset_layout.addStretch(1)
            appearance_form.addRow(t("预设配色"), preset_row)

            self.font_path_edit = QLineEdit(core.config.get("font_path", ""))
            self.font_path_edit.setPlaceholderText(t("可填写字体文件或字体文件夹路径"))
            font_btn = QPushButton(t("选择"))
            font_btn.setProperty("secondary", True)
            font_btn.clicked.connect(self.choose_font_path)
            font_row = QWidget()
            font_row_layout = QHBoxLayout(font_row)
            font_row_layout.setContentsMargins(0, 0, 0, 0)
            font_row_layout.setSpacing(8)
            font_row_layout.addWidget(self.font_path_edit, 1)
            font_row_layout.addWidget(font_btn)
            appearance_form.addRow(t("自定义字体"), font_row)

            dpi_row = QWidget()
            dpi_layout = QHBoxLayout(dpi_row)
            dpi_layout.setContentsMargins(0, 0, 0, 0)
            dpi_layout.setSpacing(10)
            self.dpi_scale_slider = QSlider(Qt.Orientation.Horizontal)
            self.dpi_scale_slider.setRange(75, 200)
            self.dpi_scale_slider.setSingleStep(5)
            self.dpi_scale_slider.setPageStep(10)
            self.dpi_scale_slider.setValue(dpi_percent(core.config.get("dpi_scale", 1.0)))
            self.dpi_scale_value_label = QLabel(f"{self.dpi_scale_slider.value()}%")
            self.dpi_scale_value_label.setMinimumWidth(54)
            self.dpi_scale_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.dpi_scale_slider.valueChanged.connect(self.on_dpi_scale_changed)
            dpi_layout.addWidget(self.dpi_scale_slider, 1)
            dpi_layout.addWidget(self.dpi_scale_value_label)
            appearance_form.addRow(t("程序内 DPI"), dpi_row)

            # ── 暗色模式开关 ──
            self.dark_mode_check = QCheckBox(t("暗色模式"))
            self.dark_mode_check.setChecked(bool(core.config.get("dark_mode", False)))
            self.dark_mode_check.toggled.connect(self._on_dark_mode_toggled)
            appearance_form.addRow(t("界面主题"), self.dark_mode_check)

            display_buttons = QHBoxLayout()
            save_display_btn = QPushButton(t("保存并应用显示设置"))
            save_display_btn.setProperty("secondary", True)
            save_display_btn.clicked.connect(self.save_display_settings)
            reset_display_btn = QPushButton(t("重置外观与显示"))
            reset_display_btn.setProperty("secondary", True)
            reset_display_btn.clicked.connect(self.reset_display_settings)
            display_buttons.addWidget(save_display_btn)
            display_buttons.addWidget(reset_display_btn)
            display_buttons.addStretch(1)
            appearance_layout.addWidget(appearance_box)
            appearance_layout.addLayout(display_buttons)
            appearance_hint = QLabel(t("滑条和数值输入框保持 Qt 默认外观；显示缩放改为程序内 DPI 设置，保存后重启程序完全生效。"))
            appearance_hint.setWordWrap(True)
            appearance_hint.setProperty("muted", True)
            appearance_layout.addWidget(appearance_hint)
            appearance_layout.addStretch(1)

            # ── Language row ──
            lang_row = QWidget()
            lang_layout = QHBoxLayout(lang_row)
            lang_layout.setContentsMargins(0, 0, 0, 0)
            lang_layout.setSpacing(8)
            lang_label = QLabel(t("语言"))
            lang_label.setFixedWidth(60)
            self.lang_combo = QComboBox()
            self.lang_combo.setMaximumWidth(140)
            self.lang_combo.addItem(t("中文"), "zh")
            self.lang_combo.addItem("English", "en")
            self._prepare_combo_popup(self.lang_combo)
            # Set current language
            cur_lang = core.config.get("language", "zh")
            idx = self.lang_combo.findData(cur_lang)
            if idx >= 0:
                self.lang_combo.setCurrentIndex(idx)
            self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
            lang_hint = QLabel(t("重启后生效"))
            lang_hint.setProperty("muted", True)
            lang_layout.addWidget(lang_label)
            lang_layout.addWidget(self.lang_combo)
            lang_layout.addWidget(lang_hint)
            lang_layout.addStretch(1)
            appearance_layout.insertLayout(0, lang_layout)

            add_settings_page(t("外观与显示"), appearance_page)

            shell_page = QWidget()
            shell_layout = QVBoxLayout(shell_page)
            shell_layout.setContentsMargins(0, 0, 0, 0)
            shell_layout.setSpacing(12)

            runtime = QGroupBox(t("后台与启动"))
            form = QFormLayout(runtime)
            form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            form.setHorizontalSpacing(14)
            form.setVerticalSpacing(10)
            self.bg_check = QCheckBox(t("关闭窗口时隐藏到托盘"))
            self.bg_check.toggled.connect(self.on_background_changed)
            self.auto_start_check = QCheckBox(t("开机自启动"))
            if core.IS_WINDOWS:
                self.auto_start_check.setToolTip(t("启用后会在启动文件夹生成 ShangBackground.vbs，开机时自动后台启动。"))
            elif core.IS_MACOS:
                self.auto_start_check.setToolTip(t("启用后会写入 LaunchAgents，登录后自动后台启动。"))
            else:
                self.auto_start_check.setToolTip(t("启用后会写入 ~/.config/autostart，登录后自动后台启动。"))
            self.auto_start_check.toggled.connect(self.on_auto_start_changed)
            self.tray_check = QCheckBox(t("显示系统托盘图标"))
            self.tray_check.toggled.connect(self.on_tray_changed)
            self.tray_action = QComboBox()
            self.tray_action_map = {
                t("下一张壁纸"): "next",
                t("上一张壁纸"): "previous",
                t("随机壁纸"): "random",
                t("打开主界面"): "show",
                t("跳转到当前壁纸"): "jump",
                t("无操作"): "none",
            }
            for label, action in self.tray_action_map.items():
                self.tray_action.addItem(label, action)
            self.tray_action.currentIndexChanged.connect(self.on_tray_action_changed)
            self.tray_notify_check = QCheckBox(t("最小化到托盘时显示通知"))
            self.tray_notify_check.toggled.connect(self.on_tray_notify_changed)
            form.addRow(self.bg_check)
            form.addRow(self.auto_start_check)
            form.addRow(self.tray_check)
            form.addRow(t("单击托盘图标"), self.tray_action)
            form.addRow(self.tray_notify_check)

            shell_layout.addWidget(runtime)
            shell_hint = QLabel(t("主题与字体已移动到“外观与显示”，这里仅保留后台运行和启动相关设置。"))
            shell_hint.setWordWrap(True)
            shell_hint.setProperty("muted", True)
            shell_layout.addWidget(shell_hint)
            shell_layout.addStretch(1)
            add_settings_page(t("后台与启动"), shell_page)

            tray_page = QWidget()
            tray_layout_outer = QVBoxLayout(tray_page)
            tray_layout_outer.setContentsMargins(0, 0, 0, 0)
            tray_layout_outer.setSpacing(12)
            tray_menu_box = QGroupBox(t("托盘右键菜单项"))
            tray_menu_layout = QGridLayout(tray_menu_box)
            tray_menu_layout.setHorizontalSpacing(12)
            tray_menu_layout.setVerticalSpacing(10)
            self.tray_menu_labels = {
                "show": t("打开主界面"), "previous": t("上一张"), "next": t("下一张"), "random": t("随机"),
                "bing": t("同步必应"), "jump": t("跳转壁纸"), "about": t("关于"), "exit": t("退出"),
            }
            self.tray_menu_checks = {}
            for i, (action, label) in enumerate(self.tray_menu_labels.items()):
                cb = QCheckBox(label)
                cb.toggled.connect(self.on_tray_menu_changed)
                self.tray_menu_checks[action] = cb
                tray_menu_layout.addWidget(cb, i // 3, i % 3)
            tray_layout_outer.addWidget(tray_menu_box)
            tray_hint = QLabel(t("建议触屏设备保留“打开主界面”“跳转壁纸”和“退出”，减少托盘菜单层级。"))
            tray_hint.setWordWrap(True)
            tray_hint.setProperty("muted", True)
            tray_layout_outer.addWidget(tray_hint)
            tray_layout_outer.addStretch(1)
            add_settings_page(t("托盘菜单"), tray_page)

            if core.IS_WINDOWS:
                shortcut_page = QWidget()
                shortcut_layout = QVBoxLayout(shortcut_page)
                shortcut_layout.setContentsMargins(0, 0, 0, 0)
                shortcut_layout.setSpacing(12)
                shortcut_box = QGroupBox(t("桌面右键菜单快捷键"))
                shortcut_form = QFormLayout(shortcut_box)
                shortcut_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
                shortcut_form.setHorizontalSpacing(14)
                shortcut_form.setVerticalSpacing(10)
                self.ctx_shortcut_edits = {}
                self.ctx_shortcut_current_labels = {}
                for action, label, default_key, _cfg_key, _widget_name in self._context_action_defs():
                    row = QWidget()
                    row_layout = QHBoxLayout(row)
                    row_layout.setContentsMargins(0, 0, 0, 0)
                    row_layout.setSpacing(8)
                    edit = QLineEdit(self._context_hotkey(action))
                    edit.setPlaceholderText(default_key)
                    edit.setMinimumWidth(150)
                    edit.setToolTip(t("可填写单个字母/数字作为右键菜单助记键，也可填写 Ctrl+Alt+N 这类显示用组合键。"))
                    current = QLabel(self._context_hotkey_display(action))
                    current.setProperty("muted", True)
                    edit.editingFinished.connect(lambda action=action, edit=edit: self.on_context_hotkey_changed(action, edit))
                    self.ctx_shortcut_edits[action] = edit
                    self.ctx_shortcut_current_labels[action] = current
                    row_layout.addWidget(edit, 1)
                    row_layout.addWidget(current)
                    shortcut_form.addRow(label, row)
                shortcut_layout.addWidget(shortcut_box)
                shortcut_hint = QLabel(t("修改后点击首页“注册右键菜单”即可同步到 Windows 资源管理器。"))
                shortcut_hint.setWordWrap(True)
                shortcut_hint.setProperty("muted", True)
                shortcut_layout.addWidget(shortcut_hint)
                shortcut_layout.addStretch(1)
                add_settings_page(t("右键快捷键"), shortcut_page)

            nav.currentRowChanged.connect(stack.setCurrentIndex)
            nav.setCurrentRow(0)
            return page

        def choose_font_path(self):
            start = self.font_path_edit.text().strip() if hasattr(self, "font_path_edit") else ""
            if not start or not os.path.exists(start):
                start = str(Path.home())
            path, _ = QFileDialog.getOpenFileName(self, t("选择字体文件"), start, t("字体文件 (*.ttf *.ttc *.otf);;所有文件 (*.*)"))
            if not path:
                folder = QFileDialog.getExistingDirectory(self, t("或选择字体文件夹"), start)
                path = folder or ""
            if path and hasattr(self, "font_path_edit"):
                self.font_path_edit.setText(path)

        def on_dpi_scale_changed(self, value: int):
            if hasattr(self, "dpi_scale_value_label"):
                self.dpi_scale_value_label.setText(f"{int(value)}%")

        def _on_language_changed(self, index):
            """Handle language combo box changes from Settings."""
            sender = self.sender()
            combo = sender if isinstance(sender, QComboBox) else getattr(self, "lang_combo", None)
            if not self._is_qobject_alive(combo):
                if combo is getattr(self, "lang_combo", None):
                    self.lang_combo = None
                return
            try:
                lang_data = combo.currentData()
            except RuntimeError:
                self.lang_combo = None
                return
            self._apply_language_change(lang_data, source=combo)

        def _apply_language_change(self, lang_data: str, source=None):
            if lang_data not in ("zh", "en"):
                return
            # Sync Settings combo only if the C++ object is still alive.
            combo = getattr(self, "lang_combo", None)
            if self._is_qobject_alive(combo) and combo is not source:
                try:
                    idx = combo.findData(lang_data)
                    if idx >= 0:
                        combo.blockSignals(True)
                        combo.setCurrentIndex(idx)
                        combo.blockSignals(False)
                except RuntimeError:
                    self.lang_combo = None
            self._refresh_header_language_buttons(lang_data)

            if lang_data != core.config.get("language", "zh"):
                core.config["language"] = lang_data
                core.save_config()
                set_language(lang_data)
                load_language(lang_data)
                QMessageBox.information(
                    self, t("提示"),
                    t("切换语言后需要重启程序才能完全生效。")
                )

        def save_display_settings(self):
            value = self.font_path_edit.text().strip() if hasattr(self, "font_path_edit") else ""
            old_scale = clamp_dpi_scale(core.config.get("dpi_scale", 1.0))
            new_scale = clamp_dpi_scale((self.dpi_scale_slider.value() if hasattr(self, "dpi_scale_slider") else 100) / 100.0)
            core.config["font_path"] = value
            core.config["dpi_scale"] = new_scale
            core.config.pop("font_size", None)
            if hasattr(self, "dark_mode_check"):
                core.config["dark_mode"] = bool(self.dark_mode_check.isChecked())
            core.save_config()
            family = apply_application_font(QApplication.instance())
            self._rebuild_stylesheet()
            self._refresh_settings_nav_style()
            apply_dpi_environment(core.config)
            self.set_status(t("显示设置已保存：") + f"DPI {dpi_percent(new_scale)}% / " + t("字体") + f" {family}")
            if abs(old_scale - new_scale) > 0.001:
                QMessageBox.information(self, t("外观与显示"), t("程序内 DPI 已保存。Qt 需要在启动前读取 DPI 设置，请重启程序后完全生效。"))
            else:
                QMessageBox.information(self, t("外观与显示"), t("显示设置已保存。当前字体：") + f"{family}，DPI：{dpi_percent(new_scale)}%")

        def reset_display_settings(self):
            core.config["theme_color"] = DEFAULT_THEME_COLOR
            core.config["font_path"] = ""
            core.config["dpi_scale"] = 1.0
            core.config.pop("font_size", None)
            core.config["dark_mode"] = False
            core.save_config()
            self._theme_color = core.config["theme_color"]
            if hasattr(self, "theme_color_edit"):
                self.theme_color_edit.setText(self._theme_color)
            if hasattr(self, "dpi_scale_slider"):
                self.dpi_scale_slider.setValue(100)
            if hasattr(self, "font_path_edit"):
                self.font_path_edit.setText("")
            apply_application_font(QApplication.instance())
            self._rebuild_stylesheet()
            self._update_theme_color_preview()
            self._refresh_settings_nav_style()
            apply_dpi_environment(core.config)
            self.set_status(t("外观与显示已重置"))
            QMessageBox.information(self, t("外观与显示"), t("已重置主题色、字体路径和程序内 DPI。若 DPI 曾改变，请重启程序确认效果。"))

        def save_font_settings(self):
            self.save_display_settings()

        def save_font_path(self):
            self.save_display_settings()

        # ---------- 暗色模式相关方法 ----------
        def _on_dark_mode_toggled(self, checked: bool) -> None:
            """切换暗色模式并立即应用样式。"""
            core.config["dark_mode"] = bool(checked)
            self._rebuild_stylesheet()
            self._refresh_settings_nav_style()
            if hasattr(self, "_refresh_color_buttons"):
                self._refresh_color_buttons()
            if hasattr(self, "_refresh_styled_widgets"):
                self._refresh_styled_widgets()
            # 强制刷新 SVG 图标以适配暗色/亮色 currentColor
            self._refresh_svg_button_icons()
            self.set_status(t("暗色模式已开启") if checked else t("亮色模式已恢复"))

        # ---------- 主题色相关方法 ----------
        def _update_theme_color_preview(self):
            """更新主题色预览色块。"""
            if not hasattr(self, "theme_color_preview"):
                return
            color = self._theme_color if hasattr(self, "_theme_color") else core.config.get("theme_color", DEFAULT_THEME_COLOR)
            self.theme_color_preview.setStyleSheet(
                f"background-color: {color}; border: 2px solid #d0d7de; border-radius: 6px;")

        def _choose_theme_color(self):
            """打开颜色选择器选择主题色。"""
            from PySide6.QtWidgets import QColorDialog
            from PySide6.QtGui import QColor
            current = QColor(self._theme_color if hasattr(self, "_theme_color") else core.config.get("theme_color", DEFAULT_THEME_COLOR))
            color = QColorDialog.getColor(current, self, t("选择主题色"))
            if color.isValid():
                hex_color = color.name()
                if hasattr(self, "theme_color_edit"):
                    self.theme_color_edit.setText(hex_color)
                self._theme_color = hex_color
                self._update_theme_color_preview()

        def _apply_theme_color(self):
            """应用主题色并保存到配置。"""
            if not hasattr(self, "theme_color_edit"):
                return
            from PySide6.QtGui import QColor
            hex_color = self.theme_color_edit.text().strip()
            if not hex_color:
                hex_color = DEFAULT_THEME_COLOR
            # 验证颜色有效性
            test = QColor(hex_color)
            if not test.isValid():
                QMessageBox.warning(self, t("主题色"), t("无效的颜色值：") + f"{hex_color}\n" + t("请使用 #RRGGBB 格式，如 #ffffff"))
                return
            self._theme_color = hex_color
            core.config["theme_color"] = hex_color
            core.save_config()
            self._rebuild_stylesheet()
            self._update_theme_color_preview()
            self._refresh_settings_nav_style()
            self.set_status(t("主题色已应用：") + f"{hex_color}")

        def _set_theme_color_preset(self, hex_color: str):
            """快捷设置预设主题色。"""
            if hasattr(self, "theme_color_edit"):
                self.theme_color_edit.setText(hex_color)
            self._theme_color = hex_color
            self._update_theme_color_preview()
            self._apply_theme_color()

        def _bing_tab(self):
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)

            info = QLabel(
                "必应壁纸可同步到本地缓存，也可以直接设置为桌面背景；“继续同步更早壁纸”会从上次记录的位置继续向前获取。"
            )
            info.setWordWrap(True)
            info.setStyleSheet(self._text_style("muted", "font-size: 12px; padding: 4px 0;"))
            layout.addWidget(info)

            cache_box = QGroupBox(t("缓存与同步设置"))
            grid = QGridLayout(cache_box)
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(10)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(3, 0)
            self.bing_cache_edit = QLineEdit(core.config.get("bing_cache_dir", "") or "")
            self.bing_cache_edit.setPlaceholderText(t("首次使用请先选择一个用于保存必应壁纸的缓存目录"))
            btn_cache = QPushButton(t("选择缓存目录"))
            btn_cache.clicked.connect(self.choose_bing_cache_dir)
            self.bing_resolution = QComboBox()
            self.bing_resolution.addItems(["auto", "1920x1080", "2560x1440", "3840x2160", "1366x768", "1920x1200"])
            self._prepare_combo_popup(self.bing_resolution)
            self.bing_resolution.setMinimumWidth(150)
            self.bing_resolution.setMaximumWidth(220)
            self.bing_count_spin = QSpinBox()
            self.bing_count_spin.setRange(1, 16)
            self.bing_count_spin.setMinimumWidth(90)
            self.bing_count_spin.setMaximumWidth(110)
            self.bing_count_spin.setAlignment(Qt.AlignCenter)
            self.bing_count_spin.setValue(min(16, int(core.config.get("bing_sync_count", 1))))

            self.bing_auto_update_check = QCheckBox(t("程序启动时自动更新"))
            self.bing_auto_update_check.setToolTip(t("程序启动后自动同步指定数量的必应壁纸，并把最新一张设为桌面背景。"))
            self.bing_auto_update_count_spin = QSpinBox()
            self.bing_auto_update_count_spin.setRange(1, 16)
            self.bing_auto_update_count_spin.setMinimumWidth(90)
            self.bing_auto_update_count_spin.setMaximumWidth(110)
            self.bing_auto_update_count_spin.setAlignment(Qt.AlignCenter)
            self.bing_auto_update_count_spin.setValue(max(1, min(16, int(core.config.get("bing_auto_update_count", core.config.get("bing_sync_count", 1)) or 1))))
            self.bing_auto_delete_check = QCheckBox(t("程序启动时自动删除"))
            self.bing_auto_delete_check.setToolTip(t("程序启动后只删除必应缓存目录中最旧的指定数量图片；不会删除文件名不含 bing 的用户图片。"))
            self.bing_auto_delete_count_spin = QSpinBox()
            self.bing_auto_delete_count_spin.setRange(1, 200)
            self.bing_auto_delete_count_spin.setMinimumWidth(90)
            self.bing_auto_delete_count_spin.setMaximumWidth(110)
            self.bing_auto_delete_count_spin.setAlignment(Qt.AlignCenter)
            self.bing_auto_delete_count_spin.setValue(max(1, min(200, int(core.config.get("bing_auto_delete_count", 1) or 1))))
            self.bing_auto_update_check.setChecked(bool(core.config.get("bing_auto_update_on_start", False)))
            self.bing_auto_delete_check.setChecked(bool(core.config.get("bing_auto_delete_on_start", False)))
            for _widget in (self.bing_auto_update_check, self.bing_auto_update_count_spin, self.bing_auto_delete_check, self.bing_auto_delete_count_spin):
                if hasattr(_widget, "toggled"):
                    _widget.toggled.connect(self.on_bing_auto_options_changed)
                else:
                    _widget.valueChanged.connect(self.on_bing_auto_options_changed)

            self.bing_sync_btn = QPushButton(t("同步今日并设为壁纸"))
            self.bing_sync_btn.setToolTip(t("下载最新必应壁纸，完成后立即设置为当前桌面背景。"))
            self.bing_sync_btn.clicked.connect(lambda: self.sync_bing_wallpaper(set_latest=True))
            self.bing_multi_btn = QPushButton(t("仅缓存多张壁纸"))
            self.bing_multi_btn.setToolTip(t("按同步张数下载壁纸到缓存目录，但不改变当前桌面背景。"))
            self.bing_multi_btn.clicked.connect(lambda: self.sync_bing_wallpaper(set_latest=False))
            self.bing_continue_btn = QPushButton(t("继续同步更早壁纸"))
            self.bing_continue_btn.setToolTip(t("从上次同步进度继续获取更早的必应壁纸。"))
            self.bing_continue_btn.clicked.connect(lambda: self.sync_bing_wallpaper(set_latest=False, continue_from_saved=True))
            self.bing_play_btn = QPushButton(t("缓存目录作为幻灯片来源"))
            self.bing_play_btn.setToolTip(t("把必应缓存目录设为幻灯片放映文件夹。"))
            self.bing_play_btn.clicked.connect(self.use_bing_cache_as_slideshow)
            self.bing_saveas_btn = QPushButton(t("另存选中壁纸"))
            self.bing_saveas_btn.setToolTip(t("把下方列表中选中的缓存壁纸另存到其他位置。"))
            self.bing_saveas_btn.clicked.connect(self.save_selected_bing_as)
            for _btn in (self.bing_sync_btn, self.bing_multi_btn, self.bing_continue_btn, self.bing_play_btn, self.bing_saveas_btn):
                _btn.setProperty("wideAction", True)
                _btn.setMinimumHeight(40)
                _btn.setMinimumWidth(180)
                _btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            grid.addWidget(QLabel(t("缓存目录")), 0, 0)
            grid.addWidget(self.bing_cache_edit, 0, 1, 1, 3)
            grid.addWidget(btn_cache, 0, 4)
            grid.addWidget(QLabel(t("分辨率")), 1, 0)
            grid.addWidget(self.bing_resolution, 1, 1)
            grid.addWidget(QLabel(t("同步张数")), 1, 2)
            grid.addWidget(self.bing_count_spin, 1, 3)
            grid.addWidget(QLabel(t("张（1-16）")), 1, 4)

            actions_grid = QGridLayout()
            actions_grid.setContentsMargins(0, 0, 0, 0)
            actions_grid.setHorizontalSpacing(10)
            actions_grid.setVerticalSpacing(10)
            for _col in range(3):
                actions_grid.setColumnStretch(_col, 1)
            grid.addWidget(self.bing_auto_update_check, 2, 0, 1, 2)
            grid.addWidget(self.bing_auto_update_count_spin, 2, 2)
            grid.addWidget(QLabel(t("张壁纸")), 2, 3, 1, 2)
            grid.addWidget(self.bing_auto_delete_check, 3, 0, 1, 2)
            grid.addWidget(self.bing_auto_delete_count_spin, 3, 2)
            grid.addWidget(QLabel(t("张最旧缓存壁纸")), 3, 3, 1, 2)

            actions_grid.addWidget(self.bing_sync_btn, 0, 0)
            actions_grid.addWidget(self.bing_multi_btn, 0, 1)
            actions_grid.addWidget(self.bing_continue_btn, 0, 2)
            actions_grid.addWidget(self.bing_play_btn, 1, 0, 1, 2)
            actions_grid.addWidget(self.bing_saveas_btn, 1, 2)
            grid.addLayout(actions_grid, 4, 0, 2, 5)
            layout.addWidget(cache_box)

            self.bing_progress = QProgressBar()
            self.bing_progress.setRange(0, 100)
            self.bing_progress.setValue(0)
            layout.addWidget(self.bing_progress)
            self.bing_status = QLabel(t("未同步；请选择缓存目录后再开始。"))
            self.bing_status.setWordWrap(True)
            self.bing_status.setStyleSheet(self._text_style("muted", "font-size: 12px;"))
            layout.addWidget(self.bing_status)

            list_title = QLabel(t("已缓存的必应壁纸（选择后可预览或另存）"))
            list_title.setProperty("muted", True)
            layout.addWidget(list_title)
            self.bing_list = QListWidget()
            self.bing_list.itemSelectionChanged.connect(self.on_bing_selection_changed)
            self._enable_touch_scrolling(self.bing_list)
            layout.addWidget(self.bing_list, 1)
            return page

        def _about_tab(self):
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(10)

            title = QLabel(f"{APP_DISPLAY_NAME} v{APP_VERSION}")
            title.setStyleSheet(self._text_style("primary", "font-size: 24px; font-weight: 700;"))
            layout.addWidget(title)

            desc = QLabel(t("一个用于快速切换、随机和管理桌面背景的小工具。"))
            desc.setWordWrap(True)
            desc.setStyleSheet(self._text_style("muted", "font-size: 13px;"))
            layout.addWidget(desc)

            links = QLabel(
                '原项目：<a href="https://github.com/xxdz-Official/ShangBackground">xxdz-Official/ShangBackground</a><br>'
                'GitHub反馈 / 统一更新源：<a href="https://github.com/purrfecto114-lgtm/ShangBackground">purrfecto114-lgtm/ShangBackground</a><br>'
                '作者主页：<a href="https://space.bilibili.com/3461569935575626?spm_id_from=333.788">b站@小小电子xxdz</a><br>'
                '<a href="app://shishe">[施舍]</a>　'
                '<a href="app://about-window">关于图片</a>　'
                '<a href="app://about-dialog">关于窗口</a>'
            )
            links.setOpenExternalLinks(False)
            links.linkActivated.connect(self._handle_about_link)
            links.setWordWrap(True)
            layout.addWidget(links)

            note = QLabel(t("右键菜单命令会直接调用本程序的 --previous、--next、--random、--jump-to-wallpaper 和 --set-wallpaper 参数。"))
            note.setWordWrap(True)
            note.setStyleSheet(self._text_style("muted", "font-size: 12px;"))
            layout.addWidget(note)
            layout.addStretch(1)
            return page

        def _log_tab(self):
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)

            path_box = QGroupBox(t("日志设置"))
            path_grid = QGridLayout(path_box)
            path_grid.setHorizontalSpacing(10)
            path_grid.setVerticalSpacing(10)
            self.log_enabled_check = QCheckBox(t("记录日志到文件（默认关闭）"))
            self.log_enabled_check.setChecked(bool(core.config.get("log_enabled", False)))
            self.log_enabled_check.toggled.connect(self.on_log_enabled_changed)
            self.log_path_edit = QLineEdit(core.config.get("log_file_path", "") or "")
            self.log_path_edit.setReadOnly(True)
            self.log_path_edit.setPlaceholderText(t("首次开启日志时请选择保存路径"))
            btn_choose_log = QPushButton(t("选择日志路径"))
            btn_choose_log.setProperty("secondary", True)
            btn_choose_log.clicked.connect(self.choose_log_file_path)
            path_grid.addWidget(self.log_enabled_check, 0, 0, 1, 2)
            path_grid.addWidget(self.log_path_edit, 1, 0)
            path_grid.addWidget(btn_choose_log, 1, 1)
            layout.addWidget(path_box)

            controls = QHBoxLayout()
            btn_load = QPushButton(t("刷新日志"))
            btn_load.setProperty("secondary", True)
            btn_load.clicked.connect(self.load_log_file)
            btn_clear_view = QPushButton(t("清空显示"))
            btn_clear_view.setProperty("secondary", True)
            btn_clear_view.clicked.connect(lambda: self.log_box.clear())
            btn_delete = QPushButton(t("清空/删除日志文件"))
            btn_delete.setProperty("secondary", True)
            btn_delete.clicked.connect(self.delete_log_file)
            btn_export = QPushButton(t("导出日志"))
            btn_export.setProperty("secondary", True)
            btn_export.clicked.connect(self.export_log_file)
            for w in (btn_load, btn_clear_view, btn_delete, btn_export):
                controls.addWidget(w)
            controls.addStretch(1)
            layout.addLayout(controls)

            self.log_box = QTextEdit()
            self.log_box.setReadOnly(True)
            layout.addWidget(self.log_box, 1)
            self.load_log_file()
            return page

        def _setup_about_sprite_animation(self):
            """about.png 是三态竖排精灵图，提供普通、悬停、按下三态动画。"""
            if not hasattr(self, "about_sprite_btn"):
                return
            path = self._img_path("about.png")
            self._about_frames = []
            if os.path.exists(path):
                pix = QPixmap(path)
                if not pix.isNull():
                    frame_h = pix.width()
                    count = max(1, pix.height() // frame_h)
                    for i in range(count):
                        frame = pix.copy(0, i * frame_h, pix.width(), frame_h).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self._about_frames.append(frame)
            if not self._about_frames:
                self.about_sprite_btn.setText(t("关于"))
                return
            self._about_state = 0
            self._about_anim_step = 0
            self._about_anim_from = self._about_frames[0]
            self._about_anim_to = self._about_frames[0]
            self.about_sprite_btn.setIcon(QIcon(self._about_frames[0]))
            self.about_sprite_btn.setIconSize(QSize(64, 64))
            self._about_anim_timer = QTimer(self)
            self._about_anim_timer.setInterval(18)
            self._about_anim_timer.timeout.connect(self._advance_about_crossfade)

        def _blend_about_frames(self, start: QPixmap, target: QPixmap, ratio: float) -> QPixmap:
            out = QPixmap(start.size())
            out.fill(Qt.transparent)
            painter = QPainter(out)
            painter.setOpacity(1.0)
            painter.drawPixmap(0, 0, start)
            painter.setOpacity(max(0.0, min(1.0, ratio)))
            painter.drawPixmap(0, 0, target)
            painter.end()
            return out

        def _fade_about_sprite_to(self, state: int):
            if not getattr(self, "_about_frames", None):
                return
            state = max(0, min(state, len(self._about_frames) - 1))
            if state == getattr(self, "_about_state", 0) and not self._about_anim_timer.isActive():
                return
            self._about_anim_timer.stop()
            self._about_anim_from = self._about_frames[getattr(self, "_about_state", 0)]
            self._about_anim_to = self._about_frames[state]
            self._about_target_state = state
            self._about_anim_step = 0
            self._about_anim_timer.start()

        def _advance_about_crossfade(self):
            steps = 10
            self._about_anim_step += 1
            ratio = self._about_anim_step / steps
            if ratio >= 1:
                self._about_anim_timer.stop()
                self._about_state = getattr(self, "_about_target_state", 0)
                self.about_sprite_btn.setIcon(QIcon(self._about_frames[self._about_state]))
                return
            self.about_sprite_btn.setIcon(QIcon(self._blend_about_frames(self._about_anim_from, self._about_anim_to, ratio)))

        def eventFilter(self, obj, event):
            try:
                if isinstance(obj, QListView) and obj.objectName() == "ComboPopupView" and event.type() == QEvent.Type.Show:
                    self._animate_widget_flash(obj, 120)
            except Exception:
                pass
            if getattr(self, "about_sprite_btn", None) is obj:
                if event.type() == QEvent.Type.Enter:
                    self._fade_about_sprite_to(1)
                elif event.type() == QEvent.Type.Leave:
                    self._fade_about_sprite_to(0)
                elif event.type() == QEvent.Type.MouseButtonPress:
                    self._fade_about_sprite_to(2)
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    self._fade_about_sprite_to(1)
            return super().eventFilter(obj, event)

        def _app_command(self, *args: str) -> list[str]:
            """源码运行和 PyInstaller onedir 运行都能打开同一个入口。"""
            if getattr(sys, "frozen", False):
                return [sys.executable, *args]
            return [sys.executable, os.path.join(core.BASE_DIR, "main.py"), *args]

        def open_url(self, url: str):
            QDesktopServices.openUrl(QUrl(url))

        def _handle_about_link(self, link: str):
            if link == "app://shishe":
                self.open_shishe_image()
            elif link == "app://about-window":
                self.open_local_image("about-window.png")
            elif link == "app://about-dialog":
                self.show_about_dialog()
            else:
                self.open_url(link)

        def _default_log_path(self) -> str:
            return os.path.join(str(Path.home()), "ShangBackground_wallpaper_debug.log")

        def _log_file_path(self) -> str:
            return core.config.get("log_file_path", "") or ""

        def choose_log_file_path(self):
            default = self._log_file_path() or self._default_log_path()
            dest, _ = QFileDialog.getSaveFileName(self, t("选择日志保存路径"), default, t("日志文件 (*.log *.txt);;所有文件 (*.*)"))
            if not dest:
                return False
            core.config["log_file_path"] = dest
            core.save_config()
            if hasattr(self, "log_path_edit"):
                self.log_path_edit.setText(dest)
            self.set_status(t("日志路径已设置：") + f"{dest}")
            return True

        def on_log_enabled_changed(self, checked: bool):
            if checked and not self._log_file_path():
                if not self.choose_log_file_path():
                    self.log_enabled_check.blockSignals(True)
                    self.log_enabled_check.setChecked(False)
                    self.log_enabled_check.blockSignals(False)
                    core.config["log_enabled"] = False
                    core.save_config()
                    self.set_status(t("已取消开启日志"))
                    return
            core.config["log_enabled"] = bool(checked)
            core.save_config()
            self.set_status(t("日志文件记录已开启") if checked else t("日志文件记录已关闭"))
            self.load_log_file()

        def load_log_file(self):
            if not hasattr(self, "log_box"):
                return
            path = self._log_file_path()
            self.log_box.clear()
            if hasattr(self, "log_path_edit"):
                self.log_path_edit.setText(path)
            if not core.config.get("log_enabled", False) and not path:
                self.log_box.setPlainText(t("日志默认关闭。需要记录文件日志时，请先开启日志并选择保存路径。"))
                return
            if not path:
                self.log_box.setPlainText(t("尚未设置日志路径。"))
                return
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        self.log_box.setPlainText(f.read()[-120000:])
                except Exception as e:
                    self.log_box.setPlainText(t("读取日志失败：") + str(e))
            else:
                self.log_box.setPlainText(t("暂无日志文件。开启日志后，新日志会写入所选路径。"))

        def delete_log_file(self):
            path = self._log_file_path()
            if not path:
                QMessageBox.information(self, t("日志"), t("尚未设置日志路径。"))
                return
            try:
                if os.path.exists(path):
                    os.remove(path)
                if hasattr(self, "log_box"):
                    self.log_box.clear()
                self.set_status(t("日志文件已删除"))
            except Exception as e:
                QMessageBox.warning(self, t("日志"), t("删除日志失败：") + str(e))

        def export_log_file(self):
            src = self._log_file_path()
            default = self._default_log_path()
            dest, _ = QFileDialog.getSaveFileName(self, t("导出日志"), default, t("日志文件 (*.log *.txt);;所有文件 (*.*)"))
            if not dest:
                return
            try:
                if src and os.path.exists(src):
                    shutil.copyfile(src, dest)
                else:
                    with open(dest, "w", encoding="utf-8") as f:
                        f.write(self.log_box.toPlainText() if hasattr(self, "log_box") else "")
                self.set_status(t("日志已导出：") + f"{dest}")
            except Exception as e:
                QMessageBox.warning(self, t("日志"), t("导出日志失败：") + str(e))

        def open_local_image(self, name: str):
            path = self._img_path(name)
            if os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.warning(self, t("资源缺失"), t("找不到图片：") + str(name))

        def open_shishe_image(self):
            self.open_local_image("shishe.png")

        def refresh_from_config(self):
            cfg = core.config
            self._set_combo_current_data(self.mode_combo, normalize_mode_key(cfg.get("mode", "幻灯片放映")))
            self._set_combo_current_data(self.fit_combo, normalize_style_key(cfg.get("fit_mode", "填充")))
            self.folder_edit.setText(cfg.get("slide_folder", ""))
            self.seconds_spin.setValue(int(cfg.get("slide_seconds", 300)))
            self.shuffle_check.setChecked(bool(cfg.get("shuffle", False)))
            self.single_edit.setText(cfg.get("single_image", ""))
            self.angle_spin.setValue(int(cfg.get("gradient_angle", 60)))
            self._paint_button(self.solid_btn, cfg.get("solid_color", "#ffffff"))
            self._paint_button(self.grad1_btn, cfg.get("solid_color", "#ffffff"))
            self._paint_button(self.grad2_btn, cfg.get("gradient_color2", "#ffffff"))
            if hasattr(self, "ctx_prev"):
                ctx_widgets = (self.ctx_prev, self.ctx_next, self.ctx_random, self.ctx_jump)
                for widget in ctx_widgets:
                    widget.blockSignals(True)
                self.ctx_prev.setChecked(bool(cfg.get("ctx_last_wallpaper", False)))
                self.ctx_next.setChecked(bool(cfg.get("ctx_next_wallpaper", False)))
                self.ctx_random.setChecked(bool(cfg.get("ctx_random_wallpaper", False)))
                self.ctx_jump.setChecked(bool(cfg.get("ctx_jump_to_wallpaper", False)))
                for widget in ctx_widgets:
                    widget.blockSignals(False)
                self._refresh_context_shortcut_labels()
            if hasattr(self, "ctx_shortcut_edits"):
                for action, edit in self.ctx_shortcut_edits.items():
                    edit.blockSignals(True)
                    edit.setText(self._context_hotkey(action))
                    edit.blockSignals(False)
                self._refresh_context_shortcut_labels()

            settings_widgets = ("bg_check", "auto_start_check", "tray_check", "tray_notify_check")
            if all(hasattr(self, name) for name in settings_widgets):
                widgets = tuple(getattr(self, name) for name in settings_widgets)
                for widget in widgets:
                    widget.blockSignals(True)
                self.bg_check.setChecked(bool(cfg.get("run_in_background", True)))
                self.auto_start_check.setChecked(bool(cfg.get("auto_start", False)))
                self.tray_check.setChecked(bool(cfg.get("tray_icon", True)))
                self.tray_notify_check.setChecked(bool(cfg.get("tray_notify", True)))
                for widget in widgets:
                    widget.blockSignals(False)

            if hasattr(self, "tray_menu_checks"):
                menu_items = cfg.get("tray_menu_items") or ["show", "previous", "next", "random", "bing", "jump", "about", "exit"]
                if menu_items and isinstance(menu_items[0], dict):
                    menu_items = [item.get("action") for item in menu_items if item.get("enabled", True)]
                for action, cb in self.tray_menu_checks.items():
                    cb.blockSignals(True)
                    cb.setChecked(action in menu_items)
                    cb.blockSignals(False)

            if hasattr(self, "tray_action"):
                self.tray_action.blockSignals(True)
                wanted_action = cfg.get("tray_click_action", "next")
                idx = self.tray_action.findData(wanted_action)
                fallback = self.tray_action.findData("next")
                self.tray_action.setCurrentIndex(idx if idx >= 0 else fallback)
                self.tray_action.blockSignals(False)
            if hasattr(self, "bing_cache_edit"):
                self.bing_cache_edit.setText(cfg.get("bing_cache_dir", "") or "")
            if hasattr(self, "bing_count_spin"):
                self.bing_count_spin.blockSignals(True)
                self.bing_count_spin.setValue(int(cfg.get("bing_sync_count", 1)))
                self.bing_count_spin.blockSignals(False)
            if hasattr(self, "font_path_edit"):
                self.font_path_edit.setText(cfg.get("font_path", "") or "")
            if hasattr(self, "theme_color_edit"):
                self.theme_color_edit.setText(getattr(self, "_theme_color", cfg.get("theme_color", DEFAULT_THEME_COLOR)))
                self._update_theme_color_preview()
            if hasattr(self, "dpi_scale_slider"):
                self.dpi_scale_slider.blockSignals(True)
                self.dpi_scale_slider.setValue(dpi_percent(cfg.get("dpi_scale", 1.0)))
                self.dpi_scale_slider.blockSignals(False)
                if hasattr(self, "dpi_scale_value_label"):
                    self.dpi_scale_value_label.setText(f"{self.dpi_scale_slider.value()}%")
            self.update_control_states()

        def update_control_states(self):
            mode = normalize_mode_key(core.config.get("mode", self.mode_combo.currentData() if self._is_qobject_alive(self.mode_combo) else "幻灯片放映"))
            is_slide = mode == "幻灯片放映"
            is_image = mode == "图片"
            is_solid = mode == "纯色"
            is_gradient = mode == "渐变"

            for w in (self.folder_edit, self.btn_browse_folder, self.seconds_spin, self.shuffle_check,
                      self.btn_prev, self.btn_next, self.btn_random, self.btn_random_prob, self.btn_start, self.btn_stop):
                w.setEnabled(is_slide)
            self.single_edit.setEnabled(is_image)
            self.btn_single.setEnabled(is_image)
            self.solid_btn.setEnabled(is_solid)
            self.grad1_btn.setEnabled(is_gradient)
            self.grad2_btn.setEnabled(is_gradient)
            self.angle_spin.setEnabled(is_gradient)
            self.angle_apply_btn.setEnabled(is_gradient)

            self.slide_box.setEnabled(is_slide)
            self.single_box.setEnabled(is_image)
            # 色彩区域保持可见，只把当前模式不可用的按钮置灰，避免用户误以为配置丢失。
            self.color_box.setEnabled(True)
            self._refresh_color_buttons()

        def _run_core_sync(self, fn, *args):
            name = getattr(fn, "__name__", t("操作"))
            self.begin_operation(f"正在执行：{name}")
            try:
                QApplication.processEvents()
                result = fn(*args)
                core.save_config()
                self._schedule_preview_refresh()
                self.finish_operation(t("操作完成"))
                return result
            except Exception as e:
                self.finish_operation(t("操作失败"))
                QMessageBox.warning(self, t("错误"), str(e))
                core.log(f"PySide6 操作失败: {e}")
                return None

        def run_core(self, fn, *args):
            """Run slow wallpaper operations off the GUI thread to keep PySide responsive."""
            name = getattr(fn, "__name__", t("操作"))
            async_safe = {"previous_wallpaper", "next_wallpaper", "random_wallpaper", "set_wallpaper", "set_wallpaper_direct"}
            if name not in async_safe:
                return self._run_core_sync(fn, *args)
            if self._core_busy:
                self.set_status(t("已有壁纸操作正在执行，请稍候…"))
                return None
            self._core_busy = True
            self.begin_operation(f"正在执行：{name}", cancellable=False)

            def _worker():
                try:
                    result = fn(*args)
                    core.save_config()
                    self.core_result_signal.emit(True, t("操作完成"), result)
                except Exception as exc:
                    core.log(f"后台壁纸操作失败: {exc}")
                    self.core_result_signal.emit(False, str(exc), None)

            self._core_worker_thread = threading.Thread(target=_worker, daemon=True)
            self._core_worker_thread.start()
            return None

        def _on_core_finished(self, ok: bool, message: str, _result):
            self._core_busy = False
            self._schedule_preview_refresh()
            self.finish_operation(message if ok else t("操作失败"))
            if not ok:
                QMessageBox.warning(self, t("错误"), message)


        def on_mode_changed(self, _index=None):
            mode_key = normalize_mode_key(self.mode_combo.currentData() if self._is_qobject_alive(self.mode_combo) else _index)
            core.config["mode"] = mode_key
            core.save_config()
            self.update_control_states()
            self.set_status(t("正在切换模式…"))

            def _apply_mode():
                if mode_key == "幻灯片放映":
                    self.run_core(core.restart_slideshow)
                elif mode_key == "图片":
                    img = core.config.get("single_image")
                    if img and os.path.exists(img):
                        self.run_core(core.set_wallpaper, img, t("切换单张图片模式"))
                    else:
                        self._schedule_preview_refresh()
                elif mode_key == "纯色":
                    self.run_core(core.apply_solid)
                elif mode_key == "渐变":
                    self.apply_gradient_wallpaper()
                else:
                    self._schedule_preview_refresh()

            QTimer.singleShot(0, _apply_mode)

        def on_fit_changed(self, _index=None):
            fit_key = normalize_style_key(self.fit_combo.currentData() if self._is_qobject_alive(self.fit_combo) else _index)
            core.config["fit_mode"] = fit_key
            self.run_core(core.set_fit_mode, fit_key)

        def choose_folder(self):
            folder = QFileDialog.getExistingDirectory(self, t("选择壁纸文件夹"), self.folder_edit.text() or str(Path.home()))
            if not folder:
                return
            core.config["slide_folder"] = folder
            self.folder_edit.setText(folder)
            core.config["mode"] = "幻灯片放映"
            self._set_combo_current_data(self.mode_combo, "幻灯片放映")
            core.save_config()
            self.run_core(core.restart_slideshow)

        def on_seconds_changed(self, value):
            core.config["slide_seconds"] = int(value)
            core.save_config()
            if normalize_mode_key(core.config.get("mode")) == "幻灯片放映":
                core.restart_slideshow()

        def on_shuffle_changed(self, checked):
            core.config["shuffle"] = bool(checked)
            core.save_config()
            if normalize_mode_key(core.config.get("mode")) == "幻灯片放映":
                core.restart_slideshow()

        def choose_single_image(self):
            path, _ = QFileDialog.getOpenFileName(self, t("选择图片"), str(Path.home()), t("图片文件 (*.jpg *.jpeg *.png *.bmp);;所有文件 (*.*)"))
            if not path:
                return
            core.config["single_image"] = path
            core.config["mode"] = "图片"
            self.single_edit.setText(path)
            self._set_combo_current_data(self.mode_combo, "图片")
            core.save_config()
            self.run_core(core.set_wallpaper, path, t("单张图片"))

        def choose_solid_color(self):
            color = QColorDialog.getColor(QColor(core.config.get("solid_color", "#ffffff")), self, t("选择纯色"))
            if not color.isValid():
                return
            value = color.name()
            core.config["solid_color"] = value
            self._paint_button(self.solid_btn, value)
            core.save_config()
            if normalize_mode_key(core.config.get("mode")) == "纯色":
                self.run_core(core.apply_solid)

        def choose_gradient_color(self, index: int):
            key = "solid_color" if index == 1 else "gradient_color2"
            color = QColorDialog.getColor(QColor(core.config.get(key, "#ffffff")), self, t("选择渐变颜色"))
            if not color.isValid():
                return
            core.config[key] = color.name()
            self._paint_button(self.grad1_btn if index == 1 else self.grad2_btn, color.name())
            core.save_config()
            if normalize_mode_key(core.config.get("mode")) == "渐变":
                self.apply_gradient_wallpaper()

        def on_gradient_changed(self, value):
            core.config["gradient_angle"] = int(value)
            core.save_config()

        def on_gradient_apply(self):
            if normalize_mode_key(core.config.get("mode")) == "渐变":
                self.apply_gradient_wallpaper()

        def apply_gradient_wallpaper(self):
            c1 = core.config.get("solid_color", "#ffffff")
            c2 = core.config.get("gradient_color2", "#ffffff")
            angle = int(core.config.get("gradient_angle", 60))
            path = core.create_gradient_wallpaper(c1, c2, angle)
            if path:
                self.run_core(core.set_wallpaper_direct, path, t("渐变"))

        def _refresh_color_buttons(self):
            if not all(hasattr(self, name) for name in ("solid_btn", "grad1_btn", "grad2_btn")):
                return
            self._paint_button(self.solid_btn, core.config.get("solid_color", "#ffffff"))
            self._paint_button(self.grad1_btn, core.config.get("solid_color", "#ffffff"))
            self._paint_button(self.grad2_btn, core.config.get("gradient_color2", "#ffffff"))

        def _paint_button(self, btn: QPushButton, color: str):
            qcolor = QColor(color if color else "#ffffff")
            if not qcolor.isValid():
                qcolor = QColor("#ffffff")
                color = "#ffffff"
            # 白色/浅色背景使用深色文字，解决默认纯色为白色时按钮文字不可读的问题。
            brightness = (qcolor.red() * 299 + qcolor.green() * 587 + qcolor.blue() * 114) / 1000
            text_color = "#24292f" if brightness >= 170 else "#ffffff"
            border = "#c9d1d9" if brightness >= 230 else qcolor.darker(115).name()
            hover_border = self._theme_color if hasattr(self, "_theme_color") else core.config.get("theme_color", DEFAULT_THEME_COLOR)
            btn.setStyleSheet(
                "QPushButton {"
                f" background: {qcolor.name()};"
                f" border: 1px solid {border};"
                f" border-radius: 6px; color: {text_color}; padding: 5px 12px; font-weight: 600; }}"
                f"QPushButton:hover:enabled {{ border: 1px solid {hover_border}; }}"
                "QPushButton:disabled { background: #eaeef2; border: 1px solid #d0d7de; color: #8c959f; }"
            )
            try:
                btn.style().unpolish(btn)
                btn.style().polish(btn)
            except Exception:
                pass
            btn.update()

        def _context_action_defs(self):
            return [
                ("previous", t("上一张壁纸"), "U", "ctx_last_wallpaper", "ctx_prev"),
                ("next", t("下一张壁纸"), "N", "ctx_next_wallpaper", "ctx_next"),
                ("random", t("随机壁纸"), "3", "ctx_random_wallpaper", "ctx_random"),
                ("jump", t("跳转到壁纸"), "V", "ctx_jump_to_wallpaper", "ctx_jump"),
            ]

        def _context_hotkey(self, action: str) -> str:
            default_map = {item[0]: item[2] for item in self._context_action_defs()}
            return str(core.config.get(f"hotkey_{action}", default_map.get(action, "")) or "").strip()

        def _context_hotkey_display(self, action: str) -> str:
            raw = self._context_hotkey(action)
            if not raw:
                return t("当前：无")
            parts = [p.strip() for p in raw.replace("-", "+").split("+") if p.strip()]
            names = {"ctrl": "Ctrl", "control": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win", "meta": "Win"}
            display = "+".join(names.get(p.lower(), p.upper() if len(p) == 1 else p) for p in parts)
            return f"当前：{display}"

        def _context_checkbox_label(self, action: str, label: str) -> str:
            return f"{label}（{self._context_hotkey_display(action).replace('当前：', '')}）"

        def _refresh_context_shortcut_labels(self):
            for action, label, _default_key, _cfg_key, widget_name in self._context_action_defs():
                widget = getattr(self, widget_name, None)
                if self._is_qobject_alive(widget):
                    widget.setText(self._context_checkbox_label(action, label))
                current_labels = getattr(self, "ctx_shortcut_current_labels", {})
                if action in current_labels and self._is_qobject_alive(current_labels[action]):
                    current_labels[action].setText(self._context_hotkey_display(action))

        def on_context_hotkey_changed(self, action: str, edit: QLineEdit):
            value = edit.text().strip().replace(" ", "")
            core.config[f"hotkey_{action}"] = value
            core.save_config()
            edit.setText(value)
            self._refresh_context_shortcut_labels()
            self.set_status(t("右键菜单快捷键已保存"))

        def _update_ctx(self, key, value):
            core.config[key] = bool(value)
            core.config["ctx_set_wallpaper"] = False
            core.config["ctx_global_settings"] = False
            core.config["ctx_personalize"] = False
            core.save_config()

        def ask_yes_no(self, title: str, text: str, *, default_yes: bool = True) -> bool:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle(title)
            box.setText(text)
            yes_btn = box.addButton(t("是"), QMessageBox.ButtonRole.YesRole)
            no_btn = box.addButton(t("否"), QMessageBox.ButtonRole.NoRole)
            box.setDefaultButton(yes_btn if default_yes else no_btn)
            box.exec()
            return box.clickedButton() is yes_btn

        def register_context_with_prompt(self):
            if core.IS_WINDOWS and not core.is_windows_admin():
                if self.ask_yes_no(
                    t("需要管理员权限"),
                    t("同步桌面右键菜单需要写入 HKEY_CLASSES_ROOT。是否以管理员身份重启并继续？"),
                    default_yes=True,
                ):
                    self.restart_as_admin(extra_args=["--sync-context-on-start"])
                return
            self.sync_context_menu(show_message=True)

        def sync_context_menu(self, show_message=False):
            ok = core.register_context(show_admin_prompt=False)
            self.set_status(t("右键菜单已同步") if ok else t("右键菜单同步失败或已跳过"))
            if show_message:
                QMessageBox.information(self, t("右键菜单"), t("同步完成") if ok else t("同步失败或已跳过"))
            return ok

        def open_global_settings_from_home(self):
            dlg = getattr(self, "_settings_dialog", None)
            if self._is_qobject_alive(dlg):
                try:
                    dlg.show()
                    dlg.raise_()
                    dlg.activateWindow()
                    return
                except RuntimeError:
                    self._clear_settings_widget_refs()
            else:
                self._clear_settings_widget_refs()

            dialog = QDialog(self)
            self._settings_dialog = dialog
            dialog.setWindowTitle(t("全局设置"))
            icon_path = self._img_path("settings.svg")
            if os.path.exists(icon_path):
                dialog.setWindowIcon(QIcon(icon_path))
            elif not getattr(self, "app_icon", QIcon()).isNull():
                dialog.setWindowIcon(self.app_icon)
            dialog.setModal(False)
            dialog.resize(860, 620)
            dialog.setMinimumSize(780, 560)
            if getattr(self, "_theme_stylesheet", ""):
                dialog.setStyleSheet(self._theme_stylesheet)
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(10)
            settings_page = self._settings_tab()
            layout.addWidget(settings_page)
            self.refresh_from_config()
            dialog.destroyed.connect(lambda *_: self._clear_settings_widget_refs())
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            try:
                effect = QGraphicsOpacityEffect(dialog)
                dialog.setGraphicsEffect(effect)
                anim = QPropertyAnimation(effect, b"opacity", dialog)
                anim.setDuration(180)
                anim.setStartValue(0.25)
                anim.setEndValue(1.0)
                anim.setEasingCurve(QEasingCurve.OutCubic)
                self._animations.append(anim)
                anim.start()
            except Exception:
                pass
            self.set_status(t("已打开全局设置"))

        # ---------- 随机概率（百分比） ----------
        def open_random_probability_settings(self):
            folder = (self.folder_edit.text().strip() if hasattr(self, "folder_edit") else "") or core.config.get("slide_folder", "")
            if not folder or not os.path.isdir(folder):
                QMessageBox.information(self, t("随机概率"), t("请先在幻灯片放映中选择有效的壁纸文件夹。"))
                return

            existing = getattr(self, "_random_probability_dialog", None)
            if existing is not None:
                try:
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                    return
                except RuntimeError:
                    self._random_probability_dialog = None

            try:
                import random_copy
                from probability_dialog import RandomProbabilityDialog
                images = random_copy.get_original_image_paths(folder)
            except Exception as exc:
                QMessageBox.warning(self, t("随机概率"), t("加载随机概率设置失败：") + str(exc))
                return

            if not images:
                QMessageBox.information(self, t("随机概率"), t("当前文件夹中没有可设置的壁纸图片。"))
                return

            def on_saved():
                self.set_status(t("随机壁纸百分比已保存"))

            dialog = RandomProbabilityDialog(
                self,
                folder,
                images,
                random_copy,
                translate=t,
                on_saved=on_saved,
                logger=core.log,
            )
            self._random_probability_dialog = dialog
            if not getattr(self, "app_icon", QIcon()).isNull():
                dialog.setWindowIcon(self.app_icon)
            if getattr(self, "_theme_stylesheet", ""):
                dialog.setStyleSheet(self._theme_stylesheet)

            def cleanup_dialog(*_args):
                if getattr(self, "_random_probability_dialog", None) is dialog:
                    self._random_probability_dialog = None

            dialog.destroyed.connect(cleanup_dialog)
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()

        def _linux_autostart_command(self) -> str:
            if core.is_frozen():
                return shlex_join([sys.executable, "--hide"])
            return shlex_join([sys.executable, os.path.abspath(__file__), "--hide"])

        def set_auto_start(self, enable: bool):
            """Linux 分支仅写入 XDG autostart，不保留 Windows/macOS 启动项兼容逻辑。"""
            autostart_dir = os.path.expanduser("~/.config/autostart")
            desktop_path = os.path.join(autostart_dir, "shangbackground.desktop")
            if enable:
                os.makedirs(autostart_dir, exist_ok=True)
                desktop_content = (
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=ShangBackground\n"
                    f"Exec={self._linux_autostart_command()}\n"
                    "Hidden=false\n"
                    "NoDisplay=false\n"
                    "X-GNOME-Autostart-enabled=true\n"
                    "Comment=Desktop wallpaper manager\n"
                )
                try:
                    with open(desktop_path, "w", encoding="utf-8") as f:
                        f.write(desktop_content)
                    core.log(t("Linux 开机自启动已启用"))
                except Exception as exc:
                    core.log(t("Linux 自启动 .desktop 文件创建失败") + f": {exc}")
                    raise
            else:
                if os.path.exists(desktop_path):
                    try:
                        os.remove(desktop_path)
                        core.log(t("Linux 开机自启动已禁用"))
                    except Exception as exc:
                        core.log(t("Linux 自启动 .desktop 文件删除失败") + f": {exc}")
                        raise

        def on_auto_start_changed(self, checked):
            try:
                self.set_auto_start(bool(checked))
                core.config["auto_start"] = bool(checked)
                core.config["auto_start_prompt_shown"] = True
                core.save_config()
                self.set_status(t("开机自启动已启用") if checked else t("开机自启动已关闭"))
            except Exception as e:
                if hasattr(self, "auto_start_check"):
                    self.auto_start_check.blockSignals(True)
                    self.auto_start_check.setChecked(not bool(checked))
                    self.auto_start_check.blockSignals(False)
                QMessageBox.warning(self, t("开机自启动"), t("设置开机自启动失败：") + str(e))

        def on_tray_notify_changed(self, checked):
            core.config["tray_notify"] = bool(checked)
            core.save_config()

        def maybe_show_auto_start_prompt(self):
            if core.config.get("auto_start_prompt_shown", False):
                return
            if core.hide_window:
                return
            self.show_auto_start_prompt()

        def show_auto_start_prompt(self):
            dialog = QDialog(self)
            dialog.setWindowTitle(t("开机自启动建议"))
            dialog.setModal(True)
            dialog.setFixedSize(520, 300)
            if os.path.exists(self.icon_path):
                dialog.setWindowIcon(QIcon(self.icon_path))
            if getattr(self, "_theme_stylesheet", ""):
                dialog.setStyleSheet(self._theme_stylesheet)

            main = QVBoxLayout(dialog)
            main.setContentsMargins(22, 20, 22, 18)
            main.setSpacing(10)
            top_row = QHBoxLayout()
            hello_label = QLabel()
            hello_path = self._img_path("hello.png")
            if os.path.exists(hello_path):
                pix = QPixmap(hello_path)
                if not pix.isNull():
                    hello_label.setPixmap(pix.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            hello_label.setFixedSize(104, 104)
            hello_label.setAlignment(Qt.AlignCenter)
            top_row.addWidget(hello_label)
            title = QLabel(t("您是否想要开机自启动本工具？"))
            title.setWordWrap(True)
            title.setStyleSheet("font-size: 18px; font-weight: 700;")
            top_row.addWidget(title, 1)
            main.addLayout(top_row)

            info = QTextEdit()
            info.setReadOnly(True)
            info.setFixedHeight(82)
            info.setText(t("开机自启动后，软件会后台运行，而且占用资源极少，基本不会影响开机速度。确定后，此操作可能会被杀毒软件拦截，您可以选择允许或加入白名单。"))
            info.setStyleSheet("QTextEdit { border-radius: 8px; padding: 8px; font-size: 13px; }")
            main.addWidget(info)

            buttons = QHBoxLayout()
            buttons.addStretch(1)
            btn_yes = QPushButton(t("好哒"))
            btn_no = QPushButton(t("不，并不再提示"))
            btn_yes.setMinimumHeight(36)
            btn_no.setMinimumHeight(36)
            buttons.addWidget(btn_yes)
            buttons.addWidget(btn_no)
            main.addLayout(buttons)

            def accept_startup():
                try:
                    self.set_auto_start(True)
                    core.config["auto_start"] = True
                    core.config["auto_start_prompt_shown"] = True
                    core.save_config()
                    if hasattr(self, "auto_start_check"):
                        self.auto_start_check.blockSignals(True)
                        self.auto_start_check.setChecked(True)
                        self.auto_start_check.blockSignals(False)
                    self.set_status(t("开机自启动已启用"))
                    dialog.accept()
                except Exception as e:
                    QMessageBox.warning(dialog, t("开机自启动"), t("设置开机自启动失败：") + str(e))

            def reject_startup():
                core.config["auto_start"] = False
                core.config["auto_start_prompt_shown"] = True
                core.save_config()
                if hasattr(self, "auto_start_check"):
                    self.auto_start_check.blockSignals(True)
                    self.auto_start_check.setChecked(False)
                    self.auto_start_check.blockSignals(False)
                self.set_status(t("已跳过开机自启动"))
                dialog.reject()

            btn_yes.clicked.connect(accept_startup)
            btn_no.clicked.connect(reject_startup)
            dialog.exec()

        def on_background_changed(self, checked):
            core.config["run_in_background"] = bool(checked)
            core.save_config()

        def on_tray_changed(self, checked):
            core.config["tray_icon"] = bool(checked)
            core.save_config()
            if checked:
                self.create_or_update_tray()
            elif self.tray:
                self.tray.hide()
                self.tray.deleteLater()
                self.tray = None

        def on_tray_action_changed(self, index):
            action = self.tray_action.itemData(index) or "next"
            core.config["tray_click_action"] = action
            core.save_config()
            self.create_or_update_tray()

        def on_tray_menu_changed(self):
            if not hasattr(self, "tray_menu_checks"):
                return
            selected = [action for action, cb in self.tray_menu_checks.items() if cb.isChecked()]
            required = ["show", "exit"]
            for item in required:
                if item not in selected:
                    selected.append(item)
                    self.tray_menu_checks[item].setChecked(True)
            core.config["tray_menu_items"] = selected
            core.save_config()
            self.create_or_update_tray()

        def create_or_update_tray(self):
            if not QSystemTrayIcon.isSystemTrayAvailable():
                core.log(t("系统托盘不可用，已跳过"))
                return
            if self.tray is None:
                icon = QIcon(self.icon_path) if os.path.exists(self.icon_path) else self.windowIcon()
                self.tray = QSystemTrayIcon(icon, self)
                self.tray.activated.connect(self.on_tray_activated)
            else:
                icon = QIcon(self.icon_path) if os.path.exists(self.icon_path) else self.windowIcon()
                self.tray.setIcon(icon)

            labels = {
                "show": t("打开设置主界面"),
                "previous": t("上一张壁纸"),
                "next": t("下一张壁纸"),
                "random": t("随机壁纸"),
                "bing": t("同步必应壁纸"),
                "jump": t("跳转到壁纸"),
                "about": t("关于"),
                "exit": t("退出程序"),
            }
            defaults = ["show", "previous", "next", "random", "bing", "jump", "about", "exit"]
            actions = core.config.get("tray_menu_items") or defaults
            if isinstance(actions, list) and actions and isinstance(actions[0], dict):
                actions = [item.get("action") for item in actions if item.get("enabled", True)]
            actions = [a for a in actions if a in labels]
            if not actions:
                actions = defaults

            menu = QMenu()
            action_map = {
                "show": self.show_from_tray,
                "previous": lambda: self.run_core(core.previous_wallpaper),
                "next": lambda: self.run_core(core.next_wallpaper),
                "random": lambda: self.run_core(core.random_wallpaper),
                "bing": lambda: self.sync_bing_wallpaper(set_latest=True),
                "jump": self.open_wallpaper_sidebar,
                "about": self.show_about_dialog,
                "exit": self.exit_app,
            }
            for i, name in enumerate(actions):
                if i and name in {"about", "exit"}:
                    menu.addSeparator()
                menu.addAction(labels[name], action_map[name])
            self.tray.setContextMenu(menu)
            self.tray.setToolTip(APP_DISPLAY_NAME)
            self.tray.show()

        def on_tray_activated(self, reason):
            if reason == QSystemTrayIcon.Trigger:
                action = core.config.get("tray_click_action", "next")
                if action == "none":
                    return
                if action == "show":
                    self.show_from_tray()
                elif action == "previous":
                    self.run_core(core.previous_wallpaper)
                elif action == "random":
                    self.run_core(core.random_wallpaper)
                elif action == "jump":
                    self.open_wallpaper_sidebar()
                else:
                    self.run_core(core.next_wallpaper)

        def show_from_tray(self):
            self.showNormal()
            self.raise_()
            self.activateWindow()

        def update_preview(self):
            path = core.config.get("current_wallpaper") or core.get_current_wallpaper()
            if path and os.path.exists(path):
                self._last_preview_path = path
                self.current_label.setText(path)
                self.current_label.setToolTip(path)
                self.preview_canvas.set_preview(path)
            else:
                self._last_preview_path = ""
                self.current_label.setText("")
                self.current_label.setToolTip(t("未检测到当前壁纸"))
                self.preview_canvas.set_preview("")
            self.refresh_history_list()

        def update_preview_if_changed(self):
            path = core.config.get("current_wallpaper") or core.get_current_wallpaper()
            hist_len = len(core.config.get("history", []))
            if path != getattr(self, "_last_preview_path", "") or hist_len != getattr(self, "_last_history_len", -1):
                self.update_preview()

        def _schedule_preview_refresh(self, initial_delay: int = 0):
            """分批刷新预览；initial_delay 用于启动期把图片解码让到界面显示之后。"""
            def _first_refresh():
                self.update_preview()
                for delay in (120, 450, 1000, 1800):
                    QTimer.singleShot(delay, self.update_preview_if_changed)
            if initial_delay and initial_delay > 0:
                QTimer.singleShot(int(initial_delay), _first_refresh)
            else:
                _first_refresh()

        def refresh_history_list(self):
            if not hasattr(self, "history_list"):
                return
            selected = self.history_list.currentItem().data(Qt.UserRole) if self.history_list.currentItem() else None
            self.history_list.blockSignals(True)
            self.history_list.clear()
            seen = set()
            self._last_history_len = len(core.config.get("history", []))
            for path in core.config.get("history", [])[:8]:
                if not path or path in seen or not os.path.exists(path):
                    continue
                seen.add(path)
                item = QListWidgetItem()
                item.setToolTip(path)
                item.setData(Qt.UserRole, path)
                item.setSizeHint(QSize(118, 78))
                pix = self._load_icon_pixmap(path, QSize(108, 68))
                if not pix.isNull():
                    item.setIcon(QIcon(pix))
                self.history_list.addItem(item)
                if path == selected:
                    self.history_list.setCurrentItem(item)
            self.history_list.blockSignals(False)

        def _open_file_location(self, path: str):
            if not path or not os.path.exists(path):
                return
            try:
                if sys.platform.startswith("win"):
                    import subprocess
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-R", path])
                else:
                    folder = os.path.dirname(path)
                    subprocess.Popen(["xdg-open", folder])
            except Exception as e:
                QMessageBox.warning(self, t("跳转失败"), str(e))

        def _load_icon_pixmap(self, path: str, size: QSize) -> QPixmap:
            reader = QImageReader(path)
            reader.setAutoTransform(True)
            reader.setAllocationLimit(128)  # 图标尺寸较小，128MB 足够
            original = reader.size()
            if original.isValid():
                scaled = original.scaled(size, Qt.KeepAspectRatio)
                if scaled.isValid():
                    reader.setScaledSize(scaled)
            image = reader.read()
            return QPixmap.fromImage(image) if not image.isNull() else QPixmap()

        def open_selected_history_location(self):
            item = self.history_list.currentItem() if hasattr(self, "history_list") else None
            self.open_history_item_location(item)

        def open_history_item_location(self, item: QListWidgetItem):
            if hasattr(self, "_history_single_click_timer"):
                self._history_single_click_timer.stop()
            path = item.data(Qt.UserRole) if item else ""
            self._open_file_location(path)

        def schedule_apply_history_item(self, item: QListWidgetItem):
            self._pending_history_item = item
            self._history_single_click_timer.start(230)

        def apply_pending_history_item(self):
            item = getattr(self, "_pending_history_item", None)
            self._pending_history_item = None
            self.apply_history_item(item)

        def apply_history_item(self, item: QListWidgetItem):
            path = item.data(Qt.UserRole) if item else ""
            if path and os.path.exists(path):
                def _apply_from_history():
                    core.push_wallpaper(path)
                    return core.set_wallpaper_direct(path, t("历史记录"))
                self.run_core(_apply_from_history)

        def open_current_folder(self):
            path = core.config.get("current_wallpaper") or core.get_current_wallpaper()
            folder = os.path.dirname(path) if path else core.config.get("slide_folder", "")
            if folder and os.path.isdir(folder):
                if sys.platform.startswith("win"):
                    os.startfile(folder)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", folder])
                else:
                    subprocess.Popen(["xdg-open", folder])

        def open_wallpaper_sidebar(self) -> None:
            sb = getattr(self, "_sidebar", None)
            if sb is not None:
                try:
                    if hasattr(sb, "_is_closing") and not sb._is_closing:
                        sb.raise_()
                        sb.activateWindow()
                        return
                except Exception:
                    pass
                self._sidebar = None

            from wallpaper_sidebar import WallpaperSidebar

            folder = core.config.get("slide_folder", "")
            current = core.config.get("current_wallpaper", "") or core.get_current_wallpaper()

            if not folder or not os.path.isdir(folder):
                QMessageBox.information(self, t("提示"), t("请先在软件中设置壁纸文件夹"))
                return

            def _switch(path: str) -> None:
                try:
                    core.push_wallpaper(path)
                    core.set_wallpaper_direct(path, t("侧边栏切换"))
                    QTimer.singleShot(50, self.update_preview)
                except Exception as exc:
                    core.log(f"侧边栏切换壁纸失败: {exc}")

            sidebar_log = self._log_file_path() if core.config.get("log_enabled", False) else None
            self._sidebar = WallpaperSidebar(
                None, folder, current, sidebar_log,
                show_message=lambda t, m: QMessageBox.information(self, t, m),
                switch_wallpaper=_switch,
            )
            self._sidebar.closed.connect(lambda: setattr(self, "_sidebar", None))

        def on_bing_auto_options_changed(self, *args, save: bool = True):
            if not hasattr(self, "bing_auto_update_check"):
                return
            try:
                core.config["bing_auto_update_on_start"] = bool(self.bing_auto_update_check.isChecked())
                core.config["bing_auto_update_count"] = max(1, min(16, int(self.bing_auto_update_count_spin.value())))
                core.config["bing_auto_delete_on_start"] = bool(self.bing_auto_delete_check.isChecked())
                core.config["bing_auto_delete_count"] = max(1, min(200, int(self.bing_auto_delete_count_spin.value())))
                if save:
                    core.save_config()
            except Exception as exc:
                core.log(f"保存必应启动选项失败: {exc}")

        def _delete_oldest_bing_cached(self, count: int) -> int:
            cache_dir = core.config.get("bing_cache_dir", "") or ""
            if not cache_dir or not os.path.isdir(cache_dir):
                return 0
            try:
                from bing_downloader import BingDownloader
                return BingDownloader(cache_dir=cache_dir).delete_oldest_cached_wallpapers(count=count, keyword="bing")
            except Exception as exc:
                core.log(f"自动删除必应缓存失败: {exc}")
                return 0

        def run_bing_startup_tasks(self):
            if getattr(self, "_startup_bing_automation_done", False):
                return
            self._startup_bing_automation_done = True
            cache_dir = core.config.get("bing_cache_dir", "") or ""
            do_delete = bool(core.config.get("bing_auto_delete_on_start", False))
            do_update = bool(core.config.get("bing_auto_update_on_start", False))
            if not (do_delete or do_update):
                return
            if not cache_dir:
                self.set_status(t("必应启动自动操作已跳过：未设置缓存目录"))
                return
            if do_delete:
                count = max(1, min(200, int(core.config.get("bing_auto_delete_count", 1) or 1)))
                deleted = self._delete_oldest_bing_cached(count)
                self.set_status(f"启动时已自动删除 {deleted} 张最旧必应缓存壁纸")
                self.refresh_bing_cache_list()
            if do_update:
                count = max(1, min(16, int(core.config.get("bing_auto_update_count", 1) or 1)))
                if hasattr(self, "bing_cache_edit"):
                    self.bing_cache_edit.setText(cache_dir)
                if hasattr(self, "bing_count_spin"):
                    self.bing_count_spin.setValue(count)
                self.sync_bing_wallpaper(set_latest=True, force_count=count)

        def _bing_downloader(self):
            from bing_downloader import BingDownloader
            cache_dir = self.bing_cache_edit.text().strip()
            if not cache_dir:
                raise ValueError("请先填写或选择必应壁纸缓存目录")
            core.config["bing_cache_dir"] = cache_dir
            core.config["bing_sync_count"] = int(self.bing_count_spin.value())
            if hasattr(self, "bing_auto_update_check"):
                self.on_bing_auto_options_changed(save=False)
            core.save_config()
            return BingDownloader(cache_dir=cache_dir)

        def refresh_bing_cache_list(self):
            if not hasattr(self, "bing_list"):
                return
            self.bing_list.clear()
            cache_dir = core.config.get("bing_cache_dir", "") or ""
            if not cache_dir:
                if hasattr(self, "bing_status"):
                    self.bing_status.setText(t("首次使用请先选择必应壁纸缓存目录"))
                return
            try:
                from bing_downloader import BingDownloader
                for path in BingDownloader(cache_dir=cache_dir).get_cached_wallpapers():
                    item = QListWidgetItem(os.path.basename(path))
                    item.setData(Qt.UserRole, path)
                    self.bing_list.addItem(item)
            except Exception as e:
                core.log(f"刷新必应缓存列表失败: {e}")

        def choose_bing_cache_dir(self):
            folder = QFileDialog.getExistingDirectory(self, t("选择必应壁纸缓存目录"), self.bing_cache_edit.text() or str(Path.home()))
            if not folder:
                return
            old_folder = core.config.get("bing_cache_dir", "") or ""
            self.bing_cache_edit.setText(folder)
            core.config["bing_cache_dir"] = folder
            if os.path.abspath(old_folder) != os.path.abspath(folder):
                core.config["bing_next_index"] = 0
            core.save_config()
            self.refresh_bing_cache_list()

        def on_bing_selection_changed(self):
            item = self.bing_list.currentItem()
            if not item:
                return
            path = item.data(Qt.UserRole)
            if path and os.path.exists(path):
                self._pending_bing_path = path
                self._bing_preview_timer.start(80)

        def apply_pending_bing_preview(self):
            path = getattr(self, "_pending_bing_path", "")
            if not path or not os.path.exists(path):
                return
            self.preview_canvas.set_preview(path)
            self.current_label.setText(path)
            self.current_label.setToolTip(path)
            if hasattr(self, "bing_status"):
                self.bing_status.setText(t("已选择预览：") + f"{path}")

        def use_bing_cache_as_slideshow(self):
            folder = self.bing_cache_edit.text().strip()
            if not folder or not os.path.isdir(folder):
                QMessageBox.warning(self, t("必应壁纸"), t("请先选择或同步一个有效的缓存目录。"))
                return
            core.config["slide_folder"] = folder
            core.config["mode"] = "幻灯片放映"
            self.folder_edit.setText(folder)
            self._set_combo_current_data(self.mode_combo, "幻灯片放映")
            core.save_config()
            self.run_core(core.restart_slideshow)
            self.set_status(t("必应缓存已设为幻灯片来源"))

        def save_selected_bing_as(self):
            item = self.bing_list.currentItem()
            if not item:
                QMessageBox.information(self, t("必应壁纸"), t("请先在列表中选择一张已缓存的必应壁纸。"))
                return
            src = item.data(Qt.UserRole)
            if not src or not os.path.exists(src):
                QMessageBox.warning(self, t("必应壁纸"), t("选中的缓存文件不存在。"))
                return
            dst, _ = QFileDialog.getSaveFileName(self, t("另存必应壁纸"), os.path.join(str(Path.home()), os.path.basename(src)), t("JPEG 图片 (*.jpg);;所有文件 (*.*)"))
            if not dst:
                return
            try:
                import shutil
                shutil.copy2(src, dst)
                self.set_status(t("已另存为：") + f"{dst}")
            except Exception as e:
                QMessageBox.warning(self, t("另存失败"), str(e))

        def sync_bing_wallpaper(self, set_latest: bool = True, continue_from_saved: bool = False, force_count: int | None = None):
            cache_dir = self.bing_cache_edit.text().strip()
            if not cache_dir:
                QMessageBox.information(self, t("必应壁纸"), t("首次使用必应壁纸前，请先选择或填写缓存目录。"))
                self.bing_cache_edit.setFocus()
                return
            resolution = self.bing_resolution.currentText().strip() or "auto"
            count = max(1, min(16, int(force_count if force_count is not None else self.bing_count_spin.value())))
            start_index = max(0, int(core.config.get("bing_next_index", 0))) if continue_from_saved else 0
            core.config["bing_cache_dir"] = cache_dir
            core.config["bing_sync_count"] = count
            core.save_config()

            for btn in (self.bing_sync_btn, self.bing_multi_btn, getattr(self, "bing_continue_btn", None)):
                if btn is not None:
                    btn.setEnabled(False)
            self.bing_progress.setValue(0)
            mode_text = f"正在从第 {start_index + 1} 张开始继续同步必应壁纸..." if continue_from_saved else "正在同步必应壁纸..."
            self.bing_status.setText(mode_text)
            self.begin_operation(mode_text, cancellable=True)

            def _work():
                try:
                    from bing_downloader import BingDownloader
                    downloader = BingDownloader(cache_dir=cache_dir)
                    paths = []
                    seen_paths = set()
                    infos = downloader.fetch_history(days=count, resolution=resolution, start_index=start_index)
                    total = max(1, len(infos))
                    for idx, info in enumerate(infos, 1):
                        if self._current_operation_cancel.is_set():
                            self._emit_bing_result(False, t("必应壁纸同步已终止"), "")
                            return
                        path = downloader.download_wallpaper(info)
                        if path and path not in seen_paths:
                            paths.append(path)
                            seen_paths.add(path)
                        self.bing_result_signal.emit(True, f"必应同步进度：{idx}/{total}", path or "")
                    if not paths:
                        self._emit_bing_result(False, t("没有同步到必应壁纸"), "")
                        return

                    next_index = start_index + len(infos)
                    if next_index > int(core.config.get("bing_next_index", 0)) or not continue_from_saved:
                        core.config["bing_next_index"] = max(next_index, int(core.config.get("bing_next_index", 0)))
                        core.save_config()

                    deleted = 0
                    if core.config.get("bing_auto_cleanup", False):
                        deleted = downloader.cleanup_cached_wallpapers(max_count=count, keyword="bing")

                    latest = paths[0]
                    if self._current_operation_cancel.is_set():
                        self._emit_bing_result(False, t("必应壁纸同步已终止"), "")
                        return
                    if set_latest:
                        core.push_wallpaper(latest)
                        core.set_wallpaper_direct(latest, t("必应壁纸"))
                        cleanup_note = f"；已自动删除 {deleted} 张过量 bing 缓存" if deleted else ""
                        self._emit_bing_result(True, f"已同步 {len(paths)} 张并设置最新必应壁纸{cleanup_note}，下次可从第 {core.config.get('bing_next_index', 0) + 1} 张继续", latest)
                    else:
                        cleanup_note = f"；已自动删除 {deleted} 张过量 bing 缓存" if deleted else ""
                        self._emit_bing_result(True, f"已同步 {len(paths)} 张必应壁纸到缓存目录{cleanup_note}，下次可从第 {core.config.get('bing_next_index', 0) + 1} 张继续", latest)
                except Exception as e:
                    self._emit_bing_result(False, f"同步必应壁纸失败：{e}", "")

            self._bing_worker_thread = threading.Thread(target=_work, daemon=True)
            self._bing_worker_thread.start()

        def _emit_bing_result(self, ok: bool, message: str, path: str):
            self.bing_result_signal.emit(ok, message, path)

        def _on_bing_finished(self, ok: bool, message: str, path: str):
            is_progress = t("进度") in message
            if not is_progress:
                self.bing_sync_btn.setEnabled(True)
                self.bing_multi_btn.setEnabled(True)
                if hasattr(self, "bing_continue_btn"):
                    self.bing_continue_btn.setEnabled(True)
                self.finish_operation(message)
            if is_progress:
                try:
                    done, total = message.split("：", 1)[1].split("/", 1)
                    self.bing_progress.setValue(int(int(done) / max(1, int(total)) * 100))
                except Exception:
                    pass
            else:
                self.bing_progress.setValue(100 if ok else 0)
            self.bing_status.setText(message + (f"\n{path}" if path else ""))
            self.set_status(message)
            if is_progress:
                return
            self.refresh_bing_cache_list()
            self.update_preview()
            if not ok:
                QMessageBox.warning(self, t("必应壁纸"), message)

        def open_update_target(self):
            url = getattr(self, "_latest_asset_url", "") or getattr(self, "_latest_release_url", "") or GITHUB_LATEST_RELEASE_URL
            QDesktopServices.openUrl(QUrl(url))

        def open_project_homepage(self):
            QDesktopServices.openUrl(QUrl(GITHUB_PROJECT_URL))

        def _set_update_status_text(self, text: str):
            widget = getattr(self, "update_status_label", None)
            if widget is None:
                return
            try:
                if isinstance(widget, QTextEdit):
                    widget.setPlainText(text)
                else:
                    widget.setText(text)
            except RuntimeError:
                pass

        def start_update_check(self, button=None):
            if button is not None:
                button.setEnabled(False)
            self.begin_operation(t("正在检查更新…"))
            self._set_update_status_text("正在检查 GitHub Release 更新源...")
            if hasattr(self, "update_download_btn"):
                self.update_download_btn.setEnabled(False)
            self._update_checker = UpdateChecker()
            self._update_checker.finished.connect(lambda ok, msg, info, button=button: self.on_update_checked(ok, msg, info, button))
            self._update_checker.start()

        def on_update_checked(self, ok: bool, message: str, info: dict, button=None):
            if button is not None:
                button.setEnabled(True)
            self.finish_operation(message)
            if not hasattr(self, "update_status_label"):
                return
            if not ok:
                self._set_update_status_text(message)
                if hasattr(self, "update_download_btn"):
                    self.update_download_btn.setEnabled(True)
                    self.update_download_btn.setText(t("打开发布页"))
                return
            assets = info.get("assets") or []
            self._latest_release_url = info.get("url") or GITHUB_LATEST_RELEASE_URL
            self._latest_asset_url = ""
            asset_text = ""
            if assets:
                first = assets[0]
                self._latest_asset_url = first.get("download_url", "") or ""
                size_mb = (first.get("size") or 0) / 1024 / 1024
                asset_text = f"\n附件：{first.get('name', '')}（{size_mb:.1f} MB）"
            if hasattr(self, "update_download_btn"):
                self.update_download_btn.setEnabled(True)
                self.update_download_btn.setText(t("下载最新版") if self._latest_asset_url else t("打开发布页"))
            notes = (info.get("body") or "").strip()
            if len(notes) > 3000:
                notes = notes[:3000].rstrip() + "..."
            self._set_update_status_text(
                f"{message}\n更新源：GitHub Release\n当前版本：v{APP_VERSION}\n最新版本：{info.get('tag') or info.get('version')}\n"
                f"发布名称：{info.get('name') or '未命名'}{asset_text}\n\n{notes or '暂无更新说明'}"
            )

        def show_about_dialog(self):
            dlg = QDialog(self)
            dlg.setWindowTitle(t("关于 上一个桌面背景"))
            dlg.resize(680, 720)
            dlg.setMinimumSize(620, 620)
            dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(24, 20, 24, 20)
            layout.setSpacing(12)

            self._about_dlg_logo = QLabel(dlg)
            self._about_dlg_logo.setAlignment(Qt.AlignCenter)
            self._about_dlg_logo.setFixedHeight(86)
            txtlogo_path = self._img_path("txtlogo.png")
            if os.path.exists(txtlogo_path):
                pix = QPixmap(txtlogo_path)
                if not pix.isNull():
                    self._about_dlg_logo.setPixmap(pix.scaled(400, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    try:
                        effect = QGraphicsOpacityEffect(self._about_dlg_logo)
                        self._about_dlg_logo.setGraphicsEffect(effect)
                        self._logo_anim = QPropertyAnimation(effect, b"opacity", dlg)
                        self._logo_anim.setDuration(260)
                        self._logo_anim.setStartValue(0.15)
                        self._logo_anim.setEndValue(1.0)
                        self._logo_anim.setEasingCurve(QEasingCurve.OutCubic)
                        self._logo_anim.start()
                    except Exception:
                        pass
            layout.addWidget(self._about_dlg_logo)

            about_path = self._img_path("about-window.png")
            if os.path.exists(about_path):
                pix = QPixmap(about_path)
                if not pix.isNull():
                    img_label = QLabel(dlg)
                    img_label.setAlignment(Qt.AlignCenter)
                    img_label.setPixmap(pix.scaled(420, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    layout.addWidget(img_label)

            ver_label = QLabel(f"{APP_DISPLAY_NAME} v{APP_VERSION}")
            ver_label.setAlignment(Qt.AlignCenter)
            ver_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
            layout.addWidget(ver_label)

            update_box = QGroupBox(t("版本更新"))
            update_layout = QVBoxLayout(update_box)
            self.update_status_label = QTextEdit()
            self.update_status_label.setReadOnly(True)
            self.update_status_label.setMinimumHeight(150)
            self.update_status_label.setMaximumHeight(230)
            self.update_status_label.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            self.update_status_label.setPlainText(t("点击下方按钮检查 GitHub Release 更新源；检查结果、附件和更新说明会显示在这里，可滚动查看。"))
            update_layout.addWidget(self.update_status_label)
            update_buttons = QHBoxLayout()
            check_btn = QPushButton(t("检查更新"))
            check_btn.clicked.connect(lambda: self.start_update_check(check_btn))
            self.update_download_btn = QPushButton(t("打开发布页"))
            self.update_download_btn.setProperty("secondary", True)
            self.update_download_btn.clicked.connect(self.open_update_target)
            project_btn = QPushButton(t("打开项目页"))
            project_btn.setProperty("secondary", True)
            project_btn.clicked.connect(self.open_project_homepage)
            update_buttons.addWidget(check_btn)
            update_buttons.addWidget(self.update_download_btn)
            update_buttons.addWidget(project_btn)
            update_layout.addLayout(update_buttons)
            layout.addWidget(update_box)

            link_label = QLabel(
                '原项目：<a href="https://github.com/xxdz-Official/ShangBackground">GitHub</a><br>'
                f'反馈地址：<a href="{GITHUB_PROJECT_URL}">GitHub / 更新源</a><br>'
                '作者主页：b站@小小电子xxdz'
            )
            link_label.setOpenExternalLinks(True)
            link_label.setAlignment(Qt.AlignCenter)
            link_label.setWordWrap(True)
            layout.addWidget(link_label)

            close_btn = QPushButton(t("关闭"))
            close_btn.clicked.connect(dlg.accept)
            layout.addWidget(close_btn)

            try:
                parent_center = self.frameGeometry().center()
                geo = dlg.frameGeometry()
                geo.moveCenter(parent_center)
                dlg.move(geo.topLeft())
            except Exception:
                pass

            dlg.exec()

        def restart_as_admin(self, extra_args=None):
            self._closing_for_exit = True
            if self.tray:
                self.tray.hide()
                self.tray.deleteLater()
                self.tray = None
                QApplication.processEvents()
            if core.restart_as_admin(extra_args=extra_args):
                core._do_exit(0)
            else:
                self._closing_for_exit = False
                QMessageBox.warning(self, t("提权失败"), t("无法以管理员身份重启，请手动右键以管理员身份运行。"))

        def exit_app(self):
            self._closing_for_exit = True
            if self.tray:
                self.tray.hide()
                self.tray.deleteLater()
                self.tray = None
                QApplication.processEvents()
            core.stop_slideshow()
            core.restore_session_original_wallpaper()
            core.release_single_instance_mutex()
            _release_singleton_mutex()
            QApplication.instance().quit()

        def closeEvent(self, event):
            if core.config.get("run_in_background", True) and not self._closing_for_exit:
                event.ignore()
                self.hide()
                if self.tray and core.config.get("tray_notify", True):
                    self.tray.showMessage(APP_DISPLAY_NAME, t("已隐藏到系统托盘"), QSystemTrayIcon.Information, 1500)
                return
            if self.tray:
                self.tray.hide()
                self.tray.deleteLater()
                self.tray = None
            core.restore_session_original_wallpaper()
            core.release_single_instance_mutex()
            _release_singleton_mutex()
            event.accept()


def main() -> int:
    args = _parse_early_args()

    # ---------- 系统版本检查 ----------
    # Linux 分支仅适用于 Linux；若不匹配则弹窗警告（使用 tkinter，避免与 PySide6 QApplication 冲突）。
    if not sys.platform.startswith("linux"):
        print("=" * 60, file=sys.stderr)
        print("WARNING: This version of ShangBackground is for Linux only.", file=sys.stderr)
        print(f"Detected system: {sys.platform}", file=sys.stderr)
        print("Continuing may cause errors. Please use the correct platform version.", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        try:
            import tkinter as _tk
            _root = _tk.Tk()
            _root.withdraw()
            from tkinter import messagebox as _tkmb
            _result = _tkmb.askyesno(
                "ShangBackground — " + str(t("系统不匹配")),
                str(t("当前版本仅适用于 Linux 系统。")) + "\n\n" +
                str(t("检测到当前系统非 Linux，继续运行可能导致异常。")) + "\n\n" +
                str(t("是否仍要继续运行？")),
            )
            _root.destroy()
            if not _result:
                return 1
        except Exception:
            return 1

    if not PYSIDE_AVAILABLE:
        print(f"PySide6 不可用：{PYSIDE_IMPORT_ERROR}")
        try:
            from dependency_prompt import prompt_install_dependencies
            prompt_install_dependencies(None, _dependency_availability_for_pyside(), prefer_pyside=False)
        except Exception as exc:
            print(f"依赖提示不可用：{exc}")
        return 2

    is_action_launch = _is_action_launch(args)
    direct_action_launch = (args.previous or args.next or args.random or bool(args.set_wallpaper) or args.jump_to_wallpaper)

    # ---------- 单实例检测（普通权限文件锁 + 回环端口辅助） ----------
    if not direct_action_launch:
        if _is_already_running():
            core.log("检测到已有实例，已阻止重复启动")
            if not is_action_launch:
                core.show_message(t("不要重复运行"), t("不要重复运行，已有主界面正在运行。"))
            return 0

    if _handle_action_args(args):
        core.release_single_instance_mutex()
        _release_singleton_mutex()
        return 0

    used_dpi = apply_dpi_environment(core.config)
    core.log(f"程序内 DPI 缩放: {dpi_percent(used_dpi)}%")
    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_PROCESS_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setDesktopFileName(APP_PROCESS_NAME)
    _install_qt_chinese_translator(app)
    icon_path = os.path.join(core.BASE_DIR, "img", "LOGO.png")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(core.BASE_DIR, "img", "LOGO.ico")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
    try:
        chosen_font = apply_application_font(app)
        core.log(f"界面字体: {chosen_font}")
    except Exception as exc:
        core.log(f"界面字体初始化失败: {exc}")

    window = ShangBackgroundWindow()
    core.root = QtRootShim(window)
    core.canvas = None
    def _post_show_runtime_startup():
        try:
            from dependency_prompt import prompt_install_dependencies
            if not prompt_install_dependencies(None, _dependency_availability_for_pyside(), parent=window, prefer_pyside=True):
                window.exit_app()
                return
        except Exception as exc:
            core.log(f"PySide6 依赖检查跳过: {exc}")
        core.capture_session_original_wallpaper()
        if getattr(args, "sync_context_on_start", False):
            QTimer.singleShot(250, lambda: window.sync_context_menu(show_message=True))
        core.report_usage()
        if normalize_mode_key(core.config.get("mode")) == "幻灯片放映" and core.config.get("slide_folder"):
            core.start_slideshow()

    QTimer.singleShot(0, _post_show_runtime_startup)

    if core.hide_window or args.hide:
        window.hide()
    else:
        window.show()
    code = app.exec()
    if window.tray:
        window.tray.hide()
    core.stop_slideshow()
    if getattr(window, "_closing_for_exit", False):
        core.restore_session_original_wallpaper()
    core.release_single_instance_mutex()
    _release_singleton_mutex()
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())