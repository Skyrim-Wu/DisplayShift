"""Windows Dxva2 DDC backend. Native handles live for exactly one session."""
from __future__ import annotations

import ctypes as c
from ctypes import wintypes as w
from contextlib import contextmanager

from .engine import Display


class MonitorInfo(c.Structure):
    _fields_ = [('size', w.DWORD), ('monitor', w.RECT), ('work', w.RECT),
                ('flags', w.DWORD), ('device', w.WCHAR * 32)]


class DeviceInfo(c.Structure):
    _fields_ = [('size', w.DWORD), ('name', w.WCHAR * 32), ('description', w.WCHAR * 128),
                ('flags', w.DWORD), ('identifier', w.WCHAR * 128), ('key', w.WCHAR * 128)]


class PhysicalMonitor(c.Structure):
    _fields_ = [('handle', w.HANDLE), ('description', w.WCHAR * 128)]


def edid_name(identifier):
    import winreg
    # EDD_GET_DEVICE_INTERFACE_NAME returns \\?\DISPLAY#MODEL#INSTANCE#{GUID}.
    parts = identifier.split('#')
    if len(parts) < 3:
        return ''
    try:
        key_path = 'SYSTEM\\CurrentControlSet\\Enum\\DISPLAY\\' + parts[1] + '\\' + parts[2] + '\\Device Parameters'
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            data = winreg.QueryValueEx(key, 'EDID')[0]
        for start in (54, 72, 90, 108):
            if data[start:start + 5] == b'\x00\x00\x00\xfc\x00':
                return data[start + 5:start + 18].decode('ascii', errors='replace').strip(' \n\x00')
    except OSError:
        pass
    return ''


class WindowsBackend:
    def __init__(self):
        self.user = c.WinDLL('user32', use_last_error=True)
        self.dx = c.WinDLL('dxva2', use_last_error=True)
        self.callback_type = c.WINFUNCTYPE(w.BOOL, w.HANDLE, w.HDC, c.POINTER(w.RECT), w.LPARAM)
        signatures = [
            (self.user.EnumDisplayMonitors, [w.HDC, c.POINTER(w.RECT), self.callback_type, w.LPARAM]),
            (self.user.GetMonitorInfoW, [w.HANDLE, c.POINTER(MonitorInfo)]),
            (self.user.EnumDisplayDevicesW, [w.LPCWSTR, w.DWORD, c.POINTER(DeviceInfo), w.DWORD]),
            (self.dx.GetNumberOfPhysicalMonitorsFromHMONITOR, [w.HANDLE, c.POINTER(w.DWORD)]),
            (self.dx.GetPhysicalMonitorsFromHMONITOR, [w.HANDLE, w.DWORD, c.POINTER(PhysicalMonitor)]),
            (self.dx.DestroyPhysicalMonitors, [w.DWORD, c.POINTER(PhysicalMonitor)]),
            (self.dx.GetVCPFeatureAndVCPFeatureReply, [w.HANDLE, w.BYTE, c.POINTER(c.c_int), c.POINTER(w.DWORD), c.POINTER(w.DWORD)]),
            (self.dx.SetVCPFeature, [w.HANDLE, w.BYTE, w.DWORD]),
            (self.dx.GetCapabilitiesStringLength, [w.HANDLE, c.POINTER(w.DWORD)]),
            (self.dx.CapabilitiesRequestAndCapabilitiesReply, [w.HANDLE, c.c_void_p, w.DWORD]),
        ]
        for function, arguments in signatures:
            function.argtypes = arguments
            function.restype = w.BOOL

    @contextmanager
    def session(self):
        logical = []
        callback = self.callback_type(lambda handle, dc, rect, data: logical.append(handle) or 1)
        if not self.user.EnumDisplayMonitors(None, None, callback, 0):
            raise c.WinError(c.get_last_error())
        displays, allocated = [], []
        try:
            for handle in logical:
                info = MonitorInfo()
                info.size = c.sizeof(info)
                if not self.user.GetMonitorInfoW(handle, c.byref(info)):
                    continue
                count = w.DWORD()
                if not self.dx.GetNumberOfPhysicalMonitorsFromHMONITOR(handle, c.byref(count)) or not count.value:
                    continue
                physical = (PhysicalMonitor * count.value)()
                if not self.dx.GetPhysicalMonitorsFromHMONITOR(handle, count, physical):
                    continue
                allocated.append((count, physical))
                # Clone/MST ordering is not a safe identity mapping. Require an unambiguous device.
                if count.value != 1:
                    continue
                device = DeviceInfo()
                device.size = c.sizeof(device)
                if not self.user.EnumDisplayDevicesW(info.device, 0, c.byref(device), 1):
                    continue
                identifier = device.identifier
                if not identifier:
                    continue
                name = edid_name(identifier) or physical[0].description or device.description
                displays.append(Display(identifier, name, handle=physical[0].handle))
            yield displays
        finally:
            for count, physical in allocated:
                self.dx.DestroyPhysicalMonitors(count, physical)

    def probe(self, display):
        value, maximum, kind = w.DWORD(), w.DWORD(), c.c_int()
        if self.dx.GetVCPFeatureAndVCPFeatureReply(display.handle, 0x60, c.byref(kind), c.byref(value), c.byref(maximum)):
            display.current_input = value.value
            display.detail = f'当前输入 {value.value:#04x}'
        else:
            display.detail = f'输入读取失败（Windows {c.get_last_error()}）；检查 DDC/CI 或专用协议'
        length = w.DWORD()
        if self.dx.GetCapabilitiesStringLength(display.handle, c.byref(length)) and 0 < length.value < 65536:
            buffer = c.create_string_buffer(length.value)
            if self.dx.CapabilitiesRequestAndCapabilitiesReply(display.handle, buffer, length):
                display.detail += '\nCapabilities: ' + buffer.value.decode('ascii', errors='replace')

    @staticmethod
    def check_protocol(protocol):
        if protocol != 'standard':
            raise RuntimeError('Windows 标准接口不能发送 LG 专用地址；需要显卡专用控制后端')

    def write(self, display, value, protocol):
        self.check_protocol(protocol)
        if not self.dx.SetVCPFeature(display.handle, 0x60, value):
            raise c.WinError(c.get_last_error())
