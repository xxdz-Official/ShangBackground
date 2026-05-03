import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, ttk

from app_config import (
    FONT_FAMILY,
    IMAGE_FILETYPES,
    IS_WINDOWS,
    UI_ACCENT,
    UI_ACCENT_DARK,
    UI_ACCENT_SOFT,
    UI_BG,
    UI_BORDER,
    UI_BORDER_SOFT,
    UI_MUTED,
    UI_PANEL,
    UI_SURFACE,
    UI_TEXT,
    VIDEO_FILETYPES,
)


_ORIGINAL_TTK_BUTTON = ttk.Button
_ORIGINAL_TTK_COMBOBOX = ttk.Combobox


def _rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    radius = min(radius, max(1, (x2 - x1) // 2), max(1, (y2 - y1) // 2))
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


class FigmaButton(tk.Canvas):
    def __init__(self, master=None, **kwargs):
        self.command = kwargs.pop("command", None)
        self.text = kwargs.pop("text", "")
        self.state_value = kwargs.pop("state", "normal")
        self.style_name = kwargs.pop("style", "")
        self.width_chars = kwargs.pop("width", None)
        self.font = kwargs.pop("font", (FONT_FAMILY, 10))
        self.padding_x = 14
        self.padding_y = 7
        cursor = kwargs.pop("cursor", "hand2")
        super().__init__(master, highlightthickness=0, bd=0, relief="flat", cursor=cursor, bg=_parent_bg(master))
        self._hover = False
        self._pressed = False
        self._font_obj = tkfont.Font(font=self.font)
        self._redraw()
        self.bind("<Configure>", lambda event: self._redraw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _measure(self):
        text_width = self._font_obj.measure(str(self.text))
        if self.width_chars:
            text_width = max(text_width, int(self.width_chars) * self._font_obj.measure("0"))
        width = max(72, text_width + self.padding_x * 2)
        height = max(32, self._font_obj.metrics("linespace") + self.padding_y * 2)
        super().configure(width=width, height=height)

    def _palette(self):
        disabled = str(self.state_value) == "disabled"
        accent = self.style_name == "Accent.TButton"
        if accent:
            fill = UI_ACCENT
            outline = UI_ACCENT
            text = UI_PANEL
            if self._hover:
                fill = UI_ACCENT_DARK
                outline = UI_ACCENT_DARK
            if self._pressed:
                fill = "#006bbf"
                outline = "#006bbf"
            if disabled:
                fill = "#b9e6fe"
                outline = "#b9e6fe"
                text = UI_PANEL
            return fill, outline, text
        fill = UI_PANEL
        outline = UI_BORDER
        text = UI_TEXT
        if self._hover:
            fill = UI_SURFACE
        if self._pressed:
            fill = "#e4e7ec"
        if disabled:
            fill = UI_SURFACE
            outline = UI_BORDER_SOFT
            text = "#98a2b3"
        return fill, outline, text

    def _redraw(self):
        self._measure()
        self.delete("all")
        width = max(1, self.winfo_width() or int(self.cget("width")))
        height = max(1, self.winfo_height() or int(self.cget("height")))
        fill, outline, text_color = self._palette()
        _rounded_rect(self, 1, 1, width - 1, height - 1, 13, fill=fill, outline=outline, width=1)
        self.create_text(width // 2, height // 2, text=self.text, fill=text_color, font=self.font)

    def _on_enter(self, event):
        self._hover = True
        self._redraw()

    def _on_leave(self, event):
        self._hover = False
        self._pressed = False
        self._redraw()

    def _on_press(self, event):
        if str(self.state_value) == "disabled":
            return
        self._pressed = True
        self._redraw()

    def _on_release(self, event):
        if str(self.state_value) == "disabled":
            return
        was_pressed = self._pressed
        self._pressed = False
        self._redraw()
        if was_pressed and self.command:
            self.command()

    def configure(self, cnf=None, **kwargs):
        cnf = cnf or {}
        kwargs.update(cnf)
        redraw = False
        for key in ("text", "state", "command", "style", "width", "font"):
            if key in kwargs:
                value = kwargs.pop(key)
                if key == "text":
                    self.text = value
                elif key == "state":
                    self.state_value = value
                elif key == "command":
                    self.command = value
                elif key == "style":
                    self.style_name = value
                elif key == "width":
                    self.width_chars = value
                elif key == "font":
                    self.font = value
                    self._font_obj = tkfont.Font(font=self.font)
                redraw = True
        result = super().configure(**kwargs)
        if redraw:
            self._redraw()
        return result

    config = configure

    def cget(self, key):
        if key == "text":
            return self.text
        if key == "state":
            return self.state_value
        if key == "command":
            return self.command
        if key == "style":
            return self.style_name
        return super().cget(key)

    def invoke(self):
        if str(self.state_value) != "disabled" and self.command:
            return self.command()
        return None


class FigmaCombobox(tk.Frame):
    def __init__(self, master=None, **kwargs):
        self.values = list(kwargs.pop("values", []))
        self.textvariable = kwargs.pop("textvariable", None)
        self.state_value = kwargs.pop("state", "normal")
        self.width_chars = kwargs.pop("width", 18)
        self.font = kwargs.pop("font", (FONT_FAMILY, 10))
        self.height_rows = kwargs.pop("height", 10)
        super().__init__(master, bg=_parent_bg(master), bd=0, highlightthickness=0)
        self._font_obj = tkfont.Font(font=self.font)
        self._selected = tk.StringVar(value=self.textvariable.get() if self.textvariable else "")
        self._callbacks = []
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, relief="flat", bg=_parent_bg(master), cursor="hand2")
        self.canvas.pack(fill="both", expand=True)
        self._dropdown = None
        self.canvas.bind("<Button-1>", lambda event: self._toggle_dropdown())
        self.canvas.bind("<Configure>", lambda event: self._redraw())
        if self.textvariable is not None:
            self.textvariable.trace_add("write", lambda *args: self.set(self.textvariable.get(), notify=False))
        self._redraw()

    def _measure(self):
        width = max(90, int(self.width_chars) * self._font_obj.measure("0") + 40)
        height = max(32, self._font_obj.metrics("linespace") + 12)
        super().configure(width=width, height=height)
        self.pack_propagate(False)

    def _redraw(self):
        self._measure()
        self.canvas.delete("all")
        width = max(1, self.winfo_width() or int(self.cget("width")))
        height = max(1, self.winfo_height() or int(self.cget("height")))
        disabled = str(self.state_value) == "disabled"
        fill = UI_SURFACE if disabled else UI_PANEL
        outline = UI_BORDER_SOFT if disabled else UI_BORDER
        text_color = "#98a2b3" if disabled else UI_TEXT
        _rounded_rect(self.canvas, 1, 1, width - 1, height - 1, 12, fill=fill, outline=outline, width=1)
        self.canvas.create_text(12, height // 2, anchor="w", text=self.get(), fill=text_color, font=self.font)
        arrow_x = width - 19
        arrow_y = height // 2
        self.canvas.create_polygon(
            arrow_x - 5, arrow_y - 3,
            arrow_x + 5, arrow_y - 3,
            arrow_x, arrow_y + 4,
            fill=UI_MUTED if not disabled else "#98a2b3",
            outline="",
        )

    def _toggle_dropdown(self):
        if str(self.state_value) == "disabled":
            return
        if self._dropdown and self._dropdown.winfo_exists():
            self._dropdown.destroy()
            return
        self._open_dropdown()

    def _open_dropdown(self):
        self._dropdown = tk.Toplevel(self)
        self._dropdown.overrideredirect(True)
        self._dropdown.configure(bg=UI_BORDER)
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 4
        width = self.winfo_width()
        row_count = min(max(1, self.height_rows), max(1, len(self.values)))
        row_height = 28
        self._dropdown.geometry(f"{width}x{row_count * row_height + 2}+{x}+{y}")
        listbox = tk.Listbox(
            self._dropdown,
            bg=UI_PANEL,
            fg=UI_TEXT,
            selectbackground=UI_ACCENT_SOFT,
            selectforeground=UI_TEXT,
            activestyle="none",
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=self.font,
            exportselection=False,
        )
        listbox.pack(fill="both", expand=True, padx=1, pady=1)
        for value in self.values:
            listbox.insert("end", value)
        current = self.get()
        if current in self.values:
            idx = self.values.index(current)
            listbox.selection_set(idx)
            listbox.see(idx)

        def choose(event=None):
            selection = listbox.curselection()
            if selection:
                self.set(listbox.get(selection[0]))
            if self._dropdown and self._dropdown.winfo_exists():
                self._dropdown.destroy()

        listbox.bind("<ButtonRelease-1>", choose)
        listbox.bind("<Return>", choose)
        self._dropdown.bind("<Escape>", lambda event: self._dropdown.destroy())
        self._dropdown.after(100, lambda: self._dropdown.focus_force())
        listbox.focus_set()

    def set(self, value, notify=True):
        self._selected.set(value)
        if self.textvariable is not None and self.textvariable.get() != value:
            self.textvariable.set(value)
        self._redraw()
        if notify:
            for callback in self._callbacks:
                event = tk.Event()
                event.widget = self
                callback(event)

    def get(self):
        return self._selected.get()

    def bind(self, sequence=None, func=None, add=None):
        if sequence == "<<ComboboxSelected>>" and func is not None:
            self._callbacks.append(func)
            return str(len(self._callbacks) - 1)
        return super().bind(sequence, func, add)

    def configure(self, cnf=None, **kwargs):
        cnf = cnf or {}
        kwargs.update(cnf)
        redraw = False
        for key in ("values", "state", "width", "font", "height"):
            if key in kwargs:
                value = kwargs.pop(key)
                if key == "values":
                    self.values = list(value)
                elif key == "state":
                    self.state_value = value
                elif key == "width":
                    self.width_chars = value
                elif key == "font":
                    self.font = value
                    self._font_obj = tkfont.Font(font=self.font)
                elif key == "height":
                    self.height_rows = int(value)
                redraw = True
        result = super().configure(**kwargs)
        if redraw:
            self._redraw()
        return result

    config = configure

    def cget(self, key):
        if key == "values":
            return self.values
        if key == "state":
            return self.state_value
        if key == "width":
            return self.width_chars
        return super().cget(key)

    def __setitem__(self, key, value):
        self.configure(**{key: value})

    def __getitem__(self, key):
        return self.cget(key)

    def current(self, index=None):
        if index is None:
            try:
                return self.values.index(self.get())
            except ValueError:
                return -1
        if 0 <= index < len(self.values):
            self.set(self.values[index])
            return index
        return -1


def _parent_bg(parent):
    try:
        return parent.cget("bg")
    except Exception:
        return UI_BG


def setup_modern_style(style):
    for theme in ("clam", "vista" if IS_WINDOWS else "clam", "aqua", "default"):
        try:
            style.theme_use(theme)
            break
        except tk.TclError:
            continue

    # Figma-like 基础：浅灰画布、白色面板、细描边、紧凑控件。
    style.configure(".", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 10))
    style.configure("TFrame", background=UI_BG)
    style.configure("Panel.TFrame", background=UI_PANEL, relief="flat", borderwidth=1)
    style.configure("Surface.TFrame", background=UI_SURFACE, relief="flat", borderwidth=0)
    style.configure("TLabel", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 10))
    style.configure("Muted.TLabel", background=UI_BG, foreground=UI_MUTED, font=(FONT_FAMILY, 9))
    style.configure("Panel.TLabel", background=UI_PANEL, foreground=UI_TEXT, font=(FONT_FAMILY, 10))
    style.configure("Title.TLabel", background=UI_BG, foreground=UI_TEXT, font=(FONT_FAMILY, 12, "bold"))
    style.configure("Section.TLabel", background=UI_BG, foreground=UI_MUTED, font=(FONT_FAMILY, 9, "bold"))

    style.configure("TButton",
                   font=(FONT_FAMILY, 10),
                   padding=(12, 6),
                   relief="flat",
                   borderwidth=1,
                   background=UI_PANEL,
                   foreground=UI_TEXT,
                   lightcolor=UI_BORDER,
                   darkcolor=UI_BORDER,
                   focuscolor=UI_ACCENT_SOFT,
                   focusthickness=1)
    style.map("TButton",
             background=[("disabled", UI_SURFACE), ("active", UI_SURFACE), ("pressed", "#e4e7ec")],
             foreground=[("disabled", "#98a2b3")],
             relief=[("pressed", "flat")])

    style.configure("Accent.TButton",
                   foreground="#ffffff",
                   background=UI_ACCENT,
                   font=(FONT_FAMILY, 10, "bold"),
                   padding=(14, 7),
                   relief="flat",
                   borderwidth=1,
                   lightcolor=UI_ACCENT,
                   darkcolor=UI_ACCENT,
                   focuscolor=UI_ACCENT_SOFT,
                   focusthickness=1)
    style.map("Accent.TButton",
             background=[("disabled", "#b9e6fe"), ("active", UI_ACCENT_DARK), ("pressed", "#006bbf")],
             foreground=[("disabled", "#ffffff")],
             relief=[("pressed", "flat")])

    style.configure("TCheckbutton",
                    background=UI_BG,
                    foreground=UI_TEXT,
                    font=(FONT_FAMILY, 10),
                    padding=(0, 3),
                    focuscolor=UI_ACCENT_SOFT)
    style.map("TCheckbutton",
              foreground=[("disabled", "#98a2b3")],
              background=[("active", UI_BG)])
    style.configure("TRadiobutton",
                    background=UI_BG,
                    foreground=UI_TEXT,
                    font=(FONT_FAMILY, 10),
                    padding=(0, 3),
                    focuscolor=UI_ACCENT_SOFT)
    style.map("TRadiobutton", background=[("active", UI_BG)])

    style.configure("TEntry",
                    fieldbackground=UI_PANEL,
                    background=UI_PANEL,
                    foreground=UI_TEXT,
                    insertcolor=UI_TEXT,
                    padding=(8, 5),
                    relief="flat",
                    borderwidth=1,
                    lightcolor=UI_BORDER,
                    darkcolor=UI_BORDER)
    style.map("TEntry",
              fieldbackground=[("disabled", UI_SURFACE), ("readonly", UI_SURFACE)],
              foreground=[("disabled", "#98a2b3")],
              lightcolor=[("focus", UI_ACCENT)],
              darkcolor=[("focus", UI_ACCENT)])
    style.configure("TCombobox",
                   padding=(8, 5),
                   font=(FONT_FAMILY, 10),
                   relief="flat",
                   borderwidth=1,
                   background=UI_PANEL,
                   fieldbackground=UI_PANEL,
                   foreground=UI_TEXT,
                   arrowcolor=UI_MUTED,
                   lightcolor=UI_BORDER,
                   darkcolor=UI_BORDER)
    style.map("TCombobox",
             fieldbackground=[("readonly", UI_PANEL), ("disabled", UI_SURFACE)],
             foreground=[("disabled", "#98a2b3")],
             selectbackground=[("focus", UI_ACCENT_SOFT)],
             selectforeground=[("focus", UI_TEXT)],
             lightcolor=[("focus", UI_ACCENT)],
             darkcolor=[("focus", UI_ACCENT)])

    style.configure("Treeview",
                   rowheight=28,
                   font=(FONT_FAMILY, 10),
                   background=UI_PANEL,
                   fieldbackground=UI_PANEL,
                   foreground=UI_TEXT,
                   relief="flat",
                   borderwidth=1,
                   lightcolor=UI_BORDER_SOFT,
                   darkcolor=UI_BORDER_SOFT)
    style.map("Treeview",
              background=[("selected", UI_ACCENT_SOFT)],
              foreground=[("selected", UI_TEXT)])
    style.configure("Treeview.Heading",
                   font=(FONT_FAMILY, 10, "bold"),
                   background=UI_SURFACE,
                   foreground=UI_MUTED,
                   relief="flat",
                   borderwidth=1,
                   lightcolor=UI_BORDER_SOFT,
                   darkcolor=UI_BORDER_SOFT)
    style.map("Treeview.Heading",
             background=[("active", "#e4e7ec")])

    style.configure("Rounded.TFrame",
                   background=UI_PANEL,
                   relief="flat",
                   borderwidth=0)

    style.configure("Card.TFrame",
                   background=UI_PANEL,
                   relief="flat",
                   borderwidth=1,
                   lightcolor=UI_BORDER_SOFT,
                   darkcolor=UI_BORDER_SOFT)

    style.configure("TLabelframe",
                    background=UI_BG,
                    foreground=UI_MUTED,
                    relief="flat",
                    borderwidth=1,
                    lightcolor=UI_BORDER_SOFT,
                    darkcolor=UI_BORDER_SOFT)
    style.configure("TLabelframe.Label",
                    background=UI_BG,
                    foreground=UI_MUTED,
                    font=(FONT_FAMILY, 9, "bold"))

    style.configure("Vertical.TScrollbar",
                    background=UI_SURFACE,
                    troughcolor=UI_BG,
                    bordercolor=UI_BG,
                    arrowcolor=UI_MUTED,
                    relief="flat",
                    width=12)
    style.map("Vertical.TScrollbar",
              background=[("active", UI_BORDER), ("pressed", UI_MUTED)])
    style.configure("Horizontal.TScrollbar",
                    background=UI_SURFACE,
                    troughcolor=UI_BG,
                    bordercolor=UI_BG,
                    arrowcolor=UI_MUTED,
                    relief="flat",
                    width=12)
    style.configure("TProgressbar",
                    background=UI_ACCENT,
                    troughcolor=UI_SURFACE,
                    bordercolor=UI_BORDER_SOFT,
                    lightcolor=UI_ACCENT,
                    darkcolor=UI_ACCENT)
    style.configure("TNotebook", background=UI_BG, borderwidth=0)
    style.configure("TNotebook.Tab",
                    background=UI_SURFACE,
                    foreground=UI_MUTED,
                    padding=(12, 6),
                    borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", UI_PANEL), ("active", UI_PANEL)],
              foreground=[("selected", UI_TEXT), ("active", UI_TEXT)])
    _install_rounded_elements(style)
    ttk.Button = FigmaButton
    ttk.Combobox = FigmaCombobox


def _install_rounded_elements(style):
    try:
        from PIL import Image, ImageDraw, ImageTk
    except ImportError:
        return

    def rounded_image(fill, outline, radius=14, width=140, height=36):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            (1, 1, width - 2, height - 2),
            radius=radius,
            fill=fill,
            outline=outline,
            width=1,
        )
        return ImageTk.PhotoImage(img)

    images = getattr(style, "_figma_images", [])
    button_normal = rounded_image(UI_PANEL, UI_BORDER, 14)
    button_active = rounded_image(UI_SURFACE, UI_BORDER, 14)
    button_pressed = rounded_image("#e4e7ec", UI_BORDER, 14)
    button_disabled = rounded_image(UI_SURFACE, UI_BORDER_SOFT, 14)
    accent_normal = rounded_image(UI_ACCENT, UI_ACCENT, 14)
    accent_active = rounded_image(UI_ACCENT_DARK, UI_ACCENT_DARK, 14)
    accent_pressed = rounded_image("#006bbf", "#006bbf", 14)
    accent_disabled = rounded_image("#b9e6fe", "#b9e6fe", 14)
    input_normal = rounded_image(UI_PANEL, UI_BORDER, 12)
    input_focus = rounded_image(UI_PANEL, UI_ACCENT, 12)
    input_disabled = rounded_image(UI_SURFACE, UI_BORDER_SOFT, 12)
    combo_normal = rounded_image(UI_PANEL, UI_BORDER, 12)
    combo_focus = rounded_image(UI_PANEL, UI_ACCENT, 12)
    combo_disabled = rounded_image(UI_SURFACE, UI_BORDER_SOFT, 12)
    images.extend([
        button_normal, button_active, button_pressed, button_disabled,
        accent_normal, accent_active, accent_pressed, accent_disabled,
        input_normal, input_focus, input_disabled,
        combo_normal, combo_focus, combo_disabled,
    ])
    style._figma_images = images

    try:
        style.element_create(
            "FigmaButton.border",
            "image",
            button_normal,
            ("disabled", button_disabled),
            ("pressed", button_pressed),
            ("active", button_active),
            border=(14, 14, 14, 14),
            sticky="nsew",
        )
    except tk.TclError:
        pass
    try:
        style.element_create(
            "FigmaAccentButton.border",
            "image",
            accent_normal,
            ("disabled", accent_disabled),
            ("pressed", accent_pressed),
            ("active", accent_active),
            border=(14, 14, 14, 14),
            sticky="nsew",
        )
    except tk.TclError:
        pass
    try:
        style.element_create(
            "FigmaEntry.field",
            "image",
            input_normal,
            ("disabled", input_disabled),
            ("readonly", input_disabled),
            ("focus", input_focus),
            border=(14, 14, 14, 14),
            sticky="nsew",
        )
    except tk.TclError:
        pass
    try:
        style.element_create(
            "FigmaCombobox.field",
            "image",
            combo_normal,
            ("disabled", combo_disabled),
            ("readonly", combo_normal),
            ("focus", combo_focus),
            border=(14, 14, 14, 14),
            sticky="nsew",
        )
    except tk.TclError:
        pass

    button_layout = [
        ("FigmaButton.border", {
            "sticky": "nsew",
            "children": [
                ("Button.padding", {
                    "sticky": "nsew",
                    "children": [("Button.label", {"sticky": "nsew"})],
                }),
            ],
        }),
    ]
    accent_layout = [
        ("FigmaAccentButton.border", {
            "sticky": "nsew",
            "children": [
                ("Button.padding", {
                    "sticky": "nsew",
                    "children": [("Button.label", {"sticky": "nsew"})],
                }),
            ],
        }),
    ]
    try:
        style.layout("TButton", button_layout)
        style.layout("Accent.TButton", accent_layout)
    except tk.TclError:
        pass
    entry_layout = [
        ("FigmaEntry.field", {
            "sticky": "nsew",
            "children": [
                ("Entry.padding", {
                    "sticky": "nsew",
                    "children": [("Entry.textarea", {"sticky": "nsew"})],
                }),
            ],
        }),
    ]
    combo_layout = [
        ("FigmaCombobox.field", {
            "sticky": "nsew",
            "children": [
                ("Combobox.padding", {
                    "sticky": "nsew",
                    "children": [
                        ("Combobox.textarea", {"sticky": "nsew"}),
                    ],
                }),
                ("Combobox.downarrow", {"side": "right", "sticky": "ns"}),
            ],
        }),
    ]
    try:
        style.layout("TEntry", entry_layout)
        style.layout("TCombobox", combo_layout)
    except tk.TclError:
        pass


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
    """Figma-like rounded panel."""
    def __init__(self, parent, radius=14, bg=UI_PANEL, border=UI_BORDER_SOFT, padding=14, outer_bg=None, **kwargs):
        if outer_bg is None:
            try:
                outer_bg = parent.cget("bg")
            except tk.TclError:
                outer_bg = UI_BG
        super().__init__(parent, bg=outer_bg, **kwargs)
        self.radius = radius
        self.panel_bg = bg
        self.outer_bg = outer_bg
        self.border = border
        self.padding = padding
        self.canvas = tk.Canvas(self, bg=outer_bg, highlightthickness=0, bd=0, relief="flat")
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.content = tk.Frame(self, bg=bg, bd=0, highlightthickness=0)
        self.content_window = self.canvas.create_window(
            self.padding,
            self.padding,
            window=self.content,
            anchor="nw",
        )
        self.bind("<Configure>", self._redraw)
        self.content.bind("<Configure>", lambda event: self.canvas.tag_raise(self.content_window))

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
                fill=self.panel_bg,
                outline=self.border,
                width=1
            )

            self.bg_image = ImageTk.PhotoImage(img)
            if hasattr(self, "bg_item"):
                self.canvas.itemconfigure(self.bg_item, image=self.bg_image)
            else:
                self.bg_item = self.canvas.create_image(0, 0, anchor="nw", image=self.bg_image)
            content_width = max(1, width - self.padding * 2)
            content_height = max(1, height - self.padding * 2)
            self.canvas.coords(self.content_window, self.padding, self.padding)
            self.canvas.itemconfigure(self.content_window, width=content_width, height=content_height)
            self.canvas.tag_lower(self.bg_item)
            self.canvas.tag_raise(self.content_window)

        except ImportError:
            self.content.place(
                x=self.padding,
                y=self.padding,
                relwidth=1,
                relheight=1,
                width=-self.padding * 2,
                height=-self.padding * 2,
            )
            pass
