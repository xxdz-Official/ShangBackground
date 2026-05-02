import tkinter as tk
from tkinter import filedialog

from app_config import (
    FONT_FAMILY,
    IMAGE_FILETYPES,
    IS_WINDOWS,
    UI_ACCENT,
    UI_ACCENT_DARK,
    UI_BG,
    UI_PANEL,
    UI_TEXT,
    VIDEO_FILETYPES,
)


def setup_modern_style(style):
    for theme in ("vista" if IS_WINDOWS else "clam", "aqua", "default"):
        try:
            style.theme_use(theme)
            break
        except tk.TclError:
            continue

    # 基础样式设置
    style.configure(".", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 10))
    style.configure("TFrame", background=UI_BG)
    style.configure("Panel.TFrame", background=UI_PANEL, relief="flat", borderwidth=0)
    style.configure("TLabel", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 10))
    style.configure("Title.TLabel", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 12, "bold"))

    # 按钮样式 - 增强圆角效果
    style.configure("TButton",
                   font=(FONT_FAMILY, 10),
                   padding=(12, 7),
                   relief="flat",
                   borderwidth=0,
                   focusthickness=0)
    style.map("TButton",
             background=[("active", "#e5e7eb"), ("pressed", "#d1d5db")],
             relief=[("pressed", "sunken")])

    # 强调按钮样式
    style.configure("Accent.TButton",
                   foreground="#ffffff",
                   background=UI_ACCENT,
                   font=(FONT_FAMILY, 10, "bold"),
                   padding=(14, 8),
                   relief="flat",
                   borderwidth=0,
                   focusthickness=0)
    style.map("Accent.TButton",
             background=[("active", UI_ACCENT_DARK), ("pressed", "#0d9488")],
             relief=[("pressed", "sunken")])

    # 其他控件样式
    style.configure("TCheckbutton", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 10))
    style.configure("TRadiobutton", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 10))
    style.configure("TCombobox",
                   padding=(8, 4),
                   font=(FONT_FAMILY, 10),
                   relief="flat",
                   borderwidth=1)
    style.map("TCombobox",
             fieldbackground=[("readonly", UI_PANEL)],
             selectbackground=[("focus", UI_ACCENT)])

    # Treeview样式
    style.configure("Treeview",
                   rowheight=28,
                   font=(FONT_FAMILY, 10),
                   background=UI_PANEL,
                   fieldbackground=UI_PANEL,
                   relief="flat",
                   borderwidth=0)
    style.configure("Treeview.Heading",
                   font=(FONT_FAMILY, 10, "bold"),
                   background=UI_ACCENT,
                   foreground="#ffffff",
                   relief="flat",
                   borderwidth=0)
    style.map("Treeview.Heading",
             background=[("active", UI_ACCENT_DARK)])

    # 自定义圆角框架样式
    style.configure("Rounded.TFrame",
                   background=UI_PANEL,
                   relief="flat",
                   borderwidth=0)

    # 卡片样式
    style.configure("Card.TFrame",
                   background=UI_PANEL,
                   relief="raised",
                   borderwidth=1,
                   lightcolor="#e5e7eb",
                   darkcolor="#d1d5db")


def ask_image_file(parent=None):
    return filedialog.askopenfilename(
        parent=parent,
        title="选择图片",
        filetypes=IMAGE_FILETYPES,
    )


def ask_video_file(parent=None):
    return filedialog.askopenfilename(
        parent=parent,
        title="选择视频",
        filetypes=VIDEO_FILETYPES,
    )


class RoundedFrame(tk.Frame):
    """圆角框架类"""
    def __init__(self, parent, radius=15, bg=UI_PANEL, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        self.radius = radius
        self.bg = bg
        self.bind("<Configure>", self._redraw)

    def _redraw(self, event=None):
        """重绘圆角边框"""
        try:
            from PIL import Image, ImageDraw, ImageTk
            width = self.winfo_width()
            height = self.winfo_height()
            if width <= 0 or height <= 0:
                return

            # 创建圆角矩形图像
            img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 绘制圆角矩形
            draw.rounded_rectangle(
                [(0, 0), (width-1, height-1)],
                radius=self.radius,
                fill=self.bg,
                outline="#e5e7eb",
                width=1
            )

            # 转换为PhotoImage
            self.bg_image = ImageTk.PhotoImage(img)

            # 创建或更新标签
            if hasattr(self, 'bg_label'):
                self.bg_label.configure(image=self.bg_image)
            else:
                self.bg_label = tk.Label(self, image=self.bg_image, bg=self.bg)
                self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                self.bg_label.lower()  # 放在底部作为背景

        except ImportError:
            # 如果没有PIL，使用普通框架
            pass
