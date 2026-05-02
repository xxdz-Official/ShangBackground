# -*- coding: utf-8 -*-
"""
随机概率管理模块（文件复制法）
- 通过复制图片文件来增加被随机选中的概率
- 用户调整滑块后暂存修改，点击保存按钮才实际执行文件复制/删除
- 关闭窗口时如有未保存修改则提示
"""

import os
import json
import shutil
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import logging

# 日志配置
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wallpaper_debug.log")
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log(msg):
    print(msg)
    logging.info(msg)

COPY_PREFIX = "(xxdz_random_copy)"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RANDOM_CONFIG_PATH = os.path.join(BASE_DIR, "random.json")


def _load_config():
    if os.path.exists(RANDOM_CONFIG_PATH):
        try:
            with open(RANDOM_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def _save_config(data):
    try:
        with open(RANDOM_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存随机配置失败: {e}")


def get_copy_count(folder_path, filename):
    folder_abs = os.path.abspath(folder_path)
    config = _load_config()
    folder_data = config.get(folder_abs, {})
    return folder_data.get(filename, 0)


def _apply_copy_count(folder_path, filename, copy_count):
    """实际执行文件复制/删除（不保存配置）"""
    folder_abs = os.path.abspath(folder_path)
    print(f"[DEBUG] _apply_copy_count: folder={folder_abs}, filename={filename}, copy_count={copy_count}")
    log(f"_apply_copy_count: folder={folder_abs}, filename={filename}, copy_count={copy_count}")
    
    if not os.path.isdir(folder_abs):
        print(f"[DEBUG] _apply_copy_count: 文件夹无效")
        return False
    original_path = os.path.join(folder_abs, filename)
    if not os.path.exists(original_path):
        print(f"[DEBUG] _apply_copy_count: 原图不存在 {original_path}")
        return False
    copy_count = int(copy_count)
    if copy_count < 0:
        copy_count = 0

    # 删除所有旧副本
    deleted = 0
    for f in os.listdir(folder_abs):
        if f.startswith(COPY_PREFIX) and f.endswith(filename):
            try:
                os.remove(os.path.join(folder_abs, f))
                deleted += 1
                print(f"[DEBUG] _apply_copy_count: 删除旧副本 {f}")
            except:
                pass
    print(f"[DEBUG] _apply_copy_count: 共删除 {deleted} 个旧副本")

    # 创建新副本
    created = 0
    for i in range(1, copy_count + 1):
        copy_name = f"{COPY_PREFIX}_{i}_{filename}"
        copy_path = os.path.join(folder_abs, copy_name)
        try:
            shutil.copy2(original_path, copy_path)
            created += 1
            print(f"[DEBUG] _apply_copy_count: 创建副本 {copy_name}")
        except Exception as e:
            print(f"[DEBUG] _apply_copy_count: 复制失败 {copy_name}: {e}")
    print(f"[DEBUG] _apply_copy_count: 共创建 {created} 个副本 (目标: {copy_count})")
    return True


def save_all_changes(folder_path, changes_dict):
    """
    批量保存所有更改
    changes_dict: {filename: copy_count}
    """
    folder_abs = os.path.abspath(folder_path)
    print(f"[DEBUG] save_all_changes: folder={folder_abs}, changes_dict={changes_dict}")
    log(f"save_all_changes: folder={folder_abs}, changes_dict={changes_dict}")
    
    for filename, copy_count in changes_dict.items():
        print(f"[DEBUG] save_all_changes: 处理 {filename} -> copy_count={copy_count}")
        _apply_copy_count(folder_abs, filename, copy_count)

    # 更新配置文件
    config = _load_config()
    print(f"[DEBUG] save_all_changes: 加载现有配置 = {config}")
    
    if not changes_dict:
        if folder_abs in config:
            del config[folder_abs]
            print(f"[DEBUG] save_all_changes: 删除文件夹配置 {folder_abs}")
    else:
        if folder_abs not in config:
            config[folder_abs] = {}
            print(f"[DEBUG] save_all_changes: 创建新文件夹配置 {folder_abs}")
        for filename, copy_count in changes_dict.items():
            if copy_count == 0:
                if filename in config[folder_abs]:
                    del config[folder_abs][filename]
                    print(f"[DEBUG] save_all_changes: 删除 {filename} 配置")
            else:
                config[folder_abs][filename] = copy_count
                print(f"[DEBUG] save_all_changes: 设置 {filename} -> {copy_count}")
        if not config[folder_abs]:
            del config[folder_abs]
            print(f"[DEBUG] save_all_changes: 文件夹配置为空，删除")
    
    print(f"[DEBUG] save_all_changes: 保存配置 = {config}")
    _save_config(config)
    print(f"[DEBUG] save_all_changes: 保存完成")


def cleanup_folder(folder_path):
    """删除指定文件夹下所有副本文件，并清空配置"""
    folder_abs = os.path.abspath(folder_path)
    if not os.path.isdir(folder_abs):
        return
    for f in os.listdir(folder_abs):
        if f.startswith(COPY_PREFIX):
            try:
                os.remove(os.path.join(folder_abs, f))
            except:
                pass
    config = _load_config()
    if folder_abs in config:
        del config[folder_abs]
        _save_config(config)


def cleanup_physical_only(folder_path):
    """仅删除指定文件夹下所有副本文件，不清空配置文件（保留权重）"""
    folder_abs = os.path.abspath(folder_path)
    if not os.path.isdir(folder_abs):
        return
    deleted = 0
    for f in os.listdir(folder_abs):
        if f.startswith(COPY_PREFIX):
            try:
                os.remove(os.path.join(folder_abs, f))
                deleted += 1
            except:
                pass
    log(f"cleanup_physical_only: 删除了 {deleted} 个副本文件，配置未改动")


def restore_weights(folder_path):
    """
    根据 random.json 中的配置恢复副本文件
    """
    folder_abs = os.path.abspath(folder_path)
    print(f"[DEBUG] restore_weights 被调用, folder={folder_abs}")
    log(f"restore_weights: 被调用, folder={folder_abs}")
    
    if not os.path.isdir(folder_abs):
        print(f"[DEBUG] restore_weights: 文件夹无效 {folder_abs}")
        log(f"restore_weights: 文件夹无效 {folder_abs}")
        return

    config = _load_config()
    print(f"[DEBUG] restore_weights: 加载的配置 = {config}")
    log(f"restore_weights: 加载的配置 = {config}")
    
    folder_data = config.get(folder_abs, {})
    print(f"[DEBUG] restore_weights: folder_data = {folder_data}")
    log(f"restore_weights: folder_data = {folder_data}")

    if not folder_data:
        print(f"[DEBUG] restore_weights: 没有找到权重配置 for {folder_abs}，请先通过「设置随机概率」保存权重")
        log(f"restore_weights: 没有找到权重配置 for {folder_abs}，跳过恢复")
        # 增加提示，方便用户排查
        if 'root' in globals() and root is not None:
            try:
                from tkinter import messagebox
                root.after(0, lambda: messagebox.showinfo("提示喵", "未找到随机概率配置，请先打开「设置随机概率」并保存"))
            except:
                pass
        return

    print(f"[DEBUG] restore_weights: 开始恢复 {len(folder_data)} 个图片的副本")
    log(f"restore_weights: 开始恢复 {len(folder_data)} 个图片的副本")

    for filename, copy_count in folder_data.items():
        original_path = os.path.join(folder_abs, filename)
        print(f"[DEBUG] restore_weights: 处理 {filename}, copy_count={copy_count}, 原图路径={original_path}")
        log(f"restore_weights: 处理 {filename}, copy_count={copy_count}")
        
        if not os.path.exists(original_path):
            print(f"[DEBUG] restore_weights: 原图不存在 {filename}")
            log(f"restore_weights: 原图不存在 {filename}")
            continue

        # 删除该图片已有的所有副本
        deleted_count = 0
        for f in os.listdir(folder_abs):
            if f.startswith(COPY_PREFIX) and f.endswith(filename):
                try:
                    os.remove(os.path.join(folder_abs, f))
                    deleted_count += 1
                    print(f"[DEBUG] restore_weights: 删除旧副本 {f}")
                    log(f"restore_weights: 删除旧副本 {f}")
                except Exception as e:
                    print(f"[DEBUG] restore_weights: 删除失败 {f}: {e}")
                    pass
        print(f"[DEBUG] restore_weights: 共删除 {deleted_count} 个旧副本")

        # 创建新副本
        created_count = 0
        for i in range(1, copy_count + 1):
            copy_name = f"{COPY_PREFIX}_{i}_{filename}"
            copy_path = os.path.join(folder_abs, copy_name)
            try:
                shutil.copy2(original_path, copy_path)
                created_count += 1
                print(f"[DEBUG] restore_weights: 创建副本 {copy_name}")
                log(f"restore_weights: 创建副本 {copy_name}")
            except Exception as e:
                print(f"[DEBUG] restore_weights: 复制失败 {copy_name}: {e}")
                log(f"restore_weights: 复制失败 {copy_name}: {e}")
        print(f"[DEBUG] restore_weights: 共创建 {created_count} 个副本 (目标: {copy_count})")

    print(f"[DEBUG] restore_weights: 恢复完成")
    log(f"restore_weights: 恢复完成")


def get_all_images_with_copies(folder_path):
    folder_abs = os.path.abspath(folder_path)
    if not os.path.isdir(folder_abs):
        return []
    all_files = os.listdir(folder_abs)
    return [os.path.join(folder_abs, f) for f in all_files
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]


def open_random_probability_window(parent, folder):
    if not folder or not os.path.isdir(folder):
        tk.messagebox.showwarning("提示喵", "请先设置幻灯片文件夹", parent=parent)
        return

    all_files = os.listdir(folder)
    image_ext = ('.jpg', '.jpeg', '.png', '.bmp')
    original_images = [f for f in all_files
                       if f.lower().endswith(image_ext) and not f.startswith(COPY_PREFIX)]

    if not original_images:
        tk.messagebox.showinfo("提示喵", "文件夹中没有图片", parent=parent)
        return

    win = tk.Toplevel(parent)
    win.title("随机概率设置")
    win.geometry("995x505")
    win.minsize(500, 400)
    icon_path = os.path.join(BASE_DIR, "img", "LOGO.ico")
    if os.path.exists(icon_path):
        try:
            win.iconbitmap(icon_path)
        except:
            pass

    main_frame = ttk.Frame(win, padding=10)
    main_frame.pack(fill="both", expand=True)

    # 存储每个图片的当前显示值和原始值
    items = {}
    pending_changes = {}  # {filename: new_value}
    has_unsaved_changes = False

    def mark_unsaved():
        nonlocal has_unsaved_changes
        has_unsaved_changes = True

    def on_image_click(filename, event=None):
        # 先移除所有图片的高亮边框
        for fname, data in items.items():
            data['frame'].config(highlightbackground='#ffffff', highlightcolor='#ffffff', highlightthickness=0)
        # 高亮当前选中的图片
        current_data = items[filename]
        current_data['frame'].config(highlightbackground='#12F2D8', highlightcolor='#12F2D8', highlightthickness=2)

    def create_thumbnail(img_path):
        try:
            img = Image.open(img_path)
            img.thumbnail((140, 100), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except:
            return None

    # 顶部按钮栏（背景色 #CCFCF2）
    top_frame = tk.Frame(main_frame, bg='#CCFCF2')
    top_frame.pack(fill="x", pady=(0, 10))

    def delete_all():
        nonlocal pending_changes, has_unsaved_changes
        if tk.messagebox.askyesno("确认？", f"删除文件夹「{folder}」中所有识别文件（副本）？\n注意：此操作立即生效，无法撤销喵",
                                  parent=win):
            cleanup_folder(folder)
            # 清空待保存更改
            pending_changes = {}
            has_unsaved_changes = False
            # 刷新窗口
            win.destroy()
            open_random_probability_window(parent, folder)

    btn_frame = tk.Frame(top_frame, bg='#CCFCF2')
    btn_frame.pack(side="left")
    ttk.Button(btn_frame, text="一键删除所有识别文件", command=delete_all).pack(side="left")
    tip_label = tk.Label(btn_frame, text="  ⓘ 此功能可以提供您喜欢的某个壁纸被随机到概率，也会在壁纸文件夹下创建识别文件，当然您可以随时恢复到最初状态",
                         bg='#CCFCF2', fg='#666666', font=("微软雅黑", 8))
    tip_label.pack(side="left", padx=(10, 0))

    def save_changes():
        nonlocal has_unsaved_changes, pending_changes
        print(f"[DEBUG] save_changes: pending_changes = {pending_changes}")
        if pending_changes:
            save_all_changes(folder, pending_changes.copy())
            # 更新原始值
            for filename, new_val in pending_changes.items():
                items[filename]['original_value'] = new_val
                items[filename]['weight_label'].config(text=f"喜欢附加值: {new_val}")
                print(f"[DEBUG] save_changes: 更新 {filename} 权重显示为 {new_val}")
            pending_changes = {}
            has_unsaved_changes = False
            win.destroy()  # 保存后自动关闭窗口
        else:
            print(f"[DEBUG] save_changes: 没有待保存的更改")

    def close_window():
        nonlocal has_unsaved_changes
        if has_unsaved_changes:
            result = tk.messagebox.askyesnocancel("未保存的更改",
                                                  "随机概率已修改，您是否保存更改啊？",
                                                  parent=win)
            if result is True:  # 是
                save_changes()
                win.destroy()
            elif result is False:  # 否
                win.destroy()
            # else: 取消，什么都不做
        else:
            win.destroy()

    ttk.Button(top_frame, text="保存", command=save_changes).pack(side="right", padx=(5, 0))
    ttk.Button(top_frame, text="取消", command=close_window).pack(side="right")

    # 滚动区域
    canvas = tk.Canvas(main_frame, bg='#ffffff', highlightthickness=0)
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg='#ffffff')
    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # 创建图片网格（使用 grid 布局，动态列数）
    all_img_frames = []
    for filename in original_images:
        full_path = os.path.join(folder, filename)
        photo = create_thumbnail(full_path)

        # 创建图片框架
        img_frame = tk.Frame(scrollable_frame, relief="flat", borderwidth=0, bg='#ffffff')

        if photo:
            img_label = tk.Label(img_frame, image=photo, cursor="hand2")
            img_label.image = photo
            img_label.pack(pady=5)
        else:
            img_label = tk.Label(img_frame, text="加载失败", bg="#ddd", width=20, height=8)
            img_label.pack(pady=5)

        name_label = ttk.Label(img_frame, text=filename, wraplength=130)
        name_label.pack()

        current_count = get_copy_count(folder, filename)
        weight_label = ttk.Label(img_frame, text=f"喜欢附加值: {current_count}")
        weight_label.pack(pady=(2, 0))

        # 滑块框架
        slider_frame = ttk.Frame(img_frame)

        # 创建独立的变量（关键：每个图片有自己的变量）
        var = tk.IntVar(value=current_count)

        scale = ttk.Scale(slider_frame, from_=0, to=20, orient="horizontal",
                          variable=var, length=120)
        scale.pack(side="left", padx=5)

        # 可编辑的输入框
        spinbox = ttk.Spinbox(slider_frame, from_=0, to=999, width=4, textvariable=var)
        spinbox.pack(side="left", padx=2)

        # 保存当前循环中的变量到局部变量，确保每个图片独立
        current_filename = filename
        current_var = var
        current_scale = scale
        current_spinbox = spinbox

        def on_slide(val, fn=current_filename, v=current_var, sb=current_spinbox):
            int_val = int(float(val))
            v.set(int_val)
            sb.delete(0, tk.END)
            sb.insert(0, str(int_val))
            pending_changes[fn] = int_val
            mark_unsaved()

        def on_spinbox_change(*args, fn=current_filename, v=current_var, sc=current_scale, sb=current_spinbox):
            try:
                val = v.get()
                if val < 0:
                    val = 0
                    v.set(0)
                if val > 999:
                    val = 999
                    v.set(999)
                sc.set(val)
                sb.delete(0, tk.END)
                sb.insert(0, str(val))
                pending_changes[fn] = val
                mark_unsaved()
            except:
                pass

        scale.config(command=on_slide)
        var.trace_add("write", on_spinbox_change)

        slider_frame.pack(fill="x", pady=(5, 0))

        items[filename] = {
            'frame': img_frame,
            'slider_frame': slider_frame,
            'var': var,
            'scale': scale,
            'weight_label': weight_label,
            'original_value': current_count,
            'display_value': current_count
        }

        img_label.bind("<Button-1>", lambda e, fn=filename: on_image_click(fn))
        name_label.bind("<Button-1>", lambda e, fn=filename: on_image_click(fn))
        weight_label.bind("<Button-1>", lambda e, fn=filename: on_image_click(fn))

        all_img_frames.append(img_frame)

    # 动态布局函数：使用 grid 重新排列
    def relayout(event=None):
        canvas_width = canvas.winfo_width()
        if canvas_width < 100:
            canvas_width = 800
        min_item_width = 170
        cols = max(1, canvas_width // min_item_width)

        for img_frame in all_img_frames:
            img_frame.grid_forget()

        for i, img_frame in enumerate(all_img_frames):
            row = i // cols
            col = i % cols
            img_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

        for c in range(cols):
            scrollable_frame.grid_columnconfigure(c, weight=1)

    # 将所有框架放入 scrollable_frame
    for img_frame in all_img_frames:
        img_frame.pack_forget()

    win.update_idletasks()
    relayout()
    canvas.bind("<Configure>", relayout)

    def on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind("<MouseWheel>", on_mousewheel)
    scrollable_frame.bind("<MouseWheel>", on_mousewheel)

    win.protocol("WM_DELETE_WINDOW", close_window)
    win.mainloop()