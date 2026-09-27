from __future__ import annotations

import argparse
import copy
import json
import platform
import queue
import threading
from dataclasses import asdict
from pathlib import Path

from shiftcore.backends import create_backend, scan
from shiftcore.config import CONFIG_PATH, load_config, save_config, shortcut_spec, other_host, validate
from shiftcore.engine import resolve, switch_all


class DisplayShift:
    def __init__(self, config=None, backend=None, config_path=CONFIG_PATH, start_services=True):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk
        self.config_path = config_path
        self.config = config if config is not None else load_config(config_path)
        self.system = platform.system()
        self.backend = backend or create_backend(self.config)
        self.events = queue.Queue()
        self.displays = []
        self.busy = False
        self.listener = None
        self.dialog = None
        self.root = tk.Tk()
        self.root.title('DisplayShift')
        self.root.geometry('850x630')
        self.root.minsize(740, 540)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.build_ui()
        self.poll_id = self.root.after(80, self.consume_events)
        if start_services:
            self.install_shortcut()
            self.refresh_monitors()

    def build_ui(self):
        tk, ttk = self.tk, self.ttk
        shell = ttk.Frame(self.root, padding=24)
        shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='DisplayShift', font=('TkDefaultFont', 24, 'bold')).pack(anchor='w')
        ttk.Label(shell, text='一键将共享显示器切换到另一台电脑', padding=(0, 6, 0, 20)).pack(anchor='w')
        actions = ttk.Frame(shell)
        actions.pack(fill='x')
        self.mac_button = ttk.Button(actions, text='切换到 Mac', padding=14, command=lambda: self.switch('mac'))
        self.windows_button = ttk.Button(actions, text='切换到 Windows', padding=14, command=lambda: self.switch('windows'))
        self.mac_button.pack(side='left', fill='x', expand=True, padx=(0, 8))
        self.windows_button.pack(side='left', fill='x', expand=True)
        self.status = tk.StringVar(value='点击「重新检测」读取显示器；检测不会改变输入源。')
        ttk.Label(shell, textvariable=self.status, wraplength=760, padding=(0, 18, 0, 10)).pack(anchor='w')
        self.table = ttk.Treeview(shell, columns=('windows', 'mac', 'status'), show='tree headings', height=5)
        self.table.heading('#0', text='显示器')
        self.table.heading('windows', text='Windows')
        self.table.heading('mac', text='Mac')
        self.table.heading('status', text='状态')
        self.table.column('#0', width=185, minwidth=155)
        for name in ('windows', 'mac', 'status'):
            self.table.column(name, width=160, minwidth=110)
        self.table.pack(fill='x')
        for index, profile in enumerate(self.config['displays']):
            self.table.insert('', 'end', iid=str(index), text=profile['name'], values=(
                profile.get('windows_port', profile['windows_input']),
                profile.get('mac_port', profile['mac_input']), '尚未检测'))
        ttk.Label(shell, text='检测与切换记录', padding=(0, 14, 0, 4)).pack(anchor='w')
        log_frame = ttk.Frame(shell)
        log_frame.pack(fill='both', expand=True)
        self.log = tk.Text(log_frame, height=6, wrap='word', state='disabled', font='TkFixedFont')
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.log.pack(side='left', fill='both', expand=True)
        footer = ttk.Frame(shell, padding=(0, 12, 0, 0))
        footer.pack(fill='x')
        self.shortcut_status = tk.StringVar(value='快捷键尚未启动')
        ttk.Label(footer, textvariable=self.shortcut_status, wraplength=430).pack(side='left')
        self.settings_button = ttk.Button(footer, text='逐屏设置', command=self.settings)
        self.settings_button.pack(side='right', padx=(8, 0))
        self.refresh_button = ttk.Button(footer, text='重新检测', command=self.refresh_monitors)
        self.refresh_button.pack(side='right')

    def append_log(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def set_busy(self, value):
        self.busy = value
        for button in (self.mac_button, self.windows_button, self.settings_button, self.refresh_button):
            button.configure(state='disabled' if value else 'normal')

    def job(self, kind, operation):
        if self.busy or self.dialog is not None:
            return False
        self.set_busy(True)
        def work():
            try:
                self.events.put((kind, operation()))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=work, daemon=True).start()
        return True

    def refresh_monitors(self):
        if self.job('scan', lambda: scan(self.backend)):
            self.status.set('正在读取显示器信息…')

    def switch(self, target):
        config = copy.deepcopy(self.config)
        if self.job('switch', lambda: switch_all(config, self.backend, self.system, target)):
            self.status.set(f'正在向显示器发送切换到 {"Mac" if target == "mac" else "Windows"} 的指令…')

    def consume_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == 'hotkey':
                    self.switch(other_host(self.system))
                    continue
                if kind == 'shortcut-error':
                    self.shortcut_status.set(payload)
                    continue
                self.set_busy(False)
                if kind == 'scan':
                    self.displays = payload
                    self.status.set(f'检测到 {len(payload)} 块显示器。' if payload else '未检测到物理显示器；检查连接及本机桌面会话。')
                    for index, profile in enumerate(self.config['displays']):
                        try:
                            display = resolve(profile, payload, self.system)
                            state = display.detail.split('\n')[0]
                        except ValueError as exc:
                            state = str(exc)
                        if not profile['enabled']:
                            state = '已停用'
                        self.table.set(str(index), 'status', state)
                    for display in payload:
                        self.append_log(f'{display.name}\n{display.detail}')
                elif kind == 'switch':
                    sent = sum(r.status == 'sent' for r in payload)
                    failed = sum(r.status == 'failed' for r in payload)
                    self.status.set(f'已发送 {sent} 屏，未完成 {failed} 屏。请以实际画面为准。' if payload else '没有启用的显示器。')
                    for result in payload:
                        self.append_log(f'{result.name}：{result.detail}')
                        for index, profile in enumerate(self.config['displays']):
                            if result.name == profile['name']:
                                self.table.set(str(index), 'status', '已发送，待确认画面' if result.status == 'sent' else '未完成，查看记录')
                elif kind == 'error':
                    self.status.set('操作未完成，请查看下方记录。')
                    self.append_log(payload)
        except queue.Empty:
            pass
        self.poll_id = self.root.after(80, self.consume_events)

    def install_shortcut(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
        try:
            from pynput import keyboard
            if self.system == 'Darwin':
                import HIServices
                if not HIServices.AXIsProcessTrusted():
                    raise RuntimeError('请在系统设置中授予辅助功能／输入监控权限')
            self.listener = keyboard.GlobalHotKeys({shortcut_spec(self.config['shortcut']):
                                                   lambda: self.events.put(('hotkey', None))})
            self.listener.start()
            listener = self.listener
            def watch():
                try:
                    listener.join()
                    if self.listener is listener and listener.running:
                        self.events.put(('shortcut-error', '快捷键监听已停止；请检查系统输入监控权限'))
                except Exception as exc:
                    self.events.put(('shortcut-error', f'快捷键已停止：{exc}'))
            threading.Thread(target=watch, daemon=True).start()
            self.shortcut_status.set(f'{self.config["shortcut"]} → {"Windows" if self.system == "Darwin" else "Mac"}')
        except Exception as exc:
            self.shortcut_status.set(f'快捷键不可用；仍可使用按钮。{exc}')

    def settings(self):
        if self.busy or self.dialog is not None:
            return
        tk, ttk = self.tk, self.ttk
        dialog = self.dialog = tk.Toplevel(self.root)
        dialog.title('DisplayShift · 逐屏设置')
        dialog.transient(self.root)
        dialog.minsize(720, 500)
        body = ttk.Frame(dialog, padding=20)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='按本机检测到的显示器绑定。输入代码可填十进制或 0x 开头的十六进制。', wraplength=700).pack(anchor='w')
        ttk.Label(body, text='LG USB-C 先在 Mac 检测当前输入再填写；LG 专用协议在 Windows 上尚未接入。', wraplength=700, padding=(0, 4, 0, 14)).pack(anchor='w')
        choices = ['自动匹配型号'] + [f'{d.name} [{d.identifier}]' for d in self.displays]
        rows = []
        notebook = ttk.Notebook(body)
        notebook.pack(fill='both', expand=True)
        for profile in self.config['displays']:
            frame = ttk.Frame(notebook, padding=16)
            notebook.add(frame, text=profile['name'])
            enabled = tk.BooleanVar(value=profile['enabled'])
            ttk.Checkbutton(frame, text='参与一键切换', variable=enabled).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 12))
            selected_id = profile['ids'].get(self.system, '')
            selected = next((i + 1 for i, d in enumerate(self.displays) if d.identifier == selected_id), 0)
            local_choices = choices.copy()
            if selected_id and not selected:
                local_choices.append(f'已保存（当前未连接）[{selected_id}]')
                selected = len(local_choices) - 1
            ttk.Label(frame, text='本机显示器').grid(row=1, column=0, sticky='w', padx=(0, 12), pady=6)
            binding = ttk.Combobox(frame, values=local_choices, state='readonly', width=60)
            binding.current(selected)
            binding.grid(row=1, column=1, sticky='ew', pady=6)
            fields = {}
            for row, (key, label) in enumerate((('windows_input', 'Windows 输入代码'), ('mac_input', 'Mac 输入代码')), 2):
                ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', pady=6)
                variable = tk.StringVar(value=profile[key])
                fields[key] = variable
                ttk.Entry(frame, textvariable=variable).grid(row=row, column=1, sticky='ew', pady=6)
            protocol = tk.StringVar(value=profile['protocol'])
            ttk.Label(frame, text='控制协议').grid(row=4, column=0, sticky='w', pady=6)
            ttk.Combobox(frame, textvariable=protocol, values=['standard', 'lg-alt'], state='readonly').grid(row=4, column=1, sticky='ew', pady=6)
            ttk.Label(frame, text='standard：HDMI 1=0x11，HDMI 2=0x12，DP=0x0f。\nlg-alt 使用另一套代码，切换协议后请同步修改两台电脑的输入代码。', wraplength=600).grid(row=5, column=0, columnspan=2, sticky='w', pady=12)
            frame.columnconfigure(1, weight=1)
            rows.append((enabled, binding, fields, protocol, selected_id))
        general = ttk.Frame(body, padding=(0, 12, 0, 0))
        general.pack(fill='x')
        shortcut = tk.StringVar(value=self.config['shortcut'])
        helper = tk.StringVar(value=self.config['m1ddc_path'])
        for row, (label, variable) in enumerate((('全局快捷键', shortcut), ('Mac 的 m1ddc 路径（可留空自动查找）', helper))):
            ttk.Label(general, text=label).grid(row=row, column=0, sticky='w', pady=5, padx=(0, 12))
            ttk.Entry(general, textvariable=variable).grid(row=row, column=1, sticky='ew', pady=5)
        general.columnconfigure(1, weight=1)
        error = tk.StringVar()
        ttk.Label(body, textvariable=error, wraplength=680).pack(anchor='w', pady=8)
        def close():
            dialog.grab_release()
            dialog.destroy()
            self.dialog = None
            self.settings_button.focus_set()
        def save():
            candidate = copy.deepcopy(self.config)
            try:
                for profile, (enabled, binding, fields, protocol, old_id) in zip(candidate['displays'], rows):
                    profile['enabled'] = enabled.get()
                    profile['protocol'] = protocol.get()
                    profile.update({key: var.get().strip() for key, var in fields.items()})
                    choice = binding.current()
                    profile['ids'][self.system] = '' if choice == 0 else (
                        self.displays[choice - 1].identifier if choice <= len(self.displays) else old_id)
                candidate['shortcut'] = shortcut.get().strip()
                candidate['m1ddc_path'] = helper.get().strip()
                validate(candidate)
                save_config(candidate, self.config_path)
            except (ValueError, OSError) as exc:
                error.set(str(exc))
                return
            self.config = candidate
            self.backend = create_backend(candidate)
            self.install_shortcut()
            close()
            self.refresh_monitors()
        bar = ttk.Frame(body)
        bar.pack(fill='x')
        ttk.Button(bar, text='保存并应用', command=save).pack(side='right')
        ttk.Button(bar, text='取消', command=close).pack(side='right', padx=8)
        dialog.protocol('WM_DELETE_WINDOW', close)
        dialog.bind('<Escape>', lambda event: close())
        dialog.grab_set()
        dialog.focus_set()

    def close(self):
        if self.listener:
            self.listener.stop()
        self.root.after_cancel(self.poll_id)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main(argv=None):
    parser = argparse.ArgumentParser(description='DisplayShift · 三屏输入源切换')
    parser.add_argument('--config', type=Path, default=CONFIG_PATH)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--diagnose', action='store_true', help='只读检测并输出 JSON')
    action.add_argument('--switch', choices=['mac', 'windows'])
    action.add_argument('--self-check', action='store_true', help='验证打包运行库；不读取或切换显示器')
    parser.add_argument('--dry-run', action='store_true', help='与 --switch 一起使用，仅显示计划')
    args = parser.parse_args(argv)
    if args.dry_run and not args.switch:
        parser.error('--dry-run 需要 --switch')
    try:
        if args.self_check:
            import tkinter
            from pynput import keyboard
            keyboard.HotKey.parse(shortcut_spec('ctrl+alt+shift+d'))
            root = tkinter.Tk()
            root.withdraw()
            root.update_idletasks()
            root.destroy()
            return 0
        config = load_config(args.config)
        backend = create_backend(config)
        if args.diagnose:
            print(json.dumps({'system': platform.system(), 'displays': [asdict(d) for d in scan(backend)]}, ensure_ascii=True, indent=2))
        elif args.switch:
            results = switch_all(config, backend, platform.system(), args.switch, args.dry_run)
            print(json.dumps([asdict(r) for r in results], ensure_ascii=True, indent=2))
            return 1 if not results or any(r.status == 'failed' for r in results) else 0
        else:
            DisplayShift(config, backend, args.config).run()
        return 0
    except Exception as exc:
        if args.diagnose or args.switch or args.self_check:
            print(json.dumps({'error': str(exc)}, ensure_ascii=True))
        else:
            from tkinter import Tk, messagebox
            root = Tk()
            root.withdraw()
            messagebox.showerror('DisplayShift 无法启动', f'{exc}\n\n配置路径：{args.config}', parent=root)
            root.destroy()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
