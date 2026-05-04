# 本仓库为[xxdz-Official/ShangBackground](https://github.com/xxdz-Official/ShangBackground/)的开发版,不稳定,由于我的电脑是macOS,目前没有对Windows环境进行测试

# ShangBackground
实现“上一个桌面背景”的右键菜单，而且有更多的壁纸切换动画，可高度自定义！由B站UP_小小电子xxdz开发

## macOS 本机支持

现在可以在 macOS 上直接运行源码版：

```bash
python3 src/main.py
```

默认界面已迁移到 PySide6 Qt Quick/QML。若需要临时回到旧 Tk 界面，可运行：

```bash
python3 src/main.py --legacy-tk
```

macOS 支持的能力：

- 设置/读取当前桌面背景，使用系统 `osascript` 调用。
- 图片、纯色、渐变、幻灯片等主流程可运行。
- 视频壁纸使用独立 macOS 桌面层级播放器子进程，避免与 Tk 主循环冲突。
- 菜单栏常驻使用独立 macOS 原生 helper 子进程，菜单项由 QML 设置窗口保存的配置控制。
- 右键菜单使用 macOS Finder 系统服务/快速操作集成，可执行上一张、下一张、随机、跳转、显示主界面和文件设为壁纸。
- 开机自启动使用 `~/Library/LaunchAgents/com.xxdz.shangbackground.plist`。
- Windows 桌面右键菜单注册会在 macOS 上自动跳过，避免启动报错。

建议依赖：

```bash
python3 -m pip install PySide6 pillow requests numpy pystray psutil pyobjc-framework-Cocoa pyobjc-framework-AVFoundation
```

其中 `PySide6` 为默认 Qt Quick/QML 界面必需依赖；首次启动缺失时会提示安装。`psutil` 为可选依赖；未安装时仅跳过旧进程清理。`pyobjc-framework-Cocoa` 用于 macOS 菜单栏常驻，`pyobjc-framework-AVFoundation` 用于 macOS 视频壁纸。
