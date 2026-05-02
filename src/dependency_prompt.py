import importlib.util
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

from app_config import DEPENDENCIES


def get_missing_dependencies(availability):
    missing = []
    for dep in DEPENDENCIES:
        module = dep["module"]
        installed = availability.get(module)
        if installed is None:
            installed = importlib.util.find_spec(module) is not None
        if not installed:
            missing.append(dep)
    return missing


def build_install_command(packages):
    return [sys.executable, "-m", "pip", "install", *packages]


def show_install_log_window(parent, packages):
    cmd = build_install_command(packages)
    output_queue = queue.Queue()
    result = {"returncode": None, "error": ""}

    win = tk.Toplevel(parent) if parent is not None else tk.Toplevel()
    win.title("安装运行依赖")
    win.geometry("720x420")
    win.minsize(620, 360)
    win.transient(parent)
    win.grab_set()

    container = ttk.Frame(win, padding=12)
    container.pack(fill="both", expand=True)

    status_var = tk.StringVar(value="正在安装依赖...")
    ttk.Label(container, textvariable=status_var).pack(anchor="w", pady=(0, 8))

    text_frame = ttk.Frame(container)
    text_frame.pack(fill="both", expand=True)

    log_text = tk.Text(text_frame, wrap="word", height=16, state="disabled")
    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=log_text.yview)
    log_text.configure(yscrollcommand=scrollbar.set)
    log_text.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    close_btn = ttk.Button(container, text="关闭", command=win.destroy, state="disabled")
    close_btn.pack(anchor="e", pady=(10, 0))

    def append_log(message):
        log_text.configure(state="normal")
        log_text.insert("end", message)
        log_text.see("end")
        log_text.configure(state="disabled")

    append_log("$ " + " ".join(cmd) + "\n\n")

    def worker():
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if process.stdout is not None:
                for line in process.stdout:
                    output_queue.put(("log", line))
            result["returncode"] = process.wait()
        except Exception as e:
            result["returncode"] = -1
            result["error"] = str(e)
            output_queue.put(("log", f"\n安装进程启动失败：{e}\n"))
        finally:
            output_queue.put(("done", None))

    def poll_output():
        while True:
            try:
                kind, payload = output_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                append_log(payload)
            elif kind == "done":
                if result["returncode"] == 0:
                    status_var.set("依赖安装完成，请重新启动软件。")
                    append_log("\n安装完成。\n")
                else:
                    status_var.set("依赖安装失败，请查看日志。")
                    append_log(f"\n安装失败，退出码：{result['returncode']}\n")
                close_btn.configure(state="normal")
                return
        win.after(80, poll_output)

    threading.Thread(target=worker, daemon=True).start()
    win.after(80, poll_output)
    win.wait_window()
    return result["returncode"] == 0, " ".join(cmd)


def prompt_install_dependencies(messagebox, availability, parent=None):
    missing = get_missing_dependencies(availability)
    if not missing:
        return True

    required_missing = [dep for dep in missing if dep["required"]]
    packages = [dep["package"] for dep in missing]
    details = "\n".join(
        f"- {dep['package']}：{dep['desc']}" + ("（必需）" if dep["required"] else "（建议）")
        for dep in missing
    )
    cmd_text = f"{sys.executable} -m pip install {' '.join(packages)}"
    msg = (
        "检测到软件运行依赖未安装：\n\n"
        f"{details}\n\n"
        "是否现在自动安装？\n\n"
        f"将执行：\n{cmd_text}"
    )

    try:
        should_install = messagebox.askyesno("安装运行依赖", msg)
    except Exception:
        should_install = False

    if should_install:
        success, cmd_text = show_install_log_window(parent, packages)
        if success:
            messagebox.showinfo("安装完成", "依赖安装完成，请重新启动软件。")
            return False
        messagebox.showerror("安装失败", f"依赖安装失败，请查看日志窗口，或在终端手动执行：\n\n{cmd_text}")
    else:
        messagebox.showinfo("手动安装依赖", f"可以在终端执行：\n\n{cmd_text}")

    if required_missing:
        messagebox.showerror("缺少必需依赖", "缺少必需依赖，软件无法继续启动。")
        return False
    return True
