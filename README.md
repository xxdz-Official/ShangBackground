# Windows 支持（原版）
实现“上一个桌面背景”的右键菜单，而且有更多的壁纸切换动画，可高度自定义！由B站UP_小小电子xxdz开发

## macOS 支持（感谢@zjhcx贡献）

现在可以在 macOS 上直接运行源码版：

```bash
cd "上一个桌面背景 - 源代码"
python3 main.py
```

macOS 支持的能力：

- 设置/读取当前桌面背景，使用系统 `osascript` 调用。
- 图片、纯色、渐变、幻灯片等主流程可运行。
- 开机自启动使用 `~/Library/LaunchAgents/com.xxdz.shangbackground.plist`。
- Windows 桌面右键菜单注册会在 macOS 上自动跳过，避免启动报错。

建议依赖：

```bash
python3 -m pip install pillow requests numpy pystray psutil
```

其中 `psutil` 为可选依赖；未安装时仅跳过旧进程清理。
