# DisplayShift

一键将三台显示器的输入源切换到 Mac 或 Windows。两台电脑都运行此应用。
Windows 标准协议使用系统 Dxva2，LG 专用协议使用 AMD 驱动的 ADL2；
Apple Silicon macOS 的 Release 应用内置已打补丁的 `m1ddc`。
全局快捷键默认 `Ctrl + Alt + Shift + D`：Windows 上切向 Mac，Mac 上切向 Windows。
程序必须保持运行；最小化后快捷键仍工作，关闭窗口即退出。

## 下载即用

在 [GitHub Releases](https://github.com/Skyrim-Wu/DisplayShift/releases/latest) 下载对应平台附件，
不要选择 GitHub 自动提供的 Source code 源码压缩包。

- Windows x64：解压 `DisplayShift-版本-Windows-x64.zip`，双击 `DisplayShift.exe`。
- Mac（M 系列，macOS 15+）：解压 `DisplayShift-版本-macOS-arm64.zip`，将应用拖到「应用程序」后打开。

两个版本都已包含 Python/Tk，Mac 还包含 m1ddc；用户无需安装开发工具。
首次运行默认启用全部三屏，LG 使用已验证的专用协议。已有配置不会被覆盖；
用过之前单屏配置的用户需在「逐屏设置」重新启用 ASUS / Alienware。
签名状态、快捷键权限和接线预设详见 [Release 使用说明](RELEASE-README.md)。

## 当前接线与验证状态

| 显示器 | Windows | Mac | 当前接线代码（Windows / Mac） |
| --- | --- | --- | --- |
| ASUS VG27AQ3A | HDMI 2 | USB-C 转 HDMI → HDMI 1 | `0x12` / `0x11` |
| Alienware AW2725QF | DP | Mac 原生 HDMI → HDMI 1 | `0x0f` / `0x11` |
| LG 27UP850N | DP | USB-C | 专用 `lg-alt`：`0xd0` / `0xd1`（双向实测） |

Mac 为 16 英寸 M5 Pro，无扩展坞。2026-09-27 在 Windows / AMD Radeon RX 5700
上完成只读实机检测，三台显示器均可读取 DDC：ASUS 返回当前输入 `0x12`，
LG 返回 `0x0f`，Alienware 返回原始值 `0x0f0f`（保留原值，不擅自截断）。
随后完成 LG 单屏双向实测，并由用户确认 Windows→Mac 三屏同时切换成功；
Mac→Windows 的 ASUS / Alienware 仍需单独验证。

LG 的标准能力列表包含 `0x11 / 0x12 / 0x0f / 0x10`，但本机实际使用上述专用协议，
不能把这些标准值混用于专用协议。LG 的能力字符串还自报 `WK95U`，所以身份匹配优先用 EDID
名称（本机为 `LG ULTRAFINE`）和保存的设备 ID，不使用该能力字符串型号。

## Windows 启动

打包后双击 `dist/DisplayShift/DisplayShift.exe`，无需安装 Python；移动时复制整个
`DisplayShift` 文件夹。源码运行需 Python 3.11+（包含 Tk）：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe displayshift.py
```

## Mac 启动

安装包含 Tk 的 Python 3.11+（例如 python.org 安装包）。使用同一份源码：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

按 [m1ddc 上游说明](https://github.com/waydabber/m1ddc) 安装当前版本。
需要 Apple Command Line Tools 的 `clang` 和 `make`。例如在本项目目录：

```bash
git clone https://github.com/waydabber/m1ddc.git .tools/m1ddc
git -C .tools/m1ddc checkout 04d949794102eb8df01ad3681afff6464a3eede2
git -C .tools/m1ddc apply ../../tools/m1ddc.patch
cp tools/displayshift_reply.h .tools/m1ddc/headers/
make -C .tools/m1ddc
.tools/m1ddc/m1ddc display list
.venv/bin/python displayshift.py
```

以上为源码开发步骤；Release 用户无需操作。源码运行时可在「逐屏设置」中填入
`.tools/m1ddc/m1ddc` 的**绝对路径**，或将可执行文件放入 PATH。
也会自动查找 `/opt/homebrew/bin/m1ddc` 和 `/usr/local/bin/m1ddc`。
macOS 全局快捷键可能需要为运行应用或终端授予辅助功能／输入监控权限。

本项目提供的 `tools/m1ddc.patch` 对上述固定版本修复：排除 Mac 内置屏幕，
校验 DDC 回复的头部、功能码和校验和，拒绝将空应答后的残留数据解释为输入代码，
并修正 16 位数值复制长度。已经应用过补丁时不要重复执行 `git apply`。
更新工具后，也需替换应用设置中 `m1ddc_path` 指向的可执行文件。

2026-09-27 Mac 只读检查：AW2725QF 的有效回复为 `0x1111`，应用对该型号的
`0x0f0f / 0x1111 / 0x1212` 映射为 DP / HDMI 1 / HDMI 2，并保留原值显示。
LG 和 ASUS 当时返回 DDC 空应答，不能用尾部的 `2809` 或 `0` 校准。
随后 LG 在用户确认显示 Mac USB-C 画面时返回 `0x0f`，与 Windows DP 读数相同。
该 LG（Mac 报告 vendor `0x1e6d` / model `0x5bcb`）回复的长度字节为 `0x51`，但校验和按
标准长度 `0x88` 生成；补丁仅对该型号兼容此格式，并继续验证功能码和校验和。
对应解析器位于 `tools/displayshift_reply.h`，测试使用实机捕获数据及损坏数据。
这些标准读取结果不能校准 LG 的 USB-C 输入；后续已通过专用协议实际切换确认
`0xd0` / `0xd1`，详见下文。

上游当前支持 USB-C / DP Alt Mode 以及部分原生 HDMI 通道，不能笼统说 Mac HDMI
全不支持；M5 Pro 原生 HDMI 与本条 USB-C 转 HDMI 线能否发送 DDC 仍需实测。
有画面和能控制显示器不是同一件事。

## 首次配置与 LG 校准

1. 在显示器菜单启用 DDC/CI，打开应用后点「重新检测」。检测只读，不切屏。
2. 「逐屏设置」中将每个配置绑定到对应的本机显示器。未绑定时仅允许唯一型号匹配；
   同型号多屏需手动绑定。Windows 和 Mac 的设备 ID 分开保存。
3. 本机 LG 已实测：**两台电脑**的 LG 协议均设为 `lg-alt`，Windows 输入 `0xd0`，
   Mac 输入 `0xd1`。其他型号需独立校准，不能用标准 DDC 读数替代 LG 专用代码。
   配置不会经网络自动同步。仅凭枚举到显示器不能确认输入控制可用。
4. 每次先只启用一块显示器测试，确认双向切换后再启用全部三块。
   目的电脑须已接好并有视频输出；若切到无信号画面，可用显示器实体菜单切回。

部分 LG 同系列需要专用地址 `0x50` / VCP `0xf4`，普通 VCP `0x60` 不一定有效。
本项目的 Mac 后端可选 `lg-alt`，使用 m1ddc 的 `input-alt`。
[ddcutil 维护者记录](https://github.com/rockowitz/ddcutil/wiki/Switching-input-source-on-LG-monitors)
中 27UP850-W / 27UP85NP-W 的专用 DP 值为 `0xd0`，USB-C 为 `0xd1`，
其 USB-C 值不能直接当作本机已验证映射。

2026-09-27 本机 27UP850N 实测：普通 `standard / 0x0f` 未切换；从 Mac 的
USB-C 通道发送 `lg-alt / 0xd0` 后，用户确认成功切到 Windows / DisplayPort。
切换后从 Mac 发送 `lg-alt / 0xd1`，用户确认仍停留在 Windows，读取也变为
DDC 空应答。这可能是非当前输入通道无法控制，尚不能区分通道限制与回切代码问题。
当时的 Mac 配置将 LG 的 Windows 输入改为 `lg-alt / 0xd0`，Mac 输入保留空值。
后续从当前活动的 Windows DP 通道完成了回切实测，见下文。

Windows 已接入 AMD ADL2 的 `DDCBlockAccess`，`lg-alt` 会发送完整的 LG 专用
DDC 数据包（目标 `0x6e`、源 `0x50`、功能 `0xf4`）。`0x50` 是消息内的源地址，
不是向 EDID EEPROM 写入。无需额外下载 DLL，直接加载系统 AMD 驱动。
协议依据 [AMD 官方 ADL 文档](https://gpuopen-librariesandsdks.github.io/adl/group__I2CDDCEDIDAPI.html)
和 [amdddc-windows 的协议实现](https://github.com/amildahl/amdddc-windows)。
不能只把 `0xd1` 填进 standard 协议；协议、源地址和代码必须对应。

驱动输出通过 Windows 设备 ID 精确绑定；不会根据显示器顺序或重名猜测。
复制/MST 模式若无法唯一对应则拒绝写入。该专用后端目前仅支持 AMD，
NVIDIA / Intel 仍使用标准协议，不能通过本后端发送 LG 专用指令。

2026-09-27 Windows / RX 5700 实机：ADL 只读枚举识别 LG 为 adapter 1 / display 4，
与 `GSM5BC2` 的 Windows 设备 ID 一致。随后单独向 LG 发送
`lg-alt / 0xd1`（数据包 `6e 50 84 03 f4 00 d1 9c`），驱动返回成功，
但用户确认单次发送未切换。随后按 Mac 工具的方式间隔 50 ms 发送两次，
LG 的 Windows DDC 应答由有效输入 `0x0f` 变为 `6e 80 be` 空应答；
用户随后确认 LG 已显示 Mac，且 Mac 已唤醒，至此 LG 单屏两个方向均实测成功。
未单独控制 Mac 唤醒状态，不能断言首次失败仅由发送次数导致。
后端已采用两次发送；首次成功后若第二次因断连失败，仍仅报告「指令已发送」。
每次运行都会重新枚举，不保存这些临时索引。

当前机器的配置保存在 `config.windows-lg.json`（沿用测试文件名，已忽略，不提交设备 ID），
现已恢复启用全部三屏；LG 的 Mac 为 `lg-alt / 0xd1`，Windows 为 `lg-alt / 0xd0`。
Release 默认配置同样启用三屏，按上表接线。双击 `Start-DisplayShift.cmd` 打开本地新版，
再点「切换到 Mac」或按 `Ctrl + Alt + Shift + D`。
先关闭旧版 DisplayShift，避免两份程序同时响应快捷键。
本地最新打包位于 `dist/DisplayShift/DisplayShift.exe`；
开发启动脚本会传入上述配置。Release 包可直接打开 EXE，不需要此脚本或本地配置文件。
切换前确保 Mac 已唤醒；本程序发送显示器输入指令，不负责唤醒 Mac。

源码三屏命令：

```powershell
.venv\Scripts\python.exe displayshift.py --config config.windows-lg.json --switch mac --dry-run
.venv\Scripts\python.exe displayshift.py --config config.windows-lg.json --switch mac
```

LG 的 Mac 输入为空时，一键切向 Mac 会报告 LG 未完成，仍继续处理 ASUS / Alienware。
一次写入失败不会中止其他屏幕。命令发送成功只表示驱动接受，界面不会宣称画面已确认切换。

## 配置、诊断与打包

在「逐屏设置」保存时原子写入 `~/.displayshift/config.json`，不在检测时自动写入。
旧原型的全局输入值格式会明确报错，保留原文件；将其重命名备份后重新配置即可。
支持 `--config path/to/config.json` 使用另一个配置文件。

```bash
python displayshift.py --diagnose
python displayshift.py --switch mac --dry-run
python displayshift.py --switch windows --dry-run
# 下面命令会实际发送输入源切换指令：
python displayshift.py --switch mac
```

诊断输出含显示器设备标识，不自动上传。软件没有网络服务，不切换键盘鼠标，不启动或唤醒对方电脑。
`--dry-run` 只枚举并输出计划，未校准／缺失／重复绑定会报告失败。

在各自平台打包（Windows 上不能生成可验证的 Mac .app）：

```bash
python -m pip install -r requirements-build.txt
python tools/build.py
```

Mac 构建会自动嵌入 `.tools/m1ddc/m1ddc`，也可用 `--m1ddc /absolute/path/m1ddc`
指定已打补丁的工具（旁边必须有上游 LICENSE）。仅生成 Apple Silicon 应用，
采用临时签名，未做 Developer ID 签名和公证。Windows 输出目录包含所有运行时文件。

仓库的 `.github/workflows/release.yml` 会在 `v*` 标签推送后，分别在 Windows 和
Mac runner 上执行测试、构建、应用自检，然后同时上传两平台 ZIP 与 SHA-256 到 Release。
任一平台失败都不会发布。维护者创建新版本时，提交代码后运行：

```bash
git tag v0.1.0
git push origin main v0.1.0
```

## 开发验证

```bash
python -m unittest discover -s tests -v
python tests/smoke_ui.py
```

测试覆盖 AMD 数据包/校验和、设备 ID 绑定、歧义拒绝、驱动错误传播、资源释放，
以及逐屏映射、拔插导致的顺序变化、部分失败继续、重复绑定、快捷键方向、
配置损坏保护、Mac 命令超时／参数、Tk 设置和忙碌状态。测试不发送真实切换指令。
