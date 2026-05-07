import sys


IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
APP_NAME = "xxdz_上一个桌面背景"

UI_BG = "#f7f8fa"
UI_PANEL = "#ffffff"
UI_SURFACE = "#f2f4f7"
UI_ACCENT = "#0d99ff"
UI_ACCENT_DARK = "#007be5"
UI_ACCENT_SOFT = "#e5f4ff"
UI_TEXT = "#111827"
UI_MUTED = "#667085"
UI_BORDER = "#d0d5dd"
UI_BORDER_SOFT = "#eaecf0"
UI_DANGER = "#f04438"
UI_SUCCESS = "#12b76a"
FONT_FAMILY = "Microsoft YaHei" if IS_WINDOWS else ("PingFang SC" if IS_MACOS else "Noto Sans CJK SC")

IMAGE_FILETYPES = [
    ("JPEG 图片", "*.jpg"),
    ("JPEG 图片", "*.jpeg"),
    ("PNG 图片", "*.png"),
    ("BMP 图片", "*.bmp"),
    ("GIF 图片", "*.gif"),
]

VIDEO_FILETYPES = [
    ("MP4 视频", "*.mp4"),
    ("MOV 视频", "*.mov"),
    ("M4V 视频", "*.m4v"),
    ("AVI 视频", "*.avi"),
    ("MKV 视频", "*.mkv"),
]

DEPENDENCIES = [
    {"module": "PySide6", "package": "PySide6", "required": True, "desc": "Qt Quick/QML 图形界面与现代圆角控件"},
    {"module": "PIL", "package": "pillow", "required": True, "desc": "图片读取、缩略图和壁纸生成"},
    {"module": "requests", "package": "requests", "required": False, "desc": "版本检查和使用统计"},
    {"module": "numpy", "package": "numpy", "required": False, "desc": "更快的渐变/转场生成"},
    {"module": "pystray", "package": "pystray", "required": False, "desc": "系统托盘图标"},
    {"module": "keyboard", "package": "keyboard", "required": False, "desc": "全局快捷键支持"},
    {"module": "psutil", "package": "psutil", "required": False, "desc": "进程清理与辅助控制"},
    {"module": "AppKit", "package": "pyobjc-framework-Cocoa", "required": False, "desc": "macOS 菜单栏常驻"},
    {"module": "AVFoundation", "package": "pyobjc-framework-AVFoundation", "required": False, "desc": "macOS 视频壁纸播放器"},
]

STYLE_MAP = {"填充": 10, "适应": 6, "拉伸": 2, "平铺": 1, "居中": 0}
