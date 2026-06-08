# Linux.ver(beta) is now a separated platform project; keep platform flags fixed.
IS_WINDOWS = False
IS_MACOS = False
IS_LINUX = True
APP_NAME = "ShangBackground"

UI_BG = "#f6f8fb"
UI_PANEL = "#ffffff"
DEFAULT_THEME_COLOR = "#ffffff"
DEFAULT_SOLID_COLOR = "#ffffff"
DEFAULT_GRADIENT_COLOR2 = "#ffffff"
UI_ACCENT = "#12c7b7"
UI_ACCENT_DARK = "#0f766e"
UI_TEXT = "#1f2937"
UI_MUTED = "#6b7280"
UI_BORDER = "#d8dee9"
FONT_FAMILY = "Noto Sans CJK SC"
FONT_EXTENSIONS = (".ttf", ".ttc", ".otf")

IMAGE_FILETYPES = [
    ("JPEG 图片", "*.jpg"),
    ("JPEG 图片", "*.jpeg"),
    ("PNG 图片", "*.png"),
    ("BMP 图片", "*.bmp"),
    ("GIF 图片", "*.gif"),
]


def get_image_filetypes(lang_func=None):
    """Return image filetypes with translated descriptions."""
    if lang_func is None:
        return IMAGE_FILETYPES
    return [
        (lang_func(desc, desc), ext)
        for desc, ext in IMAGE_FILETYPES
    ]


DEPENDENCIES = [
    {"module": "PIL", "package": "pillow", "required": True, "desc": "图片读取、缩略图和壁纸生成"},
    {"module": "requests", "package": "requests", "required": False, "desc": "网络请求（版本检查等）"},
    {"module": "numpy", "package": "numpy", "required": False, "desc": "更快的渐变壁纸生成"},
    {"module": "PySide6", "package": "PySide6-Essentials", "required": True, "desc": "新版 PySide6 图形界面与系统托盘"},
    {"module": "httpx", "package": "httpx", "required": False, "desc": "Bing 壁纸 API 下载"},
    {"module": "psutil", "package": "psutil", "required": False, "desc": "进程清理与辅助控制"},
]

# Style map: Chinese key -> Windows WallpaperStyle value
STYLE_MAP = {"填充": 10, "适应": 6, "拉伸": 2, "平铺": 1, "居中": 0}

# Style key lists for UI (order matters for display)
STYLE_KEYS = ["填充", "适应", "拉伸", "居中", "平铺"]

# Mode keys
MODE_KEYS = ["幻灯片放映", "图片", "纯色", "渐变"]

# Canonical internal keys.  The UI may display translated text, but config/core
# logic must keep these Chinese keys for backwards compatibility.
MODE_ALIASES = {
    "幻灯片放映": "幻灯片放映",
    "幻灯片": "幻灯片放映",
    "slideshow": "幻灯片放映",
    "slide show": "幻灯片放映",
    "slides": "幻灯片放映",
    "图片": "图片",
    "单张图片": "图片",
    "image": "图片",
    "picture": "图片",
    "single image": "图片",
    "纯色": "纯色",
    "solid": "纯色",
    "solid color": "纯色",
    "渐变": "渐变",
    "gradient": "渐变",
}
STYLE_ALIASES = {
    "填充": "填充",
    "fill": "填充",
    "zoom": "填充",
    "适应": "适应",
    "fit": "适应",
    "scaled": "适应",
    "拉伸": "拉伸",
    "stretch": "拉伸",
    "stretched": "拉伸",
    "居中": "居中",
    "center": "居中",
    "centered": "居中",
    "平铺": "平铺",
    "tile": "平铺",
    "tiled": "平铺",
}

def _norm_text(value):
    return str(value or "").strip().lower()

def normalize_mode_key(value, default="幻灯片放映"):
    """Return a stable Chinese mode key from Chinese/English UI text or old configs."""
    if value in MODE_KEYS:
        return value
    return MODE_ALIASES.get(_norm_text(value), default)

def normalize_style_key(value, default="填充"):
    """Return a stable Chinese fit/style key from Chinese/English UI text or old configs."""
    if value in STYLE_KEYS:
        return value
    return STYLE_ALIASES.get(_norm_text(value), default)

