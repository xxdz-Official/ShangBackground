from __future__ import annotations

import importlib.util
import subprocess
import sys
import threading
from typing import Iterable

from app_config import DEPENDENCIES
from i18n import t


def get_missing_dependencies(availability):
    missing = []
    availability = availability or {}
    for dep in DEPENDENCIES:
        module = dep["module"]
        installed = availability.get(module)
        if installed is None:
            installed = importlib.util.find_spec(module) is not None
        if not installed:
            missing.append(dep)
    return missing


def build_install_command(packages: Iterable[str]):
    return [sys.executable, "-m", "pip", "install", *packages]


def _format_command(packages: Iterable[str]) -> str:
    return " ".join(build_install_command(packages))


def _try_import_tk():
    try:
        import tkinter as tk
        from tkinter import messagebox, scrolledtext
        return tk, messagebox, scrolledtext
    except Exception:
        return None, None, None


_TK_HIDDEN_ROOT = None


def _get_hidden_root():
    """Return a singleton hidden Tk root suitable as parent for messageboxes.

    Avoid creating/destroying many temporary Tk instances which can flash
    windows on some platforms. If Tk is unavailable, return None.
    """
    global _TK_HIDDEN_ROOT
    if _TK_HIDDEN_ROOT is not None:
        return _TK_HIDDEN_ROOT
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        _TK_HIDDEN_ROOT = root
        return root
    except Exception:
        return None


def _install_with_tk(packages) -> bool:
    tk, messagebox, scrolledtext = _try_import_tk()
    if tk is None:
        return False

    command = build_install_command(packages)
    win = tk.Tk()
    win.title(t("安装运行依赖"))
    win.geometry("680x420")
    win.minsize(560, 340)

    title = tk.Label(win, text=t("正在安装运行依赖"), font=("Microsoft YaHei UI", 12, "bold"))
    title.pack(anchor="w", padx=12, pady=(12, 4))
    status = tk.Label(win, text=t("准备执行：") + " ".join(command), anchor="w", justify="left", wraplength=640)
    status.pack(fill="x", padx=12)
    log_box = scrolledtext.ScrolledText(win, height=16)
    log_box.pack(fill="both", expand=True, padx=12, pady=10)
    close_btn = tk.Button(win, text=t("关闭"), state="disabled", command=win.destroy)
    close_btn.pack(anchor="e", padx=12, pady=(0, 12))

    result = {"ok": False}

    def append(text: str):
        log_box.insert("end", text)
        log_box.see("end")

    def worker():
        rc = -1
        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if proc.stdout is not None:
                for line in proc.stdout:
                    win.after(0, append, line)
            rc = proc.wait()
        except Exception as exc:
            win.after(0, append, "\n" + t("安装进程启动失败：") + f"{exc}\n")
        result["ok"] = (rc == 0)
        def finish():
            status.config(text=t("依赖安装完成，请重新启动软件。") if rc == 0 else t("依赖安装失败，请复制命令手动执行。"))
            append("\n" + (t("安装完成。") if rc == 0 else t("安装失败，退出码：") + str(rc)) + "\n")
            close_btn.config(state="normal")
        win.after(0, finish)

    append("$ " + " ".join(command) + "\n\n")
    threading.Thread(target=worker, daemon=True).start()
    win.mainloop()
    return bool(result["ok"])


def _prompt_with_tk(missing, packages) -> bool | None:
    tk, messagebox, _scrolledtext = _try_import_tk()
    command_text = _format_command(packages)
    if tk is None:
        print(t("缺少运行依赖：") + ", ".join(dep["package"] for dep in missing))
        print(t("可以在终端执行：") + command_text)
        return None

    root = _get_hidden_root()
    names = "\n".join(f"- {dep['package']}：{dep['desc']}" for dep in missing)
    text = t("检测到缺少运行依赖：") + "\n\n" + names + "\n\n" + t("是否现在自动安装？")
    if root is not None:
        answer = messagebox.askyesnocancel(t("运行依赖检查"), text, parent=root)
    else:
        answer = messagebox.askyesnocancel(t("运行依赖检查"), text)
    if answer is None:
        return False
    if answer:
        ok = _install_with_tk(packages)
        if ok:
            root = _get_hidden_root()
            if root is not None:
                messagebox.showinfo(t("安装完成"), t("依赖安装完成，请重新启动软件。"), parent=root)
            else:
                messagebox.showinfo(t("安装完成"), t("依赖安装完成，请重新启动软件。"))
            return False
        root = _get_hidden_root()
        if root is not None:
            messagebox.showerror(t("安装失败"), t("依赖安装失败，请在终端手动执行：") + "\n\n" + command_text, parent=root)
        else:
            messagebox.showerror(t("安装失败"), t("依赖安装失败，请在终端手动执行：") + "\n\n" + command_text)
        return False

    root = _get_hidden_root()
    if root is not None:
        messagebox.showinfo(t("手动安装依赖"), t("可以在终端执行：") + "\n\n" + command_text, parent=root)
    else:
        messagebox.showinfo(t("手动安装依赖"), t("可以在终端执行：") + "\n\n" + command_text)
    return None


def show_install_log_window(parent, packages):
    ok = _install_with_tk(list(packages))
    return ok, _format_command(packages)


def prompt_install_dependencies(_notifier, availability, parent=None, prefer_pyside=None):
    """用 tkinter 显示小型依赖提示，不再依赖 PySide6 才能弹出安装窗口。"""
    missing = get_missing_dependencies(availability)
    if not missing:
        return True

    packages = [dep["package"] for dep in missing]
    required_missing = [dep for dep in missing if dep.get("required")]
    result = _prompt_with_tk(missing, packages)
    if result is False:
        return False
    if required_missing:
        print(t("缺少必需依赖：") + ", ".join(dep["package"] for dep in required_missing))
        return False
    return True
