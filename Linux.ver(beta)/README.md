# ShangBackground Linux.ver(beta)

这是从 Windows PySide6 版迁移出的 Linux 独立目录，优先适配 Debian / Ubuntu / GNOME，同时加入 KDE、XFCE、feh、nitrogen 的壁纸后端兜底。

- 源码运行：`python3 src/main.py`
- 打包脚本：`./build_linux_onedir.sh`
- 打包说明：`README_BUILD_Linux.md`

主要改动：英文 CN/EN 语言切换、托盘“关于”等价到 GUI 精灵图关于窗口、XDG autostart、用户目录配置文件、PyInstaller onedir 资源路径适配。
