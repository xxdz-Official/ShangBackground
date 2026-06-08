# macOS.ver(alpha) 构建说明

macOS 版只面向 macOS 运行，不依赖其他客户端目录。首次切换壁纸时，系统可能要求允许 Terminal / Python / 打包后的 App 控制 “System Events”。

```bash
cd "MacOS.ver(alpha)"
python3 -m pip install -r requirements-macos.txt
python3 src/main.py
```

打包：

```bash
chmod +x build_macos_onedir.sh
./build_macos_onedir.sh
open dist/ShangBackground.app
```

说明：

- 依赖使用 `PySide6-Essentials`。
- 不再使用 `--collect-all PySide6`；只显式补充 SVG 图标需要的 `QtSvg/QtSvgWidgets`。
- 当前版本固定为 `1.3.0`，更新检查可解析 `1.3.0`、`v1.3.0`、`app_ver=1.3.0` 以及带前后缀的 Release 名称。
