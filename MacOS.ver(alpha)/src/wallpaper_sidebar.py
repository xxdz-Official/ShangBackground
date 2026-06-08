# wallpaper_sidebar.py
"""
壁纸侧边栏 — PySide6 版
从右侧滑入/滑出，保留原动画手感；与原调用接口完全兼容。
点击侧边栏外部或按 Esc 键自动收起。
"""

from __future__ import annotations

import os
import threading
import time

from PySide6.QtCore import (
    QEasingCurve, QEvent, QObject, QPoint,
    QPropertyAnimation, Qt, QTimer, Signal,
)
from PySide6.QtGui import QCursor, QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QScroller, QScrollerProperties, QVBoxLayout, QWidget,
)
from PIL import Image

import core_engine as core
from app_config import FONT_FAMILY
from i18n import t


def _sidebar_colors() -> dict[str, str]:
    dark = bool(getattr(core, "config", {}).get("dark_mode", False))
    if dark:
        return {"panel":"#1e1e2e","card":"#252536","card_hover":"#2d2d3f","active":"#123456","active_border":"#58a6ff","border":"#4d4d65","text":"#e6e6f0","muted":"#a7a7ba","thumb":"#2d2d3f","scroll_bg":"#1e1e2e","scroll_handle":"#4d4d65","scroll_hover":"#6d6d85","close_hover":"#3d3d55","close_pressed":"#4d4d65"}
    return {"panel":"#f7f8fa","card":"#ffffff","card_hover":"#f5f5f5","active":"#deeeff","active_border":"#4a90d9","border":"#dddddd","text":"#333333","muted":"#777777","thumb":"#eeeeee","scroll_bg":"#f1f3f5","scroll_handle":"#c9d1d9","scroll_hover":"#8c959f","close_hover":"#e0e0e0","close_pressed":"#c8c8c8"}


# ── 常量 ──────────────────────────────────────────────────────────────────────
SUPPORTED_EXT = ('.jpg', '.jpeg', '.png', '.bmp')
COPY_PREFIX   = "(xxdz_random_copy)"
THUMB_WIDTH   = 148
THUMB_HEIGHT  = 94


# ── 工具函数 ──────────────────────────────────────────────────────────────────
def log_to_file(msg: str, log_path=None) -> None:
    try:
        ts   = time.strftime("[%H:%M:%S]")
        line = f"{ts} [Sidebar] {msg}"
        print(line)
        if log_path:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass


def generate_thumbnail_fast(
    img_path: str,
    size: tuple = (THUMB_WIDTH, THUMB_HEIGHT),
) -> Image.Image:
    try:
        with Image.open(img_path) as src:
            img = src.copy()
        img.thumbnail(
            (size[0] * 2, size[1] * 2),
            Image.Resampling.BILINEAR,
        )
        return img.resize(size, Image.Resampling.BILINEAR)
    except Exception as exc:
        log_to_file(f"生成缩略图失败 {img_path}: {exc}")
        return Image.new("RGB", size, (200, 200, 200))


def pil_to_qpixmap(pil_img: Image.Image) -> QPixmap:
    rgba  = pil_img.convert("RGBA")
    data  = rgba.tobytes("raw", "RGBA")
    qimg  = QImage(
        data, rgba.width, rgba.height,
        rgba.width * 4,
        QImage.Format.Format_RGBA8888,
    )
    return QPixmap.fromImage(qimg.copy())


# ── Signal 桥 ─────────────────────────────────────────────────────────────────
class _LoaderSignals(QObject):
    ready = Signal(int, object, str)


# ── 缩略图后台加载器 ──────────────────────────────────────────────────────────
class ThumbnailLoader:
    def __init__(self, sidebar: "WallpaperSidebar"):
        self._sidebar = sidebar
        self._stop    = False
        self._signals = _LoaderSignals()
        self._signals.ready.connect(sidebar.on_thumbnail_ready)

    def load_all(self) -> None:
        self._stop = False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        # 顺序后台加载，避免图片很多时一次性创建大量线程导致触屏滚动卡顿。
        for idx, path in enumerate(self._sidebar.image_paths):
            if self._stop:
                break
            self._worker(idx, path)

    def _worker(self, idx: int, path: str) -> None:
        if self._stop:
            return
        try:
            pil_img = generate_thumbnail_fast(path)
            if not self._stop:
                self._signals.ready.emit(idx, pil_img, path)
        except Exception as exc:
            log_to_file(f"加载缩略图线程异常 {path}: {exc}")

    def stop(self) -> None:
        self._stop = True
        try:
            self._signals.ready.disconnect()
        except RuntimeError:
            pass


# ── 单张壁纸卡片 ──────────────────────────────────────────────────────────────
class ThumbnailItem(QFrame):
    clicked = Signal(str)

    _S_NORMAL = (
        "ThumbnailItem{"
        "background:#ffffff;border:1px solid #dddddd;border-radius:6px;}"
    )
    _S_HOVER = (
        "ThumbnailItem{"
        "background:#f5f5f5;border:1px solid #aaaaaa;border-radius:6px;}"
    )
    _S_ACTIVE = (
        "ThumbnailItem{"
        "background:#deeeff;border:2px solid #4a90d9;border-radius:6px;}"
    )

    @staticmethod
    def _item_style(kind: str = "normal") -> str:
        c = _sidebar_colors()
        if kind == "active":
            return f"ThumbnailItem{{background:{c['active']};border:2px solid {c['active_border']};border-radius:6px;}}"
        if kind == "hover":
            return f"ThumbnailItem{{background:{c['card_hover']};border:1px solid {c['scroll_hover']};border-radius:6px;}}"
        return f"ThumbnailItem{{background:{c['card']};border:1px solid {c['border']};border-radius:6px;}}"

    def __init__(self, img_path: str, parent=None):
        super().__init__(parent)
        self.img_path     = img_path
        self._highlighted = False
        self._loaded      = False
        self._press_pos   = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setFixedHeight(116)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setStyleSheet(self._item_style("normal"))
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(7, 7, 7, 7)
        lay.setSpacing(0)

        self.img_lbl = QLabel(t("加载中…"))
        self.img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_lbl.setFixedSize(THUMB_WIDTH, THUMB_HEIGHT)
        c = _sidebar_colors()
        self.img_lbl.setStyleSheet(
            f"background:{c['thumb']};color:{c['muted']};border-radius:3px;"
            f"font-family:'{FONT_FAMILY}';font-size:9pt;"
        )

        self.setToolTip(self.img_path)
        lay.addWidget(self.img_lbl,  0, Qt.AlignmentFlag.AlignCenter)

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        self.img_lbl.setPixmap(pixmap)
        self.img_lbl.setText("")
        self.img_lbl.setStyleSheet("background:transparent;border:none;")
        self._loaded = True

    def set_highlighted(self, on: bool) -> None:
        self._highlighted = on
        self.setStyleSheet(self._item_style("active") if on else self._item_style("normal"))

    @property
    def loaded(self) -> bool:
        return self._loaded

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if (pos - self._press_pos).manhattanLength() <= 10:
                self.clicked.emit(self.img_path)
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        if not self._highlighted:
            self.setStyleSheet(self._item_style("hover"))
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._highlighted:
            self.setStyleSheet(self._item_style("normal"))
        super().leaveEvent(event)




class _OutsideClickShield(QWidget):
    """全屏透明点击层：触屏/鼠标点到侧边栏外部时负责收起侧边栏。"""

    def __init__(self, sidebar: "WallpaperSidebar"):
        super().__init__(None)
        self.sidebar = sidebar
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("background: transparent;")
        self.setWindowOpacity(0.001)
        screens = QApplication.screens()
        if screens:
            geo = screens[0].geometry()
            for screen in screens[1:]:
                geo = geo.united(screen.geometry())
            self.setGeometry(geo)

    def mousePressEvent(self, event) -> None:
        if self.sidebar and not self.sidebar._is_closing:
            self.sidebar.close_sidebar()
        event.accept()

    def event(self, event) -> bool:
        if event.type() in (QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd):
            if self.sidebar and not self.sidebar._is_closing:
                QTimer.singleShot(0, self.sidebar.close_sidebar)
            event.accept()
            return True
        return super().event(event)


def _enable_touch_scrolling(widget) -> None:
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
        props.setScrollMetric(QScrollerProperties.ScrollMetric.HorizontalOvershootPolicy, QScrollerProperties.OvershootPolicy.OvershootAlwaysOff)
        scroller.setScrollerProperties(props)
    except Exception:
        pass


# ── 主侧边栏窗口 ──────────────────────────────────────────────────────────────
class WallpaperSidebar(QWidget):
    """
    无边框、置顶的右侧滑入侧边栏。

    功能：
      - 点击侧边栏外部区域自动收起（应用级 eventFilter）
      - 按 Esc 键收起
      - 侧边栏标题栏 ✕ 按钮关闭

    closed Signal：侧边栏彻底关闭后发出。
    """

    closed = Signal()

    def __init__(
        self,
        master,
        folder: str,
        current_path: str,
        log_path,
        show_message=None,
        switch_wallpaper=None,
    ):
        super().__init__(None)

        self.folder           = folder
        self.current_path     = current_path or ""
        self.log_path         = log_path
        self.show_message     = show_message or (lambda t, m: None)
        self.switch_wallpaper = switch_wallpaper

        self.image_paths:     list[str]                  = []
        self.thumbnail_items: list[ThumbnailItem]        = []
        self.is_animating:    bool                       = False
        self._is_closing:     bool                       = False
        self.loader:          ThumbnailLoader | None     = None
        self._anim:           QPropertyAnimation | None  = None
        self._shield:         _OutsideClickShield | None = None
        self._outside_poll_timer: QTimer | None = None
        self._outside_mouse_was_down = False

        if not QApplication.instance():
            raise RuntimeError(
                "WallpaperSidebar 必须在 QApplication 创建之后才能实例化"
            )

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint  |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)

        # ── 收集图片路径 ──────────────────────────────────────────────────────
        try:
            files = sorted([
                f for f in os.listdir(folder)
                if f.lower().endswith(SUPPORTED_EXT)
                and not f.startswith(COPY_PREFIX)
            ])
            log_to_file(f"找到 {len(files)} 张图片", log_path)
        except Exception as exc:
            log_to_file(f"列出图片失败: {exc}", log_path)
            self.show_message(t("错误"), t("无法读取壁纸文件夹"))
            QTimer.singleShot(0, self.deleteLater)
            return

        if not files:
            log_to_file("文件夹中没有图片", log_path)
            self.show_message("提示喵", "壁纸文件夹中没有图片")
            QTimer.singleShot(0, self.deleteLater)
            return

        self.image_paths = [os.path.join(folder, f) for f in files]

        screen   = QApplication.primaryScreen()
        geo      = screen.geometry()
        self._sw = geo.width()
        self._sh = geo.height()
        self._w  = 260
        self._tx = self._sw - self._w

        self._build_ui()
        self._create_items()

        self._shield = _OutsideClickShield(self)
        self._shield.show()
        self._shield.raise_()

        # 应用级事件过滤器保留为同一应用内点击的兜底；透明点击层负责真实桌面/触屏外部点击。
        if app := QApplication.instance():
            app.installEventFilter(self)

        self.animate_in()
        self._start_outside_click_polling()

        QTimer.singleShot(300,  self.highlight_current)
        QTimer.singleShot(500,  self.start_loading_thumbnails)
        QTimer.singleShot(1500, self.scroll_to_current_after_load)
        log_to_file("侧边栏初始化完成", self.log_path)

    # ═══════════════════════════════ UI 构建 ══════════════════════════════════

    def _build_ui(self) -> None:
        self.setFixedSize(self._w, self._sh)
        c = _sidebar_colors()
        self.setStyleSheet(f"background:{c['panel']}; color:{c['text']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 标题栏 ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(42)
        header.setStyleSheet(f"background:{c['panel']};border-bottom:1px solid {c['border']};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 6, 10, 6)

        title_lbl = QLabel(t("壁纸列表"))
        title_lbl.setStyleSheet(
            f"font-family:'{FONT_FAMILY}';font-size:12pt;"
            f"font-weight:bold;color:{c['text']};"
        )

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{c['muted']};
                font-size:12pt; border:none; border-radius:4px;
            }}
            QPushButton:hover   {{ background:{c['close_hover']}; color:{c['text']}; }}
            QPushButton:pressed {{ background:{c['close_pressed']}; }}
        """)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.close_sidebar)

        hl.addWidget(title_lbl)
        hl.addStretch()
        hl.addWidget(close_btn)

        # ── 滚动区域 ──────────────────────────────────────────────────────────
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.viewport().setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{ background:{c['panel']}; border:none; }}
            QScrollBar:vertical {{ background:{c['scroll_bg']}; width:10px; margin:0; border-radius:5px; }}
            QScrollBar::handle:vertical {{ background:{c['scroll_handle']}; border-radius:5px; min-height:30px; }}
            QScrollBar::handle:vertical:hover {{ background:{c['scroll_hover']}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; background:transparent; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}
        """)
        _enable_touch_scrolling(self.scroll_area)

        self._container = QWidget()
        self._container.setStyleSheet(f"background:{c['panel']};")
        self._vlay = QVBoxLayout(self._container)
        self._vlay.setContentsMargins(8, 8, 8, 8)
        self._vlay.setSpacing(8)
        self.scroll_area.setWidget(self._container)

        root.addWidget(header)
        root.addWidget(self.scroll_area)

    def _create_items(self) -> None:
        for path in self.image_paths:
            item = ThumbnailItem(path)
            item.clicked.connect(self.on_thumbnail_click)
            self._vlay.addWidget(item)
            self.thumbnail_items.append(item)
        self._vlay.addStretch()

    # ═══════════════════════════════ 缩略图加载 ═══════════════════════════════

    def start_loading_thumbnails(self) -> None:
        if self._is_closing:
            return
        self.loader = ThumbnailLoader(self)
        self.loader.load_all()
        log_to_file("开始后台加载缩略图", self.log_path)

    def on_thumbnail_ready(self, idx: int, pil_img, path: str) -> None:
        if self._is_closing or idx >= len(self.thumbnail_items):
            return
        try:
            item = self.thumbnail_items[idx]
            if item.img_path != path:
                return
            item.set_thumbnail(pil_to_qpixmap(pil_img))
            if os.path.normpath(path) == os.path.normpath(self.current_path):
                item.set_highlighted(True)
        except Exception as exc:
            log_to_file(f"更新缩略图 UI 失败: {exc}", self.log_path)

    # ═══════════════════════════════ 高亮 / 滚动 ══════════════════════════════

    def highlight_current(self) -> None:
        if self._is_closing:
            return
        target = -1
        for i, item in enumerate(self.thumbnail_items):
            is_cur = (
                os.path.normpath(item.img_path) ==
                os.path.normpath(self.current_path)
            )
            item.set_highlighted(is_cur)
            if is_cur:
                target = i

        if target >= 0:
            log_to_file(
                f"高亮当前壁纸: "
                f"{os.path.basename(self.thumbnail_items[target].img_path)}",
                self.log_path,
            )
            QTimer.singleShot(120, lambda: self._scroll_to(target))

    def _scroll_to(self, idx: int) -> None:
        if self._is_closing or idx >= len(self.thumbnail_items):
            return
        self.scroll_area.ensureWidgetVisible(
            self.thumbnail_items[idx], xMargin=0, yMargin=60
        )

    def scroll_to_current_after_load(self) -> None:
        def _check() -> None:
            if self._is_closing:
                return
            if all(it.loaded for it in self.thumbnail_items):
                log_to_file("所有缩略图加载完成，重新定位", self.log_path)
                self.highlight_current()
            else:
                QTimer.singleShot(500, _check)

        QTimer.singleShot(1000, _check)

    # ═══════════════════════════════ 交互逻辑 ═════════════════════════════════

    def on_thumbnail_click(self, path: str) -> None:
        log_to_file(f"点击壁纸: {path}", self.log_path)
        try:
            if self.switch_wallpaper:
                self.switch_wallpaper(path)
            log_to_file("已切换壁纸", self.log_path)
        except Exception as exc:
            log_to_file(f"切换壁纸失败: {exc}", self.log_path)
        QTimer.singleShot(100, self.close_sidebar)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        应用级事件过滤器：点击侧边栏外部时自动收起。

        逻辑：
          1. 动画播放中（is_animating=True）或已在关闭流程中，不响应。
          2. 确认是 MouseButtonPress 且是真实的 QMouseEvent。
          3. 全局坐标不在侧边栏矩形内 → 触发 close_sidebar。
        """
        if not self._is_closing and not self.is_animating:
            if event.type() == QEvent.Type.MouseButtonPress:
                if isinstance(event, QMouseEvent):
                    try:
                        pos = event.globalPosition().toPoint()
                        # 使用 frameGeometry 获取全局坐标下的窗口矩形
                        if not self.frameGeometry().contains(pos):
                            QTimer.singleShot(0, self.close_sidebar)
                    except Exception:
                        pass
        return False  # 不拦截事件，让其继续传递

    def _global_mouse_buttons_down(self) -> bool:
        """读取全局鼠标按键状态；Windows 下用普通权限可用的 GetAsyncKeyState 兜底。"""
        if os.name == "nt":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x01, 0x02, 0x04))
            except Exception:
                pass
        buttons = QApplication.mouseButtons()
        return bool(buttons & (Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton))

    def _start_outside_click_polling(self) -> None:
        """兜底检测桌面/其它窗口点击，解决部分系统透明点击层不触发的问题。"""
        self._outside_poll_timer = QTimer(self)
        self._outside_poll_timer.setInterval(70)
        self._outside_poll_timer.timeout.connect(self._poll_outside_click)
        self._outside_poll_timer.start()

    def _poll_outside_click(self) -> None:
        if self._is_closing or self.is_animating:
            return
        is_down = self._global_mouse_buttons_down()
        if is_down and not self._outside_mouse_was_down:
            pos = QCursor.pos()
            if not self.frameGeometry().contains(pos):
                QTimer.singleShot(0, self.close_sidebar)
        self._outside_mouse_was_down = is_down

    # ═══════════════════════════════ 键盘支持 ═════════════════════════════════

    def keyPressEvent(self, event) -> None:
        """
        Esc 键快速关闭侧边栏。
        与点击外部收起的行为等效，同样经过动画滑出流程。
        """
        if event.key() == Qt.Key.Key_Escape:
            self.close_sidebar()
        else:
            super().keyPressEvent(event)

    # ═══════════════════════════════ /滑出动画 ════════════════════════════

    def animate_in(self) -> None:
        """从屏幕右边缘滑入（OutCubic 200 ms）。"""
        start = QPoint(self._sw, 0)
        end   = QPoint(self._tx, 0)

        self.move(start)
        if self._shield:
            self._shield.show()
            self._shield.raise_()
        self.show()
        self.raise_()
        self.activateWindow()
        try:
            self.scroll_area.setUpdatesEnabled(False)
            self._container.setUpdatesEnabled(False)
        except Exception:
            pass

        self.is_animating = True
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.finished.connect(self._on_in_done)
        self._anim.start()

    def _on_in_done(self) -> None:
        self.is_animating = False
        try:
            self._container.setUpdatesEnabled(True)
            self.scroll_area.setUpdatesEnabled(True)
            self.scroll_area.viewport().update()
        except Exception:
            pass
        self.raise_()
        self.activateWindow()

    def animate_out(self, on_complete=None) -> None:
        """滑出至屏幕右边缘（InCubic 160 ms）。"""
        if self.is_animating:
            return
        self.is_animating = True
        try:
            self.scroll_area.setUpdatesEnabled(False)
            self._container.setUpdatesEnabled(False)
        except Exception:
            pass

        start = QPoint(self._tx, 0)
        end   = QPoint(self._sw, 0)

        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)

        def _done() -> None:
            self.is_animating = False
            try:
                self._container.setUpdatesEnabled(True)
                self.scroll_area.setUpdatesEnabled(True)
            except Exception:
                pass
            if on_complete:
                on_complete()

        self._anim.finished.connect(_done)
        self._anim.start()

    # ═══════════════════════════════ 关闭逻辑 ═════════════════════════════════

    def close_sidebar(self) -> None:
        """触发滑出动画后关闭。双重 guard 避免重入。"""
        if self.is_animating or self._is_closing:
            return
        self._is_closing = True

        if self.loader:
            self.loader.stop()
        if self._outside_poll_timer:
            self._outside_poll_timer.stop()
            self._outside_poll_timer = None
        log_to_file("关闭侧边栏", self.log_path)
        self._remove_event_filter()
        self._close_click_shield()

        def _finish() -> None:
            try:
                self.close()
                self.deleteLater()
            except Exception:
                pass

        self.animate_out(_finish)

    def _remove_event_filter(self) -> None:
        if app := QApplication.instance():
            try:
                app.removeEventFilter(self)
            except Exception:
                pass

    def _close_click_shield(self) -> None:
        shield = getattr(self, "_shield", None)
        self._shield = None
        if shield is not None:
            try:
                shield.close()
                shield.deleteLater()
            except Exception:
                pass

    def closeEvent(self, event) -> None:
        """Alt+F4 / 系统强制关闭时的安全兜底。"""
        self._is_closing = True
        if self.loader:
            self.loader.stop()
        if self._outside_poll_timer:
            self._outside_poll_timer.stop()
            self._outside_poll_timer = None
        if self._anim:
            self._anim.stop()
        self._remove_event_filter()
        self._close_click_shield()
        super().closeEvent(event)
        try:
            self.closed.emit()
        except RuntimeError:
            pass