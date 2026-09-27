from __future__ import annotations

from dataclasses import dataclass

from .config import input_value, validate


@dataclass
class Display:
    identifier: str
    name: str
    current_input: int | None = None
    detail: str = ''
    handle: object = None


@dataclass
class Result:
    name: str
    status: str
    detail: str


def resolve(profile: dict, displays: list[Display], system: str) -> Display:
    identifier = profile['ids'].get(system)
    if identifier:
        matches = [d for d in displays if d.identifier == identifier]
    else:
        matches = [d for d in displays if any(
            alias.casefold() in d.name.casefold() for alias in profile['match'])]
    if len(matches) != 1:
        raise ValueError('未找到显示器，请重新检测或绑定' if not matches else '有多个匹配，请在设置中绑定唯一显示器')
    return matches[0]


def switch_all(config: dict, backend, system: str, target: str, dry_run=False) -> list[Result]:
    validate(config)
    if target not in ('mac', 'windows'):
        raise ValueError('未知目标电脑')
    results = []
    # Acquire and resolve ALL targets before any write changes the display topology.
    with backend.session() as displays:
        planned = []
        for profile in config['displays']:
            if not profile['enabled']:
                continue
            try:
                display = resolve(profile, displays, system)
                code = profile[f'{target}_input']
                if not code.strip():
                    raise ValueError(f'{target} 输入代码待校准；本屏未发送切换指令')
                value = input_value(code)
                backend.check_protocol(profile['protocol'])
                planned.append((profile, display, value))
            except Exception as exc:
                results.append(Result(profile['name'], 'failed', str(exc)))
        identifiers = [display.identifier for _, display, _ in planned]
        for profile, display, value in planned:
            try:
                if identifiers.count(display.identifier) > 1:
                    raise ValueError('多个配置指向同一显示器，请重新绑定')
                if dry_run:
                    results.append(Result(profile['name'], 'planned', f'{display.name} → {value:#04x} ({profile["protocol"]})'))
                    continue
                backend.write(display, value, profile['protocol'])
                # Writing can disconnect our host. An accepted command is not proof of a visible switch.
                results.append(Result(profile['name'], 'sent', '切换指令已发送，请以显示器画面为准'))
            except Exception as exc:
                results.append(Result(profile['name'], 'failed', str(exc)))
    return results
