import os
import threading
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from app_config import FONT_FAMILY


SUPPORTED_EXT = ('.jpg', '.jpeg', '.png', '.bmp')
COPY_PREFIX = "(xxdz_random_copy)"
THUMB_WIDTH = 180
THUMB_HEIGHT = 120


def log_to_file(msg, log_path=None):
    pass


def generate_thumbnail_fast(img_path, size=(THUMB_WIDTH, THUMB_HEIGHT)):
    try:
        img = Image.open(img_path)
        img.thumbnail((size[0] * 2, size[1] * 2), Image.Resampling.LANCZOS)
        img = img.resize(size, Image.Resampling.NEAREST)
        return img
    except Exception as e:
        log_to_file(f"生成缩略图失败 {img_path}: {e}")
        return Image.new('RGB', size, (200, 200, 200))


class ThumbnailLoader:
    def __init__(self, sidebar, max_workers=8):
        self.sidebar = sidebar
        self.max_workers = max_workers
        self.loading_threads = []
        self._stop = False

    def load_all(self):
        self._stop = False
        for idx, img_path in enumerate(self.sidebar.image_paths):
            if self._stop:
                break
            thread = threading.Thread(target=self._load_one, args=(idx, img_path))
            thread.daemon = True
            thread.start()
            self.loading_threads.append(thread)

    def _load_one(self, idx, img_path):
        if self._stop:
            return
        try:
            pil_img = generate_thumbnail_fast(img_path)
            photo = ImageTk.PhotoImage(pil_img)

            def update_ui():
                if self._stop:
                    return
                self.sidebar.update_thumbnail(idx, photo, img_path)

            if self.sidebar.master and self.sidebar.master.winfo_exists():
                self.sidebar.master.after(0, update_ui)
        except Exception as e:
            log_to_file(f"加载缩略图线程异常 {img_path}: {e}")

    def stop(self):
        self._stop = True


class WallpaperSidebar:
    def __init__(self, master, folder, current_path, log_path, show_message=None, switch_wallpaper=None):
        self.master = master
        self.folder = folder
        self.current_path = current_path
        self.log_path = log_path
        self.show_message = show_message or (lambda title, msg: None)
        self.switch_wallpaper = switch_wallpaper
        self.thumbnails = []
        self.scroll_canvas = None
        self.scroll_frame = None
        self.is_animating = False
        self._is_closing = False
        self.loader = None
        self._global_click_id = None

        try:
            images = [f for f in os.listdir(folder)
                      if f.lower().endswith(SUPPORTED_EXT) and not f.startswith(COPY_PREFIX)]
            log_to_file(f"找到 {len(images)} 张图片", log_path)
        except Exception as e:
            log_to_file(f"列出图片失败: {e}", log_path)
            self.show_message("错误", "无法读取壁纸文件夹")
            self.master.destroy()
            return
        if not images:
            log_to_file("文件夹中没有图片", log_path)
            self.show_message("提示喵", "壁纸文件夹中没有图片")
            self.master.destroy()
            return
        self.image_paths = [os.path.join(folder, img) for img in images]

        self.setup_ui()
        self.create_placeholders()
        self.highlight_current()
        self.setup_click_outside_handler()
        self.master.after(500, self.start_loading_thumbnails)
        self.master.after(300, self.highlight_current)
        self.master.after(1500, self.scroll_to_current_after_load)
        log_to_file("侧边栏初始化完成", self.log_path)

    def setup_ui(self):
        self.master.title("壁纸侧边栏")
        self.master.overrideredirect(True)
        self.master.attributes('-topmost', True)
        self.master.configure(bg='#f0f0f0')
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        self.width = 300
        self.height = screen_height
        self.x = screen_width - self.width
        self.y = 0
        self.master.geometry(f"{self.width}x{self.height}+{screen_width}+{self.y}")

        close_btn = tk.Label(self.master, text="X", font=("Segoe UI", 14),
                             bg='#f0f0f0', fg='#666', cursor="hand2")
        close_btn.place(x=self.width - 35, y=5, width=30, height=30)
        close_btn.bind("<Button-1>", lambda e: self.close_sidebar())

        title = tk.Label(self.master, text="壁纸列表", font=(FONT_FAMILY, 12, "bold"),
                         bg='#f0f0f0', fg='#333')
        title.place(x=10, y=5)

        self.scroll_canvas = tk.Canvas(self.master, bg='#f0f0f0', highlightthickness=0)
        self.scroll_frame = tk.Frame(self.scroll_canvas, bg='#f0f0f0')
        self.v_scrollbar = ttk.Scrollbar(self.master, orient="vertical", command=self.scroll_canvas.yview)
        self.scroll_canvas.configure(yscrollcommand=self.v_scrollbar.set)

        self.v_scrollbar.pack(side="right", fill="y")
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.canvas_window = self.scroll_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")

        self.scroll_frame.bind("<Configure>", self.on_frame_configure)
        self.scroll_canvas.bind("<Configure>", self.on_canvas_configure)

        def on_mousewheel(event):
            self.scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.scroll_canvas.bind("<MouseWheel>", on_mousewheel)
        self.scroll_frame.bind("<MouseWheel>", on_mousewheel)
        self.animate_in()

    def on_frame_configure(self, event):
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))

    def on_canvas_configure(self, event):
        self.scroll_canvas.itemconfig(self.canvas_window, width=event.width)

    def create_placeholders(self):
        for idx, img_path in enumerate(self.image_paths):
            frame = tk.Frame(self.scroll_frame, bg='#ffffff', relief="flat", bd=1, height=150)
            frame.pack(pady=5, padx=10, fill="x")
            frame.pack_propagate(False)

            placeholder_label = tk.Label(frame, text="加载中...", bg='#ffffff', fg='#999',
                                         font=(FONT_FAMILY, 10))
            placeholder_label.pack(expand=True, fill="both", pady=30)

            name = os.path.splitext(os.path.basename(img_path))[0]
            name_label = tk.Label(frame, text=name, bg='#ffffff', fg='#555',
                                  font=(FONT_FAMILY, 9), wraplength=THUMB_WIDTH)
            name_label.pack(pady=(0, 5))

            def make_callback(path):
                return lambda e: self.on_thumbnail_click(path)

            frame.bind("<Button-1>", make_callback(img_path))
            name_label.bind("<Button-1>", make_callback(img_path))

            self.thumbnails.append({
                'path': img_path,
                'frame': frame,
                'photo': None,
                'img_label': None,
                'placeholder_label': placeholder_label,
                'name_label': name_label
            })

    def update_thumbnail(self, idx, photo, img_path):
        if self._is_closing or idx >= len(self.thumbnails):
            return
        try:
            item = self.thumbnails[idx]
            if item['path'] != img_path:
                return
            frame = item['frame']
            if item['placeholder_label']:
                item['placeholder_label'].destroy()
            img_label = tk.Label(frame, image=photo, bg='#ffffff', cursor="hand2")
            img_label.image = photo
            img_label.pack(pady=5)
            item['name_label'].pack(pady=(0, 5))

            def make_callback(path):
                return lambda e: self.on_thumbnail_click(path)

            img_label.bind("<Button-1>", make_callback(img_path))
            item['img_label'] = img_label
            item['photo'] = photo
            item['placeholder_label'] = None
            frame.configure(bg='#ffffff')
            if os.path.normpath(img_path) == os.path.normpath(self.current_path):
                frame.config(bg="#e0f0ff", relief="solid", bd=2)
            self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
        except Exception as e:
            log_to_file(f"更新缩略图失败: {e}", self.log_path)

    def start_loading_thumbnails(self):
        self.loader = ThumbnailLoader(self)
        self.loader.load_all()

    def highlight_current(self):
        def do_highlight_and_scroll():
            if self._is_closing:
                return
            target_idx = -1
            for idx, item in enumerate(self.thumbnails):
                if os.path.normpath(item['path']) == os.path.normpath(self.current_path):
                    target_idx = idx
                    break
            if target_idx == -1:
                log_to_file("未找到当前壁纸", self.log_path)
                return
            item = self.thumbnails[target_idx]
            item['frame'].config(bg="#e0f0ff", relief="solid", bd=2)

            def scroll_to_item():
                if self._is_closing:
                    return
                try:
                    y = item['frame'].winfo_y()
                    canvas_h = self.scroll_canvas.winfo_height()
                    target_y = max(0, y - (canvas_h // 3))
                    bbox = self.scroll_canvas.bbox("all")
                    if bbox and bbox[3] > 0:
                        scroll_pos = target_y / bbox[3]
                        scroll_pos = max(0, min(1, scroll_pos))
                        self.scroll_canvas.yview_moveto(scroll_pos)
                        log_to_file(f"滚动到当前壁纸: {os.path.basename(item['path'])} 位置={scroll_pos:.2f}",
                                    self.log_path)
                except Exception as e:
                    log_to_file(f"滚动失败: {e}", self.log_path)

            self.master.after(100, scroll_to_item)

        self.master.after(200, do_highlight_and_scroll)

    def scroll_to_current_after_load(self):
        def check_all_loaded():
            if self._is_closing:
                return
            all_loaded = all(item['photo'] is not None for item in self.thumbnails)
            if all_loaded:
                log_to_file("所有缩略图加载完成，重新滚动到当前壁纸", self.log_path)
                self.highlight_current()
            else:
                self.master.after(500, check_all_loaded)

        self.master.after(1000, check_all_loaded)

    def on_thumbnail_click(self, target_path):
        log_to_file(f"点击壁纸: {target_path}", self.log_path)
        try:
            if self.switch_wallpaper:
                self.switch_wallpaper(target_path)
            log_to_file("已切换壁纸", self.log_path)
        except Exception as e:
            log_to_file(f"切换壁纸失败: {e}", self.log_path)
        self.master.after(100, self.close_sidebar)

    def setup_click_outside_handler(self):
        self.master.grab_set()
        self.master.bind("<Button-1>", self._on_click_inside)
        self.master.bind("<FocusOut>", self._on_focus_out)
        self._start_click_monitor()
        log_to_file("点击外部收起功能已启用", self.log_path)

    def _on_click_inside(self, event):
        pass

    def _on_focus_out(self, event):
        log_to_file("侧边栏失去焦点，关闭", self.log_path)
        self.close_sidebar()

    def _start_click_monitor(self):
        def check_mouse():
            if self._is_closing or self.is_animating:
                return
            try:
                cursor_pos = self.master.winfo_pointerxy()
                x = self.master.winfo_x()
                y = self.master.winfo_y()
                w = self.master.winfo_width()
                h = self.master.winfo_height()
                if not (x <= cursor_pos[0] <= x + w and y <= cursor_pos[1] <= y + h):
                    if self.master.focus_get() is None:
                        log_to_file("检测到点击外部，关闭侧边栏", self.log_path)
                        self.close_sidebar()
                        return
            except Exception:
                pass
            if not self._is_closing:
                self.master.after(200, check_mouse)

        self.master.after(500, check_mouse)

    def animate_in(self):
        screen_width = self.master.winfo_screenwidth()
        start_x = screen_width
        end_x = self.x
        steps = 15
        delay = 8
        self.is_animating = True

        def step(step_idx):
            if step_idx <= steps and self.is_animating:
                t = step_idx / steps
                ease = 1 - (1 - t) ** 1.5
                cur_x = start_x - (start_x - end_x) * ease
                self.master.geometry(f"{self.width}x{self.height}+{int(cur_x)}+{self.y}")
                self.master.update_idletasks()
                self.master.after(delay, lambda: step(step_idx + 1))
            else:
                self.master.geometry(f"{self.width}x{self.height}+{end_x}+{self.y}")
                self.master.grab_set()
                self.master.focus_force()
                self.is_animating = False

        step(1)

    def animate_out(self, on_complete=None):
        if self.is_animating:
            return
        self.is_animating = True
        screen_width = self.master.winfo_screenwidth()
        start_x = self.x
        end_x = screen_width
        steps = 12
        delay = 8

        def step(step_idx):
            if step_idx <= steps and self.is_animating:
                t = step_idx / steps
                ease = t ** 1.2
                cur_x = start_x + (end_x - start_x) * ease
                self.master.geometry(f"{self.width}x{self.height}+{int(cur_x)}+{self.y}")
                self.master.update_idletasks()
                self.master.after(delay, lambda: step(step_idx + 1))
            else:
                if on_complete:
                    on_complete()
                self.is_animating = False

        step(1)

    def close_sidebar(self):
        if self.is_animating or self._is_closing:
            return
        self._is_closing = True
        if self.loader:
            self.loader.stop()
        log_to_file("关闭侧边栏", self.log_path)
        try:
            self.master.grab_release()
        except Exception:
            pass

        def on_animation_complete():
            try:
                self.master.destroy()
            except Exception:
                pass

        self.animate_out(on_animation_complete)
