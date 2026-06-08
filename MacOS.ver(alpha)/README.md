# ShangBackground macOS 适配版

这是从 Windows PySide6 版迁移出的 macOS 独立目录。主要入口：

- 源码运行：`python3 src/main.py`
- 打包脚本：`./build_macos_onedir.sh`
- 打包说明：`README_BUILD_MacOS.md`

主要改动：英文 CN/EN 语言切换、托盘“关于”等价到 GUI 精灵图关于窗口、macOS osascript 壁纸切换、LaunchAgents 自启动、用户目录配置文件、PyInstaller onedir 资源路径适配。
