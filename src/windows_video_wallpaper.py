import argparse
import os
import subprocess
import sys
import time
import threading

from app_config import IS_WINDOWS

try:
    import psutil
except ImportError:
    psutil = None

PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "windows_video_wallpaper.pid")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".avi", ".mkv")


def is_supported_platform():
    return IS_WINDOWS


def validate_video_path(path):
    return bool(path and os.path.isfile(path) and path.lower().endswith(VIDEO_EXTENSIONS))


def _read_pid():
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def _is_process_alive(pid):
    if not pid:
        return False
    if psutil is not None:
        try:
            process = psutil.Process(pid)
            if process.status() == psutil.STATUS_ZOMBIE:
                return False
            return process.is_running()
        except psutil.NoSuchProcess:
            return False
        except Exception:
            pass
    try:
        import ctypes
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


def stop_video_wallpaper():
    pid = _read_pid()
    if pid:
        _terminate_pid(pid)
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass


def _terminate_pid(pid):
    if not _is_process_alive(pid):
        return
    if psutil is not None:
        try:
            process = psutil.Process(pid)
            children = process.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except Exception:
                    pass
            process.terminate()
            gone, alive = psutil.wait_procs([process, *children], timeout=2)
            for proc in alive:
                try:
                    proc.kill()
                except Exception:
                    pass
            psutil.wait_procs(alive, timeout=1)
            return
        except psutil.NoSuchProcess:
            return
        except Exception:
            pass
    try:
        import ctypes
        PROCESS_TERMINATE = 0x0001
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if handle:
            ctypes.windll.kernel32.TerminateProcess(handle, 0)
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass


def start_video_wallpaper(video_path):
    """
    启动Windows视频壁纸
    使用MPV播放器在桌面上播放视频
    """
    if not IS_WINDOWS:
        return False, "Windows视频壁纸仅支持 Windows"

    if not validate_video_path(video_path):
        return False, "请选择有效的视频文件 (mp4/mov/m4v/avi/mkv)"

    # 检查是否已有运行中的实例
    pid = _read_pid()
    if pid and _is_process_alive(pid):
        return True, ""

    try:
        # 使用MPV播放器播放视频壁纸
        # MPV需要安装并在PATH中
        cmd = [
            "mpv.exe",
            "--no-audio",
            "--loop",
            "--no-osc",
            "--no-osd",
            "--no-input-default-bindings",
            "--input-ipc-server=\\\\.\\pipe\\mpv-socket",
            "--wid=0",  # 嵌入到桌面
            video_path
        ]

        # 或者使用VLC作为备选
        # cmd = [
        #     "vlc.exe",
        #     "--no-audio",
        #     "--loop",
        #     "--no-video-title",
        #     "--no-qt-system-tray",
        #     video_path
        # ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(process.pid))

        return True, ""

    except FileNotFoundError:
        return False, "未找到视频播放器，请安装MPV或VLC并添加到PATH"
    except Exception as e:
        return False, f"启动视频壁纸失败: {str(e)}"


def is_video_wallpaper_running():
    """检查视频壁纸是否正在运行"""
    pid = _read_pid()
    return pid and _is_process_alive(pid)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video_path", help="视频文件路径")
    args = parser.parse_args()

    success, error = start_video_wallpaper(args.video_path)
    if not success:
        print(f"错误: {error}")
        sys.exit(1)
    else:
        print("Windows视频壁纸已启动")
        # 保持运行直到被终止
        try:
            while True:
                time.sleep(1)
                if not is_video_wallpaper_running():
                    break
        except KeyboardInterrupt:
            pass
        stop_video_wallpaper()


if __name__ == "__main__":
    main()