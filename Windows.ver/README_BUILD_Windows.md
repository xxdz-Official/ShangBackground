# Windows.ver 构建说明

Windows 版只面向 Windows 运行，不依赖其他客户端目录。

```bat
cd Windows.ver
build_windows_onedir.bat
.\dist\ShangBackground\ShangBackground.exe
```

完整 onedir + UPX 命令见根目录 `BUILD_COMMANDS_ALL_PLATFORMS.md`。

说明：

- 依赖使用 `PySide6-Essentials`。
- 不再使用 `--collect-all PySide6`；只显式补充 SVG 图标需要的 `QtSvg/QtSvgWidgets`。
- 当前版本固定为 `1.3.0`，更新检查可解析 `1.3.0`、`v1.3.0`、`app_ver=1.3.0` 以及带前后缀的 Release 名称。
