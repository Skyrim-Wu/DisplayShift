from __future__ import annotations

import platform
import re
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

from .engine import Display


class MacBackend:
    def __init__(self, executable=''):
        self.executable = executable or shutil.which('m1ddc') or next(
            (p for p in ('/opt/homebrew/bin/m1ddc', '/usr/local/bin/m1ddc') if Path(p).is_file()), '')

    def command(self, *args):
        if not self.executable:
            raise RuntimeError('未找到 m1ddc；按 README 安装后，在设置中指定路径')
        try:
            result = subprocess.run([self.executable, *args], capture_output=True,
                                    text=True, encoding='utf-8', timeout=12, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('m1ddc 超时；请检查当前接口的 DDC 支持') from exc
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout).strip() or f'm1ddc 返回 {result.returncode}')
        return result.stdout.strip()

    @staticmethod
    def parse_displays(output):
        displays = []
        for line in output.splitlines():
            match = re.fullmatch(r'\[(\d+)\]\s+(.+)\s+\(([0-9a-fA-F-]{36})\)', line.strip())
            if match:
                displays.append(Display(match[3], match[2].strip()))
        if not displays:
            raise RuntimeError('m1ddc 未返回可识别的显示器；运行 m1ddc display list 检查')
        return displays

    @contextmanager
    def session(self):
        yield self.parse_displays(self.command('display', 'list'))

    def probe(self, display):
        try:
            value = self.command('display', display.identifier, 'get', 'input')
            if not value.isdecimal() or not 0 < int(value) <= 255:
                raise ValueError('显示器未返回有效的输入源代码')
            display.current_input = int(value)
            display.detail = f'当前输入 {int(value):#04x}'
        except Exception as exc:
            display.detail = f'输入读取失败：{exc}'

    @staticmethod
    def check_protocol(protocol):
        if protocol not in ('standard', 'lg-alt'):
            raise ValueError('不支持的控制协议')

    def write(self, display, value, protocol):
        self.check_protocol(protocol)
        self.command('display', display.identifier, 'set',
                     'input-alt' if protocol == 'lg-alt' else 'input', str(value))


def create_backend(config):
    system = platform.system()
    if system == 'Darwin':
        return MacBackend(config['m1ddc_path'])
    if system == 'Windows':
        from .windows import WindowsBackend
        return WindowsBackend()
    raise RuntimeError('目前支持 Windows 和 Apple Silicon macOS')


def scan(backend):
    with backend.session() as displays:
        for display in displays:
            backend.probe(display)
        # Do not leak expired native handles to callers.
        return [Display(d.identifier, d.name, d.current_input, d.detail) for d in displays]
