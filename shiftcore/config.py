from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path

CONFIG_PATH = Path.home() / '.displayshift' / 'config.json'

# Input codes are per display, never a shared global value.
DEFAULT_CONFIG = {
    'version': 2,
    'shortcut': 'ctrl+alt+shift+d',
    'm1ddc_path': '',
    'displays': [
        {'name': 'ASUS VG27AQ3A', 'match': ['VG27AQ3A'], 'enabled': True,
         'ids': {}, 'protocol': 'standard', 'mac_input': '0x11', 'windows_input': '0x12',
         'mac_port': 'HDMI 1 · USB-C 转 HDMI', 'windows_port': 'HDMI 2'},
        {'name': 'Alienware AW2725QF', 'match': ['AW2725QF'], 'enabled': True,
         'ids': {}, 'protocol': 'standard', 'mac_input': '0x11', 'windows_input': '0x0f',
         'mac_port': 'HDMI 1 · Mac 原生 HDMI', 'windows_port': 'DisplayPort'},
        {'name': 'LG 27UP850N', 'match': ['27UP850', 'LG ULTRAFINE'], 'enabled': True,
         'ids': {}, 'protocol': 'standard', 'mac_input': '', 'windows_input': '0x0f',
         'mac_port': 'USB-C · 输入代码待校准', 'windows_port': 'DisplayPort'},
    ],
}


def input_value(value: str) -> int:
    """Accept decimal or explicitly prefixed hex, and reject accidental wide values."""
    try:
        value = value.strip()
        number = int(value, 16 if value.lower().startswith('0x') else 10)
    except (ValueError, AttributeError) as exc:
        raise ValueError('输入代码必须是十进制或 0x 开头的十六进制数') from exc
    if not 1 <= number <= 255:
        raise ValueError('输入代码必须在 1–255 之间')
    return number


def shortcut_spec(value: str) -> str:
    parts = value.lower().strip().split('+')
    modifiers = {'ctrl', 'alt', 'shift', 'cmd'}
    if (len(parts) < 2 or len(set(parts)) != len(parts)
            or any(p not in modifiers for p in parts[:-1])
            or len(parts[-1]) != 1 or not parts[-1].isascii() or not parts[-1].isalnum()):
        raise ValueError('快捷键格式示例：ctrl+alt+shift+d；Mac 也可用 cmd')
    return '+'.join(f'<{p}>' for p in parts[:-1]) + '+' + parts[-1]


def other_host(system: str) -> str:
    if system not in ('Windows', 'Darwin'):
        raise RuntimeError('目前支持 Windows 和 Apple Silicon macOS')
    return 'windows' if system == 'Darwin' else 'mac'


def validate(config: dict) -> None:
    if not isinstance(config, dict) or config.get('version') != 2:
        raise ValueError('配置格式不支持；请保留原文件并重新配置')
    shortcut_spec(config.get('shortcut', ''))
    if not isinstance(config.get('m1ddc_path'), str):
        raise ValueError('m1ddc_path 必须是路径字符串')
    displays = config.get('displays')
    if not isinstance(displays, list) or not displays:
        raise ValueError('配置中必须包含显示器')
    names = set()
    bound = set()
    for display in displays:
        if not isinstance(display, dict):
            raise ValueError('显示器配置格式错误')
        name = display.get('name')
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError('显示器名称不能为空或重复')
        names.add(name)
        if display.get('protocol') not in ('standard', 'lg-alt'):
            raise ValueError(f'{name}：未知控制协议')
        if not isinstance(display.get('enabled'), bool):
            raise ValueError(f'{name}：enabled 必须为布尔值')
        if not isinstance(display.get('match'), list) or not all(
                isinstance(alias, str) and alias.strip() for alias in display['match']):
            raise ValueError(f'{name}：match 必须为名称列表')
        if not isinstance(display.get('ids'), dict):
            raise ValueError(f'{name}：ids 格式错误')
        for system, identifier in display['ids'].items():
            if system not in ('Windows', 'Darwin') or not isinstance(identifier, str):
                raise ValueError(f'{name}：显示器绑定无效')
            if identifier and display['enabled']:
                pair = (system, identifier)
                if pair in bound:
                    raise ValueError('不能将同一显示器绑定到两个配置')
                bound.add(pair)
        for host in ('mac', 'windows'):
            value = display.get(f'{host}_input')
            if not isinstance(value, str):
                raise ValueError(f'{name}：输入代码格式错误')
            if value.strip():
                input_value(value)


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    config = json.loads(path.read_text(encoding='utf-8'))
    # The prototype applied a single code to every monitor. Do not silently migrate it.
    validate(config)
    return config


def save_config(config: dict, path: Path = CONFIG_PATH) -> None:
    validate(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='config-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(config, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
