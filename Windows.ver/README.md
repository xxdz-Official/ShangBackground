# ShangBackground Windows.ver

这是 Windows 独立分支，基于 PySide6 版整理，保留 Windows 专用能力，不和 macOS / Linux 分支混放。

## 已合并的通用 GUI 更改

- 启动时读取 `settings.json` 的 `language`，英文界面不会只保存配置却不生效。
- 标题栏空闲处增加 66px 宽 `中 / EN` 切换，不改动原主按钮和布局。
- 设置页语言选项与标题栏语言选项同步。
- 英文译文尽量短，降低按钮、下拉框错位风险。
- 系统托盘右键 `关于` 调用 `show_about_dialog()`，效果等价于点击 GUI 精灵图。

## Windows 专用逻辑

- 保留桌面右键菜单、注册表壁纸样式、自启动、管理员权限重启、Windows 消息单实例/唤醒等逻辑。
- 不把 macOS 的 `osascript` 或 Linux 的 `gsettings/xfconf/feh` 当成 Windows 专属路径。
- 配置与随机概率数据存放在 `%LOCALAPPDATA%/ShangBackground`；首次运行会尽量迁移旧目录中的配置，避免安装目录只读和多用户互相影响。

## 运行源码

```bat
python -m pip install -r requirements-windows.txt
python src\main.py
```

## 打包

推荐先用 `build_windows_onedir.bat`。脚本优先使用项目内 `upx\upx.exe`，不存在时再尝试 PATH 中的 UPX；同时显式排除 Qt/Python 关键 DLL，降低压缩破坏 Qt 插件的概率。

```bat
build_windows_onedir.bat
.\dist\ShangBackground\ShangBackground.exe
```

如果打包后出现 Qt platform plugin、DLL 加载或杀软误报问题，用无 UPX 兜底脚本：

```bat
build_windows_onedir_noupx.bat
```
