# DisplayShift

下载后即可运行，无需安装 Python、Homebrew 或 m1ddc。

- **Windows x64**：完整解压，双击文件夹中的 `DisplayShift.exe`。
  保留同目录 `_internal`；不要只复制 EXE。LG 专用协议需要 AMD 显卡驱动。
- **Mac / Apple Silicon**：解压，将 `DisplayShift.app` 拖到「应用程序」后打开。
  已内置修复过的 m1ddc。支持 macOS 15+ 的 M 系列 Mac，不支持 Intel Mac。

首次使用默认启用三台显示器，按当前接线预设：

| 显示器 | Windows | Mac | 协议 |
| --- | --- | --- | --- |
| ASUS VG27AQ3A | HDMI 2 / 0x12 | HDMI 1 / 0x11 | standard |
| Alienware AW2725QF | DP / 0x0f | HDMI 1 / 0x11 | standard |
| LG 27UP850N | DP / 0xd0 | USB-C / 0xd1 | lg-alt |

LG 已完成本机双向实测，Windows→Mac 三屏同时切换也已由用户确认。
Mac→Windows 的 ASUS / Alienware 尚未确认。其他型号、接线需要在「逐屏设置」中调整。
已有配置会保留；如果之前用过 LG 单屏测试配置，需要重新启用 ASUS 和 Alienware。

两台电脑都打开应用，点击目标电脑按钮；也可按 `Ctrl + Alt + Shift + D`，
自动切到另一台电脑。程序需要保持运行，关闭窗口即退出。
快捷键在 Mac 上可能需要授予 DisplayShift 辅助功能/输入监控权限。
切换前确保目标电脑已唤醒。程序不负责唤醒电脑或切换键盘鼠标。

首版未做开发者签名/Apple 公证。系统首次打开可能提示未知发布者。
确认来自本仓库 Release 后，可按系统界面允许运行；Mac 可在
「系统设置 → 隐私与安全性」选择「仍要打开」。不需要关闭系统安全保护。

配置保存在用户目录 `~/.displayshift/config.json`，更新应用不会覆盖。
命令发送成功不等于画面已验证，显示器无信号时可用实体菜单切回。
