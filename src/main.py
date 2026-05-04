import importlib.util
import argparse
import sys


def _print_help():
    parser = argparse.ArgumentParser(description="xxdz_上一个桌面背景")
    parser.add_argument("--previous", action="store_true", help="切换到上一张壁纸")
    parser.add_argument("--next", action="store_true", help="切换到下一张壁纸")
    parser.add_argument("--random", action="store_true", help="随机切换壁纸")
    parser.add_argument("--show", action="store_true", help="显示主窗口")
    parser.add_argument("--hide", action="store_true", help="隐藏主窗口")
    parser.add_argument("--jump-to-wallpaper", action="store_true", help="打开壁纸侧边栏")
    parser.add_argument("--set-wallpaper", help="设置指定壁纸")
    parser.add_argument("--quick-settings", action="store_true", help="显示快速设置")
    parser.add_argument("--switch-mode", action="store_true", help="切换壁纸模式")
    parser.add_argument("--open-wallpaper-folder", action="store_true", help="打开壁纸文件夹")
    parser.add_argument("--about", action="store_true", help="显示关于信息")
    parser.add_argument("--legacy-tk", action="store_true", help="使用旧 Tk 界面启动")
    parser.print_help()


def _ensure_pyside6():
    if importlib.util.find_spec("PySide6") is not None:
        return True
    try:
        import tkinter as tk
        from tkinter import messagebox

        from dependency_prompt import prompt_install_dependencies

        root = tk.Tk()
        root.withdraw()
        ok = prompt_install_dependencies(
            messagebox,
            {"PySide6": False},
            parent=root,
        )
        root.destroy()
        return ok and importlib.util.find_spec("PySide6") is not None
    except Exception:
        print("缺少 PySide6，请先执行：")
        print(f"{sys.executable} -m pip install PySide6")
        return False


def main():
    if "--macos-menu-bar-helper" in sys.argv:
        sys.argv.remove("--macos-menu-bar-helper")
        from macos_menu_bar import main as menu_bar_main

        menu_bar_main()
        return

    if "--macos-video-wallpaper-helper" in sys.argv:
        sys.argv.remove("--macos-video-wallpaper-helper")
        from macos_video_wallpaper import main as video_wallpaper_main

        video_wallpaper_main()
        return

    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        _print_help()
        return

    cli_actions = {
        "--previous",
        "--next",
        "--random",
        "--set-wallpaper",
    }
    if any(arg in cli_actions for arg in sys.argv[1:]) and importlib.util.find_spec("PySide6") is None:
        from tk_main import handle_command_line

        handle_command_line()
        return

    if "--legacy-tk" in sys.argv:
        sys.argv.remove("--legacy-tk")
        from tk_main import main as tk_main

        tk_main()
        return

    if not _ensure_pyside6():
        return

    from qml_main import main as qt_main

    qt_main()


if __name__ == "__main__":
    main()
