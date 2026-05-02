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
    style.configure(".", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 10))
    style.configure("TFrame", background=UI_BG)
    style.configure("Panel.TFrame", background=UI_PANEL)
    style.configure("TLabel", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 10))
    style.configure("Title.TLabel", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 12, "bold"))
    style.configure("TButton", font=(FONT_FAMILY, 10), padding=(12, 7))
    style.configure("Accent.TButton", foreground="#ffffff", background=UI_ACCENT, padding=(14, 8))
    style.map("Accent.TButton", background=[("active", UI_ACCENT_DARK), ("pressed", "#0d9488")])
    style.configure("TCheckbutton", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 10))
    style.configure("TRadiobutton", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 10))
    style.configure("TCombobox", padding=(8, 4), font=(FONT_FAMILY, 10))
    style.configure("Treeview", rowheight=28, font=(FONT_FAMILY, 10), background=UI_PANEL, fieldbackground=UI_PANEL)
    style.configure("Treeview.Heading", font=(FONT_FAMILY, 10, "bold"))


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
