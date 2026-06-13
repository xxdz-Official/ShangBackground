
<h1><img src="https://xxdz-official.github.io/ShangBackground/img/LOGO.png" width="100" height="100" style="display: inline-block; vertical-align: middle;">  上一个桌面背景</h1>

作者：小小电子xxdz

B站UID: [小小电子xxdz的个人空间](https://space.bilibili.com/3461569935575626)

演示视频：https://www.bilibili.com/video/BV1juRgBbE2G

---

## 💻 Windows 支持（原版）

实现“上一个桌面背景”的右键菜单，而且有更多的壁纸切换动画，可高度自定义！由 B站 UP_小小电子xxdz 开发 ᗜⰙᗜ

---

## 🍎 贡献版 1：macOS 基础支持

**作者：@zjhcx**

现在可以在 macOS 上直接运行源码版：

```bash
cd "上一个桌面背景 - 源代码"
python3 main.py
```

macOS 支持的能力 ૮₍ ˊᯅˋ₎ა：

- 设置/读取当前桌面背景，使用系统 `osascript` 调用
- 图片、纯色、渐变、幻灯片等主流程可运行
- 开机自启动使用 `~/Library/LaunchAgents/com.xxdz.shangbackground.plist`。
- Windows 桌面右键菜单注册会在 macOS 上自动跳过，避免启动报错

建议依赖：

```bash
python3 -m pip install pillow requests numpy pystray psutil
```

其中 `psutil` 为可选依赖；未安装时仅跳过旧进程清理 (｡- .•)

---

## 🧩 贡献版 2：【贡献版】v-1.3.0

**作者：hjy-233、purrfecto114-lgtm**

在这个版本中，添加了自动化打包脚本，并引入了 Tcl 9 trace 兼容性修复，以及对 macOS 多桌面壁纸设置的修复 ˶>ᗜ<˶

**主要更新：**
- feat(build): 添加自动化打包脚本
- fix(tkinter): 修复 Tcl 9 trace 兼容性
- fix(macOS): 修复多桌面壁纸设置
- chore: 更新 .gitignore 忽略构建产物

**如何获取：**
请切换到仓库的 `【贡献版】v-1.3.0` 分支进行使用 ˶>ᗜ<˶

---

## 🚀 贡献版 3：【贡献版】原生-macOS-SwiftUI-客户端 + Python-CLI-参数解析

**作者：hjy-233**

这是一个基于 macOS 原生 SwiftUI 构建的客户端，配合 Python CLI 参数解析，提供了更优雅的 macOS 原生体验 ₍ᐢ˶• ˔ กᐢ₎

**主要更新：**
- feat(macOS): 添加原生 macOS SwiftUI 应用
- feat(macOS): 添加开机启动功能
- feat: 添加 Python 资源文件到 macOS 应用
- feat(build): 添加自动化打包脚本

**使用说明：**
1. 切换到该贡献分支
2. 运行 build 脚本打包为 macOS 应用
3. 享受原生 SwiftUI 界面带来的丝滑体验 •͈ᴗ⁃͈ ✧

---

## 📦 依赖安装

```bash
pip3 install pillow requests numpy pystray psutil
```

> **提示**：为获得最佳体验，建议安装所有依赖。ᶻz ₍^_   ̫ _^₎  
> **注意**：如果 `psutil` 未安装，仅跳过旧进程清理，不影响主功能。

---

## 🚀 快速开始

### Windows
1. 下载 Release 版本
2. 解压并运行 `main.exe`
3. 在桌面右键即可看到“上一个桌面背景”菜单

### macOS
1. 克隆仓库：`git clone https://github.com/xxdz-Official/ShangBackground.git`
2. 进入源码目录：`cd ShangBackground/src`
3. 运行 `python3 main.py`

---

## 👥 贡献者

感谢以下作者的贡献与支持 ദ്ദി˶ｰ̀֊ｰ́ )✧：

| 贡献者 | 贡献内容 |
|--------|----------|
| 小小电子xxdz | 原作者，Windows 原版 |
| @zjhcx | macOS 基础支持 |
| @hjy-233 | v-1.3.0 开发、SwiftUI 客户端开发 |
| @purrfecto114-lgtm | v-1.3.0 开发 |

---

## 📃 授权说明

本项目的源码采用 **GPL 许可证** 发布，欢迎自由使用与修改 ૮₍ ˊᯅˋ₎ა

**注意**：所有原版图片资源（位于 `img/` 目录）由 `小小电子xxdz` 制作，保留版权，不包含在 GPL 许可范围内

---

## 🔗 相关链接

- 作者官网：https://xxdz-official.github.io/x
- B站：小小电子xxdz
- GitHub 仓库：https://github.com/xxdz-Official/ShangBackground
```
