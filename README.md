<h1 align="center">
  <img src="https://xxdz-official.github.io/ShangBackground/img/LOGO.png" width="100" height="100" alt="Logo" style="display: inline-block; vertical-align: middle;">
  <br>
  上一个桌面背景 / ShangBackground
</h1>

<p align="center">
  <b>实现"上一个桌面背景"的右键菜单，拥有更多壁纸切换动画，可高度自定义！</b><br>
  <b>Bring back the "Previous Desktop Background" right-click menu with more wallpaper transition animations and high customizability!</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows-blue?style=flat-square&logo=windows">
  <img src="https://img.shields.io/badge/Platform-macOS-black?style=flat-square&logo=apple">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square">
  <img src="https://img.shields.io/badge/Python-3.x-yellow?style=flat-square&logo=python">
</p>

---

## 📖 简介 / Introduction

**上一个桌面背景** 是一款由 **B站UP主 [小小电子xxdz](https://space.bilibili.com/)** 开发的桌面壁纸管理工具。

**ShangBackground** is a desktop wallpaper management tool developed by **Bilibili UP主 [小小电子xxdz](https://space.bilibili.com/)**.

它恢复了 Windows 经典的"上一个桌面背景"右键菜单功能，并加入了丰富的壁纸切换动画与高度自定义选项。

It restores the classic Windows "Previous Desktop Background" right-click menu feature, enriched with a variety of wallpaper transition animations and highly customizable options.

---

## 🖥️ Windows 支持 / Windows Support

> **原版由 小小电子xxdz 开发 / Original version by 小小电子xxdz**

- ✅ 恢复"上一个桌面背景"右键菜单
- ✅ 多种壁纸切换动画
- ✅ 高度自定义配置
- ✅ 开机自启动支持
- ✅ 系统托盘驻留

- ✅ Restore "Previous Desktop Background" right-click menu
- ✅ Multiple wallpaper transition animations
- ✅ Highly customizable configuration
- ✅ Auto-start on boot
- ✅ System tray integration

---

## 🍎 macOS 支持 / macOS Support

> **感谢 [@zjhcx](https://github.com/zjhcx) 贡献 / Thanks to [@zjhcx](https://github.com/zjhcx) for the contribution**

现在可以在 macOS 上直接运行源码版：

Now you can run the source version directly on macOS:

```bash
cd "上一个桌面背景 - 源代码"
python3 main.py
```

### macOS 支持的能力 / macOS Capabilities

- 设置/读取当前桌面背景，使用系统 `osascript` 调用  
  Set/read current desktop background using system `osascript` calls
- 图片、纯色、渐变、幻灯片等主流程可运行  
  Main workflows supported: images, solid colors, gradients, slideshows
- 开机自启动使用 `~/Library/LaunchAgents/com.xxdz.shangbackground.plist`  
  Auto-start uses `~/Library/LaunchAgents/com.xxdz.shangbackground.plist`
- Windows 桌面右键菜单注册会在 macOS 上自动跳过，避免启动报错  
  Windows desktop right-click menu registration is automatically skipped on macOS to prevent startup errors

---

## 📦 依赖安装 / Dependencies

```bash
python3 -m pip install pillow requests numpy pystray psutil
```

> 💡 `psutil` 为可选依赖；未安装时仅跳过旧进程清理。  
> 💡 `psutil` is optional; if not installed, old process cleanup will be skipped.

---

## 🚀 快速开始 / Quick Start

### Windows

1. 下载并解压 release 版本  
   Download and extract the release version
2. 运行主程序  
   Run the main executable
3. 在桌面右键即可看到"上一个桌面背景"菜单  
   Right-click on the desktop to see the "Previous Desktop Background" menu

### macOS

1. 克隆仓库 / Clone the repository:
   ```bash
   git clone https://github.com/xxdz-official/ShangBackground.git
   ```
2. 进入源码目录并运行 / Enter source directory and run:
   ```bash
   cd "上一个桌面背景 - 源代码"
   python3 main.py
   ```

---

## 👥 贡献者 / Contributors

感谢所有为本项目做出贡献的开发者！

Thanks to all developers who have contributed to this project!

| 贡献者 / Contributor | 贡献内容 / Contribution |
|---|---|
| [小小电子xxdz](https://space.bilibili.com/) | 项目创始人、Windows 原版开发 / Project founder, original Windows version |
| [@zjhcx](https://github.com/zjhcx) | macOS 适配与移植 / macOS adaptation and porting |
| [@purrfecto114-lgtm](https://github.com/purrfecto114-lgtm) | Fork 维护与社区推广 / Fork maintenance and community promotion |

> 🤝 欢迎提交 Issue 和 Pull Request！  
> 🤝 Issues and Pull Requests are welcome!

---

## ⚠️ 授权说明 / License Notice

### 代码 / Source Code

本项目源代码采用 **[MIT 许可证](LICENSE)** 发布，可自由修改和分发。

The source code of this project is licensed under the **[MIT License](LICENSE)**, free to modify and distribute.

### 图像素材 / Image Assets

本项目 `/img/` 目录下的所有图像、Logo、图标等视觉素材由 **小小电子xxdz** 创作，**保留所有权利**，不包含在 MIT 许可证范围内。

All images, logos, icons and other visual assets in the `/img/` directory are created by **小小电子xxdz** and **all rights reserved**. They are **NOT** covered by the MIT License.

详见 [NOTICE](NOTICE) 文件了解完整版权声明。  
See the [NOTICE](NOTICE) file for the full copyright statement.

---

## 🔗 相关链接 / Links

- 🌐 作者官网 / Author Website: [xxdz-official.github.io](https://xxdz-official.github.io/)
- 📺 Bilibili: [小小电子xxdz](https://space.bilibili.com/)
- 💻 GitHub 仓库 / Repository: [xxdz-official/ShangBackground](https://github.com/xxdz-official/ShangBackground)
- 🍴 Fork 仓库 / Fork: [purrfecto114-lgtm/ShangBackground](https://github.com/purrfecto114-lgtm/ShangBackground)

---

<p align="center">
  Made with ❤️ by 小小电子xxdz and contributors.
</p>
