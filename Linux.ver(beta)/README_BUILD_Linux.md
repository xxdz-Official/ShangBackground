# Linux.ver(beta) 说明（Ubuntu / Debian / Fedora 优先）

## 运行源码

Linux 分支只面向 Linux。依赖提示会读取 `/etc/os-release`，优先给出发行版包管理器命令：Ubuntu/Debian 使用 `apt`，Fedora 使用 `dnf`，Arch 系作为常见桌面回退使用 `pacman`；无法可靠识别时才回退到 `pip --user`。

```bash
cd "Linux.ver(beta)"
python3 src/main.py
```

如需手动安装运行依赖，可按系统选择：

```bash
# Ubuntu / Debian / Linux Mint 等 apt 系
sudo apt update
sudo apt install -y python3-pil python3-requests python3-numpy \
  python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets \
  python3-pyside6.qtsvg python3-pyside6.qtsvgwidgets \
  python3-httpx python3-psutil libxcb-cursor0 libxkbcommon-x11-0 xrandr

# Fedora / RHEL 系
sudo dnf install -y python3-pillow python3-requests python3-numpy \
  python3-pyside6 python3-httpx python3-psutil xrandr

# Arch / Manjaro / EndeavourOS 系
sudo pacman -Syu --needed python-pillow python-requests python-numpy \
  pyside6 python-httpx python-psutil xorg-xrandr
```

按桌面环境安装至少一个壁纸后端：

```bash
# GNOME / Cinnamon 通常已有 gsettings
sudo apt install -y dconf-gsettings-backend

# KDE Plasma 可选
sudo apt install -y plasma-workspace

# XFCE 可选
sudo apt install -y xfconf

# 轻量窗口管理器可选
sudo apt install -y feh nitrogen
```

## PyInstaller + UPX onedir 打包命令

> 说明：PyInstaller 会通过 `--upx-dir` 查找 UPX。Qt 插件/部分共享库可能不适合 UPX 压缩，PyInstaller 新版会自动排除不少 Qt 插件；如果某个 `.so` 被压坏，额外加 `--upx-exclude "*.so"` 或对问题文件单独排除。

```bash
cd "Linux.ver(beta)"
python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --contents-directory "." \
  --name "ShangBackground" \
  --paths "src" \
  --add-data "src/img:img" \
  --add-data "src/lang:lang" \
  --add-data "src/settings.json:." \
  --add-data "fonts:fonts" \
  --hidden-import "PySide6.QtSvg" \
  --hidden-import "PySide6.QtSvgWidgets" \
  --exclude-module "tkinter" \
  --exclude-module "PyQt5" \
  --exclude-module "PyQt6" \
  --exclude-module "PySide2" \
  --exclude-module "matplotlib" \
  --exclude-module "pandas" \
  --exclude-module "scipy" \
  --exclude-module "IPython" \
  --exclude-module "notebook" \
  --exclude-module "pytest" \
  --upx-dir "/path/to/upx-directory" \
  "src/main.py"
```

也可以直接执行脚本；脚本会自动使用 `PATH` 中的 `upx`，或使用你提供的 `UPX_DIR`：

```bash
chmod +x build_linux_onedir.sh
UPX_DIR=/path/to/upx-directory ./build_linux_onedir.sh
./dist/ShangBackground/ShangBackground
```

分发给其他同架构 Linux 用户：

```bash
tar -xzf ShangBackground-linux-x86_64.tar.gz
./ShangBackground/ShangBackground
```

## Linux 专项改动

- 壁纸设置按顺序尝试 `gsettings`、`plasma-apply-wallpaperimage`、`qdbus/qdbus6`、`xfconf-query`、`feh`、`nitrogen`。
- 开机自启动只写入 `~/.config/autostart/shangbackground.desktop`，不再保留 Windows/macOS 启动项分支。
- 依赖检查不再创建额外 tkinter 根窗口：PySide6 可用时使用当前 Qt 主窗口；PySide6 不可用时只在终端输出命令。
- 更新检查使用 `src/update_services.py` 读取 GitHub Release；版本策略固定为 `1.3.0`，可解析 `1.3.0`、`v1.3.0`、`app_ver=1.3.0` 以及带前后缀的 Release 名称。
- PyInstaller 命令不再 `--collect-all PySide6`，只补充实际需要的 QtSvg/QtSvgWidgets，并显式排除 tkinter、其他 Qt 绑定和常见大体积无关科学/Notebook 库。

## Debian/KDE Live 运行提示

如果出现 Qt 平台插件 xcb 无法初始化，先安装运行库：

```bash
sudo apt install libxcb-cursor0 libxkbcommon-x11-0
```

KDE Plasma 壁纸优先使用 `plasma-apply-wallpaperimage`，缺失时会退回 `qdbus6/qdbus`。
