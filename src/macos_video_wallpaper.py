import argparse
import importlib.util
import os
import signal
import subprocess
import sys
import time

from app_config import IS_MACOS

try:
    import psutil
except ImportError:
    psutil = None


PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_wallpaper.pid")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".avi", ".mkv")


def is_supported_platform():
    return IS_MACOS


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
        os.kill(pid, 0)
        return True
    except OSError:
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
        _reap_child(pid)
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
            _reap_child(pid)
            return
        except psutil.NoSuchProcess:
            _reap_child(pid)
            return
        except Exception:
            pass
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(40):
            if not _is_process_alive(pid):
                break
            time.sleep(0.05)
        if _is_process_alive(pid):
            os.kill(pid, signal.SIGKILL)
            for _ in range(20):
                if not _is_process_alive(pid):
                    break
                time.sleep(0.05)
    except ProcessLookupError:
        pass
    except Exception:
        pass
    _reap_child(pid)


def _reap_child(pid):
    try:
        while True:
            waited_pid, _ = os.waitpid(pid, os.WNOHANG)
            if waited_pid == 0:
                break
    except ChildProcessError:
        pass
    except Exception:
        pass


def start_video_wallpaper(video_path, muted=True):
    if not IS_MACOS:
        return False, "视频壁纸当前仅支持 macOS"
    if importlib.util.find_spec("AVFoundation") is None:
        return False, "缺少 pyobjc-framework-AVFoundation，请先安装依赖"
    if not validate_video_path(video_path):
        return False, "请选择 mp4/mov/m4v/avi/mkv 视频文件"

    stop_video_wallpaper()
    if getattr(sys, "frozen", False):
        cmd = [
            os.path.abspath(sys.executable),
            "--macos-video-wallpaper-helper",
            "--run-player",
            os.path.abspath(video_path),
        ]
    else:
        cmd = [
            sys.executable,
            os.path.abspath(__file__),
            "--run-player",
            os.path.abspath(video_path),
        ]
    if muted:
        cmd.append("--muted")
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(process.pid))
        return True, ""
    except Exception as e:
        return False, str(e)


def _get_desktop_window_level(Quartz):
    try:
        return Quartz.CGWindowLevelForKey(Quartz.kCGDesktopIconWindowLevelKey) - 1
    except Exception:
        return Quartz.CGWindowLevelForKey(Quartz.kCGDesktopWindowLevelKey) + 1


def run_player(video_path, muted=True):
    if not validate_video_path(video_path):
        raise SystemExit(2)

    import objc
    from AppKit import (
        NSApplication,
        NSApplicationActivationPolicyAccessory,
        NSBackingStoreBuffered,
        NSBorderlessWindowMask,
        NSColor,
        NSScreen,
        NSWindow,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorIgnoresCycle,
        NSWindowCollectionBehaviorStationary,
    )
    from Foundation import NSObject, NSNotificationCenter, NSURL
    import AVFoundation
    import Quartz

    try:
        import CoreMedia
    except Exception:
        CoreMedia = None

    class LoopObserver(NSObject):
        player = objc.ivar()

        def initWithPlayer_(self, player):
            self = objc.super(LoopObserver, self).init()
            if self is None:
                return None
            self.player = player
            return self

        def playerDidFinish_(self, notification):
            try:
                if CoreMedia is not None:
                    self.player.seekToTime_(CoreMedia.CMTimeMake(0, 1))
                else:
                    self.player.seekToTime_(AVFoundation.CMTimeMake(0, 1))
                self.player.play()
            except Exception:
                pass

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    windows = []
    players = []
    observers = []
    layers = []

    def terminate_player(signum, frame):
        for player in players:
            try:
                player.pause()
            except Exception:
                pass
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except Exception:
            pass
        os._exit(0)

    signal.signal(signal.SIGTERM, terminate_player)
    signal.signal(signal.SIGINT, terminate_player)

    window_level = _get_desktop_window_level(Quartz)
    video_url = NSURL.fileURLWithPath_(os.path.abspath(video_path))

    for screen in NSScreen.screens():
        frame = screen.frame()
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            NSBorderlessWindowMask,
            NSBackingStoreBuffered,
            False,
        )
        window.setLevel_(window_level)
        window.setOpaque_(True)
        window.setBackgroundColor_(NSColor.blackColor())
        window.setIgnoresMouseEvents_(True)
        window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        view = window.contentView()
        view.setWantsLayer_(True)
        player_item = AVFoundation.AVPlayerItem.playerItemWithURL_(video_url)
        player = AVFoundation.AVPlayer.playerWithPlayerItem_(player_item)
        player.setMuted_(bool(muted))

        layer = AVFoundation.AVPlayerLayer.playerLayerWithPlayer_(player)
        layer.setFrame_(view.bounds())
        try:
            layer.setVideoGravity_(AVFoundation.AVLayerVideoGravityResizeAspectFill)
        except Exception:
            layer.setVideoGravity_("AVLayerVideoGravityResizeAspectFill")
        view.layer().addSublayer_(layer)

        observer = LoopObserver.alloc().initWithPlayer_(player)
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            observer,
            "playerDidFinish:",
            AVFoundation.AVPlayerItemDidPlayToEndTimeNotification,
            player_item,
        )

        window.orderFrontRegardless()
        player.play()

        windows.append(window)
        players.append(player)
        observers.append(observer)
        layers.append(layer)

    app.run()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-player", dest="video_path")
    parser.add_argument("--muted", action="store_true")
    args = parser.parse_args()
    if args.video_path:
        run_player(args.video_path, muted=args.muted)


if __name__ == "__main__":
    main()
